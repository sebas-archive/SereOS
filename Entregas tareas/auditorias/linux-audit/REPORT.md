# AUDITORÍA A2 — Audio real de PAC-MAN SereOS en Linux/SDL2 (CachyOS)

- **Tarea:** `task-2` — Fase de AUDITORÍA (solo lectura de fuentes; compilación en `build/`
  y arneses propios permitidos).
- **Autor:** `linux-audit` (especialista de plataforma Linux).
- **Fecha:** 2026-11-20.
- **Proyecto auditado:** `/home/t1an/Descargas/sereos02/Pac-man SereOS`
  (rama Linux/SDL2; núcleo compartido con SereOS).
- **Host:** CachyOS, kernel 7.3.3-1-cachyos, KDE Plasma/Wayland, PipeWire 1.6.11
  (compatibilidad PulseAudio 15.0.0), SDL2 **2.32.74**, ffmpeg/Python3+numpy disponibles.
- **Binario auditado:** `build/pacman-sereos` recompilado con `make -B linux`
  (SHA-256 `23ea9d03eb310ad2925f4efe64dd3df84751587d62f459538b98c204ecd90e3e`).
- **Evidencias (todas en el workspace):** `audit/linux-audit/evidence/`
  (raw S16LE 44100 estéreo, WAV escuchables, logs, CSV), arneses en
  `audit/linux-audit/harness/`.
- **Restricción del entorno:** en esta sesión el `/tmp` de **bash es un tmpfs efímero
  por invocación** (no persiste y el Lead no lo ve). Por directriz del Lead, todos los
  entregables están en `audit/linux-audit/`, no en `/tmp`.

---

## 0. Veredicto en 10 líneas

1. **El contexto de partida era incorrecto en un punto central:** la build Linux **SÍ
   usa el PCM de `sfx_res.c`**. `platform_linux.c` abre un segundo dispositivo SDL en
   cola (`AUDIO_U8` mono 11025) y reproduce los WAV embebidos (`platform_linux.c:252-296`,
   `:342-372`). La onda cuadrada es solo *fallback* para los 5 slots sin WAV y para
   cuando no se puede abrir el dispositivo PCM. Prueba: `nm build/pacman-sereos` muestra
   **19 símbolos `pacasset_pcm_*`** y `pacasset_sfx_res` (log `nm_sfx_res.log`).
2. **10 de 15 slots tienen WAV** (2,3,4,6,7,8,9,12,13,15). Suenan, con duración y
   energía correctas (pico ≈ −0,5…−0,8 dBFS, sin clipping).
3. **5 slots son síntesis** (1 MENU, 5 POWER, 10 LEVEL_CLEAR, 11 GAME_OVER,
   14 SIREN_FRIGHT). Todos suenan **~20 dB más bajos** que los WAV y con la frecuencia
   **÷2,97** respecto a la tabla (`f = 22050·f_nominal/65536`): GAME_OVER cae a **55 Hz**
   (subsónico) y SIREN_FRIGHT a **148/221 Hz**.
4. **2 slots están AUSENTES en runtime:** MENU(1) no tiene ningún punto de llamada
   (`PAC_SFX_MENU` solo aparece en el header) y GHOST_RESPAWN(15) tiene WAV pero
   `pac_emit_event` no lo mapea (`game.c:275-313`, default) aunque se emite en
   `game_entities.c:375,384` (medido: 0 reproducciones).
5. **Game Start suena UNA sola vez** (1 reproducción en 6,2 s, y 1 con 3 pausas/reanudaciones),
   dura **4,229 s reales** (= 4,234 s del recurso), sin distorsión ni corte final. Pero el
   `hold` es **4500 ms > 4234 ms** → **266 ms de silencio** antes de que vuelva la sirena.
6. **Defecto grave de mezcla:** hay **una sola cola PCM** y cada `pac_audio_play` hace
   `SDL_ClearQueuedAudio` (`platform_linux.c:278`): los one-shot **se cortan entre sí**.
   Medido: EAT_GHOST reprodujo 24 ms de 574 ms (96 % perdido) al dispararse EAT_FRUIT 31 ms
   después.
7. **Defecto grave de hold:** los `hold` de `game_audio.c:21-36` son más cortos que los WAV,
   así que **la reanudación de la sirena trunca** EAT_GHOST (300/574 ms), EAT_FRUIT
   (250/440 ms, medido `ClearQueuedAudio` con 2022 B ≈ 183 ms), EXTRA_LIFE (900/1899 ms) y
   WAKA (70/84,5 ms).
8. **Defecto grave de sirena FRIGHT:** SIREN_FRIGHT(14) no tiene WAV y usa síntesis, pero
   `pac_audio_loop` **no detiene la cola PCM** al cambiar a un slot sintetizado
   (`platform_linux.c:390-404`). Medido en la traza: tras `set_siren(12→14)` la cola PCM
   sigue reencolándose (`QueueAudio len=1470`, queued 629→2099) → **la sirena de persecución
   sigue sonando debajo del “fright”**. POWER (hold 0) también se solapa con la sirena.
