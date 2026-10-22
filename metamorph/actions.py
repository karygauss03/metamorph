"""File actions: Share, Float, Copy, Move, Copy Path, Terminal."""

import os
import shutil
import subprocess
import threading
from pathlib import Path

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

from .util import unique_path


class ActionResult:
    def __init__(self, message, error=False, outputs=()):
        self.message, self.error, self.outputs = message, error, list(outputs)


# ------------------------------------------------------------------ clipboard

class FileClipboard(threading.Thread):
    """Own the CLIPBOARD selection and serve files the way file managers expect.

    GTK3's Python bindings cannot offer custom targets, so this speaks the
    selection protocol directly: Nautilus pastes x-special/gnome-copied-files,
    browsers and chat apps read text/uri-list, editors get the plain paths.
    """

    _current = None

    def __init__(self, paths):
        super().__init__(daemon=True, name="clipboard")
        self.paths = [Path(p).resolve() for p in paths]
        self.ready = threading.Event()
        self.ok = False

    @classmethod
    def copy(cls, paths):
        owner = cls(paths)
        owner.start()
        owner.ready.wait(2)
        cls._current = owner
        return owner.ok

    def run(self):
        from Xlib import X, Xatom, display
        from Xlib.protocol import event

        d = display.Display()
        win = d.screen().root.create_window(0, 0, 1, 1, 0, X.CopyFromParent)
        atom = d.intern_atom
        clipboard = atom("CLIPBOARD")
        uris = "\r\n".join(p.as_uri() for p in self.paths).encode()
        text = "\n".join(str(p) for p in self.paths).encode()
        data = {
            atom("x-special/gnome-copied-files"): b"copy\n" + "\n".join(p.as_uri() for p in self.paths).encode(),
            atom("text/uri-list"): uris + b"\r\n",
            atom("UTF8_STRING"): text,
            atom("text/plain;charset=utf-8"): text,
            atom("text/plain"): text,
            Xatom.STRING: text,
        }
        targets, timestamp = atom("TARGETS"), atom("TIMESTAMP")
        win.set_selection_owner(clipboard, X.CurrentTime)
        d.flush()
        self.ok = d.get_selection_owner(clipboard) == win
        self.ready.set()
        if not self.ok:
            return
        while True:
            ev = d.next_event()
            if ev.type == X.SelectionClear:
                break
            if ev.type != X.SelectionRequest:
                continue
            prop = ev.property or ev.target
            if ev.target == targets:
                ev.requestor.change_property(prop, Xatom.ATOM, 32, [targets, timestamp, *data])
            elif ev.target == timestamp:
                ev.requestor.change_property(prop, Xatom.INTEGER, 32, [X.CurrentTime])
            elif ev.target in data:
                ev.requestor.change_property(prop, ev.target, 8, data[ev.target])
            else:
                prop = X.NONE
            ev.requestor.send_event(event.SelectionNotify(
                time=ev.time, requestor=ev.requestor, selection=ev.selection,
                target=ev.target, property=prop))
            d.flush()
        win.destroy()
        d.close()


def copy_files(paths):
    if FileClipboard.copy(paths):
        n = len(paths)
        return ActionResult(f"Copied {Path(paths[0]).name if n == 1 else f'{n} items'} - paste in any folder")
    return ActionResult("Could not take ownership of the clipboard", error=True)


def copy_path(paths):
    text = "\n".join(str(Path(p)) for p in paths)
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(text, -1)
    clipboard.store()
    return ActionResult(f"Copied path: {text if len(paths) == 1 else f'{len(paths)} paths'}")


# ------------------------------------------------------------------ move / terminal / share

def move_to(paths, folder):
    folder = Path(folder)
    moved = []
    for p in paths:
        p = Path(p)
        if p.parent.resolve() == folder.resolve():
            continue
        dest = unique_path(folder / p.name)
        shutil.move(str(p), dest)
        moved.append(dest)
    if not moved:
        return ActionResult("Already in that folder")
    return ActionResult(f"Moved {len(moved)} item{'s' if len(moved) > 1 else ''} to {folder.name or folder}",
                        outputs=moved)


def choose_folder(parent, start, recent):
    dialog = Gtk.FileChooserDialog(title="Move to", parent=parent, action=Gtk.FileChooserAction.SELECT_FOLDER)
    dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Move Here", Gtk.ResponseType.ACCEPT)
    dialog.set_default_response(Gtk.ResponseType.ACCEPT)
    dialog.set_keep_above(True)
    dialog.set_current_folder(str(start))
    for folder in recent:
        if Path(folder).is_dir():
            try:
                dialog.add_shortcut_folder(folder)
            except GLib.Error:
                pass
    result = dialog.run()
    chosen = dialog.get_filename() if result == Gtk.ResponseType.ACCEPT else None
    dialog.destroy()
    return chosen


TERMINALS = [
    ("gnome-terminal", ["--working-directory={dir}"]),
    ("kgx", ["--working-directory={dir}"]),
    ("ptyxis", ["--new-window", "--working-directory={dir}"]),
    ("tilix", ["--working-directory={dir}"]),
    ("konsole", ["--workdir", "{dir}"]),
    ("xfce4-terminal", ["--working-directory={dir}"]),
    ("alacritty", ["--working-directory", "{dir}"]),
    ("kitty", ["--directory", "{dir}"]),
    ("x-terminal-emulator", []),
    ("xterm", []),
]


