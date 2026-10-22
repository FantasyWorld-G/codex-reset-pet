"""Build a release from an explicit allowlist, excluding runtime/user data."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
version = json.loads((ROOT/'plugins/reset-reminder/.codex-plugin/plugin.json').read_text('utf-8'))['version']
files = [ROOT/name for name in ('README.md','README.en.md','CHANGELOG.md','requirements.txt','install.ps1','start.ps1',
                               '.agents/plugins/marketplace.json')]
for directory in ('docs','plugins','scripts'):
    files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and
                 '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo'))
files = sorted(set(files))
for path in files:
    if path.name in {'usage.json','state.json','auth.json','desktop-runtime.json','desktop-settings.json'} or path.suffix=='.log':
        raise ValueError(f'Runtime data cannot be published: {path.name}')
destination = ROOT/'dist'
destination.mkdir(exist_ok=True)
archive = destination/f'codex-reset-pet-v{version}.zip'
with ZipFile(archive,'w',ZIP_DEFLATED) as output:
    for path in files:
        output.write(path,Path('codex-reset-pet')/path.relative_to(ROOT))
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
(destination/'SHA256SUMS.txt').write_text(f'{checksum}  {archive.name}\n','ascii')
print(f'Built {archive.name}: {len(files)} files, SHA256 {checksum}')
