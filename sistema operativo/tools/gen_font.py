#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/gen_font.py - generador de la fuente bitmap 8x16 de SereOS.

Genera graphics/font_data.c con:

    const uint8_t font8x16[FONT_COUNT][FONT_GLYPH_H];

ASCII imprimible 32..126 (95 glifos), 16 filas de 8 bits por glifo,
bit 7 = pixel mas a la izquierda (misma convencion que graphics/font.h).

Origen de los datos
-------------------
Via preferente: rasterizacion con Pillow (PIL) de "DejaVu Sans Mono" a
13 px, anclaje "ls" (baseline) en la fila 13 del celda de 16 y umbral de
binarizacion 96.  DejaVu deriva de Bitstream Vera:

    Fonts are (c) Bitstream. DejaVu changes are in public domain.
    Copyright (c) 2003 by Bitstream, Inc. All Rights Reserved.
    Bitstream Vera is a trademark of Bitstream, Inc.
    Licencia: Bitstream Vera Fonts Copyright (permisiva, ver el aviso
    completo incluido al final de graphics/font_data.c).

Via alternativa (sin PIL, sin fuentes del sistema): tabla de respaldo
incrustada en este mismo archivo, con exactamente los mismos bytes que
produjo la rasterizacion.  Asi el resultado es reproducible en cualquier
maquina: la fuente queda compilada dentro del kernel y no hay dependencia
de ejecucion.

Uso:
    python3 tools/gen_font.py                 # rasteriza (si puede) y escribe
    python3 tools/gen_font.py --force-fallback  # usa solo la tabla incrustada
    python3 tools/gen_font.py --dump-hex      # imprime la tabla en hexadecimal
    python3 tools/gen_font.py --out ruta.c    # cambia la salida

