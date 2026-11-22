# Ejecutar y probar SereOS v1.0

## Arrancar en QEMU

Con `sereos.iso` ya compilada (`make`):

```bash
make run            # QEMU con ventana en el escritorio del anfitrion
make run-audio      # igual + SB16 con el backend de audio del sistema
make run-audio-wav  # headless + SB16 grabando a audio-capture.wav
make run-headless   # QEMU sin ventana (útil por SSH / CI); log en serial.log
```

Todos los objetivos usan `qemu-system-i386` con 256 MiB de RAM y `-vga std`, y
añaden `-enable-kvm -cpu host` automáticamente **si `/dev/kvm` es escribible**.
Si no lo es, arrancan con emulación TCG (más lento).

* `run-audio` usa `-audiodev pipewire,id=snd0 -device sb16,audiodev=snd0`
  (`AUDIODEV` se puede cambiar en el Makefile, p.ej. a `pa` o `sdl`). Si el
  backend no está disponible, QEMU puede fallar: usa `make run`.
* `run-audio-wav` arranca sin ventana y graba el audio del SB16 emulado en
  `audio-capture.wav` con `-audiodev wav,id=snd0,path=audio-capture.wav`.
  El WAV se finaliza al cerrar QEMU; es la base del test automático de audio.

Comando equivalente manual:

```bash
qemu-system-i386 -m 256M -vga std -cdrom sereos.iso \
                 -serial file:serial.log -rtc base=localtime
# solo si /dev/kvm es accesible:
qemu-system-i386 -enable-kvm -cpu host -m 256M -vga std -cdrom sereos.iso \
                 -serial file:serial.log -rtc base=localtime
```

La primera vez que arranca aparece el menú de GRUB 2 durante **2 segundos**:

1. **SereOS 1.0 - SereOS Desktop** (por defecto): pide 1024x768x32 y arranca el
   escritorio gráfico.
2. **SereOS 1.0 - modo texto (diagnóstico)**: arranca la consola VGA de 80x25
   con la shell de texto (fallback si no hay framebuffer).

### Dónde ver los mensajes

Todo el diagnóstico del kernel sale por el puerto serie **COM1** y se guarda en
`serial.log` (la opción `-serial file:serial.log` está fijada en el Makefile y
en el arnés de pruebas). Mientras QEMU corre con ventana puedes abrir otra
terminal y seguirlo en vivo:

```bash
tail -f serial.log
```

En la propia máquina virtual, dentro del escritorio:

* **F2** abre la terminal gráfica: `dmesg` muestra el registro del kernel y
  `help` la lista de comandos.
* En modo texto, la shell VGA escribe directamente en pantalla.

## Atajos de teclado

### Escritorio

| Tecla | Acción |
|---|---|
| **F1** | Abrir el gestor de archivos |
| **F2** | Abrir la terminal gráfica |
| **F3** | Abrir el monitor del sistema |
| **F4** | Abrir «PAC-MAN SereOS» |
| **F5** | Abrir «Acerca de SereOS» |
| **F6** | Enfocar la siguiente ventana |
| **F7** | Minimizar la ventana activa |
| **Ctrl+W** / **Alt+W** | Cerrar la ventana activa (atajo pensado para las pruebas automatizadas) |

El ratón PS/2 también se usa para mover el cursor y pulsar los semáforos de las
ventanas (cerrar/minimizar/maximizar) y los iconos del dock. Las primitivas de
entrada son reales (IRQ 1 y IRQ 12); no hay simulación de teclado.

### PAC-MAN SereOS (F4)

| Tecla | Acción |
|---|---|
| Flechas o **WASD** | Mover a Pacman por el laberinto |
| **Enter** | Iniciar partida / confirmar en los menús |
| **Esc** | Pausa; desde el menú de pausa, volver |
| **R** | Reiniciar la partida |
| **Q** | Volver al título desde la pausa; en game over, Q/Esc salen al escritorio |
| **Esc** en la pantalla de título | Volver al escritorio |

Objetivo: comerse todos los dots del laberinto evitando a los 4 fantasmas.
Las *power pills* vuelven a los fantasmas azules (asustados) durante unos
segundos y permiten comérselos. Cada fantasma comido da puntos extra; hay
vidas, nivel y récord. Ver [PAKMAN_SEREOS.md](PAKMAN_SEREOS.md) para la arquitectura, la IA
de los fantasmas, el laberinto y el audio.

