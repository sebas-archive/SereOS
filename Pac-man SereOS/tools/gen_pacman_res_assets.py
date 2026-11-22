#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/gen_pacman_res_assets.py - assets definitivos de PAC-MAN SereOS (Res).

FASE 2 (task-36): convierte los recursos de `/home/t1an/Descargas/Res` en
datos C compilados, con licencia de uso privado/academico y sin modificar los
originales.

Genera (reproducible y determinista):
  assets/sprites_res.c/.h   5 frutas Res + fantasmas Res recoloreados + ojos
                            16x16 RGB565 con transparencia 0xF81F
  assets/font_arcade.c/.h   atlas alpha 8bpp de Press Start K (8x16, Latin-1)
  assets/sfx_res.c/.h       11 WAV -> PCM u8 mono 11025, loops/sirenas/chunks
  assets/res_original/      20 originales (19 usados + key.png de procedencia), sin modificar, + LICENSE_RES.md
  assets/LICENSE_RES.md     procedencia, hashes y aviso de no redistribucion
  assets/fonts/LICENSE_ARCADE.md  atribucion codeman38 + aviso user-supplied
  /tmp/res_gen/**           previews PNG/WAV, waveforms y metricas

Uso:
    python3 tools/gen_pacman_res_assets.py [--res DIR] [--out DIR]

Entrada por defecto: /home/t1an/Descargas/Res
Salida por defecto: la raiz de `Pac-man SereOS/` (donde vive este script).

No se integra en core/render/platform: solo entrega datos y headers.
"""

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import sys
import wave

try:
    from PIL import Image, ImageDraw
    import numpy as np
except ImportError:
    sys.stderr.write("ERROR: se necesita Pillow + NumPy (Python bundled).\n")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RES = "/home/t1an/Descargas/Res"
DEFAULT_OUT = ROOT
PREVIEW_DIR = "/tmp/res_gen"

SPRITE_SIZE = 16
SPRITE_PIXELS = SPRITE_SIZE * SPRITE_SIZE
TRANSPARENT = 0xF81F
OUTLINE_RGB = (24, 34, 54)      # #182236, identidad actual de SereOS
ALPHA_THRESHOLD = 128

GHOST_COLORS = [
    ("BLINKY", (255, 0, 0)),        # Paku-Paku: vbRed
    ("PINKY", (255, 184, 255)),     # Paku-Paku: RGB(255,184,255)
    ("INKY", (0, 255, 255)),        # Paku-Paku: vbCyan
    ("CLYDE", (255, 184, 81)),      # Paku-Paku: RGB(255,184,81)
]
GHOST_FRIGHT_TINT = (0, 0, 255)
GHOST_FLASH_TINT = (255, 255, 255)

FRUITS = [
    ("cherry.png", "CEREZA"),
    ("strawberry.png", "FRESA"),
    ("peach.png", "NARANJA"),
    ("apple.png", "MANZANA"),
    ("grapes.png", "UVAS"),
]

EYE_DIRS = [("RIGHT", (1, 0)), ("LEFT", (-1, 0)),
            ("UP", (0, -1)), ("DOWN", (0, 1))]

FONT_SIZE_PX = 8             # píxeles del glifo Press Start K dentro de la celda
FONT_W = 8
FONT_H = 16
FONT_BASELINE = 8            # linea base dentro de la celda 8x16
FONT_FIRST = 32
FONT_LAST = 255
FONT_COUNT = FONT_LAST - FONT_FIRST + 1
FONT_REQUIRED = "ñÑáéíóúüÁÉÍÓÚÜ¿¡"

AUDIO_RATE = 11025
SB16_MAX_BLOCK = 32768
SIREN_VARIANTS_PCT = [0, 10, 20, 30]
# Flag por defecto de `pacasset_sfx_res_loop[]` para clips cuyo loop se pide
# explicitamente por API (pac_audio_loop) y no al reproducirse como one-shot.
LOOP_FLAG_OVERRIDE = {"GHOST_RESPAWN": 0}

# Recursos usados (los NO usados no se copian ni convierten; ver auditoria).
PNG_USED = [f for f, _ in FRUITS] + ["ghost1.png", "ghost2.png"]
# Procedencia de la llave decorativa del indicador NIVEL: se copia tal cual
# (el sprite de la llave es procedural, este PNG no se convierte).
PNG_PROVENANCE = ["key.png"]
WAV_USED = [
    "game start.wav", "waka1.wav", "waka2.wav", "eat ghost.wav",
    "eat fruit.wav", "extra life.wav", "ghost respawn.wav",
    "hunted siren.wav", "hunter siren.wav", "pacman death.wav",
    "intermission.wav",
]
TTF_USED = "prstartk.ttf"

# Hashes MD5 verificados en la auditoria (task-34).
EXPECTED_MD5 = {
    "cherry.png": "5e618304f090913d6065ef1509f41235",
    "strawberry.png": "fe5c52249b327b58d0f0d09e45322ddb",
    "peach.png": "9234915891b6cc3439f88864ebbcf685",
    "apple.png": "cf56cd2b32d26f4c15dc508e5153521f",
    "grapes.png": "ddfadec1107f87d89d9fea074f27016d",
    "ghost1.png": "521be1b68ff40fc6efaca2ee6a078016",
    "ghost2.png": "4ec74e51c6f8923fd84929e0d946c51b",
    "key.png": "8a426c989a35a3a436837c4d0fd64177",
    "prstartk.ttf": "4e9a195e88e19adc94992d05f63db8ac",
    "game start.wav": "07914ee70de9f5f1166ed3e9b35fc9db",
    "waka1.wav": "9e3c8eb9b4d7af04971b12c9af3e5bb4",
    "waka2.wav": "0452cd64893e3fbd3503190e9ff318c7",
    "eat ghost.wav": "61d4ded9e6249e64b735982f6ced3ec5",
    "eat fruit.wav": "514eeeeb192e8ca45ca92aa308f61f63",
    "extra life.wav": "27991f5575aec8695f0f9a68925b9df8",
    "ghost respawn.wav": "43fae1a4447f5026f8f23a9d9dd02b95",
    "hunted siren.wav": "8d5759b619045b5f6879ec83175d67a9",
    "hunter siren.wav": "d35ceeea5823f2ea9c1a3d2107826b92",
    "pacman death.wav": "b5cacf9a37e6a4fd396f6fd914168780",
    "intermission.wav": "566c0f2299b8a7ebef6372010fa6866e",
}

EXCLUDED_FILES = [
    ("retroghost1.png", "No usado por Paku-Paku; candidato a skin Retro futuro."),
    ("retroghost2.png", "No usado por Paku-Paku; candidato a skin Retro futuro."),
    ("Clydeeghost.png", "No usado; arte grande para menu (no se integra en v1)."),
    ("dead.png", "No usado; rafaga final de muerte (no es la secuencia arcade)."),
    ("atari full.ttf", "Sin licencia clara, marca Atari, sin Latin-1; excluido."),
]


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------
def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rgb565(rgb):
    return ((rgb[0] >> 3) << 11) | ((rgb[1] >> 2) << 5) | (rgb[2] >> 3)


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def emit_u16_array(decl, values, per_line=16):
    out = ["const uint16_t %s = {" % decl]
    for i in range(0, len(values), per_line):
        out.append("\t" + ", ".join("0x%04X" % v for v in values[i:i + per_line]) + ",")
    out.append("};")
    return "\n".join(out)


def emit_u8_array(decl, values, per_line=20):
    out = ["const uint8_t %s = {" % decl]
    for i in range(0, len(values), per_line):
        out.append("\t" + ", ".join("0x%02X" % v for v in values[i:i + per_line]) + ",")
    out.append("};")
    return "\n".join(out)


def _emit_tree(decl, tree, fmt, per_line):
    lines = ["const %s %s = {" % ("uint16_t" if fmt == "0x%04X" else "uint8_t", decl)]
    def walk(node, indent):
        pre = "\t" * indent
        if node and isinstance(node[0], (list, tuple)):
            for item in node:
                lines.append(pre + "{")
                walk(item, indent + 1)
                lines.append(pre + "},")
        else:
            for i in range(0, len(node), per_line):
                lines.append(pre + ", ".join(fmt % v for v in node[i:i + per_line]) + ",")
    walk(tree, 1)
    lines.append("};")
    return "\n".join(lines)


def emit_u16_tree(decl, tree):
    return _emit_tree(decl, tree, "0x%04X", 16)


def emit_u8_tree(decl, tree):
    return _emit_tree(decl, tree, "0x%02X", 8)


def chunk_tree(flat, chunk_len):
    return [flat[i:i + chunk_len] for i in range(0, len(flat), chunk_len)]


# ---------------------------------------------------------------------------
# copia de originales + licencias
# ---------------------------------------------------------------------------
def copy_originals(res_dir, out_dir):
    dest = os.path.join(out_dir, "assets", "res_original")
    os.makedirs(dest, exist_ok=True)
    used = PNG_USED + PNG_PROVENANCE + WAV_USED + [TTF_USED]
    for name in used:
        src = os.path.join(res_dir, name)
        if not os.path.isfile(src):
            raise SystemExit("ERROR: falta el recurso %s" % src)
        got = md5_of(src)
        if got != EXPECTED_MD5[name]:
            raise SystemExit("ERROR: %s no coincide con el hash auditado "
                             "(esperado %s, real %s)"
                             % (name, EXPECTED_MD5[name], got))
        dst = os.path.join(dest, name)
        if os.path.isfile(dst):
            if md5_of(dst) != got:
                raise SystemExit("ERROR: %s en res_original/ difiere del original; "
                                 "no se sobrescribe" % dst)
        else:
            shutil.copyfile(src, dst)
    return used, dest


def license_res_md(res_dir, used, dest):
    lines = []
    lines.append("# Licencia y procedencia de los recursos originales de PAC-MAN SereOS")
    lines.append("")
    lines.append("**Entrega privada/académica.** Los recursos de `assets/res_original/`")
    lines.append("fueron suministrados por el usuario del proyecto desde")
    lines.append("`/home/t1an/Descargas/Res` y se copian **sin modificaciones** solo")
    lines.append("para trazabilidad. **No se autoriza su redistribución pública** (ni")
    lines.append("los originales ni los datos derivados de `assets/*.c` que los")
    lines.append("contienen) sin permiso de sus autores.")
    lines.append("")
    lines.append("Los PNG y WAV tienen origen arcade/terceros (personajes, frutas y")
    lines.append("sonidos reconocibles de Pac-Man, marca de Namco); no se reclama")
    lines.append("autoría. `prstartk.ttf` es *Press Start K* (© 2001-2002 codeman38),")
    lines.append("sin licencia declarada en el archivo: uso user-supplied/privado con")
    lines.append("atribución. Ver también `assets/fonts/LICENSE_ARCADE.md`.")
    lines.append("")
    lines.append("## Originales usados (%d archivos, copiados sin modificar)"
                 % len(used))
    lines.append("")
    lines.append("| Archivo | MD5 | Formato | Uso |")
    lines.append("|---|---|---|---|")
    for name in used:
        path = os.path.join(res_dir, name)
        fmt = ("PNG" if name.endswith(".png") else
               "WAV" if name.endswith(".wav") else "TTF")
        if fmt == "PNG":
            im = Image.open(path)
            desc = "%dx%d %s" % (im.size[0], im.size[1], im.mode)
            if name in PNG_PROVENANCE:
                use = "llave decorativa: procedencia (sprite procedural)"
            else:
                use = "fruta Res" if name != "ghost1.png" and name != "ghost2.png" else "cuerpo fantasma Res"
        elif fmt == "WAV":
            with wave.open(path, "rb") as w:
                desc = "%dch %db %dHz" % (w.getnchannels(), w.getsampwidth() * 8,
                                          w.getframerate())
            use = ("sfx Res (nivel completado)" if name == "intermission.wav"
                   else "sfx Res")
        else:
            desc = "Press Start K"
            use = "atlas de fuente arcade"
        lines.append("| `%s` | `%s` | %s | %s |" % (name, md5_of(path), desc, use))
    lines.append("")
    lines.append("## Recursos excluidos (documentados, NO copiados)")
    lines.append("")
    for name, why in EXCLUDED_FILES:
        lines.append("- `%s`: %s" % (name, why))
    lines.append("")
    lines.append("## Conversión")
    lines.append("")
    lines.append("- PNG -> `assets/sprites_res.c` (RGB565 16x16, clave `0xF81F`).")
    lines.append("- WAV -> `assets/sfx_res.c` (PCM u8 mono 11025 Hz, normalizado).")
    lines.append("- TTF -> `assets/font_arcade.c` (cobertura alfa 8bpp 8x16).")
    lines.append("- Regenerar: `python3 tools/gen_pacman_res_assets.py`.")
    lines.append("")
    return "\n".join(lines)


def license_arcade_md(res_dir, out_dir):
    font_md5 = md5_of(os.path.join(res_dir, TTF_USED))
    lines = [
        "# Licencia de la fuente arcade (Press Start K)",
        "",
        "El atlas `assets/font_arcade.c` se rasteriza a partir de:",
        "",
        "- **Press Start K** — © 2001-2002 **codeman38** (Cody Boisclair),",
        "  versión 1.01, archivo `prstartk.ttf` (MD5 `%s`)." % font_md5,
        "- Distribución original de referencia: Zone38 / codeman38;",
        "  la familia posterior *Press Start 2P* es una obra distinta publicada",
        "  con SIL Open Font License 1.1 en Google Fonts.",
        "",
        "## Aviso de licencia",
        "",
        "`prstartk.ttf` **no incluye un campo de licencia en sus metadatos**.",
        "Se usa aquí como recurso suministrado por el usuario para una",
        "**entrega privada/académica**, con atribución al autor. No se afirma",
        "ninguna licencia permisiva y **no se autoriza la redistribución pública**",
        "del TTF ni de este atlas sin permiso del autor.",
        "",
        "Si el proyecto se publica, sustituir este atlas por **Press Start 2P**",
        "(SIL OFL 1.1, Google Fonts) o por la tipografía Inter ya incluida.",
        "",
        "El texto completo de la OFL de Press Start 2P está en su distribución;",
        "este atlas no lo incorpora porque el archivo usado es Press Start K.",
        "",
        "Regenerar: `python3 tools/gen_pacman_res_assets.py`.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# sprites
# ---------------------------------------------------------------------------
def resize_rgba(im, size):
    """Resize premultiplicado para no oscurecer los bordes al reducir.
    size puede ser int (cuadrado) o (ancho, alto)."""
    if isinstance(size, int):
        size = (size, size)
    arr = np.asarray(im.convert("RGBA"), dtype=np.float64)
    a = arr[..., 3:4] / 255.0
    prem = np.concatenate([arr[..., :3] * a, arr[..., 3:4]], axis=-1)
    pm = Image.fromarray(np.clip(np.round(prem), 0, 255).astype(np.uint8), "RGBA")
    pm = pm.resize(size, Image.LANCZOS)
    out = np.asarray(pm, dtype=np.float64)
    alpha = out[..., 3:4]
    rgb = np.where(alpha > 0.0, out[..., :3] * 255.0 / np.maximum(alpha, 1e-6), 0.0)
    out[..., :3] = np.clip(np.round(rgb), 0, 255)
    out[..., 3] = alpha[..., 0]
    return Image.fromarray(np.clip(np.round(out), 0, 255).astype(np.uint8), "RGBA")


def fit_center(im, box, canvas=SPRITE_SIZE):
    """Escala RGBA para caber en box x box y la centra en el lienzo."""
    im = im.convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    scale = min(box / float(w), box / float(h))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    im = resize_rgba(im, (nw, nh))
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    out.alpha_composite(im, ((canvas - nw) // 2, (canvas - nh) // 2))
    return out


def compose_sprite_generic(rgba, size, outline=True):
    """RGBA size x size -> lista row-major RGB565 con 0xF81F + contorno."""
    px = rgba.load()
    n = size
    rows = [TRANSPARENT] * (n * n)
    opaque = [False] * (n * n)
    for y in range(n):
        for x in range(n):
            r, g, b, a = px[x, y]
            if a >= ALPHA_THRESHOLD:
                rows[y * n + x] = rgb565((r, g, b))
                opaque[y * n + x] = True
    if not outline:
        return rows
    dark = rgb565(OUTLINE_RGB)
    for y in range(n):
        for x in range(n):
            i = y * n + x
            if opaque[i]:
                continue
            adj = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < n and 0 <= ny < n and opaque[ny * n + nx]:
                        adj = True
            if adj:
                rows[i] = dark
    return rows


def compose_sprite(rgba):
    """RGBA 16x16 -> row-major RGB565 con 0xF81F y contorno oscuro."""
    return compose_sprite_generic(rgba, SPRITE_SIZE, outline=True)


def draw_face(canvas, look=(0, 0), mode="normal"):
    """Dibuja la cara del fantasma (escalable) con supersampling 4x.

    mode:
      "normal" -> ojos blancos + pupilas azules (mirada `look`)
      "fright" -> ojos blancos sin pupila + boca en zigzag blanca
      "flash"  -> ojos/boca azul oscuro sobre cuerpo blanco
      "eyes"   -> solo ojos normales (fantasma comido volviendo a casa)
    """
    ss = 4
    scale = canvas / 16.0
    big = Image.new("RGBA", (canvas * ss, canvas * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)

    def ell(cx, cy, rx, ry, fill):
        d.ellipse([(cx - rx) * ss, (cy - ry) * ss,
                   (cx + rx) * ss, (cy + ry) * ss], fill=fill)

    if mode in ("normal", "eyes"):
        for cx in (5.3, 10.7):
            ell(cx * scale, 6.6 * scale, 1.9 * scale, 2.5 * scale,
                (255, 255, 255, 255))
        ox = look[0] * 1.2 * scale
        oy = look[1] * 1.2 * scale
        for cx in (5.3, 10.7):
            ell(cx * scale + ox, 6.6 * scale + oy, 1.15 * scale,
                1.25 * scale, (0, 0, 255, 255))
    else:
        eye = (255, 255, 255, 255) if mode == "fright" else (26, 30, 120, 255)
        for cx in (5.3, 10.7):
            ell(cx * scale, 6.4 * scale, 1.7 * scale, 2.2 * scale, eye)
        # boca en zigzag clasica
        width = max(1, int(round(1.1 * ss)))
        pts = [(4.2, 10.4), (5.8, 11.4), (7.4, 10.4), (9.0, 11.4),
               (10.6, 10.4), (12.2, 11.4)]
        pts = [(x * scale * ss, y * scale * ss) for x, y in pts]
        d.line(pts, fill=eye, width=width)
    return big.resize((canvas, canvas), Image.LANCZOS)


def recolor_ghost(im, tint):
    arr = np.asarray(im.convert("RGBA"), dtype=np.float64)
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    shade = np.clip(lum / 157.0, 0.15, 1.55)
    out = np.empty_like(arr)
    for i, t in enumerate(tint):
        out[..., i] = np.clip(t * shade, 0, 255)
    out[..., 3] = a
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def load_ghost(res_dir, name):
    return Image.open(os.path.join(res_dir, name)).convert("RGBA")


def ghost_rgba(res_dir, name, tint, face_mode="normal"):
    body = recolor_ghost(load_ghost(res_dir, name), tint)
    small = fit_center(body, 14, SPRITE_SIZE)
    if face_mode:
        face = draw_face(SPRITE_SIZE, (0, 0), mode=face_mode)
        small = small.copy()
        small.alpha_composite(face)
    return small


def make_sprites(res_dir):
    """Devuelve dict de arrays y metadata de sprite."""
    data = {}
    # frutas
    fruits = []
    for fname, _label in FRUITS:
        im = Image.open(os.path.join(res_dir, fname)).convert("RGBA")
        rgba = fit_center(im, 14, SPRITE_SIZE)
        rows = compose_sprite(rgba)
        if sum(1 for v in rows if v != TRANSPARENT) < 20:
            raise SystemExit("ERROR: fruta %s casi vacia" % fname)
        fruits.append(rows)
    data["fruit"] = fruits

    # fantasmas: 4 colores x 2 frames, ojos neutros compuestos
    ghost_frames = []
    for _name, tint in GHOST_COLORS:
        per_color = []
        for fname in ("ghost1.png", "ghost2.png"):
            rgba = ghost_rgba(res_dir, fname, tint, face_mode="normal")
            per_color.append(compose_sprite(rgba))
        ghost_frames.append(per_color)
    data["ghost"] = ghost_frames

    # asustado / parpadeo: 2 frames (cuerpo azul/blanco, ojos cazados)
    fright = []
    flash = []
    for fname in ("ghost1.png", "ghost2.png"):
        fright.append(compose_sprite(
            ghost_rgba(res_dir, fname, GHOST_FRIGHT_TINT, face_mode="fright")))
        flash.append(compose_sprite(
            ghost_rgba(res_dir, fname, GHOST_FLASH_TINT, face_mode="flash")))
    data["fright"] = fright
    data["flash"] = flash

    # ojos solos por direccion
    eyes = []
    for _dname, look in EYE_DIRS:
        e = draw_face(SPRITE_SIZE, look, mode="eyes")
        eyes.append(compose_sprite_generic(e, SPRITE_SIZE, outline=False))
    data["eyes"] = eyes

    # previews (16 y 32 opcional en /tmp, 32 NO entregado)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    make_sprite_sheet(data, res_dir)
    make_sprite64_sheet(res_dir)
    return data


def sprite_png(rows, scale=8, size=SPRITE_SIZE):
    n = size
    im = Image.new("RGB", (n, n), (0, 0, 0))
    px = im.load()
    for y in range(n):
        for x in range(n):
            v = rows[y * n + x]
            if v == TRANSPARENT:
                px[x, y] = (56, 60, 70) if ((x // 2 + y // 2) % 2 == 0) else (42, 46, 56)
            else:
                r = (v >> 11) & 0x1F
                g = (v >> 5) & 0x3F
                b = v & 0x1F
                px[x, y] = ((r << 3) | (r >> 2), (g << 2) | (g >> 4),
                            (b << 3) | (b >> 2))
    return im.resize((n * scale, n * scale), Image.NEAREST)


def make_sprite_sheet(data, res_dir):
    scale = 5
    cell = SPRITE_SIZE * scale
    rows = [("FRUTAS", data["fruit"]),
            ("FANTASMAS", [g[0] for g in data["ghost"]]),
            ("FANTASMAS f2", [g[1] for g in data["ghost"]]),
            ("ASUSTADO", data["fright"]),
            ("FLASH", data["flash"]),
            ("OJOS", data["eyes"])]
    width = max(len(r[1]) for r in rows) * (cell + 8) + 130
    height = len(rows) * (cell + 14) + 30
    sheet = Image.new("RGB", (width, height), (16, 18, 24))
    d = ImageDraw.Draw(sheet)
    try:
        from PIL import ImageFont
        f = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 12)
    except Exception:
        f = None
    for r, (label, sprites) in enumerate(rows):
        y = 24 + r * (cell + 14)
        d.text((6, y), label, fill=(200, 215, 235), font=f)
        for c, spr in enumerate(sprites):
            x = 130 + c * (cell + 8)
            sheet.paste(sprite_png(spr, scale), (x, y))
        if r == 0:
            for c, (fname, _) in enumerate(FRUITS):
                d.text((130 + c * (cell + 8) + 2, 4 + 0),
                       fname.replace(".png", ""), fill=(130, 190, 240), font=f)
    sheet.save(os.path.join(PREVIEW_DIR, "sprites_res_sheet.png"))
    print("preview sprites ->", os.path.join(PREVIEW_DIR, "sprites_res_sheet.png"))


def make_sprite64_sheet(res_dir):
    """32x32 opcional SOLO preview en /tmp (no se entrega como principal)."""
    cell = 32
    sheet = Image.new("RGB", (4 * (cell + 8) + 12, 2 * (cell + 8) + 30),
                      (16, 18, 24))
    d = ImageDraw.Draw(sheet)
    try:
        from PIL import ImageFont
        f = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 11)
    except Exception:
        f = None
    for i, (name, tint) in enumerate(GHOST_COLORS):
        body = recolor_ghost(load_ghost(res_dir, "ghost1.png"), tint)
        body = resize_rgba(body, 32)
        body.alpha_composite(draw_face(32, (0, 0), mode="normal"))
        rows = compose_sprite_generic(body, 32, outline=True)
        sheet.paste(sprite_png(rows, 1, 32), (8 + i * (cell + 8), 20))
        d.text((8 + i * (cell + 8), 4), name, fill=(210, 220, 240), font=f)
    sheet.save(os.path.join(PREVIEW_DIR, "sprites_res_32_preview.png"))
    print("preview 32 (opcional, no entregado) ->",
          os.path.join(PREVIEW_DIR, "sprites_res_32_preview.png"))


def emit_sprites(out_dir, data):
    lines = []
    lines.append("/* assets/sprites_res.c - sprites derivados de Res (PAC-MAN SereOS)")
    lines.append(" *")
    lines.append(" * GENERADO por tools/gen_pacman_res_assets.py: NO EDITAR A MANO.")
    lines.append(" * 16x16 uint16_t RGB565, transparencia 0xF81F, contorno oscuro.")
    lines.append(" * Arte de origen: recursos de /home/t1an/Descargas/Res suministrados")
    lines.append(" * por el usuario (uso privado/academico; ver assets/LICENSE_RES.md).")
    lines.append(" * Frutas y cuerpos de fantasma provienen de Res; ojos procedurales.")
    lines.append(" */")
    lines.append('#include "sprites_res.h"')
    lines.append("")

    names = ["%s" % label for _f, label in FRUITS]
    lines.append(emit_u16_tree(
        "pacasset_fruit_sprite_res[5][PAC_RES_SPRITE_PIXELS]",
        data["fruit"]))
    lines.append("")
    lines.append(emit_u16_tree(
        "pacasset_ghost_frame_res[PAC_RES_GHOST_COLORS][PAC_RES_GHOST_FRAMES]"
        "[PAC_RES_SPRITE_PIXELS]", data["ghost"]))
    lines.append("")
    lines.append(emit_u16_tree(
        "pacasset_ghost_fright_frame_res[PAC_RES_GHOST_FRAMES][PAC_RES_SPRITE_PIXELS]",
        data["fright"]))
    lines.append("")
    lines.append(emit_u16_tree(
        "pacasset_ghost_flash_frame_res[PAC_RES_GHOST_FRAMES][PAC_RES_SPRITE_PIXELS]",
        data["flash"]))
    lines.append("")
    lines.append(emit_u16_tree(
        "pacasset_ghost_eyes_frame_res[PAC_RES_GHOST_EYE_DIRS][PAC_RES_SPRITE_PIXELS]",
        data["eyes"]))
    lines.append("")
    lines.append("const char *const pacasset_fruit_name_res[5] = {")
    lines.append("\t" + ", ".join('"%s"' % n for n in names) + ",")
    lines.append("};")
    lines.append("")
    lines.append("const uint8_t pacasset_res_sprite_size = %d;" % SPRITE_SIZE)
    lines.append("const uint16_t pacasset_res_sprite_pixels = %d;" % SPRITE_PIXELS)
    lines.append("")
    write_text(os.path.join(out_dir, "assets", "sprites_res.c"), "\n".join(lines))
    header = """/* assets/sprites_res.h - sprites definitivos derivados de Res
 *
 * 16x16 uint16_t RGB565, transparente = 0xF81F.
 * Contrato para game-dev (integra con PACMAN_USE_RES_ASSETS):
 *   - pacasset_fruit_sprite_res[5][256]        frutas CEREZA..UVAS (indices 0..4)
 *   - pacasset_ghost_frame_res[4][2][256]      colores 0 rojo/1 rosa/2 cian/3 naranja,
 *                                              frames 0/1 de falda, ojos neutros ya compuestos
 *   - pacasset_ghost_fright_frame_res[2][256]  asustado (cuerpo azul, ojos cazados)
 *   - pacasset_ghost_flash_frame_res[2][256]   parpadeo final (cuerpo blanco)
 *   - pacasset_ghost_eyes_frame_res[4][256]    solo ojos, mirando derecha/izquierda/arriba/abajo
 *   - pacasset_fruit_name_res[5]               CEREZA..UVAS (ASCII, sin acentos)
 * Pac-Man y vida: se mantienen los actuales (Res no aporta PNG).
 * Uso privado/academico; ver assets/LICENSE_RES.md.
 */
#ifndef PACMAN_SPRITES_RES_H
#define PACMAN_SPRITES_RES_H
#include <stdint.h>

#define PAC_RES_SPRITE_SIZE   16
#define PAC_RES_SPRITE_PIXELS (PAC_RES_SPRITE_SIZE * PAC_RES_SPRITE_SIZE)
#define PAC_RES_TRANSPARENT   0xF81Fu

#define PAC_RES_GHOST_COLORS  4
#define PAC_RES_GHOST_FRAMES  2
#define PAC_RES_GHOST_EYE_DIRS 4

#define PAC_RES_GHOST_BLINKY  0
#define PAC_RES_GHOST_PINKY   1
#define PAC_RES_GHOST_INKY    2
#define PAC_RES_GHOST_CLYDE   3

#define PAC_RES_EYE_RIGHT     0
#define PAC_RES_EYE_LEFT      1
#define PAC_RES_EYE_UP        2
#define PAC_RES_EYE_DOWN      3

extern const uint16_t pacasset_fruit_sprite_res[5][PAC_RES_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_frame_res[PAC_RES_GHOST_COLORS]
                                             [PAC_RES_GHOST_FRAMES]
                                             [PAC_RES_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_fright_frame_res[PAC_RES_GHOST_FRAMES]
                                                     [PAC_RES_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_flash_frame_res[PAC_RES_GHOST_FRAMES]
                                                    [PAC_RES_SPRITE_PIXELS];
extern const uint16_t pacasset_ghost_eyes_frame_res[PAC_RES_GHOST_EYE_DIRS]
                                                   [PAC_RES_SPRITE_PIXELS];
extern const char *const pacasset_fruit_name_res[5];

extern const uint8_t pacasset_res_sprite_size;
extern const uint16_t pacasset_res_sprite_pixels;

#endif /* PACMAN_SPRITES_RES_H */
"""
    write_text(os.path.join(out_dir, "assets", "sprites_res.h"), header)
    print("sprites -> assets/sprites_res.c/h")


