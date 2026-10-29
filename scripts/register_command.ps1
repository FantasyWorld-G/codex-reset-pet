param([Parameter(Mandatory=$true)][string]$InstallRoot, [switch]$NoPath)
$ErrorActionPreference = 'Stop'
$info = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $InstallRoot 'install.json') | ConvertFrom-Json
$bin = Join-Path ([IO.Path]::GetFullPath($InstallRoot)) 'bin'
New-Item -ItemType Directory -Path $bin -Force | Out-Null
foreach ($name in @('codex-pet.cmd','codex-pet.ps1')) {
    Copy-Item -LiteralPath (Join-Path $info.appRoot $name) -Destination (Join-Path $bin $name) -Force
}
if (-not $NoPath) {
    # Preserve the existing user PATH verbatim; never overwrite the machine PATH.
    $current = [Environment]::GetEnvironmentVariable('Path','User')
    $present = @($current -split ';' | Where-Object { $_.Trim().TrimEnd('\') -ieq $bin.TrimEnd('\') }).Count -gt 0
    if (-not $present) {
        $updated = if ([string]::IsNullOrEmpty($current)) { $bin } else { $current.TrimEnd(';')+';'+$bin }
        [Environment]::SetEnvironmentVariable('Path',$updated,'User')
    }
    if (-not (@($env:Path -split ';') -contains $bin)) { $env:Path += ';'+$bin }
    # Explorer picks up changes for newly opened terminals; existing apps may need restarting.
    if (-not ('PetEnvironmentBroadcast' -as [type])) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PetEnvironmentBroadcast {
    [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern IntPtr SendMessageTimeout(IntPtr h, uint m, UIntPtr w, string l, uint f, uint t, out UIntPtr r);
}
'@
    }
    $broadcastResult = [UIntPtr]::Zero
    [PetEnvironmentBroadcast]::SendMessageTimeout([IntPtr]0xffff,0x1a,[UIntPtr]::Zero,'Environment',2,1000,[ref]$broadcastResult) | Out-Null
    Write-Host 'Command installed: codex-pet. Open a new terminal (restart your terminal app if needed).'
} else { Write-Host "Command files installed in $bin (PATH unchanged)." }
