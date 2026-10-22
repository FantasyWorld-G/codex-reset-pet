param([string]$DataDir, [string]$PythonExe)
$ErrorActionPreference = 'Stop'
if (-not $DataDir) { $DataDir = Join-Path $env:LOCALAPPDATA 'CodexResetPet/data' }
if (-not $PythonExe) {
    $runtimeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    $candidate = Join-Path $runtimeRoot 'runtime/Scripts/pythonw.exe'
    if (Test-Path -LiteralPath $candidate) { $PythonExe = $candidate }
    else {
        $pythonCommand = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        if (-not $pythonCommand) { throw 'Python not found. Run install.ps1 first.' }
        $PythonExe = $pythonCommand.Source
    }
}
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
$script = Join-Path $PSScriptRoot 'plugins/reset-reminder/skills/reset-reminder/scripts/desktop_pet.py'
$usage = Join-Path $DataDir 'usage.json'
$settings = Join-Path $DataDir 'desktop-settings.json'
$arguments = @(('"'+$script+'"'),'--usage',('"'+$usage+'"'),'--settings',('"'+$settings+'"'))
# The requested desktop widget is visible; pythonw itself has no console.
Start-Process -FilePath $PythonExe -ArgumentList $arguments -WindowStyle Hidden
