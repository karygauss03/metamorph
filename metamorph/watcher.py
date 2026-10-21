"""Detect "file drag in progress + modifier held" anywhere on an X11 desktop.

Every XDND drag source takes ownership of the XdndSelection when the drag
starts (and GTK/Qt release it when it ends). XFixes tells us about ownership
changes without polling the selection; the pointer mask tells us whether the
button is still down and which modifiers are held - that works even while the
drag source holds an active pointer/keyboard grab.
"""

import os
import threading
import time

from gi.repository import GLib
from Xlib import X, XK, display
from Xlib.ext import xfixes

MASKS = {"Shift": X.ShiftMask, "Ctrl": X.ControlMask, "Alt": X.Mod1Mask, "Super": X.Mod4Mask}
BUTTONS = X.Button1Mask | X.Button2Mask | X.Button3Mask
POLL = 0.02
DEBUG = bool(os.environ.get("METAMORPH_DEBUG"))


def _log(*args):
    if DEBUG:
        print("watcher:", *args, flush=True)


class DragWatcher(threading.Thread):
    """Calls callbacks on the GTK main loop:

    on_mode(mode, x, y)  - a modifier mapped to mode ('convert'|'tool'|'action') was pressed mid-drag
    on_end()             - the drag finished (dropped anywhere) or was cancelled
    on_cancel()          - Escape pressed while the wheel was open
    """

    def __init__(self, get_keys, on_mode, on_end, on_cancel):
        super().__init__(daemon=True, name="drag-watcher")
        self.get_keys = get_keys
        self.on_mode, self.on_end, self.on_cancel = on_mode, on_end, on_cancel
        self.enabled = True
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            self._loop()
        except Exception as exc:  # pragma: no cover - logged for diagnostics
            print(f"metamorph: drag watcher stopped: {exc}", flush=True)

    def _loop(self):
        d = display.Display()
        root = d.screen().root
        if not d.has_extension("XFIXES"):
            raise RuntimeError("the X server has no XFIXES extension")
        d.xfixes_query_version()
        xdnd = d.intern_atom("XdndSelection")
        d.xfixes_select_selection_input(root, xdnd, xfixes.XFixesSetSelectionOwnerNotifyMask)
        d.flush()
        escape = d.keysym_to_keycode(XK.string_to_keysym("Escape"))

        dragging = False
        mode = None
        suppressed = False
        prev_mods = 0
        while not self._stop.is_set():
            while d.pending_events():
                ev = d.next_event()
                # python-xlib builds extension events from a copy of the class, so
                # isinstance() against xfixes.SetSelectionOwnerNotify is always False.
                if type(ev).__name__ == "SetSelectionOwnerNotify":
                    owner_id = getattr(ev.owner, "id", ev.owner)
                    _log("XdndSelection owner", hex(owner_id) if isinstance(owner_id, int) else owner_id)
                    if owner_id:
                        pointer = root.query_pointer()
                        if pointer.mask & BUTTONS:
                            dragging, mode, suppressed = True, None, False
                            prev_mods = pointer.mask
                    elif dragging:
                        dragging = False
                        GLib.idle_add(self.on_end)
            if dragging:
                pointer = root.query_pointer()
                if not pointer.mask & BUTTONS:
                    dragging = False
                    GLib.idle_add(self.on_end)
                    continue
                if self.enabled and not suppressed:
                    keys = self.get_keys()
                    pressed = pointer.mask & ~prev_mods
                    new_mode = None
                    # A newly pressed modifier wins; otherwise keep the open mode.
                    for name, m in keys.items():
                        if MASKS[m] & pressed:
                            new_mode = name
                    if new_mode is None and mode is None:
                        for name, m in keys.items():
                            if MASKS[m] & pointer.mask:
                                new_mode = name
                    if new_mode and new_mode != mode:
                        _log("mode", new_mode, "mask", hex(pointer.mask))
                        mode = new_mode
                        GLib.idle_add(self.on_mode, mode, pointer.root_x, pointer.root_y)
                    if mode:
                        keymap = d.query_keymap()
                        if keymap[escape // 8] & (1 << (escape % 8)):
                            suppressed = True
                            GLib.idle_add(self.on_cancel)
                prev_mods = pointer.mask
            time.sleep(POLL)
