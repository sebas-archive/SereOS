# -*- coding: utf-8 -*-
"""SereOS 1.0: presentación final, sistema de diseño nuevo.
Marca: logotipo oficial (S blanca sobre azul #004EFD). Una sola familia tipográfica (Inter) más
JetBrains Mono para rótulos. Tarjetas con borde fino, iconos de línea Lucide, capturas y
diagramas propios del proyecto. Créditos en recursos/CREDITOS.md."""
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
PAC = REC + "/pacman/"
MARCA = REC + "/marca/"
OUT = DOC + "/presentacion/Presentacion_SereOS_Nueva.pptx"

# Paleta
AZUL = "004EFD"
AZUL_SUAVE = "E6EEFF"
AZUL_PROF = "003BC9"
NAVY = "0A1230"
NAVY_TARJ = "121B3D"
NAVY_LINEA = "26335F"
FONDO = "F6F8FC"
BLANCO = "FFFFFF"
LINEA = "E1E6F1"
TINTA = "0B1020"
GRIS = "5B647A"
GRIS_CLARO = "A9B3CC"
AZUL_CLARO = "DCE7FF"
AMARILLO = "FFC700"

SANS = "Inter"
MONO = "JetBrains Mono"

W, H = 13.333, 7.5
M = 0.8
CW = W - 2 * M  # ancho útil

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


def tarjeta(s, x, y, w, h, fondo=BLANCO, borde=LINEA, radio=0.2):
    r = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = rgb(fondo)
    if borde:
        r.line.color.rgb = rgb(borde)
        r.line.width = Pt(0.75)
    else:
        r.line.fill.background()
    r.shadow.inherit = False
    r.adjustments[0] = min(0.5, radio / min(w, h))
    return r


def texto(s, x, y, w, h, parrafos, size=16, color=TINTA, font=SANS, bold=False, align="l",
          anclaje="t", espacio=0, interlinea=None, spc=None):
    caja = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = caja.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anclaje]
    if isinstance(parrafos, str):
        parrafos = [parrafos]
    for i, t in enumerate(parrafos):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        if i > 0:
            p.space_before = Pt(espacio)
        if interlinea:
            p.line_spacing = interlinea
        r = p.add_run()
        r.text = t
        r.font.size = Pt(size)
        r.font.color.rgb = rgb(color)
        r.font.name = font
        r.font.bold = bold
        if spc is not None:
            r._r.get_or_add_rPr().set("spc", str(spc))
    return caja


def redondear(pic, adj):
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


def imagen(s, ruta, x, y, w, h, fondo=None, borde=LINEA, pad=0.2, radio=0.2):
    """Imagen centrada, sin deformar, con esquinas redondeadas; opcionalmente dentro de una tarjeta."""
    if fondo:
        tarjeta(s, x, y, w, h, fondo, borde, radio=0.24)
        x, y, w, h = x + pad, y + pad, w - 2 * pad, h - 2 * pad
    iw, ih = Image.open(ruta).size
    esc = min(w / iw, h / ih)
    pw, ph = iw * esc, ih * esc
    pic = s.shapes.add_picture(ruta, Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))
    redondear(pic, int(min(50000, radio / min(pw, ph) * 100000)))
    return pic


def libre(s, ruta, x, y, h):
    iw, ih = Image.open(ruta).size
    s.shapes.add_picture(ruta, Inches(x), Inches(y), Inches(h * iw / ih), Inches(h))


def baldosa(s, icono, x, y, lado=0.62, fondo=AZUL_SUAVE, color="azul"):
    """Baldosa redondeada con un icono de línea."""
    tarjeta(s, x, y, lado, lado, fondo, None, radio=lado * 0.3)
    g = lado * 0.52
    s.shapes.add_picture(ICO + f"{icono}_{color}.png", Inches(x + (lado - g) / 2), Inches(y + (lado - g) / 2),
                         Inches(g), Inches(g))


