# Compilación de SereOS v1.0

SereOS es un sistema operativo *bare-metal* de 32 bits (i686) escrito en C99 y
NASM. El resultado de la compilación es un kernel Multiboot 1 (`sereos.bin`) y
una imagen ISO arrancable con GRUB 2 (`sereos.iso`).

## Requisitos

### Arch Linux / CachyOS

```bash
sudo pacman -S --needed base-devel nasm grub xorriso mtools qemu-system-x86
```

| Paquete | Para qué se usa |
|---|---|
| `base-devel` | `gcc`, `make`, `binutils` (en CachyOS viene instalado) |
| `nasm` | ensamblador de `boot/boot.s` e `boot/isr.s` |
| `grub` | `grub-mkrescue` y `grub-file` (validación Multiboot) |
| `xorriso`, `mtools` | herramientas que usa `grub-mkrescue` para crear la ISO |
| `qemu-system-x86` | emulador `qemu-system-i386` |

Para **regenerar** los atlases tipográficos e iconos del rediseño (opcional:
`graphics/text_data.c` y `gui/icons_data.c` ya están en el repositorio) hacen
falta las fuentes OFL y Pillow:

```bash
sudo pacman -S --needed inter-font ttf-jetbrains-mono
python3 tools/gen_ui_fonts.py      # Inter + JetBrains Mono -> text_data.c
python3 tools/gen_ui_icons.py      # iconografia lineal -> icons_data.c
```

Comprueba que todo está disponible:

```bash
for t in gcc make nasm grub-mkrescue grub-file xorriso mformat qemu-system-i386; do
    command -v "$t" >/dev/null && echo "OK  $t" || echo "FALTA $t"
done
```

### Opción A: compilador cruzado i686-elf (recomendado)

El Makefile usa `i686-elf-gcc` si está en el `PATH`. Instalación desde AUR:

```bash
paru -S --needed i686-elf-gcc i686-elf-binutils
```

Con el compilador cruzado no hace falta ninguna biblioteca de 32 bits del
sistema: el compilador y su `libgcc` son específicos para i686-elf.

### Opción B: gcc del sistema en modo -m32 (sin cross compiler)

Si no hay `i686-elf-gcc`, el Makefile detecta el caso y compila con
`gcc -m32 -ffreestanding` (define `SEREOS_HOST_GCC`). En Arch/CachyOS esto
requiere el repositorio **multilib** habilitado y las bibliotecas de 32 bits:

```bash
# /etc/pacman.conf debe tener [multilib] habilitado
sudo pacman -S --needed lib32-gcc-libs
```

Si el enlazado falla con errores del tipo `cannot find -lgcc` o
`skipping incompatible .../libgcc.a`, falta `lib32-gcc-libs` (o usa la opción A).

## Componente del juego (dependencia)

El videojuego **PAC-MAN SereOS** (versión definitiva M2/M3/M4) ya no vive
dentro de este árbol: es el componente hermano `../Pac-man SereOS/` (una sola
copia de lógica/render para SereOS y Linux). La compilación del OS construye su
librería freestanding y la enlaza al kernel:

```bash
make game-lib                                # recompila el componente
make                                          # OS + lib enlazada
make GAME_DIR="/otra/ruta/Pac-man SereOS"     # componente en otra ubicacion
make game-clean                               # limpia el build del componente
```

`sereos.bin` depende de `$(GAME_DIR)/build/sereos/libpacman.a`, que se enlaza
**después de los objetos y antes de `-lgcc`**; `apps/apps.c` solo llama a
`app_game()`. Build aprobada por QA: `libpacman.a` 280.906 B md5
`28a84127e0ef206764ce48ef7bfd316d`, binario Linux 769.568 B md5
`42f33373157cf1bf2590215152e05ae3` (131/131 + 7/7 tests). El componente se compila con flags freestanding (`-m32
-ffreestanding`, sin SDL ni headers Linux) y usa `OS_DIR` para localizar los
headers de este árbol. Incluye recursos privados de `Res` (ver
[PAKMAN_SEREOS.md](PAKMAN_SEREOS.md) y
[LICENSE_RES.md](../Pac-man SereOS/assets/LICENSE_RES.md)); `make clean` no
borra la librería del componente.

## Compilar

La raíz del proyecto es la carpeta `sistema operativo/` (dentro de
`Descargas/sereos02/`); todos los comandos se ejecutan desde ella:

```bash
cd "sistema operativo"   # desde /home/t1an/Descargas/sereos02
make game-lib            # opcional: recompila ../Pac-man SereOS (libpacman.a)
make clean               # opcional: borra build/, sereos.bin, sereos-text.bin, sereos.iso, isodir/
make -j$(nproc)          # compila el OS y enlaza la libreria del juego
```

