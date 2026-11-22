#!/usr/bin/env python3
"""Verificacion visual de la UI de SereOS (menú, About, botones de ventana).

Usa la ISO de prueba enlazada con un stub de audio_detail() mientras el
modulo de audio aun no publica la funcion real.
"""
import sys, time
from pathlib import Path

OS_DIR = Path("/home/t1an/Descargas/sereos02/sistema operativo")
sys.path.insert(0, str(OS_DIR / "tools"))
from qemu_ctrl import QemuController  # noqa: E402

OUT = Path("/home/t1an/Descargas/sereos02/docs/screenshots/raw/ui-verify")
ISO = OS_DIR / "sereos.iso"
S = 1024.0 / 1024.0

def shot(vm, name):
    vm.screendump(OUT / f"{name}.ppm")
    print(f"[shot] {name}", flush=True)

def move(vm, dx, dy, step=40, pause=0.02):
    sx = 1 if dx >= 0 else -1
    sy = 1 if dy >= 0 else -1
    dx, dy = abs(int(dx)), abs(int(dy))
    while dx > 0 or dy > 0:
        cx = min(dx, step) * sx
        cy = min(dy, step) * sy
        vm.mouse_move_rel(cx, cy)
        dx -= abs(cx); dy -= abs(cy)
        time.sleep(pause)
    time.sleep(0.15)

def click(vm, x=None, y=None):
    if x is not None:
        move(vm, x - click.px, y - click.py)
        click.px, click.py = x, y
    vm.mouse_button("left", True); time.sleep(0.08)
    vm.mouse_button("left", False); time.sleep(0.45)
click.px, click.py = 512, 384

def wait_app(vm, app, since):
    hit = vm.wait_marker(f"APP_OPEN:{app}", 10, since)
    print("  ", hit.line, flush=True)
    return hit

def main():
    fails = []
    with QemuController(ISO, OUT / "run-real", use_kvm=None) as vm:
        vm.wait_marker("GUI_READY", 60)
        time.sleep(1.0)
        shot(vm, "01-desktop")

        # --- menu del logo -------------------------------------------------
        move(vm, -700, -500)          # cursor a (0,0)
        click.px, click.py = 0, 0
        click(vm, 97, 18)             # boton de menu: abre el menu
        time.sleep(0.4)
        shot(vm, "02-menu")

        # --- About desde el menu (insignia i + botones a la derecha) -------
        since = vm.marker_offset()
        click(vm, 199, 101)           # fila "Acerca de"
        wait_app(vm, "about", since)
        time.sleep(0.6)
        shot(vm, "04-about")

        # --- cerrar About con Alt+W ---------------------------------------
        since = vm.marker_offset()
        vm.sendkey("alt-w"); time.sleep(0.6)
        try:
            vm.wait_marker("APP_CLOSE:about", 5, since)
            print("   APP_CLOSE:about", flush=True)
        except Exception as exc:
            fails.append(f"Alt+W sobre About: {exc}")

        # --- resto de apps: mismos botones a la derecha -------------------
        for key, app, name in (("f1", "files", "05-files"),
                               ("f2", "terminal", "06-terminal"),
                               ("f3", "monitor", "07-monitor"),
                               ("f5", "about", "08-about2")):
            since = vm.marker_offset()
            vm.sendkey(key)
            wait_app(vm, app, since)
            time.sleep(0.7)
            shot(vm, name)

        # --- PAC-MAN: maximizar con el boton (glifo restaurar) ------------
        for app in ("about", "monitor", "terminal", "files"):
            since = vm.marker_offset()
            vm.sendkey("alt-w")
            try:
                vm.wait_marker(f"APP_CLOSE:{app}", 4, since)
            except Exception:
                pass
            time.sleep(0.2)
        since = vm.marker_offset()
        vm.sendkey("f4")
        wait_app(vm, "game", since)
        time.sleep(1.0)
        shot(vm, "09-game")
        # ventana del juego tras el cascade: x=72, y=86, w=880
        click(vm, 72 + 880 - 14 - 18, 86 + 34 // 2)   # boton maximizar/restaurar
        time.sleep(0.9)
        shot(vm, "10-game-maximized")
        click(vm, 1024 - 14 - 18, 30 + 34 // 2)       # restaurar
        time.sleep(0.9)
        shot(vm, "11-game-restored")
        click(vm, 72 + 880 - 14, 86 + 34 // 2)        # boton cerrar
        time.sleep(0.8)
        shot(vm, "12-close-click")
        try:
            hits = [h for h in vm.serial_lines() if h.startswith("APP_CLOSE:game")]
            print("   APP_CLOSE:game" if hits else "   (sin APP_CLOSE:game)")
            if not hits:
                fails.append("boton cerrar no genero APP_CLOSE:game")
        except Exception as exc:
            fails.append(f"close game: {exc}")

        fatals = vm.fatal_markers()
        print("serial tail:\n" + vm.serial_tail(12), flush=True)
        if fatals:
            fails.append("PANICO/EXCEPCION: " + "; ".join(fatals))
        print("FAILS:", fails if fails else "ninguno")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
