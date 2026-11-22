# AUDITORÍA A3 — Audio nativo de PAC-MAN SereOS (SereOS kernel + SB16 + app)

Fecha: 2026-11-20 · Auditor: `sereos-audit` (task-3) · Workspace: `/home/t1an/Descargas/sereos02`
Fase: **AUDITORÍA SOLO-LECTURA** (no se editó ninguna fuente). Compilar y ejecutar QEMU sí se usó.
Evidencias: `audit/sereos-audit/` (esta carpeta; el `/tmp` de cada llamada bash es efímero y no persiste).

---

## 0. Resumen ejecutivo

- El juego **sí está integrado** en el SO: `apps/apps.c:18` registra `app_game()` y el símbolo `T app_game` vive en `build/sereos/libpacman.a` (`game_app.c:164`), enlazado en `sereos.bin` (`0x21e8d0`).
- El **SB16 se inicializa y funciona**: en QEMU 11.1.3 + `-device sb16` el runtime reporta `backend=sb16`, DSP `0x0405` (4.5), base `0x220`, `rate=11025`, y el PCM capturado **correlaciona con los WAV de Res** (SIREN_HUNT `corr 100 ms = 0.993`; START chunk0 `0.883`).
- **Defecto crítico confirmado**: `pacasset_pcm_game_start_1` (segundo chunk de START) **cruza el límite de 64 KiB del DMA 8237** (`0xff40 + 13908 > 0x10000`), `sb16.c:134` lo rechaza y START suena **2.97 s de 4.23 s**; después hay **~1.5 s de silencio** antes de la sirena. Evidencia runtime: `g_pcm_chunk=1`, `g_pcm_active=0`, `sb16_total_plays` no incrementa.
- El **fallback al altavoz del PC** funciona (backend `pcspk`, tonos 950/520/390/370/290/180/140 Hz detectados) y el **fallback sintetizado del kernel** también (GAME_OVER: `audio_play_counter` 0→1 y 1.6 s audibles).
- Hay **duplicación de sistema de audio**: el juego trae su propio PCM (`assets/sfx_res.c`, 127 034 B) y el kernel su propio set sintetizado (`audio/sfx_data.c`, 111 133 B). No hay conflicto de símbolos, pero conviven dos máquinas de estado y la del kernel queda casi sin usar.
- Slots **AUSENTES por integración** (no rotos): `MENU` (nunca se llama) y `GHOST_RESPAWN` (asset y flag loop existen, el juego no lo dispara; si se disparara quedaría en loop infinito).

---

## 1. Mapa de integración nativa (archivo → build → runtime → evento → driver)

### 1.1 Build (evidencia de compilación real)

`cd "sistema operativo" && make -j20` → `EXIT=0` (log en `probe-sb16.log`/salida de sesión). Artefactos al día:

| Artefacto | Tamaño | Fecha | Evidencia |
|---|---|---|---|
| `sistema operativo/sereos.bin` | 1 455 648 B | 04:27:27 | `grub-file --is-x86-multiboot` OK |
| `sistema operativo/sereos.iso` | 36 691 968 B | 04:27 | arranca en QEMU |
| `Pac-man SereOS/build/sereos/libpacman.a` | 278 170 B | 04:27:27 | 17 objetos |
| `sistema operativo/build/` | 49 `.o` | — | todos los `.o` son más nuevos que sus fuentes (comprobado) |

Cadena de build:
- `sistema operativo/Makefile:28,35` define `GAME_DIR=../Pac-man SereOS` y `GAME_LIB=$(GAME_DIR)/build/sereos/libpacman.a`; `Makefile:66-67` enlaza `$(OBJS) "$(GAME_LIB)" -lgcc`; `Makefile:73-78` construye la librería con `make -C "$(GAME_DIR)" sereos OS_DIR=...`. `SRCS_C` (`Makefile:49-50`) barre el árbol y excluye `./apps/game/*` (que no existe: el juego sólo entra como librería).
- `Pac-man SereOS/Makefile:46-50`: `SEREOS_SRCS = src/core/*.c src/render/*.c src/platform/sereos/*.c assets/*.c` → `ar rcs build/sereos/libpacman.a`. `assets/*.c` incluye `assets/sfx_res.c` (772 741 B, tablas `pacasset_*`) y los sprites/fuente. La variante Linux (`Makefile:27-29`) además añade `assets/fonts/*.c`; la de SereOS no, pero `font_arcade.c` está en `assets/` raíz.
- **Sin conflicto de símbolos**: `sfx_res.o` exporta `pacasset_*`; `audio/sfx_data.o` exporta `sfx_clips`/`clip_*`; el juego importa `audio_*`/`sb16_*` (nm: `U audio_init`, `U sb16_play`, ...). `nm -n sereos.bin`: `app_game 0x21e8d0`, `sfx_clips 0x22ca00`, `pacasset_sfx_res 0x31c3e0`, `audio_dma 0x360000`.

