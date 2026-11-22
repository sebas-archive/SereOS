# Funcionalidades de SereOS v1.0

Lista honesta de lo que **está implementado realmente** en SereOS 1.0. Cada
apartado indica cómo se ha comprobado: por lectura del código y/o por la suite
automática de QEMU (`tools/run_tests.py`, resultados en
[`screenshots/test-results.json`](screenshots/test-results.json)).

Lo que no existe está listado al final y detallado en
[LIMITATIONS.md](LIMITATIONS.md). No se documentan funcionalidades inventadas.

## Arranque

* **GRUB 2 + Multiboot 1** (`grub.cfg`, `boot/boot.s`): el kernel valida la
  firma Multiboot y arranca con `-m 256M`.
* **Menú GRUB con dos entradas** (timeout 2 s): escritorio gráfico
  1024x768x32 y consola de texto VGA como respaldo.
* **Modos de vídeo con fallback**: pide `1024x768x32`; si el firmware no lo da,
  GRUB elige `800x600x32`, `1024x768x24` o `auto`. Si no hay framebuffer, el
  kernel sigue con la consola VGA de texto.
* **Diagnóstico por COM1** (`serial.log`): marcadores de estado y errores;
  también se imprimen por la consola VGA.
* Verificado: pruebas `boot` (marcadores `SEREOS_BOOT_OK`, `SPLASH_DONE`,
  `DESKTOP_READY`, `GUI_READY`) y `text_fallback` (`SEREOS_TEXT_MODE`).

## Núcleo (kernel)

* **GDT propia** de 5 descriptores: nulo, código y datos de kernel (anillo 0),
  código y datos de usuario (anillo 3).
* **IDT** con las 32 excepciones del procesador y los 16 IRQ, con el **PIC
  8259 remapeado a 32–47**; stubs de interrupción en NASM.
* **PIT a 100 Hz** (IRQ 0) para reloj y temporización.
* **Teclado PS/2** (IRQ 1, scancode set 1, distribución US) con detección
  real del teclado.
* **Ratón PS/2** (IRQ 12) con cursor absoluto en la pantalla; si no hay ratón
  el escritorio sigue siendo navegable por teclado.
* **RTC CMOS** (fecha/hora, comando `date`/`time`).
* **PC speaker** por el canal 2 del PIT (tonos no bloqueantes para el juego y
  pitidos puntuales); opcional, no necesario para el sistema.
* **Registro del kernel** (`dmesg`) con marcas de tiempo reales.
* **Pantallas de excepción y pánico** en VGA de texto y sobre el framebuffer
  del escritorio, con parada segura.
* Verificado: arranque estable y ausencia de `SEREOS_EXCEPTION`/`SEREOS_PANIC`
  en toda la suite (`no_fatal`).

## Audio

* **Sound Blaster 16** (DSP + DMA 8237, PCM **8 bits mono**) con **fallback al
  altavoz del PC** cuando no hay tarjeta; `audio_available()` y
  `audio_backend()` exponen el estado real.
* API no bloqueante (`audio_play`, `audio_loop`, `audio_update`) con efectos
  originales sintetizados en el repo: menú, inicio, waka-waka, power pill,
  comer fantasma, fruta, muerte, vida extra, nivel completado, game over y
  sirenas de persecución.
* El juego usa el audio en su paso cooperativo; el monitor/«Acerca de» pueden
  consultar el backend.
* Verificado: `make run-audio` (audible, backend del anfitrión) y
  `make run-audio-wav`; la suite incluye una prueba `audio` que analiza
  `audio-capture.wav` (PCM, duración y peak/RMS).

## Memoria

* **Allocator de marcos físicos de 4 KiB** sobre el mapa de memoria que
  reporta Multiboot, con conteo de marcos libres/usados.
* **Paginación con identidad** (virtual = física) activada con **PSE (páginas
  de 4 MiB)** más una tabla fina de 4 KiB para el primer bloque; el
  framebuffer se mapea aunque esté en otro rango alineado.
* **Heap del kernel** `kmalloc/kzalloc/kfree/krealloc` con estrategia
  *first-fit* sobre un arena estático de 8 MiB.
* La app **Monitor** muestra memoria física, marcos, heap, uso y mayor bloque
  libre reales.

## Sistema de archivos (RAMFS)

* **Árbol real de nodos en RAM** (nodo 0 = `/`), no una simulación:
  `fs_create`, `fs_mkdir`, `fs_delete`, `fs_lookup`, `fs_chdir`, `fs_getcwd`,
  `fs_open`, `fs_read`, `fs_write`, `fs_list`.
