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

# Ensure VS / cargo on PATH when possible
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
    $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($vs) {
        $devShell = Join-Path $vs "Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
        if (Test-Path $devShell) {
            Import-Module $devShell
            Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments "-arch=x64" | Out-Null
        }
    }
}

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
if (-not (Test-Path "node_modules")) { npm install }
npm run tauri build
if ($LASTEXITCODE -ne 0) { throw "tauri build failed" }

$bundleDir = Join-Path $Root "desktop\src-tauri\target\release\bundle\nsis"
$setup = Get-ChildItem -Path $bundleDir -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $setup) {
    Write-Warning "NSIS bundle not found under $bundleDir - check tauri build output."
    Write-Host "Expected artifact name: DubVI_${Version}_x64-setup.exe"
    exit 1
}

$finalName = "DubVI_${Version}_x64-setup.exe"
$finalPath = Join-Path $Release $finalName
Copy-Item -Force $setup.FullName $finalPath

$hash = (Get-FileHash -Algorithm SHA256 -Path $finalPath).Hash.ToLower()
$checksumPath = "$finalPath.sha256"
Set-Content -Path $checksumPath -Value "$hash  $finalName" -Encoding ascii

Write-Host "[OK] $finalPath"
Write-Host "[OK] $checksumPath"
Write-Host "SHA256: $hash"
