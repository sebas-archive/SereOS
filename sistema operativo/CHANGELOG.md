# Changelog de SereOS

Todas las versiones relevantes del proyecto. SereOS es un sistema operativo
bare-metal propio para i686 (C + NASM) que arranca con GRUB 2 / Multiboot 1.

## [1.9] — Auditoría de audio: SB16 real, IRQ 5, pcspk y configuración de VM (2026)

* **Causas del "no suena" encontradas y corregidas**:
  1. **Mixer en silencio**: el driver escribía `0xFF` en los registros de
     volumen `0x04`/`0x22` del SB16. En una SB16 esos registros son
     *atenuación* (`0x00` = 0 dB, `0xFF` = -62 dB): el driver **silenciaba la
     tarjeta** en hardware real. Ahora se escriben `0x00` en `0x04`, `0x22` y
     `0x30..0x33` (los que aplican QEMU/VirtualBox/SB16 reales).
  2. **Modo DMA erróneo**: se programaba el 8237 con `0x45` (*WRITE*,
     dispositivo→memoria). Para reproducir hay que usar `0x49`
     (*READ*, memoria→dispositivo); con `0x45` el 8237 habría machacado la
     bounce buffer en hardware real.
  3. **Sin detección en el arranque**: `audio_init()` no se llamaba en
     `kernel_main()`, así que el backend real solo aparecía si se abría una
     app que lo inicializase. Ahora se inicializa tras `sti()` y se registra
     `[OK] Audio: <detalle>` en el log serie/`dmesg`.
  4. **Detección limitada**: `sb16_init()` solo probaba 0x220 y 0x240; ahora
     escanea **0x220..0x280** (paso 0x10) con reset del DSP (1 en base+6,
     espera ≥3 µs, 0, 0xAA con timeout) y nunca marca disponible si no responde.
  5. **Sin IRQ 5**: el fin de bloque se estimaba solo por tiempo. Ahora hay
     handler IRQ 5 (`irq_install(5,...)`, ack leyendo `base+0x0E`, EOI de
     `interrupt_handler`) y el canal se libera por IRQ o, como red de
     seguridad, por tiempo (`duración + 100 ms`).
  6. **VM mal configurada** (causa externa): `make run`/QEMU sin `-device
     sb16` no tiene tarjeta y el altavoz PC no se oye sin
     `-machine pcspk-audiodev=...`; VirtualBox por defecto usa AC'97/HDA (no
     SB16) y VMware no emula SB16. Documentado en `docs/AUDIO_VM.md`.
* **Nuevo contrato de UI**: `const char *audio_detail(void)` en `audio/audio.h`
  (`"SB16 0x220 IRQ5 DMA1"`, `"solo PC speaker"`,
  `"no disponible"`), usado por la fila Audio de Acerca de.
* **Diagnóstico visible**: comandos de shell `audio`, `beep [hz] [ms]` y
  `audiotest`; este último emite `AUDIO_TEST:<backend>`,
  `AUDIO_DETAIL:<detalle>` y `AUDIO_TEST_DONE tones=.. irq=.. pit_hz=..` por
  COM1 para verificación automática.
* **pcspk verificado**: PIT canal 2 en modo 3 (0x43=0xB6, 0x42), bits 0/1 de
  0x61 y sin interferir con el PIT 100 Hz del canal 0 (comprobado con
  `pit_hz=100` y `pit_ticks` durante el `audiotest`).
* **Verificación real (QEMU 11.1.3, TCG, evidencia en
  `docs/evidence/audio/`)**: SB16 0x220 IRQ5 DMA1 DSP 4.5 con `tones=4 irq=4`,
  WAV de 0,788 s activos con peak **-3,0 dBFS**, RMS **-3,4 dBFS** y tonos
  441,7/658,3/883,3/1316,7 Hz (440/660/880/1320 esperados); fallback pcspk con
  `-machine pc,pcspk-audiodev=wav` con 0,797 s activos y los mismos 4 tonos;
  SB16 en 0x240 detectado por el escaneo; SB16 con IRQ 7 reproduce por fin por
  tiempo (`irq=0`); sin audio no hay crash y `audio_detail` = "solo PC speaker".
* **Docs**: nuevo `docs/AUDIO_VM.md` (QEMU moderno/antiguo, VirtualBox, VMware,
  hardware, diagnóstico), `docs/AUDIO.md` actualizado (mixer, modo DMA 0x49,
  IRQ 5, contrato, evidencias) y README con la sección "Audio en QEMU".

