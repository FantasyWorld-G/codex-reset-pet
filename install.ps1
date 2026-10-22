[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'CodexResetPet'),
    [string]$SourcePath,
    [switch]$NoLaunch,
    [switch]$NoShortcut,
    [switch]$SkipPlugin
)
$ErrorActionPreference = 'Stop'
$Version = '0.4.1'
$Repository = 'FantasyWorld-G/codex-reset-pet'
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
$appRoot = Join-Path $InstallRoot ('app/'+$Version)
$dataRoot = Join-Path $InstallRoot 'data'
$runtimeRoot = Join-Path $InstallRoot 'runtime'
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ('codex-reset-pet-'+[Guid]::NewGuid().ToString('N'))

function Find-Python {
    $candidates = @()
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*WindowsApps*') { $candidates += $command.Source }
    $candidates += @(Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs/Python/Python*/python.exe') -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object FullName)
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        & $candidate -c 'import sys,tkinter,venv; assert sys.version_info >= (3,10)' 2>$null
        if ($LASTEXITCODE -eq 0) { return $candidate }
    }
    return $null
}

try {
    New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
    if (-not $SourcePath) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $releaseBase = "https://github.com/$Repository/releases/download/v$Version"
        $archiveName = "codex-reset-pet-v$Version.zip"
        $archivePath = Join-Path $temporaryRoot $archiveName
        Write-Host "Downloading Codex Reset Pet $Version..."
        Invoke-WebRequest -UseBasicParsing -Uri "$releaseBase/$archiveName" -OutFile $archivePath
        $checksumPath = Join-Path $temporaryRoot 'SHA256SUMS.txt'
        Invoke-WebRequest -UseBasicParsing -Uri "$releaseBase/SHA256SUMS.txt" -OutFile $checksumPath
        $checksumLine = @(Get-Content -LiteralPath $checksumPath | Where-Object { $_ -match ('^[0-9a-fA-F]{64}\s+'+[regex]::Escape($archiveName)+'$') })
        if ($checksumLine.Count -ne 1) { throw 'Release checksum is missing or ambiguous.' }
        $expected = ($checksumLine[0] -split '\s+')[0]
        if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -ne $expected) { throw 'Download checksum mismatch.' }
        $unpackRoot = Join-Path $temporaryRoot 'unpacked'
        Expand-Archive -LiteralPath $archivePath -DestinationPath $unpackRoot
        $SourcePath = Join-Path $unpackRoot 'codex-reset-pet'
    }
    $SourcePath = (Resolve-Path -LiteralPath $SourcePath).Path
    $manifestPath = Join-Path $SourcePath 'plugins/reset-reminder/.codex-plugin/plugin.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Invalid source package.' }
    $manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
    if ($manifest.version -ne $Version) { throw 'Installer and package versions differ.' }

    $pythonExe = Find-Python
    if (-not $pythonExe) {
        if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
            throw 'Install Python 3.10+ with tkinter from python.org, then run this command again.'
        }
        Write-Host 'Installing per-user Python 3.12 with winget...'
        & winget.exe install --id Python.Python.3.12 --exact --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw 'Python installation failed. Install Python manually and retry.' }
        $pythonExe = Find-Python
        if (-not $pythonExe) { throw 'Python with tkinter is still unavailable.' }
    }
    New-Item -ItemType Directory -Path $appRoot,$dataRoot -Force | Out-Null
    if ($SourcePath.TrimEnd('\') -ne $appRoot.TrimEnd('\')) {
        foreach ($item in Get-ChildItem -LiteralPath $SourcePath -Force) {
            if ($item.Name -notin @('.git','.venv','__pycache__','dist','data','runtime','work')) {
                Copy-Item -LiteralPath $item.FullName -Destination $appRoot -Recurse -Force
            }
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $runtimeRoot 'Scripts/python.exe'))) {
        & $pythonExe -m venv $runtimeRoot
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated Python environment.' }
    }
    $runtimePython = Join-Path $runtimeRoot 'Scripts/python.exe'
    & $runtimePython -m pip install --disable-pip-version-check -r (Join-Path $appRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; rerun to retry.' }
    & $runtimePython -c 'import tkinter; from PIL import Image,ImageTk,ImageDraw,ImageFont'
    if ($LASTEXITCODE -ne 0) { throw 'Runtime dependency check failed.' }
    $pythonw = Join-Path $runtimeRoot 'Scripts/pythonw.exe'
    $pluginInstalled = $false
    if (-not $SkipPlugin) {
        $codexCommand = Get-Command codex.exe -ErrorAction SilentlyContinue
        $codexPath = if ($codexCommand) { $codexCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs/OpenAI/Codex/bin/codex.exe' }
        if (Test-Path -LiteralPath $codexPath) {
            & $codexPath plugin marketplace add $appRoot
            if ($LASTEXITCODE -ne 0) { throw 'Codex marketplace registration failed. Update Codex or rerun with -SkipPlugin.' }
            & $codexPath plugin add 'reset-reminder@codex-reset-pet'
            if ($LASTEXITCODE -ne 0) { throw 'Codex plugin installation failed. Update Codex or rerun with -SkipPlugin.' }
            $pluginInstalled = $true
        } else {
            Write-Warning 'Codex CLI not found. Desktop pet installed; install Codex and rerun to add account synchronization.'
        }
    }
    $startScript = Join-Path $appRoot 'start.ps1'
    if (-not $NoShortcut) {
        $shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Codex Reset Pet.lnk'
        $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
        $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
        $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$startScript+'" -DataDir "'+$dataRoot+'" -PythonExe "'+$pythonw+'"'
        $shortcut.WorkingDirectory = $appRoot
        $shortcut.Description = 'Codex Reset Pet - desktop reset countdown'
        $shortcut.Save()
    }
    $info = @{version=$Version;appRoot=$appRoot;dataDir=$dataRoot;pythonw=$pythonw;pluginInstalled=$pluginInstalled}
    [IO.File]::WriteAllText((Join-Path $InstallRoot 'install.json'),($info | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
    if (-not $NoLaunch) { & $startScript -DataDir $dataRoot -PythonExe $pythonw }
    Write-Host "Installed $Version at $appRoot"
    Write-Host "Account snapshot directory: $dataRoot"
    Write-Host 'Open a new Codex chat and ask the reset-reminder plugin to synchronize your account once.'
    Write-Host 'No scheduled checks or Windows startup task have been enabled.'
} finally {
    $resolvedTemporary = [IO.Path]::GetFullPath($temporaryRoot)
    $temporaryParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')+'\'
    if ($resolvedTemporary.StartsWith($temporaryParent,[StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($resolvedTemporary) -match '^codex-reset-pet-[0-9a-f]{32}$' -and
        (Test-Path -LiteralPath $resolvedTemporary)) {
        Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
    }
}
