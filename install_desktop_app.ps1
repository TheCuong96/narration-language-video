#Requires -Version 5.1
<#
.SYNOPSIS
  Install Dub VI as a desktop app (Start Menu + Desktop shortcuts).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\install_desktop_app.ps1
#>

$ErrorActionPreference = "Stop"

$AppName = "Dub VI"
$SourceDir = $PSScriptRoot
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\DubVI"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$Desktop = [Environment]::GetFolderPath("Desktop")

Write-Host ""
Write-Host "=== Cai dat $AppName ===" -ForegroundColor Cyan
Write-Host "Nguon : $SourceDir"
Write-Host "Cai vao: $InstallDir"
Write-Host ""

# 1) Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[!!] Chua co Python tren PATH. Cai Python 3.10+ tai https://python.org" -ForegroundColor Red
    Write-Host "     (nho tick 'Add python.exe to PATH')" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Python: $($python.Source)"

# 2) Copy app files
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$files = @(
    "dub_vi.py",
    "dub_deps.py",
    "dub_vi_gui.py",
    "dub-vi.cmd",
    "DubVI.bat",
    "requirements-dub.txt",
    "README-dub-vi.md",
    "Uninstall-DubVI.ps1"
)
foreach ($f in $files) {
    $src = Join-Path $SourceDir $f
    if (Test-Path $src) {
        Copy-Item -Force $src (Join-Path $InstallDir $f)
        Write-Host "  + $f"
    }
}

# Write uninstall script into install dir (always refresh)
$uninstallPath = Join-Path $InstallDir "Uninstall-DubVI.ps1"
@"
#Requires -Version 5.1
`$InstallDir = '$InstallDir'
`$AppName = '$AppName'
`$Desktop = [Environment]::GetFolderPath('Desktop')
`$StartMenu = Join-Path `$env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
Remove-Item -Force (Join-Path `$Desktop "`$AppName.lnk") -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path `$StartMenu "`$AppName.lnk") -ErrorAction SilentlyContinue
if (Test-Path `$InstallDir) { Remove-Item -Recurse -Force `$InstallDir }
Write-Host 'Da go cai dat Dub VI.'
"@ | Set-Content -Encoding UTF8 $uninstallPath

# 3) Dependency setup
Write-Host ""
Write-Host "Dang kiem tra / cai dependency (co the mat vai phut)..." -ForegroundColor Yellow
& python (Join-Path $InstallDir "dub_vi.py") --setup
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!!] Setup dependency that bai. Ban van co the mo app va bam 'Kiem tra / Cai dat'." -ForegroundColor Yellow
}

# 4) Shortcuts
function New-Shortcut {
    param(
        [string]$LinkPath,
        [string]$TargetPath,
        [string]$Arguments,
        [string]$WorkDir,
        [string]$IconLocation
    )
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($LinkPath)
    $s.TargetPath = $TargetPath
    $s.Arguments = $Arguments
    $s.WorkingDirectory = $WorkDir
    if ($IconLocation) { $s.IconLocation = $IconLocation }
    $s.WindowStyle = 1
    $s.Description = "Long tieng Viet cho video (Dub VI)"
    $s.Save()
}

$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue)
if ($pythonw) {
    $target = $pythonw.Source
    $args = "`"$(Join-Path $InstallDir 'dub_vi_gui.py')`""
} else {
    $target = "cmd.exe"
    $args = "/c `"$(Join-Path $InstallDir 'DubVI.bat')`""
}

$desktopLnk = Join-Path $Desktop "$AppName.lnk"
$startLnk = Join-Path $StartMenuDir "$AppName.lnk"
New-Shortcut -LinkPath $desktopLnk -TargetPath $target -Arguments $args -WorkDir $InstallDir -IconLocation "imageres.dll,19"
New-Shortcut -LinkPath $startLnk -TargetPath $target -Arguments $args -WorkDir $InstallDir -IconLocation "imageres.dll,19"

Write-Host ""
Write-Host "=== Xong! ===" -ForegroundColor Green
Write-Host "Da tao shortcut:"
Write-Host "  - Desktop : $desktopLnk"
Write-Host "  - Start   : $startLnk"
Write-Host ""
Write-Host "Mo app bang icon '$AppName' tren Desktop."
Write-Host "Go cai: powershell -ExecutionPolicy Bypass -File `"$uninstallPath`""
Write-Host ""
