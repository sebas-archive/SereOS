# Árbol de código — SereOS + PAC-MAN SereOS

Documento generado automáticamente por [`tools/code_tree.py`](../tools/code_tree.py) (Python 3, solo librería estándar). No editar a mano: se regenera con el comando de abajo.

## Qué es cada proyecto

### `sistema operativo/`

SereOS Desktop: sistema operativo propio **bare-metal** para x86 de 32 bits (i686), escrito en C99 y NASM, que arranca con GRUB 2 / Multiboot 1 y no usa Linux ni librerías del sistema anfitrión. Incluye escritorio gráfico estilo macOS, aplicaciones nativas (terminal, gestor de archivos, monitor, acerca de), y el juego PAC-MAN enlazado como librería freestanding. Subdirectorios: `boot/`, `kernel/`, `drivers/`, `memory/`, `process/`, `filesystem/`, `graphics/`, `gui/`, `apps/`, `shell/`, `libc/`, `include/`, más `docs/`, `tools/`, `assets/`, `audio/`, `isodir/` y `build/` (este último excluido del árbol por ser artefactos).

### `Pac-man SereOS/`

PAC-MAN SereOS: videojuego arcade original del proyecto, con una única lógica de juego compartida y **dos backends**: SereOS nativo (freestanding, exporta `app_t *app_game(void)`) y Linux/SDL2. Subdirectorios: `src/core/` (lógica), `src/render/` (dibujo), `src/platform/sereos/` y `src/platform/linux/` (backends), `include/`, `assets/` (fuentes/recursos), `tests/`, `tools/`, `docs/` y `build/` (excluido del árbol por ser artefactos).

## Cómo regenerar este documento

Este documento y la herramienta viven juntos en `Entregas tareas/`, así que los
comandos se ejecutan **desde esa carpeta**. `code_tree.py` detecta la raíz del
workspace buscando hacia arriba la carpeta que contiene `sistema operativo/` y
`Pac-man SereOS/` (también se puede forzar con `--root`). `--markdown` escribe
la salida relativa al directorio actual, por lo que hay que redirigirla a
`docs/CODE_TREE.md` desde dentro de `Entregas tareas/`:

```bash
# desde la raíz del workspace
cd "Entregas tareas"

# regenerar este documento (relativo al cwd de "Entregas tareas")
python3 tools/code_tree.py --markdown > docs/CODE_TREE.md
```

Vistas rápidas en la terminal (sin generar archivo):

```bash
cd "Entregas tareas"
python3 tools/code_tree.py                      # árbol, 3 niveles
python3 tools/code_tree.py --depth 2            # más compacto
python3 tools/code_tree.py --sizes              # líneas por archivo
python3 tools/code_tree.py --filter .c,.h       # solo C
python3 tools/code_tree.py --dup --sizes --only "Pac-man SereOS"
python3 tools/code_tree.py --stats              # tabla por directorio
python3 tools/code_tree.py --only "sistema operativo" --depth 2
```

También funciona invocándolo por ruta desde la raíz del workspace, porque el
script resuelve su raíz por sí mismo:

```bash
python3 "Entregas tareas/tools/code_tree.py" --depth 1
```

## Estadísticas por directorio

### `sistema operativo/`

| Directorio | Archivos | Líneas |
|---|---:|---:|
| `./` | 127 | 76575 |
| `apps/` | 9 | 2157 |
| `apps/about/` | 2 | 360 |
| `apps/filemanager/` | 2 | 861 |
| `apps/sysmonitor/` | 2 | 466 |
| `apps/terminal/` | 2 | 450 |
| `assets/` | 1 | 48 |
| `assets/logo/` | 1 | 48 |
| `audio/` | 4 | 7458 |
| `boot/` | 2 | 166 |
| `docs/` | 17 | 4095 |
| `docs/reference/` | 7 | 1092 |
| `drivers/` | 16 | 1934 |
| `filesystem/` | 2 | 484 |
| `graphics/` | 11 | 17272 |
| `gui/` | 25 | 30698 |
| `include/` | 2 | 41 |
| `isodir/` | 1 | 16 |
| `isodir/boot/` | 1 | 16 |
| `isodir/boot/grub/` | 1 | 16 |
| `kernel/` | 8 | 515 |
| `libc/` | 2 | 259 |
| `memory/` | 4 | 528 |
| `process/` | 4 | 273 |
| `shell/` | 2 | 760 |
| `tools/` | 12 | 9025 |

> Conteos acumulados (incluyen subdirectorios); la fila raíz es el total del proyecto.

### `Pac-man SereOS/`

