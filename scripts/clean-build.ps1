#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

$paths = @(
    (Join-Path $Root "engine\build"),
    (Join-Path $Root "engine\dist"),
    (Join-Path $Root "engine\__pycache__"),
    (Join-Path $Root "desktop\dist"),
    (Join-Path $Root "desktop\src-tauri\target"),
    (Join-Path $Root "release\staging")
)
foreach ($p in $paths) {
    if (Test-Path $p) {
        Write-Host "Removing $p"
        Remove-Item -Recurse -Force $p
    }
}
Write-Host "[OK] Clean complete (kept release/*.exe if any)"
