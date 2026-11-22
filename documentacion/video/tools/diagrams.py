"""Diagramas animables de la escena de arquitectura (SVG -> PNG 1920x1080).

Solo muestran componentes implementados en el código de SereOS:
  kernel/, boot/, drivers/, memory/, process/, graphics/, gui/, shell/, apps/.
"""
import os, subprocess

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "diagramas")
W, H = 1920, 1080
BG = "#0a0d14"
FG = "#e8edf5"
MUTED = "#7d8799"
BLUE = "#4f8cff"
GREEN = "#5ee0b8"
AMBER = "#f5b54a"
CYAN = "#48c7e6"
CARD = "#131a26"
LINE = "#2a3446"

FONT = "Inter, Noto Sans, sans-serif"


def head(title, sub):
    return f'''
<text x="120" y="120" font-family="{FONT}" font-size="26" font-weight="600" fill="{BLUE}" letter-spacing="4">{title}</text>
<text x="120" y="176" font-family="{FONT}" font-size="54" font-weight="700" fill="{FG}">{sub}</text>'''


def box(x, y, w, h, label, sub="", color=BLUE, fs=30):
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="{CARD}" '
         f'stroke="{color}" stroke-width="3"/>')
    s += (f'<text x="{x + w/2}" y="{y + h/2 - (6 if sub else -10)}" text-anchor="middle" '
          f'font-family="{FONT}" font-size="{fs}" font-weight="600" fill="{FG}">{label}</text>')
    if sub:
        s += (f'<text x="{x + w/2}" y="{y + h/2 + 30}" text-anchor="middle" '
              f'font-family="{FONT}" font-size="22" fill="{MUTED}">{sub}</text>')
    return s


def arrow(x1, y1, x2, y2, color=MUTED):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="3" '
            f'marker-end="url(#ah)"/>')


DEFS = (f'<defs><marker id="ah" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">'
        f'<path d="M0,0 L12,6 L0,12 z" fill="{MUTED}"/></marker>'
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="#0b1020"/><stop offset="1" stop-color="{BG}"/></linearGradient></defs>')


def svg(body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'{DEFS}<rect width="{W}" height="{H}" fill="url(#bg)"/>{body}</svg>')


def d1_capas():
    b = head("ARQUITECTURA", "Seis capas: cada una usa la inferior")
    rows = [
        ("Aplicaciones", "Terminal · Archivos · Monitor · PAC-MAN SereOS · Acerca de", BLUE),
        ("Escritorio", "Ventanas · dock · lanzador ≡ · barra superior", GREEN),
        ("Gráficos", "framebuffer 1024×768×32 · fuente · texto · cursor", CYAN),
        ("Servicios", "RAMFS · planificador cooperativo · kmalloc", AMBER),
        ("Núcleo", "GDT · IDT · PIC 8259 · PIT 100 Hz · paginación PSE", BLUE),
        ("Arranque y hardware", "GRUB / Multiboot 1 · teclado y ratón PS/2 · RTC · SB16 / PC speaker", MUTED),
    ]
    y = 300
    for label, sub, color in rows:
        b += box(260, y, 1400, 100, label, sub, color, fs=32)
        y += 118
    return svg(b)


def d2_arranque():
    b = head("ARRANQUE", "De GRUB al escritorio")
    steps = [
        ("GRUB 2", "menú y carga\nMultiboot", BLUE),
        ("boot.s", "cabecera Multiboot\npila inicial", BLUE),
        ("kernel_main", "inicialización\nen orden", GREEN),
        ("Splash", "logo oficial\nSereOS", CYAN),
        ("Escritorio", "GUI_LOOP", AMBER),
    ]
    x = 120
    for i, (l, s, c) in enumerate(steps):
        b += box(x, 470, 300, 170, l, "", c, fs=34)
        for k, line in enumerate(s.split("\n")):
            b += (f'<text x="{x + 150}" y="{520 + k*34}" text-anchor="middle" font-family="{FONT}" '
                  f'font-size="22" fill="{MUTED}">{line}</text>')
        if i < len(steps) - 1:
            b += arrow(x + 300, 555, x + 350, 555)
        x += 370
    b += (f'<text x="120" y="740" font-family="{FONT}" font-size="26" fill="{FG}">'
          f'kernel_main inicializa en orden: GDT → IDT/PIC → PIT → teclado → ratón → RTC → framebuffer</text>')
    b += (f'<text x="120" y="784" font-family="{FONT}" font-size="26" fill="{FG}">'
          f'→ paginación PSE → heap → RAMFS → planificador → interrupciones → motor gráfico → GUI</text>')
    b += (f'<text x="120" y="860" font-family="{FONT}" font-size="22" fill="{MUTED}">'
          f'Alternativa: entrada «modo texto (diagnóstico)» en el mismo GRUB.</text>')
    return svg(b)


def d3_interrupciones():
    b = head("INTERRUPCIONES", "Del hardware a su controlador")
    b += box(120, 330, 380, 110, "Teclado PS/2", "IRQ 1", BLUE)
    b += box(120, 480, 380, 110, "Ratón PS/2", "IRQ 12", GREEN)
    b += box(120, 630, 380, 110, "PIT 8253", "IRQ 0 · 100 Hz", AMBER)
    b += box(680, 430, 330, 170, "PIC 8259", "remapeado a 32–47", CYAN)
    b += box(1190, 430, 330, 170, "IDT", "256 entradas", BLUE)
    b += box(1640, 330, 200, 110, "Driver", "input.c", GREEN, fs=26)
    b += box(1640, 630, 200, 110, "Scheduler", "tick", AMBER, fs=26)
    for y in (385, 535, 685):
        b += arrow(500, y, 680, 515 if y != 685 else 515)
    b += arrow(1010, 515, 1190, 515)
    b += arrow(1520, 500, 1640, 385)
    b += arrow(1520, 520, 1640, 685)
    b += (f'<text x="120" y="850" font-family="{FONT}" font-size="24" fill="{MUTED}">'
          f'La GDT define los segmentos; la IDT dirige cada vector a su manejador (isr.s / idt.c).</text>')
    return svg(b)


def d4_memoria():
    b = head("MEMORIA Y PROCESOS", "Identidad PSE, heap y tareas cooperativas")
    b += box(120, 330, 480, 220, "Paginación PSE", "identidad 1:1 hasta 512 MiB\npáginas de 4 MiB", BLUE)
    b += box(720, 330, 480, 220, "Marcos físicos", "asignador de 4 KiB\nallocator propio", CYAN)
    b += box(1320, 330, 480, 220, "kmalloc", "heap del kernel\nkfree", GREEN)
    b += arrow(600, 440, 720, 440)
    b += arrow(1200, 440, 1320, 440)
    b += box(120, 640, 700, 200, "Planificador", "round-robin cooperativo\nhasta 32 tareas", AMBER)
    b += box(900, 640, 900, 200, "Tareas de la GUI", "terminal · files · monitor · game\nla tarea cede el turno con cada paso", BLUE)
    b += arrow(820, 740, 900, 740)
    return svg(b)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("d1_capas", d1_capas), ("d2_arranque", d2_arranque),
                     ("d3_interrupciones", d3_interrupciones), ("d4_memoria", d4_memoria)):
        svg_path = os.path.join(OUT, name + ".svg")
        png_path = os.path.join(OUT, name + ".png")
        with open(svg_path, "w") as f:
            f.write(fn())
        subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H), "-o", png_path, svg_path], check=True)
        print("ok", png_path)
