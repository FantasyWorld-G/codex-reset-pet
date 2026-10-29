"""Reject installation instructions and package metadata that target different versions."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check_release():
    version = json.loads((ROOT/'plugins/reset-reminder/.codex-plugin/plugin.json').read_text('utf-8'))['version']
    assert re.fullmatch(r'\d+\.\d+\.\d+', version), 'Invalid release version'
    installer = (ROOT/'install.ps1').read_text('utf-8')
    assert re.search(r"\$Version = '([^']+)'", installer)[1] == version, 'Installer version differs'
    primary = ('README.md', 'README.en.md', 'docs/使用说明.md')
    for name in (*primary, 'docs/installation.md', 'docs/installation.en.md'):
        text = (ROOT/name).read_text('utf-8')
        refs = re.findall(r'--ref v(\d+\.\d+\.\d+)', text)
        assert refs and set(refs) == {version}, f'{name}: stale Codex install/update tag'
        # Check actual downloads, Git commands and checksum regexes, not historical prose.
        normalized = text.replace('\\.', '.')
        pins = re.findall(r'(?:--branch v|/releases/tag/v|codex-reset-pet-v|/codex-reset-pet/v)(\d+\.\d+\.\d+)', normalized)
        assert all(pin == version for pin in pins), f'{name}: stale desktop installation target'
        if name in primary:
            assert 'main/update.ps1' in text, f'{name}: missing latest stable updater command'
            assert '-InstallRoot' in text and '-SkipPlugin' in text, f'{name}: missing alternate installation options'
            assert 'codex-pet status' in text and '-NoPath' in text, f'{name}: missing command startup instructions'
    for name in ('README.md', 'README.en.md'):
        headings = re.findall(r'^## (.+)$', (ROOT/name).read_text('utf-8'), re.M)
        assert 'Codex' in headings[0], f'{name}: keep Codex installation first'
    changelog = (ROOT/'CHANGELOG.md').read_text('utf-8')
    assert re.search(r'^## (\S+)', changelog, re.M)[1] == version, 'Changelog release differs'
    print(f'Release {version}: installer, plugin and installation/update instructions agree')


if __name__ == '__main__':
    check_release()
