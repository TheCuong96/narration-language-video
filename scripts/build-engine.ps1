#Requires -Version 5.1
<#
.SYNOPSIS
  Build DubVIEngine.exe with PyInstaller (CPU base deps only).
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Engine = Join-Path $Root "engine"
$Dist = Join-Path $Engine "dist"
$OutBin = Join-Path $Root "desktop\src-tauri\binaries"

Set-Location $Engine
python -m pip install --upgrade pip
python -m pip install -r requirements-base.txt pyinstaller
# Required by setuptools pkg_resources inside the frozen exe (pyi_rth_pkgres)
python -m pip install "appdirs>=1.4.4" "packaging>=24" "jaraco.text>=3.11" "more-itertools>=10" "platformdirs>=4"

if (Test-Path $Dist) { Remove-Item -Recurse -Force $Dist }
python -m PyInstaller --noconfirm DubVIEngine.spec
if (-not (Test-Path (Join-Path $Dist "DubVIEngine.exe"))) {
    throw "PyInstaller did not produce DubVIEngine.exe"
}

New-Item -ItemType Directory -Force -Path $OutBin | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "release\staging") | Out-Null
# Tauri externalBin expects target-triple suffix on Windows
$triple = "x86_64-pc-windows-msvc"
Copy-Item -Force (Join-Path $Dist "DubVIEngine.exe") (Join-Path $OutBin "DubVIEngine-$triple.exe")
Copy-Item -Force (Join-Path $Dist "DubVIEngine.exe") (Join-Path $Root "release\staging\DubVIEngine.exe")
Write-Host "[OK] Engine -> desktop\src-tauri\binaries\DubVIEngine-$triple.exe"
