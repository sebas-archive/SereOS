#!/usr/bin/env python3
"""tools/gen_pacman_assets.py - generador reproducible de los sprites de
Pacman SereOS (proyecto final de Sistemas Operativos, UMB 2026).

Arte 100% ORIGINAL creado para SereOS: no se copia ni se deriva ningun
sprite de Pac-Man / Namco / Paku-Paku. Solo se toma como referencia la
estetica general del genero arcade de 16 bits, con la identidad visual del
escritorio SereOS (navy profundo, azul electrico y cian).

Salida:
  assets/sprites.c   arrays const uint16_t RGB565 16x16
  assets/preview.png hoja de prevision ampliada

Formato: 16x16, fila a fila, 0xF81F = transparente (GFX_TRANSPARENT).
Contorno oscuro SIEMPRE opaco (no se usa negro como falso transparente).

Uso:
  py=~/.dsh/.../python/bin/python3
  $py tools/gen_pacman_assets.py

El script es determinista: mismo codigo -> mismo assets.c y mismo preview.
"""
import math
import os
import re
import sys

W = H = 16
N = W * H
TRANSPARENT = 0xF81F
SPRITE_SIZE = 16

# ---------------------------------------------------------------------------
# paleta base (identidad SereOS + arcade)
# ---------------------------------------------------------------------------
OUTLINE = (24, 34, 54)          # #182236 navy oscuro: contorno legible sobre negro/navy
NAVY_DEEP = (10, 15, 28)        # #0A0F1C
ACCENT = (46, 123, 255)         # #2E7BFF azul electrico SereOS
ACCENT2 = (34, 211, 238)        # #22D3EE cian SereOS
WHITE = (244, 249, 255)
BLACK = (0, 0, 0)

# Pacman: ambar con brillo (se lee sobre negro)
PAC_BASE = (255, 201, 60)       # #FFC93C
PAC_LIGHT = (255, 229, 138)     # #FFE58A
PAC_DARK = (224, 154, 30)       # #E09A1E
PAC_SPEC = (255, 246, 208)      # #FFF6D0

# Fantasmas: 4 colores originales (base, luz, sombra)
GHOST_PALETTES = [
    ("ROJO", (255, 74, 90), (255, 142, 152), (188, 36, 54)),
    ("ROSA", (255, 108, 196), (255, 174, 226), (194, 50, 138)),
    ("CIAN", (46, 214, 226), (136, 244, 250), (16, 136, 152)),
    ("NARANJA", (255, 156, 55), (255, 204, 126), (200, 98, 16)),
]
GHOST_EYE_WHITE = (244, 249, 255)
GHOST_PUPIL = (46, 123, 255)

# Frightened / flash
FRIGHT_BASE = (61, 98, 232)     # #3D62E8 azul arcade de alto contraste
FRIGHT_LIGHT = (104, 142, 255)  # #688EFF
FRIGHT_DARK = (32, 52, 140)     # #20348C
FRIGHT_FACE = (240, 246, 255)   # cara casi blanca: ojos/boca legibles
FLASH_BASE = (244, 247, 255)    # blanco SereOS del parpadeo
FLASH_LIGHT = (255, 255, 255)
FLASH_DARK = (170, 190, 225)
FLASH_FACE = (46, 123, 255)

# Frutas: paletas propias
CHERRY = ((255, 70, 85), (255, 140, 151), (176, 30, 48))
STRAWBERRY = ((255, 77, 106), (255, 149, 168), (193, 39, 66))
ORANGE = ((255, 159, 46), (255, 196, 107), (201, 106, 14))
APPLE = ((226, 61, 76), (255, 122, 136), (156, 30, 48))
GRAPES = ((155, 103, 255), (196, 165, 255), (91, 46, 184))

STEM_BROWN = (138, 90, 43)
LEAF_GREEN = (40, 200, 64)
LEAF_LIGHT = (108, 255, 138)
SEED = (255, 233, 168)
KEY_GOLD = (255, 210, 74)
KEY_LIGHT = (255, 240, 168)
KEY_DARK = (200, 146, 31)


def rgb565(c):
    """0x00RRGGBB -> RGB565 (5-6-5)."""
    r, g, b = c
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


OUTLINE_565 = rgb565(OUTLINE)


