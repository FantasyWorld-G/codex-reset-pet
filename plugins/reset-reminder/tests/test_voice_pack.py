"""Import synthetic fixtures only: no third-party recordings or network calls."""
import array
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'skills/reset-reminder/scripts'
sys.path.insert(0, str(SCRIPTS))
import voice_pack as voice
from pet_audio import PetAudio


class VoicePackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'my voices'
        self.source.mkdir()
        self.data = self.root/'data'
        self.data.mkdir()
        self.target = self.data/'voice-amitaro'
        (self.data/'desktop-settings.json').write_text('{"sound_enabled":false}')

    def prepared(self):
        for name in voice.NAMES+('pet',):
            voice.write_pcm(self.source/(name+'.wav'), [1000, -1000]*4410)
        manifest = dict(provider='amitaro', clips=[dict(file=p.name, installed_sha256=voice.digest(p))
                                                  for p in self.source.glob('*.wav')])
        (self.source/'manifest.json').write_text(json.dumps(manifest))

    def snapshot(self):
        return {str(p.relative_to(self.data)): p.read_bytes() for p in self.data.rglob('*') if p.is_file()}

    def test_prepared_copy_is_exact_and_ignores_unrelated_private_files(self):
        self.prepared()
        (self.source/'usage.json').write_text('private account data')
        voice.import_pack(self.source, self.data)
        for p in self.source.glob('*.wav'):
            self.assertEqual(p.read_bytes(), (self.target/p.name).read_bytes())
        self.assertFalse((self.target/'usage.json').exists())
        self.assertIn(voice.CREDIT, (self.target/'CREDITS.txt').read_text())
        self.assertEqual((self.data/'desktop-settings.json').read_text(), '{"sound_enabled":false}')
        self.assertIn('amitaro (9 clips)', voice.describe(self.data))
        self.assertIn('Already installed', voice.import_pack(self.target, self.data))

    def test_invalid_or_missing_file_preserves_old_pack(self):
        self.prepared()
        voice.import_pack(self.source, self.data)
        before = self.snapshot()
        (self.source/'pout.wav').write_bytes(b'not a wave')
        with self.assertRaises(ValueError):
            voice.import_pack(self.source, self.data)
        self.assertEqual(before, self.snapshot())
        (self.source/'pout.wav').unlink()
        with self.assertRaises(ValueError):
            voice.import_pack(self.source, self.data)
        self.assertEqual(before, self.snapshot())

    def test_failed_commit_rolls_back_previous_pack(self):
        self.prepared()
        voice.import_pack(self.source, self.data)
        before = self.snapshot()
        rename = Path.rename
        def failing_rename(path, destination):
            if path.name == 'new':
                raise OSError('Simulated file lock')
            return rename(path, destination)
        with patch.object(Path, 'rename', failing_rename), self.assertRaisesRegex(OSError, 'file lock'):
            voice.import_pack(self.source, self.data)
        self.assertEqual(before, self.snapshot())

    def test_checksum_and_truncated_pcm_rejected_runtime_falls_back(self):
        self.prepared()
        voice.import_pack(self.source, self.data)
        voice.write_pcm(self.target/'pout.wav', [500]*4410)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            voice.validate_pack(self.target)
        self.assertIn('fallback', voice.describe(self.data))
        with self.assertLogs(level='ERROR'):
            audio = PetAudio(self.root/'bundled', backend=object(), personal_assets=self.target)
        self.assertEqual(audio.provider, 'original-synthesis')
        path = self.source/'click_1.wav'
        path.write_bytes(path.read_bytes()[:-20])
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            voice.read_pcm(path)

    def test_raw_recipe_pout_sleep_and_pat(self):
        for name in voice.SOURCE_HASHES:
            voice.write_pcm(self.source/name, [10000, -10000]*4410)
        hashes = {n: voice.digest(self.source/n) for n in voice.SOURCE_HASHES}
        with patch.dict(voice.SOURCE_HASHES, hashes):
            voice.import_pack(self.source, self.data)
        metadata, names = voice.validate_pack(self.target)
        self.assertEqual(metadata['recipe'], voice.RECIPE)
        self.assertEqual(len(names), 9)
        sleep, rate, channels = voice.read_pcm(self.target/'sleep.wav')
        self.assertEqual(len(sleep), 3*rate)
        self.assertFalse(any(sleep[8820:]))
        pat, _, _ = voice.read_pcm(self.target/'pet.wav')
        self.assertEqual(len(pat), 8820*2+4410)
        self.assertFalse(any(pat[8820:13230]))
        pout = next(c for c in metadata['clips'] if c['file'] == 'pout.wav')
        self.assertEqual(pout['original'], 'nmou_03.wav')
        self.assertEqual(pout['duration'], .2)
        self.assertEqual(voice.read_pcm(self.target/'drag.wav')[0], voice.read_pcm(self.target/'click_1.wav')[0])
        self.assertEqual(voice.read_pcm(self.target/'land.wav')[0], voice.read_pcm(self.target/'click_2.wav')[0])

    def test_wrong_original_and_missing_source_do_not_install(self):
        for name in voice.SOURCE_HASHES:
            voice.write_pcm(self.source/name, [1000]*4410)
        with self.assertRaisesRegex(ValueError, 'Original differs'):
            voice.import_pack(self.source, self.data)
        self.assertFalse(self.target.exists())
        self.assertIn('original-synthesis', voice.describe(self.data))
        with self.assertRaisesRegex(ValueError, 'Source must be a folder'):
            voice.import_pack(self.root/'absent', self.data)

    def test_complete_release_works_on_fresh_install_and_overrides_legacy_pack(self):
        import shutil
        self.prepared()
        assets = self.root/'assets/sounds'
        assets.mkdir(parents=True)
        bundled = assets.parent/'bundled-voice'
        shutil.copytree(self.source, bundled)
        chosen, provider, errors = voice.choose_audio(assets, self.target)
        self.assertEqual((chosen, provider, errors), (bundled, 'amitaro-bundled', []))
        # Legacy packs remain intact but no longer hide updated release voices.
        shutil.copytree(self.source, self.target)
        original = (self.target/'pout.wav').read_bytes()
        self.assertEqual(voice.choose_audio(assets, self.target)[0], bundled)
        self.assertIn('amitaro-bundled', voice.describe(self.data, assets))
        self.assertEqual((self.target/'pout.wav').read_bytes(), original)
        audio = PetAudio(assets, backend=object(), personal_assets=self.target)
        self.assertEqual(audio.provider, 'amitaro-bundled')
        self.assertTrue((audio.assets/'pet.wav').is_file())
        # A deliberate import still permits personal customization.
        voice.import_pack(self.source, self.data)
        self.assertEqual(voice.choose_audio(assets, self.target)[0], self.target)

    def test_corrupt_bundled_pack_reports_fallback_and_mute_is_preserved(self):
        import shutil
        self.prepared()
        assets = self.root/'assets/sounds'
        assets.mkdir(parents=True)
        bundled = assets.parent/'bundled-voice'
        shutil.copytree(self.source, bundled)
        (bundled/'pout.wav').write_bytes(b'corrupt')
        chosen, provider, errors = voice.choose_audio(assets, None)
        self.assertEqual((chosen, provider), (assets, 'original-synthesis'))
        self.assertTrue(errors)
        shutil.copyfile(self.source/'pout.wav', bundled/'pout.wav')
        audio = PetAudio(assets, enabled=False, backend=object())
        self.assertEqual(audio.provider, 'amitaro-bundled')
        self.assertFalse(audio.play('pet'))


if __name__ == '__main__':
    unittest.main()
