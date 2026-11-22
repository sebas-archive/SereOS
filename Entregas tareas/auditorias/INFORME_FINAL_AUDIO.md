# AUDITORÍA INTEGRAL DE AUDIO — PAC-MAN SereOS (informe final)

- **Fecha:** 2026-11-20 · **Workspace:** `/home/t1an/Descargas/sereos02`
- **Fuente original de sonidos:** `/home/t1an/Descargas/Res/` (intacta; hashes MD5/SHA-256 verificados antes y después).
- **Ámbito:** videojuego `Pac-man SereOS/` (CachyOS/Linux-SDL2) y SO nativo `sistema operativo/` (SereOS, driver SB16 del kernel).
- **Método:** auditoría solo-lectura (4 informes en `audit/`) → corrección por ámbitos disjuntos → verificación independiente con builds limpios y capturas reales de audio.
- **Evidencias:** `audit/wav-integrity/`, `audit/linux-audit/`, `audit/sereos-audit/`, `audit/events-audit/`, `audit/fix-assets/`, `audit/fix-core/`, `audit/fix-linux/`, `audit/fix-sereos/`, `audit/verify/`.

---

## 0. Veredicto

Los **11 WAV de `Res` existen y son técnicamente válidos**; tras la corrección, los **11 están integrados** en el pipeline PCM del juego (antes 10). Los eventos del enunciado tienen sonido en CachyOS y la ruta nativa SereOS reproduce PCM real por SB16 (START corregido de 2,97 s truncados a **4,23 s completos**). Quedan limitaciones de hardware/kernel (mono 8 bits, sin mezclador en el SO) y eventos que no se pudieron provocar en la partida automatizada de QEMU, marcados **NO VERIFICADO** con motivo. Detalle por sonido en §2 y §7.

**Verificación independiente (task-9 + re-verificación B5/B6, `audit/verify/REPORT.md`): PASS** en build limpio (0 warnings), **209 checks** + 7 smokes, assets 11/11 intactos y deterministas, Linux/CachyOS (arnés lógico 30/30 + capturas reales de todos los clips), SereOS nativo (START completo con chunk1 firmado **+0,9958**, sirena 0,4002 s). Solo aparecieron 2 defectos **BAJOS**, corregidos después (pausa no silenciaba one-shots → B5; docs obsoletas → B6). No se encontró ningún fallo grave de audio.

*Configuración del árbol:* el workspace es compartido con otra sesión concurrente ajena a esta auditoría (UI, `kernel/shutdown`, docs del SO). Los hashes del estado verificado están en §9; los cambios de audio de este trabajo no se revirtieron.

---

## 1. Inventario completo de WAV encontrados

**`Res/` contiene exactamente 11 WAV, sin subdirectorios ni WAV extra** (`find Res -iname '*.wav'` → 11/11; `ffmpeg` decodifica 11/11 sin error; MD5 registrados en `audit/wav-integrity/REPORT.md`).

| # | Archivo | Bytes | Formato origen | Rate/ch/bits | Duración | MD5 | Copia en res_original |
|---:|---|---:|---|---|---:|---|---|
| 1 | `game start.wav` | 420.408 | PCM u8, estéreo dual-mono | 48000 / 2 / 8 | 4,378 s | `07914ee70de9f5f1166ed3e9b35fc9db` | Sí |
| 2 | `waka1.wav` | 16.320 | PCM s16, estéreo dual-mono | 48000 / 2 / 16 | 0,0846 s | `9e3c8eb9b4d7af04971b12c9af3e5bb4` | Sí |
| 3 | `waka2.wav` | 16.256 | PCM s16, estéreo dual-mono | 48000 / 2 / 16 | 0,0842 s | `0452cd64893e3fbd3503190e9ff318c7` | Sí |
| 4 | `eat ghost.wav` | 6.408 | PCM u8, mono | 11025 / 1 / 8 | 0,5736 s | `61d4ded9e6249e64b735982f6ced3ec5` | Sí |
| 5 | `eat fruit.wav` | 5.120 | PCM u8, mono | 11025 / 1 / 8 | 0,4395 s | `514eeeeb192e8ca45ca92aa308f61f63` | Sí |
| 6 | `extra life.wav` | 21.248 | PCM u8, mono | 11025 / 1 / 8 | 1,8993 s | `27991f5575aec8695f0f9a68925b9df8` | Sí |
| 7 | `ghost respawn.wav` | 52.390 | PCM u8, estéreo dual-mono | 48000 / 2 / 8 | 0,5449 s (loop 0,266 s) | `43fae1a4447f5026f8f23a9d9dd02b95` | Sí |
| 8 | `hunted siren.wav` | 113.494 | PCM u8, estéreo dual-mono | 48000 / 2 / 8 | 1,1814 s (loop 0,400 s) | `8d5759b619045b5f6879ec83175d67a9` | Sí |
| 9 | `hunter siren.wav` | 230.902 | PCM u8, estéreo dual-mono | 48000 / 2 / 8 | 2,4044 s (loop 0,133 s) | `d35ceeea5823f2ea9c1a3d2107826b92` | Sí |
| 10 | `pacman death.wav` | 17.008 | PCM u8, mono | 11025 / 1 / 8 | 1,5343 s | `b5cacf9a37e6a4fd396f6fd914168780` | Sí |
| 11 | `intermission.wav` | 57.600 | PCM u8, mono | 11025 / 1 / 8 | 5,2043 s | `566c0f2299b8a7ebef6372010fa6866e` | **Sí (añadido en la corrección)** |

