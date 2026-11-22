#!/usr/bin/env python3
"""tools/gen_ui_icons.py - generador reproducible de la iconografia de SereOS.

Arte ORIGINAL, geometrico y lineal (licencia del proyecto SereOS). Cada icono
se define como una lista de operaciones vectoriales sobre una rejilla de
24x24 (trazo 1.5-2 px, esquinas redondeadas, sin 3D ni emojis). El generador
rasteriza con PIL a 4x supersampling y baja a cobertura alfa 8bpp para los
tamanos 16, 20, 24, 32, 40, 48 y 64 px, y emite:

  gui/icons_data.c   arrays const uint8_t (cobertura alfa) + tabla de bitmaps

Uso:
  py=~/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
  $py tools/gen_ui_icons.py                # genera gui/icons_data.c
  $py tools/gen_ui_icons.py --preview /tmp/ui_icons.png

El script es determinista (mismo codigo -> mismos bytes). Cero dependencias
en tiempo de ejecucion: el motor solo usa cobertura alfa precalculada.
"""
import math
import os
import sys

from PIL import Image, ImageDraw

GRID = 24.0
STROKE = 1.75
SS = 4                       # supersampling
SIZES = (16, 20, 24, 32, 40, 48, 64)
PUBLIC_IDS = (
    "sereos", "files", "folder", "file", "terminal", "monitor", "settings",
    "about", "game", "power", "network", "memory", "storage", "disk",
    "search", "close", "minimize", "maximize", "restore", "chevron_left",
    "chevron_right", "play", "pause", "refresh", "info", "check", "warning",
    "error", "home", "arrows", "plus", "minus", "menu", "clock", "cpu", "ram",
)


# ---------------------------------------------------------------------------
# DSL de dibujo (coordenadas en la rejilla de 24x24)
# ---------------------------------------------------------------------------
def L(x0, y0, x1, y1, w=STROKE):
    return ("line", (x0, y0, x1, y1), w)


def PL(points, w=STROKE, closed=False):
    return ("poly", tuple(points), w, closed)


def RR(x, y, w, h, r=2.0, stroke=STROKE):
    return ("rrect", (x, y, w, h, r), stroke)


def FR(x, y, w, h, r=2.0):
    return ("rrect", (x, y, w, h, r), 0.0)


def C(cx, cy, r, w=STROKE):
    return ("circle", (cx, cy, r), w)


def DOT(cx, cy, r):
    return ("dot", (cx, cy, r), 0.0)


def A(cx, cy, r, a0, a1, w=STROKE):
    return ("arc", (cx, cy, r, a0, a1), w)


def EL(cx, cy, rx, ry, w=STROKE):
    return ("ellipse", (cx, cy, rx, ry), w)


def EA(cx, cy, rx, ry, a0, a1, w=STROKE):
    return ("earc", (cx, cy, rx, ry, a0, a1), w)


def BEZ(segments, w=STROKE):
    return ("bezier", tuple(segments), w)


def HEAD(tip, direction_deg, size=3.2, w=STROKE, spread=32.0):
    """Punta de flecha: dos trazos desde `tip` hacia atras."""
    ops = []
    for s in (-spread, spread):
        a = math.radians(direction_deg + 180.0 + s)
        ops.append(L(tip[0], tip[1],
                     tip[0] + size * math.cos(a), tip[1] + size * math.sin(a), w))
    return ops


# ---------------------------------------------------------------------------
# definicion de los iconos (36 ids publicos)
# ---------------------------------------------------------------------------
ICONS = {}

# marca SereOS (squircle + S minimalista, sin texto)
_S_SEGMENTS = (
    ((15.6, 6.9), (12.9, 4.7), (8.7, 5.7), (8.7, 9.2)),
    ((8.7, 11.5), (11.0, 12.6), (12.3, 13.1), (12.3, 13.1)),
    ((15.0, 14.0), (15.9, 15.6), (14.0, 17.0), (14.0, 17.0)),
    ((12.1, 18.3), (9.8, 18.2), (8.2, 16.5), (8.2, 16.5)),
)
ICONS["sereos"] = [RR(2.5, 2.5, 19.0, 19.0, 6.0, 1.6), BEZ(_S_SEGMENTS, 2.1)]

# archivos/carpetas
_folder = [RR(3.4, 8.0, 17.2, 11.6, 2.2),
           PL(((3.4, 8.0), (3.4, 6.0), (9.2, 6.0), (11.0, 8.0)))]
