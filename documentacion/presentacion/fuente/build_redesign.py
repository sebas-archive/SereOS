# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_CONNECTOR
from pptx.oxml.ns import qn
from lxml import etree
from PIL import Image, ImageEnhance

os.makedirs(SCRATCH, exist_ok=True)
prs = Presentation()
prs.slide_width = Inches(W); prs.slide_height = Inches(H)
prs.slide_master.background.fill.solid()
prs.slide_master.background.fill.fore_color.rgb = RGBColor.from_string(BG)
BLANK = prs.slide_layouts[6]
TOTAL = 16
state = {"n": 0}

def rgb(h): return RGBColor.from_string(h)

def tb(s, x, y, w, h, paras, size=SZ_CUERPO, color=TXT, font=FONT_TEXT, bold=False,
       align="l", anchor="t", after=0, line_sp=None):
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    items = paras if isinstance(paras, list) else [paras]
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        if after: p.space_after = Pt(after)
        if line_sp: p.line_spacing = line_sp
        r = p.add_run(); r.text = it
        f = r.font; f.size = Pt(max(size, SZ_MINIMO)); f.bold = bold; f.name = font
        f.color.rgb = rgb(color)
    return box

def pic(s, path, x, y, w=None, h=None):
    iw, ih = Image.open(path).size; ar = iw / ih
    if w and h:
        if w / h > ar: pw, ph = h * ar, h
        else: pw, ph = w, w / ar
    elif w: pw, ph = w, w / ar
    else: pw, ph = h * ar, h
    s.shapes.add_picture(path, Inches(x), Inches(y), Inches(pw), Inches(ph))
    return x, y, pw, ph

def notes(s, text):
    s.notes_slide.notes_text_frame.text = text

def transition(s):
    el = s._element
    tr = etree.Element(qn("p:transition")); tr.set("spd", "med")
    etree.SubElement(tr, qn("p:fade"))
    clr = el.find(qn("p:clrMapOvr"))
    (clr.addnext(tr) if clr is not None else el.insert(1, tr))

def slide(kicker=None, title=None, numbered=True):
    s = prs.slides.add_slide(BLANK)
    state["n"] += 1
    if kicker:
        tb(s, MARGEN, 0.36, 9, 0.3, kicker, size=SZ_PIE, color=GRIS, font=FONT_MONO)
    if title:
        tb(s, MARGEN, 0.72, 11.9, 0.9, title, size=SZ_TITULO, color=TXT, bold=True)
    if numbered:
        tb(s, W - MARGEN - 1.2, 6.98, 1.2, 0.3, f"{state['n']:02d}/{TOTAL}", size=SZ_PIE,
           color=GRIS, font=FONT_MONO, align="r")
    transition(s)
    return s

def dark_cover(path_in, path_out):
    im = Image.open(path_in).convert("RGB")
    im = ImageEnhance.Brightness(im).enhance(0.28)
    im.save(path_out)
    return path_out

# 01 Portada ------------------------------------------------------------
s = prs.slides.add_slide(BLANK); state["n"] += 1
cover = dark_cover(CAP + "/02_escritorio/escritorio_principal.png", SCRATCH + "/portada_oscura.png")
iw, ih = Image.open(cover).size
bgw = W; bgh = W * ih / iw
s.shapes.add_picture(cover, Inches(0), Inches((H - bgh) / 2), Inches(bgw), Inches(bgh))
tb(s, MARGEN, 0.7, 9, 0.3, "PROYECTO FINAL · SISTEMAS OPERATIVOS", size=SZ_PIE, color=GRIS, font=FONT_MONO)
tb(s, MARGEN, 2.7, 10, 1.8, "SereOS", size=SZ_PORTADA, color=TXT, bold=True)
tb(s, MARGEN, 4.55, 8.6, 1.0, "Sistema operativo x86 de 32 bits con escritorio gráfico y PAC-MAN integrado.",
   size=24, color=TXT)
tb(s, MARGEN, 6.25, 9, 0.35, "Universidad Mariana (UMB)  ·  Noviembre de 2026", size=SZ_PIE, color=GRIS)
tb(s, MARGEN, 6.62, 9, 0.35, "Integrantes: [nombres del equipo]", size=SZ_PIE, color=GRIS)
transition(s)
notes(s, "Presentamos SereOS, un sistema operativo propio para i686 con escritorio gráfico y un juego integrado. "
         "Todo lo que mostramos se compiló desde cero y se probó en Oracle VM VirtualBox.")

