import errno
import os
from pathlib import Path
import subprocess,sys,tempfile,threading,time,traceback,unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'))
import tibo_history as tibo
import tibo_posts as posts
import desktop_pet as pet

NOW=1792692000

def history(now=NOW):
    return {'captured_at':now,'updated_at':now,'last_reset':{
        'at':now-60,'source':'operator-observed','confirmed':True}}


def post(now=NOW, body='New post'):
    return {'id':str((int(now*1000)-1288834974657)<<22),'body':body,'captured_at':now}


class TiboTests(unittest.TestCase):
    def test_latest_public_x_post_ignores_old_pins_and_quoted_posts(self):
        older=post(NOW-3600)['id']
        newest=post()['id']
        foreign=post(NOW+1)['id']
        html=f"""
            <article><a href="/thsottiaux/status/{older}">Pinned</a>
              <div dir="auto" class="whitespace-pre-wrap">Old post</div></article>
            <article><a href="/other/status/{foreign}">Other</a>
              <a href="/thsottiaux/status/{foreign}">Quoted</a></article>
            <article><a href="/thsottiaux/status/{newest}">Latest</a>
              <div dir="auto" class="whitespace-pre-wrap"><span>Nothing about resets &amp; more</span><br>Second line</div>
              <div data-slot="embedded-tweet-frame"><div dir="auto" class="whitespace-pre-wrap">Quote</div></div>
            </article>"""
        with patch.object(posts,'urlopen') as request, patch.object(posts.time,'time',return_value=NOW):
            response=request.return_value.__enter__.return_value
            response.geturl.return_value=posts.PROFILE_URL
            response.read.return_value=html.encode()
            result=posts.fetch_latest_post()
        self.assertEqual(result['id'],newest)
        self.assertEqual(result['body'],'Nothing about resets & more\nSecond line')
        self.assertEqual(request.call_args.args[0].full_url,posts.PROFILE_URL)
        self.assertNotIn('Authorization',request.call_args.args[0].headers)
        view=posts.post_view(result,NOW)
        self.assertEqual(view['date'],tibo.clock_label(NOW)+' · @thsottiaux')
        self.assertEqual(view['url'],posts.PROFILE_URL+'/status/'+newest)

    def test_media_post_does_not_take_body_from_quoted_author(self):
        parser=posts.ProfilePosts()
        post_id=post()['id']
        parser.feed(f"""<article><a href="/thsottiaux/status/{post_id}">Latest</a>
            <div data-slot="embedded-tweet-frame">
              <div class="whitespace-pre-wrap" dir="auto">Someone else's quote</div>
            </div></article>""")
        self.assertEqual(parser.posts,[(int(post_id),'')])

    def test_login_or_empty_profile_is_a_fetch_failure(self):
        with patch.object(posts,'urlopen') as request:
            response=request.return_value.__enter__.return_value
            for url in ('https://x.com/i/flow/login',posts.PROFILE_URL):
                response.geturl.return_value=url
                response.read.return_value=b'<html>Please log in</html>'
                with self.assertRaises(ValueError):posts.fetch_latest_post()

    def test_cached_post_retained_when_x_is_unavailable(self):
        view=posts.post_view(post(),NOW,'无网络连接')
        self.assertEqual(view['body'],'New post')
        self.assertEqual(view['status'],'无网络连接 · 显示缓存')
        self.assertIn('缓存',posts.post_view(post(),NOW+601)['status'])
        self.assertEqual(posts.post_view(None,NOW,'连接失败')['url'],'')

    def test_network_errors_have_distinct_messages(self):
        for error, message in (
            (URLError(OSError(errno.ENETDOWN,'offline')), '无网络连接'),
            (URLError(ConnectionRefusedError()), '连接失败'),
            (URLError(TimeoutError()), '连接超时'),
            (HTTPError(posts.PROFILE_URL,503,'Unavailable',None,None), '获取失败'),
        ):
            with self.subTest(error=error):
                self.assertEqual(pet.connection_message(error),message)

    def test_history_selects_completed_reset_not_teaser_or_banked_grant(self):
        base={'id':'1','type':'reset','confirmed':True,'announced_at':NOW-60}
        events=[base,dict(base,id='2',announced_at=NOW,confirmed=False),
                dict(base,id='3',announced_at=NOW,banked_grant=True),
                dict(base,id='4',announced_at=NOW,preview=True),
                dict(base,id='5',announced_at=NOW+60),None]
        self.assertEqual(tibo.latest_reset(events,NOW)['id'],'1')

    def test_history_observation_and_categories_are_not_official_reason(self):
        data=history();data['last_reset']={'at':NOW-1,'source':'operator-observed',
            'confirmed':True,'reason_tags':['incident','compensation'],
            'url':'https://x.com/thsottiaux/status/123'}
        view=tibo.history_view(data,NOW)
        self.assertEqual(view['last_date'],tibo.clock_label(NOW-1))
        self.assertIn('暂无',view['last_reason'])
        self.assertIn('事故相关',view['last_category'])
        self.assertIn('待 Tibo 确认',view['last_status'])
        self.assertEqual(view['last_url'],data['last_reset']['url'])

    def test_source_links_are_only_public_post_urls(self):
        for url in ('javascript:alert(1)','file:///c:/secret','https://x.com.evil/u/status/12',None):
            self.assertEqual(tibo.source_url(url),'')
        self.assertEqual(tibo.source_url('https://x.com/u/status/123'),'https://x.com/u/status/123')

    def test_history_fetch_and_stale_label(self):
        now=time.time();event={'id':'1','type':'reset','confirmed':True,
            'announced_at':now-10,'reason_tags':[]}
        with patch.object(tibo,'public_json',return_value={'updated_at':now,'events':[event]}) as request:
            data=tibo.fetch_history()
        self.assertEqual(request.call_args.args[0],tibo.TIMELINE_URL)
        view=tibo.history_view(data,now+3601)
        self.assertIn('缓存',view['last_title'])
        self.assertEqual(view['last_reason'],'网站暂无原因或公告说明')

    def test_announcement_text_is_retained_and_not_replaced_with_unknown_reason(self):
        event={'type':'reset','confirmed':True,'announced_at':NOW-1,
               'summary':'English announcement','localized_summary':'第 17 天，今天是重置日。',
               'reason_tags':['incident']}
        data=history();data['last_reset']=tibo.latest_reset([event],NOW)
        view=tibo.history_view(data,NOW)
        self.assertEqual(view['last_announcement'],event['localized_summary'])
        self.assertEqual(view['last_reason'],'网站说明：'+event['localized_summary'])
        self.assertNotIn('补偿',view['last_reason'])

    def test_missing_translation_falls_back_and_malformed_text_is_ignored(self):
        self.assertEqual(tibo.announcement_text({'localized_summary':None,'summary':' Reset\n day '}),'Reset day')
        self.assertEqual(tibo.announcement_text({'localized_summary':{},'summary':42}),'')
        self.assertEqual(len(tibo.announcement_text({'summary':'a'*5000})),4000)

    @unittest.skipUnless(os.name=='nt','Native Windows UI')
    def test_ui_layout_failure_and_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,__file__,'--ui',directory],capture_output=True,
                                  text=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('TIBO_UI_PASSED',result.stdout)


