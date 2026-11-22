#!/usr/bin/env python3
"""verify_ui_clean.py - capturas LIMPIAS de cada ventana (una sola abierta).

Para medir centrado de titulo sin ventanas solapadas y confirmar botones a la
derecha en las 5 apps: se abre cada app, se captura, se cierra con Alt+W.
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

OUT = EVID / "run-ui-clean"
OUT.mkdir(parents=True, exist_ok=True)
APPS = [
    ("f1", "files", "files"),
    ("f2", "terminal", "terminal"),
    ("f3", "monitor", "monitor"),
    ("f5", "about", "about"),
    ("f4", "game", "game"),
]


def zoom(png, box, out_name, scale=2):
    img = ppm_to_png.read_png(png)
    c = ppm_to_png.crop(img, *box)
    ppm_to_png.write_png(OUT / out_name,
                         ppm_to_png.scale_nearest(c, box[2] * scale, box[3] * scale))


def title_center(png, r):
    """bbox del texto claro de la barra de titulo (ventana limpia)."""
    img = ppm_to_png.read_png(png)
    y = int(r["row_y"])
    x0, x1 = r["window_x0"], r["window_x1"]
    bx = int(r["centers_x"][0]) - 40
    px, w = img.pixels, img.width
    xs = []
    for yy in range(max(0, y - 11), min(img.height, y + 12)):
        for xx in range(x0 + 15, min(bx, x1)):
            i = (yy * w + xx) * 3
            if px[i] > 170 and px[i + 1] > 170 and px[i + 2] > 170:
                xs.append(xx)
    if not xs:
        return None
    return {"bbox": [min(xs), max(xs)],
            "center": round((min(xs) + max(xs)) / 2, 1),
            "window_center": round((x0 + x1) / 2, 1),
            "offset": round((min(xs) + max(xs)) / 2 - (x0 + x1) / 2, 1)}


def main() -> int:
    res = {"checks": {}, "steps": [], "ok": True}

    def step(name, ok=True, **kw):
        res["steps"].append({"step": name, "ok": bool(ok), **kw})
        print(f"[{'OK ' if ok else 'FAIL'}] {name} {kw}", flush=True)
        if not ok:
            res["ok"] = False

    vm = Vm("ui-clean")
    try:
        vm.start(gui_timeout=150)
        step("GUI_READY")
        time.sleep(0.6)
        vm.shot("00_desktop")
        for key, appid, name in APPS:
            vm.key(key, settle=0.7)
            vm.wait(f"APP_OPEN:{appid}", 25)
            time.sleep(1.0)
            p = vm.shot(f"{name}_clean")
            r = check_ui_pixels.analyze(p)
            tc = title_center(p, r)
            res["checks"][name] = {
                "order": r.get("order_left_to_right"),
                "centers_x": r.get("centers_x"),
                "centers_y": r.get("centers_y"),
                "spacing": r.get("spacing_px"),
                "window": [r.get("window_x0"), r.get("window_x1")],
                "right_margin": r.get("right_margin_px"),
                "in_right_third": r.get("in_right_third"),
                "title": tc,
            }
            step(f"{name}_botones_derecha",
                 r.get("order_left_to_right") == ["amber", "green", "red"] and
                 bool(r.get("in_right_third")),
                 order=r.get("order_left_to_right"),
                 right_margin=r.get("right_margin_px"),
                 title_offset=tc.get("offset") if tc else None)
            if name == "about":
                zoom(p, (150, 160, 130, 100), "about_icon_zoom.png", 5)
            if name == "game":
                zoom(p, (int(r["centers_x"][1]) - 14, int(r["row_y"]) - 14,
                         28, 28), "game_glyph_max_zoom.png", 8)
            vm.key("alt+w", settle=0.8)
            try:
                vm.wait(f"APP_CLOSE:{appid}", 15)
                step(f"APP_CLOSE:{appid}", True)
            except Exception as exc:  # noqa: BLE001
                step(f"APP_CLOSE:{appid}", False, error=str(exc)[:200])
        # F6/F7 con una ventana
        vm.key("f1", settle=0.6)
        vm.wait("APP_OPEN:files", 20)
        vm.key("f6", settle=0.5)
        vm.shot("f6_focus")
        vm.key("f7", settle=0.7)
        p = vm.shot("f7_minimize")
        # tras minimizar no debe quedar ventana visible
        info = ppm_to_png.analyze(ppm_to_png.read_png(p))
        step("f7_minimiza", info.non_black_ratio > 0.5)
        vm.key("f1", settle=0.6)  # reabrir
        vm.key("alt+w", settle=0.6)
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