## Audio

SereOS reproduce efectos de sonido del juego con un driver de **Sound Blaster
16** (DSP, IRQ 5, DMA 1 por defecto) sobre la emulación de QEMU. Hay tres formas
de comprobarlo:

1. **Audible** (`make run-audio`): requiere un backend de audio del anfitrión
   (pipewire/pa/sdl, configurable con `AUDIODEV` en el Makefile). Abre el juego
   con **F4**, pulsa **Enter** y mueve a Pacman: se oyen los efectos.
2. **Grabado a WAV** (`make run-audio-wav`): arranca sin ventana, guarda el
   audio en `audio-capture.wav` y lo finaliza al cerrar QEMU. Para verificarlo
   manualmente:

   ```bash
   make run-audio-wav
   # en otra terminal, escribe por el monitor o juega tu mismo; al salir:
   python3 - <<'EOF'
   import wave
   with wave.open("audio-capture.wav", "rb") as w:
       print(w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes())
   EOF
   ```

3. **Automático**: la prueba `audio` de `tools/run_tests.py` arranca QEMU con
   `-audiodev wav,...,path=.../audio-capture.wav -device sb16`, abre el juego,
   inicia la partida, mueve a Pacman durante ~10 s y comprueba que el WAV
   existe, tiene datos PCM, dura al menos 0.3 s y sus muestras no son
   silenciosas (peak y RMS calculados en Python puro parseando los chunks
   WAV). Última pasada: **9,04 s**, 44,1 kHz, 16 bits, 2 canales, peak
   **23.296** (71% FS) y RMS **18.240** → audio real, no silencioso.

   Nota: QEMU puede dejar los tamaños de los chunks RIFF/data sin finalizar
   con `-audiodev wav`; el analizador usa los bytes reales del chunk `data`,
   así que la prueba sigue siendo válida.

Si el backend o el driver no están disponibles, el WAV puede existir pero estar
vacío o silencioso: la prueba lo reporta como fallo y no se oculta. Más detalle
del subsistema en [AUDIO.md](AUDIO.md).

## Terminal gráfica: comandos

La terminal del escritorio comparte el mismo intérprete que la consola de
texto (`shell/`). Comandos disponibles:

```
help                esta ayuda
clear               limpia la pantalla/scrollback
about               informacion de SereOS
version             version y datos de compilacion
sysinfo             resumen real del sistema
mem                 memoria fisica detectada
free                memoria libre y heap del kernel
ticks               ticks del PIT y tiempo encendido
dmesg               registro del kernel con marcas de tiempo
date / time         fecha y hora del reloj CMOS
echo <texto>        repite el texto
scroll              imprime 30 lineas (prueba de scroll)
div0                provoca una division por cero (prueba de la IDT)
pwd                 directorio actual del RAMFS
ls [ruta]           lista un directorio
cd <ruta>           cambia de directorio
mkdir <ruta>        crea un directorio
touch <archivo>     crea un archivo vacio
cat <archivo>       muestra un archivo de texto
write <archivo> <texto>  escribe texto en un archivo
rm <ruta>           borra un archivo o directorio vacio
```

`div0` provoca intencionadamente una excepción de división por cero para
demostrar la IDT y la pantalla de pánico; el sistema se detiene de forma segura
(es lo esperado, no un fallo del arnés). El arnés de pruebas **no** ejecuta
`div0`, porque su verificación exige ausencia de `SEREOS_EXCEPTION`.

## Probar el fallback de modo texto

Es la segunda entrada de GRUB y hay dos formas de arrancarla:

1. **Con teclado (recomendado, sin tocar nada):** al aparecer el menú de GRUB
   (2 s de timeout) pulsa **flecha abajo** y luego **Enter**. El log serie debe
   mostrar:

   ```
   SEREOS_TEXT_MODE
   ```

   El arnés lo automatiza con `sendkey down` + `sendkey ret`; si el timing
   falla, genera una ISO auxiliar con `default=1` y `timeout=0` para repetir la
   prueba de forma determinista.

2. **Fijando la entrada por defecto:** edita temporalmente `grub.cfg` y cambia
   `set default=0` por `set default=1` (o pon `set timeout=0`), recompila con
   `make`, arranca y comprueba `SEREOS_TEXT_MODE` en `serial.log`.

