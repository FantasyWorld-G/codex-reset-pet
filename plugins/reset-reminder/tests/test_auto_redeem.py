import copy,json,os
from pathlib import Path
import subprocess,sys,tempfile,threading,time,unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'))
import auto_redeem as auto
from refresh_usage import RefreshError,make_snapshot,save_snapshot

NOW=1792699200
ACCOUNT={'type':'chatgpt','email':'test@example.invalid','planType':'pro'}


def card(name='soon',left=900,**kwargs):
    return dict({'id':name,'expiresAt':NOW+left,'status':'available','resetType':'codexRateLimits'},**kwargs)


def limits(cards=None):
    return {'rateLimits':{'primary':{'usedPercent':60}},
            'rateLimitResetCredits':{'availableCount':len(cards or []),'credits':cards or []}}


class AutoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config=self.root/'auto-redeem.json';self.state=self.root/'auto-redeem-state.json';self.usage=self.root/'desktop-usage.json'
        self.policy={'enabled':True,'account_id':make_snapshot(ACCOUNT,limits())['usage']['accountId'],
                     'start_before':960,'stop_before':360}
        save_snapshot(self.config,self.policy)
        self.calls=[];self.clock=NOW
        self.initial=limits([card(),card('later',100000)])
        self.fresh=None;self.after=None;self.account=ACCOUNT;self.current_account=ACCOUNT
        self.outcome='reset';self.side_effect=None

    def execute(self,operation,**kwargs):
        def request(i,method,params=None):
            self.calls.append((method,params))
            if self.side_effect:self.side_effect(method,params)
            if method=='account/read':return {'account':self.current_account}
            if method=='account/rateLimits/read':
                return self.after or self.fresh or self.initial
            if method.endswith('/consume'):
                # A durable pending record must exist before every send.
                state=json.loads(self.state.read_text('utf-8'))
                self.assertEqual(state['attempts'][params['idempotencyKey']]['outcome'],'pending')
                if isinstance(self.outcome,Exception):raise self.outcome
                return {'outcome':self.outcome}
            raise AssertionError(method)
        return operation(self.account,self.initial,request)

    def run_cycle(self):
        return auto.run_cycle(self.config,self.state,self.usage,client='fake',clock=lambda:self.clock,execute=self.execute)

    def consumes(self):return [params for method,params in self.calls if method.endswith('/consume')]

    def test_exact_card_and_persistent_key_then_refresh(self):
        result=self.run_cycle()
        self.assertEqual(result['outcome'],'reset')
        self.assertEqual(len(self.consumes()),1)
        self.assertEqual(self.consumes()[0]['creditId'],'soon')
        self.assertTrue(self.consumes()[0]['idempotencyKey'])
        self.assertEqual(self.calls[-1][0],'account/rateLimits/read')
        self.run_cycle()
        self.assertEqual(len(self.consumes()),1)

    def test_default_off_and_invalid_policy_never_connect(self):
        for config in ({},{'enabled':True},dict(self.policy,enabled=False),dict(self.policy,start_before=0)):
            save_snapshot(self.config,config)
            self.assertIn('关闭',self.run_cycle()['message'])
        self.assertEqual(self.calls,[])

    def test_window_boundaries_expired_used_and_unrelated_types(self):
        for c in [card(left=961),card(left=360),card(left=0),card(left=-1),
                  card(status='used'),card(resetType='other'),card(expiresAt=None),card(id='')]:
            self.initial=limits([c])
            self.run_cycle()
        self.assertEqual(self.consumes(),[])
        self.initial=limits([card(left=960)]);self.run_cycle()
        self.assertEqual(len(self.consumes()),1)

    def test_strict_five_minute_mode(self):
        save_snapshot(self.config,dict(self.policy,start_before=300,stop_before=0))
        self.initial=limits([card(left=301)]);self.run_cycle();self.assertFalse(self.consumes())
        self.initial=limits([card(left=300)]);self.run_cycle();self.assertEqual(len(self.consumes()),1)

    def test_missing_details_cannot_use_cached_snapshot(self):
        save_snapshot(self.usage,make_snapshot(ACCOUNT,self.initial))
        self.initial['rateLimitResetCredits']={'availableCount':3}
        with self.assertRaises(RefreshError):self.run_cycle()
        self.assertFalse(self.consumes())

    def test_account_binding_and_switch_during_check(self):
        self.account=dict(ACCOUNT,email='different@example.invalid')
        with self.assertRaises(RefreshError):self.run_cycle()
        self.account=ACCOUNT;self.current_account=dict(ACCOUNT,email='different@example.invalid')
        with self.assertRaises(RefreshError):self.run_cycle()
        self.assertFalse(self.consumes())

    def test_clock_or_credit_change_before_send_skips(self):
        def advance(method,params):
            if method=='account/rateLimits/read':self.clock=NOW+600
        self.side_effect=advance;self.run_cycle();self.assertFalse(self.consumes())
        self.side_effect=None;self.clock=NOW
        for c in (card(status='used'),card(left=99999)):
            self.fresh=limits([c]);self.run_cycle()
        self.assertFalse(self.consumes())

    def test_disable_while_request_running_skips(self):
        def disable(method,params):save_snapshot(self.config,dict(self.policy,enabled=False))
        self.side_effect=disable
        self.run_cycle();self.assertFalse(self.consumes())

    def test_timeout_retry_reuses_same_id_and_never_selects_another_card(self):
        self.outcome=RefreshError('timeout')
        with self.assertRaises(RefreshError):self.run_cycle()
        original=dict(self.consumes()[0]);self.outcome='alreadyRedeemed'
        self.run_cycle()
        self.assertEqual(self.consumes(),[original,original])
        self.run_cycle();self.assertEqual(len(self.consumes()),2)

    def test_unknown_result_missing_credit_blocks_other_cards(self):
        self.outcome=RefreshError('timeout')
        with self.assertRaises(RefreshError):self.run_cycle()
        self.initial=limits([card('other',800)])
        result=self.run_cycle()
        self.assertIn('待核实',result['message'])
        self.assertEqual(len(self.consumes()),1)

    def test_nothing_to_reset_retries_same_key_inside_window_only(self):
        self.outcome='nothingToReset';self.run_cycle();self.run_cycle()
        self.assertEqual(self.consumes()[0],self.consumes()[1])
        self.clock=NOW+600;self.run_cycle();self.assertEqual(len(self.consumes()),2)

    def test_no_credit_is_not_success_or_fallback(self):
        self.outcome='noCredit';result=self.run_cycle();self.run_cycle()
        self.assertEqual(result['outcome'],'noCredit')
        self.assertEqual(len(self.consumes()),1)

    def test_corrupt_journal_and_write_failure_prevent_consume(self):
        self.state.write_text('{broken','utf-8')
        with self.assertRaises(RefreshError):self.run_cycle()
        self.state.unlink()
        original=auto.save_snapshot
        def fail(path,value):
            if path==self.state:raise OSError('disk full')
            original(path,value)
        with patch.object(auto,'save_snapshot',fail):
            with self.assertRaises(OSError):self.run_cycle()
        self.assertFalse(self.consumes())

    def test_concurrent_cycle_cannot_enter(self):
        with auto.CreditLock(self.state.with_suffix('.lock')):
            with self.assertRaises(RefreshError):self.run_cycle()
        self.assertFalse(self.consumes())

    def test_legacy_cli_schema_never_selected(self):
        with patch.object(auto,'candidates',return_value=[sys.executable]),patch.object(auto,'supports_exact_credit',return_value=False):
            with self.assertRaises(RefreshError):auto.exact_credit_client()

    def test_real_transport_sends_exact_credit_and_reaps_child(self):
        import refresh_usage
        original=subprocess.Popen;processes=[];capture=self.root/'consume.json'
        def start(command,**kwargs):
            process=original([sys.executable,'-u',str(Path(__file__).with_name('fake_account_server.py')),
                              'auto',str(capture)],**kwargs)
            processes.append(process);return process
        with patch.object(refresh_usage.subprocess,'Popen',start):
            result=auto.run_cycle(self.config,self.state,self.usage,client='fixture',clock=lambda:NOW)
        self.assertEqual(result['outcome'],'reset')
        sent=json.loads(capture.read_text('utf-8'))
        self.assertEqual(sent['creditId'],'soon')
        self.assertTrue(sent['idempotencyKey'])
        self.assertTrue(all(p.poll() is not None for p in processes))

    @unittest.skipUnless(os.name=='nt','Windows native UI')
    def test_ui_enroll_disable_and_background_poll(self):
        result=subprocess.run([sys.executable,__file__,'--ui',str(self.root)],capture_output=True,
                              text=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)