## [1.8] — Integración final v3: audio Game Start, respawn de fantasmas y muerte (2026)

* **Build aprobada del componente**: `build/pacman-sereos` 769.568 B (md5
  `42f33373157cf1bf2590215152e05ae3`) y `libpacman.a` 280.906 B (md5
  `28a84127e0ef206764ce48ef7bfd316d`); **131/131 checks** de core + **7/7**
  pantallas smoke, 0 warnings, README/docs y 9 capturas actualizadas.
* **Correcciones v3**: (a) **audio Game Start** sin corte del chunk inicial
  del sample; (b) **respawn de fantasmas entre tiles** (ojos → casa →
  reaparición sin solaparse ni saltar); (c) la **muerte conserva laberinto,
  dots, puntuación y nivel** (solo se pierde una vida y se reinician
  posiciones).
* **QA v3**: escenas `--scene gamestart|ghostcapture|death`; nuevos marcadores
  por COM1: `LEVEL_START <n>`, `GHOST_EATEN/RETURNED/REVIVED <id>`,
  `PAC_DEATH`, `LIFE_START <vidas>` y
  `PAC_STATS dots=.. power=.. score=.. level=.. lives=..`.
* **Integración OS**: se enlaza `libpacman.a` antes de `-lgcc`;
  `apps/apps.c` solo llama a `app_game()`; sin `apps/game/`. La app mantiene
  id `game`, icono `game`, 880x560 y nombre **«PAC-MAN SereOS»**.
* **Build**: 0 warnings; `sereos.bin` 1.250.856 B (md5
  `dfd3bc7d10f5093ee61f72bdbda58653`) e ISO 36.282.368 B (md5
  `c430ea24528d7b1f21ae47d0d1a86b16`); `sereos-text.bin` 1.250.856 B (md5
  `b19338dbcb81e7f76b195fff0153c6a2`); un único `app_game`.
* **Verificación QEMU (ISO final)**: abrir desde el dock, attract/PRESS START,
  menú arcade, partida real, **muerte real** con `PAC_STATS` que pasa de
  `dots=240 score=0 level=1 lives=3` a `dots=233 score=70 level=1 lives=2`
  (laberinto/puntuación/nivel conservados), pausa, salida y escritorio limpio,
  **0 excepciones**. Escenas Linux: `GHOST_EATEN 0` → `GHOST_RETURNED 0` →
  `GHOST_REVIVED 0` y `--scene death` con `PAC_STATS` antes/después.
* **Audio SB16** (`-audiodev wav`): WAV de **17,162 s activos**, peak
  **29.952** (91,4 % FS), RMS **16.403** (50,1 % FS), **0 muestras recortadas**
  y hueco interno máximo **66 ms** (sin cortes/distorsión audibles).
* **Docs**: README/PAKMAN/BUILD/FEATURES/LIMITATIONS actualizados con la
  realidad de v3 y enlaces a las auditorías del componente. Capturas/ZIP/docx
  finales los genera QA.
* **Top bar**: la marca pasa a ser el **PNG ribbon**
  (`assets/logo/ribbon_s_logo.png`) dibujado **sin fondo azul**, a la altura
  visual del wordmark (`TOPBAR_LOGO=10 px`) y alineado con él (gap 8 px); el
  resto de ubicaciones conserva el glifo oficial y su contenedor azul.

## [1.7] — PAC-MAN SereOS definitivo: M2/M3/M4, recursos Res y audio SB16 (2026)

* **Versión definitiva del juego**: se integra la librería final
  `../Pac-man SereOS/build/sereos/libpacman.a` (277.630 B, md5
  `09fe549d0490eaafb48ea75e0d25ca5a`; 107 checks de core + 7/7 pantallas
  smoke y 9 capturas corregidas). Binario Linux aprobado por QA:
  `build/pacman-sereos` 753.808 B, md5 `dcc58b2c7263fe96a7f8d352d1621831`. La app conserva id `game`, icono `game`, 880x560 y el
  nombre visible exacto **«PAC-MAN SereOS»** en titlebar, topbar, dock, menú y
  Acerca de.
