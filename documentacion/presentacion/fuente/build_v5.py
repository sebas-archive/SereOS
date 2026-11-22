# -*- coding: utf-8 -*-
"""SereOS 1.0: presentación final con tarjetas redondeadas, imágenes redondeadas
e iconos de línea (Lucide, ver recursos/CREDITOS.md)."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree
from PIL import Image

DOC = "/home/t1an/Descargas/sereos02/documentacion"
CAP = DOC + "/capturas"
DIA = DOC + "/diagramas"
REC = DOC + "/presentacion/recursos"
ICO = REC + "/iconos/png/"
OUT = DOC + "/presentacion/Presentacion_SereOS_Nueva.pptx"

NOCHE = "0D0F16"
TARJETA_OSCURA = "1A1E2A"
PAPEL = "F4EFE3"
BLANCO = "FFFFFF"
TINTA = "14161F"
MENTA = "9AA3B8"
GRIS = "5C6275"
TEXTO_MEDIO = "3A3F4F"
AMARILLO = "FFCB1F"
ROJO = "FF5B47"
CIAN = "3DDBD9"
AZUL = "2F5BFF"

TITULO = "Fira Sans Condensed"
SANS = "Inter"
MONO = "JetBrains Mono"

W, H = 13.333, 7.5
M = 0.7

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
BLANK = prs.slide_layouts[6]


def rgb(h):
    return RGBColor.from_string(h)


def lienzo(fondo):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(fondo)
    return s


def tarjeta(s, x, y, w, h, color, radio=0.22):
    r = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = rgb(color)
    r.line.fill.background()
    r.shadow.inherit = False
    r.adjustments[0] = min(0.5, radio / min(w, h))
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


def redondear(pic, adj=6000):
    geom = pic._element.spPr.find(qn("a:prstGeom"))
    geom.set("prst", "roundRect")
    av = geom.find(qn("a:avLst"))
    if av is None:
        av = etree.SubElement(geom, qn("a:avLst"))
    for g in list(av):
        av.remove(g)
    gd = etree.SubElement(av, qn("a:gd"))
    gd.set("name", "adj")
    gd.set("fmla", f"val {adj}")


def imagen(s, ruta, x, y, w, h, fondo=None, pad=0.18, radio=0.22):
    """Tarjeta redondeada (opcional) con la imagen centrada, sin deformar, con esquinas redondeadas."""
    if fondo:
        tarjeta(s, x, y, w, h, fondo, radio)
        x, y, w, h = x + pad, y + pad, w - 2 * pad, h - 2 * pad
    iw, ih = Image.open(ruta).size
    esc = min(w / iw, h / ih)
    pw, ph = iw * esc, ih * esc
    px = x + (w - pw) / 2
    py = y + (h - ph) / 2
    pic = s.shapes.add_picture(ruta, Inches(px), Inches(py), Inches(pw), Inches(ph))
    redondear(pic, adj=int(min(50000, radio / min(pw, ph) * 100000)))
    return px, py, pw, ph


def icono(s, nombre, color, x, y, h, fondo=None, w=None):
    return imagen(s, ICO + f"{nombre}_{color}.png", x, y, w or h, h, fondo=fondo, pad=0.22, radio=0.1)


def pastillas(s, x, y, w, color, n=16, tam=9):
    """Hilera de pastillas de PAC-MAN como texto (puntos), alineada a la derecha del encabezado."""
    texto(s, x, y, w, 0.3, " ".join(["●"] * n), size=tam, color=color, align="r")


def fantasma(s, ruta, x, y, h):
    """Imagen real (sprite CC0) sin tarjeta, con alto fijo."""
    iw, ih = Image.open(ruta).size
    w = h * iw / ih
    s.shapes.add_picture(ruta, Inches(x), Inches(y), Inches(w), Inches(h))
    return w


PAC = REC + "/pacman/"
GH = {n: PAC + f"silueta_{n}_tinta.png" for n in ["azul", "rojo", "rosa", "naranja"]}
PACMAN = PAC + "pacman_mono_tinta.png"
PACMAN_AMARILLO = PAC + "pacman_mono_amarillo.png"


def kicker(s, x, y, txt, color=GRIS, dots=False):
    texto(s, x, y, 9, 0.3, txt.upper(), size=12, color=color, font=MONO, bold=True)
    if dots:
        pastillas(s, 9.2, y + 0.02, 3.4, color, n=14, tam=8)


def titulo(s, x, y, w, h, txt, size=40, color=TINTA):
    return texto(s, x, y, w, h, txt, size=size, color=color, font=TITULO, bold=True, interlinea=0.95)


def notas(s, txt):
    s.notes_slide.notes_text_frame.text = txt


ICONO_BG = None

# 01 Portada ------------------------------------------------------------------
s = lienzo(NOCHE)
kicker(s, M, 0.7, "Proyecto final de sistemas operativos", MENTA, dots=False)
texto(s, M - 0.05, 1.3, 7, 2.3, "SereOS", size=150, color=AMARILLO, font=TITULO, bold=True, interlinea=0.85)
texto(s, M, 3.7, 6.2, 1.2, "Un sistema operativo x86 de 32 bits que arranca, dibuja ventanas y se juega.",
      size=20, color=PAPEL, interlinea=1.2)
tarjeta(s, M, 5.2, 6.1, 1.6, TARJETA_OSCURA)
texto(s, M + 0.35, 5.5, 5.5, 1.2, [
    "Miguel Eduardo Angulo Cantor",
    "Karol Asley Orjuela Mape",
    "Juan David Gómez Rojas",
    "Sebastián Fernando Revelo Meneses"], size=14, color=PAPEL, espacio=2)
texto(s, 7.3, 6.45, 5.3, 0.3, "Universidad Manuela Beltrán, noviembre de 2026", size=12, color=MENTA, align="r")
tarjeta(s, 7.3, 0.7, 5.3, 5.4, TARJETA_OSCURA, radio=0.3)
imagen(s, CAP + "/02_escritorio/escritorio_principal.png", 7.3, 0.7, 5.3, 5.4, pad=0.3, radio=0.2)
notas(s, "Presentamos SereOS, un sistema operativo propio para i686 con escritorio gráfico y un juego integrado. "
         "Todo se compiló desde cero y se probó en Oracle VM VirtualBox.")

# 02 Pregunta -----------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "El problema", GRIS)
tarjeta(s, M, 1.2, 11.9, 3.5, BLANCO, radio=0.3)
texto(s, M + 0.6, 1.7, 10.8, 2.6, "¿Qué pasa entre GRUB y la primera ventana?", size=64,
      color=TINTA, font=TITULO, bold=True, interlinea=0.95, anclaje="m")
tarjeta(s, M, 5.0, 5.8, 1.8, AMARILLO, radio=0.25)
texto(s, M + 0.5, 5.25, 4.9, 1.4, ["Objetivo", "Recorrer el camino completo, no solo estudiarlo."],
      size=18, color=TINTA, espacio=6, interlinea=1.2)
tarjeta(s, 6.8, 5.0, 5.8, 1.8, TINTA, radio=0.25)
texto(s, 7.3, 5.25, 4.9, 1.4, ["Método", "Escribir arranque, kernel, ventanas y un juego, y probarlo en VirtualBox."],
      size=18, color=PAPEL, espacio=6, interlinea=1.2)
notas(s, "El planteamiento es responder qué ocurre desde que el gestor de arranque entrega el control hasta que "
         "aparece una interfaz usable.")

# 03 Cifras -------------------------------------------------------------------
s = lienzo(NOCHE)
kicker(s, M, 0.7, "SereOS 1.0 en números", MENTA)
titulo(s, M, 1.05, 9.5, 1.2, "Un kernel monolítico para i686", size=40, color=PAPEL)
icono(s, "cpu", "papel", 11.4, 0.8, 1.2)
cifras = [("7", "capas de arquitectura", AMARILLO),
          ("23", "pasos de inicialización en kernel_main", PAPEL),
          ("25", "comandos en la shell", PAPEL),
          ("35,1", "MiB de imagen ISO", CIAN)]
for i, (num, lab, col) in enumerate(cifras):
    x = M + i * 3.0
    tarjeta(s, x, 2.7, 2.8, 3.9, TARJETA_OSCURA, radio=0.25)
    texto(s, x + 0.3, 3.0, 2.3, 1.6, num, size=72, color=col, font=TITULO, bold=True, anclaje="m")
    texto(s, x + 0.3, 4.9, 2.2, 1.5, lab, size=18, color=PAPEL, interlinea=1.2)
notas(s, "SereOS es un kernel monolítico que se ejecuta íntegramente en anillo 0. Estas cifras resumen el alcance real.")

# 04 Arquitectura -------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Arquitectura", GRIS)
titulo(s, M, 1.05, 4.8, 1.8, "Siete capas que solo miran hacia abajo", size=40)
tarjeta(s, M, 3.1, 4.6, 3.5, BLANCO, radio=0.25)
texto(s, M + 0.4, 3.5, 3.8, 3.0,
      "Cada capa llama a la de abajo, desde el hardware hasta las aplicaciones. Las aplicaciones "
      "no tienen privilegios propios: comparten el anillo 0 con el kernel.", size=18, color=TEXTO_MEDIO,
      interlinea=1.3)
imagen(s, DIA + "/d1_arquitectura_capas.png", 5.6, 0.7, 7.0, 6.1, fondo=BLANCO, pad=0.2, radio=0.25)
notas(s, "Leemos el diagrama de abajo hacia arriba. No hay separación de privilegios entre aplicaciones y kernel.")

# 05 Arranque -----------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Arranque", GRIS)
titulo(s, M, 1.05, 11, 0.9, "Del menú de GRUB al escritorio", size=40)
imagen(s, DIA + "/d2_arranque.png", M, 2.2, 7.6, 4.6, fondo=BLANCO, pad=0.2, radio=0.25)
imagen(s, CAP + "/01_arranque/grub_menu.png", 8.6, 2.2, 4.0, 2.4, fondo=TINTA, pad=0.15, radio=0.2)
tarjeta(s, 8.6, 4.8, 4.0, 2.0, AMARILLO, radio=0.25)
texto(s, 8.9, 5.05, 3.5, 1.6, ["kernel_main ejecuta 23 pasos en orden.",
                               "Sin framebuffer, el sistema cae a la consola de texto."],
      size=16, color=TINTA, espacio=10, interlinea=1.25)
notas(s, "GRUB carga la imagen Multiboot y salta a boot.s, que prepara la pila y llama a kernel_main. "
         "Si no hay framebuffer, el sistema arranca en modo texto.")

# 06 Interrupciones -----------------------------------------------------------
s = lienzo(NOCHE)
kicker(s, M, 0.7, "Núcleo", MENTA)
tarjeta(s, M, 1.9, 5.2, 4.9, TARJETA_OSCURA, radio=0.3)
texto(s, M + 0.4, 2.2, 4.5, 2.0, "100", size=160, color=AMARILLO, font=TITULO, bold=True, interlinea=0.85)
texto(s, M + 0.4, 4.1, 4.4, 0.6, "interrupciones por segundo del PIT", size=20, color=PAPEL)
texto(s, M + 0.4, 4.9, 4.4, 1.8, ["El PIC remapeado lleva las IRQ a los vectores 32 a 47.",
                                  "En VirtualBox, 3 439 ticks tras 34 segundos."],
      size=16, color=MENTA, espacio=10, interlinea=1.3)
imagen(s, DIA + "/d3_interrupciones.png", 6.2, 1.9, 6.4, 4.9, fondo=BLANCO, pad=0.2, radio=0.25)
notas(s, "Una interrupción pasa por isr.s hasta interrupt_handler. Si el vector es menor que 32 es una excepción "
         "y el sistema entra en pantalla de error.")

# 07 Memoria ------------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Memoria", GRIS)
tarjeta(s, M, 1.9, 5.0, 4.9, BLANCO, radio=0.3)
texto(s, M + 0.4, 2.2, 4.3, 2.0, "512", size=150, color=AZUL, font=TITULO, bold=True, interlinea=0.85)
texto(s, M + 0.4, 4.1, 4.3, 0.5, "MiB con identidad y páginas PSE", size=20, color=TINTA)
texto(s, M + 0.4, 4.8, 4.3, 1.5,
      "La dirección virtual es igual a la física, con páginas de 4 MiB. El heap del kernel tiene 8 MiB para kmalloc.",
      size=16, color=TEXTO_MEDIO, interlinea=1.3)
icono(s, "memory-stick", "azul", M + 0.4, 6.0, 0.55)
imagen(s, DIA + "/d4_mapa_memoria.png", 6.0, 1.9, 6.6, 4.9, fondo=BLANCO, pad=0.2, radio=0.25)
notas(s, "La paginación de identidad permite mapear 512 MiB con páginas grandes. El framebuffer que entrega GRUB "
         "cae dentro de esa ventana.")

# 08 Ventanas -----------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Entorno gráfico", GRIS)
tarjeta(s, M, 1.9, 4.4, 4.9, TINTA, radio=0.3)
texto(s, M + 0.4, 2.3, 3.6, 1.6, "Varias ventanas, un solo buffer", size=32, color=PAPEL, font=TITULO, bold=True,
      interlinea=0.95)
texto(s, M + 0.4, 4.1, 3.6, 2.2,
      "El compositor dibuja en memoria y copia al framebuffer solo las regiones que cambiaron.",
      size=16, color=PAPEL, interlinea=1.3)
imagen(s, CAP + "/04_aplicaciones/multiventana.png", 5.4, 1.9, 7.2, 4.9, fondo=TINTA, pad=0.2, radio=0.25)
notas(s, "La captura muestra terminal y otra aplicación abiertas a la vez, en VirtualBox.")

# 09 Apps ---------------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Escritorio", GRIS)
titulo(s, M, 1.05, 11, 0.9, "Las apps que vienen con SereOS", size=40)
celdas = [(CAP + "/02_escritorio/qemu_menu_launcher.png", "Menú de inicio",
           "Lanza cada aplicación desde el escritorio."),
          (CAP + "/04_aplicaciones/explorador_archivos.png", "Explorador de archivos",
           "Navega el sistema de archivos RAMFS."),
          (CAP + "/04_aplicaciones/monitor_sistema.png", "Monitor del sistema",
           "Muestra memoria, tiempo y tareas en curso.")]
for i, (ruta, lab, desc) in enumerate(celdas):
    x = M + i * 4.1
    tarjeta(s, x, 1.9, 3.9, 4.9, BLANCO, radio=0.3)
    imagen(s, ruta, x + 0.2, 2.1, 3.5, 2.9, pad=0.0, radio=0.18)
    texto(s, x + 0.3, 5.3, 3.4, 0.4, lab, size=18, color=TINTA, bold=True)
    texto(s, x + 0.3, 5.75, 3.4, 0.9, desc, size=14, color=TEXTO_MEDIO, interlinea=1.2)
notas(s, "Todas las aplicaciones son ventanas del mismo compositor. Las capturas son de VirtualBox.")

# 10 Terminal -----------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Terminal", GRIS)
titulo(s, M, 1.05, 5.2, 1.6, "Una shell de 25 comandos", size=40)
tarjeta(s, M, 2.8, 5.2, 2.2, TINTA, radio=0.25)
texto(s, M + 0.4, 3.1, 4.5, 1.8, [
    "$ help        lista los comandos",
    "$ sysinfo     resumen del sistema",
    "$ div0        división por cero"], size=14, color=PAPEL, font=MONO, interlinea=1.45)
tarjeta(s, M, 5.2, 5.2, 1.6, BLANCO, radio=0.25)
texto(s, M + 0.4, 5.45, 4.4, 1.2, "La misma shell atiende la ventana gráfica y la consola VGA de respaldo.",
      size=16, color=TEXTO_MEDIO, interlinea=1.3)
imagen(s, CAP + "/03_terminal/cmd_sysinfo_version.png", 6.3, 1.9, 6.3, 4.9, fondo=TINTA, pad=0.2, radio=0.25)
notas(s, "La shell se comparte entre la terminal gráfica y la consola de texto. div0 sirve para probar la IDT.")

# 11 Comandos -----------------------------------------------------------------
s = lienzo(NOCHE)
kicker(s, M, 0.7, "Terminal", MENTA)
titulo(s, M, 1.05, 11, 0.9, "Comandos que dan información", size=40, color=PAPEL)
celdas = [(CAP + "/03_terminal/cmd_help.png", "help", "Lista lo disponible en la shell."),
          (CAP + "/03_terminal/cmd_dmesg.png", "dmesg", "Registro del arranque, paso a paso.")]
for i, (ruta, lab, desc) in enumerate(celdas):
    x = M + i * 6.1
    tarjeta(s, x, 2.1, 5.8, 4.6, TARJETA_OSCURA, radio=0.3)
    imagen(s, ruta, x + 0.25, 2.3, 5.3, 3.4, pad=0.0, radio=0.18)
    texto(s, x + 0.35, 5.9, 5.1, 0.4, lab, size=18, color=PAPEL, font=MONO, bold=True)
    texto(s, x + 0.35, 6.3, 5.1, 0.4, desc, size=14, color=MENTA)
notas(s, "Las salidas son reales, tomadas en VirtualBox. dmesg reproduce el registro de inicialización del kernel.")

# 12 PAC-MAN ------------------------------------------------------------------
s = lienzo(AMARILLO)
kicker(s, M, 0.7, "PAC-MAN SereOS", TINTA, dots=True)
imagen(s, CAP + "/05_pacman_sereos_vbox/05_partida_dots_fantasmas.png", M, 1.9, 6.4, 4.9, fondo=BLANCO,
       pad=0.2, radio=0.25)
tarjeta(s, 7.6, 1.9, 5.0, 3.0, NOCHE, radio=0.3)
texto(s, 7.95, 2.2, 4.4, 2.6, "Un juego como aplicación nativa", size=28, color=PAPEL, font=TITULO, bold=True,
      interlinea=0.95)
texto(s, 7.95, 3.45, 4.4, 1.5, "Se compila como libpacman.a y el kernel lo ejecuta como una aplicación más.",
      size=14, color=MENTA, interlinea=1.3)
pastillas(s, 7.95, 4.45, 4.5, AMARILLO, n=14, tam=10)
tarjeta(s, 7.6, 5.15, 5.0, 1.65, BLANCO, radio=0.25)
fantasma(s, PACMAN, 7.95, 5.4, 1.1)
texto(s, 9.3, 5.45, 3.1, 1.3, ["Makefile propio, pruebas y", "un contrato de plataforma."],
      size=14, color=TINTA, interlinea=1.3)
notas(s, "PAC-MAN SereOS se compila como biblioteca y el kernel la ejecuta como una aplicación más.")

# 13 PAC-MAN pantallas --------------------------------------------------------
s = lienzo(AMARILLO)
kicker(s, M, 0.7, "PAC-MAN SereOS", TINTA, dots=True)
titulo(s, M, 1.05, 11, 0.9, "De la portada al fin de partida", size=40, color=TINTA)
for i, g in enumerate(["rojo", "rosa", "azul", "naranja"]):
    fantasma(s, GH[g], 9.6 + i * 0.8, 1.05, 0.8)
trio = [(CAP + "/05_pacman_sereos_vbox/02_attract.png", "Pantalla de inicio"),
        (CAP + "/05_pacman_sereos_vbox/03_menu_principal.png", "Menú principal"),
        (CAP + "/05_pacman_sereos_vbox/12_game_over.png", "Fin de partida")]
for i, (ruta, lab) in enumerate(trio):
    x = M + i * 4.1
    tarjeta(s, x, 2.1, 3.9, 4.7, BLANCO, radio=0.3)
    imagen(s, ruta, x + 0.2, 2.3, 3.5, 3.5, pad=0.0, radio=0.18)
    texto(s, x + 0.3, 6.0, 3.4, 0.4, lab, size=14, color=TINTA, font=MONO, bold=True)
notas(s, "El juego pasa por las mismas pantallas en VirtualBox: inicio, menú, partida y fin de partida.")

# 14 Errores ------------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Errores y modo texto", GRIS)
titulo(s, M, 1.05, 11, 0.9, "Cuando algo falla, se ve en pantalla", size=40)
tarjeta(s, M, 2.1, 5.9, 4.6, TINTA, radio=0.3)
imagen(s, CAP + "/03_terminal/panico_div0.png", M + 0.25, 2.3, 5.4, 3.5, pad=0.0, radio=0.18)
texto(s, M + 0.35, 6.0, 5.2, 0.4, "Pánico por división entre cero (div0)", size=12, color=MENTA, font=MONO)
tarjeta(s, 6.8, 2.1, 5.8, 4.6, TINTA, radio=0.3)
imagen(s, CAP + "/03_terminal/modo_texto_sysinfo.png", 7.05, 2.3, 5.3, 3.5, pad=0.0, radio=0.18)
texto(s, 7.15, 6.0, 5.2, 0.4, "Modo texto con sysinfo, sin framebuffer", size=12, color=MENTA, font=MONO)
notas(s, "El pánico se activa desde la shell con div0 y muestra los registros del momento del fallo. El modo texto "
         "aparece cuando GRUB no entrega un framebuffer.")

# 15 Dos plataformas ----------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "El juego", GRIS)
titulo(s, M, 1.05, 11, 0.9, "Una lógica, dos plataformas", size=40)
imagen(s, DIA + "/d5_arquitectura_juego.png", M, 2.1, 7.0, 4.7, fondo=BLANCO, pad=0.2, radio=0.25)
notas_txt = [
    "El núcleo y el render no conocen SereOS ni SDL.",
    "El contrato pac_platform.h lo implementan SereOS y Linux.",
    "Linux se usa solo para probar el juego en desarrollo."]
for i, t in enumerate(notas_txt):
    y = 2.1 + i * 1.6
    tarjeta(s, 8.1, y, 4.5, 1.4, TINTA if i == 1 else BLANCO, radio=0.22)
    texto(s, 8.4, y + 0.22, 3.95, 1.0, t, size=16, color=PAPEL if i == 1 else TINTA, interlinea=1.25,
          anclaje="m")
notas(s, "El juego tiene una lógica común y dos adaptadores: uno para Linux con SDL2 y otro para SereOS.")

# 16 ISO ----------------------------------------------------------------------
s = lienzo(NOCHE)
kicker(s, M, 0.7, "Construcción", MENTA)
imagen(s, DIA + "/d6_pipeline_iso.png", M, 1.9, 8.0, 4.9, fondo=BLANCO, pad=0.2, radio=0.25)
tarjeta(s, 9.0, 1.9, 3.6, 2.4, TARJETA_OSCURA, radio=0.25)
texto(s, 9.3, 2.15, 3.1, 1.3, "35,1", size=72, color=AMARILLO, font=TITULO, bold=True, anclaje="m")
texto(s, 9.3, 3.5, 3.1, 0.6, "MiB de sereos.iso", size=18, color=PAPEL)
tarjeta(s, 9.0, 4.5, 3.6, 2.3, BLANCO, radio=0.25)
texto(s, 9.3, 4.75, 3.1, 1.9, ["36 835 328 bytes.",
                               "Ocho pasos con make. El arranque en VirtualBox sigue siendo manual."],
      size=14, color=TINTA, espacio=8, interlinea=1.3)
notas(s, "El Makefile compila el kernel con gcc -m32 y nasm, enlaza el juego como libpacman.a y genera la ISO "
         "con grub-mkrescue.")

# 17 Pruebas ------------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Pruebas", GRIS)
titulo(s, M, 1.05, 11, 0.9, "Qué verificamos y dónde", size=40)
pruebas = [("24", "pruebas en VirtualBox", AZUL), ("209", "comprobaciones de make test del juego", TINTA),
           ("2", "pruebas de ratón en QEMU con la misma ISO", TINTA)]
for i, (num, lab, col) in enumerate(pruebas):
    x = M + i * 4.1
    tarjeta(s, x, 2.1, 3.9, 2.5, BLANCO, radio=0.3)
    texto(s, x + 0.35, 2.4, 3.2, 1.2, num, size=64, color=col, font=TITULO, bold=True, anclaje="m")
    texto(s, x + 0.35, 3.7, 3.2, 0.8, lab, size=16, color=TEXTO_MEDIO, interlinea=1.2)
tarjeta(s, M, 4.9, 11.9, 1.9, TINTA, radio=0.3)
icono(s, "check-circle", "papel", M + 0.4, 5.25, 0.9)
texto(s, M + 1.7, 5.15, 9.8, 1.6, ["[OK] paginación identidad, PSE 4 MiB",
                                   "[OK] planificador round-robin listo"],
      size=16, color=PAPEL, font=MONO, espacio=8, interlinea=1.3, anclaje="m")
notas(s, "El arnés automático de QEMU no se repitió, así que no presentamos sus resultados como propios.")

# 18 Limitaciones -------------------------------------------------------------
s = lienzo(NOCHE)
kicker(s, M, 0.7, "Limitaciones", MENTA)
titulo(s, M, 1.05, 11, 0.9, "Lo que no probamos ni hicimos", size=40, color=PAPEL)
tarjeta(s, M, 2.1, 5.8, 4.7, TARJETA_OSCURA, radio=0.3)
texto(s, M + 0.45, 2.45, 5.0, 0.6, "No probado", size=24, color=AMARILLO, font=TITULO, bold=True)
texto(s, M + 0.45, 3.2, 5.0, 3.0, ["Sonido audible de la SB16", "Apagado y reinicio",
                                   "Redimensionado de ventanas", "Hardware físico"],
      size=18, color=PAPEL, espacio=12, interlinea=1.2)
tarjeta(s, 6.8, 2.1, 5.8, 4.7, TARJETA_OSCURA, radio=0.3)
texto(s, 7.25, 2.45, 4.5, 0.6, "No implementado", size=24, color=ROJO, font=TITULO, bold=True)
texto(s, 7.25, 3.2, 4.4, 2.2, ["Multitarea preemptiva y anillo 3", "Llamadas al sistema",
                               "Disco, red, USB y UEFI"], size=18, color=PAPEL, espacio=12, interlinea=1.2)
icono(s, "hard-drive", "papel", 10.7, 5.2, 1.2, fondo=None)
notas(s, "Los pendientes son parte del resultado. Tampoco se probó en hardware real.")

# 19 Conclusiones -------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Conclusiones", GRIS)
titulo(s, M, 1.05, 11, 0.9, "Lo que nos dejó el proyecto", size=40)
concl = ["El orden de arranque y el remapeo del PIC se ven en pantalla.",
         "Separar la lógica del juego de su plataforma permite correrlo en dos sistemas.",
         "La evidencia decide qué afirmamos, no lo que creíamos antes."]
for i, c in enumerate(concl):
    y = 2.1 + i * 1.55
    tarjeta(s, M, y, 11.9, 1.3, BLANCO if i != 1 else TINTA, radio=0.25)
    texto(s, M + 0.4, y, 1.0, 1.3, f"{i + 1}", size=40, color=AZUL if i != 1 else AMARILLO,
          font=TITULO, bold=True, anclaje="m")
    texto(s, M + 1.5, y, 10.0, 1.3, c, size=24, color=TINTA if i != 1 else PAPEL, font=TITULO, bold=True,
          anclaje="m", interlinea=1.05)
notas(s, "Insistimos en que la verificación con evidencia es la que decide qué afirmamos.")

# 20 Cierre -------------------------------------------------------------------
s = lienzo(AMARILLO)
kicker(s, M, 0.7, "Gracias por su atención", TINTA)
texto(s, M - 0.05, 1.05, 11.5, 2.0, "Gracias", size=130, color=TINTA, font=TITULO, bold=True, interlinea=0.85)
texto(s, M, 3.05, 9.0, 0.8, "¿Preguntas?", size=40, color=TINTA, font=TITULO, bold=True)
tarjeta(s, M, 3.9, 7.4, 2.7, NOCHE, radio=0.3)
texto(s, M + 0.45, 4.2, 6.6, 2.2, [
    "Miguel Eduardo Angulo Cantor",
    "Karol Asley Orjuela Mape",
    "Juan David Gómez Rojas",
    "Sebastián Fernando Revelo Meneses"], size=18, color=PAPEL, espacio=4)
notas(s, "Agradecemos la atención. Estamos listos para preguntas sobre el arranque, el kernel o el juego.")

# 21 Créditos -----------------------------------------------------------------
s = lienzo(PAPEL)
kicker(s, M, 0.7, "Anexo", GRIS)
titulo(s, M, 1.05, 11, 0.9, "Créditos de los recursos gráficos", size=40)
tarjeta(s, M, 2.1, 11.9, 4.2, BLANCO, radio=0.3)
texto(s, M + 0.5, 2.5, 10.9, 3.6, [
    "Iconos (cpu, memory-stick, disc-3, check-circle, hard-drive, ghost): Lucide 1.69.0, licencia ISC.",
    "Fantasmas y PAC-MAN: siluetas monocromáticas derivadas de 'ghosts' (OpenGameArt, CC0) y de 'Pac-Man portal icon' (Wikimedia Commons, dominio público).",
    "Diagramas técnicos (d1 a d6), capturas de escritorio, terminal, aplicaciones y PAC-MAN: material propio del proyecto, generado en VirtualBox y con el script de diagramas del repositorio."],
    size=16, color=TINTA, espacio=14, interlinea=1.3)
notas(s, "Detalle completo con enlaces y licencias en recursos/CREDITOS.md.")

prs.save(OUT)
print("guardado", OUT, "diapositivas", len(prs.slides))
