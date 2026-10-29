"""Exercise the command with isolated installation metadata and fake processes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.name == 'nt', 'Windows command entry point')
class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pet command ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.bin = self.root/'bin'
        self.bin.mkdir()
        shutil.copyfile(ROOT/'codex-pet.ps1', self.bin/'codex-pet.ps1')
        self.app = self.root/'app'
        self.app.mkdir()
        self.data = self.root/'data'
        self.data.mkdir()
        self.script = self.app/'plugins/reset-reminder/skills/reset-reminder/scripts/desktop_pet.py'
        self.script.parent.mkdir(parents=True)
        self.script.touch()
        self.python = self.root/'pythonw.exe'
        self.python.touch()
        (self.root/'install.json').write_text(json.dumps(dict(version='0.4.5',appRoot=str(self.app),
            dataDir=str(self.data),pythonw=str(self.python))), 'utf-8')
        (self.app/'start.ps1').write_text('''param($DataDir,$PythonExe)
$countFile = Join-Path $DataDir 'launch-count.txt'
$count = if (Test-Path $countFile) { [int](Get-Content $countFile) } else { 0 }
Set-Content -LiteralPath $countFile -Value ($count+1)
'{"pid":1234,"lifecycle":"running"}' | Set-Content (Join-Path $DataDir 'desktop-runtime.json')
$script = Join-Path $PSScriptRoot 'plugins/reset-reminder/skills/reset-reminder/scripts/desktop_pet.py'
$settings = Join-Path $DataDir 'desktop-settings.json'
@{ProcessId=1234;Name='pythonw.exe';CommandLine=($script+' --settings '+$settings)} | ConvertTo-Json | Set-Content (Join-Path $DataDir 'process.json')
''', 'utf-8')
        self.harness = self.root/'harness.ps1'
        self.harness.write_text('''param($Entry,$Action,$DataDir,$Source)
function Get-CimInstance {
    param($ClassName,$Filter,$ErrorAction)
    $file = Join-Path $DataDir 'process.json'
    if (Test-Path $file) { Get-Content -Raw $file | ConvertFrom-Json }
}
if ($Source) { & $Entry $Action $Source } else { & $Entry $Action }
exit $LASTEXITCODE
''', 'utf-8')

    def run_command(self, action='start', expected=0, source=None):
        result = subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass',
            '-File',str(self.harness),'-Entry',str(self.bin/'codex-pet.ps1'),'-Action',action,
            '-DataDir',str(self.data)]+(['-Source',str(source)] if source else []),capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode, expected, result.stdout+result.stderr)
        return result.stdout+result.stderr

    def test_start_uses_metadata_and_repeated_start_does_not_duplicate(self):
        self.assertIn('Started',self.run_command())
        self.assertIn('Already running',self.run_command())
        self.assertEqual((self.data/'launch-count.txt').read_text().strip(),'1')
        self.assertIn('Running',self.run_command('status'))

    def test_wrong_process_identity_is_not_treated_as_running(self):
        (self.data/'desktop-runtime.json').write_text('{"pid":1234,"lifecycle":"running"}')
        (self.data/'process.json').write_text(json.dumps(dict(ProcessId=1234,Name='notepad.exe',CommandLine='unrelated')))
        self.assertIn('Stopped',self.run_command('status'))
        self.assertIn('Started',self.run_command())

    def test_missing_installation_and_failed_start_report_errors(self):
        (self.app/'start.ps1').write_text("throw 'simulated start failure'")
        self.assertIn('simulated start failure',self.run_command(expected=1))
        (self.root/'install.json').unlink()
        self.assertIn('installation not found',self.run_command(expected=1))
        self.assertIn('codex-pet [',self.run_command('help'))

    def test_version_status_do_not_launch_or_modify_installation(self):
        self.assertIn('0.4.5',self.run_command('version'))
        self.assertIn('Stopped',self.run_command('status'))
        self.assertFalse((self.data/'launch-count.txt').exists())

    def test_sounds_import_real_python_with_spaces_and_running_guard(self):
        scripts = ROOT/'plugins/reset-reminder/skills/reset-reminder/scripts'
        sys.path.insert(0, str(scripts))
        import voice_pack
        shutil.copyfile(scripts/'voice_pack.py', self.script.parent/'voice_pack.py')
        info = json.loads((self.root/'install.json').read_text())
        info['pythonw'] = str(Path(sys.executable).with_name('pythonw.exe'))
        (self.root/'install.json').write_text(json.dumps(info))
        self.assertIn('original-synthesis', self.run_command('sounds'))
        self.assertFalse((self.data/'launch-count.txt').exists())
        source = self.root/'personal voice folder'
        source.mkdir()
        (source/'manifest.json').write_text('{"provider":"amitaro"}')
        for name in voice_pack.NAMES:
            voice_pack.write_pcm(source/(name+'.wav'), [1000]*4410)
        self.assertIn('Installed Amitaro', self.run_command('sounds', source=source))
        self.assertIn('amitaro (8 clips)', self.run_command('sounds'))
        self.assertIn('failed', self.run_command('sounds', source=self.root/'missing', expected=1))
        self.run_command('start')
        self.assertIn('Exit the pet', self.run_command('sounds', source=source, expected=1))


if __name__ == '__main__':
    unittest.main()
