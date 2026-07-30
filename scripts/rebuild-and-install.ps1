#Requires -Version 5.1
<#
.SYNOPSIS
  Rebuild installer with latest code, then launch the setup.exe
#>
$ErrorActionPreference = "Stop"
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
$Root = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Write-Host "[!!] Chua co cargo tren PATH. Cai: winget install Rustlang.Rustup" -ForegroundColor Red
    exit 1
}

# VS DevShell for link.exe
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
    $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($vs) {
        $dll = Join-Path $vs "Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
        if (Test-Path $dll) {
            Import-Module $dll
            Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments "-arch=x64" | Out-Null
        }
    }
}

Write-Host "=== Rebuild desktop installer ===" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "build-desktop.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$setup = Join-Path $Root "release\DubVI_0.1.0_x64-setup.exe"
if (-not (Test-Path $setup)) {
    Write-Host "[!!] Khong thay $setup" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Build xong. Dang mo bo cai..." -ForegroundColor Green
Start-Process $setup
Write-Host "Sau khi cai xong, mo Dub VI tu Start Menu (ban moi)."
