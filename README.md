# Nougat PDF Converter

A small Windows GUI app that converts **scientific PDFs** (including scanned
papers with complex math) into **Markdown**, **HTML**, and optionally **PDF**,
using Meta's [Nougat](https://github.com/facebookresearch/nougat) model
running on your local **GPU**.

Where typical PDF parsers (PyPDF, pdfminer, even LiteParse) fail on scanned
papers and equations, Nougat understands the page visually and emits clean
Mathpix Markdown with proper LaTeX for formulas.

---

## Features

- One-click GUI: pick a PDF, pick output folder + name, click **Convert**.
- Page range support (`1-5,10,15-20`) or whole document.
- Outputs `.mmd` (Markdown), `.html` (with MathJax), and optionally `.pdf`.
- Uses CUDA on an NVIDIA GPU automatically (~10 s/page on an RTX 5080;
  60-90 s/page on CPU).
- Zero cloud dependencies - runs entirely locally.

## Requirements

- **Windows 10/11**
- **Python 3.12** in a venv at `C:\nougat-env` containing `nougat-ocr` and a
  CUDA-capable PyTorch build (see [INSTALL.md](INSTALL.md)).
- **NVIDIA GPU** with current drivers (optional but strongly recommended).
- **Pandoc** at `C:\Program Files\Pandoc\pandoc.exe` (for HTML/PDF export).
  Install with `winget install --id JohnMacFarlane.Pandoc -e`.
- **MiKTeX** (only if you want PDF output).
  Install with `winget install --id MiKTeX.MiKTeX -e`.

## Usage

1. Double-click `Nougat.bat` (or run `python nougat_app.py` from the
   `C:\nougat-env` venv).
2. **Browse...** to pick a PDF.
3. Pick an output folder and base file name.
4. (Optional) Set page range; leave blank for the full document.
5. Tick HTML/PDF options as desired.
6. Click **Convert**. Watch the live log for progress.

The app shows whether it's running on `CUDA <gpu name>` or falling back to
`CPU` in the status bar.

## Files

- [`nougat_app.py`](nougat_app.py) - the Tkinter GUI and conversion pipeline.
- [`Nougat.bat`](Nougat.bat) - double-click launcher (uses `pythonw.exe`,
  no console window).
- [`INSTALL.md`](INSTALL.md) - one-time environment setup steps.

## License

MIT (the wrapper). Nougat itself is released by Meta under CC-BY-NC-4.0 -
review their license before commercial use.
