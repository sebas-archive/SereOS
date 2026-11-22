# VERIFICACIÓN INDEPENDIENTE C — Audio PAC-MAN SereOS (CachyOS/Linux + SereOS nativo)

- **Agente:** `verifier` (independiente de fixers B1–B4 y auditores A1–A4).
- **Tarea:** `task-9` (completada). **Fecha:** 2026-11-20.
- **Workspace:** `/home/t1an/Descargas/sereos02`.
- **Restricciones respetadas:** no se editó ninguna fuente del juego/SO, ni assets, ni tests.
  Todo el trabajo y las evidencias están en `audit/verify/`.
- **Nota de honestidad:** no se escuchó audio de oído; las conclusiones se basan en capturas
  reales medidas con numpy/ffmpeg, en los tests del proyecto y en un arnés lógico propio.
  Lo no provocable se marca **NO VERIFICADO** con motivo.

---

## 0. Snapshot congelado y árbol compartido (leer primero)

El workspace está **compartido con otra sesión/proceso ajeno** que editó el SO durante la
verificación (el Lead lo confirmó: "hay OTRA sesión concurrente… no puedo detenerla"). Por eso
el veredicto nativo se refiere a un **snapshot congelado** (no al árbol "vivo"):

| Elemento | Valor / hora |
|---|---|
| Snapshot de hashes (fuentes del juego + SO audio/drivers/apps/docs) | `audit/verify/evidence/logs/tree_snapshot_v3.md5` (133 archivos), md5 del fichero **`462a041487eeb364a7bfd4cd28f11b02`**, tomado **05:30:25** |
| Rebuild SO/ISO desde ese snapshot | `sereos.bin` md5 **`fe07c51db8c44ec845819f8c2826155b`**, `sereos.iso` md5 **`2f271b702171122b5f7d903339b42871`**, **0 warnings**, build rc=0 (05:30:25) |
| Captura nativa | `audit/verify/evidence/sereos/sereos_frozen.wav` (05:31:27) |
| Re-comprobación de hashes justo después de capturar | **idénticos a v3 → árbol estable durante la captura** |
| Fuentes del juego (Linux) | **idénticas entre el snapshot inicial (05:04, `tree_snapshot.md5`) y v3** → el veredicto Linux es válido |
| Cambios ajenos detectados durante la verificación | SO: `sb16.h/.c` 05:22, `speaker.c` 05:23, `audio/audio.h` 05:23, `apps/about/about.c` 05:23, `audio/audio.c` 05:25 y **05:29:52**. Se rehizo ISO y se repitió la captura nativa sobre v3 |

> **Veredicto nativo: verificado sobre snapshot v3 (md5 `462a0414…`), árbol compartido con otra
> sesión concurrente.** Las huellas de las correcciones B4 están presentes en v3
> (`audio_dma_bounce` en `sistema operativo/audio/audio.c`, `pcm_start(sfx, 0)` en
> `Pac-man SereOS/src/platform/sereos/platform_sereos.c`, `pcspk_release_expired` en `audio.c`).

---

## 1. Veredicto PASS/FAIL por comprobación de `task-9`