En modo texto la pantalla es VGA 80x25; puedes escribir los mismos comandos de
la shell (`help`, `ls`, `dmesg`…). QEMU sigue capturando la pantalla con
`screendump`, aunque el tamaño de la imagen será el del modo texto.

## Navegación adaptativa (dock <-> topnav)

Con **ninguna** ventana maximizada se muestra el **dock flotante** centrado y
la topbar con el nombre de la app. Al **maximizar** una ventana (semáforo verde
o doble clic en la barra de título):

* El **dock desaparece** (no hay barra inferior de ningún tipo) y la ventana
  se expande **full-height hasta `y=sh-1`** (1024: 30..767).
* Los **5 accesos** (Archivos, Terminal, Monitor, Pacman, Información) pasan a
  la **topbar central**, centrados en la pantalla (bloques 448..575 en 1024,
  336..463 en 800, 576..703 en 1280) con los mismos iconos del dock.
* El icono de la app activa se resalta con `accent_soft` + subrayado; las apps
  abiertas muestran un punto. Clic en un acceso: abre, enfoca o
  minimiza/restaura la app activa (sin duplicar `APP_OPEN`).
* La transición (~145 ms) baja y oculta el dock **antes** de mostrar la nav:
  sin iconos duplicados. Con **2 maximizadas** se mantiene topnav; al
  restaurar/minimizar la **última** vuelve el dock.

Escenarios cubiertos por las pruebas `dock` y `topnav`: `18_dock_window`,
`21_dock_restored`, `34_topnav_maximized`, `35_topnav_active`,
`36_topnav_restore_dock`, `37_topnav_multiwindow`,
`38_topnav_minimize_last`, `39_topnav_800` y `40_topnav_1280`; la suite
comprueba por píxeles ausencia de dock/barra inferior, app hasta `sh-1`,
centrado exacto de los 5 accesos, un único indicador activo, multicuenta,
minimizar la última, clics sin duplicados y transición sin iconos simultáneos.

## Capturas de pantalla## Capturas de pantalla

### Manualmente, con el monitor de QEMU

El arnés arranca QEMU con el monitor en un socket Unix. Con una ejecución
interactiva normal (`make run`) el monitor está en stdio: `Ctrl+Alt+2` cambia
a él y `Ctrl+Alt+1` vuelve a la pantalla.

Desde el monitor:

```
screendump /tmp/sereos.ppm
```

Ese comando escribe un PPM binario P6. Conviértelo a PNG y analízalo con las
herramientas del proyecto:

```bash
python3 tools/ppm_to_png.py /tmp/sereos.ppm docs/screenshots/desktop.png
python3 tools/ppm_to_png.py --stats docs/screenshots/desktop.png
python3 tools/ppm_to_png.py --check /tmp/sereos.ppm   # exit 1 si está negro
```

### Con el arnés de pruebas

```bash
python3 tools/run_tests.py                 # suite completa (18 pruebas)
python3 tools/run_tests.py --list          # nombres de las pruebas
python3 tools/run_tests.py --only boot,game,topnav
python3 tools/run_tests.py --kvm off       # sin KVM (TCG)
python3 tools/run_tests.py --timeout-scale 2
python3 tools/run_tests.py --no-grub-shot
python3 tools/run_tests.py --iso /tmp/iso-congelada/sereos.iso \
                           --shots-dir /tmp/set-antes   # set alternativo
```

La suite lanza QEMU headless con KVM (o TCG si no hay), espera los marcadores
del log serie, envía teclas por el monitor (`sendkey`), captura con
`screendump` y guarda:

