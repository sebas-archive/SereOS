#!/usr/bin/env python3
"""probe_prep.py - dry-run de PREPARACION del arnes (no es veredicto).

Valida: arranque GUI_READY, raton PS/2 por HMP (menu del logo), captura
PPM->PNG, F5 About, cierre Alt+W. No ejecuta la verificacion final task-4.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vmkit import EVID, Vm  # noqa: E402


def main() -> int:
    out = EVID / "prep-dryrun"
    out.mkdir(parents=True, exist_ok=True)
    log = {"steps": [], "ok": True}

    def step(name, **kw):
        log["steps"].append({"step": name, **kw})
        print(f"[{name}] {kw}", flush=True)

    vm = Vm("prep-dryrun")
    try:
        t0 = time.time()
        vm.start(gui_timeout=150)
        step("GUI_READY", seconds=round(time.time() - t0, 2))
        time.sleep(1.0)
        p = vm.shot("00_desktop")
        step("shot_desktop", png=str(p))

        # Menu del logo: boton ~ (97,18) segun capturas previas.
        vm.click_at(97, 18, settle=0.8)
        p = vm.shot("01_menu")
        step("shot_menu_click", png=str(p), cursor=[vm.cx, vm.cy])

        vm.key("esc", settle=0.4)
        p = vm.shot("02_menu_closed")
        step("shot_menu_closed", png=str(p))

        vm.key("f5", settle=0.8)
        try:
            vm.wait("APP_OPEN:about", 20)
            step("APP_OPEN:about", found=True)
        except Exception as exc:  # noqa: BLE001
            step("APP_OPEN:about", found=False, error=str(exc))
            log["ok"] = False
        p = vm.shot("03_about")
        step("shot_about", png=str(p))

        vm.key("alt+w", settle=0.8)
        try:
            vm.wait("APP_CLOSE:about", 15)
            step("APP_CLOSE:about", found=True)
        except Exception as exc:  # noqa: BLE001
            step("APP_CLOSE:about", found=False, error=str(exc))
        p = vm.shot("04_after_close")
        step("shot_after_close", png=str(p))

        fatals = vm.fatals()
        step("fatal_markers", fatals=fatals)
        if fatals:
            log["ok"] = False
        vm.save_serial()
        log["shots"] = vm.shots
        (out / "dryrun.json").write_text(
            json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(log, indent=2, ensure_ascii=False))
        return 0 if log["ok"] else 1
    finally:
        vm.stop()


if __name__ == "__main__":
    raise SystemExit(main())
