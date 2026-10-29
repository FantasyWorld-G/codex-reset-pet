@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -SourcePath "%~dp0." -SkipPlugin %*
set "petInstallExit=%ERRORLEVEL%"
if not "%petInstallExit%"=="0" (
  echo Installation failed. See the message above.
  pause
)
exit /b %petInstallExit%
