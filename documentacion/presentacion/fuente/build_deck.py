# -*- coding: utf-8 -*-
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree
from PIL import Image

ROOT = "/home/t1an/Descargas/sereos02"
DOC = ROOT + "/documentacion"
CAP = DOC + "/capturas"
LOGO = ROOT + "/sistema operativo/assets/logo/official_logo.png"
OUT = DOC + "/presentacion"
os.makedirs(OUT, exist_ok=True)

BLUE = "004EFD"; INK = "0E1420"; GRAPH = "1A1E26"; PAPER = "F5F6F8"
WHITE = "FFFFFF"; MUTED = "6B7280"; MUTED_D = "9AA3B2"; LINE = "C9CED8"
AMBER = "F2A93B"; SOFT = "E8EEFF"; INK_TXT = "111827"

TITLE_F = "Fira Sans Condensed"; BODY_F = "Fira Sans"; MONO_F = "DejaVu Sans Mono"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
W = 13.333; H = 7.5; M = 0.6
TOTAL = 20
counter = {"n": 0}

def rgb(h): return RGBColor.from_string(h)

def bg(slide, color):
    f = slide.background.fill
    f.solid(); f.fore_color.rgb = rgb(color)

def text(slide, x, y, w, h, s, size=16, color=INK_TXT, bold=False, font=BODY_F,
         align="l", anchor="t", spacing=None, italic=False):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        if spacing: p.space_after = Pt(spacing)
        r = p.add_run(); r.text = line
        f = r.font; f.size = Pt(size); f.bold = bold; f.italic = italic
        f.name = font; f.color.rgb = rgb(color)
    return tb

def rect(slide, x, y, w, h, fill=None, line=None, lw=0.75):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.shadow.inherit = False
    if fill: s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    else: s.fill.background()
    if line: s.line.color.rgb = rgb(line); s.line.width = Pt(lw)
    else: s.line.fill.background()
    return s

def rect_text(slide, x, y, w, h, lines, fill=None, line=None, color=INK_TXT, size=13,
              mono_second=False, align="l", anchor="m", lw=0.75):
    s = rect(slide, x, y, w, h, fill, line, lw)
    tf = s.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = tf.margin_bottom = Inches(0.05)
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    for i, line_ in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        r = p.add_run(); r.text = line_
        is_mono = mono_second and i == 1
        r.font.name = MONO_F if is_mono else BODY_F
        r.font.size = Pt(size - 2 if is_mono else size)
        r.font.bold = (i == 0)
        r.font.color.rgb = rgb(color)
    return s

def line(slide, x1, y1, x2, y2, color=INK_TXT, w=1.0, arrow=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color); c.line.width = Pt(w)
    if arrow:
        ln = c.line._get_or_add_ln()
        t = etree.SubElement(ln, qn("a:tailEnd")); t.set("type", "triangle"); t.set("w", "med"); t.set("len", "med")
    return c

def pic(slide, path, x, y, w=None, h=None):
    """Insert picture scaled to fit inside box (w,h) keeping aspect; returns (x,y,w,h) actually used."""
    iw, ih = Image.open(path).size
    ar = iw / ih
    if w and h:
        if w / h > ar: W_, H_ = h * ar, h
        else: W_, H_ = w, w / ar
    elif w: W_, H_ = w, w / ar
    else: W_, H_ = h * ar, h
    px = x + ((w - W_) / 2 if w else 0)
    py = y + ((h - H_) / 2 if h else 0)
    slide.shapes.add_picture(path, Inches(px), Inches(py), Inches(W_), Inches(H_))
    return px, py, W_, H_

def pic_frame(slide, path, x, y, w, h, color=LINE):
    px, py, pw, ph = pic(slide, path, x, y, w, h)
    rect(slide, px, py, pw, ph, None, color, 0.75)
    return px, py, pw, ph

def transition(slide):
    el = slide._element
    tr = etree.Element(qn("p:transition")); tr.set("spd", "med")
    etree.SubElement(tr, qn("p:fade"))
    clr = el.find(qn("p:clrMapOvr"))
    if clr is not None: clr.addnext(tr)
    else: el.insert(1, tr)

def new_slide(bgc, dark=False, label="", title="", footer_dark=None):
    s = prs.slides.add_slide(BLANK)
    bg(s, bgc)
    counter["n"] += 1
    n = counter["n"]
    fg = PAPER if dark else INK_TXT
    sub = MUTED_D if dark else MUTED
    if label:
        text(s, M, 0.42, 9, 0.3, label, size=10.5, color=BLUE if not dark else AMBER, font=MONO_F)
    if title:
        text(s, M, 0.72, 12.1, 0.8, title, size=30, color=fg, bold=True, font=TITLE_F)
    text(s, M, 7.02, 8, 0.25, "SereOS 1.0  ·  Proyecto final de Sistemas Operativos", size=9.5, color=sub, font=MONO_F)
    text(s, W - M - 1, 7.02, 1, 0.25, f"{n:02d} / {TOTAL}", size=9.5, color=sub, font=MONO_F, align="r")
    transition(s)
    return s, fg, sub

def caption(slide, s, x, y, w, color=MUTED, size=10.5):
    text(slide, x, y, w, 0.4, s, size=size, color=color, font=BODY_F, italic=False)

