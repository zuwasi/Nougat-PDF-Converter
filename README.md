# Nougat PDF Converter

A Windows GUI app that converts **scientific PDFs** — including scanned papers
with complex math — into **Markdown**, **HTML**, and optionally **PDF**, using
Meta's [Nougat](https://github.com/facebookresearch/nougat) model running on
your local **NVIDIA GPU** (or CPU).

Where typical PDF parsers (PyPDF, pdfminer, even LiteParse) fail on scanned
papers and equations, Nougat understands the page visually and emits clean
[Mathpix Markdown](https://mathpix.com/docs/mathpix-markdown/overview) with
proper LaTeX for formulas.

> **Example:** A 1983 scanned MIT plasma fusion preprint with 27 multi-line
> equations involving Bessel functions, integrals, and Greek symbols converted
> in ~30 seconds (4 pages) on an RTX 5080. Equation numbers, sub/superscripts,
> primes, and references all preserved as proper LaTeX.

---

## Table of Contents

- [Quick Install](#quick-install-recommended)
- [How to Use](#how-to-use-the-gui)
- [What You Get](#output-formats)
- [Tips for Best Results](#tips-for-best-results)
- [Troubleshooting](#troubleshooting)
- [Command Line](#command-line)
- [Uninstall](#uninstall)
- [How It Works](#how-it-works)
- [Manual / Developer Install](#manual--developer-install)
- [Build a Release Yourself](#build-a-release-yourself)
- [Requirements](#requirements)
- [License](#license)

---

## Quick Install (recommended)

1. Go to the [Releases page](https://github.com/zuwasi/Nougat-PDF-Converter/releases)
   and download the latest `NougatPDFConverter-vX.Y.Z.zip`.
2. Right-click the ZIP → **Extract All...**
3. Open the extracted folder, go into the `installer\` subfolder, and
   **double-click `Install.cmd`**.
4. Approve any UAC / SmartScreen prompts. The installer will:
   - Install Python 3.12 (via winget) if missing.
   - Create a self-contained venv at `%LOCALAPPDATA%\NougatPDFConverter\venv`.
   - Detect your NVIDIA GPU and install the matching CUDA-enabled PyTorch
     (RTX 50 / Blackwell → cu128, older NVIDIA → cu124, no GPU → CPU wheels).
   - Install Nougat plus all the pinned dependencies it needs.
   - Install Pandoc (for HTML/PDF export).
   - Add a **Start Menu shortcut** ("Nougat PDF Converter") and a
     **`nougat-pdf`** command on your PATH.
5. When it finishes, launch **Nougat PDF Converter** from the Start Menu, or
   open a **new** terminal and type `nougat-pdf`.

> First conversion will download the Nougat model weights (~1.4 GB) into
> `%USERPROFILE%\.cache\torch\hub\nougat`. To pre-download during install
> instead, run `Install.cmd -PreloadModel`.

### Installer flags

```powershell
# Skip Pandoc (use this if you only want .mmd output)
.\Install.cmd -SkipPandoc

# Force CPU-only install (no NVIDIA GPU available)
.\Install.cmd -Cpu

# Pre-download the Nougat model weights so first run is instant
.\Install.cmd -PreloadModel

# Custom install location
.\Install.cmd -InstallDir "D:\Apps\NougatPDFConverter"
```

---

## How to Use the GUI

After install, launch **Nougat PDF Converter** from the Start Menu.

```diagram
╭───────────────────────────────────────────────────────────────╮
│ Nougat PDF -> Markdown / HTML / PDF                           │
├───────────────────────────────────────────────────────────────┤
│  Input PDF:    [ C:\papers\my_paper.pdf      ] [ Browse... ]  │
│  Output folder:[ C:\Users\me\Documents       ] [ Browse... ]  │
│  Output name:  [ my_paper                    ]                │
│  Pages:        [ 1-5,10                      ]  (blank = all) │
│                [x] Also produce HTML (MathJax)                │
│                [ ] Also produce PDF (needs LaTeX)             │
│  Compute:      CUDA  NVIDIA GeForce RTX 5080 Laptop GPU       │
│  [ Convert ]                                                  │
├───────────────────────────────────────────────────────────────┤
│  $ nougat ... -p 1-5,10 ...                                   │
│  100%|##########| 6/6 [00:48<00:00,  8.12s/it]                │
│  [OK] Markdown -> C:\Users\me\Documents\my_paper.mmd          │
│  [OK] HTML     -> C:\Users\me\Documents\my_paper.html         │
│  Done.                                                        │
╰───────────────────────────────────────────────────────────────╯
```

**Step-by-step:**

1. **Browse...** to pick the PDF you want to convert.
2. The **Output folder** defaults to your `Documents` folder. Change if you
   want results elsewhere.
3. **Output name** auto-fills from the PDF's filename (no extension). Edit it
   to whatever base name you want — the app appends `.mmd`, `.html`, `.pdf`.
4. **Pages** (optional): leave blank to convert the whole document, or use
   ranges/lists like `1-5`, `10`, `1-3,7,12-15`.
5. Tick **HTML** to also produce a browser-renderable file with MathJax.
   Tick **PDF** if you have MiKTeX installed and want a typeset PDF.
6. Watch the **Compute** label — it shows `CUDA <gpu name>` if the GPU is
   active, or `CPU` if it's falling back.
7. Click **Convert**. The log box streams Nougat's progress live
   (~10 s/page on a recent NVIDIA GPU, 60–90 s/page on CPU).

---

## Output Formats

| Extension | What it is | Best for |
|---|---|---|
| `.mmd`  | Mathpix Markdown — plain-text Markdown with `$...$` LaTeX math | Pasting into Obsidian/Notion/Mathpix viewers, feeding to LLMs, version control |
| `.html` | Standalone HTML rendered with MathJax via Pandoc | Reading in any browser, sharing as a single file |
| `.pdf`  | Typeset PDF rendered via XeLaTeX (requires MiKTeX) | Printing, archiving, publishing |

The `.mmd` file is the **primary** output. HTML and PDF are post-processed
from it with [Pandoc](https://pandoc.org/).

---

## Tips for Best Results

- **Skip the figure-only pages.** Nougat handles text and equations beautifully
  but slows down (and can hallucinate) on pages that are 100% diagrams. Use the
  **Pages** field to limit to text/equation pages.
- **Check the first equation of each section.** Nougat occasionally gets stuck
  in a token-repetition loop on hard-to-read symbols — you'll see something
  like `\text{\text{\text{...}}}`. Re-running just that page sometimes fixes it.
- **Keep the GUI open while converting** — the live log is the best progress
  signal. The progress bar from the underlying `nougat` CLI updates per page.
- **For huge documents (50+ pages),** convert in chunks of ~20 pages at a
  time and concatenate the `.mmd` files. This is more resilient to errors
  than one big run.
- **Older typewriter-era scans** (pre-2000) are harder than modern arXiv PDFs
  because Nougat was trained on the latter. Expect more equation errors on
  those — but it's still dramatically better than alternatives.

---

## Troubleshooting

### "Could not find a Nougat venv"
The launcher couldn't find `venv\Scripts\pythonw.exe` next to the app or at
`C:\nougat-env\Scripts\pythonw.exe`. Re-run the installer.

### Compute says "CPU" instead of "CUDA <gpu>"
- Make sure you have an NVIDIA GPU and current drivers (`nvidia-smi` works
  in PowerShell).
- If you have an RTX 50-series card and installed before the cu128 wheels
  were available, re-run the installer. It's safe to re-run over an existing
  install.

### "pandoc not found" warning
Open a new terminal and run `pandoc --version`. If it's missing, install with
`winget install --id JohnMacFarlane.Pandoc -e` and re-run the conversion.

### PDF output fails with `! LaTeX Error`
You need a LaTeX engine. Install MiKTeX:
```powershell
winget install --id MiKTeX.MiKTeX -e
```
Then re-run the conversion. The first PDF will be slow because MiKTeX
fetches packages on demand.

### Garbled equation with repeated `\text{...}`
Nougat token-loop on a hard scan. Try:
- Re-running just that page.
- Converting at higher DPI (edit `nougat_app.py`, add `--dpi 200` to the
  command list).
- For mission-critical math, send that page to [Mathpix](https://mathpix.com/).

### Out-of-memory on GPU
Add `--batchsize 1` (already the default). On 8 GB cards you may need to
fall back to CPU; pass `-Cpu` to the installer to reinstall with CPU wheels.

### "ImportError: numpy.core.multiarray failed to import"
Some dependency on PATH is using a different numpy. The installer pins
`numpy<2`. Re-run the installer to reset the venv state.

---

## Command Line

After install, the `nougat-pdf` command is on your PATH (in any **new**
terminal). It just launches the GUI — there is no separate CLI yet. If you
want to script conversions directly, call the underlying `nougat` binary
from the venv:

```powershell
& "$env:LOCALAPPDATA\NougatPDFConverter\venv\Scripts\nougat.exe" `
    "C:\path\to\paper.pdf" `
    -o "C:\path\to\output" `
    -m 0.1.0-base --no-skipping -p 1-5 --batchsize 1
```

---

## Uninstall

From PowerShell, in the extracted release folder:

```powershell
powershell -ExecutionPolicy Bypass -File installer\uninstall.ps1
```

This removes:
- The install dir (`%LOCALAPPDATA%\NougatPDFConverter` by default)
- The Start Menu shortcut
- The user PATH entry

It **does not** remove Python, Pandoc, MiKTeX, or NVIDIA drivers — those
may be used by other software on your system.

---

## How It Works

```diagram
              ╭──────────────╮
              │  Your PDF    │
              ╰──────┬───────╯
                     │
                     ▼
        ╭────────────────────────╮
        │ pypdfium2 rasterises   │
        │ each page to image     │
        ╰──────┬─────────────────╯
               │
               ▼
        ╭──────────────────────────────╮
        │ Nougat Vision-Encoder-Decoder│  ←  runs on GPU (CUDA)
        │ (~250 M parameter Donut SwT) │
        ╰──────┬───────────────────────╯
               │
               ▼
        ╭────────────────────────╮
        │  Mathpix Markdown      │
        │  (.mmd, with LaTeX)    │
        ╰──────┬─────────────────╯
               │
        ╭──────┴───────────╮
        ▼                  ▼
  ╭───────────╮      ╭───────────╮
  │  Pandoc   │      │  Pandoc   │
  │  -> HTML  │      │  -> PDF   │
  │ (MathJax) │      │ (XeLaTeX) │
  ╰───────────╯      ╰───────────╯
```

The GUI is a thin Tkinter wrapper that:
1. Discovers the venv (env var → `../venv` → `C:\nougat-env`).
2. Spawns the `nougat` CLI as a subprocess and streams its stdout/stderr to
   the log box.
3. Renames the output to your chosen base name.
4. Optionally invokes Pandoc to produce HTML and/or PDF.

---

## Manual / Developer Install

If you'd rather not run the installer, the exact venv-bootstrap steps live
in [INSTALL.md](INSTALL.md). The dependency pins are necessary because
Nougat 0.1.17 was released against older versions of `transformers`,
`albumentations`, `pypdfium2`, etc. Newer versions break it.

---

## Build a Release Yourself

```powershell
# Build a ZIP only
powershell -ExecutionPolicy Bypass -File installer\build-release.ps1 -Version 1.0.2

# Build a ZIP and create a GitHub Release (requires `gh auth login`)
powershell -ExecutionPolicy Bypass -File installer\build-release.ps1 -Version 1.0.2 -Publish
```

---

## Requirements

- Windows 10 or 11, 64-bit
- ~5 GB free disk (PyTorch + CUDA + Nougat model weights)
- ~6 GB free RAM
- **Recommended:** NVIDIA GPU with current drivers (RTX 20-series or newer
  for sensible speed; RTX 50-series automatically uses cu128 wheels)

The installer handles everything else.

---

## Files in this Repo

- [`app/nougat_app.py`](app/nougat_app.py) — the Tkinter GUI and conversion pipeline.
- [`app/Nougat.bat`](app/Nougat.bat) — launcher (uses `pythonw.exe`, no console window).
- [`installer/install.ps1`](installer/install.ps1) — the PowerShell installer.
- [`installer/Install.cmd`](installer/Install.cmd) — bootstraps the installer with execution-policy bypass.
- [`installer/uninstall.ps1`](installer/uninstall.ps1) — clean removal.
- [`installer/build-release.ps1`](installer/build-release.ps1) — packages a release ZIP and (with `-Publish`) creates a GitHub Release.

---

## License

This wrapper: **MIT** (see [LICENSE](LICENSE)).

Nougat itself is released by Meta under **CC-BY-NC-4.0** — review their
[license](https://github.com/facebookresearch/nougat/blob/main/LICENSE)
before commercial use.

PyTorch (BSD-3-Clause), Pandoc (GPL-2.0), MiKTeX (mixed) all have their
own licenses — none are bundled in this repo or release ZIP; the installer
fetches them from official sources at install time.
