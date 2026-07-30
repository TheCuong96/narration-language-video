#Requires -Version 5.1
<#
.SYNOPSIS
  Verify release artifacts and that installer payload looks sane.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Version = "0.1.0"
$Release = Join-Path $Root "release"
$Setup = Join-Path $Release "DubVI_${Version}_x64-setup.exe"
$Sum = "$Setup.sha256"

$ok = $true
function Check($cond, $msg) {
    if ($cond) { Write-Host "[OK] $msg" }
    else { Write-Host "[!!] $msg" -ForegroundColor Red; $script:ok = $false }
}

Check (Test-Path $Setup) "Installer exists: $Setup"
Check (Test-Path $Sum) "Checksum exists: $Sum"

if (Test-Path $Setup) {
    $size = (Get-Item $Setup).Length
    Check ($size -gt 5MB) "Installer size > 5MB ($([math]::Round($size/1MB,1)) MB)"
    if (Test-Path $Sum) {
        $expected = (Get-Content $Sum -Raw).Split()[0].Trim().ToLower()
        $actual = (Get-FileHash -Algorithm SHA256 -Path $Setup).Hash.ToLower()
        Check ($expected -eq $actual) "SHA256 matches"
    }
}

Check (Test-Path (Join-Path $Root "resources\bin\ffmpeg.exe")) "Bundled ffmpeg in resources/bin"
Check (Test-Path (Join-Path $Root "resources\bin\ffprobe.exe")) "Bundled ffprobe in resources/bin"
Check (-not (Test-Path (Join-Path $Root "release\*.mp4"))) "No user videos in release/"
Check (-not (Test-Path (Join-Path $Root "release\.env"))) "No secrets in release/"

# Ensure GPU wheels not required in base requirements
$base = Get-Content (Join-Path $Root "engine\requirements-base.txt") -Raw
Check ($base -notmatch "nvidia-") "requirements-base.txt has no nvidia packages"

if ($ok) { Write-Host "`nVERIFY PASSED" -ForegroundColor Green; exit 0 }
Write-Host "`nVERIFY FAILED" -ForegroundColor Red; exit 1