def open_terminal(paths):
    p = Path(paths[0])
    folder = p if p.is_dir() else p.parent
    for exe, args in TERMINALS:
        if shutil.which(exe):
            subprocess.Popen([exe, *[a.format(dir=folder) for a in args]], cwd=folder,
                             start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return ActionResult(f"Terminal opened in {folder}")
    return ActionResult("No terminal emulator found", error=True)


def share(paths):
    """Linux has no AirDrop; use KDE Connect, Bluetooth or e-mail, in that order."""
    files = [str(Path(p)) for p in paths if Path(p).is_file()]
    if not files:
        return ActionResult("Only files can be shared", error=True)
    if shutil.which("kdeconnect-cli"):
        out = subprocess.run(["kdeconnect-cli", "-a", "--id-name-only"], capture_output=True, text=True).stdout
        devices = [line.split(" ", 1) for line in out.splitlines() if line.strip()]
        if devices:
            dev_id, name = devices[0][0], devices[0][-1]
            for f in files:
                subprocess.Popen(["kdeconnect-cli", "-d", dev_id, "--share", f])
            return ActionResult(f"Sending to {name} via KDE Connect")
    if shutil.which("bluetooth-sendto"):
        subprocess.Popen(["bluetooth-sendto", *files], start_new_session=True)
        return ActionResult("Choose a Bluetooth device")
    if shutil.which("xdg-email"):
        args = ["xdg-email"]
        for f in files:
            args += ["--attach", f]
        subprocess.Popen(args, start_new_session=True)
        return ActionResult("Opened a new e-mail with the attachment")
    return ActionResult("Install KDE Connect or gnome-bluetooth to share files", error=True)


# ------------------------------------------------------------------ float shelf

class FloatShelf(Gtk.Window):
    """Always-on-top shelf: park files here and drag them out (or into the wheel) later."""

    def __init__(self, app):
        super().__init__(title="Float")
        self.get_style_context().add_class("metamorph")
        self.app = app
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.stick()
        self.get_style_context().add_class("metamorph-shelf")
        self.items = []

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        handle = Gtk.EventBox()
        bar = Gtk.Box(spacing=6)
        bar.set_margin_start(10)
        bar.set_margin_end(4)
        bar.set_margin_top(4)
        title = Gtk.Label(label="Float", xalign=0)
        title.get_style_context().add_class("metamorph-shelf-title")
        bar.pack_start(title, True, True, 0)
        clear = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        clear.set_relief(Gtk.ReliefStyle.NONE)
        clear.set_tooltip_text("Close the shelf")
        clear.connect("clicked", lambda b: self.clear())
        bar.pack_end(clear, False, False, 0)
        handle.add(bar)
        handle.connect("button-press-event", self._on_handle_press)
        outer.pack_start(handle, False, False, 0)

        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_max_children_per_line(4)
        self.flow.set_min_children_per_line(1)
        self.flow.set_column_spacing(4)
        self.flow.set_row_spacing(4)
        self.flow.set_margin_start(8)
        self.flow.set_margin_end(8)
        self.flow.set_margin_bottom(8)
        outer.pack_start(self.flow, True, True, 0)
        self.add(outer)

        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY | Gdk.DragAction.LINK)
        self.drag_dest_add_uri_targets()
        self.connect("drag-data-received", self._on_drop)
        self.connect("delete-event", lambda *a: self.clear() or True)

    def add_paths(self, paths):
        known = {p for p, _ in self.items}
        for p in paths:
            p = Path(p)
            if p in known:
                continue
            widget = self._item(p)
            self.items.append((p, widget))
            self.flow.add(widget)
        self.show_all()
        if not self.get_position()[0] and not self.get_position()[1]:
            self._place()
        self.present()

    def clear(self):
        for _, widget in self.items:
            widget.get_parent().destroy()
        self.items = []
        self.hide()

    def _remove(self, path):
        for i, (p, widget) in enumerate(self.items):
            if p == path:
                widget.get_parent().destroy()
                del self.items[i]
                break
        if not self.items:
            self.hide()
        else:
            self.resize(1, 1)

    def _place(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        area = monitor.get_workarea()
        self.move(area.x + area.width - 360, area.y + 80)

    def _on_handle_press(self, widget, event):
        if event.button == 1:
            self.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
        return True

    def _on_drop(self, widget, ctx, x, y, data, info, time):
        paths = [Gio.File.new_for_uri(u).get_path() for u in data.get_uris() or []]
        self.add_paths([p for p in paths if p])

    def _item(self, path):
        box = Gtk.EventBox()
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        col.set_size_request(76, -1)
        col.get_style_context().add_class("metamorph-shelf-item")
        col.pack_start(self._icon(path), False, False, 0)
        name = Gtk.Label(label=path.name)
        name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        name.set_max_width_chars(10)
        col.pack_start(name, False, False, 0)
        box.add(col)
        box.set_tooltip_text(f"{path}\nDrag out to use it. Hold a wheel key while dragging to convert.\n"
                             "Double-click opens, right-click removes.")
        box.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [], Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        box.drag_source_add_uri_targets()
        box.connect("drag-data-get", lambda w, ctx, data, info, t: data.set_uris([path.as_uri()]))
        box.connect("button-press-event", self._on_item_press, path)
        return box

    def _on_item_press(self, widget, event, path):
        if event.button == 3:
            self._remove(path)
        elif event.type == Gdk.EventType._2BUTTON_PRESS:
            Gio.AppInfo.launch_default_for_uri(path.as_uri(), None)
        return False

    @staticmethod
    def _icon(path):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 56, 56, True)
            return Gtk.Image.new_from_pixbuf(pixbuf)
        except GLib.Error:
            pass
        try:
            info = Gio.File.new_for_path(str(path)).query_info("standard::icon", 0, None)
            return Gtk.Image.new_from_gicon(info.get_icon(), Gtk.IconSize.DIALOG)
        except GLib.Error:
            return Gtk.Image.new_from_icon_name("text-x-generic", Gtk.IconSize.DIALOG)