* Límites: **64 nodos**, nombres de 28 caracteres, **1024 bytes por archivo**,
  rutas de 128 caracteres.
* Se crea una semilla en `fs_init()` (`/home`, `/docs`, `/readme.txt`, etc.).
* Lo usan tanto la **shell** (`ls`, `cd`, `pwd`, `mkdir`, `touch`, `cat`,
  `write`, `rm`) como el **gestor de archivos** (misma API `fs_*`).
* Verificado: suite abre el gestor (`APP_OPEN:files`); los comandos de RAMFS
  se comprueban visualmente en la terminal.

## Tareas y planificador

* **Tareas cooperativas** (hasta 32) y **planificador round-robin** que se
  ejecuta una vez por frame desde el bucle del escritorio; soporta tareas
  dormidas con despertar por tick.
* Modelo **cooperativo sin cambio de pila**: cada tarea ejecuta un paso corto
  y retorna; no hay multitarea preemptiva (ver LIMITATIONS.md).
* Contadores reales expuestos al Monitor: pasos, activaciones, tarea actual.

## Motor gráfico

* **Framebuffer** con *backbuffer* y presentación por regiones sucias
  (`gfx_mark_dirty`/`gfx_present_dirty`), recorte (clipping) integrado.
* Primitivas: píxel, rectángulos rellenos y con alfa, contornos, líneas (con
  alfa), círculos, rectángulos redondeados (alfa), degradados verticales,
  sombras y halos radiales.
* **Motor tipográfico** con Inter (UI) y JetBrains Mono (datos): atlases de
  cobertura alfa generados en compilación, cobertura ASCII + Latin-1 y
  medición/recorte por estilo (`text_width`, `text_draw_clipped`). Se conserva
  la fuente bitmap 8x16 de compatibilidad para el código heredado.
* Sprites RGB565 con clave de transparencia y bitmaps monocromo.
* Composición con mezcla alfa simulada por software (sin aceleración 3D).
* Verificado: todas las capturas de la suite analizan los PPM y confirman que
  la pantalla no está en negro y tiene decenas de colores distintos.

## Gestor de ventanas: maximización full-bleed

* Maximizar (semáforo verde o doble clic en la barra de título) ocupa
  exactamente `x=0..sw-1, y=30..sh-49`: **sin radios, sombras, márgenes ni
  wallpaper**, con una sola topbar y **sin barra inferior**; los 5 accesos
  aparecen centrados en la topbar.
* Restaurar devuelve el **rect normal exacto** sin relanzar la app; minimizar
  una maximizada vuelve al dock y restaurarla la devuelve **maximizada**.
* Ventanas normales redimensionables por bordes/esquinas (8 px) con mínimo
  300x180 y clamp al work area.
* Apps adaptadas al tamaño: Archivos, Terminal, Monitor, About y Pacman
  (tablero centrado con dots/power). Capturas `25`–`32`.
* **Esquinas redondeadas sin parches**: composición con clipping real (guarda
  el fondo bajo las esquinas y restaura solo lo exterior al arco); dentro del
  arco se conserva la barra de estado y fuera el fondo/sombra, verificado
  también con ventana superpuesta y resize. Capturas `33`/`33b`/`33c`.

## Navegación adaptativa: dock y accesos en la topbar

* **Logotipo oficial**: `assets/logo/official_logo.png` (1296x1213, S blanca
  sobre azul) generado a sprites RGB565 por `tools/gen_logo.py`; se usa en
  splash, topbar, cabecera del menú, About y
  pánico. Escalado por altura con `icons_logo_width()`: proporción 1,0685 sin
  deformación. Detalle en [LOGO.md](LOGO.md).
* **Navegación adaptativa**: con ninguna ventana maximizada se muestra el
  **dock flotante**; con al menos una maximizada el dock **desaparece** y los
  5 accesos (Archivos/Terminal/Monitor/Pacman/Información) pasan a la
  **topbar central**, centrados en pantalla (1024: 448..575; 800: 336..463;
  1280: 576..703), con el mismo icono/tinte, indicador activo
  `accent_soft`+subrayado y punto en apps abiertas. La maximizada es
  **full-height** hasta `sh-1` sin barra inferior. Clic abre/enfoca o
  minimiza la activa; no duplica `APP_OPEN`. La transición (~145 ms) oculta el
  dock antes de mostrar la nav, sin iconos duplicados. Verificado a
  1024x768, 1280x1024 y 800x600.