# ---------- 01 Portada ----------
s, fg, sub = new_slide(PAPER, label="PROYECTO FINAL — SISTEMAS OPERATIVOS")
# remove the default footer-number? keep consistent
text(s, M, 2.1, 7.4, 1.6, "SereOS", size=110, color=INK_TXT, bold=True, font=TITLE_F)
text(s, M, 3.85, 6.6, 1.0,
     "Sistema operativo x86 de 32 bits con escritorio gráfico y PAC-MAN SereOS integrado.",
     size=20, color=GRAPH, font=BODY_F)
rect(s, M, 5.15, 0.9, 0.06, fill=BLUE)
text(s, M, 5.4, 7, 0.4, "Noviembre de 2026", size=14, color=MUTED, font=BODY_F)
lx = 8.45; ly = 1.25; ls = 4.2
pic(s, LOGO, lx, ly, ls, ls)

# ---------- 02 Introducción ----------
s, fg, sub = new_slide(PAPER, label="01  INTRODUCCIÓN", title="Del arranque al escritorio, sin capas ocultas")
text(s, M, 2.0, 5.6, 3.0,
     ["Un sistema operativo se estudia a menudo por sus conceptos y por ejemplos recortados. "
      "Quedan sin respuesta preguntas prácticas: qué ocurre entre el salto de GRUB al kernel "
      "y la aparición de una ventana, o cómo se coordinan el controlador de interrupciones, "
      "el temporizador y el teclado."],
     size=17, color=GRAPH, spacing=0)
text(s, M, 4.35, 5.6, 1.6,
     ["SereOS construye ese recorrido completo: kernel propio, drivers, escritorio y una "
      "aplicación interactiva que se ejecuta dentro del propio sistema."],
     size=17, color=GRAPH)
# right: objectives as numbered typographic rows
x0 = 7.0; y0 = 2.0
text(s, x0, y0 - 0.02, 5.5, 0.3, "OBJETIVO GENERAL", size=10.5, color=BLUE, font=MONO_F)
text(s, x0, y0 + 0.3, 5.7, 1.4,
     "Diseñar, implementar y validar un sistema operativo propio de 32 bits que arranque desde "
     "una ISO con GRUB, y desarrollar PAC-MAN SereOS como aplicación nativa.",
     size=16, color=INK_TXT)
rect(s, x0, 4.1, 5.7, 0.012, fill=LINE)
text(s, x0, 4.3, 5.5, 0.3, "CRITERIO DE VALIDACIÓN", size=10.5, color=BLUE, font=MONO_F)
text(s, x0, 4.6, 5.7, 1.4,
     "Arranque en Oracle VM VirtualBox 7.2.22 con la ISO recompilada desde cero, "
     "y registro de cada prueba con su evidencia.",
     size=16, color=INK_TXT)

# ---------- 03 Evolución ----------
s, fg, sub = new_slide(INK, dark=True, label="02  VISIÓN GENERAL", title="Tres versiones, una misma base de código")
# timeline horizontal
ty = 3.05
line(s, M, ty, W - M, ty, color=MUTED_D, w=1.0)
events = [
    (M + 0.0,  "0.1", "23 oct", "Cabecera Multiboot, terminal VGA, Makefile con ISO", "5 archivos · 230 líneas"),
    (M + 4.1,  "0.2", "30 oct", "GDT propia, IDT, PIC, PIT a 100 Hz, teclado PS/2, shell", "15 archivos · 674 líneas"),
    (M + 8.2,  "1.0", "20 nov", "Ratón, RTC, serie, SB16, memoria, tareas, RAMFS, escritorio, PAC-MAN", "93 archivos · 63 777 líneas"),
]
for x, v, d, desc, nums in events:
    rect(s, x, ty - 0.09, 0.18, 0.18, fill=AMBER if v == "1.0" else BLUE)
    text(s, x, ty - 0.75, 3.8, 0.5, f"v{v}", size=30, color=PAPER, bold=True, font=TITLE_F)
    text(s, x + 1.05, ty - 0.66, 2.5, 0.3, d, size=12, color=MUTED_D, font=MONO_F)
    text(s, x, ty + 0.35, 3.6, 1.2, desc, size=14, color=PAPER)
    text(s, x, ty + 1.45, 3.6, 0.4, nums, size=12, color=AMBER if v == "1.0" else MUTED_D, font=MONO_F)
# key numbers strip
rect(s, M, 5.6, W - 2 * M, 0.012, fill=GRAPH)
stats = [("25", "comandos en la shell"), ("4", "aplicaciones nativas"), ("1024×768", "framebuffer de 32 bits"), ("100 Hz", "frecuencia del PIT")]
for i, (v, l) in enumerate(stats):
    x = M + i * 3.05
    text(s, x, 5.8, 2.9, 0.6, v, size=28, color=PAPER, bold=True, font=TITLE_F)
    text(s, x, 6.42, 2.9, 0.4, l, size=12, color=MUTED_D)