ICONS["folder"] = list(_folder)
ICONS["files"] = _folder + [L(7.2, 12.6, 13.2, 12.6, 1.5),
                            L(7.2, 15.6, 11.6, 15.6, 1.5)]
ICONS["file"] = [
    PL(((6.6, 20.4), (6.6, 3.6), (13.6, 3.6), (17.4, 7.6), (17.4, 20.4)),
       closed=True),
    PL(((13.6, 3.6), (13.6, 7.6), (17.4, 7.6))),
    L(9.2, 11.2, 14.8, 11.2, 1.5),
    L(9.2, 14.2, 14.8, 14.2, 1.5),
    L(9.2, 17.2, 12.6, 17.2, 1.5),
]

# terminal y monitor
ICONS["terminal"] = [RR(3.0, 4.5, 18.0, 15.0, 3.0),
                     L(3.0, 9.0, 21.0, 9.0, 1.5),
                     PL(((7.0, 11.6), (10.4, 14.0), (7.0, 16.4))),
                     L(12.6, 16.4, 16.4, 16.4, 2.0)]
ICONS["monitor"] = [RR(3.0, 4.4, 18.0, 12.4, 2.2),
                    L(12.0, 16.8, 12.0, 20.0),
                    L(8.6, 20.4, 15.4, 20.4, 1.75)]

# ajustes: tres deslizadores horizontales (lineal, inequivoco)
ICONS["settings"] = [L(4.4, 7.4, 19.6, 7.4, 1.7),
                     L(4.4, 12.0, 19.6, 12.0, 1.7),
                     L(4.4, 16.6, 19.6, 16.6, 1.7),
                     L(9.0, 5.0, 9.0, 9.8, 1.9),
                     L(15.2, 9.6, 15.2, 14.4, 1.9),
                     L(7.2, 14.2, 7.2, 19.0, 1.9)]

# acerca de: circulo + i
ICONS["about"] = [C(12.0, 12.0, 8.4), DOT(12.0, 7.6, 1.25),
                  L(12.0, 10.6, 12.0, 16.8, 2.0)]
# info: cuadrado redondeado + i
ICONS["info"] = [RR(4.2, 4.2, 15.6, 15.6, 4.2), DOT(12.0, 8.0, 1.2),
                 L(12.0, 10.8, 12.0, 16.4, 2.0)]

# juego: mando original
ICONS["game"] = [RR(2.8, 7.4, 18.4, 10.4, 5.0),
                 L(6.4, 12.6, 9.6, 12.6, 1.8),
                 L(8.0, 11.0, 8.0, 14.2, 1.8),
                 DOT(15.2, 11.6, 1.2), DOT(17.2, 13.6, 1.2)]

# energia / red
ICONS["power"] = [A(12.0, 12.6, 8.0, -58.0, 238.0, 1.75),
                  L(12.0, 4.0, 12.0, 11.6, 2.0)]
ICONS["network"] = [A(12.0, 18.6, 9.0, 218.0, 322.0, 1.75),
                    A(12.0, 18.6, 5.4, 218.0, 322.0, 1.75),
                    DOT(12.0, 18.4, 1.3)]

# memoria: modulos apilados; ram: modulo DIMM con pines y muesca
ICONS["memory"] = [RR(3.4, 5.4, 17.2, 3.8, 1.2),
                   RR(3.4, 10.2, 17.2, 3.8, 1.2),
                   RR(3.4, 15.0, 17.2, 3.8, 1.2)]
_ram = [RR(2.6, 8.8, 18.8, 6.4, 1.5)]
for _x in (4.8, 7.4, 9.8, 14.2, 16.6, 19.2):
    _ram.append(L(_x, 15.2, _x, 17.8, 1.5))
ICONS["ram"] = _ram

# almacenamiento: cilindro de base de datos
ICONS["storage"] = [EL(12.0, 6.6, 7.0, 2.6),
                    L(5.0, 6.6, 5.0, 17.4),
                    L(19.0, 6.6, 19.0, 17.4),
                    EA(12.0, 17.4, 7.0, 2.6, 0.0, 180.0),
                    EA(12.0, 11.0, 7.0, 2.6, 0.0, 180.0),
                    EA(12.0, 15.0, 7.0, 2.6, 0.0, 180.0)]

# disquete
ICONS["disk"] = [RR(4.0, 4.0, 16.0, 16.0, 2.2),
                 PL(((8.4, 4.2), (8.4, 8.2), (15.6, 8.2), (15.6, 4.2)), 1.5),
                 RR(7.0, 12.6, 10.0, 6.2, 1.0, 1.5)]

