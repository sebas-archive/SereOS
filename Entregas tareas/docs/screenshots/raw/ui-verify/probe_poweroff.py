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
        cx=min(dx,step)*sx; cy=min(dy,step)*sy
        vm.mouse_move_rel(cx,cy); dx-=abs(cx); dy-=abs(cy); time.sleep(0.02)
    time.sleep(0.15)

def click(vm):
    vm.mouse_button("left", True); time.sleep(0.1)
    vm.mouse_button("left", False); time.sleep(0.5)

with QemuController(ISO, OUT / "run-po-real", use_kvm=None) as vm:
    vm.wait_marker("GUI_READY", 60); time.sleep(1.0)
    move(vm, -700, -500)
    move(vm, 97, 18); click(vm)          # abrir menu
    time.sleep(0.3)
    vm.screendump(OUT / "po-01-menu.ppm")
    move(vm, 199-97, 289-18); click(vm)  # Apagar
    print("click Apagar enviado", flush=True)
    time.sleep(0.35)
    try:
        vm.screendump(OUT / "po-02-apagando.ppm")
        print("shot apagando", flush=True)
    except Exception as exc:
        print("sin captura de apagado:", exc, flush=True)
    time.sleep(2.5)
    running = vm.is_running()
    print("qemu sigue vivo:", running, flush=True)
    if running:
        vm.screendump(OUT / "po-02-apagando.ppm")
    print("serial tail:\n" + vm.serial_tail(10), flush=True)
    print("SEREOS_POWEROFF:", vm.has_marker("SEREOS_POWEROFF"), flush=True)
