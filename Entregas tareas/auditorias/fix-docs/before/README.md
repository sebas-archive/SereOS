# PAC-MAN SereOS + SereOS — Proyecto final de Sistemas Operativos (2026)

**Un proyecto, dos componentes:** el sistema operativo bare-metal **SereOS** y
el videojuego arcade **PAC-MAN SereOS**, que comparte una única lógica entre
SereOS y Linux/SDL2. Esta es la **versión definitiva (v1.8)**, con la auditoría
de Paku-Paku/Res integrada, menús arcade, recursos Res, audio PCM/SB16 y las
**correcciones v3** de audio Game Start, respawn de fantasmas y muerte sin
reinicio del laberinto.

La entrega contiene los dos componentes completos, la ISO arrancable de
SereOS, los binarios finales del juego, este README y la memoria técnica
`SereOS_Proyecto_Final.docx` con capturas reales de ambos entornos.

## Estructura de la entrega

```
SereOS_Proyecto_Final/
├── README.md                         # este documento global
├── SereOS_Proyecto_Final.docx        # memoria técnica (arquitectura, capturas, pruebas)
├── sistema operativo/                # componente 1: SereOS bare-metal
│   ├── boot/ kernel/ drivers/ memory/ process/ filesystem/
│   ├── graphics/ gui/ apps/ audio/ shell/ include/ libc/
│   ├── assets/ tools/ docs/           # docs v1.7 + capturas QA
│   ├── Makefile  grub.cfg  linker.ld
│   ├── sereos.bin  sereos-text.bin  sereos.iso
│   └── (sin apps/game: el juego NO está duplicado en el OS)
└── Pac-man SereOS/                   # componente 2: juego con lógica compartida
    ├── src/core/ src/render/          # lógica + render compartidos
    ├── src/platform/sereos/           # adaptador nativo SereOS (freestanding)
    ├── src/platform/linux/            # backend SDL2
    ├── include/ tests/ tools/ docs/   # incluye AUDIT_PAKUPAKU / AUDIT_RESOURCES
    ├── assets/                        # Res (privados), fuente arcade, fallback propio
    ├── docs/captures/                 # 9 capturas reales del juego
    ├── Makefile  run.sh
    └── build/pacman-sereos  build/sereos/libpacman.a
```

El ZIP **no incluye artefactos intermedios** (objetos `.o`, PPM smoke,
`isodir`, capturas raw, `__pycache__`); sí incluye la ISO de SereOS y los
binarios finales del juego.

## 1. Componente SereOS (sistema operativo)

Sistema operativo propio i686 escrito en C99 y NASM, arranque GRUB 2 /
Multiboot 1, sin Linux ni librerías del anfitrión:

- Kernel monotítico, GDT/IDT propias, paginación PSE de 4 MiB, heap, RAMFS,
  planificador cooperativo, PIT 100 Hz, RTC CMOS, serial COM1, PS/2 teclado y
  ratón y **audio SB16 por DMA** (detección real 0x220–0x280, IRQ 5, DMA 1,
  mixer al máximo y fin de bloque por IRQ) con **fallback al altavoz PC** (PIT
  canal 2) y detección visible en `dmesg`/Acerca de vía `audio_detail()`.
- Motor gráfico nativo con doble búfer, escritorio con wallpaper original,
  ventanas redondeadas con sombra, topbar, dock, menú, pantalla de pánico y
  **navegación adaptativa**: con una ventana maximizada el dock desaparece y
  los 5 accesos pasan a la topbar (app full-height hasta el último píxel).
- Apps nativas: Archivos, Terminal, Monitor, Acerca de y PAC-MAN SereOS.
- **Integración del juego como librería**: el Makefile compila y enlaza
  `../Pac-man SereOS/build/sereos/libpacman.a`, que exporta
  `app_t *app_game(void)`; no existe `apps/game/` en el árbol del OS.
- **v1.8**: integra las correcciones v3 (Game Start sin corte, ciclo de
  fantasmas con respawn y muerte que conserva el laberinto) y mantiene el
  nombre visible exacto **«PAC-MAN SereOS»** en titlebar, topbar, dock, menú y
  Acerca de.

Build y ejecución (CachyOS/Linux host; requiere gcc multilib, nasm,
grub-mkrescue y QEMU):

```sh
cd "sistema operativo"
make clean && make                  # 0 warnings -> sereos.iso + sereos.bin
make run                            # QEMU con ventana
make run-audio                      # QEMU + SB16/PipeWire
python3 tools/run_tests.py          # suite QA en QEMU/KVM
```

### Audio en QEMU: que suene de verdad