Este archivo NO se compila en el kernel: es una herramienta de desarrollo.
"""

import os
import sys

# --- parametros de rasterizacion ------------------------------------------
GLYPH_W = 8
GLYPH_H = 16
FIRST = 32
LAST = 126
COUNT = LAST - FIRST + 1

RASTER_SIZE = 13       # tamano en puntos de DejaVu Sans Mono
RASTER_BASELINE = 13   # fila de la linea base dentro de la celda 8x16
RASTER_THRESHOLD = 96  # umbral de binarizacion (0..255)

# Fuentes candidatas (se usa la primera que exista y rasterice bien).
FONT_CANDIDATES = [
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/local/share/fonts/DejaVuSansMono.ttf",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "graphics", "font_data.c")

# Tabla de respaldo: 95 glifos * 16 bytes en hexadecimal.
# Se rellena a partir de la salida de --dump-hex.  Permite generar la fuente
# en un entorno sin Pillow y sin fuentes, de forma 100% reproducible.
FALLBACK_HEX = """
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 18 18 18 18 18 18 00 18 18 00 00 00
00 00 00 00 2C 2C 2C 2C 00 00 00 00 00 00 00 00
00 00 00 12 16 14 7F 24 2C FE 68 48 48 00 00 00
00 00 00 00 08 3C 6E 68 38 1E 0A 4E 3C 08 08 00
00 00 00 00 70 90 90 76 18 6E 0B 0B 0E 00 00 00
00 00 00 00 3C 60 20 30 5B CB C6 66 3B 00 00 00
00 00 00 00 18 18 18 18 00 00 00 00 00 00 00 00
00 00 0C 08 18 10 10 10 10 10 10 18 08 0C 00 00
00 00 30 10 18 18 08 08 08 08 18 18 10 30 00 00
00 00 00 00 10 56 3C 3C 56 10 00 00 00 00 00 00
00 00 00 00 00 18 18 18 FE 18 18 18 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 18 18 10 10 00
00 00 00 00 00 00 00 00 00 3C 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 18 18 00 00 00
00 00 00 00 06 04 0C 08 18 10 10 30 20 60 40 00
00 00 00 00 3C 66 66 46 5A 46 66 66 3C 00 00 00
00 00 00 00 78 08 08 08 08 08 08 08 3E 00 00 00
00 00 00 00 3C 46 06 06 0C 18 30 60 7E 00 00 00
00 00 00 00 3C 44 06 04 3C 06 06 46 3C 00 00 00
00 00 00 00 0C 1C 14 24 64 44 7E 04 04 00 00 00
00 00 00 00 7C 60 60 7C 04 06 06 44 7C 00 00 00
00 00 00 00 3C 60 40 7C 66 42 42 66 3C 00 00 00
00 00 00 00 7E 06 04 0C 08 18 18 10 30 00 00 00
00 00 00 00 3C 66 46 66 3C 66 42 66 3C 00 00 00
00 00 00 00 3C 66 46 46 66 3E 06 44 38 00 00 00
00 00 00 00 00 00 18 18 00 00 00 18 18 00 00 00
00 00 00 00 00 00 18 18 00 00 00 18 18 10 10 00
00 00 00 00 00 00 02 1C 70 70 1C 02 00 00 00 00
00 00 00 00 00 00 00 FE 00 00 FE 00 00 00 00 00
00 00 00 00 00 00 C0 78 0E 0E 78 C0 00 00 00 00
00 00 00 00 3C 66 06 0C 18 10 00 18 18 00 00 00
00 00 00 00 3C 62 42 DF 93 93 93 DF 40 60 1E 00
00 00 00 00 18 18 3C 2C 24 66 7E 42 C3 00 00 00
00 00 00 00 7C 46 46 46 7C 46 42 46 7C 00 00 00
00 00 00 00 1C 22 60 40 40 40 60 22 1C 00 00 00
00 00 00 00 78 4C 46 46 42 46 46 4C 78 00 00 00
00 00 00 00 7E 60 60 60 7E 60 60 60 7E 00 00 00
00 00 00 00 7E 60 60 60 7E 60 60 60 60 00 00 00
00 00 00 00 3C 62 40 40 4E 42 42 66 3E 00 00 00
00 00 00 00 42 42 42 42 7E 42 42 42 42 00 00 00
00 00 00 00 7E 18 18 18 18 18 18 18 7E 00 00 00
00 00 00 00 3C 04 04 04 04 04 04 4C 78 00 00 00
00 00 00 00 42 44 48 70 78 48 4C 46 43 00 00 00
00 00 00 00 60 60 60 60 60 60 60 60 7E 00 00 00
00 00 00 00 E6 E6 E6 FA DA DA C2 C2 C2 00 00 00
00 00 00 00 62 62 72 52 5A 4A 4E 46 46 00 00 00
00 00 00 00 3C 66 46 42 42 42 46 66 3C 00 00 00
00 00 00 00 7C 66 62 62 66 7C 60 60 60 00 00 00
00 00 00 00 3C 66 46 42 42 42 46 66 3C 0C 04 00
00 00 00 00 7C 46 46 46 7C 4C 46 42 43 00 00 00
00 00 00 00 3C 64 40 60 3C 06 02 46 3C 00 00 00
00 00 00 00 FF 18 18 18 18 18 18 18 18 00 00 00
00 00 00 00 46 46 46 46 46 46 46 66 3C 00 00 00
00 00 00 00 C2 42 66 66 24 2C 3C 18 18 00 00 00
00 00 00 00 83 C3 C3 DA 5A 7A 6E 66 66 00 00 00
00 00 00 00 42 66 3C 18 18 3C 24 66 C3 00 00 00
00 00 00 00 C2 66 24 3C 18 18 18 18 18 00 00 00
00 00 00 00 7E 06 04 0C 18 10 30 60 7F 00 00 00
00 00 1C 10 10 10 10 10 10 10 10 10 10 1C 00 00
00 00 00 00 40 60 20 30 10 10 18 08 0C 04 06 00
00 00 38 08 08 08 08 08 08 08 08 08 08 38 00 00
00 00 00 00 18 3C 64 42 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 FF
00 00 00 30 10 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 3C 46 06 3E 46 46 7E 00 00 00
00 00 60 60 60 60 7C 66 62 62 62 66 7C 00 00 00
00 00 00 00 00 00 1C 22 60 60 60 22 1C 00 00 00
00 00 06 06 06 06 3E 66 46 46 46 66 3E 00 00 00
00 00 00 00 00 00 3C 66 42 7E 40 62 3C 00 00 00
00 00 0E 18 10 10 7E 10 10 10 10 10 10 00 00 00
00 00 00 00 00 00 3E 66 46 46 46 66 3E 06 04 38
00 00 60 60 60 60 7C 66 66 66 66 66 66 00 00 00
00 00 18 00 00 00 78 18 18 18 18 18 7E 00 00 00
00 00 08 00 00 00 38 08 08 08 08 08 08 08 18 70
00 00 60 60 60 60 66 6C 78 78 6C 66 62 00 00 00
00 00 70 10 10 10 10 10 10 10 10 18 0E 00 00 00
00 00 00 00 00 00 7E 5A 5A 5A 5A 5A 5A 00 00 00
00 00 00 00 00 00 7C 66 66 66 66 66 66 00 00 00
00 00 00 00 00 00 3C 66 46 42 46 66 3C 00 00 00
00 00 00 00 00 00 7C 66 62 62 62 66 7C 60 60 60
00 00 00 00 00 00 3E 66 46 46 46 66 3E 06 06 06
00 00 00 00 00 00 3E 30 30 30 30 30 30 00 00 00
00 00 00 00 00 00 3C 64 60 3C 06 46 3C 00 00 00
00 00 00 00 10 10 7E 10 10 10 10 10 1E 00 00 00
00 00 00 00 00 00 66 66 66 66 66 66 3E 00 00 00
00 00 00 00 00 00 42 46 64 24 3C 38 18 00 00 00
00 00 00 00 00 00 83 C3 DA 5A 7E 6E 64 00 00 00
00 00 00 00 00 00 66 24 18 18 3C 24 46 00 00 00
00 00 00 00 00 00 42 66 64 24 3C 18 18 18 10 70
00 00 00 00 00 00 7E 04 0C 18 30 20 7E 00 00 00
00 00 0E 18 18 18 18 70 10 18 18 18 18 0E 00 00
00 00 18 18 18 18 18 18 18 18 18 18 18 18 18 00
00 00 70 10 18 18 18 0E 18 18 18 18 10 70 00 00
00 00 00 00 00 00 00 00 72 0E 00 00 00 00 00 00
"""


# --------------------------------------------------------------------------
# Rasterizacion con Pillow
# --------------------------------------------------------------------------
def rasterize_with_pillow():
    """Devuelve [(nombre, [[16 bytes] x 95])] o None si no es posible."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    for path in FONT_CANDIDATES:
        if not os.path.isfile(path):
            continue
        try:
            font = ImageFont.truetype(path, RASTER_SIZE)
        except Exception:
            continue

        glyphs = []
        ok = True
        for code in range(FIRST, LAST + 1):
            ch = chr(code)
            # Se rasteriza cada glifo aislado en su celda: asi la posicion
            # subpixel del avance fraccional de la TTF no desplaza el dibujo.
            img = Image.new("L", (GLYPH_W, GLYPH_H), 0)
            draw = ImageDraw.Draw(img)
            draw.text((0, RASTER_BASELINE), ch, fill=255, font=font, anchor="ls")
            rows = []
            ink = 0
            for y in range(GLYPH_H):
                bits = 0
                for x in range(GLYPH_W):
                    if img.getpixel((x, y)) >= RASTER_THRESHOLD:
                        bits |= 0x80 >> x
                        ink += 1
                rows.append(bits)
            if code != 32 and ink == 0:
                ok = False  # glifo vacio: rasterizacion inaceptable
                break
            glyphs.append(rows)
        if ok:
            return os.path.basename(path), glyphs
    return None


