# AUDITORÍA A1 — Inventario e integridad técnica de WAV (PAC-MAN SereOS)

- **Agente:** `wav-integrity` (especialista de audio: formato/calidad)
- **Tarea compartida:** `task-1` — **FASE AUDITORÍA, SOLO LECTURA** (no se modificó el proyecto ni los WAV originales).
- **Fecha:** 2026-11-20.
- **Fuentes de verdad:** `/home/t1an/Descargas/Res` (11 WAV) y `/home/t1an/Descargas/sereos02/Pac-man SereOS/assets/` (`sfx_res.c/.h`, `res_original/`, `tools/gen_pacman_res_assets.py`, `docs/AUDIT_RESOURCES.md`).
- **Referencia de comportamiento:** `/home/t1an/Descargas/Paku-Paku` (VB6; `cGame.cls`, `modSoundFX.bas`).
- **Herramientas:** `python3` del sistema (NumPy 2.5.4), Python bundled del harness (NumPy 2.3.5 + Pillow 12.3), `wave`, `struct`, `hashlib`, `ffprobe`/`ffmpeg` 9.0.2. Evidencias en `/home/t1an/Descargas/sereos02/audit/wav-integrity/`.
- **Nota de honestidad:** este informe es **análisis estático + decodificación numérica**. No se escuchó audio ni se ejecutó el juego en hardware SB16 real; los puntos que dependen de eso se marcan **NO VERIFICADO**.

---

## 1. Inventario recursivo de WAV en `Res/`

`find Res -iname '*.wav'` → **11/11**, sin subdirectorios y **sin WAV extra**. `Res/` contiene 15 PNG, 2 TTF, 11 WAV, 1 `.db`, 1 `.ini`. Los 11 WAV decodifican sin error con `ffmpeg -v error` (11/11 OK). Los MD5 coinciden con los documentados en `docs/AUDIT_RESOURCES.md` §1.1.

| # | Archivo | Bytes | MD5 | SHA-256 |
|---:|---|---:|---|---|
| 1 | `game start.wav` | 420.408 | `07914ee70de9f5f1166ed3e9b35fc9db` | `8f12aa7cf731390cd12c0e803ca56cbf522a4db18bf14f6220b0e23fcced3709` |
| 2 | `waka1.wav` | 16.320 | `9e3c8eb9b4d7af04971b12c9af3e5bb4` | `c48cbd0230ec7cc036f73413239f1f149cc55464843962e71ae5115ad513c315` |
| 3 | `waka2.wav` | 16.256 | `0452cd64893e3fbd3503190e9ff318c7` | `96a948f80681cb0d1b1bc3a1c64ba5bea9822ffdb5df7f9f13772a8f1fe47176` |
| 4 | `eat ghost.wav` | 6.408 | `61d4ded9e6249e64b735982f6ced3ec5` | `888696fafb55e06ff383707eccbba7e8b822412857078d52b4e4cbbc3ce5665f` |
| 5 | `eat fruit.wav` | 5.120 | `514eeeeb192e8ca45ca92aa308f61f63` | `82c96a997ac2e837de4e418f29f4f4fa6142dd2a0c38f764b6d989d8bd98605d` |
| 6 | `extra life.wav` | 21.248 | `27991f5575aec8695f0f9a68925b9df8` | `767db1552130e676398c121ec605f90f20c89bbbab272305bc781adc8e91d1cd` |
| 7 | `ghost respawn.wav` | 52.390 | `43fae1a4447f5026f8f23a9d9dd02b95` | `82b46c4ddbb0e9e8d2430e49123549e456b599c95333ad4adb1f2dc9f0c81b94` |
| 8 | `hunted siren.wav` | 113.494 | `8d5759b619045b5f6879ec83175d67a9` | `7580824f43dc6f670a6841c68330e6d3f120d35695cc3d139ca1c7a40aa7df21` |
| 9 | `hunter siren.wav` | 230.902 | `d35ceeea5823f2ea9c1a3d2107826b92` | `3d03beaa387fd5bb169cac9cef2a556010f42b53a1ef4a9488965c30de7c60d2` |
| 10 | `pacman death.wav` | 17.008 | `b5cacf9a37e6a4fd396f6fd914168780` | `1c3e91df8e19041ea5783185c5a8a9f2321993b43481c215d8caf3df590290de` |
| 11 | `intermission.wav` | 57.600 | `566c0f2299b8a7ebef6372010fa6866e` | `49863198b068a61191173b2a32a23b4a10aa02da29caf625a92b31149e2aae4c` |