def ui_worker(folder):
    import desktop_pet as pet
    root=Path(folder)
    # The process uses mocks exclusively; never contact a real account in tests.
    (root/'auto-redeem.json').unlink(missing_ok=True)
    app=pet.Companion(root/'usage.json',root/'settings.json',tibo_enabled=False)
    errors=[];checks=[]
    app.root.report_callback_exception=lambda kind,value,tb:errors.append(str(value))
    def enroll(operation,**kw):return operation(ACCOUNT,limits([card()]),None)
    def cycle(*args):
        checks.append(1)
        return {'message':'自动使用：等待临期窗口','delay':300}
    phase=0
    def verify():
        nonlocal phase
        try:
            if app.auto_busy or not checks:app.root.after(50,verify);return
            assert not errors,errors
            assert auto.valid_policy(app.auto_policy)
            app.expanded=True;app.draw();app.root.update_idletasks()
            bounds=app.canvas.bbox(app.auto_status_item)
            assert bounds[2]<=350 and bounds[3]<296,bounds
            assert len(app.frame_times)>10
            app.disable_auto()
            assert not auto.valid_policy(auto.read_config(app.auto_config_path))
            app.close()
        except Exception as error:errors.append(str(error));app.close()
    with patch.object(pet,'exact_credit_client',return_value='fake'),patch.object(pet,'account_operation',enroll),patch.object(pet,'run_cycle',cycle):
        app.enable_auto(960,360)
        app.root.after(1100,verify)
        app.root.after(8000,lambda:(errors.append('timeout'),app.close()))
        app.root.mainloop()
        if app.auto_thread:app.auto_thread.join(timeout=2)
    if errors:raise AssertionError(errors)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--ui':ui_worker(sys.argv[2])
    else:unittest.main()