* **Contenido arcade**: *attract* con tabla de personajes y **PRESS START**,
  menú principal de 6 opciones (incluye **Continuar**), pausa de 5, game over
  de 3, ajustes (sonido/pantalla completa/controles persistidos en RAMFS) y
  F11 pantalla completa. Un **único laberinto real** 28x31 (240 dots + 4 power
  pills) con **21 configuraciones** (L22+ = L21): no se inventan layouts.
* **Reglas auditadas contra Paku-Paku**: salidas del pen por dots/tiempo,
  frightened (velocidad y objetivo pseudoaleatorio), Cruise Elroy, tabla
  scatter/chase, fruta a 70/170 dots y puntuación clásica. Ver
  [`AUDIT_PAKUPAKU.md`](../Pac-man SereOS/docs/AUDIT_PAKUPAKU.md).
* **Recursos `Res`** (privados, uso académico): 10 PNG (frutas + cuerpos de
  fantasmas recoloreados), fuente arcade Press Start K y PCM u8 mono 11025 Hz
  de 10 WAV. **Aviso**: material sin licencia/atribución de origen arcade; se
  usa con atribución y **sin redistribución pública**; el arte propio queda
  como fallback. Ver
  [`AUDIT_RESOURCES.md`](../Pac-man SereOS/docs/AUDIT_RESOURCES.md) y
  [`LICENSE_RES.md`](../Pac-man SereOS/assets/LICENSE_RES.md).
* **Audio real**: SB16 por DMA con los PCM de `Res` (trozos ≤32 KiB y cola en
  `pac_audio_update`) y fallback a la capa `audio/` sintetizada; probado en
  QEMU con captura WAV no silenciosa.
* **Build**: 0 warnings; `sereos.bin` 1.246.660 B (md5
  `deeffd09795d7afd29ed515900d7f759`) e ISO 36.274.176 B (md5
  `6666c7763910be1bece046bfd557712c`); un único `app_game`. `sereos-text.bin`
  1.246.660 B (md5 `2e5a665cc3fabe5f9629256802ac2d0e`).
* **Verificación QEMU**: attract/PRESS START, menú, partida, pausa y salida;
  topbar/titlebar/tooltip/menú exactos «PAC-MAN SereOS», `GAME_MENU` →
  `GAME_START` → `GAME_PAUSE` → `GAME_EXIT` → `APP_CLOSE:game`, escritorio
  limpio y **0 excepciones**; también verificado el menú de ajustes. Audio
  SB16 capturado con `-audiodev wav`: 3,855 s activos, peak 29.952 (91,4 % FS)
  y RMS 10.639 (32,5 % FS), 39/39 ventanas de 100 ms con señal.
* **Docs**: `docs/PAKMAN_SEREOS.md` reescrito para la versión definitiva y
  enlazado a las auditorías del componente; README/FEATURES/AUDIO/LIMITATIONS/
  BUILD actualizados. Capturas/ZIP/docx finales los genera QA.

## [1.6] — Integración de Pac-man SereOS como componente externo (2026)

* **Componente separado**: el juego vive en `Pac-man SereOS/` (carpeta hermana
  del OS) con una sola copia de la lógica y dos backends (SereOS freestanding y
  Linux/SDL2). `sistema operativo/apps/game/` se elimina por completo: no hay
  duplicación de código, arte ni audio.
* **Integración por librería**: el kernel enlaza
  `"../Pac-man SereOS/build/sereos/libpacman.a"` (89.722 B) **después de los
  objetos y antes de `-lgcc`**; `apps/apps.c` solo llama a `app_game()` y el
  `nm` del binario contiene un único símbolo `app_game`. La app conserva id
  `game`, icono `game`, tamaño 880x560 y nombre **«Pac-man SereOS»**.
* **Makefile del OS**: nuevas variables `GAME_DIR` (por defecto
  `../Pac-man SereOS`) y `OS_DIR`, target `game-lib` (recompila el componente
  pasando `OS_DIR`), regla que construye la librería si falta, `game-clean`, y
  exclusión de `apps/game/*` y de `-Iapps/game` del build. `make clean` no
  borra la librería del componente.
* **Build**: `make clean && make` sin warnings; `sereos.bin` pasa a 1.063.488 B
  (md5 `97613dc7…`) y la ISO a 35.909.632 B. Sin SDL ni headers Linux en el
  kernel (la librería es freestanding).
