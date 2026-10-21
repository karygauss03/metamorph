"""SRT / WebVTT subtitles."""

import re
from pathlib import Path

from ..util import ConversionError

TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
ARROW = re.compile(r"^\s*(\S+)\s*-->\s*(\S+)(.*)$")


def _seconds(stamp):
    m = TIME.fullmatch(stamp.strip())
    if not m:
        raise ConversionError(f"Bad timestamp: {stamp}")
    h, mnt, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mnt) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def _stamp(sec, sep):
    ms = round(sec * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def parse(src):
    text = Path(src).read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", text):
        lines = block.strip("\n").split("\n")
        for i, line in enumerate(lines):
            m = ARROW.match(line)
            if m:
                body = [l for l in lines[i + 1:]]
                cues.append((_seconds(m[1]), _seconds(m[2]), "\n".join(body).strip()))
                break
    if not cues:
        raise ConversionError(f"No subtitle cues found in {Path(src).name}")
    return cues


def convert(src, target, dest, ctx):
    cues = parse(src)
    if target == "srt":
        out = "\n".join(f"{i}\n{_stamp(a, ',')} --> {_stamp(b, ',')}\n{re.sub(r'</?[cv][^>]*>', '', t)}\n"
                        for i, (a, b, t) in enumerate(cues, 1))
    elif target == "vtt":
        out = "WEBVTT\n\n" + "\n".join(f"{_stamp(a, '.')} --> {_stamp(b, '.')}\n{t}\n" for a, b, t in cues)
    else:
        plain = [re.sub(r"<[^>]+>|\{\\[^}]*\}", "", t) for _, _, t in cues]
        out = "\n".join(p for p in plain if p.strip()) + "\n"
    Path(dest).write_text(out, encoding="utf-8")
    return Path(dest)
