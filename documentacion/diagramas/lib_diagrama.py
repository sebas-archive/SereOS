# -*- coding: utf-8 -*-
"""lib_diagrama.py: utilidades compartidas para los diagramas de SereOS.

Genera SVG a mano (coordenadas controladas), mide el texto con las mismas
fuentes que se usan al renderizar (Inter y JetBrains Mono), enruta conectores
ortogonales por canales libres y verifica automaticamente que no haya
flechas sobre cajas, etiquetas solapadas ni texto fuera de su caja.

Convencion: el lienzo de diseno mide 1200 px de ancho y se exporta a 2400 px
(escala 2). Con un ancho de 16 cm en el documento, 21 px de diseno equivalen a
unos 7,9 pt, 22 px a unos 8,3 pt y 26 px a unos 9,8 pt.
"""
import heapq
import html
import math
import os
import subprocess

from PIL import ImageFont

FONT_SANS = "/usr/share/fonts/inter/InterVariable.ttf"
FONT_MONO = {"Regular": "/usr/share/fonts/TTF/JetBrainsMono-Regular.ttf",
             "Bold": "/usr/share/fonts/TTF/JetBrainsMono-Bold.ttf"}

W_DESIGN = 1200          # ancho de diseno (px)
MARGIN = 40              # margen del lienzo
GRID = 10                # paso del enrutador
CLEAR = 12               # holgura de las flechas respecto de las cajas
MIN_FONT = 21            # texto minimo (px de diseno)
TITLE_FONT = 36
PAD = 16                 # relleno interno de las cajas
EXPORT_SCALE = 2

# --- paleta unica: un color por significado --------------------------------
PALETA = {
    "azul":     dict(fill="#DBEAFE", stroke="#2563EB", dark="#1E3A8A", sig="nucleo y logica"),
    "verde":    dict(fill="#DCFCE7", stroke="#16A34A", dark="#14532D", sig="subsistemas y memoria"),
    "ambar":    dict(fill="#FEF3C7", stroke="#D97706", dark="#78350F", sig="drivers y compilacion"),
    "rojo":     dict(fill="#FEE2E2", stroke="#DC2626", dark="#7F1D1D", sig="arranque, errores y critico"),
    "violeta":  dict(fill="#EDE9FE", stroke="#7C3AED", dark="#4C1D95", sig="aplicaciones y GUI"),
    "gris":     dict(fill="#E5E7EB", stroke="#6B7280", dark="#1F2937", sig="hardware y externo"),
    "turquesa": dict(fill="#CCFBF1", stroke="#0D9488", dark="#134E4A", sig="graficos y render"),
}
INK = "#111827"
SUB = "#374151"
ARROW = "#374151"
NOTE = "#4B5563"

_font_cache = {}


def _font(kind, weight, size):
    key = (kind, weight, size)
    if key not in _font_cache:
        if kind == "mono":
            f = ImageFont.truetype(FONT_MONO["Bold" if weight == "Bold" else "Regular"], size)
        else:
            f = ImageFont.truetype(FONT_SANS, size)
            try:
                f.set_variation_by_name("Bold" if weight == "Bold" else "Regular")
            except Exception:
                pass
        _font_cache[key] = f
    return _font_cache[key]


def medir(texto, tam, kind="sans", weight="Regular"):
    """Ancho en px del texto (con un 3 % de holgura por diferencias de render)."""
    return _font(kind, weight, tam).getlength(texto) * 1.03


def esc(t):
    return html.escape(t, quote=False)


class Rect:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def x2(self):
        return self.x + self.w

    @property
    def y2(self):
        return self.y + self.h

    def grow(self, d):
        return Rect(self.x - d, self.y - d, self.w + 2 * d, self.h + 2 * d)

    def hit(self, o):
        return not (self.x2 <= o.x or o.x2 <= self.x or self.y2 <= o.y or o.y2 <= self.y)

    def contains(self, px, py):
        return self.x < px < self.x2 and self.y < py < self.y2


def seg_hit_rect(p, q, r):
    """Segmento ortogonal p-q contra rectangulo r (interior abierto)."""
    x1, x2 = sorted((p[0], q[0]))
    y1, y2 = sorted((p[1], q[1]))
    return not (x2 <= r.x or r.x2 <= x1 or y2 <= r.y or r.y2 <= y1) if (x1 != x2 or y1 != y2) else False