9. **Mapeo semántico de sirenas invertido** respecto a la referencia: `hunted siren.wav`
   (slot 13, “asustado” según `docs/AUDIT_RESOURCES.md:126`) se usa en juego normal
   temprano, y el modo asustado (slot 14) no tiene WAV. Las 8 variantes de pitch
   +10/+20/+30 % están en el binario pero **nunca se usan**.
10. **Colas y cierre correctos:** bucle de sirena 10 s con cola acotada (máx 2203 B,
    media 1466 B, sin crecimiento), `ClearQueuedAudio` en stop/pausa de sirena y cierre de
    los **dos** dispositivos en `pac_platform_shutdown` (`platform_linux.c:497-523`).
    Si el dispositivo no abre, el juego sigue en silencio; si `SDL_Init(AUDIO)` falla, el
    juego **no arranca** (`platform_linux.c:447`).

---

## 1. Cadena de audio real en Linux

```
src/core/game.c          pac_sound_play()/pac_sound_set_siren()   (game.c:283,289,294,297,300,305,308 y :333,338,390)
        │
        ▼
src/core/game_audio.c    hold/estricto·sirena → pac_audio_play/loop/stop_loop (game_audio.c:38-78)
        │
        ▼
src/platform/linux/platform_linux.c
   ├── g_audio_dev  : callback de síntesis, S16SYS mono 22050 Hz (platform_linux.c:298-323, :325-341)
   └── g_pcm_dev    : cola de PCM de sfx_res, U8 mono 11025 Hz (platform_linux.c:342-357)
        │
        ├── si slot tiene WAV  → pcm_start(): SDL_ClearQueuedAudio + SDL_QueueAudio chunks (:252-296, :364-404)
        └── si no (o falló g_pcm_dev) → síntesis cuadrada en g_audio_dev
        ▼
assets/sfx_res.c  PCM u8 mono 11025 (10 clips + 8 variantes de sirena + tablas; sfx_res.c:6427-6506)
```

**Inclusión en build (verificada):**
- `Makefile:27-29` incluye `$(wildcard assets/*.c)` en `LINUX_SRCS` → `assets/sfx_res.c`
  entra en el binario (log `evidence/logs/make_linux_clean.log`).
- `nm build/pacman-sereos`: 19 símbolos `pacasset_pcm_*` (10 clips usados, `game_start`
  troceado en 2, + 8 variantes de sirena) y `pacasset_sfx_res` (log `nm_sfx_res.log`).
- El binario Linux **sí referencia `sfx_res.h`** (`platform_linux.c:21`) y **reproduce
  esos datos** en runtime (capturas de la sección 3).

> **Conclusión del punto dudoso del encargo:** *“¿el recurso WAV embebido se referencia
> desde la build Linux?”* → **SÍ, se referencia, se carga y se reproduce**. Lo que no se
> usa es el *troceado SB16* (se encolan los chunks con `SDL_QueueAudio` de golpe, válido en
> Linux). No es cierto que Linux use “solo síntesis de onda cuadrada”.

---

## 2. Metodología y comandos reproducibles

### 2.1 Compilación limpia

```bash
cd "/home/t1an/Descargas/sereos02/Pac-man SereOS"
make -B linux            # -> build/pacman-sereos (log en audit/linux-audit/evidence/logs/make_linux_clean.log)
sha256sum build/pacman-sereos
```

### 2.2 Arnés A — captura PCM por slot (`harness/harness_slots.c`)

Incluye `platform_linux.c` **sin modificarlo** (misma unidad de traducción) para poder
dejar abierto solo el dispositivo que se captura. Motivo: el driver `disk` de SDL abre un
fichero por dispositivo y, con los **dos** dispositivos del juego, el contenido se
corrompe (demostrado en §7.2). Las ramas internas de decisión son idénticas a las del juego.

```bash
P="/home/t1an/Descargas/sereos02/Pac-man SereOS"
S="audit/linux-audit"
gcc -O2 -g -std=gnu99 -I"$P/include" -I"$P/src/core" -I"$P/src/render" \
    -I"$P/src/platform/linux" -I"$P/assets" -I"$P/assets/fonts" \
    $(pkg-config --cflags sdl2) harness/harness_slots.c \
    "$P/src/platform/linux/text_linux.c" "$P/assets/sfx_res.c" "$P/assets/fonts/text_data.c" \
    -o harness_slots $(pkg-config --libs sdl2) -lm

# WAV (dispositivo PCM; el driver disk escribe S16LE 44100 estéreo tras conversión SDL):
SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=evidence/raw/2_start_pcm.raw \
    ./harness_slots 2 0 5600 pcm
# Síntesis (dispositivo de callback):
SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=evidence/raw/11_game_over_synth.raw \
    ./harness_slots 11 0 1200 synth
# Bucle de sirena 10 s (estudio de cola):
SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=evidence/raw/12_siren_chase_pcm_loop10s.raw \
    ./harness_slots 12 1 10000 pcm
```