**Estado inventario: COMPLETO (11/11).** No hay WAV adicionales en `Res/` (tampoco `.WAV`).

---

## 2. Tabla técnica por archivo

Formato de referencia: PCM (audio_format=1) en todos. `u8` = PCM 8 bits sin signo (silencio=128); `s16` = PCM 16 bits little-endian. Valores medidos sobre el **mono mix** (media de canales; se verificó que los estéreo son dual-mono exactos), salvo pico que se midió sobre todos los canales. Pico/RMS en dBFS (full-scale=1.0). DC en LSB del formato origen. Clipping = muestras al máximo/mínimo del formato. Silencio = umbral −60 dBFS.

| Archivo | Formato | Rate/ch/bits | Muestras | Duración (s) | Bytes | Bitrate (kbps) | Pico dBFS | RMS dBFS | DC (LSB) | Clip | Sil. ini/fin (s) | Cola | Veredicto |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| `game start.wav` | u8 estéreo dual-mono | 48000 / 2 / 8 | 210.165 | 4,378438 | 420.408 | 768,1 | −4,19 | −15,37 | −4,39 | 0 | 0,1327 / 0,0165 | fade-out ~35 ms hasta 0, sin click | **OK con reservas**: 9,0× sobredimensionado |
| `waka1.wav` | s16 estéreo dual-mono | 48000 / 2 / 16 | 4.059 | 0,084562 | 16.320 | 1543,9 | −12,08 | −16,26 | −990 | 0 | 0,0011 / 0,0011 | corte seco a 0 (sin fade, sin click) | OK |
| `waka2.wav` | s16 estéreo dual-mono | 48000 / 2 / 16 | 4.043 | 0,084229 | 16.256 | 1544,0 | −12,08 | −16,23 | −1036 | 0 | 0,0009 / 0,0008 | corte seco a 0 (sin fade, sin click) | OK |
| `eat ghost.wav` | u8 mono | 11025 / 1 / 8 | 6.324 | 0,573605 | 6.408 | 89,4 | −0,21 | −7,82 | +0,42 | 0 | ~0 / 0,0015 | termina en silencio | OK |
| `eat fruit.wav` | u8 mono | 11025 / 1 / 8 | 4.845 | 0,439456 | 5.120 | 93,2 | −0,28 | −7,69 | −0,17 | 0 | 0 / 0,0004 | termina en silencio | OK (padding RIFF) |
| `extra life.wav` | u8 mono | 11025 / 1 / 8 | 20.940 | 1,899320 | 21.248 | 89,5 | −0,56 | −9,91 | −0,66 | 0 | 0 / 0 | decae a 0 en ~1 ms | OK |
| `pacman death.wav` | u8 mono | 11025 / 1 / 8 | 16.916 | 1,534331 | 17.008 | 88,7 | −0,63 | −10,50 | −0,35 | 0 | 0 / 0 | decae a ~0, sin click | OK |
| `intermission.wav` | u8 mono | 11025 / 1 / 8 | 57.377 | 5,204263 | 57.600 | 88,5 | −0,21 | −9,77 | −0,40 | 0 | 0 / 0 | decae a 0, sin click | **OK técnico, NO integrado** |
| `ghost respawn.wav` | u8 estéreo dual-mono | 48000 / 2 / 8 | 26.153 | 0,544854 | 52.390 | 769,2 | −13,84 | −18,01 | −3,17 | 0 | 0 / 0 | bucle 0,2663 s | OK (loop) |
| `hunted siren.wav` | u8 estéreo dual-mono | 48000 / 2 / 8 | 56.705 | 1,181354 | 113.494 | 768,6 | −18,06 | −23,26 | −0,95 | 0 | 0 / 0 | bucle 0,4001 s | OK (loop; seam mejorable) |
| `hunter siren.wav` | u8 estéreo dual-mono | 48000 / 2 / 8 | 115.409 | 2,404354 | 230.902 | 768,3 | −12,60 | −21,88 | −1,59 | 0 | 0 / 0 | bucle 0,1333 s | OK técnico; **asignación semántica errónea** |