# 02 Problema -----------------------------------------------------------
s = slide("01  PROBLEMA Y OBJETIVO", "De GRUB a la primera ventana")
tb(s, MARGEN, 2.1, 5.2, 0.3, "PREGUNTA", size=SZ_PIE, color=GRIS, font=FONT_MONO)
tb(s, MARGEN, 2.5, 5.6, 2.0, "¿Qué ocurre entre el salto de GRUB al kernel y la aparición de una ventana?",
   size=28, color=TXT, line_sp=1.1)
tb(s, 7.0, 2.1, 5.2, 0.3, "OBJETIVO", size=SZ_PIE, color=GRIS, font=FONT_MONO)
tb(s, 7.0, 2.5, 5.6, 2.0, "Construir un sistema propio que arranque en VirtualBox y ejecute un juego.",
   size=28, color=TXT, line_sp=1.1)
notes(s, "El planteamiento es responder qué pasa entre el gestor de arranque y una interfaz usable. "
         "El objetivo fue construir ese recorrido completo y no solo estudiarlo en teoría.")

# 03 Qué es SereOS (captura completa) ------------------------------------
s = slide("02  VISIÓN GENERAL", None)
pic(s, CAP + "/02_escritorio/escritorio_principal.png", W - 10.0, 0, h=H)
tb(s, MARGEN, 0.72, 2.5, 0.9, "SereOS", size=SZ_TITULO, color=TXT, bold=True)
tb(s, MARGEN, 1.75, 2.4, 3.6, "Versión 1.0. Kernel monolítico para i686, con escritorio, terminal y aplicaciones propias.",
   size=SZ_CUERPO, color=TXT)
tb(s, MARGEN, 6.9, 2.6, 0.3, "Escritorio en VirtualBox", size=SZ_PIE, color=GRIS)
notes(s, "SereOS es un kernel monolítico que se ejecuta íntegramente en anillo 0. "
         "Esta es una captura real del escritorio, sin retoques.")

# 04 Arquitectura (diagrama d1) ------------------------------------------
s = slide("03  ARQUITECTURA", "Siete capas, un kernel monolítico")
pic(s, DIA + "/d1_arquitectura_capas.png", MARGEN, 1.85, h=5.0)
tb(s, 7.2, 2.0, 5.4, 2.8, ["Cada capa usa la inferior, de hardware a aplicaciones.",
                             "Las aplicaciones no tienen privilegios propios: comparten el anillo 0 con el kernel."],
   size=SZ_CUERPO, color=TXT, after=14)
notes(s, "Leemos el diagrama de abajo hacia arriba. La capa de núcleo arranca el sistema y las aplicaciones "
         "dependen de todas las capas inferiores. No hay separación de privilegios entre aplicaciones y kernel.")

# 05 Arranque (d2 + GRUB) ------------------------------------------------
s = slide("04  ARRANQUE", "Del arranque al escritorio")
pic(s, DIA + "/d2_arranque.png", MARGEN, 1.85, h=5.0)
_, gy, _, gh = pic(s, CAP + "/01_arranque/grub_menu.png", 7.2, 1.95, w=4.8)
tb(s, 7.2, gy + gh + 0.12, 5.4, 0.3, "Menú de GRUB en VirtualBox", size=SZ_PIE, color=GRIS)
tb(s, 7.2, gy + gh + 0.7, 5.4, 1.6, ["kernel_main inicializa 23 pasos en orden.",
                            "Sin framebuffer, arranca la consola de texto."], size=SZ_CUERPO, color=TXT, after=10)
notes(s, "GRUB carga la imagen Multiboot y salta a boot.s, que prepara la pila y llama a kernel_main. "
         "Si no hay framebuffer, el sistema usa la segunda entrada de GRUB y arranca en modo texto.")

# 06 Interrupciones (d3 + cifra) -----------------------------------------
s = slide("05  NÚCLEO", "Interrupciones y temporización")
pic(s, DIA + "/d3_interrupciones.png", MARGEN, 1.85, h=4.95)
tb(s, 7.6, 2.0, 5.0, 1.6, "100 Hz", size=SZ_HERO, color=ACENTO, bold=True)
tb(s, 7.6, 3.75, 5.0, 2.8, ["Frecuencia del PIT: IRQ 0. El PIC remapeado lleva las IRQ a los vectores 32 a 47.",
                             "3 439 ticks tras 34 s en VirtualBox."], size=SZ_CUERPO, color=TXT, after=12)
notes(s, "Una interrupción pasa por isr.s hasta interrupt_handler. Si el vector es menor que 32 es una excepción "
         "y el sistema entra en pantalla de error. El temporizador marca 100 ticks por segundo.")