### 1.2 Runtime: quién inicializa audio

- `kernel/kernel.c:96` `speaker_init()` (deja PIT canal 2 y compuerta conocidos) pero **NO llama `audio_init()`**.
- `audio_init()` se llama desde: `apps/sysmonitor/sysmonitor.c:415`, `apps/about/about.c:307` y **el juego**: `platform_sereos.c:456-460` (`pac_audio_init()` → `audio_init()` + `sb16_init()` redundante pero idempotente).
- `audio_init()` (`audio/audio.c:165-189`) elige backend: `sb16_init()` → `BACKEND_SB16`; si falla → `BACKEND_PCSPK`.
- `sb16_init()` (`drivers/sb16.c:148-187`): sondea `0x220`/`0x240`, reset DSP (0xAA), `0xE1` versión, mixer vol max (0x22/0x04 = 0xFF), speaker off (0xD3), halt DMA (0xD0), enmascara canal 1.

### 1.3 Cadena evento → hardware (ruta del juego)

```
pac_game tick/colisión (src/core/game.c:280-310, 329-342, 385-392)
  └─ pac_sound_play / pac_sound_set_siren (src/core/game_audio.c:38-85)
       └─ pac_audio_play / pac_audio_loop (src/platform/sereos/platform_sereos.c:478-504)
            ├─ SI hay asset Res y SB16 presente: pcm_start() → pcm_play_chunk()
            │    → sb16_play(chunk_ptr, chunk_len, 11025)   [platform_sereos.c:414-446]
            └─ SI NO hay asset Res: os_sfx() → audio_play()/audio_loop() del kernel
                 → audio.c:103-117 sb16_start_clip() (copia a audio_dma 32 KiB alineado 64 KiB)
                 → sb16_play() → DSP 0x14 + DMA 8237 canal 1
                 (o pcspk_oneshot() si no hay SB16)
       └─ cada frame: pac_audio_update() (platform_sereos.c:518-536)
            → audio_update() del kernel y avance de chunks/loops PCM
```

- `sb16_play()` (`drivers/sb16.c:208-248`): valida `<16 MiB` y no cruzar 64 KiB (`dma_program`, :129-146), programa tasa 0x41, speaker 0xD1, comando 0x14 y programa el 8237 (canal 1, single-cycle, modo 0x45).
- No se usa IRQ5: la finalización se detecta por tiempo (`sb16_busy()`, `drivers/sb16.c:250-268`, granularidad del PIT = 10 ms).
- **Tablas de assets Res** (`assets/sfx_res.c:6427-6510`): `pacasset_sfx_res[16]`, `pacasset_sfx_res_chunks[16][2]`, `pacasset_sfx_res_chunk_len`, `pacasset_sfx_res_loop`, `pacasset_sfx_res_rate=11025`. START está partido en 2 chunks (`32768 + 13908`).

---

## 2. Tabla por sonido/slot (estado en SereOS nativo)

Leyenda: **COMPLETO** = ruta + hardware + reproducción demostrada; **PARCIAL** = reproduce pero con defecto/limitación; **AUSENTE** = existe el sonido o el asset pero no se dispara; **ERROR** = ruta rota; **NO VERIFICADO** = código/asset coherentes pero el evento no se pudo provocar en QEMU.