Notas de integridad:
- **Ningún archivo tiene clipping** (0 muestras a 0/255 en u8, 0 a −32768/32767 en s16) ni distorsión por saturación.
- **Anchura de banda real muy baja**: el 82,7 % de la energía de `game start` está bajo 1 kHz y el **99,65 % bajo 5,5 kHz** (bandas: 0–1k 82,68 %, 1–4k 16,80 %, 4–5,5k 0,17 %, >5,5k 0,35 %). Lo mismo ocurre en los demás clips de 48 kHz, con distinto grado: `ghost respawn`/`hunted siren` ≥ 99,6 % bajo 5,5 kHz; `waka1`/`waka2` 97,4–97,8 %; `hunter siren` 93,4 % (≈6,6 % entre 5,5–20 kHz). Es decir, el rate 48 kHz aporta muy poco o ningún contenido audible sobre ~5 kHz.
- **Estéreo redundante**: los 6 WAV de 48 kHz son **dual-mono exactos** (`max|L−R| = 0`, correlación 1,0), por lo que el segundo canal no aporta información.
- **Padding anómalo**: `eat fruit.wav` (+186 B), `extra life.wav` (+220 B) e `intermission.wav` (+134 B) tienen bytes cero **después** del tamaño declarado en `RIFF` (el `RIFF size` no cubre el archivo completo). Son ceros, no audio; `ffmpeg` los decodifica sin error. No afecta a la conversión (el generador solo lee el chunk `data`).
- Chunks auxiliares: `LIST/INFO` (`ICRD` 1994-11-30 en `eat fruit`/`intermission`, 1996-02-02 en `extra life`, `ISFT` "Lavf58.2.100" en `game start`, "WHAM 1.31 by Andrew Bulhak" en `pacman death`), `SAUR 1.3.0.0` (32 B) en `eat ghost`, `ghost respawn`, sirenas, waka1/2, `fact` en `extra life`/`eat fruit`/`intermission`. **No hay chunk `smpl`/`cue`** (no hay puntos de bucle nativos).

### 2.1 `game start.wav` en detalle (420.408 B)

- **Por qué es tan grande:** 420.408 B = cabecera 78 B + `data` 420.330 B. El `data` son **210.165 frames × 2 canales × 1 byte = 420.330 B** a **48 kHz estéreo u8**. Es decir, el tamaño no se debe a un error ni a datos corruptos, sino a un formato de origen **48 kHz × 2 canales** (dual-mono exacto) para una locución/música de 4,378 s.
- **Contenido real:** 0,1327 s de silencio inicial + música de 4,2292 s (con micro-pausas de 50–60 ms entre frases) + 0,0165 s de silencio final. El generador recorta el silencio y entrega **46.676 muestras** (4,2337 s) → el archivo original es **9,007× más grande** que el PCM embebido útil.
- **Final:** NO hay corte abrupto ni distorsión. Los últimos ~35 ms son un **fade-out** de −13 dBFS a −37 dBFS y las últimas 793 muestras son 0 exacto; la última muestra activa vale 0,0078 (−42 dBFS) y las 20 últimas muestras son 0. El pico global es −4,19 dBFS y no hay clipping.
- **Troceado SB16:** el PCM final (46.676) se parte en **2 chunks: 32.768 + 13.908** (ambos ≤ 32.768). La concatenación reproduce exactamente el PCM completo y el salto en la frontera es **8 LSB** frente a un p99 de diferencias de 37 LSB (sin click). ✔

---

