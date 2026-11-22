# -*- coding: utf-8 -*-
"""SereOS 1.0: presentación final. Dirección visual: bloques de color plano, tipografía grande
y un hilo de pellets que recorre el deck como un laberinto de Pac-Man."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image
from pptx.oxml.ns import qn
from lxml import etree

DOC = "/home/t1an/Descargas/sereos02/documentacion"
CAP = DOC + "/capturas"
DIA = DOC + "/diagramas"
OUT = DOC + "/presentacion/Presentacion_SereOS_Nueva.pptx"

NOCHE = "0D0F16"    # fondo oscuro
PAPEL = "F4EFE3"    # crema
TINTA = "14161F"    # texto sobre claro
MENTA = "9AA3B8"    # texto secundario sobre oscuro
AMARILLO = "FFCB1F"
ROJO = "FF5B47"
CIAN = "3DDBD9"
AZUL = "2F5BFF"

TITULO = "Fira Sans Condensed"
SANS = "Inter"
MONO = "JetBrains Mono"

W, H = 13.333, 7.5
M = 0.8

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
BLANK = prs.slide_layouts[6]
TOTAL = 20
pag = {"n": 0}


def rgb(h):
    return RGBColor.from_string(h)


def lienzo(fondo):
    s = prs.slides.add_slide(BLANK)
    pag["n"] += 1
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(fondo)
    return s


def bloque(s, x, y, w, h, color, forma=MSO_SHAPE.RECTANGLE):
    r = s.shapes.add_shape(forma, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = rgb(color)
    r.line.fill.background()
    r.shadow.inherit = False
    return r


def texto(s, x, y, w, h, parrafos, size=20, color=TINTA, font=SANS, bold=False,
          align="l", anclaje="t", espacio=0, interlinea=None):
    caja = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = caja.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anclaje]
    if isinstance(parrafos, str):
        parrafos = [parrafos]
    for i, p_txt in enumerate(parrafos):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        if i > 0:
            p.space_before = Pt(espacio)
        if interlinea:
            p.line_spacing = interlinea
        r = p.add_run()
        r.text = p_txt
        r.font.size = Pt(size)
        r.font.color.rgb = rgb(color)
        r.font.name = font
        r.font.bold = bold
    return caja


def pellets(s, x, y, n, paso, color, radio=0.07, vertical=False):
    for i in range(n):
        cx = x + (0 if vertical else i * paso)
        cy = y + (i * paso if vertical else 0)
        bloque(s, cx, cy, radio * 2, radio * 2, color, MSO_SHAPE.OVAL)


def pacman(s, x, y, d, color=AMARILLO, boca=90):
    """Pac-Man con la boca abierta hacia la derecha; boca en grados."""
    p = s.shapes.add_shape(MSO_SHAPE.PIE, Inches(x), Inches(y), Inches(d), Inches(d))
    p.fill.solid()
    p.fill.fore_color.rgb = rgb(color)
    p.line.fill.background()
    p.shadow.inherit = False
    # OOXML: ángulos en 1/60000 de grado; python-pptx divide entre 100000
    ini = (boca / 2) * 60000 / 100000
    fin = (360 - boca / 2) * 60000 / 100000
    p.adjustments[0] = ini
    p.adjustments[1] = fin
    return p


def foto(s, ruta, x, y, w=None, h=None, marco=None):
    iw, ih = Image.open(ruta).size
    esc = min(w / iw, h / ih) if (w and h) else (w / iw if w else h / ih)
    pw, ph = iw * esc, ih * esc
    px = x + (w - pw) / 2 if w else x
    py = y + (h - ph) / 2 if h else y
    if marco:
        m = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(px - 0.07), Inches(py - 0.07),
                               Inches(pw + 0.14), Inches(ph + 0.14))
        m.fill.solid()
        m.fill.fore_color.rgb = rgb(marco)
        m.line.fill.background()
        m.shadow.inherit = False
        m.adjustments[0] = 0.06
    pic = s.shapes.add_picture(ruta, Inches(px), Inches(py), Inches(pw), Inches(ph))
    pic.auto_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE
    av = pic._element.spPr.find(qn("a:prstGeom")).find(qn("a:avLst"))
    for g in list(av):
        av.remove(g)
    gd = etree.SubElement(av, qn("a:gd"))
    gd.set("name", "adj")
    gd.set("fmla", "val 3500")
    return px, py, pw, ph


VERDE = "2BB673"
BLANCO = "FFFFFF"


def _rect(s, x, y, w, h, color, forma_=MSO_SHAPE.RECTANGLE):
    return bloque(s, x, y, w, h, color, forma_)


def fantasma(s, x, y, d, color):
    """Fantasma de PAC-MAN: cuerpo redondeado, falda en zigzag y ojos."""
    cuerpo = s.shapes.add_shape(MSO_SHAPE.ROUND_2_SAME_RECTANGLE, Inches(x), Inches(y),
                                Inches(d), Inches(d * 0.82))
    cuerpo.fill.solid(); cuerpo.fill.fore_color.rgb = rgb(color)
    cuerpo.line.fill.background(); cuerpo.shadow.inherit = False
    cuerpo.adjustments[0] = 0.5
    cuerpo.adjustments[1] = 0.0
    for i in range(3):
        t = s.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(x + i * d / 3), Inches(y + d * 0.74),
                               Inches(d / 3), Inches(d * 0.26))
        t.rotation = 180
        t.fill.solid(); t.fill.fore_color.rgb = rgb(color)
        t.line.fill.background(); t.shadow.inherit = False
    for ox in (0.24, 0.56):
        bloque(s, x + ox * d, y + d * 0.26, d * 0.2, d * 0.24, BLANCO, MSO_SHAPE.OVAL)
        bloque(s, x + (ox + 0.07) * d, y + d * 0.34, d * 0.1, d * 0.12, TINTA, MSO_SHAPE.OVAL)


def chip(s, x, y, d, color):
    """Procesador: cuerpo cuadrado, núcleo y patas."""
    for i in range(4):
        off = 0.12 + i * 0.24
        _rect(s, x + off * d, y - d * 0.08, d * 0.08, d * 0.1, color)
        _rect(s, x + off * d, y + d * 0.98, d * 0.08, d * 0.1, color)
        _rect(s, x - d * 0.08, y + off * d, d * 0.1, d * 0.08, color)
        _rect(s, x + d * 0.98, y + off * d, d * 0.1, d * 0.08, color)
    c = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(d), Inches(d))
    c.fill.solid(); c.fill.fore_color.rgb = rgb(color); c.line.fill.background(); c.shadow.inherit = False
    c.adjustments[0] = 0.12
    bloque(s, x + d * 0.28, y + d * 0.28, d * 0.44, d * 0.44, PAPEL, MSO_SHAPE.ROUNDED_RECTANGLE)


def ventana(s, x, y, w, h, color):
    """Icono de ventana con barra de título y tres botones."""
    v = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    v.fill.solid(); v.fill.fore_color.rgb = rgb(PAPEL); v.line.color.rgb = rgb(color); v.line.width = Pt(2.5)
    v.shadow.inherit = False; v.adjustments[0] = 0.1
    bloque(s, x + 0.04, y + 0.04, w - 0.08, h * 0.2, color, MSO_SHAPE.ROUNDED_RECTANGLE)
    for i in range(3):
        bloque(s, x + 0.12 + i * 0.13, y + h * 0.1 - 0.03, 0.06, 0.06, PAPEL, MSO_SHAPE.OVAL)


def terminal_icono(s, x, y, w, h, color):
    v = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    v.fill.solid(); v.fill.fore_color.rgb = rgb(TINTA); v.line.color.rgb = rgb(color); v.line.width = Pt(2)
    v.shadow.inherit = False; v.adjustments[0] = 0.12
    t = texto(s, x + 0.12, y + h * 0.3, w - 0.2, h * 0.5, "$_", size=max(8, int(w * 14)), color=color, font=MONO,
              bold=True)


def ram(s, x, y, w, h, color):
    _rect(s, x, y, w, h, color, MSO_SHAPE.ROUNDED_RECTANGLE)
    for i in range(6):
        _rect(s, x + 0.1 + i * (w - 0.2) / 6, y + h - 0.12, (w - 0.2) / 6 - 0.06, 0.07, PAPEL)
    _rect(s, x + w * 0.2, y + 0.12, w * 0.6, h * 0.35, PAPEL, MSO_SHAPE.ROUNDED_RECTANGLE)


def potencia(s, x, y, d, color):
    r = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    r.fill.background(); r.line.color.rgb = rgb(color); r.line.width = Pt(4); r.shadow.inherit = False
    _rect(s, x + d * 0.46, y - d * 0.12, d * 0.08, d * 0.5, color, MSO_SHAPE.ROUNDED_RECTANGLE)


def cereza(s, x, y, d, color):
    bloque(s, x, y + d * 0.45, d * 0.5, d * 0.5, color, MSO_SHAPE.OVAL)
    bloque(s, x + d * 0.5, y + d * 0.45, d * 0.5, d * 0.5, color, MSO_SHAPE.OVAL)
    _rect(s, x + d * 0.22, y, d * 0.05, d * 0.5, VERDE)
    _rect(s, x + d * 0.7, y, d * 0.05, d * 0.5, VERDE)


def pared(s, x, y, w, h, color):
    r = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.background(); r.line.color.rgb = rgb(color); r.line.width = Pt(3); r.shadow.inherit = False
    r.adjustments[0] = 0.5


def forma(s, tipo, x, y, w, h, color):
    """Elementos gráficos: formas básicas, íconos de sistema y de PAC-MAN."""
    if tipo == "circulo":
        return bloque(s, x, y, w, h, color, MSO_SHAPE.OVAL)
    if tipo == "pildora":
        r = bloque(s, x, y, w, h, color, MSO_SHAPE.ROUNDED_RECTANGLE)
        r.adjustments[0] = 0.5
        return r
    if tipo == "cruz":
        return bloque(s, x, y, w, h, color, MSO_SHAPE.CROSS)
    if tipo == "estrella":
        return bloque(s, x, y, w, h, color, MSO_SHAPE.STAR_4_POINT)
    if tipo == "anillo":
        r = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(w), Inches(h))
        r.fill.background(); r.line.color.rgb = rgb(color); r.line.width = Pt(4); r.shadow.inherit = False
        return r
    if tipo == "fantasma":
        return fantasma(s, x, y, w, color)
    if tipo == "chip":
        return chip(s, x, y, w, color)
    if tipo == "ventana":
        return ventana(s, x, y, w, h, color)
    if tipo == "terminal":
        return terminal_icono(s, x, y, w, h, color)
    if tipo == "ram":
        return ram(s, x, y, w, h, color)
    if tipo == "engranaje":
        return bloque(s, x, y, w, h, color, MSO_SHAPE.GEAR_6)
    if tipo == "carpeta":
        bloque(s, x, y, w * 0.4, h * 0.18, color, MSO_SHAPE.ROUNDED_RECTANGLE)
        r = bloque(s, x, y + h * 0.12, w, h * 0.88, color, MSO_SHAPE.ROUNDED_RECTANGLE)
        r.adjustments[0] = 0.08
        return r
    if tipo == "disco":
        return bloque(s, x, y, w, h, color, MSO_SHAPE.CAN)
    if tipo == "rayo":
        return bloque(s, x, y, w, h, color, MSO_SHAPE.LIGHTNING_BOLT)
    if tipo == "potencia":
        return potencia(s, x, y, w, color)
    if tipo == "alerta":
        t = bloque(s, x, y, w, h * 0.9, color, MSO_SHAPE.ISOSCELES_TRIANGLE)
        texto(s, x, y + h * 0.28, w, h * 0.5, "!", size=int(w * 40), color=BLANCO, font=TITULO, bold=True,
              align="c")
        return t
    if tipo == "pellet":
        return bloque(s, x, y, w, h, color, MSO_SHAPE.OVAL)
    if tipo == "pastilla":
        return bloque(s, x, y, w, h, color, MSO_SHAPE.OVAL)
    if tipo == "cereza":
        return cereza(s, x, y, w, color)
    if tipo == "pared":
        return pared(s, x, y, w, h, color)
    if tipo == "pacman":
        return pacman(s, x, y, w, color, boca=80)


DECOR = {
    1: [("fantasma", 6.5, 0.45, 0.7, 0, ROJO), ("anillo", 6.9, 6.7, 0.35, 0.35, AMARILLO),
        ("pildora", 12.0, 4.6, 0.8, 0.28, CIAN), ("fantasma", 11.0, 4.6, 0.6, 0, CIAN),
        ("pellet", 7.6, 6.9, 0.1, 0.1, PAPEL)],
    2: [("ventana", 11.5, 0.45, 1.3, 0.95, AZUL), ("circulo", 10.2, 4.6, 2.1, 2.1, AZUL),
        ("anillo", 9.4, 6.3, 0.4, 0.4, TINTA)],
    3: [("chip", 11.2, 1.2, 1.2, 0, AMARILLO), ("circulo", 11.9, 5.2, 0.6, 0.6, CIAN),
        ("ram", 10.2, 6.1, 1.2, 0.45, CIAN)],
    4: [("pildora", 0.8, 6.25, 1.7, 0.36, AZUL), ("pildora", 2.7, 6.25, 1.4, 0.36, AMARILLO),
        ("engranaje", 5.0, 0.4, 0.55, 0.55, AZUL)],
    5: [("potencia", 12.0, 0.6, 0.6, 0, TINTA), ("anillo", 6.7, 6.25, 0.5, 0.5, TINTA),
        ("carpeta", 10.7, 0.5, 0.8, 0.65, TINTA)],
    6: [("rayo", 11.9, 0.4, 0.5, 0.75, ROJO), ("circulo", 5.6, 0.55, 0.35, 0.35, AMARILLO)],
    7: [("ram", 11.2, 0.6, 1.5, 0.6, AZUL), ("pildora", 0.8, 6.3, 1.3, 0.3, TINTA),
        ("anillo", 5.2, 0.6, 0.4, 0.4, AZUL)],
    8: [("ventana", 3.6, 0.35, 0.9, 0.65, AMARILLO), ("ventana", 3.2, 6.35, 0.8, 0.6, PAPEL),
        ("circulo", 3.5, 6.5, 0.4, 0.4, AMARILLO)],
    9: [("pildora", 0.8, 6.3, 1.6, 0.32, AZUL), ("carpeta", 4.5, 0.35, 0.7, 0.55, AZUL)],
    10: [("pildora", 4.6, 0.55, 1.2, 0.3, AMARILLO), ("terminal", 11.5, 0.12, 1.1, 0.7, AZUL)],
    11: [("anillo", 0.8, 6.35, 0.4, 0.4, MENTA), ("engranaje", 12.0, 0.4, 0.5, 0.5, AMARILLO),
         ("disco", 11.9, 6.2, 0.6, 0.7, MENTA)],
    12: [("fantasma", 11.9, 0.3, 0.7, 0, ROJO), ("fantasma", 12.5, 0.3, 0.7, 0, CIAN),
         ("fantasma", 12.25, 6.1, 0.65, 0, AZUL), ("pildora", 10.6, 6.3, 1.5, 0.3, PAPEL),
         ("pared", 0.5, 6.7, 0.6, 0.12, AZUL)],
    13: [("fantasma", 10.9, 0.4, 0.6, 0, ROJO), ("fantasma", 11.7, 0.4, 0.6, 0, CIAN),
         ("fantasma", 12.5, 0.4, 0.6, 0, "FFB8DE"), ("pastilla", 12.2, 6.2, 0.45, 0.45, TINTA),
         ("pared", 5.5, 6.3, 1.4, 0.4, AZUL)],
    14: [("alerta", 12.0, 0.3, 0.75, 0.75, ROJO)],
    15: [("chip", 11.8, 0.6, 0.9, 0, AZUL), ("circulo", 12.4, 6.3, 0.5, 0.5, ROJO)],
    16: [("disco", 12.0, 0.35, 0.8, 0.95, CIAN), ("anillo", 0.8, 6.4, 0.4, 0.4, AMARILLO)],
    17: [("engranaje", 12.0, 0.35, 0.6, 0.6, AZUL), ("pildora", 0.8, 6.35, 1.4, 0.32, AMARILLO)],
    18: [("alerta", 12.0, 0.4, 0.7, 0.7, AMARILLO), ("estrella", 12.2, 6.3, 0.35, 0.35, AMARILLO)],
    19: [("pildora", 0.8, 6.4, 1.5, 0.3, AMARILLO), ("potencia", 12.1, 0.5, 0.55, 0, AZUL)],
    20: [("fantasma", 10.9, 0.5, 1.0, 0, ROJO), ("fantasma", 12.0, 0.5, 1.0, 0, CIAN),
         ("anillo", 11.6, 5.6, 0.8, 0.8, TINTA)],
}


def decor(s):
    for tipo, x, y, w, h, c in DECOR.get(pag["n"], []):
        forma(s, tipo, x, y, w, h, c)


def pie(s, oscuro=False):
    decor(s)


def notas(s, txt):
    s.notes_slide.notes_text_frame.text = txt


def titular(s, x, y, w, h, txt, size=54, color=TINTA, oscuro=False):
    return texto(s, x, y, w, h, txt, size=size, color=color, font=TITULO, bold=True, interlinea=0.95)


def galeria(s, items, x0, y0, cw, ch, gx, gy, color_txt):
    """Cuadrícula 2x2 de capturas con pie de foto. Cada celda cw x ch (4:3)."""
    for i, (ruta, lab) in enumerate(items):
        col, fila = i % 2, i // 2
        x = x0 + col * (cw + gx)
        y = y0 + fila * (ch + gy + 0.3)
        foto(s, ruta, x, y, w=cw, h=ch, marco=color_txt)
        texto(s, x, y + ch + 0.12, cw, 0.3, lab, size=12, color=color_txt, font=MONO)


# 01 Portada -------------------------------------------------------------------
s = lienzo(NOCHE)
texto(s, M, 0.7, 6, 0.3, "PROYECTO FINAL DE SISTEMAS OPERATIVOS", size=12, color=MENTA, font=MONO)
texto(s, M - 0.05, 1.45, 8.5, 2.6, "SereOS", size=150, color=AMARILLO, font=TITULO, bold=True,
      interlinea=0.85)
texto(s, M, 4.15, 5.4, 1.1, "Un sistema operativo x86 de 32 bits que arranca, dibuja ventanas y se juega.",
      size=22, color=PAPEL, interlinea=1.2)
pellets(s, M, 5.55, 9, 0.42, AMARILLO, radio=0.06)
pacman(s, M + 8.6, 5.25, 0.55)
texto(s, M, 6.25, 5.5, 0.9, [
    "Miguel Eduardo Angulo Cantor",
    "Karol Asley Orjuela Mape",
    "Juan David Gómez Rojas",
    "Sebastián Fernando Revelo Meneses"], size=13, color=PAPEL, espacio=0)
texto(s, 7.5, 6.25, 5.0, 0.3, "Universidad Manuela Beltrán", size=13, color=MENTA, align="r")
texto(s, 7.5, 6.55, 5.0, 0.3, "Noviembre de 2026", size=13, color=MENTA, align="r")
foto(s, CAP + "/02_escritorio/escritorio_principal.png", 8.4, 0.75, w=4.15, h=3.6, marco=AMARILLO)
decor(s)
notas(s, "Presentamos SereOS, un sistema operativo propio para i686 con escritorio gráfico y un juego integrado. "
         "Todo se compiló desde cero y se probó en Oracle VM VirtualBox.")

# 02 Pregunta ------------------------------------------------------------------
s = lienzo(PAPEL)
texto(s, M, 0.7, 6, 0.3, "EL PROBLEMA", size=12, color="5C6275", font=MONO)
texto(s, M, 1.4, 11.6, 3.6, "¿Qué pasa entre GRUB y la primera ventana?", size=72,
      color=TINTA, font=TITULO, bold=True, interlinea=0.95)
bloque(s, M, 4.55, 4.9, 0.5, AMARILLO)
texto(s, M + 0.15, 4.6, 5, 0.4, "Construir el camino completo", size=20, color=TINTA, bold=True)
texto(s, M, 5.45, 7.4, 1.2,
      "Escribimos el arranque, el kernel, el dibujo de ventanas y un juego. Lo probamos en VirtualBox "
      "para no quedarnos con la teoría.", size=18, color="3A3F4F", interlinea=1.25)
pellets(s, M, 6.7, 12, 0.36, "B9B2A0", radio=0.035)
pie(s)
notas(s, "El planteamiento es responder qué ocurre desde que el gestor de arranque entrega el control hasta que "
         "aparece una interfaz usable. El objetivo fue recorrer ese camino completo, no solo estudiarlo.")

# 03 Cifras -------------------------------------------------------------------
s = lienzo(NOCHE)
texto(s, M, 0.7, 6, 0.3, "SEREOS 1.0 EN NÚMEROS", size=12, color=MENTA, font=MONO)
titular(s, M, 1.1, 11, 1.2, "Un kernel monolítico para i686", size=44, color=PAPEL)
filas = [("7", "capas de arquitectura", AMARILLO),
         ("23", "pasos de inicialización en kernel_main", PAPEL),
         ("25", "comandos en la shell", PAPEL),
         ("35,1", "MiB de imagen ISO", CIAN)]
for i, (num, lab, col) in enumerate(filas):
    y = 2.55 + i * 1.1
    texto(s, M, y, 3.6, 1.0, num, size=72, color=col, font=TITULO, bold=True, anclaje="m")
    texto(s, M + 3.9, y, 7, 1.0, lab, size=24, color=PAPEL, anclaje="m")
    bloque(s, M, y + 1.02, 11.7, 0.01, "2A2E3B")
pie(s, oscuro=True)
notas(s, "SereOS es un kernel monolítico que se ejecuta íntegramente en anillo 0. Estas cifras resumen el alcance real.")

# 04 Arquitectura --------------------------------------------------------------
s = lienzo(PAPEL)
texto(s, M, 0.7, 6, 0.3, "ARQUITECTURA", size=12, color="5C6275", font=MONO)
titular(s, M, 1.1, 4.8, 3.0, "Siete capas que solo miran hacia abajo", size=40)
texto(s, M, 3.7, 4.4, 2.2,
      "Cada capa llama a la de abajo, desde el hardware hasta las aplicaciones. Las aplicaciones "
      "no tienen privilegios propios: comparten el anillo 0 con el kernel.", size=17, color="3A3F4F", interlinea=1.3)
foto(s, DIA + "/d1_arquitectura_capas.png", 5.7, 0.6, w=7.0, h=6.3)
pie(s)
notas(s, "Leemos el diagrama de abajo hacia arriba. No hay separación de privilegios entre aplicaciones y kernel.")

# 05 Arranque -----------------------------------------------------------------
s = lienzo(AMARILLO)
texto(s, M, 0.7, 6, 0.3, "ARRANQUE", size=12, color=TINTA, font=MONO, bold=True)
titular(s, M, 1.05, 11, 1.0, "Del menú de GRUB al escritorio", size=44)
foto(s, DIA + "/d2_arranque.png", M, 2.25, h=4.7)
foto(s, CAP + "/01_arranque/grub_menu.png", 8.6, 2.3, w=3.95, marco=TINTA)
texto(s, 8.6, 4.2, 3.95, 0.3, "Menú de GRUB en VirtualBox", size=12, color=TINTA, font=MONO)
texto(s, 8.6, 4.85, 4.0, 2.0, [
    "kernel_main ejecuta 23 pasos en orden.",
    "Sin framebuffer, el sistema cae a la consola de texto."], size=17, color=TINTA, espacio=12, interlinea=1.25)
pie(s)
notas(s, "GRUB carga la imagen Multiboot y salta a boot.s, que prepara la pila y llama a kernel_main. "
         "Si no hay framebuffer, el sistema arranca en modo texto.")

# 06 Interrupciones -----------------------------------------------------------
s = lienzo(NOCHE)
texto(s, M, 0.7, 6, 0.3, "NÚCLEO", size=12, color=MENTA, font=MONO)
texto(s, M - 0.05, 1.1, 5.6, 2.2, "100", size=170, color=AMARILLO, font=TITULO, bold=True, interlinea=0.85)
texto(s, M, 3.35, 5, 0.5, "interrupciones por segundo del PIT", size=22, color=PAPEL)
texto(s, M, 4.15, 4.6, 2.2, [
    "El PIC remapeado lleva las IRQ a los vectores 32 a 47.",
    "En VirtualBox, 3 439 ticks tras 34 segundos."], size=17, color=MENTA, espacio=12, interlinea=1.3)
foto(s, DIA + "/d3_interrupciones.png", 6.3, 1.0, w=6.2, h=5.6, marco=None)
pie(s, oscuro=True)
notas(s, "Una interrupción pasa por isr.s hasta interrupt_handler. Si el vector es menor que 32 es una excepción "
         "y el sistema entra en pantalla de error.")

# 07 Memoria ------------------------------------------------------------------
s = lienzo(PAPEL)
texto(s, M, 0.7, 6, 0.3, "MEMORIA", size=12, color="5C6275", font=MONO)
texto(s, M - 0.05, 1.1, 6, 2.0, "512", size=170, color=AZUL, font=TITULO, bold=True, interlinea=0.85)
texto(s, M, 3.35, 5, 0.5, "MiB con identidad y páginas PSE", size=22, color=TINTA)
texto(s, M, 4.2, 4.8, 2.0, [
    "La dirección virtual es igual a la física, con páginas de 4 MiB.",
    "El heap del kernel tiene 8 MiB para kmalloc."], size=17, color="3A3F4F", espacio=12, interlinea=1.3)
foto(s, DIA + "/d4_mapa_memoria.png", 6.4, 0.7, w=6.2, h=6.1)
pie(s)
notas(s, "La paginación de identidad permite mapear 512 MiB con páginas grandes. El framebuffer que entrega GRUB "
         "cae dentro de esa ventana.")

# 08 Ventanas (captura a sangre) ----------------------------------------------
s = lienzo(NOCHE)
bloque(s, 0, 0, 4.6, H, AZUL)
texto(s, M, 0.7, 4, 0.3, "ENTORNO GRÁFICO", size=12, color=PAPEL, font=MONO)
titular(s, M, 1.1, 3.8, 3.4, "Varias ventanas, un solo buffer", size=40, color=PAPEL)
texto(s, M, 4.1, 3.4, 2.2,
      "El compositor dibuja en memoria y copia al framebuffer solo las regiones que cambiaron.",
      size=17, color=PAPEL, interlinea=1.3)
s.shapes.add_picture(CAP + "/04_aplicaciones/multiventana.png", Inches(4.9), Inches(0), Inches(8.433), Inches(H))
pie(s, oscuro=True)
notas(s, "La captura muestra terminal y otra aplicación abiertas a la vez, en VirtualBox.")

# A Escritorio y aplicaciones (galería 2x2) -----------------------------------
s = lienzo(PAPEL)
texto(s, M, 0.7, 6, 0.3, "ESCRITORIO", size=12, color="5C6275", font=MONO)
titular(s, M, 1.1, 3.9, 2.4, "Las apps que vienen con SereOS", size=40)
texto(s, M, 3.7, 3.7, 2.4, "Un menú de inicio, un explorador de archivos, un monitor del sistema "
      "y la ventana Acerca de. Todas comparten el mismo compositor.", size=17, color="3A3F4F", interlinea=1.3)
galeria(s, [(CAP + "/02_escritorio/qemu_menu_launcher.png", "Menú de inicio"),
            (CAP + "/04_aplicaciones/explorador_archivos.png", "Explorador de archivos"),
            (CAP + "/04_aplicaciones/monitor_sistema.png", "Monitor del sistema"),
            (CAP + "/04_aplicaciones/acerca_de.png", "Acerca de")], 5.3, 0.9, 3.33, 2.5, 0.35, 0.5, TINTA)
pie(s)
notas(s, "Todas las aplicaciones son ventanas del mismo compositor. Las capturas son de VirtualBox.")

# 09 Terminal -----------------------------------------------------------------
s = lienzo(PAPEL)
texto(s, M, 0.7, 6, 0.3, "TERMINAL", size=12, color="5C6275", font=MONO)
titular(s, M, 1.1, 5, 1.6, "Una shell de 25 comandos", size=40)
bloque(s, M, 2.85, 4.9, 2.55, TINTA)
texto(s, M + 0.35, 3.1, 4.4, 2.2, [
    "$ help",
    "  lista los comandos",
    "$ sysinfo",
    "  resumen del sistema",
    "$ div0",
    "  división por cero"], size=15, color=PAPEL, font=MONO, interlinea=1.3)
texto(s, M, 5.7, 4.8, 1.0, "La misma shell atiende la ventana gráfica y la consola VGA de respaldo.",
      size=17, color="3A3F4F", interlinea=1.3)
foto(s, CAP + "/03_terminal/cmd_sysinfo_version.png", 6.2, 0.9, w=6.3, h=5.4, marco=TINTA)
pie(s)
notas(s, "La shell se comparte entre la terminal gráfica y la consola de texto. div0 sirve para probar la IDT.")

# B Comandos de la terminal (galería 2x2) ------------------------------------
s = lienzo(NOCHE)
texto(s, M, 0.7, 6, 0.3, "TERMINAL", size=12, color=MENTA, font=MONO)
titular(s, M, 1.1, 3.9, 2.4, "Cuatro comandos en acción", size=40, color=PAPEL)
texto(s, M, 3.7, 3.7, 2.4, "help lista lo disponible, dmesg muestra el registro del arranque, "
      "free y date dan memoria y hora, y audio prueba la SB16.", size=17, color=MENTA, interlinea=1.3)
galeria(s, [(CAP + "/03_terminal/cmd_help.png", "help"),
            (CAP + "/03_terminal/cmd_dmesg.png", "dmesg"),
            (CAP + "/03_terminal/cmd_mem_free_ticks_date.png", "free, ticks y date"),
            (CAP + "/03_terminal/cmd_audio_echo_about.png", "audio, echo y about")], 5.3, 0.9, 3.33, 2.5, 0.35, 0.5, MENTA)
pie(s, oscuro=True)
notas(s, "Las salidas son reales, tomadas en VirtualBox. dmesg reproduce el registro de inicialización del kernel.")

# 10 PAC-MAN ------------------------------------------------------------------
s = lienzo(AMARILLO)
foto(s, CAP + "/05_pacman_sereos_vbox/05_partida_dots_fantasmas.png", M, 0.9, w=6.0, h=5.1, marco=TINTA)
texto(s, M, 6.25, 6, 0.3, "Partida en VirtualBox", size=12, color=TINTA, font=MONO)
texto(s, 7.3, 1.0, 5.3, 1.0, "PAC-MAN SereOS", size=48, color=TINTA, font=TITULO, bold=True)
texto(s, 7.3, 2.2, 5.1, 2.8, [
    "El juego se compila como libpacman.a y el kernel lo ejecuta como una aplicación más.",
    "Tiene su propio Makefile, pruebas y un contrato de plataforma."], size=19, color=TINTA, espacio=16,
    interlinea=1.3)
pacman(s, 7.3, 5.2, 1.0, color=TINTA, boca=80)
pellets(s, 8.7, 5.7, 4, 0.5, TINTA, radio=0.06)
pie(s)
notas(s, "PAC-MAN SereOS se compila como biblioteca y el kernel la ejecuta como una aplicación más.")

# D PAC-MAN: pantallas del juego --------------------------------------------------
s = lienzo(AMARILLO)
texto(s, M, 0.7, 6, 0.3, "PAC-MAN SEREOS", size=12, color=TINTA, font=MONO, bold=True)
titular(s, M, 1.1, 11, 1.0, "De la portada al fin de partida", size=40)
trio = [(CAP + "/05_pacman_sereos_vbox/02_attract.png", "Pantalla de inicio"),
        (CAP + "/05_pacman_sereos_vbox/03_menu_principal.png", "Menú principal"),
        (CAP + "/05_pacman_sereos_vbox/12_game_over.png", "Fin de partida")]
for i, (ruta, lab) in enumerate(trio):
    x = M + i * 4.0
    foto(s, ruta, x, 2.3, w=3.8, h=2.85, marco=TINTA)
    texto(s, x, 5.35, 3.8, 0.3, lab, size=14, color=TINTA, font=MONO)
pie(s)
notas(s, "El juego pasa por las mismas pantallas en VirtualBox: inicio, menú, partida y fin de partida.")

# C Errores y modo texto --------------------------------------------------------
s = lienzo(PAPEL)
texto(s, M, 0.7, 6, 0.3, "ERRORES Y MODO TEXTO", size=12, color="5C6275", font=MONO)
titular(s, M, 1.1, 11, 1.0, "Cuando algo falla, se ve en pantalla", size=40)
foto(s, CAP + "/03_terminal/panico_div0.png", M, 2.3, w=5.7, h=3.95, marco=ROJO)
texto(s, M, 6.45, 5.7, 0.3, "Pánico por división entre cero (div0)", size=12, color="5C6275", font=MONO)
foto(s, CAP + "/03_terminal/modo_texto_sysinfo.png", 6.85, 2.3, w=5.7, h=3.95, marco=TINTA)
texto(s, 6.85, 6.45, 5.7, 0.3, "Modo texto con sysinfo, sin framebuffer", size=12, color="5C6275", font=MONO)
pie(s)
notas(s, "El pánico se activa desde la shell con div0 y muestra los registros del momento del fallo. El modo texto "
         "aparece cuando GRUB no entrega un framebuffer.")

# 11 Dos plataformas ----------------------------------------------------------
s = lienzo(PAPEL)
texto(s, M, 0.7, 6, 0.3, "EL JUEGO", size=12, color="5C6275", font=MONO)
titular(s, M, 1.1, 11, 1.0, "Una lógica, dos plataformas", size=40)
foto(s, DIA + "/d5_arquitectura_juego.png", M, 2.2, h=4.6)
texto(s, 8.4, 2.4, 4.2, 3.8, [
    "El núcleo y el render no conocen SereOS ni SDL.",
    "El contrato pac_platform.h lo implementan SereOS y Linux.",
    "Linux se usa solo para probar el juego en desarrollo."], size=18, color=TINTA, espacio=18, interlinea=1.3)
pacman(s, 8.4, 5.9, 0.6, color=AMARILLO, boca=70)
pie(s)
notas(s, "El juego tiene una lógica común y dos adaptadores: uno para Linux con SDL2 y otro para SereOS.")

# 12 ISO ----------------------------------------------------------------------
s = lienzo(NOCHE)
texto(s, M, 0.7, 6, 0.3, "CONSTRUCCIÓN", size=12, color=MENTA, font=MONO)
foto(s, DIA + "/d6_pipeline_iso.png", M, 1.4, w=8.1)
texto(s, 9.4, 1.5, 3.4, 1.4, "35,1", size=110, color=AMARILLO, font=TITULO, bold=True, interlinea=0.85)
texto(s, 9.4, 3.0, 3.4, 0.5, "MiB de sereos.iso", size=20, color=PAPEL)
texto(s, 9.4, 3.8, 3.4, 2.5, [
    "36 835 328 bytes.",
    "Ocho pasos con make. El arranque en VirtualBox sigue siendo manual."],
    size=17, color=MENTA, espacio=12, interlinea=1.3)
pie(s, oscuro=True)
notas(s, "El Makefile compila el kernel con gcc -m32 y nasm, enlaza el juego como libpacman.a y genera la ISO "
         "con grub-mkrescue.")

# 13 Pruebas -----------------------------------------------------------------
s = lienzo(PAPEL)
texto(s, M, 0.7, 6, 0.3, "PRUEBAS", size=12, color="5C6275", font=MONO)
titular(s, M, 1.1, 11, 1.0, "Qué verificamos y dónde", size=40)
pruebas = [("24", "pruebas en VirtualBox"),
           ("209", "comprobaciones de make test del juego"),
           ("2", "pruebas de ratón en QEMU con la misma ISO")]
for i, (num, lab) in enumerate(pruebas):
    y = 2.45 + i * 1.05
    texto(s, M, y, 2.2, 0.95, num, size=60, color=AZUL if i == 0 else TINTA, font=TITULO, bold=True, anclaje="m")
    texto(s, M + 2.5, y, 6.2, 0.95, lab, size=20, color=TINTA, anclaje="m", interlinea=1.15)
bloque(s, 9.5, 2.45, 3.0, 3.05, TINTA)
texto(s, 9.75, 2.7, 2.6, 2.7, [
    "[OK] paginación",
    "identidad, PSE 4 MiB",
    "",
    "[OK] planificador",
    "round-robin listo"], size=14, color=PAPEL, font=MONO, interlinea=1.35)
texto(s, 9.5, 5.6, 3.0, 0.6, "Salida del puerto serie en VirtualBox", size=12, color="5C6275", interlinea=1.2)
pie(s)
notas(s, "El arnés automático de QEMU no se repitió, así que no presentamos sus resultados como propios.")

# 14 Limitaciones -------------------------------------------------------------
s = lienzo(NOCHE)
texto(s, M, 0.7, 6, 0.3, "LIMITACIONES", size=12, color=MENTA, font=MONO)
titular(s, M, 1.1, 11, 1.0, "Lo que no probamos ni hicimos", size=40, color=PAPEL)
for i, (titulo, items, col) in enumerate([
        ("No probado", ["Sonido audible de la SB16", "Apagado y reinicio", "Redimensionado de ventanas",
                        "Hardware físico"], AMARILLO),
        ("No implementado", ["Multitarea preemptiva y anillo 3", "Llamadas al sistema",
                             "Disco, red, USB y UEFI"], ROJO)]):
    x = M + i * 6.0
    bloque(s, x, 2.5, 0.1, 3.7, col)
    texto(s, x + 0.45, 2.45, 5, 0.5, titulo, size=28, color=col, font=TITULO, bold=True)
    texto(s, x + 0.45, 3.15, 5.0, 3.0, items, size=20, color=PAPEL, espacio=12, interlinea=1.2)
texto(s, M, 6.2, 11.5, 0.5,
      "El planificador es cooperativo: una tarea que no cede el control congela el escritorio.",
      size=16, color=MENTA)
pie(s, oscuro=True)
notas(s, "Los pendientes son parte del resultado. Tampoco se probó en hardware real.")

# 15 Conclusiones -------------------------------------------------------------
s = lienzo(PAPEL)
texto(s, M, 0.7, 6, 0.3, "CONCLUSIONES", size=12, color="5C6275", font=MONO)
concl = ["El orden de arranque y el remapeo del PIC se ven en pantalla.",
         "Separar la lógica del juego de su plataforma permite correrlo en dos sistemas.",
         "La evidencia decide qué afirmamos, no lo que creíamos antes."]
for i, c in enumerate(concl):
    y = 1.5 + i * 1.75
    texto(s, M, y, 1.2, 1.2, f"{i + 1}", size=80, color=AZUL, font=TITULO, bold=True)
    texto(s, M + 1.6, y + 0.15, 10.2, 1.3, c, size=30, color=TINTA, font=TITULO, bold=True, interlinea=1.05)
pie(s)
notas(s, "Insistimos en que la verificación con evidencia es la que decide qué afirmamos.")

# 16 Cierre -------------------------------------------------------------------
s = lienzo(AMARILLO)
texto(s, M - 0.05, 0.9, 11, 2.2, "¿Preguntas?", size=130, color=TINTA, font=TITULO, bold=True, interlinea=0.85)
pellets(s, M, 3.85, 13, 0.55, TINTA, radio=0.07)
pacman(s, M + 0.1, 4.85, 1.2, color=TINTA, boca=80)
texto(s, M + 1.7, 4.95, 10, 1.2, [
    "Miguel Eduardo Angulo Cantor",
    "Karol Asley Orjuela Mape",
    "Juan David Gómez Rojas",
    "Sebastián Fernando Revelo Meneses"], size=18, color=TINTA, espacio=2)
decor(s)
notas(s, "Agradecemos la atención. Estamos listos para preguntas sobre el arranque, el kernel o el juego.")

prs.save(OUT)
print("guardado", OUT, "diapositivas", len(prs.slides))
