#!/usr/bin/env python3
"""verify_maximize.py - maximizar/restaurar PAC-MAN por doble clic y por boton.

Corrige la secuencia de verify_ui.py: tras maximizar, la barra de titulo baja a
y=47, por lo que el doble clic de restaurar debe hacerse en la NUEVA posicion.
Captura de cerca el boton verde para ver el glifo "restaurar" (dos cuadrados).
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

OUT = EVID / "run-max"
OUT.mkdir(parents=True, exist_ok=True)


def zoom_glyph(png, cx, cy, out_name, size=26, scale=10):
    img = ppm_to_png.read_png(png)
    c = ppm_to_png.crop(img, int(cx) - size // 2, int(cy) - size // 2, size, size)
    ppm_to_png.write_png(OUT / out_name,
                         ppm_to_png.scale_nearest(c, size * scale, size * scale))


def main() -> int:
    res = {"steps": [], "checks": {}, "ok": True}

    def step(name, ok=True, **kw):
        res["steps"].append({"step": name, "ok": bool(ok), **kw})
        print(f"[{'OK ' if ok else 'FAIL'}] {name} {kw}", flush=True)
        if not ok:
            res["ok"] = False

    vm = Vm("max")
    try:
        vm.start(gui_timeout=150)
        step("GUI_READY")
        vm.key("f4", settle=0.8)
        vm.wait("APP_OPEN:game", 25)
        time.sleep(1.5)
        p = vm.shot("01_game_normal")
        info = check_ui_pixels.analyze(p)
        res["checks"]["normal"] = info
        cy_n = float(info["row_y"])
        x_n = info["centers_x"]
        step("normal", row_y=cy_n, window_x0=info["window_x0"])

        # (1) doble clic en la barra de titulo -> maximizar
        vm.double_click_at(512, int(cy_n), settle=1.0)
        p = vm.shot("02_game_max_dblclick")
        info = check_ui_pixels.analyze(p)
        res["checks"]["max_dblclick"] = info
        cy_m = float(info["row_y"])
        maximized = info["window_x0"] <= 2 and info["window_x1"] >= 1021 and cy_n > cy_m
        step("maximizar_doble_clic", maximized, row_y=cy_m,
             window=[info["window_x0"], info["window_x1"]])
        zoom_glyph(p, info["centers_x"][1], cy_m, "02_glyph_restore_zoom.png")

        # (2) doble clic en la NUEVA barra (y=47) -> restaurar
        vm.double_click_at(512, int(cy_m), settle=1.0)
        p = vm.shot("03_game_restored_dblclick")
        info = check_ui_pixels.analyze(p)
        res["checks"]["restored_dblclick"] = info
        step("restaurar_doble_clic", abs(float(info["row_y"]) - cy_n) <= 2 and
             info["window_x0"] > 2, row_y=info["row_y"],
             window=[info["window_x0"], info["window_x1"]])
        zoom_glyph(p, info["centers_x"][1], float(info["row_y"]),
                   "03_glyph_maximize_zoom.png")

        # (3) maximizar por BOTON (verde, indice 1)
        x_btn = info["centers_x"][1]
        y_btn = float(info["row_y"])
        vm.click_at(int(x_btn), int(y_btn), settle=1.0)
        p = vm.shot("04_game_max_button")
        info = check_ui_pixels.analyze(p)
        res["checks"]["max_button"] = info
        step("maximizar_boton", info["window_x0"] <= 2 and
             info["window_x1"] >= 1021, row_y=info["row_y"],
             window=[info["window_x0"], info["window_x1"]])
        zoom_glyph(p, info["centers_x"][1], float(info["row_y"]),
                   "04_glyph_restore_boton_zoom.png")

        # (4) restaurar por BOTON en la posicion maximizada
        vm.click_at(int(info["centers_x"][1]), int(info["row_y"]), settle=1.0)
        p = vm.shot("05_game_restored_button")
        info = check_ui_pixels.analyze(p)
        res["checks"]["restored_button"] = info
        step("restaurar_boton", info["window_x0"] > 2, row_y=info["row_y"],
             window=[info["window_x0"], info["window_x1"]])

        # (5) cerrar con Alt+W
        vm.key("alt+w", settle=0.9)
        try:
            vm.wait("APP_CLOSE:game", 15)
            step("APP_CLOSE:game", True)
        except Exception as exc:  # noqa: BLE001
            step("APP_CLOSE:game", False, error=str(exc)[:300])
        vm.shot("06_desktop_after_close")
        res["fatals"] = vm.fatals()
        step("sin_panic", not res["fatals"], fatals=res["fatals"])
        vm.save_serial()
    except Exception as exc:  # noqa: BLE001
        res["ok"] = False
        res["error"] = str(exc)
        res["traceback"] = traceback.format_exc()
        print("ERROR:", exc, file=sys.stderr)
        try:
            vm.save_serial()
        except Exception:  # noqa: BLE001
            pass
    finally:
        vm.stop()
    (OUT / "result.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