Los `.raw` se convierten a WAV escuchable (ffmpeg) y se analizan con
`harness/analyze_slots.py` (numpy: duración activa, pico/RMS dBFS, FFT dominante,
huecos, clipping). Resultado completo: `evidence/analysis_slots.csv`.
Todas las capturas son **audio real emitido por SDL** (no una simulación del código).

### 2.3 Arnés B — traza de la cadena del juego (`harness/harness_flow.c`)

Se enlaza contra los `.o` de `make linux` (sin `main.o`) usando `ld --wrap` para
interceptar, **solo en el arnés**, `pac_audio_*`, `pac_sound_*` y
`SDL_OpenAudioDevice/QueueAudio/ClearQueuedAudio/CloseAudioDevice`. No se modifica
ninguna fuente del proyecto. Muestra el orden exacto de llamadas, `hold`, `siren`, estado
y bytes en cola (`SDL_GetQueuedAudioSize`).

```bash
P="/home/t1an/Descargas/sereos02/Pac-man SereOS"
mapfile -d '' OBJS < <(find "$P/build/linux/obj" -name '*.o' ! -name 'main.o' -print0 | sort -z)
gcc -O2 -g -std=gnu99 -w -I"$P/include" -I"$P/src/core" -I"$P/src/render" \
    -I"$P/src/platform/linux" -I"$P/assets" -I"$P/assets/fonts" \
    $(pkg-config --cflags sdl2) harness/harness_flow.c "${OBJS[@]}" \
    -Wl,--wrap=SDL_GetTicks -Wl,--wrap=SDL_GetQueuedAudioSize \
    -Wl,--wrap=SDL_OpenAudioDevice -Wl,--wrap=SDL_QueueAudio \
    -Wl,--wrap=SDL_ClearQueuedAudio -Wl,--wrap=SDL_CloseAudioDevice \
    -Wl,--wrap=pac_audio_play -Wl,--wrap=pac_audio_loop \
    -Wl,--wrap=pac_audio_stop_loop -Wl,--wrap=pac_audio_stop \
    -Wl,--wrap=pac_sound_play -Wl,--wrap=pac_sound_set_siren -Wl,--wrap=pac_sound_stop \
    -o harness_flow $(pkg-config --libs sdl2) -lm

for sc in start pausecycle siren oneshot death holdcut respawn; do
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./harness_flow $sc \
      > evidence/logs/flow_$sc.log 2>&1
done
```

### 2.4 Comprobaciones de host y binario real

```bash
# Binario real, escena Game Start, captura con driver disk (demuestra limitación de 2 dispositivos):
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=evidence/raw/real_gamestart.raw \
  "$P/build/pacman-sereos" --smoke 400 --scene gamestart

# Driver real del host (PipeWire):
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=pipewire "$P/build/pacman-sereos" --smoke 200 --scene gamestart

# Fallo del subsistema de audio:
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=no_such_driver "$P/build/pacman-sereos" --smoke 5 --scene menu

# Sonido desactivado en Ajustes (fichero de persistencia):
mkdir -p tmp/xdg/pacman-sereos && printf 0 > tmp/xdg/pacman-sereos/sound.txt
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=evidence/raw/real_soundoff.raw \
  XDG_DATA_HOME=tmp/xdg "$P/build/pacman-sereos" --smoke 200 --scene gamestart
```

---

## 3. Tabla por slot: ¿suena? ¿WAV o síntesis? ¿qué se midió?

CAPTURAS: `evidence/raw/*.raw` (S16LE 44100 estéreo, salida real de SDL).
`active` = duración con señal; `peak/rms` dBFS; `freq` = FFT dominante.

