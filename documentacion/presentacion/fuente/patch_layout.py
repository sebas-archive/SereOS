src = open("build_deck.py", encoding="utf-8").read()
def rep(old, new, count=1):
    global src
    assert src.count(old) == count, (src.count(old), old[:70])
    src = src.replace(old, new)

rep("top = 1.95; rh = 0.6; gap = 0.09", "top = 1.9; rh = 0.58; gap = 0.08")
rep('caption(s, "Cada fila usa la inmediatamente inferior. Subtítulos: módulos (.c) de cada carpeta.", M, 6.7, 12, size=10.5)',
    'caption(s, "Cada fila usa la inmediatamente inferior. Subtítulos: módulos (.c) de cada carpeta.", M, 6.62, 12, size=10.5)')

a = src.index("# decision split"); b = src.index('caption(s, "Si el número mágico')
new5 = '''# decision layout (kernel_main -> decision -> two branches)
k4x = M + 3 * (bw + bg_gap) + bw / 2
line(s, k4x, by + bh, k4x, 4.55, color=MUTED_D, w=1.25)
line(s, k4x, 4.55, 8.36, 4.55, color=MUTED_D, w=1.25, arrow=True)
rect_text(s, 5.4, 4.25, 2.95, 0.6, ["¿Framebuffer válido?"], fill=None, line=AMBER, color=PAPER, size=14, align="c", lw=1.25)
line(s, 6.2, 4.85, 4.45, 5.6, color=MUTED_D, w=1.25, arrow=True)
line(s, 7.6, 4.85, 9.25, 5.6, color=MUTED_D, w=1.25, arrow=True)
rect_text(s, 2.9, 5.6, 3.1, 0.8, ["Sí: escritorio SereOS", "entrada por defecto de GRUB"], fill=GRAPH, color=PAPER, size=13, align="c")
rect_text(s, 7.7, 5.6, 3.1, 0.8, ["No: consola de texto", "segunda entrada del menú"], fill=GRAPH, color=PAPER, size=13, align="c")
'''
src = src[:a] + new5 + src[b:]
rep('caption(s, "Si el número mágico de Multiboot no es el esperado, boot_fail escribe [FAIL] y detiene la máquina.", M, 6.7, 12, color=MUTED_D)',
    'caption(s, "Si el número mágico de Multiboot no es el esperado, boot_fail escribe [FAIL] y detiene la máquina.", M, 6.62, 12, color=MUTED_D)')

a = src.index("# memory bar diagram"); b = src.index('caption(s, "", M, 6.7, 8)')
new8 = '''# memory bar diagram
bx0 = M; bw_ = 12.13; by0 = 4.9
text(s, bx0, by0 - 0.45, 8, 0.3, "MAPA DE DIRECCIONES (PAGINACIÓN DE IDENTIDAD)", size=10.5, color=AMBER, font=MONO_F)
rect(s, bx0, by0, bw_ * 0.7, 0.7, fill=BLUE)
text(s, bx0 + 0.2, by0 + 0.12, 9, 0.5, "0 – 512 MiB · dirección virtual = física · páginas PSE de 4 MiB", size=13, color=WHITE, font=BODY_F, anchor="m")
rect(s, bx0 + bw_ * 0.7, by0, bw_ * 0.3, 0.7, fill=GRAPH, line=MUTED_D, lw=0.5)
text(s, bx0 + bw_ * 0.7 + 0.2, by0 + 0.12, 3.5, 0.5, "Rango donde GRUB coloca el framebuffer", size=12, color=PAPER, anchor="m")
text(s, bx0, by0 + 0.95, 12, 0.5, "Según el capítulo 5.1 del informe: identidad hasta 512 MiB, más el rango del framebuffer.",
     size=10.5, color=MUTED_D)
'''
src = src[:a] + new8 + src[b:]
rep('caption(s, "", M, 6.7, 8)', 'caption(s, "", M, 6.62, 8)')

rep('pic_frame(s, CAP + "/03_terminal/cmd_help.png", M, 1.8, 7.4, 5.05, color=GRAPH)',
    'pic_frame(s, CAP + "/03_terminal/cmd_help.png", M, 1.8, 6.2, 4.65, color=GRAPH)')
rep('caption(s, "Salida de help en VirtualBox. Muestra la parte final de la lista; la ventana se desplaza.", M, 6.9 - 0.1, 7.4, size=10)',
    'caption(s, "Salida de help en VirtualBox. Muestra la parte final de la lista; la ventana se desplaza.", M, 6.6, 6.4, size=10)')
rep("    yy += 0.6\n", "    yy += 0.55\n")
rep('caption(s, "Tabla 10 del informe; lista completa de 25 comandos.", 8.5, 6.9 - 0.12, 4.3, size=10)',
    'caption(s, "Tabla 10 del informe; lista completa de 25 comandos.", 8.5, 6.6, 4.3, size=10)')
rep("yy = 2.2\n", "yy = 2.15\n")

rep('pic_frame(s, CAP + "/02_escritorio/escritorio_principal.png", M, 1.8, 7.3, 5.1, color=GRAPH)',
    'pic_frame(s, CAP + "/02_escritorio/escritorio_principal.png", M, 1.8, 6.13, 4.6, color=GRAPH)')
rep('caption(s, "Escritorio real en VirtualBox. Barra superior y dock con cinco accesos.", M, 6.95, 7.3, color=MUTED_D, size=10)',
    'caption(s, "Escritorio real en VirtualBox. Barra superior y dock con cinco accesos.", M, 6.55, 7.3, color=MUTED_D, size=10)')

