"""Shared helpers: backend discovery, subprocess execution, output naming."""

import os
import re
import shutil
import subprocess
import tempfile
import threading
from functools import lru_cache
from pathlib import Path

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "metamorph"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "metamorph"


class ConversionError(Exception):
    """Raised when a backend fails; the message is shown to the user."""


@lru_cache(maxsize=None)
def ffmpeg():
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


@lru_cache(maxsize=None)
def pandoc():
    path = shutil.which("pandoc")
    if path:
        return path
    try:
        import pypandoc
        return pypandoc.get_pandoc_path()
    except Exception:
        return None


@lru_cache(maxsize=None)
def soffice():
    return shutil.which("soffice") or shutil.which("libreoffice")


@lru_cache(maxsize=None)
def soffice_component(name):
    """True if a LibreOffice module ('writer', 'calc', 'impress') is installed.

    Distributions split LibreOffice into packages; soffice exists as soon as
    any one of them is installed, but can only load documents for those present.
    """
    exe = soffice()
    if not exe:
        return False
    lib = {"writer": "libswlo.so", "calc": "libsclo.so", "impress": "libsdlo.so"}[name]
    program = Path(os.path.realpath(exe)).parent
    return any((d / lib).exists() for d in (program, Path("/usr/lib/libreoffice/program"),
                                              Path("/opt/libreoffice/program")))


@lru_cache(maxsize=None)
def ghostscript():
    return shutil.which("gs")


@lru_cache(maxsize=None)
def unrar():
    return shutil.which("unrar") or shutil.which("7z")


@lru_cache(maxsize=None)
def has_module(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


def backends():
    """Name -> location (or None) for every backend, shown in Settings."""
    return {
        "ffmpeg": ffmpeg(),
        "pandoc": pandoc(),
        "LibreOffice Writer": soffice() if soffice_component("writer") else None,
        "LibreOffice Calc": soffice() if soffice_component("calc") else None,
        "LibreOffice Impress": soffice() if soffice_component("impress") else None,
        "Ghostscript": ghostscript(),
        "unrar": unrar(),
        "PyMuPDF": "python module" if has_module("pymupdf") else None,
        "pdf2docx": "python module" if has_module("pdf2docx") else None,
        "python-pptx": "python module" if has_module("pptx") else None,
        "pillow-heif": "python module" if has_module("pillow_heif") else None,
    }


def run(args, cwd=None, timeout=None, progress_parser=None):
    """Run a command, raising ConversionError with the tail of stderr on failure."""
    proc = subprocess.Popen(
        [str(a) for a in args], cwd=cwd, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if progress_parser is None else subprocess.STDOUT,
        stdin=subprocess.DEVNULL, text=True, errors="replace",
    )
    if progress_parser is not None:
        tail = []
        for line in proc.stdout:
            progress_parser(line)
            tail = (tail + [line])[-30:]
        proc.wait(timeout)
        err = "".join(tail)
    else:
        _, err = proc.communicate(timeout=timeout)
    if proc.returncode != 0:
        lines = [l for l in err.strip().splitlines() if l.strip()]
        raise ConversionError(f"{Path(str(args[0])).name} failed: " + " / ".join(lines[-3:]))
    return err


_lo_lock = threading.Lock()


def soffice_convert(src, out_dir, target, infilter=None):
    """Convert with headless LibreOffice using a private profile.

    A dedicated profile keeps conversions working while the user has
    LibreOffice open; the lock serialises calls because one profile cannot
    be shared by concurrent instances.
    """
    exe = soffice()
    if not exe:
        raise ConversionError("LibreOffice is not installed")
    profile = Path(os.environ.get("METAMORPH_LO_PROFILE", CACHE_DIR / "lo-profile"))
    profile.mkdir(parents=True, exist_ok=True)
    args = [exe, f"-env:UserInstallation={profile.as_uri()}", "--headless",
            "--norestore", "--convert-to", target, "--outdir", out_dir]
    if infilter:
        args.insert(-4, f"--infilter={infilter}")
    args.append(src)
    with _lo_lock:
        run(args, timeout=600)
    produced = Path(out_dir) / (Path(src).stem + "." + target.split(":")[0])
    if not produced.exists():
        raise ConversionError(f"LibreOffice could not convert {Path(src).name}")
    return produced


def unique_path(path):
    """Return path, or 'name (2).ext', 'name (3).ext'... if it already exists."""
    path = Path(path)
    if not path.exists():
        return path
    stem, suffix = path.name, ""
    for ext in (".tar.gz",):
        if path.name.endswith(ext):
            stem, suffix = path.name[: -len(ext)], ext
            break
    else:
        stem, suffix = path.stem, path.suffix
    stem = re.sub(r" \(\d+\)$", "", stem)
    n = 2
    while True:
        candidate = path.with_name(f"{stem} ({n}){suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def base_name(path):
    """File name without its (possibly double) extension."""
    name = Path(path).name
    for ext in (".tar.gz", ".tar.bz2", ".tar.xz"):
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return Path(path).stem


def output_for(src, ext, out_dir=None, suffix=""):
    """Unique output path for src converted to ext ('' for a directory)."""
    folder = Path(out_dir) if out_dir else Path(src).parent
    name = base_name(src) + suffix + (f".{ext}" if ext else "")
    return unique_path(folder / name)


def temp_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="job-", dir=CACHE_DIR)


def extension(path):
    name = Path(path).name.lower()
    for ext in ("tar.gz", "tar.bz2", "tar.xz"):
        if name.endswith("." + ext):
            return ext
    return Path(name).suffix.lstrip(".")


def parse_time(text):
    """'1:02:03.5', '02:03', '93' or '93.5' -> seconds."""
    text = str(text).strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) > 3:
        raise ConversionError(f"Invalid time: {text}")
    try:
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
    except ValueError:
        raise ConversionError(f"Invalid time: {text}")
    return seconds


def parse_page_ranges(text, page_count):
    """'1-3, 5, 8-' -> [0, 1, 2, 4, 7, ...] (zero based, in order given)."""
    pages = []
    for chunk in str(text).replace(" ", "").split(","):
        if not chunk:
            continue
        try:
            if "-" in chunk:
                start, end = chunk.split("-", 1)
                start = int(start) if start else 1
                end = int(end) if end else page_count
            else:
                start = end = int(chunk)
        except ValueError:
            raise ConversionError(f"Invalid page range: {chunk}")
        if start < 1 or end > page_count or start > end:
            raise ConversionError(f"Pages {chunk} are outside 1-{page_count}")
        pages.extend(range(start - 1, end))
    if not pages:
        raise ConversionError("No pages selected")
    return pages


def parse_number(cell):
    """Cell text -> int/float when it is clearly a number, in either 1,234.5 or 1.234,5 style."""
    if cell is None:
        return None
    text = str(cell).strip()
    t = text.replace(" ", "").replace("\xa0", "").replace(" ", "")
    if re.fullmatch(r"-?0\d+", t):
        return text  # leading zero: an identifier like 007, not a number
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d*\.\d+", t):
        return float(t)
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", t):        # 1,234 / 1,234.5
        return float(t.replace(",", "")) if "." in t else int(t.replace(",", ""))
    if re.fullmatch(r"-?\d*,\d+", t):                         # 38,5 (decimal comma)
        return float(t.replace(",", "."))
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", t):        # 1.234.567 / 1.234,5
        t = t.replace(".", "")
        return float(t.replace(",", ".")) if "," in t else int(t)
    return text