## 3. Comparación WAV original → PCM embebido (`assets/sfx_res.c`)

**Verificación de bytes:** se parsearon los 19 arrays `const uint8_t[]` de `sfx_res.c` y se regeneró el PCM con las funciones de `tools/gen_pacman_res_assets.py`. Resultado: **los 10 slots y las 8 variantes de sirena son byte-idénticos** al generador (0 diferencias; longitud y contenido). Las tablas (`pacasset_sfx_res`, `loop`, `chunk_count`, `chunks`, `chunk_len`, `total_bytes`, `rate`) son coherentes. Además, re-ejecutar el generador completo en `/tmp/regen` produce `sfx_res.c`/`sfx_res.h` con **MD5 idénticos** a los del proyecto (`f00b14fbed4413daded2310db3988485` / `479ebca8c61fd9809fb642229e4ee8e5`), en 4,9 s. **Generador determinista y reproducible ✔**

Slots declarados: 16. **Con datos: 2,3,4,6,7,8,9,12,13,15.** Vacíos (`data=NULL,len=0`): **1 MENU, 5 POWER, 10 LEVEL_CLEAR, 11 GAME_OVER, 14 SIREN_FRIGHT** (verificado parseando el array).

| Slot | Símbolo | WAV | Muestras PCM | Duración | Chunks | Loop | Ganancia norm. | SNR cuantización | SNR vs fuente | Seam loop |
|---:|---|---|---:|---:|---:|---|---:|---:|---:|---:|
| 2 | START | game start.wav | 46.676 | 4,2337 s | **2** (32768+13908) | no | +3,47 dB | 41,8 dB | 23,2 dB | — |
| 3 | WAKA1 | waka1.wav | 932 | 0,0845 s | 1 | no | +11,35 dB | 47,7 dB | 15,7 dB | — |
| 4 | WAKA2 | waka2.wav | 929 | 0,0843 s | 1 | no | +11,35 dB | 46,7 dB | 16,0 dB | — |
| 6 | EAT_GHOST | eat ghost.wav | 6.324 | 0,5736 s | 1 | no | −0,52 dB | 44,6 dB | 44,7 dB | — |
| 7 | EAT_FRUIT | eat fruit.wav | 4.845 | 0,4395 s | 1 | no | −0,45 dB | 44,7 dB | 44,7 dB | — |
| 8 | DEATH | pacman death.wav | 16.916 | 1,5343 s | 1 | no | −0,09 dB | 42,0 dB | 42,1 dB | — |
| 9 | EXTRA_LIFE | extra life.wav | 20.940 | 1,8993 s | 1 | no | −0,16 dB | 42,3 dB | 42,4 dB | — |
| 12 | SIREN_CHASE | hunter siren.wav | 1.470 | 0,1333 s | 1 | **sí** | +11,88 dB | 42,7 dB | 11,7 dB | 12 LSB |
| 13 | SIREN_HUNT | hunted siren.wav | 4.412 | 0,4002 s | 1 | **sí** | +17,34 dB | 47,3 dB | 28,0 dB | 24 LSB |
| 15 | GHOST_RESPAWN | ghost respawn.wav | 2.935 | 0,2662 s | 1 | **sí** | +13,12 dB | 47,8 dB | 24,7 dB | 1 LSB |

- **Total PCM declarado: 127.034 B** = 106.379 B de los 10 slots principales + 20.655 B de las 8 variantes de sirena (incluye los arrays `*_p0` duplicados). Suma de arrays del `.c` = 127.034 ✔
- **Normalización:** pico global embebido = **117 LSB (valor u8 245 / 11) = −0,71 dBFS**, sin clipping (0 muestras 0/255 en los 10 slots). ✔
- **Troceado:** solo START necesita 2 trozos. Las demás longitudes ≤ 3.2768. Tabla `chunk_len` coherente (suma = len por slot; `chunk_count` correcto). ✔
- **Loop trimming:** los clips loop se recortan a **un periodo**: `ghost respawn` 6.007→2.935, `hunted siren` 13.024→4.412, `hunter siren` 26.508→1.470 muestras. El material sobrante del WAV (repeticiones) se descarta a propósito.
- **Recorte de silencio:** solo `game start` pierde audio (0,1304 s de silencio inicial + cola); los demás conservan todas sus muestras (los 11.025 Hz no necesitan remuestreo).