# ---------- 04 Arquitectura general ----------
s, fg, sub = new_slide(PAPER, label="03  ARQUITECTURA GENERAL", title="Siete capas, un kernel monolítico")
rows = [
    ("Aplicaciones", "capa 1", [("Terminal", "terminal_app"), ("Archivos", "filemanager"), ("Monitor y Acerca de", ""), ("PAC-MAN", "libpacman.a")]),
    ("Escritorio", "capa 2", [("Compositor", "dock y barra"), ("Ventanas", "window"), ("Cursor", "cursor, splash"), ("Tema y UI", "theme, ui")]),
    ("Gráficos", "capa 3", [("Framebuffer", "LFB 1024×768"), ("Backbuffer", "regiones sucias"), ("Motor 2D", "graphics"), ("Tipografía", "text")]),
    ("Subsistemas", "capa 4", [("Memoria", "page, kmalloc"), ("Tareas", "task, scheduler"), ("RAMFS", "fs"), ("Shell", "25 comandos")]),
    ("Drivers", "capa 5", [("PIT", "timer"), ("PS/2", "teclado y ratón"), ("RTC y COM1", "rtc, serial"), ("SB16", "audio, sb16")]),
    ("Núcleo", "capa 6", [("Arranque", "boot.s e isr.s"), ("GDT e IDT", "gdt, idt, PIC"), ("Log y pánico", "log, panic"), ("Apagado", "shutdown")]),
    ("Hardware", "capa 7", [("GRUB 2", "Multiboot 1"), ("CPU i686", "modo protegido"), ("RAM y video", "256 MiB, LFB"), ("Periféricos", "PIC, PIT, PS/2")]),
]
top = 1.9; rh = 0.58; gap = 0.08
label_w = 2.35; cell_w = 2.05; cgap = 0.1
x_start = M
for r, (name, cap, cells) in enumerate(rows):
    y = top + r * (rh + gap)
    fill_label = INK if r in (0, 1) else (BLUE if r in (5,) else GRAPH)
    text(s, x_start, y, label_w, rh, [name, cap], size=13, color=INK_TXT, bold=False, anchor="m")
    # label bold first line
    for i, (t1, t2) in enumerate(cells):
        cx = x_start + label_w + 0.2 + i * (cell_w + cgap)
        rect(s, cx, y, cell_w, rh, fill=WHITE, line=GRAPH if r in (0, 6) else LINE, lw=0.75)
        tb = text(s, cx + 0.1, y + 0.06, cell_w - 0.2, rh - 0.1,
                  [t1] + ([t2] if t2 else []), size=12, color=INK_TXT, bold=False, anchor="m", align="c")
        tb.text_frame.paragraphs[0].runs[0].font.bold = True
        if t2:
            tb.text_frame.paragraphs[1].runs[0].font.name = MONO_F
            tb.text_frame.paragraphs[1].runs[0].font.size = Pt(10)
            tb.text_frame.paragraphs[1].runs[0].font.color.rgb = rgb(MUTED)
    # use arrow on right edge between rows (usa a)
caption(s, "Cada fila usa la inmediatamente inferior. Subtítulos: módulos (.c) de cada carpeta.", M, 6.62, 12, size=10.5)
# bold layer names
for r, (name, cap, cells) in enumerate(rows):
    pass

# ---------- 05 Proceso de arranque ----------
s, fg, sub = new_slide(INK, dark=True, label="04  PROCESO DE ARRANQUE", title="Del arranque al escritorio")
steps = [
    ("BIOS", "Encuentra la ISO y carga el sector de arranque de grub-mkrescue"),
    ("GRUB 2", "Lee grub.cfg, muestra el menú (2 s) y carga el kernel en Multiboot 1"),
    ("boot.s", "Cabecera Multiboot, pila de 64 KiB, empuja EAX y EBX y llama a kernel_main"),
    ("kernel_main", "Inicialización en 23 pasos, cada uno con [OK] en el registro del kernel"),
]
bx = M; by = 2.0; bw = 2.7; bh = 1.85; bg_gap = 0.4
for i, (t1, t2) in enumerate(steps):
    x = bx + i * (bw + bg_gap)
    rect(s, x, by, bw, bh, fill=GRAPH, line=None)
    text(s, x + 0.2, by + 0.18, bw - 0.4, 0.3, f"0{i+1}", size=11, color=AMBER, font=MONO_F)
    text(s, x + 0.2, by + 0.5, bw - 0.4, 0.4, t1, size=18, color=PAPER, bold=True, font=TITLE_F)
    text(s, x + 0.2, by + 0.95, bw - 0.4, 0.9, t2, size=12, color=MUTED_D)
    if i < len(steps) - 1:
        line(s, x + bw + 0.04, by + bh / 2, x + bw + bg_gap - 0.04, by + bh / 2, color=MUTED_D, w=1.25, arrow=True)