`make run` **no** da tarjeta de sonido a la VM: SereOS cae al altavoz PC, que
QEMU no enruta sin `pcspk-audiodev` (y VirtualBox/VMware no reproducen). Para
oír PCM hay que pasar un **SB16** con backend de audio:

```sh
# QEMU moderno: SB16 audible por PipeWire/PulseAudio/ALSA
qemu-system-i386 -m 256M -vga std -cdrom sereos.iso \
  -audiodev pipewire,id=snd0 -device sb16,audiodev=snd0
# o con el Makefile:
make run-audio                      # SB16 + PipeWire (AUDIODEV configurable)
make run-audio-wav                  # headless: captura audio-capture.wav
```

Con la ISO arrancada: **F2** (Terminal) → `audiotest` (tonos 440/660/880/1320
Hz + marcas `AUDIO_TEST:<backend>` / `AUDIO_TEST_DONE` por COM1) o `beep`.
`dmesg` muestra la línea `[OK] Audio: ...` del arranque y `audio` el detalle
real. En **VirtualBox**: Configuración → Audio → *SoundBlaster 16* (AC'97 e
Intel HDA no valen). **VMware no emula SB16**. Comandos exactos, diagnóstico y
evidencia en [`sistema operativo/docs/AUDIO_VM.md`](sistema%20operativo/docs/AUDIO_VM.md);
capturas/WAV/logs en `sistema operativo/docs/evidence/audio/`.

Artefactos finales (se regeneran con `make`; md5 de la build de esta
entrega): `sereos.iso` 36.827.136 B (md5 `16e90cef725696e2b98ea574e8135ac1`),
`sereos.bin` 1.522.000 B (md5 `fe07c51db8c44ec845819f8c2826155b`) y
`sereos-text.bin` 1.522.000 B (md5 `8ab579cb8a24856a48f3a900b5d186a1`).

## 2. Componente PAC-MAN SereOS (videojuego)

Juego arcade con **una sola lógica** (`src/core` + `src/render`) y dos
backends. La interfaz `include/pac_platform.h` independiza el núcleo de SDL y
de las cabeceras del OS; cada backend implementa render, input, tiempo, audio,
persistencia y ciclo de vida.

### Fidelidad auditada a Paku-Paku / Res

- **Un único laberinto real** de 28×31 (240 dots, 4 power pills, túneles con
  wrap, casa de fantasmas); no se inventan layouts.
- **21 configuraciones** de nivel (L1–L21) con velocidades, tiempos de
  frightened, scatter/chase y Cruise Elroy auditados; **L22+ reutiliza la 21**.
- Reglas: salidas del pen por dots/tiempo, 4 fantasmas con IA Blinky/Pinky/
  Inky/Clyde, frightened con velocidad/objetivo pseudoaleatorio, fruta a
  70/170 dots, puntuación clásica, 3 vidas y vida extra.
- **Menús arcade**: attract con CHARACTER/NICKNAME y **PRESS START**, menú
  principal de 6 opciones (incluye Continuar), pausa de 5, game over de 3,
  ajustes (sonido/pantalla completa/controles) y **F11** pantalla completa.
- **Recursos Res** (privados, uso académico): **10 PNG usados** (frutas y
  cuerpos de fantasmas recoloreados), **10 WAV usados** convertidos a PCM u8
  mono 11.025 Hz, y la fuente arcade **Press Start K**. Quedan **5 PNG no
  usados** (retroghost1/2, Clydeeghost, dead, Key-icon), **1 WAV no usado**
  (`intermission.wav`) y **1 TTF no usado** (`atari full.ttf`).
- **Audio**: PCM real en Linux (SDL2) y **SB16 por DMA en SereOS** con cola de
  trozos ≤32 KiB y fallback a la capa sintetizada propia.
- **Nombre visible exacto «PAC-MAN SereOS»** en toda la UI.

### Linux (objetivo por defecto)

```sh
cd "Pac-man SereOS"
make linux          # -> build/pacman-sereos
./run.sh            # comprueba SDL2, compila si falta y ejecuta
./build/pacman-sereos
make test           # 131 checks de core + 7/7 smoke
```

Dependencias: `gcc`, `make`, `pkg-config` y `SDL2` (CachyOS/Arch:
`sudo pacman -S --needed base-devel sdl2`). Ventana 1024×768 con escalado
entero; F11 alterna pantalla completa. Binario final: **769.568 B**
(md5 `42f33373157cf1bf2590215152e05ae3`).

### SereOS (librería nativa freestanding)

