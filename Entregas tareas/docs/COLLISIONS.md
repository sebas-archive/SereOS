# Por qué "chocan" los cambios — sereos02

**Fecha del análisis:** 2026-11-20 04:30 (-05) · **Workspace:** `/home/t1an/Descargas/sereos02`
**Método:** hashes SHA-256 de ambos árboles, traza de escrituras de los generadores, lectura de los dos `Makefile` y línea de tiempo de mtimes (`find -newermt`).

---

## TL;DR — 3 causas, de mayor a menor impacto

1. **Hay otra sesión de agente escribiendo en esta misma carpeta ahora mismo.** Entre las 04:24:34 y las 04:27:27 se regeneraron assets del juego, se editó `src/render/game_render.c` y se reconstruyeron `sereos.bin` y `sereos.iso` (evidencia en §4). Si tú editas mientras el otro proceso regenera o compila, tus cambios desaparecen o quedan mezclados.
2. **Archivos duplicados entre los dos árboles, y un generador divergente.** El mismo `gen_pacman_assets.py` existe en los dos lados pero escribe a **destinos distintos** y con **contratos distintos** (8 frutas vs 5). Editas la copia que no se usa y "no pasa nada"; o corres la copia equivocada y aparece un `apps/game/` que el README dice que no debe existir.
3. **No hay git.** Ni historial, ni `git status`, ni forma de ver qué cambió o de recuperar lo pisado. Además `build/`, `isodir/`, `*.bin` y `*.iso` viven dentro del árbol y se regeneran, así que se confunden con el código fuente.

---

## 1. Cómo ver el árbol (tú mismo)

```bash
cd ~/Descargas/sereos02/"Entregas tareas"   # docs/ y tools/ viven aquí

python3 tools/code_tree.py                 # árbol de los 2 proyectos (3 niveles)
python3 tools/code_tree.py --depth 2       # compacto
python3 tools/code_tree.py --sizes         # con líneas por archivo
python3 tools/code_tree.py --stats         # tabla archivos/líneas por directorio
python3 tools/code_tree.py --dup --sizes   # árbol marcando archivos duplicados
python3 tools/code_tree.py --filter .c,.h,.py
python3 tools/code_tree.py --only "Pac-man SereOS" --depth 4
```

El script resuelve su raíz buscando hacia arriba la carpeta que contiene
`sistema operativo/` y `Pac-man SereOS/`, así que también funciona como
`python3 "Entregas tareas/tools/code_tree.py"` desde la raíz del workspace
(o con `--root`). `--markdown` escribe relativo al directorio actual: hay que
ejecutarlo desde `Entregas tareas/`.

También: `docs/CODE_TREE.md` (volcado completo, se regenera con
`python3 tools/code_tree.py --markdown > docs/CODE_TREE.md` desde
`Entregas tareas/`), o el explorador de VS Code
(`code "/home/t1an/Descargas/sereos02"` → `Ctrl+Shift+E`).

**Snapshot actual:** `sistema operativo/` = 127 archivos / 76 575 líneas ·
`Pac-man SereOS/` = 64 archivos / 48 147 líneas.

---

## 2. Archivos que existen en LOS DOS árboles (hash SHA-256)

| Estado | Basename | bytes | Ruta A (sistema operativo) | Ruta B (Pac-man SereOS) |
|---|---|---:|---|---|
| ⚠️ **DIVERGE** | `gen_pacman_assets.py` | 40 028 | `tools/gen_pacman_assets.py` (1092 líneas) | `tools/gen_pacman_assets.py` (975 líneas) |
| **IDÉNTICO** | `gen_ui_fonts.py` | 28 515 | `tools/gen_ui_fonts.py` | `tools/gen_ui_fonts.py` |
| **IDÉNTICO** | `text_data.c` | 1 246 642 | `graphics/text_data.c` | `assets/fonts/text_data.c` |
| **IDÉNTICO** | `text_internal.h` | 4 028 | `graphics/text_internal.h` | `assets/fonts/text_internal.h` |
| diverge (normal) | `Makefile` | 5 163 | `Makefile` (kernel, 130 líneas) | `Makefile` (juego, 100 líneas) |
| diverge (normal) | `README.md` | varios | `README.md`, `docs/reference/README.md`, `assets/logo/README.md` | `README.md`, `assets/README.md` |

