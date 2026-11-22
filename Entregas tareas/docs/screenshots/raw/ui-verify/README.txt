Evidencia visual de la UI de SereOS (task-3 de ui-engineer)
===========================================================

Todas las capturas se tomaron de la ISO REAL `sistema operativo/sereos.iso`
(compilada con `make -C "sistema operativo"`), arrancada en QEMU i386 a
1024x768 mediante `tools/qemu_ctrl.py` (screendump) y convertida PPM->PNG con
`tools/ppm_to_png.py`. Raton PS/2 inyectado con QMP `input-send-event`
(rel/btn). Sin SEREOS_PANIC ni excepciones en ninguna ronda.

- 01-desktop.png          escritorio; logo S en la top bar; About del dock con
                          la insignia i en circulo azul/celeste.
- 02-menu.png             menu del logo: cabecera con logo S, Acerca de con
                          insignia i, Reiniciar con icono refresh y Apagar
                          DEBAJO con icono power; pista Alt+W.
- 04-about.png            ventana Acerca de: icono i en la cabecera de
                          contenido, fila Audio con audio_detail() real
                          ("solo PC speaker" en QEMU sin SB16), botones a la
                          DERECHA en orden minimizar(ambar)/maximizar(verde)/
                          cerrar(rojo) y titulo centrado.
- 05-files, 06-terminal, 07-monitor, 08-about2, 09-game
                          mismo frame compartido en TODAS las apps.
- 10-game-maximized.png   PAC-MAN maximizado: boton central con glifo
                          "restaurar" (dos cuadrados); titulo centrado.
- 11-game-restored.png    vuelta a estado normal con el mismo boton.
- 12-close-click.png      tras pulsar el boton cerrar (serial APP_CLOSE:game).
- 13-dblclick-max.png     doble clic en la barra de titulo -> maximizada.
- 14-dblclick-restore.png doble clic en la barra ya maximizada -> restaurada.
- po-01-menu.png          menu antes de pulsar Apagar.
- po-02-apagando.png     pantalla "Apagando..." y QEMU sale por ACPI; serial:
                          SEREOS_SHUTDOWN, SEREOS_POWEROFF, pm1a=0x0604, s5=1.
- zoom-*-buttons.png      ampliaciones 8x de los glifos de los botones.
- serial-ui-verify.log    log serie de la ronda completa de UI.
- serial-dblclick.log     log serie de la prueba de doble clic.
- serial-poweroff.log     log serie de la prueba menu -> Apagar.

Scripts reproducibles: verify_ui.py (ronda completa), probe_dblclick.py
(doble clic maximizar/restaurar) y probe_poweroff.py (menu -> Apagar).
