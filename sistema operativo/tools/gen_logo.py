#!/usr/bin/env python3
"""tools/gen_logo.py - genera el logotipo OFICIAL de SereOS para el kernel.

Fuente unica: assets/logo/official_logo.png (imagen oficial proporcionada por
el propietario del proyecto; 1296x1213, RGB, fondo azul #004EFD y S blanca).
NO se rediseña, recorta ni deforma: el sprite completo solo se escala con
LANCZOS preservando la proporcion original (1296/1213 = 1,0685) y el glifo S
se extrae de la MISMA imagen con su caja alfa.

Genera:
  gui/logo_data.h
      struct logo_bitmap_t (sprites RGB565 completos, compat PLAIN)
      struct logo_glyph_t  (mascaras alfa 8bpp del glifo S)
      contadores, alturas y macros de la geometria del glifo.
  gui/logo_data.c
      una tabla RGB565 por altura de sprite y una mascara alfa 8bpp por
      altura de glifo.

SPRITES COMPLETOS (compatibilidad, LOGO_SHAPE_PLAIN)
  Alturas: 16, 18, 20, 22, 24, 28, 32, 40, 48, 56, 64, 96, 128 px.
  Anchos: round(h * 1296 / 1213).

GLIFO S (mascaras alfa 8bpp, LOGO_SHAPE_CIRCLE/SQUIRCLE/ROUNDED)
  Se extrae el canal R (valido porque el fondo tiene R=0..4 y la S blanca
  R=255): alfa = clamp((r - r_bg) / (255 - r_bg)), con r_bg = 4 (maximo R del
  fondo medido en el PNG oficial). La caja del glifo se obtiene del propio
  canal alfa (incluye el suavizado de los bordes) y cada mascara se escala con
  LANCZOS a la altura pedida conservando la proporcion nominal oficial
  354/376 (0,9415).

  Alturas: 8..32 px paso 1, 34..64 paso 2, 68..96 paso 4, 104..128 paso 8,
  mas 43 y 49 px (alturas exactas de SPLASH_LOGO_SMALL y SPLASH_LOGO). El
  componente elige la altura exacta si existe; si no, la mas cercana.

  Las mascaras se guardan fila a fila (w*h bytes) y en runtime solo se tintan
  y componen con gfx_blit_alpha8(), sin escalado ni asignaciones de memoria.

SEGUNDA FUENTE: GLIFO RIBBON (solo top bar)
  assets/logo/ribbon_s_logo.png (1296x1213 RGBA, S blanca sobre transparente).
  Se usa el canal A con umbral > 16 (descarta ~78.000 px de halo con alfa
  1..15 que, si no, agrandan la caja a 1193x1167) y se normaliza 255/254.
  Caja real (243,190) 834x944 px, proporcion 834/944 = 0,8835; el glifo se
  centra por bbox. Se generan mascaras alfa 8bpp para 8..32 paso 1 y 34..64
  paso 2 (el top bar usa 12 px) en gui/logo_ribbon_data.c/.h. La tabla
  OFICIAL (gui/logo_data.*) se mantiene BYTE-IDÉNTICA.

Uso:
  py=~/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
  $py tools/gen_logo.py
  $py tools/gen_logo.py --preview /tmp/logo_sizes.png

El script es determinista (mismas entradas -> mismos bytes) y falla con
codigo 1 si alguna validacion (proporcion, caja del glifo, cobertura, clave
de transparencia) no se cumple.
"""
import math
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "logo", "official_logo.png")
OUT_C = os.path.join(ROOT, "gui", "logo_data.c")
OUT_H = os.path.join(ROOT, "gui", "logo_data.h")

# proporcion original oficial (no cambiar)
SRC_W, SRC_H = 1296, 1213
HEIGHTS = (16, 18, 20, 22, 24, 28, 32, 40, 48, 56, 64, 96, 128)
TRANSPARENT = 0xF81F          # clave de transparencia del motor (no debe usarse)

# glifo S: caja oficial nominal y umbral de fondo del canal R
GLYPH_ASPECT_NUM = 354
GLYPH_ASPECT_DEN = 376
GLYPH_BG_R = 4                # maximo R del fondo azul medido en el PNG
GLYPH_EXACT_HEIGHTS = (43, 49)   # SPLASH_LOGO_SMALL / SPLASH_LOGO
GLYPH_VALUES_PER_LINE = 24