# 07 Memoria (d4 + cifra) ------------------------------------------------
s = slide("05  NÚCLEO", "Memoria: identidad con PSE")
pic(s, DIA + "/d4_mapa_memoria.png", MARGEN, 1.85, h=5.0)
tb(s, 7.6, 2.1, 5.3, 1.3, "512 MiB", size=80, color=ACENTO, bold=True)
tb(s, 7.6, 3.7, 5.0, 2.8, ["Dirección virtual igual a la física, con páginas PSE de 4 MiB.",
                             "Heap del kernel de 8 MiB para kmalloc."], size=SZ_CUERPO, color=TXT, after=12)
notes(s, "La paginación de identidad permite mapear 512 MiB con páginas grandes. El framebuffer que entrega GRUB "
         "cae dentro de esa ventana de direcciones.")

# 08 Ventanas (captura completa) -----------------------------------------
s = slide("06  ENTORNO GRÁFICO", None)
pic(s, CAP + "/04_aplicaciones/multiventana.png", 5.5, 0.9, h=5.9)
tb(s, MARGEN, 1.0, 4.2, 2.6, "Varias ventanas con foco, sobre un compositor propio.",
   size=28, color=TXT, line_sp=1.1)
tb(s, MARGEN, 6.45, 4.4, 0.3, "Captura en VirtualBox", size=SZ_PIE, color=GRIS)
notes(s, "El compositor dibuja las ventanas en un buffer y copia al framebuffer solo las regiones que cambian. "
         "La captura muestra terminal y otra aplicación abiertas a la vez.")

# 09 Terminal (código + captura) -----------------------------------------
s = slide("07  TERMINAL", "Una shell de 25 comandos")
tb(s, MARGEN, 2.0, 5.2, 0.3, "COMANDOS", size=SZ_PIE, color=GRIS, font=FONT_MONO)
tb(s, MARGEN, 2.5, 5.4, 2.4, ["help      lista los comandos",
                               "sysinfo   resumen del sistema",
                               "div0      división por cero"],
   size=SZ_CODIGO, color=TXT, font=FONT_MONO, after=10)
tb(s, MARGEN, 4.9, 5.2, 1.4, "La misma shell atiende la terminal gráfica y la consola VGA de respaldo.",
   size=SZ_CUERPO, color=TXT)
_, sy, _, sh = pic(s, CAP + "/03_terminal/cmd_sysinfo_version.png", 6.4, 1.9, w=6.2)
tb(s, 6.4, sy + sh + 0.12, 6.2, 0.3, "Salida de sysinfo en VirtualBox", size=SZ_PIE, color=GRIS)
notes(s, "La shell está compartida entre la terminal gráfica y la consola de texto. "
         "Mostramos tres comandos: help, sysinfo y div0, que sirve para probar la IDT.")

# 10 PAC-MAN (captura + texto) -------------------------------------------
s = slide("08  PAC-MAN SEREOS", "Un juego como aplicación nativa")
pic(s, CAP + "/05_pacman_sereos_vbox/05_partida_dots_fantasmas.png", MARGEN, 1.85, w=7.0)
tb(s, MARGEN, 6.5, 7.0, 0.3, "Partida en VirtualBox", size=SZ_PIE, color=GRIS)
tb(s, 8.4, 2.0, 4.3, 3.0, ["Se enlaza al kernel como libpacman.a.",
                            "Tiene su propio Makefile, pruebas y contrato de plataforma."],
   size=SZ_CUERPO, color=TXT, after=14)
notes(s, "PAC-MAN SereOS se compila como biblioteca y el kernel la ejecuta como una aplicación más. "
         "Lo importante es que el juego no depende del kernel para su lógica.")

# 11 PAC-MAN arquitectura (d5) -------------------------------------------
s = slide("09  PAC-MAN SEREOS", "Una lógica, dos plataformas")
pic(s, DIA + "/d5_arquitectura_juego.png", MARGEN, 1.85, h=5.0)
tb(s, 7.6, 2.0, 5.0, 3.0, ["El núcleo y el render no conocen SereOS ni SDL.",
                            "El contrato pac_platform.h lo implementan SereOS y Linux.",
                            "Linux se usa solo para pruebas."], size=SZ_CUERPO, color=TXT, after=14)
notes(s, "El juego tiene una lógica común y dos adaptadores. El adaptador de Linux permite desarrollar y probar "
         "con SDL2, y el de SereOS produce libpacman.a.")

# 12 ISO (d6 + cifra) ----------------------------------------------------
s = slide("10  CONSTRUCCIÓN", "De las fuentes a la ISO")
pic(s, DIA + "/d6_pipeline_iso.png", MARGEN, 1.85, w=8.4)
tb(s, 9.6, 2.0, 3.2, 1.2, "35,1 MiB", size=40, color=ACENTO, bold=True)
tb(s, 9.6, 2.95, 3.2, 2.5, ["sereos.iso, 36 835 328 bytes.", "Pasos 1 a 8 con make. El arranque en VirtualBox es manual."],
   size=SZ_CUERPO, color=TXT, after=10)