# buscar
ICONS["search"] = [C(10.6, 10.6, 6.2), L(15.2, 15.2, 20.0, 20.0, 2.2)]

# control de ventana
ICONS["close"] = [L(6.6, 6.6, 17.4, 17.4, 2.0), L(17.4, 6.6, 6.6, 17.4, 2.0)]
ICONS["minimize"] = [L(6.6, 12.0, 17.4, 12.0, 2.0)]
ICONS["maximize"] = [RR(5.0, 5.0, 14.0, 14.0, 2.5)]
ICONS["restore"] = [RR(9.2, 6.0, 9.6, 9.6, 2.0),
                    PL(((6.0, 9.0), (6.0, 19.0), (16.0, 19.0)))]

# chevrons
ICONS["chevron_left"] = [PL(((14.6, 6.6), (8.6, 12.0), (14.6, 17.4)), 2.0)]
ICONS["chevron_right"] = [PL(((9.4, 6.6), (15.4, 12.0), (9.4, 17.4)), 2.0)]

# reproduccion
ICONS["play"] = [PL(((8.6, 5.6), (18.4, 12.0), (8.6, 18.4)), 2.0, closed=True)]
ICONS["pause"] = [L(8.8, 5.6, 8.8, 18.4, 2.2), L(15.2, 5.6, 15.2, 18.4, 2.2)]

# actualizar: arco + flecha (sentido horario)
_refresh = [A(12.0, 12.0, 7.2, -60.0, 210.0, 1.75)]
_end = (12.0 + 7.2 * math.cos(math.radians(210.0)),
        12.0 + 7.2 * math.sin(math.radians(210.0)))
_refresh += HEAD(_end, 300.0, 3.8, 1.75, 38.0)
ICONS["refresh"] = _refresh

# comprobaciones / estados
ICONS["check"] = [PL(((6.6, 12.4), (10.6, 16.4), (18.0, 7.6)), 2.1)]
ICONS["warning"] = [PL(((12.0, 4.2), (21.0, 19.2), (3.0, 19.2)), 1.75, closed=True),
                    L(12.0, 9.6, 12.0, 14.2, 2.0), DOT(12.0, 16.9, 1.15)]
ICONS["error"] = [C(12.0, 12.0, 8.4),
                  L(8.8, 8.8, 15.2, 15.2, 1.9),
                  L(15.2, 8.8, 8.8, 15.2, 1.9)]

# navegacion
ICONS["home"] = [PL(((3.2, 11.2), (12.0, 4.0), (20.8, 11.2))),
                 PL(((6.0, 9.4), (6.0, 20.0), (18.0, 20.0), (18.0, 9.4))),
                 PL(((10.0, 20.0), (10.0, 14.8), (14.0, 14.8), (14.0, 20.0)), 1.6)]
ICONS["arrows"] = [L(12.0, 4.4, 12.0, 19.6),
                   L(4.4, 12.0, 19.6, 12.0),
                   PL(((9.6, 7.0), (12.0, 4.4), (14.4, 7.0))),
                   PL(((9.6, 17.0), (12.0, 19.6), (14.4, 17.0))),
                   PL(((7.0, 9.6), (4.4, 12.0), (7.0, 14.4))),
                   PL(((17.0, 9.6), (19.6, 12.0), (17.0, 14.4)))]

# operaciones simples
ICONS["plus"] = [L(12.0, 5.4, 12.0, 18.6, 2.1), L(5.4, 12.0, 18.6, 12.0, 2.1)]
ICONS["minus"] = [L(5.4, 12.0, 18.6, 12.0, 2.1)]
ICONS["menu"] = [L(4.6, 7.4, 19.4, 7.4, 1.9),
                 L(4.6, 12.0, 19.4, 12.0, 1.9),
                 L(4.6, 16.6, 19.4, 16.6, 1.9)]

# reloj
ICONS["clock"] = [C(12.0, 12.0, 8.4),
                  L(12.0, 6.8, 12.0, 12.2, 1.9),
                  L(12.0, 12.2, 15.8, 14.4, 1.9)]

# hardware
_cpu = [RR(6.0, 6.0, 12.0, 12.0, 2.0), RR(9.4, 9.4, 5.2, 5.2, 1.0, 1.5)]
for _t in (9.4, 12.0, 14.6):
    _cpu.append(L(_t, 3.4, _t, 6.0, 1.5))
    _cpu.append(L(_t, 18.0, _t, 20.6, 1.5))
    _cpu.append(L(3.4, _t, 6.0, _t, 1.5))
    _cpu.append(L(18.0, _t, 20.6, _t, 1.5))