| # | Slot / sonido | Fuente | Ruta nativa | Estado | Evidencia |
|---|---|---|---|---|---|
| 0 | NONE | — | — | — | `sfx_clips[0]` vacío |
| 1 | MENU | synth kernel | `audio_play(AUDIO_MENU)` | **AUSENTE** | No hay ninguna llamada `PAC_SFX_MENU` en `src/` (sólo el enum `pac_platform.h:94`); menú silencioso |
| 2 | START | Res PCM (2 chunks) | PCM → `sb16_play` | **PARCIAL (ERROR DMA)** | chunk0 suena; chunk1 rechazado por límite 64 KiB; `sb16.c:134`; `dma-check.txt`; runtime `memprobe-history.txt` |
| 3 | WAKA1 | Res PCM 932 | PCM | **COMPLETO** | slot=3 visto en runtime; PCM persistido en `scenario-sb16scen.tsv` |
| 4 | WAKA2 | Res PCM 929 | PCM | **COMPLETO** | slot=4 visto en runtime (memprobe/scenario) |
| 5 | POWER | synth kernel (no hay WAV Res) | `audio_play` kernel | **NO VERIFICADO** | ruta existe; no se comió power-pellet en las pruebas; riesgo de cola/starve (D3) |
| 6 | EAT_GHOST | Res PCM 6324 | PCM | **NO VERIFICADO** (PARCIAL) | asset y ruta OK (misma que slots 3/4); no se comió fantasma en las pruebas |
| 7 | EAT_FRUIT | Res PCM 4845 | PCM | **NO VERIFICADO** (PARCIAL) | idem; no apareció fruta en ~40 s |
| 8 | DEATH | Res PCM 16916 | PCM | **COMPLETO** | slot=8 en `memprobe-history.txt` (28 muestras), `PAC_DEATH` ×3 en serial, `sb_plays` avanza |
| 9 | EXTRA_LIFE | Res PCM 20940 | PCM | **NO VERIFICADO** (PARCIAL) | no se alcanzó 1UP; ruta idéntica a slots validados |
| 10 | LEVEL_CLEAR | synth kernel | `audio_play` | **NO VERIFICADO** | no se completó nivel; ruta fallback usada por GAME_OVER sí validada |
| 11 | GAME_OVER | synth kernel | `audio_play` → `audio_dma` | **COMPLETO** | serial `GAME_OVER`; `audio_play_counter` 0→1; captura 1.6 s audibles, clip 1.54 s, corr local 100 ms hasta 0.76 |
| 12 | SIREN_CHASE | Res PCM 1470 (loop) | PCM loop | **NO VERIFICADO** (PARCIAL) | ruta loop validada con slot 13; no se llegó a `dots_left+power<=50` en prueba |
| 13 | SIREN_HUNT | Res PCM 4412 (loop) | PCM loop | **COMPLETO** | runtime slot=13 loop=1; autocorrelación de captura = **0.4001 s = 4412/11025**; corr local 100 ms **0.993** |
| 14 | SIREN_FRIGHT | synth kernel (no hay WAV Res) | `audio_loop` | **NO VERIFICADO + DEFECTO** | no se comió power-pellet; además transición PCM→loop kernel no corta el motor PCM (D2) |
| 15 | GHOST_RESPAWN | Res PCM 2935, `loop=1` | — | **AUSENTE** | `pac_emit_event` (`game.c:280-310`) no tiene caso `PAC_GAME_EVENT_GHOST_RESPAWN`; `game_audio.c` nunca lo reproduce. Si se reprodujera, `loop=1` quedaría infinito |
| — | Intermission | — | — | **AUSENTE (por diseño)** | declarado explícitamente fuera en `assets/sfx_res.h:1-30`; no hay WAV ni clip sintetizado |

Resumen: 5 COMPLETO/PARCIAL-funcional con PCM real, 1 PARCIAL por DMA, 2 AUSENTE por integración, 6 NO VERIFICADO con ruta/asset coherentes (no se alcanzó el evento), 1 AUSENTE por diseño.

---

## 3. Pruebas reales en QEMU (comandos exactos y resultados)

Entorno: QEMU 11.1.3, TCG (no hay `/dev/kvm` en esta máquina), `-m 256M`, `-vga std`, ISO `sereos.iso`.

### 3.1 Arranque + app + captura de audio

