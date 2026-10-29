# Other installation and update options

[Back to README](../README.en.md) · [简体中文](installation.md)

Choose only the alternatives you need below. Everyday startup only needs `codex-pet`.


### Manual release download (no Git required)

Download `codex-reset-pet-v0.4.7.zip` and `SHA256SUMS.txt` from [Release v0.4.7](https://github.com/FantasyWorld-G/codex-reset-pet/releases/tag/v0.4.7). Put both files in one directory and verify the checksum before extracting the archive:

```powershell
$archive = (Resolve-Path '.\codex-reset-pet-v0.4.7.zip').Path
$expected = ((Get-Content '.\SHA256SUMS.txt' | Where-Object { $_ -match '\s+codex-reset-pet-v0\.4\.7\.zip$' }) -split '\s+')[0]
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
git clone --branch v0.4.7 --depth 1 https://github.com/FantasyWorld-G/codex-reset-pet.git
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

Desktop-only installations still require a signed-in Codex CLI for quota refresh. See the [complete user guide (Chinese)](使用说明.md) for all options.

## Installer and updater options

Append options to `powershell ... -File $file`. Only `-SourcePath` is exclusive to the installer; all other options also work with the updater.

| Option | Purpose |
| --- | --- |
| `-InstallRoot 'D:\Apps\CodexResetPet'` | Custom directory; keep the original directory when updating |
| `-SkipPlugin` | Skip plugin registration; still install and launch the desktop pet |
| `-NoLaunch` | Do not launch afterward |
| `-NoShortcut` | Do not create a desktop shortcut |
| `-NoPath` | Leave user PATH unchanged; still create command files |
| `-SourcePath .` | Install from the current extracted source directory |

## Start without PATH

For the default installation, use the command below. Adjust the directory for custom installations:

```powershell
& "$env:LOCALAPPDATA\CodexResetPet\bin\codex-pet.cmd"
```

If `codex-pet` is not found, fully close and reopen your terminal app. Embedded terminals may require restarting their host app.

## Update only the Codex plugin


For a Git marketplace installed using the README commands, switch its pinned version to v0.4.7 with:

```powershell
codex plugin marketplace remove codex-reset-pet
codex plugin marketplace add FantasyWorld-G/codex-reset-pet --ref v0.4.7
codex plugin add reset-reminder@codex-reset-pet
```

For a future release, replace `v0.4.7` with its published tag. If your Git marketplace intentionally tracks `main`, use the following instead; refreshing a pinned tag does not advance to a newer release:

```powershell
codex plugin marketplace upgrade codex-reset-pet
codex plugin add reset-reminder@codex-reset-pet
```

If the desktop installer registered a local marketplace, use [the desktop updater](../README.en.md#one-command-update-existing-installations) instead. Plugin-only updates do not update desktop files. Start a new Codex chat afterward. [Official marketplace commands](https://learn.chatgpt.com/docs/cli/reference).

## Development and testing

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s plugins/reset-reminder/tests -v
python scripts/build_release.py
```

The regression tests cover animation state transitions, countdowns, reset-credit filtering, notification deduplication, connection failures and recovery, timeouts, cancellation, malformed responses, save failures, Tibo forecast parsing, and native Windows layout and refresh regression. Native-window integration tests are skipped on non-Windows systems. See the [failure-handling test report (Chinese)](异常处理测试.md). The release package and checksum file are written to `dist/`. Packaging uses an explicit file allowlist to exclude runtime data and caches.


## Included audio

The complete v0.4.7 package includes nine current voices for all desktop installation methods, without manual import. Double-click install.cmd from the extracted package to install and launch. Legacy personal files are retained; only explicit import selections override included voices. Inspect with codex-pet sounds. Starting with v0.4.7, the stable release package and updater include these voices.