ICONS["cpu"] = _cpu

# ---------------------------------------------------------------------------
ENTRIES = [(name, ICONS[name]) for name in PUBLIC_IDS]


# ---------------------------------------------------------------------------
# rasterizacion
# ---------------------------------------------------------------------------
def _caps(d, pts, w4):
    r = w4 / 2.0
    for (x, y) in pts:
        d.ellipse((x - r, y - r, x + r, y + r), fill=255)


def _bezier_points(segments, samples=18):
    pts = []
    for (p0, c1, c2, p1) in segments:
        for i in range(samples + 1):
            t = i / float(samples)
            mt = 1.0 - t
            x = (mt ** 3) * p0[0] + 3 * (mt ** 2) * t * c1[0] + \
                3 * mt * (t ** 2) * c2[0] + (t ** 3) * p1[0]
            y = (mt ** 3) * p0[1] + 3 * (mt ** 2) * t * c1[1] + \
                3 * mt * (t ** 2) * c2[1] + (t ** 3) * p1[1]
            if not pts or abs(x - pts[-1][0]) > 0.01 or abs(y - pts[-1][1]) > 0.01:
                pts.append((x, y))
    return pts


def rasterize(ops, size):
    spread = size * SS
    k = spread / GRID
    img = Image.new("L", (spread, spread), 0)
    d = ImageDraw.Draw(img)

    def sc(v):
        return v * k

    def W(w):
        return max(1, int(round(w * k)))

    for op in ops:
        kind = op[0]
        if kind == "line":
            (x0, y0, x1, y1), w = op[1], op[2]
            w4 = W(w)
            pts = [(sc(x0), sc(y0)), (sc(x1), sc(y1))]
            d.line(pts, fill=255, width=w4)
            _caps(d, pts, w4)
        elif kind == "poly":
            pts, w, closed = op[1], op[2], op[3]
            w4 = W(w)
            p = [(sc(x), sc(y)) for (x, y) in pts]
            if closed:
                p = p + [p[0]]
            d.line(p, fill=255, width=w4, joint="curve")
            _caps(d, [p[0], p[-1]], w4)
        elif kind == "rrect":
            (x, y, w, h, r), stroke = op[1], op[2]
            box = (sc(x), sc(y), sc(x + w), sc(y + h))
            rr = max(0.0, sc(r))
            if stroke <= 0:
                d.rounded_rectangle(box, radius=rr, fill=255)
            else:
                d.rounded_rectangle(box, radius=rr, outline=255, width=W(stroke))
        elif kind == "circle":
            (cx, cy, r), w = op[1], op[2]
            box = (sc(cx - r), sc(cy - r), sc(cx + r), sc(cy + r))
            d.ellipse(box, outline=255, width=W(w))
        elif kind == "dot":
            (cx, cy, r) = op[1]
            box = (sc(cx - r), sc(cy - r), sc(cx + r), sc(cy + r))
            d.ellipse(box, fill=255)
        elif kind == "ellipse":
            (cx, cy, rx, ry), w = op[1], op[2]
            box = (sc(cx - rx), sc(cy - ry), sc(cx + rx), sc(cy + ry))
            d.ellipse(box, outline=255, width=W(w))
        elif kind == "arc":
            (cx, cy, r, a0, a1), w = op[1], op[2]
            box = (sc(cx - r), sc(cy - r), sc(cx + r), sc(cy + r))
            d.arc(box, a0, a1, fill=255, width=W(w))
            caps = []
            for a in (a0, a1):
                ar = math.radians(a)
                caps.append((sc(cx + r * math.cos(ar)), sc(cy + r * math.sin(ar))))
            _caps(d, caps, W(w))
        elif kind == "earc":
            (cx, cy, rx, ry, a0, a1), w = op[1], op[2]
            box = (sc(cx - rx), sc(cy - ry), sc(cx + rx), sc(cy + ry))
            d.arc(box, a0, a1, fill=255, width=W(w))
            caps = []
            for a in (a0, a1):
                ar = math.radians(a)
                caps.append((sc(cx + rx * math.cos(ar)), sc(cy + ry * math.sin(ar))))
            _caps(d, caps, W(w))
        elif kind == "bezier":
            segs, w = op[1], op[2]
            pts = _bezier_points(segs)
            w4 = W(w)
            p = [(sc(x), sc(y)) for (x, y) in pts]
            d.line(p, fill=255, width=w4, joint="curve")
            _caps(d, [p[0], p[-1]], w4)
        else:
            raise ValueError("operacion desconocida: %r" % (kind,))

    out = img.resize((size, size), Image.BOX)
    return out.tobytes()


