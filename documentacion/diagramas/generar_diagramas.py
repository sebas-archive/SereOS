# -*- coding: utf-8 -*-
"""Regenera los seis diagramas tecnicos de SereOS (SVG y PNG).

Uso:  python3 generar_diagramas.py            (desde la carpeta diagramas/)
Salida: d1..d6 en .svg y .png (2400 px de ancho). Falla si algun diagrama tiene
flechas sobre cajas, etiquetas solapadas o texto fuera de su caja.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_diagrama import Diagrama, medir  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
M = "mono"


def d1():
    d = Diagrama("d1_arquitectura_capas", "Arquitectura por capas de SereOS 1.0",
                 "Subtítulos: módulos (.c) de cada carpeta. Las flechas del margen derecho indican «usa a».")
    capas = [
        ("Aplicaciones", "violeta", [
            ("Terminal", "terminal_app", "violeta"), ("Archivos", "filemanager", "violeta"),
            ("Monitor", "y Acerca de", "violeta"), ("PAC-MAN", "libpacman.a", "violeta")]),
        ("Escritorio", "violeta", [
            ("Compositor", "dock y barra", "violeta"), ("Ventanas", "window", "violeta"),
            ("Cursor", "cursor, splash", "violeta"), ("Tema y UI", "theme, ui", "violeta")]),
        ("Gráficos", "turquesa", [
            ("Framebuffer", "LFB 1024x768", "turquesa"), ("Backbuffer", "regiones sucias", "turquesa"),
            ("Motor 2D", "graphics", "turquesa"), ("Tipografía", "text", "turquesa")]),
        ("Subsistemas", "verde", [
            ("Memoria", "page, kmalloc", "verde"), ("Tareas", "task, scheduler", "verde"),
            ("RAMFS", "fs", "verde"), ("Shell", "25 comandos", "verde")]),
        ("Drivers", "ambar", [
            ("PIT", "timer", "ambar"), ("PS/2", "teclado y ratón", "ambar"),
            ("RTC y COM1", "rtc, serial", "ambar"), ("SB16", "audio, sb16", "ambar")]),
        ("Núcleo", "azul", [
            ("Arranque", "boot.s e isr.s", "rojo"), ("GDT e IDT", "gdt, idt, PIC", "azul"),
            ("Log y pánico", "log, panic", "rojo"), ("Apagado", "shutdown", "azul")]),
        ("Hardware", "gris", [
            ("GRUB 2", "Multiboot 1", "gris"), ("CPU i686", "modo protegido", "gris"),
            ("RAM y video", "256 MiB, LFB", "gris"), ("Periféricos", "PIC, PIT, PS/2", "gris")]),
    ]
    y = 120
    H, GAP = 100, 20
    xs = [260, 480, 700, 920]
    centros = []
    for i, (nombre, col, items) in enumerate(capas):
        d.caja(f"capa{i}", 40, y, 200, H, col, nombre, [f"capa {i + 1}"], thick=True, tsize=22, lsize=21)
        for j, (t, sub, c) in enumerate(items):
            d.caja(f"c{i}_{j}", xs[j], y, 200, H, c, t, [sub], tsize=22, lsize=21)
        centros.append(y + H / 2)
        y += H + GAP
    for a, b in zip(centros, centros[1:]):
        d.linea(1140, a + 6, 1140, b - 6)
    return d


def d2():
    d = Diagrama("d2_arranque", "Secuencia de arranque de SereOS desde la ISO",
                 "Fuente: boot/boot.s, kernel/kernel.c y grub.cfg. El orden de los 23 pasos es el de kernel_main().")
    hitos = [("BIOS", "firmware"), ("GRUB 2", "Multiboot 1"), ("boot.s", "pila 64 KiB"),
             ("kernel", "23 pasos"), ("splash", "logo, ~1 s"), ("gui_run", "escritorio")]
    xs = [40 + i * 192 for i in range(6)]
    for i, (t, s) in enumerate(hitos):
        d.caja(f"h{i}", xs[i], 120, 160, 100, "rojo" if i < 4 else ("turquesa" if i == 4 else "violeta"),
               t, [s], num="ABCDEF"[i], tsize=22, lsize=21)
    for i in range(5):
        d.flecha(f"h{i}", f"h{i + 1}", recta=True)
    # cabecera de la cuadricula, unida a "kernel"
    d.caja("cab", 340, 280, 720, 80, "azul", "kernel_main() inicializa en este orden", [], tsize=24, thick=True)
    d.flecha("h3", "cab", "b", "t", fb=(xs[3] + 80 - 340) / 720, recta=True)
    pasos = [("serial", "rojo"), ("terminal", "rojo"), ("klog", "rojo"), ("Multiboot", "rojo"), ("GDT", "rojo"), ("IDT + PIC", "rojo"),
             ("input", "ambar"), ("PIT", "ambar"), ("teclado", "ambar"), ("ratón", "ambar"), ("RTC", "ambar"), ("speaker", "ambar"),
             ("framebuffer", "turquesa"), ("marcos", "verde"), ("heap", "verde"), ("paginación", "verde"), ("RAMFS", "verde"), ("tareas", "verde"),
             ("sti", "verde"), ("audio", "verde"), ("gfx_init", "turquesa"), ("apps", "violeta"), ("gui_init", "violeta")]
    gx = [80 + i * 182 for i in range(6)]
    for k, (t, c) in enumerate(pasos):
        r, cc = divmod(k, 6)
        d.caja(f"p{k + 1}", gx[cc], 400 + r * 80, 170, 60, c, t, [], num=k + 1, tsize=22)
    d.leyenda(100, 730, [("rojo", "Arranque x86"), ("ambar", "Drivers"), ("verde", "Memoria y sistema"),
                        ("turquesa", "Gráficos"), ("violeta", "Escritorio y apps")], ancho_tot=1060)
    d.caja("txt", 80, 790, 1080, 100, "rojo", "Sin framebuffer: modo texto (segunda entrada de GRUB)",
           ["kernel_main escribe SEREOS_TEXT_MODE por COM1 y llama a shell_run_text() con sereos-text.bin"],
           tsize=22, lsize=21, dashed=True)
    d.flecha("p13", "txt", "l", "l", label=None)
    return d


def d3():
    d = Diagrama("d3_interrupciones", "Camino de una interrupción en SereOS",
                 "Fuente: boot/isr.s y kernel/idt.c. IRQ 0 = PIT, IRQ 1 = teclado, IRQ 12 = ratón.")
    y = 120
    ws = [170, 170, 170, 170, 280]
    xs = [40]
    for w in ws[:-1]:
        xs.append(xs[-1] + w + 40)
    datos = [("Hardware", ["PIT, teclado,", "ratón"], "gris"), ("PIC 8259", ["IRQ 0-15 →", "vector 32-47"], "gris"),
             ("CPU + IDT", ["consulta", "la IDT"], "gris"), ("isr.s", ["guarda los", "registros"], "azul"),
             ("interrupt_handler()", ["kernel/idt.c"], "azul")]
    for i, (t, ls, c) in enumerate(datos):
        d.caja(f"m{i}", xs[i], y, ws[i], 120, c, t, ls, num=i + 1, thick=(i == 4), tsize=22, lsize=21)
    for i in range(4):
        d.flecha(f"m{i}", f"m{i + 1}", recta=True)
    x5 = xs[4]
    d.caja("irq", x5, 340, 280, 120, "azul", "irq_handlers[n]", ["timer, teclado,", "ratón"], num=6, tsize=22, lsize=21)
    d.caja("eoi", x5, 520, 280, 100, "gris", "EOI al PIC", ["outb(0x20, 0x20)"], num=7, tsize=22, lsize=21)
    d.caja("iret", x5, 680, 280, 100, "azul", "iret", ["restaura registros"], num=8, tsize=22, lsize=21)
    d.caja("prog", 440, 680, 280, 100, "gris", "Programa", ["continúa donde estaba"], num=9, tsize=22, lsize=21)
    d.caja("pan", 440, 340, 280, 120, "rojo", "panic_exception()", ["pantalla de error", "y hlt"], tsize=22, lsize=21)
    d.flecha("m4", "irq", "b", "t", label="n ≥ 32 (IRQ)", recta=True)
    d.flecha("m4", "pan", "b", "t", label="n < 32 (excepción)", dashed=True, color="#DC2626", fa=0.1)
    d.flecha("irq", "eoi", "b", "t", recta=True)
    d.flecha("eoi", "iret", "b", "t", recta=True)
    d.flecha("iret", "prog", "l", "r", label="retorno", recta=True)
    d.panel("vec", 40, 500, 360, 280, "gris", "Vectores",
            [("0-31: excepciones", "sans"), ("0 = división por cero", "sans"), ("14 = falla de página", "sans"),
             ("32-47: IRQ del PIC", "sans"), ("32 = PIT, 33 = teclado", "sans"), ("44 = ratón", "sans")], tsize=24, lsize=22)
    return d


def d4():
    d = Diagrama("d4_mapa_memoria", "Mapa de memoria del kernel",
                 "Fuente: readelf -lW y memory/page.c. Alturas no proporcionales. Flecha derecha: direcciones crecientes.")
    bx, bw, bh = 380, 520, 100
    bloques = [
        ("0xE0000000 – 0xFFFFFFFF", "Ventana del framebuffer", ["512 MiB con PSE; el LFB de GRUB cae aquí"], "turquesa"),
        None,
        ("0x01698000 – 0x1FFFFFFF", "Marcos libres (page_alloc)", ["identidad PSE hasta 512 MiB"], "verde"),
        ("0x0035B000 – 0x016878DF", ".data y .bss  (19,2 MiB)", ["heap 8 MiB, backbuffer, bitmaps"], "azul"),
        ("0x0022C000 – 0x0035A5BF", ".rodata  (1,2 MiB)", ["fuentes, iconos, sonidos, sprites"], "ambar"),
        ("0x00200000 – 0x0022B191", ".text  (172 KiB)", ["código y cabecera Multiboot"], "rojo"),
        None,
        ("0x00100000 – 0x001FFFFF", "Libre  (1 MiB)", ["marcos disponibles"], "verde"),
        ("0x00000000 – 0x000FFFFF", "Memoria baja  (1 MiB)", ["BIOS, VGA, EBDA: reservada"], "gris"),
    ]
    y = 120
    ys = {}
    for k, b in enumerate(bloques):
        if b is None:
            d.salto(bx + bw / 2, y + 20, 160)
            y += 40
            continue
        a, t, ls, c = b
        d.caja(f"b{k}", bx, y, bw, bh, c, t, ls, tsize=22, lsize=21)
        d.texto(bx - 20, y + bh / 2 + 7, a, 21, "mono", "Regular", "#111827", "end")
        ys[k] = y
        y += bh + 20
    # llave del kernel (de .text a .bss)
    ytop = ys[3]
    ybot = ys[5] + bh
    d.llave(bx + bw + 20, ytop, ybot, "r")
    d.texto(bx + bw + 60, ytop + 16, "kernel_end", 21, "mono", "Bold")
    d.texto(bx + bw + 60, ytop + 42, "≈ 22,5 MiB", 21, "mono")
    d.texto(bx + bw + 60, (ytop + ybot) / 2 + 7, "sereos.bin", 21, "mono", "Bold")
    d.texto(bx + bw + 60, ybot - 34, "kernel_start", 21, "mono", "Bold")
    d.texto(bx + bw + 60, ybot - 8, "= 2 MiB", 21, "mono")
    d.linea(1146, ys[8] + bh, 1146, ys[0])
    return d


def d5():
    d = Diagrama("d5_arquitectura_juego", "PAC-MAN SereOS: una lógica, dos plataformas",
                 "Fuente: Pac-man SereOS/ (wc -l sobre los .c y .h de cada carpeta) y Makefiles del juego y del sistema.")
    d.caja("core", 40, 120, 1120, 100, "azul", "src/core  (3 270 líneas)",
           ["estados, laberinto 28x31, entidades, IA de fantasmas, puntuación y audio"], tsize=24, lsize=22)
    d.caja("rend", 40, 280, 1120, 100, "turquesa", "src/render  (1 426 líneas)",
           ["pantallas, HUD, menús arcade y laberinto prerrenderizado"], tsize=24, lsize=22)
    d.caja("ctr", 40, 440, 1120, 100, "ambar", "include/pac_platform.h  (contrato, ABI 1)",
           ["tiempo, memoria, entrada, dibujo, texto, audio, almacenamiento"], tsize=24, lsize=22, thick=True)
    d.caja("psr", 40, 620, 540, 130, "violeta", "platform/sereos  (756 líneas)",
           ["game_app.c: app_game()", "platform_sereos.c: kernel"], tsize=24, lsize=22)
    d.caja("pln", 620, 620, 540, 130, "gris", "platform/linux  (1 821 líneas)",
           ["SDL2 y framebuffer por software", "escenas forzadas para pruebas"], tsize=24, lsize=22)
    d.caja("osr", 40, 810, 540, 100, "rojo", "libpacman.a  →  sereos.bin",
           ["se enlaza al kernel antes de -lgcc"], tsize=24, lsize=22)
    d.caja("lnx", 620, 810, 540, 100, "gris", "build/pacman-sereos",
           ["ejecutable nativo en Linux con SDL2"], tsize=24, lsize=22)
    d.flecha("core", "rend", "b", "t", label="lo dibuja", recta=True)
    d.flecha("rend", "ctr", "b", "t", label="usa", recta=True)
    d.flecha("ctr", "psr", "b", "t", label="implementa", fb=0.5, fa=0.241, recta=True)
    d.flecha("ctr", "pln", "b", "t", label="implementa", fb=0.5, fa=0.759, recta=True)
    d.flecha("psr", "osr", "b", "t", label="se enlaza", recta=True)
    d.flecha("pln", "lnx", "b", "t", label="se compila", recta=True)
    return d


def d6():
    d = Diagrama("d6_pipeline_iso", "Cadena de construcción de la ISO",
                 "Fuente: Makefile del sistema y del juego. Pasos 1 a 8 con make; el arranque en VirtualBox es manual.")
    xs = [40, 320, 600, 880]
    W, H = 240, 120
    d.caja("os", xs[0], 140, W, H, "azul", "Fuentes del OS", ["50 archivos .c y .s"], num=1, tsize=22, lsize=21)
    d.caja("gm", xs[0], 340, W, H, "violeta", "Fuentes del juego", ["src/core y render", "platform/sereos"], num=2, tsize=22, lsize=21)
    d.caja("cc", xs[1], 140, W, H, "ambar", "gcc -m32 y nasm", ["objetos en build/"], num=3, tsize=22, lsize=21)
    d.caja("ms", xs[1], 340, W, H, "ambar", "make sereos", ["ar rcs →", "libpacman.a"], num=3, tsize=22, lsize=21)
    d.caja("ld", xs[2], 240, W, H, "rojo", "Enlace", ["gcc -T linker.ld", "→ sereos.bin"], num=4, tsize=22, lsize=21)
    d.caja("pt", xs[3], 140, W, H, "ambar", "Variante de texto", ["patch_multiboot", "_text.py: 0x7 → 0x3"], num=5, tsize=22, lsize=21)
    d.caja("gf", xs[3], 340, W, H, "verde", "grub-file", ["valida la cabecera", "de ambos binarios"], num=6, tsize=22, lsize=21)
    d.caja("iso_dir", xs[3], 560, W, H, "verde", "isodir/", ["los 2 .bin y", "grub.cfg"], num=7, tsize=22, lsize=21)
    d.caja("mk", xs[2], 560, W, H, "ambar", "grub-mkrescue", ["xorriso + mtools"], num=8, tsize=22, lsize=21)
    d.caja("iso", xs[1], 560, W, H, "rojo", "sereos.iso", ["36 835 328 B", "(35,1 MiB)"], tsize=22, lsize=21, thick=True)
    d.caja("vb", xs[0], 560, W, H, "gris", "VirtualBox", ["paso manual", "BIOS, 256 MiB"], tsize=22, lsize=21, dashed=True)
    d.flecha("os", "cc", recta=True)
    d.flecha("gm", "ms", recta=True)
    d.flecha("cc", "ld")
    d.flecha("ms", "ld")
    d.flecha("ld", "pt")
    d.flecha("ld", "gf")
    d.flecha("pt", "iso_dir", "r", "r")
    d.flecha("gf", "iso_dir", "b", "t", label="sereos.bin", recta=True)
    d.flecha("iso_dir", "mk", "l", "r", recta=True)
    d.flecha("mk", "iso", "l", "r", recta=True)
    d.flecha("iso", "vb", "l", "r", recta=True, dashed=True)
    return d


def main():
    ok = True
    for f in (d1, d2, d3, d4, d5, d6):
        try:
            res, _ = f().construir(AQUI)
        except Exception as e:  # noqa: BLE001
            print(f"[{f.__name__}] ERROR: {e}")
            res = False
        ok = ok and res
    if not ok:
        print("\nHAY CHOQUES: corregir antes de usar los diagramas.")
        sys.exit(1)
    print("\nTodos los diagramas pasaron la verificación.")


if __name__ == "__main__":
    main()
