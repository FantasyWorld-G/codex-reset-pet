"""Public reset history, kept separate from the latest X post."""
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import json
import re

from check_reset import CN, epoch as parse_epoch

MAX_AGE = 3600
TIMELINE_URL = 'https://codex-reset.com/api/timeline?locale=zh'
REASON_TAGS = {'incident':'事故相关','compensation':'用量补偿','milestone':'里程碑',
               'launch':'产品发布','promo':'活动赠送','unlock':'额度提升'}


def public_json(url):
    request = Request(url,headers={'User-Agent':'CodexResetPet/0.4.10','Accept':'application/json'})
    with urlopen(request,timeout=10) as response:
        raw = response.read(1_000_001)
    if len(raw)>1_000_000:
        raise ValueError('网站响应过大')
    return json.loads(raw)


def source_url(value):
    # Only open ordinary source-post URLs, never execute website-provided schemes.
    return value if isinstance(value,str) and re.fullmatch(
        r'https://(?:x\.com|twitter\.com)/[A-Za-z0-9_]+/status/[0-9]+',value) else ''


def announcement_text(event):
    for key in ('localized_summary','summary','text'):
        value=event.get(key)
        if isinstance(value,str):
            value=' '.join(value.split())
            if value:return value[:4000]
    return ''


def latest_reset(events, now):
    candidates=[]
    for event in events:
        if (not isinstance(event,dict) or event.get('type')!='reset'
                or event.get('banked_grant') or event.get('preview')):
            continue
        observed=event.get('observation_result')=='reset_observed'
        if not observed and event.get('confirmed') is not True:
            continue
        at=next((value for key in ('effective_at','observed_at','announced_at')
                 if (value:=epoch(event.get(key))) is not None),None)
        if at is not None and at<=now:
            clean={key:event.get(key) for key in ('id','url','source','confirmed','reason_tags',
                   'observation_result','reset_verification_status')}
            clean['at']=at
            clean['announcement']=announcement_text(event)
            candidates.append(clean)
    return max(candidates,key=lambda e:e['at'],default=None)


def epoch(value):
    """Reject timestamps that cannot be rendered on the current platform."""
    try:
        result = parse_epoch(value)
        if result is not None:
            datetime.fromtimestamp(result,CN)
        return result
    except (ValueError,TypeError,OverflowError,OSError):
        return None


def fetch_history(cancel=None):
    if cancel is not None and cancel.is_set():
        raise ValueError('已取消')
    timeline = public_json(TIMELINE_URL)
    now = datetime.now(timezone.utc).timestamp()
    updated = epoch(timeline.get('updated_at')) if isinstance(timeline, dict) else None
    if (updated is None or not -60 <= now-updated <= MAX_AGE
            or not isinstance(timeline.get('events'), list)):
        raise ValueError('网站历史格式无效或已过期')
    if cancel is not None and cancel.is_set():
        raise ValueError('已取消')
    return {'captured_at':now,'updated_at':updated,'last_reset':latest_reset(timeline['events'],now)}


def clock_label(value):
    return datetime.fromtimestamp(value,CN).strftime('%m/%d %H:%M')


def history_view(snapshot, now, error=''):
    view={'last_title':'上次 Tibo 重置','last_date':'等待网站记录',
          'last_reason':'网站暂无原因或公告说明','last_category':'网站分类：暂无',
          'last_status':'网站记录不代表本账户已到账','last_url':'','last_announcement':''}
    if error:
        view.update(last_date='暂无法获取',last_reason='可点击「刷新帖子」重试',
                    last_category='',last_status=error)
    if not isinstance(snapshot,dict):
        return view
    updated=epoch(snapshot.get('updated_at'))
    if updated is None or updated>now+60:
        return view
    event=snapshot.get('last_reset')
    at=epoch(event.get('at')) if isinstance(event,dict) else None
    if at is None or at>now:
        return view
    view.update(last_date=clock_label(at),last_url=source_url(event.get('url')),
                last_reason='网站暂无原因或公告说明',last_category='网站分类：暂无')
    tags=event.get('reason_tags')
    labels=[REASON_TAGS[t] for t in tags if isinstance(t,str) and t in REASON_TAGS] if isinstance(tags,list) else []
    if labels:
        labels=list(dict.fromkeys(labels))
        view['last_category']='网站分类：'+' / '.join(labels[:2])+(' 等' if len(labels)>2 else '')
    announcement=event.get('announcement')
    if isinstance(announcement,str) and announcement.strip():
        view['last_announcement']=' '.join(announcement.split())[:4000]
        view['last_reason']='网站说明：'+view['last_announcement']
    observed=event.get('source') in ('operator-observed','operator_observed')
    view['last_status']=('网站观测 · 待 Tibo 确认' if observed else
                         '社区已确认 · 非本账户到账确认' if event.get('confirmed') is True else
                         '网站历史记录 · 等待核实')
    if error or now-updated>MAX_AGE:
        view['last_title']+=' · 缓存'
        view['last_status']=(error or '缓存待更新')+' · '+view['last_status']
    return view