* `docs/screenshots/*.png` — capturas finales: `00_grub_menu`, `01_splash`,
  `02_desktop`, `02b_topbar_dock`, `02c_dock_tooltip` (hover real sobre el
  icono del juego), `03_terminal` (help/ls/date/free/dmesg),
  `04_files` y `04b_files_home`, `05_monitor`, `06_about` (14/14 + audio),
  `07_pacman_titulo`, `08_pacman_ready`, `08b_pacman_partida`,
  `09_pacman_comiendo`, `10_pacman_frightened`, `11_pacman_pausa`,
  `12_pacman_gameover`, `13_multiventana`, `14_text_mode`, `15_panic`
  (div0 real), `16_resolution_1280x1024`, `17_resolution_800x600`,
  `18_dock_window`, `21_dock_restored`, `22_menu_logo`,
  `25_maximized_fullbleed`, `26_restore_exact`, `27_doubleclick`,
  `28_minimize_restore`, `29_max_terminal`, `30_resize`, `31_max_1280`,
  `32_max_800`, `33_window_corners_clean`, `34_topnav_maximized`,
  `35_topnav_active`, `36_topnav_restore_dock`, `37_topnav_multiwindow`,
  `38_topnav_minimize_last`, `39_topnav_800`, `40_topnav_1280`, más
  `compare_before_after.png` y el set previo en `screenshots/before/`.
* `docs/screenshots/raw/<fecha>/` — PPM crudos y `serial.log` de cada VM,
* `docs/screenshots/test-results.json` — resumen detallado (pasos, marcadores,
  estadísticas de cada captura).

Las pruebas de pánico y resolución usan VMs aparte (la excepción de `div0` se
excluye del chequeo global y es esperada); las de resolución generan una ISO
temporal en `/tmp` parcheando la petición de vídeo de la cabecera Multiboot.
Los PPM crudos se conservan solo de las 3 últimas ejecuciones
(`--keep-runs N`), y `make clean` borra `docs/screenshots/raw/`.

### Control manual de QEMU

El módulo `tools/qemu_ctrl.py` también se puede usar como herramienta:

```bash
# arranca, espera el escritorio, envía F2 y captura
python3 tools/qemu_ctrl.py --keys "f2" --shot /tmp/terminal.ppm
# elige la segunda entrada de GRUB y comprueba el modo texto
python3 tools/qemu_ctrl.py --text-mode
# escribir en la terminal abierta y capturar
python3 tools/qemu_ctrl.py --keys "f2" --text "help" --shot /tmp/help.ppm
```

Opciones: `--iso`, `--workdir`, `--kvm auto|on|off`, `--timeout`,
`--marker` (repetible), `--text`, `--shot`.

## Marcadores del log serie

Los marcadores son líneas completas que escribe el kernel por COM1. El arnés
espera a que aparezcan con timeout; se pueden añadir nuevos sin cambiar la
suite.

| Marcador | Significado |
|---|---|
| `SEREOS_BOOT_OK mem=<MiB>` | arranque Multiboot correcto; kernel inicializado |
| `DESKTOP_READY` | `gui_init()` completó los subsistemas del escritorio |
| `SPLASH_DONE` | la pantalla de arranque (splash) terminó |
| `GUI_READY` | el bucle principal del escritorio está a punto de arrancar |
| `APP_OPEN:<id>` | se abrió una ventana de la app `<id>` (`terminal`, `files`, `sysmonitor`, `game`, `about`) |
| `APP_CLOSE:<id>` | se cerró la ventana `<id>` |
| `GAME_MENU` | el juego muestra su menú principal |
| `GAME_START` | comenzó la partida |
| `GAME_PAUSE` | partida pausada |
| `GAME_OVER` / `GAME_WIN` | fin de partida (derrota/victoria) |
| `GAME_EXIT` | el juego volvió al escritorio |
| `SEREOS_TEXT_MODE` | arrancó la consola VGA de respaldo (2ª entrada GRUB) |
| `SEREOS_EXCEPTION <detalle>` | excepción del procesador (no debe aparecer en las pruebas) |
| `SEREOS_PANIC <detalle>` | pánico del kernel (no debe aparecer en las pruebas) |

## Ratón en las pruebas automatizadas

SereOS usa un ratón **PS/2 relativo**. El arnés ofrece `mouse_move_rel`,
`mouse_button` y `mouse_click` vía QMP (`input-send-event`). Los eventos
absolutos de QMP solo funcionan con tabletas USB, por lo que `mouse_move_abs`
es *best-effort* y puede no mover el cursor.

Por eso todas las pruebas de navegación usan **atajos de teclado**. El único
paso que intenta el ratón es el cierre de ventanas (clic en el semáforo rojo);
si el clic no funciona, se informa como fallo real de la prueba, no se oculta.
La posición inicial del cursor es el centro de la pantalla y el arnés lleva su
cuenta para los movimientos relativos.