* **Verificación QEMU** (`tools/run_tests.py --only game` sobre la ISO v1.6):
  **PASS**, `APP_OPEN:game` una sola vez, `GAME_MENU` → `GAME_START` → dots →
  power pill (frightened) → `GAME_PAUSE` → reanudar → `GAME_OVER` →
  `GAME_EXIT` y escritorio recuperado, **0 excepciones**. Capturas/serial de la
  integración en `/tmp` y suite oficial completa a cargo de QA.
* **Docs**: README, `docs/PAKMAN_SEREOS.md`, `docs/BUILD.md`, `docs/FEATURES.md`
  y `docs/AUDIO.md` actualizados con la nueva arquitectura (juego en
  `Pac-man SereOS/` enlazado como librería) y los comandos de build.

## [1.5] — Navegación adaptativa: dock oculto y accesos en la topbar (2026)

* **Navegación adaptativa**: con una ventana maximizada el **dock inferior
  desaparece por completo** (no hay barra de tareas) y los **5 accesos**
  (Archivos, Terminal, Monitor, Pacman, Información) pasan a la **topbar
  central**, centrados en la pantalla —1024: bloque `448..575`, 800:
  `336..463`, 1280: `576..703`— con los mismos iconos/tintes del dock,
  indicador activo (`accent_soft` + subrayado de 2 px) y punto en apps
  abiertas.
* **Geometría full-height**: la maximizada ocupa `x=0, y=30, w=sw, h=sh-30` y
  llega hasta `y=sh-1` (1024: 30..767), sin dock/taskbar ni franjas; la
  máxima full-bleed deja de reservar 48 px abajo.
* **Transición** discreta (~145 ms): el dock baja y se oculta **antes** de que
  aparezca la nav (sin iconos duplicados simultáneos); a la inversa al
  restaurar. Restaurar/minimizar la **última** maximizada devuelve el dock;
  con otra maximizada abierta se mantiene topnav. Clic en un acceso: abre,
  enfoca o minimiza/restaura la activa sin duplicar `APP_OPEN`.
* **Taskbar eliminada** del compositor: capturas/código de la antigua barra
  full-width (`19/20/23/24…`) retirados; navegación en `34`–`40`.
* Suite ampliada a **18 pruebas** (`dock` + `topnav`; se retira `taskbar`) con
  pixel checks de ausencia de dock/barra inferior, app hasta `sh-1`, centrado
  exacto de los 5 accesos, un único activo, multicuenta, minimizar la última,
  clics sin duplicados, transición y 800/1280. QA oficial: **18/18 PASS**,
  0 excepciones y **41 capturas** finales.

## [1.4] — Corrección del artefacto de esquinas y bordes de ventanas (2026)

* **Bug corregido (compositor)**: al componer ventanas normales se guardaban y
  restauraban bloques completos de 14x14 px en las esquinas inferiores, lo que
  sobrescribía la barra de estado de la app con el color del cuerpo de la
  ventana y dejaba parches cuadrados/contorno rectangular. Ahora se guarda el
  fondo real bajo las 4 esquinas antes de pintar y se restaura **solo lo que
  queda fuera** del rectángulo redondeado; el interior (contenido/status bar)
  queda intacto y el contorno se redibuja.
* Verificado por píxeles en Archivos normal: dentro del arco BR =
  `surface_2 (26,30,38)`, fuera = fondo `(10,13,24)`, **0 px de cuerpo
  (20,23,30) fuera** en las 4 esquinas; también con ventana superpuesta
  (`13_multiventana`) y tras resize (900→940, `30_resize`). Las maximizadas
  siguen square full-bleed por diseño.
* Nueva prueba `corners` (suite **17 pruebas**) y capturas de evidencia
  `33_window_corners_clean` (mosaico 10x), `33b_window_corners_overlap` y
  `33c_window_corners_resized`; 38 capturas finales.
* QA oficial sobre la ISO final: **17/17 PASS** (`KVM=si`), 0 excepciones
  inesperadas, audio no silencioso y comparativa actualizada.

## [1.3] — WM: maximización full-bleed, doble clic, minimizar con estado y resize (2026)

* **Maximización full-bleed real**: la ventana cubre exactamente
  `x=0..sw-1, y=30..sh-49` (1024x768: 0,30 1024x690) **sin radios, sombras,
  márgenes ni wallpaper**; topbar y barra de tareas globales se dibujan una
  sola vez y el contenido de la app ocupa todo el área. Verificado a
  1024x768, 1280x1024 y 800x600 (pixel checks: 0 % wallpaper, esquinas (0,30)
  de titlebar, única barra/logo).