## Sistema de diseño e identidad visual

* **Tokens únicos** en `gui/theme.h`/`gui/theme.c`: paleta semántica (fondo
  `#0B0D12`, superficies, texto, acentos y estados), escala de espaciado
  múltiplo de 4 (`SP_0..SP_12`), radios (`RADIUS_XS..XL`) y métricas de
  barra/dock/ventanas. Ninguna app inventa colores ni márgenes.
* **Tipografía nativa**: Inter (Regular/SemiBold) para UI y JetBrains Mono
  para terminal/datos, ambas **SIL OFL 1.1**, rasterizadas en tiempo de
  compilación con `tools/gen_ui_fonts.py` a atlases de cobertura alfa de 8
  bits (`graphics/text_data.c`); en ejecución no hay fuentes externas ni
  dependencias. Escala de 10/11/12/13/16/20/30 px y cobertura **ASCII +
  Latin-1** (acentos y ñ) vía UTF-8.
* **Iconografía lineal propia**: iconos y atlas 16/20/24/32/40/48/64 px
  generados por `tools/gen_ui_icons.py` (`gui/icons_data.c`), con estados
  normal/hover/activo y tinte coherente con el tema.
* **Métricas de escritorio**: barra superior de 30 px, dock centrado de
  58 px con iconos de 40 px e indicador de app abierta, ventanas con radio
  10, barra de título de 34 px, borde de 1 px y sombra sutil.
* **Splash minimalista** (~1 s) con logotipo, nombre y barra de progreso;
  **pantalla de pánico sobria** con título `TEXT_DISPLAY`, detalle técnico en
  monoespaciada y parada segura.
* **Contraste medido** (WCAG 2.1): texto principal 16,3:1, secundario 8,2:1;
  el color de acento se reserva para foco/acciones.
* **Resoluciones**: 1024x768 (principal), 1280x1024 y 800x600 verificadas en
  QEMU con ISOs temporales que ajustan la petición de vídeo Multiboot.
* Verificado: suite oficial **18/18 PASS** y capturas reales
  `00_grub_menu` … `40_topnav_1280` en [screenshots/](screenshots/)
  (incluye `02b_topbar_dock`, `02c_dock_tooltip` con hover real, `15_panic` con `div0` real, escenarios dock/topnav 18–40 y las dos
  resoluciones alternativas). Revisión visual de
  jerarquía/alineación/tipografía/contraste/recortes hecha sobre las 21
  capturas finales, más la comparativa antes/después
  (`screenshots/compare_before_after.png`).

## Escritorio (SereOS Desktop)

* **Splash de arranque** animado con logotipo, estrellas, barra de progreso y
  los mensajes reales del registro del kernel, con transición al escritorio.
* **Fondo de escritorio** generado por degradados/halos y **barra superior**
  con menú, nombre de la app activa y reloj real.
* **Dock inferior** con iconos vectoriales dibujados por código, animación de
  escala al pasar el ratón, tooltips e indicadores de app abierta.
* **Gestor de ventanas** (hasta 8): barra de título, semáforos
  cerrar/minimizar/maximizar, foco (clic o F6), arrastre con el ratón,
  minimizar/restaurar, maximizar, cierre y cascada.
* **Cursor de ratón** compuesto por software sobre el backbuffer.
* Atajos globales: **F1** archivos, **F2** terminal, **F3** monitor,
  **F4** juego, **F5** acerca de, **F6** siguiente ventana, **F7** minimizar,
  **Ctrl+W / Alt+W** cerrar ventana activa.
* Verificado: suite `boot`, `terminal`, `files`, `monitor`, `about`, `game`,
  `window_close` y `window_focus`.

## Aplicaciones

* **Terminal** (`terminal`): shell compartida con scrollback, colores, edición
  de línea, historial de 16 entradas y flechas arriba/abajo.
* **Archivos** (`files`): explorador real del RAMFS con listado de directorios,
  navegación, selección, ordenación y previsualización de archivos de texto.
* **Monitor** (`sysmonitor`): estado real del sistema —frames/uptime, memoria
  física y heap, ticks del PIT, tareas cooperativas y nodos del RAMFS.
* **Acerca de** (`about`): identidad y versión del sistema plus lista de
  componentes con su disponibilidad real (consultada a las APIs).