### 3.1 Fidelidad numérica

Dos métricas separadas (no mezclarlas, como hace el doc previo):
1. **SNR de cuantización** (PCM u8 vs. referencia float ya normalizada): **41,8–47,8 dB**, error RMS **0,27–0,30 LSB**. Es el límite propio de 8 bits y es correcto.
2. **SNR total vs. WAV original** (PCM reconstruido al rate/fuente y comparado con el original):
   - Fuentes ya a **11.025 Hz**: **42,0–44,7 dB** (solo cuantización, sin remuestreo). ✔
   - Fuentes a **48 kHz**: **11,7–28,0 dB** (`hunter siren` 11,7; `waka` 15,7/16,0; `game start` 23,2; `ghost respawn` 24,7; `hunted siren` 28,0). Esta pérdida está dominada por el **filtro antialias a ~4,96 kHz** del remuestreo 48k→11k, no por cuantización (los componentes >5 kHz del original se descartan). Es esperable y aceptable para SB16, pero debe documentarse: **no es una copia “fiel” de la fuente de 48 kHz**, es una fiel conversión a 11 kHz.
- **DC offset embebido** (media u8−128): game start −6,9 LSB; waka1 −13,8; waka2 −13,0; ghost respawn −14,2; hunted siren −7,2; hunter siren −6,6; resto −0,2…−0,6. La normalización amplifica el DC de origen (p.ej. waka pasa de −990 LSB s16 a −13,8 LSB u8 con +11,35 dB). No genera clipping, pero conviene un DC-block en la fase de corrección.
- **Bucles:** `ghost respawn` seam 1 LSB (excelente); `hunter siren` 12 LSB; `hunted siren` **24 LSB** (salto de −14,5 dBFS absoluto cada 0,4 s; audible en teoría aunque dentro del p99 de diferencias). El crossfade de 5 ms del generador no elimina del todo el salto de las sirenas.

---

## 4. `Res` vs `assets/res_original/`

| Archivo | En `Res` | En `res_original` | MD5 igual | SHA-256 igual | Tamaño |
|---|---|---:|---:|---:|---:|
| los 10 WAV usados | sí | sí | **sí** | **sí** | idéntico |
| `intermission.wav` | sí | **NO** | — | — | 57.600 B |

- **10/10 copias byte-idénticas** (MD5 y SHA-256 comprobados) ✔
- **Falta `intermission.wav`** en `res_original/` (y en el PCM): `res_original/` tiene solo 10 WAV. `assets/LICENSE_RES.md` lista 19 originales (10 WAV) y documenta `intermission.wav` como excluido ("No usado por Paku-Paku; decision: no portar"), lo cual es coherente con el contenido actual pero **incompleto respecto a las 11 fuentes de `Res/`**.
- `docs/AUDIT_RESOURCES.md` §3.5/§6 recomienda usar `intermission` para "nivel completado", pero el generador lo excluye: **la recomendación no se implementó**.

---

## 5. Asignación `hunted siren` / `hunter siren` (SIREN_HUNT 13 / SIREN_CHASE 12)

Evidencia en Paku-Paku (fuente de verdad del comportamiento original):
- `cGame.cls:582`: al comer una **power pill** (fantasmas asustados) → `gAmbientSound = "HunterSiren"`.
- `cGame.cls:279` y `cGame.cls:333`: al **terminar el efecto** de la power pill (`mPowerPillCounter = 0`) o al reanudar el nivel → `gAmbientSound = "HuntedSiren"` (modo normal).
- `modSoundFX.bas:126-131`: si `gAmbientSound = "HunterSiren"` reproduce `hunter siren.wav`; si no, `hunted siren.wav`.
- `modSoundFX.bas:88-101` (`SetSirenFrequency`): la **modulación de tono** (+0/10/20/30 % según dots restantes: ≤12 → +30 %, ≤61 → +20 %, ≤85 → +10 %) se aplica **solo a `hunted siren`**, no a `hunter siren`.

