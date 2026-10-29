param([Parameter(Mandatory=$true)][string]$InstallRoot)
$ErrorActionPreference = 'Stop'
$record = Join-Path $InstallRoot 'install.json'
if (-not (Test-Path -LiteralPath $record)) { return }
$old = Get-Content -Raw -Encoding UTF8 -LiteralPath $record | ConvertFrom-Json
$runtime = Join-Path $old.dataDir 'desktop-runtime.json'
if (-not (Test-Path -LiteralPath $runtime)) { return }
$state = Get-Content -Raw -Encoding UTF8 -LiteralPath $runtime | ConvertFrom-Json
if ($state.lifecycle -eq 'closed' -or [int]$state.pid -le 0) { return }
$petProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$state.pid)"
if (-not $petProcess) { return }
$scriptPath = (Join-Path $old.appRoot 'plugins/reset-reminder/skills/reset-reminder/scripts/desktop_pet.py').Replace('/','\').ToLowerInvariant()
$settingsPath = (Join-Path $old.dataDir 'desktop-settings.json').Replace('/','\').ToLowerInvariant()
$command = [string]$petProcess.CommandLine
$command = $command.Replace('/','\').ToLowerInvariant()
if ($petProcess.Name -notin @('python.exe','pythonw.exe') -or
    -not $command.Contains($scriptPath) -or -not $command.Contains($settingsPath)) {
    # Stale PID files must never close another process.
    return
}
if (-not ('PetUpgradeClose' -as [type])) {
    Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class PetUpgradeClose {
    private delegate bool Visitor(IntPtr hwnd, IntPtr param);
    [DllImport("user32.dll")] private static extern bool EnumWindows(Visitor visit, IntPtr param);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetClassName(IntPtr hwnd, StringBuilder name, int size);
    [DllImport("user32.dll")] private static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr w, IntPtr l);
    public static int Close(int pid) {
        int count = 0;
        Visitor visit = (hwnd, param) => {
            uint owner;
            GetWindowThreadProcessId(hwnd, out owner);
            if (owner == (uint)pid) {
                var name = new StringBuilder(256);
                GetClassName(hwnd, name, name.Capacity);
                if (name.ToString() == "TkTopLevel" && PostMessage(hwnd, 0x10, IntPtr.Zero, IntPtr.Zero)) count++;
            }
            return true;
        };
        EnumWindows(visit, IntPtr.Zero);
        return count;
    }
}
'@
}
Write-Host 'Closing the previous desktop pet gracefully before installing the new version...'
if ([PetUpgradeClose]::Close([int]$state.pid) -eq 0) {
    throw 'Could not find the existing pet window. Exit it from its right-click menu and retry.'
}
Wait-Process -Id ([int]$state.pid) -Timeout 15 -ErrorAction SilentlyContinue
if (Get-Process -Id ([int]$state.pid) -ErrorAction SilentlyContinue) {
    throw 'The previous pet is still closing. Wait, then retry installation; it has not been force-terminated.'
}