```sh
cd "Pac-man SereOS"
make sereos         # -> build/sereos/libpacman.a (app_t *app_game(void))
```
Compila con `-m32 -ffreestanding -fno-pie -mno-sse`, sin SDL ni libc del host;
el backend SereOS usa las APIs nativas del OS. Librería final: **280.906 B**
(md5 `28a84127e0ef206764ce48ef7bfd316d`). La integración la hace el Makefile
del OS (enlaza la librería antes de `-lgcc`).

### Correcciones v3 verificadas (task-38)

| Bug reportado | Corrección real | Evidencia QA |
|---|---|---|
| Game Start distorsionado/cortado | cola PCM chunk a chunk (no `len` total), Start una sola vez, sirena/loops no lo cortan | WAV Linux vs `game start.wav`: **correlación 0.9972**, 0 clipping, energía continua; SB16 OS activo sin clipping ni huecos (hueco máx. 66 ms) |
| Fantasma comido desaparece | snap al centro del tile + BFS de regreso; ciclo **EATEN→RETURNED→REVIVING→LEAVING→NORMAL** y recapturas | 131 tests: **200/400/800/1600**, 4 fantasmas pasan por REVIVING, reaparecen y la segunda power pill vuelve a permitir 200; capturas de ojos/retorno/reaparición |
| Muerte reinicia el laberinto | `pac_start_level` solo al iniciar/nuevo nivel; muerte solo pierde vida y reinicia posiciones | `PAC_STATS` antes/después: dots 240→230, power 4→4, score 0→100, level 1; tras morir dots=230, score=100, lives=2; reset solo al subir nivel |

Capturas reales de esta ronda: `ghost_eyes`, `ghost_return`, `ghost_reappear`,
`death_anim`, `death_after` (Linux) y `os_death_anim`, `os_death_after` (OS).
Envolventes de audio en `audio_waveform.png` y `os_audio_waveform.png`.

### Controles

| Acción | Teclas |
|---|---|
| Mover a Pac-man | Flechas o WASD (Z/X opcionales) |
| Confirmar en menús | Enter / Espacio |
| Pausa / continuar | Esc |
| Reintentar / reiniciar | R |
| Volver al menú (en pausa) | Q |
| Salir en menú/game over | Esc |
| Pantalla completa | F11 |

Récord Linux: `$XDG_DATA_HOME/pacman-sereos/record.txt` (fallback
`~/.local/share/...`); ajustes en el mismo directorio. En SereOS, RAMFS.

## 3. Pruebas y resultados reales

| Comprobación | Resultado |
|---|---|
| Linux `make clean && make linux` | **0 warnings**, binario 753.808 B |
| Linux `make test` | **131/131 checks**, 0 fallos, **7/7 smoke** (attract/menu/settings/play/pause/gameover/victory) |
| Linux independencia OS | `src/core`/`src/render` sin SDL ni headers del OS; build con `OS_DIR` inexistente |
| Récord persistente | `record.txt` = 1500; menú posterior muestra HIGH SCORE 1500 |
| Assets Res | **21 originales** verificados md5 contra `LICENSE_RES.md`; licencias y exclusiones OK |
| Audio Linux | PCM real inicializado con **PipeWire** |
| `make sereos` | 0 warnings; lib 280.906 B, 32-bit, exporta `app_game`, **0 símbolos SDL** |
| OS build | **0 warnings**, 1 `app_game` |
| OS suite QEMU/KVM | **18/18 PASS**, 0 excepciones, 42 capturas reales |
| Integración OS | Abre desde **dock y menú**; attract/PRESS START, menú, Configuración, partida, pausa, salida y escritorio limpio; APP_OPEN/CLOSE ×2, GAME_MENU ×4, GAME_START, GAME_PAUSE, GAME_EXIT ×2 |
| Nombre UI | **«PAC-MAN SereOS»** exacto en titlebar/topbar/dock/menú/Acerca |
| Audio SB16 (QEMU) | Captura activa 17,162 s, peak 29.952 (91,4 % FS), RMS 16.403 (50,1 % FS), 0 recortes, hueco máx. 66 ms |
| Audio VM v1.9 (`audiotest`) | SB16 0x220 IRQ5 DMA1 DSP 4.5, `tones=4 irq=4`, WAV 0,788 s peak -3,0 dBFS y tonos 441,7/658,3/883,3/1316,7 Hz; sin SB16: `solo PC speaker` + PIT 100 Hz; SB16 en 0x240 y con IRQ 7 también correctos |
| Arranque | ISO Multiboot validada y boot real hasta `GUI_READY` |

> Nota de QA: el arnés `game` se recalibró para la paleta de sprites Res
> (familias de color de los 4 fantasmas/frightened) y el nuevo flujo de salida
> desde game over; el resto de la suite no cambió. La integración se validó
> además manualmente y por capturas/pixeles.