- **Ningún archivo tiene clipping** ni distorsión por saturación; `game start` termina con fade-out correcto (últimas 20 muestras a 0, sin click); los 48 kHz son dual-mono exactos.
- `game start.wav` mide 420.408 B porque es **48 kHz estéreo u8** de origen: el PCM útil para el juego (mono 11.025 Hz) son 46.676 muestras = 4,2337 s (el original es 9,0× más grande, no está corrupto).
- `res_original/` tiene ahora **11/11 archivos byte-idénticos** a `Res` (MD5+SHA-256); los originales de `Res` **no se han convertido ni reemplazado**.

---

## 2. Tabla de integración (estado anterior → estado final)

Leyenda: **COMPLETO** = archivo integrado y reproducción verificada; **PARCIAL** = presente con integración/calidad incompleta; **AUSENTE** = no integrado; **ERROR** = fallo; **NO VERIFICADO** = no se pudo comprobar la reproducción (se indica motivo).

| Sonido (slot) | WAV en Res | Copia al proyecto | Ubicación / build | Evento asociado | ANTES (auditoría) | ESTADO FINAL Linux/CachyOS | ESTADO FINAL SereOS nativo |
|---|---|---|---|---|---|---|---|
| Game Start (2) | Sí | Sí | `assets/sfx_res.c` slot 2 → `libpacman.a`/binario | inicio de partida | PARCIAL (START terminaba, pero nativo se truncaba) | **COMPLETO** (4,229 s, 1 sola vez) | **COMPLETO** (4,17-4,30 s audibles de un clip de 4,23 s; bug DMA corregido) |
| Waka 1/2 (3,4) | Sí | Sí | idem slots 3/4 | consumo de puntos (alternado) | PARCIAL (14,5 ms cortados) | **COMPLETO** (84 ms, alterna) | **COMPLETO** (slots 3/4 vistos en runtime) |
| Power (5) | **No existe** | — | fallback sintetizado | superpunto (no hay clip en Res) | PARCIAL (16 ms, tapado) | **COMPLETO como síntesis** (1200 Hz, hold 320 ms) | NO VERIFICADO (evento no provocado; ruta synth validada) |
| Eat Ghost (6) | Sí | Sí | slot 6 | captura de fantasma | PARCIAL (se cortaba a 300 ms; otro SFX lo borraba) | **COMPLETO** (573,6 ms, mezclado) | NO VERIFICADO (evento no provocado; ruta PCM idéntica a slots validados) |
| Eat Fruit (7) | Sí | Sí | slot 7 | consumo de fruta | PARCIAL (cortado a 250 ms) | **COMPLETO** (439,5 ms) | NO VERIFICADO (evento no provocado) |
| Extra Life (9) | Sí | Sí | slot 9 | vida adicional | ERROR (inaudible: la pisaba el waka) | **COMPLETO** (1899 ms, prioridad) | NO VERIFICADO (no se alcanzó 1UP) |
| Death (8) | Sí | Sí | slot 8 | muerte de Pac-Man | COMPLETO | **COMPLETO** (1534 ms) | **COMPLETO** (slot 8, `PAC_DEATH`×3) |
| Sirena persecución (13) | Sí (`hunted siren`) | Sí | slot 13 loop | ambiente normal | PARCIAL (semántica invertida) | **COMPLETO** (loop; solo una sirena) | **COMPLETO** (loop 0,4001 s, corr 0,997) |
| Sirena frightened (12) | Sí (`hunter siren`) | Sí | slot 12 loop | power pill | ERROR (usaba slot vacío y se solapaba) | **COMPLETO** (hunter, sin solape) | NO VERIFICADO (evento no provocado; ruta loop validada) |
| Ghost Respawn (15) | Sí | Sí | slot 15 loop | regreso de fantasmas (ojos) | AUSENTE (evento sin `case`) | **COMPLETO** (loop mientras hay ojos) | NO VERIFICADO (evento no provocado; one-shot/loop corregido) |
| Level Clear / Intermission (10) | **Sí** (`intermission.wav`) | **No → Sí** | **slot 10 (nuevo)** | transición de nivel | AUSENTE (síntesis 0,49 s) | **COMPLETO** (5,200 s PCM) | NO VERIFICADO (no se completó nivel; ruta PCM automática) |
| Game Over (11) | **No existe** | — | fallback sintetizado | fin de partida | PARCIAL (55 Hz subsónico) | **COMPLETO como síntesis** (166 Hz) | **COMPLETO** (synth 1,6 s audible) |
| Menu (1) | **No existe** | — | fallback sintetizado | menú/attract/navegación | AUSENTE (0 llamadas) | **COMPLETO como síntesis** (659 Hz) | NO VERIFICADO (cableado en core; ruta synth validada) |