# decision layout (kernel_main -> decision -> two branches)
k4x = M + 3 * (bw + bg_gap) + bw / 2
line(s, k4x, by + bh, k4x, 4.55, color=MUTED_D, w=1.25)
line(s, k4x, 4.55, 8.36, 4.55, color=MUTED_D, w=1.25, arrow=True)
rect_text(s, 5.4, 4.25, 2.95, 0.6, ["¿Framebuffer válido?"], fill=None, line=AMBER, color=PAPER, size=14, align="c", lw=1.25)
line(s, 6.2, 4.85, 4.45, 5.6, color=MUTED_D, w=1.25, arrow=True)
line(s, 7.6, 4.85, 9.25, 5.6, color=MUTED_D, w=1.25, arrow=True)
rect_text(s, 2.9, 5.6, 3.1, 0.8, ["Sí: escritorio SereOS", "entrada por defecto de GRUB"], fill=GRAPH, color=PAPER, size=13, align="c")
rect_text(s, 7.7, 5.6, 3.1, 0.8, ["No: consola de texto", "segunda entrada del menú"], fill=GRAPH, color=PAPER, size=13, align="c")
caption(s, "Si el número mágico de Multiboot no es el esperado, boot_fail escribe [FAIL] y detiene la máquina.", M, 6.62, 12, color=MUTED_D)
# captures on left-top? keep composition: no captures here, kept diagrammatic

# ---------- 06 Kernel ----------
s, fg, sub = new_slide(PAPER, label="05  KERNEL", title="Un kernel construido desde cero")
items = [
    ("GDT", "Cinco descriptores en modelo plano. Base 0, límite 4 GiB. Anillo 0 para el kernel."),
    ("IDT", "32 vectores de excepción y 16 de IRQ. Puertas de interrupción de 32 bits, anillo 0."),
    ("PIC 8259", "Remapeado: IRQ 0–15 a los vectores 32–47, para no chocar con las excepciones."),
    ("PIT", "1 193 182 Hz divididos por 11 931: 100 interrupciones por segundo."),
    ("Log y pánico", "Anillo de 96 entradas con marca de tiempo. Las excepciones muestran una pantalla de error."),
]
y = 2.0
for t1, t2 in items:
    text(s, M, y, 2.2, 0.4, t1, size=17, color=BLUE, bold=True, font=TITLE_F)
    text(s, M + 2.35, y + 0.03, 4.2, 0.9, t2, size=14, color=INK_TXT)
    rect(s, M, y + 0.92, 6.55, 0.01, fill=LINE)
    y += 0.98
pic_frame(s, CAP + "/03_terminal/panico_div0.png", 7.35, 1.95, 5.38, 4.04, color=GRAPH)
caption(s, "Excepción de división por cero (vector 0), provocada con el comando div0. VirtualBox.", 7.35, 6.12, 5.4)

# ---------- 07 Interrupciones ----------
s, fg, sub = new_slide(PAPER, label="06  SUBSISTEMAS", title="Interrupciones y temporización")
# flow diagram horizontal, native
fy = 2.35
nodes = [
    (M, "IRQ o excepción", "El procesador entrega el vector"),
    (M + 2.75, "boot/isr.s", "Empuja el vector y guarda registros"),
    (M + 5.5, "interrupt_handler()", "Decide según el vector"),
]
for x, t1, t2 in nodes:
    rect_text(s, x, fy, 2.4, 1.0, [t1, t2], fill=WHITE, line=GRAPH, color=INK_TXT, size=13, align="c")
for i in range(2):
    x = nodes[i][0] + 2.4
    line(s, x + 0.04, fy + 0.5, nodes[i + 1][0] - 0.04, fy + 0.5, color=GRAPH, w=1.25, arrow=True)
# branches from handler
hx = M + 5.5 + 2.4
rect_text(s, hx + 0.55, fy - 0.85, 3.4, 0.75, ["Vector < 32", "panic_exception(): no regresa"], fill=None, line=GRAPH, color=INK_TXT, size=12, align="c")
rect_text(s, hx + 0.55, fy + 1.45, 3.4, 1.05, ["Vector ≥ 32", "contador de ticks, manejador de irq_install()", "EOI al PIC maestro y, si IRQ ≥ 8, al esclavo"], fill=None, line=GRAPH, color=INK_TXT, size=12, align="c")
line(s, hx + 0.1, fy + 0.5, hx + 0.55, fy - 0.45, color=GRAPH, w=1.25, arrow=True)
line(s, hx + 0.1, fy + 0.5, hx + 0.55, fy + 1.95, color=GRAPH, w=1.25, arrow=True)
# facts row
fy2 = 5.3
rect(s, M, fy2 - 0.2, W - 2 * M, 0.01, fill=LINE)
facts = [("100 Hz", "PIT, IRQ 0"), ("3 439", "ticks tras 34 s de funcionamiento (VirtualBox)"), ("512", "posiciones de la cola circular de entrada")]
for i, (v, l) in enumerate(facts):
    x = M + i * 4.05
    text(s, x, fy2 + 0.05, 3.8, 0.6, v, size=30, color=BLUE, bold=True, font=TITLE_F)
    text(s, x, fy2 + 0.75, 3.7, 0.7, l, size=12.5, color=INK_TXT)
caption(s, "Diagrama propio a partir de boot/isr.s y kernel/idt.c.", M, 6.7, 12)

