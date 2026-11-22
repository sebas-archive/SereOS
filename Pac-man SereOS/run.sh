#!/bin/sh
# run.sh - lanzador Linux de PAC-MAN SereOS
#
# Verifica SDL2, construye si hace falta y ejecuta el juego.
# Uso: ./run.sh [opciones]
#   --smoke N        ejecuta N frames sin ventana (requiere SDL_VIDEODRIVER=dummy)
#   --screenshot R   guarda una captura PPM del ultimo frame
#   --scene S        QA: attract|menu|settings|play|pause|gameover|victory|frightened|gamestart|ghostcapture|death
#   F11              pantalla completa
#
# Capturas sin display (QA):
#   SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./run.sh \
#       --smoke 4 --scene pause --screenshot /tmp/pause.ppm
# Record persistente: $XDG_DATA_HOME/pacman-sereos/record.txt
#   (fallback ~/.local/share/pacman-sereos/record.txt)
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BIN="$ROOT/build/pacman-sereos"

have_sdl=0
if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists sdl2 2>/dev/null; then
    have_sdl=1
elif command -v sdl2-config >/dev/null 2>&1; then
    have_sdl=1
fi

if [ "$have_sdl" -eq 0 ]; then
    echo "ERROR: no se encontro SDL2 (pkg-config sdl2 o sdl2-config)." >&2
    echo "  CachyOS/Arch:  sudo pacman -S --needed sdl2" >&2
    echo "  Debian/Ubuntu: sudo apt install libsdl2-dev" >&2
    exit 1
fi

if [ ! -x "$BIN" ]; then
    echo "[run.sh] compilando PAC-MAN SereOS..."
    if ! make -C "$ROOT" linux; then
        echo "ERROR: fallo la compilacion (ver mensajes de make)." >&2
        exit 1
    fi
fi

if [ ! -x "$BIN" ]; then
    echo "ERROR: no existe $BIN tras compilar." >&2
    exit 1
fi

echo "[run.sh] PAC-MAN SereOS -> $BIN"
exec "$BIN" "$@"