def ui_worker(directory):
    folder=Path(directory);app=pet.Companion(folder/'usage.json',folder/'settings.json',tibo_enabled=False,quota_auto_refresh=False,sound_enabled=False)
    app.expanded=True
    app.tibo_snapshots={'post':post(time.time(), 'Previous post'), 'history':history(time.time())}
    app.tibo_snapshots['history']['last_reset']={'at':time.time()-60,'source':'operator-observed',
        'confirmed':True,'reason_tags':list(tibo.REASON_TAGS),
        'announcement':'第 17 天，今天是重置日。'+'这里是网站提供的公告说明。'*40,
        'url':'https://x.com/thsottiaux/status/123'}
    app.tick_tibo(time.time())
    app.draw();app.root.update()
    errors=[];calls=[];release=threading.Event()
    app.root.report_callback_exception=lambda kind,value,tb:errors.append(str(value))
    def fetch(cancel):
        calls.append(1)
        release.wait(2)
        if len(calls)==1:raise URLError(OSError(errno.ENETUNREACH,'simulated offline'))
        if len(calls)==3:raise URLError(ConnectionRefusedError())
        return post(time.time(), "Latest original text")
    def verify_layout():
        boxes=[app.canvas.bbox(i) for i in app.tibo_items[:2]]
        for i,box in enumerate(boxes):
            assert box[0]>=20 and box[2]<=350,box
            if i<len(boxes)-1:assert box[3]<boxes[i+1][1],boxes
        assert boxes[0][2]<264,boxes[0]
        assert boxes[-1][3]<349,boxes[-1]
        assert app.tibo_post_body.winfo_ismapped() and app.tibo_post_button.winfo_ismapped()
        assert app.tibo_translate_button.winfo_ismapped()
        assert app.tibo_translate_button['text']=='翻译'
        assert app.tibo_translate_button.winfo_x()+app.tibo_translate_button.winfo_width() < app.tibo_post_button.winfo_x()
        assert app.tibo_refresh_button.winfo_ismapped()
        assert app.canvas.bbox(app.footer_item)[1]>=439
        history=[app.canvas.bbox(i) for i in app.tibo_history_items]
        for i,box in enumerate(history):
            assert box[0]>=20 and box[2]<=350,box
            if i<4:assert box[3]<history[i+1][1],history
        assert history[0][2]<264
        offset=app.post_layout_offset
        assert 436+offset<=history[0][1] and history[-1][3]<566+offset
        assert app.canvas.bbox(app.footer_item)[1]>566+offset
        assert app.tibo_translate_button.winfo_y()>=app.tibo_post_frame.winfo_y()+app.tibo_post_frame.winfo_height()
        assert app.canvas.bbox(app.tibo_items[-1])[2] < app.tibo_translate_button.winfo_x()
        assert app.tibo_source_button.winfo_ismapped()
    verify_layout()
    original_height=app.tibo_post_frame.winfo_height()
    anchor_y=app.root.winfo_y()+app.post_layout_offset
    assert original_height<pet.POST_BASE_HEIGHT and not app.post_scroll.winfo_ismapped()
    app.show_history_details();app.root.update()
    dialog=app.history_dialog
    app.show_history_details()
    assert app.history_dialog is dialog
    texts=[widget for frame in dialog.winfo_children() for widget in frame.winfo_children()
           if isinstance(widget,pet.tk.Text)]
    assert len(texts)==1 and texts[0]['state']=='disabled'
    assert app.tibo_model['last_announcement'] in texts[0].get('1.0','end')
    assert '不等于官方重置原因' in texts[0].get('1.0','end')
    dialog.destroy()
    with patch.object(pet.webbrowser,'open',return_value=True) as browser:
        app.tibo_source_button.invoke()
        browser.assert_called_once_with('https://x.com/thsottiaux/status/123',new=2)
    phase=0
    def verify():
        nonlocal phase
        try:
            if app.tibo_busy or app.translation_pending:
                app.root.after(50,verify)
                return
            assert not errors,errors
            assert app.tibo_refresh_button['state']=='normal'
            verify_layout()
            if phase==0:
                assert app.tibo_errors=={'post':'无网络连接'}
                assert app.canvas.itemcget(app.tibo_items[-1],'text')=='无网络连接 · 显示缓存'
                assert app.canvas.itemcget(app.tibo_items[-1],'fill')==pet.CONNECTION_WARNING
                assert app.tibo_post_body.get('1.0','end-1c')=='Previous post'
                assert app.tibo_model['last_date']!='等待网站记录'
                assert len(calls)==1
                phase=1;app.refresh_tibo();app.root.after(50,verify);return
            if phase==2:
                assert app.canvas.itemcget(app.tibo_items[-1],'text')=='翻译失败 · 连接超时'
                assert app.tibo_post_body.get('1.0','end-1c')=='Latest original text'
                phase=3;app.tibo_translate_button.invoke();app.root.after(50,verify);return
            if phase==3:
                text=app.tibo_post_body.get('1.0','end-1c')
                assert '最新的原始文字' in text and 'Latest original text' in text
                assert translator.call_count==2
                assert app.tibo_post_frame.winfo_height()>original_height
                assert app.root.winfo_y()+app.post_layout_offset==anchor_y
                app.tibo_translate_button.invoke()
                assert translator.call_count==2
                app.tibo_snapshots['post']=post(time.time(),'Long post\n'*150)
                app.tick_tibo(time.time())
                app.update_tibo_display()
                phase=4;app.root.after(50,verify);return
            if phase==4:
                assert app.tibo_post_body.get('1.0','end-1c')=='Long post\n'*150
                assert app.tibo_post_frame.winfo_height()<=pet.POST_MAX_HEIGHT
                assert app.post_scroll.winfo_ismapped()
                app.tibo_post_body.yview_moveto(1)
                assert app.tibo_post_body.yview()[0]>0
                assert app.root.winfo_y()+app.post_layout_offset==anchor_y
                app.tibo_snapshots.clear()
                phase=5;app.refresh_tibo();app.root.after(50,verify);return
            if phase==5:
                assert app.canvas.itemcget(app.tibo_items[-1],'text')=='连接失败'
                assert '刷新帖子' in app.tibo_post_body.get('1.0','end-1c')
                assert app.tibo_post_button['state']=='disabled' and app.tibo_translate_button['state']=='disabled'
                assert app.canvas.itemcget(app.tibo_history_items[-1],'text')=='无网络连接'
                phase=6;app.refresh_tibo();app.root.after(50,verify);return
            if phase==6:
                assert not app.tibo_errors
                assert app.canvas.itemcget(app.tibo_items[-1],'text')==''
                assert app.tibo_post_body.get('1.0','end-1c')=='Latest original text'
                assert app.tibo_post_button['state']=='normal' and app.tibo_translate_button['state']=='normal'
                print('TIBO_UI_PASSED',flush=True);app.close()
                return
            assert app.tibo_errors=={'history':'连接失败'}
            assert app.tibo_post_body.get('1.0','end-1c')=='Latest original text'
            assert '缓存' in app.tibo_model['last_title']
            with patch.object(pet.webbrowser,'open',return_value=True) as browser:
                app.tibo_post_button.invoke()
                browser.assert_called_once_with(app.tibo_post_model['url'],new=2)
            assert len(calls)==2
            assert app.tibo_path.exists()
            assert not app.usage.exists(),'Public post touched official account data'
            assert not app.manual_usage.exists()
            assert len(app.frame_times)>10
            phase=2
            app.tibo_translate_button.invoke()
            assert app.tibo_translate_button['state']=='disabled'
            app.root.after(50,verify)
        except Exception:
            errors.append(traceback.format_exc());app.close()
    with patch.object(pet,'fetch_latest_post',fetch), patch.object(
            pet,'fetch_history',side_effect=[app.tibo_snapshots['history'],ConnectionRefusedError(),
                URLError(OSError(errno.ENETUNREACH,'simulated offline')),history(time.time())]), patch.object(
            pet,'translate_post',side_effect=[TimeoutError(),'最新的原始文字']) as translator:
        app.tibo_enabled=True
        app.refresh_tibo()
        for _ in range(20):app.refresh_tibo()
        assert app.tibo_refresh_button['state']=='disabled'
        app.collapse();app.toggle()
        app.root.after(300,release.set)
        app.root.after(600,verify)
        app.root.after(8000,lambda:(errors.append('UI timeout'),app.close()))
        app.root.mainloop()
        if app.tibo_thread:app.tibo_thread.join(timeout=3)
    if errors:raise AssertionError(errors)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--ui':ui_worker(sys.argv[2])
    else:unittest.main()
