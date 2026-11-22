#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/gen_ui_fonts.py - genera los atlases tipograficos de SereOS.

Rasteriza, EN TIEMPO DE COMPILACION, las dos familias tipograficas del
sistema a cobertura alfa de 8 bits y emite graphics/text_data.c, que se
compila dentro del kernel.  En tiempo de ejecucion NO hay dependencias:
sin PIL, sin archivos de fuentes, sin malloc y sin FPU.

Familias y licencias
--------------------
- UI: Inter (variables estaticas del TTC) desde /usr/share/fonts/inter/Inter.ttc
  indices 0 = Inter Regular y 12 = Inter SemiBold.
  Copyright (c) 2016 The Inter Project Authors. SIL Open Font License 1.1.
  Texto de licencia: /usr/share/licenses/inter-font/LICENSE.txt
- Codigo: JetBrains Mono Regular desde
  /usr/share/fonts/TTF/JetBrainsMono-Regular.ttf
  Copyright 2020 The JetBrains Mono Project Authors. SIL Open Font License 1.1.
  Texto de licencia: /usr/share/licenses/ttf-jetbrains-mono/LICENSE

Ambas licencias OFL permiten incrustar los datos rasterizados en el kernel;
el aviso completo de licencia se incluye en la cabecera de text_data.c y en
las constantes INTER_LICENSE / JETBRAINS_LICENSE de este generador.

Estilos (deben coincidir con text_style_t de graphics/text.h)
--------------------------------------------------------------
TEXT_CAPTION     Inter Regular 10 px
TEXT_SMALL       Inter Regular 11 px
TEXT_BODY        Inter Regular 13 px
TEXT_LABEL       Inter SemiBold 12 px
TEXT_TITLE       Inter SemiBold 16 px
TEXT_HEADLINE    Inter SemiBold 20 px
TEXT_DISPLAY     Inter SemiBold 30 px
TEXT_MONO        JetBrains Mono Regular 13 px
TEXT_MONO_SMALL  JetBrains Mono Regular 11 px

Formato generado
----------------
graphics/text_data.c contiene, para cada estilo, un atlas `uint8_t[]` con la
cobertura de cada glifo empaquetada como width*height bytes y una tabla
`text_glyph_t[226]` con offset/width/height/bearing_x/bearing_y/advance.
El decodificado UTF-8 (ASCII + Latin-1, 1-2 bytes) ocurre en runtime en
graphics/text.c.  El generador valida que ningun glifo visible quede vacio y
que 'A', 'g', '0', 'N con tilde', 'n con tilde' y 'a con acento' tengan tinta.

Uso
---
    python3 tools/gen_ui_fonts.py             # escribe graphics/text_data.c
    python3 tools/gen_ui_fonts.py --out ruta  # salida alternativa

