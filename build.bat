@echo off
setlocal EnableExtensions
title Dub VI - build installer

rem Explorer starts .bat with "cmd /c" — window closes as soon as a child calls
rem exit, or when PowerShell/npm finish, so "pause" never shows.
rem Relaunch in cmd /k so this window stays until you close it.
if /I not "%~1"=="--keep-open" (
  start "Dub VI - build installer" cmd /k call "%~f0" --keep-open
  exit /b 0
)

cd /d "%~dp0"
if not exist "release" mkdir "release"
set "LOG=%~dp0release\last-build.log"
set "SETUP=%~dp0release\DubVI_0.1.0_x64-setup.exe"

echo.
echo === Dub VI: build.bat ===
echo Artifact: release\DubVI_0.1.0_x64-setup.exe
echo Log:      release\last-build.log
echo.
echo Neu dang chay yarn tauri dev hoac app Dub VI, hay tat truoc.
echo Doan "Running makensis" se IM LANG 5-15 phut — dung tat cua so.
echo.

set "ERR=1"
where powershell >nul 2>nul
if errorlevel 1 (
  echo [!!] Khong tim thay powershell.
  echo.
  goto :hold
)

rem Call the script directly. Do NOT use "npm run build": npm.cmd/node can
rem terminate this console before pause runs.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-desktop-fast.ps1"
set "ERR=%ERRORLEVEL%"
echo.
echo ---
echo Build xong luc %DATE% %TIME%  (code %ERR%)
echo ---
echo.

if not "%ERR%"=="0" (
  echo [!!] Build that bai (code %ERR%).
  echo     Xem %LOG%
  echo     KHONG cai release\DubVI_0.1.0_x64-setup.exe neu ngay thang khong phai hom nay.
  goto :hold
)

if exist "%SETUP%" (
  echo [OK] File cai dat:
  for %%F in ("%SETUP%") do (
    echo     %%~fF
    echo     Ngay: %%~tF
    echo     Size: %%~zF bytes
  )
  echo.
  echo Chi cai file nay khi ngay thang la luc vua build.
  explorer /select,"%SETUP%"
) else (
  echo [!!] Khong thay release\DubVI_0.1.0_x64-setup.exe
  explorer "%~dp0release"
)

:hold
echo.
echo Cua so nay se KHONG tu tat. Nhan phim bat ky, roi go exit neu muon dong.
pause
exit /b %ERR%
