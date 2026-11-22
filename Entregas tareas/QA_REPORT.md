# QA REPORT v3 — PAC-MAN SereOS v1.8 + SereOS (fixes task-38)

**Fecha:** 2026-11-20 · **Fuente:** `/tmp/sereos_final_snapshot/` (congelado,
sin escrituras en el repo real) · **Salidas:** `/tmp/sereos_final_deliverables/`

## Veredicto

**PASS FINAL v3.** Los 3 bugs reportados están corregidos y verificados con
evidencia real (no simulación): audio Game Start sin corte, ciclo completo de
fantasmas con respawn/recapturas y muerte que conserva laberinto/puntuación/
nivel. Suite OS 18/18 PASS y Linux 131/131 + 7/7.

## 1. Artefactos finales

| Artefacto | Tamaño | md5 |
|---|---|---|
| `sistema operativo/sereos.iso` | 36.282.368 B | `c430ea24528d7b1f21ae47d0d1a86b16` |
| `sistema operativo/sereos.bin` | 1.250.856 B | `dfd3bc7d10f5093ee61f72bdbda58653` |
| `sistema operativo/sereos-text.bin` | 1.250.856 B | `b19338dbcb81e7f76b195fff0153c6a2` |
| `Pac-man SereOS/build/pacman-sereos` | 769.568 B | `42f33373157cf1bf2590215152e05ae3` |
| `Pac-man SereOS/build/sereos/libpacman.a` | 280.906 B | `28a84127e0ef206764ce48ef7bfd316d` |

Estructura: `apps/game` ausente; Makefile del OS enlaza la lib; `app_game()`
único; docs OS v1.8; labels exactos **«PAC-MAN SereOS»** en titlebar/topbar/
dock/menú/Acerca.

## 2. Bug 1 — audio Game Start

- **Linux**: WAV real capturado con PipeWire y comparado contra el clip de
  referencia `game start.wav`:
  - captura **5,803 s**, referencia **4,378 s**, offset **0,184 s**;
  - **correlación 0.9972**, **0 clipping**, energía continua por ventanas
    (RMS 0,12–0,30), sin corte del chunk inicial.
- **OS SB16**: captura QEMU `-audiodev wav` + SB16; audio activo **17,162 s**,
  peak **29.952** (91,4 % FS), RMS **16.403** (50,1 % FS), **0 muestras
  recortadas**, hueco máximo **66 ms**; la envolvente del Game Start está
  presente. Limitación honesta: la emulación SB16 8-bit de QEMU no permite una
  correlación de forma de onda tan directa como el backend PCM Linux; se
  verificó continuidad/energía y ausencia de recortes/huecos.
- Fix de código: cola PCM **chunk a chunk** (no `len` total), Start una sola
  vez, sirena/loops no lo cortan; tests `M3: Game Start usa chunks validos`,
  `chunks suman longitud total`, `no es loop`, `suena exactamente una vez`.
- Evidencias: `screens_v3/audio_game_start.wav`, `audio_metrics.json`,
  `audio_waveform.png`, `os_audio_waveform.png`, `os_v3_audio_metrics.json`.

## 3. Bug 2 — fantasmas capturados

- Tests de core reales: **200 → 400 → 800 → 1600** con cuatro fantasmas; el
  cuarto termina frightened; los cuatro pasan por **REVIVING**, reaparecen y
  vuelven a **NORMAL/LEAVING**; la **segunda power pill** vuelve a permitir
  capturar (200). Marcadores `GHOST_EATEN/RETURNED/REVIVED` presentes.
- Escenas QA reales y capturas: `ghost_eyes` (ojos regresando a casa),
  `ghost_return`, `ghost_reappear` (reaparecido y recapturable).
- Fix: snap al centro del tile + BFS de regreso cuando `dir=NONE` entre tiles.
- Evidencia Linux serial: `GAME_START / GHOST_EATEN 0 / GHOST_RETURNED 0 /
  GHOST_REVIVED 0` + suite 131 checks.
- Nota: el ciclo se verificó en el **binario Linux real** y en el core
  compartido (misma librería que ejecuta SereOS). En la sesión OS automatizada
  no se alcanzó una captura de fantasma (ruta no determinista); la muerte real
  en OS sí se verificó por marcadores.

## 4. Bug 3 — muerte no reinicia el laberinto

- `PAC_STATS` antes/después en OS real (QEMU):
  - `dots=240 power=4 score=0 level=1 lives=3` (inicio)
  - tras jugar/morir: `dots=215 power=3 score=300 level=1 lives=2`
  - **dots/power restantes, score y nivel se conservan**; solo baja la vida y
    se reinician posiciones. Reset de laberinto solo al **completar nivel**
    (test `M3: siguiente nivel si resetea dots/power`).
- Linux serial death scene: `PAC_STATS dots=230 power=4 score=100 level=1
  lives=3 → PAC_DEATH → LIFE_START 2 → PAC_STATS dots=230 power=4 score=100
  level=1 lives=2`.
- Capturas: `death_anim`, `death_after` (Linux), `os_death_anim`,
  `os_death_after` (OS).

