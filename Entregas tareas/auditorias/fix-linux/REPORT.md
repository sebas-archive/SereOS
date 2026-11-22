# CORRECCIÓN B3 — Plataforma Linux/SDL2 de PAC-MAN SereOS

- **Tarea:** `task-7` (fase de corrección), basada en `audit/linux-audit/REPORT.md` §10.
- **Autor:** `linux-audit`.
- **Fecha:** 2026-11-20.
- **Scope respetado:** solo se modificó **`Pac-man SereOS/src/platform/linux/platform_linux.c`**.
  `Makefile`, `src/core/`, `assets/`, `include/`, `tests/` y el SO **no** se tocaron
  (`Makefile` verificado byte a byte contra el backup; `cmp` OK).
- **Integración final probada con:** núcleo B2 (task-6) y assets B1 (task-5) ya
  regenerados (`assets/sfx_res.c` 1120069 B, slot 10 LEVEL_CLEAR = intermission PCM
  57377 muestras / 5,204 s / 2 chunks; `pacasset_sfx_res_loop[15]=0`).
- **Binario final:** `build/pacman-sereos`, SHA-256
  `9bc91ce541a2fb9d5012635026749b18561f9b49bca8a43f2e654049aa81fb0c`,
  compilado con `make -B linux` → **0 warnings, 0 errores**.
- **Evidencias:** `audit/fix-linux/evidence/` (raw/wav/logs/CSV), arneses en
  `audit/fix-linux/harness/`, diff completo en
  `evidence/logs/platform_linux_fix.diff` (637 líneas), backup del original en
  `audit/fix-linux/backup/platform_linux.c.orig`.

---

## 1. Qué se cambió (una sola fuente, sin API nueva)

| # | Requisito task-7 | Implementación en `platform_linux.c` |
|---|---|---|
| 1 | P0: no solapar sirena WAV + síntesis | `pac_audio_play()` rama sintetizada → `pcm_loop_stop()` (`:655-668`); `pac_audio_loop()` rama sintetizada → `pcm_loop_stop()` + `synth_loop_start()` (`:670-686`). `pcm_loop_stop()` limpia la cola si no hay one-shots vivos (`:394-403`). |
| 2 | P1: síntesis con frecuencia/amplitud reales | `synth_phase_inc()` = `freq·65536/22050` (antes se usaba `freq` como incremento → ÷2,97) (`:472-480`); `PAC_SYNTH_AMP 10000` (antes ±2200 → −21,6 dBFS) (`:47`, `:508-512`); envolvente anti-click de 2 ms (`synth_fade_gain`, `:514-526`). Bucle y one-shot sintetizados se mezclan en el callback (`:528-562`). |
| 3 | Cola PCM única: mezcla software mínima sin ABI nueva | Mezclador propio en `pac_audio_update()`: bucle de sirena + hasta 6 voces one-shot (`pcm_voice_start`, `:359-392`), leídas por chunks de `sfx_res` (soporta clips de 2 chunks, p. ej. START/intermission) y mezcladas en bloques de 256 muestras u8 (`mixer_feed`, `:421-468`). **No se llama `SDL_ClearQueuedAudio` al reproducir**: un one-shot ya no borra al anterior ni a la sirena (`:655-668`). Ganancia `1/nº_fuentes` para no saturar el u8 (`:447-457`). La prioridad sigue decidiéndola el core (B2); el backend solo mezcla. |
| 4 | Cola robusta, stop limpia, cierre correcto, arranque sin audio | Cola realimentada hasta `PAC_PCM_TARGET=512 B` (~46 ms) con tope de 32 iteraciones; 10 s de bucle sin huecos y cola acotada (máx 761 B). `pcm_stop()`/`pac_audio_stop()` vacían voces+cola+stream (`:405-416`, `:693-697`); `pac_platform_shutdown()` cierra los 2 dispositivos y libera el `SDL_AudioStream` (`:773-800`). `pac_platform_init()` inicializa vídeo/eventos y luego `SDL_InitSubSystem(AUDIO)` por separado: si el audio falla **el juego arranca en silencio**, ya no `exit 1` (`:710-735`). Fallback si el host no da `u8/mono/11025` exacto: `SDL_AudioStream` de conversión (`:615-646`) en vez de cerrar el dispositivo y caer a beeps. |
| 5 | Sin hardcodear slots (LEVEL_CLEAR) | Todo es data-driven con `pacasset_sfx_res_available(slot)` y las tablas `pacasset_sfx_res_chunks/len/count`. Al regenerar B1, el slot 10 sonó automáticamente como PCM de 5,200 s sin tocar código (`evidence/logs/fix_10_level_clear_pcm.log`, `analysis_slots.csv`). |

