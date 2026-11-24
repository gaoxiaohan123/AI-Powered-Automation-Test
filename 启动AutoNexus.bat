@echo off
setlocal EnableExtensions

cd /d "%~dp0"
set "URL=http://127.0.0.1:9090/"
set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" set "PYTHON=python"

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 9090 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if not errorlevel 1 (
    start "" "%URL%"
    exit /b 0
)

start "AutoNexus Server" /d "%~dp0" "%PYTHON%" "%~dp0app.py"

for /l %%I in (1,1,30) do (
    powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 9090 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
    if not errorlevel 1 (
        start "" "%URL%"
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)

echo AutoNexus failed to start. Check the "AutoNexus Server" window for details.
pause
exit /b 1