| # | Comprobación | Veredicto | Evidencia |
|---|---|---|---|
| 1 | Build limpio Linux + lib SereOS + ISO | **PASS** | `logs/static_summary.txt`, `logs/make_linux.log` (0 warnings), `logs/make_sereos_lib.log`, `logs/make_sereos_iso.log`; ISO 36.806.656 B; rebuild SO final rc=0 y 0 warnings |
| 2 | Tests del proyecto | **PASS** | `logs/make_test.log`: **`checks=194 failures=0`**, `TODAS LAS PRUEBAS OK` (7 smokes OK) |
| 3 | Assets 11 WAV intactos + PCM | **PASS** | `logs/assets_check.json` (36/36 checks ok): MD5/SHA de los 11 WAV de `Res` intactos; `res_original` 11/11 byte-idénticos; slots PCM `[2,3,4,6,7,8,9,10,12,13,15]`; START 46.676 (32.768+13.908); LEVEL_CLEAR 57.377 (32.768+24.609); total 184.411 B; loop 12/13=1, 15=0; **0 clipping**; regeneración del generador byte-idéntica (`sfx_res.c/h`) |
| 4 | Reproducción real Linux/CachyOS | **PASS** (1 residual BAJO: pausa) | `evidence/disk/*` (driver `disk`, captura limpia), `evidence/linux/*` (binario real, escena QA), `evidence/linux/wav/*`; §3 |
| 5 | Reproducción nativa SereOS | **PASS (START/serial/sirena)** + **NO VERIFICADO** (eventos no provocables) | `evidence/sereos/sereos_frozen.*`, `logs/analyze_sereos_frozen.log`, §4 |
| 6 | Limpieza del árbol + docs | **PARCIAL/FAIL menor** | Sin scratch en fuentes (PASS); **docs obsoletos** (`docs/GAME.md:133`, `README.md:176`) → defecto BAJO, §5 |
| 7 | Tabla final por sonido | **entregada** | §6 |

---

## 2. Método (independiente y reproducible)

- **Arnés lógico** `harness/harness_flow_verify.c`: enlaza el **núcleo real** y registra las
  llamadas `pac_audio_*` con `ld --wrap` (nuestro logging, no el mock de los fixers) →
  **30/30 PASS** (`logs/harness_flow_result.txt`).
- **Captura por slot con vector `disk` de SDL** `harness/harness_disk.c`: incluye
  `platform_linux.c` sin editarlo, cierra el dispositivo de síntesis y deja que SDL escriba un
  único RAW S16LE 44100 (captura exacta, sin mezclador del host). Resultados §3.
- **Captura del binario real** con escenas QA + null sink PipeWire + `parec` 48 kHz
  (`harness/capture_linux.sh`, sink con **nombre único**), análisis por correlación local
  normalizada (`harness/analyze_real.py`).
- **SereOS**: QEMU 11.1.3 + `-device sb16` + `-audiodev wav` (aislado), `-serial file:` y QMP
  (`sendkey` + `xp` de globals) (`harness/capture_sereos.sh`, `harness/sereos_scenario.py`).
  QEMU escribe `RIFF/data size = 0` (quirk conocido): el analizador usa el payload restante.
- **Parser propio** de `assets/sfx_res.c` (`harness/parse_assets.py`) y análisis
  duración/energía/espectro/clipping/correlación (`harness/analyze_audio.py`,
  `harness/analyze_captures.py`, `harness/analyze_sereos.py`).

Nota metodológica honesta sobre **clipping de captura vs asset**: los assets no tienen clipping
(0 muestras 0/255) y las capturas con el driver `disk` tampoco (pico −0,8 dBFS máx). Una tanda
inicial de capturas por null-sink mostró +1,35 dB y picos recortados: se debía al **volumen
restaurado del nodo PipeWire de nombre reutilizado `verify_null`** (host), no al juego; con un
sink de nombre nuevo la ganancia medida es **×1,010 y clipping 0**. Las capturas finales usan
un sink único y son limpias.

---

## 3. Linux/CachyOS — resultados medidos

### 3.1 Arnés lógico (núcleo real, 30/30 PASS)

`START` se pide **1 vez** y la sirena normal vuelve tras el hold; waka alterna 3/4 (3 dots → 3
plays); `EXTRA_LIFE` no es pisada por el waka del mismo tick; `GHOST_RESPAWN`(15) se pide como
loop mientras hay ojos `EATEN` y vuelve a 13; frightened usa **12** y normal **13**; `MENU` se
pide al navegar; `LEVEL_CLEAR`(10) dura ≥5,2 s; `GAME_OVER`(11) se pide; pausa/foco paran y
rearman el loop; toggle OFF→ON rearma; prioridad de one-shots (EAT_GHOST no truncado por waka);
`POWER`(5) pide beep y el loop 12 no lo corta antes de ~300 ms.

