<#
.SYNOPSIS
    One-click installer for Nougat PDF Converter on Windows.

.DESCRIPTION
    Creates a self-contained install at %LOCALAPPDATA%\NougatPDFConverter:
      * Python 3.12 (via winget if missing)
      * venv with PyTorch (CUDA when an NVIDIA GPU is present), nougat-ocr,
        and the exact dependency pins Nougat 0.1.17 needs to run
      * Pandoc (via winget) for HTML/PDF export
      * Application files (nougat_app.py + Nougat.bat)
      * Start Menu shortcut and PATH entry ("nougat-pdf" command)

    Run from PowerShell:
      powershell -ExecutionPolicy Bypass -File install.ps1

    Optional flags:
      -InstallDir "<path>"    Install root (default: %LOCALAPPDATA%\NougatPDFConverter)
      -Cpu                    Force CPU-only PyTorch wheels
      -SkipPandoc             Don't install Pandoc
      -PreloadModel           Pre-download the Nougat model weights now (~1.4 GB)
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'NougatPDFConverter'),
    [switch]$Cpu,
    [switch]$SkipPandoc,
    [switch]$PreloadModel
)

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }

# ---------------------------------------------------------------------------
# 1. Locate or install Python 3.12
# ---------------------------------------------------------------------------
function Get-Python312 {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $list = & py -0p 2>$null
        foreach ($line in $list) {
            if ($line -match '3\.12.*\s+(.+python\.exe)') {
                return $matches[1].Trim()
            }
        }
    }
    $direct = Get-Command python3.12 -ErrorAction SilentlyContinue
    if ($direct) { return $direct.Source }
    return $null
}

Write-Step "Checking for Python 3.12"
$python312 = Get-Python312
if (-not $python312) {
    Write-Warn2 "Python 3.12 not found - installing via winget"
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements --silent
    if ($LASTEXITCODE -ne 0) { throw "winget failed to install Python 3.12" }
    # Refresh PATH for current process
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path','User')
    $python312 = Get-Python312
    if (-not $python312) { throw "Python 3.12 still not found after install" }
}
Write-Ok "Using Python: $python312"

# ---------------------------------------------------------------------------
# 2. Create install dir + venv
# ---------------------------------------------------------------------------
Write-Step "Preparing install directory: $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$venvDir = Join-Path $InstallDir 'venv'
$appDir  = Join-Path $InstallDir 'app'
New-Item -ItemType Directory -Force -Path $appDir | Out-Null

