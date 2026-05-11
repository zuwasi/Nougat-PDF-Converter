"""
Nougat GUI - simple desktop app for OCR'ing scientific PDFs to Mathpix Markdown
(and optionally HTML/PDF via pandoc).

Two parsing engines:
  * Nougat   - local, free, GPU-accelerated, weak on dense layouts
  * LlamaParse premium - cloud, free tier (1000 credits/day), much better
                         on math/2-column papers
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import Tk, StringVar, BooleanVar, filedialog, messagebox, END, DISABLED, NORMAL
from tkinter import ttk, scrolledtext

ENGINE_NOUGAT     = "Nougat (local, free, GPU)"
ENGINE_LLAMAPARSE = "LlamaParse Premium (cloud, free tier)"
SETTINGS_PATH = Path(os.environ.get("LOCALAPPDATA",
                                    str(Path.home()))) / "NougatPDFConverter" / "settings.json"


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_settings(data: dict) -> None:
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

# --- Configuration ----------------------------------------------------------
DEFAULT_MODEL = "0.1.0-base"


def _find_venv() -> Path:
    """Locate the Python venv that has nougat installed.

    Resolution order:
      1. NOUGAT_VENV environment variable (set by installer/launcher).
      2. ../venv next to this script (release/installer layout).
      3. C:\\nougat-env (legacy / dev layout).
    """
    here = Path(__file__).resolve().parent
    candidates = []
    env = os.environ.get("NOUGAT_VENV")
    if env:
        candidates.append(Path(env))
    candidates += [here.parent / "venv", Path(r"C:\nougat-env")]
    for c in candidates:
        if (c / "Scripts" / "python.exe").is_file():
            return c
    return candidates[0]  # fall through; later checks will report it


def _find_pandoc() -> Path:
    """Pandoc lives wherever winget/installer put it; check PATH first."""
    on_path = shutil.which("pandoc")
    if on_path:
        return Path(on_path)
    for c in (
        Path(r"C:\Program Files\Pandoc\pandoc.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / r"Programs\Pandoc\pandoc.exe",
    ):
        if c.is_file():
            return c
    return Path("pandoc.exe")  # let it fail later with a clear message


VENV          = _find_venv()
NOUGAT_PYTHON = VENV / "Scripts" / "python.exe"
NOUGAT_EXE    = VENV / "Scripts" / "nougat.exe"
PANDOC_EXE    = _find_pandoc()


def _default_output_dir() -> str:
    """Pick a safe writable folder, avoiding Documents on Windows because it
    is often protected by Controlled Folder Access / OneDrive Backup with
    deny-delete ACLs that break atomic file moves."""
    candidates = [Path(r"C:\Amp_demos\nougat-out"), Path.home() / "Nougat-Output"]
    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            # Probe write access by creating + deleting a sentinel file.
            probe = c / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return str(c)
        except Exception:
            continue
    # Last resort
    return str(Path.home())


def auto_clean_mmd(text: str) -> tuple[str, dict]:
    """Strip common Nougat OCR artefacts so the math at least renders.
    Returns (cleaned_text, stats)."""
    stats = {"text_loops": 0, "ws_runs": 0, "bar_loops": 0, "stray_rbrack": 0}

    # 1. Runaway \text{\text{\text{...}}} loops -> single \text{}
    def _fix_text_loop(m: re.Match) -> str:
        stats["text_loops"] += 1
        return r"\text{}"
    text = re.sub(r"(?:\\text\{\s*){4,}\}*", _fix_text_loop, text)

    # 2. Long whitespace runs in math: \,\,\,\,\,...  ->  \quad
    def _fix_ws(m: re.Match) -> str:
        stats["ws_runs"] += 1
        return r"\quad "
    text = re.sub(r"(?:\\,\s*){8,}", _fix_ws, text)

    # 3. Bar-vector token loops like
    #    \bar{\mathbf{x}} \bar{\mathbf{y}} \bar{\mathbf{x}} \bar{\mathbf{y}} ...
    def _fix_bar_loop(m: re.Match) -> str:
        stats["bar_loops"] += 1
        return r"\bar{\mathbf{x}}\bar{\mathbf{x}} + \bar{\mathbf{y}}\bar{\mathbf{y}} + \bar{\mathbf{z}}\bar{\mathbf{z}}"
    text = re.sub(
        r"(?:\\bar\{\\mathbf\{[xyz]\}\}\s*){6,}",
        _fix_bar_loop, text,
    )

    # 4. Stray \rbrack with no opening \lbrack on the same equation line
    def _fix_rbrack(m: re.Match) -> str:
        stats["stray_rbrack"] += 1
        return "]"
    text = re.sub(r"\\rbrack(?![\w])", _fix_rbrack, text)

    return text, stats


def run_llamaparse(pdf: Path, out_md: Path, api_key: str, log) -> None:
    """Send pdf to LlamaParse premium-mode and save the resulting markdown."""
    log("Submitting to LlamaParse (premium mode)...\n")
    os.environ["LLAMA_CLOUD_API_KEY"] = api_key
    try:
        from llama_cloud_services import LlamaParse
    except ImportError:
        raise RuntimeError(
            "llama-cloud-services not installed. Run:\n"
            f"  {NOUGAT_PYTHON} -m pip install llama-cloud-services llama-cloud==0.1.46"
        )
    parser = LlamaParse(
        result_type="markdown",
        parse_mode="parse_page_with_lvm",
        language="en",
        verbose=False,
    )
    result = parser.parse(str(pdf))
    try:
        result.save_markdown(str(out_md))
    except AttributeError:
        # Fallback for very new SDK shapes that drop .save_markdown
        md = ""
        for page in getattr(result, "pages", []):
            md += getattr(page, "md", "") + "\n\n"
        out_md.write_text(md, encoding="utf-8")
    log(f"  LlamaParse done -> {out_md.name}\n")


def gpu_status() -> str:
    """Return a short string describing CUDA / GPU availability."""
    try:
        out = subprocess.check_output(
            [str(NOUGAT_PYTHON), "-c",
             "import torch;print('CUDA' if torch.cuda.is_available() else 'CPU');"
             "print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"],
            stderr=subprocess.STDOUT, text=True, timeout=15,
        ).strip().splitlines()
        mode = out[0] if out else "?"
        dev  = out[1] if len(out) > 1 else ""
        return f"{mode}  {dev}".strip()
    except Exception as e:
        return f"unknown ({e})"


class NougatApp:
    def __init__(self, root: Tk):
        self.root = root
        root.title("Nougat PDF -> Markdown / HTML / PDF")
        root.geometry("820x680")

        s = _load_settings()
        self.input_pdf    = StringVar()
        self.output_dir   = StringVar(value=s.get("output_dir", _default_output_dir()))
        self.out_name     = StringVar(value="output")
        self.pages        = StringVar(value="")          # blank = all
        self.figure_pages = StringVar(value="")          # render as PNG
        self.engine       = StringVar(value=s.get("engine", ENGINE_NOUGAT))
        self.api_key      = StringVar(value=s.get("llamaparse_api_key", ""))
        self.auto_clean   = BooleanVar(value=s.get("auto_clean", True))
        self.make_html    = BooleanVar(value=True)
        self.make_pdf     = BooleanVar(value=False)
        self.gpu_text     = StringVar(value="checking GPU...")

        self._build_ui()
        threading.Thread(target=self._update_gpu, daemon=True).start()

    # ---------- UI ----------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(self.root)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        # Row: input PDF
        ttk.Label(frm, text="Input PDF:").grid(row=0, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.input_pdf, width=70).grid(row=0, column=1, sticky="we", **pad)
        ttk.Button(frm, text="Browse...", command=self._pick_input).grid(row=0, column=2, **pad)

        # Row: output dir
        ttk.Label(frm, text="Output folder:").grid(row=1, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.output_dir, width=70).grid(row=1, column=1, sticky="we", **pad)
        ttk.Button(frm, text="Browse...", command=self._pick_outdir).grid(row=1, column=2, **pad)

        # Row: output base name
        ttk.Label(frm, text="Output name:").grid(row=2, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.out_name, width=40).grid(row=2, column=1, sticky="w", **pad)

        # Row: page range
        ttk.Label(frm, text="Pages (e.g. 1-5,10):").grid(row=3, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.pages, width=20).grid(row=3, column=1, sticky="w", **pad)
        ttk.Label(frm, text="(blank = all)").grid(row=3, column=1, sticky="w", padx=(180, 0))

        # Row: figure pages (rendered as PNG and embedded)
        ttk.Label(frm, text="Figure pages (render as image):").grid(row=4, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.figure_pages, width=20).grid(row=4, column=1, sticky="w", **pad)
        ttk.Label(frm, text="(e.g. 14-29; blank = none)").grid(row=4, column=1, sticky="w", padx=(180, 0))

        # Row: engine selector
        ttk.Label(frm, text="Engine:").grid(row=5, column=0, sticky="e", **pad)
        engine_cb = ttk.Combobox(frm, textvariable=self.engine,
                                 values=[ENGINE_NOUGAT, ENGINE_LLAMAPARSE],
                                 state="readonly", width=44)
        engine_cb.grid(row=5, column=1, sticky="w", **pad)
        engine_cb.bind("<<ComboboxSelected>>", lambda e: self._on_engine_change())

        # Row: LlamaParse API key (visible only when LlamaParse selected)
        self.api_lbl = ttk.Label(frm, text="LlamaParse API key:")
        self.api_lbl.grid(row=6, column=0, sticky="e", **pad)
        self.api_entry = ttk.Entry(frm, textvariable=self.api_key, width=58, show="*")
        self.api_entry.grid(row=6, column=1, sticky="w", **pad)
        ttk.Button(frm, text="Save", command=self._save_settings_now).grid(row=6, column=2, **pad)

        # Row: format / cleanup checkboxes
        opts = ttk.Frame(frm)
        opts.grid(row=7, column=1, sticky="w", **pad)
        ttk.Checkbutton(opts, text="Auto-clean OCR artefacts",
                        variable=self.auto_clean).pack(side="left", padx=4)
        ttk.Checkbutton(opts, text="Also produce HTML (MathJax)",
                        variable=self.make_html).pack(side="left", padx=4)
        ttk.Checkbutton(opts, text="Also produce PDF (needs LaTeX)",
                        variable=self.make_pdf).pack(side="left", padx=4)

        # Row: GPU status
        gpu_frame = ttk.Frame(frm)
        gpu_frame.grid(row=8, column=1, sticky="w", **pad)
        ttk.Label(gpu_frame, text="Compute:").pack(side="left")
        ttk.Label(gpu_frame, textvariable=self.gpu_text, foreground="#0a6").pack(side="left", padx=4)

        # Row: run button
        self.run_btn = ttk.Button(frm, text="Convert", command=self._run)
        self.run_btn.grid(row=9, column=1, sticky="w", **pad)

        # Log box
        self.log = scrolledtext.ScrolledText(frm, height=18, wrap="word", font=("Consolas", 9))
        self.log.grid(row=10, column=0, columnspan=3, sticky="nsew", **pad)
        frm.rowconfigure(10, weight=1)
        frm.columnconfigure(1, weight=1)

        self._on_engine_change()  # initial show/hide of the API key row

    def _on_engine_change(self):
        if self.engine.get() == ENGINE_LLAMAPARSE:
            self.api_lbl.grid()
            self.api_entry.grid()
        else:
            self.api_lbl.grid_remove()
            self.api_entry.grid_remove()

    def _save_settings_now(self):
        _save_settings({
            "output_dir": self.output_dir.get(),
            "engine": self.engine.get(),
            "llamaparse_api_key": self.api_key.get(),
            "auto_clean": bool(self.auto_clean.get()),
        })
        messagebox.showinfo("Saved", f"Settings saved to:\n{SETTINGS_PATH}")

    # ---------- Helpers ----------
    def _pick_input(self):
        f = filedialog.askopenfilename(
            title="Pick a PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if f:
            self.input_pdf.set(f)
            stem = Path(f).stem
            if not self.out_name.get() or self.out_name.get() == "output":
                self.out_name.set(stem)

    def _pick_outdir(self):
        d = filedialog.askdirectory(title="Pick output folder")
        if d:
            self.output_dir.set(d)

    def _update_gpu(self):
        self.gpu_text.set(gpu_status())

    def _log(self, text: str):
        self.log.insert(END, text)
        self.log.see(END)
        self.log.update_idletasks()

    # ---------- Run pipeline ----------
    @staticmethod
    def _parse_pages(spec: str) -> list[int]:
        """Parse '1-5,10,15-17' -> [1,2,3,4,5,10,15,16,17]."""
        out: list[int] = []
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                out.extend(range(int(a), int(b) + 1))
            else:
                out.append(int(part))
        return sorted(set(out))

    def _render_figure_pages(self, in_pdf: Path, out_dir: Path,
                             name: str, page_spec: str) -> list[Path]:
        """Render selected pages of in_pdf as PNGs into <out_dir>/<name>_figures/.
        Returns the produced PNG paths in page order."""
        try:
            import pypdfium2 as pdfium
        except ImportError:
            self._log("\n[WARN] pypdfium2 not available; cannot render figure pages.\n")
            return []

        try:
            pages = self._parse_pages(page_spec)
        except ValueError as e:
            self._log(f"\n[WARN] Could not parse figure pages '{page_spec}': {e}\n")
            return []
        if not pages:
            return []

        fig_dir = out_dir / f"{name}_figures"
        fig_dir.mkdir(exist_ok=True)
        produced: list[Path] = []

        self._log(f"\nRendering figure pages {pages} -> {fig_dir.name}/\n")
        pdf = pdfium.PdfDocument(str(in_pdf))
        try:
            n = len(pdf)
            for p in pages:
                if p < 1 or p > n:
                    self._log(f"  page {p}: out of range (PDF has {n})\n")
                    continue
                page = pdf[p - 1]
                # 200 DPI -> scale = 200/72 ~ 2.78
                bitmap = page.render(scale=200 / 72)
                pil = bitmap.to_pil()
                out_png = fig_dir / f"page-{p:03d}.png"
                pil.save(out_png, format="PNG", optimize=True)
                produced.append(out_png)
                self._log(f"  page {p}: -> {out_png.name}\n")
        finally:
            pdf.close()
        return produced

    def _safe_replace(self, src: Path, dst: Path,
                      retries: int = 6, delay: float = 0.5) -> None:
        """Move src -> dst, replacing dst if it exists. Robust against
        Windows + OneDrive sync transient locks: retries with backoff and
        falls back to copy + best-effort delete."""
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                # Path.replace overwrites atomically on the same volume.
                src.replace(dst)
                return
            except (PermissionError, OSError) as e:
                last_err = e
                self._log(
                    f"  rename attempt {attempt+1}/{retries} failed: {e.__class__.__name__}; retrying...\n"
                )
                time.sleep(delay)
                delay *= 1.5
        # Last resort: copy + try to delete the source.
        self._log("  falling back to copy + delete\n")
        try:
            shutil.copy2(str(src), str(dst))
            try:
                src.unlink()
            except Exception as ue:
                self._log(f"  warning: could not delete staging file ({ue})\n")
            return
        except Exception as e:
            raise RuntimeError(
                f"Could not write {dst}. The file may be open in another program "
                f"(browser, editor) or locked by OneDrive sync. Original error: {last_err}"
            ) from e

    @staticmethod
    def _embed_figures_in_mmd(mmd_path: Path, name: str, pngs: list[Path]) -> int:
        """Insert each rendered page-image inline, right under the matching
        `Figure N.` caption Nougat extracted. Pairs caption-N with the i-th
        rendered page (assumes user gave figure pages in figure-number order,
        which is true for nearly all scientific papers).

        Any rendered pages with no matching caption are appended at the end
        under '## Additional figure pages'. Returns total embedded count.
        """
        if not pngs:
            return 0
        text = mmd_path.read_text(encoding="utf-8")
        lines = text.splitlines()

        # Match common caption styles: "Figure 1.", "Fig. 1.", "Fig 1:",
        # "Figure 1a:", etc.
        cap_re = re.compile(r"^\s*(?:Figure|Fig\.?)\s+(\d+[a-z]?)\s*[.:]\s")
        seen: set[str] = set()
        cap_positions: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            m = cap_re.match(line)
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                cap_positions.append((i, m.group(1)))

        paired = list(zip(cap_positions, pngs))
        leftover = pngs[len(paired):]

        # Insert bottom-up so the indices we recorded stay valid.
        for (idx, label), png in reversed(paired):
            rel = f"{name}_figures/{png.name}".replace("\\", "/")
            lines.insert(idx + 1, f"\n![Figure {label}]({rel})\n")

        if leftover:
            lines.append("")
            lines.append("## Additional figure pages")
            for png in leftover:
                page_num = int(png.stem.split("-")[-1])
                rel = f"{name}_figures/{png.name}".replace("\\", "/")
                lines.append(f"\n**Page {page_num}**\n")
                lines.append(f"![Page {page_num}]({rel})\n")

        mmd_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return len(pngs)

    def _run(self):
        in_pdf = Path(self.input_pdf.get().strip().strip('"'))
        out_dir = Path(self.output_dir.get().strip().strip('"'))
        name = (self.out_name.get().strip() or in_pdf.stem)
        pages = self.pages.get().strip()
        fig_pages = self.figure_pages.get().strip()
        engine = self.engine.get()

        if not in_pdf.is_file():
            messagebox.showerror("Missing file", f"Input PDF not found:\n{in_pdf}")
            return
        if engine == ENGINE_NOUGAT and not NOUGAT_EXE.is_file():
            messagebox.showerror("Nougat not found",
                                 f"Expected nougat at:\n{NOUGAT_EXE}\n\nRe-run the installer.")
            return
        if engine == ENGINE_LLAMAPARSE and not self.api_key.get().strip():
            messagebox.showerror("API key required",
                                 "LlamaParse needs an API key. Get one free at\n"
                                 "https://cloud.llamaindex.ai\nthen paste it and click Save.")
            return
        out_dir.mkdir(parents=True, exist_ok=True)

        # Persist current settings on every run.
        _save_settings({
            "output_dir": self.output_dir.get(),
            "engine": engine,
            "llamaparse_api_key": self.api_key.get(),
            "auto_clean": bool(self.auto_clean.get()),
        })

        self.run_btn.configure(state=DISABLED)
        self.log.delete("1.0", END)
        threading.Thread(target=self._pipeline,
                         args=(in_pdf, out_dir, name, pages, fig_pages, engine),
                         daemon=True).start()

    def _pipeline(self, in_pdf: Path, out_dir: Path, name: str,
                  pages: str, fig_pages: str, engine: str):
        try:
            mmd_dst = out_dir / f"{name}.mmd"

            if engine == ENGINE_LLAMAPARSE:
                self._log(f"Engine: LlamaParse premium\n")
                run_llamaparse(in_pdf, mmd_dst, self.api_key.get().strip(), self._log)
                self._log(f"\n[OK] Markdown -> {mmd_dst}\n")
            else:
                # Nougat: it writes <input-stem>.mmd into the output dir, so
                # work in a stable staging dir and move afterwards.
                stage = out_dir / "_nougat_tmp"
                stage.mkdir(exist_ok=True)
                for old in stage.glob("*.mmd"):
                    old.unlink()

                cmd = [str(NOUGAT_EXE), str(in_pdf),
                       "-o", str(stage),
                       "-m", DEFAULT_MODEL,
                       "--no-skipping", "--batchsize", "1"]
                if pages:
                    cmd += ["-p", pages]

                self._log(f"Engine: Nougat\n$ {' '.join(cmd)}\n\n")
                self._stream(cmd)

                produced = list(stage.glob("*.mmd"))
                if not produced:
                    self._log("\n[ERROR] Nougat produced no .mmd file.\n")
                    return
                self._safe_replace(produced[0], mmd_dst)
                self._log(f"\n[OK] Markdown -> {mmd_dst}\n")
                shutil.rmtree(stage, ignore_errors=True)

            # Auto-clean OCR artefacts (token loops, whitespace runs, etc.)
            if self.auto_clean.get():
                txt = mmd_dst.read_text(encoding="utf-8")
                cleaned, stats = auto_clean_mmd(txt)
                if cleaned != txt:
                    mmd_dst.write_text(cleaned, encoding="utf-8")
                    self._log(f"[OK] Auto-cleaned: {stats}\n")
                else:
                    self._log("[OK] Auto-clean: no artefacts found\n")

            # Optional: render figure pages and embed them inline beside the
            # matching captions Nougat extracted.
            if fig_pages:
                pngs = self._render_figure_pages(in_pdf, out_dir, name, fig_pages)
                if pngs:
                    n = self._embed_figures_in_mmd(mmd_dst, name, pngs)
                    self._log(f"[OK] Embedded {n} figure(s) inline in .mmd\n")

            # Optional HTML
            if self.make_html.get():
                if not PANDOC_EXE.is_file():
                    self._log("\n[WARN] pandoc not found, skipping HTML.\n")
                else:
                    html = out_dir / f"{name}.html"
                    self._log(f"\nRunning pandoc -> {html.name}\n")
                    # Nougat emits LaTeX-style \(...\) and \[...\] math, not
                    # pandoc's default $...$. Enable the right extension and
                    # also widen the page (default max-width 36em chops long
                    # equations) and give it a title.
                    self._stream([
                        str(PANDOC_EXE), str(mmd_dst),
                        "-f", "markdown+tex_math_double_backslash",
                        "-s", "-o", str(html), "--mathjax",
                        "--metadata", f"title={name}",
                        "-V", "maxwidth=64em",
                    ])
                    self._log(f"[OK] HTML -> {html}\n")

            # Optional PDF
            if self.make_pdf.get():
                if not PANDOC_EXE.is_file():
                    self._log("\n[WARN] pandoc not found, skipping PDF.\n")
                else:
                    pdf = out_dir / f"{name}.pdf"
                    self._log(f"\nRunning pandoc -> {pdf.name} (needs LaTeX)\n")
                    rc = self._stream([
                        str(PANDOC_EXE), str(mmd_dst),
                        "-f", "markdown+tex_math_double_backslash",
                        "-o", str(pdf), "--pdf-engine=xelatex",
                    ])
                    if rc == 0:
                        self._log(f"[OK] PDF -> {pdf}\n")
                    else:
                        self._log("[ERROR] PDF failed. Install MiKTeX:\n"
                                  "         winget install --id MiKTeX.MiKTeX -e\n")

            self._log("\nDone.\n")
        except Exception as e:
            self._log(f"\n[EXCEPTION] {e}\n")
        finally:
            self.run_btn.configure(state=NORMAL)

    def _stream(self, cmd) -> int:
        """Run a subprocess and stream its output to the log. Returns exit code."""
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=creationflags,
        )
        assert proc.stdout is not None
        # Nougat emits tqdm bars with carriage returns; collapse them.
        for raw in iter(proc.stdout.readline, ""):
            line = re.sub(r".*\r", "", raw)  # keep only the part after the last CR
            self._log(line)
        proc.wait()
        return proc.returncode


def main():
    if not NOUGAT_PYTHON.is_file():
        print(f"ERROR: nougat venv python not found: {NOUGAT_PYTHON}", file=sys.stderr)
        sys.exit(1)
    root = Tk()
    NougatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