# ---------------------------------------------------------------------------
# validacion
# ---------------------------------------------------------------------------
def validate(masks, min_ink=None):
    errs = []
    for (name, _ops) in ENTRIES:
        for si, size in enumerate(SIZES):
            cov = masks[name][si]
            if len(cov) != size * size:
                errs.append("%s@%d: tamano %d" % (name, size, len(cov)))
                continue
            ink = sum(1 for v in cov if v > 24)
            total = float(size * size)
            if ink == 0:
                errs.append("%s@%d: icono vacio" % (name, size))
                continue
            ratio = ink / total
            if ratio < 0.025:
                errs.append("%s@%d: tinta insuficiente (%.1f%%)" % (name, size, ratio * 100))
            if min_ink is not None and ink < min_ink:
                errs.append("%s@%d: solo %d px" % (name, size, ink))
        # tamano mayor debe tener mas tinta que el menor
        small = sum(1 for v in masks[name][0] if v > 24)
        big = sum(1 for v in masks[name][-1] if v > 24)
        if not (big > small):
            errs.append("%s: cobertura no creciente (%d -> %d)" % (name, small, big))
    return errs


# ---------------------------------------------------------------------------
# emision de gui/icons_data.c
# ---------------------------------------------------------------------------
def emit(data_dir):
    masks = {}
    for (name, ops) in ENTRIES:
        masks[name] = [rasterize(ops, size) for size in SIZES]

    errs = validate(masks)
    if errs:
        print("VALIDACION FALLIDA:", file=sys.stderr)
        for e in errs:
            print("  -", e, file=sys.stderr)
        return None, None, 1

    offsets = []
    blob_parts = []
    pos = 0
    for (name, _ops) in ENTRIES:
        row = []
        for si, size in enumerate(SIZES):
            row.append(pos)
            blob_parts.append(masks[name][si])
            pos += size * size
        offsets.append(row)

    out = []
    out.append("/* gui/icons_data.c - atlas de cobertura alfa de la iconografia SereOS")
    out.append(" *")
    out.append(" * GENERADO AUTOMATICAMENTE por tools/gen_ui_icons.py; no editar a mano.")
    out.append(" * Arte original de SereOS (geometrico, lineal, rejilla 24x24, 4x supersampling).")
    out.append(" * Formato: mascaras de cobertura alfa 8bpp, una por icono y tamano;")
    out.append(" * fila a fila (w*h bytes), tintadas en tiempo de ejecucion con gfx_blit_alpha8.")
    out.append(" */")
    out.append("#include <stdint.h>")
    out.append("")
    out.append("typedef struct {")
    out.append("    const uint8_t *mask;")
    out.append("    uint16_t w, h;")
    out.append("} ui_icon_bitmap_t;")
    out.append("")
    out.append("/* tamanos del atlas, de menor a mayor */")
    out.append("const uint16_t ui_icon_dims[%d] = {%s};" %
               (len(SIZES), ", ".join(str(s) for s in SIZES)))
    out.append("")
    out.append("const uint16_t ui_icon_public_count = %du;" % len(PUBLIC_IDS))
    out.append("")
    out.append("const char *const ui_icon_names[%d] = {" % len(ENTRIES))
    for (name, _ops) in ENTRIES:
        out.append('    "%s",' % name)
    out.append("};")
    out.append("")
    out.append("/* mascaras concatenadas (icono mayor -> tamanos menores) */")
    out.append("static const uint8_t ui_icon_blob[%d] = {" % pos)
    cur = 0
    for (name, _ops) in ENTRIES:
        for si, size in enumerate(SIZES):
            out.append("    /* %s @ %dx%d */" % (name, size, size))
            data = masks[name][si]
            for i in range(0, len(data), 24):
                out.append("    " + " ".join("0x%02Xu," % b for b in data[i:i + 24]))
            cur += size * size
    out.append("};")
    out.append("")
    out.append("/* tabla de bitmaps: [icono][tamano] */")
    out.append("const ui_icon_bitmap_t ui_icon_bitmaps[%d][%d] = {" %
               (len(ENTRIES), len(SIZES)))
    for ei, (name, _ops) in enumerate(ENTRIES):
        out.append("    { /* %s */" % name)
        row = []
        for si, size in enumerate(SIZES):
            row.append("        { ui_icon_blob + %du, %d, %d }," %
                       (offsets[ei][si], size, size))
        out.extend(row)
        out.append("    },")
    out.append("};")
    out.append("")

    path = os.path.join(data_dir, "icons_data.c")
    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(out))

    total = pos
    return path, total, 0


