#!/usr/bin/env python3
"""verify_shutdown.py - verificacion APAGADO real task-4.

Sesion A (QEMU por defecto): menu -> Apagar -> QEMU debe salir por ACPI
(puerto PM1a_CNT, serial SEREOS_SHUTDOWN + SEREOS_POWEROFF). Captura del menu
y de la pantalla "Apagando...". Sesion B opcional: -M pc,acpi=off +
-device isa-debug-exit para probar la cascada si ACPI no apaga.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS))
from vmkit import EVID, Vm  # noqa: E402

MENU_X, MENU_Y_LOGO = 97, 18
APAGAR = (150, 289)   # menu_item_rect(index=6): base 86 + 180 + SEP 8 + 15


def crop_zoom(png, out, box, scale=2):
    from vmkit import ppm_to_png
    img = ppm_to_png.read_png(png)
    c = ppm_to_png.crop(img, *box)
    ppm_to_png.write_png(out, ppm_to_png.scale_nearest(c, box[2] * scale, box[3] * scale))


def run(name: str, extra_args=None) -> dict:
    out = EVID / f"run-{name}"
    out.mkdir(parents=True, exist_ok=True)
    res = {"name": name, "steps": [], "ok": False, "extra_args": extra_args or []}
    vm = Vm(name, extra_args=extra_args)
    try:
        vm.start(gui_timeout=150)
        time.sleep(0.8)
        vm.click_at(MENU_X, MENU_Y_LOGO, settle=0.7)
        p = vm.shot("01_menu")
        crop_zoom(p, out / "01_menu_crop.png", (70, 25, 255, 320), 2)

        vm.click_at(*APAGAR, settle=0.0)
        # captura inmediata de la pantalla "Apagando..." (antes del ACPI outw)
        shot_ok = False
        try:
            time.sleep(0.15)
            vm.shot("02_apagando")
            shot_ok = True
        except Exception as exc:  # noqa: BLE001
            res["steps"].append({"step": "shot_apagando_fallo", "error": str(exc)[:200]})
        # QEMU debe terminar solo (ACPI). Esperamos hasta 15 s.
        t0 = time.time()
        exited = False
        rc = None
        while time.time() - t0 < 15.0:
            if vm.vm.proc is not None and vm.vm.proc.poll() is not None:
                exited = True
                rc = vm.vm.proc.returncode
                break
            time.sleep(0.1)
        elapsed = round(time.time() - t0, 2)
        vm.save_serial()
        serial = vm.vm.serial_text()
        res.update({
            "qemu_exited": exited,
            "qemu_returncode": rc,
            "exit_wait_s": elapsed,
            "shot_apagando": shot_ok,
            "serial_poweroff": "SEREOS_POWEROFF" in serial,
            "serial_shutdown": "SEREOS_SHUTDOWN" in serial,
            "serial_acpi_line": next((ln for ln in serial.splitlines()
                                      if ln.startswith("SEREOS_SHUTDOWN:acpi")), None),
            "serial_port_line": next((ln for ln in serial.splitlines()
                                      if ln.startswith("SEREOS_SHUTDOWN:port")), None),
            "serial_safe_line": "SEREOS_POWEROFF_SAFE" in serial,
            "serial_restart_line": "SEREOS_RESTART" in serial,
            "fatals": vm.fatals(),
            "serial_tail": serial.splitlines()[-15:],
        })
        res["ok"] = bool(exited and res["serial_poweroff"] and
                         res["serial_shutdown"] and not res["fatals"])
    except Exception as exc:  # noqa: BLE001
        res["error"] = str(exc)
        res["traceback"] = traceback.format_exc()
        try:
            vm.save_serial()
        except Exception:  # noqa: BLE001
            pass
    finally:
        vm.stop()
    (out / "result.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return res


def main() -> int:
    results = {}
    results["default"] = run("shutdown-default")
    print(json.dumps({k: {kk: vv for kk, vv in v.items()
                          if kk not in ("serial_tail", "steps")}
                      for k, v in results.items()}, indent=2, ensure_ascii=False))
    # Sesion B: ACPI apagado + isa-debug-exit (cascada de respaldo, opcional)
    if "--with-fallback" in sys.argv:
        results["isa_debug_exit"] = run(
            "shutdown-isadebugexit",
            extra_args=["-machine", "pc,acpi=off",
                        "-device", "isa-debug-exit,iobase=0x501,iosize=0x04"])
        print(json.dumps({k: {kk: vv for kk, vv in v.items()
                              if kk not in ("serial_tail", "steps")}
                          for k, v in results.items()}, indent=2, ensure_ascii=False))
    allok = all(r.get("ok") for r in results.values())
    (EVID / "run-shutdown-default" / "result_all.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
