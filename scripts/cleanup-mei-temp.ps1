#Requires -Version 5.1
<#
.SYNOPSIS
  Delete orphan PyInstaller %TEMP%\_MEI* folders left by DubVIEngine onefile runs.
#>
$ErrorActionPreference = "Continue"
$Temp = [System.IO.Path]::GetTempPath().TrimEnd('\')
$dirs = Get-ChildItem -Path $Temp -Directory -Filter "_MEI*" -ErrorAction SilentlyContinue
if (-not $dirs) {
    Write-Host "[OK] No _MEI* folders under $Temp"
    exit 0
}

$freed = 0L
$count = 0
foreach ($d in $dirs) {
    try {
        $size = 0L
        $files = Get-ChildItem -LiteralPath $d.FullName -Recurse -Force -File -ErrorAction SilentlyContinue
        if ($files) {
            $size = [int64]($files | Measure-Object -Property Length -Sum).Sum
        }
        Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction Stop
        $freed += [int64]$size
        $count++
        Write-Host "Removed $($d.Name) ($([math]::Round($size/1GB, 2)) GB)"
    } catch {
        Write-Warning "Could not remove $($d.FullName): $($_.Exception.Message)"
    }
}

Write-Host "[OK] Removed $count folder(s), ~$([math]::Round($freed/1GB, 2)) GB freed from $Temp"
