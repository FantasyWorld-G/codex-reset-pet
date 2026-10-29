# Codex Reset Pet · Desktop Reset Companion

[![简体中文](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-6e7781?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/Language-English-0969da?style=for-the-badge)](README.en.md)

I kept missing reset times and letting resets go to waste, so I built this desktop companion. It includes a **tibo reset** button that opens [the Tibo reset tracker](https://codex-reset.com/zh/tibo).

A persistent Windows desktop pet that displays **Codex account quota resets** and **reset-credit expiration times**, with countdowns and a companion plugin for checking Tibo updates. Times are shown in Beijing time (UTC+8).

<img src="docs/pet-preview.png" width="288" alt="Sleep-state rendering preview, with growing zzz particles floating above the pet's head">

This is an independent local desktop application and Codex skill plugin, not an official OpenAI Pet. It supports Windows 10/11 and does not require an API key. Account synchronization requires a signed-in Codex desktop environment that provides the account usage tool. The desktop interface currently uses Chinese; this README is its English guide.

## Install through Codex (plugin first)

For first-time setup, run this entire block in PowerShell or the Codex terminal. The pet launches automatically when installation completes:

```powershell
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.5
codex plugin add reset-reminder@codex-reset-pet
codex plugin list --marketplace codex-reset-pet

# Install and launch the desktop pet (the plugin was installed above)
$f = Join-Path $env:TEMP 'codex-reset-pet-install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/v0.4.5/install.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f -SkipPlugin
```

The first three lines install the Codex query/reminder plugin. The final line installs the desktop app and Python/Pillow dependencies, creates a shortcut, and launches the pet. `-SkipPlugin` avoids duplicate plugin registration; it does not skip desktop installation or launch. For plugin-only setup, run only the first three lines. Open a new Codex chat to synchronize your account; the pet still opens with a waiting-for-sync message before account data is available.

Commands are documented in the [official OpenAI CLI reference](https://learn.chatgpt.com/docs/cli/reference).

## Desktop pet: one-command installation

Paste this line into **PowerShell** to install the pinned **v0.4.5** release:

**v0.4.5 includes double-click head pats, interaction sounds, a happy reaction after dragging, Tibo forecasts and history, independent startup fixes, and optional expiring-credit redemption (off by default).** Quota display, Refresh, and urgency colors are retained. Existing users should use the updater below. Third-party recordings are not bundled; the installer includes synthesized sounds.

```powershell
$f = Join-Path $env:TEMP 'codex-reset-pet-install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/v0.4.5/install.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f
```

The installer downloads the release package and verifies its SHA-256 checksum. It checks for Python, installs Python 3.12 for the current user through winget if needed, installs Pillow in an isolated virtual environment, creates a desktop shortcut, and launches the pet. If it finds the Codex CLI, it also installs the companion plugin. Git is not required, and administrator privileges are normally unnecessary. Installation requires access to GitHub and PyPI, plus the winget package source if Python needs to be installed.

The default installation directory is `%LOCALAPPDATA%\CodexResetPet`. Installation does not create scheduled checks, enable Windows startup, or read your login credentials. You can inspect the [installer](install.ps1) or download the package manually from [Releases](https://github.com/FantasyWorld-G/codex-reset-pet/releases/tag/v0.4.5).

## Other installation options

### Manual release download (no Git required)

Download `codex-reset-pet-v0.4.5.zip` and `SHA256SUMS.txt` from [Release v0.4.5](https://github.com/FantasyWorld-G/codex-reset-pet/releases/tag/v0.4.5). Put both files in one directory and verify the checksum before extracting the archive:

```powershell
$archive = (Resolve-Path '.\codex-reset-pet-v0.4.5.zip').Path
$expected = ((Get-Content '.\SHA256SUMS.txt' | Where-Object { $_ -match '\s+codex-reset-pet-v0\.4\.5\.zip$' }) -split '\s+')[0]
$sha256 = [Security.Cryptography.SHA256]::Create()
$archiveStream = [IO.File]::OpenRead($archive)
try { $actual = ([BitConverter]::ToString($sha256.ComputeHash($archiveStream))).Replace('-','') }
finally { $archiveStream.Dispose(); $sha256.Dispose() }
if ($actual -ne $expected) { throw 'SHA-256 mismatch' }
```

In the extracted `codex-reset-pet` directory, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath .
```

### Git / source installation

With Git installed, run this in the directory where you want to keep the source:

```powershell
git clone --branch v0.4.5 --depth 1 https://github.com/FantasyWorld-G/codex-reset-pet.git
Set-Location codex-reset-pet
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath .
```

You can also download a source ZIP from GitHub and run the same `install.ps1 -SourcePath .` command after extraction. The installer still checks Python and installs Pillow, which requires the corresponding network access.

### Desktop only / custom directory

Choose one of these alternatives from the extracted package or source directory:

```powershell
# Install the desktop app without registering the Codex plugin
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath . -SkipPlugin

# Use a custom installation directory
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath . -InstallRoot 'D:\Apps\CodexResetPet'

# Do not launch or create a desktop shortcut yet
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath . -NoLaunch -NoShortcut
```

Desktop-only installations still require a signed-in Codex CLI for quota refresh. See the [complete user guide (Chinese)](docs/使用说明.md) for all options.

## One-command update (existing installations)

First right-click the pet and choose `退出桌面小精灵` (Exit), then run this in **PowerShell**:

```powershell
$f = Join-Path $env:TEMP 'codex-reset-pet-update.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/main/update.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f
```

The updater finds the latest stable GitHub release and downloads its installer. The installer verifies the package SHA-256, updates the application, plugin, and shortcut, then launches the new version. Account snapshots, window position, and settings in `data/` are preserved. No scheduled task is created. If updating fails, resolve the reported error and retry.

For a custom installation, append `-InstallRoot 'D:\Apps\CodexResetPet'` to the final command, using the original installation directory. Add `-SkipPlugin` for a desktop-only installation `-NoLaunch` to postpone launch, or `-NoShortcut` to skip shortcut creation. Users running directly from a source checkout should update their source or install with `install.ps1 -SourcePath .`; this updater targets installer-managed directories.

After updating, the installed version should be `0.4.5`; double-click for a head pat and use the context menu to toggle sounds. Open a new Codex chat to load the updated companion plugin.

### Update only the Codex plugin

For a Git marketplace installed using the commands above, switch its pinned version to v0.4.5 with:

```powershell
codex plugin marketplace remove codex-reset-pet
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.5
codex plugin add reset-reminder@codex-reset-pet
```

For a future release, replace `v0.4.5` with its published tag. If your Git marketplace intentionally tracks `main`, use the following instead; refreshing a pinned tag does not advance to a newer release:

```powershell
codex plugin marketplace upgrade codex-reset-pet
codex plugin add reset-reminder@codex-reset-pet
```

If the desktop installer registered a local marketplace, use the desktop updater instead. Plugin-only updates do not update desktop files. Start a new Codex chat afterward. [Official marketplace commands](https://learn.chatgpt.com/docs/cli/reference).

## Start again / check installation

After installation, open a new terminal and start the pet with one command, without an AI request:

```powershell
codex-pet
```

`codex-pet start` also launches it; `codex-pet status` reports whether it is running and `codex-pet version` prints the installed version. Repeated starts do not open another instance. This is this project's command, not a `codex` subcommand. Launching needs no network or model quota; quota refresh and Tibo queries still need network access.

The installer appends the installation's `bin` directory to your user PATH. Fully close and reopen existing terminal apps if needed, including the host of embedded terminals. Pass `-NoPath` to install/update without changing PATH; use the desktop shortcut or `& "$env:LOCALAPPDATA\CodexResetPet\bin\codex-pet.cmd"` instead (adjust for custom installations).

Double-click the desktop shortcut, or read the current installation metadata and launch without hard-coding a version:

```powershell
$petRoot = Join-Path $env:LOCALAPPDATA 'CodexResetPet'
$installed = Get-Content -Raw -LiteralPath (Join-Path $petRoot 'install.json') | ConvertFrom-Json
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $installed.appRoot 'start.ps1') -DataDir $installed.dataDir -PythonExe $installed.pythonw
```

For a custom installation, set `$petRoot` to its original directory. To check the desktop version and installed Codex plugin:

```powershell
Get-Content -Raw -LiteralPath (Join-Path $petRoot 'install.json') | ConvertFrom-Json | Select-Object version,appRoot,dataDir
codex plugin list --marketplace codex-reset-pet
```

## First-time setup

After installation, open a **new Codex chat** and send:

> Use the reset-reminder plugin to synchronize my account quota reset and reset-credit expiration information to the installed desktop pet. Synchronize once only; do not create a scheduled task.

Until the first synchronization, the window shows “等待账户同步” (waiting for account synchronization). The package does not contain the publisher's account information. v0.4.5 also offers a Refresh button that obtains quota and reset times through your signed-in Codex CLI. Reset-credit expiration details still require a full account synchronization.

To enable automatic synchronization, explicitly ask Codex:

> Synchronize the desktop pet's account status every hour and check for Tibo reset updates. Notify me only when there is something actionable.

You can later say, “Turn off the reset reminder's scheduled task.” Automatic checks require the computer to be awake, Codex to be running, and network access and sufficient Codex quota to be available. The pet does not independently access your account in the background unless you opt into the optional automatic credit-redemption feature.

## Controls and display

| Action | Result |
| --- | --- |
| Click the pet | Wave/wink and toggle the information bubble; every third click triggers a pout |
| Double-click the pet | Pat its head and play a laugh without toggling the bubble; single clicks wait about 300 ms to distinguish double clicks |
| Drag the pet | Move the window while the pet looks surprised and tilts |
| Release after dragging | Play a happy bounce, then return to idle |
| Leave it untouched for 10 seconds | Enter sleep and stay asleep, with growing zzz particles floating upward |
| Click or drag while asleep | Wake the pet and respond to the interaction; it will not fall asleep while held |
| Click `刷新` (Refresh) | Retrieve quota and reset time through the signed-in Codex CLI without blocking animation |
| Click `tibo reset` | Open the [Tibo page](https://codex-reset.com/zh/tibo) in the default browser |
| Click `更新预估` (v0.4.5 feature) | Refresh the third card's public Tibo forecast immediately |
| Click × in the information bubble | Collapse the bubble without quitting |
| Right-click the pet → `退出桌面小精灵` | Quit the application |

Dates and remaining-time labels change color independently as their deadlines approach. The character retains its original colors. Animation states switch directly without inserting unrelated expressions. Animation targets 60Hz; actual performance depends on system load. Account snapshots older than 90 minutes are marked as needing synchronization. Time colors continue to reflect the recorded deadlines; they indicate urgency, not freshly verified account data.

The account card also displays the remaining quota percentage and a progress bar, calculated as `100 - usedPercent` from Codex's account status. It updates when the account snapshot is refreshed. Missing data is shown as `--`; stale data is labeled “上次同步” (last synchronized value). The window rereads local data every 5 seconds and recalculates countdowns every 0.5 seconds; neither operation requests account data. Click Refresh to call Codex’s read-only `account/rateLimits/read` endpoint. This does not enable scheduled tasks or start a model turn. Duplicate clicks are disabled while refreshing; failures show a message and retain the last data.

Manual refreshes use a separate `desktop-usage.json` cache and do not overwrite the plugin’s full `usage.json` snapshot. The newest quota snapshot wins. Some CLI versions return only the reset-credit count, without expiration details; the card then shows “上次记录” (previous record). Perform a full account synchronization to update credit expiration details.

## Documentation and maintenance

v0.4.5 adds original nonverbal synthesized sounds for taps, pouts, pickup, landing, and waking. Entering sleep plays one three-second clip without looping. Idle animations and background refreshes remain silent. Right-click the pet to mute; the preference is saved. No additional audio runtime dependency is required.

An optional personal Amitaro recording pack is supported in `voice-amitaro` beside the settings file. A complete pack and manifest enable it automatically, with attribution in the README and voice documentation. Attribution is not shown on the desktop or in the context menu. Third-party recordings are not distributed in this repository or installer. See [voice notes and credits](docs/voice-credits.md).

Each expression uses distinct rhythm, resonance, and breathiness. Moving the pet at least 180 screen pixels from the drag origin triggers one cheerful three-part chuckle per gesture. An immediate release keeps the chuckle playing while the landing animation proceeds normally.

v0.4.5 fixes launcher lifetime coupling: use `start.ps1` to launch through the local Windows process creation interface, so launcher job cleanup does not terminate the pet. Runtime diagnostics update every 30 seconds, and explicit closes record their reason. Check `desktop-launcher.log` in the data directory if startup fails.

v0.4.5: right-click the pet → 临期重置卡自动使用 to opt into either 16–6 minutes before expiration or the last 5 minutes. It binds to the signed-in account, requires fresh details and exact credit selection, and preserves an idempotency key across retries. It is off by default. It cannot execute while the pet is closed or the computer is asleep, and missed windows are skipped.

v0.4.5 also includes a previous Tibo reset card with its time, confirmation status, the website announcement, website categories, and a source-post button. Categories are not official explanations. Click the announcement preview to read its details. History refreshes together with the forecast.

**v0.4.5 feature:** a separate Tibo forecast card fetches the website's public forecast at startup and every 5 minutes while the pet runs. It displays a structured announcement target in Beijing time with a countdown and urgency colors, or “暂无明确预告” when no explicit target exists. Probabilities are never converted to definite dates. Failed requests retain clearly labeled cached data; records older than one hour are marked stale. This does not send account data or enable Codex scheduled tasks. Website observations do not confirm a reset for your account. This feature is included in the v0.4.5 release package.

- [Complete user guide: synchronization, installer options, updates, uninstalling, and troubleshooting (Chinese)](docs/使用说明.md)
- [Changelog (Chinese)](CHANGELOG.md)
- [Character asset generation notes (Chinese)](plugins/reset-reminder/assets/生成说明.txt)

The repository contains code, tests, and character assets. It does not contain account snapshots, credentials, logs, or personal scheduled-task settings. Community updates are classified as signals, pending verification, community-confirmed resets, or banked resets. Community confirmation does not prove that a reset has reached your account. The reminder plugin does not redeem credits. The desktop feature can redeem an expiring credit only after the user explicitly enables it.

## Development and testing

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s plugins/reset-reminder/tests -v
python scripts/build_release.py
```

The 90 tests cover animation state transitions, countdowns, reset-credit filtering, notification deduplication, connection failures and recovery, timeouts, cancellation, malformed responses, save failures, Tibo forecast parsing, and native Windows layout and refresh regression. Native-window integration tests are skipped on non-Windows systems. See the [failure-handling test report (Chinese)](docs/异常处理测试.md). The release package and checksum file are written to `dist/`. Packaging uses an explicit file allowlist to exclude runtime data and caches.

Double-click the pet to pat its head and play a gentle laugh; the context menu also offers this action. Two nearby taps within 300 ms trigger one head pat without toggling the bubble or counting toward the every-third-tap pout. Single taps wait 300 ms; dragging responds immediately.

## Voice credits

The optional personal recording pack uses voices by **Amitaro’s Voice Material Studio — あみたろの声素材工房** ([official website](https://amitaro.net/)). Thank you to the creator for providing these recordings. They are governed by the [author’s terms](https://amitaro.net/voice/terms/), not this project’s source license. Third-party recordings are not included in the repository or installer; the default sounds are synthesized for this project. See [voice notes and credits](docs/voice-credits.md) for the clip mapping.
