[CmdletBinding()]
param(
    [ValidateSet('start','status','version','help','sounds')]
    [string]$Action = 'start',
    [string]$Source
)
$ErrorActionPreference = 'Stop'
try {
    if ($Action -eq 'help') {
        Write-Output 'codex-pet [start|status|version|help|sounds]'
        Write-Output 'codex-pet sounds [voice-folder] - inspect or import personal voices offline'
        Write-Output 'Start the installed desktop pet locally, without an AI request.'
        exit 0
    }
    $installRoot = Split-Path $PSScriptRoot -Parent
    $record = Join-Path $installRoot 'install.json'
    if (-not (Test-Path -LiteralPath $record)) {
        throw 'Desktop installation not found. Run install.ps1 first.'
    }
    $info = Get-Content -Raw -Encoding UTF8 -LiteralPath $record | ConvertFrom-Json
    if ($Source -and $Action -ne 'sounds') { throw 'A source folder is only supported with: codex-pet sounds [voice-folder]' }
    if ($Action -eq 'version') { Write-Output $info.version; exit 0 }
    $petScript = Join-Path $info.appRoot 'plugins/reset-reminder/skills/reset-reminder/scripts/desktop_pet.py'
    $settings = Join-Path $info.dataDir 'desktop-settings.json'
    function Find-RunningPet {
        $statusFile = Join-Path $info.dataDir 'desktop-runtime.json'
        try {
            $status = Get-Content -Raw -Encoding UTF8 -LiteralPath $statusFile | ConvertFrom-Json
            $petProcessId = [int]$status.pid
            if ($petProcessId -le 0 -or $status.lifecycle -eq 'closed') { return $null }
            $process = Get-CimInstance Win32_Process -Filter "ProcessId=$petProcessId" -ErrorAction Stop
            if ($process -and $process.Name -in @('python.exe','pythonw.exe') -and
                $process.CommandLine.Contains($petScript) -and $process.CommandLine.Contains($settings)) {
                return $process
            }
        } catch { return $null }
        return $null
    }
    if ($Action -eq 'status') {
        $running = Find-RunningPet
        if ($running) { Write-Output "Running (PID $($running.ProcessId))" }
        else { Write-Output 'Stopped' }
        exit 0
    }
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $key = ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($installRoot.ToLowerInvariant())))).Replace('-','') }
    finally { $hash.Dispose() }
    $mutex = New-Object Threading.Mutex($false, ('Local\CodexResetPet-Start-'+$key))
    $ownsMutex = $false
    try {
        try { $ownsMutex = $mutex.WaitOne(0) }
        catch [Threading.AbandonedMutexException] { $ownsMutex = $true }
        if (-not $ownsMutex) { throw 'Another start or voice import is in progress; retry shortly.' }
        if ($Action -eq 'sounds') {
            if ($Source -and (Find-RunningPet)) { throw 'Exit the pet using its right-click menu before importing voices, then retry.' }
            $python = Join-Path (Split-Path $info.pythonw -Parent) 'python.exe'
            $voiceScript = Join-Path $info.appRoot 'plugins/reset-reminder/skills/reset-reminder/scripts/voice_pack.py'
            $voiceArgs = @('-X','utf8',$voiceScript,'--data-dir',$info.dataDir)
            if ($Source) { $voiceArgs += @('--source',$Source) }
            & $python @voiceArgs
            $voiceExit = $LASTEXITCODE
            if (-not $Source -and (Find-RunningPet)) {
                $runtime = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $info.dataDir 'desktop-runtime.json') | ConvertFrom-Json
                Write-Output "Running pet: sound_pack=$($runtime.sound_pack), sound_enabled=$($runtime.sound_enabled)"
            }
            exit $voiceExit
        }
        $running = Find-RunningPet
        if ($running) { Write-Output "Already running (PID $($running.ProcessId))"; exit 0 }
        $startScript = Join-Path $info.appRoot 'start.ps1'
        if (-not (Test-Path -LiteralPath $startScript) -or -not (Test-Path -LiteralPath $info.pythonw)) {
            throw 'Installation is incomplete. Run the desktop installer again to repair it.'
        }
        & $startScript -DataDir $info.dataDir -PythonExe $info.pythonw
        $deadline = [DateTime]::UtcNow.AddSeconds(10)
        do {
            $running = Find-RunningPet
            if ($running) { Write-Output "Started (PID $($running.ProcessId))"; exit 0 }
            Start-Sleep -Milliseconds 200
        } while ([DateTime]::UtcNow -lt $deadline)
        throw "Pet startup was not confirmed. Check $($info.dataDir)/desktop-events.log and desktop-crash.log."
    } finally {
        if ($ownsMutex) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
} catch {
    [Console]::Error.WriteLine('codex-pet: '+$_.Exception.Message)
    exit 1
}
