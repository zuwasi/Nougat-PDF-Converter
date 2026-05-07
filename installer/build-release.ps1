<#
.SYNOPSIS
    Build a release ZIP and (optionally) publish a GitHub Release.

.DESCRIPTION
    Bundles the app/, installer/, README, INSTALL, LICENSE into
    NougatPDFConverter-vX.Y.Z.zip in the repo root, then (with -Publish)
    creates a GitHub Release with that ZIP attached using `gh`.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Version,
    [switch]$Publish,
    [string]$Notes = "Self-contained Windows installer for Nougat PDF Converter."
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stage = Join-Path $env:TEMP "nougat-release-$Version"
$zipName = "NougatPDFConverter-v$Version.zip"
$zipPath = Join-Path $root $zipName

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Write-Host "Staging files..."
Copy-Item (Join-Path $root 'app')        -Destination $stage -Recurse
Copy-Item (Join-Path $root 'installer')  -Destination $stage -Recurse
Copy-Item (Join-Path $root 'README.md')  -Destination $stage
Copy-Item (Join-Path $root 'INSTALL.md') -Destination $stage
Copy-Item (Join-Path $root 'LICENSE')    -Destination $stage

Write-Host "Creating $zipName..."
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -CompressionLevel Optimal
Remove-Item $stage -Recurse -Force

Write-Host ("ZIP: {0}  ({1:N2} MB)" -f $zipPath, ((Get-Item $zipPath).Length/1MB))

if ($Publish) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "gh CLI not found" }
    Write-Host "Publishing GitHub Release v$Version..."
    gh release create "v$Version" $zipPath --title "v$Version" --notes $Notes
}