# ---------------------------------------------------------------------------
# fuente arcade
# ---------------------------------------------------------------------------
def make_font(res_dir):
    from PIL import Image, ImageDraw, ImageFont
    path = os.path.join(res_dir, TTF_USED)
    font = ImageFont.truetype(path, FONT_SIZE_PX)
    glyphs = {}
    present = []
    missing = []
    for cp in range(FONT_FIRST, FONT_LAST + 1):
        # controles C1: sin glifo; runtime usa fallback
        if 127 <= cp <= 159:
            present.append(0)
            missing.append(cp)
            glyphs[cp] = None
            continue
        if cp == 160:  # NBSP -> celda vacia
            present.append(1)
            glyphs[cp] = bytes(FONT_H * FONT_W)
            continue
        img = Image.new("L", (FONT_W, FONT_H), 0)
        d = ImageDraw.Draw(img)
        d.text((0, FONT_BASELINE), chr(cp), font=font, fill=255, anchor="ls")
        cov = img.tobytes()
        if any(b > 0 for b in cov) or cp == 32:
            present.append(1)
            glyphs[cp] = cov
        else:
            present.append(0)
            missing.append(cp)
            glyphs[cp] = None
    # glifo fallback '?' y glifo de caja
    fallback = glyphs[ord("?")]
    if fallback is None:
        raise SystemExit("ERROR: '?' sin tinta en prstartk")
    for cp in range(FONT_FIRST, FONT_LAST + 1):
        if glyphs[cp] is None:
            glyphs[cp] = fallback
    # validar codepoints obligatorios
    for ch in FONT_REQUIRED:
        cp = ord(ch)
        if cp < FONT_FIRST or cp > FONT_LAST or not present[cp - FONT_FIRST]:
            raise SystemExit("ERROR: prstartk no cubre '%s' (U+%04X)" % (ch, cp))
    # preview
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    preview = render_font_preview(glyphs)
    preview.save(os.path.join(PREVIEW_DIR, "font_arcade_preview.png"))
    print("preview fuente ->", os.path.join(PREVIEW_DIR,
                                           "font_arcade_preview.png"))
    print("glifos ausentes (fallback '?'):", ", ".join("U+%04X" % c
          for c in missing))
    return glyphs, present, missing


