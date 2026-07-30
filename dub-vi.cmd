@echo off
setlocal
REM dub-vi launcher for Windows
REM Usage: dub-vi.cmd -i D:\videos\en -o D:\videos\vi
REM        dub-vi.cmd --setup

set "SCRIPT_DIR=%~dp0"
set "PYTHONUNBUFFERED=1"

where python >nul 2>nul
if errorlevel 1 (
  echo [!!] Python not found on PATH. Install Python 3.10+ from https://python.org
  exit /b 1
)

python "%SCRIPT_DIR%dub_vi.py" %*
exit /b %ERRORLEVEL%
