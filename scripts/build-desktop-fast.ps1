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
$Release = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $Release | Out-Null
$BuildLog = Join-Path $Release "last-build.log"
try { Stop-Transcript | Out-Null } catch { }
Start-Transcript -Path $BuildLog -Force | Out-Null

function Invoke-Npm([string]$ArgsLine) {
    # call npm.cmd so its EXIT cannot terminate the parent console.
    cmd.exe /c "call npm.cmd $ArgsLine"
    if ($LASTEXITCODE -ne 0) {
        throw "npm $ArgsLine failed (exit $LASTEXITCODE)"
    }
}

function Stop-IfDubViRunning {
    # Do not inspect .Path on every process: with ErrorAction Stop that
    # throws on protected PIDs and kills the whole build.bat window.
    $hits = @(Get-Process -Name dubvi, DubVIEngine -ErrorAction SilentlyContinue)
    if ($hits.Count -eq 0) {
        return
    }
    Write-Host "[!!] Dang mo Dub VI (yarn tauri dev hoac app da cai)." -ForegroundColor Yellow
    foreach ($p in $hits) {
        Write-Host ("     PID {0} {1}" -f $p.Id, $p.ProcessName)
    }
    Write-Host "Tat cac cua so do, roi nhan Enter de tiep tuc (hoac dong cua so nay de huy)."
    [void](Read-Host)
    $still = @(Get-Process -Name dubvi, DubVIEngine -ErrorAction SilentlyContinue)
    if ($still.Count -gt 0) {
        Write-Host "[!!] Van con process dubvi. Build installer co the giu ban cu." -ForegroundColor Yellow
        Write-Host "Nhan Enter de van build, hoac dong cua so de huy."
        [void](Read-Host)
    }
}

$exitCode = 0
try {
    if ($EngineOnly -and $UiOnly) { throw "Use either -EngineOnly or -UiOnly, not both" }
    if ($UiOnly) { $SkipEngine = $true }

    if (-not $EngineOnly) {
        Stop-IfDubViRunning
        . (Join-Path $PSScriptRoot "import-vs-dev-env.ps1")
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
    } else {
        # --- 3) Tauri ---
        Write-Host "=== 3) Desktop (Tauri) ===" -ForegroundColor Cyan
        Write-Host "Sau khi compile Rust, makensis se dong goi setup.exe va CO THE IM LANG 5-15 phut." -ForegroundColor Yellow
        Write-Host "Khong tat cua so khi thay dong 'Running makensis'." -ForegroundColor Yellow
        Set-Location (Join-Path $Root "desktop")
        if (-not (Test-Path "node_modules")) { Invoke-Npm "install" }
        Invoke-Npm "run tauri build"
        & (Join-Path $PSScriptRoot "publish-installer.ps1")
    }
} catch {
    $exitCode = 1
    Write-Host "[!!] $($_.Exception.Message)" -ForegroundColor Red
} finally {
    try { Stop-Transcript | Out-Null } catch { }
}
exit $exitCode