def render_font_preview(glyphs, scale=4):
    lines = [
        "SEREOS 1.0",
        "PUNTUACION 10000",
        "NIVEL 3  VIDAS 2",
        "ñÑ áéíóú üÁÉÍÓÚ¿¡",
        "PAC-MAN SEREOS 2026",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "abcdefghijklmnopqrstuvwxyz 0123456789",
    ]
    w = max(len(line) for line in lines) * FONT_W
    h = len(lines) * FONT_H
    canvas = Image.new("L", (w, h), 0)
    for row, line in enumerate(lines):
        for col, ch in enumerate(line):
            cp = ord(ch)
            cov = glyphs.get(cp)
            if cov is None:
                continue
            for y in range(FONT_H):
                for x in range(FONT_W):
                    v = cov[y * FONT_W + x]
                    if v:
                        canvas.putpixel((col * FONT_W + x, row * FONT_H + y), v)
    im = Image.new("RGB", canvas.size, (11, 13, 18))
    px = im.load()
    cpix = canvas.load()
    for y in range(canvas.size[1]):
        for x in range(canvas.size[0]):
            v = cpix[x, y]
            if v:
                px[x, y] = (v, v, v)
    return im.resize((w * scale, h * scale), Image.NEAREST)


def emit_font(out_dir, glyphs, present, missing):
    tree = []
    for cp in range(FONT_FIRST, FONT_LAST + 1):
        cov = glyphs[cp]
        tree.append([list(cov[y * FONT_W:(y + 1) * FONT_W])
                     for y in range(FONT_H)])
    body = emit_u8_tree(
        "pac_arcade_font_cov[PAC_ARCADEFONT_COUNT][PAC_ARCADEFONT_H]"
        "[PAC_ARCADEFONT_W]", tree)
    miss_lines = []
    miss_lines.append("/* codepoints sin glifo real en prstartk (se dibuja '?') */")
    miss_lines.append("const uint8_t pac_arcade_font_missing_count = %d;"
                      % len(missing))
    if missing:
        miss_lines.append("const uint16_t pac_arcade_font_missing_cps[] = {")
        for i in range(0, len(missing), 12):
            miss_lines.append("\t" + ", ".join("0x%04X" % c
                                               for c in missing[i:i + 12]) + ",")
        miss_lines.append("};")
    else:
        miss_lines.append("const uint16_t pac_arcade_font_missing_cps[1] = { 0 };")
    lines = []
    lines.append("/* assets/font_arcade.c - atlas alpha 8bpp de Press Start K")
    lines.append(" *")
    lines.append(" * GENERADO por tools/gen_pacman_res_assets.py: NO EDITAR A MANO.")
    lines.append(" * Fuente: prstartk.ttf (Press Start K, (c) 2001-2002 codeman38),")
    lines.append(" * recurso user-supplied para entrega privada/academica.")
    lines.append(" * Ver assets/fonts/LICENSE_ARCADE.md.")
    lines.append(" * Formato: 224 celdas de 8x16 pixeles, 1 byte de cobertura (0..255)")
    lines.append(" * por pixel; glifo de 8x8 pixeles alineado arriba (baseline en fila 8).")
    lines.append(" */")
    lines.append('#include "font_arcade.h"')
    lines.append("")
    lines.extend(body.splitlines())
    lines.append("")
    lines.extend(miss_lines)
    lines.append("")
    lines.append("const uint8_t pac_arcade_font_present[PAC_ARCADEFONT_COUNT] = {")
    for i in range(0, FONT_COUNT, 28):
        lines.append("\t" + ", ".join(str(v) for v in present[i:i + 28]) + ",")
    lines.append("};")
    lines.append("")
    lines.append("const uint8_t pac_arcade_font_advance = %d;" % FONT_W)
    lines.append("const uint8_t pac_arcade_font_ascent = %d;" % FONT_BASELINE)
    lines.append("const uint8_t pac_arcade_font_line_height = %d;" % FONT_H)
    lines.append("")
    write_text(os.path.join(out_dir, "assets", "font_arcade.c"),
               "\n".join(lines))
    header = """/* assets/font_arcade.h - tipografia arcade (Press Start K) de PAC-MAN SereOS
 *
 * Atlas de cobertura alfa 8bpp generado en tiempo de build desde
 * prstartk.ttf (Press Start K, (c) 2001-2002 codeman38; recurso
 * user-supplied, ver assets/fonts/LICENSE_ARCADE.md).
 *
 * Formato acordado con game-dev:
 *   - celda 8x16 ASCII+Latin-1 (codepoints 32..255, 224 celdas)
 *   - glifo de 8x8 pixeles alineado arriba; baseline en la fila 8
 *   - avance fijo 8 px, line_height 16 px
 *   - `pac_arcade_font_present[cp-32]` indica si el glifo es real o '?'
 *     (los ausentes se rellenan con '?'; lista en
 *      pac_arcade_font_missing_cps / _count)
 * Uso (compositing por glyph):
 *   const uint8_t *cov = pac_arcade_font_cov[cp - PAC_ARCADEFONT_FIRST];
 *   para (fila 0..15) para (col 0..7): alfa = cov[fila*8+col];
 *   dibujar pixel (x+col, y+fila) con color y alfa (alpha blending).
 * Fallback de texto acentuado no cubierto: tipografia Inter del escritorio.
 */
#ifndef PACMAN_FONT_ARCADE_H
#define PACMAN_FONT_ARCADE_H
#include <stdint.h>

#define PAC_ARCADEFONT_W 8
#define PAC_ARCADEFONT_H 16
#define PAC_ARCADEFONT_FIRST 32
#define PAC_ARCADEFONT_LAST  255
#define PAC_ARCADEFONT_COUNT (PAC_ARCADEFONT_LAST - PAC_ARCADEFONT_FIRST + 1)
#define PAC_ARCADEFONT_BYTES_PER_GLYPH (PAC_ARCADEFONT_W * PAC_ARCADEFONT_H)

extern const uint8_t pac_arcade_font_cov[PAC_ARCADEFONT_COUNT]
                                        [PAC_ARCADEFONT_H][PAC_ARCADEFONT_W];
extern const uint8_t pac_arcade_font_present[PAC_ARCADEFONT_COUNT];
extern const uint8_t pac_arcade_font_missing_count;
extern const uint16_t pac_arcade_font_missing_cps[];
extern const uint8_t pac_arcade_font_advance;      /* 8 */
extern const uint8_t pac_arcade_font_ascent;       /* 8 (baseline desde el top) */
extern const uint8_t pac_arcade_font_line_height;  /* 16 */

static inline const uint8_t *pac_arcade_font_glyph(uint32_t codepoint)
{
	int index;
	if (codepoint < (uint32_t)PAC_ARCADEFONT_FIRST ||
	    codepoint > (uint32_t)PAC_ARCADEFONT_LAST) {
		codepoint = (uint32_t)'?';
	}
	index = (int)(codepoint - (uint32_t)PAC_ARCADEFONT_FIRST);
	return &pac_arcade_font_cov[index][0][0];
}

static inline int pac_arcade_font_covers(uint32_t codepoint)
{
	if (codepoint < (uint32_t)PAC_ARCADEFONT_FIRST ||
	    codepoint > (uint32_t)PAC_ARCADEFONT_LAST) {
		return 0;
	}
	return (int)pac_arcade_font_present[codepoint - (uint32_t)PAC_ARCADEFONT_FIRST];
}

#endif /* PACMAN_FONT_ARCADE_H */
"""
    write_text(os.path.join(out_dir, "assets", "font_arcade.h"), header)
    print("fuente -> assets/font_arcade.c/h (atlas %d bytes)"
          % (FONT_COUNT * FONT_H * FONT_W))


