#!/usr/bin/env python3
"""Verificacion de la correccion UI: logo S en contenido, i solo en accesos."""
import sys, time
from pathlib import Path

OS_DIR = Path("/home/t1an/Descargas/sereos02/sistema operativo")
sys.path.insert(0, str(OS_DIR / "tools"))
from qemu_ctrl import QemuController  # noqa: E402

OUT = Path("/home/t1an/Descargas/sereos02/docs/screenshots/raw/ui-fix")
ISO = OS_DIR / "sereos.iso"

def shot(vm, name):
    vm.screendump(OUT / f"{name}.ppm"); print("[shot]", name, flush=True)

def move(vm, dx, dy, step=40):
    sx = 1 if dx >= 0 else -1; sy = 1 if dy >= 0 else -1
    dx, dy = abs(int(dx)), abs(int(dy))
    while dx > 0 or dy > 0:
        cx = min(dx, step) * sx; cy = min(dy, step) * sy
        vm.mouse_move_rel(cx, cy); dx -= abs(cx); dy -= abs(cy)
        time.sleep(0.02)
    time.sleep(0.15)

def click(vm):
    vm.mouse_button("left", True); time.sleep(0.08)
    vm.mouse_button("left", False); time.sleep(0.45)

with QemuController(ISO, OUT / "run", use_kvm=None) as vm:
    vm.wait_marker("GUI_READY", 60); time.sleep(1.0)
    shot(vm, "01-escritorio-topbar-S-dock-i")
    # menu abierto (i en la fila Acerca de, Apagar visible)
    move(vm, -700, -500)          # cursor a (0,0)
    move(vm, 97, 18); click(vm)
    time.sleep(0.3)
    shot(vm, "02-menu-i-acceso-y-Apagar")
    # About desde el menu -> contenido con logo S
    since = vm.marker_offset()
    move(vm, 199 - 97, 101 - 18); click(vm)
    vm.wait_marker("APP_OPEN:about", 10, since)
    time.sleep(0.7)
    shot(vm, "03-about-logo-S-audio-botones-derecha")
    print("serial tail:", vm.serial_tail(4), flush=True)
    print("panicos:", vm.fatal_markers(), flush=True)