### 3.2 Capturas por slot con driver `disk` (audio real de la plataforma)

| Slot | Sonido | Medido (duración activa / pico / clip / dom.) | Correlación con el clip | Estado |
|---|---|---|---|---|
| 2 | START | span **4,233 s** (activo 3,784 por micro-pausas), −0,8 dBFS, **0 clip** | chunk0 (0–32.768): 14/14 excerptos, min **0,975**; chunk1 (32.768–46.676): 6/6, min **0,993**, sin inversión | **COMPLETO** |
| 3/4 | WAKA1/2 | 0,086 s cada uno, −0,8 dBFS, 0 clip | 0,955 / 0,938 | **COMPLETO** |
| 6 | EAT_GHOST | **0,573 s** = clip | 0,965 | **COMPLETO** |
| 7 | EAT_FRUIT | **0,440 s** = clip | 0,995 | **COMPLETO** |
| 8 | DEATH | **1,536 s** = clip | 0,967 | **COMPLETO** |
| 9 | EXTRA_LIFE | **1,901 s** = clip | 0,964 | **COMPLETO** |
| 10 | LEVEL_CLEAR | **5,204 s** = intermission, −0,8 dBFS, 0 clip | **26/26 excerptos, min 0,985** | **COMPLETO** |
| 15 | GHOST_RESPAWN | **0,269 s** = clip | 0,912 | **COMPLETO** (slot) |
| 12 | SIREN_CHASE | bucle 3,135 s sin huecos | periodo 0,1333 s (autocorr 1,0; primer periodo 0,99) | **COMPLETO** |
| 13 | SIREN_HUNT | bucle 3,135 s sin huecos | periodo 0,4002 s | **COMPLETO** |

**Mezcla (afirmación B3):** verificada. `mix2` (WAKA1+DEATH a la vez): el espectro del tramo
de solape contiene **ambos timbres** (picos ~560/850 Hz de WAKA1 y ~1.400 Hz de DEATH).
`mix6` (6 voces simultáneas): audio continuo **2,064 s** (si fuera "last-wins" terminaría en
~0,873 s), pico −0,5 dBFS, **0 clipping** → reparto de ganancia 1/N correcto.

### 3.3 Binario real, escenas QA (captura limpia, gain ×1,010, clip 0)

| Escena | Medición | Interpretación |
|---|---|---|
| `gamestart` | START: **1 sola aparición**, span **4,200 s**, min corr. **0,9986**; después solo sirena 13 (0,4002 s). Pico −0,8 dBFS, clip 0 | **PASS**: START una vez, completo y sin distorsión |
| `play` | solo sirena **13** (HUNT), sin 12 | **PASS** |
| `frightened` | 12 (CHASE) presente de 5,3–6,9 s; después 13 (HUNT). Ventanas con **ambas a la vez: 0** | **PASS**: mapeo correcto y sin solape |
| `ghostcapture` | 12 → 13 secuencial; 0 ventanas de solape | **PASS** (sin solape) |
| `death` | START interrumpido por muerte (prioridad DEATH), luego 13 | **PASS** |
| `victory` | LEVEL_CLEAR presente; 26 excerptos, **span 5,200 s** (intermission) | **PASS** |
| `gameover` | beep sintetizado 165 Hz (0,6 s), −8,3 dBFS; 238 muestras a 0 dBFS (onda cuadrada a escala completa) | **PASS funcional** (nota: beep duro) |
| `menu` | **active=0**: la escena QA fija `state=MENU` directamente y **no** navega, así que no se dispara el blip. El sonido MENU se verificó por el arnés lógico (se pide al navegar) y por captura del slot 1: **0,26 s, 660 Hz** | **PASS** (la escena no ejerce navegación) |
| `pause` | START suena completo (~4,2 s) con la partida pausada | **PARCIAL**: la pausa para la sirena pero **no silencia un one-shot en curso** (residual BAJO, preexistente) |
| `soundoff` | silencio total (pico −180 dBFS) | **PASS** |

