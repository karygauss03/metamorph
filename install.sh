#!/bin/sh
# Install Metamorph for the current user (no root needed).
#   ./install.sh                 venv, launcher, menu entry, Files script (F4), start at login
#   ./install.sh --no-autostart  same, without starting at login
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN="$HOME/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
SCRIPTS="${XDG_DATA_HOME:-$HOME/.local/share}/nautilus/scripts"
ACCELS="${XDG_CONFIG_HOME:-$HOME/.config}/nautilus/scripts-accels"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
AUTOSTART=1
[ "${1:-}" = "--no-autostart" ] && AUTOSTART=0

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1 ($2)"; exit 1; }; }
need python3 "sudo apt install python3"
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" 2>/dev/null \
  || { echo "Missing GTK 3 bindings: sudo apt install python3-gi gir1.2-gtk-3.0"; exit 1; }
python3 -c "import Xlib" 2>/dev/null || { echo "Missing python-xlib: sudo apt install python3-xlib"; exit 1; }

echo "==> Python environment"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python /usr/bin/python3 --system-site-packages "$ROOT/.venv"
  else
    python3 -m venv --system-site-packages "$ROOT/.venv"
  fi
fi
if command -v uv >/dev/null 2>&1; then
  uv pip install --quiet --python "$ROOT/.venv/bin/python" -r "$ROOT/requirements.txt"
else
  "$ROOT/.venv/bin/python" -m pip install --quiet -r "$ROOT/requirements.txt"
fi

echo "==> Launcher, icon and menu entry"
mkdir -p "$BIN" "$APPS" "$ICONS"
chmod +x "$ROOT/bin/metamorph"
ln -sf "$ROOT/bin/metamorph" "$BIN/metamorph"
cp "$ROOT/data/metamorph.svg" "$ICONS/metamorph.svg"
# No MimeType= on purpose: GNOME falls back to apps in ~/.local for any type
# without an explicit default, so registering types made Metamorph the app that
# opens photos, music and videos on double-click.
cat > "$APPS/io.github.metamorph.Metamorph.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Metamorph
GenericName=File Converter
Comment=Drag a file, hold a key, drop it on a format
Exec=$BIN/metamorph open %F
Icon=metamorph
Terminal=false
Categories=Utility;GTK;
Keywords=convert;converter;image;video;audio;pdf;compress;
StartupNotify=false
EOF
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -q "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" 2>/dev/null || true

echo "==> Files (Nautilus) script: right-click > Scripts > Metamorph, or F4"
mkdir -p "$SCRIPTS" "$(dirname "$ACCELS")"
cat > "$SCRIPTS/Metamorph" <<EOF
#!/bin/sh
exec "$BIN/metamorph" open "\$@"
EOF
chmod +x "$SCRIPTS/Metamorph"
if ! grep -qs " Metamorph\$" "$ACCELS"; then
  printf 'F4 Metamorph\n' >> "$ACCELS"
fi

if [ "$AUTOSTART" = 1 ]; then
  echo "==> Start at login"
  mkdir -p "$AUTOSTART_DIR"
  cat > "$AUTOSTART_DIR/metamorph.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Metamorph
Exec=$BIN/metamorph --background
Icon=metamorph
X-GNOME-Autostart-enabled=true
NoDisplay=true
Comment=Drag-and-drop file converter
EOF
fi

echo "==> Starting the background watcher"
"$BIN/metamorph" quit >/dev/null 2>&1 || true
sleep 1
nohup "$BIN/metamorph" --background >/dev/null 2>&1 &
"$ROOT/.venv/bin/python" -m metamorph doctor | tail -1
echo
echo "Done. Drag any file and hold Shift (convert), Alt (tools) or Ctrl (actions)."
echo "Restart Files once for the F4 shortcut: nautilus -q"
