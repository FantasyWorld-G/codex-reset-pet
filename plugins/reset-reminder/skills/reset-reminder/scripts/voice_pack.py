"""Offline personal voice import. Never downloads or distributes recordings."""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import wave

CREDIT = "Voice: Amitaro's Voice Material Studio (https://amitaro.net/)"
TERMS = 'https://amitaro.net/voice/voice_rule/'
ENGLISH_TERMS = 'https://amitaro.net/voice/terms/'
PAGE = 'https://amitaro.net/voice/game_01/'
RECIPE = '2026-10-29'
NAMES = ('click_1', 'click_2', 'pout', 'drag', 'drag_happy', 'land', 'sleep', 'wake')
MAPPING = dict(zip(NAMES, ('fufu_02.wav', 'ehehe_01.wav', 'nmou_03.wav', 'fufu_02.wav',
                          'aha_01.wav', 'ehehe_01.wav', 'akubi_03.wav', 'n_02.wav')))
SOURCE_HASHES = {
    'fufu_02.wav': '06601a314554bc9e03632a545a600b9b27ca7f122a003df5d121ace95aa23fd9',
    'ehehe_01.wav': '15f074f34217b2e6843d49145f855e3b06dc9937361187fcc284031a72b55a9b',
    'nmou_03.wav': '0774c345ed215ba19f5d6607b201692a694baeca6c046440313b7f8bdc8e5d24',
    'aha_01.wav': '206801d57848f9de89273dca91201ad05ca7cc2efc7c4c56bd6fa78e93a5664b',
    'akubi_03.wav': '08efd5c73bdeb1af032d513a309c00b6850cc080d6ca90e34237534b963bcc07',
    'n_02.wav': '970e3231c64e15571b4062f56d7238876561fb2d8a5d6fb80c248701d5fdb0de',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject_link(path):
    if path.is_symlink() or (path.exists() and getattr(path.stat(), 'st_file_attributes', 0) & 0x400):
        raise ValueError(f'Links/junctions are not supported: {path.name}')


def read_pcm(path):
    reject_link(path)
    if not path.is_file() or not 44 <= path.stat().st_size <= 2_000_000:
        raise ValueError(f'Missing or oversized WAV: {path.name}')
    with wave.open(str(path), 'rb') as clip:
        channels, width, rate, frames, compression, _ = clip.getparams()
        if width != 2 or channels not in (1, 2) or not 8000 <= rate <= 96000 or compression != 'NONE' or not 0 < frames <= rate*6:
            raise ValueError(f'Unsupported PCM WAV: {path.name}')
        data = clip.readframes(frames)
        if len(data) != frames*channels*width:
            raise ValueError(f'Truncated WAV: {path.name}')
    samples = array.array('h', data)
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples, rate, channels


def write_pcm(path, samples, rate=44100):
    values = array.array('h', samples)
    if sys.byteorder != 'little':
        values.byteswap()
    with wave.open(str(path), 'wb') as clip:
        clip.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        clip.writeframes(values.tobytes())


def validate_pack(folder):
    reject_link(folder)
    manifest = folder/'manifest.json'
    reject_link(manifest)
    if manifest.stat().st_size > 65536:
        raise ValueError('Voice manifest is too large')
    metadata = json.loads(manifest.read_text('utf-8-sig'))
    if not isinstance(metadata, dict) or metadata.get('provider') != 'amitaro':
        raise ValueError('Not an Amitaro personal pack')
    clips = metadata.get('clips', [])
    if not isinstance(clips, list) or any(not isinstance(c, dict) for c in clips):
        raise ValueError('Invalid voice clip metadata')
    hashes = {c.get('file'): c.get('installed_sha256') for c in clips}
    names = NAMES + (('pet',) if (folder/'pet.wav').exists() else ())
    for name in names:
        path = folder/(name+'.wav')
        read_pcm(path)
        expected = hashes.get(path.name)
        if expected and digest(path) != expected:
            raise ValueError(f'Voice checksum mismatch: {path.name}')
    return metadata, names


def build_raw(source, destination):
    processed = {}
    records = []
    for filename, expected in SOURCE_HASHES.items():
        path = source/filename
        samples, rate, channels = read_pcm(path)
        if rate != 44100 or channels != 1 or digest(path) != expected:
            raise ValueError(f'Original differs from the selected recording: {filename}. See docs/voice-credits.md.')
        values = [x/32768 for x in samples]
        peak = max(max(abs(x) for x in values), 1e-9)
        active = [x for x in values if abs(x) > peak*.04]
        rms = max(math.sqrt(sum(x*x for x in active)/max(1, len(active))), 1e-9)
        gain = min(1., .28/peak, .07/rms)
        edge = min(round(rate*.003), len(values)//2)
        pcm = []
        for i, sample in enumerate(values):
            fade = min(1., i/(edge-1), (len(values)-1-i)/(edge-1)) if edge > 1 else 1.
            pcm.append(math.floor(sample*gain*fade*32768))
        processed[filename] = pcm, gain
    for name, filename in MAPPING.items():
        pcm, gain = processed[filename]
        if name == 'sleep':
            if len(pcm) > 3*44100:
                raise ValueError('Sleep original exceeds three seconds')
            pcm = pcm + [0]*(3*44100-len(pcm))
        path = destination/(name+'.wav')
        write_pcm(path, pcm)
        records.append(dict(file=path.name, original=filename, source_page=PAGE,
                            source_sha256=SOURCE_HASHES[filename], installed_sha256=digest(path),
                            duration=len(pcm)/44100, gain=gain))
    first = processed['fufu_02.wav'][0]
    second = processed['ehehe_01.wav'][0]
    pat = [math.floor(x*.85) for x in first+[0]*4410+second]
    write_pcm(destination/'pet.wav', pat)
    records.append(dict(file='pet.wav', original='fufu_02.wav + ehehe_01.wav', source_page=PAGE,
                        installed_sha256=digest(destination/'pet.wav'), duration=len(pat)/44100))
    metadata = dict(provider='amitaro', recipe=RECIPE, credit=CREDIT, license_url=TERMS,
                    english_terms_url=ENGLISH_TERMS, clips=records,
                    processing='Gain reduction, 3ms fades, sleep padded to 3s; pat joins laughs with 100ms silence at 0.85 gain. No pitch/tempo changes.')
    (destination/'manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), 'utf-8')


def import_pack(source, data_dir):
    source, data_dir = Path(source).absolute(), Path(data_dir).absolute()
    reject_link(source)
    if not source.is_dir():
        raise ValueError('Source must be a folder containing a personal pack or the six original WAV files')
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir/'voice-amitaro'
    reject_link(target)
    if target.exists() and not target.is_dir():
        raise ValueError('voice-amitaro is not a directory')
    if source.resolve() == target.resolve():
        validate_pack(target)
        return 'Already installed; validated the existing personal pack.'
    temporary = Path(tempfile.mkdtemp(prefix='.voice-import-', dir=data_dir))
    staged, backup = temporary/'new', temporary/'previous'
    staged.mkdir()
    try:
        if (source/'manifest.json').exists():
            _, names = validate_pack(source)
            for name in ['manifest.json']+[n+'.wav' for n in names]:
                shutil.copyfile(source/name, staged/name)
        else:
            build_raw(source, staged)
        (staged/'CREDITS.txt').write_text(
            f'{CREDIT}\nTerms: {TERMS}\nEnglish terms: {ENGLISH_TERMS}\n'
            'Personal local use; not CC0. Do not publish as a standalone voice pack.\n', 'utf-8')
        validate_pack(staged)
        if target.exists():
            target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            if backup.exists():
                backup.rename(target)
            raise
    finally:
        # If restoring fails, keep the previous pack and report its path.
        if backup.exists() and not target.exists():
            print(f'Recovery copy retained at: {backup}', file=sys.stderr)
        else:
            shutil.rmtree(temporary)
    return 'Installed Amitaro personal voices. Start the pet with: codex-pet'


def describe(data_dir):
    folder = Path(data_dir)/'voice-amitaro'
    if not folder.exists():
        return f'Configured sound pack: original-synthesis (bundled).\nNo personal pack at: {folder}'
    try:
        metadata, names = validate_pack(folder)
    except (OSError, ValueError, TypeError, wave.Error, EOFError) as error:
        return f'Configured sound pack: original-synthesis (fallback).\nPersonal pack invalid: {error}'
    return (f'Configured sound pack: amitaro ({len(names)} clips).\nLocation: {folder}\n'
            f'Recipe: {metadata.get("recipe", "personal import; revision unspecified")}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    try:
        if args.source:
            print(import_pack(args.source, args.data_dir))
        print(describe(args.data_dir))
        if not args.source:
            print('Import: codex-pet sounds "path-to-voice-folder"\nGuide: docs/voice-credits.md')
    except (OSError, ValueError, TypeError, wave.Error, EOFError) as error:
        print(f'Voice import failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