Síntesis corregida (capturas del slot): MENU 660 Hz / 0,26 s; POWER 1200 Hz / 0,17 s;
GAME_OVER 165 Hz / 0,61 s; FRIGHT (fallback) 440 Hz. Antes: ÷2,97 de frecuencia y −20 dB.

---

## 4. SereOS nativo — veredicto sobre snapshot v3

QEMU 11.1.3 + `-device sb16` + `-audiodev wav`; serial y globals por QMP. Captura
`evidence/sereos/sereos_frozen.wav` (28,13 s de audio, pico −0,8 dBFS, **0 clipping**, silencio
máximo 0,047 s → sin el hueco de ~1,5 s del defecto D1).

**Serial** (`sereos_frozen.serial`): `SEREOS_BOOT_OK`, `GUI_READY`, `GAME_MENU`,
`APP_OPEN:game`, `LEVEL_START 1`, `GAME_START`, `PAC_DEATH`, `LIFE_START 2`, `PAC_DEATH`,
`LIFE_START 1`, `PAC_DEATH`, `GAME_OVER`.

**RAM del guest (QMP `xp`, solo lectura, `sereos_frozen.probe.txt`):**
`t=19,01 slot=2 active=1 total_plays=3` → `t=21,54 chunk=1 total_plays=4` (**el chunk1 de START
sí se reproduce; D1 corregido**) → `t=23,06 chunk=0 loop=1 total_plays=5` (sirena) →
`slot 4`/`slot 3` (waka) → `slot=13 loop=1` y `total_plays` subiendo (loop rearmado).

**START, verificación de chunk1 (pregunta especial del Lead):** por excerptos de 0,2 s con
búsqueda de lag local (deriva de reloj invitado/anfitrión):
- chunk0 (0–32.768): 14 excerptos, **min corr +0,990** (todas positivas).
- chunk1 (32.768–46.676): 6 excerptos, **min corr +0,993**, media **+0,996**, **0 negativas**.
- chunk1 completo: **corr firmada +0,9958** (referencia invertida: −0,9958 en el mismo lag).
- span audible del START: **4,172 s** (clip 4,234 s; diferencia de ventana de búsqueda);
  silencio interno máximo **0,047 s** (pausas musicales).
→ **El chunk1 es el audio correcto de `game start` (positivo, sin inversión de polaridad) y el
START es completo.** La cifra "chunk1 corr −0,847" del informe B4 es un **artefacto de su
medición** (signo/lag); no hay defecto residual en el audio.

**Presencia de slots en la captura nativa (correlación local, firmada):** START **+0,995**,
WAKA1 **+0,992**, WAKA2 **+0,993**, DEATH **+0,988**, SIREN_HUNT **+0,997** (periodo 0,4002 s)
→ **COMPLETO** (PCM por SB16, loops y one-shots). Sin evidencia (no provocados en la partida
automatizada): EAT_GHOST, EAT_FRUIT, EXTRA_LIFE, LEVEL_CLEAR, SIREN_CHASE/FRIGHT, GHOST_RESPAWN,
POWER, MENU y audio de GAME_OVER → **NO VERIFICADO** con motivo (la app del SO no tiene escenas
QA; en ~40 s de `sendkey` no se come power-pellet/fruta/fantasma ni se completa nivel; el
serial sí confirma `GAME_OVER`).

---

## 5. Limpieza del árbol, regenerabilidad y docs

- **Sin scratch en fuentes:** PASS (no hay `.o/.raw/.wav/.tmp/.bin/.iso` en `src/`, `assets/`
  fuera de `res_original`, `audio/`, `drivers/`, `apps/`, `include/`).