**Detalles de diseño relevantes**
- `pac_audio_loop()` WAV no limpia la cola: cambia el bucle y sigue mezclando one-shots
  (evita el ping-pong waka↔sirena del informe §5.2).
- Al pasar de WAV a síntesis (p. ej. FRIGHT si no tuviera WAV, POWER) se para el bucle PCM
  (`pcm_loop_stop`) y, si no hay one-shots, se limpia la cola → **la sirena WAV no sigue
  sonando debajo** (ver §3).
- El bucle PCM se lee muestra a muestra con reinicio de chunk al final: sin huecos y con
  clips de cualquier número de chunks (START 2, intermission 2).
- No se cambió `include/pac_platform.h` ni la firma de `pac_audio_*`.

---

## 2. Medidas ANTES → DESPUÉS (capturas reales `SDL_AUDIODRIVER=disk`)

Tabla generada por `harness/analyze_slots.py` sobre
`evidence/raw/fix_*.raw` (S16LE 44100 estéreo, salida real de SDL) y comparada con
`audit/linux-audit/evidence/analysis_slots.csv` (antes). Completa en
`evidence/before_after_slots.txt`.

| Slot | Sonido | ANTES | DESPUÉS | Veredicto |
|---:|---|---|---|---|
| 1 | MENU | 221 Hz, RMS −23,5, pico −21,6 | **659 Hz, RMS −10,4, pico −8,1** | pitch/vol corregidos |
| 2 | START | 4,229 s, −0,8 pico, 0 clipping | 4,229 s, −0,8 pico, 0 clipping | intacto |
| 3/4 | WAKA1/2 | 0,083 s, 851/603 Hz | 0,083 s, 851/603 Hz | intacto |
| 5 | POWER | 404 Hz, RMS −23,5 | **1200 Hz, RMS −10,4** | pitch/vol corregidos |
| 6 | EAT_GHOST | 0,569 s, 855 Hz | 0,569 s, 855 Hz | intacto (ya no lo borra otro SFX) |
| 7 | EAT_FRUIT | 0,435 s, 209 Hz | 0,435 s, 209 Hz | intacto |
| 8 | DEATH | 1,534 s, 536 Hz | 1,534 s, 536 Hz | intacto |
| 9 | EXTRA_LIFE | 1,899 s, 374 Hz | 1,899 s, 374 Hz | intacto |
| 10 | LEVEL_CLEAR | 0,488 s sintetizado, 592 Hz | **5,200 s PCM, 181 Hz** | B1+B3: intermission real |
| 11 | GAME_OVER | **55 Hz** (subsónico), RMS −23,5 | **166 Hz, RMS −10,3** | audible |
| 12 | SIREN_CHASE | 2,078 s continuo | **10,461 s continuo, 845–1650 Hz** | bucle robusto |
| 13 | SIREN_HUNT | 2,090 s continuo | 2,090 s continuo, 396–851 Hz | intacto |
| 14 | SIREN_FRIGHT (fallback synth) | 148/221 Hz, RMS −23,5 | **439/660 Hz, RMS −10,3** | solo fallback (B2 usa slot 12) |
| 15 | GHOST_RESPAWN | one-shot 0,266 s (nunca disparado) | **bucle continuo (1,045 s capturados)** | B2 lo pide como loop; B3 lo mezcla |

**0 muestras clipeadas** en las 16 capturas por slot y en las 4 de mezcla
(`clipped=0` en `analysis_slots.csv`; comprobación extra de mezclas en §3).
`END/AFTER_STOP queued=0` en **19/19** capturas (cola drenada al parar).

### 2.1 Verificación START (una sola vez, duración, sin corte)
`evidence/logs/fix_flow_start.log` (núcleo B2 + plataforma B3):
- `pac_audio_play(2)` **una única vez** (t=100 ms); `SUMMARY start_plays=1` tras 6,17 s.
  Con `pausecycle` (3 pausas/reanudaciones) también `start_plays=1`.
- Encola el clip completo por el mezclador: 46676 B (2 chunks) reproducidos en
  **4,229 s** de señal activa (recurso 4,234 s), pico −0,78 dBFS, 0 clipping, cola natural.
