# Codex Reset Pet · Desktop Reset Companion

[![简体中文](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-6e7781?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/Language-English-0969da?style=for-the-badge)](README.en.md)

I kept missing reset times and letting resets go to waste, so I built this desktop companion. It includes a **tibo reset** button that opens [the Tibo reset tracker](https://codex-reset.com/zh/tibo).

A persistent Windows desktop pet that displays **Codex account quota resets** and **reset-credit expiration times**, with countdowns and a companion plugin for checking Tibo updates. Times are shown in Beijing time (UTC+8).

<img src="docs/pet-preview.png" width="288" alt="Sleep-state rendering preview, with growing zzz particles floating above the pet's head">

This is an independent local desktop application and Codex skill plugin, not an official OpenAI Pet. It supports Windows 10/11 and does not require an API key. Account synchronization requires a signed-in Codex desktop environment that provides the account usage tool. The desktop interface currently uses Chinese; this README is its English guide.

## One-command installation

Paste this line into **PowerShell** to install the pinned **v0.4.2** release:

The features below describe the `main` branch. The v0.4.2 package does not include the remaining-quota progress bar or manual refresh button added afterward. To get the latest features, use the source installation instructions below.

```powershell
$f = Join-Path $env:TEMP 'codex-reset-pet-install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/v0.4.2/install.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f
```

The installer downloads the release package and verifies its SHA-256 checksum. It checks for Python, installs Python 3.12 for the current user through winget if needed, installs Pillow in an isolated virtual environment, creates a desktop shortcut, and launches the pet. If it finds the Codex CLI, it also installs the companion plugin. Git is not required, and administrator privileges are normally unnecessary. Installation requires access to GitHub and PyPI, plus the winget package source if Python needs to be installed.

The default installation directory is `%LOCALAPPDATA%\CodexResetPet`. Installation does not create scheduled checks, enable Windows startup, or read your login credentials. You can inspect the [installer](install.ps1) or download the package manually from [Releases](https://github.com/FantasyWorld-G/codex-reset-pet/releases/tag/v0.4.2).

## First-time setup

After installation, open a **new Codex chat** and send:

> Use the reset-reminder plugin to synchronize my account quota reset and reset-credit expiration information to the installed desktop pet. Synchronize once only; do not create a scheduled task.

Until the first synchronization, the window shows “等待账户同步” (waiting for account synchronization). The package does not contain the publisher's account information. The latest source version also offers a Refresh button that obtains quota and reset times through your signed-in Codex CLI. Reset-credit expiration details still require a full account synchronization.

To enable automatic synchronization, explicitly ask Codex:

> Synchronize the desktop pet's account status every hour and check for Tibo reset updates. Notify me only when there is something actionable.

You can later say, “Turn off the reset reminder's scheduled task.” Automatic checks require the computer to be awake, Codex to be running, and network access and sufficient Codex quota to be available. The pet does not independently access your account in the background.

## Controls and display

| Action | Result |
| --- | --- |
| Click the pet | Wave/wink and toggle the information bubble; every third click triggers a pout |
| Drag the pet | Move the window while the pet looks surprised and tilts |
| Release after dragging | Play a happy bounce, then return to idle |
| Leave it untouched for 10 seconds | Enter sleep and stay asleep, with growing zzz particles floating upward |
| Click or drag while asleep | Wake the pet and respond to the interaction; it will not fall asleep while held |
| Click `刷新` (Refresh) | Retrieve quota and reset time through the signed-in Codex CLI without blocking animation |
| Click `tibo reset` | Open the [Tibo page](https://codex-reset.com/zh/tibo) in the default browser |
| Click × in the information bubble | Collapse the bubble without quitting |
| Right-click the pet → `退出桌面小精灵` | Quit the application |

Dates and remaining-time labels change color independently as their deadlines approach. The character retains its original colors. Animation states switch directly without inserting unrelated expressions. Animation targets 60Hz; actual performance depends on system load. Account snapshots older than 90 minutes are marked as needing synchronization. Time colors continue to reflect the recorded deadlines; they indicate urgency, not freshly verified account data.

The account card also displays the remaining quota percentage and a progress bar, calculated as `100 - usedPercent` from Codex's account status. It updates when the account snapshot is refreshed. Missing data is shown as `--`; stale data is labeled “上次同步” (last synchronized value). The window rereads local data every 5 seconds and recalculates countdowns every 0.5 seconds; neither operation requests account data. Click Refresh to call Codex’s read-only `account/rateLimits/read` endpoint. This does not enable scheduled tasks or start a model turn. Duplicate clicks are disabled while refreshing; failures show a message and retain the last data.

Manual refreshes use a separate `desktop-usage.json` cache and do not overwrite the plugin’s full `usage.json` snapshot. The newest quota snapshot wins. Some CLI versions return only the reset-credit count, without expiration details; the card then shows “上次记录” (previous record). Perform a full account synchronization to update credit expiration details.

## Other installation options

If Python 3.10+ with tkinter is already installed, download the source code, open PowerShell in the extracted repository directory, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath .
```

To install only the Codex query plugin, without the desktop application:

```powershell
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.2
codex plugin add reset-reminder@codex-reset-pet
```

See the [official OpenAI plugin documentation](https://developers.openai.com/plugins/build/plugins) for marketplace installation details. Installing only the query plugin does not install Python or Pillow and does not start the desktop pet.

## Documentation and maintenance

- [Complete user guide: synchronization, installer options, updates, uninstalling, and troubleshooting (Chinese)](docs/使用说明.md)
- [Changelog (Chinese)](CHANGELOG.md)
- [Character asset generation notes (Chinese)](plugins/reset-reminder/assets/生成说明.txt)

The repository contains code, tests, and character assets. It does not contain account snapshots, credentials, logs, or personal scheduled-task settings. Community updates are classified as signals, pending verification, community-confirmed resets, or banked resets. Community confirmation does not prove that a reset has reached your account. The plugin never redeems reset credits automatically.

## Development and testing

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s plugins/reset-reminder/tests -v
python scripts/build_release.py
```

The 40 tests cover animation state transitions, countdowns, reset-credit filtering, notification deduplication, and native Windows drag regression. Native-window integration tests are skipped on non-Windows systems. The release package and checksum file are written to `dist/`. Packaging uses an explicit file allowlist to exclude runtime data and caches.