# ---------------------------------------------------------------------------
# audio
# ---------------------------------------------------------------------------
def load_wav_mono(path):
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    else:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    if ch == 2:
        a = (a[0::2] + a[1::2]) * 0.5
    return a, sr, ch, sw


def resample_sinc(a, sr_in, sr_out, half=24):
    if sr_in == sr_out:
        return a.copy()
    n_out = int(round(len(a) * sr_out / float(sr_in)))
    fc = min(0.5 * sr_out / float(sr_in), 0.5) * 0.90
    taps = np.arange(-half, half + 1)
    win = 0.54 + 0.46 * np.cos(np.pi * taps / half)
    out = np.empty(n_out)
    for i in range(n_out):
        pos = i * sr_in / float(sr_out)
        b = int(math.floor(pos))
        idx = b + taps
        valid = (idx >= 0) & (idx < len(a))
        d = pos - idx[valid]
        out[i] = float(np.sum(a[idx[valid]] * np.sinc(fc * d * 2.0) * win[valid]))
    return out


def trim_silence(a, sr, thresh_db=-55.0):
    thr = 10.0 ** (thresh_db / 20.0)
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    s = max(0, int(idx[0]) - int(sr * 0.002))
    e = min(len(a), int(idx[-1]) + int(sr * 0.002) + 1)
    return a[s:e]