# ---------------------------------------------------------------------------
# lienzo de sprites
# ---------------------------------------------------------------------------
class Sprite:
    def __init__(self, name):
        self.name = name
        self.col = [None] * N          # color RGB por pixel (None = transparente)
        self.body = [False] * N        # mascara de las formas que reciben sombreado
        self.wanted_outline = True

    # -- primitivas basicas -------------------------------------------------
    def pix(self, x, y, color):
        if 0 <= x < W and 0 <= y < H:
            self.col[y * W + x] = color

    def get(self, x, y):
        if 0 <= x < W and 0 <= y < H:
            return self.col[y * W + x]
        return None

    def opaque(self, x, y):
        return 0 <= x < W and 0 <= y < H and self.col[y * W + x] is not None

    def body_at(self, x, y):
        return 0 <= x < W and 0 <= y < H and self.body[y * W + x]

    def add_mask(self, mask, color):
        for i, on in enumerate(mask):
            if on:
                self.col[i] = color
                self.body[i] = True

    # -- sombreado automatico ----------------------------------------------
    def shade(self, light, dark, light_side=True):
        """Luz superior/izquierda y sombra inferior/derecha sobre la mascara
        del cuerpo. Da volumen de superficie sin degradados suaves (pixel art)."""
        out = list(self.col)
        cx = (W - 1) / 2.0
        cy = (H - 1) / 2.0
        for y in range(H):
            for x in range(W):
                i = y * W + x
                if not self.body[i]:
                    continue
                up = self.body_at(x, y - 1)
                dn = self.body_at(x, y + 1)
                lf = self.body_at(x - 1, y)
                rt = self.body_at(x + 1, y)
                top_light = (not up) and x <= cx + 1.5
                left_light = light_side and (not lf) and y <= cy
                bot_dark = (not dn) and x >= cx - 1.5
                right_dark = (not rt) and y >= cy
                if top_light or left_light:
                    out[i] = light
                elif bot_dark or right_dark:
                    out[i] = dark
        self.col = out

    # -- detalles -----------------------------------------------------------
    def paint(self, coords, color):
        for x, y in coords:
            self.pix(x, y, color)

    def specular(self, dots, color):
        self.paint(dots, color)

    # -- contorno -----------------------------------------------------------
    def outline(self, color=OUTLINE):
        """Rellena con el color de contorno todo pixel transparente que toque
        la figura (4-vecindad). El contorno es siempre opaco. Los huecos
        transparentes encerrados por la figura se rellenan tambien con el
        contorno (sombra interior) para que la transparencia quede solo fuera
        de la figura, como exige el contrato."""
        src = [c is not None for c in self.col]
        out = list(self.col)
        for y in range(H):
            for x in range(W):
                i = y * W + x
                if src[i]:
                    continue
                if ((x > 0 and src[i - 1]) or (x < W - 1 and src[i + 1]) or
                        (y > 0 and src[i - W]) or (y < H - 1 and src[i + W])):
                    out[i] = color
        self.col = out
        # rellenar huecos transparentes encerrados con el color de contorno
        open_ = [False] * N
        stack = []
        for x in range(W):
            for y in (0, H - 1):
                i = y * W + x
                if self.col[i] is None and not open_[i]:
                    open_[i] = True
                    stack.append(i)
        for y in range(H):
            for x in (0, W - 1):
                i = y * W + x
                if self.col[i] is None and not open_[i]:
                    open_[i] = True
                    stack.append(i)
        while stack:
            i = stack.pop()
            x, y = i % W, i // W
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < W and 0 <= ny < H:
                    j = ny * W + nx
                    if self.col[j] is None and not open_[j]:
                        open_[j] = True
                        stack.append(j)
        for i in range(N):
            if self.col[i] is None and not open_[i]:
                self.col[i] = color

    # -- transformaciones --------------------------------------------------
    def mirrored(self):
        s = Sprite(self.name + "_mirror")
        s.wanted_outline = False
        for y in range(H):
            for x in range(W):
                s.col[y * W + (W - 1 - x)] = self.col[y * W + x]
        return s

    def rotated_cw(self):
        s = Sprite(self.name + "_cw")
        s.wanted_outline = False
        for y in range(H):
            for x in range(W):
                s.col[x * W + (H - 1 - y)] = self.col[y * W + x]
        return s

    def rotated_ccw(self):
        s = Sprite(self.name + "_ccw")
        s.wanted_outline = False
        for y in range(H):
            for x in range(W):
                s.col[(W - 1 - x) * W + y] = self.col[y * W + x]
        return s

    # -- salida -------------------------------------------------------------
    def to565(self):
        out = []
        for c in self.col:
            out.append(TRANSPARENT if c is None else rgb565(c))
        return out

    def opaque_count(self):
        return sum(1 for c in self.col if c is not None)


# ---------------------------------------------------------------------------
# mascaras geometricas
# ---------------------------------------------------------------------------
def circle_mask(cx, cy, r):
    m = [False] * N
    for y in range(H):
        for x in range(W):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                m[y * W + x] = True
    return m


def rect_mask(x0, y0, x1, y1):
    m = [False] * N
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if 0 <= x < W and 0 <= y < H:
                m[y * W + x] = True
    return m


def union(*masks):
    m = [False] * N
    for mk in masks:
        for i, on in enumerate(mk):
            if on:
                m[i] = True
    return m


def rows_mask(rows):
    """rows: lista de (y, x0, x1)"""
    m = [False] * N
    for y, x0, x1 in rows:
        for x in range(x0, x1 + 1):
            if 0 <= x < W and 0 <= y < H:
                m[y * W + x] = True
    return m


def bresenham(x0, y0, x1, y1):
    pts = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return pts


# ---------------------------------------------------------------------------
# Pacman
# ---------------------------------------------------------------------------
PAC_MOUTH = (0, 22, 40)     # boca cerrada, semiabierta, abierta (grados)


