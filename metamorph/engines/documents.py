"""Text documents and ebooks (pandoc, LibreOffice for PDF and legacy formats)."""

import html
import shutil
from pathlib import Path

from ..util import ConversionError, pandoc, run, soffice_component, soffice_convert, temp_dir

READERS = {
    "docx": "docx", "odt": "odt", "md": "markdown", "markdown": "markdown",
    "rtf": "rtf", "html": "html", "htm": "html", "epub": "epub",
}
WRITERS = {
    "docx": "docx", "odt": "odt", "md": "gfm", "txt": "plain",
    "epub": "epub3", "html": "html5",
}
# Formats LibreOffice renders to PDF faithfully, with page layout.
OFFICE_INPUTS = {"docx", "doc", "odt", "rtf"}


def _txt_as_html(src, tmp):
    """Plain text -> HTML paragraphs, so pandoc does not interpret it as Markdown."""
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    paras = [p for p in text.replace("\r\n", "\n").split("\n\n")]
    body = "\n".join("<p>" + "<br>".join(html.escape(l) for l in p.split("\n")) + "</p>"
                     for p in paras if p.strip())
    out = Path(tmp) / (Path(src).stem + ".html")
    out.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    return out


def pandoc_convert(src, target, dest, ctx, title=None):
    exe = pandoc()
    if not exe:
        raise ConversionError("pandoc is not installed")
    src, dest = Path(src), Path(dest)
    ext = src.suffix.lower().lstrip(".")
    with temp_dir() as tmp:
        if ext == "txt":
            src, ext = _txt_as_html(src, tmp), "html"
        elif ext == "doc":
            src, ext = soffice_convert(src, tmp, "docx"), "docx"
        reader = READERS.get(ext)
        if not reader:
            raise ConversionError(f"Cannot read .{ext} documents")
        args = [exe, str(src), "-f", reader, "-t", WRITERS[target], "-o", str(dest)]
        stem = title or Path(dest).stem
        if target == "html":
            args += ["--standalone", "--embed-resources", "--metadata", f"pagetitle={stem}"]
        elif target == "epub":
            args += ["--metadata", f"title={stem}"]
        elif target == "md":
            args += ["--wrap=none", f"--extract-media={stem}_media"]
        elif target == "txt":
            args += ["--wrap=none"]
        run(args, cwd=str(dest.parent), timeout=600)
    media = dest.parent / f"{Path(dest).stem}_media"
    if media.exists() and not any(media.rglob("*")):
        shutil.rmtree(media)
    return dest


PDF_CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.45; }
h1 { font-size: 22pt; } h2 { font-size: 17pt; } h3 { font-size: 14pt; }
pre, code { font-family: monospace; font-size: 9.5pt; }
table { border-collapse: collapse; } td, th { border: 1px solid #999; padding: 3px 6px; }
img { max-width: 100%; }
"""


def _html_to_pdf(src, dest, ctx):
    """Lay out a document with PyMuPDF's HTML engine (no LibreOffice needed)."""
    import pymupdf
    src, dest = Path(src), Path(dest)
    with temp_dir() as tmp:
        html_path = Path(tmp) / "doc.html"
        ext = src.suffix.lower().lstrip(".")
        if ext == "txt":
            src, ext = _txt_as_html(src, tmp), "html"
        reader = READERS.get(ext)
        if not reader:
            raise ConversionError(f"Cannot read .{ext} documents")
        run([pandoc(), str(src), "-f", reader, "-t", "html5", "-o", str(html_path),
             "--extract-media=media"], cwd=tmp, timeout=600)
        story = pymupdf.Story(html=html_path.read_text(encoding="utf-8"), user_css=PDF_CSS,
                              archive=pymupdf.Archive(tmp))
        writer = pymupdf.DocumentWriter(str(dest))
        page = pymupdf.paper_rect("a4")
        frame = page + (56, 56, -56, -56)
        more = True
        while more:
            device = writer.begin_page(page)
            more, _ = story.place(frame)
            story.draw(device)
            writer.end_page()
        writer.close()
    return dest


def to_pdf(src, dest, ctx):
    src, dest = Path(src), Path(dest)
    ext = src.suffix.lower().lstrip(".")
    if ext in OFFICE_INPUTS and soffice_component("writer"):
        # LibreOffice keeps the original page layout, fonts and headers.
        with temp_dir() as tmp:
            shutil.move(str(soffice_convert(src, tmp, "pdf")), dest)
        return dest
    if ext == "doc":
        raise ConversionError("Legacy .doc files need LibreOffice Writer")
    return _html_to_pdf(src, dest, ctx)


def convert(src, target, dest, ctx):
    if target == "pdf":
        return to_pdf(src, dest, ctx)
    if Path(src).suffix.lower() in (".doc",) and target in ("docx", "odt"):
        with temp_dir() as tmp:
            shutil.move(str(soffice_convert(src, tmp, target)), dest)
        return Path(dest)
    return pandoc_convert(src, target, dest, ctx)
