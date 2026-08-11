@echo off
setlocal
cd /d "%~dp0"
title Dub VI - build installer
echo.
echo === Dub VI: npm run build ===
echo Artifact: release\DubVI_0.1.0_x64-setup.exe
echo.

where npm >nul 2>nul
if errorlevel 1 (
  echo [!!] Chua co npm. Cai Node.js 20+ roi chay lai.
  pause
  exit /b 1
)

call npm run build
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
  echo [!!] Build that bai (code %ERR%).
  pause
  exit /b %ERR%
)

echo [OK] Xong. Mo thu muc release...
if exist "release\DubVI_0.1.0_x64-setup.exe" (
  explorer /select,"%~dp0release\DubVI_0.1.0_x64-setup.exe"
) else (
  explorer "%~dp0release"
)
pause
exit /b 0