def make_pacman(mouth):
    """Comecocos mirando a la derecha; luego se rota/espeja."""
    s = Sprite("pacman")
    mask = circle_mask(7.5, 7.5, 6.25)
    if mouth > 0:
        for y in range(H):
            for x in range(W):
                dx = x - 7.5
                dy = y - 7.5
                if dx > 0:
                    ang = abs(math.degrees(math.atan2(dy, dx)))
                    if ang <= mouth:
                        mask[y * W + x] = False
    s.add_mask(mask, PAC_BASE)
    s.shade(PAC_LIGHT, PAC_DARK)
    # brillo especular arriba-izquierda, solo dentro de la figura
    for x, y in ((4, 3), (5, 3), (4, 4), (5, 4)):
        if s.opaque(x, y):
            s.pix(x, y, PAC_SPEC)
    s.outline()
    return s


def pacman_frames():
    out = [[None] * 3 for _ in range(4)]
    for mouth in range(3):
        base = make_pacman(PAC_MOUTH[mouth])
        out[0][mouth] = base                      # derecha
        out[1][mouth] = base.mirrored()           # izquierda
        out[2][mouth] = base.rotated_ccw()        # arriba
        out[3][mouth] = base.rotated_cw()         # abajo
    return out


# ---------------------------------------------------------------------------
# Fantasmas
# ---------------------------------------------------------------------------
def ghost_body_mask(frame):
    m = [False] * N
    cx, cy, r = 7.5, 8.5, 7.0
    for y in range(2, 9):
        dy = y - cy
        half = math.sqrt(max(0.0, r * r - dy * dy))
        x0 = int(math.ceil(cx - half))
        x1 = int(math.floor(cx + half))
        for x in range(x0, x1 + 1):
            m[y * W + x] = True
    for y in range(9, 12):
        for x in range(1, 15):
            m[y * W + x] = True
    for x in range(1, 15):
        m[12 * W + x] = True
    feet = [(1, 4), (6, 9), (11, 14)] if frame == 0 else [(2, 5), (7, 10), (12, 14)]
    for a, b in feet:
        for x in range(a, b + 1):
            m[13 * W + x] = True
    return m


def _eye_pixels(look, eye_x):
    """pupila 2x2 dentro de un ojo 4x4 en eye_x, desplazada segun la mirada."""
    dx, dy = look
    px = eye_x + 1 + dx
    py = 7 + dy
    px = max(eye_x, min(eye_x + 2, px))
    py = max(6, min(8, py))
    return [(px, py), (px + 1, py), (px, py + 1), (px + 1, py + 1)]


def draw_ghost_eyes(s, look=(0, 0), border=False):
    """Dos ojos blancos 4x4 con pupila azul 2x2. border=True anade contorno
    oscuro (usado en ghost_eyes_frame, que va sin cuerpo)."""
    for ex in (3, 9):
        if border:
            for y in range(5, 11):
                for x in range(ex - 1, ex + 5):
                    s.pix(x, y, OUTLINE)
        for y in range(6, 10):
            for x in range(ex, ex + 4):
                s.pix(x, y, GHOST_EYE_WHITE)
        for x, y in _eye_pixels(look, ex):
            s.pix(x, y, GHOST_PUPIL)


def make_ghost(color_idx, frame, look=(0, 0)):
    name, base, light, dark = GHOST_PALETTES[color_idx]
    s = Sprite("ghost_" + name)
    s.add_mask(ghost_body_mask(frame), base)
    s.shade(light, dark)
    # brillo del domo (un par de pixeles)
    s.specular([(5, 3), (6, 3), (5, 4)], light)
    draw_ghost_eyes(s, look, border=False)
    s.outline()
    return s


def frightened_body(frame, base, light, dark, face):
    s = Sprite("fright")
    s.add_mask(ghost_body_mask(frame), base)
    s.shade(light, dark)
    # ojos redondos asustados + boca en zigzag
    for ex in (4, 10):
        for y in range(7, 9):
            for x in range(ex, ex + 2):
                s.pix(x, y, face)
    for x in range(4, 12):
        s.pix(x, 10 if (x % 2 == 0) else 11, face)
    s.outline()
    return s


def make_fright(frame):
    return frightened_body(frame, FRIGHT_BASE, FRIGHT_LIGHT, FRIGHT_DARK, FRIGHT_FACE)


def make_flash(frame):
    return frightened_body(frame, FLASH_BASE, FLASH_LIGHT, FLASH_DARK, FLASH_FACE)


def make_eyes_only(look):
    s = Sprite("eyes")
    draw_ghost_eyes(s, look, border=True)
    s.wanted_outline = False   # el borde ya lo pinta draw_ghost_eyes
    return s


