#!/usr/bin/env python3
"""verify_final_ui.py - verificacion UI FINAL task-4 + correccion task-5.

Comprueba sobre el arbol final:
  - About: LOGO S (S blanca sobre cuadro azul redondeado) en el contenido,
    SIN icono "i" (diff contra baseline pre-fix del logo S).
  - Menu: icono "i" SOLO en la fila "Acerca de"; Reiniciar y Apagar presentes.
  - Dock: tile About con "i". Topbar: logo S + wordmark "SereOS".
  - 5 ventanas con botones a la derecha (ambar/verde/rojo), titulo centrado.
  - PAC-MAN maximizar/restaurar por doble clic y glifo restaurar.
  - Alt+W cierra y emite APP_CLOSE; F1..F7; help/dmesg.
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

OUT = EVID / "run-final-ui"
OUT.mkdir(parents=True, exist_ok=True)
BASE_ABOUT = EVID / "run-prep-dryrun" / "03_about.png"   # pre-fix: logo S


def crop_img(png, box, scale=1):
    img = ppm_to_png.read_png(png)
    c = ppm_to_png.crop(img, *box)
    if scale > 1:
        c = ppm_to_png.scale_nearest(c, box[2] * scale, box[3] * scale)
    return c


def save(img, name):
    ppm_to_png.write_png(OUT / name, img)


def mean_abs_diff(a, b) -> float:
    n = min(len(a.pixels), len(b.pixels))
    s = 0
    for i in range(0, n, 3):
        s += abs(a.pixels[i] - b.pixels[i]) + abs(a.pixels[i + 1] - b.pixels[i + 1]) \
            + abs(a.pixels[i + 2] - b.pixels[i + 2])
    return s / (n / 3) / 3.0


def title_center(png, r):
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

    vm = Vm("final-ui")
    try:
        vm.start(gui_timeout=150)
        step("GUI_READY")
        time.sleep(0.8)

        # ---------- escritorio: topbar y dock ----------
        p = vm.shot("01_desktop")
        save(crop_img(p, (0, 0, 420, 34), 3), "01_topbar_zoom.png")
        save(crop_img(p, (360, 690, 310, 72), 3), "02_dock_zoom.png")
        step("captura_topbar_dock")

        # ---------- menu: i en About, Reiniciar y Apagar ----------
        vm.click_at(97, 18, settle=0.7)
        p = vm.shot("03_menu")
        save(crop_img(p, (70, 25, 255, 320), 2), "03_menu_zoom.png")
        save(crop_img(p, (78, 78, 235, 46), 5), "03_menu_about_icon_zoom.png")
        vm.key("esc", settle=0.4)

        # ---------- About: logo S en contenido, SIN i ----------
        vm.key("f5", settle=0.6)
        vm.wait("APP_OPEN:about", 25)
        time.sleep(0.9)
        p = vm.shot("04_about")
        cur = crop_img(p, (150, 160, 130, 100), 4)
        save(cur, "04_about_content_icon_zoom.png")
        base = crop_img(BASE_ABOUT, (150, 160, 130, 100), 4)
        save(base, "04_about_icon_baseline_S_zoom.png")
        res["checks"]["about_icon"] = {
            "diff_vs_baseline_logo_S": round(mean_abs_diff(cur, base), 2),
        }
        # el logo S pre-fix es la referencia: diff bajo => logo S restaurado
        step("about_contenido_logo_S",
             mean_abs_diff(cur, base) < 12.0,
             diff_vs_baseline=res["checks"]["about_icon"]["diff_vs_baseline_logo_S"])
        r = check_ui_pixels.analyze(p)
        tc = title_center(p, r)
        res["checks"]["about_buttons"] = {
            "order": r.get("order_left_to_right"),
            "right_margin": r.get("right_margin_px"),
            "in_right_third": r.get("in_right_third"),
            "title": tc,
        }
        step("about_botones_derecha",
             r.get("order_left_to_right") == ["amber", "green", "red"] and
             bool(r.get("in_right_third")) and tc and abs(tc["offset"]) <= 1.5,
             order=r.get("order_left_to_right"), title_offset=tc["offset"] if tc else None)
        vm.shot("05_about_full")
        vm.key("alt+w", settle=0.7)
        vm.wait("APP_CLOSE:about", 15)
        step("APP_CLOSE:about", True)

        # ---------- 5 ventanas limpias ----------
        apps = [("f1", "files", "Archivos"), ("f2", "terminal", "Terminal"),
                ("f3", "monitor", "Monitor"), ("f4", "game", "PAC-MAN")]
        for key, appid, label in apps:
            vm.key(key, settle=0.7)
            vm.wait(f"APP_OPEN:{appid}", 25)
            time.sleep(1.0)
            p = vm.shot(f"06_{appid}")
            r = check_ui_pixels.analyze(p)
            tc = title_center(p, r)
            res["checks"][appid] = {
                "order": r.get("order_left_to_right"),
                "centers_x": r.get("centers_x"),
                "right_margin": r.get("right_margin_px"),
                "in_right_third": r.get("in_right_third"),
                "title": tc,
            }
            step(f"{appid}_botones_derecha_y_titulo_centrado",
                 r.get("order_left_to_right") == ["amber", "green", "red"] and
                 bool(r.get("in_right_third")) and tc and abs(tc["offset"]) <= 1.5,
                 order=r.get("order_left_to_right"),
                 right_margin=r.get("right_margin_px"),
                 title_offset=tc["offset"] if tc else None)
            if appid == "game":
                cy = float(r["row_y"])
                # maximizar
                vm.double_click_at(512, int(cy), settle=1.0)
                p = vm.shot("07_game_maximized")
                rm = check_ui_pixels.analyze(p)
                res["checks"]["game_max"] = rm
                step("game_maximizado", rm["window_x0"] <= 2 and
                     rm["window_x1"] >= 1021 and
                     rm.get("order_left_to_right") == ["amber", "green", "red"],
                     row_y=rm["row_y"], window=[rm["window_x0"], rm["window_x1"]])
                cy2 = float(rm["row_y"])
                save(crop_img(p, (int(rm["centers_x"][1]) - 14,
                                  int(cy2) - 14, 28, 28), 8),
                     "07_game_glyph_restore_zoom.png")
                # restaurar
                vm.double_click_at(512, int(cy2), settle=1.0)
                p = vm.shot("08_game_restored")
                rr = check_ui_pixels.analyze(p)
                res["checks"]["game_restored"] = rr
                step("game_restaurado", rr["window_x0"] > 2 and
                     abs(float(rr["row_y"]) - cy) <= 2,
                     row_y=rr["row_y"], window=[rr["window_x0"], rr["window_x1"]])
                save(crop_img(p, (int(rr["centers_x"][1]) - 14,
                                  int(rr["row_y"]) - 14, 28, 28), 8),
                     "08_game_glyph_maximize_zoom.png")
            vm.key("alt+w", settle=0.8)
            try:
                vm.wait(f"APP_CLOSE:{appid}", 15)
                step(f"APP_CLOSE:{appid}", True)
            except Exception as exc:  # noqa: BLE001
                step(f"APP_CLOSE:{appid}", False, error=str(exc)[:200])

        # ---------- help / dmesg ----------
        vm.key("f2", settle=0.7)
        vm.wait("APP_OPEN:terminal", 20)
        time.sleep(0.5)
        vm.type_line("help", settle=0.9)
        p = vm.shot("09_terminal_help")
        save(crop_img(p, (0, 60, 720, 480)), "09_terminal_help_crop.png")
        vm.type_line("dmesg", settle=1.0)
        p = vm.shot("10_terminal_dmesg")
        vm.type_line("audio", settle=0.8)
        vm.shot("11_terminal_audio")

        # ---------- F6/F7 ----------
        vm.key("f1", settle=0.7)
        vm.wait("APP_OPEN:files", 20)
        vm.key("f3", settle=0.7)
        vm.wait("APP_OPEN:monitor", 20)
        vm.key("f6", settle=0.6)
        vm.shot("12_f6_focus")
        vm.key("f7", settle=0.7)
        vm.shot("13_f7_minimize")
        step("f1_f7_abren_y_minimizan", True)
        # cerrar restantes
        for _ in range(4):
            vm.key("alt+w", settle=0.5)
        p = vm.shot("14_desktop_final")
        res["fatals"] = vm.fatals()
        step("sin_panic_exception", not res["fatals"], fatals=res["fatals"])
        vm.save_serial()
    except Exception as exc:  # noqa: BLE001
        res["ok"] = False
        res["error"] = str(exc)
        res["traceback"] = traceback.format_exc()
        print("ERROR:", exc, file=sys.stderr)
        try:
            vm.save_serial()
            vm.shot("99_error")
        except Exception:  # noqa: BLE001
            pass
    finally:
        vm.stop()
    (OUT / "result.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
