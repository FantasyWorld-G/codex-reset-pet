"""Reject incomplete packages before an installation is marked successful."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'plugins/reset-reminder/skills/reset-reminder/scripts'))
from voice_pack import validate_pack


def verify_bundle():
    metadata, voices = validate_pack(ROOT/'plugins/reset-reminder/assets/bundled-voice')
    if len(voices) != 9 or metadata.get('recipe') != '2026-10-29':
        raise ValueError('The complete package must include all nine current voice clips')
    print('Verified: current nine voice clips are included in this application package.')


if __name__ == '__main__':
    verify_bundle()