def encabezado(s, rotulo, titulo, sub=None, oscuro=False, w=CW):
    texto(s, M, 0.62, 8, 0.3, rotulo.upper(), size=11, color=GRIS_CLARO if oscuro else AZUL, font=MONO,
          bold=True, spc=120)
    texto(s, M, 0.95, w, 0.8, titulo, size=34, color=BLANCO if oscuro else TINTA, bold=True, spc=-40,
          interlinea=0.95)
    if sub:
        texto(s, M, 1.72, w, 0.5, sub, size=16, color=GRIS_CLARO if oscuro else GRIS, interlinea=1.2)


def notas(s, txt):
    s.notes_slide.notes_text_frame.text = txt


def tarjeta_oscura(s, x, y, w, h):
    return tarjeta(s, x, y, w, h, NAVY_TARJ, NAVY_LINEA, radio=0.24)


CY = 2.6          # inicio del contenido bajo el encabezado
CH = H - CY - 0.6  # alto del contenido

# 01 Portada ------------------------------------------------------------------
s = lienzo(AZUL)
libre(s, MARCA + "logo_s_blanca.png", M, 0.7, 0.75)
texto(s, M + 0.85, 0.95, 6, 0.3, "PROYECTO FINAL DE SISTEMAS OPERATIVOS", size=11, color=AZUL_CLARO, font=MONO,
      bold=True, spc=120)
texto(s, M - 0.06, 2.0, 6.9, 2.0, "SereOS", size=104, color=BLANCO, bold=True, spc=-200, interlinea=0.85)
texto(s, M, 4.2, 5.6, 1.0, "Un sistema operativo x86 de 32 bits que arranca, dibuja ventanas y se juega.",
      size=20, color=AZUL_CLARO, interlinea=1.25)
texto(s, M, 5.45, 4, 0.3, "EQUIPO", size=11, color=AZUL_CLARO, font=MONO, bold=True, spc=120)
texto(s, M, 5.78, 3.3, 0.9, ["Miguel Eduardo Angulo Cantor", "Karol Asley Orjuela Mape"], size=13,
      color=BLANCO, espacio=3)
texto(s, 4.2, 5.78, 3.4, 0.9, ["Juan David Gómez Rojas", "Sebastián Fernando Revelo Meneses"], size=13,
      color=BLANCO, espacio=3)
texto(s, M, 6.8, 6.5, 0.3, "Universidad Manuela Beltrán, noviembre de 2026", size=12, color=AZUL_CLARO)
imagen(s, CAP + "/02_escritorio/escritorio_principal.png", 7.9, 0.7, 4.65, 6.1, fondo=FONDO, borde=None, pad=0.25,
       radio=0.18)
notas(s, "Presentamos SereOS, un sistema operativo propio para i686 con escritorio gráfico y un juego integrado. "
         "Todo se compiló desde cero y se probó en Oracle VM VirtualBox.")

# 02 Contenido ----------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Contenido", "Lo que vamos a recorrer", "Del arranque al juego, con evidencia en cada paso.")
items = [("layers", "Arquitectura", "Siete capas y un kernel monolítico."),
         ("power", "Arranque", "De GRUB a la primera ventana."),
         ("cpu", "Núcleo", "Interrupciones, temporización y memoria."),
         ("app-window", "Entorno gráfico", "Ventanas, aplicaciones y terminal."),
         ("gamepad-2", "PAC-MAN SereOS", "Un juego como aplicación nativa."),
         ("circle-check", "Pruebas y límites", "Qué verificamos y qué no.")]
