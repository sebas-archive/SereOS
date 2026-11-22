# -*- coding: utf-8 -*-
"""SereOS 1.0: presentación con recursos gráficos reales.
Sin formas geométricas decorativas: solo texto, fotografías, capturas del proyecto,
diagramas técnicos y arte real de PAC-MAN (ver recursos/CREDITOS.md)."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from PIL import Image

DOC = "/home/t1an/Descargas/sereos02/documentacion"
CAP = DOC + "/capturas"
DIA = DOC + "/diagramas"
REC = DOC + "/presentacion/recursos"
OUT = DOC + "/presentacion/Presentacion_SereOS_Nueva.pptx"

NOCHE = "0D0F16"
PAPEL = "F4EFE3"
TINTA = "14161F"
MENTA = "9AA3B8"
GRIS = "5C6275"
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


def rgb(h):
    return RGBColor.from_string(h)


def lienzo(fondo=PAPEL, imagen=None):
    s = prs.slides.add_slide(BLANK)
    if imagen:
        s.shapes.add_picture(imagen, 0, 0, Inches(W), Inches(H))
    else:
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = rgb(fondo)
    return s


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


def foto(s, ruta, x, y, w=None, h=None):
    """Inserta la imagen dentro de la caja (w, h) sin deformarla."""
    iw, ih = Image.open(ruta).size
    if w and h:
        esc = min(w / iw, h / ih)
    elif w:
        esc = w / iw
    else:
        esc = h / ih
    pw, ph = iw * esc, ih * esc
    px = x + ((w - pw) / 2 if w else 0)
    py = y + ((h - ph) / 2 if (w and h) else 0)
    s.shapes.add_picture(ruta, Inches(px), Inches(py), Inches(pw), Inches(ph))
    return px, py, pw, ph


def etiqueta(s, x, y, txt, color=GRIS):
    texto(s, x, y, 8, 0.3, txt.upper(), size=12, color=color, font=MONO, bold=True)


def titular(s, x, y, w, h, txt, size=40, color=TINTA):
    return texto(s, x, y, w, h, txt, size=size, color=color, font=TITULO, bold=True, interlinea=0.95)


def notas(s, txt):
    s.notes_slide.notes_text_frame.text = txt


ICO = REC + "/iconos/png/"


def icono(s, nombre, color, x, y, h):
    return foto(s, ICO + f"{nombre}_{color}.png", x, y, h=h)


# 01 Portada ------------------------------------------------------------------
s = lienzo(NOCHE)
texto(s, M, 0.7, 6, 0.3, "PROYECTO FINAL DE SISTEMAS OPERATIVOS", size=12, color=MENTA, font=MONO)
texto(s, M - 0.05, 1.5, 8, 2.4, "SereOS", size=150, color=AMARILLO, font=TITULO, bold=True, interlinea=0.85)
texto(s, M, 4.1, 5.6, 1.1, "Un sistema operativo x86 de 32 bits que arranca, dibuja ventanas y se juega.",
      size=22, color=PAPEL, interlinea=1.2)
texto(s, M, 5.9, 5.5, 1.2, [
    "Miguel Eduardo Angulo Cantor",
    "Karol Asley Orjuela Mape",
    "Juan David Gómez Rojas",
    "Sebastián Fernando Revelo Meneses"], size=13, color=PAPEL)
texto(s, 7.6, 5.9, 4.9, 0.3, "Universidad Manuela Beltrán", size=13, color=MENTA, align="r")
texto(s, 7.6, 6.2, 4.9, 0.3, "Noviembre de 2026", size=13, color=MENTA, align="r")
icono(s, "ghost", "amarillo", 10.9, 0.9, 1.1)
notas(s, "Presentamos SereOS, un sistema operativo propio para i686 con escritorio gráfico y un juego integrado. "
         "Todo se compiló desde cero y se probó en Oracle VM VirtualBox.")

# 02 Pregunta -----------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "El problema", GRIS)
texto(s, M, 1.9, 11.6, 3.0, "¿Qué pasa entre GRUB y la primera ventana?", size=72,
      color=TINTA, font=TITULO, bold=True, interlinea=0.95)
texto(s, M, 5.0, 7.0, 1.2,
      "Escribimos el arranque, el kernel, el dibujo de ventanas y un juego, y lo probamos en VirtualBox.",
      size=19, color="3A3F4F", interlinea=1.3)
notas(s, "El planteamiento es responder qué ocurre desde que el gestor de arranque entrega el control hasta que "
         "aparece una interfaz usable.")

# 03 Cifras -------------------------------------------------------------------
s = lienzo(NOCHE)
etiqueta(s, M, 0.7, "SereOS 1.0 en números", MENTA)
titular(s, M, 1.1, 8.0, 1.4, "Un kernel monolítico para i686", size=44, color=PAPEL)
filas = [("7", "capas de arquitectura", AMARILLO),
         ("23", "pasos de inicialización en kernel_main", PAPEL),
         ("25", "comandos en la shell", PAPEL),
         ("35,1", "MiB de imagen ISO", CIAN)]
for i, (num, lab, col) in enumerate(filas):
    y = 2.7 + i * 1.05
    texto(s, M, y, 3.0, 1.0, num, size=66, color=col, font=TITULO, bold=True, anclaje="m")
    texto(s, M + 3.2, y, 4.8, 1.0, lab, size=22, color=PAPEL, anclaje="m")
icono(s, "cpu", "papel", 10.9, 1.0, 1.4)
notas(s, "SereOS es un kernel monolítico que se ejecuta íntegramente en anillo 0. Estas cifras resumen el alcance real.")

# 04 Arquitectura -------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Arquitectura", GRIS)
titular(s, M, 1.1, 4.8, 3.0, "Siete capas que solo miran hacia abajo", size=40)
texto(s, M, 3.7, 4.4, 2.6,
      "Cada capa llama a la de abajo, desde el hardware hasta las aplicaciones. Las aplicaciones "
      "no tienen privilegios propios: comparten el anillo 0 con el kernel.", size=17, color="3A3F4F", interlinea=1.3)
foto(s, DIA + "/d1_arquitectura_capas.png", 5.7, 0.6, w=7.0, h=6.3)
notas(s, "Leemos el diagrama de abajo hacia arriba. No hay separación de privilegios entre aplicaciones y kernel.")

# 05 Arranque -----------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Arranque", GRIS)
titular(s, M, 1.1, 11, 1.0, "Del menú de GRUB al escritorio", size=40)
foto(s, DIA + "/d2_arranque.png", M, 2.3, h=4.6)
foto(s, CAP + "/01_arranque/grub_menu.png", 8.6, 2.4, w=3.95)
texto(s, 8.6, 4.3, 3.95, 0.3, "Menú de GRUB en VirtualBox", size=12, color=GRIS, font=MONO)
texto(s, 8.6, 4.9, 4.0, 1.8, [
    "kernel_main ejecuta 23 pasos en orden.",
    "Sin framebuffer, el sistema cae a la consola de texto."], size=17, color=TINTA, espacio=12, interlinea=1.25)
notas(s, "GRUB carga la imagen Multiboot y salta a boot.s, que prepara la pila y llama a kernel_main. "
         "Si no hay framebuffer, el sistema arranca en modo texto.")

# 06 Interrupciones -----------------------------------------------------------
s = lienzo(NOCHE)
etiqueta(s, M, 0.7, "Núcleo", MENTA)
texto(s, M - 0.05, 1.1, 5.6, 2.2, "100", size=170, color=AMARILLO, font=TITULO, bold=True, interlinea=0.85)
texto(s, M, 3.35, 5, 0.5, "interrupciones por segundo del PIT", size=22, color=PAPEL)
texto(s, M, 4.15, 4.6, 2.2, [
    "El PIC remapeado lleva las IRQ a los vectores 32 a 47.",
    "En VirtualBox, 3 439 ticks tras 34 segundos."], size=17, color=MENTA, espacio=12, interlinea=1.3)
foto(s, DIA + "/d3_interrupciones.png", 6.3, 1.0, w=6.2, h=5.6)
notas(s, "Una interrupción pasa por isr.s hasta interrupt_handler. Si el vector es menor que 32 es una excepción "
         "y el sistema entra en pantalla de error.")

# 07 Memoria ------------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Memoria", GRIS)
texto(s, M - 0.05, 1.1, 6, 2.0, "512", size=150, color=AZUL, font=TITULO, bold=True, interlinea=0.85)
texto(s, M, 3.2, 5, 0.5, "MiB con identidad y páginas PSE", size=22, color=TINTA)
texto(s, M, 3.9, 4.8, 1.6,
      "La dirección virtual es igual a la física, con páginas de 4 MiB. El heap del kernel tiene 8 MiB para kmalloc.",
      size=17, color="3A3F4F", interlinea=1.3)
icono(s, "memory-stick", "azul", M, 5.7, 0.9)
foto(s, DIA + "/d4_mapa_memoria.png", 6.4, 0.7, w=6.2, h=6.1)
notas(s, "La paginación de identidad permite mapear 512 MiB con páginas grandes. El framebuffer que entrega GRUB "
         "cae dentro de esa ventana.")

# 08 Ventanas -----------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Entorno gráfico", GRIS)
titular(s, M, 1.1, 4.6, 2.2, "Varias ventanas, un solo buffer", size=40)
texto(s, M, 3.4, 3.9, 2.4,
      "El compositor dibuja en memoria y copia al framebuffer solo las regiones que cambiaron.",
      size=17, color="3A3F4F", interlinea=1.3)
foto(s, CAP + "/04_aplicaciones/multiventana.png", 6.1, 0.9, w=6.5, h=5.0)
notas(s, "La captura muestra terminal y otra aplicación abiertas a la vez, en VirtualBox.")

# 09 Apps (tres capturas) -----------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Escritorio", GRIS)
titular(s, M, 1.1, 11, 1.0, "Las apps que vienen con SereOS", size=40)
celdas = [(CAP + "/02_escritorio/qemu_menu_launcher.png", "Menú de inicio"),
          (CAP + "/04_aplicaciones/explorador_archivos.png", "Explorador de archivos"),
          (CAP + "/04_aplicaciones/monitor_sistema.png", "Monitor del sistema")]
for i, (ruta, lab) in enumerate(celdas):
    x = M + i * 4.0
    foto(s, ruta, x, 2.5, w=3.7, h=2.8)
    texto(s, x, 5.5, 3.7, 0.3, lab, size=12, color=GRIS, font=MONO)
notas(s, "Todas las aplicaciones son ventanas del mismo compositor. Las capturas son de VirtualBox.")

# 10 Terminal -----------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Terminal", GRIS)
titular(s, M, 1.1, 5, 1.6, "Una shell de 25 comandos", size=40)
texto(s, M, 2.9, 4.9, 2.3, [
    "$ help        lista los comandos",
    "$ sysinfo     resumen del sistema",
    "$ div0        división por cero"], size=15, color=TINTA, font=MONO, interlinea=1.4)
texto(s, M, 5.0, 4.8, 1.0, "La misma shell atiende la ventana gráfica y la consola VGA de respaldo.",
      size=17, color="3A3F4F", interlinea=1.3)
foto(s, CAP + "/03_terminal/cmd_sysinfo_version.png", 6.2, 0.9, w=6.3, h=5.4)
notas(s, "La shell se comparte entre la terminal gráfica y la consola de texto. div0 sirve para probar la IDT.")

# 11 Comandos (dos capturas) --------------------------------------------------
s = lienzo(NOCHE)
etiqueta(s, M, 0.7, "Terminal", MENTA)
titular(s, M, 1.1, 5, 1.2, "Comandos que dan información", size=40, color=PAPEL)
texto(s, M, 2.5, 3.9, 2.0, "help lista lo disponible y dmesg muestra el registro del arranque, "
      "con cada paso del kernel.", size=17, color=MENTA, interlinea=1.3)
celdas = [(CAP + "/03_terminal/cmd_help.png", "help"),
          (CAP + "/03_terminal/cmd_dmesg.png", "dmesg")]
for i, (ruta, lab) in enumerate(celdas):
    x = 6.0 + i * 3.5
    foto(s, ruta, x, 2.2, w=3.3, h=2.5)
    texto(s, x, 4.9, 3.3, 0.3, lab, size=12, color=MENTA, font=MONO)
notas(s, "Las salidas son reales, tomadas en VirtualBox. dmesg reproduce el registro de inicialización del kernel.")

# 12 PAC-MAN ------------------------------------------------------------------
s = lienzo(AMARILLO)
etiqueta(s, M, 0.7, "PAC-MAN SereOS", TINTA)
foto(s, CAP + "/05_pacman_sereos_vbox/05_partida_dots_fantasmas.png", M, 1.5, w=6.0, h=4.6)
texto(s, M, 6.3, 6, 0.3, "Partida en VirtualBox", size=12, color=TINTA, font=MONO)
titular(s, 7.5, 1.4, 5.1, 1.0, "Un juego como aplicación nativa", size=40, color=TINTA)
texto(s, 7.5, 2.7, 4.9, 2.2, [
    "El juego se compila como libpacman.a y el kernel lo ejecuta como una aplicación más.",
    "Tiene su propio Makefile, pruebas y un contrato de plataforma."], size=19, color=TINTA, espacio=14,
    interlinea=1.3)
icono(s, "ghost", "tinta", 7.5, 5.2, 0.9)
notas(s, "PAC-MAN SereOS se compila como biblioteca y el kernel la ejecuta como una aplicación más.")

# 13 PAC-MAN pantallas --------------------------------------------------------
s = lienzo(AMARILLO)
etiqueta(s, M, 0.7, "PAC-MAN SereOS", TINTA)
titular(s, M, 1.1, 8.5, 1.0, "De la portada al fin de partida", size=40, color=TINTA)
trio = [(CAP + "/05_pacman_sereos_vbox/02_attract.png", "Pantalla de inicio"),
        (CAP + "/05_pacman_sereos_vbox/03_menu_principal.png", "Menú principal"),
        (CAP + "/05_pacman_sereos_vbox/12_game_over.png", "Fin de partida")]
for i, (ruta, lab) in enumerate(trio):
    x = M + i * 4.0
    foto(s, ruta, x, 2.5, w=3.7, h=2.8)
    texto(s, x, 5.5, 3.7, 0.3, lab, size=14, color=TINTA, font=MONO)
notas(s, "El juego pasa por las mismas pantallas en VirtualBox: inicio, menú, partida y fin de partida.")

# 14 Errores ------------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Errores y modo texto", GRIS)
titular(s, M, 1.1, 11, 1.0, "Cuando algo falla, se ve en pantalla", size=40)
foto(s, CAP + "/03_terminal/panico_div0.png", M, 2.4, w=5.7, h=3.9)
texto(s, M, 6.45, 5.7, 0.3, "Pánico por división entre cero (div0)", size=12, color=GRIS, font=MONO)
foto(s, CAP + "/03_terminal/modo_texto_sysinfo.png", 6.85, 2.4, w=5.7, h=3.9)
texto(s, 6.85, 6.45, 5.7, 0.3, "Modo texto con sysinfo, sin framebuffer", size=12, color=GRIS, font=MONO)
notas(s, "El pánico se activa desde la shell con div0 y muestra los registros del momento del fallo. El modo texto "
         "aparece cuando GRUB no entrega un framebuffer.")

# 15 Dos plataformas ----------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "El juego", GRIS)
titular(s, M, 1.1, 11, 1.0, "Una lógica, dos plataformas", size=40)
foto(s, DIA + "/d5_arquitectura_juego.png", M, 2.2, h=4.6)
texto(s, 8.4, 2.4, 4.2, 3.8, [
    "El núcleo y el render no conocen SereOS ni SDL.",
    "El contrato pac_platform.h lo implementan SereOS y Linux.",
    "Linux se usa solo para probar el juego en desarrollo."], size=18, color=TINTA, espacio=18, interlinea=1.3)
notas(s, "El juego tiene una lógica común y dos adaptadores: uno para Linux con SDL2 y otro para SereOS.")

# 16 ISO ----------------------------------------------------------------------
s = lienzo(NOCHE)
etiqueta(s, M, 0.7, "Construcción", MENTA)
foto(s, DIA + "/d6_pipeline_iso.png", M, 1.4, w=8.1)
texto(s, 9.4, 1.5, 3.4, 1.4, "35,1", size=110, color=AMARILLO, font=TITULO, bold=True, interlinea=0.85)
texto(s, 9.4, 3.0, 3.4, 0.5, "MiB de sereos.iso", size=20, color=PAPEL)
texto(s, 9.4, 3.8, 3.4, 2.0, [
    "36 835 328 bytes.",
    "Ocho pasos con make. El arranque en VirtualBox sigue siendo manual."],
    size=17, color=MENTA, espacio=12, interlinea=1.3)
icono(s, "disc-3", "papel", 9.4, 5.6, 0.9)
notas(s, "El Makefile compila el kernel con gcc -m32 y nasm, enlaza el juego como libpacman.a y genera la ISO "
         "con grub-mkrescue.")

# 17 Pruebas ------------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Pruebas", GRIS)
titular(s, M, 1.1, 11, 1.0, "Qué verificamos y dónde", size=40)
pruebas = [("24", "pruebas en VirtualBox"),
           ("209", "comprobaciones de make test del juego"),
           ("2", "pruebas de ratón en QEMU con la misma ISO")]
for i, (num, lab) in enumerate(pruebas):
    y = 2.45 + i * 1.05
    texto(s, M, y, 2.2, 0.95, num, size=60, color=AZUL if i == 0 else TINTA, font=TITULO, bold=True, anclaje="m")
    texto(s, M + 2.5, y, 5.6, 0.95, lab, size=20, color=TINTA, anclaje="m", interlinea=1.15)
icono(s, "check-circle", "azul", 9.9, 2.5, 0.9)
texto(s, 9.3, 3.8, 3.4, 2.0, [
    "[OK] paginación",
    "identidad, PSE 4 MiB",
    "[OK] planificador",
    "round-robin listo"], size=14, color=TINTA, font=MONO, interlinea=1.35)
notas(s, "El arnés automático de QEMU no se repitió, así que no presentamos sus resultados como propios.")

# 18 Limitaciones -------------------------------------------------------------
s = lienzo(NOCHE)
etiqueta(s, M, 0.7, "Limitaciones", MENTA)
titular(s, M, 1.1, 11, 1.0, "Lo que no probamos ni hicimos", size=40, color=PAPEL)
texto(s, M, 2.6, 5.0, 0.5, "No probado", size=28, color=AMARILLO, font=TITULO, bold=True)
texto(s, M, 3.2, 5.0, 2.0, ["Sonido audible de la SB16", "Apagado y reinicio",
                            "Redimensionado de ventanas", "Hardware físico"],
      size=20, color=PAPEL, espacio=12, interlinea=1.2)
texto(s, M, 5.5, 5.0, 0.5, "No implementado", size=28, color=ROJO, font=TITULO, bold=True)
texto(s, M, 6.05, 6.0, 0.8, ["Multitarea preemptiva y anillo 3", "Llamadas, disco, red, USB y UEFI"],
      size=18, color=PAPEL, espacio=6, interlinea=1.2)
icono(s, "hard-drive", "papel", 9.6, 2.6, 1.6)
notas(s, "Los pendientes son parte del resultado. Tampoco se probó en hardware real.")

# 19 Conclusiones -------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Conclusiones", GRIS)
concl = ["El orden de arranque y el remapeo del PIC se ven en pantalla.",
         "Separar la lógica del juego de su plataforma permite correrlo en dos sistemas.",
         "La evidencia decide qué afirmamos, no lo que creíamos antes."]
for i, c in enumerate(concl):
    y = 1.5 + i * 1.75
    texto(s, M, y, 1.2, 1.2, f"{i + 1}", size=80, color=AZUL, font=TITULO, bold=True)
    texto(s, M + 1.6, y + 0.15, 10.2, 1.3, c, size=30, color=TINTA, font=TITULO, bold=True, interlinea=1.05)
notas(s, "Insistimos en que la verificación con evidencia es la que decide qué afirmamos.")

# 20 Cierre -------------------------------------------------------------------
s = lienzo(AMARILLO)
texto(s, M - 0.05, 0.9, 11.5, 2.2, "¿Preguntas?", size=120, color=TINTA, font=TITULO, bold=True, interlinea=0.85)
texto(s, M, 4.4, 6.5, 1.6, [
    "Miguel Eduardo Angulo Cantor",
    "Karol Asley Orjuela Mape",
    "Juan David Gómez Rojas",
    "Sebastián Fernando Revelo Meneses"], size=18, color=TINTA, espacio=2)
icono(s, "ghost", "tinta", 10.9, 4.4, 1.2)
notas(s, "Agradecemos la atención. Estamos listos para preguntas sobre el arranque, el kernel o el juego.")

# 21 Créditos -----------------------------------------------------------------
s = lienzo(PAPEL)
etiqueta(s, M, 0.7, "Anexo", GRIS)
titular(s, M, 1.1, 11, 1.0, "Créditos de los recursos gráficos", size=36)
texto(s, M, 2.3, 11.7, 4.5, [
    "Iconos (ghost, cpu, memory-stick, disc-3, check-circle, hard-drive): Lucide 1.69.0, licencia ISC.",
    "Diagramas, capturas y el resto de imágenes: material propio del proyecto."],
    size=16, color=TINTA, espacio=10, interlinea=1.25)
notas(s, "Detalle completo con enlaces y licencias en recursos/CREDITOS.md.")

prs.save(OUT)
print("guardado", OUT, "diapositivas", len(prs.slides))
