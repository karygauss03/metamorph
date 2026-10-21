"""Every conversion, tool and action, and which of them apply to a selection."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import util
from .util import ConversionError, extension

# ------------------------------------------------------------------ formats

# Canonical extension for aliases, so JPEG files don't get offered "JPG".
ALIASES = {"jpeg": "jpg", "tif": "tiff", "heif": "heic", "aif": "aiff", "oga": "ogg",
           "htm": "html", "markdown": "md", "tgz": "tar.gz", "svgz": "svg", "m4v": "mp4"}

CATEGORIES = {
    "image": ({"jpg", "png", "webp", "heic", "tiff", "avif", "bmp", "gif", "svg"},
              ["jpg", "png", "webp", "heic", "tiff", "avif", "bmp", "pdf"]),
    "audio": ({"mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "wma", "aac"},
              ["mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "wma"]),
    "video": ({"mp4", "mov", "mkv", "webm", "avi", "wmv", "mpg", "mpeg", "3gp", "flv"},
              ["mp4", "mov", "mkv", "webm", "avi", "wmv", "gif", "mp3"]),
    "pdf": ({"pdf"}, ["docx", "odt", "pptx", "xlsx", "jpg", "png", "epub", "txt", "md"]),
    "document": ({"docx", "doc", "odt", "md", "txt", "rtf", "html"},
                 ["docx", "odt", "md", "txt", "epub", "html", "pdf"]),
    "ebook": ({"epub"}, ["pdf", "docx", "odt", "md", "txt", "html"]),
    "slides": ({"pptx", "ppt", "odp"}, ["pdf", "jpg", "png", "pptx", "odp"]),
    "sheet": ({"xlsx", "xls", "ods", "csv", "tsv"}, ["xlsx", "ods", "csv", "tsv", "pdf"]),
    "subtitle": ({"srt", "vtt"}, ["srt", "vtt", "txt"]),
    "archive": ({"zip", "tar", "tar.gz", "gz", "rar", "7z"}, ["zip", "tar", "tar.gz"]),
}
# Inputs that can only be read, never offered as a target from their own category.
EXTRA_TARGETS = {"gif": ["mp4", "webm"]}

LABELS = {"tar.gz": "TAR.GZ", "webp": "WebP", "webm": "WebM", "md": "Markdown", "txt": "Text", "epub": "EPUB"}

CATEGORY_LABELS = {
    "image": "Image", "audio": "Audio", "video": "Video", "pdf": "PDF", "document": "Document",
    "ebook": "Ebook", "slides": "Slides", "sheet": "Spreadsheet", "subtitle": "Subtitles",
    "archive": "Archive", "folder": "Folder", "file": "File",
}


def canonical(path):
    ext = extension(path)
    return ALIASES.get(ext, ext)


def category_of(path):
    path = Path(path)
    if path.is_dir():
        return "folder"
    ext = canonical(path)
    for name, (inputs, _) in CATEGORIES.items():
        if ext in inputs:
            return name
    return "file"


def label(ext):
    return LABELS.get(ext, ext.upper())


# ------------------------------------------------------------------ operations

@dataclass
class Param:
    key: str
    label: str
    kind: str = "text"            # text | time | int | choice | bool
    default: object = ""
    options: tuple = ()
    hint: str = ""


@dataclass
class Operation:
    id: str
    label: str
    kind: str                      # convert | tool | action
    categories: frozenset = frozenset()
    run: Optional[Callable] = None  # per-file: run(path, ctx) / multi: run(paths, ctx)
    multi: bool = False
    min_files: int = 1
    params: list = field(default_factory=list)
    requires: tuple = ()
    description: str = ""
    target: str = ""
    editor: str = ""               # interactive window used instead of the params dialog

    def available(self):
        return all(_REQUIREMENTS[r]() for r in self.requires)


_REQUIREMENTS = {
    "ffmpeg": lambda: bool(util.ffmpeg()),
    "pandoc": lambda: bool(util.pandoc()),
    "soffice": lambda: bool(util.soffice()),
    "fitz": lambda: util.has_module("pymupdf"),
    "pdf2docx": lambda: util.has_module("pdf2docx"),
    "pptx": lambda: util.has_module("pptx"),
    "heif": lambda: util.has_module("pillow_heif"),
    "unrar": lambda: bool(util.unrar()),
    "writer": lambda: util.soffice_component("writer"),
    "calc": lambda: util.soffice_component("calc"),
    "impress": lambda: util.soffice_component("impress"),
}

# Inputs that only LibreOffice can read.
INPUT_REQUIRES = {"doc": ("writer",), "xls": ("calc",), "ods": ("calc",), "rar": ("unrar",), "7z": ("unrar",)}


def input_readable(path):
    return all(_REQUIREMENTS[r]() for r in INPUT_REQUIRES.get(canonical(path), ()))


@dataclass
class Context:
    settings: dict
    params: dict = field(default_factory=dict)
    out_dir: Optional[str] = None
    progress: Callable = lambda fraction: None
    cancelled: Callable = lambda: False


def _conversion_requires(category, target, src_ext=None):
    req = {
        "audio": ("ffmpeg",), "video": ("ffmpeg",),
        "pdf": ("fitz",), "document": ("pandoc",), "ebook": ("pandoc",),
        "slides": ("impress",), "subtitle": (), "archive": (), "image": (), "sheet": (),
    }[category]
    if category == "pdf" and target in ("docx", "odt", "epub"):
        req += ("pdf2docx", "pandoc") if target != "docx" else ("pdf2docx",)
    if category == "pdf" and target == "pptx":
        req += ("pptx",)
    if category in ("document", "ebook") and target == "pdf":
        req += ("fitz",)
    if category == "sheet" and target in ("pdf", "ods"):
        req += ("calc",)
    if category == "image" and target == "heic":
        req += ("heif",)
    if target in ("mp4", "webm") and category == "image":
        req += ("ffmpeg",)
    return req


def _convert_fn(category, target):
    def run(path, ctx):
        from .engines import archives, documents, images, media, office, pdf, subtitles
        src = Path(path)
        dest = util.output_for(src, target, ctx.out_dir)
        if category == "image":
            if target in ("mp4", "webm"):
                return media.gif_to_video(src, target, dest, ctx)
            return images.convert(src, target, dest, ctx)
        engine = {
            "audio": media.convert, "video": media.convert, "pdf": pdf.convert,
            "document": documents.convert, "ebook": documents.convert,
            "slides": office.slides_convert, "sheet": office.sheets_convert,
            "subtitle": subtitles.convert, "archive": archives.convert,
        }[category]
        try:
            return engine(src, target, dest, ctx)
        except BaseException:
            if dest.is_file():
                dest.unlink()
            raise
    return run


def _conversions():
    ops = {}
    for category, (inputs, outputs) in CATEGORIES.items():
        for target in outputs:
            op_id = f"convert:{category}:{target}"
            ops[op_id] = Operation(
                op_id, label(target), "convert", frozenset({category}),
                _convert_fn(category, target), requires=_conversion_requires(category, target),
                target=target, description=f"Convert to {label(target)}")
    for src_ext, targets in EXTRA_TARGETS.items():
        for target in targets:
            op_id = f"convert:image:{target}"
            ops[op_id] = Operation(op_id, label(target), "convert", frozenset({"image"}),
                                   _convert_fn("image", target), requires=("ffmpeg",),
                                   target=target, description=f"Convert to {label(target)}")
    return ops


ANGLE = Param("angle", "Rotation", "choice", "90° clockwise", ("90° clockwise", "90° counter-clockwise", "180°"))
LEVEL = Param("level", "Quality", "choice", "Balanced", ("High", "Balanced", "Small"))


def _lazy(module, name):
    def call(*args):
        mod = __import__(f"metamorph.engines.{module}", fromlist=[name])
        return getattr(mod, name)(*args)
    return call


def _image_resize(path, ctx):
    size = ctx.params.get("size", "50%")
    if size.endswith("%"):
        ctx.params = {**ctx.params, "percent": float(size[:-1]), "width": 0}
    else:
        ctx.params = {**ctx.params, "width": int(size.split()[0])}
    return _lazy("images", "resize")(path, ctx)


def _merge(paths, ctx):
    cats = {category_of(p) for p in paths}
    if len(cats) != 1:
        raise ConversionError("Merge needs files of the same kind")
    cat = cats.pop()
    if cat == "image":
        return _lazy("images", "images_to_pdf")(paths, ctx)
    if cat == "pdf":
        return _lazy("pdf", "merge")(paths, ctx)
    if cat in ("audio", "video"):
        return _lazy("media", "merge")(paths, ctx)
    if cat in ("document", "subtitle") and all(canonical(p) in ("txt", "md", "srt", "vtt") for p in paths):
        first = Path(paths[0])
        dest = util.unique_path(Path(ctx.out_dir or first.parent) / f"{first.stem} (merged){first.suffix}")
        dest.write_text("\n\n".join(Path(p).read_text(encoding="utf-8", errors="replace").rstrip()
                                    for p in paths) + "\n", encoding="utf-8")
        return dest
    raise ConversionError(f"Merging {CATEGORY_LABELS[cat].lower()} files is not supported")


TOOLS = [
    # Images
    Operation("tool:image:compress", "Compress", "tool", frozenset({"image"}), _lazy("images", "compress"),
              params=[Param("quality", "Quality", "int", 70, hint="1-100, lower is smaller")],
              description="Smaller file, same format"),
    Operation("tool:image:resize", "Resize", "tool", frozenset({"image"}), _image_resize,
              params=[Param("size", "Size", "choice", "50%", ("25%", "50%", "75%", "3840 px wide",
                                                               "1920 px wide", "1280 px wide", "800 px wide"))],
              description="Scale by percent or width"),
    Operation("tool:image:crop", "Crop", "tool", frozenset({"image"}), _lazy("images", "crop"),
              params=[Param("shape", "Crop to", "choice", "Trim borders",
                            ("Trim borders", "Square 1:1", "Landscape 16:9", "Landscape 4:3",
                             "Portrait 9:16", "Portrait 4:5")),
                      Param("rect", "Rectangle", "text", "", hint="x0,y0,x1,y1 as fractions, e.g. 0.1,0,0.9,1")],
              editor="crop", description="Draw the area to keep"),
    Operation("tool:image:rotate", "Rotate", "tool", frozenset({"image"}), _lazy("images", "rotate"), params=[ANGLE],
              description="Turn 90° or 180°"),
    Operation("tool:image:flip", "Flip", "tool", frozenset({"image"}), _lazy("images", "flip"),
              description="Mirror horizontally"),
    Operation("tool:image:grayscale", "Grayscale", "tool", frozenset({"image"}), _lazy("images", "grayscale"),
              description="Black and white copy"),
    Operation("tool:image:strip", "Strip Info", "tool", frozenset({"image"}), _lazy("images", "strip_metadata"),
              description="Remove EXIF, GPS and other metadata"),
    # Video
    Operation("tool:video:compress", "Compress", "tool", frozenset({"video"}), _lazy("media", "compress"),
              requires=("ffmpeg",), params=[LEVEL, Param("max_height", "Max height", "choice", "1080",
                                                        ("2160", "1080", "720", "480"))],
              description="Smaller H.264 MP4"),
    Operation("tool:media:trim", "Trim", "tool", frozenset({"video", "audio"}), _lazy("media", "trim"),
              requires=("ffmpeg",), params=[Param("start", "Start", "time", "0:00", hint="mm:ss or hh:mm:ss"),
                                            Param("end", "End", "time", "", hint="empty = to the end")],
              description="Cut to a time range"),
    Operation("tool:media:split", "Split", "tool", frozenset({"video", "audio"}), _lazy("media", "split"),
              requires=("ffmpeg",), params=[Param("parts", "Equal parts", "int", 2),
                                            Param("segment", "Or every", "time", "", hint="e.g. 5:00, overrides parts")],
              description="Split at keyframes without re-encoding"),
    Operation("tool:video:mute", "Mute", "tool", frozenset({"video"}), _lazy("media", "mute"), requires=("ffmpeg",),
              description="Remove the audio track"),
    Operation("tool:video:audio", "Audio", "tool", frozenset({"video"}), _lazy("media", "extract_audio"),
              requires=("ffmpeg",), description="Extract the audio track without re-encoding"),
    Operation("tool:video:rotate", "Rotate", "tool", frozenset({"video"}), _lazy("media", "rotate"),
              requires=("ffmpeg",), params=[ANGLE],
              description="Turn 90° or 180°"),
    Operation("tool:video:resize", "Resize", "tool", frozenset({"video"}), _lazy("media", "resize"),
              requires=("ffmpeg",), params=[Param("height", "Height", "choice", "720", ("1080", "720", "480", "360"))],
              description="Scale down to 1080p, 720p..."),
    Operation("tool:media:speed", "Speed", "tool", frozenset({"video", "audio"}), _lazy("media", "speed"),
              requires=("ffmpeg",), params=[Param("factor", "Speed", "choice", "2×", ("0.5×", "0.75×", "1.25×", "1.5×", "2×", "3×"))],
              description="Speed up or slow down"),
    # Audio
    Operation("tool:audio:compress", "Compress", "tool", frozenset({"audio"}), _lazy("media", "compress"),
              requires=("ffmpeg",), description="128 kbps MP3"),
    Operation("tool:audio:normalize", "Normalize", "tool", frozenset({"audio", "video"}), _lazy("media", "normalize"),
              requires=("ffmpeg",), description="Even out loudness (EBU R128)"),
    # PDF
    Operation("tool:pdf:compress", "Compress", "tool", frozenset({"pdf"}), _lazy("pdf", "compress"),
              requires=("fitz",), params=[LEVEL],
              description="Shrink images and streams"),
    Operation("tool:pdf:split", "Split", "tool", frozenset({"pdf"}), _lazy("pdf", "split"), requires=("fitz",),
              params=[Param("ranges", "Ranges", "text", "", hint="empty = every page; e.g. 1-3; 4-6")],
              description="One PDF per page or range"),
    Operation("tool:pdf:extract", "Pages", "tool", frozenset({"pdf"}), _lazy("pdf", "extract_pages"),
              requires=("fitz",), params=[Param("pages", "Keep pages", "text", "1", hint="e.g. 1-3, 5")],
              description="Extract pages into a new PDF"),
    Operation("tool:pdf:remove", "Remove", "tool", frozenset({"pdf"}), _lazy("pdf", "remove_pages"),
              requires=("fitz",), params=[Param("pages", "Remove pages", "text", "1", hint="e.g. 2, 4-5")],
              description="Delete pages"),
    Operation("tool:pdf:rotate", "Rotate", "tool", frozenset({"pdf"}), _lazy("pdf", "rotate"), requires=("fitz",),
              params=[ANGLE],
              description="Rotate every page"),
    Operation("tool:pdf:images", "Images", "tool", frozenset({"pdf"}), _lazy("pdf", "extract_images"),
              requires=("fitz",), description="Save every embedded image"),
    # Any selection
    Operation("tool:any:merge", "Merge", "tool", frozenset({"image", "pdf", "audio", "video", "document", "subtitle"}),
              _merge, multi=True, min_files=2, description="Combine into one file"),
    Operation("tool:any:zip", "Zip", "tool", frozenset(), _lazy("archives", "zip_files"), multi=True,
              description="Compress into a ZIP archive"),
    Operation("tool:archive:extract", "Extract", "tool", frozenset({"archive"}), _lazy("archives", "unpack"),
              description="Unpack next to the archive"),
]

ACTIONS = [
    Operation("action:share", "Share", "action", description="Send to a phone or another device"),
    Operation("action:float", "Float", "action", description="Keep the file in a floating shelf"),
    Operation("action:copy", "Copy", "action", description="Copy the file to the clipboard"),
    Operation("action:move", "Move", "action", description="Move to another folder"),
    Operation("action:path", "Copy Path", "action", description="Copy the full path"),
    Operation("action:terminal", "Terminal", "action", description="Open a terminal here"),
]

CONVERSIONS = _conversions()
ALL = {**CONVERSIONS, **{op.id: op for op in TOOLS}, **{op.id: op for op in ACTIONS}}


def operations_for(paths, kind):
    """Operations of one kind that apply to every path in the selection."""
    paths = [Path(p) for p in paths]
    if not paths:
        return []
    if kind == "action":
        return list(ACTIONS)
    cats = [category_of(p) for p in paths]
    if kind == "convert":
        if "folder" in cats or "file" in cats or not all(input_readable(p) for p in paths):
            return []
        exts = {canonical(p) for p in paths}
        common = None
        for cat in set(cats):
            targets = [CONVERSIONS[f"convert:{cat}:{t}"] for t in CATEGORIES[cat][1]]
            targets += [CONVERSIONS[f"convert:{cat}:{t}"] for e in exts for t in EXTRA_TARGETS.get(e, [])
                        if cat == "image"]
            by_target = {op.target: op for op in targets}
            common = by_target if common is None else {t: op for t, op in common.items() if t in by_target}
        result = [op for op in (common or {}).values() if op.available()]
        if len(exts) == 1:
            # Don't offer converting a file to its own format.
            result = [op for op in result if op.target != next(iter(exts))]
        if len(set(cats)) > 1:
            # Mixed kinds: each file uses its own category's engine for the target.
            result = [MixedConversion(op.target) for op in result]
        return result
    ops = []
    readable = all(input_readable(p) for p in paths)
    for op in TOOLS:
        if not op.available() or (not readable and op.id != "tool:any:zip"):
            continue
        if op.multi:
            if len(paths) < op.min_files:
                continue
            if op.categories and not (len(set(cats)) == 1 and cats[0] in op.categories):
                continue
            ops.append(op)
        elif all(c in op.categories for c in cats):
            ops.append(op)
    return ops


def MixedConversion(target):
    def run(path, ctx):
        if canonical(path) == target:
            return path  # already in the target format
        return CONVERSIONS[f"convert:{category_of(path)}:{target}"].run(path, ctx)
    return Operation(f"convert:mixed:{target}", label(target), "convert", run=run, target=target,
                     description=f"Convert to {label(target)}")


def conversion_count():
    """Number of distinct input-format -> output-format pairs that are available."""
    total = 0
    for cat, (inputs, outputs) in CATEGORIES.items():
        for ext in inputs:
            if not all(_REQUIREMENTS[r]() for r in INPUT_REQUIRES.get(ext, ())):
                continue
            targets = [t for t in outputs if t != ext] + (EXTRA_TARGETS.get(ext, []) if cat == "image" else [])
            total += sum(1 for t in targets if CONVERSIONS[f"convert:{cat}:{t}"].available())
    return total


def execute(op, paths, ctx):
    """Run an operation over a selection; returns the produced paths."""
    if op.multi:
        return [op.run([str(p) for p in paths], ctx)]
    outputs = []
    total = len(paths)
    for i, path in enumerate(paths):
        if ctx.cancelled():
            break
        sub = Context(ctx.settings, ctx.params, ctx.out_dir,
                      lambda f, i=i: ctx.progress((i + max(0.0, min(1.0, f))) / total), ctx.cancelled)
        outputs.append(op.run(str(path), sub))
        ctx.progress((i + 1) / total)
    return outputs