Extra: `sistema operativo/graphics/font.h` y `Pac-man SereOS/tests/legacy_font.h`
son **el mismo archivo con dos nombres** (mismo hash `c2c4fc22e8e7`).

> Los `text_data.c` / `text_internal.h` de `graphics/` y de `assets/fonts/` son
> idénticos **hoy** (02:03). Copia manual, no symlink: el día que regeneres uno,
> el otro se queda viejo y el que compile dependerá de qué `Makefile` corras.

---

## 3. Generadores: quién escribe qué y A DÓNDE

| Script | Línea del destino | Escribe | Destino real |
|---|---|---|---|
| `sistema operativo/tools/gen_pacman_assets.py` | `999` | `assets.c`, `preview.png` | `sistema operativo/apps/game/assets/` ← **ese directorio NO existe** (el README dice que el juego no se duplica en el OS) |
| `Pac-man SereOS/tools/gen_pacman_assets.py` | `916` | `sprites.c`, `preview.png` | `Pac-man SereOS/assets/` ← el que se usa de verdad |
| `Pac-man SereOS/tools/gen_pacman_res_assets.py` | `45–47` (`ROOT`/`DEFAULT_OUT`) + `625,679,819,882` | `sprites_res.c/h`, `font_arcade.c/h`, licencias (`208`) | `Pac-man SereOS/assets/` (solo existe aquí; el árbol OS no tiene esta herramienta) |
| `sistema operativo/tools/gen_ui_fonts.py` | `69` (`DEFAULT_OUT = ROOT/graphics/text_data.c`) | `graphics/text_data.c` | En el árbol OS: `sistema operativo/graphics/`. La copia de `Pac-man SereOS/tools/` escribiría en `Pac-man SereOS/graphics/` ← **ese directorio no existe** |
| `Pac-man SereOS/tools/gen_pacman_res_assets.py` | `208` | `assets/res_original/`, `LICENSE_RES.md`, `assets/fonts/LICENSE_ARCADE.md` | `Pac-man SereOS/assets/` |

**La divergencia que muerde** (diff entre las dos copias de `gen_pacman_assets.py`):

* Versión **Pac-man**: 5 frutas (`["CEREZA","FRESA","NARANJA","MANZANA","UVAS"]`, línea 974) → `assets/sprites.c`.
* Versión **OS**: 8 frutas (añade `MELON`, `BELL`, `STAR`, líneas 1057) → `apps/game/assets/assets.c`.

Son dos versiones del mismo generador con destinos y contratos distintos: no se
puede "arreglar" una sin decidir cuál es la buena.

---

## 4. Línea de tiempo: alguien más está escribiendo aquí

| Hora | Qué pasó |
|---|---|
| 02:03 | Copia manual `text_data.c` / `text_internal.h` a `Pac-man SereOS/assets/fonts/` |
| 04:21 | Se generó `docs/CODE_TREE.md` (snapshot de este análisis) |
| 04:24:34 | `Pac-man SereOS/docs/AUDIT_RESOURCES.md` reescrito |
| 04:24:41–04:24:49 | Regenerados `assets/sprites.c`, `preview.png`, `sprites_res.c/h`, `font_arcade.c/h`, `sfx_res.c/h`, licencias |
| 04:24:56 | `Pac-man SereOS/README.md` y `assets/README.md` reescritos |
| 04:25:23 | Editado `src/render/game_render.c` |
| 04:26 | Screenshots de verificación en `/tmp` (`a2_*_zoom.png`, `verify_harness.c`) |
| 04:27:27 | Reconstruidos `sereos.bin`, `sereos-text.bin`, `isodir/boot/*`, `sereos.iso` |

Rastros en `/tmp`: `v2_os_build.log`, `repro_gen2.log`, `verify_harness.c`,
`task12_build.log`, `final_clean_build.log`. **No** son de esta sesión
(esta sesión no compiló ni regeneró assets). Es una **segunda sesión/agente**
trabajando el mismo directorio en ráfagas.

Prueba de que los artefactos ya no coinciden con el QA entregado: el
`QA_REPORT.md` certifica `sereos.bin` = **1 250 856 B** (md5 `dfd3bc7d…`), y el
binario actual pesa **1 455 648 B**. Dos builds distintos del mismo árbol.

