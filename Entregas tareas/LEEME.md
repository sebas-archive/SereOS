# LEEME — cómo está organizada la entrega

Este workspace quedó reorganizado para que su **nivel superior** contenga
**solo 3 carpetas principales**. Nada se borró: todos los archivos que antes
estaban sueltos en la raíz se **movieron** a `Entregas tareas/` manteniendo su
contenido intacto.

```
sereos02/
├── sistema operativo/      # componente 1: SereOS bare-metal
├── Pac-man SereOS/         # componente 2: el juego PAC-MAN SereOS
└── Entregas tareas/        # documentación, entregables congelados y evidencias
```

## 1. `sistema operativo/` — componente SereOS

Sistema operativo propio i686 (C99 + NASM, GRUB 2 / Multiboot 1). Aquí están
las **ISO y binarios arrancables**:

- `sistema operativo/sereos.iso` — ISO arrancable de la entrega.
- `sistema operativo/sereos.bin` — imagen binaria del kernel.
- `sistema operativo/sereos-text.bin` — variante de arranque en modo texto.

Build y ejecución (requiere `gcc` multilib, `nasm`, `grub-mkrescue`, QEMU):

```sh
cd "sistema operativo"
make clean && make     # -> sereos.iso + sereos.bin
make run               # QEMU
make run-audio         # QEMU + SB16/PipeWire
python3 tools/run_tests.py
```

El contenido de esta carpeta **no se tocó** durante la reorganización.

## 2. `Pac-man SereOS/` — componente PAC-MAN SereOS

Juego arcade con una sola lógica compartida (`src/core` + `src/render`) y dos
backends: SereOS nativo (freestanding) y Linux/SDL2. Aquí están los
**binarios finales del juego**:

- `Pac-man SereOS/build/pacman-sereos` — binario Linux/SDL2.
- `Pac-man SereOS/build/sereos/libpacman.a` — librería nativa para SereOS
  (exporta `app_t *app_game(void)`).

```sh
cd "Pac-man SereOS"
make linux             # -> build/pacman-sereos
./run.sh               # compila si falta y ejecuta
make test              # 209 checks de core + 7/7 smoke
make sereos            # -> build/sereos/libpacman.a
```

El contenido de esta carpeta **no se tocó** durante la reorganización.

## 3. `Entregas tareas/` — documentación, entregables y evidencias

```
Entregas tareas/
├── README.md                      # documento global de la entrega (actualizado a la nueva estructura)
├── QA_REPORT.md                   # informe QA v3 (bugfixes task-38)
├── LEEME.md                       # este índice
├── SereOS_Proyecto_Final.docx     # memoria técnica (entregable congelado)
├── SereOS_Proyecto_Final.zip      # paquete congelado de la entrega
├── auditorias/                    # evidencias de auditoría de código y fixes
├── evidencias-qa/                 # evidencias de QA (Linux, audio, apagado, VirtualBox)
├── docs/                          # CODE_TREE.md, COLLISIONS.md, screenshots/
└── tools/                         # code_tree.py (generador del árbol de código)
```

### Entregables congelados

`SereOS_Proyecto_Final.docx` y `SereOS_Proyecto_Final.zip` son los **entregables
de la entrega final y no se modifican**. El ZIP conserva **la estructura
interna antigua** de la entrega, es decir, en su interior las dos carpetas
`Pac-man SereOS/` y `sistema operativo/` cuelgan de su raíz junto a
`README.md` y `SereOS_Proyecto_Final.docx`; no refleja la nueva carpeta
`Entregas tareas/` (esa carpeta es solo del workspace de trabajo).

### Evidencias de auditoría y QA

- `auditorias/` — auditorías de código (Paku-Paku/Recursos), rondas de
  correcciones (`fix-assets`, `fix-core`, `fix-docs`, `fix-linux`, `fix-sereos`),
  `verify/`, `final/`, `linux-audit/`, `sereos-audit/`, `events-audit/`,
  `wav-integrity/`, `_backup/` e `INFORME_FINAL_AUDIO.md`.
- `evidencias-qa/` — salidas de QA: `audit_linux/`, `qa_audio/`,
  `shutdown-test/` y `vbox_audio/`.

### Documentación y herramienta de árbol

- `docs/CODE_TREE.md` — árbol de código de los dos componentes.
- `docs/COLLISIONS.md` — colisiones de nombres entre ambos proyectos.
- `docs/screenshots/raw/` — capturas en bruto usadas por la documentación.
- `tools/code_tree.py` — utilidad de solo lectura que imprime el árbol de
  código (Python 3, librería estándar).

Al haber movido `docs/` y `tools/` **juntos**, el enlace relativo
`docs/CODE_TREE.md → ../tools/code_tree.py` sigue resolviendo.

## Cómo usar `code_tree.py` después del movimiento

El script detecta su raíz **buscando hacia arriba** la carpeta que contiene a la
vez `sistema operativo/` y `Pac-man SereOS/`, de modo que funciona en la nueva
ubicación; además acepta `--root` para forzar una raíz.

```sh
# desde la raíz del workspace (/home/t1an/Descargas/sereos02)
python3 "Entregas tareas/tools/code_tree.py" --depth 1

# o desde la carpeta de la entrega
cd "Entregas tareas"
python3 tools/code_tree.py                     # árbol, 3 niveles
python3 tools/code_tree.py --depth 2
python3 tools/code_tree.py --sizes
python3 tools/code_tree.py --dup --sizes --only "Pac-man SereOS"
python3 tools/code_tree.py --markdown > docs/CODE_TREE.md   # regenerar (escaneo largo)
```

## Verificación de la reorganización

- `ls -1A` en `/home/t1an/Descargas/sereos02` muestra **solo** las 3 carpetas
  principales (`Entregas tareas`, `Pac-man SereOS`, `sistema operativo`), sin
  archivos sueltos ni ocultos.
- El número de archivos y el total de bytes de `auditorias/`,
  `evidencias-qa/`, `docs/` y `tools/` coincide con el inventario previo; solo
  se añadió este `LEEME.md` y se editaron `README.md`, `docs/CODE_TREE.md` y
  `tools/code_tree.py` para reflejar la nueva estructura.
