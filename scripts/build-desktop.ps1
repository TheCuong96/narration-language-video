#Requires -Version 5.1
<#
.SYNOPSIS
  Full production build: FFmpeg + engine + Tauri NSIS installer + SHA256.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Version = "0.1.0"
$Release = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $Release | Out-Null

# Ensure VS / cargo on PATH when possible (do not use Enter-VsDevShell — it can close CMD)
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
. (Join-Path $PSScriptRoot "import-vs-dev-env.ps1")

Write-Host "=== 1) FFmpeg ===" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "download-ffmpeg.ps1")

Write-Host "=== 2) Engine ===" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "build-engine.ps1")

# Copy ffmpeg into tauri resources
$ResBin = Join-Path $Root "desktop\src-tauri\resources\bin"
New-Item -ItemType Directory -Force -Path $ResBin | Out-Null
Copy-Item -Force (Join-Path $Root "resources\bin\ffmpeg.exe") $ResBin
Copy-Item -Force (Join-Path $Root "resources\bin\ffprobe.exe") $ResBin

Write-Host "=== 3) Desktop (Tauri) ===" -ForegroundColor Cyan
Set-Location (Join-Path $Root "desktop")
if (-not (Test-Path "node_modules")) {
    cmd /c "npm install"
    if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
}
cmd /c "npm run tauri build"
if ($LASTEXITCODE -ne 0) { throw "tauri build failed (exit $LASTEXITCODE)" }
& (Join-Path $PSScriptRoot "publish-installer.ps1")
