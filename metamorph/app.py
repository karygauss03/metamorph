"""The resident application: drag watcher, wheel, jobs, actions, settings."""

import os
import shutil
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import actions, settings  # noqa: E402
from .dialogs import ParamsDialog, SettingsWindow  # noqa: E402
from .jobs import Job, JobQueue, Notifier, Toast  # noqa: E402
from .wheel import Wheel  # noqa: E402

APP_ID = "io.github.metamorph.Metamorph"

CSS = b"""
.metamorph-toast { border: 1px solid alpha(@theme_fg_color, 0.14); border-radius: 0; }
.metamorph-card { padding: 4px 2px; }
.metamorph-card-title { font-weight: bold; }
.metamorph-error { color: @error_color; }
.metamorph-dropzone {
  border: 2px dashed alpha(@theme_fg_color, 0.22);
  border-radius: 14px;
  background-color: alpha(@theme_fg_color, 0.03);
}
.metamorph-shelf { border: 1px solid alpha(@theme_fg_color, 0.14); }
.metamorph-shelf-title { font-weight: bold; }
.metamorph-shelf-item { padding: 6px; }
"""


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.settings = settings.load()
        self.exec_path = shutil.which("metamorph") or str(Path(sys.argv[0]).resolve())
        self.window = None
        self.shelf = None
        self.watcher = None

    # ------------------------------------------------------------ lifecycle

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.notifier = Notifier()
        self.queue = JobQueue(lambda: self.settings, self.notifier)
        self.toast = Toast(self.queue)
        self.wheel = Wheel(self, self.choose)
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *a: self.quit())
        self.add_action(quit_action)
        self._start_watcher()
        self.hold()  # stay resident without windows

    def _start_watcher(self):
        if os.environ.get("XDG_SESSION_TYPE") == "wayland":
            # XWayland only sees drags between X11 clients, so the watcher would miss most.
            print("metamorph: global drag detection needs X11; use the drop zone or Files script", flush=True)
            return
        from .watcher import DragWatcher
        self.watcher = DragWatcher(self.wheel_keys, self._on_drag_mode, self.wheel.drag_ended,
                                   self.wheel.dismiss)
        self.watcher.enabled = self.settings["enabled"]
        self.watcher.start()

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        cwd = cmdline.get_cwd() or os.getcwd()
        if args and args[0] == "open":
            mode = "convert"
            files = []
            for a in args[1:]:
                if a.startswith("--mode="):
                    mode = {"tools": "tool", "actions": "action"}.get(a[7:], a[7:])
                else:
                    files.append(a)
            paths = [Path(f) if os.path.isabs(f) else Path(cwd) / f for f in files]
            paths = [p for p in paths if p.exists()]
            if paths:
                GLib.idle_add(self.open_wheel, paths, mode)
            else:  # launched from the app grid without files
                self.show_settings()
        elif args and args[0] == "quit":
            self.quit()
        elif "--background" not in args:
            self.show_settings()
        return 0

    def show_settings(self):
        if self.window is None:
            self.window = SettingsWindow(self)
            self.window.connect("destroy", lambda w: setattr(self, "window", None))
        self.window.show_all()
        self.window.present()

    # ------------------------------------------------------------ settings

    def wheel_keys(self):
        s = self.settings
        return {"convert": s["key_convert"], "tool": s["key_tools"], "action": s["key_actions"]}

    def update_setting(self, key, value):
        self.settings[key] = value
        settings.save(self.settings)
        if key == "enabled" and self.watcher:
            self.watcher.enabled = value

    # ------------------------------------------------------------ wheel

    def _on_drag_mode(self, mode, x, y):
        self.wheel.show_for_drag(mode, x, y)

    def open_wheel(self, paths, mode="convert"):
        self.wheel.show_interactive(paths, mode)
        return False

    def choose(self, op, paths):
        if op.kind == "action":
            self.run_action(op, paths)
        elif op.editor == "crop":
            from .cropper import CropWindow
            CropWindow(paths, lambda params: self.queue.submit(op, paths, params))
        elif op.params:
            ParamsDialog(op, paths, lambda params: self.queue.submit(op, paths, params))
        else:
            self.queue.submit(op, paths, {})
        return False

    # ------------------------------------------------------------ actions

    def run_action(self, op, paths):
        name = op.id.split(":", 1)[1]
        try:
            if name == "float":
                if self.shelf is None:
                    self.shelf = actions.FloatShelf(self)
                self.shelf.add_paths(paths)
                return
            if name == "move":
                recent = self.settings.get("recent_moves", [])
                start = recent[0] if recent else str(Path(paths[0]).parent)
                folder = actions.choose_folder(None, start, recent)
                if not folder:
                    return
                self.update_setting("recent_moves", [folder] + [f for f in recent if f != folder][:4])
                result = actions.move_to(paths, folder)
            else:
                result = {"share": actions.share, "copy": actions.copy_files,
                          "path": actions.copy_path, "terminal": actions.open_terminal}[name](paths)
        except Exception as exc:
            result = actions.ActionResult(str(exc), error=True)
        self.flash(op, paths, result)

    def flash(self, op, paths, result):
        job = Job(op, paths, {})
        job.state = "failed" if result.error else "done"
        job.error = result.message
        job.message = result.message
        job.outputs = result.outputs
        job.progress = 1.0
        self.toast.update(job)


def run_app(argv):
    app = App()
    return app.run([sys.argv[0], *argv])
