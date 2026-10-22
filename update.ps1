[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'CodexResetPet'),
    [switch]$NoLaunch,
    [switch]$NoShortcut,
    [switch]$SkipPlugin
)
$ErrorActionPreference = 'Stop'
$Repository = 'FantasyWorld-G/codex-reset-pet'
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
$temporaryInstaller = Join-Path ([IO.Path]::GetTempPath()) ('codex-reset-pet-update-'+[Guid]::NewGuid().ToString('N')+'.ps1')

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repository/releases/latest" -Headers @{ 'User-Agent'='CodexResetPet-Updater' }
    $tag = [string]$release.tag_name
    if ($release.draft -or $release.prerelease -or $tag -notmatch '^v\d+\.\d+\.\d+$') {
        throw 'No supported stable release found. See the GitHub Releases page.'
    }
    Write-Host "Updating Codex Reset Pet to $tag. Existing data will be preserved."
    Write-Host 'Exit the running pet from its right-click menu before updating.'
    Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/$Repository/$tag/install.ps1" -OutFile $temporaryInstaller
    $installerArguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$temporaryInstaller,'-InstallRoot',$InstallRoot)
    if ($NoLaunch) { $installerArguments += '-NoLaunch' }
    if ($NoShortcut) { $installerArguments += '-NoShortcut' }
    if ($SkipPlugin) { $installerArguments += '-SkipPlugin' }
    & powershell.exe @installerArguments
    if ($LASTEXITCODE -ne 0) { throw "Update failed (installer exit code $LASTEXITCODE). Existing account data is retained; retry after fixing the reported error." }
    Write-Host "Updated to $tag. Click Refresh to read your latest quota."
} finally {
    # This is one uniquely named temporary file, never a directory deletion.
    if (Test-Path -LiteralPath $temporaryInstaller) {
        Remove-Item -LiteralPath $temporaryInstaller -Force
    }
}