| Slot | Nombre | Fuente | ¿Suena? | `active` | pico | RMS | `freq` real | Estado |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | MENU | síntesis (sin WAV) | **no en el juego** (nunca se llama) | 0,255 s* | −21,6 | −23,5 | 220,7 Hz* | **AUSENTE** (sin punto de llamada) |
| 2 | START (Game Start) | **WAV** (2 chunks) | sí, 1 vez | 4,229 s | −0,78 | −11,64 | melodía 199–1133 Hz | **COMPLETO** (con 266 ms de silencio tras el hold) |
| 3 | WAKA1 | **WAV** | sí | 0,0829 s | −0,78 | −5,28 | 850,6 Hz | **PARCIAL** (recorte 14,5 ms por reanudar sirena) |
| 4 | WAKA2 | **WAV** | sí | 0,0830 s | −0,78 | −6,18 | 602,9 Hz | **PARCIAL** (idem) |
| 5 | POWER | síntesis | sí | 0,186 s | −21,3 | −23,5 | 403,7 Hz (nominal 1200) | **PARCIAL/ERROR**: pitch ÷2,97, −18 dB, hold 0 → se solapa con sirena |
| 6 | EAT_GHOST | **WAV** | sí, cortado | 0,569 s | −0,64 | −8,38 | 366–1144 Hz | **PARCIAL**: siren a 300 ms (52 %), y cualquier otro SFX lo borra |
| 7 | EAT_FRUIT | **WAV** | sí, cortado | 0,435 s | −0,72 | −8,16 | 208,6 Hz | **PARCIAL**: siren a 250 ms (57 %); medido clear de 2022 B |
| 8 | DEATH | **WAV** | sí | 1,534 s | −0,51 | −10,67 | 390–751 Hz | **COMPLETO** (hold 2000 > 1534; death_ms bloquea sirena) |
| 9 | EXTRA_LIFE | **WAV** | sí, cortado | 1,899 s | −0,47 | −10,14 | ~374 Hz | **PARCIAL**: siren a 900 ms (47 %) |
| 10 | LEVEL_CLEAR | síntesis | sí | 0,488 s | −21,6 | −23,5 | 592,2 Hz (nominal 1760) | **ERROR**: pitch y −18 dB; 1050 ms de silencio tras 450 ms |
| 11 | GAME_OVER | síntesis | sí (casi inaudible) | 0,650 s | −21,6 | −23,5 | **55,2 Hz** (nominal 165) | **ERROR**: subsónico |
| 12 | SIREN_CHASE | **WAV loop** | sí, continuo | 2,078 s (10 s sin cortes) | −0,78 | −10,36 | 845–1650 Hz | **PARCIAL**: bucle correcto; variantes de pitch sin uso; lo corta cada dot |
| 13 | SIREN_HUNT | **WAV loop** | sí, continuo | 2,090 s | −0,78 | −5,72 | 396–851 Hz | **PARCIAL**: bucle correcto, pero es el WAV de “asustado” usado en juego normal |
| 14 | SIREN_FRIGHT | síntesis (sin WAV) | sí (débil) | 2,090 s | −21,6 | −23,5 | 148 / 221 Hz alternos | **ERROR**: pitch, volumen y **solape con la sirena WAV previa** |
| 15 | GHOST_RESPAWN | **WAV** (existe) | **no** (evento no mapeado) | 0,266 s† / loop continuo† | −0,66 | −5,11 | 2180–2322 Hz | **AUSENTE** (0 reproducciones; evidencia `flow_respawn.log`) |

\* slot 1 capturado forzando `pac_audio_play(1)` en el arnés (no ocurre en el juego).
† slot 15 capturado forzando la llamada en el arnés: one-shot 266 ms / bucle continuo;
el juego **nunca lo dispara** porque `pac_emit_event(GHOST_RESPAWN)` cae en `default`.
“Música de fondo”: **no existe** en esta build (no hay pista de música; `intermission.wav`
no se incluye por diseño).

---

## 4. `game start`: ¿una sola vez? duración real, corte final y silencio

**Flujo** (`game.c:374-393`): menú → `pac_start_new_game()` → `pac_sound_set_siren(NONE)`
→ `pac_sound_play(PAC_SFX_START)` → `g->audio_hold_ms = 4500`.
`pac_sound_play` ve `effect_hold_ms(START)=4500`, para la sirena y llama a
`pac_audio_play(2)`; como el slot 2 tiene WAV, se encolan sus dos chunks
(`platform_linux.c:252-296`, `sfx_res.c:6454-6465`: 32768 + 13908 = 46676 muestras).

**Traza real** (`evidence/logs/flow_start.log`):

```
[    99] SOURCE pac_sound_play(slot=2) state=PLAYING hold=0 siren=0 audio_ok=1
[    99] pac_audio_stop_loop()  pcm_queued=0
[    99] pac_audio_play(2)  pcm_queued=0
[    99]   SDL_QueueAudio dev=3 len=32768 queued_before=0   queued_after=32768  <== PCM
[    99]   SDL_QueueAudio dev=3 len=13908 queued_before=32761 queued_after=46669 <== PCM
[    99]   => hold=4500 siren=0
[   167] STATE tras-start ... hold=4436 ready=4436 pcm_queued=45901
[  4171] STATE t+ ... hold=436 pcm_queued=0          ← el WAV ya se agotó
[  4612] pac_audio_loop(13) siren=13 ...             ← reanuda la sirena (hold 4500 agotado)
[  6172] SUMMARY start_plays=1 loop_hunt=8 ...
```

- **Una sola reproducción** en 6,17 s de partida: `start_plays=1` (y `loop_hunt=8`, la
  sirena reanudada). En `flow_pausecycle.log` (3 pausas/reanudaciones) también
  `start_plays=1`: pausar no re-dispara el Game Start.
- **Duración real:** 4,229 s de señal activa vs **4,234 s** del recurso
  (46676/11025 = 4,2337 s); la diferencia es el redondeo del umbral de silencio.
- **Sin distorsión ni corte final:** pico −0,78 dBFS, **0 muestras recortadas**
  (clipping = 0), cola de 20 ms con RMS 771 (frente a pico 29952) y delta máximo
  entre muestras 4507 (sin click); canales L/R idénticos (diferencia media 0,0).
  El recurso termina naturalmente y el `hold` es más largo que el WAV, así que **no lo
  trunca**.
