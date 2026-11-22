#!/usr/bin/env python3
"""make_comparison.py - mosaico antes/despues para el rediseno de SereOS.

Genera `docs/screenshots/compare_before_after.png` apilando pares de capturas
(antes a la izquierda, despues a la derecha) sin dependencias externas: usa el
lector/escritor PNG propio de `tools/ppm_to_png.py`.

Uso:
    python3 tools/make_comparison.py
    python3 tools/make_comparison.py --width 420 \
        --pairs 02_desktop,06_about,02b_topbar_dock

Filas por defecto: escritorio, zoom barra+dock, terminal y Acerca de.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import ppm_to_png as P  # noqa: E402

DEFAULT_PAIRS = ["02_desktop", "02b_topbar_dock", "02c_dock_tooltip",
                 "03_terminal", "06_about"]
SEPARATOR = (0x4C, 0x8D, 0xFF)      # theme.accent
GAP_BG = (0x2A, 0x30, 0x40)         # theme.border


def pane(path: Path, width: int) -> P.PPMImage:
    img = P.read_png(path)
    height = max(1, round(img.height * width / img.width))
    return P.scale_nearest(img, width, height)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Genera el mosaico antes/despues del rediseno de SereOS.")
    parser.add_argument("--before", default=str(ROOT / "docs/screenshots/before"))
    parser.add_argument("--after", default=str(ROOT / "docs/screenshots"))
    parser.add_argument("--out",
                        default=str(ROOT / "docs/screenshots/compare_before_after.png"))
    parser.add_argument("--width", type=int, default=480,
                        help="ancho de cada captura en el mosaico (px)")
    parser.add_argument("--pairs", default=",".join(DEFAULT_PAIRS),
                        help="nombres de captura separados por comas")
    parser.add_argument("--gap", type=int, default=8)
    args = parser.parse_args(argv)

    before_dir = Path(args.before)
    after_dir = Path(args.after)
    pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]

    rows: list[P.PPMImage] = []
    used: list[str] = []
    for name in pairs:
        before = before_dir / f"{name}.png"
        after = after_dir / f"{name}.png"
        if not before.is_file() or not after.is_file():
            missing = [str(p) for p in (before, after) if not p.is_file()]
            print(f"aviso: se omite {name} (falta {', '.join(missing)})",
                  file=sys.stderr)
            continue
        try:
            left = pane(before, args.width)
            right = pane(after, args.width)
        except P.PPMError as exc:
            print(f"aviso: no se pudo procesar {name}: {exc}", file=sys.stderr)
            continue
        height = max(left.height, right.height)
        sep = P.PPMImage(6, height, 255, bytes(SEPARATOR) * 6 * height)
        row = P.hstack([left, sep, right], gap=args.gap, gap_color=GAP_BG)
        rows.append(row)
        used.append(name)

    if not rows:
        print("error: no hay pares validos antes/despues", file=sys.stderr)
        return 1

    mosaic = P.vstack(rows, gap=args.gap + 4, gap_color=(0x0B, 0x0D, 0x12))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    P.write_png(out, mosaic)
    print(f"[OK] {out} ({mosaic.width}x{mosaic.height} px)")
    print("     filas: " + ", ".join(used))
    print("     orden de cada fila: ANTES | DESPUES")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