def normalize(a, peak=0.92):
    p = float(np.max(np.abs(a))) if len(a) else 0.0
    return a * (peak / p) if p > 0 else a


def to_u8(a):
    return np.clip(np.round(a * 127.0 + 128.0), 0, 255).astype(np.uint8)


def db(x):
    return float(20.0 * np.log10(max(abs(x), 1e-9)))


def find_loop(x, sr):
    """Periodo natural por autocorrelacion y mejor punto de inicio."""
    n = len(x)
    if n < sr // 4:
        return None
    xc = x - x.mean()
    off = int(n * 0.30)
    seg = xc[off:]
    nfft = 1 << int(math.ceil(math.log2(2 * len(seg))))
    F = np.fft.rfft(seg, nfft)
    ac = np.fft.irfft(F * np.conj(F), nfft)[:len(seg)]
    ac /= (ac[0] + 1e-12)
    lo = int(sr * 0.08)
    hi = min(int(sr * 0.6), len(seg) - 1)
    if hi <= lo:
        return None
    lag = lo + int(np.argmax(ac[lo:hi]))
    best = (1e9, 0)
    for st in range(off, n - lag - 1, max(1, sr // 200)):
        wl = min(int(sr * 0.02), n - st - lag)
        if wl < 100:
            continue
        err = float(np.mean(np.abs(xc[st:st + wl] - xc[st + lag:st + lag + wl])))
        if err < best[0]:
            best = (err, st)
    return lag, best[1], best[0]


def make_loop(a, sr, fade_ms=5.0):
    """Recorta a un periodo y aplica crossfade con la continuacion real."""
    info = find_loop(a, sr)
    if info is None:
        return None
    period, start, err = info
    if start + period >= len(a):
        start = max(0, len(a) - period - 1)
    loop = a[start:start + period].copy()
    xf = min(int(sr * fade_ms / 1000.0), period // 4)
    if xf > 1:
        cont = a[start + period:start + period + xf]
        if len(cont) == xf:
            fade = np.linspace(0.0, 1.0, xf)
            loop[:xf] = loop[:xf] * fade + cont * (1.0 - fade)
    seam = float(abs(loop[0] - loop[-1]))
    return loop, dict(period=period, start=start, match_err=err,
                      crossfade=xf, seam=seam,
                      seam_db=db(seam))


def trim_to_period(a, sr):
    info = find_loop(a, sr)
    if info is None:
        return a, None
    period, start, _err = info
    return a[start:start + period], period


CLIPS = [
    # (slot, archivo, nombre simbolo, loop, sirena_variantes)
    ("START", "game start.wav", "game_start", False, False),
    ("WAKA1", "waka1.wav", "waka1", False, False),
    ("WAKA2", "waka2.wav", "waka2", False, False),
    ("EAT_GHOST", "eat ghost.wav", "eat_ghost", False, False),
    ("EAT_FRUIT", "eat fruit.wav", "eat_fruit", False, False),
    ("EXTRA_LIFE", "extra life.wav", "extra_life", False, False),
    ("DEATH", "pacman death.wav", "pacman_death", False, False),
    ("LEVEL_CLEAR", "intermission.wav", "level_clear", False, False),
    ("GHOST_RESPAWN", "ghost respawn.wav", "ghost_respawn", True, False),
    ("SIREN_HUNT", "hunted siren.wav", "siren_hunt", True, True),
    ("SIREN_CHASE", "hunter siren.wav", "siren_chase", True, True),
]
SLOT_INDEX = {"MENU": 1, "START": 2, "WAKA1": 3, "WAKA2": 4, "POWER": 5,
              "EAT_GHOST": 6, "EAT_FRUIT": 7, "DEATH": 8, "EXTRA_LIFE": 9,
              "LEVEL_CLEAR": 10, "GAME_OVER": 11, "SIREN_CHASE": 12,
              "SIREN_HUNT": 13, "SIREN_FRIGHT": 14, "GHOST_RESPAWN": 15}
SLOT_COUNT = 16


def convert_base(a, sr):
    b = resample_sinc(a, sr, AUDIO_RATE) if sr != AUDIO_RATE else a.copy()
    b = trim_silence(b, AUDIO_RATE)
    return normalize(b)


def convert_clip(a, sr, loop, variant_pct=0):
    b = convert_base(a, sr)
    if variant_pct:
        b = resample_sinc(b, AUDIO_RATE,
                          AUDIO_RATE * 100.0 / (100.0 + variant_pct))
        b = normalize(trim_silence(b, AUDIO_RATE))
    loop_info = None
    if loop:
        made = make_loop(b, AUDIO_RATE)
        if made is None:
            raise SystemExit("ERROR: no se pudo calcular el loop")
        b, loop_info = made
    return to_u8(b), loop_info


def make_sfx(res_dir):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    sfx_dir = os.path.join(PREVIEW_DIR, "sfx")
    os.makedirs(sfx_dir, exist_ok=True)
    result = {"clips": {}, "siren_variants": {}, "stats": []}
    for slot, fname, sym, loop, siren in CLIPS:
        a, sr, ch, sw = load_wav_mono(os.path.join(res_dir, fname))
        pcm, info = convert_clip(a, sr, loop)
        result["clips"][slot] = {"sym": sym, "pcm": pcm, "loop": loop,
                                 "info": info}
        save_preview_wav(os.path.join(sfx_dir, sym + ".wav"), pcm)
        st = dict(slot=slot, file=fname, source_ch=ch, source_bits=sw * 8,
                  source_rate=sr, source_dur=round(len(a) / float(sr), 4),
                  frames=int(len(pcm)), dur=round(len(pcm) / float(AUDIO_RATE), 4),
                  peak_u8=int(np.max(np.abs(pcm.astype(np.int32) - 128))) * 2,
                  chunks=int(math.ceil(len(pcm) / float(SB16_MAX_BLOCK))),
                  loop=loop, loop_info=info)
        if siren:
            variants = []
            for pct in SIREN_VARIANTS_PCT:
                vpcm, vinfo = convert_clip(a, sr, True, pct)
                variants.append(dict(pct=pct, pcm=vpcm, info=vinfo))
                save_preview_wav(os.path.join(
                    sfx_dir, "%s_%d.pct.wav" % (sym, pct)), vpcm)
                st.setdefault("variants", []).append(
                    dict(pct=pct, frames=int(len(vpcm)), loop_info=vinfo))
            result["siren_variants"][slot] = variants
        result["stats"].append(st)
        print("sfx %-14s %6d fr %5.3fs %s%s" % (
            slot, len(pcm), len(pcm) / float(AUDIO_RATE),
            "loop" if loop else "one-shot",
            " (%d chunks)" % st["chunks"] if st["chunks"] > 1 else ""))
    make_waveforms(result, sfx_dir)
    json.dump(result["stats"], open(os.path.join(PREVIEW_DIR,
                                                 "sfx_stats.json"), "w"),
              indent=1)
    return result


def save_preview_wav(path, pcm):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(AUDIO_RATE)
        w.writeframes(pcm.tobytes())


def make_waveforms(result, sfx_dir):
    from PIL import ImageDraw
    rows = result["stats"]
    height = 70
    img = Image.new("RGB", (700, height * len(rows) + 10), (14, 16, 22))
    d = ImageDraw.Draw(img)
    try:
        from PIL import ImageFont
        f = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 10)
    except Exception:
        f = None
    for r, st in enumerate(rows):
        y0 = 6 + r * height
        d.rectangle([0, y0, 699, y0 + height - 6], fill=(20, 24, 32))
        pcm = result["clips"][st["slot"]]["pcm"].astype(np.float64) - 128.0
        n = len(pcm)
        if n > 0:
            for x in range(700):
                i0 = int(x * n / 700.0)
                i1 = max(i0 + 1, int((x + 1) * n / 700.0))
                v = np.max(np.abs(pcm[i0:i1])) if i1 > i0 else 0.0
                h = int(v / 128.0 * (height - 24) / 2)
                d.line([(x, y0 + height // 2 - 5 - h),
                        (x, y0 + height // 2 - 5 + h)], fill=(90, 200, 255))
        label = "%s %s %d fr%s" % (st["slot"], "LOOP" if st["loop"] else "one-shot",
                                   st["frames"],
                                   " x%d" % st["chunks"] if st["chunks"] > 1 else "")
        d.text((6, y0 + 2), label, fill=(220, 230, 245), font=f)
    img.save(os.path.join(PREVIEW_DIR, "sfx_waveforms.png"))
    print("preview waveforms ->", os.path.join(PREVIEW_DIR, "sfx_waveforms.png"))


def emit_sfx(out_dir, res):
    c = []
    c.append("/* assets/sfx_res.c - SFX PCM derivados de Res (PAC-MAN SereOS)")
    c.append(" *")
    c.append(" * GENERADO por tools/gen_pacman_res_assets.py: NO EDITAR A MANO.")
    c.append(" * PCM 8 bits SIN SIGNO, mono, 11025 Hz (SB16 de SereOS).")
    c.append(" * Recursos de origen suministrados por el usuario (entrega privada);")
    c.append(" * ver assets/LICENSE_RES.md. Incluye los 11 WAV de Res"
             " (intermission en LEVEL_CLEAR).")
    c.append(" */")
    c.append('#include "sfx_res.h"')
    c.append("")
    data_names = {}
    for slot, info in res["clips"].items():
        sym = info["sym"]
        pcm = info["pcm"]
        if len(pcm) <= SB16_MAX_BLOCK:
            name = "pacasset_pcm_" + sym
            c.append(emit_u8_array(name + "[]", pcm.tolist(), per_line=20))
            c.append("")
            data_names[slot] = [name]
        else:
            chunks = [pcm[i:i + SB16_MAX_BLOCK]
                      for i in range(0, len(pcm), SB16_MAX_BLOCK)]
            names = []
            for i, chunk in enumerate(chunks):
                name = "pacasset_pcm_%s_%d" % (sym, i)
                c.append(emit_u8_array(name + "[]", chunk.tolist(),
                                       per_line=20))
                c.append("")
                names.append(name)
            data_names[slot] = names
    # variantes de sirena
    for slot, variants in res["siren_variants"].items():
        sym = res["clips"][slot]["sym"]
        names = []
        for v in variants:
            pct = v["pct"]
            name = "pacasset_pcm_%s_p%d" % (sym, pct)
            c.append(emit_u8_array(name + "[]", v["pcm"].tolist(),
                                   per_line=20))
            c.append("")
            names.append(name)
        data_names[slot + "_VARIANTS"] = names
    # tablas
    c.append("const pac_res_sfx_t pacasset_sfx_res[PACASSET_RES_SFX_SLOTS] = {")
    for slot in range(SLOT_COUNT):
        clip_name = next((s for s in SLOT_INDEX if SLOT_INDEX[s] == slot), None)
        if clip_name is not None and clip_name in res["clips"]:
            info = res["clips"][clip_name]
            c.append("\t[%d] = { %s, %du },  /* %s */"
                     % (slot, data_names[clip_name][0], len(info["pcm"]), clip_name))
        else:
            c.append("\t[%d] = { 0, 0u },  /* sin WAV: fallback sintetizado */"
                     % slot)
    c.append("};")
    c.append("")
    c.append("const uint8_t pacasset_sfx_res_loop[PACASSET_RES_SFX_SLOTS] = {")
    loops = []
    for slot in range(SLOT_COUNT):
        clip_name = next((s for s in SLOT_INDEX if SLOT_INDEX[s] == slot), None)
        flag = (1 if clip_name is not None and clip_name in res["clips"]
                and res["clips"][clip_name]["loop"] else 0)
        if clip_name in LOOP_FLAG_OVERRIDE:
            flag = LOOP_FLAG_OVERRIDE[clip_name]
        loops.append(flag)
    c.append("\t" + ", ".join(str(v) for v in loops) + ",")
    c.append("};")
    c.append("")
    c.append("const uint8_t pacasset_sfx_res_chunk_count[PACASSET_RES_SFX_SLOTS] = {")
    counts = []
    for slot in range(SLOT_COUNT):
        clip_name = next((s for s in SLOT_INDEX if SLOT_INDEX[s] == slot), None)
        counts.append(len(data_names[clip_name]) if clip_name is not None and clip_name in
                      res["clips"] else 0)
    c.append("\t" + ", ".join(str(v) for v in counts) + ",")
    c.append("};")
    c.append("")
    c.append("const uint8_t *const pacasset_sfx_res_chunks"
             "[PACASSET_RES_SFX_SLOTS][PACASSET_RES_SFX_MAX_CHUNKS] = {")
    for slot in range(SLOT_COUNT):
        clip_name = next((s for s in SLOT_INDEX if SLOT_INDEX[s] == slot), None)
        if clip_name is not None and clip_name in res["clips"]:
            names = data_names[clip_name]
            row = ["\t{ " + ", ".join(names)]
            while len(names) < 2:
                names = names + ["0"]
            row = ["\t{ %s }," % ", ".join(names)]
            c.append(row[0])
        else:
            c.append("\t{ 0, 0 },")
    c.append("};")
    c.append("")
    c.append("const uint32_t pacasset_sfx_res_chunk_len"
             "[PACASSET_RES_SFX_SLOTS][PACASSET_RES_SFX_MAX_CHUNKS] = {")
    for slot in range(SLOT_COUNT):
        clip_name = next((s for s in SLOT_INDEX if SLOT_INDEX[s] == slot), None)
        if clip_name is not None and clip_name in res["clips"]:
            lens = [min(SB16_MAX_BLOCK, len(res["clips"][clip_name]["pcm"]) - i *
                        SB16_MAX_BLOCK) for i in range(counts[slot])]
            while len(lens) < 2:
                lens.append(0)
            c.append("\t{ %su, %su }," % (lens[0], lens[1]))
        else:
            c.append("\t{ 0u, 0u },")
    c.append("};")
    c.append("")
    # sirenas: variantes
    for slot, arr_name in (("SIREN_HUNT", "pacasset_siren_hunt_res"),
                           ("SIREN_CHASE", "pacasset_siren_chase_res")):
        variants = res["siren_variants"][slot]
        c.append("const pac_res_sfx_t %s[PACASSET_RES_SIREN_VARIANTS] = {"
                 % arr_name)
        for v in variants:
            name = "pacasset_pcm_%s_p%d" % (res["clips"][slot]["sym"], v["pct"])
            c.append("\t{ %s, %du },  /* +%d%% */"
                     % (name, len(v["pcm"]), v["pct"]))
        c.append("};")
        c.append("")
    c.append("const uint8_t pacasset_siren_variant_pct"
             "[PACASSET_RES_SIREN_VARIANTS] = { %s };"
             % ", ".join(str(p) for p in SIREN_VARIANTS_PCT))
    c.append("")
    c.append("const uint16_t pacasset_sfx_res_rate = %d;" % AUDIO_RATE)
    c.append("")
    total = sum(len(info["pcm"]) for info in res["clips"].values())
    total += sum(len(v["pcm"]) for variants in res["siren_variants"].values()
                 for v in variants)
    c.append("const uint32_t pacasset_sfx_res_total_bytes = %du;" % total)
    c.append("")
    write_text(os.path.join(out_dir, "assets", "sfx_res.c"), "\n".join(c))

    header = """/* assets/sfx_res.h - SFX PCM definitivos derivados de Res (PAC-MAN SereOS)
 *
 * PCM 8 bits SIN SIGNO, mono, 11025 Hz (compatible con el SB16 de SereOS
 * y con SDL Linux). Generado desde los 11 WAV de Res (incluye intermission).
 * Recurso de uso privado/academico; ver assets/LICENSE_RES.md.
 *
 * Slots: identicos a `pac_audio_sfx_t` (pac_platform.h) con la adicion de
 * PAC_SFX_GHOST_RESPAWN al final, es decir:
 *   0 NONE | 1 MENU | 2 START | 3 WAKA1 | 4 WAKA2 | 5 POWER |
 *   6 EAT_GHOST | 7 EAT_FRUIT | 8 DEATH | 9 EXTRA_LIFE | 10 LEVEL_CLEAR |
 *   11 GAME_OVER | 12 SIREN_CHASE | 13 SIREN_HUNT | 14 SIREN_FRIGHT |
 *   15 GHOST_RESPAWN
 * Slots con WAV: 2,3,4,6,7,8,9,10,12,13,15. Sin WAV (data=0): 1,5,11,14.
 *   START=game start, WAKA1/2=waka1/2, EAT_GHOST=eat ghost,
 *   EAT_FRUIT=eat fruit, EXTRA_LIFE=extra life, DEATH=pacman death,
 *   LEVEL_CLEAR=intermission (one-shot, 2 trozos),
 *   GHOST_RESPAWN=ghost respawn (periodo de bucle; flag loop=0 por defecto:
 *   el bucle se pide con pac_audio_loop),
 *   SIREN_HUNT=hunted siren (loop), SIREN_CHASE=hunter siren (loop).
 *
 * Clips largos (START y LEVEL_CLEAR) se entregan troceados en bloques <=32768
 * (limite SB16):
 *   pacasset_sfx_res_chunk_count[slot]     numero de trozos (1 o 2)
 *   pacasset_sfx_res_chunks[slot][i]       puntero al trozo i
 *   pacasset_sfx_res_chunk_len[slot][i]    muestras del trozo i
 * `pacasset_sfx_res[slot].data` apunta al primer trozo y `.len` es el total.
 * Para reproducir en SB16: enviar trozos de uno en uno respetando el limite
 * de bloque; en Linux se puede reproducir el total de una vez.
 *
 * Sirenas: `pacasset_siren_hunt_res[4]` / `pacasset_siren_chase_res[4]` con
 * pitch +0/+10/+20/+30% ya remuestreado (mismo rate 11025); el slot 13/12
 * del array principal apunta a la variante +0%.
 */
#ifndef PACMAN_SFX_RES_H
#define PACMAN_SFX_RES_H
#include <stdint.h>

#define PACASSET_RES_SFX_RATE          11025
#define PACASSET_RES_SFX_SLOTS         16
#define PACASSET_RES_SFX_MAX_CHUNKS    2
#define PACASSET_RES_SIREN_VARIANTS    4

#define PACASSET_RES_SFX_NONE          0
#define PACASSET_RES_SFX_MENU          1
#define PACASSET_RES_SFX_START         2
#define PACASSET_RES_SFX_WAKA1         3
#define PACASSET_RES_SFX_WAKA2         4
#define PACASSET_RES_SFX_POWER         5
#define PACASSET_RES_SFX_EAT_GHOST     6
#define PACASSET_RES_SFX_EAT_FRUIT     7
#define PACASSET_RES_SFX_DEATH         8
#define PACASSET_RES_SFX_EXTRA_LIFE    9
#define PACASSET_RES_SFX_LEVEL_CLEAR   10
#define PACASSET_RES_SFX_GAME_OVER     11
#define PACASSET_RES_SFX_SIREN_CHASE   12
#define PACASSET_RES_SFX_SIREN_HUNT    13
#define PACASSET_RES_SFX_SIREN_FRIGHT  14
#define PACASSET_RES_SFX_GHOST_RESPAWN 15

typedef struct {
	const uint8_t *data;   /* muestras PCM u8 (primer trozo si chunks>1) */
	uint32_t       len;    /* muestras totales (todos los trozos) */
} pac_res_sfx_t;

extern const pac_res_sfx_t pacasset_sfx_res[PACASSET_RES_SFX_SLOTS];
extern const uint8_t pacasset_sfx_res_loop[PACASSET_RES_SFX_SLOTS];
extern const uint8_t pacasset_sfx_res_chunk_count[PACASSET_RES_SFX_SLOTS];
extern const uint8_t *const pacasset_sfx_res_chunks
        [PACASSET_RES_SFX_SLOTS][PACASSET_RES_SFX_MAX_CHUNKS];
extern const uint32_t pacasset_sfx_res_chunk_len
        [PACASSET_RES_SFX_SLOTS][PACASSET_RES_SFX_MAX_CHUNKS];
extern const uint16_t pacasset_sfx_res_rate;
extern const uint32_t pacasset_sfx_res_total_bytes;

/* 4 variantes de frecuencia (pitch +0/10/20/30%) de cada sirena */
extern const pac_res_sfx_t pacasset_siren_hunt_res[PACASSET_RES_SIREN_VARIANTS];
extern const pac_res_sfx_t pacasset_siren_chase_res[PACASSET_RES_SIREN_VARIANTS];
extern const uint8_t pacasset_siren_variant_pct[PACASSET_RES_SIREN_VARIANTS];

static inline int pacasset_sfx_res_available(int slot)
{
	return (slot >= 0 && slot < PACASSET_RES_SFX_SLOTS &&
	        pacasset_sfx_res[slot].data != 0 && pacasset_sfx_res[slot].len != 0u);
}

#endif /* PACMAN_SFX_RES_H */
"""
    write_text(os.path.join(out_dir, "assets", "sfx_res.h"), header)
    print("audio -> assets/sfx_res.c/h (%d bytes PCM, %d slots)"
          % (total, SLOT_COUNT))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--res", default=DEFAULT_RES)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv[1:])

    res_dir = args.res
    out_dir = args.out
    if not os.path.isdir(res_dir):
        raise SystemExit("ERROR: no existe el directorio Res: %s" % res_dir)
    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "tools"), exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    print("== originales ==")
    used, dest = copy_originals(res_dir, out_dir)
    print("copiados/verificados %d originales en %s" % (len(used), dest))
    write_text(os.path.join(dest, "LICENSE_RES.md"),
               license_res_md(res_dir, used, dest))
    write_text(os.path.join(out_dir, "assets", "LICENSE_RES.md"),
               license_res_md(res_dir, used, dest))
    write_text(os.path.join(out_dir, "assets", "fonts", "LICENSE_ARCADE.md"),
               license_arcade_md(res_dir, out_dir))
    print("licencias -> assets/LICENSE_RES.md, assets/fonts/LICENSE_ARCADE.md")

    print("== sprites ==")
    sprites = make_sprites(res_dir)
    emit_sprites(out_dir, sprites)

    print("== fuente arcade ==")
    glyphs, present, missing = make_font(res_dir)
    emit_font(out_dir, glyphs, present, missing)

    print("== audio ==")
    sfx = make_sfx(res_dir)
    emit_sfx(out_dir, sfx)

    print("")
    print("OK. Assets generados en %s:" % out_dir)
    print("  assets/sprites_res.c/h")
    print("  assets/font_arcade.c/h")
    print("  assets/sfx_res.c/h")
    print("  assets/res_original/ (+ LICENSE_RES.md)")
    print("  assets/LICENSE_RES.md, assets/fonts/LICENSE_ARCADE.md")
    print("Previews/metricas en %s" % PREVIEW_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
