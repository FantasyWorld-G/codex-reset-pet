import array
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import wave

SCRIPTS = Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'
sys.path.insert(0, str(SCRIPTS))
from pet_audio import PetAudio
from animation_state import AnimationStateMachine, State

ASSETS = SCRIPTS.parents[2]/'assets/sounds'


def make_personal_pack(folder):
    folder.mkdir()
    (folder/'manifest.json').write_text('{"provider":"amitaro"}', 'utf-8')
    for name in ('click_1','click_2','pout','drag','drag_happy','land','sleep','wake'):
        with wave.open(str(folder/(name+'.wav')), 'wb') as clip:
            clip.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            clip.writeframes(b'\x00\x00'*3200)


class Backend:
    SND_FILENAME, SND_ASYNC, SND_NODEFAULT = 1, 2, 4

    def __init__(self):
        self.calls = []

    def PlaySound(self, path, flags):
        self.calls.append((Path(path).stem if path else None, flags))


class PetAudioTests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.now = 0
        self.audio = PetAudio(ASSETS, backend=self.backend, clock=lambda:self.now)
        self.state = AnimationStateMachine(0)

    def observe(self):
        state, _ = self.state.update(self.now)
        self.audio.observe(state, self.state.revision)

    def test_sleep_plays_once_and_wakes_on_touch(self):
        self.observe()
        self.assertEqual(self.backend.calls, [])
        self.now = 10
        self.observe()
        for self.now in range(11, 100):
            self.observe()
        self.assertEqual(self.backend.calls, [('sleep', 7)])
        self.state.touch(self.now)
        self.observe()
        self.assertEqual(self.backend.calls[-2:], [(None, 0), ('wake', 7)])

    def test_drag_once_then_land_and_silent_idle(self):
        self.state.press(0)
        self.state.play(State.DRAG, 0)
        for self.now in range(20):
            self.observe()
        self.assertEqual(self.backend.calls, [('drag', 7)])
        self.state.release(self.now)
        self.state.play(State.LAND, self.now)
        self.observe()
        self.now += 2
        self.observe()
        self.assertEqual(self.backend.calls, [('drag', 7), ('land', 7)])

    def test_click_variants_throttle_and_pout(self):
        for self.now in (0, .05, .4):
            self.state.play(State.CLICK, self.now)
            self.observe()
        self.assertEqual(len(self.backend.calls), 2)
        self.now = .8
        self.state.play(State.CLICK, self.now)
        self.observe()
        self.assertEqual(self.backend.calls[-1][0], 'click_2')
        self.state.play(State.POUT, self.now)
        self.observe()
        self.assertEqual(self.backend.calls[-1][0], 'pout')

    def test_drag_distance_once_per_gesture_and_not_cut_by_release(self):
        for distance in (0, 5, 70, 179.9):
            self.audio.drag_distance(distance, 1)
        self.assertEqual(self.backend.calls, [('drag', 7)])
        self.audio.drag_distance(180, 1)
        for distance in (200, 300, 10, 400):
            self.audio.drag_distance(distance, 1)
        self.audio.observe('drag', 1)
        self.audio.observe('land', 2)
        self.assertEqual(self.backend.calls, [('drag', 7), ('drag_happy', 7)])
        self.now += 2
        self.audio.drag_distance(250, 3)
        self.now += 1
        self.audio.observe('land', 4)
        self.assertEqual([name for name, _ in self.backend.calls],
                         ['drag', 'drag_happy', 'drag', 'drag_happy', 'land'])

    def test_cancel_rearms_distance_and_muted_travel_stays_silent(self):
        self.audio.drag_distance(180, 1)
        self.audio.observe('idle', 2)
        self.audio.drag_distance(180, 3)
        self.assertEqual(sum(name == 'drag_happy' for name, _ in self.backend.calls), 2)
        self.audio.set_enabled(False)
        before = len(self.backend.calls)
        self.audio.drag_distance(200, 4)
        self.audio.observe('land', 5)
        self.assertEqual(len(self.backend.calls), before)

    def test_muting_stops_and_does_not_replay_sleep_on_enable(self):
        self.now = 10
        self.observe()
        self.audio.set_enabled(False)
        self.audio.set_enabled(True)
        self.now = 20
        self.observe()
        self.assertEqual(self.backend.calls, [('sleep', 7), (None, 0)])
        self.audio.close()
        self.audio.play('click_1')
        self.assertEqual(self.backend.calls[-1], (None, 0))
        self.assertEqual(len(self.backend.calls), 3)

    def test_missing_asset_and_backend_error_do_not_break_animation(self):
        with tempfile.TemporaryDirectory() as folder:
            self.audio.assets = Path(folder)
            with self.assertLogs(level='ERROR'):
                self.audio.play('sleep')
            self.assertEqual(self.backend.calls, [])
        self.audio.assets = ASSETS
        def fail(*args):
            raise RuntimeError('No audio device')
        self.backend.PlaySound = fail
        with self.assertLogs(level='ERROR'):
            self.audio.play('drag')
            self.audio.close()

    def test_head_pat_plays_once_and_supports_older_sound_packs(self):
        self.audio.observe('pat',1)
        self.audio.observe('pat',1)
        self.assertEqual(self.backend.calls,[('click_2',7)])
        with tempfile.TemporaryDirectory() as directory:
            personal = Path(directory)/'voice-amitaro'
            make_personal_pack(personal)
            (personal/'pet.wav').write_bytes((personal/'click_2.wav').read_bytes())
            audio = PetAudio(ASSETS,backend=self.backend,personal_assets=personal)
            audio.observe('pat',1)
            audio.observe('pat',1)
            self.assertEqual(self.backend.calls[-1],('pet',7))
            self.assertEqual(len(self.backend.calls),2)

    def test_assets_duration_level_and_silent_edges(self):
        names = {'click_1','click_2','pout','drag','drag_happy','land','wake','sleep'}
        self.assertEqual({p.stem for p in ASSETS.glob('*.wav')}, names)
        for name in names:
            with self.subTest(name=name), wave.open(str(ASSETS/(name+'.wav'))) as audio:
                self.assertEqual(audio.getnchannels(), 1)
                self.assertEqual(audio.getsampwidth(), 2)
                duration = audio.getnframes()/audio.getframerate()
                if name == 'sleep':
                    self.assertEqual(duration, 3)
                elif name == 'drag_happy':
                    self.assertAlmostEqual(duration, PetAudio.DRAG_HAPPY_SECONDS)
                else:
                    self.assertLess(duration, 1)
                pcm = array.array('h', audio.readframes(audio.getnframes()))
                self.assertGreater(max(map(abs, pcm)), 1000)
                self.assertLess(max(map(abs, pcm)), 10000)
                self.assertLess(abs(pcm[0]), 30)
                self.assertLess(abs(pcm[-1]), 30)

    def test_personal_pack_selection_and_actual_playback_length(self):
        with tempfile.TemporaryDirectory() as directory:
            personal = Path(directory)/'voice-amitaro'
            make_personal_pack(personal)
            audio = PetAudio(ASSETS, backend=self.backend, clock=lambda:self.now,
                             personal_assets=personal)
            self.assertEqual(audio.provider, 'amitaro')
            self.assertEqual(audio.assets, personal)
            self.assertAlmostEqual(audio.drag_happy_seconds, .4)
            audio.drag_distance(180, 1)
            self.now = .2
            audio.observe('land', 2)
            self.assertEqual(self.backend.calls[-1][0], 'drag_happy')
            audio.drag_distance(180, 3)
            self.now = .7
            audio.observe('land', 4)
            self.assertEqual(self.backend.calls[-1][0], 'land')

    def test_missing_or_incomplete_personal_pack_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            personal = Path(directory)/'voice-amitaro'
            audio = PetAudio(ASSETS, backend=self.backend, personal_assets=personal)
            self.assertEqual(audio.provider, 'original-synthesis')
            make_personal_pack(personal)
            (personal/'wake.wav').unlink()
            with self.assertLogs(level='ERROR'):
                audio = PetAudio(ASSETS, backend=self.backend, personal_assets=personal)
            self.assertEqual(audio.assets, ASSETS)
            (personal/'manifest.json').write_text('[]', 'utf-8')
            with self.assertLogs(level='ERROR'):
                audio = PetAudio(ASSETS, backend=self.backend, personal_assets=personal)
            self.assertEqual(audio.provider, 'original-synthesis')

    @unittest.skipUnless(os.name == 'nt', 'Windows desktop integration')
    def test_ui_actions_and_saved_mute_setting(self):
        result = subprocess.run([sys.executable, __file__, '--ui-worker'],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+'\n'+result.stderr)
        self.assertIn('audio-ui-ok', result.stdout)