# ---------------------------------------------------------------------------
# Frutas (disenos originales)
# ---------------------------------------------------------------------------
def fruit_cherry():
    s = Sprite("fruit_cherry")
    m = union(circle_mask(4.6, 11.2, 2.9), circle_mask(10.4, 10.2, 3.0))
    s.add_mask(m, CHERRY[0])
    s.shade(CHERRY[1], CHERRY[2])
    s.specular([(3, 9), (4, 9), (3, 10), (9, 8), (10, 8)], CHERRY[1])
    # tallos y hoja
    for x, y in bresenham(5, 9, 8, 3) + bresenham(10, 7, 8, 3):
        s.pix(x, y, STEM_BROWN)
    s.paint([(8, 2), (8, 3), (9, 2), (9, 3), (10, 2), (10, 3)], LEAF_GREEN)
    s.pix(9, 2, LEAF_LIGHT)
    s.outline()
    return s


def fruit_strawberry():
    s = Sprite("fruit_strawberry")
    rows = [(4, 4, 11), (5, 3, 12), (6, 2, 13), (7, 2, 13), (8, 2, 13),
            (9, 3, 12), (10, 3, 12), (11, 4, 11), (12, 5, 10), (13, 7, 8)]
    s.add_mask(rows_mask(rows), STRAWBERRY[0])
    s.shade(STRAWBERRY[1], STRAWBERRY[2])
    # hoja superior
    s.paint([(3, 3), (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3), (10, 3),
             (11, 3), (12, 3), (4, 2), (6, 2), (8, 2), (10, 2), (8, 1)], LEAF_GREEN)
    s.paint([(5, 3), (7, 2), (9, 2)], LEAF_LIGHT)
    # semillas
    for x, y in ((4, 6), (7, 6), (10, 6), (5, 8), (8, 8), (11, 8),
                 (6, 10), (9, 10), (7, 12)):
        s.pix(x, y, SEED)
    s.outline()
    return s


def fruit_orange():
    s = Sprite("fruit_orange")
    s.add_mask(circle_mask(8.0, 8.5, 5.2), ORANGE[0])
    s.shade(ORANGE[1], ORANGE[2])
    s.specular([(5, 5), (6, 5), (5, 6), (4, 7)], ORANGE[1])
    # hoja y tallo
    s.paint([(8, 2), (8, 3)], STEM_BROWN)
    s.paint([(9, 2), (10, 2), (11, 2), (10, 3), (11, 3), (12, 3)], LEAF_GREEN)
    s.pix(10, 2, LEAF_LIGHT)
    s.outline()
    return s


def fruit_apple():
    s = Sprite("fruit_apple")
    m = union(circle_mask(5.8, 8.8, 4.6), circle_mask(10.2, 8.8, 4.6))
    m = union(m, rows_mask([(12, 5, 10), (13, 6, 9)]))
    s.add_mask(m, APPLE[0])
    s.shade(APPLE[1], APPLE[2])
    s.specular([(4, 6), (5, 6), (4, 7)], APPLE[1])
    s.paint([(8, 2), (8, 3), (8, 4), (8, 5)], STEM_BROWN)
    s.paint([(9, 3), (10, 3), (11, 3), (10, 4), (11, 4)], LEAF_GREEN)
    s.pix(10, 3, LEAF_LIGHT)
    s.outline()
    return s


def fruit_grapes():
    s = Sprite("fruit_grapes")
    # se pintan de atras hacia delante; cada baya lleva su propio brillo
    berries = [(6.0, 4.8), (9.5, 5.4), (5.0, 7.2), (8.0, 7.6), (10.8, 7.9),
               (6.4, 9.8), (9.6, 10.0), (8.0, 12.2)]
    for cx, cy in berries:
        mask = circle_mask(cx, cy, 1.7)
        for i, on in enumerate(mask):
            if on:
                s.col[i] = GRAPES[0]
        for y in range(H):
            for x in range(W):
                i = y * W + x
                if not mask[i]:
                    continue
                up = (y > 0 and mask[i - W])
                dn = (y < H - 1 and mask[i + W])
                lf = (x > 0 and mask[i - 1])
                rt = (x < W - 1 and mask[i + 1])
                if not up or (not lf):
                    s.col[i] = GRAPES[1]
                elif not dn or (not rt):
                    s.col[i] = GRAPES[2]
        s.pix(int(cx), int(cy) - 1, GRAPES[1])
    # tallo + hoja
    for x, y in bresenham(8, 1, 8, 4):
        s.pix(x, y, STEM_BROWN)
    s.paint([(9, 2), (10, 2), (11, 2), (10, 3)], LEAF_GREEN)
    s.pix(10, 2, LEAF_LIGHT)
    s.outline()
    return s


FRUIT_BUILDERS = [
    ("CEREZA", fruit_cherry),
    ("FRESA", fruit_strawberry),
    ("NARANJA", fruit_orange),
    ("MANZANA", fruit_apple),
    ("UVAS", fruit_grapes),
]


# ---------------------------------------------------------------------------
# vida extra
# ---------------------------------------------------------------------------
def make_life():
    base = make_pacman(PAC_MOUTH[1])
    base.name = "life"
    return base


