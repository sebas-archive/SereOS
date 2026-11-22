#!/usr/bin/env python3
"""Captura la ventana Acerca de (F5) para comprobar la fila Audio (audio_detail)."""
import sys, time
from pathlib import Path
ROOT = Path("/home/t1an/Descargas/sereos02")
OS = ROOT / "sistema operativo"
TREE = ROOT / "build/qa_audio/tree/sistema operativo"
OUT = ROOT / "build/qa_audio/evidence"
sys.path.insert(0, str(OS / "tools"))
from qemu_ctrl import QemuController  # noqa: E402

def run(tag, extra):
    wd = OUT / f"vm_about_{tag}"
    vm = QemuController(TREE/"sereos.iso", wd, use_kvm=False, extra_args=extra)
    try:
        vm.start()
        vm.wait_marker("GUI_READY", 240)
        since = vm.marker_offset()
        vm.press("f5")
        vm.wait_marker_prefix("APP_OPEN:about", 60, since)
        time.sleep(2.5)
        shot = vm.screendump(OUT / f"about_{tag}.ppm")
        print(tag, "captura:", shot)
        print("\n".join(l for l in vm.serial_text().splitlines()
                        if "Audio" in l or "AUDIO" in l))
    finally:
        vm.stop()

run("sb16", ["-audiodev", "wav,id=snd0,path=/dev/null",
             "-device", "sb16,audiodev=snd0"])
run("noaudio", [])