| Directorio | Archivos | Líneas |
|---|---:|---:|
| `./` | 64 | 48147 |
| `assets/` | 15 | 33777 |
| `assets/fonts/` | 4 | 14391 |
| `assets/res_original/` | 1 | 54 |
| `docs/` | 5 | 2076 |
| `include/` | 4 | 395 |
| `src/` | 27 | 6778 |
| `src/core/` | 14 | 3140 |
| `src/platform/` | 7 | 2255 |
| `src/platform/linux/` | 4 | 1536 |
| `src/platform/sereos/` | 3 | 719 |
| `src/render/` | 6 | 1383 |
| `tests/` | 7 | 1713 |
| `tools/` | 3 | 3064 |

> Conteos acumulados (incluyen subdirectorios); la fila raíz es el total del proyecto.

## Árbol completo

### `sistema operativo/`

```text
sistema operativo/
├── apps/  (9 archivos, 2157 líneas)
│   ├── about/  (2 archivos, 360 líneas)
│   │   ├── about.c  (350 líneas)
│   │   └── about.h  (10 líneas)
│   ├── filemanager/  (2 archivos, 861 líneas)
│   │   ├── filemanager.c  (851 líneas)
│   │   └── filemanager.h  (10 líneas)
│   ├── sysmonitor/  (2 archivos, 466 líneas)
│   │   ├── sysmonitor.c  (456 líneas)
│   │   └── sysmonitor.h  (10 líneas)
│   ├── terminal/  (2 archivos, 450 líneas)
│   │   ├── terminal_app.c  (440 líneas)
│   │   └── terminal_app.h  (10 líneas)
│   └── apps.c  (20 líneas)
├── assets/  (1 archivo, 48 líneas)
│   └── logo/  (1 archivo, 48 líneas)
│       └── README.md  (48 líneas)  ⚠ dup
├── audio/  (4 archivos, 7458 líneas)
│   ├── audio.c  (336 líneas)
│   ├── audio.h  (54 líneas)
│   ├── sfx_data.c  (7024 líneas)
│   └── sfx_data.h  (44 líneas)
├── boot/  (2 archivos, 166 líneas)
│   ├── boot.s  (43 líneas)
│   └── isr.s  (123 líneas)
├── docs/  (17 archivos, 4095 líneas)
│   ├── reference/  (7 archivos, 1092 líneas)
│   │   ├── constants.md  (258 líneas)
│   │   ├── gen_levels.py  (151 líneas)
│   │   ├── gen_maze.py  (369 líneas)
│   │   ├── levels.csv  (22 líneas)
│   │   ├── maze.c  (146 líneas)
│   │   ├── maze.txt  (115 líneas)
│   │   └── README.md  (31 líneas)  ⚠ dup
│   ├── AUDIO.md  (309 líneas)
│   ├── BUILD.md  (201 líneas)
│   ├── DESIGN.md  (387 líneas)
│   ├── FEATURES.md  (269 líneas)
│   ├── ICONS.md  (85 líneas)
│   ├── LIMITATIONS.md  (193 líneas)
│   ├── LOGO.md  (225 líneas)
│   ├── PAKMAN_SEREOS.md  (225 líneas)
│   ├── PAKU_AUDIT.md  (776 líneas)
│   └── RUN.md  (333 líneas)
├── drivers/  (16 archivos, 1934 líneas)
│   ├── input.c  (208 líneas)
│   ├── input.h  (93 líneas)
│   ├── keyboard.c  (334 líneas)
│   ├── mouse.c  (269 líneas)
│   ├── rtc.c  (206 líneas)
│   ├── rtc.h  (21 líneas)
│   ├── sb16.c  (277 líneas)
│   ├── sb16.h  (44 líneas)
│   ├── serial.c  (81 líneas)
│   ├── serial.h  (12 líneas)
│   ├── speaker.c  (74 líneas)
│   ├── speaker.h  (11 líneas)
│   ├── terminal.c  (195 líneas)
│   ├── terminal.h  (24 líneas)
│   ├── timer.c  (72 líneas)
│   └── timer.h  (13 líneas)
├── filesystem/  (2 archivos, 484 líneas)
│   ├── fs.c  (429 líneas)
│   └── fs.h  (55 líneas)
├── graphics/  (11 archivos, 17272 líneas)
│   ├── font.c  (91 líneas)
│   ├── font.h  (20 líneas)
│   ├── font_data.c  (160 líneas)
│   ├── framebuffer.c  (782 líneas)
│   ├── framebuffer.h  (55 líneas)
│   ├── graphics.c  (1456 líneas)
│   ├── graphics.h  (69 líneas)
│   ├── text.c  (422 líneas)
│   ├── text.h  (51 líneas)
│   ├── text_data.c  (14085 líneas)  ⚠ dup
│   └── text_internal.h  (81 líneas)  ⚠ dup
├── gui/  (25 archivos, 30698 líneas)
│   ├── app.c  (59 líneas)
│   ├── app.h  (38 líneas)
│   ├── cursor.c  (148 líneas)
│   ├── cursor.h  (12 líneas)
│   ├── desktop.c  (1753 líneas)
│   ├── desktop.h  (31 líneas)
│   ├── gui.c  (512 líneas)
│   ├── gui.h  (19 líneas)
│   ├── icons.c  (128 líneas)
│   ├── icons.h  (38 líneas)
│   ├── icons_data.c  (16085 líneas)
│   ├── logo.c  (589 líneas)
│   ├── logo.h  (107 líneas)
│   ├── logo_data.c  (7409 líneas)
│   ├── logo_data.h  (59 líneas)
│   ├── logo_ribbon_data.c  (2117 líneas)
│   ├── logo_ribbon_data.h  (35 líneas)
│   ├── splash.c  (253 líneas)
│   ├── splash.h  (10 líneas)
│   ├── theme.c  (68 líneas)
│   ├── theme.h  (148 líneas)
│   ├── ui.c  (279 líneas)
│   ├── ui.h  (51 líneas)
│   ├── window.c  (676 líneas)
│   └── window.h  (74 líneas)
├── include/  (2 archivos, 41 líneas)
│   ├── io.h  (27 líneas)
│   └── sereos_version.h  (14 líneas)
├── isodir/  (1 archivo, 16 líneas)
│   └── boot/  (1 archivo, 16 líneas)
│       └── grub/  (1 archivo, 16 líneas)
│           └── grub.cfg  (16 líneas)
├── kernel/  (8 archivos, 515 líneas)
│   ├── gdt.c  (33 líneas)
│   ├── idt.c  (64 líneas)
│   ├── interrupts.h  (21 líneas)
│   ├── kernel.c  (145 líneas)
│   ├── log.c  (153 líneas)
│   ├── log.h  (19 líneas)
│   ├── panic.c  (70 líneas)
│   └── panic.h  (10 líneas)
├── libc/  (2 archivos, 259 líneas)
│   ├── string.c  (226 líneas)
│   └── string.h  (33 líneas)
├── memory/  (4 archivos, 528 líneas)
│   ├── kmalloc.c  (215 líneas)
│   ├── kmalloc.h  (21 líneas)
│   ├── page.c  (264 líneas)
│   └── page.h  (28 líneas)
├── process/  (4 archivos, 273 líneas)
│   ├── scheduler.c  (79 líneas)
│   ├── scheduler.h  (14 líneas)
│   ├── task.c  (136 líneas)
│   └── task.h  (44 líneas)
├── shell/  (2 archivos, 760 líneas)
│   ├── shell.c  (711 líneas)
│   └── shell.h  (49 líneas)
├── tools/  (12 archivos, 9025 líneas)
│   ├── gen_audio.py  (392 líneas)
│   ├── gen_font.py  (394 líneas)
│   ├── gen_logo.py  (687 líneas)
│   ├── gen_pacman_assets.py  (1092 líneas)  ⚠ dup
│   ├── gen_ui_fonts.py  (663 líneas)  ⚠ dup
│   ├── gen_ui_icons.py  (580 líneas)
│   ├── make_comparison.py  (95 líneas)
│   ├── patch_multiboot_mode.py  (43 líneas)
│   ├── patch_multiboot_text.py  (43 líneas)
│   ├── ppm_to_png.py  (520 líneas)
│   ├── qemu_ctrl.py  (891 líneas)
│   └── run_tests.py  (3625 líneas)
├── CHANGELOG.md  (372 líneas)
├── grub.cfg  (16 líneas)
├── linker.ld  (36 líneas)
├── Makefile  (130 líneas)  ⚠ dup
└── README.md  (292 líneas)  ⚠ dup
```