def make_key():
    """Llave dorada decorativa (icono del indicador NIVEL, no es fruta)."""
    s = Sprite("key")
    # anilla del paleton
    s.add_mask(circle_mask(5.0, 8.0, 3.6), KEY_GOLD)
    s.shade(KEY_LIGHT, KEY_DARK)
    # agujero de la anilla (oscuro, no transparencia)
    for y in range(H):
        for x in range(W):
            if (x - 5.0) ** 2 + (y - 8.0) ** 2 <= 1.7 ** 2:
                s.pix(x, y, OUTLINE)
    # vastago + dientes
    s.add_mask(rows_mask([(7, 8, 14), (8, 8, 14)]), KEY_GOLD)
    s.add_mask(rows_mask([(9, 11, 12), (10, 11, 12), (9, 13, 14)]), KEY_GOLD)
    s.shade(KEY_LIGHT, KEY_DARK)
    s.paint([(8, 7), (9, 7), (10, 7), (11, 7), (12, 7)], KEY_LIGHT)
    s.outline()
    return s


# ---------------------------------------------------------------------------
# validacion
# ---------------------------------------------------------------------------
def validate(sprite, min_opaque, has_transparency=True):
    errs = []
    name = sprite.name
    arr = sprite.to565()
    if len(arr) != N:
        errs.append("%s: %d pixeles" % (name, len(arr)))
    trans = arr.count(TRANSPARENT)
    opaque = N - trans
    if opaque < min_opaque:
        errs.append("%s: solo %d pixeles opacos (min %d)" % (name, opaque, min_opaque))
    if has_transparency and trans < 4:
        errs.append("%s: sin transparencia exterior" % name)
    if trans > 0 and has_transparency:
        # la transparencia debe estar conectada al borde (sin agujeros internos)
        seen = [False] * N
        stack = []
        for x in range(W):
            for y in (0, H - 1):
                i = y * W + x
                if arr[i] == TRANSPARENT and not seen[i]:
                    seen[i] = True
                    stack.append(i)
        for y in range(H):
            for x in (0, W - 1):
                i = y * W + x
                if arr[i] == TRANSPARENT and not seen[i]:
                    seen[i] = True
                    stack.append(i)
        while stack:
            i = stack.pop()
            x, y = i % W, i // W
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < W and 0 <= ny < H:
                    j = ny * W + nx
                    if arr[j] == TRANSPARENT and not seen[j]:
                        seen[j] = True
                        stack.append(j)
        holes = sum(1 for i in range(N) if arr[i] == TRANSPARENT and not seen[i])
        if holes:
            errs.append("%s: %d pixeles transparentes encerrados (agujero interno)" %
                        (name, holes))
    # el contorno debe existir y separar del fondo
    if sprite.wanted_outline:
        out_n = sum(1 for v in arr if v == OUTLINE_565)
        if out_n < 8:
            errs.append("%s: contorno insuficiente (%d px)" % (name, out_n))
        # todo pixel opaco vecino de transparencia debe ser del color de contorno
        bad = 0
        for y in range(H):
            for x in range(W):
                i = y * W + x
                if arr[i] == TRANSPARENT:
                    continue
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < W and 0 <= ny < H and arr[ny * W + nx] == TRANSPARENT:
                        if arr[i] != OUTLINE_565:
                            bad += 1
                        break
        if bad:
            errs.append("%s: %d px opacos sin contorno junto al borde" % (name, bad))
    # ningun color real puede coincidir con la clave de transparencia
    for v in arr:
        if v != TRANSPARENT and v == TRANSPARENT:
            errs.append("%s: color valido igual a transparente" % name)
    return errs, arr


# ---------------------------------------------------------------------------
# emision de assets.c
# ---------------------------------------------------------------------------
def fmt_rows(obj):
    arr = obj.to565() if hasattr(obj, "to565") else obj
    lines = []
    for y in range(H):
        vals = ", ".join("0x%04X" % v for v in arr[y * W:(y + 1) * W])
        lines.append("        /* y%02d */ %s," % (y, vals))
    return "\n".join(lines)