Es determinista: misma version de Pillow/FreeType y mismas fuentes producen
exactamente el mismo archivo.  No se compila en el kernel.
"""

import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
    from PIL import ImageFont as PILImageFont
except ImportError:
    sys.stderr.write("ERROR: este generador necesita Pillow (modulo PIL).\n")
    sys.exit(1)

# --------------------------------------------------------------------------
# rutas y constantes del formato
# --------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "graphics", "text_data.c")

INTER_TTC = "/usr/share/fonts/inter/Inter.ttc"
INTER_REGULAR_INDEX = 0
INTER_SEMIBOLD_INDEX = 12
JETBRAINS_TTF = "/usr/share/fonts/TTF/JetBrainsMono-Regular.ttf"

TEXT_FIRST = 32
TEXT_LAST = 255
GLYPH_COUNT = TEXT_LAST - TEXT_FIRST + 1          # 224
GLYPH_FALLBACK = GLYPH_COUNT                      # 224: '?'
GLYPH_REPLACEMENT = GLYPH_COUNT + 1               # 225: U+FFFD
GLYPH_EXTRA_FIRST = GLYPH_COUNT + 2               # 226: signos extendidos

# codepoints de control C1: no se rasterizan (runtime usa el fallback)
def is_c1(cp):
    return 127 <= cp <= 159

# glifos legitimamente sin tinta (espacios de ancho fijo)
BLANK_CODEPOINTS = {32, 160}
# guion suave: invisible sin motor de particion de palabras; avance 0
ZERO_WIDTH_CODEPOINTS = {173}

# glifos obligatorios para la validacion del generador
REQUIRED_INK = ["A", "g", "0", "\u00d1", "\u00f1", "\u00e1"]

# Signos tipograficos fuera de Latin-1 habituales en la interfaz.  Se indexan
# en text_extra_codepoints[] (orden estable que comparte graphics/text.c).
EXTRA_CODEPOINTS = [
    0x2013,  # guion medio
    0x2014,  # guion largo (em dash)
    0x2018, 0x2019,  # comillas simples
    0x201C, 0x201D,  # comillas dobles
    0x2022,  # vineta
    0x2026,  # puntos suspensivos
    0x20AC,  # euro
    0x2192,  # flecha derecha
    0x2190,  # flecha izquierda
    0x2122,  # marca registrada
]
EXTRA_COUNT = len(EXTRA_CODEPOINTS)
GLYPHS_TOTAL = GLYPH_COUNT + 2 + EXTRA_COUNT

# Metrica de interlineado: ascent+descent de la fuente + un respiro optico
# proporcional al tamano (minimo 2 px, para que las cajas no se toquen).
def line_gap_for(size):
    return max(2, int(round(size * 0.18)))


STYLES = [
    {"symbol": "text_font_caption", "name": "TEXT_CAPTION",
     "desc": "Inter Regular 10 px", "path": INTER_TTC,
     "index": INTER_REGULAR_INDEX, "size": 10},
    {"symbol": "text_font_small", "name": "TEXT_SMALL",
     "desc": "Inter Regular 11 px", "path": INTER_TTC,
     "index": INTER_REGULAR_INDEX, "size": 11},
    {"symbol": "text_font_body", "name": "TEXT_BODY",
     "desc": "Inter Regular 13 px", "path": INTER_TTC,
     "index": INTER_REGULAR_INDEX, "size": 13},
    {"symbol": "text_font_label", "name": "TEXT_LABEL",
     "desc": "Inter SemiBold 12 px", "path": INTER_TTC,
     "index": INTER_SEMIBOLD_INDEX, "size": 12},
    {"symbol": "text_font_title", "name": "TEXT_TITLE",
     "desc": "Inter SemiBold 16 px", "path": INTER_TTC,
     "index": INTER_SEMIBOLD_INDEX, "size": 16},
    {"symbol": "text_font_headline", "name": "TEXT_HEADLINE",
     "desc": "Inter SemiBold 20 px", "path": INTER_TTC,
     "index": INTER_SEMIBOLD_INDEX, "size": 20},
    {"symbol": "text_font_display", "name": "TEXT_DISPLAY",
     "desc": "Inter SemiBold 30 px", "path": INTER_TTC,
     "index": INTER_SEMIBOLD_INDEX, "size": 30},
    {"symbol": "text_font_mono", "name": "TEXT_MONO",
     "desc": "JetBrains Mono Regular 13 px", "path": JETBRAINS_TTF,
     "index": 0, "size": 13},
    {"symbol": "text_font_mono_small", "name": "TEXT_MONO_SMALL",
     "desc": "JetBrains Mono Regular 11 px", "path": JETBRAINS_TTF,
     "index": 0, "size": 11},
]

# --------------------------------------------------------------------------
# licencias completas (SIL Open Font License 1.1), incluidas en text_data.c
# --------------------------------------------------------------------------
INTER_LICENSE = """Copyright (c) 2016 The Inter Project Authors (https://github.com/rsms/inter)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL

-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded,
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION AND CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE."""

JETBRAINS_LICENSE = """Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://scripts.sil.org/OFL


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE."""


# --------------------------------------------------------------------------
# carga de fuentes
# --------------------------------------------------------------------------
def load_font(path, size, index):
    kwargs = {"index": index}
    try:
        # Layout basico: sin shaping ni kerning, avance por caracter, que es
        # justo lo que el motor de runtime sabe dibujar.
        kwargs["layout_engine"] = PILImageFont.Layout.BASIC
    except AttributeError:
        pass
    return ImageFont.truetype(path, size, **kwargs)


# --------------------------------------------------------------------------
# rasterizacion de un glifo
# --------------------------------------------------------------------------
def rasterize_glyph(font, ch, size):
    """Devuelve (w, h, bearing_x, bearing_y, advance, mask_bytes).

    Se dibuja con el ancla 'ls' (left, baseline) sobre un lienzo con margen
    suficiente y se recorta la caja real de tinta con Image.getbbox(); asi no
    dependemos de las metricas declaradas y no se pierde ningun borde
    antialiasado.
    """
    pad = size * 2
    side = size * 4
    canvas = Image.new("L", (side, side), 0)
    draw = ImageDraw.Draw(canvas)
    ax = size
    ay = pad
    draw.text((ax, ay), ch, font=font, fill=255, anchor="ls")

    advance = int(round(font.getlength(ch)))
    if advance < 0:
        advance = 0
    if advance > 255:
        raise ValueError("avance excesivo (%d) para %r a %d px"
                         % (advance, ch, size))

    ink = canvas.getbbox()
    if ink is None:
        return (0, 0, 0, 0, advance, b"")

    x0, y0, x1, y1 = ink
    w = x1 - x0
    h = y1 - y0
    # El glifo debe caber en la tabla de texto sin desbordar el lienzo.
    if x0 < 0 or y0 < 0 or w <= 0 or h <= 0 or w > 255 or h > 255:
        raise ValueError("glifo fuera de rango: %r cp=U+%04X bbox=%r"
                         % (ch, ord(ch), ink))
    mask = canvas.crop((x0, y0, x1, y1)).tobytes()
    bearing_x = x0 - ax
    bearing_y = ay - y0
    if bearing_x < -128 or bearing_x > 127 or bearing_y < -128 or bearing_y > 127:
        raise ValueError("bearing fuera de int8: %r" % (ch,))
    return (w, h, bearing_x, bearing_y, advance, mask)


def build_style(style):
    """Rasteriza los 226 glifos del estilo y devuelve la estructura Python."""
    if not os.path.isfile(style["path"]):
        raise SystemExit("ERROR: no existe la fuente %s (instale el paquete "
                         "de fuentes correspondiente)" % style["path"])
    font = load_font(style["path"], style["size"], style["index"])
    ascent, descent = font.getmetrics()
    line_height = ascent + descent
    line_gap = line_gap_for(style["size"])
    if ascent <= 0 or line_height <= ascent or line_height > 255:
        raise SystemExit("ERROR: metricas fuera de rango en %s: (%d,%d)"
                         % (style["name"], ascent, descent))

    glyphs = []
    for cp in range(TEXT_FIRST, TEXT_LAST + 1):
        if is_c1(cp):
            # Los controles C1 no se dibujan nunca (runtime usa fallback);
            # se dejan entradas vacias para mantener el indice cp-FIRST.
            glyphs.append((0, 0, 0, 0, 0, b""))
            continue
        if cp in ZERO_WIDTH_CODEPOINTS:
            # guion suave: invisible (no hay particion de palabras)
            glyphs.append((0, 0, 0, 0, 0, b""))
            continue
        glyphs.append(rasterize_glyph(font, chr(cp), style["size"]))

    # Glifo comodin '?' para codepoints fuera de Latin-1.
    fallback = rasterize_glyph(font, "?", style["size"])
    if fallback[0] == 0 and fallback[1] == 0:
        raise SystemExit("ERROR: '?' sin tinta en %s" % style["name"])
    glyphs.append(fallback)

    # Glifo de reemplazo U+FFFD para secuencias UTF-8 invalidas.
    replacement = rasterize_glyph(font, "\ufffd", style["size"])
    if replacement[0] == 0 and replacement[1] == 0:
        replacement = fallback  # fuente sin U+FFFD: se reutiliza '?'
    glyphs.append(replacement)

    # Signos tipograficos extendidos (fuera de Latin-1).
    for cp in EXTRA_CODEPOINTS:
        extra = rasterize_glyph(font, chr(cp), style["size"])
        if extra[0] == 0 or extra[1] == 0:
            raise SystemExit("ERROR: signo extendido U+%04X sin tinta en %s"
                             % (cp, style["name"]))
        glyphs.append(extra)

    assert len(glyphs) == GLYPHS_TOTAL

    # -------- validaciones de calidad --------
    for i, (w, h, _bx, _by, _adv, _mask) in enumerate(glyphs[:GLYPH_COUNT]):
        cp = TEXT_FIRST + i
        if is_c1(cp):
            continue
        if cp in BLANK_CODEPOINTS or cp in ZERO_WIDTH_CODEPOINTS:
            if w != 0 or h != 0:
                raise SystemExit("ERROR: %s U+%04X deberia estar vacio"
                                 % (style["name"], cp))
            continue
        if w == 0 or h == 0:
            raise SystemExit("ERROR: glifo visible vacio en %s: U+%04X %r"
                             % (style["name"], cp, chr(cp)))

    glyphs_by_char = {}
    for ch in REQUIRED_INK:
        w, h = rasterize_glyph(font, ch, style["size"])[:2]
        glyphs_by_char[ch] = w * h
        if w == 0 or h == 0:
            raise SystemExit("ERROR: %s no tiene tinta en %s"
                             % (ch, style["name"]))

    # anchos proporcionales (UI) y monoespaciados (mono)
    width_iiii = sum(glyphs[ord(c) - TEXT_FIRST][4] for c in "iiii")
    width_MMMM = sum(glyphs[ord(c) - TEXT_FIRST][4] for c in "MMMM")
    is_mono = "JetBrains" in style["desc"]
    if is_mono:
        if not (width_iiii == width_MMMM):
            raise SystemExit("ERROR: %s no es monoespaciada (iiii=%d MMMM=%d)"
                             % (style["name"], width_iiii, width_MMMM))
    else:
        if not (width_iiii < width_MMMM):
            raise SystemExit("ERROR: %s sin anchos proporcionales "
                             "(iiii=%d MMMM=%d)"
                             % (style["name"], width_iiii, width_MMMM))

    # empaquetado del atlas
    atlas = bytearray()
    offsets = []
    for (w, h, _bx, _by, _adv, mask) in glyphs:
        offsets.append(len(atlas))
        if w and h and len(mask) != w * h:
            raise SystemExit("ERROR: mascara inconsistente en %s"
                             % style["name"])
        atlas.extend(mask)
        if len(atlas) > 0xFFFFFFFF:
            raise SystemExit("ERROR: atlas demasiado grande en %s"
                             % style["name"])

    max_pixels = max((w * h for (w, h, *_rest) in glyphs), default=0)
    return {
        "style": style,
        "ascent": ascent,
        "descent": descent,
        "line_height": line_height,
        "line_gap": line_gap,
        "glyphs": glyphs,
        "offsets": offsets,
        "atlas": bytes(atlas),
        "max_pixels": max_pixels,
    }


# --------------------------------------------------------------------------
# emision de C
# --------------------------------------------------------------------------
def c_comment_lines(text, prefix):
    out = []
    for line in text.splitlines():
        out.append((prefix + " " + line).rstrip())
    return out


def glyph_label(cp):
    if 33 <= cp <= 126:
        ch = chr(cp)
        if ch in "\\'":
            ch = "\\" + ch
        return "0x%02X '%s'" % (cp, ch)
    return "0x%02X" % cp


def emit_c(built, out_path):
    lines = []
    lines.append("/* graphics/text_data.c - atlases tipograficos de SereOS")
    lines.append(" *")
    lines.append(" * GENERADO por tools/gen_ui_fonts.py: NO EDITAR A MANO.")
    lines.append(" *")
    lines.append(" * Dos familias rasterizadas durante la compilacion a cobertura")
    lines.append(" * alfa de 8 bits (sin dependencias en tiempo de ejecucion):")
    lines.append(" *   - Inter Regular / SemiBold  (interfaz de usuario)")
    lines.append(" *   - JetBrains Mono Regular    (codigo, terminal y datos)")
    lines.append(" *")
    lines.append(" * 9 estilos, ASCII + Latin-1 (32..255) mas '?' y U+FFFD.")
    lines.append(" * Cada glifo: width*height bytes de cobertura, offset en el atlas")
    lines.append(" * del estilo; el runtime dibuja un gfx_blit_alpha8() por glifo.")
    lines.append(" *")
    lines.append(" * ------------------------------------------------------------------")
    lines.append(" * LICENCIA - INTER (SIL Open Font License 1.1)")
    lines.append(" * ------------------------------------------------------------------")
    lines.extend(c_comment_lines(INTER_LICENSE, " *"))
    lines.append(" * ------------------------------------------------------------------")
    lines.append(" * LICENCIA - JETBRAINS MONO (SIL Open Font License 1.1)")
    lines.append(" * ------------------------------------------------------------------")
    lines.extend(c_comment_lines(JETBRAINS_LICENSE, " *"))
    lines.append(" */")
    lines.append("")
    lines.append('#include "text_internal.h"')
    lines.append("")
    lines.append("/* Codepoints de los glifos extendidos (orden estable, fuera de")
    lines.append(" * Latin-1); el indice del glifo es TEXT_GLYPH_EXTRA_FIRST + i. */")
    lines.append("const uint16_t text_extra_codepoints[TEXT_EXTRA_COUNT] = {")
    for i in range(0, EXTRA_COUNT, 8):
        chunk = EXTRA_CODEPOINTS[i:i + 8]
        lines.append("\t" + ", ".join("0x%04X" % cp for cp in chunk) + ",")
    lines.append("};")
    lines.append("")

    total_bytes = 0
    for item in built:
        style = item["style"]
        symbol = style["symbol"]
        tag = symbol[len("text_font_"):]
        atlas_name = "text_atlas_" + tag
        glyphs_name = "text_glyphs_" + tag
        atlas = item["atlas"]
        total_bytes += len(atlas)
        lines.append("/* ------------------------------------------------------------------")
        lines.append(" * %s - %s" % (style["name"], style["desc"]))
        lines.append(" * line_height=%d ascent=%d line_gap=%d glifos=%d atlas=%d B"
                     % (item["line_height"], item["ascent"], item["line_gap"],
                        GLYPHS_TOTAL, len(atlas)))
        lines.append(" * ------------------------------------------------------------------ */")
        lines.append("static const uint8_t %s[] = {" % atlas_name)
        for i in range(0, len(atlas), 16):
            chunk = atlas[i:i + 16]
            lines.append("\t" + ", ".join("0x%02X" % b for b in chunk) + ",")
        lines.append("};")
        lines.append("")
        lines.append("static const text_glyph_t %s[TEXT_GLYPHS_TOTAL] = {"
                     % glyphs_name)
        for i, (w, h, bx, by, adv, _mask) in enumerate(item["glyphs"]):
            if i < GLYPH_COUNT:
                cp = TEXT_FIRST + i
                label = glyph_label(cp)
            elif i == GLYPH_FALLBACK:
                label = "fallback '?'"
            elif i == GLYPH_REPLACEMENT:
                label = "replacement U+FFFD"
            else:
                label = "extra U+%04X" % EXTRA_CODEPOINTS[i - GLYPH_EXTRA_FIRST]
            lines.append("\t{ %7d, %3d, %2d, %3d, %3d, %3d },  /* %s */"
                         % (item["offsets"][i], w, h, bx, by, adv, label))
        lines.append("};")
        lines.append("")
        lines.append("const text_font_t %s = {" % symbol)
        lines.append("\t.line_height = %d," % item["line_height"])
        lines.append("\t.ascent = %d," % item["ascent"])
        lines.append("\t.line_gap = %d," % item["line_gap"])
        lines.append("\t.reserved = 0,")
        lines.append("\t.glyph_count = TEXT_GLYPHS_TOTAL,")
        lines.append("\t.atlas_size = sizeof(%s)," % atlas_name)
        lines.append("\t.glyphs = %s," % glyphs_name)
        lines.append("\t.atlas = %s" % atlas_name)
        lines.append("};")
        lines.append("")

    text = "\n".join(lines) + "\n"
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, out_path)
    return total_bytes


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv):
    out_path = DEFAULT_OUT
    args = argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--out":
            i += 1
            if i >= len(args):
                raise SystemExit("--out necesita una ruta")
            out_path = args[i]
        elif args[i] in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            raise SystemExit("opcion desconocida: %s" % args[i])
        i += 1

    built = []
    for style in STYLES:
        item = build_style(style)
        built.append(item)
        print("%-22s %-26s lh=%-2d asc=%-2d gap=%d glifos=%d atlas=%5d B "
              "maxGlyph=%d px"
              % (item["style"]["name"], item["style"]["desc"],
                 item["line_height"], item["ascent"], item["line_gap"],
                 GLYPHS_TOTAL, len(item["atlas"]), item["max_pixels"]))

    total = emit_c(built, out_path)
    lines = sum(1 for _ in open(out_path, "rb"))
    print("")
    print("escrito %s" % out_path)
    print("atlas total: %.1f KiB en %d estilos; fuente: %d lineas"
          % (total / 1024.0, len(built), lines))
    print("licencias: Inter y JetBrains Mono, SIL OFL 1.1 (incluidas en el "
          "archivo generado)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