Conclusión:
- **`hunted siren` → SIREN_HUNT(13)**: correcto en cuanto a nombre y a su uso como **sirena del modo normal**. Estado: **PARCIAL** (el PCM existe y buclea, pero no se aplica la modulación de tono; seam 24 LSB).
- **`hunter siren` → SIREN_CHASE(12)**: el nombre coincide, pero **la semántica está invertida respecto a Paku-Paku**. En el original `hunter siren` es la sirena del **modo asustado** (Pac-Man cazador), NO una "sirena de persecución normal". El proyecto la usa en `src/core/game.c:435-440` como sirena del **tramo final del nivel** (`dots_left + power_left <= 50`), mientras que para el modo asustado usa `SIREN_FRIGHT` (slot 14), que **no tiene PCM** y cae al fallback sintetizado. Estado: **ERROR** (asignación semántica).
- **`pacasset_siren_hunt_res[4]` / `pacasset_siren_chase_res[4]`** (20.655 B de variantes +0/10/20/30 %) **no se usan en ningún `.c`/`.h` del juego**: `grep -rn pacasset_siren src include tests` solo devuelve las declaraciones de `sfx_res.c/.h`. La modulación de sirena de Paku-Paku está **AUSENTE en comportamiento** (los datos existen).
- Para la fase de corrección, la asignación coherente con el original sería: **modo asustado → `hunter siren` (con o sin variantes)**, **modo normal → `hunted siren` con variantes de pitch según dots**, y decidir si `SIREN_CHASE`/`SIREN_FRIGHT` se reutilizan o se eliminan.

### 5.1 Verificación de afirmaciones de `docs/AUDIT_RESOURCES.md`

| Afirmación del doc | Medición | Veredicto |
|---|---|---|
| 11 WAV en `Res`, MD5 listados | 11/11, MD5 coinciden | ✔ correcto |
| 10 WAV usados por Paku-Paku; `intermission` no | modSoundFX + grep | ✔ correcto |
| `game start` 2ch 8b 48k 4,378 s / 420.408 B | medido | ✔ correcto |
| `waka1/2` únicos 16 bits; 4.059/4.043 frames | medido | ✔ correcto |
| Slots 1/5/10/11/14 sin datos | parseado de `sfx_res.c` | ✔ correcto |
| START troceado ≤32768; total 127.034 B | 32.768+13.908; suma arrays 127.034 | ✔ correcto |
| `intermission` (57.377) > 32768 y "requiere trozos" | 57.377 ✔ pero **no está embebido** (no se trocea) | ⚠ obsoleto/no aplica |
| §3.4: `sfx_game_start` 48.272 frames | es el valor **pre-trim**; el PCM entregado es 46.676 | ⚠ doc mezcla prototipo y entrega |
| Pico normalizado "234/255 (−0,7 dBFS)" | valor u8 real **245** (117 LSB de amplitud → −0,71 dBFS) | ⚠ número erróneo, magnitud correcta |
| "SNR 29–44 dB frente a referencia 4,8 kHz" | cuantización 41,8–47,8 dB; total vs fuente 11,7–28,0 dB (48k) / 42–45 dB (11k) | ⚠ no reproducible; métrica mal definida |
| "waka 16→8 bits SNR 38,4 dB" | cuantización 46,7–47,7 dB; total vs fuente 15,7–16,0 dB | ⚠ no reproducible |
| Sirenas: periodo 4.412/1.470; seam 4,0 LSB (hunted) y 27 LSB (hunter) | periodos ✔; seams entregados **24 LSB (hunted) y 12 LSB (hunter)** | ⚠ valores de seam no coinciden con el entregado |
| "sin clipping", pico ≈ −0,7 dBFS | 0 muestras al máximo/mínimo; pico −0,71 dBFS | ✔ correcto |
| Generador determinista | re-ejecución → `sfx_res.c/h` byte-idénticos | ✔ correcto |
| Recomendación "usar intermission para level-clear" | no implementada (excluido) | ✘ no cumplida |