* **PAC-MAN SereOS** (`game`, componente externo `../Pac-man SereOS/` enlazado
  como `libpacman.a`): versión definitiva M2/M3/M4 del juego arcade de
  laberinto, en C nativo y punto fijo Q8.8 (sin FPU): *attract* con PRESS
  START, menú principal (Jugar/Continuar/Récords/Instrucciones/Ajustes/Salir),
  pausa, game over, ajustes persistidos y F11; **131/131 checks** de core +
  7/7 pantallas smoke. Correcciones v3 verificadas: audio Game Start sin corte
  del chunk inicial, respawn de fantasmas entre tiles y muerte que **conserva
  laberinto/dots/puntuación/nivel** (solo pierde vida). Laberinto clásico de **28x31 tiles** (240 dots
  + 4 power pills, casa de fantasmas, puerta y túneles con *wrap*), Pacman con
  boca animada y 4 fantasmas con IA por personalidad (Blinky persecución
  directa y Cruise Elroy, Pinky 4 tiles por delante, Inky vector con Blinky,
  Clyde a distancia 8), fases scatter/chase de la tabla de 21 niveles,
  frightened con parpadeo, ojos que vuelven a casa por BFS, frutas, vidas,
  nivel, récord, vida extra a 10.000 puntos, menú, instrucciones, pausa,
  game over y nivel completado. Puntuación 10/50/200-400-800-1600/fruta.
  Sprites (16x16 RGB565) y audio originales. Lógica y render compartidos con la
  versión Linux/SDL2 del componente; el OS solo enlaza `app_game()` (sin copia
  del juego dentro de `sistema operativo/`). Ver
  [PAKMAN_SEREOS.md](PAKMAN_SEREOS.md) y [BUILD.md](BUILD.md).
* Verificado: suite `terminal`, `files`, `monitor`, `about`, `game` y `audio`.
  En `game` se comprueban los marcadores `GAME_MENU` → `GAME_START` →
  `GAME_PAUSE` → `GAME_OVER` → `GAME_EXIT`, y por píxeles reales: dots
  visibles, 4 fantasmas, power pills, dos capturas comiendo dots con menos
  dots y el estado *frightened* (cuerpos azules). Ver
  [screenshots/](screenshots/).

## Shell compartida

Un solo intérprete (`shell/shell.c`) escribe a través de un callback: lo usan
igual la terminal gráfica y la consola VGA de respaldo. Comandos:

`help`, `clear`, `about`, `version`, `sysinfo`, `mem`, `free`, `ticks`,
`dmesg`, `date`, `time`, `echo`, `scroll`, `div0`, `pwd`, `ls`, `cd`, `mkdir`,
`touch`, `cat`, `write`, `rm`.

Verificado: `help`, `ls`, `date`, `free` y `dmesg` se teclean en la terminal
gráfica y se comprueba que la pantalla cambia; `help` también en modo texto.

## Herramientas de QA incluidas

* `tools/qemu_ctrl.py`: arranca QEMU con KVM (fallback sin KVM), espera
  marcadores del puerto serie, envía teclas por el monitor (`sendkey`), captura
  con `screendump`, inyecta ratón relativo por QMP y cierra QEMU limpiamente.
* `tools/ppm_to_png.py`: conversión PPM P6 → PNG con zlib (sin PIL), análisis
  de capturas (colores distintos, píxeles no negros, luminancia) y comparación
  entre capturas.
* `tools/run_tests.py`: suite real de **18 pruebas** (arranque, escritorio,
  apps, navegación adaptativa, PAC-MAN SereOS, audio SB16, cierre/foco de ventanas, fallback de texto,
  pánico por `div0` y resoluciones 1280x1024/800x600), con capturas PNG y
  resumen JSON; opciones `--iso` y `--shots-dir` para sets antes/después.
* `tools/gen_ui_fonts.py` / `tools/gen_ui_icons.py`: rasterizan las fuentes
  Inter/JetBrains Mono (OFL) y generan la iconografía lineal propia.
* `tools/make_comparison.py`: genera el mosaico antes/después del rediseño.
* `tools/patch_multiboot_text.py`: genera el kernel auxiliar `sereos-text.bin`
  (sin petición de framebuffer en la cabecera Multiboot) que hace posible la
  entrada de GRUB en modo texto VGA.

## Lo que NO está implementado

Sin multitarea preemptiva, sin espacio de usuario/syscalls, sin red, sin audio
digital estéreo/16 bits ni música en streaming, sin disco/particiones
persistentes, sin FPU/SIMD, sin SMP, sin protección de memoria entre apps, sin
ratón absoluto ni USB. Detalle y justificación en
[LIMITATIONS.md](LIMITATIONS.md).