- **Limitación que persiste (es del core, no de la plataforma):** `hold START = 4500 ms`
  > clip 4234 ms ⇒ **266 ms de silencio** antes de reanudar la sirena (t=4170 cola 0,
  t=4612 `pac_audio_loop(13)`). Se mantiene por diseño B2 (`PAC_READY_START_MS`).

### 2.2 Verificación de mezcla y transiciones (arnés propio, dispositivo PCM aislado)
| Prueba | Evidencia | Resultado |
|---|---|---|
| Sirena WAV + EAT_GHOST | `fix_combo_siren_ghost` | 2 fuentes mezcladas; la voz de ghost sigue **574 ms** completa (antes: la sirena la cortaba o el siguiente SFX la borraba). |
| EAT_GHOST + EAT_FRUIT a 50 ms | `fix_combo_ghost_fruit` | **2 voces simultáneas**, audio activo 0,571 s (ghost 574 ms; antes el ghost se cortaba a 24 ms), pico −1,66 dBFS, **0 clipping**. |
| Sirena WAV → POWER (synth) | `fix_combo_power_synth` | la sirena PCM se corta en **0,302 s** y la cola queda a 0; antes seguía sonando debajo. |
| Sirena WAV → FRIGHT synth | `fix_combo_fright_synth` | ídem, corte en 0,313 s. |
| Cola en bucle 10 s | `fix_12_siren_chase_pcm_loop` | sin huecos (10,461 s activos), `queued` máx **761 B** (< objetivo+bloque), media ~694 B, sin crecimiento. |
| `pac_audio_stop` | logs `AFTER_STOP` | `queued=0` en las 19 capturas; dispositivos cerrados (`dev=2` y `dev=3`) al salir. |

### 2.3 Mapa final de sirenas (núcleo B2 + plataforma B3)
`evidence/logs/fix_flow_sirenmap.log` (Pac-Man congelado para aislar):
`normal → pac_audio_loop(13)` (hunted WAV) → `fright → loop(12)` (hunter WAV) →
`ojos de fantasma → loop(15)` (respawn WAV) → vuelta a `loop(13)`.
Transiciones sin `ClearQueuedAudio` (mezclador continuo) y sin dos sirenas simultáneas.
Los tests del core (`make test`, 194 checks) cubren además: *frightened usa CHASE/hunter
slot 12*, *GHOST_RESPAWN suena como loop mientras hay ojos*, *MENÚ suena*, *OFF/ON y
pérdida de foco rearman la sirena*.

---

## 3. Build, tests y modos de fallo (todos verificados)

| Comprobación | Comando | Resultado |
|---|---|---|
| Compilación limpia | `make -B linux` | **0 errores, 0 warnings** (`fix_make_linux.log`); binario SHA-256 `9bc91ce5…` |
| Tests del core | `make test` | **194 checks, 0 failures** + smoke Linux 7/7 OK (`fix_make_test.log`) |
| Host real (PipeWire) | `SDL_AUDIODRIVER=pipewire --smoke 120` | exit 0, sin errores (`fix_real_pipewire.log`) |
| `SDL_Init(AUDIO)` falla | `SDL_AUDIODRIVER=no_such_driver` | **exit 0** (antes exit 1); aviso “audio no disponible; el juego seguira en silencio” y juego funcional (`fix_real_badaudio.log`) |
| Dispositivo no abre | `SDL_DISKAUDIOFILE=/proc/no/x.raw` | exit 0, “audio: sin dispositivos”, juego en silencio (`fix_real_nodev.log`) |
| Sonido OFF en Ajustes | `sound.txt=0` + captura | silencio total, pico 0 (`fix_real_soundoff.log/.raw`) |
| Sin fugas de cola | 10 s bucle + stop | cola acotada y 0 al parar; dispositivos cerrados |

**Nota de QA:** el driver `disk` con el **binario real** sigue sin ser fiable para capturar
(auditoría §9): el juego abre 2 dispositivos que escriben el mismo `SDL_DISKAUDIOFILE`.
Para medir por slot se usó el arnés `harness_slots_fix` (deja abierto un solo dispositivo;
no modifica el proyecto).

---

## 4. Limitaciones que persisten (honestas)

1. **Hueco de 266 ms tras Game Start**: el `hold` de 4500 ms lo fija el core (B2) alineado
   con `PAC_READY_START_MS`; el clip dura 4234 ms. No es corregible desde la plataforma.
