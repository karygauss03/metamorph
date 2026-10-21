"""ZIP / TAR / GZIP archives (RAR and 7z input via unrar/7z)."""

import gzip
import os
import shutil
import tarfile
import zipfile
from pathlib import Path

from ..util import ConversionError, base_name, run, temp_dir, unique_path, unrar


def _safe_members(names, root):
    root = Path(root).resolve()
    for name in names:
        target = (root / name).resolve()
        if root not in target.parents and target != root:
            raise ConversionError(f"Archive entry escapes its folder: {name}")


def extract(src, dest_dir):
    """Unpack any supported archive into dest_dir (created if missing)."""
    src, dest_dir = Path(src), Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = src.name.lower()
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as zf:
            _safe_members(zf.namelist(), dest_dir)
            zf.extractall(dest_dir)
    elif name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")) or tarfile.is_tarfile(src):
        with tarfile.open(src) as tf:
            tf.extractall(dest_dir, filter="data")
    elif name.endswith(".gz"):
        with gzip.open(src, "rb") as fin, open(dest_dir / src.name[:-3], "wb") as fout:
            shutil.copyfileobj(fin, fout)
    elif name.endswith((".rar", ".7z")):
        tool = unrar()
        if not tool:
            raise ConversionError("Extracting RAR/7z needs unrar or 7z")
        if Path(tool).name == "unrar":
            run([tool, "x", "-o+", "-idq", str(src), str(dest_dir) + os.sep])
        else:
            run([tool, "x", "-y", f"-o{dest_dir}", str(src)])
    else:
        raise ConversionError(f"Unsupported archive: {src.name}")
    return dest_dir


def pack(sources, target, dest, root=None):
    """Pack files/folders into a zip, tar or tar.gz. Paths are stored relative to root."""
    dest = Path(dest)
    if target == "zip":
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for src in sources:
                src = Path(src)
                base = Path(root) if root else src.parent
                if src.is_dir():
                    for p in sorted(src.rglob("*")):
                        zf.write(p, p.relative_to(base))
                else:
                    zf.write(src, src.relative_to(base))
    else:
        mode = "w:gz" if target in ("tar.gz", "tgz") else "w"
        with tarfile.open(dest, mode) as tf:
            for src in sources:
                src = Path(src)
                base = Path(root) if root else src.parent
                tf.add(src, arcname=str(src.relative_to(base)))
    return dest


def convert(src, target, dest, ctx):
    with temp_dir() as tmp:
        content = extract(src, Path(tmp) / "x")
        items = sorted(content.iterdir())
        if not items:
            raise ConversionError(f"{Path(src).name} is empty")
        return pack(items, target, dest, root=content)


def unpack(src, ctx):
    src = Path(src)
    folder = unique_path(Path(ctx.out_dir or src.parent) / base_name(src))
    with temp_dir() as tmp:
        content = extract(src, Path(tmp) / "x")
        items = list(content.iterdir())
        if len(items) == 1 and items[0].is_dir():
            # Archive already wraps everything in one folder: don't double-nest it.
            folder = unique_path(folder.parent / items[0].name)
            shutil.move(str(items[0]), folder)
        else:
            shutil.move(str(content), folder)
    return folder


def zip_files(paths, ctx):
    first = Path(paths[0])
    name = base_name(first) if len(paths) == 1 else (first.parent.name or "Archive")
    dest = unique_path(Path(ctx.out_dir or first.parent) / f"{name}.zip")
    return pack(paths, "zip", dest)
