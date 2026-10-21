"""The radial wheel: an XDND drop target during drags, a menu otherwise."""

import math
from pathlib import Path

from gi.repository import Gdk, Gio, GLib, Gtk, Pango, PangoCairo

from . import registry

MODES = ("convert", "tool", "action")
MODE_TITLES = {"convert": "Convert", "tool": "Tools", "action": "Actions"}

HUB = 74
SINGLE_OUTER = 178
MID = 142
OUTER = 212
PAD = 10
SIZE = 2 * (OUTER + PAD)
GAP = 3.0                       # px between slices
INNER_MAX = 8                   # slices on the inner ring before a second ring

# Colours (r, g, b, a). The wheel is a HUD over arbitrary content, so it has its own
# dark surface instead of following the GTK theme.
SURFACE = (0.09, 0.09, 0.10, 0.985)
RIM = (1, 1, 1, 0.10)
SLICE = (0.16, 0.16, 0.18, 1)
SLICE_DIM = (0.12, 0.12, 0.135, 1)
ACCENT = (1.0, 0.541, 0.122, 1)  # tangerine #FF8A1F
TEXT = (0.96, 0.96, 0.97, 1)
TEXT_MUTED = (0.66, 0.66, 0.70, 1)
TEXT_ON_ACCENT = (0.10, 0.06, 0.02, 1)

URI_TARGET = Gtk.TargetEntry.new("text/uri-list", 0, 0)


def _rgba(cr, c):
    cr.set_source_rgba(*c)


class Slice:
    __slots__ = ("op", "r0", "r1", "a0", "a1", "index")

    def __init__(self, op, r0, r1, a0, a1, index):
        self.op, self.r0, self.r1, self.a0, self.a1, self.index = op, r0, r1, a0, a1, index

    def contains(self, r, a):
        if not self.r0 <= r < self.r1:
            return False
        a = (a - self.a0) % (2 * math.pi)
        return a < (self.a1 - self.a0)


def layout(ops):
    n = len(ops)
    if not n:
        return []
    rings = [(HUB, SINGLE_OUTER, ops)] if n <= INNER_MAX + 2 else \
        [(HUB, MID, ops[:INNER_MAX]), (MID, OUTER, ops[INNER_MAX:])]
    slices = []
    for r0, r1, ring in rings:
        step = 2 * math.pi / len(ring)
        start = -math.pi / 2 - step / 2  # first item centred at 12 o'clock
        for i, op in enumerate(ring):
            slices.append(Slice(op, r0, r1, start + i * step, start + (i + 1) * step, len(slices)))
    return slices