```bash
# 1) sink nulo de PulseAudio para capturar sin altavoz físico
pactl load-module module-null-sink sink_name=sereos_audit
parec -d sereos_audit.monitor --raw --rate=44100 --channels=2 --format=s16le > capture.raw &

# 2) QEMU con SB16 emulado y ratón/teclado por QMP (sendkey)
PULSE_SINK=sereos_audit qemu-system-i386 -m 256M -vga std -display none -boot d \
  -cdrom "sistema operativo/sereos.iso" -serial file:serial.log \
  -audiodev pa,id=snd -device sb16,audiodev=snd -machine pcspk-audiodev=snd \
  -qmp unix:qmp.sock,server=on,wait=off -no-reboot

# 3) automatización (QMP human-monitor-command): f4 → ret → ret → flechas
```

Scripts: `qemu_probe.py` (captura + screenshots), `mem_probe.py` (lectura de globals del kernel por QMP `xp`, solo lectura), `scenario_probe.py` (partida hasta GAME_OVER), `final_analysis.py`, `check_dma.py`.
Captura alternativa usada también: `-audiodev wav,id=snd,path=capture.wav -device sb16,audiodev=snd` (`capture.wav`, `capture-sb16only.wav`, `capture-pcspk.wav`).

### 3.2 Log serial (extracto, `serial-sb16scen.log`)

```
GUI_READY / GUI_LOOP
APP_OPEN:game        ← F4 abre la app registrada por apps/apps.c:18
GAME_MENU
LEVEL_START 1
PAC_STATS dots=240 power=4 score=0 level=1 lives=3
GAME_START           ← segundo Enter arranca partida
PAC_DEATH / LIFE_START 2
PAC_STATS dots=211 ... score=290 lives=2
PAC_DEATH / LIFE_START 1
PAC_STATS dots=208 ... lives=1
PAC_DEATH
GAME_OVER
```

### 3.3 Estado del driver leído en memoria del kernel (QMP `xp`, `memprobe.log`/`memprobe-history.txt`)

```
game-open     backend=1(sb16) ready=1 dsp=0x0405 base=0x220 last_rate=0 plays=0
start+0.15s   sb16_playing=1 sb_plays=1 rate=11025 pcm(slot=2 active=1 loop=0 chunk=0)
start+2.85s   sb16_playing=1 sb_plays=1 pcm(slot=2 active=1 chunk=0)
start+3.00s   sb16_playing=0 sb_plays=1 pcm(slot=2 active=0 chunk=1)   ← chunk1 NO se reproduce
start+4.50s   sb_plays=2 pcm(slot=13 active=1 loop=1 chunk=0)           ← sirena HUNT
move+...      slots 3/4 (waka) intercalados
(final)       slot=8 (death); fallback GAME_OVER → audio_play_counter 0→1
```
Esto demuestra: inicialización real del SB16, tasa 11025 aplicada, límite de bloque, y que la app usa la ruta PCM del juego (el `play_counter` del kernel sólo avanza en los fallbacks sintetizados).

### 3.4 ¿El PCM capturado corresponde a los WAV? (análisis de señal)

No es ruido: hay correlación y periodicidad verificables.

| Clip | Medida | Resultado |
|---|---|---|
| START chunk0 | corr local 100 ms al inicio (`t=8.02 s` de captura) | **+0.883** (MATCH) |
| START chunk1 | corr en 11.0–12.4 s | **+0.12** (no aparece) |
| Duración audible de START | run audible 8.00–11.00 s | **3.00 s** (asset completo 4.23 s; chunk0=2.97 s) |
| Silencio donde iría chunk1 | 11.0–12.5 s | ~1.5 s sin señal (no hay audio) |
| SIREN_HUNT (loop) | corr local 100 ms | **+0.993** (MATCH) |
| SIREN_HUNT (loop) | autocorrelación de la captura | **0.4001 s** = 4412 muestras / 11025 Hz = 0.4002 s |
| GAME_OVER (fallback sintetizado) | run audible 37.4–39.0 s = 1.6 s (clip 1.54 s); corr local | hasta **0.76**; `audio_play_counter` 0→1 |
| PC speaker fallback (sin `-device sb16`, `scenario-pcspkscen.tsv`) | backend=2, tonos dominantes detectados | 950 (START), 520/390 (WAKA1/2), 370/290 (siren hunt), 180 (DEATH), 140 (GAME_OVER) Hz → coinciden con `pcspk_map`/`pcspk_siren` |