**Riesgo concreto:** dos `make` a la vez sobre el mismo `build/` producen
objetos a medio escribir, `sereos.bin` inconsistente y un ISO que arranca mal;
dos generadores a la vez producen `.c` con el contenido del otro proceso.

---

## 5. Quién manda en el build (no hay copias entre árboles)

* `sistema operativo/Makefile:28` → `GAME_DIR ?= ../Pac-man SereOS`; `:74` compila
  `build/sereos/libpacman.a` desde el árbol del juego pasándole `OS_DIR`.
  **No copia fuentes** del juego al OS (solo enlaza la librería).
* `Pac-man SereOS/Makefile:14` → `OS_DIR ?= ../sistema operativo`; `:40-45` usa los
  headers del OS (`-I"$(OS_DIR)/…"`). Tampoco escribe dentro del OS.
* Cada uno escribe **su propio** `build/`; el OS además arma `isodir/` + `sereos.iso`
  (`sistema operativo/Makefile:89-96`), con `rm -rf isodir` en cada corrida.

=> Los "choques" **no** vienen de que `make` copie archivos, sino de
(a) dos escritores concurrentes, (b) fuentes duplicadas que divergen y
(c) artefactos regenerables conviviendo con el código.

---

## 6. Plan para dejar de chocar (en este orden)

1. **Un solo escritor a la vez.** Cierra/pausa la otra sesión de agente (Claude
   Desktop / terminal) antes de editar. Regla práctica: un agente + un `make`.
2. **Fuente de verdad explícita:**
   * kernel/OS → `sistema operativo/`
   * juego → `Pac-man SereOS/`
   * El generador del OS (`sistema operativo/tools/gen_pacman_assets.py`) está
     desfasado y escribe a `apps/game/`: apartarlo como legacy (o borrarlo) y
     quedarse con el de `Pac-man SereOS/tools/`.
   * `Pac-man SereOS/assets/fonts/text_data.c|text_internal.h`: o se genera ahí,
     o son un **symlink** a `sistema operativo/graphics/…`. Nunca dos copias.
3. **Meter git** (no destructivo, 1 minuto) para ver y recuperar cambios:
   ```bash
   cd ~/Descargas/sereos02
   git init
   printf 'build/\nisodir/\n*.o\n*.a\n*.d\n*.bin\n*.iso\n*.img\n__pycache__/\ndocs/screenshots/\n*.pyc\n' > .gitignore
   git add -A && git commit -m "snapshot: estado actual SereOS + PAC-MAN"
   ```
   A partir de ahí: `git status` te dice qué cambió y `git diff` qué exactamente.
4. **No editar generados a mano** (§7). Si hay que cambiarlos, se cambia el
   generador y se regenera.
5. **Un solo comando de build** y de una terminal:
   `cd "sistema operativo" && make` (ya compila la lib del juego y arma el ISO).
6. **Comprobar duplicados** antes y después de un cambio:
   `python3 "Entregas tareas/tools/code_tree.py" --dup --sizes`

---

## 7. Archivos GENERADOS — no editar a mano

| Archivo | Lo regenera |
|---|---|
| `sistema operativo/graphics/text_data.c`, `text_internal.h` | `python3 sistema\ operativo/tools/gen_ui_fonts.py` |
| `Pac-man SereOS/assets/fonts/text_data.c`, `text_internal.h` | copia manual de los de arriba (o symlink) |
| `Pac-man SereOS/assets/sprites.c`, `preview.png` | `python3 "Pac-man SereOS/tools/gen_pacman_assets.py"` |
| `Pac-man SereOS/assets/sprites_res.c/h`, `font_arcade.c/h`, `sfx_res.c/h`, `LICENSE_RES.md`, `assets/fonts/LICENSE_ARCADE.md`, `assets/res_original/` | `python3 "Pac-man SereOS/tools/gen_pacman_res_assets.py"` (requiere Pillow + NumPy) |
| `sistema operativo/sereos.bin`, `sereos-text.bin`, `sereos.iso`, `isodir/**` | `make` en `sistema operativo/` |
| `Pac-man SereOS/build/**`, `sistema operativo/build/**` | `make` |

Si un cambio "no aparece", primero mira **si el archivo es generado**: tu edición
se pierde en el siguiente build.