# ---------- 08 Memoria y planificación ----------
s, fg, sub = new_slide(INK, dark=True, label="06  SUBSISTEMAS", title="Memoria y planificación cooperativa")
text(s, M, 2.0, 5.2, 0.4, "Marcos de 4 KiB, paginación de identidad con PSE y heap kmalloc.", size=16, color=PAPER)
text(s, M, 2.6, 5.2, 0.8, "Planificador round-robin cooperativo: cada tarea ejecuta un paso corto y regresa.", size=16, color=PAPER)
text(s, M, 3.6, 5.2, 0.4, "Una tarea que no cede el control congela el escritorio.", size=14, color=MUTED_D)
# memory bar diagram
bx0 = M; bw_ = 12.13; by0 = 4.9
text(s, bx0, by0 - 0.45, 8, 0.3, "MAPA DE DIRECCIONES (PAGINACIÓN DE IDENTIDAD)", size=10.5, color=AMBER, font=MONO_F)
rect(s, bx0, by0, bw_ * 0.7, 0.7, fill=BLUE)
text(s, bx0 + 0.2, by0 + 0.12, 9, 0.5, "0 – 512 MiB · dirección virtual = física · páginas PSE de 4 MiB", size=13, color=WHITE, font=BODY_F, anchor="m")
rect(s, bx0 + bw_ * 0.7, by0, bw_ * 0.3, 0.7, fill=GRAPH, line=MUTED_D, lw=0.5)
text(s, bx0 + bw_ * 0.7 + 0.2, by0 + 0.12, 3.5, 0.5, "Rango donde GRUB coloca el framebuffer", size=12, color=PAPER, anchor="m")
text(s, bx0, by0 + 0.95, 12, 0.5, "Según el capítulo 5.1 del informe: identidad hasta 512 MiB, más el rango del framebuffer.",
     size=10.5, color=MUTED_D)
caption(s, "", M, 6.62, 8)

# ---------- 09 Terminal ----------
s, fg, sub = new_slide(PAPER, label="07  TERMINAL", title="Shell de 25 comandos, en la terminal gráfica")
pic_frame(s, CAP + "/03_terminal/cmd_help.png", M, 1.8, 6.2, 4.65, color=GRAPH)
caption(s, "Salida de help en VirtualBox. Muestra la parte final de la lista; la ventana se desplaza.", M, 6.6, 6.4, size=10)
cmds = [
    ("help, about, version, sysinfo", "ayuda y resumen del sistema"),
    ("mem, free, ticks", "memoria, heap y ticks del PIT"),
    ("dmesg", "registro del kernel con marcas de tiempo"),
    ("date, time", "reloj CMOS"),
    ("div0", "división por cero para probar la IDT"),
    ("audio, beep, audiotest", "backend de audio y pruebas"),
    ("ls, cd, mkdir, touch, rm", "operaciones sobre el RAMFS"),
    ("cat, write", "leer y escribir archivos"),
]
text(s, 8.5, 1.8, 4.2, 0.3, "COMANDOS SELECCIONADOS", size=10.5, color=BLUE, font=MONO_F)
yy = 2.15
for c, d in cmds:
    text(s, 8.5, yy, 4.25, 0.3, c, size=12, color=INK_TXT, font=MONO_F, bold=False)
    text(s, 8.5, yy + 0.27, 4.25, 0.3, d, size=11.5, color=MUTED)
    yy += 0.55
caption(s, "Tabla 10 del informe; lista completa de 25 comandos.", 8.5, 6.6, 4.3, size=10)

# ---------- 10 Escritorio ----------
s, fg, sub = new_slide(INK, dark=True, label="08  ENTORNO GRÁFICO", title="Escritorio, barra superior y dock")
pic_frame(s, CAP + "/02_escritorio/escritorio_principal.png", M, 1.8, 6.13, 4.6, color=GRAPH)
caption(s, "Escritorio real en VirtualBox. Barra superior y dock con cinco accesos.", M, 6.55, 7.3, color=MUTED_D, size=10)
text(s, 8.4, 1.85, 4.3, 0.3, "BARRA SUPERIOR", size=10.5, color=AMBER, font=MONO_F)
text(s, 8.4, 2.2, 4.3, 0.9, "Logotipo con menú, título de la ventana activa, memoria usada, tiempo de encendido, fecha y hora.", size=14, color=PAPER)
text(s, 8.4, 3.55, 4.3, 0.3, "DOCK", size=10.5, color=AMBER, font=MONO_F)
text(s, 8.4, 3.9, 4.3, 1.2, "Archivos, terminal, monitor del sistema, juego y Acerca de. Muestra un tooltip al pasar el ratón.", size=14, color=PAPER)
text(s, 8.4, 5.25, 4.3, 0.3, "CURSOR", size=10.5, color=AMBER, font=MONO_F)
text(s, 8.4, 5.6, 4.3, 0.8, "Puntero dibujado por software sobre el framebuffer, con versión ampliada.", size=14, color=PAPER)