* **Doble clic en la barra de título** alterna maximizar/restaurar (≤350 ms) y
  el semáforo verde sigue funcionando. Restaurar recupera el **rect exacto**
  sin relanzar la app (sin `APP_OPEN` repetido).
* **Minimizar una maximizada** vuelve al dock y, al restaurarla desde el dock o
  la barra, recupera el estado **maximizado full-bleed** (`was_maximized`).
* **Resize** de ventanas normales por bordes/esquinas de 8 px con mínimo
  300x180 y clamp al work area; las maximizadas no se redimensionan.
* Apps adaptadas al nuevo tamaño (Archivos, Terminal, Monitor, About y
  Pacman). **Bug corregido**: al reabrir Pacman se reconstruye el tablero y
  vuelven los 240 dots y 4 power pills (antes la segunda apertura salía sin
  dots por `maze.base` por instancia y `maze_ready` estático).
* Suite ampliada a **16 pruebas** (nueva `maximize`) y capturas `25`–`32`;
  documentación WM en [docs/DESIGN.md](docs/DESIGN.md) y [docs/RUN.md](docs/RUN.md).
* QA oficial sobre la ISO final: **16/16 PASS** (`KVM=si`), **0 excepciones
  inesperadas**, 35 capturas + comparativa.

## [1.2] — Logotipo oficial y barra de tareas adaptativa (2026)

* **Logotipo oficial** de SereOS (S blanca sobre azul, `assets/logo/official_logo.png`,
  1296x1213) sustituye a las marcas procedurales anteriores en splash, barra
  superior, cabecera del menú, marca de la barra de tareas, «Acerca de» y
  pantalla de pánico. Generado a sprites RGB565 (`tools/gen_logo.py`) y escalado
  por altura conservando la proporción 1,0685 (sin deformación); el logo antiguo
  (`logo_badge`/`logo_s`/`logo_mono`) queda eliminado.
* **Barra de tareas adaptativa**: al maximizar una ventana, el dock flotante se
  convierte en una barra full-width de **48 px** con marca a la izquierda,
  iconos centrados, app activa resaltada y tray (memoria/uptime/fecha/reloj) a
  la derecha; la ventana maximizada ocupa el work area real entre la topbar y la
  barra sin taparla. Restaurar/minimizar/cerrar la última maximizada devuelve el
  dock. Verificado a 1024x768, 1280x1024 y 800x600.
* Suite ampliada con la prueba `taskbar` y capturas `18_dock_window` …
  `24_taskbar_800`, además de `22_menu_logo` (cabecera con el logo oficial).
* Documentación nueva [docs/LOGO.md](docs/LOGO.md) y secciones de logotipo y
  barra de tareas en [docs/DESIGN.md](docs/DESIGN.md); README/FEATURES/RUN
  actualizados.
* QA oficial sobre la ISO final: **15/15 PASS** (incluye la prueba `taskbar`,
  pánico por `div0`, resoluciones 1280x1024/800x600, audio no silencioso y 0
  excepciones inesperadas), **29 capturas** y comparativa antes/después.

## [1.1] — Rediseño visual integral (2026)

Rediseño profesional de toda la interfaz con un sistema de diseño único,
tipografía nativa y verificación visual real en QEMU (mantiene las
funcionalidades de la 1.0, incluido Pacman SereOS y el audio).

### Sistema de diseño

* Nueva identidad «SereOS UI»: paleta carbón (`#0B0D12` y superficies
  neutras), azul de acento `#4C8DFF`, cian `#4CC9E0` y estados
  verde/ámbar/rojo; contraste medido (texto principal 16,3:1).
* Tokens únicos en `gui/theme.h`/`gui/theme.c`: escala de espaciado múltiplo
  de 4, radios 4–18 px, sombras sutiles y métricas de barra superior
  (30 px), dock centrado (58 px) y ventanas (radio 10, barra 34, borde 1).
* **Tipografía nativa** Inter (UI) y JetBrains Mono (datos), ambas SIL OFL 1.1,
  rasterizadas en compilación a atlases alfa (`graphics/text_data.c`) con
  cobertura ASCII + Latin-1; sin dependencias en ejecución.
* **Iconografía lineal original**: 36 ids y atlas 16–64 px generados por
  `tools/gen_ui_icons.py` (`gui/icons_data.c`), con estados y tinte del tema.
