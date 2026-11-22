#!/usr/bin/env python3
"""Verifica el acceso About de la topnav (dock oculto) con el icono i.

Raton: se aparca el cursor en una zona vacia, se mueve al objetivo y se
corrige con la posicion real detectada en el screendump (bucle cerrado).
"""
import sys, time
from pathlib import Path
from PIL import Image

OS_DIR = Path("/home/t1an/Descargas/sereos02/sistema operativo")
sys.path.insert(0, str(OS_DIR / "tools"))
from qemu_ctrl import QemuController
OUT = Path("/home/t1an/Descargas/sereos02/docs/screenshots/raw/ui-fix")
ISO = OS_DIR / "sereos.iso"

def shot(vm, name):
    p = vm.screendump(OUT / f"{name}.ppm")
    return Image.open(p).convert("RGB")

def move(vm, dx, dy, step=20, pause=0.05):
    sx = 1 if dx >= 0 else -1; sy = 1 if dy >= 0 else -1
    dx, dy = abs(int(dx)), abs(int(dy))
    while dx > 0 or dy > 0:
        cx = min(dx, step) * sx; cy = min(dy, step) * sy
        vm.mouse_move_rel(cx, cy); dx -= abs(cx); dy -= abs(cy)
        time.sleep(pause)
    time.sleep(0.25)

def find_cursor(img, region):
    """bbox del relleno claro (theme.text) del cursor dentro de region."""
    x0, y0, x1, y1 = region
    px = img.load()
    pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1)
           if px[x, y][0] > 225 and px[x, y][1] > 225 and px[x, y][2] > 225]
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    # el primer pixel de relleno '*' esta en (1,1) del sprite: la punta real
    # (hotspot) es ese pixel menos (1,1)
    tip = min(pts, key=lambda p: (p[1], p[0]))
    return (tip[0] - 1, tip[1] - 1)

def move_to(vm, tx, ty, cur):
    for _ in range(4):
        dx, dy = tx - cur[0], ty - cur[1]
        if abs(dx) <= 2 and abs(dy) <= 2:
            break
        move(vm, dx, dy)
        cur = find_cursor(shot(vm, "tmp-cursor"),
                          (tx - 40, ty - 40, tx + 40, ty + 40))
        if cur is None:
            print("  cursor no detectado cerca del objetivo", flush=True)
            return False
    print(f"  cursor en {cur} (objetivo {tx},{ty})", flush=True)
    return True

def click(vm):
    vm.mouse_button("left", True); time.sleep(0.08)
    vm.mouse_button("left", False); time.sleep(0.9)

with QemuController(ISO, OUT / "run-topnav", use_kvm=None) as vm:
    vm.wait_marker("GUI_READY", 60); time.sleep(1.0)
    vm.sendkey("f5"); vm.wait_marker("APP_OPEN:about", 10); time.sleep(0.8)
    # aparcar en el wallpaper liso de la esquina inferior izquierda
    move(vm, -502, 316)
    img = shot(vm, "tmp-park")
    tip = find_cursor(img, (0, 675, 80, 730))
    print("  cursor aparcado en", tip, flush=True)
    # About cascade 0: el boton maximizar esta en (788,113)
    be = (788, 113)
    if tip is not None and move_to(vm, be[0], be[1], tip):
        click(vm)
    time.sleep(0.8)
    shot(vm, "04-about-max-topnav-i")
    print("  panicos:", vm.fatal_markers(), flush=True)