## 5. QA Linux v3

| Comprobación | Resultado |
|---|---|
| `make clean && make linux` | **0 warnings**; binario final 769.568 B |
| `make test` | **131/131 checks, 0 fallos; 7/7 smoke** |
| Escenas `gamestart|ghostcapture|death` | rc=0; capturas y seriales reales |
| `make sereos` | 0 warnings; lib 280.906 B, `app_game`, 0 SDL |
| Assets/licencias | 21 originales md5 OK; `LICENSE_RES/ARCADE/LICENSE` presentes |
| Récord | XDG 1500 persistente; menú HIGH SCORE 1500 |
| Audio | PCM real PipeWire; F11 en fuente/ajuste visible |
| Nombre | «PAC-MAN SereOS» exacto; 0 «Pacman SereOS» en strings |
| Fix stride | capturas sin bandas (Configuración/attract/menú) |

## 6. QA OS v3 (ISO nueva, QEMU/KVM)

- Suite completa: **18/18 PASS, 0 FAIL, 0 SKIP, 0 excepciones inesperadas;
  42 capturas** en `screens_v3/os-suite/` + JSON.
- Integración real desde **dock**: attract/PRESS START → menú → partida;
  **muerte real** (`PAC_DEATH`, `LIFE_START 2`, `PAC_STATS` conservados);
  capturas OS `attract`, `menu`, `game_play`, `frightened`, `death_anim`,
  `death_after`, `desktop_after`.
- Identidad exacta «PAC-MAN SereOS»; audio SB16 WAV (ver §2); arranque
  Multiboot/GUI_READY; 0 excepciones.
- Arnés `game` recalibrado en v2 (familias Res/frightened, salida game over,
  flujo audio attract→menú→partida); en v3 el subconjunto boot/game/audio y la
  suite completa pasan. La integración se validó además manualmente y con
  marcadores/píxeles; ningún FAIL de calibración se cuenta como fallo del
  producto.

## 7. Entregables v3

| Fichero | Tamaño | md5 |
|---|---|---|
| `README.md` | 13.590 B | `e0ab9b37fa1f0cae6aff151de9f07cb8` |
| `SereOS_Proyecto_Final.zip` | **20.392.355 B (19,4 MB)** | `7d64d1b6629153eece6da1670848a54e` |
| `SereOS_Proyecto_Final.docx` | 617.339 B | `bdfa95885770c28b86f1eee130274497` |
| `QA_REPORT.md` | este documento | — |

DOCX v3 validado python-docx: portada, TOC, **21 apartados, 7 tablas,
27 imágenes reales** (Linux + OS + audio + ojos/reaparición/muerte), historia
v1.0–v1.8, sección específica de los 3 fixes y limitaciones honestas.

## 8. Verificación del ZIP v3 en limpio (`/tmp/zip_check_v3/`)

- Extracción correcta; estructura exacta `sistema operativo/` +
  `Pac-man SereOS/` + README + DOCX; `apps/game` ausente.
- md5 extraídos = finales (ISO `c430ea24…`, bin `dfd3bc7d…`, text
  `b19338db…`, Linux `42f33373…`, lib `28a84127…`, README `e0ab9b37…`,
  DOCX `bdfa9588…`).
- `grub-file --is-x86-multiboot` OK; **boot real ISO extraída**:
  `SEREOS_BOOT_OK`, `SPLASH_DONE`, `GUI_READY`.
- `make clean && make linux` desde el ZIP → **0 warnings**;
  `make test` → **131/131 + 7/7 smoke**.
- Docs/capturas de suite incluidas: 42 PNG + JSON 18/18.

## 9. Limitaciones honestas

- Un solo laberinto real 28×31; 21 configuraciones (L22+=L21).
- No replay `.pmg`, demo automática, testing ni selector clásico/moderno;
  Continuar solo en la sesión.
- Recursos Res privados/user-supplied de origen arcade, sin redistribución
  pública; uso académico con atribución y fallback propio.
- La correlación de forma de onda del Game Start SB16 no es directamente
  comparable por la emulación 8-bit de QEMU; se verificaron continuidad,
  energía, ausencia de clipping/huecos y presencia de la envolvente.
- En OS automatizado no se alcanzó la captura de un fantasma (no
  determinista); el ciclo se verificó en Linux real y en el core compartido.

## 10. Evidencias

- `screens_v3/os-suite/` (42 capturas + JSON).
- `screens_v3/linux/` (9 escenas oficiales), `screens_v3/ghost_*`,
  `screens_v3/death_*`, `screens_v3/os_*`, `screens_v3/audio_waveform.png`,
  `screens_v3/os_audio_waveform.png`, `screens_v3/audio_game_start.wav`,
  `audio_metrics.json`, `linux_final/linux_qa_v2_metrics.json`.
- Logs: `/tmp/qa_os_v3_suite.log`, `/tmp/qa_os_v3_run.log`,
  `/tmp/v3s_linux_test.log`, `/tmp/zipv3_build.log`, `/tmp/zipv3_test.log`,
  `/tmp/zipv3_boot.log`.