- **Regenerable por `make clean`:** PASS — build Linux limpio, lib SereOS y SO/ISO desde cero;
  `sereos.bin` binario reproducible (recompilación byte-idéntica en el mismo snapshot).
- **Docs — defecto BAJO (stale, no corregido por el verificador):**
  - `Pac-man SereOS/docs/GAME.md:133` dice "`intermission.wav` no se usa (Paku no lo usa)" y
    "131 casos"; contradice `docs/GAME.md:90-94` (intermission integrado) y el recuento real
    (**194** checks).
  - `Pac-man SereOS/README.md:176` dice "10 WAV … (intermission excluido)"; el estado real es
    **11 WAV** con intermission en el slot 10.
  - `sistema operativo/CHANGELOG.md:65` ("de 10 WAV") es una entrada histórica del CHANGELOG,
    no una afirmación del estado actual.

---

## 6. Tabla final por sonido/evento

Leyenda: **COMPLETO** = ruta + audio medido; **PARCIAL** = suena con defecto/limitación;
**NO VERIFICADO** = no provocable (con motivo); **AUSENTE** = no existe/no se dispara.

| Sonido / evento | CachyOS/Linux | Evidencia Linux | SereOS nativo | Evidencia SereOS |
|---|---|---|---|---|
| Game start (2, START) | **COMPLETO** (1 vez, 4,233 s) | disk slot2; real_start 1 aparición 4,2 s corr 0,9986 | **COMPLETO** (chunk0+chunk1) | captura 4,172 s; chunk1 +0,9958; probe chunk=1, total_plays+1 |
| Waka 1/2 (3/4) | **COMPLETO** (alterna) | disk 0,086 s; arnés 3/3 alterno | **COMPLETO** | corr +0,992 / +0,993; probe slots 3/4 |
| Eat ghost (6) | **COMPLETO** | disk 0,573 s; prioridad OK | NO VERIFICADO (no se comió fantasma) | — |
| Eat fruit (7) | **COMPLETO** | disk 0,440 s | NO VERIFICADO (no apareció fruta en la partida) | — |
| Extra life (9) | **COMPLETO** | disk 1,901 s; no pisada por waka | NO VERIFICADO (no se alcanzó 1UP) | — |
| Death (8) | **COMPLETO** | disk 1,536 s; real_death | **COMPLETO** | corr +0,988; serial `PAC_DEATH` ×3 |
| Ghost respawn (15) | **COMPLETO** (slot + lógica loop) | disk 0,269 s; loop 15 en arnés | NO VERIFICADO (no provocado) | — |
| Sirena normal (13, hunted) | **COMPLETO** | periodo 0,4002 s; real_play solo 13 | **COMPLETO** | corr +0,997; periodo 0,4002 s; loop rearmado |
| Sirena frightened (12, hunter) | **COMPLETO** | real_frightened 12→13, 0 solape; mix | NO VERIFICADO (sin power-pellet) | — |
| POWer / power-pellet (5) | **COMPLETO** (síntesis 1200 Hz; hold 320) | captura slot 5; arnés POWER | NO VERIFICADO (síntesis kernel; no provocado) | — |
| Nivel completado (10, intermission) | **COMPLETO** (5,204 s) | disk 26/26 excerptos; real_victory span 5,2 s | NO VERIFICADO (no se completó nivel) | — |
| Game over (11) | **COMPLETO** (beep 165 Hz/0,6 s) | captura slot 11; real_gameover | **PARCIAL/NO VERIFICADO**: serial `GAME_OVER` sí; audio sintetizado no aislado en la captura | serial; fallback sintetizado del kernel |
| Menú (1) | **COMPLETO** (se pide al navegar; beep 660 Hz) | arnés MENU; captura slot 1; real_menu active=0 (escena no navega) | NO VERIFICADO (no se navegó el menú del SO) | — |
| Pausa / foco / toggle sonido | **PARCIAL**: sirena para/rearma y toggle OK; **la pausa no silencia un one-shot en curso** (START sigue 4,2 s) | real_pause; arnés pausa/foco/toggle | NO VERIFICADO | — |
| Sonido OFF | **COMPLETO** (silencio total) | real_soundoff | NO VERIFICADO | — |