Nota metodológica (limitación de QEMU, no del driver): con `-audiodev wav` de QEMU 11.1.3 las capturas salieron con RIFF/data size = 0 y, al compartir el mismo `audiodev` dos voces (SB16 + pcspk), con contenido inconsistente/no interpretable; un arranque sin reproducir audio deja el WAV en 44 B (silencio). Por eso la prueba concluyente se hizo con **PulseAudio null-sink + `parec` (raw 44100 s16le)**, cuyos ficheros crudos están en esta carpeta.

Screenshots de la app real: `shot-pa-05-playing-start.png`, `shot-sb16-05-playing-start.png`, `shot-sb16-02-monitor.png` (escritorio SereOS con el juego y el monitor). Las capturas `.ppm` son las originales de QEMU; los `.png` son la conversión.

---

## 4. Limitaciones reales del audio del kernel

1. **Sólo PCM 8 bits sin signo, mono, 11025 Hz** en la práctica: todos los assets son u8 mono 11025 (`sfx_data.h:4-32`, `sfx_res.h`); `set_sample_rate()` acepta 5000–45000 Hz pero no hay conversión de formato/estéreo (el DMA 8-bit es mono).
2. **Un solo canal/reproducción**: no hay mezclador en la API (`audio.h`); el mixer sólo se usa al inicializar volumen maestro/voz al máximo (`sb16.c:173-175`). No se pueden solapar sonidos; como mucho, cola de 4 one-shots en `audio.c:30,86-100`, y **si la cola se llena se descarta** (`audio_underruns`).
3. **Sin IRQ5 ni detección de terminal count**: la finalización es por tiempo con PIT a 100 Hz (`sb16.c:14-16,236-268`) → resolución 10 ms y deriva; no hay doble buffer ni streaming continuo: el "loop" lo rearma la CPU (`platform_sereos.c:518-536`), con huecos de ~1 frame (~33 ms a 30 fps).
4. **DMA 8237 8 bits canal 1**: buffer físico < 16 MiB y **sin cruzar 64 KiB** (`sb16.c:133-134`). `audio.c` usa una bounce buffer estática de 32 KiB alineada a 64 KiB (`audio.c:40`, `nm`→`audio_dma 0x360000`, OK), pero **la ruta del juego NO usa esa bounce buffer**: pasa punteros a `.rodata` del asset directamente (`platform_sereos.c:414-425`), de ahí el fallo de chunk1.
5. **Altavoz del PC (PIT canal 2)**: sólo tonos (sin PCM), un tono a la vez, sin mezcla; sirenas por retuning alterno (`audio.c:122-160,296-318`). Es el fallback si no hay SB16.
6. **QEMU**: el SB16 **no existe por defecto** en la máquina `pc`; hay que añadir `-device sb16,audiodev=...` (los targets `run-audio*` del Makefile lo hacen). IRQ/DMA del modelo QEMU (IRQ5/DMA1) no los usa el driver. Sin `/dev/kvm` la emulación va más lenta, pero el tiempo del guest fue ≈ tiempo real en las pruebas.
7. **Inicialización perezosa**: no hay `audio_init()` en `kernel_main`; hasta abrir Monitor/Acerca de/juego el backend es "ninguno".
8. **Dos sistemas de audio en el mismo kernel** (`audio/sfx_data.c` 724 489 B + `assets/sfx_res.c` 772 741 B; 238 KB de PCM total en el binario de 1.45 MB): el del kernel queda casi sin usar por el juego (sólo fallbacks).

---

## 5. Defectos concretos (archivo:línea)

