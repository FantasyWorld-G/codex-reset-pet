import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import wave
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'
sys.path.insert(0, str(SCRIPTS))
from quota_alert import QuotaAlert
from pet_audio import PetAudio
from animation_state import AnimationStateMachine, State
from test_desktop_pet import snapshot, NOW
from test_pet_audio import Backend, ASSETS


def exhausted(now=NOW):
    source = snapshot()
    source['captured_at'] = now
    source['usage']['rateLimits']['secondary'] = {'usedPercent': 100, 'resetsAt': now+86400}
    return source


class QuotaAlertTests(unittest.TestCase):
    def test_secondary_exhaustion_cards_and_persistent_dedup(self):
        watcher = QuotaAlert()
        notice, trigger = watcher.evaluate([exhausted()], {}, NOW)
        self.assertTrue(trigger)
        self.assertIn('1 张', notice['detail'])
        self.assertNotIn('test-account', json.dumps(watcher.history))
        restarted = QuotaAlert(json.loads(json.dumps(watcher.history)))
        self.assertFalse(restarted.evaluate([exhausted(NOW+1)], {}, NOW+1)[1])
        self.assertIsNone(restarted.evaluate([dict(snapshot(), captured_at=NOW+2)], {}, NOW+2)[0])
        self.assertTrue(restarted.evaluate([exhausted(NOW+3)], {}, NOW+3)[1])

    def test_current_account_auto_suppresses_but_other_account_does_not(self):
        watcher = QuotaAlert()
        policy = {'enabled': True, 'start_before': 960, 'stop_before': 360, 'account_id': 'test-account'}
        self.assertEqual(watcher.evaluate([exhausted()], policy, NOW), (None, False))
        policy['account_id'] = 'other'
        self.assertTrue(watcher.evaluate([exhausted()], policy, NOW)[1])
        policy['account_id'] = 'test-account'
        self.assertEqual(watcher.evaluate([exhausted()], policy, NOW), (None, False))

    def test_unknown_none_expired_and_used_cards(self):
        for cards, expected in [(None, '待确认'), ({'credits': []}, '暂无'),
            ({'credits': [{'status': 'used', 'resetType': 'codexRateLimits', 'expiresAt': NOW+999}]}, '暂无'),
            ({'credits': [{'status': 'available', 'resetType': 'codexRateLimits', 'expiresAt': NOW}]}, '暂无'),
            ({'credits': [{'status': 'available', 'resetType': 'codexRateLimits'}]}, '待确认')]:
            with self.subTest(cards=cards):
                source = exhausted()
                source['usage']['rateLimitResetCredits'] = cards
                notice, trigger = QuotaAlert().evaluate([source], {}, NOW)
                self.assertTrue(trigger)
                self.assertIn(expected, notice['detail'])

    def test_stale_future_invalid_reset_and_old_cache_do_not_alert(self):
        for source in [dict(exhausted(), captured_at=NOW-601), dict(exhausted(), captured_at=NOW+61),
                       {'captured_at': NOW, 'usage': {}}, None]:
            self.assertEqual(QuotaAlert().evaluate([source], {}, NOW), (None, False))
        source = exhausted()
        source['usage']['rateLimits']['secondary']['resetsAt'] = NOW
        self.assertEqual(QuotaAlert().evaluate([source], {}, NOW), (None, False))
        self.assertEqual(QuotaAlert().evaluate([exhausted(), {'captured_at': NOW+1, 'usage': {}}], {}, NOW), (None, False))
        watcher = QuotaAlert()
        watcher.evaluate([exhausted(NOW+2)], {}, NOW+2)
        watcher.evaluate([snapshot()], {}, NOW+2)  # Old healthy cache cannot rearm.
        self.assertFalse(watcher.evaluate([exhausted(NOW+3)], {}, NOW+3)[1])
        watcher.evaluate([None], {}, NOW+3)  # Disconnect cannot rearm.
        self.assertFalse(watcher.evaluate([exhausted(NOW+4)], {}, NOW+4)[1])

    def test_account_switch_and_corrupt_settings(self):
        watcher = QuotaAlert({'bad': {'captured': 'invalid'}, 'bad2': None})
        self.assertTrue(watcher.evaluate([exhausted()], {}, NOW)[1])
        other = exhausted(NOW+1)
        other['usage']['accountId'] = 'other'
        other['usage']['rateLimitResetCredits'] = None
        notice, trigger = watcher.evaluate([exhausted(), other], {}, NOW+1)
        self.assertTrue(trigger)
        self.assertIn('待确认', notice['detail'])

    def test_sound_duration_priority_stop_mute_and_shutdown(self):
        clock = [0.]
        backend = Backend()
        audio = PetAudio(ASSETS, backend=backend, clock=lambda: clock[0])
        with wave.open(str(audio.alert_assets/'urgent.wav')) as clip:
            self.assertEqual(clip.getnframes()/clip.getframerate(), 10)
        audio.urgent()
        audio.observe('sleep', 1)
        audio.observe('click', 2)
        self.assertEqual(backend.calls, [('urgent', 7)])
        clock[0] = 9.99
        audio.tick()
        self.assertEqual(len(backend.calls), 1)
        clock[0] = 10
        audio.tick()
        self.assertEqual(backend.calls[-1], (None, 0))
        audio.urgent()
        audio.set_enabled(False)
        self.assertEqual(audio.urgent_until, 0)
        count = len(backend.calls)
        audio.urgent()
        self.assertEqual(len(backend.calls), count)
        audio.set_enabled(True)
        audio.urgent()
        audio.close()
        self.assertEqual(backend.calls[-1], (None, 0))

    def test_progressive_recordings_and_expression_stages(self):
        import json
        from animation_state import animation_pose
        folder = ASSETS.parent/'alerts'
        timeline = json.loads((folder/'timeline.json').read_text('utf-8'))['clips']
        with wave.open(str(folder/'urgent.wav')) as cue:
            self.assertEqual(cue.getnframes()/cue.getframerate(),10)
            pcm=cue.readframes(cue.getnframes())
        self.assertEqual([x['file'] for x in timeline],['abababababa_03.wav']*3+['abababababa_04.wav']*3)
        for entry in timeline:
            with wave.open(str(folder/'sources'/entry['file'])) as source:
                raw=source.readframes(source.getnframes())
            offset=round(entry['start']*44100)*2
            self.assertEqual(pcm[offset:offset+len(raw)],raw)
        self.assertEqual([animation_pose('urgent',t)[0] for t in [0,2,5,9.9]],[6,7,8,8])

    def test_urgent_pose_ten_seconds_and_direct_interaction(self):
        machine = AnimationStateMachine(0)
        machine.play(State.URGENT, 0)
        self.assertEqual(machine.update(9.99)[0], State.URGENT)
        self.assertEqual(machine.update(10)[0], State.SLEEP)
        machine.play(State.URGENT, 11)
        machine.play(State.DRAG, 12)
        self.assertEqual(machine.update(12)[0], State.DRAG)

    @unittest.skipUnless(os.name == 'nt', 'Windows UI')
    def test_desktop_notice_and_recovery(self):
        result = subprocess.run([sys.executable, __file__, '--ui-worker'], capture_output=True,
                                text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


def ui_worker():
    import desktop_pet as pet
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with patch.object(pet, 'run_cycle') as redeem:
            app = pet.Companion(root/'usage.json', root/'settings.json', tibo_enabled=False,
                                quota_auto_refresh=False, sound_enabled=False, windowed=True)
            try:
                app.audio.backend = Backend()
                app.audio.set_enabled(True)
                app.expanded = False
                app.draw()
                app.envelope = exhausted()
                app.model = pet.display_model(app.envelope, None, NOW)
                app.tick_quota_alert(NOW)
                app.root.update_idletasks()
                assert app.expanded
                assert app.canvas.itemcget(app.quota_text, 'text') == '额度已用完'
                assert '1 张' in app.canvas.itemcget(app.quota_notice_item, 'text')
                bounds = app.canvas.bbox(app.quota_notice_item)
                assert bounds[2] <= 350 and bounds[3] < 189, bounds
                assert app.animation.state == State.URGENT
                for index in (6,7,8):
                    assert app.sprites[index].getchannel("A").getextrema() == (0,255)
                    assert app.rendered_sprite(index,6) is not None
                assert app.audio.backend.calls == [('urgent', 7)]
                if '--screenshot' in sys.argv:
                    from PIL import ImageGrab
                    app.root.update()
                    x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
                    ImageGrab.grab((x, y, x+app.WIDTH, y+app.HEIGHT)).save(
                        sys.argv[sys.argv.index('--screenshot')+1])
                app.tick_quota_alert(NOW+1)
                assert app.audio.backend.calls == [('urgent', 7)]
                assert json.loads(app.settings.read_text('utf-8'))['quota_alert_history']
                app.envelope = dict(snapshot(), captured_at=NOW+2)
                app.tick_quota_alert(NOW+2)
                app.update_display()
                assert app.quota_notice is None
                assert app.audio.backend.calls[-1] == (None, 0)
                redeem.assert_not_called()
            finally:
                app.close()


if __name__ == '__main__':
    if '--ui-worker' in sys.argv:
        ui_worker()
    else:
        unittest.main()