---

## 6. Tabla de estados por requisito (faceta audio/archivo)

| Requisito | Estado | Justificación / evidencia |
|---|---|---|
| 11 WAV originales presentes en `Res` | **COMPLETO** | 11/11, MD5+SHA-256, decodifican OK |
| Copias en `assets/res_original/` | **PARCIAL** | 10/11 byte-idénticas; falta `intermission.wav` |
| `game start` PCM + troceado SB16 | **COMPLETO** | 46.676 frames; 32.768+13.908; concatenación exacta; salto 8 LSB |
| `waka1`/`waka2` (alternancia comer punto) | **COMPLETO** | 932/929 frames; 16→8 bits sin clipping |
| `eat ghost` | **COMPLETO** | 6.324 frames; −0,52 dB normalización |
| `eat fruit` | **COMPLETO** | 4.845 frames; padding RIFF inocuo |
| `extra life` | **COMPLETO** | 20.940 frames |
| `pacman death` | **COMPLETO** | 16.916 frames |
| `ghost respawn` (bucle ojos) | **COMPLETO** | 2.935 frames; seam 1 LSB |
| `hunted siren` (bucle modo normal) | **PARCIAL** | PCM y bucle OK; sin modulación de pitch; seam 24 LSB |
| `hunter siren` (bucle) | **ERROR** | Asignada a SIREN_CHASE(12) con semántica de Paku-Paku invertida (debería ser modo asustado) |
| `SIREN_FRIGHT` (modo asustado) | **AUSENTE** | slot 14 sin PCM; usa fallback sintetizado; `hunter siren` no se usa aquí |
| `MENU` | **AUSENTE** | slot 1 sin PCM; no hay fuente en `Res`; el slot ni se reproduce en `src/` |
| `POWER` (power pill) | **AUSENTE** | slot 5 sin PCM; se reproduce (`game.c:289,610`) con síntesis |
| `LEVEL_CLEAR` (nivel completado) | **PARCIAL** | sin PCM (slot 10); `intermission.wav` válido (57.377 frames/5,204 s) existe en `Res` pero no se copió ni integró; fallback sintetizado |
| `GAME_OVER` | **AUSENTE** | slot 11 sin PCM; fallback sintetizado |
| Modulación de sirena por dots (+0/10/20/30 %) | **AUSENTE (comportamiento)** | 20.655 B de variantes pre-cocinadas presentes pero 0 referencias en `src/` |
| Normalización / anti-clipping | **COMPLETO** | pico 117 LSB (−0,71 dBFS); 0 muestras al máximo en los 10 slots |
| Fidelidad PCM vs original | **PARCIAL** | 11.025 Hz: 42–48 dB; 48 kHz: 11,7–28,0 dB por pérdida de banda >~5 kHz (esperable, documentar) |
| DC offset del PCM | **PARCIAL** | −0,2 a −14,2 LSB, amplificado por normalización; sin clipping |
| Generador reproducible/determinista | **COMPLETO** | re-ejecución en `/tmp/regen` → `sfx_res.c/h` MD5 idénticos |
| `docs/AUDIT_RESOURCES.md` exacto | **PARCIAL** | mayoría verificada; imprecisiones en SNR, pico (245 vs 234), seams y frames pre-trim |
| Reproducción en hardware SB16 real | **NO VERIFICADO** | solo análisis estático y revisión de código; no hay hardware SB16 |
| Calidad percibida / clics audibles | **NO VERIFICADO** | no se reprodujo/escuchó audio; solo métricas numéricas |

---

## 7. Hallazgos más graves (con evidencia numérica)

