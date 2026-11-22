src = open("build_redesign.py", encoding="utf-8").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, old[:60]
    src = src.replace(old, new)

# 03: short title, body below it
rep('tb(s, MARGEN, 0.72, 2.5, 2.0, "SereOS 1.0", size=SZ_TITULO, color=TXT, bold=True)\ntb(s, MARGEN, 1.9, 2.4, 3.0, "Kernel monolítico para i686 con escritorio, terminal y aplicaciones propias.",',
    'tb(s, MARGEN, 0.72, 2.5, 0.9, "SereOS", size=SZ_TITULO, color=TXT, bold=True)\ntb(s, MARGEN, 1.75, 2.4, 3.6, "Versión 1.0. Kernel monolítico para i686, con escritorio, terminal y aplicaciones propias.",')

# 05: caption and text placed from the real picture height
rep('pic(s, CAP + "/01_arranque/grub_menu.png", 7.2, 1.95, w=5.4)\ntb(s, 7.2, 4.5, 5.4, 0.3, "Menú de GRUB en VirtualBox", size=SZ_PIE, color=GRIS)\ntb(s, 7.2, 5.1, 5.4, 1.6,',
    '_, gy, _, gh = pic(s, CAP + "/01_arranque/grub_menu.png", 7.2, 1.95, w=5.4)\ntb(s, 7.2, gy + gh + 0.12, 5.4, 0.3, "Menú de GRUB en VirtualBox", size=SZ_PIE, color=GRIS)\ntb(s, 7.2, gy + gh + 0.7, 5.4, 1.6,')

# 07: number fits on one line, body moves down
rep('tb(s, 7.6, 2.0, 5.0, 1.6, "512 MiB", size=SZ_HERO, color=ACENTO, bold=True)\ntb(s, 7.6, 3.75, 5.0, 2.8,',
    'tb(s, 7.6, 2.1, 5.3, 1.3, "512 MiB", size=80, color=ACENTO, bold=True)\ntb(s, 7.6, 3.7, 5.0, 2.8,')

# 09: shorter description so it fits its column
rep('"div0      provoca una división por cero"', '"div0      división por cero"')

# 14: fewer words
rep('["Sonido audible de la SB16.", "Apagado y reinicio desde el menú.",\n                              "Redimensionado de ventanas.", "Hardware físico."]',
    '["Sonido audible de la SB16.", "Apagado y reinicio.",\n                              "Redimensionado de ventanas.", "Hardware físico."]')
rep('["Multitarea preemptiva y anillo 3.", "Llamadas al sistema.",\n                           "Disco, red, USB y UEFI."]',
    '["Multitarea preemptiva y anillo 3.", "Llamadas al sistema.",\n                           "Disco, red, USB y UEFI."]')

# 15: three short statements, 25 words in total
rep('"El orden de inicialización del kernel y el remapeo del PIC son decisiones que se ven en pantalla."',
    '"Arranque y PIC: decisiones visibles en pantalla."')
rep('"Separar lógica y plataforma permitió ejecutar el mismo juego en dos sistemas."',
    '"Lógica separada de plataforma: el juego corre en dos sistemas."')
rep('"Los avances estaban desactualizados; el código y las pruebas mandan."',
    '"La evidencia manda sobre los avances antiguos."')

open("build_redesign.py", "w", encoding="utf-8").write(src)
print("patched")
