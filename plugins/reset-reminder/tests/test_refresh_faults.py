"""Refresh failures with real child processes and isolated native UI workers."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'
FIXTURE = Path(__file__).with_name('fake_account_server.py')
sys.path.insert(0,str(SCRIPTS))
import refresh_usage as refresh
import desktop_pet as pet

REAL_POPEN = subprocess.Popen


def fixture_factory(mode, processes):
    def start(command, **kwargs):
        process = REAL_POPEN([sys.executable,'-u',str(FIXTURE),mode],**kwargs)
        processes.append(process)
        return process
    return start


class RefreshFaultTests(unittest.TestCase):
    def fetch(self,mode,**kwargs):
        processes=[]
        try:
            with patch.object(refresh.subprocess,'Popen',fixture_factory(mode,processes)):
                return refresh.fetch_snapshot(executable='fixture',**kwargs)
        finally:
            for process in processes:
                try:
                    self.assertIsNotNone(process.poll(),'Refresh leaked its account-server process')
                finally:
                    if process.poll() is None:
                        process.kill();process.wait(timeout=3)

    def test_offline_then_reconnect(self):
        with self.assertRaisesRegex(refresh.RefreshError,'网络'):
            self.fetch('offline')
        self.assertEqual(self.fetch('success')['usage']['rateLimits']['primary']['usedPercent'],40)

    def test_server_disconnect(self):
        with self.assertRaisesRegex(refresh.RefreshError,'断开'):
            self.fetch('disconnect')

    def test_timeout_is_bounded_and_next_request_recovers(self):
        started=time.monotonic()
        with self.assertRaisesRegex(refresh.RefreshError,'超时'):
            self.fetch('timeout',timeout=.4)
        self.assertLess(time.monotonic()-started,4)
        self.assertEqual(self.fetch('success')['source'],'codex-app-server')

    def test_cancellation_reaps_child(self):
        cancel=threading.Event()
        timer=threading.Timer(.3,cancel.set)
        timer.start()
        started=time.monotonic()
        try:
            with self.assertRaisesRegex(refresh.RefreshError,'取消'):
                self.fetch('timeout',cancel=cancel)
        finally:
            timer.cancel()
        self.assertLess(time.monotonic()-started,4)

    def test_invalid_encoding_does_not_leave_an_unhandled_reader_exception(self):
        errors=[]
        with patch.object(threading,'excepthook',lambda args:errors.append(args.exc_value)):
            with self.assertRaises(refresh.RefreshError):
                self.fetch('invalid_encoding')
        self.assertEqual(errors,[])

    def test_invalid_quota_and_signed_out_are_not_successes(self):
        for mode in ('bad_quota','signed_out'):
            with self.subTest(mode=mode),self.assertRaises(refresh.RefreshError):
                self.fetch(mode)

    def test_noisy_protocol_recovers(self):
        self.assertEqual(self.fetch('noisy')['source'],'codex-app-server')

    def test_launch_failure_is_actionable(self):
        with patch.object(refresh.subprocess,'Popen',side_effect=FileNotFoundError):
            with self.assertRaisesRegex(refresh.RefreshError,'无法启动'):
                refresh.fetch_snapshot(executable='missing')

    def test_disk_write_failure_preserves_last_snapshot_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'desktop-usage.json'
            target.write_text('last good snapshot')
            with patch.object(refresh.os,'replace',side_effect=PermissionError('locked')):
                with self.assertRaises(OSError):
                    refresh.save_snapshot(target,{'captured_at':'new'})
            self.assertEqual(target.read_text(),'last good snapshot')
            self.assertEqual(list(Path(directory).glob('*.tmp')),[])

    @unittest.skipUnless(os.name=='nt','Native Windows UI')
    def test_ui_offline_reconnect_timeout_disk_failure_and_duplicate_clicks(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,__file__,'--ui',directory],
                capture_output=True,text=True,encoding='utf-8',timeout=25)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('"scenarios": 6',result.stdout)

    @unittest.skipUnless(os.name=='nt','Native Windows UI')
    def test_close_waits_for_cancelled_refresh_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,__file__,'--close',directory],
                capture_output=True,text=True,encoding='utf-8',timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            self.assertTrue((Path(directory)/'cleanup-complete').exists(),
                            'Closing the UI abandoned the refresh cleanup')
            self.assertFalse((Path(directory)/'desktop-usage.json').exists())


def close_worker(directory):
    # A delayed cleanup models the child-process reaping in fetch_snapshot's finally.
    # No real account process is spawned in this exit-regression case.
    ready=threading.Event()
    def fetch(cancel):
        ready.set()
        try:
            cancel.wait(5)
            raise refresh.RefreshError('已取消刷新')
        finally:
            time.sleep(.3)
            (Path(directory)/'cleanup-complete').write_text('done')
    app=pet.Companion(Path(directory)/'usage.json',Path(directory)/'settings.json',tibo_enabled=False,quota_auto_refresh=False,sound_enabled=False)
    def close_when_ready():
        if ready.is_set():app.close()
        else:app.root.after(10,close_when_ready)
    with patch.object(pet,'fetch_snapshot',fetch):
        app.refresh_usage()
        app.root.after(10,close_when_ready)
        app.root.mainloop()


def ui_worker(directory):
    folder=Path(directory)
    original={'captured_at':pet.datetime.now(pet.CN).isoformat(),'usage':{
        'accountId':'test','rateLimits':{'primary':{'usedPercent':25,'resetsAt':time.time()+7200}}}}
    refresh.save_snapshot(folder/'usage.json',original)
    refresh.save_snapshot(folder/'desktop-usage.json',original)
    app=pet.Companion(folder/'usage.json',folder/'settings.json',tibo_enabled=False,quota_auto_refresh=False,sound_enabled=False)
    app.expanded=True;app.draw()
    errors=[];processes=[];calls=[];completed=[];beats=[]
    app.root.report_callback_exception=lambda kind,value,tb:errors.append(str(value))
    modes=iter(('offline','success','timeout','success','disk','success'))
    real_save=refresh.save_snapshot
    state={}
    def fetch(cancel):
        mode=state['mode'];calls.append(mode)
        with patch.object(refresh.subprocess,'Popen',fixture_factory('success' if mode=='disk' else mode,processes)):
            return refresh.fetch_snapshot(cancel=cancel,timeout=.7 if mode=='timeout' else 3,executable='fixture')
    def save(path,snapshot):
        if state['mode']=='disk':raise PermissionError('simulated locked cache')
        return real_save(path,snapshot)
    def heartbeat():
        beats.append(time.monotonic())
        app.root.after(20,heartbeat)
    def begin():
        try:mode=next(modes)
        except StopIteration:
            assert not errors,errors
            assert all(p.poll() is not None for p in processes)
            assert len(calls)==6,calls
            print(json.dumps({'scenarios':len(completed),'ui_heartbeats':len(beats),'child_processes_reaped':len(processes)}),flush=True)
            app.close();return
        state.update(mode=mode,before=app.manual_usage.read_bytes(),percent=app.model['remaining_percent'],beat=len(beats),started=time.monotonic())
        app.refresh_button.invoke()
        assert app.refresh_button['state']=='disabled'
        for _ in range(20):app.refresh_usage()
        # Rebuilding the bubble while I/O is pending must preserve busy state.
        app.collapse();app.toggle()
        assert app.refresh_button['state']=='disabled'
        app.root.after(50,verify)
    def verify():
        try:
            assert time.monotonic()-state['started']<6,'Stuck refresh button'
            if app.refresh_busy:
                app.root.after(50,verify);return
            assert app.refresh_button['state']=='normal'
            assert len(beats)>state['beat']+3,'UI event loop blocked'
            assert not errors,errors
            if state['mode']=='success':
                assert app.model['remaining_percent']==60
                assert app.refresh_message=='额度刷新成功'
            else:
                assert app.manual_usage.read_bytes()==state['before']
                assert app.model['remaining_percent']==state['percent']
                assert app.refresh_message!='额度刷新成功'
            completed.append(state['mode'])
            begin()
        except Exception as error:
            errors.append(str(error));app.close()
    with patch.object(pet,'fetch_snapshot',fetch),patch.object(pet,'save_snapshot',save):
        app.root.after(10,heartbeat)
        app.root.after(50,begin)
        app.root.mainloop()
    if errors:raise AssertionError(errors)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--close':close_worker(sys.argv[2])
    elif len(sys.argv)>1 and sys.argv[1]=='--ui':ui_worker(sys.argv[2])
    else:unittest.main()
