#!/usr/bin/env python3
"""verify_ui.py - verificacion UI final task-4 (sesion sin audio).

Captura: escritorio, menu (Reiniciar+Apagar), About (F5), Archivos, Terminal
(help/dmesg), Monitor, PAC-MAN, maximizar/restaurar (doble clic y boton),
cierre Alt+W, F1..F7. Guarda PPM/PNG/logs/serial en evidence/run-ui/.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS))
from vmkit import EVID, Vm, ppm_to_png  # noqa: E402
import check_ui_pixels  # noqa: E402

OUT = EVID / "run-ui"
OUT.mkdir(parents=True, exist_ok=True)
RES = {"steps": [], "ok": True, "checks": {}}


def step(name, ok=True, **kw):
    RES["steps"].append({"step": name, "ok": ok, **kw})
    print(f"[{'OK ' if ok else 'FAIL'}] {name} {kw}", flush=True)
    if not ok:
        RES["ok"] = False


def check(name, cond, **kw):
    step(name, bool(cond), **kw)
    return bool(cond)


def wait(vm, marker, timeout=25, required=True):
    try:
        hit = vm.wait(marker, timeout)
        return True
    except Exception as exc:  # noqa: BLE001
        step(f"wait:{marker}", False, error=str(exc)[:300])
        if required:
            raise
        return False


def crop_save(png, out_name, box, scale=1):
    img = ppm_to_png.read_png(png)
    x, y, w, h = box
    c = ppm_to_png.crop(img, x, y, w, h)
    if scale > 1:
        c = ppm_to_png.scale_nearest(c, w * scale, h * scale)
    p = OUT / out_name
    ppm_to_png.write_png(p, c)
    return p


def main() -> int:
    vm = Vm("ui")
    try:
        t0 = time.time()
        vm.start(gui_timeout=150)
        step("GUI_READY", seconds=round(time.time() - t0, 2))
        time.sleep(0.8)
        p = vm.shot("01_desktop")
        crop_save(p, "01_desktop_topbar_crop.png", (0, 0, 1024, 40), 1)

        # ---- MENU: debe mostrar Reiniciar y Apagar (icono power) ----
        vm.click_at(97, 18, settle=0.7)
        p = vm.shot("02_menu")
        crop_save(p, "02_menu_crop.png", (70, 25, 255, 320), 2)
        vm.key("esc", settle=0.4)
        vm.shot("03_menu_closed")

        # ---- ABOUT (F5): icono i + fila Audio ----
        vm.key("f5", settle=0.6)
        wait(vm, "APP_OPEN:about")
        time.sleep(0.7)
        p = vm.shot("04_about")
        crop_save(p, "04_about_header_crop.png", (145, 140, 700, 160), 2)
        crop_save(p, "04_about_icon_crop.png", (150, 160, 130, 100), 4)
        vm.key("alt+w", settle=0.7)
        wait(vm, "APP_CLOSE:about", 15)

        # ---- ARCHIVOS F1 ----
        vm.key("f1", settle=0.6)
        wait(vm, "APP_OPEN:files")
        time.sleep(0.7)
        vm.shot("05_files")

        # ---- TERMINAL F2 + help/dmesg ----
        vm.key("f2", settle=0.7)
        wait(vm, "APP_OPEN:terminal")
        time.sleep(0.6)
        vm.shot("06_terminal")
        vm.type_line("help", settle=0.9)
        p = vm.shot("07_terminal_help")
        crop_save(p, "07_terminal_help_crop.png", (0, 60, 700, 500), 1)
        vm.type_line("dmesg", settle=1.0)
        vm.shot("08_terminal_dmesg")
        vm.type_line("audio", settle=1.0)
        vm.shot("09_terminal_audio")

        # ---- MONITOR F3 ----
        vm.key("f3", settle=0.7)
        wait(vm, "APP_OPEN:monitor")
        time.sleep(0.8)
        vm.shot("10_monitor")

        # ---- PAC-MAN F4 ----
        vm.key("f4", settle=1.0)
        wait(vm, "APP_OPEN:game")
        time.sleep(2.0)
        p = vm.shot("11_game")
        info = check_ui_pixels.analyze(p)
        RES["checks"]["game_buttons_normal"] = info
        check("game_buttones_3_colores", len(info.get("centers_x", [])) == 3, info=info)
        cy = info.get("row_y", 200)
        # doble clic en barra de titulo (centro) -> maximizar
        vm.double_click_at(512, cy, settle=1.0)
        p = vm.shot("12_game_maximized")
        info_max = check_ui_pixels.analyze(p)
        RES["checks"]["game_buttons_maximized"] = info_max
        step("game_maximizado", centers_y=info_max.get("centers_y"),
             order=info_max.get("order_left_to_right"))
        # doble clic -> restaurar
        vm.double_click_at(512, cy, settle=1.0)
        p = vm.shot("13_game_restored")
        info_rest = check_ui_pixels.analyze(p)
        RES["checks"]["game_buttons_restored"] = info_rest
        step("game_restaurado", centers_y=info_rest.get("centers_y"))
        # maximizar por BOTON (indice 1 = verde, centro)
        xs = info_rest.get("centers_x")
        if xs and len(xs) == 3:
            vm.click_at(int(xs[1]), cy, settle=1.0)
            p = vm.shot("14_game_max_button")
            RES["checks"]["game_buttons_max_button"] = check_ui_pixels.analyze(p)
            vm.click_at(int(xs[1]), cy, settle=1.0)
            vm.shot("15_game_restore_button")
        # cerrar con Alt+W
        vm.key("alt+w", settle=0.9)
        wait(vm, "APP_CLOSE:game", 15)
        vm.shot("16_desktop_after_game")

        # ---- F6 enfocar / F7 minimizar (regresion) ----
        vm.key("f1", settle=0.7)
        wait(vm, "APP_OPEN:files", 15, required=False)
        vm.key("f3", settle=0.7)
        wait(vm, "APP_OPEN:monitor", 15, required=False)
        vm.shot("17_two_windows")
        vm.key("f6", settle=0.6)
        vm.shot("18_f6_focus")
        vm.key("f7", settle=0.7)
        vm.shot("19_f7_minimize")
        # cerrar todas las ventanas abiertas
        for i in range(4):
            vm.key("alt+w", settle=0.5)
        vm.shot("20_final_desktop")

        fatals = vm.fatals()
        step("sin_panic_exception", not fatals, fatals=fatals)
        vm.save_serial()
        RES["serial_lines"] = vm.vm.serial_lines()
        RES["shots"] = vm.shots
    except Exception as exc:  # noqa: BLE001
        RES["ok"] = False
        RES["error"] = f"{exc}"
        RES["traceback"] = traceback.format_exc()
        print("ERROR:", exc, file=sys.stderr)
        try:
            vm.save_serial()
            vm.shot("99_error")
        except Exception:  # noqa: BLE001
            pass
    finally:
        vm.stop()
    (OUT / "result.json").write_text(
        json.dumps(RES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if RES["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
