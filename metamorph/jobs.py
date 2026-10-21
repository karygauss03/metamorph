"""Background job queue with a progress toast and desktop notifications."""

import itertools
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from . import registry
from .util import ConversionError

_ids = itertools.count(1)


class Job:
    def __init__(self, op, paths, params):
        self.id = next(_ids)
        self.op, self.paths, self.params = op, [Path(p) for p in paths], params
        self.state = "queued"          # queued | running | done | failed | cancelled
        self.progress = 0.0
        self.outputs = []
        self.error = ""
        self.started = self.finished = 0.0
        self.cancel = threading.Event()

    @property
    def title(self):
        name = self.paths[0].name if len(self.paths) == 1 else f"{len(self.paths)} files"
        verb = {"convert": f"to {self.op.label}", "tool": self.op.label}.get(self.op.kind, self.op.label)
        return f"{name} {verb}" if self.op.kind == "convert" else f"{verb}: {name}"


class JobQueue:
    def __init__(self, get_settings, notifier):
        self.get_settings = get_settings
        self.notifier = notifier
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="job")
        self.jobs = []
        self.listeners = []

    def submit(self, op, paths, params):
        job = Job(op, paths, params)
        self.jobs.insert(0, job)
        del self.jobs[50:]
        self._changed(job)
        self.pool.submit(self._run, job)
        return job

    def _changed(self, job):
        for listener in self.listeners:
            listener(job)

    def _run(self, job):
        conf = self.get_settings()
        out_dir = conf["output_folder"] if conf["output"] == "folder" and conf["output_folder"] else None
        last = [0.0]

        def progress(fraction):
            job.progress = fraction
            now = time.monotonic()
            if now - last[0] > 0.15:
                last[0] = now
                GLib.idle_add(self._changed, job)

        job.state, job.started = "running", time.monotonic()
        GLib.idle_add(self._changed, job)
        ctx = registry.Context(conf, dict(job.params), out_dir, progress, job.cancel.is_set)
        try:
            job.outputs = [Path(p) for p in registry.execute(job.op, job.paths, ctx)]
            job.state = "cancelled" if job.cancel.is_set() else "done"
        except ConversionError as exc:
            job.state, job.error = "failed", str(exc)
        except Exception as exc:  # unexpected: still report instead of failing silently
            job.state, job.error = "failed", f"{type(exc).__name__}: {exc}"
        job.progress, job.finished = 1.0, time.monotonic()
        GLib.idle_add(self._finished, job)

    def _finished(self, job):
        self._changed(job)
        conf = self.get_settings()
        if conf.get("notify") and job.finished - job.started > 4:
            if job.state == "done":
                self.notifier.notify("Done", job.title, job.outputs[0] if job.outputs else None)
            elif job.state == "failed":
                self.notifier.notify("Failed", f"{job.title}\n{job.error}", None)
        if job.state == "done" and conf.get("reveal_after") and job.outputs:
            reveal(job.outputs)


def reveal(paths):
    """Select the files in the file manager (org.freedesktop.FileManager1)."""
    uris = [Path(p).as_uri() for p in paths if Path(p).exists()]
    if not uris:
        return
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        bus.call_sync("org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
                      "org.freedesktop.FileManager1", "ShowItems", GLib.Variant("(ass)", (uris, "")),
                      None, Gio.DBusCallFlags.NONE, 3000)
    except GLib.Error:
        Gio.AppInfo.launch_default_for_uri(Path(paths[0]).parent.as_uri(), None)


def open_file(path):
    try:
        Gio.AppInfo.launch_default_for_uri(Path(path).as_uri(), None)
    except GLib.Error as exc:
        print(f"metamorph: cannot open {path}: {exc.message}")


class Notifier:
    """org.freedesktop.Notifications with a 'Show' action (no .desktop needed)."""

    def __init__(self):
        self.pending = {}
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION)
            self.bus.signal_subscribe("org.freedesktop.Notifications", "org.freedesktop.Notifications",
                                      "ActionInvoked", "/org/freedesktop/Notifications", None,
                                      Gio.DBusSignalFlags.NONE, self._on_action)
        except GLib.Error:
            self.bus = None

    def notify(self, summary, body, path):
        if not self.bus:
            return
        actions = ["default", "Show", "show", "Show in Files"] if path else []
        params = GLib.Variant("(susssasa{sv}i)", ("Metamorph", 0, "emblem-synchronizing-symbolic",
                                                 summary, body, actions, {}, 6000))

        def done(bus, result):
            try:
                (nid,) = bus.call_finish(result).unpack()
                if path:
                    self.pending[nid] = path
            except GLib.Error:
                pass
        self.bus.call("org.freedesktop.Notifications", "/org/freedesktop/Notifications",
                      "org.freedesktop.Notifications", "Notify", params, None,
                      Gio.DBusCallFlags.NONE, 3000, None, done)

    def _on_action(self, conn, sender, path, iface, signal, params):
        nid, action = params.unpack()
        target = self.pending.pop(nid, None)
        if target:
            reveal([target])


