"""Freeform crop window: draw, move and resize the area to keep."""

from pathlib import Path

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
from PIL import ImageOps

from .engines import images
from .util import ConversionError

RATIOS = [("free", "Free", None), ("original", "Original", "original"), ("1:1", "Square 1:1", 1.0),
          ("16:9", "16:9", 16 / 9), ("4:3", "4:3", 4 / 3), ("3:2", "3:2", 3 / 2),
          ("2:3", "2:3", 2 / 3), ("4:5", "4:5", 4 / 5), ("9:16", "9:16", 9 / 16)]
CURSORS = {"nw": "nw-resize", "n": "n-resize", "ne": "ne-resize", "e": "e-resize", "se": "se-resize",
           "s": "s-resize", "sw": "sw-resize", "w": "w-resize", "move": "move", "new": "crosshair"}
OPPOSITE = {"nw": "se", "ne": "sw", "se": "nw", "sw": "ne"}
MARGIN = 28
HANDLE = 10        # handle size in view pixels
GRAB = 12          # pointer tolerance around handles and edges
PREVIEW_MAX = 1800

CANVAS = (0.11, 0.11, 0.12)
SHADE = (0, 0, 0, 0.58)
LINE = (1, 1, 1, 0.95)
GUIDE = (1, 1, 1, 0.32)
ACCENT = (1.0, 0.541, 0.122)


