"""User settings stored as JSON in ~/.config/metamorph/settings.json."""

import json

from .util import CONFIG_DIR

PATH = CONFIG_DIR / "settings.json"

MODIFIERS = ("Shift", "Ctrl", "Alt", "Super")

DEFAULTS = {
    "enabled": True,
    # Modifier held during a drag -> wheel. Super is avoided by default because
    # GNOME opens the Activities overview when it is released on its own.
    "key_convert": "Shift",
    "key_tools": "Alt",
    "key_actions": "Ctrl",
    "output": "beside",            # beside | folder
    "output_folder": "",
    "image_quality": 90,
    "video_quality": "Balanced",   # High | Balanced | Small
    "gif_fps": 12,
    "gif_width": 640,
    "notify": True,
    "reveal_after": False,
    "recent_moves": [],
}


def load():
    data = dict(DEFAULTS)
    try:
        data.update(json.loads(PATH.read_text()))
    except (FileNotFoundError, ValueError):
        pass
    return data


def save(data):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({k: data[k] for k in DEFAULTS if k in data}, indent=2))
    tmp.replace(PATH)
