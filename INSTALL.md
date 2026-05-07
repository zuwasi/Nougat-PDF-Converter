# One-time Environment Setup

This app expects a Python 3.12 venv at `C:\nougat-env` with a very specific
set of pinned dependencies. Nougat 0.1.17 was released against older
versions of `transformers`, `albumentations`, `pypdfium2`, etc. Newer
versions break it.

## 1. Create the venv

You need Python 3.12 installed (`py -3.12 --version`). Then:

```powershell
py -3.12 -m venv C:\nougat-env
C:\nougat-env\Scripts\python.exe -m pip install --upgrade pip
```

## 2. Install PyTorch with CUDA

For an **NVIDIA RTX 50-series (Blackwell)** card you need the cu128 wheels:

```powershell
C:\nougat-env\Scripts\python.exe -m pip install torch torchvision `
    --index-url https://download.pytorch.org/whl/cu128
```

For older cards (RTX 30/40 series), `cu124` wheels also work.

Verify CUDA:

```powershell
C:\nougat-env\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## 3. Install Nougat and pin its dependencies

```powershell
C:\nougat-env\Scripts\python.exe -m pip install nougat-ocr

# Roll the breakers back to versions Nougat 0.1.17 was tested against
C:\nougat-env\Scripts\python.exe -m pip install `
    "transformers==4.34.1" "tokenizers<0.15" `
    "albumentations<1.4" "opencv-python-headless<4.10" `
    "pydantic<2" "pypdfium2==4.18.0" `
    "pytorch-lightning<2.4" "lightning<2.4" `
    "timm==0.5.4" "numpy<2"
```

## 4. (Optional) Pandoc and MiKTeX for HTML/PDF export

```powershell
winget install --id JohnMacFarlane.Pandoc -e
winget install --id MiKTeX.MiKTeX -e          # only if you want PDF output
```

## 5. First run

Double-click `Nougat.bat`. The first run will download the Nougat
`0.1.0-base` model weights (~1.4 GB) into
`%USERPROFILE%\.cache\torch\hub\nougat`.