# ---------------------------------------------------------------------------
# preview opcional (para revision de diseno; QA genera las capturas finales)
# ---------------------------------------------------------------------------
def write_preview(path, masks):
    BG = (11, 13, 18)
    PANEL = (30, 36, 48)
    TEXT = (242, 244, 248)
    DIM = (110, 119, 136)
    ACCENT = (76, 141, 255)

    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 12)
        small = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 10)
        big = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf", 20)
    except OSError:
        font = small = big = None

    def blend(color, a):
        return tuple((c * a + b * (255 - a)) // 255 for c, b in zip(color, BG))

    def draw_cov(img, x, y, cov, size, color):
        px = img.load()
        for yy in range(size):
            for xx in range(size):
                a = cov[yy * size + xx]
                if a:
                    px[x + xx, y + yy] = blend(color, a)

    cols = 6
    cell_w, cell_h = 168, 130
    rows = (len(PUBLIC_IDS) + cols - 1) // cols
    W = max(cols * cell_w + 48, 1460)
    H = rows * cell_h + 240
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((24, 18), "SereOS UI icons - linear geometric set", fill=TEXT, font=big)
    d.text((24, 46), "original SereOS art | 24x24 grid, 1.75 px stroke, 4x supersampling | atlas 16/20/24/32/40/48/64",
           fill=DIM, font=small)

    for i, name in enumerate(PUBLIC_IDS):
        col = i % cols
        row = i // cols
        cx = 24 + col * cell_w
        cy = 76 + row * cell_h
        d.rounded_rectangle((cx, cy, cx + 120, cy + 110), radius=10, outline=PANEL)
        draw_cov(img, cx + 8, cy + 8, masks[name][5], 48, TEXT)
        draw_cov(img, cx + 62, cy + 8, masks[name][2], 24, DIM)
        draw_cov(img, cx + 62, cy + 38, masks[name][1], 20, DIM)
        draw_cov(img, cx + 62, cy + 62, masks[name][0], 16, DIM)
        d.text((cx + 8, cy + 92), name, fill=TEXT, font=font)

    y0 = 76 + rows * cell_h + 14
    d.text((24, y0), "atlas sizes (sample: game, files, info, clock):",
           fill=TEXT, font=font)
    sy = y0 + 26
    sx = 24
    for name in ("game", "files", "info", "clock"):
        for si, s in enumerate(SIZES):
            d.rectangle((sx - 2, sy - 2, sx + s + 1, sy + s + 1), outline=PANEL)
            draw_cov(img, sx, sy, masks[name][si], s, TEXT)
            sx += s + 12
        sx += 14

    img.save(path)
    return path


# ---------------------------------------------------------------------------
def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root, "gui")
    preview = None
    args = argv[1:]
    if args and args[0] == "--preview":
        if len(args) < 2:
            print("uso: gen_ui_icons.py --preview SALIDA.png", file=sys.stderr)
            return 2
        preview = args[1]

    masks = {}
    for (name, ops) in ENTRIES:
        masks[name] = [rasterize(ops, size) for size in SIZES]

    errs = validate(masks)
    if errs:
        print("VALIDACION FALLIDA:", file=sys.stderr)
        for e in errs:
            print("  -", e, file=sys.stderr)
        return 1

    path, total, rc = emit(data_dir)
    if rc:
        return rc

    # estadisticas
    name_w = max(len(n) for n, _ in ENTRIES)
    print("OK: %d iconos x %d tamanos" % (len(ENTRIES), len(SIZES)))
    print("  datos      : %s (%d bytes de cobertura)" % (path, total))
    print("  tamanos    : %s" % ", ".join(str(s) for s in SIZES))
    biggest = max(ENTRIES, key=lambda e: max(sum(1 for v in masks[e[0]][si] if v > 24)
                                             for si in range(len(SIZES))))
    print("  validacion : todos no vacios, cobertura creciente, trazo 1.75/24")
    print("  ids        : " + " ".join(PUBLIC_IDS[:6]) + " ...")
    if preview:
        p = write_preview(preview, masks)
        print("  preview    : %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