### `Pac-man SereOS/`

```text
Pac-man SereOS/
├── assets/  (15 archivos, 33777 líneas)
│   ├── fonts/  (4 archivos, 14391 líneas)
│   │   ├── LICENSE.md  (200 líneas)
│   │   ├── LICENSE_ARCADE.md  (25 líneas)
│   │   ├── text_data.c  (14085 líneas)  ⚠ dup
│   │   └── text_internal.h  (81 líneas)  ⚠ dup
│   ├── res_original/  (1 archivo, 54 líneas)
│   │   └── LICENSE_RES.md  (54 líneas)
│   ├── font_arcade.c  (11237 líneas)
│   ├── font_arcade.h  (60 líneas)
│   ├── LICENSE_RES.md  (54 líneas)
│   ├── README.md  (168 líneas)  ⚠ dup
│   ├── sfx_res.c  (6510 líneas)
│   ├── sfx_res.h  (83 líneas)
│   ├── sprites.c  (702 líneas)
│   ├── sprites.h  (49 líneas)
│   ├── sprites_res.c  (417 líneas)
│   └── sprites_res.h  (52 líneas)
├── docs/  (5 archivos, 2076 líneas)
│   ├── ARCHITECTURE.md  (275 líneas)
│   ├── AUDIT_PAKUPAKU.md  (621 líneas)
│   ├── AUDIT_RESOURCES.md  (896 líneas)
│   ├── GAME.md  (133 líneas)
│   └── INTEGRATION.md  (151 líneas)
├── include/  (4 archivos, 395 líneas)
│   ├── pac_platform.h  (234 líneas)
│   ├── pac_theme.h  (58 líneas)
│   ├── pac_ui.h  (25 líneas)
│   └── pacman.h  (78 líneas)
├── src/  (27 archivos, 6778 líneas)
│   ├── core/  (14 archivos, 3140 líneas)
│   │   ├── game.c  (945 líneas)
│   │   ├── game_ai.c  (492 líneas)
│   │   ├── game_ai.h  (39 líneas)
│   │   ├── game_audio.c  (85 líneas)
│   │   ├── game_audio.h  (13 líneas)
│   │   ├── game_entities.c  (534 líneas)
│   │   ├── game_entities.h  (22 líneas)
│   │   ├── game_input.c  (137 líneas)
│   │   ├── game_input.h  (15 líneas)
│   │   ├── game_maze.c  (416 líneas)
│   │   ├── game_maze.h  (55 líneas)
│   │   ├── pac_game.h  (324 líneas)
│   │   ├── pac_util.c  (54 líneas)
│   │   └── pac_util.h  (9 líneas)
│   ├── platform/  (7 archivos, 2255 líneas)
│   │   ├── linux/  (4 archivos, 1536 líneas)
│   │   │   ├── main.c  (223 líneas)
│   │   │   ├── platform_linux.c  (859 líneas)
│   │   │   ├── platform_linux.h  (27 líneas)
│   │   │   └── text_linux.c  (427 líneas)
│   │   └── sereos/  (3 archivos, 719 líneas)
│   │       ├── game_app.c  (167 líneas)
│   │       ├── platform_sereos.c  (536 líneas)
│   │       └── platform_sereos.h  (16 líneas)
│   └── render/  (6 archivos, 1383 líneas)
│       ├── arcade_text.c  (122 líneas)
│       ├── arcade_text.h  (17 líneas)
│       ├── game_render.c  (1150 líneas)
│       ├── game_render.h  (13 líneas)
│       ├── pac_theme.c  (40 líneas)
│       └── pac_ui.c  (41 líneas)
├── tests/  (7 archivos, 1713 líneas)
│   ├── core_tests.c  (1020 líneas)
│   ├── legacy_font.c  (91 líneas)
│   ├── legacy_font.h  (20 líneas)
│   ├── legacy_font_data.c  (160 líneas)
│   ├── mock_platform.c  (328 líneas)
│   ├── mock_platform.h  (33 líneas)
│   └── run_tests.sh  (61 líneas)
├── tools/  (3 archivos, 3064 líneas)
│   ├── gen_pacman_assets.py  (1008 líneas)  ⚠ dup
│   ├── gen_pacman_res_assets.py  (1393 líneas)
│   └── gen_ui_fonts.py  (663 líneas)  ⚠ dup
├── Makefile  (100 líneas)  ⚠ dup
├── README.md  (195 líneas)  ⚠ dup
└── run.sh  (49 líneas)
```

## Notas

- **Exclusiones:** `build/`, `.git/`, `__pycache__/`, `docs/screenshots/` (capturas), archivos binarios por extensión (`.png`, `.jpg`, `.zip`, `.docx`, `.bin`, `.iso`, `.img`, `.o`, `.a`, `.d`, `.pyc`, `.wav`, `.ttf`, `.ppm`, …) y archivos de más de 200 KB sin extensión de texto conocida. Por eso los totales pueden ser menores que `find | wc -l`.
- **`--sizes`** cuenta líneas reales (`\n`) de cada archivo de texto; los binarios (solo visibles con `--all`) muestran su tamaño.
- **`⚠ dup`** marca archivos cuyo nombre también existe en el otro proyecto (p. ej. `Makefile`, `README.md`, `text_data.c`).
- Este documento no incluye la documentación de la entrega (`README.md`,
  `QA_REPORT.md`, `.docx`, `.zip`), que vive junto a `docs/` y `tools/` en
  `Entregas tareas/`: muestra solo los dos proyectos de código
  (`sistema operativo/` y `Pac-man SereOS/`), que son las otras dos carpetas
  principales del workspace.

