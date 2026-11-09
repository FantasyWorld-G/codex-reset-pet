"""Reject incomplete packages before an installation is marked successful."""
from pathlib import Path
import sys
import hashlib
import wave
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'plugins/reset-reminder/skills/reset-reminder/scripts'))
from voice_pack import validate_pack


def verify_bundle():
    metadata, voices = validate_pack(ROOT/'plugins/reset-reminder/assets/bundled-voice')
    if len(voices) != 9 or metadata.get('recipe') != '2026-10-29':
        raise ValueError('The complete package must include all nine current voice clips')
    urgent = ROOT/'plugins/reset-reminder/assets/alerts/urgent.wav'
    if hashlib.sha256(urgent.read_bytes()).hexdigest() != '082caa0dfb7f91c33b49bf521d7a14b121d553aa2936c13eacb3d57a0f5475d5':
        raise ValueError('The quota alert sound is missing or damaged')
    with wave.open(str(urgent)) as clip:
        if clip.getnframes()/clip.getframerate() != 10:
            raise ValueError('The quota alert must last ten seconds')
    with Image.open(ROOT/'plugins/reset-reminder/assets/maid-urgent-sprites.png') as sheet:
        if sheet.mode != 'RGBA' or sheet.width != sheet.height*3 or sheet.getchannel('A').getextrema()[0] != 0:
            raise ValueError('The three transparent urgent expression sprites are missing or invalid')
    print('Verified: nine current voices and the ten-second quota alert are included.')


if __name__ == '__main__':
    verify_bundle()
