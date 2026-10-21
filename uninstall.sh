#!/bin/sh
# Remove everything install.sh added (the project folder and its .venv are left alone).
set -u
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
"$HOME/.local/bin/metamorph" quit >/dev/null 2>&1 || true
rm -f "$HOME/.local/bin/metamorph" \
      "$DATA/applications/io.github.metamorph.Metamorph.desktop" \
      "$DATA/icons/hicolor/scalable/apps/metamorph.svg" \
      "$DATA/nautilus/scripts/Metamorph" \
      "$CONF/autostart/metamorph.desktop"
if [ -f "$CONF/nautilus/scripts-accels" ]; then
  sed -i '/ Metamorph$/d' "$CONF/nautilus/scripts-accels"
fi
update-desktop-database "$DATA/applications" 2>/dev/null || true
echo "Metamorph removed. Settings remain in $CONF/metamorph (delete it to reset)."