# ---------- 11 Ventanas ----------
s, fg, sub = new_slide(PAPER, label="08  ENTORNO GRÁFICO", title="Ventanas con foco y varias aplicaciones a la vez")
pic_frame(s, CAP + "/04_aplicaciones/multiventana.png", M, 1.85, 8.2, 4.45, color=GRAPH)
caption(s, "Captura en VirtualBox: varias ventanas abiertas a la vez en el compositor.", M, 6.5, 9.1, size=10)
text(s, 10.2, 2.0, 2.6, 0.3, "COMPOSITOR", size=10.5, color=BLUE, font=MONO_F)
text(s, 10.2, 2.35, 2.6, 1.8, "Dibuja las ventanas en un backbuffer y copia al framebuffer solo las regiones modificadas.", size=14, color=INK_TXT)
text(s, 10.2, 4.3, 2.6, 0.3, "LÍMITES", size=10.5, color=BLUE, font=MONO_F)
text(s, 10.2, 4.65, 2.6, 1.8, "Hasta 8 ventanas. El redimensionado no se ejercitó en la validación.", size=14, color=INK_TXT)

# ---------- 12 Aplicaciones ----------
s, fg, sub = new_slide(PAPER, label="09  APLICACIONES", title="Aplicaciones nativas verificadas")
pic_frame(s, CAP + "/04_aplicaciones/explorador_archivos.png", M, 1.85, 5.9, 3.4, color=GRAPH)
pic_frame(s, CAP + "/04_aplicaciones/monitor_sistema.png", 6.85, 1.85, 5.9, 3.4, color=GRAPH)
text(s, M, 5.45, 5.9, 0.3, "ARCHIVOS", size=10.5, color=BLUE, font=MONO_F)
text(s, M, 5.75, 5.9, 0.9, "Muestra el RAMFS: los archivos creados desde la terminal, visibles en la aplicación.", size=14, color=INK_TXT)
text(s, 6.85, 5.45, 5.9, 0.3, "MONITOR DEL SISTEMA", size=10.5, color=BLUE, font=MONO_F)
text(s, 6.85, 5.75, 5.9, 0.9, "Memoria, tareas del planificador y contadores de errores del registro del kernel.", size=14, color=INK_TXT)
caption(s, "Capturas en VirtualBox. Acerca de y terminal se documentan en el capítulo 11 del informe.", M, 6.6, 12, size=10)

# ---------- 13 PAC-MAN intro ----------
s, fg, sub = new_slide(INK, dark=True, label="10  PAC-MAN SEREOS", title="Un videojuego como aplicación del sistema")
text(s, M, 2.0, 4.9, 1.6,
     "El juego es un componente con su propio Makefile, sus pruebas y un contrato de plataforma. "
     "SereOS lo consume como biblioteca libpacman.a.", size=16, color=PAPER)
text(s, M, 3.9, 4.9, 1.2,
     "El mismo código se ejecuta en CachyOS con SDL2 durante el desarrollo y dentro de SereOS en la entrega.",
     size=14, color=MUTED_D)
pic_frame(s, CAP + "/05_pacman_sereos_vbox/05_partida_dots_fantasmas.png", 5.9, 1.85, 6.83, 4.6, color=GRAPH)
caption(s, "Partida en VirtualBox, con la interfaz del juego dentro de la ventana de SereOS.", 5.9, 6.55, 6.9, color=MUTED_D, size=10)

# ---------- 14 Arquitectura del juego ----------
s, fg, sub = new_slide(PAPER, label="11  ARQUITECTURA DEL VIDEOJUEGO", title="Lógica, render y plataforma separados")
# diagram
gx = M; gw = 7.6
rect_text(s, gx, 1.9, gw, 1.0, ["Núcleo  ·  src/core", "game.c · game_maze.c · game_entities.c · game_ai.c · game_input.c · game_audio.c"],
          fill=WHITE, line=GRAPH, size=13, mono_second=True)
rect_text(s, gx, 3.2, gw, 0.9, ["Render  ·  src/render", "game_render.c · pac_ui.c · pac_theme.c · arcade_text.c"],
          fill=WHITE, line=GRAPH, size=13, mono_second=True)
rect_text(s, gx, 4.4, gw, 0.7, ["Contrato de plataforma  ·  include/pac_platform.h (ABI 1)"],
          fill=SOFT, line=BLUE, size=13, color=BLUE, lw=1.25)
rect_text(s, gx, 5.4, 3.7, 0.9, ["Adaptador SereOS", "libpacman.a"], fill=WHITE, line=GRAPH, size=13, mono_second=True)
rect_text(s, gx + 3.9, 5.4, 3.7, 0.9, ["Adaptador Linux", "SDL2 · solo pruebas en CachyOS"], fill=WHITE, line=GRAPH, size=13, mono_second=True)
line(s, gx + gw / 2, 2.9, gx + gw / 2, 3.2, color=GRAPH, w=1.25, arrow=True)
line(s, gx + gw / 2, 4.1, gx + gw / 2, 4.4, color=GRAPH, w=1.25, arrow=True)
line(s, gx + 1.85, 5.1, gx + 1.85, 5.4, color=GRAPH, w=1.25, arrow=True)
line(s, gx + 5.75, 5.1, gx + 5.75, 5.4, color=GRAPH, w=1.25, arrow=True)
# right commentary
rx = 8.7
text(s, rx, 1.9, 4.0, 0.3, "REGLAS DE DISEÑO", size=10.5, color=BLUE, font=MONO_F)
text(s, rx, 2.25, 4.0, 1.6, "El núcleo nunca incluye cabeceras de SereOS ni de SDL. Solo conoce el contrato.", size=15, color=INK_TXT)
text(s, rx, 3.6, 4.0, 1.6, "El render dibuja menús, HUD y laberinto con las primitivas del contrato.", size=15, color=INK_TXT)
text(s, rx, 4.95, 4.0, 1.5, "El juego usa punto fijo porque el kernel no inicializa la unidad de coma flotante.", size=15, color=INK_TXT)
caption(s, "Diagrama propio basado en docs/ARCHITECTURE.md y en la estructura de carpetas del componente.", M, 6.5, 12)

