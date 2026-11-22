#!/usr/bin/env python3
"""check_ui_pixels.py - comprobacion programatica de los botones de ventana.

Busca los tres circulos de trafico (rojo, ambar, verde) en la franja de la
barra de titulo de una captura PPM/PNG de SereOS y verifica:
  - que existen los 3 colores,
  - orden izquierda->derecha: minimizar(ambar/rojo?), etc. (se reporta orden real),
  - que estan alineados horizontalmente y pegados al borde DERECHO de la ventana.

Uso: python3 check_ui_pixels.py captura.ppm [--json salida.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/t1an/Descargas/sereos02/sistema operativo/tools")
import ppm_to_png  # noqa: E402


def load(path: Path) -> ppm_to_png.PPMImage:
    if path.suffix.lower() == ".png":
        return ppm_to_png.read_png(path)
    return ppm_to_png.read_ppm(path)


def color_mask(img, pred):
    px = img.pixels
    w, h = img.width, img.height
    pts = []
    for y in range(h):
        row = y * w * 3
        for x in range(w):
            i = row + x * 3
            r, g, b = px[i], px[i + 1], px[i + 2]
            if pred(r, g, b):
                pts.append((x, y))
    return pts


def clusters(points, min_size=12):
    """Agrupacion simple por rejilla (los circulos son ~10px de diametro)."""
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
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    q = (cx + dx, cy + dy)
                    if q in pts and q not in seen:
                        seen.add(q)
                        stack.append(q)
        if len(comp) >= min_size:
            xs = [c[0] for c in comp]
            ys = [c[1] for c in comp]
            out.append({
                "n": len(comp),
                "cx": sum(xs) / len(xs),
                "cy": sum(ys) / len(ys),
                "x0": min(xs), "x1": max(xs),
                "y0": min(ys), "y1": max(ys),
            })
    out.sort(key=lambda c: c["cx"])
    return out


def analyze(path: Path) -> dict:
    img = load(path)
    red = clusters(color_mask(
        img, lambda r, g, b: r >= 170 and g <= 110 and b <= 110))
    amber = clusters(color_mask(
        img, lambda r, g, b: r >= 150 and 90 <= g <= 210 and b <= 110))
    green = clusters(color_mask(
        img, lambda r, g, b: r <= 140 and g >= 140 and g > r + 40 and
        g > b + 20))
    # filtrar por tamano de circulo de trafico (radio ~5 -> area ~78)
    def filt(cs):
        return [c for c in cs if 20 <= c["n"] <= 400 and
                (c["x1"] - c["x0"]) <= 20 and (c["y1"] - c["y0"]) <= 20]
    red, amber, green = filt(red), filt(amber), filt(green)
    rows = {}
    for name, cs in (("red", red), ("amber", amber), ("green", green)):
        for c in cs:
            key = round(c["cy"] / 4) * 4
            rows.setdefault(key, []).append((name, c))
    # Nos quedamos con la fila que tenga mas colores distintos (barra de titulo)
    best = None
    for cy, items in rows.items():
        names = {n for n, _ in items}
        score = (len(names), len(items))
        if best is None or score > best[0]:
            best = (score, cy, items)
    if best is None:
        return {"path": str(path), "found": False}
    _, cy, items = best
    items.sort(key=lambda t: t[1]["cx"])
    order = [n for n, _ in items]
    cy_vals = [c["cy"] for _, c in items]

    # Borde derecho/inquierdo de la ventana: se camina por la fila del titulo
    # desde el color de fondo del titulo hasta que cambie (borde/fuera).
    def px(x, y):
        i = (y * img.width + x) * 3
        return (img.pixels[i], img.pixels[i + 1], img.pixels[i + 2])

    if len(items) >= 2:
        ref_x = int((items[-1][1]["cx"] + items[-2][1]["cx"]) / 2)
    else:
        ref_x = int(items[0][1]["cx"]) - 20
    ref = px(ref_x, cy)
    def same(c):
        return all(abs(c[k] - ref[k]) <= 6 for k in range(3))
    same_xs = [x for x in range(img.width) if same(px(x, cy))]
    x0 = min(same_xs) if same_xs else ref_x
    x1 = max(same_xs) if same_xs else ref_x
    # el borde de la ventana esta ~1px fuera del ultimo pixel del fondo
    x1 += 1
    right_margin = x1 - items[-1][1]["cx"]
    return {
        "window_x0": x0,
        "window_x1": x1,
        "right_margin_px": round(right_margin, 1),
        "in_right_third": bool(items[0][1]["cx"] > x0 + (x1 - x0) * 0.6),
        "path": str(path),
        "found": True,
        "row_y": cy,
        "order_left_to_right": order,
        "centers_x": [round(c["cx"], 1) for _, c in items],
        "centers_y": [round(c[1]["cy"], 1) for c in items],
        "aligned_y": (max(cy_vals) - min(cy_vals)) <= 3,
        "spacing_px": [round(items[i + 1][1]["cx"] - items[i][1]["cx"], 1)
                       for i in range(len(items) - 1)],
        "colors": {n: sum(1 for x, _ in items if x == n)
                   for n in ("red", "amber", "green")},
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    res = analyze(Path(argv[1]))
    print(json.dumps(res, indent=2))
    out = Path(argv[argv.index("--json") + 1]) if "--json" in argv else None
    if out:
        out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    return 0 if res.get("found") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