Salida esperada al final:

```
[OK] kernel multiboot valido
[OK] sereos.iso generada
```

Artefactos generados:

| Fichero / directorio | Contenido |
|---|---|
| `build/` | objetos `.o` y dependencias `.d` (un `.o` por `.c`/`.s`) |
| `sereos.bin` | kernel ELF32 Multiboot 1, validado con `grub-file` |
| `isodir/` | árbol temporal usado por `grub-mkrescue` |
| `sereos.iso` | imagen arrancable (GRUB 2 + kernel + `grub.cfg`) |
| `serial.log` | log del puerto serie COM1 creado al ejecutar `make run` |

El Makefile construye automáticamente todos los `.c` y `.s` del árbol
(excluyendo `tools/`), sin listas manuales de ficheros.

### Comprobar el kernel

```bash
grub-file --is-x86-multiboot sereos.bin && echo "Multiboot OK"
file sereos.bin sereos.iso
```

### Limpiar

```bash
make clean
```

Borra `build/`, `sereos.bin`, `sereos-text.bin`, `sereos.iso`, `isodir/`,
`serial.log`, `audio-capture.wav` y las capturas crudas
`docs/screenshots/raw/`. Las capturas PNG de `docs/screenshots/` se conservan.

## Ejecutar

```bash
make run            # QEMU con ventana (KVM si /dev/kvm es accesible)
make run-audio      # igual + Sound Blaster 16 con el backend del anfitrion
make run-audio-wav  # headless + SB16 grabando a audio-capture.wav
make run-headless   # QEMU sin ventana; log en serial.log (CI / capturas)
```

Ver [RUN.md](RUN.md) para los atajos de teclado, el monitor de QEMU y la
ejecución de las pruebas automatizadas.

## Pruebas automatizadas

Con la ISO ya compilada:

```bash
python3 tools/run_tests.py            # suite completa + capturas PNG
python3 tools/run_tests.py --list     # lista de pruebas
python3 tools/run_tests.py --only boot,game
python3 tools/run_tests.py --kvm off  # forzar TCG (sin KVM)
```

Las capturas se escriben en `docs/screenshots/` y el resumen en
`docs/screenshots/test-results.json`. Además de las pruebas funcionales, la
suite captura `02b_topbar_dock` (zoom barra+dock), `15_panic` (div0 real en
una VM aparte), `16_resolution_1280x1024` y `17_resolution_800x600` (ISOs
temporales en `/tmp` que parchean la petición de vídeo Multiboot, sin tocar el
repo). Opciones útiles: `--iso RUTA` y `--shots-dir DIR` para generar sets
sobre una ISO congelada (comparativa antes/después). El script sale con código
distinto de 0 si alguna prueba falla.

## Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| `make: nasm: No such file or directory` | instala `nasm` |
| `grub-mkrescue: command not found` | instala `grub` (y `xorriso`, `mtools`) |
| `grub-file: not found` | `grub-file` viene en el paquete `grub` |
| `error: cannot find -lgcc` / `skipping incompatible libgcc.a` | falta `lib32-gcc-libs` (multilib) o usa `i686-elf-gcc` |
| `ld: cannot find -lgcc` con cross compiler | instala `i686-elf-gcc` completo (incluye libgcc) |
| `qemu-system-i386: Could not access KVM kernel module` | `/dev/kvm` no accesible: añade el usuario al grupo `kvm`, o usa `make run` (sin KVM) y `python3 tools/run_tests.py --kvm off` |
| `make run`: no aparece ninguna ventana | usa `make run-headless` y revisa `serial.log`; comprueba que `sereos.iso` existe |
| La ISO arranca pero no llega al escritorio | revisa `serial.log` (marcadores y posibles `SEREOS_EXCEPTION`/`SEREOS_PANIC`) y prueba la 2ª entrada de GRUB (modo texto) |

## Estructura del proyecto

```
boot/        arranque Multiboot y stubs de interrupciones (NASM)
kernel/      núcleo: GDT, IDT, main, log, paneles de pánico
drivers/     serial COM1, teclado PS/2, ratón, PIT, RTC, PC speaker, VGA texto, input
memory/      allocator de marcos (4 KiB), paginación PSE y heap kmalloc
process/     tareas cooperativas y planificador round-robin
filesystem/  RAMFS (árbol de nodos en memoria)
graphics/    framebuffer, primitivas gráficas y fuente de mapa de bits
gui/         escritorio: ventanas, compositor, dock, barra, cursor, iconos, splash
apps/        terminal, gestor de archivos, monitor, acerca de y juego
shell/       intérprete de comandos compartido (VGA y terminal gráfica)
libc/        funciones de cadena/memoria básicas
tools/       scripts de pruebas QEMU y conversión de capturas
docs/        documentación y capturas
```
