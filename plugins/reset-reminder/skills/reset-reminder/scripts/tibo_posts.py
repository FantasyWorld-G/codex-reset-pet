"""Read Tibo's public X profile without signing in or executing page scripts."""
from datetime import datetime
from html.parser import HTMLParser
import json
import re
import textwrap
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from check_reset import CN


HANDLE = 'thsottiaux'
PROFILE_URL = f'https://x.com/{HANDLE}'
TRANSLATE_URL = 'https://translate.googleapis.com/translate_a/single'
POST_PATH = re.compile(r'/([a-zA-Z0-9_]+)/status/([0-9]{16,20})')
MAX_HTML = 2_000_000


class ProfilePosts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles = 0
        self.permalink = None
        self.body_depth = 0
        self.body = []
        self.body_read = False
        self.posts = []

    def handle_starttag(self, tag, attributes):
        if tag == 'article':
            self.articles += 1
        if self.articles != 1:
            return
        attrs = dict(attributes)
        if self.body_depth:
            if tag == 'div':
                self.body_depth += 1
            elif tag == 'br':
                self.body.append('\n')
            return
        if tag == 'a' and self.permalink is None:
            self.permalink = POST_PATH.fullmatch(attrs.get('href') or '')
        if attrs.get('data-slot') == 'embedded-tweet-frame':
            self.body_read = True
        if (tag == 'div' and self.permalink and not self.body_read
                and self.permalink[1].lower() == HANDLE
                and (attrs.get('data-testid') == 'tweetText'
                     or (attrs.get('dir') == 'auto'
                         and 'whitespace-pre-wrap' in (attrs.get('class') or '').split()))):
            self.body_depth = 1
            self.body_read = True

    def handle_data(self, data):
        if self.articles == 1 and self.body_depth:
            self.body.append(data)

    def handle_endtag(self, tag):
        if tag == 'div' and self.articles == 1 and self.body_depth:
            self.body_depth -= 1
        if tag != 'article' or not self.articles:
            return
        self.articles -= 1
        if self.articles:
            return
        if self.permalink and self.permalink[1].lower() == HANDLE:
            self.posts.append((int(self.permalink[2]), ''.join(self.body).strip()))
        self.permalink = None
        self.body_depth = 0
        self.body = []
        self.body_read = False


def fetch_latest_post(cancel=None):
    if cancel is not None and cancel.is_set():
        raise ValueError('已取消')
    request = Request(PROFILE_URL, headers={
        'User-Agent':'Mozilla/5.0', 'Accept':'text/html',
    })
    with urlopen(request, timeout=10) as response:
        if response.geturl().rstrip('/') != PROFILE_URL:
            raise ValueError('X 主页未返回公开时间线')
        raw = response.read(MAX_HTML + 1)
    if len(raw) > MAX_HTML:
        raise ValueError('X 主页响应过大')
    if cancel is not None and cancel.is_set():
        raise ValueError('已取消')
    parser = ProfilePosts()
    parser.feed(raw.decode('utf-8'))
    parser.close()
    if not parser.posts:
        raise ValueError('X 主页未返回 Tibo 的帖子')
    post_id, body = max(parser.posts, key=lambda post:post[0])
    now = time.time()
    if not post_time(str(post_id), now):
        raise ValueError('X 帖子发布时间无效')
    return {'id':str(post_id), 'body':body, 'captured_at':now}


def translate_post(body, cancel=None):
    """Translate the public post text on demand using Google's web endpoint."""
    translated = []
    for part in textwrap.wrap(body, width=4500, replace_whitespace=False, expand_tabs=False):
        if cancel is not None and cancel.is_set():
            raise ValueError('已取消')
        form = urlencode({'client':'gtx','sl':'auto','tl':'zh-CN','dt':'t','q':part})
        request = Request(TRANSLATE_URL, data=form.encode('ascii'),
                          headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        with urlopen(request, timeout=8) as response:
            raw = response.read(512_001)
        if len(raw) > 512_000:
            raise ValueError('翻译响应过大')
        data = json.loads(raw)
        if not isinstance(data,list) or not data or not isinstance(data[0],list):
            raise ValueError('翻译响应格式无效')
        text = ''.join(row[0] for row in data[0]
                       if isinstance(row,list) and row and isinstance(row[0],str))
        if not text.strip():
            raise ValueError('翻译结果为空')
        translated.append(text)
    if not translated:
        raise ValueError('帖子正文为空')
    return '\n'.join(translated)


def post_time(post_id, now):
    if not isinstance(post_id, str) or not re.fullmatch(r'[0-9]{16,20}', post_id):
        return None
    # The X Snowflake ID includes the creation time in its upper bits.
    created = ((int(post_id) >> 22) + 1288834974657) / 1000
    return created if created <= now + 60 else None


def post_view(post, now, error=''):
    view = {'title':'Tibo 最新帖子', 'date':f'@{HANDLE}',
            'body':'等待获取 X 帖子', 'status':'', 'url':'', 'has_text':False}
    if error:
        view.update(body='暂时无法读取 X 主页，可点击「刷新帖子」重试。', status=error)
    if not isinstance(post, dict):
        return view
    post_id, body = post.get('id'), post.get('body')
    created = post_time(post_id, now)
    if created is None or not isinstance(body, str):
        return view
    captured = post.get('captured_at')
    stale = isinstance(captured, (int,float)) and now - captured > 600
    view.update(date=datetime.fromtimestamp(created,CN).strftime('%m/%d %H:%M') + f' · @{HANDLE}',
                body=body or '这条帖子没有可显示的正文，请查看原帖。',
                status=f'{error} · 显示缓存' if error else '显示缓存' if stale else '',
                url=f'{PROFILE_URL}/status/{post_id}', has_text=bool(body.strip()))
    return view