**Limitaciones reales que persisten**
1. Documentación obsoleta en `docs/GAME.md:133` y `README.md:176` (BAJO; no es audio).
2. La pausa no detiene el one-shot YA en curso (BAJO, preexistente).
3. `effect_hold_ms(START)=4500` vs clip 4,234 s → ~266 ms de silencio antes de la sirena
   (documentado y aceptado por diseño).
4. SereOS: PCM mono u8 11025 por SB16, una voz PCM + loop por rearme en `pac_audio_update`;
   el **kernel** sigue sin mezclador para sus fallbacks sintetizados; sin IRQ5/hardware real
   no se puede verificar la temporización en hierro (solo QEMU/TCG).
5. El beep sintetizado de GAME_OVER (onda cuadrada a escala completa) resulta duro (238
   muestras a 0 dBFS en la captura): funcional, no es distorsión de assets.
6. Slots sin escena QA nativa (SereOS) quedan **NO VERIFICADO** por imposibilidad de provocar
   el evento con `sendkey` en el tiempo de ejecución.
7. QEMU `-audiodev wav` escribe `RIFF/data size = 0`; se analiza el payload (documentado).

---

## 7. Índice de evidencias (todas en `audit/verify/`)

```
REPORT.md                          este documento
harness/
  harness_flow_verify.c            núcleo real + ld --wrap (30/30 PASS)   [logs/harness_flow_result.txt]
  harness_disk.c                   captura por slot con driver disk       [evidence/disk/*.raw]
  harness_capture.c                captura por slot API pública + null sink
  capture_linux.sh                 binario real (escenas QA) + slots, sink único
  capture_sereos.sh                QEMU SB16 + serial + QMP               [evidence/sereos/]
  sereos_scenario.py / qmp_peek.py / qmp_keys.py  automatización QMP
  parse_assets.py / analyze_audio.py / analyze_captures.py / analyze_real.py
  analyze_sereos.py / verify_assets.py / verify_static.sh / env_check.sh
evidence/
  env.txt                          entorno (versiones, sinks, backends QEMU)
  logs/static_summary.txt          PASS/FAIL de builds/tests/assets/limpieza
  logs/assets_check.json           36/36 checks de assets
  logs/make_test.log               checks=194 failures=0
  logs/tree_snapshot{,_v2,_v3}.md5 hashes del árbol (v3 = snapshot del veredicto)
  disk/                            capturas limpias por slot + mezcla (mix2/mix6)
  linux/*.raw + linux/wav/*.wav    binario real por escena (escuchables)
  linux/*.json / analysis.*        métricas y correlaciones
  sereos/sereos_frozen.{wav,serial,probe.txt}   captura nativa del snapshot v3
  sereos_analysis.json             START chunk0/chunk1, span, silencios
```

**Reproducción mínima** (desde el workspace):
```sh
./audit/verify/harness/build_harnesses.sh
./audit/verify/harness/verify_static.sh
./audit/verify/harness/harness_flow_verify all
./audit/verify/harness/capture_linux.sh
python3 audit/verify/harness/analyze_real.py
python3 audit/verify/harness/analyze_captures.py
SYMBOLS="g_pcm_slot,g_pcm_chunk,g_pcm_active,g_pcm_loop,total_plays" \
  ./audit/verify/harness/capture_sereos.sh wav final 55
python3 audit/verify/harness/analyze_sereos.py audit/verify/evidence/sereos/sereos_frozen.wav
```

---

## 8. Conclusión