# ---------- 15 Demostración del juego ----------
s, fg, sub = new_slide(INK, dark=True, label="12  DEMOSTRACIÓN", title="Mecánicas dentro de SereOS, en VirtualBox")
imgs = [
    ("02_attract.png", "Atracción"),
    ("03_menu_principal.png", "Menú principal"),
    ("03c_instrucciones.png", "Instrucciones"),
    ("05_partida_dots_fantasmas.png", "Partida"),
    ("06_fantasmas_asustados.png", "Fantasmas asustados"),
    ("07_asustados_con_fruta.png", "Asustados con fruta"),
    ("08_captura_de_fantasma.png", "Captura de fantasma"),
    ("12_game_over.png", "Fin de juego"),
]
cw = 2.6; chh = cw * 0.75; cgx = (W - 2 * M - 4 * cw) / 3
for i, (f, cap_) in enumerate(imgs):
    r_, c_ = divmod(i, 4)
    x = M + c_ * (cw + cgx); y = 1.8 + r_ * (chh + 0.5)
    pic_frame(s, CAP + "/05_pacman_sereos_vbox/" + f, x, y, cw, chh, color=GRAPH)
    text(s, x, y + chh + 0.08, cw, 0.3, cap_, size=11.5, color=MUTED_D)
caption(s, "Secuencia de la validación: menús, partida, fantasmas asustados, captura y fin de juego.", M, 6.62, 12, color=MUTED_D, size=10.5)

# ---------- 16 Compilación e ISO ----------
s, fg, sub = new_slide(PAPER, label="13  COMPILACIÓN Y ISO", title="De las fuentes a sereos.iso")
pipe = [
    ("Fuentes", ".c, .s, .h del kernel y de libpacman"),
    ("Ensamblado", "NASM 3.02 (formato elf32)"),
    ("Compilación", "gcc 16.2.1 -m32 -ffreestanding -nostdlib"),
    ("Enlace", "linker.ld y libpacman.a"),
    ("ISO", "grub-mkrescue 2.16 con xorriso"),
]
px_ = M; py_ = 2.0; pw_ = 2.2; pgap = 0.27
for i, (t1, t2) in enumerate(pipe):
    x = px_ + i * (pw_ + pgap)
    rect_text(s, x, py_, pw_, 1.25, [t1, t2], fill=WHITE, line=GRAPH, size=13, align="c")
    if i < len(pipe) - 1:
        line(s, x + pw_ + 0.03, py_ + 0.62, x + pw_ + pgap - 0.03, py_ + 0.62, color=GRAPH, w=1.25, arrow=True)
text(s, M, 3.7, 6, 0.3, "COMANDOS", size=10.5, color=BLUE, font=MONO_F)
text(s, M, 4.02, 5.9, 1.6, ["make clean && make game-clean && make -j8",
                              "sha256sum \"sistema operativo/sereos.iso\""],
     size=12.5, color=INK_TXT, font=MONO_F)
text(s, 6.9, 3.7, 6, 0.3, "ARTEFACTOS VERIFICADOS", size=10.5, color=BLUE, font=MONO_F)
text(s, 6.9, 4.02, 5.8, 1.8,
     ["sereos.iso: 36 835 328 bytes",
      "sha256 ISO: 4fe9ea95…7c96d9",
      "sereos.bin extraído de la ISO coincide con el compilado"],
     size=12.5, color=INK_TXT, font=MONO_F)
caption(s, "No se usó i686-elf-gcc: no estaba instalado. El Makefile compila con gcc -m32 (SEREOS_HOST_GCC).", M, 6.35, 12, color=MUTED, size=11)

# ---------- 17 Ejecución y pruebas ----------
s, fg, sub = new_slide(INK, dark=True, label="14  EJECUCIÓN Y PRUEBAS", title="Validación en Oracle VM VirtualBox")
text(s, M, 1.95, 5.2, 0.3, "MÁQUINA VIRTUAL", size=10.5, color=AMBER, font=MONO_F)
text(s, M, 2.3, 5.2, 2.2,
     ["VirtualBox 7.2.22, BIOS, 256 MiB",
      "Controlador VBoxVGA, Sound Blaster 16",
      "ISO por IDE, COM1 a archivo",
      "Capturas con VBoxManage controlvm screenshotpng"],
     size=14, color=PAPER)
text(s, M, 4.35, 5.2, 0.3, "RESULTADOS", size=10.5, color=AMBER, font=MONO_F)
text(s, M, 4.7, 5.2, 1.6,
     ["24 pruebas en VirtualBox (P04–P18, P21–P29).",
      "2 pruebas de ratón en QEMU con la misma ISO (P19–P20).",
      "make test del juego: 209 comprobaciones sin fallos y 7 pruebas de humo (P30)."],
     size=14, color=PAPER)
