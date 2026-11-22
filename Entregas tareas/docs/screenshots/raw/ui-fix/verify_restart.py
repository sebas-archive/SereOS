#!/usr/bin/env python3
"""Menu -> Reiniciar: captura la pantalla "Reiniciando..." y confirma reset."""
import sys, time
from pathlib import Path
OS_DIR = Path("/home/t1an/Descargas/sereos02/sistema operativo")
sys.path.insert(0, str(OS_DIR / "tools"))
from qemu_ctrl import QemuController
OUT = Path("/home/t1an/Descargas/sereos02/docs/screenshots/raw/ui-fix")
ISO = OS_DIR / "sereos.iso"

def move(vm, dx, dy, step=40):
    sx = 1 if dx >= 0 else -1; sy = 1 if dy >= 0 else -1
    dx, dy = abs(int(dx)), abs(int(dy))
    while dx > 0 or dy > 0:
        cx = min(dx, step) * sx; cy = min(dy, step) * sy
        vm.mouse_move_rel(cx, cy); dx -= abs(cx); dy -= abs(cy)
        time.sleep(0.02)
    time.sleep(0.2)

def click(vm):
    vm.mouse_button("left", True); time.sleep(0.08)
    vm.mouse_button("left", False); time.sleep(0.4)

with QemuController(ISO, OUT / "run-restart", use_kvm=None) as vm:
    vm.wait_marker("GUI_READY", 60); time.sleep(1.0)
    move(vm, -700, -500)          # (0,0)
    move(vm, 97, 18); click(vm)   # menu del logo (item Reiniciar en y=259)
    time.sleep(0.3)
    vm.screendump(OUT / "05-menu-Reiniciar.ppm")
    move(vm, 199 - 97, 259 - 18); click(vm)
    print("click Reiniciar", flush=True)
    time.sleep(0.30)
    try:
        vm.screendump(OUT / "06-reiniciando.ppm")
        print("shot reiniciando", flush=True)
    except Exception as exc:
        print("sin captura:", exc, flush=True)
    time.sleep(2.5)
    print("qemu sigue vivo:", vm.is_running(), flush=True)
    print("serial tail:\n" + vm.serial_tail(12), flush=True)
    print("SEREOS_RESTART:", vm.has_marker("SEREOS_RESTART"), flush=True)