**Nota:** MENÚ, POWER y GAME OVER **no existen como clip en `Res`** (no se inventaron): se mantienen con el fallback sintetizado de cada backend, ahora con pitch/volumen correctos y declarado en `docs/GAME.md` y `assets/sfx_res.h`.

---

## 3. Eventos sin sonido detectados (y estado final)

| Evento | Antes | Ahora |
|---|---|---|
| Inicio de partida | Sonaba (WAV), nativo truncado a 2,97 s | Suena 1 sola vez y completo (4,23 s) |
| Consumo de puntos | Sonaba, 14,5 ms cortado, reiniciaba sirena cada punto | Completo (84 ms) + gracia de 300 ms anti-stutter |
| Superpunto | Sonaba 16 ms y lo tapaba la sirena frightened | Sintetizado 320 ms con prioridad |
| Captura de fantasma | Cortado a 300 ms / borrado por otro SFX | Completo 574 ms con mezcla |
| **Regreso de fantasmas** | **Mudo** (evento sin `case`) | Loop de respawn mientras hay ojos; vuelve a la sirena normal |
| Consumo de fruta | Cortado 250 ms; al aparecer la fruta sonaba POWER (evento erróneo) | Completo 440 ms; POWER espurio eliminado |
| **Vida adicional** | **Inaudible** (waka la pisaba) | 1.899 ms con prioridad sobre waka |
| Muerte de Pac-Man | Correcto | Completo 1,53 s |
| Sirena persecución | Sonaba, pero usaba el clip de frightened | `hunted siren` (slot 13) correcto |
| **Sirena frightened** | **Slot vacío**, se solapaba con la sirena WAV | `hunter siren` (slot 12) correcto, una sola sirena |
| **Transición de nivel** | Muda de facto (síntesis 0,49 s; 1400 ms de estado) | `intermission.wav` 5,204 s, estado 5400 ms |
| Menú / attract | Silencio total | Blip de menú en attract/menú/navegación/pausa |
| Game Over | Sonaba, 55 Hz (subsónico) | 166 Hz audible |
| Pausa / pérdida de foco / OFF→ON | Sirena se quedaba muda o seguía | Para y rearma correctamente |

---

## 4. Errores detectados (antes de corregir)

