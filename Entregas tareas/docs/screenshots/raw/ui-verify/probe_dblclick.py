#!/usr/bin/env python3
"""Comprueba doble clic en la barra de titulo: maximiza y restaura."""
import sys, time
from pathlib import Path
OS_DIR = Path("/home/t1an/Descargas/sereos02/sistema operativo")
sys.path.insert(0, str(OS_DIR / "tools"))
from qemu_ctrl import QemuController
OUT = Path("/home/t1an/Descargas/sereos02/docs/screenshots/raw/ui-verify")
ISO = OS_DIR / "sereos.iso"

def move(vm, dx, dy, step=40):
    sx = 1 if dx >= 0 else -1; sy = 1 if dy >= 0 else -1
    dx, dy = abs(int(dx)), abs(int(dy))
    while dx > 0 or dy > 0:
        cx = min(dx, step) * sx; cy = min(dy, step) * sy
        vm.mouse_move_rel(cx, cy); dx -= abs(cx); dy -= abs(cy)
        time.sleep(0.02)
    time.sleep(0.2)

def dbl(vm):
    vm.mouse_button("left", True); time.sleep(0.06)
    vm.mouse_button("left", False); time.sleep(0.15)
    vm.mouse_button("left", True); time.sleep(0.06)
    vm.mouse_button("left", False)
    time.sleep(0.9)

with QemuController(ISO, OUT / "run-dbl", use_kvm=None) as vm:
    vm.wait_marker("GUI_READY", 60); time.sleep(1.0)
    vm.sendkey("f1"); vm.wait_marker("APP_OPEN:files", 10); time.sleep(0.8)
    move(vm, -600, -500)
    move(vm, 480, 82)      # barra de titulo (ventana Archivos: y=66..100)
    dbl(vm)
    vm.screendump(OUT / "13-dblclick-max.ppm")
    time.sleep(0.4)
    move(vm, 0, -35)       # barra de titulo de la ventana maximizada (y=47)
    dbl(vm)                # doble clic -> restaura
    vm.screendump(OUT / "14-dblclick-restore.ppm")
    print("capturas listas; panicos:", vm.fatal_markers(), flush=True)
