"""Audio and video conversion and tools (ffmpeg)."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..util import ConversionError, ffmpeg, parse_time, run, temp_dir, unique_path

AUDIO_ARGS = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    "opus": ["-c:a", "libopus", "-b:a", "128k"],
    "aiff": ["-c:a", "pcm_s16be"],
    "wma": ["-c:a", "wmav2", "-b:a", "192k"],
}

# CRF per quality preset for x264 / VP9.
QUALITY = {"High": (18, 28), "Balanced": (22, 33), "Small": (28, 40)}
EVEN = "scale=trunc(iw/2)*2:trunc(ih/2)*2"


@dataclass
class Info:
    duration: float = 0.0
    video: str = ""
    audio: str = ""
    width: int = 0
    height: int = 0


def probe(src):
    exe = _exe()
    proc = subprocess.run([exe, "-hide_banner", "-i", str(src)], capture_output=True,
                          text=True, errors="replace")
    if proc.returncode < 0:
        raise ConversionError(f"ffmpeg crashed while reading {Path(src).name}")
    out = proc.stderr
    info = Info()
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if m:
        info.duration = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    for line in out.splitlines():
        if "Stream #" not in line:
            continue
        m = re.search(r"(Video|Audio): (\w+)", line)
        if not m:
            continue
        if m[1] == "Video" and not info.video and "attached pic" not in line:
            info.video = m[2]
            dims = re.search(r", (\d{2,5})x(\d{2,5})", line)
            if dims:
                info.width, info.height = int(dims[1]), int(dims[2])
        elif m[1] == "Audio" and not info.audio:
            info.audio = m[2]
    if not info.video and not info.audio:
        raise ConversionError(f"{Path(src).name} has no audio or video stream")
    return info


def _exe():
    exe = ffmpeg()
    if not exe:
        raise ConversionError("ffmpeg is not installed")
    return exe


def _ffmpeg(args, ctx, duration=0.0):
    """Run ffmpeg, reporting progress from its -progress output."""
    def parse(line):
        if duration and line.startswith("out_time_us="):
            try:
                ctx.progress(min(1.0, int(line.split("=")[1]) / 1e6 / duration))
            except ValueError:
                pass
    run([_exe(), "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
         "-progress", "pipe:1", "-nostats", *args], progress_parser=parse)


def video_args(target, info, ctx, vf=None):
    crf_x264, crf_vp9 = QUALITY.get(ctx.settings.get("video_quality", "Balanced"), QUALITY["Balanced"])
    filters = ",".join(f for f in (vf, EVEN) if f)
    audio = ["-c:a", "aac", "-b:a", "160k"] if info.audio else ["-an"]
    if target in ("mp4", "mov", "mkv"):
        args = ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf_x264),
                "-pix_fmt", "yuv420p", "-vf", filters, *audio]
        if target == "mp4":
            args += ["-movflags", "+faststart"]
        return args
    if target == "webm":
        return ["-c:v", "libvpx-vp9", "-crf", str(crf_vp9), "-b:v", "0", "-row-mt", "1",
                "-deadline", "good", "-cpu-used", "4", "-pix_fmt", "yuv420p", "-vf", filters,
                *(["-c:a", "libopus", "-b:a", "128k"] if info.audio else ["-an"])]
    if target == "avi":
        return ["-c:v", "mpeg4", "-q:v", "3", "-vf", filters,
                *(["-c:a", "libmp3lame", "-q:a", "3"] if info.audio else ["-an"])]
    if target == "wmv":
        return ["-c:v", "wmv2", "-q:v", "3", "-vf", filters,
                *(["-c:a", "wmav2", "-b:a", "160k"] if info.audio else ["-an"])]
    raise ConversionError(f"Unsupported video target {target}")


def _can_remux(info, target):
    """Container swap without re-encoding when the codecs are already playable."""
    if target not in ("mp4", "mov", "mkv"):
        return False
    return info.video in ("h264", "hevc") and info.audio in ("", "aac", "mp3", "alac")


def convert(src, target, dest, ctx):
    src, dest = Path(src), Path(dest)
    info = probe(src)
    inp = ["-i", str(src)]
    if target in AUDIO_ARGS:
        if not info.audio:
            raise ConversionError(f"{src.name} has no audio track")
        _ffmpeg([*inp, "-vn", "-map_metadata", "0", *AUDIO_ARGS[target], str(dest)], ctx, info.duration)
        return dest
    if not info.video:
        raise ConversionError(f"{src.name} has no video track")
    if target == "gif":
        fps = ctx.settings.get("gif_fps", 12)
        width = ctx.settings.get("gif_width", 640)
        graph = (f"fps={fps},scale='min({width},iw)':-2:flags=lanczos,split[a][b];"
                 "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
        _ffmpeg([*inp, "-filter_complex", graph, "-loop", "0", str(dest)], ctx, info.duration)
        return dest
    if _can_remux(info, target):
        try:
            _ffmpeg([*inp, "-map", "0:v:0", "-map", "0:a?", "-c", "copy",
                     *(["-movflags", "+faststart"] if target == "mp4" else []), str(dest)],
                    ctx, info.duration)
            return dest
        except ConversionError:
            dest.unlink(missing_ok=True)
    _ffmpeg([*inp, "-map", "0:v:0", "-map", "0:a:0?", *video_args(target, info, ctx), str(dest)],
            ctx, info.duration)
    return dest


# ---------------------------------------------------------------- tools

def _dest(src, ctx, suffix, ext=None):
    src = Path(src)
    return unique_path(Path(ctx.out_dir or src.parent) / f"{src.stem}{suffix}.{ext or src.suffix.lstrip('.')}")


def _reencode(src, ctx, suffix, vf=None, af=None, extra=(), ext=None):
    """Re-encode keeping the source container, applying optional filters."""
    src = Path(src)
    info = probe(src)
    dest = _dest(src, ctx, suffix, ext)
    target = (ext or src.suffix.lstrip(".")).lower()
    if info.video:
        if target not in ("mp4", "mov", "mkv", "webm", "avi", "wmv"):
            target = "mp4"
            dest = dest.with_suffix(".mp4")
        args = video_args(target, info, ctx, vf)
        if af and info.audio:
            args += ["-af", af]
    else:
        target = {"aif": "aiff", "oga": "ogg", "aac": "m4a"}.get(target, target)
        if target not in AUDIO_ARGS:
            target = "m4a"
            dest = dest.with_suffix(".m4a")
        args = [*AUDIO_ARGS[target], *(["-af", af] if af else [])]
    _ffmpeg(["-i", str(src), *extra, *args, str(dest)], ctx, info.duration)
    return dest


def compress(src, ctx):
    src = Path(src)
    info = probe(src)
    if not info.video:
        dest = _dest(src, ctx, " (compressed)", "mp3" if src.suffix.lower() != ".opus" else "opus")
        codec = ["-c:a", "libopus", "-b:a", "64k"] if dest.suffix == ".opus" else ["-c:a", "libmp3lame", "-b:a", "128k"]
        _ffmpeg(["-i", str(src), "-vn", *codec, str(dest)], ctx, info.duration)
        return dest
    dest = _dest(src, ctx, " (compressed)", "mp4")
    long_side = int(ctx.params.get("max_height", 1080))
    vf = f"scale='if(gt(ih,{long_side}),-2,iw)':'min(ih,{long_side})'"
    crf = {"Small": 32, "Balanced": 28, "High": 24}.get(ctx.params.get("level", "Balanced"), 28)
    _ffmpeg(["-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "slow",
             "-crf", str(crf), "-pix_fmt", "yuv420p", "-vf", f"{vf},{EVEN}",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dest)], ctx, info.duration)
    return dest


def trim(src, ctx):
    src = Path(src)
    info = probe(src)
    start = parse_time(ctx.params.get("start")) or 0.0
    end = parse_time(ctx.params.get("end")) or info.duration
    if end <= start:
        raise ConversionError("End time must be after start time")
    if info.duration and start >= info.duration:
        raise ConversionError(f"Start time is past the end ({info.duration:.1f}s)")
    length = end - start
    dest = _dest(src, ctx, " (trimmed)")
    exact = ctx.params.get("exact", True)
    if not exact:
        _ffmpeg(["-ss", f"{start}", "-i", str(src), "-t", f"{length}", "-c", "copy", str(dest)], ctx, length)
        return dest
    # Accurate cut: seek before input, then re-encode.
    target = src.suffix.lstrip(".").lower()
    if info.video:
        if target not in ("mp4", "mov", "mkv", "webm", "avi", "wmv"):
            target, dest = "mp4", dest.with_suffix(".mp4")
        args = video_args(target, info, ctx)
    else:
        target = {"aif": "aiff", "oga": "ogg", "aac": "m4a"}.get(target, target)
        if target not in AUDIO_ARGS:
            target, dest = "m4a", dest.with_suffix(".m4a")
        args = AUDIO_ARGS[target]
    _ffmpeg(["-ss", f"{start}", "-i", str(src), "-t", f"{length}", *args, str(dest)], ctx, length)
    return dest


def split(src, ctx):
    src = Path(src)
    info = probe(src)
    if not info.duration:
        raise ConversionError("Cannot determine the duration")
    parts = ctx.params.get("parts")
    seg = parse_time(ctx.params.get("segment")) if ctx.params.get("segment") else None
    if not seg:
        seg = info.duration / max(2, int(parts or 2))
    folder = unique_path(Path(ctx.out_dir or src.parent) / f"{src.stem} (parts)")
    folder.mkdir()
    ext = src.suffix.lstrip(".")
    _ffmpeg(["-i", str(src), "-map", "0", "-c", "copy", "-f", "segment", "-segment_time", f"{seg}",
             "-reset_timestamps", "1", str(folder / f"{src.stem} %02d.{ext}")], ctx, info.duration)
    return folder


def mute(src, ctx):
    src = Path(src)
    dest = _dest(src, ctx, " (muted)")
    _ffmpeg(["-i", str(src), "-map", "0:v", "-c", "copy", "-an", str(dest)], ctx, probe(src).duration)
    return dest


def extract_audio(src, ctx):
    src = Path(src)
    info = probe(src)
    if not info.audio:
        raise ConversionError(f"{src.name} has no audio track")
    copy_ext = {"aac": "m4a", "mp3": "mp3", "opus": "opus", "vorbis": "ogg", "flac": "flac"}.get(info.audio)
    if copy_ext:
        dest = _dest(src, ctx, "", copy_ext)
        _ffmpeg(["-i", str(src), "-vn", "-map", "0:a:0", "-c:a", "copy", str(dest)], ctx, info.duration)
    else:
        dest = _dest(src, ctx, "", "m4a")
        _ffmpeg(["-i", str(src), "-vn", "-map", "0:a:0", *AUDIO_ARGS["m4a"], str(dest)], ctx, info.duration)
    return dest


def rotate(src, ctx):
    vf = {"90° clockwise": "transpose=1", "90° counter-clockwise": "transpose=2",
          "180°": "transpose=1,transpose=1"}[ctx.params.get("angle", "90° clockwise")]
    return _reencode(src, ctx, " (rotated)", vf=vf)


def resize(src, ctx):
    height = int(ctx.params.get("height", 720))
    return _reencode(src, ctx, f" ({height}p)", vf=f"scale=-2:'min({height},ih)'")


def speed(src, ctx):
    factor = float(str(ctx.params.get("factor", "2×")).rstrip("×x"))
    if not 0.25 <= factor <= 4:
        raise ConversionError("Speed must be between 0.25× and 4×")
    atempo, remaining = [], factor
    while remaining > 2.0:
        atempo.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        atempo.append("atempo=0.5")
        remaining /= 0.5
    atempo.append(f"atempo={remaining:.4f}")
    info = probe(src)
    vf = f"setpts=PTS/{factor}" if info.video else None
    return _reencode(src, ctx, f" ({factor:g}x)", vf=vf, af=",".join(atempo))


def normalize(src, ctx):
    return _reencode(src, ctx, " (normalized)", af="loudnorm=I=-16:TP=-1.5:LRA=11")


def merge(paths, ctx):
    """Concatenate videos or audio files in the given order (re-encoded)."""
    infos = [probe(p) for p in paths]
    first = Path(paths[0])
    is_video = all(i.video for i in infos)
    if not is_video and not all(i.audio for i in infos):
        raise ConversionError("Merge needs all videos or all audio files")
    args = []
    for p in paths:
        args += ["-i", str(p)]
    n = len(paths)
    total = sum(i.duration for i in infos)
    if is_video:
        w = max(i.width for i in infos) // 2 * 2 or 1280
        h = max(i.height for i in infos) // 2 * 2 or 720
        has_audio = all(i.audio for i in infos)
        chains, inputs = [], ""
        for k in range(n):
            chains.append(f"[{k}:v:0]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v{k}]")
            inputs += f"[v{k}]" + (f"[{k}:a:0]" if has_audio else "")
        graph = ";".join(chains) + f";{inputs}concat=n={n}:v=1:a={1 if has_audio else 0}[v]" + ("[a]" if has_audio else "")
        dest = unique_path(Path(ctx.out_dir or first.parent) / f"{first.stem} (merged).mp4")
        _ffmpeg([*args, "-filter_complex", graph, "-map", "[v]", *(["-map", "[a]"] if has_audio else []),
                 "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "160k",
                 "-movflags", "+faststart", str(dest)], ctx, total)
        return dest
    graph = "".join(f"[{k}:a:0]" for k in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    ext = first.suffix.lstrip(".").lower()
    ext = ext if ext in AUDIO_ARGS else "m4a"
    dest = unique_path(Path(ctx.out_dir or first.parent) / f"{first.stem} (merged).{ext}")
    _ffmpeg([*args, "-filter_complex", graph, "-map", "[a]", *AUDIO_ARGS[ext], str(dest)], ctx, total)
    return dest


def gif_to_video(src, target, dest, ctx):
    info = probe(src)
    args = video_args(target, Info(info.duration, info.video, "", info.width, info.height), ctx)
    _ffmpeg(["-i", str(src), *args, str(dest)], ctx, info.duration)
    return Path(dest)
