@echo off
setlocal
REM Fix: cargo/rust not on PATH in new CMD windows
set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

where cargo >nul 2>&1
if errorlevel 1 (
  echo [!!] Khong tim thay cargo.
  echo Cai Rust: winget install Rustlang.Rustup
  echo Roi DONG CMD nay, mo lai, chay lai script.
  pause
  exit /b 1
)

cd /d "%~dp0..\desktop"
if not exist "node_modules\" call npm install
echo.
echo Dang mo Dub VI (dev)...
call npm run tauri dev
pause
