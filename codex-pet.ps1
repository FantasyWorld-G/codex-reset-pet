[CmdletBinding()]
param(
    [ValidateSet('start','status','version','help')]
    [string]$Action = 'start'
)
$ErrorActionPreference = 'Stop'
try {
    if ($Action -eq 'help') {
        Write-Output 'codex-pet [start|status|version|help]'
        Write-Output 'Start the installed desktop pet locally, without an AI request.'
        exit 0
    }
    $installRoot = Split-Path $PSScriptRoot -Parent
    $record = Join-Path $installRoot 'install.json'
    if (-not (Test-Path -LiteralPath $record)) {
        throw 'Desktop installation not found. Run install.ps1 first.'
    }
    $info = Get-Content -Raw -Encoding UTF8 -LiteralPath $record | ConvertFrom-Json
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
        if (-not $ownsMutex) { Write-Output 'Startup is already in progress.'; exit 0 }
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
