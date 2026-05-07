<#
.SYNOPSIS
    Removes Nougat PDF Converter from this machine.

.DESCRIPTION
    Deletes the install dir, the Start Menu shortcut, and the user PATH entry.
    Does NOT uninstall Python, Pandoc, or PyTorch (those may be used by other tools).
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'NougatPDFConverter')
)

$ErrorActionPreference = 'Stop'
$appDir = Join-Path $InstallDir 'app'

Write-Host "Removing Start Menu shortcut..."
$lnk = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Nougat PDF Converter.lnk'
if (Test-Path $lnk) { Remove-Item $lnk -Force }

Write-Host "Removing PATH entry..."
$userPath = [System.Environment]::GetEnvironmentVariable('Path','User')
if ($userPath -like "*$appDir*") {
    $new = ($userPath -split ';' | Where-Object { $_ -and ($_ -ne $appDir) }) -join ';'
    [System.Environment]::SetEnvironmentVariable('Path', $new, 'User')
}

Write-Host "Removing install dir: $InstallDir"
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}

Write-Host "Done. (Python, Pandoc, MiKTeX were NOT removed.)"