notes(s, "El Makefile compila el kernel con gcc -m32 y nasm, enlaza el juego como libpacman.a y genera la ISO "
         "con grub-mkrescue. Antes de cargarla en VirtualBox se valida la cabecera Multiboot.")

# 13 Pruebas (cifras + registro) -----------------------------------------
s = slide("11  PRUEBAS", "Qué se verificó")
cols = [("24", "pruebas en VirtualBox"), ("209", "comprobaciones de make test del juego"),
        ("2", "pruebas de ratón en QEMU, con la misma ISO")]
for i, (n, lab) in enumerate(cols):
    x = MARGEN + i * 4.1
    tb(s, x, 2.0, 3.8, 1.6, n, size=SZ_HERO, color=ACENTO if i == 0 else TXT, bold=True)
    tb(s, x, 3.7, 3.6, 0.9, lab, size=SZ_CUERPO, color=TXT)
tb(s, MARGEN, 5.1, 11.5, 0.3, "Registro del puerto serie, VirtualBox", size=SZ_PIE, color=GRIS)
tb(s, MARGEN, 5.5, 11.9, 0.4, "[OK] Paginacion activada (identidad, PSE 4 MiB)", size=SZ_CODIGO, color=TXT, font=FONT_MONO)
tb(s, MARGEN, 5.95, 11.9, 0.4, "[OK] Planificador cooperativo round-robin listo", size=SZ_CODIGO, color=TXT, font=FONT_MONO)
notes(s, "Las pruebas en VirtualBox cubren arranque, terminal, aplicaciones y el juego. El arnés automático de QEMU "
         "no se repitió, así que no presentamos sus resultados como propios.")

# 14 Limitaciones (dos columnas) -----------------------------------------
s = slide("12  LIMITACIONES", "Lo que queda sin probar o sin hacer")
tb(s, MARGEN, 2.0, 5.5, 0.3, "SIN PROBAR", size=SZ_PIE, color=GRIS, font=FONT_MONO)
tb(s, MARGEN, 2.5, 5.5, 3.0, ["Sonido audible de la SB16.", "Apagado y reinicio.",
                              "Redimensionado de ventanas.", "Hardware físico."],
   size=SZ_CUERPO, color=TXT, after=12)
tb(s, 7.0, 2.0, 5.5, 0.3, "NO IMPLEMENTADO", size=SZ_PIE, color=GRIS, font=FONT_MONO)
tb(s, 7.0, 2.5, 5.5, 3.0, ["Multitarea preemptiva y anillo 3.", "Llamadas al sistema.",
                           "Disco, red, USB y UEFI."],
   size=SZ_CUERPO, color=TXT, after=12)
notes(s, "Los pendientes son parte del resultado. El planificador es cooperativo, así que una tarea que no cede el "
         "control congela el escritorio. Tampoco se probó en hardware real.")

# 15 Conclusiones --------------------------------------------------------
s = slide("13  CONCLUSIONES", "Lo que aprendimos")
tb(s, MARGEN, 2.2, 11.8, 1.2, "Arranque y PIC: decisiones visibles en pantalla.",
   size=SZ_LEAD, color=TXT, line_sp=1.1)
tb(s, MARGEN, 3.7, 11.8, 1.2, "Lógica separada de plataforma: el juego corre en dos sistemas.",
   size=SZ_LEAD, color=TXT, line_sp=1.1)
tb(s, MARGEN, 5.2, 11.8, 1.2, "La evidencia manda sobre los avances antiguos.",
   size=SZ_LEAD, color=TXT, line_sp=1.1)
notes(s, "Estos son los tres aprendizajes que nos dejó el proyecto. Insistimos en que la verificación con evidencia "
         "es la que decide qué afirmamos.")

# 16 Cierre --------------------------------------------------------------
s = slide(None, None, numbered=True)
tb(s, MARGEN, 2.2, 11, 1.8, "Gracias", size=SZ_HERO, color=TXT, bold=True)
tb(s, MARGEN, 4.1, 11, 0.8, "¿Preguntas?", size=36, color=ACENTO, bold=True)
tb(s, MARGEN, 6.5, 8, 0.3, "SereOS 1.0  ·  Sistemas Operativos  ·  UMB 2026", size=SZ_PIE, color=GRIS, font=FONT_MONO)
notes(s, "Agradecemos la atención. Estamos listos para preguntas sobre el arranque, el kernel o el juego.")

out = OUT + "/Presentacion_Final_SereOS.pptx"
prs.save(out)
print("saved", out, "slides", len(prs.slides))
