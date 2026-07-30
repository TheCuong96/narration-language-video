#Requires -Version 5.1
<#
.SYNOPSIS
  Download portable FFmpeg/ffprobe into resources/bin (no system install).
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$OutDir = Join-Path $Root "resources\bin"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$ffmpeg = Join-Path $OutDir "ffmpeg.exe"
$ffprobe = Join-Path $OutDir "ffprobe.exe"
if ((Test-Path $ffmpeg) -and (Test-Path $ffprobe)) {
    Write-Host "[OK] FFmpeg already present in $OutDir"
    exit 0
}

$zipUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$tmp = Join-Path $env:TEMP ("dubvi-ffmpeg-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$zip = Join-Path $tmp "ffmpeg.zip"

Write-Host "Downloading FFmpeg essentials..."
Invoke-WebRequest -Uri $zipUrl -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $tmp -Force

$bin = Get-ChildItem -Path $tmp -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if (-not $bin) { throw "ffmpeg.exe not found in archive" }
$probe = Join-Path $bin.DirectoryName "ffprobe.exe"
Copy-Item -Force $bin.FullName $ffmpeg
Copy-Item -Force $probe $ffprobe
Remove-Item -Recurse -Force $tmp
Write-Host "[OK] Installed to $OutDir"
