# Informe de validación: SereOS 1.0 y PAC-MAN SereOS

Fecha de la validación: 20 de noviembre de 2026. Equipo: CachyOS (Linux 7.3.3), gcc 16.2.1, NASM 3.02, GRUB 2.16, VirtualBox 7.2.22r175245, QEMU 11.1.3.

## 1. Qué se inspeccionó

- `ProyectoFinal_sistemas_operativos.docx` (documento base): es la plantilla institucional de la UMB (portada, tabla de contenido y secciones vacías: Introducción, Objetivos, Conclusiones, Referencias, Anexos). Se respetó su portada, sus estilos de título y su tabla de contenido.
- `avances_que_teniamos_proyecto_final.docx`: avances v0.1 (23 oct) y v0.2 (30 oct). Se recuperaron su historia, sus tablas de GDT/PIC/PIT, la tabla de comandos de la shell y cuatro capturas históricas (rotuladas como tales).
- Proyecto real en `sereos02/`: código del sistema (50 archivos .c/.s, 43 .h), Makefiles, `grub.cfg`, `linker.ld`, README, CHANGELOG, docs/ del sistema y del juego, y el componente `Pac-man SereOS/` (núcleo, render, plataformas, assets, pruebas).

Los dos DOCX de entrada no se modificaron (el original conserva su SHA-256 `213449f5...3ad32`).

## 2. Qué se modificó en la documentación

Se creó `ProyectoFinal_sistemas_operativos_FINAL.docx` sobre una copia de la plantilla: 93 páginas, 21 capítulos más referencias y 7 anexos, 45 figuras y 29 tablas con numeración automática (campos SEQ), tabla de contenido, lista de figuras y lista de tablas con campos actualizables, encabezado con número de página y pie institucional. Pasó el validador de esquema OOXML. El PDF se generó con LibreOffice a partir de ese mismo DOCX (93 páginas, Times New Roman incrustada).

Se añadieron secciones de la plantilla que estaban vacías (Introducción, Objetivos, Conclusiones, Referencias, Anexos) y se amplió con los capítulos técnicos.

Fuente de los diagramas: dibujados por nosotros con PIL a partir de la estructura del código (`documentacion/herramientas/diag.py`).

## 3. Pruebas ejecutadas

| Id | Prueba | Entorno | Resultado |
|---|---|---|---|
| P01-P03 | ISO nueva, cabeceras Multiboot válidas, compilación limpia sin advertencias | CachyOS | OK |
| P04-P18 | GRUB (2 entradas), arranque gráfico, splash, SB16 detectada, terminal y comandos (help, sysinfo, version, dmesg, mem, free, ticks, date, RAMFS, errores), Archivos, Monitor, Acerca de, multiventana y Ctrl+W, consola de texto, excepción div0 | VirtualBox | OK |
| P19-P20 | Menú del logotipo, ayuda del dock, maximizar y restaurar con navegación superior | QEMU | OK |
| P21-P29 | PAC-MAN SereOS desde F4: atracción, menús, instrucciones, partida, píldora y fantasmas asustados, captura de fantasma, fruta visible, muerte, pausa, fin de juego y reintento | VirtualBox | OK |
| P30 | `make test` del juego: 209 comprobaciones sin fallos y 7 pruebas de humo | CachyOS | OK |

## 4. ISO utilizada

`sistema operativo/sereos.iso`, 36 835 328 bytes, generada el 20/11/2026 09:15 tras `make clean && make game-clean && make -j8`.

- SHA-256 ISO: `4fe9ea95131e571082a6ea07a471aaf4cb1549aaa2ad702a68ea87599d7c96d9`
- SHA-256 `sereos.bin`: `ca9bf32ab10b9894c0b44fd568f65e7f2b42947ef66cb56a541475ad477cc1f4` (el `boot/sereos.bin` extraído de la ISO coincide)
- La ISO anterior tenía otro hash (`44d94650...`), así que no se reutilizó una ISO vieja.
- `libpacman.a` está enlazada: `nm sereos.bin` muestra `app_game` y las funciones `pac_*`.
- El hash de la ISO se comprobó otra vez al final y no cambió durante las pruebas.

## 5. Pruebas completadas en VirtualBox