class Box:
    def __init__(self, id, x, y, w, h, color, title, lines, num, dashed, thick, tsize, lsize, align, obstacle=True, role="box"):
        self.id, self.color, self.title, self.lines = id, color, title, lines
        self.rect = Rect(x, y, w, h)
        self.num, self.dashed, self.thick = num, dashed, thick
        self.tsize, self.lsize, self.align = tsize, lsize, align
        self.obstacle, self.role = obstacle, role

    def port(self, side, frac=0.5):
        r = self.rect
        if side == "t":
            return (r.x + r.w * frac, r.y), (0, -1)
        if side == "b":
            return (r.x + r.w * frac, r.y2), (0, 1)
        if side == "l":
            return (r.x, r.y + r.h * frac), (-1, 0)
        return (r.x2, r.y + r.h * frac), (1, 0)


class Arrow:
    def __init__(self, a, b, sa, sb, label, dashed, color, fa, fb, recta=False):
        self.recta = recta
        self.a, self.b, self.sa, self.sb = a, b, sa, sb
        self.label, self.dashed, self.color, self.fa, self.fb = label, dashed, color, fa, fb
        self.pts = []
        self.pill = None


def tamano_caja(titulo, lineas=(), tsize=26, lsize=22, min_w=0, min_h=0):
    """(w, h) minimos redondeados a 20 px para el contenido dado.
    lineas: lista de (texto, 'sans'|'mono')."""
    ancho = medir(titulo, tsize, "sans", "Bold")
    for t, k in lineas:
        ancho = max(ancho, medir(t, lsize, k))
    w = max(min_w, math.ceil((ancho + 2 * PAD) / 20) * 20)
    alto = tsize * 1.25 + (len(lineas) * lsize * 1.3 if lineas else 0) + 2 * PAD
    if lineas:
        alto += 6
    h = max(min_h, math.ceil(alto / 20) * 20)
    return w, h


