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

$sidecarRoot = Join-Path $Root "desktop\src-tauri\resources\engine"
$sidecarExe = Join-Path $sidecarRoot "DubVIEngine.exe"
Check (Test-Path $sidecarExe) "Onedir sidecar exists"
Check (Test-Path (Join-Path $sidecarRoot "_internal\certifi\cacert.pem")) "certifi CA data bundled"
if (Test-Path $sidecarExe) {
    try {
        # This imports requests/urllib3 in the frozen process and calls /api/tags
        # without requiring an external Python installation or a downloaded model.
        $modelJson = & $sidecarExe models --kind translate
        Check ($LASTEXITCODE -eq 0) "Frozen sidecar models command succeeds"
        $modelCatalog = ($modelJson -join "`n") | ConvertFrom-Json
        $gemma = @($modelCatalog | Where-Object { $_.runtime -eq 'ollama' })
        Check ($gemma.Count -eq 3) "Frozen catalog has three Ollama models"
        Check (@($gemma | Where-Object { $_.download_root }).Count -eq 0) "Ollama models have no Dub VI model path"
    } catch {
        Check $false "Frozen model catalog smoke failed: $_"
    }
    $bundledWeights = @(Get-ChildItem -LiteralPath $sidecarRoot -Recurse -File -Filter '*.gguf')
    Check ($bundledWeights.Count -eq 0) "No Ollama GGUF weights bundled"
    Check (-not (Test-Path (Join-Path $sidecarRoot 'ollama.exe'))) "Ollama runtime not bundled"
}

if ($ok) { Write-Host "`nVERIFY PASSED" -ForegroundColor Green; exit 0 }
Write-Host "`nVERIFY FAILED" -ForegroundColor Red; exit 1
