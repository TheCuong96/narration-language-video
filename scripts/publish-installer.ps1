#Requires -Version 5.1
<#
.SYNOPSIS
  Copy the newest Tauri NSIS exe into release\ and refuse stale leftovers.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Version = "0.1.0"
$Release = Join-Path $Root "release"
$bundleDir = Join-Path $Root "desktop\src-tauri\target\release\bundle\nsis"
$EngineExe = Join-Path $Root "desktop\src-tauri\resources\engine\DubVIEngine.exe"
$finalName = "DubVI_${Version}_x64-setup.exe"
$finalPath = Join-Path $Release $finalName

if (-not (Test-Path $bundleDir)) {
    throw "Chua co bo cai NSIS: $bundleDir (tauri build chua chay xong)."
}

$setup = Get-ChildItem -Path $bundleDir -Filter "*.exe" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $setup) {
    throw "Khong thay file .exe trong $bundleDir"
}

$now = Get-Date
$ageMin = [math]::Round(($now - $setup.LastWriteTime).TotalMinutes, 1)
Write-Host ("NSIS bundle: {0}" -f $setup.FullName)
Write-Host ("  time: {0:yyyy-MM-dd HH:mm:ss}  size: {1:N1} MB  age: {2} phut" -f $setup.LastWriteTime, ($setup.Length / 1MB), $ageMin)

if ($setup.LastWriteTime -lt $now.AddHours(-2)) {
    throw @"
Installer trong bundle van la ban CU ($($setup.LastWriteTime)).
Tauri chua goi lai NSIS. Hay TAT Dub VI / yarn tauri dev roi chay lai build.bat.
Khong cai file release\$finalName neu ngay thang khong phai hom nay.
"@
}

if (Test-Path $EngineExe) {
    $engineTime = (Get-Item $EngineExe).LastWriteTime
    if ($setup.LastWriteTime -lt $engineTime.AddMinutes(-2)) {
        throw @"
Installer ($($setup.LastWriteTime)) cu hon engine ($engineTime).
Engine da build lai nhung Tauri chua dong goi vao setup.exe.
"@
    }
}

New-Item -ItemType Directory -Force -Path $Release | Out-Null
Copy-Item -Force $setup.FullName $finalPath
$copied = Get-Item $finalPath
$hash = (Get-FileHash -Algorithm SHA256 -Path $finalPath).Hash.ToLower()
Set-Content -Path "$finalPath.sha256" -Value "$hash  $finalName" -Encoding ascii

Write-Host "[OK] $finalPath"
Write-Host ("     {0:yyyy-MM-dd HH:mm:ss}  {1:N1} MB" -f $copied.LastWriteTime, ($copied.Length / 1MB))
Write-Host "SHA256: $hash"
Write-Host "Hay cai DUNG file nay (xem ngay thang phai la hom nay)." -ForegroundColor Green