if (-not (Test-Path (Join-Path $venvDir 'Scripts\python.exe'))) {
    Write-Step "Creating virtual environment"
    & $python312 -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
$venvPy = Join-Path $venvDir 'Scripts\python.exe'
& $venvPy -m pip install --upgrade pip --quiet
Write-Ok "venv ready at $venvDir"

# ---------------------------------------------------------------------------
# 3. Detect GPU and install PyTorch
# ---------------------------------------------------------------------------
Write-Step "Detecting GPU"
$cudaIndex = $null
if (-not $Cpu) {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($smi) {
        $gpuLine = & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1
        if ($gpuLine) {
            Write-Ok "NVIDIA GPU detected: $gpuLine"
            if ($gpuLine -match 'RTX 50|Blackwell') {
                $cudaIndex = 'https://download.pytorch.org/whl/cu128'
                Write-Ok "Using CUDA 12.8 wheels (Blackwell)"
            } else {
                $cudaIndex = 'https://download.pytorch.org/whl/cu124'
                Write-Ok "Using CUDA 12.4 wheels"
            }
        }
    } else {
        Write-Warn2 "nvidia-smi not found - falling back to CPU wheels"
    }
}

Write-Step "Installing PyTorch"
$torchArgs = @('-m','pip','install','--quiet','torch','torchvision')
if ($cudaIndex) { $torchArgs += @('--index-url',$cudaIndex) }
& $venvPy @torchArgs
if ($LASTEXITCODE -ne 0) { throw "torch install failed" }
Write-Ok "PyTorch installed"

# ---------------------------------------------------------------------------
# 4. Install nougat-ocr + pin its old-API dependencies
# ---------------------------------------------------------------------------
Write-Step "Installing nougat-ocr"
& $venvPy -m pip install --quiet nougat-ocr
if ($LASTEXITCODE -ne 0) { throw "nougat-ocr install failed" }

Write-Step "Pinning Nougat-compatible dependency versions"
$pins = @(
    'transformers==4.34.1',
    'tokenizers<0.15',
    'albumentations<1.4',
    'opencv-python-headless<4.10',
    'pydantic<2',
    'pypdfium2==4.18.0',
    'pytorch-lightning<2.4',
    'lightning<2.4',
    'timm==0.5.4',
    'numpy<2'
)
& $venvPy -m pip install --quiet @pins
if ($LASTEXITCODE -ne 0) { throw "pinning failed" }
Write-Ok "Dependencies pinned for Nougat 0.1.17 compatibility"

# LlamaParse client (cloud engine, free tier)
Write-Step "Installing LlamaParse SDK (cloud engine)"
& $venvPy -m pip install --quiet llama-cloud-services 'llama-cloud==0.1.46'
if ($LASTEXITCODE -eq 0) { Write-Ok "LlamaParse SDK installed" }
else { Write-Warn2 "LlamaParse SDK install failed (cloud engine will be unavailable)" }

# ---------------------------------------------------------------------------
# 5. Pandoc (optional)
# ---------------------------------------------------------------------------
if (-not $SkipPandoc) {
    Write-Step "Ensuring Pandoc is installed"
    function Test-Pandoc {
        if (Get-Command pandoc -ErrorAction SilentlyContinue) { return $true }
        return (Test-Path "$env:ProgramFiles\Pandoc\pandoc.exe") -or
               (Test-Path "$env:LOCALAPPDATA\Programs\Pandoc\pandoc.exe")
    }
    if (Test-Pandoc) {
        Write-Ok "Pandoc already installed"
    } else {
        winget install --id JohnMacFarlane.Pandoc -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
        # winget exits non-zero in many "already installed/up-to-date" cases,
        # so re-check by file presence rather than trusting $LASTEXITCODE.
        if (Test-Pandoc) { Write-Ok "Pandoc installed" }
        else { Write-Warn2 "Pandoc not found after install attempt - HTML/PDF export will be unavailable" }
    }
}

# ---------------------------------------------------------------------------
# 6. Copy app files
# ---------------------------------------------------------------------------
Write-Step "Installing application files"
$srcAppDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'app'
if (-not (Test-Path $srcAppDir)) { throw "Cannot find app source dir at $srcAppDir" }
Copy-Item (Join-Path $srcAppDir '*') -Destination $appDir -Recurse -Force
Write-Ok "App files copied to $appDir"

# ---------------------------------------------------------------------------
# 7. PATH + Start Menu shortcut
# ---------------------------------------------------------------------------
Write-Step "Adding to user PATH"
$userPath = [System.Environment]::GetEnvironmentVariable('Path','User')
if ($userPath -notlike "*$appDir*") {
    [System.Environment]::SetEnvironmentVariable('Path', "$userPath;$appDir", 'User')
    Write-Ok "Added $appDir to user PATH (open a new terminal to use)"
} else {
    Write-Ok "Already on PATH"
}

# Provide a friendly command name: nougat-pdf.bat -> Nougat.bat
$cmdShim = Join-Path $appDir 'nougat-pdf.bat'
Set-Content -Path $cmdShim -Value @"
@echo off
call "%~dp0Nougat.bat" %*
"@ -Encoding ASCII

Write-Step "Creating Start Menu shortcut"
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$lnk = Join-Path $startMenu 'Nougat PDF Converter.lnk'
$ws  = New-Object -ComObject WScript.Shell
$sc  = $ws.CreateShortcut($lnk)
$sc.TargetPath       = Join-Path $appDir 'Nougat.bat'
$sc.WorkingDirectory = $appDir
$sc.IconLocation     = "$env:SystemRoot\System32\shell32.dll, 23"
$sc.Description      = 'Nougat PDF Converter'
$sc.Save()
Write-Ok "Shortcut: $lnk"

# ---------------------------------------------------------------------------
# 8. Optional: pre-download model weights
# ---------------------------------------------------------------------------
if ($PreloadModel) {
    Write-Step "Pre-downloading Nougat 0.1.0-base model (~1.4 GB)"
    & $venvPy -c "from nougat.utils.checkpoint import get_checkpoint; get_checkpoint(model_tag='0.1.0-base')"
    if ($LASTEXITCODE -eq 0) { Write-Ok "Model cached" }
    else { Write-Warn2 "Model download failed (it will retry on first run)" }
}

Write-Host "`nInstall complete." -ForegroundColor Green
Write-Host "Launch from the Start Menu (Nougat PDF Converter)" -ForegroundColor Green
Write-Host "or from any new terminal:  nougat-pdf"            -ForegroundColor Green