- **Defecto asociado:** `hold=4500 ms` > `WAV=4234 ms` → **~266 ms de silencio** antes de
  que la sirena vuelva (teórico 266 ms; en la traza el hueco entre cola vacía 4171 ms y
  sirena 4612 ms es mayor porque incluye la latencia del dispositivo/disco ~100–160 ms).
- **Defecto de pausa:** durante una pausa el Game Start **sigue sonando** (ver §6).

---

## 5. Sirenas: bucle, solape, reanudación y parada

**Lógica:** `update_siren()` (`game.c:426-440`) elige HUNT si
`dots_left+power_left>50`, CHASE si ≤50, FRIGHT si `fright_ms>0`; se bloquea si
`state!=PLAYING || ready_ms>0 || death_ms>0 || audio_hold_ms>0`.
`pac_sound_set_siren` solo actúa si cambia el slot (`game_audio.c:55-68`).

**Bucle WAV correcto y cola acotada** (`evidence/logs/slots/12_siren_chase_loop10s.log`):
10 s de `pac_audio_loop(12)` con `pac_audio_update()` periódico → **sin huecos**
(active = 10 s), cola máx. **2203 B** (≈200 ms), media 1466 B, sin crecimiento
(el reencolado ocurre al bajar de `total/2`, `platform_linux.c:422-432`).
SIREN_HUNT igual (buffers de 4412 B, continua).

**Arranque/parada por estado (verificado):**
- Pausa con sirena sonando → `pac_audio_stop_loop` + `SDLK_ClearQueuedAudio`,
  cola 1393→0 (`flow_siren.log` t=1709) y `siren=0`. **Correcto**.
- Muerte → `pac_sound_set_siren(NONE)` y `hold=2000`; `death_ms>0` impide la sirena.
- Menú/Game Over/Level Clear → `pac_sound_set_siren(NONE)` (`game.c:326-346`).
- Reanudación tras one-shot → `hold` agota y `update_siren` relanza el bucle
  (`flow_start.log` t=4612). **Correcto**, pero ver truncamientos (§6) y solape (§5.2).

### 5.1 Defecto: cambio a FRIGHT **no detiene** el bucle PCM (solape real)
`pac_audio_loop` toma la rama de síntesis para el slot 14 y **no llama a `pcm_stop`**
(`platform_linux.c:390-404`). Traza (`flow_siren.log`):

```
[  1223] pac_audio_loop(14)  pcm_queued=1013
[  1223] SOURCE pac_sound_set_siren(12->14) state=PLAYING hold=0 fright=5984
[  1256]   SDL_QueueAudio dev=3 len=1470 queued_before=629 queued_after=2099 <== PCM
[  1309] STATE power ... siren=14 pcm_queued=1587
```

Es decir: **la sirena de persecución (WAV) sigue reproduciéndose y reencolándose** mientras
suena el “fright” sintetizado. En el mismo punto, POWER (`pac_sound_play(5)`, `hold=0` porque
`effect_hold_ms(POWER)` no está definido, `game_audio.c:21-36`) se añade **sin** parar la
sirena (`game.c:610` → `pac_sound_play` no entra en la rama `hold>0`): 3 sonidos a la vez
(sirena WAV + beep POWER + beep FRIGHT).

### 5.2 Defecto: cada dot interrumpe la sirena (ping-pong WAKA↔sirena)
Cada `EAT_DOT` (`game.c:283`) llama `pac_sound_play(WAKA)` con `hold=70`; al haber hold,
`game_audio.c:44-52` hace `pac_audio_stop_loop()` → **borra la sirena entera**
(`ClearQueuedAudio`), pone un WAKA de 84,5 ms y a los 70 ms la sirena **reinicia desde el
principio** (`flow_start.log` t=4819/4900/5028). Efectos: la sirena “tartamudea” en cada
dot y el WAKA pierde sus últimos ~14,5 ms (medido: `ClearQueuedAudio` con 26–29 B aún en
cola). En el arcade original ambos sonidos se solapan; aquí compiten por la misma cola.

### 5.3 Defecto: modulación de sirena no implementada + mapeo invertido
- `sfx_res.c` incluye 4 variantes de pitch (+0/+10/+20/+30 %) por sirena
  (`sfx_res.c:6481-6496`), presentes en el binario (nm) pero **ningún `src/` las referencia**.
  La sirena solo cambia por el umbral `≤50` de dots (`game.c:436-439`); no hay progresión.
- Según la referencia (`docs/AUDIT_RESOURCES.md:126`): *HunterSiren* = persecución normal,
  *HuntedSiren* = **modo asustado**. Aquí el WAV de *hunted* es el slot 13 (SIREN_HUNT) y se
  usa en juego normal temprano; el modo asustado (slot 14) no tiene WAV. El recurso adecuado
  para FRIGHT existe, pero está mal asignado.

---

## 6. Truncamientos por `hold` y cola PCM única (defectos de reproducción)

`effect_hold_ms` (`game_audio.c:21-36`): START 4500, DEATH 2000, GAME_OVER 1200,
LEVEL_CLEAR 1500, EXTRA_LIFE 900, GHOST_RESPAWN 600, EAT_GHOST 300, EAT_FRUIT 250,
WAKA 70; resto 0. Comparado con las duraciones de `sfx_res`:

