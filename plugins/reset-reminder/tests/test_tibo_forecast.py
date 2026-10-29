import copy,json,os
from pathlib import Path
import subprocess,sys,tempfile,threading,time,unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'))
import tibo_forecast as tibo
import desktop_pet as pet

NOW=1792692000

def snapshot(now=NOW):
    return {'captured_at':now,'forecast':{'updated_at':now,'last_reset_at':now-86400,
        'probabilities':{'model_24h':32,'model_48h':53},
        'official_signal':{'at':now-60,'signal_type':'dated_commitment','window':{
            'start_at':now-60,'end_at':now+3600,'target_at':now+3600,'target_kind':'deadline'}}}}


class TiboTests(unittest.TestCase):
    def test_structured_deadline_has_beijing_clock_and_countdown(self):
        view=tibo.forecast_view(snapshot(),NOW)
        self.assertEqual(view['state'],'scheduled')
        self.assertEqual(view['seconds'],3600)
        self.assertEqual(view['date'],tibo.clock_label(NOW+3600)+' 前')
        self.assertIn('预估',view['detail'])

    def test_target_elapsed_never_means_account_reset(self):
        view=tibo.forecast_view(snapshot(),NOW+3601)
        self.assertEqual(view['state'],'expired')
        self.assertIn('等待确认',view['remaining'])

    def test_center_target_reached_before_window_ends(self):
        data=snapshot();window=data['forecast']['official_signal']['window']
        window.update(target_kind='center',target_at=NOW+600)
        view=tibo.forecast_view(data,NOW+700)
        self.assertEqual(view['state'],'reached')
        self.assertTrue(view['date'].endswith('左右'))

    def test_probabilities_and_relative_pst_text_never_become_deadlines(self):
        data=snapshot()
        data['forecast']['official_signal']={'signal_type':'promise','at':NOW-60,
                                             'summary':'Tomorrow before 10am PST'}
        view=tibo.forecast_view(data,NOW)
        self.assertIsNone(view['deadline'])
        self.assertEqual(view['date'],'暂无明确预告')
        self.assertIn('24h 32%',view['detail'])

    def test_invalid_windows_do_not_create_countdowns(self):
        for changes in ({'target_at':NOW+5000},{'target_at':NOW+600},
                        {'target_at':1e300,'end_at':1e300},
                        {'end_at':'2026-10-23T10:00:00'},{'target_kind':'probability'}):
            with self.subTest(changes=changes):
                data=snapshot();data['forecast']['official_signal']['window'].update(changes)
                self.assertIsNone(tibo.forecast_view(data,NOW)['deadline'])

    def test_new_observed_reset_supersedes_old_estimate(self):
        data=snapshot();data['forecast']['last_reset_at']=NOW
        data['forecast']['latest_alert']={'kind':'reset','state':'confirmed','observed_at':NOW,
                                         'confirmation_source':'operator_observed'}
        view=tibo.forecast_view(data,NOW)
        self.assertIsNone(view['deadline'])
        self.assertEqual(view['state'],'observed')
        self.assertIn('本账户以额度刷新为准',view['detail'])

    def test_stale_or_failed_data_is_explicitly_cached(self):
        for now,failed in ((NOW,True),(NOW+3601,False)):
            view=tibo.forecast_view(snapshot(),now,failed)
            self.assertIn('缓存',view['title'])
            self.assertTrue('失败' in view['status'] or '过期' in view['status'])

    def test_invalid_snapshot_is_unavailable(self):
        for data in (None,[],{}, {'captured_at':NOW+120,'forecast':{'updated_at':NOW}},
                     {'captured_at':NOW,'forecast':{'updated_at':-1e300}}):
            self.assertEqual(tibo.forecast_view(data,NOW)['state'],'unavailable')

    def test_fetch_only_contacts_public_endpoint_and_rejects_stale_response(self):
        class Response:
            def __init__(self,data):self.data=data
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return json.dumps(self.data).encode()
        for now,valid in ((time.time(),True),(time.time()-7200,False)):
            data=snapshot(now)['forecast']
            with patch.object(tibo,'urlopen',return_value=Response(data)) as request:
                if valid:
                    self.assertIn('forecast',tibo.fetch_forecast())
                else:
                    with self.assertRaises(ValueError):tibo.fetch_forecast()
                arg=request.call_args_list[0].args[0]
                self.assertEqual(arg.full_url,tibo.FORECAST_URL)
                self.assertIsNone(arg.data)
                self.assertNotIn('Authorization',arg.headers)

    def test_history_selects_completed_reset_not_teaser_or_banked_grant(self):
        base={'id':'1','type':'reset','confirmed':True,'announced_at':NOW-60}
        events=[base,dict(base,id='2',announced_at=NOW,confirmed=False),
                dict(base,id='3',announced_at=NOW,banked_grant=True),
                dict(base,id='4',announced_at=NOW,preview=True),
                dict(base,id='5',announced_at=NOW+60),None]
        self.assertEqual(tibo.latest_reset(events,NOW)['id'],'1')

    def test_history_observation_and_categories_are_not_official_reason(self):
        data=snapshot();data['last_reset']={'at':NOW-1,'source':'operator-observed',
            'confirmed':True,'reason_tags':['incident','compensation'],
            'url':'https://x.com/thsottiaux/status/123'}
        view=tibo.forecast_view(data,NOW)
        self.assertEqual(view['last_date'],tibo.clock_label(NOW-1))
        self.assertIn('暂无',view['last_reason'])
        self.assertIn('事故相关',view['last_category'])
        self.assertIn('待 Tibo 确认',view['last_status'])
        self.assertEqual(view['last_url'],data['last_reset']['url'])
        self.assertEqual(view['state'],'scheduled') # History survives a new forecast.

    def test_newer_reset_never_inherits_old_reason(self):
        data=snapshot();data['forecast']['last_reset_at']=NOW
        data['last_reset']={'at':NOW-10,'reason_tags':['incident'],'url':'https://x.com/u/status/123'}
        view=tibo.forecast_view(data,NOW)
        self.assertEqual(view['last_category'],'网站分类：暂无')
        self.assertEqual(view['last_url'],'')
        self.assertEqual(view['last_date'],tibo.clock_label(NOW))

    def test_source_links_are_only_public_post_urls(self):
        for url in ('javascript:alert(1)','file:///c:/secret','https://x.com.evil/u/status/12',None):
            self.assertEqual(tibo.source_url(url),'')
        self.assertEqual(tibo.source_url('https://x.com/u/status/123'),'https://x.com/u/status/123')

    def test_timeline_outage_does_not_discard_forecast(self):
        with patch.object(tibo,'public_json',side_effect=[snapshot(time.time())['forecast'],OSError('offline')]):
            data=tibo.fetch_forecast()
        self.assertTrue(data['history_error'])
        view=tibo.forecast_view(data,time.time())
        self.assertEqual(view['state'],'scheduled')
        self.assertIn('历史获取失败',view['last_category'])
        self.assertIn('待获取',view['last_reason'])

    def test_history_fetch_and_stale_label(self):
        now=time.time();event={'id':'1','type':'reset','confirmed':True,
            'announced_at':now-10,'reason_tags':[]}
        with patch.object(tibo,'public_json',side_effect=[snapshot(now)['forecast'],
                {'updated_at':now,'events':[event]}]) as request:
            data=tibo.fetch_forecast()
        self.assertEqual(request.call_args.args[0],tibo.TIMELINE_URL)
        view=tibo.forecast_view(data,now+3601)
        self.assertIn('缓存',view['last_title'])
        self.assertEqual(view['last_reason'],'网站暂无原因或公告说明')

    def test_announcement_text_is_retained_and_not_replaced_with_unknown_reason(self):
        event={'type':'reset','confirmed':True,'announced_at':NOW-1,
               'summary':'English announcement','localized_summary':'第 17 天，今天是重置日。',
               'reason_tags':['incident']}
        data=snapshot();data['last_reset']=tibo.latest_reset([event],NOW)
        view=tibo.forecast_view(data,NOW)
        self.assertEqual(view['last_announcement'],event['localized_summary'])
        self.assertEqual(view['last_reason'],'网站说明：'+event['localized_summary'])
        self.assertNotIn('补偿',view['last_reason'])
        data['forecast']['last_reset_at']=NOW
        self.assertEqual(tibo.forecast_view(data,NOW)['last_announcement'],'')

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
    folder=Path(directory);app=pet.Companion(folder/'usage.json',folder/'settings.json',tibo_enabled=False)
    app.expanded=True
    app.tibo_snapshot=snapshot(time.time())
    app.tibo_snapshot['last_reset']={'at':time.time()-60,'source':'operator-observed',
        'confirmed':True,'reason_tags':list(tibo.REASON_TAGS),
        'announcement':'第 17 天，今天是重置日。'+'这里是网站提供的公告说明。'*40,
        'url':'https://x.com/thsottiaux/status/123'}
    app.tibo_model=tibo.forecast_view(app.tibo_snapshot,time.time())
    app.draw();app.root.update()
    errors=[];calls=[];release=threading.Event()
    app.root.report_callback_exception=lambda kind,value,tb:errors.append(str(value))
    def fetch(cancel):
        calls.append(1)
        release.wait(2)
        if len(calls)==1:raise OSError('simulated offline')
        return snapshot(time.time())
    def verify_layout():
        boxes=[app.canvas.bbox(i) for i in app.tibo_items]
        for i,box in enumerate(boxes):
            assert box[0]>=20 and box[2]<=350,box
            if i<4:assert box[3]<boxes[i+1][1],boxes
        assert boxes[0][2]<264,boxes[0]
        assert boxes[-1][3]<428,boxes[-1]
        assert app.tibo_refresh_button.winfo_ismapped()
        assert app.canvas.bbox(app.footer_item)[1]>=439
        history=[app.canvas.bbox(i) for i in app.tibo_history_items]
        for i,box in enumerate(history):
            assert box[0]>=20 and box[2]<=350,box
            if i<4:assert box[3]<history[i+1][1],history
        assert history[0][2]<264
        assert 436<=history[0][1] and history[-1][3]<566
        assert app.canvas.bbox(app.footer_item)[1]>566
        assert app.tibo_source_button.winfo_ismapped()
    verify_layout()
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
            if app.tibo_busy:app.root.after(50,verify);return
            assert not errors,errors
            assert app.tibo_refresh_button['state']=='normal'
            verify_layout()
            if phase==0:
                assert app.tibo_failed
                assert app.tibo_model['deadline'] is not None
                assert '缓存' in app.tibo_model['title']
                assert len(calls)==1
                phase=1;app.refresh_tibo();app.root.after(50,verify);return
            assert not app.tibo_failed
            assert len(calls)==2
            assert app.tibo_path.exists()
            assert not app.usage.exists(),'Public forecast touched official account data'
            assert not app.manual_usage.exists()
            assert len(app.frame_times)>10
            print('TIBO_UI_PASSED',flush=True);app.close()
        except Exception as error:
            errors.append(str(error));app.close()
    with patch.object(pet,'fetch_forecast',fetch):
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