* Nuevo `gui/ui.h`/`gui/ui.c` con componentes compartidos y
  `graphics/text.h` como motor de texto medido y recortado.

### Interfaz rediseñada

* **Escritorio**: barra superior con jerarquía tipográfica, reloj/datos en
  mono, dock centrado con iconos lineales e indicador de app abierta, fondo
  sobrio y sombras sutiles.
* **Ventanas**: barra de título de 34 px, semáforos consistentes, foco
  visible, contenido con márgenes de 16 px y sombra de un solo nivel.
* **Aplicaciones**: terminal (mono + paleta del tema), explorador de archivos,
  monitor con tarjetas de datos reales, acerca de (14/14 componentes y
  backend de audio) y Pacman SereOS (HUD, menús y diálogos con la nueva
  tipografía).
* **Splash minimalista** (~1 s) y **pantalla de pánico sobria** con detalle
  técnico monoespaciado.

### Verificación y herramientas

* Suite ampliada a **14 pruebas**: añade pánico real por `div0` y resoluciones
  **1280x1024** y **800x600** mediante ISOs temporales en `/tmp` que parchean
  la petición de vídeo Multiboot (sin tocar el repo).
* Capturas limpias por app y nuevas obligatorias: `02b_topbar_dock`,
  `02c_dock_tooltip`, `15_panic`, `16_resolution_1280x1024`,
  `17_resolution_800x600`; set previo al rediseño en
  `docs/screenshots/before/` y comparativa
  `docs/screenshots/compare_before_after.png` (`tools/make_comparison.py`).
* Documentación del sistema de diseño en
  [docs/DESIGN.md](docs/DESIGN.md) y actualización de README, FEATURES,
  LIMITATIONS, RUN y BUILD.
* Verificación oficial sobre la ISO final: **14/14 PASS** (incluye pánico por
  `div0`, 1024x768/1280x1024/800x600, audio WAV no silencioso y 0 excepciones
  inesperadas), 22 capturas y comparativa antes/después.

## [1.0] — SereOS Desktop + Pacman SereOS (2026)

Versión final de SereOS: escritorio gráfico completo, aplicaciones nativas,
**Pacman SereOS** (arcade de laberinto original inspirado en el género) y
audio real.

### Juego

* **Pacman SereOS**: app `game` con ventana y dock «Pacman SereOS» y pantalla
  de título «PACMAN SereOS» (F4).
* Laberinto 28x31 tiles: 240 dots, 4 power pills, casa de fantasmas, puerta y
  túneles con *wrap* horizontal.
* Pacman con animación de boca y 4 direcciones; 4 fantasmas con IA por
  personalidad (Blinky persecución directa + Cruise Elroy, Pinky 4 tiles por
  delante, Inky vector con Blinky, Clyde a distancia 8).
* Fases scatter/chase de la tabla de 21 niveles, frightened con parpadeo,
  ojos que vuelven a casa por BFS, frutas por nivel, vidas, nivel, récord,
  vida extra a 10.000 puntos, menú, instrucciones, récord, pausa, game over y
  nivel completado.
* Puntuación 10 (dot) / 50 (power pill) / 200-400-800-1600 (fantasmas) /
  fruta según nivel. Récord en RAMFS (`/home/pacman_sereos.hi`).
* Sprites 16x16 RGB565 originales (`apps/game/assets/`) y efectos de sonido
  originales; ningún recurso de terceros redistribuido.
* Documentación del juego: [docs/PAKMAN_SEREOS.md](docs/PAKMAN_SEREOS.md);
  auditoría de la referencia VB6 en [docs/PAKU_AUDIT.md](docs/PAKU_AUDIT.md).

### Audio

* Capa de audio independiente del juego (`audio/`): **Sound Blaster 16**
  (DSP + DMA 8237, PCM 8 bits mono) con **fallback al altavoz del PC**.
* 14 efectos originales sintetizados por `tools/gen_audio.py` (waka, power,
  comer fantasma, fruta, muerte, vida extra, nivel, game over y sirenas).
* API no bloqueante (`audio_play`, `audio_loop`, `audio_update`).
* Objetivos nuevos: `make run-audio` (audio audible) y `make run-audio-wav`
  (captura a `audio-capture.wav`); documentación en
  [docs/AUDIO.md](docs/AUDIO.md).