1. **Modo asustado sin sonido correcto y `hunter siren` mal usada.** `SIREN_FRIGHT(14)` tiene `data=NULL,len=0` (verificado en `sfx_res.c`) y el proyecto lo usa en `game.c:435` para el modo asustado → cae al fallback sintetizado, mientras Paku-Paku usa `hunter siren` en ese modo (`cGame.cls:582`, `modSoundFX.bas:126-131`). A la vez, `hunter siren` (1.470 frames) se usa como sirena normal del tramo final (`game.c:439`). **Contradice la referencia.**
2. **Datos de modulación de sirena muertos.** Las 8 variantes de pitch de sirena ocupan **20.655 B** dentro de `sfx_res.c` (de ellos, los arrays `*_p0` ≈5.882 B duplican el contenido de los slots 12/13; el resto, ≈14.773 B, es material adicional) y **ningún** `.c/.h` de `src/`, `include/` o `tests/` referencia `pacasset_siren_hunt_res`/`pacasset_siren_chase_res`. La modulación +0/10/20/30 % de Paku-Paku (`modSoundFX.bas:88-101`) no se aplica: la sirena PCM suena siempre a la misma frecuencia.
3. **`intermission.wav` válido pero excluido; `LEVEL_CLEAR` sin recurso.** El WAV decodifica perfecto (57.377 frames, 5,204 s, pico −0,21 dBFS, 0 clipping) y está en `Res/`, pero no está en `res_original/` ni en `sfx_res.c`; el slot 10 queda vacío. El propio `AUDIT_RESOURCES.md` §3.5 recomendaba usarlo para nivel completado, y `LICENSE_RES.md` lo excluye. `res_original/` queda en 10/11.
4. **`game start.wav` 9,007× sobredimensionado.** 420.408 B = 210.165 frames × 2 canales × 48 kHz u8, con canales idénticos (`max|L−R| = 0`) y **99,65 % de energía < 5,5 kHz**. El PCM útil es 46.676 B. La conversión final es correcta (2 chunks, sin click: salto frontera 8 LSB vs p99 37 LSB; fade-out final; sin clipping), pero la elección de formato no aporta calidad.
5. **Calidad de bucle y DC mejorables.** Seams PCM de **24 LSB (`hunted siren`, −14,5 dBFS absoluto)** y **12 LSB (`hunter siren`)** frente a 1 LSB de `ghost respawn`; DC embebido de −6,6 a **−14,2 LSB** en waka/respawn/sirenas (amplificado por la normalización de +11,9 a +17,3 dB). Son candidatos claros a la fase de corrección (loop-point/crossfade más largo y DC-block), sin afectar al audio de un solo disparo.
6. **El informe previo tiene imprecisiones** que conviene corregir: pico "234/255" → real **245**; "SNR 29–44 dB" no reproducible (cuantización 41,8–47,8 dB; total vs fuente 11,7–28,0 dB para 48 kHz); seams "4,0/27 LSB" → reales **24/12 LSB**; "`game start` 48.272 frames" es pre-trim (entregado **46.676**); `intermission` "requiere trozos" no aplica porque no está embebido.

---

## 8. Evidencias y limitaciones

- `REPORT.md` (este documento): tablas completas.
- `summary.json`: datos por archivo/slot, comparación de slots, estados por requisito y hallazgos para agregación del Lead.
- `audit_wav.py`: script reproducible (Python bundled con NumPy/Pillow) con el pipeline de medición WAV + comparación del PCM embebido; imprime las métricas en JSON.
- Ruta de evidencias (workspace): `/home/t1an/Descargas/sereos02/audit/wav-integrity/`.

Limitaciones:
- **No se escuchó** el audio ni se ejecutó el juego: la audibilidad subjetiva de los seams y los clics es **NO VERIFICADO** (solo métricas).
- **No hay hardware SB16**: la reproducción real por chunks (temporización/underruns) es **NO VERIFICADO**; el código revisado (`platform_sereos.c:478-535`, `platform_linux.c:251-329`) encadena los chunks y reencola en bucle sin perder muestras en el análisis estático.
- El "SNR vs fuente" de clips de 48 kHz depende del filtro del generador (`fc≈4,96 kHz`); se midió con la misma función del generador, no con un resampler de referencia independiente.
