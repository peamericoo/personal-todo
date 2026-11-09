#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-/usr/bin/python3}
"$PYTHON" -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' || { echo 'Instale python3-gi e gir1.2-gtk-3.0.' >&2; exit 1; }
APPDIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPDIR"
# The desktop entry contains only paths, never the access token itself.
cat > "$APPDIR/personal-todo.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Personal To-Do
Comment=Seu espaço para organizar tarefas
Exec="$HERE/start-linux.sh"
Icon=$HERE/app-icon.png
Terminal=false
Categories=Office;ProjectManagement;
StartupNotify=true
StartupWMClass=personal-todo
EOF
chmod +x "$HERE/start-linux.sh" "$HERE/reminders-linux.sh"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
mkdir -p "$AUTOSTART"
cat > "$AUTOSTART/personal-todo-reminders.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Personal To-Do lembretes
Exec="$HERE/reminders-linux.sh"
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
"$HERE/reminders-linux.sh" >/dev/null 2>&1 &
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPDIR" || true
printf 'Instalado no menu de aplicativos: Personal To-Do\n'
