#Requires -Version 5.1
<#
.SYNOPSIS
  Faster desktop build: skip FFmpeg download / pip reinstall when possible.

.PARAMETER SkipEngine
  Reuse existing desktop\src-tauri\resources\engine (skip PyInstaller).

.PARAMETER EngineOnly
  Only rebuild the Python sidecar; do not run tauri build.

.PARAMETER UiOnly
  Only run tauri build (requires engine folder already present).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build-desktop-fast.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build-desktop-fast.ps1 -SkipEngine

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build-desktop-fast.ps1 -EngineOnly
#>
param(
    [switch]$SkipEngine,
    [switch]$EngineOnly,
    [switch]$UiOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path

if ($EngineOnly -and $UiOnly) { throw "Use either -EngineOnly or -UiOnly, not both" }
if ($UiOnly) { $SkipEngine = $true }

# VS DevShell for link.exe (tauri/cargo)
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not $EngineOnly -and (Test-Path $vswhere)) {
    $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($vs) {
        $devShell = Join-Path $vs "Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
        if (Test-Path $devShell) {
            Import-Module $devShell
            Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments "-arch=x64" | Out-Null
        }
    }
}

$Ffmpeg = Join-Path $Root "resources\bin\ffmpeg.exe"
$Ffprobe = Join-Path $Root "resources\bin\ffprobe.exe"
$EngineExe = Join-Path $Root "desktop\src-tauri\resources\engine\DubVIEngine.exe"

# --- 1) FFmpeg (skip if present) ---
if (-not $EngineOnly) {
    if ((Test-Path $Ffmpeg) -and (Test-Path $Ffprobe)) {
        Write-Host "=== 1) FFmpeg (skip - already present) ===" -ForegroundColor DarkGray
    } else {
        Write-Host "=== 1) FFmpeg ===" -ForegroundColor Cyan
        & (Join-Path $PSScriptRoot "download-ffmpeg.ps1")
    }
    $ResBin = Join-Path $Root "desktop\src-tauri\resources\bin"
    New-Item -ItemType Directory -Force -Path $ResBin | Out-Null
    Copy-Item -Force $Ffmpeg $ResBin
    Copy-Item -Force $Ffprobe $ResBin
}

# --- 2) Engine ---
if ($SkipEngine) {
    if (-not (Test-Path $EngineExe)) {
        throw "SkipEngine but engine missing: $EngineExe (run without -SkipEngine first)"
    }
    Write-Host "=== 2) Engine (skip - reuse onedir) ===" -ForegroundColor DarkGray
} else {
    Write-Host "=== 2) Engine (PyInstaller onedir) ===" -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "build-engine-fast.ps1")
}

if ($EngineOnly) {
    Write-Host "[OK] Engine only. Entry: $EngineExe"
    exit 0
}

# --- 3) Tauri ---
Write-Host "=== 3) Desktop (Tauri) ===" -ForegroundColor Cyan
Set-Location (Join-Path $Root "desktop")
if (-not (Test-Path "node_modules")) { npm install }
npm run tauri build
if ($LASTEXITCODE -ne 0) { throw "tauri build failed" }

$Version = "0.1.0"
$Release = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $Release | Out-Null
$bundleDir = Join-Path $Root "desktop\src-tauri\target\release\bundle\nsis"
$setup = Get-ChildItem -Path $bundleDir -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $setup) {
    throw "NSIS bundle not found under $bundleDir"
}
$finalName = "DubVI_${Version}_x64-setup.exe"
$finalPath = Join-Path $Release $finalName
Copy-Item -Force $setup.FullName $finalPath
$hash = (Get-FileHash -Algorithm SHA256 -Path $finalPath).Hash.ToLower()
Set-Content -Path "$finalPath.sha256" -Value "$hash  $finalName" -Encoding ascii
Write-Host "[OK] $finalPath"
Write-Host "SHA256: $hash"