**Críticos (P0):**
1. `GHOST_RESPAWN` tenía WAV pero `pac_emit_event()` no tenía `case` → el regreso de fantasmas nunca sonaba (`game.c:275-313`).
2. `EXTRA_LIFE` inaudible: `pac_add_score()` la pedía y el WAKA/EAT_GHOST del mismo tick la sustituía y pisaba su hold (`game.c:101-124`, `game_audio.c:38-53`).
3. Sirenas invertidas: el juego usaba `hunter siren` como ambiente normal y un slot vacío para frightened (`game.c:427-440`, `sfx_res.h`).
4. Linux: al pasar a frightened quedaban sonando **dos sirenas** (loop PCM + synth) porque la rama sintetizada no paraba el loop PCM (`platform_linux.c:390-404`).
5. Nivel completado sin `intermission.wav` y estado de 1400 ms (clip real 5204 ms) (`pac_game.h:49`).
6. `PAC_SFX_MENU` nunca se invocaba.
7. SereOS nativo: **bug DMA crítico** — el segundo chunk de `game start` (`0x32ff40 + 13908`) cruzaba el límite de 64 KiB del 8237 y `sb16.c:134` lo rechazaba → START 2,97 s + 1,5 s de silencio.

**Altos (P1):** holds menores que el clip (waka 70/84,5; ghost 300/574; fruit 250/440; extra life 900/1899); sirena reiniciada en cada punto; loop que no se paraba al perder foco; OFF→ON dejaba la sirena muda; `pac_start_level` asignaba `g->siren` directo; `restore_continue` restauraba estado de audio obsoleto; `pac_audio_play` de SereOS honraba el flag loop del recurso; síntesis Linux a ÷2,97 de frecuencia y −20 dB de volumen; game over a 55 Hz.

**Medios (P2):** variantes de pitch de sirena (0/10/20/30 %) generadas y sin cablear (requieren ABI nueva; aplazado y documentado); DC offset de clips normalizados; seam de bucle de sirenas (24/12 LSB); cola única PCM de Linux (resuelta con mezclador); `audio_init()` perezoso en el SO.

---

## 5. Archivos modificados

**Recursos / pipeline:**
- `Pac-man SereOS/assets/sfx_res.c`, `sfx_res.h` (regenerados; 11 slots con PCM, 184.411 B)
- `Pac-man SereOS/assets/res_original/intermission.wav` (**nuevo**, byte-idéntico a Res)
- `Pac-man SereOS/assets/LICENSE_RES.md`, `assets/res_original/LICENSE_RES.md`
- `Pac-man SereOS/tools/gen_pacman_res_assets.py` (intermission → slot 10; `loop[15]=0`; cabeceras 11 WAV)
- `Pac-man SereOS/docs/GAME.md` (sección de audio: 11 WAV, LEVEL_CLEAR=intermission, síntesis declarada)

**Núcleo compartido:**
- `Pac-man SereOS/src/core/game_audio.c` (holds reales, prioridad de one-shots, validación, reset)
- `Pac-man SereOS/src/core/game.c` (sirenas, respawn, menú, nivel, foco, toggle, pausa, gracia)
- `Pac-man SereOS/src/core/pac_game.h` (`PAC_LEVEL_CLEAR_MS=5400`, `audio_oneshot`, `siren_grace_ms`)
- `Pac-man SereOS/src/core/game_entities.c` (eliminadas emisiones muertas de respawn)
- `Pac-man SereOS/tests/mock_platform.c/.h`, `tests/core_tests.c` (log de secuencia + 24 checks nuevos)

**Plataforma Linux/CachyOS:**
- `Pac-man SereOS/src/platform/linux/platform_linux.c` (mezclador PCM sin ABI nueva, síntesis corregida, loop/stop/cierre robustos, audio opcional)

**Plataforma y kernel SereOS:**
- `Pac-man SereOS/src/platform/sereos/platform_sereos.c` (bounce DMA, `pcm_start(sfx,0)`, transiciones PCM↔loop/synth)
- `sistema operativo/audio/audio.c`, `audio/audio.h` (`audio_dma_bounce()`, stop/stop_loop robustos, apagado del PC speaker)
- `sistema operativo/drivers/sb16.c` (speaker off en errores DSP; contrato DMA documentado)

**Sin cambios:** `Res/` original (solo lectura), `assets/res_original` de los 10 WAV previos, `Makefile` del juego, API pública `pac_audio_*` (ABI intacta), `include/pac_platform.h`.

**Nota:** `src/render/game_render.c`, `kernel/shutdown.*`, UI y docs del SO tienen cambios de **otra sesión concurrente** ajena a esta auditoría; no forman parte de este trabajo y no se revirtieron.

