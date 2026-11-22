#!/usr/bin/env python3
"""verify_power_final.py - pantallas nuevas "Apagando..." y "Reiniciando...".

Sesion A: menu(97,18) -> Apagar(150,289): captura la pantalla nueva (logo S +
titulo TEXT_DISPLAY sans-serif + subtitulo gris, centrados, sin solape) y
comprueba que QEMU sale por ACPI con SEREOS_SHUTDOWN/SEREOS_POWEROFF.

Sesion B: menu -> Reiniciar(150,259): captura "Reiniciando..." con el mismo
diseno y comprueba el reset (con -no-reboot QEMU termina) + SEREOS_RESTART.

Incluye un analizador de layout por pixeles (bboxes de logo/titulo/subtitulo,
centrado horizontal/vertical y huecos reales).
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

OUT = EVID / "run-power-final"
OUT.mkdir(parents=True, exist_ok=True)
APAGAR = (150, 289)
REINICIAR = (150, 259)


def save(img, name):
    ppm_to_png.write_png(OUT / name, img)


def load(png):
    return ppm_to_png.read_png(png)


def clusters(points, min_size=10, gap=3):
    pts = set(points)
    seen = set()
    out = []
    for p in points:
        if p in seen:
            continue
        stack = [p]
        seen.add(p)
        comp = []
        while stack:
            cx, cy = stack.pop()
            comp.append((cx, cy))
            for dx in range(-gap, gap + 1):
                for dy in range(-gap, gap + 1):
                    q = (cx + dx, cy + dy)
                    if q in pts and q not in seen:
                        seen.add(q)
                        stack.append(q)
        if len(comp) >= min_size:
            xs = [c[0] for c in comp]
            ys = [c[1] for c in comp]
            out.append({"n": len(comp), "x0": min(xs), "x1": max(xs),
                        "y0": min(ys), "y1": max(ys),
                        "cx": (min(xs) + max(xs)) / 2,
                        "cy": (min(ys) + max(ys)) / 2})
    out.sort(key=lambda c: c["cy"])
    return out


def analyze_layout(png) -> dict:
    img = load(png)
    px, w, h = img.pixels, img.width, img.height
    blue, white, grey = [], [], []
    for y in range(h):
        row = y * w * 3
        for x in range(w):
            i = row + x * 3
            r, g, b = px[i], px[i + 1], px[i + 2]
            if b > 140 and b > r + 50 and b > g + 25:
                blue.append((x, y))
            elif r > 205 and g > 205 and b > 205:
                white.append((x, y))
            elif 100 <= r <= 185 and abs(r - g) < 22 and b >= g and \
                    100 <= b <= 200 and abs(b - r) < 45:
                grey.append((x, y))
    res = {"path": str(png), "size": [w, h],
           "logo": None, "title": None, "subtitle": None, "ok": False}
    bc = clusters(blue, 200, 4)
    if bc:
        logo = max(bc, key=lambda c: c["n"])
        # el logo S es el bloque grande azul (~68 px)
        if (logo["x1"] - logo["x0"]) >= 30:
            res["logo"] = logo
    def bbox(points):
        xs = [q[0] for q in points]
        ys = [q[1] for q in points]
        return {"n": len(points), "x0": min(xs), "x1": max(xs),
                "y0": min(ys), "y1": max(ys),
                "cx": (min(xs) + max(xs)) / 2, "cy": (min(ys) + max(ys)) / 2}

    def row_bands(points, min_pixels=40, join_gap=2):
        """funde glifos de una misma linea por proyeccion de filas."""
        rows = {}
        for x, y in points:
            rows.setdefault(y, []).append((x, y))
        ys = sorted(rows)
        bands, cur = [], []
        for y in ys:
            if cur and y - cur[-1] > join_gap:
                bands.append(cur)
                cur = []
            cur.append(y)
        if cur:
            bands.append(cur)
        out = []
        for band in bands:
            pts = [q for y in band for q in rows[y]]
            if len(pts) >= min_pixels:
                out.append(bbox(pts))
        return out

    # el logo S tiene la "S" blanca dentro: solo texto DEBAJO del logo
    whites = [q for q in white if not res["logo"] or q[1] > res["logo"]["y1"] + 5]
    wb = row_bands(whites, 40, 2)
    if wb:
        res["title"] = wb[0]
    greys = [q for q in grey if not res["title"] or q[1] > res["title"]["y1"] + 2]
    gb = row_bands(greys, 15, 2)
    if gb:
        res["subtitle"] = gb[0]
    if res["logo"] and res["title"]:
        L, T = res["logo"], res["title"]
        entry = {
            "logo_center_x": round(L["cx"], 1),
            "title_center_x": round(T["cx"], 1),
            "gap_logo_title": round(T["y0"] - L["y1"], 1),
            "logo_top": L["y0"], "logo_bottom": L["y1"],
            "title_top": T["y0"], "title_bottom": T["y1"],
        }
        if res["subtitle"]:
            S = res["subtitle"]
            entry.update({
                "subtitle_center_x": round(S["cx"], 1),
                "gap_title_subtitle": round(S["y0"] - T["y1"], 1),
                "subtitle_top": S["y0"], "subtitle_bottom": S["y1"],
            })
            entry["block_vertical_center"] = round(
                (L["y0"] + S["y1"]) / 2, 1)
            entry["no_overlap"] = bool(
                T["y0"] > L["y1"] and S["y0"] > T["y1"])
        else:
            entry["block_vertical_center"] = round((L["y0"] + T["y1"]) / 2, 1)
            entry["no_overlap"] = bool(T["y0"] > L["y1"])
        entry["title_text_width"] = T["x1"] - T["x0"]
        entry["centered_x"] = bool(
            abs(entry["logo_center_x"] - w / 2) <= 3 and
            abs(entry["title_center_x"] - w / 2) <= 6)
        res["layout"] = entry
        res["ok"] = bool(entry["no_overlap"] and entry["centered_x"] and
                         abs(entry["block_vertical_center"] - h / 2) <= 25)
    return res


def best_shot(shots):
    best = None
    for p in shots:
        img = ppm_to_png.read_png(p)
        st = ppm_to_png.analyze(img)
        if best is None or st.mean_luma > best[0]:
            best = (st.mean_luma, p)
    return best[1] if best else None


def run(name: str, item: tuple[int, int], title: str, serial_marker: str,
        expect_exit: bool) -> dict:
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    res = {"name": name, "steps": [], "ok": False}
    vm = Vm(name)
    try:
        vm.start(gui_timeout=150)
        time.sleep(0.8)
        vm.click_at(97, 18, settle=0.7)
        vm.shot("00_menu")
        # clic en el item y captura durante los ~920 ms de animacion
        vm.click_at(*item, settle=0.0)
        shots = []
        for delay in (0.16, 0.10, 0.10):
            time.sleep(delay)
            try:
                shots.append(vm.shot(f"01_{title.lower()}_{len(shots)}"))
            except Exception:  # noqa: BLE001
                break
        # esperar salida de QEMU
        t0 = time.time()
        exited = False
        rc = None
        deadline = 15.0
        while time.time() - t0 < deadline:
            if vm.vm.proc is not None and vm.vm.proc.poll() is not None:
                exited = True
                rc = vm.vm.proc.returncode
                break
            time.sleep(0.1)
        vm.save_serial()
        serial = vm.vm.serial_text()
        res.update({
            "qemu_exited": exited,
            "qemu_returncode": rc,
            "serial_marker": serial_marker in serial,
            "serial_poweroff": "SEREOS_POWEROFF" in serial,
            "serial_shutdown": "SEREOS_SHUTDOWN" in serial,
            "serial_acpi": next((ln for ln in serial.splitlines()
                                 if ln.startswith("SEREOS_SHUTDOWN:acpi")), None),
            "fatals": vm.fatals(),
            "serial_tail": serial.splitlines()[-12:],
        })
        best = best_shot(shots)
        if best:
            res["layout"] = analyze_layout(best)
            # copia la mejor captura con nombre estable
            png = out / f"01_{title.lower()}_best.png"
            ppm_to_png.write_png(png, load(best))
            res["layout"]["best_png"] = str(png)
            res["ok"] = bool(res["layout"]["ok"] and res["serial_marker"] and
                             (res["qemu_exited"] == expect_exit) and
                             not res["fatals"])
    except Exception as exc:  # noqa: BLE001
        res["error"] = str(exc)
        res["traceback"] = traceback.format_exc()
        print("ERROR:", exc, file=sys.stderr)
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
    results = {
        "apagar": run("power-apagar", APAGAR, "Apagando", "SEREOS_SHUTDOWN", True),
        "reiniciar": run("power-reiniciar", REINICIAR, "Reiniciando",
                         "SEREOS_RESTART", True),
    }
    (OUT / "result_all.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, r in results.items():
        print(f"== {k}: ok={r.get('ok')} exit={r.get('qemu_exited')}/{r.get('qemu_returncode')} "
              f"marker={r.get('serial_marker')} layout={r.get('layout', {}).get('layout')}")
    return 0 if all(r.get("ok") for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