| Slot | WAV | hold | ¿se corta? | Pérdida |
|---|---:|---:|---|---:|
| 2 START | 4234 ms | 4500 | no (holgura) | 0 (pero +266 ms silencio) |
| 3/4 WAKA | 84,5 ms | 70 | sí (cola 26–29 B) | ~14,5 ms (justo al reanudar sirena) |
| 6 EAT_GHOST | 574 ms | 300 | **sí** | **274 ms (52 %)** |
| 7 EAT_FRUIT | 440 ms | 250 | **sí** (medido) | **~190 ms (43 %)** |
| 8 DEATH | 1534 ms | 2000 | no | 0 |
| 9 EXTRA_LIFE | 1899 ms | 900 | **sí** | **999 ms (53 %)** |
| 10 LEVEL_CLEAR | 450 ms (synth) | 1500 | no | 0 (1050 ms silencio) |
| 11 GAME_OVER | 600 ms (synth) | 1200 | no | 0 (600 ms silencio) |

**Prueba empírica del corte de EAT_FRUIT** (`evidence/logs/flow_holdcut.log`):

```
[  2207] SOURCE pac_sound_play(slot=7) ... hold=0 siren=13
[  2207] pac_audio_play(7) ... QueueAudio len=4845  <== PCM
[  2453] pac_audio_loop(13)  pcm_queued=2022          ← hold 250 ms agotado
[  2453]   SDL_ClearQueuedAudio dev=3 queued_before=2022  <== PCM   ← 183 ms de WAV tirados
```

**Cola PCM única ⇒ los one-shot se borran entre sí** (`platform_linux.c:278`):
`flow_oneshot.log`:

```
[   142] pac_audio_play(6) ... QueueAudio len=6324     (<- EAT_GHOST, 574 ms)
[   173] pac_audio_play(7) ... SDL_ClearQueuedAudio queued_before=6061  (<- 31 ms después)
```

Solo se reprodujeron 263 B de 6324 (24 ms de 574 ms → **96 % perdido**). No hay mezcla de
efectos one-shot; el último gana siempre.

---

## 7. Buffers, colas, liberación y cierre

1. **Sin crecimiento de cola:** bucle de sirena 10 s → máx 2203 B, media 1466 B, final 1051 B
   (`12_siren_chase_loop10s.log`). Reencolado acotado (`< total/2`).
2. **Limpieza explícita:** `pac_audio_stop_loop/stop` → `pcm_stop()` →
   `SDL_ClearQueuedAudio` (`platform_linux.c:290-296`); visto en pausa de sirena
   (1393→0) y al destruir el juego (`flow_pausecycle.log` t=1861: clear 26317→0).
3. **Cierre en exit:** `pac_platform_shutdown` cierra **ambos** dispositivos y llama a
   `SDL_Quit` (`platform_linux.c:497-523`); visto: `SDL_CloseAudioDevice dev=2` y `dev=3`
   en todos los `flow_*.log`.
4. **`g_pcm_dev`/`g_audio_dev`** se ponen a 0 tras cerrar; `g_pcm_active` a 0 al agotarse la
   cola (`platform_linux.c:429-431` y `:504-509`).
5. **Fugas de memoria:** **NO VERIFICADO** — `valgrind` no está instalado en el host. No se
   observa crecimiento de cola ni recursos SDL sin cerrar en las trazas; el `continue_snapshot`
   del core no es de audio.
6. **Variables muertas:** `g_pcm_len` y `g_pcm_chunk` (declaradas en `platform_linux.c:49,51`
   y asignadas en `:280-282`) no se usan después; `g_pcm_chunk` sí se usa en la versión SereOS,
   aquí quedó residual. No afecta a la reproducción.

---

## 8. UI/estado que silencia el audio (correcto)

- **Ajustes → Sonido OFF:** `pac_settings_apply` (`game.c:186-197`) pone `audio_ok=0` y
  `pac_audio_stop()`. Prueba: binario real con `sound.txt=0` → captura
  `evidence/raw/real_soundoff.raw` **100 % silencio** (pico 0, RMS −270 dBFS), juego
  funcionando (`real_soundoff.log`). **Correcto.**
- **Cierre:** `pac_game_destroy` → `pac_sound_stop` antes de `SDL_Quit` (`game.c:788-798`).
- **Ventana sin foco/minimizada:** `pac_game_tick` no avanza el juego (`game.c:822-831`) pero
  `main.c:202` sigue llamando `pac_audio_update()`; no se detiene la música/sirena al perder
  el foco. Menor: no hay mute por foco.
- **Pausa con one-shot en curso:** `pac_set_state(PAUSED)` llama `pac_sound_set_siren(NONE)`,
  pero si `g->siren` ya es `NONE` la función retorna sin parar nada (`game_audio.c:59-60`).
  Resultado medido (`flow_pausecycle.log`): pausa en t=247 con Game Start sonando,
  `pcm_queued=44877` y **la cola sigue drenándose durante la pausa** (41677→38349→…);
  el audio del Game Start **no se pausa**. Además `audio_hold_ms` se decrementa en pausa
  (`game.c:698-702`, `game_tick` corre en todos los estados) mientras `ready_ms` no: los
  temporizadores de audio no son coherentes con la pausa.

