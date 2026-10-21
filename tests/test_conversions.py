"""Run every conversion and tool against generated samples and validate the output."""

import zipfile
from pathlib import Path

import pytest

from metamorph import registry, settings
from metamorph.engines import media

PAIRS = []
for cat, (inputs, outputs) in registry.CATEGORIES.items():
    for ext in sorted(inputs):
        if ext in ("rar", "7z"):
            continue  # no free encoder to build a fixture
        targets = [t for t in outputs if t != ext]
        if cat == "image":
            targets += registry.EXTRA_TARGETS.get(ext, [])
        PAIRS += [(ext, t) for t in targets]

ZIP_BASED = {"docx", "odt", "pptx", "xlsx", "ods", "odp", "epub"}


def sample(fixtures, ext):
    return fixtures / ("notes.gz" if ext == "gz" else f"sample.{ext}")


def validate(path, target):
    path = Path(path)
    assert path.exists(), path
    files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    assert files, f"{path} is empty"
    for f in files:
        assert f.stat().st_size > 0, f
        if target in ("jpg", "png", "webp", "heic", "tiff", "avif", "bmp"):
            from PIL import Image
            import pillow_heif
            pillow_heif.register_heif_opener()
            with Image.open(f) as im:
                im.load()
                assert im.width > 10
        elif target in ("mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "wma"):
            assert media.probe(f).audio
        elif target in ("mp4", "mov", "mkv", "webm", "avi", "wmv", "gif"):
            assert media.probe(f).video
        elif target == "pdf":
            import pymupdf
            assert pymupdf.open(f).page_count >= 1
        elif target in ZIP_BASED:
            assert zipfile.is_zipfile(f)
        elif target == "zip":
            assert zipfile.ZipFile(f).namelist()
        elif target in ("tar", "tar.gz"):
            import tarfile
            assert tarfile.open(f).getnames()
        else:
            assert f.read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("ext,target", PAIRS, ids=[f"{e}->{t}" for e, t in PAIRS])
def test_conversion(fixtures, tmp_path, ext, target):
    src = sample(fixtures, ext)
    if not src.exists() or not registry.input_readable(src):
        pytest.skip(f".{ext} input needs a backend that is not installed")
    op_id = f"convert:{registry.category_of(src)}:{target}"
    if not registry.CONVERSIONS[op_id].available():
        pytest.skip(f"{op_id} needs: {', '.join(registry.CONVERSIONS[op_id].requires)}")
    ops = {op.target: op for op in registry.operations_for([src], "convert")}
    assert target in ops, f"{target} not offered for .{ext}: {list(ops)}"
    ctx = registry.Context(settings.DEFAULTS, out_dir=str(tmp_path))
    [out] = registry.execute(ops[target], [src], ctx)
    validate(out, target)


TOOL_CASES = [
    ("tool:image:compress", ["jpg"], {}), ("tool:image:compress", ["png"], {}),
    ("tool:image:resize", ["heic"], {"size": "50%"}), ("tool:image:resize", ["png"], {"size": "800 px wide"}),
    ("tool:image:crop", ["png"], {"shape": "Trim borders"}), ("tool:image:crop", ["jpg"], {"shape": "Square 1:1"}),
    ("tool:image:rotate", ["webp"], {}), ("tool:image:flip", ["gif"], {}),
    ("tool:image:grayscale", ["png"], {}), ("tool:image:strip", ["jpg"], {}),
    ("tool:video:compress", ["mov"], {}), ("tool:media:trim", ["mp4"], {"start": "0:00.5", "end": "1.5"}),
    ("tool:media:trim", ["mp3"], {"start": "0.5", "end": ""}), ("tool:media:split", ["mkv"], {"parts": "2"}),
    ("tool:video:mute", ["mp4"], {}), ("tool:video:audio", ["mov"], {}), ("tool:video:audio", ["avi"], {}),
    ("tool:video:rotate", ["webm"], {}), ("tool:video:resize", ["mp4"], {"height": "120"}),
    ("tool:media:speed", ["mp4"], {"factor": "2×"}), ("tool:media:speed", ["wav"], {"factor": "0.5×"}),
    ("tool:audio:compress", ["wav"], {}), ("tool:audio:normalize", ["flac"], {}),
    ("tool:pdf:compress", ["pdf"], {}), ("tool:pdf:split", ["pdf"], {}),
    ("tool:pdf:split", ["pdf"], {"ranges": "1; 2"}), ("tool:pdf:extract", ["pdf"], {"pages": "2"}),
    ("tool:pdf:remove", ["pdf"], {"pages": "1"}), ("tool:pdf:rotate", ["pdf"], {}),
    ("tool:pdf:images", ["pdf"], {}),
    ("tool:any:merge", ["png", "jpg", "webp"], {}), ("tool:any:merge", ["pdf", "pdf"], {}),
    ("tool:any:merge", ["mp4", "mov"], {}), ("tool:any:merge", ["mp3", "wav"], {}),
    ("tool:any:merge", ["md", "txt"], {}), ("tool:any:zip", ["png", "pdf"], {}),
    ("tool:archive:extract", ["zip"], {}), ("tool:archive:extract", ["tar.gz"], {}),
    ("tool:archive:extract", ["gz"], {}),
]


@pytest.mark.parametrize("op_id,exts,params", TOOL_CASES,
                         ids=[f"{o}-{'+'.join(e)}-{i}" for i, (o, e, _) in enumerate(TOOL_CASES)])
def test_tool(fixtures, tmp_path, op_id, exts, params):
    op = registry.ALL[op_id]
    paths = [sample(fixtures, e) for e in exts]
    assert op in registry.operations_for(paths, "tool"), f"{op_id} not offered for {exts}"
    full = {p.key: p.default for p in op.params}
    full.update(params)
    ctx = registry.Context(settings.DEFAULTS, full, out_dir=str(tmp_path))
    outputs = registry.execute(op, paths, ctx)
    assert outputs
    for out in outputs:
        out = Path(out)
        assert out.exists() and (out.is_dir() and any(out.iterdir()) or out.stat().st_size > 0)


def test_offering_rules(fixtures):
    png = sample(fixtures, "png")
    targets = [op.target for op in registry.operations_for([png], "convert")]
    assert "png" not in targets and "jpg" in targets
    mixed = registry.operations_for([png, sample(fixtures, "pdf")], "convert")
    assert {op.target for op in mixed} == {"jpg", "png"}  # shared by image and PDF
    assert not registry.operations_for([fixtures], "convert")
    tools = {op.id for op in registry.operations_for([png, sample(fixtures, "pdf")], "tool")}
    assert tools == {"tool:any:zip"}
    assert len(registry.operations_for([png], "action")) == 6


@pytest.mark.parametrize("text,value", [
    ("38,5", 38.5), ("1,234", 1234), ("1,234.5", 1234.5), ("1.5", 1.5), ("007", "007"),
    ("-3", -3), ("1.234.567", 1234567), ("1.234,5", 1234.5), ("30%", "30%"), (" 2 500 ", 2500),
])
def test_parse_number(text, value):
    from metamorph.util import parse_number
    assert parse_number(text) == value and type(parse_number(text)) is type(value)

