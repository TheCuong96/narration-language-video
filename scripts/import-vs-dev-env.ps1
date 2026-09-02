#Requires -Version 5.1
<#
.SYNOPSIS
  Import MSVC/link.exe into this process without Enter-VsDevShell.

  Enter-VsDevShell can call exit and close the parent CMD window when
  build.bat is double-clicked from Explorer.
#>
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    return
}
$vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) {
    return
}
$vcvars = Join-Path $vs "VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $vcvars)) {
    return
}
cmd.exe /c "`"$vcvars`" >nul 2>&1 && set" | ForEach-Object {
    $i = $_.IndexOf("=")
    if ($i -gt 0) {
        [Environment]::SetEnvironmentVariable($_.Substring(0, $i), $_.Substring($i + 1), "Process")
    }
}
