#Requires -Version 5.1
<#
.SYNOPSIS
  Faster PyInstaller onedir build - skip pip upgrade / reinstall when deps exist.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Engine = Join-Path $Root "engine"
$Dist = Join-Path $Engine "dist"
$DistApp = Join-Path $Dist "DubVIEngine"
$OutEngine = Join-Path $Root "desktop\src-tauri\resources\engine"

Set-Location $Engine

# Only ensure packages; do not upgrade pip / reinstall every run.
$marker = python -c "import PyInstaller, faster_whisper, ctranslate2; print('ok')" 2>$null
if ($marker -ne "ok") {
    Write-Host "Installing engine deps (first time)..."
    python -m pip install -r requirements-base.txt pyinstaller
    python -m pip install "appdirs>=1.4.4" "packaging>=24" "jaraco.text>=3.11" "more-itertools>=10" "platformdirs>=4"
} else {
    Write-Host "Python deps OK - skip pip install" -ForegroundColor DarkGray
}

if (Test-Path $Dist) { Remove-Item -Recurse -Force $Dist }
python -m PyInstaller --noconfirm DubVIEngine.spec
$EngineExe = Join-Path $DistApp "DubVIEngine.exe"
if (-not (Test-Path $EngineExe)) {
    throw "PyInstaller did not produce dist\DubVIEngine\DubVIEngine.exe"
}

if (Test-Path $OutEngine) { Remove-Item -Recurse -Force $OutEngine }
New-Item -ItemType Directory -Force -Path $OutEngine | Out-Null
Copy-Item -Recurse -Force (Join-Path $DistApp "*") $OutEngine

New-Item -ItemType Directory -Force -Path (Join-Path $Root "release\staging") | Out-Null
Copy-Item -Force $EngineExe (Join-Path $Root "release\staging\DubVIEngine.exe")
Write-Host "[OK] Engine onedir -> desktop\src-tauri\resources\engine\"
