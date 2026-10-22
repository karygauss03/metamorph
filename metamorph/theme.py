"""The Metamorph palette, shared by the cairo-drawn UI and the GTK stylesheet.

Same values as the website (site/assets/css/tokens.css): navy surfaces, one cyan
primary, violet as the only accent, green for finished jobs. Keep the two in sync.
"""

NAVY_975 = "#070a12"
NAVY_950 = "#0b0f19"
NAVY_900 = "#0f1524"
NAVY_850 = "#131a2c"
NAVY_800 = "#182136"
NAVY_750 = "#1e2942"
NAVY_700 = "#2a3754"
NAVY_600 = "#3a4a6b"
INK_50 = "#eef2f8"
INK_300 = "#a9b5c8"
INK_400 = "#8e9cb3"
CYAN_300 = "#7af8fe"
CYAN_400 = "#00f2fe"
CYAN_500 = "#00d4de"
CYAN_950 = "#03161c"
VIOLET_300 = "#c9a2f0"
VIOLET_500 = "#9d4edd"
GREEN_300 = "#6ee7b7"
GREEN_500 = "#10b981"
RED_300 = "#fca5a5"


def rgba(hex_color, alpha=1.0):
    """'#rrggbb' -> (r, g, b, a) floats for cairo."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, alpha)


# ---- cairo colours for the wheel and the crop editor
SURFACE = rgba(NAVY_950, 0.985)
RIM = (1, 1, 1, 0.10)
SLICE = rgba(NAVY_800)
SLICE_DIM = rgba(NAVY_900)
HUB = rgba(NAVY_900)
ACCENT = rgba(CYAN_400)
TEXT = rgba(INK_50)
TEXT_MUTED = rgba(INK_300)
TEXT_ON_ACCENT = rgba(CYAN_950)
CANVAS = rgba(NAVY_975)
SHADE = rgba("#02050c", 0.58)

# ---- GTK 3 stylesheet for Metamorph's own windows (class "metamorph").
# Scoped so the rest of the desktop keeps its theme.
CSS = f"""
window.metamorph, window.metamorph.background {{
  background-color: {NAVY_950};
  color: {INK_50};
}}
window.metamorph headerbar {{
  background-image: none;
  background-color: {NAVY_850};
  border-color: {NAVY_700};
  box-shadow: none;
  color: {INK_50};
}}
window.metamorph headerbar .title {{ color: {INK_50}; }}
window.metamorph headerbar .subtitle,
window.metamorph label.dim-label {{ color: {INK_300}; opacity: 1; }}
window.metamorph label {{ color: {INK_50}; }}
window.metamorph label.dim-label {{ color: {INK_300}; }}

window.metamorph button {{
  background-image: none;
  background-color: {NAVY_800};
  border: 1px solid {NAVY_700};
  border-radius: 9px;
  box-shadow: none;
  text-shadow: none;
  -gtk-icon-shadow: none;
  color: {INK_50};
}}
window.metamorph button label {{ color: inherit; }}
window.metamorph button:hover {{ background-color: {NAVY_750}; border-color: {NAVY_600}; }}
window.metamorph button:active,
window.metamorph button:checked {{ background-color: {NAVY_700}; }}
window.metamorph button:disabled {{ background-color: {NAVY_900}; color: {INK_400}; border-color: {NAVY_800}; }}
window.metamorph button:disabled label {{ color: {INK_400}; }}
window.metamorph button.flat {{ background-color: transparent; border-color: transparent; }}
window.metamorph button.flat:hover {{ background-color: {NAVY_800}; }}
window.metamorph button.suggested-action {{
  background-color: {CYAN_400};
  border-color: {CYAN_400};
  color: {CYAN_950};
  font-weight: bold;
}}
window.metamorph button.suggested-action label {{ color: {CYAN_950}; }}
window.metamorph button.suggested-action:hover {{ background-color: {CYAN_300}; border-color: {CYAN_300}; }}
window.metamorph button.suggested-action:active {{ background-color: {CYAN_500}; border-color: {CYAN_500}; }}
window.metamorph button.suggested-action:disabled {{ background-color: {NAVY_800}; border-color: {NAVY_700}; color: {INK_400}; }}
window.metamorph button.suggested-action:disabled label {{ color: {INK_400}; }}
window.metamorph *:focus {{ outline-color: {CYAN_300}; }}

window.metamorph entry,
window.metamorph spinbutton {{
  background-image: none;
  background-color: {NAVY_975};
  border: 1px solid {NAVY_700};
  border-radius: 9px;
  box-shadow: none;
  color: {INK_50};
  caret-color: {CYAN_400};
}}
window.metamorph entry:focus,
window.metamorph spinbutton:focus {{ border-color: {CYAN_400}; box-shadow: inset 0 0 0 1px {CYAN_400}; }}
window.metamorph spinbutton entry {{ border: none; box-shadow: none; background-color: transparent; }}
window.metamorph spinbutton button {{ border-radius: 0; border-width: 0 0 0 1px; background-color: {NAVY_850}; }}
window.metamorph entry selection,
window.metamorph label selection {{ background-color: {CYAN_400}; color: {CYAN_950}; }}

window.metamorph switch {{
  background-image: none;
  background-color: {NAVY_700};
  border: 1px solid {NAVY_600};
  border-radius: 14px;
  box-shadow: none;
}}
window.metamorph switch:checked {{ background-color: {CYAN_400}; border-color: {CYAN_400}; }}
window.metamorph switch slider {{
  background-image: none;
  background-color: {INK_50};
  border: none;
  border-radius: 12px;
  box-shadow: none;
}}

window.metamorph list,
window.metamorph list row {{ background-color: {NAVY_900}; color: {INK_50}; }}
window.metamorph list row:hover {{ background-color: {NAVY_850}; }}
window.metamorph list.frame,
window.metamorph frame > border {{ border: 1px solid {NAVY_700}; border-radius: 12px; }}
window.metamorph list separator,
window.metamorph separator {{ background-color: {NAVY_700}; }}

window.metamorph menu,
window.metamorph .menu,
window.metamorph popover {{ background-color: {NAVY_850}; color: {INK_50}; border-color: {NAVY_700}; }}
window.metamorph menuitem:hover {{ background-color: {NAVY_750}; }}

window.metamorph progressbar trough {{ background-image: none; background-color: {NAVY_750}; border: none; min-height: 4px; }}
window.metamorph progressbar progress {{
  background-image: linear-gradient(to right, {CYAN_400}, {VIOLET_500});
  border: none;
  min-height: 4px;
}}
window.metamorph scrollbar slider {{ background-color: {NAVY_600}; }}

.metamorph-error {{ color: {RED_300}; }}
.metamorph-success {{ color: {GREEN_300}; }}
.metamorph-toast {{ background-color: {NAVY_850}; border: 1px solid {NAVY_700}; }}
.metamorph-card {{ padding: 4px 2px; }}
.metamorph-card-title {{ font-weight: bold; }}
.metamorph-dropzone {{
  border: 2px dashed alpha({CYAN_400}, 0.35);
  border-radius: 14px;
  background-color: {NAVY_975};
}}
.metamorph-shelf {{ background-color: {NAVY_850}; border: 1px solid {NAVY_700}; }}
.metamorph-shelf-title {{ font-weight: bold; color: {INK_300}; }}
.metamorph-shelf-item {{ padding: 6px; }}
"""