---

## 6. Correcciones realizadas

1. **Integración de `intermission.wav`** como sonido de nivel completado/transición (slot 10), 5.204 s, 2 chunks de 32.768+24.609 muestras (límite SB16), sin tocar el original.
2. **Máquina de audio del núcleo:** holds = duración real del clip + margen; prioridad de one-shots (la vida extra no la pisa el waka); gracia de 300 ms tras comer puntos para no reiniciar la sirena en bucle.
3. **Semántica de sirenas corregida:** normal = `hunted siren` (slot 13), frightened = `hunter siren` (slot 12); nunca dos sirenas a la vez; respawn de ojos = loop del slot 15.
4. **Eventos completados:** MENÚ en attract/menú/navegación/pausa; nivel completado; game over; pausa/foco/toggle resincronizados; eliminado el POWER espurio al aparecer la fruta.
5. **Linux/CachyOS:** mezclador software (loop + hasta 6 one-shots) sin ABI nueva; síntesis con frecuencia/volumen reales; sin solape de sirenas; cola acotada; cierre limpio; el juego ya no aborta si no hay dispositivo de audio.
6. **SereOS nativo:** bounce buffer DMA-safe para todos los chunks (corrige el corte de START); one-shots siempre one-shot; transiciones PCM→loop/synth sin solapar motores; `audio_stop/stop_loop` robustos; PC speaker apagado correctamente.
7. **Tests:** 24 comprobaciones nuevas de audio en `core_tests.c`; mock con log de secuencia; arneses independientes de verificación.

---

## 7. Pruebas reales de reproducción

### 7.1 CachyOS / Linux-SDL2 (captura real de la salida de audio)

Método: binario real y arnés sobre el núcleo real con `SDL_AUDIODRIVER=disk` / null-sink PipeWire; medidas sobre PCM capturado (duración activa, pico/RMS, frecuencia dominante, correlación con el asset).

| Prueba | Resultado |
|---|---|
| Build limpia `make linux` | PASS, 0 warnings; `make test` = **209 checks, 0 fallos** + 7/7 escenas smoke |
| Game Start | **1 sola vez**, 4,229 s (= clip 4,234), pico −0,8 dBFS, 0 clipping medido en el asset; sin corte ni distorsión final |
| Waka 1/2 | 84 ms, alternancia correcta; no se duplica |
| Eat Ghost / Eat Fruit / Extra Life | Duraciones completas (569/435/1899 ms); EAT_GHOST ya no se borra al comer fruta (mezcla 2 voces, 0 clipping) |
| Death / Game Over | 1,534 s / 166 Hz audible |
| Sirena persecución (13) | Loop continuo, 10,46 s sin huecos; **una sola** sirena |
| Sirena frightened (12) | Cambia a hunter; la sirena WAV anterior se corta (302–313 ms de transición), sin solape |
| Nivel completado | **5,200 s PCM** del `intermission.wav` (antes 0,49 s de beep) |
| Ghost Respawn | Loop del slot 15 cuando hay ojos |
| Menú | Blip sintetizado 659 Hz |
| Pausa / foco / OFF→ON | La sirena se para y se rearma; OFF = silencio total |
| Sin dispositivo de audio | Juego arranca en silencio (exit 0), sin bloqueo |

### 7.2 SereOS nativo (QEMU 11.1.3 + `-device sb16`, TCG)

Método: build real del SO + ISO, automatización por QMP (`sendkey`) y captura por null-sink/PulseAudio; correlación del PCM capturado con el asset.

| Prueba | Resultado |
|---|---|
| Build SO + ISO + libpacman.a | PASS; serial `SEREOS_BOOT_OK`, `GUI_READY`, `LEVEL_START 1`, `GAME_START`, `PAC_DEATH`×3, `GAME_OVER` |
| Driver SB16 | Runtime `backend=sb16`, DSP `0x0405`, base `0x220`, rate `11025` |
| Game Start (bug DMA) | **ANTES:** 2,97 s + 1,5 s silencio (`sb_plays=1`, chunk1 rechazado). **DESPUÉS:** 4,30 s audibles, `sb_plays=2` en chunk1; corr chunk0 **0,992**, chunk1 magnitud **0,847** |
| Sirena persecución (13) | Loop 0,4001 s (= 4412/11025), corr **0,997** |
| Waka 1/2 / Death | Slots 3/4/8 vistos en runtime; `PAC_DEATH` en serial |
| Game Over | Fallback sintetizado audible (1,6 s) |
| Fallback sin SB16 | PC speaker: tonos 950/520/390/370/290/180 Hz correctos |
| POWER / FRIGHT / EAT_GHOST / EAT_FRUIT / EXTRA_LIFE / LEVEL_CLEAR / CHASE | **NO VERIFICADO** en QEMU: no se alcanzaron esos eventos en la partida automatizada; la ruta PCM/loop es la misma que la validada en slots 3/4/8/13, pero no se marca COMPLETO sin captura del evento |
| Hardware SB16 físico | **NO VERIFICADO** (todo QEMU/TCG; no hay SB16 real en la máquina) |