Máquina `SereOS Final` (BIOS, 256 MiB, VBoxVGA, IDE con la ISO, SB16, COM1 a archivo). Arrancada sin ventana y controlada con `VBoxManage controlvm`. Capturas con `screenshotpng`. Se completaron: GRUB, arranque gráfico, terminal, aplicaciones, modo texto, excepción, y varias partidas de PAC-MAN SereOS con marcadores del puerto serie (`GAME_START`, `PAC_DEATH`, `GHOST_EATEN`, `GAME_PAUSE`, `GAME_OVER`).

## 6. Capturas

56 capturas originales en `documentacion/capturas/` y 21 recortes de ellas, usados en el documento, en `recortes_documento/`:

- `01_arranque/` 4 (GRUB, selección de modo texto, splash)
- `02_escritorio/` 10 (escritorio; el resto con prefijo `qemu_` son de QEMU)
- `03_terminal/` 11 (comandos, pantalla de error, modo texto)
- `04_aplicaciones/` 5
- `05_pacman_sereos_vbox/` 11 (juego dentro de SereOS en VirtualBox)
- `06_pacman_cachyos/` 11 (escenas del binario de Linux, rotuladas como CachyOS)
- `00_historicas_avances/` 4 (QEMU, de los avances)
- `07_virtualbox/` registros del puerto serie de cada sesión

## 7. Funcionalidades verificadas

Arranque con GRUB y Multiboot, GDT, IDT y excepciones, PIC, PIT (3 439 ticks en 34 s), teclado, RTC, puerto serie, detección de la SB16, marcos de memoria, heap, planificador (contadores en Monitor), RAMFS (crear, escribir, leer, listar, ver en Archivos), escritorio y ventanas, shell de 25 comandos, consola de texto, pantalla de error, y el juego dentro del sistema.

## 8. Limitaciones y errores que permanecen

- No se verificó el sonido con los oídos (solo la detección de la SB16).
- No se probó apagar ni reiniciar desde el menú, mover ni redimensionar ventanas.
- No se capturó comer la fruta ni la transición de nivel dentro de VirtualBox. El nivel completado se muestra con una escena forzada del binario de Linux (rotulada).
- No se usó la ventana del Administrador de VirtualBox. VirtualBox no permite mover el ratón desde la línea de comandos, y la inyección de entrada al equipo anfitrión se descartó. Las pruebas con ratón se hicieron en QEMU con la misma ISO.
- Se usó un programa auxiliar (`documentacion/herramientas/bot.py`) que lee capturas y envía teclas para llegar a estados del juego. No modifica el juego.
- No se probó en hardware físico.
- Se observó que la tecla Escape no era reconocida si pulsación y liberación llegaban casi juntas (en el teclado virtual de VirtualBox). No se investigó la causa en el código.
- Los recursos del juego (sprites, sonidos, fuente) son de terceros con uso académico y sin redistribución pública, así que la ISO no debe publicarse.
- No se repitió el arnés automático de 18 pruebas de QEMU que trae el proyecto; sus resultados no se presentan como propios.
- En el equipo se instaló LibreOffice (repositorio oficial, `pacman -S libreoffice-fresh`) para convertir el DOCX a PDF. Antes no estaba instalado.
- La paginación del PDF corresponde al render de LibreOffice. Word puede variar levemente al abrir el DOCX; la tabla de contenido y las listas llevan campos que se actualizan con F9.

## 9. Discrepancias entre documentos y proyecto

Detalle en el anexo F del documento. Las principales: pila de 16 KiB en los avances (ahora 64 KiB), 8 comandos de shell (ahora 25), `i686-elf-gcc` (se usó `gcc -m32`), GRUB a 3 s (ahora 2 s), paginación y kmalloc "pendientes" (ya implementados), serie a 38 400 baudios en `LIMITATIONS.md` (el código usa 115 200), tamaño de ISO y número de pruebas del README desactualizados.

## 10. Entregables

- `/home/t1an/Descargas/ProyectoFinal_sistemas_operativos_FINAL.docx`
- `/home/t1an/Descargas/ProyectoFinal_sistemas_operativos_FINAL.pdf`
- `/home/t1an/Descargas/sereos02/documentacion/` (capturas, diagramas, evidencias, herramientas, copia del DOCX y PDF)
- `/home/t1an/Descargas/sereos02/sistema operativo/sereos.iso`
- Este informe