2. **Mezclador mono u8 11025**: la mezcla normaliza por nº de fuentes (`1/n`) para no
   clipear; con 2 fuentes simultáneas cada una baja ~6 dB (ducking). Es una mezcla mínima,
   no un mezclador polifónico con headroom real (el formato u8 no da margen).
3. **Latencia de arranque de efectos**: cola objetivo 512 muestras (~46 ms). Suficiente y
   sin huecos en las pruebas, pero no es latencia cero.
4. **El core sigue parando el bucle antes de cada one-shot con `hold`** (`pac_audio_stop_loop`),
   por lo que la mezcla se ejerce sobre todo en waka/overlap y en las transiciones de bucle;
   con la ventana de gracia y prioridades de B2 muchos solapes ya no llegan al backend.
5. **Fallback `SDL_AudioStream`** (hosts que no conceden `u8/mono/11025` exacto):
   implementado y compilado, pero **NO VERIFICADO en este host** (PipeWire/disk/pulse sí
   conceden el formato exacto: `g_pcm_stream=0` en todas las capturas).
6. **Fugas de memoria**: no se pudo medir (`valgrind` no está instalado); la liberación de
   recursos SDL/cola sí está verificada por logs.
7. El slot 14 (SIREN_FRIGHT) solo se usa como **fallback sintetizado**; el núcleo B2 usa
   el slot 12 (WAV hunter) para frightened. Las 8 variantes de pitch siguen sin usarse
   (pendiente de otra fase, no de la plataforma).

---

## 5. Inventario de evidencia

```
audit/fix-linux/
├── REPORT.md                          (este documento)
├── backup/
│   ├── platform_linux.c.orig          (original auditado, SHA-256 89df5c44…)
│   └── Makefile.orig                  (intacto, cmp OK)
├── harness/
│   ├── harness_slots_fix.c            (captura por slot, incluye platform_linux.c sin editar)
│   ├── harness_flow.c                 (traza game→game_audio→pac_audio→SDL con ld --wrap; escenario sirenmap)
│   ├── analyze_slots.py               (duración/energía/frecuencia/clipping)
│   └── harness_slots_fix, harness_flow (binarios)
└── evidence/
    ├── analysis_slots.csv             (medidas después; 16 slots + 4 mezclas)
    ├── before_after_slots.txt         (tabla antes/después generada)
    ├── raw/                           (20 .raw: 16 por slot + 4 de mezcla/transición + soundoff)
    ├── wav/                           (20 .wav escuchables, ffmpeg)
    └── logs/
        ├── platform_linux_fix.diff    (diff completo 637 líneas)
        ├── fix_make_linux.log         (0 warnings), fix_binary_sha256.txt
        ├── fix_make_test.log          (194 checks OK + smoke)
        ├── fix_flow_*.log             (start, pausecycle, siren, sirenmap, oneshot, death, holdcut, respawn)
        ├── fix_*_pcm/synth.log        (captura por slot + qmax/voices/AFTER_STOP)
        ├── fix_combo_*.log            (mezcla ghost+fruit, sirena→power, sirena→fright, sirena+ghost)
        ├── fix_real_badaudio.log      (audio roto ⇒ arranca en silencio, exit 0)
        ├── fix_real_nodev.log         (sin dispositivo ⇒ silencio, exit 0)
        ├── fix_real_pipewire.log      (host real OK)
        └── fix_real_soundoff.log/.raw (Ajustes OFF ⇒ silencio total)
```

**Reproducir:**
```bash
P="/home/t1an/Descargas/sereos02/Pac-man SereOS"; A="/home/t1an/Descargas/sereos02/audit/fix-linux"
cd "$P" && make -B linux && make test
gcc -O2 -std=gnu99 -w -Iinclude -Isrc/core -Isrc/render -Isrc/platform/linux -Iassets -Iassets/fonts \
    $(pkg-config --cflags sdl2) "$A/harness/harness_slots_fix.c" \
    src/platform/linux/text_linux.c assets/sfx_res.c assets/fonts/text_data.c \
    -o "$A/harness/harness_slots_fix" $(pkg-config --libs sdl2) -lm
SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=raw.raw "$A/harness/harness_slots_fix" 2 0 5600 pcm
python3 "$A/harness/analyze_slots.py"
```

**Alcance:** no se modificó ningún otro fichero del proyecto ni del SO; no se
sobrescribieron originales de `Res/`; el único cambio de código es
`src/platform/linux/platform_linux.c` (+397/−112 líneas en el diff).
