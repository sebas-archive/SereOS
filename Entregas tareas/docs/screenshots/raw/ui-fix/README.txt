Corrección UI (task-5): logo S en contenido, icono i solo en accesos
====================================================================

Capturas tomadas de la ISO REAL `sistema operativo/sereos.iso`
(`make -C "sistema operativo"`, 2026-11-20 05:43), QEMU i386 1024x768,
screendump con `tools/qemu_ctrl.py` y PPM->PNG con `tools/ppm_to_png.py`.
Sin SEREOS_PANIC ni excepciones.

- 01-escritorio-topbar-S-dock-i.png
    Barra superior: logo S + wordmark "SereOS" (logo_draw_topbar).
    Dock: tile de About con icono i azul/celeste (icons_draw_info_badge).
- 02-menu-i-acceso-y-Apagar.png
    Menú del logo: cabecera con logo S (logo_draw_brand); fila "Acerca de"
    con icono i (acceso); Reiniciar (refresh) y Apagar (power) sin cambios.
- 03-about-logo-S-audio-botones-derecha.png
    Ventana Acerca de: LOGO S blanco sobre cuadro azul redondeado en la
    cabecera del contenido (logo_draw_about), sin icono i; fila Audio con
    audio_detail() real ("solo PC speaker" en QEMU sin SB16); botones de
    ventana a la derecha minimizar/maximizar/cerrar y título centrado.
- 04-about-max-topnav-i.png
    About maximizada (dock oculto): el acceso equivalente de la topnav
    conserva el icono i; el contenido sigue mostrando el logo S.

Recursos separados:
  icono_info  = icons_draw_info_badge()  -> SOLO accesos (menú, dock, topnav)
  logo_sereos = logo_draw_about/topbar/brand() -> marca y contenido

Scripts reproducibles: verify_fix.py (escritorio, menú, About) y
verify_topnav.py (maximizar About y capturar topnav con i).

Reiniciar (task-7)
------------------
- 05-menu-Reiniciar.png   menu con la fila Reiniciar (icono refresh).
- 06-reiniciando.png      menu -> Reiniciar: pantalla "Reiniciando..." con
                          logo S, titulo y subtitulo centrados (mismo diseno
                          que "Apagando..."); QEMU se reinicia (con -no-reboot
                          termina) y el serial registra SEREOS_RESTART.
- serial-restart.log      log serie de la prueba.
Script reproducible: verify_restart.py.