def exercise_ui():
    from desktop_pet import Companion
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        make_personal_pack(folder/'voice-amitaro')
        app = Companion(folder/'usage.json',folder/'settings.json',tibo_enabled=False)
        backend = Backend()
        app.audio.backend = backend
        try:
            assert app.audio.provider == 'amitaro'
            app.expanded = True
            app.draw()
            assert not app.canvas.find_withtag('voice_credit')
            # Double tap: one head pat, no single tap audio or bubble toggles.
            expanded = app.expanded
            for _ in range(2):
                app.press_pet(100,100)
                app.release(SimpleNamespace(x_root=100,y_root=100))
                app.animate()
            assert app.interaction == 'pat'
            assert app.click_count == 0 and app.expanded == expanded
            assert backend.calls == [('click_2',7)], backend.calls
            assert app.click_timer is None
            backend.calls.clear()
            # A confirmed single tap still performs its original action.
            app.audio.clock = lambda: 1000000000
            app.press_pet(100,100)
            app.release(SimpleNamespace(x_root=100,y_root=100))
            assert not backend.calls
            until = time.monotonic()+.4
            while time.monotonic()<until:
                app.root.update()
                time.sleep(.01)
            assert app.click_count == 1 and app.expanded != expanded
            assert backend.calls == [('click_1',7)], backend.calls
            backend.calls.clear()
            # Starting a drag during the second press cancels the pending tap.
            app.press_pet(100,100)
            app.release(SimpleNamespace(x_root=100,y_root=100))
            app.press_pet(100, 100)
            app.drag(SimpleNamespace(x_root=130, y_root=120))
            app.animate()
            app.release(SimpleNamespace(x_root=130, y_root=120))
            app.animate()
            assert [call[0] for call in backend.calls] == ['drag', 'land'], backend.calls
            backend.calls.clear()
            app.audio.clock = lambda: 1000
            app.press_pet(100, 100)
            for pointer_x in (279, 280, 450, 290):
                app.drag(SimpleNamespace(x_root=pointer_x, y_root=100))
                app.animate()
            app.release(SimpleNamespace(x_root=290, y_root=100))
            app.animate()
            assert [call[0] for call in backend.calls] == ['drag', 'drag_happy'], backend.calls
            # Moving the bubble is not a pet interaction, even over the threshold.
            backend.calls.clear()
            app.drag_start = (100,100,app.root.winfo_x(),app.root.winfo_y(),False)
            app.drag(SimpleNamespace(x_root=500,y_root=100))
            app.animate()
            app.release(SimpleNamespace(x_root=500,y_root=100))
            app.animate()
            assert not backend.calls, backend.calls
            app.toggle_sound()
            assert not json.loads((folder/'settings.json').read_text())['sound_enabled']
            assert backend.calls[-1] == (None, 0)
        finally:
            app.close()
        other = Companion(folder/'usage.json',folder/'settings.json',tibo_enabled=False)
        try:
            assert not other.audio.enabled
        finally:
            other.close()
    print('audio-ui-ok')


if __name__ == '__main__':
    if '--ui-worker' in sys.argv:
        exercise_ui()
    else:
        unittest.main()