| ID | Sev. | Archivo:línea | Defecto y efecto |
|---|---|---|---|
| D1 | **CRÍTICO** | `Pac-man SereOS/src/platform/sereos/platform_sereos.c:414-425` + `sistema operativo/drivers/sb16.c:129-146` (línea 134) | `pcm_play_chunk()` entrega el puntero del asset directamente al DMA. `pacasset_pcm_game_start_1` está en `0x32ff40` (len 13 908): `0xff40 + 13908 = 0x13594 > 0x10000` ⇒ `dma_program()` devuelve 0 ⇒ START se corta a 2.972 s (de 4.233 s) y hay ~1.5 s de silencio (`sb16_plays` no sube, `g_pcm_chunk=1`, `active=0`). Ver `dma-check.txt`. **Arreglo**: usar la bounce buffer alineada (como `audio.c`) también en la ruta del juego, o trocear de forma que ningún chunk cruce 64 KiB. |
| D2 | **ALTO** | `platform_sereos.c:492-504` vs `:518-536` | `pac_audio_loop()` no detiene el motor PCM del juego (`g_pcm_active/g_pcm_slot`) cuando cae al fallback del kernel (caso slot 14 SIREN_FRIGHT, sin WAV Res): `pac_audio_update()` sigue rearmando el loop PCM anterior (slot 13) mientras `audio_loop()` del kernel intenta arrancar el loop sintetizado ⇒ conflicto/solape; SIREN_FRIGHT no suena de forma fiable. **Arreglo**: en el fallback llamar `pcm_stop()` antes de `audio_loop()`. |
| D3 | **ALTO** | `platform_sereos.c:478-490` + `sistema operativo/audio/audio.c:207-224` | Los slots sin WAV Res (1 MENU, 5 POWER, 10 LEVEL_CLEAR, 14 FRIGHT) y los one-shots van a `audio_play()` del kernel **sin parar el loop PCM**: si hay PCM sonando, el kernel encola (máx. 4; se descarta al llenarse) y el sonido puede retrasarse o perderse. |
| D4 | MEDIO | `sistema operativo/audio/audio.c:220` vs `:275-294` | En backend SB16, si `sb16_start_clip()` falla se llama `pcspk_oneshot()`, pero el apagado de ese tono sólo está en la rama `BACKEND_PCSPK` de `audio_update()` ⇒ el altavoz del PC puede quedar encendido hasta `audio_stop()`. |
| D5 | MEDIO | `sistema operativo/drivers/sb16.c:14-16,236-248,250-268`; `audio/audio.c:40` | Sin IRQ5/terminal count: duración por PIT 100 Hz (10 ms de resolución; p. ej. WAKA 84.5 ms se contabiliza como 90 ms) y sin doble buffer ⇒ deriva, cortes y huecos entre loops. |
| D6 | MEDIO | `Pac-man SereOS/src/core/game.c:280-310`; `game_audio.c:21-36` | `PAC_GAME_EVENT_GHOST_RESPAWN` existe (`pac_game.h:158`) y hay asset PCM con `loop=1` (`sfx_res.c`), pero **no hay caso en `pac_emit_event`** ni llamada en `game_audio.c` ⇒ slot 15 AUSENTE. Además `platform_sereos.c:482-484` honra el flag loop y nunca se pararía. |
| D7 | MEDIO | `Pac-man SereOS/src/core/game.c` (todo el archivo) | `PAC_SFX_MENU` no se reproduce nunca (sólo aparece en el enum `pac_platform.h:94`) ⇒ slot 1 AUSENTE, menú y navegación silenciosos. |
| D8 | BAJO | `sistema operativo/audio/sfx_data.c` + `Pac-man SereOS/assets/sfx_res.c` | Duplicación de sets de sonido (dos fuentes de verdad y dos máquinas de estado). No hay desincronización de tablas detectada: `sfx_data.h:9-25` y sus 14 arrays coinciden en longitudes; las tablas `sfx_clips` y `pacasset_sfx_res` están completas. |
| D9 | BAJO | `sistema operativo/audio/audio.c:165-189`; `platform_sereos.c:456-460` | `audio_init()` redundante en `pac_audio_init()` (llama también `sb16_init()`); es idempotente (`sb16.c:152`) pero no hace falta. |
| D10 | BAJO | `sistema operativo/Makefile:99-121` | `run-audio-wav` no enruta el altavoz del PC (`-machine pcspk-audiodev=`) ⇒ el fallback no se captura; `run-audio` usa `pipewire` (puede fallar sin sesión); `QFLAGS` siempre escribe `serial.log` ⇒ colisión en ejecuciones paralelas. |
| D11 | BAJO | `Pac-man SereOS/src/core/game_audio.c:24` | `PAC_SFX_START` fija `effect_hold_ms=4500`, pero el audio real dura 2.97 s (4.23 s si se arregla D1): deja silencio de ~1.5 s antes de la sirena. |
| D12 | INFO | `sistema operativo/audio/sfx_data.c` (`clip_*`) | El set sintetizado del kernel cubre los 14 slots, pero el juego lo usa sólo para 1/5/10/11/14; sin WAV de Res para POWER/MENU/LEVEL_CLEAR/GAME_OVER/FRIGHT (por diseño, `sfx_res.h:1-30`), ese fallback es el comportamiento esperado. |

