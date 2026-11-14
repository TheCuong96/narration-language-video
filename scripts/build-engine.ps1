#Requires -Version 5.1
<#
.SYNOPSIS
  Build DubVIEngine onedir with PyInstaller (CPU base deps only).

  Output is copied to desktop\src-tauri\resources\engine\ for Tauri bundling.
  Onedir avoids %TEMP%\_MEI* extracts left by the former onefile sidecar.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Engine = Join-Path $Root "engine"
$Dist = Join-Path $Engine "dist"
$DistApp = Join-Path $Dist "DubVIEngine"
$OutEngine = Join-Path $Root "desktop\src-tauri\resources\engine"

# Resolve recursive cleanup targets and require them inside this checkout.
foreach ($buildTarget in @($Dist, $OutEngine)) {
    $resolvedTarget = [IO.Path]::GetFullPath($buildTarget)
    $resolvedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $resolvedTarget.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe build cleanup target: $resolvedTarget"
    }
}
Set-Location $Engine
python -m pip install --upgrade pip
python -m pip install -r requirements-base.txt pyinstaller
# Required by setuptools pkg_resources inside the frozen exe (pyi_rth_pkgres)
python -m pip install "appdirs>=1.4.4" "packaging>=24" "jaraco.text>=3.11" "more-itertools>=10" "platformdirs>=4"

if (Test-Path $Dist) { Remove-Item -LiteralPath $Dist -Recurse -Force }
python -m PyInstaller --noconfirm DubVIEngine.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }
$EngineExe = Join-Path $DistApp "DubVIEngine.exe"
if (-not (Test-Path $EngineExe)) {
    throw "PyInstaller did not produce dist\DubVIEngine\DubVIEngine.exe"
}

# Ship full onedir tree as Tauri resources (exe + _internal)
if (Test-Path $OutEngine) { Remove-Item -LiteralPath $OutEngine -Recurse -Force }
New-Item -ItemType Directory -Force -Path $OutEngine | Out-Null
Copy-Item -Recurse -Force (Join-Path $DistApp "*") $OutEngine

New-Item -ItemType Directory -Force -Path (Join-Path $Root "release\staging") | Out-Null
# Staging copy for smoke checks only (not a onefile bundle).
Copy-Item -Force $EngineExe (Join-Path $Root "release\staging\DubVIEngine.exe")

Write-Host "[OK] Engine onedir -> desktop\src-tauri\resources\engine\"
Write-Host "[OK] Entry: resources\engine\DubVIEngine.exe"