class CropWindow(Gtk.Window):
    def __init__(self, paths, on_run):
        super().__init__(title="Crop")
        self.paths, self.on_run = [Path(p) for p in paths], on_run
        try:
            self.image = ImageOps.exif_transpose(images.open_image(self.paths[0]))
        except ConversionError as exc:
            self._fail(str(exc))
            return
        self.iw, self.ih = self.image.size
        preview = self.image.convert("RGBA")
        preview.thumbnail((PREVIEW_MAX, PREVIEW_MAX))
        self.pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            GLib.Bytes.new(preview.tobytes()), GdkPixbuf.Colorspace.RGB, True, 8,
            preview.width, preview.height, preview.width * 4)
        self.rect = [0.0, 0.0, float(self.iw), float(self.ih)]
        self.ratio = None
        self.drag = None
        self.hover = None

        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_position(Gtk.WindowPosition.CENTER)
        self._size_to_screen()
        self._build_header()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(self._build_toolbar(), False, False, 0)
        self.area = Gtk.DrawingArea(can_focus=True)
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                             Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        self.area.connect("draw", self._on_draw)
        self.area.connect("button-press-event", self._on_press)
        self.area.connect("button-release-event", self._on_release)
        self.area.connect("motion-notify-event", self._on_motion)
        box.pack_start(self.area, True, True, 0)
        self.add(box)
        self.connect("key-press-event", self._on_key)
        self._update()
        self.show_all()
        self.present()
        self.area.grab_focus()

    # ------------------------------------------------------------ construction

    def _fail(self, message):
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE,
                                   text="Cannot open the image", secondary_text=message)
        dialog.run()
        dialog.destroy()
        self.destroy()

    def _size_to_screen(self):
        display = Gdk.Display.get_default()
        _, px, py = display.get_default_seat().get_pointer().get_position()[0:3]
        area = display.get_monitor_at_point(px, py).get_workarea()
        max_w, max_h = area.width * 0.8, area.height * 0.8 - 110
        scale = min(1.0, (max_w - 2 * MARGIN) / self.iw, (max_h - 2 * MARGIN) / self.ih)
        width = max(560, int(self.iw * scale + 2 * MARGIN))
        height = max(420, int(self.ih * scale + 2 * MARGIN)) + 52
        self.set_default_size(width, height)

    def _build_header(self):
        n = len(self.paths)
        subtitle = self.paths[0].name if n == 1 else f"Same area for all {n} images"
        header = Gtk.HeaderBar(title="Crop", subtitle=subtitle)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda b: self.destroy())
        header.pack_start(cancel)
        self.crop_button = Gtk.Button(label="Crop")
        self.crop_button.get_style_context().add_class("suggested-action")
        self.crop_button.set_tooltip_text("Save a cropped copy (Enter)")
        self.crop_button.connect("clicked", lambda b: self._submit())
        header.pack_end(self.crop_button)
        self.set_titlebar(header)

    def _build_toolbar(self):
        bar = Gtk.Box(spacing=8)
        for side in ("top", "bottom", "start", "end"):
            getattr(bar, f"set_margin_{side}")(8)
        bar.pack_start(Gtk.Label(label="Aspect"), False, False, 0)
        self.ratio_combo = Gtk.ComboBoxText()
        for key, label, _ in RATIOS:
            self.ratio_combo.append(key, label)
        self.ratio_combo.set_active_id("free")
        self.ratio_combo.connect("changed", self._on_ratio)
        bar.pack_start(self.ratio_combo, False, False, 0)
        fit = Gtk.Button(label="Fit to Content")
        fit.set_tooltip_text("Select everything except the uniform border")
        fit.connect("clicked", self._on_fit)
        bar.pack_start(fit, False, False, 0)
        reset = Gtk.Button(label="Reset")
        reset.connect("clicked", self._on_reset)
        bar.pack_start(reset, False, False, 0)
        self.size_label = Gtk.Label(xalign=1)
        self.size_label.get_style_context().add_class("dim-label")
        bar.pack_end(self.size_label, False, False, 0)
        return bar

    # ------------------------------------------------------------ geometry

    def _view(self):
        """Scale and offset that fit the image in the drawing area."""
        w, h = self.area.get_allocated_width(), self.area.get_allocated_height()
        scale = min((w - 2 * MARGIN) / self.iw, (h - 2 * MARGIN) / self.ih)
        scale = max(scale, 1e-3)
        return scale, (w - self.iw * scale) / 2, (h - self.ih * scale) / 2

    def _to_image(self, x, y):
        scale, ox, oy = self._view()
        return (x - ox) / scale, (y - oy) / scale

    def _min_size(self):
        return max(1.0, 16 / self._view()[0])

    def _hit(self, x, y):
        scale, ox, oy = self._view()
        x0, y0, x1, y1 = (v * scale for v in self.rect)
        x0, x1, y0, y1 = x0 + ox, x1 + ox, y0 + oy, y1 + oy
        near_l, near_r = abs(x - x0) <= GRAB, abs(x - x1) <= GRAB
        near_t, near_b = abs(y - y0) <= GRAB, abs(y - y1) <= GRAB
        inside_x, inside_y = x0 - GRAB <= x <= x1 + GRAB, y0 - GRAB <= y <= y1 + GRAB
        if near_t and near_l: return "nw"
        if near_t and near_r: return "ne"
        if near_b and near_l: return "sw"
        if near_b and near_r: return "se"
        if near_t and inside_x: return "n"
        if near_b and inside_x: return "s"
        if near_l and inside_y: return "w"
        if near_r and inside_y: return "e"
        # A full-image selection cannot move, so dragging inside it draws a new one.
        full = self._pixel_box() == (0, 0, self.iw, self.ih)
        if x0 < x < x1 and y0 < y < y1 and not full: return "move"
        return "new"

    def _corner(self, ax, ay, px, py):
        """Rectangle from a fixed anchor to the pointer, honouring the ratio and bounds."""
        px, py = min(max(px, 0), self.iw), min(max(py, 0), self.ih)
        sx, sy = (1 if px >= ax else -1), (1 if py >= ay else -1)
        max_w = self.iw - ax if sx > 0 else ax
        max_h = self.ih - ay if sy > 0 else ay
        w, h = min(abs(px - ax), max_w), min(abs(py - ay), max_h)
        m = self._min_size()
        r = self.ratio
        if r:
            # Follow the pointer on the tighter axis, then keep the ratio inside the image.
            if h * r < w:
                w = h * r
            else:
                h = w / r
            if w < m:
                w, h = m, m / r
            if h < m:
                w, h = m * r, m
            if w > max_w:
                w, h = max_w, max_w / r
            if h > max_h:
                w, h = max_h * r, max_h
        else:
            w, h = min(max(w, m), max_w), min(max(h, m), max_h)
        x0, x1 = sorted((ax, ax + sx * w))
        y0, y1 = sorted((ay, ay + sy * h))
        return [x0, y0, x1, y1]

    def _edge(self, edge, start, px, py):
        x0, y0, x1, y1 = start
        m = self._min_size()
        if edge in ("e", "w"):
            if edge == "e":
                x1 = min(max(px, x0 + m), self.iw)
            else:
                x0 = max(min(px, x1 - m), 0)
            if self.ratio:
                h = min((x1 - x0) / self.ratio, self.ih)
                if edge == "e":
                    x1 = x0 + h * self.ratio
                else:
                    x0 = x1 - h * self.ratio
                cy = (y0 + y1) / 2
                y0, y1 = self._fit_span(cy - h / 2, h, self.ih)
        else:
            if edge == "s":
                y1 = min(max(py, y0 + m), self.ih)
            else:
                y0 = max(min(py, y1 - m), 0)
            if self.ratio:
                w = min((y1 - y0) * self.ratio, self.iw)
                if edge == "s":
                    y1 = y0 + w / self.ratio
                else:
                    y0 = y1 - w / self.ratio
                cx = (x0 + x1) / 2
                x0, x1 = self._fit_span(cx - w / 2, w, self.iw)
        return [x0, y0, x1, y1]

    @staticmethod
    def _fit_span(start, length, limit):
        start = min(max(start, 0), limit - length)
        return start, start + length

    def _apply_ratio(self):
        """Largest rectangle of the chosen ratio inside the current one, centred on it."""
        if not self.ratio:
            return
        x0, y0, x1, y1 = self.rect
        w, h = x1 - x0, y1 - y0
        if w / h > self.ratio:
            w = h * self.ratio
        else:
            h = w / self.ratio
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        x0, x1 = self._fit_span(cx - w / 2, w, self.iw)
        y0, y1 = self._fit_span(cy - h / 2, h, self.ih)
        self.rect = [x0, y0, x1, y1]

    def _pixel_box(self):
        x0, y0, x1, y1 = self.rect
        return round(x0), round(y0), round(x1), round(y1)

    # ------------------------------------------------------------ events

    def _on_press(self, widget, event):
        if event.button != 1:
            return False
        self.area.grab_focus()
        kind = self._hit(event.x, event.y)
        px, py = self._to_image(event.x, event.y)
        if kind == "new":
            if not (0 <= px <= self.iw and 0 <= py <= self.ih):
                return True
            self.drag = ("new", (px, py), list(self.rect))
        else:
            self.drag = (kind, (px, py), list(self.rect))
        return True

    def _on_motion(self, widget, event):
        px, py = self._to_image(event.x, event.y)
        if self.drag is None:
            kind = self._hit(event.x, event.y)
            if kind != self.hover:
                self.hover = kind
                cursor = Gdk.Cursor.new_from_name(widget.get_display(), CURSORS[kind])
                widget.get_window().set_cursor(cursor)
            return True
        kind, (sx, sy), start = self.drag
        if kind == "move":
            w, h = start[2] - start[0], start[3] - start[1]
            x0, x1 = self._fit_span(start[0] + px - sx, w, self.iw)
            y0, y1 = self._fit_span(start[1] + py - sy, h, self.ih)
            self.rect = [x0, y0, x1, y1]
        elif kind == "new":
            self.rect = self._corner(sx, sy, px, py)
        elif kind in OPPOSITE:
            anchor = {"nw": (start[2], start[3]), "ne": (start[0], start[3]),
                      "se": (start[0], start[1]), "sw": (start[2], start[1])}[kind]
            self.rect = self._corner(*anchor, px, py)
        else:
            self.rect = self._edge(kind, start, px, py)
        self._update()
        return True

    def _on_release(self, widget, event):
        if self.drag and self.drag[0] == "new":
            x0, y0, x1, y1 = self.rect
            if x1 - x0 <= self._min_size() + 0.5 and y1 - y0 <= self._min_size() + 0.5:
                self.rect = self.drag[2]  # a click, not a drag: keep the previous selection
        self.drag = None
        self._update()
        return True

    def _on_key(self, widget, event):
        key = event.keyval
        if key == Gdk.KEY_Escape:
            self.destroy()
        elif key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._submit()
        elif key in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down):
            step = 10 if event.state & Gdk.ModifierType.SHIFT_MASK else 1
            dx = {Gdk.KEY_Left: -step, Gdk.KEY_Right: step}.get(key, 0)
            dy = {Gdk.KEY_Up: -step, Gdk.KEY_Down: step}.get(key, 0)
            x0, y0, x1, y1 = self.rect
            x0, x1 = self._fit_span(x0 + dx, x1 - x0, self.iw)
            y0, y1 = self._fit_span(y0 + dy, y1 - y0, self.ih)
            self.rect = [x0, y0, x1, y1]
            self._update()
        else:
            return False
        return True

    def _on_ratio(self, combo):
        value = dict((k, r) for k, _, r in RATIOS)[combo.get_active_id()]
        self.ratio = self.iw / self.ih if value == "original" else value
        self._apply_ratio()
        self._update()

    def _on_fit(self, button):
        box = images.content_box(self.image)
        if box:
            self.ratio_combo.set_active_id("free")
            self.rect = [float(v) for v in box]
            self._update()

    def _on_reset(self, button):
        self.ratio_combo.set_active_id("free")
        self.rect = [0.0, 0.0, float(self.iw), float(self.ih)]
        self._update()

    def _update(self):
        x0, y0, x1, y1 = self._pixel_box()
        self.size_label.set_text(f"{x1 - x0} × {y1 - y0} px   at {x0}, {y0}   of {self.iw} × {self.ih}")
        self.crop_button.set_sensitive((x0, y0, x1, y1) != (0, 0, self.iw, self.ih) and x1 > x0 and y1 > y0)
        self.area.queue_draw()

    def _submit(self):
        if not self.crop_button.get_sensitive():
            return
        x0, y0, x1, y1 = self._pixel_box()
        rect = f"{x0 / self.iw:.6f},{y0 / self.ih:.6f},{x1 / self.iw:.6f},{y1 / self.ih:.6f}"
        self.destroy()
        self.on_run({"rect": rect})

    # ------------------------------------------------------------ drawing

    def _on_draw(self, widget, cr):
        scale, ox, oy = self._view()
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        cr.set_source_rgb(*CANVAS)
        cr.paint()
        iw, ih = self.iw * scale, self.ih * scale

        # Checkerboard shows transparency.
        cr.save()
        cr.rectangle(ox, oy, iw, ih)
        cr.clip()
        tile = 10
        for ty in range(int(ih // tile) + 1):
            for tx in range(int(iw // tile) + 1):
                cr.set_source_rgb(*((0.42,) * 3 if (tx + ty) % 2 else (0.34,) * 3))
                cr.rectangle(ox + tx * tile, oy + ty * tile, tile, tile)
                cr.fill()
        cr.restore()

        cr.save()
        cr.translate(ox, oy)
        factor = iw / self.pixbuf.get_width()
        cr.scale(factor, factor)
        Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
        cr.get_source().set_filter(1)  # GOOD
        cr.paint()
        cr.restore()

        x0, y0, x1, y1 = (v * scale for v in self.rect)
        x0, x1, y0, y1 = x0 + ox, x1 + ox, y0 + oy, y1 + oy
        cr.set_fill_rule(1)  # EVEN_ODD: shade everything outside the selection
        cr.rectangle(ox, oy, iw, ih)
        cr.rectangle(x0, y0, x1 - x0, y1 - y0)
        cr.set_source_rgba(*SHADE)
        cr.fill()
        cr.set_fill_rule(0)

        if self.drag:  # rule-of-thirds guides while adjusting
            cr.set_source_rgba(*GUIDE)
            cr.set_line_width(1)
            for i in (1, 2):
                gx = x0 + (x1 - x0) * i / 3
                gy = y0 + (y1 - y0) * i / 3
                cr.move_to(gx, y0); cr.line_to(gx, y1)
                cr.move_to(x0, gy); cr.line_to(x1, gy)
            cr.stroke()

        cr.set_source_rgba(*LINE)
        cr.set_line_width(1.5)
        cr.rectangle(x0, y0, x1 - x0, y1 - y0)
        cr.stroke()

        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        for hx, hy in ((x0, y0), (mx, y0), (x1, y0), (x1, my), (x1, y1), (mx, y1), (x0, y1), (x0, my)):
            cr.rectangle(hx - HANDLE / 2, hy - HANDLE / 2, HANDLE, HANDLE)
            cr.set_source_rgb(*ACCENT)
            cr.fill_preserve()
            cr.set_source_rgba(0, 0, 0, 0.6)
            cr.set_line_width(1)
            cr.stroke()
