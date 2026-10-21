"""Image conversion and tools (Pillow, pillow-heif, librsvg for SVG input)."""

from pathlib import Path

from PIL import Image, ImageOps

from ..util import ConversionError, unique_path

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF = True
except Exception:  # pragma: no cover - optional dependency
    HEIF = False

SAVE_FORMATS = {
    "jpg": "JPEG", "png": "PNG", "webp": "WEBP", "heic": "HEIF", "tiff": "TIFF",
    "avif": "AVIF", "bmp": "BMP", "gif": "GIF", "pdf": "PDF",
}
OPAQUE = {"jpg", "bmp", "pdf"}


def _render_svg(src, min_size=1024):
    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    import cairo
    handle = Rsvg.Handle.new_from_file(str(src))
    ok, w, h = handle.get_intrinsic_size_in_pixels()
    if not ok or not w or not h:
        w, h = 1024, 1024
    scale = max(1.0, min_size / max(w, h))
    width, height = int(round(w * scale)), int(round(h * scale))
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    rect = Rsvg.Rectangle()
    rect.x, rect.y, rect.width, rect.height = 0, 0, width, height
    handle.render_document(cairo.Context(surface), rect)
    surface.flush()
    # Cairo stores premultiplied BGRA; Pillow's "RGBa" mode undoes the premultiply.
    img = Image.frombuffer("RGBa", (width, height), bytes(surface.get_data()),
                           "raw", "BGRa", surface.get_stride(), 1)
    return img.convert("RGBA")


def open_image(src):
    src = Path(src)
    if src.suffix.lower() in (".svg", ".svgz"):
        return _render_svg(src)
    try:
        img = Image.open(src)
        img.load()
    except Exception as exc:
        raise ConversionError(f"Cannot read image {src.name}: {exc}")
    return img


def frames(img):
    count = getattr(img, "n_frames", 1)
    for i in range(count):
        img.seek(i)
        yield img.copy()
    img.seek(0)