for i, (ic, t, d) in enumerate(items):
    x = M + (i % 3) * 3.99
    y = CY + (i // 3) * 2.2
    tarjeta(s, x, y, 3.75, 2.0)
    baldosa(s, ic, x + 0.3, y + 0.3)
    texto(s, x + 0.3, y + 1.1, 3.2, 0.4, t, size=18, bold=True)
    texto(s, x + 0.3, y + 1.5, 3.2, 0.4, d, size=13, color=GRIS)
notas(s, "Esta es la ruta de la presentación: arquitectura, arranque, núcleo, entorno gráfico, juego y pruebas.")

# 03 Problema -----------------------------------------------------------------
s = lienzo(FONDO)
texto(s, M, 0.62, 8, 0.3, "EL PROBLEMA", size=11, color=AZUL, font=MONO, bold=True, spc=120)
texto(s, M, 1.4, 6.7, 4.4, "¿Qué pasa entre GRUB y la primera ventana?", size=54, bold=True, spc=-120,
      interlinea=0.98)
for i, (ic, t, d) in enumerate([
        ("target", "Objetivo", "Recorrer el camino completo, no solo estudiarlo en teoría."),
        ("hammer", "Método", "Escribir arranque, kernel, ventanas y un juego, y probarlo en VirtualBox.")]):
    y = 1.4 + i * 2.75
    tarjeta(s, 8.0, y, 4.53, 2.5)
    baldosa(s, ic, 8.35, y + 0.35)
    texto(s, 8.35, y + 1.15, 3.9, 0.4, t, size=20, bold=True)
    texto(s, 8.35, y + 1.6, 3.85, 0.8, d, size=14, color=GRIS, interlinea=1.3)
notas(s, "El planteamiento es responder qué ocurre desde que el gestor de arranque entrega el control hasta que "
         "aparece una interfaz usable.")

# 04 Cifras -------------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "SereOS 1.0 en números", "Un kernel monolítico para i686", "Todo se ejecuta en anillo 0.")
cifras = [("layers", "7", "capas de arquitectura"), ("list-ordered", "23", "pasos de inicialización en kernel_main"),
          ("terminal", "25", "comandos en la shell"), ("disc-3", "35,1", "MiB de imagen ISO")]
for i, (ic, n, lab) in enumerate(cifras):
    x = M + i * 2.99
    tarjeta(s, x, CY, 2.75, 3.4)
    baldosa(s, ic, x + 0.3, CY + 0.3)
    texto(s, x + 0.3, CY + 1.1, 2.3, 1.2, n, size=56, color=AZUL, bold=True, spc=-100, anclaje="m")
    texto(s, x + 0.3, CY + 2.4, 2.2, 0.9, lab, size=14, color=GRIS, interlinea=1.25)
tarjeta(s, M, 6.25, CW, 0.7, AZUL_SUAVE, None, radio=0.2)
texto(s, M + 0.35, 6.25, CW - 0.7, 0.7, "El kernel y las aplicaciones comparten el mismo espacio de privilegios.",
      size=14, color=AZUL, bold=True, anclaje="m")
notas(s, "SereOS es un kernel monolítico que se ejecuta íntegramente en anillo 0. Estas cifras resumen el alcance real.")

# 05 Arquitectura -------------------------------------------------------------
s = lienzo(FONDO)
texto(s, M, 0.62, 5, 0.3, "ARQUITECTURA", size=11, color=AZUL, font=MONO, bold=True, spc=120)
texto(s, M, 0.95, 4.7, 1.9, "Siete capas que solo miran hacia abajo", size=34, bold=True, spc=-40, interlinea=0.95)
tarjeta(s, M, 3.0, 4.5, 3.9)
baldosa(s, "layers", M + 0.35, 3.35)
texto(s, M + 0.35, 4.2, 3.85, 2.5, "Cada capa llama a la de abajo, desde el hardware hasta las aplicaciones. "
      "Las aplicaciones no tienen privilegios propios y comparten el anillo 0 con el kernel.", size=14,
      color=GRIS, interlinea=1.35)
imagen(s, DIA + "/d1_arquitectura_capas.png", 5.6, 0.6, 7.13, 6.3, fondo=BLANCO, pad=0.2)
notas(s, "Leemos el diagrama de abajo hacia arriba. No hay separación de privilegios entre aplicaciones y kernel.")

# 06 Arranque -----------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Arranque", "Del menú de GRUB al escritorio", "GRUB entrega el control a boot.s y kernel_main completa 23 pasos.")
imagen(s, DIA + "/d2_arranque.png", M, CY, 6.9, CH, fondo=BLANCO)
imagen(s, CAP + "/01_arranque/grub_menu.png", 7.95, CY, 4.58, 2.0, fondo=NAVY, borde=None, pad=0.15, radio=0.14)
tarjeta(s, 7.95, CY + 2.2, 4.58, 2.1)
baldosa(s, "power", 8.25, CY + 2.5, lado=0.55)
texto(s, 9.0, CY + 2.45, 3.3, 1.7, ["kernel_main ejecuta 23 pasos en orden.",
                                   "Sin framebuffer, cae a la consola de texto."], size=14, color=TINTA, espacio=8,
      interlinea=1.3)
notas(s, "GRUB carga la imagen Multiboot y salta a boot.s, que prepara la pila y llama a kernel_main. "
         "Si no hay framebuffer, el sistema arranca en modo texto.")

# 07 Interrupciones (oscura) --------------------------------------------------
s = lienzo(NAVY)
encabezado(s, "Núcleo", "Interrupciones y temporización", "El PIT marca el ritmo de todo el sistema.", oscuro=True)
tarjeta(s, M, CY, 4.8, CH, AZUL, None, radio=0.24)
texto(s, M + 0.4, CY + 0.2, 4.2, 2.0, "100", size=120, color=BLANCO, bold=True, spc=-200, interlinea=0.9)
texto(s, M + 0.4, CY + 2.0, 4.0, 0.7, "interrupciones por segundo del PIT", size=18, color=BLANCO, bold=True)
texto(s, M + 0.4, CY + 2.8, 4.0, 1.4, ["El PIC remapeado lleva las IRQ a los vectores 32 a 47.",
                                      "En VirtualBox, 3 439 ticks tras 34 segundos."], size=13, color=AZUL_CLARO,
      espacio=6, interlinea=1.3)
imagen(s, DIA + "/d3_interrupciones.png", 5.85, CY, 6.68, CH, fondo=BLANCO, borde=None)
notas(s, "Una interrupción pasa por isr.s hasta interrupt_handler. Si el vector es menor que 32 es una excepción "
         "y el sistema entra en pantalla de error.")

# 08 Memoria ------------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Núcleo", "Memoria con identidad y PSE", "La dirección virtual es igual a la física.")
tarjeta(s, M, CY, 4.8, CH)
baldosa(s, "memory-stick", M + 0.4, CY + 0.35)
texto(s, M + 0.4, CY + 1.05, 4.0, 1.7, "512", size=96, color=AZUL, bold=True, spc=-200, interlinea=0.9)
texto(s, M + 0.4, CY + 2.55, 4.0, 0.5, "MiB mapeados con páginas PSE de 4 MiB", size=15, bold=True)
texto(s, M + 0.4, CY + 3.2, 4.0, 1.0, "El heap del kernel tiene 8 MiB para kmalloc.", size=13, color=GRIS,
      interlinea=1.3)
imagen(s, DIA + "/d4_mapa_memoria.png", 5.85, CY, 6.68, CH, fondo=BLANCO)
notas(s, "La paginación de identidad permite mapear 512 MiB con páginas grandes. El framebuffer que entrega GRUB "
         "cae dentro de esa ventana.")

# 09 Entorno gráfico ----------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Entorno gráfico", "Varias ventanas, un solo buffer", "El compositor solo copia las regiones que cambiaron.")
tarjeta(s, M, CY, 3.9, CH)
baldosa(s, "app-window", M + 0.35, CY + 0.35)
texto(s, M + 0.35, CY + 1.2, 3.25, 2.8, ["El compositor dibuja en memoria y copia al framebuffer solo lo que cambió.",
                                         "Cada ventana mantiene su foco y su orden."], size=14, color=GRIS,
      espacio=10, interlinea=1.35)
imagen(s, CAP + "/04_aplicaciones/multiventana.png", 4.95, CY, 7.58, CH, fondo=NAVY, borde=None, pad=0.18, radio=0.16)
notas(s, "La captura muestra terminal y otra aplicación abiertas a la vez, en VirtualBox.")

# 10 Apps ---------------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Escritorio", "Las aplicaciones de SereOS", "Todas son ventanas del mismo compositor.")
celdas = [(CAP + "/02_escritorio/qemu_menu_launcher.png", "folder-tree", "Menú de inicio",
           "Lanza cada aplicación desde el escritorio."),
          (CAP + "/04_aplicaciones/explorador_archivos.png", "folder-tree", "Explorador de archivos",
           "Navega el sistema de archivos RAMFS."),
          (CAP + "/04_aplicaciones/monitor_sistema.png", "gauge", "Monitor del sistema",
           "Muestra memoria, tiempo y tareas en curso.")]
for i, (ruta, ic, t, d) in enumerate(celdas):
    x = M + i * 3.99
    tarjeta(s, x, CY, 3.75, CH)
    imagen(s, ruta, x + 0.2, CY + 0.2, 3.35, 2.45, radio=0.14)
    texto(s, x + 0.3, CY + 2.95, 3.2, 0.4, t, size=17, bold=True)
    texto(s, x + 0.3, CY + 3.4, 3.2, 0.7, d, size=13, color=GRIS, interlinea=1.3)
notas(s, "Todas las aplicaciones son ventanas del mismo compositor. Las capturas son de VirtualBox.")

# 11 Terminal -----------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Terminal", "Una shell de 25 comandos", "La misma shell atiende la ventana y la consola VGA.")
tarjeta(s, M, CY, 5.2, 2.5, NAVY, None, radio=0.24)
texto(s, M + 0.4, CY + 0.35, 4.5, 1.9, ["$ help        lista los comandos", "$ sysinfo     resumen del sistema",
                                        "$ div0        división por cero"], size=14, color=BLANCO, font=MONO,
      interlinea=1.5)
tarjeta(s, M, CY + 2.7, 5.2, 1.6)
baldosa(s, "terminal", M + 0.3, CY + 3.0, lado=0.55)
texto(s, M + 1.05, CY + 2.95, 3.9, 1.2, "div0 provoca una excepción a propósito para probar la IDT.", size=13,
      color=GRIS, interlinea=1.3, anclaje="m")
imagen(s, CAP + "/03_terminal/cmd_sysinfo_version.png", 6.3, CY, 6.23, CH, fondo=NAVY, borde=None, pad=0.18,
       radio=0.16)
notas(s, "La shell se comparte entre la terminal gráfica y la consola de texto. div0 sirve para probar la IDT.")

# 12 Comandos (oscura) --------------------------------------------------------
s = lienzo(NAVY)
encabezado(s, "Terminal", "Comandos que dan información", "Salidas reales, tomadas en VirtualBox.", oscuro=True)
celdas = [(CAP + "/03_terminal/cmd_help.png", "help", "Lista lo disponible en la shell."),
          (CAP + "/03_terminal/cmd_dmesg.png", "dmesg", "Registro del arranque, paso a paso.")]
for i, (ruta, t, d) in enumerate(celdas):
    x = M + i * 6.0
    tarjeta_oscura(s, x, CY, 5.73, CH)
    imagen(s, ruta, x + 0.2, CY + 0.2, 5.33, 2.9, borde=None, radio=0.14)
    texto(s, x + 0.35, CY + 3.3, 5.0, 0.4, t, size=17, color=BLANCO, font=MONO, bold=True)
    texto(s, x + 0.35, CY + 3.75, 5.0, 0.4, d, size=13, color=GRIS_CLARO)
notas(s, "Las salidas son reales, tomadas en VirtualBox. dmesg reproduce el registro de inicialización del kernel.")

# 13 PAC-MAN (oscura, acento amarillo) ----------------------------------------
s = lienzo(NAVY)
texto(s, M, 0.62, 8, 0.3, "PAC-MAN SEREOS", size=11, color=AMARILLO, font=MONO, bold=True, spc=120)
texto(s, M, 0.95, 11.7, 0.8, "Un juego como aplicación nativa", size=34, color=BLANCO, bold=True, spc=-40)
texto(s, M, 1.72, 11.7, 0.5, "Se compila como libpacman.a y el kernel lo ejecuta como una aplicación más.", size=16,
      color=GRIS_CLARO)
imagen(s, CAP + "/05_pacman_sereos_vbox/05_partida_dots_fantasmas.png", M, CY, 6.4, CH, fondo=NAVY_TARJ,
       borde=NAVY_LINEA, pad=0.2, radio=0.16)
tarjeta_oscura(s, 7.45, CY, 5.08, 2.05)
baldosa(s, "gamepad-2", 7.8, CY + 0.5, lado=0.95, fondo=NAVY_LINEA, color="amarillo")
texto(s, 9.1, CY + 0.35, 3.2, 1.4, ["Makefile propio,", "pruebas y un contrato", "de plataforma."], size=16,
      color=BLANCO, interlinea=1.3, anclaje="m")
tarjeta_oscura(s, 7.45, CY + 2.25, 5.08, 2.05)
for i in range(4):
    libre(s, ICO + "ghost_amarillo.png", 7.8 + i * 1.1, CY + 2.55, 0.85)
texto(s, 7.8, CY + 3.55, 4.4, 0.5, "Partida en VirtualBox", size=12, color=GRIS_CLARO, font=MONO)
notas(s, "PAC-MAN SereOS se compila como biblioteca y el kernel la ejecuta como una aplicación más.")

# 14 PAC-MAN pantallas (oscura) -----------------------------------------------
s = lienzo(NAVY)
texto(s, M, 0.62, 8, 0.3, "PAC-MAN SEREOS", size=11, color=AMARILLO, font=MONO, bold=True, spc=120)
texto(s, M, 0.95, 11.7, 0.8, "De la portada al fin de partida", size=34, color=BLANCO, bold=True, spc=-40)
texto(s, M, 1.72, 11.7, 0.5, "Las tres pantallas principales, tal como se ven en VirtualBox.", size=16,
      color=GRIS_CLARO)
trio = [(CAP + "/05_pacman_sereos_vbox/02_attract.png", "Pantalla de inicio"),
        (CAP + "/05_pacman_sereos_vbox/03_menu_principal.png", "Menú principal"),
        (CAP + "/05_pacman_sereos_vbox/12_game_over.png", "Fin de partida")]
for i, (ruta, t) in enumerate(trio):
    x = M + i * 3.99
    tarjeta_oscura(s, x, CY, 3.75, CH)
    imagen(s, ruta, x + 0.2, CY + 0.2, 3.35, 3.2, borde=None, radio=0.14)
    texto(s, x + 0.3, CY + 3.65, 3.2, 0.4, t, size=14, color=BLANCO, font=MONO, bold=True)
notas(s, "El juego pasa por las mismas pantallas en VirtualBox: inicio, menú, partida y fin de partida.")

# 15 Dos plataformas ----------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "El juego", "Una lógica, dos plataformas", "El mismo núcleo corre en SereOS y en Linux.")
imagen(s, DIA + "/d5_arquitectura_juego.png", M, CY, 6.9, CH, fondo=BLANCO)
filas = [("puzzle", "El núcleo y el render no conocen SereOS ni SDL."),
         ("plug", "El contrato pac_platform.h lo implementan SereOS y Linux."),
         ("flask-conical", "Linux se usa solo para probar el juego en desarrollo.")]
for i, (ic, t) in enumerate(filas):
    y = CY + i * 1.5
    tarjeta(s, 7.95, y, 4.58, 1.3)
    baldosa(s, ic, 8.25, y + 0.34, lado=0.62)
    texto(s, 9.1, y + 0.1, 3.2, 1.1, t, size=13, color=TINTA, interlinea=1.3, anclaje="m")
notas(s, "El juego tiene una lógica común y dos adaptadores: uno para Linux con SDL2 y otro para SereOS.")

# 16 ISO (oscura) -------------------------------------------------------------
s = lienzo(NAVY)
encabezado(s, "Construcción", "De las fuentes a la ISO", "Ocho pasos con make; el arranque en VirtualBox es manual.",
           oscuro=True)
imagen(s, DIA + "/d6_pipeline_iso.png", M, CY, 8.0, CH, fondo=BLANCO, borde=None)
tarjeta(s, 9.05, CY, 3.48, 2.3, AZUL, None, radio=0.24)
texto(s, 9.4, CY + 0.2, 2.9, 1.3, "35,1", size=64, color=BLANCO, bold=True, spc=-120, anclaje="m")
texto(s, 9.4, CY + 1.5, 2.9, 0.6, "MiB de sereos.iso", size=15, color=BLANCO, bold=True)
tarjeta_oscura(s, 9.05, CY + 2.5, 3.48, 1.8)
baldosa(s, "disc-3", 9.35, CY + 2.8, lado=0.55, fondo=NAVY_LINEA, color="blanco")
texto(s, 10.1, CY + 2.7, 2.2, 1.4, "36 835 328 bytes en total.", size=13, color=GRIS_CLARO, interlinea=1.3,
      anclaje="m")
notas(s, "El Makefile compila el kernel con gcc -m32 y nasm, enlaza el juego como libpacman.a y genera la ISO "
         "con grub-mkrescue.")

# 17 Pruebas ------------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Pruebas", "Qué verificamos y dónde", "Resultados de la última tanda de pruebas.")
pruebas = [("24", "pruebas en VirtualBox"), ("209", "comprobaciones de make test del juego"),
           ("2", "pruebas de ratón en QEMU con la misma ISO")]
for i, (n, lab) in enumerate(pruebas):
    x = M + i * 3.99
    tarjeta(s, x, CY, 3.75, 2.2)
    texto(s, x + 0.35, CY + 0.2, 3.1, 1.2, n, size=56, color=AZUL, bold=True, spc=-100, anclaje="m")
    texto(s, x + 0.35, CY + 1.4, 3.1, 0.7, lab, size=13, color=GRIS, interlinea=1.3)
tarjeta(s, M, CY + 2.4, CW, 1.9, NAVY, None, radio=0.24)
baldosa(s, "circle-check", M + 0.4, CY + 3.05, lado=0.6, fondo=NAVY_LINEA, color="blanco")
texto(s, M + 1.4, CY + 2.4, 10, 1.9, ["[OK] paginación activada: identidad, PSE 4 MiB",
                                      "[OK] planificador cooperativo round-robin listo"], size=14, color=BLANCO,
      font=MONO, interlinea=1.6, anclaje="m")
notas(s, "El arnés automático de QEMU no se repitió, así que no presentamos sus resultados como propios.")

# 18 Errores ------------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Errores y modo texto", "Cuando algo falla, se ve en pantalla", "El pánico muestra los registros y el modo texto sigue vivo.")
for i, (ruta, t) in enumerate([(CAP + "/03_terminal/panico_div0.png", "Pánico por división entre cero (div0)"),
                               (CAP + "/03_terminal/modo_texto_sysinfo.png", "Modo texto con sysinfo, sin framebuffer")]):
    x = M + i * 6.0
    tarjeta(s, x, CY, 5.73, CH)
    imagen(s, ruta, x + 0.2, CY + 0.2, 5.33, 3.3, fondo=NAVY, borde=None, pad=0.0, radio=0.14)
    texto(s, x + 0.35, CY + 3.7, 5.0, 0.4, t, size=12, color=GRIS, font=MONO)
notas(s, "El pánico se activa desde la shell con div0 y muestra los registros del momento del fallo. El modo texto "
         "aparece cuando GRUB no entrega un framebuffer.")

# 19 Limitaciones (oscura) ----------------------------------------------------
s = lienzo(NAVY)
encabezado(s, "Limitaciones", "Lo que no probamos ni hicimos", "Los pendientes también son parte del resultado.", oscuro=True)
bloques = [("No probado", "circle-dashed", ["Sonido audible de la SB16", "Apagado y reinicio",
                                           "Redimensionado de ventanas", "Hardware físico"]),
           ("No implementado", "circle-x", ["Multitarea preemptiva y anillo 3", "Llamadas al sistema",
                                           "Disco, red, USB y UEFI"])]
for i, (t, ic, lista) in enumerate(bloques):
    x = M + i * 6.0
    tarjeta_oscura(s, x, CY, 5.73, CH)
    texto(s, x + 0.4, CY + 0.35, 5, 0.5, t, size=20, color=BLANCO, bold=True)
    for j, it in enumerate(lista):
        y = CY + 1.15 + j * 0.78
        s.shapes.add_picture(ICO + f"{ic}_blanco.png", Inches(x + 0.4), Inches(y + 0.03), Inches(0.32), Inches(0.32))
        texto(s, x + 0.95, y, 4.5, 0.4, it, size=15, color=GRIS_CLARO)
notas(s, "Los pendientes son parte del resultado. El planificador es cooperativo, así que una tarea que no cede "
         "el control congela el escritorio. Tampoco se probó en hardware real.")

# 20 Conclusiones -------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Conclusiones", "Lo que nos dejó el proyecto", "Tres ideas para quedarnos.")
concl = [("01", "El orden de arranque y el remapeo del PIC se ven en pantalla."),
         ("02", "Separar la lógica del juego de su plataforma permite correrlo en dos sistemas."),
         ("03", "La evidencia decide qué afirmamos, no lo que creíamos antes.")]
for i, (n, t) in enumerate(concl):
    x = M + i * 3.99
    tarjeta(s, x, CY, 3.75, CH, AZUL if i == 1 else BLANCO, None if i == 1 else LINEA)
    texto(s, x + 0.35, CY + 0.3, 3.0, 0.8, n, size=36, color=AZUL_CLARO if i == 1 else AZUL, bold=True, spc=-60)
    texto(s, x + 0.35, CY + 1.4, 3.1, 2.6, t, size=19, color=BLANCO if i == 1 else TINTA, bold=True, interlinea=1.25)
notas(s, "Insistimos en que la verificación con evidencia es la que decide qué afirmamos.")

# 21 Cierre -------------------------------------------------------------------
s = lienzo(AZUL)
libre(s, MARCA + "logo_s_blanca.png", 9.5, 1.4, 3.6)
texto(s, M - 0.06, 1.4, 8.5, 2.0, "Gracias", size=112, color=BLANCO, bold=True, spc=-200, interlinea=0.85)
texto(s, M, 3.55, 7, 0.9, "¿Preguntas?", size=36, color=AZUL_CLARO, bold=True)
texto(s, M, 5.15, 4, 0.3, "EQUIPO", size=11, color=AZUL_CLARO, font=MONO, bold=True, spc=120)
texto(s, M, 5.5, 3.6, 1.0, ["Miguel Eduardo Angulo Cantor", "Karol Asley Orjuela Mape"], size=14, color=BLANCO, espacio=3)
texto(s, 4.6, 5.5, 4.0, 1.0, ["Juan David Gómez Rojas", "Sebastián Fernando Revelo Meneses"], size=14, color=BLANCO,
      espacio=3)
texto(s, M, 6.8, 7, 0.3, "Universidad Manuela Beltrán", size=12, color=AZUL_CLARO)
notas(s, "Agradecemos la atención. Estamos listos para preguntas sobre el arranque, el kernel o el juego.")

# 22 Créditos -----------------------------------------------------------------
s = lienzo(FONDO)
encabezado(s, "Anexo", "Créditos de los recursos gráficos", "Todo lo que no es material propio, con su licencia.")
tarjeta(s, M, CY, CW, 3.0)
texto(s, M + 0.5, CY + 0.4, CW - 1.0, 2.4, [
    "Iconos de línea: Lucide 1.69.0, licencia ISC (lucide.dev).",
    "Fantasmas y PAC-MAN: siluetas monocromáticas derivadas de 'ghosts' (OpenGameArt, CC0) y de 'Pac-Man portal icon' (Wikimedia Commons, dominio público).",
    "Logotipo de SereOS: material propio del proyecto.",
    "Diagramas técnicos y capturas: material propio, generado con el repositorio y VirtualBox."],
    size=14, color=TINTA, espacio=10, interlinea=1.3)
notas(s, "Detalle completo con enlaces y licencias en recursos/CREDITOS.md.")

prs.save(OUT)
print("guardado", OUT, "diapositivas", len(prs.slides))
