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
sys.path.insert(0, str(SCRIPTS))
from quota_refresh import QuotaRefresh


class QuotaScheduleTests(unittest.TestCase):
    def test_start_interval_and_resume_do_not_catch_up_with_a_burst(self):
        now = [10.]
        schedule = QuotaRefresh(clock=lambda: now[0])
        self.assertTrue(schedule.due())
        self.assertFalse(schedule.due(busy=True))
        schedule.complete(True)
        now[0] = 309
        self.assertFalse(schedule.due())
        now[0] = 310
        self.assertTrue(schedule.due())
        now[0] += 10000
        self.assertTrue(schedule.due())
        schedule.complete(True)
        self.assertFalse(schedule.due())
        self.assertEqual(schedule.next_due, now[0]+300)

    def test_retry_backoff_recovery_and_explicit_off(self):
        schedule = QuotaRefresh(clock=lambda: 100)
        for delay in (30, 60, 120, 240, 300, 300):
            schedule.complete(False, 'offline')
            self.assertEqual(schedule.next_due, 100+delay)
        self.assertEqual(schedule.last_error, 'offline')
        schedule.complete(True)
        self.assertEqual((schedule.failures, schedule.last_error), (0, ''))
        schedule.set_enabled(False)
        self.assertFalse(schedule.due())
        schedule.set_enabled(True)
        self.assertTrue(schedule.due())

    @unittest.skipUnless(os.name == 'nt', 'Windows desktop integration')
    def test_desktop_defaults_polling_faults_persistence_and_no_redemption(self):
        result = subprocess.run([sys.executable, __file__, '--ui-worker'], capture_output=True,
                                text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('automatic-quota-ok', result.stdout)


def ui_worker():
    import desktop_pet as pet
    from animation_state import State
    from test_desktop_pet import snapshot
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        # Old preferences deliberately lack the new key; upgrading defaults on.
        settings = folder/'settings.json'
        settings.write_text('{"sound_enabled":false,"expanded":true}')
        now = [100.]
        calls, mode = [], ['success']
        gate = threading.Event()
        gate.set()
        def fetch(cancel):
            calls.append(mode[0])
            assert gate.wait(3)
            if mode[0] == 'offline':
                raise pet.RefreshError('offline fixture')
            return snapshot()
        def drain(app):
            deadline = time.monotonic()+5
            while app.refresh_busy and time.monotonic()<deadline:
                app.root.update()
                app.collect_refresh()
                time.sleep(.01)
            assert not app.refresh_busy
        with patch.object(pet, 'fetch_snapshot', fetch), patch.object(pet, 'run_cycle') as redeem, \
             patch.object(pet, 'QuotaRefresh', side_effect=lambda: QuotaRefresh(clock=lambda: now[0])):
            app = pet.Companion(folder/'usage.json', settings, tibo_enabled=False)
            try:
                drain(app)
                assert calls == ['success']
                assert app.quota_refresh.enabled
                assert not app.auto_policy.get('enabled', False)
                assert not (folder/'auto-redeem.json').exists()
                assert not (folder/'auto-redeem-state.json').exists()
                redeem.assert_not_called()
                saved = app.manual_usage.read_bytes()
                app.animation.play(State.SLEEP, time.monotonic())
                now[0] = 399
                app.tick_quota()
                assert len(calls) == 1
                now[0] = 400
                mode[0] = 'offline'
                app.tick_quota()
                drain(app)
                assert len(calls) == 2
                assert app.interaction == 'sleep', 'Background refresh woke the pet'
                assert app.manual_usage.read_bytes() == saved
                assert app.quota_refresh.next_due == 430
                now[0] = 429
                app.tick_quota()
                assert len(calls) == 2
                now[0] = 430
                mode[0] = 'success'
                app.tick_quota()
                drain(app)
                assert len(calls) == 3 and app.quota_refresh.next_due == 730
                assert app.quota_refresh.last_error == ''
                # Both automatic and manual starts share one in-flight request.
                gate.clear()
                app.refresh_usage()
                for _ in range(10):
                    app.refresh_usage()
                    app.tick_quota()
                gate.set()
                drain(app)
                assert len(calls) == 4
                # Do not overlap a credit operation with read-only polling.
                app.auto_busy = True
                now[0] = 10000
                app.tick_quota()
                app.refresh_usage()
                assert len(calls) == 4
                app.auto_busy = False
                app.toggle_quota_refresh()
                assert not app.quota_refresh.enabled
                app.tick_quota()
                assert len(calls) == 4
                assert json.loads(settings.read_text())['quota_auto_refresh'] is False
                # Manual refresh remains usable while polling is off.
                app.refresh_usage()
                drain(app)
                assert len(calls) == 5
                # A completed credit check already supplies fresh quota.
                app.quota_refresh.set_enabled(True)
                app.auto_results.put((app.auto_revision, {'snapshot': snapshot(), 'message': 'fixture', 'delay': 300}))
                app.tick_auto()
                app.tick_quota()
                assert len(calls) == 5 and app.quota_refresh.next_due == now[0]+300
                app.quota_refresh.set_enabled(False)
                app.close('test')
                app.tick_quota()
                assert len(calls) == 5
            finally:
                gate.set()
                if not app.closed:
                    app.close('test cleanup')
            other = pet.Companion(folder/'usage.json', settings, tibo_enabled=False)
            try:
                assert not other.quota_refresh.enabled
                assert len(calls) == 5
                other.toggle_quota_refresh()
                other.tick_quota()
                drain(other)
                assert len(calls) == 6
                redeem.assert_not_called()
            finally:
                other.close('test')
            settings.unlink()
            fresh = pet.Companion(folder/'usage.json', settings, tibo_enabled=False)
            try:
                drain(fresh)
                assert fresh.quota_refresh.enabled and len(calls) == 7
                redeem.assert_not_called()
            finally:
                fresh.close('test')
    print('automatic-quota-ok')


if __name__ == '__main__':
    if '--ui-worker' in sys.argv:
        ui_worker()
    else:
        unittest.main()