---

## 9. Limitaciones del host CachyOS / SDL2 (verificado)

- **SDL2 2.32.74**; drivers de audio: `pipewire pulseaudio alsa sndio jack disk dummy`
  (`evidence/logs/sdl_probe.log`); driver por defecto **pipewire**.
- Salida por defecto: **“Built-in Audio Analog Stereo”** (PipeWire 1.6.11 vía PulseAudio
  15.0.0); especificación por defecto **float32le 2ch 48000 Hz**
  (`evidence/logs/sdl_devices.log`). SDL convierte desde los formatos de la app.
- **Ambos dispositivos abren con el formato exacto pedido** en este host:
  `g_audio_on=1`, `g_pcm_on=1` con los drivers `pipewire`, `pulseaudio` **y** `disk`
  (`pipewire_pcm_open.log`, `pulse_pcm_open.log`). Si un host no concede
  `U8/mono/11025` exacto, el código **cierra `g_pcm_dev`** (`platform_linux.c:350-357`) y
  los 10 slots WAV caen al beep sintetizado (degradación silenciosa, no avisa).
- **Dos streams simultáneos** (síntesis 22050 S16 y PCM 11025 U8) mezclados por PipeWire:
  funcional, pero añade latencia y no hay control de volumen maestro ni selección de
  dispositivo (SDL usa el defecto).
- **Latencia observada:** con `SDL_AUDIODRIVER=disk`, la cola tarda ~100–160 ms en reflejar
  el audio emitido (el `queued` drena a ~11025 B/s); el bucle de sirena mantiene 100–200 ms
  en cola. No hay `SDL_AUDIO_ALLOW_*` en el dispositivo de síntesis (bloqueo duro si el
  host no acepta 22050 S16 mono; SDL suele convertir, pero no hay fallback propio).
- **Sin audio / audio roto:**
  - Si el dispositivo no abre (`OpenAudioDevice` devuelve 0; p.ej. ruta de fichero
    inválida con driver disk): `pac_audio_available()=0`, el juego **arranca y corre en
    silencio** (`real_no_device.log`: `GAME_START` y exit 0; arnés: `available=0`).
  - Si `SDL_Init(SDL_INIT_VIDEO|AUDIO|EVENTS)` falla (driver de audio inexistente, servidor
    de audio caído): el juego **no arranca**, `exit 1` (`real_badaudio.log`:
    `SDL_Init: Audio target 'no_such_driver' not available`). `pac_platform_init`:
    `platform_linux.c:447-450` aborta también el vídeo por un fallo de audio.
- **Captura QA con driver `disk`:** el juego abre **2 dispositivos** que escriben en el
  **mismo** `SDL_DISKAUDIOFILE`; el fichero resultante mezcla/duplica ambos flujos
  (`real_gamestart.raw`: **19,18 s** de audio para una ejecución de ~13 s, energía
  −5,7 dBFS sostenida). **No es una captura fiable** para auditar por slot: por eso se usó
  el arnés A con un solo dispositivo activo. Limitación relevante para futuros QA.
- `SDL_Quit` se llama en shutdown; no quedan dispositivos abiertos entre ejecuciones.

---

## 10. Lista priorizada de defectos (para la fase de corrección Linux)

**P0 — roturas funcionales de audio**
1. `platform_linux.c:390-404` (rama síntesis de `pac_audio_loop`): no detener la cola PCM
   al cambiar a un slot sin WAV ⇒ sirena WAV sigue sonando bajo FRIGHT. Añadir
   `pcm_stop()` (o condición de parada) cuando el nuevo bucle no sea PCM.
2. `game_audio.c:21-36` + `game.c:390-391`: `hold` > o < duración real. Ajustar holds a la
   duración de cada WAV (ghost 574, fruit 440, extra life 1899, waka 85, start 4234) o,
   mejor, terminar el hold cuando la cola PCM del one-shot se vacíe.
3. `platform_linux.c:364-372` + `:278`: cola PCM única ⇒ one-shot se borran entre sí
   (EAT_GHOST pierde el 96 % al sonar EAT_FRUIT). Necesita cola/mezclador de efectos
   (o al menos no limpiar si el sonido en curso es un one-shot largo y el nuevo es corto).
4. `game.c:275-313`: `PAC_GAME_EVENT_GHOST_RESPAWN` sin caso de audio ⇒ slot 15 (WAV)
   nunca suena (`game_entities.c:375,384`).
5. `game.c:434-440` vs `sfx_res.h`/`docs/AUDIT_RESOURCES.md:126`: FRIGHT debe usar el
   recurso de sirena “asustado”; reasignar slot 13/14 y/o rellenar 14 con WAV.