class Toast(Gtk.Window):
    """Small stack of job cards in the bottom-right corner of the work area."""

    def __init__(self, queue):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.queue = queue
        self.set_keep_above(True)
        self.get_style_context().add_class("metamorph-toast")
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.box.set_margin_top(10)
        self.box.set_margin_bottom(10)
        self.box.set_margin_start(10)
        self.box.set_margin_end(10)
        self.add(self.box)
        self.cards = {}
        self._hide_source = 0
        queue.listeners.append(self.update)

    def update(self, job):
        card = self.cards.get(job.id)
        if card is None:
            card = JobCard(job, self._dismiss)
            self.cards[job.id] = card
            self.box.pack_end(card, False, False, 0)
            for old in list(self.cards.values())[:-4]:
                self._dismiss(old)
        if job.state in ("done", "failed", "cancelled"):
            delay = 9000 if job.state == "failed" else 4500
            GLib.timeout_add(delay, self._expire, job.id)
        self.show_all()
        for c in self.cards.values():  # show_all() revealed every child; re-apply states
            c.refresh()
        self._place()

    def _expire(self, job_id):
        card = self.cards.get(job_id)
        if card and not card.hovered and card.job.state != "running":
            self._dismiss(card)
        elif card:
            return True  # keep it while the pointer is on it
        return False

    def _dismiss(self, card):
        self.cards.pop(card.job.id, None)
        card.destroy()
        if not self.cards:
            self.hide()
        else:
            self.resize(1, 1)
            GLib.idle_add(self._place)

    def _place(self):
        display = Gdk.Display.get_default()
        seat = display.get_default_seat()
        _, x, y = seat.get_pointer().get_position()[0:3]
        monitor = display.get_monitor_at_point(x, y) or display.get_primary_monitor()
        area = monitor.get_workarea()
        w, h = self.get_size()
        self.move(area.x + area.width - w - 16, area.y + area.height - h - 16)
        return False


class JobCard(Gtk.EventBox):
    def __init__(self, job, on_close):
        super().__init__()
        self.job = job
        self.hovered = False
        self.connect("enter-notify-event", lambda *a: setattr(self, "hovered", True))
        self.connect("leave-notify-event", lambda *a: setattr(self, "hovered", False))
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        frame.get_style_context().add_class("metamorph-card")
        frame.set_size_request(320, -1)
        self.add(frame)

        top = Gtk.Box(spacing=8)
        self.title = Gtk.Label(xalign=0)
        self.title.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.title.get_style_context().add_class("metamorph-card-title")
        top.pack_start(self.title, True, True, 0)
        close = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        close.set_relief(Gtk.ReliefStyle.NONE)
        close.set_tooltip_text("Cancel" if job.state in ("queued", "running") else "Dismiss")
        close.connect("clicked", self._on_close, on_close)
        top.pack_end(close, False, False, 0)
        frame.pack_start(top, False, False, 0)

        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(44)
        self.status.get_style_context().add_class("dim-label")
        frame.pack_start(self.status, False, False, 0)
        self.bar = Gtk.ProgressBar()
        frame.pack_start(self.bar, False, False, 0)

        self.buttons = Gtk.Box(spacing=6)
        self.show_btn = Gtk.Button(label="Show in Files")
        self.show_btn.connect("clicked", lambda b: reveal(self.job.outputs))
        self.open_btn = Gtk.Button(label="Open")
        self.open_btn.connect("clicked", lambda b: open_file(self.job.outputs[0]))
        self.buttons.pack_end(self.open_btn, False, False, 0)
        self.buttons.pack_end(self.show_btn, False, False, 0)
        frame.pack_start(self.buttons, False, False, 0)

    def _on_close(self, button, on_close):
        if self.job.state in ("queued", "running"):
            self.job.cancel.set()
        on_close(self)

    def refresh(self):
        job = self.job
        self.title.set_text(job.title)
        if job.state == "queued":
            text = "Waiting"
        elif job.state == "running":
            text = f"Working  {int(job.progress * 100)}%" if job.progress else "Working"
        elif getattr(job, "message", None):
            text = job.message
        elif job.state == "done":
            names = ", ".join(p.name for p in job.outputs[:3]) + ("..." if len(job.outputs) > 3 else "")
            text = f"Saved {names}"
        elif job.state == "cancelled":
            text = "Cancelled"
        else:
            text = job.error
        self.status.set_text(text)
        ctx = self.status.get_style_context()
        (ctx.add_class if job.state == "failed" else ctx.remove_class)("metamorph-error")
        self.bar.set_visible(job.state in ("queued", "running"))
        if job.state == "running" and not job.progress:
            self.bar.pulse()
        else:
            self.bar.set_fraction(job.progress)
        done = job.state == "done" and bool(job.outputs)
        self.buttons.set_visible(done)
        self.open_btn.set_visible(done and len(job.outputs) == 1 and job.outputs[0].is_file())