Capturas reales: 9 escenas Linux en `Pac-man SereOS/docs/captures/`, capturas
v3 de ojos/retorno/reaparición/muerte en el paquete QA, capturas OS de
integración/muerte en la memoria DOCX y suite OS con 42 PNG en
`sistema operativo/docs/screenshots/`.

## 4. Historial real de versiones de SereOS

| Versión | Hito |
|---|---|
| **1.0** | SereOS Desktop + Pacman SereOS (escritorio, apps, juego) |
| **1.1** | Rediseño visual integral: sistema de diseño, Inter/JetBrains Mono, atlases e iconos |
| **1.2** | Logotipo oficial de SereOS y barra de tareas adaptativa |
| **1.3** | WM: maximización full-bleed, doble clic, minimizar con estado y resize |
| **1.4** | Corrección del artefacto de esquinas/bordes (clipping redondeado) |
| **1.5** | Navegación adaptativa: dock oculto y 5 accesos en la topbar |
| **1.6** | Integración de Pac-man SereOS como componente externo (`libpacman.a`), `apps/game` eliminado |
| **1.7** | **PAC-MAN SereOS definitivo**: M2/M3/M4, auditoría Paku-Paku/Res, 10 PNG/10 WAV, fuente arcade, menús arcade, PCM Linux + SB16, 107 checks/7 smoke, nombre exacto |
| **1.8** | **Integración final v3**: Game Start sin corte, respawn de fantasmas, muerte conserva laberinto/puntuación/nivel; 131 checks/7 smoke |

## 5. Limitaciones honestas

- **Un solo laberinto real** (28×31); las 21 configuraciones cambian
  velocidades/tiempos/IA, no el layout. L22+ = L21.
- **No se implementan**: replay `.pmg`, demo automática de attract, modo
  testing con IA aleatoria, ni selector clásico/moderno. Documentado como
  diferencia respecto a Paku-Paku.
- **Continuar** solo funciona dentro de la misma sesión (no persiste entre
  reinicios).
- Game Start validado con captura WAV/correlación alta en Linux; en SB16
  (QEMU) se validó audio activo, sin clipping ni huecos, con la envolvente del
  start presente (la emulación 8-bit SB16 no permite correlación directa de
  forma de onda como el backend PCM Linux).
- SereOS es i686, monotarea cooperativo, sin red, USB, SMP ni multitarea
  apropiativa; las ventanas maximizadas son full-height fijas.
- **Recursos Res privados**: material arcade/terceros sin licencia de
  redistribución; se usan solo en esta entrega académica con atribución. El
  arte propio queda como fallback. **No se autoriza su redistribución pública.**
- La captura de ventana real en Wayland no está automatizada en este entorno;
  las capturas Linux son render real del binario con SDL dummy + PPM→PNG.

## 6. Licencias y atribuciones

- Código, sistema operativo, arte propio y sprites de fallback: **originales
  del proyecto**.
- Recursos de `assets/res_original/`: suministrados por el usuario desde
  `/home/t1an/Descargas/Res`, origen arcade/terceros (personajes, frutas,
  sonidos reconocibles de Pac-Man/Namco); **sin autoría reclamada y sin
  redistribución pública**. Ver `Pac-man SereOS/assets/LICENSE_RES.md` y
  `docs/AUDIT_RESOURCES.md`.
- Fuente **Press Start K** (© 2001-2002 codeman38), uso privado con
  atribución; sin licencia declarada. Ver `assets/fonts/LICENSE_ARCADE.md`.
- Tipografías Inter y JetBrains Mono: **SIL OFL 1.1**
  (`Pac-man SereOS/assets/fonts/LICENSE.md`).
- Logotipo oficial de SereOS: recurso del proyecto.

## 7. Documentación adicional

- `sistema operativo/README.md`, `docs/DESIGN.md`, `docs/FEATURES.md`,
  `docs/BUILD.md`, `docs/RUN.md`, `docs/LIMITATIONS.md`,
  `docs/PAKMAN_SEREOS.md`, `docs/AUDIO.md`.
- `Pac-man SereOS/README.md`, `docs/ARCHITECTURE.md`,
  `docs/INTEGRATION.md`, `docs/GAME.md`, `docs/AUDIT_PAKUPAKU.md`,
  `docs/AUDIT_RESOURCES.md`.
- `SereOS_Proyecto_Final.docx`: memoria completa con arquitectura, auditorías,
  capturas reales de ambos entornos, resultados de pruebas y limitaciones.