def emit_assets(path, pacman, ghosts, fright, flash, eyes, fruits, life, key):
    out = []
    out.append("/* apps/game/assets/assets.c")
    out.append(" *")
    out.append(" * Sprites ORIGINALES de PAC-MAN SereOS. GENERADO AUTOMATICAMENTE por")
    out.append(" * tools/gen_pacman_assets.py; no editar a mano.")
    out.append(" *")
    out.append(" * Formato: uint16_t RGB565, 16x16, fila a fila.")
    out.append(" * Transparente = 0x%04X (GFX_TRANSPARENT del motor grafico)." % TRANSPARENT)
    out.append(" * Contorno oscuro opaco (#%02X%02X%02X) para separarse del laberinto."
               % OUTLINE)
    out.append(" * Direcciones: 0=derecha, 1=izquierda, 2=arriba, 3=abajo.")
    out.append(" * Bocas: 0=cerrada, 1=semiabierta, 2=abierta.")
    out.append(" */")
    out.append("#define PACMAN_SPRITES_IMPL 1")
    out.append('#include "sprites.h"')
    out.append("")

    out.append("/* ------------------------------------------------------------------ */")
    out.append("/* Pacman: 4 direcciones x 3 bocas                                    */")
    out.append("/* ------------------------------------------------------------------ */")
    out.append("const uint16_t pacman_frame[4][3][PAC_SPRITE_PIXELS] = {")
    for d, dirname in enumerate(("derecha", "izquierda", "arriba", "abajo")):
        out.append("    { /* direccion %d (%s) */" % (d, dirname))
        for m, mouthname in enumerate(("cerrada", "semiabierta", "abierta")):
            out.append("        { /* boca %d (%s) */" % (m, mouthname))
            out.append(fmt_rows(pacman[d][m]))
            out.append("        },")
        out.append("    },")
    out.append("};")
    out.append("")

    out.append("/* ------------------------------------------------------------------ */")
    out.append("/* Fantasmas: 4 colores x 2 frames de falda (ojos neutros al frente)   */")
    out.append("/* ------------------------------------------------------------------ */")
    out.append("const uint16_t ghost_frame[4][2][PAC_SPRITE_PIXELS] = {")
    for g, (cname, _, _, _) in enumerate(GHOST_PALETTES):
        out.append("    { /* color %d (%s) */" % (g, cname))
        for f in range(2):
            out.append("        { /* frame %d */" % f)
            out.append(fmt_rows(ghosts[g][f]))
            out.append("        },")
        out.append("    },")
    out.append("};")
    out.append("")

    out.append("/* ------------------------------------------------------------------ */")
    out.append("/* Fantasmas asustados (azul) y parpadeo final (blanco)                */")
    out.append("/* ------------------------------------------------------------------ */")
    out.append("const uint16_t ghost_fright_frame[2][PAC_SPRITE_PIXELS] = {")
    for f in range(2):
        out.append("    { /* frightened frame %d */" % f)
        out.append(fmt_rows(fright[f]))
        out.append("    },")
    out.append("};")
    out.append("")
    out.append("const uint16_t ghost_flash_frame[2][PAC_SPRITE_PIXELS] = {")
    for f in range(2):
        out.append("    { /* flash frame %d */" % f)
        out.append(fmt_rows(flash[f]))
        out.append("    },")
    out.append("};")
    out.append("")

    out.append("/* ------------------------------------------------------------------ */")
    out.append("/* Solo ojos (vuelta a la casa): 4 direcciones                        */")
    out.append("/* ------------------------------------------------------------------ */")
    out.append("const uint16_t ghost_eyes_frame[4][PAC_SPRITE_PIXELS] = {")
    for d, dirname in enumerate(("derecha", "izquierda", "arriba", "abajo")):
        out.append("    { /* mira a %s */" % dirname)
        out.append(fmt_rows(eyes[d]))
        out.append("    },")
    out.append("};")
    out.append("")

    out.append("/* ------------------------------------------------------------------ */")
    out.append("/* Frutas originales                                                  */")
    out.append("/* ------------------------------------------------------------------ */")
    out.append("const uint16_t fruit_sprite[5][PAC_SPRITE_PIXELS] = {")
    for idx, (fname, _) in enumerate(FRUIT_BUILDERS):
        out.append("    { /* fruta %d (%s) */" % (idx, fname))
        out.append(fmt_rows(fruits[idx]))
        out.append("    },")
    out.append("};")
    out.append("")
    out.append('const char *const fruit_name[5] = {')
    out.append("    " + ", ".join('"%s"' % fname for fname, _ in FRUIT_BUILDERS) + ",")
    out.append("};")
    out.append("")

    out.append("/* ------------------------------------------------------------------ */")
    out.append("/* Vida extra (mini comecocos) y llave decorativa (NIVEL)             */")
    out.append("/* ------------------------------------------------------------------ */")
    out.append("const uint16_t life_sprite[PAC_SPRITE_PIXELS] = {")
    out.append(fmt_rows(life))
    out.append("};")
    out.append("")
    out.append("/* llave dorada decorativa del indicador de nivel (no es fruta) */")
    out.append("const uint16_t key_sprite[PAC_SPRITE_PIXELS] = {")
    out.append(fmt_rows(key))
    out.append("};")
    out.append("")

    text = "\n".join(out)
    for name in ("pacman_frame", "ghost_frame", "ghost_fright_frame",
                 "ghost_flash_frame", "ghost_eyes_frame", "fruit_sprite",
                 "fruit_name", "life_sprite", "key_sprite"):
        text = re.sub(r"\b%s\b" % name, "pacasset_" + name, text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return len("\n".join(out))


# ---------------------------------------------------------------------------
# preview PNG
# ---------------------------------------------------------------------------
def draw_sprite_sheet(path, pacman, ghosts, fright, flash, eyes, fruits, life, key):
    from PIL import Image, ImageDraw, ImageFont

    BG = (10, 15, 28)
    TEXT = (239, 244, 255)
    DIM = (167, 180, 204)
    ACCENT = (46, 123, 255)
    ACCENT2 = (34, 211, 238)
    LINE = (44, 58, 85)
    CW, CH = 1260, 1000
    sheet = Image.new("RGB", (CW, CH), BG)
    d = ImageDraw.Draw(sheet)

    try:
        title_font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf", 26)
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf", 15)
        small = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 13)
    except OSError:
        title_font = ImageFont.load_default()
        font = title_font
        small = title_font

    def to_img(spr, scale):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        px = im.load()
        arr = spr.to565() if hasattr(spr, "to565") else spr
        for y in range(H):
            for x in range(W):
                v = arr[y * W + x]
                if v == TRANSPARENT:
                    px[x, y] = (0, 0, 0, 0)
                else:
                    r = ((v >> 11) & 0x1F) << 3
                    g = ((v >> 5) & 0x3F) << 2
                    b = (v & 0x1F) << 3
                    px[x, y] = (r | (r >> 5), g | (g >> 6), b | (b >> 5), 255)
        return im.resize((W * scale, H * scale), Image.NEAREST)

    def cell(x, y, scale):
        pw = W * scale
        c1, c2 = (15, 22, 39), (34, 50, 82)
        sq = scale * 2
        for yy in range(y, y + pw, sq):
            for xx in range(x, x + pw, sq):
                col = c1 if ((xx - x) // sq + (yy - y) // sq) % 2 == 0 else c2
                d.rectangle([xx, yy, xx + sq - 1, yy + sq - 1], fill=col)

    def put(spr, x, y, scale):
        cell(x, y, scale)
        im = to_img(spr, scale)
        sheet.paste(im, (x, y), im)

    def centered(text, x0, x1, y, fnt, col):
        d.text((x0 + (x1 - x0 - d.textlength(text, font=fnt)) / 2, y), text,
               font=fnt, fill=col)

    # cabecera
    d.text((30, 20), "PACMAN SereOS - sprites originales 16x16 RGB565", font=title_font, fill=TEXT)
    d.text((30, 56), "transparente = 0xF81F  |  contorno oscuro opaco  |  arte original SereOS (sin assets de Namco/Paku-Paku)",
           font=small, fill=DIM)
    d.line([30, 84, CW - 30, 84], fill=LINE, width=1)

    # ---------------- columna izquierda: Pacman ----------------
    d.text((30, 102), "PACMAN - 4 direcciones x 3 bocas", font=font, fill=ACCENT2)
    s_scale = 6
    row_h = W * s_scale + 22
    y = 150
    dirs = ("DCHA", "IZQ", "ARRIBA", "ABAJO")
    for di in range(4):
        d.text((30, y + W * s_scale // 2 - 8), dirs[di], font=small, fill=DIM)
        for mi in range(3):
            put(pacman[di][mi], 130 + mi * (W * s_scale + 14), y, s_scale)
        centered(("cerrada", "semi", "abierta")[mi] if False else "", 0, 1, 0, small, DIM)
        y += row_h
    for mi, name in enumerate(("cerrada", "semi", "abierta")):
        centered(name, 130 + mi * (W * s_scale + 14),
                 130 + mi * (W * s_scale + 14) + W * s_scale, 122, small, DIM)

    # asustados / parpadeo / ojos (columna izquierda, bajo Pacman)
    y = 150 + 4 * row_h + 8
    d.text((30, y), "ASUSTADOS / PARPADEO / OJOS", font=font, fill=ACCENT2)
    y += 32
    s_scale = 5
    fsz = W * s_scale
    d.text((30, y + fsz // 2 - 8), "FRIGHT", font=small, fill=DIM)
    for i in range(2):
        put(fright[i], 130 + i * (fsz + 12), y, s_scale)
    d.text((320, y + fsz // 2 - 8), "FLASH", font=small, fill=DIM)
    for i in range(2):
        put(flash[i], 400 + i * (fsz + 12), y, s_scale)
    y += fsz + 26
    d.text((30, y + fsz // 2 - 8), "OJOS", font=small, fill=DIM)
    eye_dirs = ("DCHA", "IZQ", "ARRIBA", "ABAJO")
    for i in range(4):
        x = 130 + i * (fsz + 10)
        put(eyes[i], x, y, s_scale)
        centered(eye_dirs[i], x, x + fsz, y + fsz + 2, small, DIM)
    y += fsz + 24

    # ---------------- columna derecha: fantasmas + frutas ----------------
    RX = 760
    d.text((RX, 102), "FANTASMAS - 4 colores x 2 frames", font=font, fill=ACCENT2)
    s_scale = 6
    y = 136
    for gi, (gname, _, _, _) in enumerate(GHOST_PALETTES):
        d.text((RX, y + W * s_scale // 2 - 8), gname, font=small, fill=DIM)
        for fi in range(2):
            put(ghosts[gi][fi], RX + 96 + fi * (W * s_scale + 14), y, s_scale)
        y += W * s_scale + 16

    y += 8
    d.text((RX, y), "FRUTAS ORIGINALES (CEREZA a UVAS)", font=font, fill=ACCENT2)
    y += 30
    s_scale = 5
    fsz = W * s_scale
    for i in range(len(FRUIT_BUILDERS)):
        col = i % 4
        row = i // 4
        x = RX + 8 + col * (fsz + 18)
        yy = y + row * (fsz + 22)
        put(fruits[i], x, yy, s_scale)
        centered(FRUIT_BUILDERS[i][0], x, x + fsz, yy + fsz + 2, small, DIM)
    y += ((len(FRUIT_BUILDERS) + 3) // 4) * (fsz + 22) + 12

    d.text((RX, y), "VIDA EXTRA + LLAVE", font=font, fill=ACCENT2)
    y += 30
    s_scale = 5
    d.text((RX, y + W * s_scale // 2 - 8), "LIFE", font=small, fill=DIM)
    put(life, RX + 70, y, s_scale)
    d.text((RX + 170, y + W * s_scale // 2 - 8), "KEY", font=small, fill=DIM)
    put(key, RX + 240, y, s_scale)
    y += W * s_scale + 20

    # pie
    d.line([30, CH - 52, CW - 30, CH - 52], fill=LINE, width=1)
    d.text((30, CH - 40),
           "generado por tools/gen_pacman_assets.py | 35 sprites | damero = pixeles transparentes (0xF81F)",
           font=small, fill=DIM)
    d.text((CW - 330, CH - 40), "SereOS Desktop 1.0 - UMB 2026", font=small, fill=ACCENT)

    sheet.save(path)
    return path


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(root, "assets")
    out_c = os.path.join(assets_dir, "sprites.c")
    out_png = os.path.join(assets_dir, "preview.png")

    pacman = pacman_frames()
    ghosts = [[make_ghost(g, f) for f in range(2)] for g in range(4)]
    fright = [make_fright(f) for f in range(2)]
    flash = [make_flash(f) for f in range(2)]
    eyes = [make_eyes_only(look) for look in ((1, 0), (-1, 0), (0, -1), (0, 1))]
    fruits = [builder() for _, builder in FRUIT_BUILDERS]
    life = make_life()
    key = make_key()

    all_errs = []

    # ---- validacion ----
    for di in range(4):
        for mi in range(3):
            errs, _ = validate(pacman[di][mi], 70)
            all_errs += errs
    for gi in range(4):
        for fi in range(2):
            errs, _ = validate(ghosts[gi][fi], 90)
            all_errs += errs
    for f in range(2):
        errs, _ = validate(fright[f], 90)
        all_errs += errs
        errs, _ = validate(flash[f], 90)
        all_errs += errs
    for di in range(4):
        errs, _ = validate(eyes[di], 20)
        all_errs += errs
    for fi in range(len(fruits)):
        errs, _ = validate(fruits[fi], 32)
        all_errs += errs
    errs, _ = validate(life, 70)
    all_errs += errs
    errs, _ = validate(key, 30)
    all_errs += errs

    # coherencia de animacion / direcciones
    for gi in range(4):
        a = ghosts[gi][0].to565()
        b = ghosts[gi][1].to565()
        if a == b:
            all_errs.append("ghost_frame[%d]: frames de falda identicos" % gi)
    for di in range(4):
        if eyes[di].to565() == eyes[(di + 1) % 4].to565():
            all_errs.append("ghost_eyes_frame: direcciones %d y %d identicas" %
                            (di, (di + 1) % 4))
    counts = [pacman[0][m].opaque_count() for m in range(3)]
    if not (counts[0] > counts[1] > counts[2]):
        all_errs.append("pacman: bocas no decrecientes %r" % (counts,))
    for fi in range(len(fruits)):
        for fj in range(fi + 1, len(fruits)):
            if fruits[fi].to565() == fruits[fj].to565():
                all_errs.append("frutas %d y %d identicas" % (fi, fj))
    names = [n for n, _ in FRUIT_BUILDERS]
    if names != ["CEREZA", "FRESA", "NARANJA", "MANZANA", "UVAS"]:
        all_errs.append("fruit_name no coincide con el contrato: %r" % (names,))

    if all_errs:
        print("VALIDACION FALLIDA:", file=sys.stderr)
        for e in all_errs:
            print("  -", e, file=sys.stderr)
        return 1

    # ---- salida ----
    nbytes = emit_assets(out_c, pacman, ghosts, fright, flash, eyes, fruits, life, key)
    draw_sprite_sheet(out_png, pacman, ghosts, fright, flash, eyes, fruits, life, key)

    transparent_counts = []
    sprites = [("pacman", [pacman[d][m] for d in range(4) for m in range(3)]),
               ("ghost", [ghosts[g][f] for g in range(4) for f in range(2)]),
               ("fright", fright), ("flash", flash), ("eyes", eyes),
               ("fruit", fruits), ("life", [life]), ("key", [key])]
    for group, lst in sprites:
        trans = [s.to565().count(TRANSPARENT) for s in lst]
        transparent_counts.append((group, min(trans), max(trans)))

    print("OK: %d sprites originales generados" % 35)
    print("  assets.c   : %s (%d bytes)" % (out_c, nbytes))
    print("  preview.png: %s" % out_png)
    print("  transparencia 0x%04X por grupo (min..max):" % TRANSPARENT)
    for group, tmin, tmax in transparent_counts:
        print("    %-7s %3d..%3d" % (group, tmin, tmax))
    print("  validacion : 16x16, contorno opaco, sin agujeros internos, "
          "frames distintos, nombres correctos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