### 7.3 Verificación independiente (agente distinto de los auditores y fixers)

- **Build limpio** Linux + `libpacman.a` + ISO (reconstruida desde snapshot): **PASS**, 0 warnings.
- **Tests:** `checks=209 failures=0`, "TODAS LAS PRUEBAS OK" + 7/7 escenas smoke (194 antes de B5; B5 añadió 15 checks).
- **Assets:** 11 MD5 de `Res` intactos; `res_original` 11/11 byte-idénticos; slots PCM `[2,3,4,6,7,8,9,10,12,13,15]`; START 46.676 (32.768+13.908); LEVEL_CLEAR 57.377 (32.768+24.609)=5,204 s; loop 12/13=1 y 15=0; 0 clipping; regeneración del generador **byte-idéntica** (36/36 checks).
- **Linux/CachyOS:** arnés lógico **30/30 PASS**; capturas reales: START 4,233 s (chunk0 mín. 0,975 / chunk1 mín. 0,993, sin inversión), WAKA 0,086 s, ghost 0,573 s, fruit 0,440 s, death 1,536 s, extra life 1,901 s, LEVEL_CLEAR 5,204 s (26/26 fragmentos mín. 0,985), respawn 0,269 s, sirenas 0,1333/0,4002 s; mezcla verificada (mix2 y mix6, 0 clipping); binario real: START 1 aparición (corr 0,9986), normal solo slot 13, frightened 12→13 **sin ventanas de solape**, victory 5,2 s, soundoff silencio, MENÚ 660 Hz/0,26 s.
- **SereOS nativo (snapshot `tree_snapshot_v3.md5`):** START **4,172 s** audibles, chunk0 14/14 mín. +0,990, chunk1 6/6 mín. +0,993 y **corr firmada +0,9958** (0 negativos: el "-0,847" de B4 era un artefacto de medición, no un defecto); silencio interno máx. 0,047 s (sin hueco); RAM QMP: `chunk=1` y `total_plays` incrementando; loop HUNT 0,4002 s; serial `SEREOS_BOOT_OK/GUI_READY/APP_OPEN:game/GAME_MENU/LEVEL_START/GAME_START/PAC_DEATH×3/GAME_OVER`.
- **Limpieza:** sin binarios scratch en fuentes; `build/` regenerable. Docs obsoletas detectadas y corregidas (B6).
- **Nota de árbol compartido:** durante la verificación, otra sesión ajena al equipo editó ficheros del SO (05:22-05:29). El veredicto nativo se emitió sobre el snapshot v3 (ISO `2f271b70…`, `sereos.bin fe07c51d…`) y los hashes se re-comprobaron tras la captura: árbol estable durante la misma.

**Cierre de los 2 defectos BAJOS de la verificación:**
- **B5 (pausa/foco):** corregido en `src/core/game.c` (+15 tests). Re-verificado: `make test` = **209/0** y escena `pauseoneshot` PASS 2/2 (con EAT_GHOST en curso, pausa y pérdida de foco emiten `pac_audio_stop/stop_loop`). **CERRADO.**
- **B6 (docs):** `docs/GAME.md` y los dos `README.md` (raíz y del proyecto) actualizados a 11 WAV/intermission, slots sintetizados 1/5/11, SIREN_FRIGHT→12, GHOST_RESPAWN loop y **209 checks**; grep final sin obsolescencias de estado actual (solo quedan las entradas históricas del CHANGELOG). **CERRADO.**
- Snapshot final de la re-verificación: `audit/verify/evidence/logs/tree_snapshot_b5b6.md5` (árbol estable durante la comprobación).

