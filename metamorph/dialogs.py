"""Tool option dialog and the settings window."""

from pathlib import Path

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from . import registry, settings, util

AUTOSTART = Path(GLib.get_user_config_dir()) / "autostart" / "metamorph.desktop"


class ParamsDialog(Gtk.Window):
    """Small form for a tool's parameters; calls on_run(params) on confirm."""

    def __init__(self, op, paths, on_run):
        super().__init__(title=op.label)
        self.op, self.on_run = op, on_run
        self.set_keep_above(True)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        header = Gtk.HeaderBar(title=op.label, subtitle=paths[0].name if len(paths) == 1 else f"{len(paths)} files")
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda b: self.destroy())
        header.pack_start(cancel)
        run = Gtk.Button(label="Run")
        run.get_style_context().add_class("suggested-action")
        run.connect("clicked", self._submit)
        header.pack_end(run)
        self.set_titlebar(header)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(grid, f"set_margin_{side}")(18)
        self.fields = {}
        row = 0
        if op.description:
            desc = Gtk.Label(label=op.description, xalign=0)
            desc.get_style_context().add_class("dim-label")
            grid.attach(desc, 0, row, 2, 1)
            row += 1
        hints = self._duration_hint(paths)
        for p in op.params:
            label = Gtk.Label(label=p.label, xalign=1)
            grid.attach(label, 0, row, 1, 1)
            if p.kind == "choice":
                widget = Gtk.ComboBoxText()
                for option in p.options:
                    widget.append(option, option)
                widget.set_active_id(str(p.default))
            elif p.kind == "int":
                widget = Gtk.SpinButton.new_with_range(1, 100 if p.key == "quality" else 1000, 1)
                widget.set_value(float(p.default or 1))
                widget.set_activates_default(True)
            elif p.kind == "bool":
                widget = Gtk.Switch(active=bool(p.default), halign=Gtk.Align.START)
            else:
                widget = Gtk.Entry(text=str(p.default or ""))
                widget.set_activates_default(True)
                widget.set_width_chars(16)
                placeholder = p.hint or ""
                if p.key == "end" and hints:
                    placeholder = f"empty = to the end ({hints})"
                widget.set_placeholder_text(placeholder)
            grid.attach(widget, 1, row, 1, 1)
            self.fields[p.key] = widget
            row += 1
            if p.hint and p.kind != "text" and p.kind != "time":
                hint = Gtk.Label(label=p.hint, xalign=0)
                hint.get_style_context().add_class("dim-label")
                grid.attach(hint, 1, row, 1, 1)
                row += 1
        self.add(grid)
        run.set_can_default(True)
        self.set_default(run)
        self.connect("key-press-event", self._on_key)
        self.show_all()
        self.present()

    @staticmethod
    def _duration_hint(paths):
        try:
            from .engines import media
            seconds = media.probe(paths[0]).duration
            m, s = divmod(int(seconds), 60)
            return f"{m}:{s:02d}"
        except Exception:
            return ""

    def _on_key(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def _submit(self, *args):
        params = {}
        for key, widget in self.fields.items():
            if isinstance(widget, Gtk.ComboBoxText):
                params[key] = widget.get_active_id()
            elif isinstance(widget, Gtk.SpinButton):
                params[key] = int(widget.get_value())
            elif isinstance(widget, Gtk.Switch):
                params[key] = widget.get_active()
            else:
                params[key] = widget.get_text().strip()
        self.destroy()
        self.on_run(params)


def set_autostart(enabled, exec_path):
    if enabled:
        AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART.write_text(
            "[Desktop Entry]\nType=Application\nName=Metamorph\n"
            f"Exec={exec_path} --background\nIcon=metamorph\nX-GNOME-Autostart-enabled=true\n"
            "NoDisplay=true\nComment=Drag-and-drop file converter\n")
    else:
        AUTOSTART.unlink(missing_ok=True)


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Metamorph")
        self.app = app
        self.set_default_size(560, 720)
        header = Gtk.HeaderBar(title="Metamorph", subtitle="Drag, hold a key, drop", show_close_button=True)
        self.set_titlebar(header)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for side in ("top", "bottom", "start", "end"):
            getattr(page, f"set_margin_{side}")(24)
        scroller.add(page)
        self.add(scroller)
        conf = app.settings

        page.pack_start(self._drop_zone(), False, False, 0)

        self._section(page, "Wheel")
        box = self._list(page)
        self._row(box, "Watch drags", "Hold a key while dragging a file to open the wheel",
                  self._switch("enabled"))
        for key, title in (("key_convert", "Convert wheel"), ("key_tools", "Tools wheel"),
                           ("key_actions", "Actions wheel")):
            self._row(box, title, None, self._combo(key, settings.MODIFIERS))
        tip = Gtk.Label(xalign=0, wrap=True)
        tip.set_markup("<small>In Files, select items and press <b>F4</b> (or right-click, "
                       "Scripts, Metamorph) to open the wheel from the keyboard: arrows choose, Enter "
                       "applies, Tab switches wheels, Esc cancels.</small>")
        tip.get_style_context().add_class("dim-label")
        tip.set_margin_top(4)
        page.pack_start(tip, False, False, 0)

        self._section(page, "Output")
        box = self._list(page)
        location = Gtk.ComboBoxText()
        location.append("beside", "Next to the original")
        location.append("folder", "In a folder")
        location.set_active_id(conf["output"])
        folder = Gtk.FileChooserButton(title="Output folder", action=Gtk.FileChooserAction.SELECT_FOLDER)
        if conf["output_folder"]:
            folder.set_filename(conf["output_folder"])
        folder.set_sensitive(conf["output"] == "folder")

        def on_location(combo):
            self.app.update_setting("output", combo.get_active_id())
            folder.set_sensitive(combo.get_active_id() == "folder")
        location.connect("changed", on_location)
        folder.connect("file-set", lambda b: self.app.update_setting("output_folder", b.get_filename() or ""))
        self._row(box, "Save converted files", None, location)
        self._row(box, "Folder", None, folder)
        quality = Gtk.SpinButton.new_with_range(40, 100, 1)
        quality.set_value(conf["image_quality"])
        quality.connect("value-changed", lambda s: self.app.update_setting("image_quality", int(s.get_value())))
        self._row(box, "Image quality", "JPG, WebP, HEIC and AVIF", quality)
        self._row(box, "Video quality", "MP4, MOV, MKV and WebM", self._combo("video_quality", ("High", "Balanced", "Small")))
        self._row(box, "Show in Files when done", None, self._switch("reveal_after"))
        self._row(box, "Notify when long jobs finish", None, self._switch("notify"))

        self._section(page, "General")
        box = self._list(page)
        autostart = Gtk.Switch(active=AUTOSTART.exists(), valign=Gtk.Align.CENTER)
        autostart.connect("notify::active", lambda s, _: set_autostart(s.get_active(), app.exec_path))
        self._row(box, "Start at login", "Keep the drag watcher running in the background", autostart)

        self._section(page, "Capabilities")
        box = self._list(page)
        count = registry.conversion_count()
        tools = sum(op.available() for op in registry.TOOLS)
        self._row(box, f"{count} conversions, {tools} tools, {len(registry.ACTIONS)} actions", None, None)
        for name, where in util.backends().items():
            status = Gtk.Label(label="Ready" if where else "Missing")
            status.get_style_context().add_class("dim-label" if where else "metamorph-error")
            self._row(box, name, None if where else MISSING_HINTS.get(name), status)

        self._section(page, "Recent")
        self.recent = self._list(page)
        self.recent_rows = {}
        for job in reversed(app.queue.jobs[:12]):
            self._add_job(job)
        app.queue.listeners.append(self._on_job)
        self.connect("destroy", lambda w: app.queue.listeners.remove(self._on_job))

    # ------------------------------------------------------------ builders

    def _drop_zone(self):
        zone = Gtk.EventBox()
        label = Gtk.Label()
        label.set_markup("<b>Drop files here</b>\n<small>or drag a file anywhere and hold "
                         f"{self.app.settings['key_convert']}</small>")
        label.set_justify(Gtk.Justification.CENTER)
        frame = Gtk.Box()
        frame.get_style_context().add_class("metamorph-dropzone")
        frame.set_size_request(-1, 110)
        frame.pack_start(label, True, True, 0)
        zone.add(frame)
        zone.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY | Gdk.DragAction.LINK)
        zone.drag_dest_add_uri_targets()

        def received(widget, ctx, x, y, data, info, time):
            paths = [Gio.File.new_for_uri(u).get_path() for u in data.get_uris() or []]
            paths = [p for p in paths if p]
            if paths:
                GLib.idle_add(self.app.open_wheel, paths, "convert")
        zone.connect("drag-data-received", received)
        return zone

    @staticmethod
    def _section(page, title):
        label = Gtk.Label(xalign=0)
        label.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        label.set_margin_top(18)
        label.set_margin_bottom(4)
        page.pack_start(label, False, False, 0)

    @staticmethod
    def _list(page):
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        box.get_style_context().add_class("frame")
        page.pack_start(box, False, False, 0)
        return box

    @staticmethod
    def _row(box, title, subtitle, widget):
        row = Gtk.Box(spacing=12)
        for side in ("top", "bottom"):
            getattr(row, f"set_margin_{side}")(8)
        row.set_margin_start(12)
        row.set_margin_end(12)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
        t = Gtk.Label(label=title, xalign=0)
        t.set_ellipsize(Pango.EllipsizeMode.END)
        text.pack_start(t, False, False, 0)
        if subtitle:
            s = Gtk.Label(label=subtitle, xalign=0, wrap=True)
            s.get_style_context().add_class("dim-label")
            s.set_max_width_chars(48)
            text.pack_start(s, False, False, 0)
        row.pack_start(text, True, True, 0)
        if widget is not None:
            widget.set_valign(Gtk.Align.CENTER)
            row.pack_end(widget, False, False, 0)
        box.add(row)
        return row

    def _switch(self, key):
        sw = Gtk.Switch(active=bool(self.app.settings[key]), valign=Gtk.Align.CENTER)
        sw.connect("notify::active", lambda s, _: self.app.update_setting(key, s.get_active()))
        return sw

    def _combo(self, key, options):
        combo = Gtk.ComboBoxText()
        for option in options:
            combo.append(option, option)
        combo.set_active_id(self.app.settings[key])
        combo.connect("changed", lambda c: self.app.update_setting(key, c.get_active_id()))
        return combo

    # ------------------------------------------------------------ recent jobs

    def _on_job(self, job):
        if job.id in self.recent_rows:
            self._fill_job(job)
        else:
            self._add_job(job)

    def _add_job(self, job):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(8)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(xalign=0)
        title.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        status = Gtk.Label(xalign=0)
        status.set_ellipsize(Pango.EllipsizeMode.END)
        status.get_style_context().add_class("dim-label")
        text.pack_start(title, False, False, 0)
        text.pack_start(status, False, False, 0)
        box.pack_start(text, True, True, 0)
        show = Gtk.Button.new_from_icon_name("folder-open-symbolic", Gtk.IconSize.BUTTON)
        show.set_tooltip_text("Show in Files")
        show.set_relief(Gtk.ReliefStyle.NONE)
        from .jobs import reveal
        show.connect("clicked", lambda b: reveal(job.outputs))
        box.pack_end(show, False, False, 0)
        row.add(box)
        self.recent.insert(row, 0)
        self.recent_rows[job.id] = (title, status, show)
        self._fill_job(job)
        row.show_all()
        self._fill_job(job)

    def _fill_job(self, job):
        title, status, show = self.recent_rows[job.id]
        title.set_text(job.title)
        text = {"queued": "Waiting", "running": f"Working {int(job.progress * 100)}%",
                "cancelled": "Cancelled"}.get(job.state)
        if job.state == "done":
            text = ", ".join(p.name for p in job.outputs[:3]) or "Done"
        elif job.state == "failed":
            text = job.error
        status.set_text(text)
        show.set_visible(job.state == "done" and bool(job.outputs))


MISSING_HINTS = {
    "ffmpeg": "Audio and video: sudo apt install ffmpeg",
    "pandoc": "Documents: sudo apt install pandoc",
    "LibreOffice Writer": "Legacy .doc input and layout-faithful Word to PDF: sudo apt install libreoffice-writer",
    "LibreOffice Calc": "XLS/ODS and spreadsheet PDF: sudo apt install libreoffice-calc",
    "LibreOffice Impress": "PowerPoint/ODP conversions: sudo apt install libreoffice-impress",
    "Ghostscript": "Stronger PDF compression: sudo apt install ghostscript",
    "unrar": "RAR input: sudo apt install unrar",
}