**Las correcciones B1–B4 cumplen el encargo de audio en lo verificable:** build/tests/assets
PASS; en **CachyOS** los 11 sonidos con WAV suenan, completos y sin truncado, START una sola
vez, sirenas correctas (13 normal / 12 frightened) sin solape, LEVEL_CLEAR usa intermission
5,2 s, mezcla de one-shots real (hasta 6 voces) y síntesis con pitch/volumen correctos. En
**SereOS nativo (snapshot v3)** el SB16 reproduce START completo —**chunk1 correcto y no
invertido**—, waka y death por PCM y la sirena en loop, con serial y globals coherentes; los
eventos no provocables quedan marcados NO VERIFICADO con motivo.

**Defectos residuales:** solo dos de baja severidad (docs obsoletos; la pausa no silencia un
one-shot en curso). **No se encontró ningún fallo grave de audio** en el snapshot verificado.

---

## 9. Re-verificación B5/B6 (correcciones residuales tras task-9)

- **Fecha:** 2026-11-20T05:34–05:36. **Sin re-capturas QEMU** (según instrucción del Lead).
- **Snapshot de esta re-verificación** (`evidence/logs/tree_snapshot_b5b6.md5`, tomado 05:34:43):
  | fichero | md5 |
  |---|---|
  | `src/core/game.c` (B5 pausa/foco) | `a143e73119207ec04991e64089b2197a` |
  | `src/core/game_audio.c` | `e737fd7fce83157b70d94ec094b2379c` |
  | `src/core/pac_game.h` | `2c01e02f41f4ab1845af7056b5d2647a` |
  | `tests/core_tests.c` | `7cd57ab2b4927f368de73439b3b338ed` |
  | `tests/mock_platform.c` | `28382c4121fc7d58d3e76d689119ebb3` |
  | `docs/GAME.md` (B6) | `b38c8d9116fbf20814cfa03e422aedcd` |
  | `README.md` | `2919e3368c611ee267f265af1ff7d049` (mtime 04:24:56: **no modificado** por B6) |

| Ítem B5/B6 | Veredicto | Evidencia |
|---|---|---|
| `make linux` con B5 | **PASS** (0 warnings) | `evidence/logs/b5b6_make_linux.log` |
| `make test` con B5 | **PASS** — **`checks=209 failures=0`**, `TODAS LAS PRUEBAS OK` | `evidence/logs/b5b6_make_test.log` |
| B5: la pausa silencia un one-shot en curso | **PASS** | arnés lógico `harness_flow_verify pauseoneshot`: `pac_audio_stop/stop_loop` emitido al pausar con EAT_GHOST en curso (2/2 PASS) — `evidence/logs/b5b6_pauseoneshot.log` |
| B5: la pérdida de foco silencia un one-shot en curso | **PASS** | idem (2/2 PASS) |
| B6: `docs/GAME.md` sin afirmaciones obsoletas | **PARCIAL** | Ya dice **11 WAV** (`:90`) e intermission 5,204 s (`:93`); residual: `docs/GAME.md:136` aún dice "194 casos" (el recuento real es **209**) |
| B6: `README.md` sección audio sin afirmaciones obsoletas | **FAIL (BAJO)** | `README.md:175-176` sigue diciendo **"10 WAV … (intermission excluido)"**; el fichero no fue modificado (mtime 04:24:56). Debe decir 11 WAV e intermission integrado en el slot 10 |
| CHANGELOG histórico ("de 10 WAV") | OK | Es una entrada histórica del CHANGELOG del SO; no es una afirmación del estado actual |

**Conclusión B5/B6:** B5 **cerrado y verificado** (209/0 tests + pausa/foco silencian one-shots).
B6 **queda parcialmente cerrado**: GAME.md actualizado (salvo el recuento de tests), pero
`README.md:175-176` sigue con la afirmación obsoleta "10 WAV / intermission excluido". Es un
defecto de documentación **BAJO**; no afecta al audio.
