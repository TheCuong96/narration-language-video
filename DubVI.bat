@echo off
REM Launch Dub VI GUI without a console window when possible
setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHONUNBUFFERED=1"

where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
  start "" pythonw "%SCRIPT_DIR%dub_vi_gui.py"
  exit /b 0
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%SCRIPT_DIR%dub_vi_gui.py"
  exit /b %ERRORLEVEL%
)

echo [!!] Python not found. Install Python 3.10+ from https://python.org
pause
exit /b 1