### Pruebas

* La suite amplía la verificación del juego: marcadores
  `GAME_MENU`/`GAME_START`/`GAME_PAUSE`/`GAME_OVER`/`GAME_EXIT` y análisis por
  píxeles (dots, 4 fantasmas, power pill/frightened), más una prueba de audio
  que valida el WAV (PCM, duración, peak/RMS) y la comprobación global de cero
  excepciones/panics.
* Capturas finales del juego y del escritorio en `docs/screenshots/`.

### Escritorio, kernel y aplicaciones

Base completa del sistema con escritorio gráfico.

#### Kernel y arranque

* Arranque GRUB 2 + Multiboot 1 con dos entradas: escritorio gráfico
  1024x768x32 y consola VGA de texto como fallback (kernel auxiliar
  `sereos-text.bin` sin petición de framebuffer).
* GDT propia (5 descriptores), IDT con 32 excepciones y 16 IRQ, PIC 8259
  remapeado, PIT a 100 Hz, teclado y ratón PS/2 con cola de eventos.
* RTC CMOS, PC speaker, consola VGA, framebuffer lineal y log por COM1
  (`serial.log`) con marcadores estables para pruebas automatizadas.
* Pantallas de excepción y pánico (VGA y framebuffer) con parada segura.

#### Memoria y sistema de archivos

* Allocator de marcos físicos de 4 KiB y paginación de identidad con PSE
  (páginas de 4 MiB) más tabla fina de 4 KiB.
* Heap del kernel `kmalloc/kzalloc/kfree/krealloc` (first-fit, arena de 8 MiB).
* RAMFS real en memoria (árbol de nodos, 64 nodos, archivos de hasta 1 KiB),
  compartido por la shell y el explorador de archivos.

#### Gráficos y escritorio

* Framebuffer con backbuffer, presentación por regiones sucias, clipping,
  mezcla alfa, degradados, sombras, halos, fuente bitmap 8x16 y sprites RGB565.
* Splash animado con los mensajes reales del kernel.
* Escritorio estilo macOS: barra superior con reloj, dock con iconos
  vectoriales y animaciones, cursor compuesto, ventanas con semáforos
  (cerrar/minimizar/maximizar), arrastre, foco, cascada y atajos de teclado.
* Atajos: F1 archivos, F2 terminal, F3 monitor, F4 juego, F5 acerca de,
  F6 siguiente ventana, F7 minimizar, Ctrl+W/Alt+W cerrar ventana.

#### Aplicaciones

* **Terminal** con shell compartida y scrollback.
* **Archivos**: explorador del RAMFS (navegación, selección, previsualización).
* **Monitor**: memoria, heap, marcos, PIT/uptime, tareas cooperativas y RAMFS.
* **Acerca de**: identidad, versión y disponibilidad real de cada componente.
* **Shell** compartida entre terminal gráfica y consola VGA: `help`, `clear`,
  `about`, `version`, `sysinfo`, `mem`, `free`, `ticks`, `dmesg`, `date`,
  `time`, `echo`, `scroll`, `div0`, `pwd`, `ls`, `cd`, `mkdir`, `touch`,
  `cat`, `write`, `rm`.

#### Pruebas y herramientas

* `tools/qemu_ctrl.py`: control de QEMU (KVM/TCG, monitor, sendkey,
  screendump, ratón QMP, cierre limpio).
* `tools/ppm_to_png.py`: conversión PPM→PNG sin PIL y análisis de capturas.
* `tools/run_tests.py`: suite real de verificación en QEMU con capturas PNG y
  resumen JSON.
* `tools/patch_multiboot_text.py`: kernel auxiliar para el arranque en modo
  texto VGA.
* Documentación: `README.md`, `docs/BUILD.md`, `docs/RUN.md`,
  `docs/FEATURES.md`, `docs/LIMITATIONS.md`, `docs/PAKMAN_SEREOS.md`,
  `docs/AUDIO.md`, `docs/PAKU_AUDIT.md` y `docs/reference/`.

## [0.2]

* GDT propia, IDT con excepciones, PIC, PIT, teclado PS/2 y shell de texto
  (`help`, `clear`, `about`, `mem`, `ticks`, `echo`, `scroll`, `div0`).

## [0.1]

* Esqueleto inicial basado en OSDev Bare Bones: arranque Multiboot y consola
  VGA de texto.