# --------------------------------------------------------------------------
# Tabla de respaldo incrustada
# --------------------------------------------------------------------------
def fallback_glyphs():
    """Interpreta FALLBACK_HEX y devuelve la lista de 95 glifos."""
    data = []
    for line in FALLBACK_HEX.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for tok in line.split():
            data.append(int(tok, 16))
    if len(data) != COUNT * GLYPH_H:
        raise SystemExit(
            "tabla de respaldo invalida: %d bytes (esperados %d)"
            % (len(data), COUNT * GLYPH_H)
        )
    glyphs = []
    for i in range(COUNT):
        glyphs.append(data[i * GLYPH_H:(i + 1) * GLYPH_H])
    return glyphs


# --------------------------------------------------------------------------
# Emision de C
# --------------------------------------------------------------------------
def glyph_label(code):
    if code == 32:
        return "espacio"
    return "'%s'" % chr(code).replace("\\", "\\\\").replace("'", "\\'")


def emit_c(glyphs, source_note, out_path):
    lines = []
    lines.append("/* graphics/font_data.c - fuente bitmap 8x16 propia de SereOS")
    lines.append(" *")
    lines.append(" * GENERADO por tools/gen_font.py: NO EDITAR A MANO.")
    lines.append(" * ASCII imprimible 32..126, %d glifos de %dx%d." %
                 (COUNT, GLYPH_W, GLYPH_H))
    lines.append(" * Cada glifo son 16 filas; el bit 7 (0x80) de cada fila es el")
    lines.append(" * pixel mas a la izquierda y el bit 0 el mas a la derecha.")
    lines.append(" *")
    lines.append(" * Origen: %s" % source_note)
    lines.append(" *")
    lines.append(" * Aviso de licencia de los datos de la fuente (Bitstream Vera):")
    lines.append(" *")
    for ln in BITSTREAM_NOTICE:
        lines.append(" * " + ln if ln else " *")
    lines.append(" */")
    lines.append("")
    lines.append('#include "font.h"')
    lines.append("")
    lines.append("const uint8_t font8x16[FONT_COUNT][FONT_GLYPH_H] = {")
    for i, rows in enumerate(glyphs):
        code = FIRST + i
        body = ", ".join("0x%02X" % b for b in rows)
        lines.append("    /* 0x%02X %s */ { %s }," % (code, glyph_label(code), body))
    lines.append("};")
    lines.append("")

    text = "\n".join(lines)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, out_path)
    return text


