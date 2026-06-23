@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_webui.ps1" %*

if errorlevel 1 (
  echo.
  echo Failed to start Emby115Toolkit V2 WebUI.
  pause
)
