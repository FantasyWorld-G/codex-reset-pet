# Codex Reset Pet · Desktop Reset Companion

[![简体中文](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-6e7781?style=for-the-badge)](README.md)
[![English](https://img.shields.io/badge/Language-English-0969da?style=for-the-badge)](README.en.md)

I kept missing reset times and letting resets go to waste, so I built this desktop companion. It includes a **tibo reset** button that opens [the Tibo reset tracker](https://codex-reset.com/zh/tibo).

A persistent Windows desktop pet that displays **Codex account quota resets** and **reset-credit expiration times**, with countdowns and a companion plugin for checking Tibo updates. Times are shown in Beijing time (UTC+8).

<img src="docs/pet-preview.png" width="288" alt="Sleep-state rendering preview, with growing zzz particles floating above the pet's head">

This is an independent local desktop application and Codex skill plugin, not an official OpenAI Pet. It supports Windows 10/11 and does not require an API key. Account synchronization requires a signed-in Codex desktop environment that provides the account usage tool. The desktop interface currently uses Chinese; this README is its English guide.

## Install through Codex (plugin first)

Current version: **v0.4.7**, including all nine current voice reactions. Download and extract the complete release, then double-click **install.cmd** to install/upgrade and launch, or use the Codex setup below.

 For first-time setup, run these two steps in **PowerShell or Codex's PowerShell terminal**.

**1. Install the companion plugin** (skip if already installed):

```powershell
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.7
codex plugin add reset-reminder@codex-reset-pet
```

**2. Install and automatically launch the desktop pet:**

```powershell
$file = "$env:TEMP\codex-reset-pet-install.ps1"
Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/v0.4.7/install.ps1' -OutFile $file
powershell -NoProfile -ExecutionPolicy Bypass -File $file -SkipPlugin
```

The pet opens automatically and a desktop shortcut is created. First installation needs network access and sets up Python/Pillow. The default directory is `%LOCALAPPDATA%\CodexResetPet`. `-SkipPlugin` only avoids duplicate plugin registration; desktop startup still happens.

**Desktop only? Run step 2 directly.** For the chat plugin only, run step 1. Desktop quota refresh requires a signed-in Codex CLI. [Official plugin command reference](https://learn.chatgpt.com/docs/cli/reference).

## Start again / check installation

After installation, reopen your terminal and run:

```powershell
codex-pet
```

Or double-click the **Codex Reset Pet** desktop shortcut. Launching makes no AI request, uses no model quota, and avoids opening another instance if already running.

| Command | Purpose |
| --- | --- |
| `codex-pet` | Start |
| `codex-pet status` | Check whether it is running |
| `codex-pet version` | Show installed version |
| `codex-pet help` | Show command help |
| `codex-pet sounds` | Show configured audio, its location, and running mute status |

If the command is not found, fully close and reopen your terminal app; embedded terminals may require restarting Codex. To quit the pet, use its right-click menu.

## One-command update (existing installations)

Run in PowerShell; the installer gracefully closes the previous instance and starts the new version:

```powershell
$file = "$env:TEMP\codex-reset-pet-update.ps1"
Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/FantasyWorld-G/codex-reset-pet/main/update.ps1' -OutFile $file
powershell -NoProfile -ExecutionPolicy Bypass -File $file
```

This installs and launches the latest stable release while preserving account snapshots, settings, and personal audio. Reuse these commands for future updates without changing a version number. For desktop-only installations, append `-SkipPlugin` to the final line; for a custom directory, append `-InstallRoot 'original installation directory'`.

## Included voice reactions

**The complete package includes all nine current voice clips. Installation and upgrades use them immediately; no copying or importing is required.** Legacy auto-detected personal files remain on disk but do not hide updated default voices. Mute preferences remain unchanged. `codex-pet sounds` reports `amitaro-bundled` for these included voices.

Only use the optional `codex-pet sounds "voice-folder"` command when deliberately selecting a personal override. See [voice mapping and credits](docs/voice-credits.md).

## First account sync

In a new Codex chat, send:

> Use the reset-reminder plugin to synchronize my account quota reset and reset-credit expiration information to the desktop pet. Synchronize once only; do not create a scheduled task.

Then use **刷新** (Refresh) in the window to update quota. Reset-credit expiration details may still require a full sync. The pet launches before synchronization and displays a waiting message. Installation does not create scheduled tasks or enable Windows startup.

## Everyday controls

| Action | Result |
| --- | --- |
| Single click | Toggle the bubble; every third single click triggers a pout |
| Double click | Head pat and laugh without toggling the bubble |
| Drag and release | Move the pet and play the landing animation; dragging 180 pixels triggers one happy sound |
| No interaction for 10 seconds | Stay asleep with zzz particles; touch to wake |
| Right click | Reactions, sound toggle, optional credit redemption, and Exit |
| Refresh / Update forecast | Update account quota / Tibo website information respectively |

The bubble shows quota, credit expiry, Tibo forecasts, and the previous reset. Times use Beijing time, with urgency colors. Website forecasts do not confirm a reset for your account. Automatic expiring-credit redemption is off by default and requires explicit opt-in; it cannot be guaranteed while asleep or offline.

## Other installation options and help

| Need | Guide |
| --- | --- |
| Manual ZIP download and SHA-256 verification | [Manual installation](docs/installation.en.md#manual-release-download-no-git-required) |
| Git / source installation | [Source installation](docs/installation.en.md#git--source-installation) |
| Custom directory, `-NoLaunch`, `-NoPath`, and more | [Installer and updater options](docs/installation.en.md#installer-and-updater-options) |
| Update only the Codex plugin | [Plugin updates](docs/installation.en.md#update-only-the-codex-plugin) |
| Sync, credit redemption, uninstalling, troubleshooting | [Complete user guide (Chinese)](docs/使用说明.md) |
| Development / changes | [Development commands](docs/installation.en.md#development-and-testing) · [Changelog](CHANGELOG.md) |

## Voice credits


The included voice reactions use recordings by **Amitaro’s Voice Material Studio — あみたろの声素材工房** ([official website](https://amitaro.net/)). Thank you to the creator for providing these recordings. They are governed by the [author’s terms](https://amitaro.net/voice/terms/), not this project’s source license. Recordings are included as resources of the complete application, not distributed as a standalone asset pack. Usage and redistribution remain subject to the author’s terms. Original synthesized audio is kept only as a corruption fallback. See [voice notes and credits](docs/voice-credits.md) for the clip mapping.