---

## 6. Lo que NO se pudo verificar (y por qué)

1. **POWER (5), SIREN_FRIGHT (14), EAT_GHOST (6), EAT_FRUIT (7), EXTRA_LIFE (9), LEVEL_CLEAR (10), SIREN_CHASE (12)**: código y assets coherentes, pero en las ~40–70 s de partida automatizada a ciegas (QMP `sendkey`) no se llegó a comer power-pellet, fruta, fantasma asustado ni completar nivel. Reproducción **NO VERIFICADA** (no "rota").
2. **Hardware real**: todo se probó en QEMU (TCG, sin KVM); no hay SB16/ISA-DMA físico en esta máquina. El comportamiento de temporización/IRQ en hierro real queda sin verificar.
3. **Timbre/volumen del PC speaker**: sólo se verificaron frecuencias dominantes (la tabla de `pcspk_map`/`pcspk_siren` coincide).
4. **Sesiones largas / fugas**: no se probó >70 s de partida ni reaperturas repetidas de la app.
5. Bugs de calidad de sonido (clicks, fase de loops) no evaluados formalmente: se documenta el hueco entre loops, no una medida psicoacústica.

---

## 7. Inventario de evidencias (`audit/sereos-audit/`)

| Fichero | Contenido |
|---|---|
| `REPORT.md` | este informe |
| `dma-check.txt` + `check_dma.py` | comprobación de límites DMA de todos los chunks contra símbolos de `sereos.bin` (1 FAIL: chunk1 START) |
| `serial.log`, `serial-sb16only.log`, `serial-memprobe.log`, `serial-sb16scen.log`, `serial-pcspkscen.log`, `serial-pa.log` | logs seriales de arranque + eventos `GAME_MENU/LEVEL_START/GAME_START/PAC_DEATH/GAME_OVER/APP_OPEN:game` |
| `memprobe.log`, `memprobe-history.txt` | estado del driver leído por QMP `xp` durante START/sirena/waka/death/GAME_OVER |
| `scenario-sb16scen.tsv`, `scenario-pcspkscen.tsv`, `scen-*.log` | muestreo de globals de audio en la partida completa, con y sin SB16 |
| `capture-sb16scen.raw`, `capture-pcspkscen.raw`, `capture-pa.raw` | capturas fiables (PulseAudio null-sink, 44100 Hz s16le estéreo) — SB16 y fallback PC speaker |
| `capture.wav`, `capture-sb16only.wav`, `capture-pcspk.wav`, `capture-bootsb16.wav`, `capture-inittest.wav` | capturas con `-audiodev wav` de QEMU; documentadas como poco fiables (ver §3.4) |
| `analysis-final.txt`, `wav-analysis.txt`, `analyze_audio.py`, `final_analysis.py` | correlación contra los PCM de `sfx_res.c`/`sfx_data.c`, periodicidad de loops, tonos del PC speaker |
| `shot-*.ppm` / `shot-*.png` | screenshots reales del escritorio SereOS y del juego (START/READY, monitor, partida) |
| `qemu_probe.py`, `mem_probe.py`, `scenario_probe.py` | automatización QEMU+QMP usada (reproducible) |
| `probe-sb16.log`, `qemu*.log` | trazas de arranque de QEMU |

Reproducción mínima: `cd "sistema operativo" && make -j20` y luego `python3 ../audit/sereos-audit/qemu_probe.py` (requiere `pactl load-module module-null-sink sink_name=sereos_audit` y `parec`).