class Wheel(Gtk.Window):
    def __init__(self, app, on_choose):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.app = app
        self.on_choose = on_choose           # on_choose(op, paths)
        self.set_default_size(SIZE, SIZE)
        self.set_size_request(SIZE, SIZE)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_title("Metamorph")
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        self.round = bool(visual and screen.is_composited())
        if self.round:
            self.set_visual(visual)
        self.set_app_paintable(True)

        self.area = Gtk.DrawingArea()
        self.area.set_can_focus(True)
        self.area.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK |
                             Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.KEY_PRESS_MASK |
                             Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.add(self.area)
        self.area.connect("draw", self._on_draw)
        self.area.drag_dest_set(0, [URI_TARGET], Gdk.DragAction.COPY | Gdk.DragAction.MOVE |
                                Gdk.DragAction.LINK | Gdk.DragAction.ASK)
        self.area.connect("drag-motion", self._on_drag_motion)
        self.area.connect("drag-leave", self._on_drag_leave)
        self.area.connect("drag-drop", self._on_drag_drop)
        self.area.connect("drag-data-received", self._on_drag_data)
        self.area.connect("motion-notify-event", self._on_motion)
        self.area.connect("button-press-event", self._on_button)
        self.area.connect("key-press-event", self._on_key)
        self.connect("grab-broken-event", lambda *a: self.dismiss())

        self.paths = []
        self.mode = "convert"
        self.slices = []
        self.hover = None
        self.message = ""
        self.dragging = False
        self.interactive = False
        self._requested = False
        self._dropping = False
        self._hide_source = 0
        self._grabbed = None
        self._map_handler = None

    # ------------------------------------------------------------ public API

    def show_for_drag(self, mode, x, y):
        """Open under the pointer while some application is dragging files."""
        if self._hide_source:
            GLib.source_remove(self._hide_source)
            self._hide_source = 0
        if self.get_visible() and self.dragging:
            self.set_mode(mode)
            return
        self.dragging, self.interactive = True, False
        self.paths, self._requested, self._dropping = [], False, False
        self.mode = mode
        self.hover = None
        self.message = "Move to read the files"
        self.slices = []
        self._place(x, y)
        self.show_all()

    def show_interactive(self, paths, mode="convert"):
        """Open as a keyboard/mouse menu for known files (Nautilus script, CLI)."""
        self.dragging, self.interactive = False, True
        self.paths = [Path(p) for p in paths]
        self.mode = mode
        self._rebuild()
        if self.slices:
            self.hover = self.slices[0]
        display = Gdk.Display.get_default()
        _, x, y = display.get_default_seat().get_pointer().get_position()[0:3]
        self._place(x, y)
        self.show_all()
        # Grab as soon as the window is on screen so early key presses aren't lost.
        self._map_handler = self.connect("map-event", lambda *a: self._grab())
        if self.get_mapped():
            self._grab()

    def set_mode(self, mode):
        if mode != self.mode:
            self.mode = mode
            self._rebuild()
            self.area.queue_draw()

    def drag_ended(self):
        """The watcher saw the pointer button go up: hide unless a drop is being handled."""
        if not self.dragging or self._hide_source:
            return
        # XdndDrop can arrive slightly after the button release; give it time.
        self._hide_source = GLib.timeout_add(600, self._hide_after_drag)

    def dismiss(self):
        self._ungrab()
        if self._hide_source:
            GLib.source_remove(self._hide_source)
            self._hide_source = 0
        self.dragging = self.interactive = False
        self.hide()

    # ------------------------------------------------------------ internals

    def _hide_after_drag(self):
        self._hide_source = 0
        if not self._dropping:
            self.dismiss()
        return False

    def _place(self, x, y):
        display = Gdk.Display.get_default()
        monitor = display.get_monitor_at_point(x, y)
        geo = monitor.get_workarea() if monitor else Gdk.Rectangle()
        left = min(max(x - SIZE // 2, geo.x), geo.x + geo.width - SIZE) if monitor else x - SIZE // 2
        top = min(max(y - SIZE // 2, geo.y), geo.y + geo.height - SIZE) if monitor else y - SIZE // 2
        self.move(int(left), int(top))

    def _rebuild(self):
        ops = registry.operations_for(self.paths, self.mode) if self.paths else []
        old = self.hover.op.id if self.hover else None
        self.slices = layout(ops)
        self.hover = next((s for s in self.slices if s.op.id == old), None)
        if self.interactive and self.hover is None and self.slices:
            self.hover = self.slices[0]
        self.message = ""
        if self.paths and not self.slices:
            other = "tools" if self.mode == "convert" else "conversions"
            self.message = f"No {MODE_TITLES[self.mode].lower()} for this selection; try {other}"

    def _hit(self, x, y):
        cx = cy = SIZE / 2
        dx, dy = x - cx, y - cy
        r = math.hypot(dx, dy)
        a = math.atan2(dy, dx)
        for s in self.slices:
            if s.contains(r, a):
                return s
        return None

    def _set_hover(self, s):
        if s is not self.hover:
            self.hover = s
            self.area.queue_draw()

    def _choose(self, s):
        if s is None:
            return
        op, paths = s.op, list(self.paths)
        self.dismiss()
        GLib.idle_add(self.on_choose, op, paths)

    # ------------------------------------------------------------ drag and drop

    def _on_drag_motion(self, widget, ctx, x, y, time):
        if self._hide_source:  # pointer is back over us
            GLib.source_remove(self._hide_source)
            self._hide_source = 0
        if not self.paths and not self._requested:
            self._requested = True
            widget.drag_get_data(ctx, Gdk.Atom.intern("text/uri-list", False), time)
        self._set_hover(self._hit(x, y))
        Gdk.drag_status(ctx, Gdk.DragAction.COPY if self.hover else 0, time)
        return True

    def _on_drag_leave(self, widget, ctx, time):
        self._set_hover(None)

    def _on_drag_drop(self, widget, ctx, x, y, time):
        target = self._hit(x, y)
        if target is None:
            Gtk.drag_finish(ctx, False, False, time)
            self.dismiss()
            return True
        self.hover = target
        if self.paths:
            Gtk.drag_finish(ctx, True, False, time)
            self._choose(target)
        else:
            self._dropping = True
            widget.drag_get_data(ctx, Gdk.Atom.intern("text/uri-list", False), time)
        return True

    def _on_drag_data(self, widget, ctx, x, y, data, info, time):
        uris = data.get_uris() or []
        paths = [Gio.File.new_for_uri(u).get_path() for u in uris]
        paths = [Path(p) for p in paths if p]
        if not self.paths:
            self.paths = paths
            if not paths:
                self.message = "Only local files can be converted"
            self._rebuild()
            self.area.queue_draw()
        if self._dropping:
            self._dropping = False
            target = self._hit(x, y) or self.hover
            if target is not None and self.paths:
                # Rebuilt slices: find the one under the drop point again.
                Gtk.drag_finish(ctx, True, False, time)
                self._choose(target)
            else:
                Gtk.drag_finish(ctx, False, False, time)
                self.dismiss()

    # ------------------------------------------------------------ pointer and keys

    def _grab(self):
        if getattr(self, "_map_handler", None):
            self.disconnect(self._map_handler)
            self._map_handler = None
        if not self.get_visible() or self._grabbed:
            return False
        window = self.get_window()
        seat = Gdk.Display.get_default().get_default_seat()
        status = seat.grab(window, Gdk.SeatCapabilities.ALL, True, None, None, None, None)
        if status == Gdk.GrabStatus.SUCCESS:
            self._grabbed = seat
        self.area.grab_focus()
        return False

    def _ungrab(self):
        if self._grabbed:
            self._grabbed.ungrab()
            self._grabbed = None

    def _on_motion(self, widget, event):
        if self.interactive:
            hit = self._hit(event.x, event.y)
            if hit:
                self._set_hover(hit)
        return True

    def _on_button(self, widget, event):
        if not self.interactive or event.button != 1:
            if event.button == 3:
                self.dismiss()
            return True
        inside = 0 <= event.x <= SIZE and 0 <= event.y <= SIZE
        hit = self._hit(event.x, event.y) if inside else None
        if hit:
            self._choose(hit)
        else:
            self.dismiss()
        return True

    def _on_key(self, widget, event):
        key = event.keyval
        name = Gdk.keyval_name(key) or ""
        keys = self.app.wheel_keys()
        if key == Gdk.KEY_Escape:
            self.dismiss()
        elif key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._choose(self.hover)
        elif key in (Gdk.KEY_Right, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Up) and self.slices:
            step = 1 if key in (Gdk.KEY_Right, Gdk.KEY_Down) else -1
            index = self.hover.index if self.hover else -step
            self._set_hover(self.slices[(index + step) % len(self.slices)])
        elif key in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            step = -1 if key == Gdk.KEY_ISO_Left_Tab else 1
            self.set_mode(MODES[(MODES.index(self.mode) + step) % 3])
        else:
            for mode, modifier in keys.items():
                if name.startswith({"Ctrl": "Control"}.get(modifier, modifier)):
                    self.set_mode(mode)
        return True

    # ------------------------------------------------------------ drawing

    def _on_draw(self, widget, cr):
        cr.set_operator(0)  # CLEAR
        cr.paint()
        cr.set_operator(2)  # OVER
        c = SIZE / 2
        outer = max((s.r1 for s in self.slices), default=SINGLE_OUTER)
        if self.round:
            cr.arc(c, c, outer + 6, 0, 2 * math.pi)
        else:
            cr.rectangle(0, 0, SIZE, SIZE)
        _rgba(cr, SURFACE)
        cr.fill_preserve()
        _rgba(cr, RIM)
        cr.set_line_width(1)
        cr.stroke()

        if not self.slices:
            cr.arc(c, c, SINGLE_OUTER - 4, 0, 2 * math.pi)
            cr.arc_negative(c, c, HUB + 4, 2 * math.pi, 0)
            _rgba(cr, SLICE_DIM)
            cr.fill()
        for s in self.slices:
            self._draw_slice(cr, c, s)
        self._draw_hub(cr, c)

    def _draw_slice(self, cr, c, s):
        hot = s is self.hover
        g0, g1 = GAP / s.r0, GAP / s.r1
        cr.new_path()
        cr.arc(c, c, s.r1 - 2, s.a0 + g1, s.a1 - g1)
        cr.arc_negative(c, c, s.r0 + 2, s.a1 - g0, s.a0 + g0)
        cr.close_path()
        _rgba(cr, ACCENT if hot else SLICE)
        cr.fill()
        mid_a = (s.a0 + s.a1) / 2
        mid_r = (s.r0 + s.r1) / 2
        arc_len = (s.a1 - s.a0) * mid_r - 2 * GAP
        width = min(arc_len, s.r1 - s.r0) - 8
        x, y = c + mid_r * math.cos(mid_a), c + mid_r * math.sin(mid_a)
        size = 10 if len(s.op.label) <= 6 else 9
        self._text(cr, s.op.label, x, y, size, TEXT_ON_ACCENT if hot else TEXT, bold=True,
                   max_width=max(width, 30))

    def _draw_hub(self, cr, c):
        cr.arc(c, c, HUB - 2, 0, 2 * math.pi)
        _rgba(cr, (0.115, 0.115, 0.13, 1))
        cr.fill()
        title = MODE_TITLES[self.mode]
        self._text(cr, title, c, c - 30, 12, ACCENT, bold=True)
        if self.hover is not None:
            body = self.hover.op.description or self.hover.op.label
        elif self.message:
            body = self.message
        elif self.paths:
            body = self.paths[0].name if len(self.paths) == 1 else f"{len(self.paths)} items"
        else:
            body = ""
        self._text(cr, body, c, c - 4, 9, TEXT, max_width=2 * HUB - 26, lines=2)
        keys = self.app.wheel_keys()
        hint = "  ".join(f"{keys[m]} {MODE_TITLES[m]}" for m in MODES if m != self.mode)
        if self.interactive:
            hint = "Tab switches  Esc closes"
        self._text(cr, hint, c, c + 34, 7.5, TEXT_MUTED, max_width=2 * HUB - 22, lines=2)

    def _text(self, cr, text, x, y, size, color, bold=False, max_width=None, lines=1):
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription.from_string(f"Sans {'Bold ' if bold else ''}{size}")
        layout.set_font_description(font)
        layout.set_alignment(Pango.Alignment.CENTER)
        if max_width:
            layout.set_width(int(max_width * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            if lines > 1:
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                layout.set_height(-lines)
        layout.set_text(text, -1)
        _, logical = layout.get_pixel_extents()
        left = x - (max_width / 2 if max_width else logical.width / 2)
        cr.move_to(left, y - logical.height / 2)
        _rgba(cr, color)
        PangoCairo.show_layout(cr, layout)