class Diagrama:
    def __init__(self, nombre, titulo, nota=None):
        self.nombre, self.titulo, self.nota = nombre, titulo, nota
        self.boxes = {}
        self.arrows = []
        self.extras = []        # svg crudo
        self.extra_rects = []   # (Rect, nombre) para verificar solapes
        self.texts = []         # (x, y, texto, tam, kind, weight, color, anchor)
        self.labels = []
        self.fuera = []         # elementos decorativos sin colision (llaves, saltos)
        self.errores = []
        self.top = 120          # y de inicio del contenido

    # ------------------------------------------------------------------ cajas
    def caja(self, id, x, y, w, h, color, titulo, lineas=(), num=None, dashed=False,
             thick=False, tsize=26, lsize=22, align="center", obstacle=True):
        assert x % 2 == 0 and y % 10 == 0 and w % 10 == 0 and h % 10 == 0, (id, x, y, w, h)
        lineas = [(l, "sans") if isinstance(l, str) else l for l in lineas]
        b = Box(id, x, y, w, h, color, titulo, lineas, num, dashed, thick, tsize, lsize, align, obstacle)
        self.boxes[id] = b
        return b

    def panel(self, id, x, y, w, h, color, titulo, lineas, tsize=24, lsize=22, align="left"):
        """Caja informativa (sin flechas) con texto alineado a la izquierda."""
        b = self.caja(id, x, y, w, h, color, titulo, lineas, tsize=tsize, lsize=lsize, align=align)
        b.role = "panel"
        return b

    def flecha(self, a, b, sa="r", sb="l", label=None, dashed=False, color=None, fa=0.5, fb=0.5, recta=False):
        ar = Arrow(a, b, sa, sb, label, dashed, color or ARROW, fa, fb, recta)
        self.arrows.append(ar)
        return ar

    def texto(self, x, y, t, tam=22, kind="sans", weight="Regular", color=INK, anchor="start"):
        self.texts.append((x, y, t, tam, kind, weight, color, anchor))
        w = medir(t, tam, kind, weight)
        x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
        self.extra_rects.append((Rect(x0, y - tam, w, tam * 1.3), "texto:" + t[:20]))

    def llave(self, x, y1, y2, lado="r"):
        s = 1 if lado == "r" else -1
        ym = (y1 + y2) / 2
        d = (f"M{x},{y1} Q{x + s * 12},{y1} {x + s * 12},{y1 + 16} L{x + s * 12},{ym - 16} "
             f"Q{x + s * 12},{ym} {x + s * 24},{ym} Q{x + s * 12},{ym} {x + s * 12},{ym + 16} "
             f"L{x + s * 12},{y2 - 16} Q{x + s * 12},{y2} {x},{y2}")
        self.fuera.append(f'<path d="{d}" fill="none" stroke="#4B5563" stroke-width="2.5"/>')
        self.extra_rects.append((Rect(min(x, x + s * 24), y1, 24, y2 - y1), "llave"))

    def linea(self, x1, y1, x2, y2, flecha=True, color="#6B7280", ancho=2.5):
        mk = ' marker-end="url(#pt)"' if flecha else ""
        self.fuera.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="{ancho}"{mk}/>')
        self.extra_rects.append((Rect(min(x1, x2) - 6, min(y1, y2), abs(x2 - x1) + 12, abs(y2 - y1)), "linea-margen"))

    def leyenda(self, x, y, items, ancho_tot=1120):
        """Fila de muestras de color con su significado (ancho segun el texto)."""
        anchos = [38 + medir(t, MIN_FONT) for _, t in items]
        libre = ancho_tot - sum(anchos)
        if libre < 20 * (len(items) - 1):
            self.errores.append("leyenda excede el ancho")
            return
        sep = libre / (len(items) - 1)
        xx = x
        for (col, txt), w in zip(items, anchos):
            pal = PALETA[col]
            self.fuera.append(f'<rect x="{xx:.1f}" y="{y}" width="28" height="28" rx="6" fill="{pal["fill"]}" stroke="{pal["stroke"]}" stroke-width="2"/>')
            self.fuera.append(f'<text x="{xx + 38:.1f}" y="{y + 21}" font-family="Inter" font-size="{MIN_FONT}" fill="{INK}">{esc(txt)}</text>')
            self.extra_rects.append((Rect(xx, y, w, 28), "leyenda"))
            xx += w + sep

    def salto(self, cx, cy, ancho=160):
        """Simbolo de corte (~ ~) para indicar que el mapa no esta a escala."""
        x0 = cx - ancho / 2
        for dy in (-6, 6):
            d = f"M{x0},{cy + dy}"
            n = int(ancho // 20)
            for i in range(n):
                xa = x0 + i * 20
                d += f" q5,{-6 if i % 2 == 0 else 6} 10,0 t10,0"
            self.fuera.append(f'<path d="{d}" fill="none" stroke="#6B7280" stroke-width="2"/>')
        self.extra_rects.append((Rect(x0, cy - 14, ancho, 28), "salto"))

    # ------------------------------------------------------------ enrutador
    def _obstaculos(self, excluir=()):
        return [b.rect.grow(CLEAR) for b in self.boxes.values() if b.obstacle]

    def _enrutar(self, ar, uso):
        A, B = self.boxes[ar.a], self.boxes[ar.b]
        p0, n0 = A.port(ar.sa, ar.fa)
        p1, n1 = B.port(ar.sb, ar.fb)
        s0 = (p0[0] + n0[0] * 20, p0[1] + n0[1] * 20)
        s1 = (p1[0] + n1[0] * 20, p1[1] + n1[1] * 20)
        obst = self._obstaculos()
        Wc, Hc = self.W, self.Hmax
        G = GRID

        def libre(x, y):
            if x < MARGIN / 2 or y < MARGIN / 2 or x > Wc - MARGIN / 2 or y > Hc:
                return False
            for r in obst:
                if r.contains(x, y):
                    return False
            return True

        # A* sobre (celda, direccion)
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        start = (round(s0[0] / G) * G, round(s0[1] / G) * G)
        goal = (round(s1[0] / G) * G, round(s1[1] / G) * G)
        din = (-n1[0], -n1[1])
        pq = [(0, 0, start, tuple(n0), None)]
        best = {}
        came = {}
        while pq:
            f, g, cur, d, par = heapq.heappop(pq)
            key = (cur, d)
            if key in best and best[key] <= g:
                continue
            best[key] = g
            came[key] = par
            if cur == goal and d == din:
                path = [cur]
                k = key
                while came[k] is not None:
                    k = came[k]
                    path.append(k[0])
                path.reverse()
                return self._armar(p0, p1, path)
            for nd in dirs:
                if nd == (-d[0], -d[1]):
                    continue
                nx, ny = cur[0] + nd[0] * G, cur[1] + nd[1] * G
                if not libre(nx, ny) and (nx, ny) != goal and (nx, ny) != start:
                    continue
                cost = 1
                if nd != d:
                    cost += 40
                cost += uso.get((nx, ny, "h" if nd[1] == 0 else "v"), 0)
                cost += 300 if uso.get((nx, ny, "v" if nd[1] == 0 else "h")) else 0
                heapq.heappush(pq, (g + cost + (abs(nx - goal[0]) + abs(ny - goal[1])) / G * 0.9, g + cost,
                                    (nx, ny), nd, key))
        raise RuntimeError(f"sin ruta para {ar.a}->{ar.b}")

    def _armar(self, p0, p1, path):
        pts = [p0] + path + [p1]
        out = [pts[0]]
        for i in range(1, len(pts) - 1):
            a, b, c = out[-1], pts[i], pts[i + 1]
            if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]):
                continue
            out.append(b)
        out.append(pts[-1])
        return out

    def _marcar_uso(self, pts, uso):
        for a, b in zip(pts, pts[1:]):
            if a[0] == b[0]:
                for y in range(int(min(a[1], b[1])), int(max(a[1], b[1])) + 1, GRID):
                    uso[(round(a[0] / GRID) * GRID, round(y / GRID) * GRID, "v")] = 200
            else:
                for x in range(int(min(a[0], b[0])), int(max(a[0], b[0])) + 1, GRID):
                    uso[(round(x / GRID) * GRID, round(a[1] / GRID) * GRID, "h")] = 200

    def enrutar_todo(self):
        uso = {}
        self.Hmax = max(b.rect.y2 for b in self.boxes.values()) + 80
        self.W = W_DESIGN
        for ar in self.arrows:
            if ar.recta:
                A, B = self.boxes[ar.a], self.boxes[ar.b]
                ar.pts = [A.port(ar.sa, ar.fa)[0], B.port(ar.sb, ar.fb)[0]]
            else:
                ar.pts = self._enrutar(ar, uso)
            self._marcar_uso(ar.pts, uso)
        self._etiquetas()

    # ------------------------------------------------------------ etiquetas
    def _etiquetas(self):
        taken = []
        for ar in self.arrows:
            if not ar.label:
                continue
            lw = medir(ar.label, MIN_FONT, "sans", "Regular") + 24
            lh = MIN_FONT + 14
            cands = []
            for a, b in zip(ar.pts, ar.pts[1:]):
                horiz = a[1] == b[1]
                length = abs(b[0] - a[0]) if horiz else abs(b[1] - a[1])
                need = (lw if horiz else lh) + 24
                if length >= need:
                    for fr in (0.5, 0.4, 0.6, 0.3, 0.7):
                        cx = a[0] + (b[0] - a[0]) * fr
                        cy = a[1] + (b[1] - a[1]) * fr
                        cands.append((abs(fr - 0.5), -length, Rect(cx - lw / 2, cy - lh / 2, lw, lh)))
            cands.sort(key=lambda t: (t[0], t[1]))
            ok = None
            for _, _, r in cands:
                if self._pill_libre(r, ar, taken):
                    ok = r
                    break
            if ok is None:
                self.errores.append(f"no hay lugar libre para la etiqueta '{ar.label}' ({ar.a}->{ar.b})")
                continue
            ar.pill = ok
            taken.append(ok)

    def _pill_libre(self, r, ar, taken):
        g = r.grow(4)
        for b in self.boxes.values():
            if g.hit(b.rect):
                return False
        for t in taken:
            if g.hit(t):
                return False
        for o in self.arrows:
            if o is ar:
                continue
            for a, b in zip(o.pts, o.pts[1:]):
                if seg_hit_rect(a, b, g):
                    return False
        for rr, _ in self.extra_rects:
            if g.hit(rr):
                return False
        return True

    # ---------------------------------------------------------- verificacion
    def verificar(self):
        err = list(self.errores)
        cajas = list(self.boxes.values())
        # 1) cajas solapadas
        for i, a in enumerate(cajas):
            for b in cajas[i + 1:]:
                if a.rect.hit(b.rect):
                    err.append(f"cajas solapadas: {a.id} y {b.id}")
        # 2) texto dentro de su caja
        for b in cajas:
            wmax = b.rect.w - 2 * PAD
            hmax = b.rect.h - 2 * PAD
            if medir(b.title, b.tsize, "sans", "Bold") > wmax + 0.01:
                err.append(f"titulo fuera de caja {b.id}: '{b.title}'")
            alto = b.tsize * 1.25 + (len(b.lines) * b.lsize * 1.3 + 6 if b.lines else 0)
            if alto > hmax + 1:
                err.append(f"texto excede el alto de la caja {b.id} ({alto:.0f} > {hmax:.0f})")
            for t, k in b.lines:
                if medir(t, b.lsize, k) > wmax + 0.01:
                    err.append(f"linea fuera de caja {b.id}: '{t}' ({medir(t, b.lsize, k):.0f} > {wmax:.0f})")
            if b.tsize < MIN_FONT or b.lsize < MIN_FONT:
                err.append(f"fuente menor de {MIN_FONT}px en {b.id}")
        # 3) flechas: no deben tocar cajas (salvo extremos), ni solapar otras flechas
        for ar in self.arrows:
            n = len(ar.pts) - 1
            for i, (a, b) in enumerate(zip(ar.pts, ar.pts[1:])):
                for bx in cajas:
                    if not bx.obstacle:
                        continue
                    r = bx.rect.grow(2)
                    es_extremo = (bx.id == ar.a and i == 0) or (bx.id == ar.b and i == n - 1)
                    if es_extremo:
                        # el tramo extremo solo puede tocar su caja en el punto de arranque
                        r = bx.rect.grow(-1)
                        # recortar el segmento 1 px
                        if seg_hit_rect(a, b, r):
                            err.append(f"flecha {ar.a}->{ar.b} entra en su propia caja")
                        continue
                    if seg_hit_rect(a, b, r):
                        err.append(f"flecha {ar.a}->{ar.b} cruza la caja {bx.id}")
                for rr, nm in self.extra_rects:
                    if seg_hit_rect(a, b, rr.grow(2)):
                        err.append(f"flecha {ar.a}->{ar.b} cruza '{nm}'")
        for i, x in enumerate(self.arrows):
            for y in self.arrows[i + 1:]:
                comp = (x.a == y.a and x.sa == y.sa and x.fa == y.fa) or (x.b == y.b and x.sb == y.sb and x.fb == y.fb)
                for a, b in zip(x.pts, x.pts[1:]):
                    for c, d in zip(y.pts, y.pts[1:]):
                        if a[0] == b[0] == c[0] == d[0]:
                            lo, hi = max(min(a[1], b[1]), min(c[1], d[1])), min(max(a[1], b[1]), max(c[1], d[1]))
                            if hi - lo > 1 and not comp:
                                err.append(f"flechas superpuestas {x.a}->{x.b} y {y.a}->{y.b}")
                        elif a[1] == b[1] == c[1] == d[1]:
                            lo, hi = max(min(a[0], b[0]), min(c[0], d[0])), min(max(a[0], b[0]), max(c[0], d[0]))
                            if hi - lo > 1 and not comp:
                                err.append(f"flechas superpuestas {x.a}->{x.b} y {y.a}->{y.b}")
                        else:
                            # cruce perpendicular
                            h, v = ((a, b), (c, d)) if a[1] == b[1] else ((c, d), (a, b))
                            if h[0][1] == h[1][1] and v[0][0] == v[1][0]:
                                if (min(h[0][0], h[1][0]) < v[0][0] < max(h[0][0], h[1][0]) and
                                        min(v[0][1], v[1][1]) < h[0][1] < max(v[0][1], v[1][1])):
                                    err.append(f"cruce de flechas {x.a}->{x.b} x {y.a}->{y.b}")
        # 4) etiquetas
        pills = [(ar, ar.pill) for ar in self.arrows if ar.pill]
        for i, (ar, p) in enumerate(pills):
            for b in cajas:
                if p.hit(b.rect):
                    err.append(f"etiqueta '{ar.label}' sobre la caja {b.id}")
            for ar2, p2 in pills[i + 1:]:
                if p.hit(p2):
                    err.append(f"etiquetas solapadas '{ar.label}' y '{ar2.label}'")
            for rr, nm in self.extra_rects:
                if p.hit(rr):
                    err.append(f"etiqueta '{ar.label}' sobre '{nm}'")
            for o in self.arrows:
                if o is ar:
                    continue
                for a, b in zip(o.pts, o.pts[1:]):
                    if seg_hit_rect(a, b, p):
                        err.append(f"etiqueta '{ar.label}' sobre la flecha {o.a}->{o.b}")
        if self.nota and medir(self.nota, MIN_FONT) > W_DESIGN - 2 * MARGIN:
            err.append(f"la nota al pie excede el ancho ({medir(self.nota, MIN_FONT):.0f} px)")
        if medir(self.titulo, TITLE_FONT, 'sans', 'Bold') > W_DESIGN - 2 * MARGIN:
            err.append('titulo demasiado ancho')
        # 5) elementos extra contra cajas
        for rr, nm in self.extra_rects:
            for b in cajas:
                if rr.hit(b.rect) and not nm.startswith("llave"):
                    err.append(f"'{nm}' se solapa con la caja {b.id}")
        return err

    # ----------------------------------------------------------- salida SVG
    def _bbox(self):
        xs, ys = [], []
        for b in self.boxes.values():
            xs += [b.rect.x, b.rect.x2]
            ys += [b.rect.y, b.rect.y2]
        for rr, _ in self.extra_rects:
            xs += [rr.x, rr.x2]
            ys += [rr.y, rr.y2]
        return min(xs), max(xs), min(ys), max(ys)

    def svg(self):
        x0, x1, y0, y1 = self._bbox()
        notahpx = 0
        if self.nota:
            notahpx = 56
        H = int(math.ceil((y1 + (notahpx or 0) + MARGIN) / 20) * 20)
        self.H = H
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W_DESIGN}" height="{H}" viewBox="0 0 {W_DESIGN} {H}">',
               '<defs><marker id="pt" markerUnits="userSpaceOnUse" viewBox="0 0 16 16" refX="15" refY="8" markerWidth="16" markerHeight="16" orient="auto">'
               f'<path d="M1,2 L15,8 L1,14 Z" fill="{ARROW}"/></marker></defs>',
               f'<rect width="{W_DESIGN}" height="{H}" fill="#FFFFFF"/>',
               f'<text x="{W_DESIGN / 2}" y="68" text-anchor="middle" font-family="Inter" font-weight="700" font-size="{TITLE_FONT}" fill="{INK}">{esc(self.titulo)}</text>']
        for s in self.fuera:
            out.append(s)
        for b in self.boxes.values():
            pal = PALETA[b.color]
            r = b.rect
            sw = 4 if b.thick else 2
            dash = ' stroke-dasharray="10 7"' if b.dashed else ""
            out.append(f'<rect x="{r.x}" y="{r.y}" width="{r.w}" height="{r.h}" rx="12" ry="12" fill="{pal["fill"]}" stroke="{pal["stroke"]}" stroke-width="{sw}"{dash}/>')
            nl = len(b.lines)
            bloque = b.tsize * 1.25 + (nl * b.lsize * 1.3 + 6 if nl else 0)
            ytop = r.y + (r.h - bloque) / 2
            tx = r.x + r.w / 2 if b.align == "center" else r.x + PAD + 4
            anc = "middle" if b.align == "center" else "start"
            out.append(f'<text x="{tx}" y="{ytop + b.tsize * 0.98:.1f}" text-anchor="{anc}" font-family="Inter" font-weight="700" font-size="{b.tsize}" fill="{pal["dark"]}">{esc(b.title)}</text>')
            y = ytop + b.tsize * 1.25 + 6
            for t, k in b.lines:
                fam = "JetBrains Mono" if k == "mono" else "Inter"
                out.append(f'<text x="{tx}" y="{y + b.lsize * 0.98:.1f}" text-anchor="{anc}" font-family="{fam}" font-size="{b.lsize}" fill="{SUB}">{esc(t)}</text>')
                y += b.lsize * 1.3
            if b.num is not None:
                cx, cy = r.x, r.y
                out.append(f'<circle cx="{cx}" cy="{cy}" r="17" fill="{pal["dark"]}" stroke="#FFFFFF" stroke-width="3"/>')
                out.append(f'<text x="{cx}" y="{cy + 7.5}" text-anchor="middle" font-family="Inter" font-weight="700" font-size="22" fill="#FFFFFF">{esc(str(b.num))}</text>')
        for ar in self.arrows:
            out.append(self._trazo(ar))
        for ar in self.arrows:
            if ar.pill:
                p = ar.pill
                out.append(f'<rect x="{p.x:.1f}" y="{p.y:.1f}" width="{p.w:.1f}" height="{p.h:.1f}" rx="{p.h / 2:.1f}" fill="#FFFFFF" stroke="#9CA3AF" stroke-width="1.5"/>')
                out.append(f'<text x="{p.x + p.w / 2:.1f}" y="{p.y + p.h / 2 + 7.5:.1f}" text-anchor="middle" font-family="Inter" font-size="{MIN_FONT}" fill="{INK}">{esc(ar.label)}</text>')
        for (x, y, t, tam, kind, weight, color, anchor) in self.texts:
            fam = "JetBrains Mono" if kind == "mono" else "Inter"
            fw = "700" if weight == "Bold" else "400"
            out.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{fam}" font-weight="{fw}" font-size="{tam}" fill="{color}">{esc(t)}</text>')
        if self.nota:
            out.append(f'<text x="{W_DESIGN / 2}" y="{H - MARGIN + 6}" text-anchor="middle" font-family="Inter" font-size="{MIN_FONT}" fill="{NOTE}">{esc(self.nota)}</text>')
        out.append("</svg>")
        return "\n".join(out)

    def _trazo(self, ar):
        pts = ar.pts
        comp_a = any(o is not ar and o.a == ar.a and o.sa == ar.sa and o.fa == ar.fa for o in self.arrows)
        comp_b = any(o is not ar and o.b == ar.b and o.sb == ar.sb and o.fb == ar.fb for o in self.arrows)
        d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
        R = 12
        for i in range(1, len(pts) - 1):
            a, b, c = pts[i - 1], pts[i], pts[i + 1]
            l1 = math.hypot(b[0] - a[0], b[1] - a[1])
            l2 = math.hypot(c[0] - b[0], c[1] - b[1])
            r = min(R, l1 / 2, l2 / 2)
            if (i == 1 and comp_a) or (i == len(pts) - 2 and comp_b):
                r = 0
            p1 = (b[0] - (b[0] - a[0]) / l1 * r, b[1] - (b[1] - a[1]) / l1 * r)
            p2 = (b[0] + (c[0] - b[0]) / l2 * r, b[1] + (c[1] - b[1]) / l2 * r)
            d += f" L{p1[0]:.1f},{p1[1]:.1f} Q{b[0]:.1f},{b[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
        d += f" L{pts[-1][0]:.1f},{pts[-1][1]:.1f}"
        dash = ' stroke-dasharray="9 7"' if ar.dashed else ""
        return f'<path d="{d}" fill="none" stroke="{ar.color}" stroke-width="3"{dash} marker-end="url(#pt)"/>'

    # ----------------------------------------------------------- exportacion
    def construir(self, carpeta):
        self.enrutar_todo()
        err = self.verificar()
        # ancho util: el contenido debe aprovechar el lienzo (sin vacio lateral)
        x0, x1, y0, y1 = self._bbox()
        if x0 < MARGIN - 0.5 or x1 > W_DESIGN - MARGIN + 0.5:
            err.append(f"contenido fuera de margenes (x {x0}..{x1})")
        if (x1 - x0) < W_DESIGN - 2 * MARGIN - 80:
            err.append(f"contenido no aprovecha el ancho ({x1 - x0:.0f} px)")
        if err:
            print(f"[{self.nombre}] CHOQUES ({len(err)}):")
            for e in err:
                print("   -", e)
            return False, err
        svg = self.svg()
        base = os.path.join(carpeta, self.nombre)
        with open(base + ".svg", "w", encoding="utf8") as f:
            f.write(svg)
        subprocess.run(["rsvg-convert", "-w", str(W_DESIGN * EXPORT_SCALE), "-b", "white",
                        "-o", base + ".png", base + ".svg"], check=True)
        print(f"[{self.nombre}] OK  {W_DESIGN}x{self.H} -> {W_DESIGN * EXPORT_SCALE}x{self.H * EXPORT_SCALE}")
        return True, []