# Aviso minimo exigido por la licencia Bitstream Vera / DejaVu.
BITSTREAM_NOTICE = [
    "Fonts are (c) Bitstream. DejaVu changes are in public domain.",
    "",
    "Bitstream Vera Fonts Copyright",
    "Copyright (c) 2003 by Bitstream, Inc. All Rights Reserved.",
    "Bitstream Vera is a trademark of Bitstream, Inc.",
    "",
    "Permission is hereby granted, free of charge, to any person obtaining",
    "a copy of the fonts accompanying this license (\"Fonts\") and associated",
    "documentation files (the \"Font Software\"), to reproduce and distribute",
    "the Font Software, including without limitation the rights to use,",
    "copy, merge, publish, distribute, and/or sell copies of the Font",
    "Software, and to permit persons to whom the Font Software is furnished",
    "to do so, subject to the following conditions:",
    "",
    "The above copyright and trademark notices and this permission notice",
    "shall be included in all copies of one or more of the Font Software",
    "typefaces.",
    "",
    "The Font Software may be modified, altered, or added to, and in",
    "particular the designs of glyphs or characters in the Fonts may be",
    "modified and additional glyphs or characters may be added to the",
    "Fonts, only if the fonts are renamed to names not containing either",
    "the words \"Bitstream\" or the word \"Vera\".",
    "",
    "The Font Software may be sold as part of a larger software package but",
    "no copy of one or more of the Font Software typefaces may be sold by",
    "itself.",
    "",
    "THE FONT SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND,",
    "EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF",
    "MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT",
    "OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL",
    "BITSTREAM OR THE GNOME FOUNDATION BE LIABLE FOR ANY CLAIM, DAMAGES OR",
    "OTHER LIABILITY, INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL,",
    "OR CONSEQUENTIAL DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR",
    "OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE FONT",
    "SOFTWARE OR FROM OTHER DEALINGS IN THE FONT SOFTWARE.",
    "",
    "Except as contained in this notice, the names of Gnome, the Gnome",
    "Foundation, and Bitstream Inc., shall not be used in advertising or",
    "otherwise to promote the sale, use or other dealings in this Font",
    "Software without prior written authorization from the Gnome Foundation",
    "or Bitstream Inc., respectively. For further information, contact:",
    "fonts at gnome dot org.",
    "",
    "Nota: el glifo se ha reducido a una matriz de 8x16 pixeles (mapa de",
    "bits) para el motor grafico de SereOS. La fuente original NO se",
    "redistribuye, solo estos datos derivados dentro de este kernel.",
]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv):
    args = argv[1:]
    out_path = DEFAULT_OUT
    force_fallback = False
    dump_only = False

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--out":
            i += 1
            if i >= len(args):
                raise SystemExit("--out necesita una ruta")
            out_path = args[i]
        elif a == "--force-fallback":
            force_fallback = True
        elif a == "--dump-hex":
            dump_only = True
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            raise SystemExit("opcion desconocida: %s" % a)
        i += 1

    glyphs = None
    source_note = None

    if not force_fallback:
        got = rasterize_with_pillow()
        if got is not None:
            source_note, glyphs = got
            source_note = ("DejaVu Sans Mono %d px rasterizada con Pillow "
                           "(%s), umbral %d." %
                           (RASTER_SIZE, source_note, RASTER_THRESHOLD))
            print("fuente: %s" % source_note)
        else:
            print("Pillow o DejaVu no disponibles: uso la tabla incrustada")

    if glyphs is None:
        glyphs = fallback_glyphs()
        source_note = ("DejaVu Sans Mono %d px rasterizada con Pillow en la "
                       "maquina de desarrollo; tabla de respaldo incrustada en "
                       "tools/gen_font.py (sin dependencia de PIL)." % RASTER_SIZE)
        print("fuente: tabla de respaldo incrustada (determinista)")

    if dump_only:
        for i in range(COUNT):
            body = " ".join("%02X" % b for b in glyphs[i])
            print("%-4s %s # 0x%02X %s" % (i, body, FIRST + i, glyph_label(FIRST + i)))
        return 0

    emit_c(glyphs, source_note, out_path)
    print("escrito %s (%d glifos, %d bytes de datos)" %
          (out_path, COUNT, COUNT * GLYPH_H))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