text(s, 6.6, 1.95, 6, 0.3, "REGISTRO DEL PUERTO SERIE (SESIÓN DEL JUEGO)", size=10.5, color=AMBER, font=MONO_F)
rect(s, 6.6, 2.3, 6.13, 3.95, fill=INK, line=GRAPH, lw=0.75)
log = [
    "[OK] Arranque Multiboot verificado (GRUB 2)",
    "[OK] GDT propia: 5 segmentos (kernel y usuario)",
    "[OK] IDT: 32 excepciones + 16 IRQ (PIC remapeado a 32-47)",
    "[OK] Temporizador PIT a 100 Hz (IRQ 0)",
    "[OK] Teclado PS/2 con eventos (IRQ 1)",
    "[OK] Raton PS/2 con eventos (IRQ 12)",
    "[OK] Framebuffer grafico 1024x768x32 validado",
    "[OK] Paginacion activada (identidad, PSE 4 MiB)",
    "[OK] Planificador cooperativo round-robin listo",
    "[OK] Interrupciones habilitadas",
]
text(s, 6.85, 2.5, 5.7, 3.9, log, size=11.5, color=PAPER, font=MONO_F, spacing=6)
caption(s, "Extracto de serial_vbox_sesion2_juego.log, sin modificar. Pruebas P19–P20 en QEMU; P01–P03 y P30 en CachyOS.", 6.6, 6.4, 6.2, color=MUTED_D, size=10)

# ---------- 18 Resultados ----------
s, fg, sub = new_slide(PAPER, label="15  RESULTADOS", title="Lo implementado y lo que queda pendiente")
text(s, M, 1.95, 5.8, 0.3, "IMPLEMENTADO Y PROBADO", size=10.5, color=BLUE, font=MONO_F)
ok = ["Arranque GRUB y Multiboot 1", "GDT, IDT y excepciones", "PIC y PIT a 100 Hz",
      "Teclado, RTC y puerto serie; ratón probado en QEMU", "Marcos, paginación PSE y heap",
      "Planificador cooperativo", "RAMFS y shell de 25 comandos",
      "Escritorio, ventanas, dock y topbar", "PAC-MAN SereOS integrado"]
text(s, M, 2.35, 5.8, 4.4, ok, size=14, color=INK_TXT, spacing=5)
rect(s, 6.75, 1.95, 0.012, 4.6, fill=LINE)
text(s, 7.1, 1.95, 5.6, 0.3, "PENDIENTE O NO IMPLEMENTADO", size=10.5, color=BLUE, font=MONO_F)
pend = ["Reproducción audible de la SB16 (solo detección)",
        "Apagado y reinicio desde el menú (no ejecutados)",
        "Redimensionado de ventanas (no ejercitado)",
        "Comer la fruta en VirtualBox (escena de CachyOS)",
        "Multitarea preemptiva, anillo 3 y llamadas al sistema",
        "Disco, red, USB, UEFI y hardware físico"]
text(s, 7.1, 2.35, 5.6, 4.4, pend, size=14, color=INK_TXT, spacing=5)
caption(s, "Fuente: informe de validación, secciones 5.3 y 8 y capítulo 19.", M, 6.7, 12, size=10.5)

# ---------- 19 Conclusiones ----------
s, fg, sub = new_slide(INK, dark=True, label="16  CONCLUSIONES", title="Lo que enseñó construirlo")
text(s, M, 2.0, 7.2, 1.8,
     "SereOS es mínimo pero completo en su recorrido: desde el arranque hasta una aplicación interactiva que usa el temporizador, el teclado y el framebuffer.",
     size=19, color=PAPER)
rows_c = [
    ("El orden importa", "La inicialización de kernel_main sigue las dependencias: serie y registro primero, luego GDT e IDT."),
    ("Una frontera limpia", "El juego compila en CachyOS y en SereOS porque solo depende del contrato pac_platform.h."),
    ("La documentación envejece", "Varias discrepancias entre avances y código, por ejemplo la pila (16 a 64 KiB) y los comandos (8 a 25)."),
]
y = 4.1
for t1, t2 in rows_c:
    text(s, M, y, 3.0, 0.4, t1, size=15, color=AMBER, bold=True, font=TITLE_F)
    text(s, M + 3.2, y + 0.02, 8.1, 0.8, t2, size=14, color=PAPER)
    y += 0.85
caption(s, "Discrepancias completas en el anexo F del informe.", M, 6.7, 12, color=MUTED_D, size=10.5)

# ---------- 20 Cierre ----------
s, fg, sub = new_slide(PAPER, label="")
text(s, M, 2.3, 9, 1.6, "GRACIAS", size=88, color=INK_TXT, bold=True, font=TITLE_F)
text(s, M, 4.0, 9, 0.8, "SereOS", size=36, color=BLUE, bold=True, font=TITLE_F)
rect(s, M, 4.95, 0.9, 0.06, fill=BLUE)
pic(s, LOGO, 9.0, 1.45, 3.5, 3.5)

prs.save(OUT + "/Presentacion_Final_SereOS.pptx")
print("slides:", len(prs.slides), "saved")
