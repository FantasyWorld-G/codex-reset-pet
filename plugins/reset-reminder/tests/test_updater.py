"""Exercise the updater in PowerShell with isolated download/installer fixtures."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]

HARNESS=r'''
param([string]$Updater,[string]$InstallRoot,[string]$Case)
$ErrorActionPreference='Stop'
$script:downloaded=$null
function Invoke-RestMethod {
    param($Uri,$Headers)
    if ($Uri -ne 'https://api.github.com/repos/FantasyWorld-G/codex-reset-pet/releases/latest') { throw 'Unexpected release URL' }
    return @{tag_name='v0.4.3'; draft=$false; prerelease=($Case -eq 'prerelease')}
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing,$Uri,$OutFile)
    if ($Uri -ne 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/v0.4.3/install.ps1') { throw 'Installer tag mismatch' }
    $script:downloaded=$OutFile
    if ($Case -eq 'download-fail') { throw 'Download failed' }
    $stub=@'
param([string]$InstallRoot,[switch]$NoLaunch,[switch]$NoShortcut,[switch]$SkipPlugin)
$result=@{root=$InstallRoot;noLaunch=[bool]$NoLaunch;noShortcut=[bool]$NoShortcut;skipPlugin=[bool]$SkipPlugin}
[IO.File]::WriteAllText((Join-Path $InstallRoot 'arguments.json'),($result | ConvertTo-Json))
if (Test-Path -LiteralPath (Join-Path $InstallRoot 'fail-installer')) { exit 7 }
exit 0
'@
    [IO.File]::WriteAllText($OutFile,$stub)
}
$failed=$false
try { & $Updater -InstallRoot $InstallRoot -NoLaunch -NoShortcut -SkipPlugin }
catch { $failed=$true }
if (($Case -eq 'success') -eq $failed) { throw 'Unexpected updater outcome' }
if ($script:downloaded -and (Test-Path -LiteralPath $script:downloaded)) { throw 'Temporary installer leaked' }
if ([IO.File]::ReadAllText((Join-Path $InstallRoot 'data/usage.json')) -ne 'preserve-existing-data') { throw 'Account cache changed' }
Write-Output 'UPDATER_CASE_PASSED'
'''


@unittest.skipUnless(os.name=='nt','Windows PowerShell updater')
class UpdaterTests(unittest.TestCase):
    def run_case(self,case):
        with tempfile.TemporaryDirectory(prefix='reset updater ') as directory:
            folder=Path(directory)
            (folder/'data').mkdir()
            (folder/'data/usage.json').write_text('preserve-existing-data')
            if case=='installer-fail':(folder/'fail-installer').touch()
            harness=folder/'harness.ps1'
            harness.write_text(HARNESS,'utf-8')
            result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass',
                '-File',str(harness),'-Updater',str(ROOT/'update.ps1'),'-InstallRoot',directory,'-Case',case],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            self.assertIn('UPDATER_CASE_PASSED',result.stdout)
            if case in ('success','installer-fail'):
                args=json.loads((folder/'arguments.json').read_text())
                # PowerShell expands Windows short names (RUNNER~1) to long paths.
                self.assertTrue(os.path.samefile(args['root'], directory))
                self.assertTrue(all(args[k] for k in ('noLaunch','noShortcut','skipPlugin')))
            else:self.assertFalse((folder/'arguments.json').exists())

    def test_success_preserves_custom_path_with_spaces_and_options(self):self.run_case('success')
    def test_download_failure_preserves_data(self):self.run_case('download-fail')
    def test_installer_failure_is_reported_and_temp_cleaned(self):self.run_case('installer-fail')
    def test_prerelease_not_installed(self):self.run_case('prerelease')


if __name__=='__main__':unittest.main()