rep('pic_frame(s, CAP + "/04_aplicaciones/multiventana.png", M, 1.85, 9.1, 4.95, color=GRAPH)',
    'pic_frame(s, CAP + "/04_aplicaciones/multiventana.png", M, 1.85, 8.2, 4.45, color=GRAPH)')
rep('caption(s, "Captura en VirtualBox: varias ventanas abiertas a la vez en el compositor.", M, 6.9, 9.1, size=10)',
    'caption(s, "Captura en VirtualBox: varias ventanas abiertas a la vez en el compositor.", M, 6.5, 9.1, size=10)')

rep('pic_frame(s, CAP + "/04_aplicaciones/explorador_archivos.png", M, 1.85, 5.9, 3.6, color=GRAPH)',
    'pic_frame(s, CAP + "/04_aplicaciones/explorador_archivos.png", M, 1.85, 5.9, 3.4, color=GRAPH)')
rep('pic_frame(s, CAP + "/04_aplicaciones/monitor_sistema.png", 6.85, 1.85, 5.9, 3.6, color=GRAPH)',
    'pic_frame(s, CAP + "/04_aplicaciones/monitor_sistema.png", 6.85, 1.85, 5.9, 3.4, color=GRAPH)')
rep('"Lista el RAMFS, crea y abre archivos. Muestra el contenido creado desde la terminal."',
    '"Muestra el RAMFS: los archivos creados desde la terminal, visibles en la aplicación."')
rep('text(s, M, 5.65, 5.9, 0.3, "ARCHIVOS"', 'text(s, M, 5.45, 5.9, 0.3, "ARCHIVOS"')
rep('text(s, M, 5.95, 5.9, 0.9, "Muestra', 'text(s, M, 5.75, 5.9, 0.9, "Muestra')
rep('text(s, 6.85, 5.65, 5.9, 0.3, "MONITOR', 'text(s, 6.85, 5.45, 5.9, 0.3, "MONITOR')
rep('text(s, 6.85, 5.95, 5.9, 0.9, "Memoria', 'text(s, 6.85, 5.75, 5.9, 0.9, "Memoria')
rep('caption(s, "Capturas en VirtualBox. Acerca de y terminal se documentan en el capítulo 11 del informe.", M, 6.95, 12, size=10)',
    'caption(s, "Capturas en VirtualBox. Acerca de y terminal se documentan en el capítulo 11 del informe.", M, 6.6, 12, size=10)')

rep('pic_frame(s, CAP + "/05_pacman_sereos_vbox/05_partida_dots_fantasmas.png", 5.9, 1.85, 6.83, 5.1, color=GRAPH)',
    'pic_frame(s, CAP + "/05_pacman_sereos_vbox/05_partida_dots_fantasmas.png", 5.9, 1.85, 6.83, 4.6, color=GRAPH)')
rep('caption(s, "Partida en VirtualBox, con la interfaz del juego dentro de la ventana de SereOS.", 5.9, 6.98, 6.9, color=MUTED_D, size=10)',
    'caption(s, "Partida en VirtualBox, con la interfaz del juego dentro de la ventana de SereOS.", 5.9, 6.55, 6.9, color=MUTED_D, size=10)')

rep('"Aritmética de punto fijo: el kernel no inicializa coma flotante."',
    '"El juego usa punto fijo porque el kernel no inicializa la unidad de coma flotante."')

rep("cw = 2.87; chh = cw * 0.75; cgx = (W - 2 * M - 4 * cw) / 3", "cw = 2.6; chh = cw * 0.75; cgx = (W - 2 * M - 4 * cw) / 3")
rep("x = M + c_ * (cw + cgx); y = 1.85 + r_ * (chh + 0.55)", "x = M + c_ * (cw + cgx); y = 1.8 + r_ * (chh + 0.5)")
rep('caption(s, "Secuencia de la validación: menús, partida, fantasmas asustados, captura y fin de juego.", M, 6.7, 12, color=MUTED_D, size=10.5)',
    'caption(s, "Secuencia de la validación: menús, partida, fantasmas asustados, captura y fin de juego.", M, 6.62, 12, color=MUTED_D, size=10.5)')

rep('"sereos.bin contenido en boot/ coincide con la ISO"', '"sereos.bin extraído de la ISO coincide con el compilado"')

rep("rect(s, 6.6, 2.3, 6.13, 4.3, fill=INK, line=GRAPH, lw=0.75)", "rect(s, 6.6, 2.3, 6.13, 3.95, fill=INK, line=GRAPH, lw=0.75)")
rep('6.6, 6.7, 6.2, color=MUTED_D, size=10)', '6.6, 6.4, 6.2, color=MUTED_D, size=10)')

rep('"Teclado, ratón, RTC y puerto serie"', '"Teclado, RTC y puerto serie; ratón probado en QEMU"')

rep('pic_frame(s, LOGO, 9.4, 1.9, 3.3, 3.3, color=None or GRAPH)\n', '')
rep('"Se detectaron 8 discrepancias entre avances y código, por ejemplo la pila (16 a 64 KiB) y los comandos (8 a 25)."',
    '"Varias discrepancias entre avances y código, por ejemplo la pila (16 a 64 KiB) y los comandos (8 a 25)."')

open("build_deck.py", "w", encoding="utf-8").write(src)
print("patched")