# glifo RIBBON: segunda fuente de marca, solo para la top bar
RIB_SRC = os.path.join(ROOT, "assets", "logo", "ribbon_s_logo.png")
OUT_RIB_C = os.path.join(ROOT, "gui", "logo_ribbon_data.c")
OUT_RIB_H = os.path.join(ROOT, "gui", "logo_ribbon_data.h")
RIB_SRC_W, RIB_SRC_H = 1296, 1213
RIB_ALPHA_MIN = 16             # umbral que elimina el halo de alfa 1..15
RIB_BODY_ALPHA = 254           # alfa del cuerpo del glifo en el PNG
RIB_ASPECT_NUM = 834           # caja real del glifo (alfa > 16)
RIB_ASPECT_DEN = 944
RIB_VALUES_PER_LINE = 24


def width_for(h):
    """ancho derivado de la proporcion oficial (redondeo al mas cercano)."""
    return int(math.floor(h * SRC_W / float(SRC_H) + 0.5))


def glyph_width_for(h):
    """ancho del glifo segun la proporcion nominal oficial 354/376."""
    return int(math.floor(h * GLYPH_ASPECT_NUM / float(GLYPH_ASPECT_DEN) + 0.5))


def glyph_heights():
    """alturas de las mascaras del glifo (ascendentes y sin duplicados)."""
    hs = set()
    for h in range(8, 33):
        hs.add(h)
    for h in range(34, 65, 2):
        hs.add(h)
    for h in range(68, 97, 4):
        hs.add(h)
    for h in range(104, 129, 8):
        hs.add(h)
    hs.update(GLYPH_EXACT_HEIGHTS)
    return tuple(sorted(hs))


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def decode(v):
    r = ((v >> 11) & 0x1F) << 3
    g = ((v >> 5) & 0x3F) << 2
    b = (v & 0x1F) << 3
    return (r | (r >> 5), g | (g >> 6), b | (b >> 5))


def load_source():
    if not os.path.isfile(SRC):
        raise SystemExit("ERROR: falta %s" % SRC)
    im = Image.open(SRC)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    if im.mode == "RGBA":
        # la identidad oficial es opaca; si hubiera alfa se compone sobre azul
        bg = Image.new("RGB", im.size, (2, 81, 249))
        bg.paste(im.convert("RGB"), (0, 0), im.split()[-1])
        im = bg
    if im.size != (SRC_W, SRC_H):
        raise SystemExit("ERROR: se esperaba %dx%d, encontrado %dx%d" %
                         (SRC_W, SRC_H, im.size[0], im.size[1]))
    return im