**P1 — calidad/sonoridad**
6. `platform_linux.c:313-321`: síntesis con frecuencia ÷2,97 (`f=22050·f_nom/65536`) y
   amplitud 2200 (~−21,6 dBFS pico, ~20 dB por debajo de los WAV). Corregir incremento de
   fase (`f_nom` → `f·65536/rate`) y normalizar amplitud; GAME_OVER a 55 Hz es inaudible.
7. `game.c:283` + `game_audio.c:44-52`: cada dot corta y reinicia la sirena (tartamudeo)
   y recorta el final del WAKA 14,5 ms. Mezclar WAKA sobre la sirena o no reiniciar la
   sirena en cada dot.
8. Variantes de pitch de sirena (+10/+20/+30 %) presentes y no usadas; implementar
   progresión por dots restantes (`sfx_res.c:6481-6496`, `pacasset_siren_*`).
9. `platform_linux.c:344-357`: si el host no da U8/11025 exacto, se pierden los 10 WAV y
   se sustituyen por beeps sin aviso. Usar `SDL_AUDIO_ALLOW_FREQUENCY_CHANGE` y/o
   `SDL_ConvertAudio`, y loguear la degradación.
10. `game.c:326-329` + `game_audio.c:59-60`: la pausa no detiene un one-shot WAV en curso
    (Game Start suena durante la pausa); hacer `pac_audio_stop()` en PAUSED/MENU y congelar
    `audio_hold_ms` durante la pausa.

**P2 — robustez/limpieza**
11. `platform_linux.c:447`: separar `SDL_Init` de vídeo y audio para que un fallo de audio
    no impida arrancar el juego (degradar a silencio).
12. `PAC_SFX_MENU` sin punto de llamada (slot 1 muerto): decidir si se implementa sonido de
    menú o se elimina el slot.
13. `platform_linux.c:49,51,280-282`: eliminar `g_pcm_len`/`g_pcm_chunk` muertos.
14. `main.c:202`: no actualizar audio si la ventana no tiene foco (evita sonido “fantasma”).
15. QA: documentar que `SDL_AUDIODRIVER=disk` con el binario real no sirve por los 2
    dispositivos; usar arnés de un solo dispositivo.

---

## 11. Inventario de evidencias

```
audit/linux-audit/
├── REPORT.md                         (este documento)
├── harness/
│   ├── harness_slots.c               (captura por slot, incluye platform_linux.c sin editar)
│   ├── harness_flow.c                (traza game→game_audio→pac_audio→SDL con ld --wrap)
│   ├── analyze_slots.py              (análisis numpy de los raw)
│   ├── probe_sdl.c / probe_dev.c     (drivers y dispositivos del host)
│   └── (binarios compilados)
└── evidence/
    ├── analysis_slots.csv            (duración/energía/frecuencia/clipping por slot)
    ├── raw/                          (21 capturas .raw S16LE 44100 estéreo, salida real SDL)
    ├── wav/                          (mismas capturas convertidas a .wav escuchables)
    └── logs/
        ├── make_linux_clean.log      (make -B linux, 0 errores)
        ├── nm_sfx_res.log            (19 símbolos pacasset_pcm_* en el binario)
        ├── sdl_probe.log / sdl_devices.log / pipewire_pcm_open.log / pulse_*.log
        ├── flow_start.log            (Game Start 1 vez, 46676 B, hold 4500, sirena t=4612)
        ├── flow_pausecycle.log       (start_plays=1 con 3 pausas; audio sigue en pausa)
        ├── flow_siren.log            (solape FRIGHT/POWER, cortes por dot, pausa)
        ├── flow_oneshot.log          (EAT_GHOST cortado al 4 % por EAT_FRUIT)
        ├── flow_holdcut.log          (ClearQueuedAudio de EAT_FRUIT a los 246 ms)
        ├── flow_death.log            (DEATH completo, GAME_OVER synth)
        ├── flow_respawn.log          (GHOST_RESPAWN: 0 reproducciones)
        ├── real_gamestart.log/.raw   (limitación del driver disk con 2 dispositivos)
        ├── real_pipewire.log         (binario real con PipeWire: OK)
        ├── real_badaudio.log         (SDL_Init falla ⇒ exit 1)
        ├── real_no_device.log        (dispositivo no abre ⇒ silencio, exit 0)
        ├── real_soundoff.log/.raw    (Ajustes Sonido OFF ⇒ silencio total)
        └── slots/*.log               (traza de cola por slot y bucle 10 s)
```

**Reproducción completa:** ejecutar los comandos de §2 en el orden indicado; los `.raw`
se regeneran en `audit/linux-audit/evidence/raw/`, los WAV con:

```bash
for f in evidence/raw/*.raw; do
  ffmpeg -y -loglevel error -f s16le -ar 44100 -ac 2 -i "$f" \
         "evidence/wav/$(basename "$f" .raw).wav"
done
```

**Aviso de alcance:** esta auditoría es de solo lectura. No se modificó ningún fichero de
`src/`, `assets/`, `include/`, `tests/` ni del SO. Solo se compiló en `build/` y se crearon
arneses propios en `audit/linux-audit/`.
