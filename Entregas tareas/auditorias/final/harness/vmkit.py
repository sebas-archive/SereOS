#!/usr/bin/env python3
"""vmkit.py - utilidades de verificacion de SereOS (verifier, task-4).

Arranca sereos.iso en QEMU a traves de ``sistema operativo/tools/qemu_ctrl.py``,
permite teclado, raton PS/2 relativo (HMP mouse_move/mouse_button), capturas
PPM->PNG y lectura del log serie. Todo lo escribe en audit/final/evidence/.

NO modifica fuentes: solo audit/final/.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path("/home/t1an/Descargas/sereos02")
OS = ROOT / "sistema operativo"
EVID = ROOT / "audit" / "final" / "evidence"
EVID.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(OS / "tools"))
import qemu_ctrl  # noqa: E402
import ppm_to_png  # noqa: E402

QemuController = qemu_ctrl.QemuController
QemuError = qemu_ctrl.QemuError
MarkerTimeout = qemu_ctrl.MarkerTimeout


class Vm:
    """QEMU + helpers; el cursor del guest empieza en (512,384) (drivers/input.c)."""

    START_X = 512
    START_Y = 384

    def __init__(self, name: str, extra_args=None, iso: Path | None = None):
        self.name = name
        self.workdir = EVID / f"run-{name}"
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.shots: list[dict] = []
        self.iso = iso or (OS / "sereos.iso")
        self.vm = QemuController(
            iso=self.iso,
            workdir=self.workdir,
            display="none",
            use_kvm=False,             # /dev/kvm no disponible (TCG)
            extra_args=list(extra_args or []),
        )
        self.cx = self.START_X
        self.cy = self.START_Y

    # -- ciclo de vida ------------------------------------------------------
    def start(self, gui_timeout: float = 120.0) -> "Vm":
        self.vm.start()
        self.vm.wait_marker("GUI_READY", gui_timeout)
        return self

    def stop(self) -> None:
        try:
            self.vm.stop(timeout=5.0)
        except Exception:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # -- serie --------------------------------------------------------------
    def wait(self, marker: str, timeout: float = 30.0):
        return self.vm.wait_marker(marker, timeout)

    def has(self, marker: str) -> bool:
        return self.vm.has_marker(marker)

    def save_serial(self, filename: str = "serial.log") -> Path:
        dest = self.workdir / filename
        dest.write_text(self.vm.serial_text(), encoding="utf-8", errors="replace")
        return dest

    def fatals(self):
        return self.vm.fatal_markers()

    # -- teclado ------------------------------------------------------------
    def key(self, combo: str, settle: float = 0.2) -> None:
        self.vm.press(combo, delay=settle)

    def type_line(self, text: str, settle: float = 0.4) -> None:
        self.vm.type_line(text, settle=settle)

    # -- raton PS/2 relativo ------------------------------------------------
    def _rel(self, dx: int, dy: int) -> None:
        # QEMU HMP mouse_move: enteros, el guest aplica 1:1 (drivers/mouse.c).
        self.vm.monitor_cmd(f"mouse_move {int(dx)} {int(dy)}")
        self.cx = max(0, min(1023, self.cx + int(dx)))
        self.cy = max(0, min(767, self.cy + int(dy)))

    def move_to(self, x: int, y: int, chunk: int = 180, pause: float = 0.025) -> None:
        x = max(0, min(1023, int(x)))
        y = max(0, min(767, int(y)))
        while (self.cx, self.cy) != (x, y):
            dx = max(-chunk, min(chunk, x - self.cx))
            dy = max(-chunk, min(chunk, y - self.cy))
            self._rel(dx, dy)
            time.sleep(pause)

    def click_at(self, x: int, y: int, settle: float = 0.45) -> None:
        self.move_to(x, y)
        time.sleep(0.10)
        self.vm.monitor_cmd("mouse_button 1")
        time.sleep(0.08)
        self.vm.monitor_cmd("mouse_button 0")
        time.sleep(settle)

    def double_click_at(self, x: int, y: int, settle: float = 0.5) -> None:
        self.move_to(x, y)
        time.sleep(0.1)
        for _ in range(2):
            self.vm.monitor_cmd("mouse_button 1")
            time.sleep(0.05)
            self.vm.monitor_cmd("mouse_button 0")
            time.sleep(0.10)
        time.sleep(settle)

    # -- capturas -----------------------------------------------------------
    def shot(self, name: str) -> Path:
        """Captura PPM+PNG en evidence/run-<name>/<name>.{ppm,png}."""
        ppmp = self.workdir / f"{name}.ppm"
        self.vm.screendump(ppmp)
        img = ppm_to_png.read_ppm(ppmp)
        png = self.workdir / f"{name}.png"
        ppm_to_png.write_png(png, img)
        st = ppm_to_png.analyze(img)
        self.shots.append({
            "name": name, "ppm": str(ppmp), "png": str(png),
            "width": st.width, "height": st.height, "distinct_colors": st.distinct_colors,
            "non_black_ratio": round(st.non_black_ratio, 4),
        })
        return png
