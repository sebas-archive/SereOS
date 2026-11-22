#!/usr/bin/env python3
import sys, time
from pathlib import Path
sys.path.insert(0, "/home/t1an/Descargas/sereos02/sistema operativo/tools")
from qemu_ctrl import QemuController, QemuError, MarkerTimeout
OS = Path("/home/t1an/Descargas/sereos02/sistema operativo")
OUT = Path("/home/t1an/Descargas/sereos02/build/qa_audio")
wav = str(OUT / "baseline.wav")
try: Path(wav).unlink()
except FileNotFoundError: pass
vm = QemuController(OS / "sereos.iso", OUT / "vm_baseline", use_kvm=False,
                    extra_args=["-audiodev", f"wav,id=snd0,path={wav}",
                                "-device", "sb16,audiodev=snd0"])
try:
    vm.start(); print("KVM:", vm.used_kvm)
    vm.wait_marker("GUI_READY", 180); print("GUI_READY")
    vm.press("f4")
    off = vm.marker_offset()
    try:
        vm.wait_marker("GAME_START", 30); print("GAME_START directo")
    except MarkerTimeout:
        print("no GAME_START en menu; envio ret")
        off = vm.marker_offset()
        try:
            vm.press("ret"); vm.wait_marker("GAME_START", 15, since=off); print("GAME_START tras ret")
        except MarkerTimeout: print("sin GAME_START")
    for _ in range(10):
        vm.press("left", delay=0.2); vm.press("up", delay=0.2)
    time.sleep(5)
    print("serial tail:\n" + vm.serial_tail(30))
    print("fatales:", vm.fatal_markers())
finally:
    vm.stop()
    print("WAV:", Path(wav).stat().st_size if Path(wav).exists() else "no existe")