def validate_sprite(im, h):
    w, hh = im.size
    px = im.load()
    blue = white = 0
    transparent_key = 0
    for y in range(hh):
        for x in range(w):
            r, g, b = px[x, y]
            v = rgb565(r, g, b)
            if v == TRANSPARENT:
                transparent_key += 1
            if b >= 140 and r <= 110 and g <= 140:
                blue += 1
            if r >= 205 and g >= 205 and b >= 205:
                white += 1
    total = w * hh
    errs = []
    if w != width_for(h):
        errs.append("ancho %d != %d" % (w, width_for(h)))
    if total == 0:
        errs.append("sprite vacio")
    if transparent_key:
        errs.append("%d px con la clave transparente 0x%04X" % (transparent_key, TRANSPARENT))
    if blue < total * 0.35:
        errs.append("fondo azul insuficiente (%d/%d)" % (blue, total))
    if white < max(4, total // 400):
        errs.append("S blanca insuficiente (%d px)" % white)
    # bordes: el fondo oficial llega al borde (azul), sin recortes raros
    for (x, y) in ((0, 0), (w - 1, 0), (0, hh - 1), (w - 1, hh - 1)):
        r, g, b = px[x, y]
        if not (b >= 120 and b > r + 60):
            errs.append("esquina (%d,%d) no azul: %r" % (x, y, (r, g, b)))
    return errs, blue, white


def extract_glyph(src):
    """extrae la mascara alfa del glifo S del mismo PNG oficial.

    Devuelve (imagen alfa recortada a la caja del glifo, (x0,y0,ancho,alto)).
    """
    red = src.split()[0]
    lut = []
    for v in range(256):
        if v <= GLYPH_BG_R:
            lut.append(0)
        else:
            lut.append(max(0, min(255, int(round(
                (v - GLYPH_BG_R) * 255.0 / (255 - GLYPH_BG_R))))))
    alpha = red.point(lut)
    box = alpha.getbbox()
    if box is None:
        raise SystemExit("ERROR: el PNG oficial no contiene glifo visible")
    gx0, gy0, gx1, gy1 = box
    gw, gh = gx1 - gx0, gy1 - gy0
    if gw < 340 or gw > 380 or gh < 365 or gh > 395:
        raise SystemExit("ERROR: caja del glifo inesperada %dx%d (esperado ~358x378)" %
                         (gw, gh))
    aspect = gw / float(gh)
    if aspect < 0.90 or aspect > 0.99:
        raise SystemExit("ERROR: proporcion del glifo %.4f fuera de rango" % aspect)
    if gx0 <= 0 or gy0 <= 0 or gx1 >= SRC_W or gy1 >= SRC_H:
        raise SystemExit("ERROR: el glifo toca el borde del PNG oficial")
    return alpha.crop(box), (gx0, gy0, gw, gh)


def build_glyphs(alpha_src):
    """escala la mascara del glifo a todas las alturas pedidas."""
    sw, sh = alpha_src.size
    glyphs = []
    errs = []
    for h in glyph_heights():
        w = glyph_width_for(h)
        m = alpha_src.resize((w, h), Image.Resampling.LANCZOS)
        vals = list(m.tobytes())
        coverage = sum(vals) / 255.0 / float(w * h)
        emax = max(vals)
        # bordes de la caja del glifo: deben conservar algo de cobertura
        edge = vals[:w] + vals[-w:] + [vals[y * w] for y in range(h)] + \
            [vals[y * w + w - 1] for y in range(h)]
        if emax < 200:
            errs.append("%dpx: alfa maximo %d insuficiente" % (h, emax))
        if coverage < 0.35 or coverage > 0.70:
            errs.append("%dpx: cobertura %.3f fuera de rango" % (h, coverage))
        if max(edge) == 0:
            errs.append("%dpx: la mascara no toca la caja del glifo" % h)
        # centro de masa cerca del centro de la caja (S oficial equilibrada)
        sx = sy = 0
        for y in range(h):
            row = vals[y * w:(y + 1) * w]
            sy += y * sum(row)
            sx += sum(x * v for x, v in enumerate(row))
        total = sum(vals)
        cx = sx / float(total) if total else 0.0
        cy = sy / float(total) if total else 0.0
        if abs(cx - (w - 1) / 2.0) > w * 0.06:
            errs.append("%dpx: glifo descentrado en x (%.2f de %d)" % (h, cx, w))
        if abs(cy - (h - 1) / 2.0) > h * 0.06:
            errs.append("%dpx: glifo descentrado en y (%.2f de %d)" % (h, cy, h))
        glyphs.append((h, w, vals))
    return glyphs, errs



def ribbon_width_for(h):
    """ancho del glifo ribbon segun su caja real 834/944."""
    return int(math.floor(h * RIB_ASPECT_NUM / float(RIB_ASPECT_DEN) + 0.5))


def ribbon_heights():
    """alturas de las mascaras ribbon: 8..32 paso 1 y 34..64 paso 2."""
    hs = set()
    for h in range(8, 33):
        hs.add(h)
    for h in range(34, 65, 2):
        hs.add(h)
    return tuple(sorted(hs))


def load_ribbon_alpha():
    """extrae y normaliza el canal A del PNG ribbon.

    Devuelve (imagen alfa recortada por bbox, (x0,y0,ancho,alto)).
    """
    if not os.path.isfile(RIB_SRC):
        raise SystemExit("ERROR: falta %s" % RIB_SRC)
    im = Image.open(RIB_SRC)
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    if im.size != (RIB_SRC_W, RIB_SRC_H):
        raise SystemExit("ERROR: ribbon se esperaba %dx%d, encontrado %dx%d" %
                         (RIB_SRC_W, RIB_SRC_H, im.size[0], im.size[1]))
    alpha = im.split()[3]
    lut = []
    for a in range(256):
        if a < RIB_ALPHA_MIN:
            lut.append(0)
        else:
            lut.append(max(0, min(255, int(round(
                a * 255.0 / float(RIB_BODY_ALPHA))))))
    norm = alpha.point(lut)
    box = norm.getbbox()
    if box is None:
        raise SystemExit("ERROR: el PNG ribbon no contiene glifo visible")
    gx0, gy0, gx1, gy1 = box
    gw, gh = gx1 - gx0, gy1 - gy0
    if gw < 820 or gw > 850 or gh < 930 or gh > 960:
        raise SystemExit("ERROR: caja ribbon inesperada %dx%d (esperado 834x944)" %
                         (gw, gh))
    aspect = gw / float(gh)
    if aspect < 0.87 or aspect > 0.90:
        raise SystemExit("ERROR: proporcion ribbon %.4f fuera de rango" % aspect)
    return norm.crop(box), (gx0, gy0, gw, gh)


def build_ribbon_glyphs(alpha_src):
    """escala el glifo ribbon a todas las alturas pedidas y valida."""
    glyphs = []
    errs = []
    for h in ribbon_heights():
        w = ribbon_width_for(h)
        m = alpha_src.resize((w, h), Image.Resampling.LANCZOS)
        vals = list(m.tobytes())
        coverage = sum(vals) / 255.0 / float(w * h)
        emax = max(vals)
        edge = vals[:w] + vals[-w:] + [vals[y * w] for y in range(h)] + \
            [vals[y * w + w - 1] for y in range(h)]
        if emax < 250:
            errs.append("ribbon %dpx: alfa maximo %d insuficiente" % (h, emax))
        if coverage < 0.40 or coverage > 0.70:
            errs.append("ribbon %dpx: cobertura %.3f fuera de rango" % (h, coverage))
        if max(edge) == 0:
            errs.append("ribbon %dpx: la mascara no toca la caja" % h)
        sx = sy = 0
        for y in range(h):
            row = vals[y * w:(y + 1) * w]
            sy += y * sum(row)
            sx += sum(x * v for x, v in enumerate(row))
        total = sum(vals)
        cx = sx / float(total) if total else 0.0
        cy = sy / float(total) if total else 0.0
        if abs(cx - (w - 1) / 2.0) > w * 0.10:
            errs.append("ribbon %dpx: glifo descentrado en x (%.2f de %d)" %
                        (h, cx, w))
        if abs(cy - (h - 1) / 2.0) > h * 0.06:
            errs.append("ribbon %dpx: glifo descentrado en y (%.2f de %d)" %
                        (h, cy, h))
        glyphs.append((h, w, vals))
    return glyphs, errs


def write_ribbon_outputs(alpha_src, box, glyphs):
    """genera gui/logo_ribbon_data.h/.c (tabla independiente de la oficial)."""
    gsw, gsh = alpha_src.size
    gcount = len(glyphs)
    gdata_bytes = sum(w * h for (h, w, vals) in glyphs)

    hdr = []
    hdr.append("/* gui/logo_ribbon_data.h - glifo RIBBON de SereOS (solo top bar)")
    hdr.append(" *")
    hdr.append(" * Segunda fuente de marca: assets/logo/ribbon_s_logo.png")
    hdr.append(" * (1296x1213 RGBA, S blanca sobre transparente), proporcionada")
    hdr.append(" * por el propietario del proyecto para la barra superior.")
    hdr.append(" * El resto de la interfaz usa el glifo OFICIAL (gui/logo_data.h).")
    hdr.append(" *")
    hdr.append(" * Mascaras de cobertura alfa 8bpp del canal A, umbral > %d" % RIB_ALPHA_MIN)
    hdr.append(" * (elimina el halo de alfa 1..15) y normalizadas 255/%d." % RIB_BODY_ALPHA)
    hdr.append(" * Caja real %dx%d, proporcion %.4f; el glifo se centra por" %
               (gsw, gsh, gsw / float(gsh)))
    hdr.append(" * bbox sin deformar.")
    hdr.append(" *")
    hdr.append(" * GENERADO AUTOMATICAMENTE por tools/gen_logo.py; no editar a mano.")
    hdr.append(" * La tabla OFICIAL (gui/logo_data.*) es independiente y no cambia.")
    hdr.append(" */")
    hdr.append("#ifndef SEREOS_LOGO_RIBBON_DATA_H")
    hdr.append("#define SEREOS_LOGO_RIBBON_DATA_H")
    hdr.append("#include <stdint.h>")
    hdr.append("")
    hdr.append("#define LOGO_RIBBON_COUNT %du" % gcount)
    hdr.append("#define LOGO_RIBBON_MIN_HEIGHT %d" % glyphs[0][0])
    hdr.append("#define LOGO_RIBBON_MAX_HEIGHT %d" % glyphs[-1][0])
    hdr.append("#define LOGO_RIBBON_SRC_W %d" % gsw)
    hdr.append("#define LOGO_RIBBON_SRC_H %d" % gsh)
    hdr.append("")
    hdr.append("typedef struct {")
    hdr.append("\tuint16_t w, h;")
    hdr.append("\tconst uint8_t *mask;  /* cobertura alfa 8bpp, w*h bytes */")
    hdr.append("} logo_ribbon_glyph_t;")
    hdr.append("")
    hdr.append("/* una entrada por altura de glifo ribbon generada (ascendente) */")
    hdr.append("extern const logo_ribbon_glyph_t logo_ribbon_glyphs[LOGO_RIBBON_COUNT];")
    hdr.append("extern const uint16_t logo_ribbon_heights[LOGO_RIBBON_COUNT];")
    hdr.append("")
    hdr.append("#endif /* SEREOS_LOGO_RIBBON_DATA_H */")
    hdr.append("")

    with open(OUT_RIB_H, "w", encoding="ascii") as f:
        f.write("\n".join(hdr))

    out = []
    out.append("/* gui/logo_ribbon_data.c - mascaras alfa 8bpp del glifo RIBBON")
    out.append(" *")
    out.append(" * GENERADO AUTOMATICAMENTE por tools/gen_logo.py; no editar a mano.")
    out.append(" * Fuente: assets/logo/ribbon_s_logo.png (1296x1213 RGBA),")
    out.append(" * asset proporcionado por el propietario del proyecto para la top bar.")
    out.append(" * Alfa desde el canal A: umbral > %d y normalizado 255/%d." %
               (RIB_ALPHA_MIN, RIB_BODY_ALPHA))
    out.append(" * Caja real %dx%d (proporcion %.4f), centrado por bbox." %
               (gsw, gsh, gsw / float(gsh)))
    out.append(" */")
    out.append('#include "logo_ribbon_data.h"')
    out.append("")
    for (h, w, vals) in glyphs:
        out.append("/* altura %d, %dx%d, %d bytes */" % (h, w, h, w * h))
        out.append("static const uint8_t logo_ribbon_mask_%d[%d] = {" % (h, w * h))
        step = RIB_VALUES_PER_LINE
        for i in range(0, len(vals), step):
            out.append("\t" + ", ".join("0x%02X" % v for v in vals[i:i + step]) + ",")
        out.append("};")
        out.append("")
    out.append("const uint16_t logo_ribbon_heights[LOGO_RIBBON_COUNT] = {")
    out.append("\t" + ", ".join(str(h) for (h, w, vals) in glyphs) + ",")
    out.append("};")
    out.append("")
    out.append("const logo_ribbon_glyph_t logo_ribbon_glyphs[LOGO_RIBBON_COUNT] = {")
    for (h, w, vals) in glyphs:
        out.append("\t{ %d, %d, logo_ribbon_mask_%d },   /* altura %d */" %
                   (w, h, h, h))
    out.append("};")
    out.append("")

    with open(OUT_RIB_C, "w", encoding="ascii") as f:
        f.write("\n".join(out))
    return gcount, gdata_bytes


def main(argv):
    preview = None
    if len(argv) > 1:
        if argv[1] != "--preview" or len(argv) < 3:
            print("uso: gen_logo.py [--preview SALIDA.png]", file=sys.stderr)
            return 2
        preview = argv[2]

    src = load_source()
    sprites = []
    errs = []
    for h in HEIGHTS:
        w = width_for(h)
        im = src.resize((w, h), Image.Resampling.LANCZOS)
        e, blue, white = validate_sprite(im, h)
        errs += ["%dpx: %s" % (h, x) for x in e]
        sprites.append((h, w, im))

    alpha_src, gbox = extract_glyph(src)
    gsw, gsh = alpha_src.size
    glyphs, gerrs = build_glyphs(alpha_src)
    errs += gerrs

    rib_alpha, rib_box = load_ribbon_alpha()
    rib_glyphs, rib_errs = build_ribbon_glyphs(rib_alpha)
    errs += rib_errs

    if errs:
        print("VALIDACION FALLIDA:", file=sys.stderr)
        for e in errs:
            print("  -", e, file=sys.stderr)
        return 1

    gcount = len(glyphs)
    gdata_bytes = sum(w * h for (h, w, vals) in glyphs)

    # ------------------------- gui/logo_data.h -------------------------
    hdr = []
    hdr.append("/* gui/logo_data.h - logotipo OFICIAL de SereOS")
    hdr.append(" *")
    hdr.append(" * Identidad oficial proporcionada por el propietario del proyecto")
    hdr.append(" * (assets/logo/official_logo.png, 1296x1213, fondo azul y S blanca).")
    hdr.append(" *")
    hdr.append(" * Sprites RGB565 completos (LOGO_SHAPE_PLAIN): escalados con LANCZOS")
    hdr.append(" * preservando la proporcion original; NO se redisenan, recortan ni")
    hdr.append(" * deforman.")
    hdr.append(" *")
    hdr.append(" * Mascaras alfa 8bpp del glifo S (FORMAS DE CONTENEDOR): extraidas del")
    hdr.append(" * mismo PNG oficial con alfa = clamp((R - %d)/(255 - %d)); en runtime" %
               (GLYPH_BG_R, GLYPH_BG_R))
    hdr.append(" * solo se tintan con gfx_blit_alpha8() y se centran en el contenedor.")
    hdr.append(" *")
    hdr.append(" * GENERADO AUTOMATICAMENTE por tools/gen_logo.py; no editar a mano.")
    hdr.append(" * Ambas tablas estan ordenadas por altura ascendente: se elige la")
    hdr.append(" * altura exacta si existe o, en su defecto, la mas cercana.")
    hdr.append(" */")
    hdr.append("#ifndef SEREOS_LOGO_DATA_H")
    hdr.append("#define SEREOS_LOGO_DATA_H")
    hdr.append("#include <stdint.h>")
    hdr.append("")
    hdr.append("#define LOGO_SIZE_COUNT %du" % len(HEIGHTS))
    hdr.append("")
    hdr.append("typedef struct {")
    hdr.append("\tuint16_t w, h;")
    hdr.append("\tconst uint16_t *px;   /* RGB565, w*h pixeles, sin transparencia */")
    hdr.append("} logo_bitmap_t;")
    hdr.append("")
    hdr.append("/* una entrada por altura generada (ascendente) */")
    hdr.append("extern const logo_bitmap_t logo_bitmaps[LOGO_SIZE_COUNT];")
    hdr.append("extern const uint16_t logo_heights[LOGO_SIZE_COUNT];")
    hdr.append("")
    hdr.append("/* ------------------------------------------------------------------ */")
    hdr.append("/* glifo S blanco: mascaras de cobertura alfa 8bpp (fila a fila)      */")
    hdr.append("/* ------------------------------------------------------------------ */")
    hdr.append("#define LOGO_GLYPH_COUNT %du" % gcount)
    hdr.append("#define LOGO_GLYPH_MIN_HEIGHT %d" % glyphs[0][0])
    hdr.append("#define LOGO_GLYPH_MAX_HEIGHT %d" % glyphs[-1][0])
    hdr.append("#define LOGO_GLYPH_SRC_W %d" % gsw)
    hdr.append("#define LOGO_GLYPH_SRC_H %d" % gsh)
    hdr.append("")
    hdr.append("typedef struct {")
    hdr.append("\tuint16_t w, h;")
    hdr.append("\tconst uint8_t *mask;  /* cobertura alfa 8bpp, w*h bytes */")
    hdr.append("} logo_official_glyph_t;")
    hdr.append("")
    hdr.append("/* gui/logo.h define el enum logo_glyph_t (OFICIAL/RIBBON).  Para no")
    hdr.append(" * colisionar con ese nombre, aqui el struct se llama")
    hdr.append(" * logo_official_glyph_t; se mantiene el alias historico solo para el")
    hdr.append(" * codigo generado que aun usa logo_glyph_t. */")
    hdr.append("#ifndef SEREOS_LOGO_GLYPH_T_DEFINED")
    hdr.append("typedef logo_official_glyph_t logo_glyph_t;")
    hdr.append("#endif")
    hdr.append("")
    hdr.append("/* una entrada por altura de glifo generada (ascendente) */")
    hdr.append("extern const logo_official_glyph_t logo_glyphs[LOGO_GLYPH_COUNT];")
    hdr.append("extern const uint16_t logo_glyph_heights[LOGO_GLYPH_COUNT];")
    hdr.append("")
    hdr.append("#endif /* SEREOS_LOGO_DATA_H */")
    hdr.append("")

    with open(OUT_H, "w", encoding="ascii") as f:
        f.write("\n".join(hdr))

    # ------------------------- gui/logo_data.c -------------------------
    out = []
    out.append("/* gui/logo_data.c - logotipo OFICIAL de SereOS")
    out.append(" *")
    out.append(" * GENERADO AUTOMATICAMENTE por tools/gen_logo.py; no editar a mano.")
    out.append(" * Fuente: assets/logo/official_logo.png (1296x1213, proporcion 1296/1213),")
    out.append(" * identidad oficial proporcionada por el propietario del proyecto.")
    out.append(" *")
    out.append(" * 1) sprites RGB565 completos (LOGO_SHAPE_PLAIN): escalado LANCZOS, sin")
    out.append(" *    rediseno, recorte ni deformacion.")
    out.append(" * 2) mascaras alfa 8bpp del glifo S (formas de contenedor): extraidas del")
    out.append(" *    canal R del mismo PNG, fila a fila, para gfx_blit_alpha8().")
    out.append(" */")
    out.append('#include "logo_data.h"')
    out.append("")
    for (h, w, im) in sprites:
        px = im.load()
        vals = []
        for y in range(h):
            row = []
            for x in range(w):
                r, g, b = px[x, y]
                row.append("0x%04X" % rgb565(r, g, b))
            vals.append("\t" + ", ".join(row) + ",")
        out.append("/* %dx%d (altura %d) */" % (w, h, h))
        out.append("static const uint16_t logo_px_%d[%d] = {" % (h, w * h))
        out.extend(vals)
        out.append("};")
        out.append("")
    out.append("const uint16_t logo_heights[LOGO_SIZE_COUNT] = {")
    out.append("\t" + ", ".join(str(h) for (h, w, im) in sprites) + ",")
    out.append("};")
    out.append("")
    out.append("const logo_bitmap_t logo_bitmaps[LOGO_SIZE_COUNT] = {")
    for (h, w, im) in sprites:
        out.append("\t{ %d, %d, logo_px_%d },   /* altura %d */" % (w, h, h, h))
    out.append("};")
    out.append("")
    out.append("/* ------------------------------------------------------------------ */")
    out.append("/* glifo S: mascaras de cobertura alfa 8bpp, una por altura            */")
    out.append("/* ------------------------------------------------------------------ */")
    out.append("")
    for (h, w, vals) in glyphs:
        out.append("/* altura %d, %dx%d, %d bytes */" % (h, w, h, w * h))
        out.append("static const uint8_t logo_glyph_mask_%d[%d] = {" % (h, w * h))
        step = GLYPH_VALUES_PER_LINE
        for i in range(0, len(vals), step):
            out.append("\t" + ", ".join("0x%02X" % v for v in vals[i:i + step]) + ",")
        out.append("};")
        out.append("")
    out.append("const uint16_t logo_glyph_heights[LOGO_GLYPH_COUNT] = {")
    out.append("\t" + ", ".join(str(h) for (h, w, vals) in glyphs) + ",")
    out.append("};")
    out.append("")
    out.append("const logo_glyph_t logo_glyphs[LOGO_GLYPH_COUNT] = {")
    for (h, w, vals) in glyphs:
        out.append("\t{ %d, %d, logo_glyph_mask_%d },   /* altura %d */" % (w, h, h, h))
    out.append("};")
    out.append("")

    with open(OUT_C, "w", encoding="ascii") as f:
        f.write("\n".join(out))

    rib_count, rib_bytes = write_ribbon_outputs(rib_alpha, rib_box, rib_glyphs)

    total_px = sum(w * h for (h, w, im) in sprites)
    print("OK: logotipo oficial generado para %d alturas de sprite y %d de glifo" %
          (len(HEIGHTS), gcount))
    print("  fuente     : %s (%dx%d, proporcion %.4f)" %
          (os.path.relpath(SRC, ROOT), SRC_W, SRC_H, SRC_W / float(SRC_H)))
    print("  header     : %s" % os.path.relpath(OUT_H, ROOT))
    print("  datos      : %s (%d bytes RGB565 + %d bytes alfa, %d pixeles)" %
          (os.path.relpath(OUT_C, ROOT), total_px * 2, gdata_bytes,
           total_px + gdata_bytes))
    print("  alturas    : " + ", ".join(
        "%d(%dx%d)" % (h, w, h) for (h, w, im) in sprites))
    print("  glifo      : caja %dx%d en (%d,%d); alfa desde R con fondo R=%d" %
          (gsw, gsh, gbox[0], gbox[1], GLYPH_BG_R))
    print("  glifo alt. : " + ", ".join("%d(%dx%d)" % (h, w, h) for (h, w, vals) in glyphs))
    print("  validacion : proporcion, bordes azules, S blanca, sin clave 0x%04X," %
          TRANSPARENT)
    print("               caja/centro/cobertura del glifo y aspecto %d/%d" %
          (GLYPH_ASPECT_NUM, GLYPH_ASPECT_DEN))
    print("  ribbon     : %s (%dx%d bbox en (%d,%d), proporcion %.4f, alfa>%d)" %
          (os.path.relpath(RIB_SRC, ROOT), rib_box[2], rib_box[3],
           rib_box[0], rib_box[1], rib_box[2] / float(rib_box[3]), RIB_ALPHA_MIN))
    print("  ribbon alt.: %d alturas (8..32 paso 1, 34..64 paso 2) -> %d bytes" %
          (rib_count, rib_bytes))
    print("  ribbon out : %s + %s (tabla oficial intacta)" %
          (os.path.relpath(OUT_RIB_H, ROOT), os.path.relpath(OUT_RIB_C, ROOT)))

    if preview:
        make_preview(preview, src, sprites)
        print("  preview    : %s" % preview)
    return 0


def make_preview(path, src, sprites):
    from PIL import ImageDraw, ImageFont
    BG = (11, 13, 18)
    PANEL = (30, 36, 48)
    TEXT = (242, 244, 248)
    DIM = (120, 130, 148)
    ACCENT = (76, 141, 255)

    try:
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 13)
        small = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 11)
        big = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf", 20)
    except OSError:
        font = small = big = None

    W = 1500
    H = 820
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((28, 20), "SereOS - logotipo oficial (assets/logo/official_logo.png)",
           font=big, fill=TEXT)
    d.text((28, 48), "RGB565 LANCZOS | proporcion original 1296/1213 | "
           "alturas 16..128 | sin rediseno/recorte",
           font=small, fill=DIM)

    def row_cell(x, y, im, scale, label):
        w, h = im.size
        z = im.resize((w * scale, h * scale), Image.Resampling.NEAREST) if scale > 1 else im
        d.rectangle((x - 2, y - 2, x + w * scale + 1, y + h * scale + 1), outline=PANEL)
        img.paste(z, (x, y))
        d.text((x, y + h * scale + 6), label, font=small, fill=DIM)
        return w * scale + 24

    # fila 1: tamanos nativos
    y = 92
    d.text((28, y - 24), "tamanos nativos (altura pedida; ancho derivado)",
           font=font, fill=ACCENT)
    x = 40
    for (h, w, im) in sprites:
        x += row_cell(x, y, im, 1, "%dx%d" % (w, h))

    # fila 2: zoom 6x de los pequenos (la S debe seguir limpia)
    y = 300
    d.text((28, y - 24), "zoom 6x (16-32): trazo de la S sin pixelado agresivo",
           font=font, fill=ACCENT)
    x = 40
    for (h, w, im) in sprites:
        if h <= 32:
            x += row_cell(x, y, im, 6, "%d" % h)

    # fila 3: 2x de los grandes
    y = 540
    d.text((28, y - 24), "2x (40-96) y 128 nativo: detalle de la identidad",
           font=font, fill=ACCENT)
    x = 40
    for (h, w, im) in sprites:
        if h >= 40 and h <= 96:
            x += row_cell(x, y, im, 2, "%d" % h)
    for (h, w, im) in sprites:
        if h == 128:
            x += row_cell(x, y, im, 1, "128")

    d.text((28, H - 24), "generado por tools/gen_logo.py --preview /tmp/logo_sizes.png",
           font=small, fill=DIM)
    img.save(path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