def flatten(img, background=(255, 255, 255)):
    """Drop alpha onto a solid background for formats that cannot store it."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        base = Image.new("RGB", img.size, background)
        base.paste(img, mask=img.getchannel("A"))
        return base
    return img.convert("RGB") if img.mode != "RGB" else img


def normalise_mode(img, fmt):
    if fmt in OPAQUE:
        return flatten(img)
    if img.mode in ("RGBA", "RGB", "L", "LA") and fmt != "heic":
        return img
    if fmt == "heic":
        return img.convert("RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB")
    if img.mode == "P" and fmt in ("png", "gif", "tiff", "bmp"):
        return img
    return img.convert("RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB")


def save(img, dest, fmt, quality=90, exif=None, extra_frames=None):
    fmt = fmt.lower()
    kwargs = {}
    if fmt in ("jpg", "webp", "heic", "avif"):
        kwargs["quality"] = quality
    if fmt == "jpg":
        kwargs.update(optimize=True, progressive=True)
    if fmt == "png":
        kwargs["optimize"] = True
    if fmt == "tiff":
        kwargs["compression"] = "tiff_lzw"
    if fmt == "pdf":
        kwargs["resolution"] = 150.0
    if exif and fmt in ("jpg", "webp", "png", "tiff", "heic", "avif"):
        kwargs["exif"] = exif
    img = normalise_mode(img, fmt)
    if extra_frames:
        kwargs.update(save_all=True, append_images=[normalise_mode(f, fmt) for f in extra_frames])
    if fmt == "heic" and not HEIF:
        raise ConversionError("HEIC output needs pillow-heif")
    try:
        img.save(dest, SAVE_FORMATS[fmt], **kwargs)
    except Exception as exc:
        Path(dest).unlink(missing_ok=True)
        raise ConversionError(f"Could not write {fmt.upper()}: {exc}")
    return Path(dest)


def _exif_bytes(img):
    try:
        exif = img.getexif()
        if exif:
            exif[0x0112] = 1  # pixels are transposed below, so reset orientation
            return exif.tobytes()
    except Exception:
        pass
    return None


def convert(src, target, dest, ctx):
    img = open_image(src)
    exif = _exif_bytes(img)
    pages = list(frames(img)) if target in ("pdf", "tiff") else [img]
    pages = [ImageOps.exif_transpose(p) for p in pages]
    quality = ctx.settings.get("image_quality", 90)
    return save(pages[0], dest, target, quality, exif, pages[1:] or None)


# ---------------------------------------------------------------- tools

def _rewrite(src, ctx, transform, suffix):
    img = open_image(src)
    fmt = Path(src).suffix.lower().lstrip(".")
    fmt = {"jpeg": "jpg", "tif": "tiff", "heif": "heic", "svg": "png"}.get(fmt, fmt)
    if fmt not in SAVE_FORMATS:
        fmt = "png"
    animated = getattr(img, "n_frames", 1) > 1 and fmt in ("gif", "webp")
    dest = unique_path(Path(ctx.out_dir or Path(src).parent) / f"{Path(src).stem}{suffix}.{fmt}")
    if animated:
        out = [transform(f) for f in frames(img)]
        out[0].save(dest, SAVE_FORMATS[fmt], save_all=True, append_images=out[1:],
                    duration=img.info.get("duration", 100), loop=img.info.get("loop", 0))
        return dest
    result = transform(ImageOps.exif_transpose(img))
    return save(result, dest, fmt, ctx.params.get("quality", ctx.settings.get("image_quality", 90)))


def compress(src, ctx):
    src = Path(src)
    quality = int(ctx.params.get("quality", 70))
    img = ImageOps.exif_transpose(open_image(src))
    fmt = src.suffix.lower().lstrip(".")
    if fmt in ("png", "bmp", "tiff", "tif", "gif", "svg"):
        # Lossless formats: quantise PNGs, otherwise re-encode as optimised PNG.
        dest = unique_path(Path(ctx.out_dir or src.parent) / f"{src.stem} (compressed).png")
        if img.mode in ("RGBA", "LA"):
            img = img.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE)
        else:
            img = img.convert("RGB").quantize(256, method=Image.Quantize.MEDIANCUT)
        img.save(dest, "PNG", optimize=True)
        return dest
    fmt = {"jpeg": "jpg", "heif": "heic"}.get(fmt, fmt)
    dest = unique_path(Path(ctx.out_dir or src.parent) / f"{src.stem} (compressed).{fmt}")
    return save(img, dest, fmt, quality)


def resize(src, ctx):
    percent = ctx.params.get("percent")
    width = int(ctx.params.get("width") or 0)

    def transform(img):
        if width:
            w = width
            h = max(1, round(img.height * width / img.width))
        else:
            p = float(percent or 50) / 100
            w, h = max(1, round(img.width * p)), max(1, round(img.height * p))
        return img.resize((w, h), Image.Resampling.LANCZOS)
    return _rewrite(src, ctx, transform, " (resized)")


CROP_RATIOS = {"Square 1:1": (1, 1), "Landscape 16:9": (16, 9), "Landscape 4:3": (4, 3),
               "Portrait 9:16": (9, 16), "Portrait 4:5": (4, 5)}


def crop(src, ctx):
    mode = ctx.params.get("shape", "Trim borders")

    def transform(img):
        if mode == "Trim borders":
            rgb = flatten(img)
            bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
            from PIL import ImageChops
            diff = ImageChops.difference(rgb, bg).convert("L").point(lambda v: 255 if v > 12 else 0)
            box = diff.getbbox()
            return img.crop(box) if box else img
        rw, rh = CROP_RATIOS[mode]
        target = rw / rh
        if img.width / img.height > target:
            w, h = round(img.height * target), img.height
        else:
            w, h = img.width, round(img.width / target)
        left, top = (img.width - w) // 2, (img.height - h) // 2
        return img.crop((left, top, left + w, top + h))
    return _rewrite(src, ctx, transform, " (cropped)")


def rotate(src, ctx):
    angle = {"90° clockwise": Image.Transpose.ROTATE_270, "90° counter-clockwise": Image.Transpose.ROTATE_90,
             "180°": Image.Transpose.ROTATE_180}[ctx.params.get("angle", "90° clockwise")]
    return _rewrite(src, ctx, lambda img: img.transpose(angle), " (rotated)")


def flip(src, ctx):
    return _rewrite(src, ctx, lambda img: img.transpose(Image.Transpose.FLIP_LEFT_RIGHT), " (flipped)")


def grayscale(src, ctx):
    def transform(img):
        if "A" in img.getbands():
            return ImageOps.grayscale(img).convert("LA") if img.mode == "LA" else Image.merge(
                "LA", (ImageOps.grayscale(img.convert("RGB")), img.getchannel("A")))
        return ImageOps.grayscale(img.convert("RGB"))
    return _rewrite(src, ctx, transform, " (grayscale)")


def strip_metadata(src, ctx):
    def transform(img):
        # Rebuild from raw pixels so no EXIF/XMP/ICC/text chunks survive.
        clean = Image.frombytes(img.mode, img.size, img.tobytes())
        if img.mode == "P":
            clean.putpalette(img.getpalette())
        return clean
    return _rewrite(src, ctx, transform, " (no metadata)")


def images_to_pdf(paths, ctx):
    pages = [flatten(ImageOps.exif_transpose(open_image(p))) for p in paths]
    first = Path(paths[0])
    dest = unique_path(Path(ctx.out_dir or first.parent) / f"{first.stem} (merged).pdf")
    pages[0].save(dest, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    return dest
