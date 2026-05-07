# Nougat PDF Converter

A Windows GUI app that converts **scientific PDFs** (including scanned papers
with complex math) into **Markdown**, **HTML**, and optionally **PDF**, using
Meta's [Nougat](https://github.com/facebookresearch/nougat) model running on
your local **GPU**.

Where typical PDF parsers (PyPDF, pdfminer, even LiteParse) fail on scanned
papers and equations, Nougat understands the page visually and emits clean
Mathpix Markdown with proper LaTeX for formulas.

---

## Quick Install (recommended)

1. Download the latest `NougatPDFConverter-vX.Y.Z.zip` from the
   [Releases page](https://github.com/zuwasi/Nougat-PDF-Converter/releases).
2. Right-click → **Extract All...**
3. Open the extracted folder, go into `installer\`, and double-click
   **`Install.cmd`**.

The installer will:

- Install Python 3.12 (via winget) if missing.
- Create a self-contained venv at `%LOCALAPPDATA%\NougatPDFConverter\venv`.
- Detect your NVIDIA GPU and install the matching CUDA-enabled PyTorch
  (Blackwell/RTX 50 -> cu128, older -> cu124, or CPU fallback).
- Install Nougat plus the exact pinned dependencies it needs.
- Install Pandoc (for HTML/PDF export).
- Add a Start Menu shortcut and a `nougat-pdf` command on your PATH.

When it finishes, launch **Nougat PDF Converter** from the Start Menu, or
type `nougat-pdf` in any new terminal.

### Installer flags

```powershell
# Skip Pandoc install (use this if you only want .mmd output)
.\Install.cmd -SkipPandoc

# Force CPU-only install (no NVIDIA GPU)
.\Install.cmd -Cpu

# Pre-download the Nougat model weights (~1.4 GB) so first run is instant
.\Install.cmd -PreloadModel

# Custom install location
.\Install.cmd -InstallDir "D:\Apps\NougatPDFConverter"
```

### Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File installer\uninstall.ps1
```

(Python, Pandoc, and CUDA drivers are intentionally left alone.)

---

## Features

- One-click GUI: pick a PDF, pick output folder + name, click **Convert**.
- Page range support (`1-5,10,15-20`) or whole document.
- Outputs `.mmd` (Markdown), `.html` (with MathJax), and optionally `.pdf`.
- Auto-detects CUDA GPU (~10 s/page on an RTX 5080; 60-90 s/page on CPU).
- Zero cloud dependencies - runs entirely locally.

## Requirements

- Windows 10/11 64-bit
- ~5 GB free disk (PyTorch + model weights)
- Optional: NVIDIA GPU with current drivers (highly recommended)

## Manual / Developer Install

See [INSTALL.md](INSTALL.md) for the step-by-step venv setup if you don't
want to use the installer.

## Files

- [`app/nougat_app.py`](app/nougat_app.py) - the Tkinter GUI and conversion pipeline.
- [`app/Nougat.bat`](app/Nougat.bat) - launcher (uses `pythonw.exe`, no console window).
- [`installer/install.ps1`](installer/install.ps1) - the PowerShell installer.
- [`installer/Install.cmd`](installer/Install.cmd) - bootstraps the installer with execution-policy bypass.
- [`installer/uninstall.ps1`](installer/uninstall.ps1) - clean removal.
- [`installer/build-release.ps1`](installer/build-release.ps1) - packages a release ZIP and (with `-Publish`) creates a GitHub Release.

## License

MIT (this wrapper). Nougat itself is released by Meta under CC-BY-NC-4.0 -
review their license before commercial use.