---

## 8. Lista final de sonidos completamente funcionales

**Con reproducción verificada por captura real en CachyOS:**
1. `game start.wav` — inicio de partida (1 vez, 4,229 s, sin distorsión).
2. `waka1.wav` / `waka2.wav` — consumo de puntos (alternados).
3. `eat ghost.wav` — captura de fantasma (completo, mezclado).
4. `eat fruit.wav` — consumo de fruta (completo).
5. `extra life.wav` — vida adicional (prioridad, completo).
6. `pacman death.wav` — muerte de Pac-Man.
7. `hunted siren.wav` — sirena de persecución (loop).
8. `hunter siren.wav` — sirena frightened (loop, una sola).
9. `ghost respawn.wav` — regreso de fantasmas (loop).
10. `intermission.wav` — transición/nivel completado (5,20 s).
11. Fallbacks sintetizados: menú, superpunto, game over (no hay clip en `Res`; declarado).

**Con reproducción verificada por captura real en SereOS nativo:**
- `game start.wav` (4,30 s, DMA corregido), `waka1/2`, `pacman death.wav`, `hunted siren.wav`, game over sintetizado, fallback PC speaker.
- Resto de slots: ruta implementada y coherente, pero evento no provocado en QEMU → **NO VERIFICADO** (no se afirma COMPLETO sin prueba).

---

## 9. Limitaciones que persisten (kernel SereOS / host CachyOS)

**Kernel SereOS (no eliminables sin reescribir el driver):**
1. PCM **u8 mono 11025 Hz**, sin conversión de formato/estéreo (todos los assets ya son u8 mono 11025).
2. **Sin mezclador**: una sola voz DMA; no se pueden solapar sirena y efecto. El core prioriza one-shots (p. ej. la vida extra descarta los waka de su intervalo); en Linux sí hay mezcla software.
3. **Sin IRQ5/terminal count**: fin de bloque por tiempo (PIT 100 Hz, 10 ms), sin doble buffer; los loops los rearma la CPU cada frame (~hueco de 1 frame).
4. DMA 8 bits canal 1: <16 MiB y sin cruzar 64 KiB/bloque de 32.768; ahora garantizado por `audio_dma_bounce()`.
5. Altavoz del PC: solo tonos (fallback), sin PCM.
6. QEMU solo emula SB16 si se añade `-device sb16`; sin KVM el guest va lento. **No se probó hardware SB16 físico.**
7. `audio_init()` sigue siendo perezoso (lo llama el juego/monitor/acerca de), no `kernel_main`.

**CachyOS (host):**
- SDL2 2.32.74 sobre PipeWire 1.6.11/PulseAudio 15; ambos dispositivos (S16 22050 y u8 11025) abren exactos; latencia ~46 ms con la cola de 512 B; mezcla u8 mono con ducking a 2+ fuentes; fugas de memoria **NO VERIFICADAS** (valgrind no instalado).
- `hold` del Game Start = 4500 ms ⇒ 266 ms de silencio entre el clip (4233,7 ms) y la sirena; es margen intencional de READY, no un corte.

**Defectos residuales:** ninguno de audio tras B5/B6 (los 2 defectos BAJOS de la verificación quedaron cerrados y re-verificados).

**Pendiente opcional (no bloquea el encargo):** cablear las variantes de pitch 0/10/20/30 % de la sirena (material ya generado en `sfx_res.c`), requiere ampliar la API de plataforma (ABI nueva) y no se hizo en esta fase.

---

## 10. Reproducibilidad

- Regenerar assets: `python3 tools/gen_pacman_res_assets.py` (con el Python bundled del harness, por Pillow); verificación: `audit/fix-assets/verify_fix.py` (determinista, hashes idénticos).
- Build Linux: `make linux` en `Pac-man SereOS/` → `build/pacman-sereos`; tests: `make test`.
- Build SereOS: `make -C "Pac-man SereOS" sereos` y `make` en `sistema operativo/` → `sereos.iso`.
- Capturas: `audit/linux-audit/harness/`, `audit/fix-linux/harness/` y `audit/verify/harness/` (scripts reproducibles).
- Hashes del árbol verificado y resto de evidencias: `audit/verify/REPORT.md` y `audit/verify/evidence/`.
