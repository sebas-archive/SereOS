# CORRECCIÓN B1 — Integración de `intermission.wav` y regeneración de assets PCM

- **Agente:** `wav-integrity` — **Tarea:** `task-5` (fase corrección).
- **Fecha:** 2026-11-20.
- **Write scope respetado:** `Pac-man SereOS/assets/`, `Pac-man SereOS/tools/gen_pacman_res_assets.py` y la sección de audio de `Pac-man SereOS/docs/GAME.md`. **No se tocó `src/`, `tests/` ni el SO.**
- **Fuente:** `/home/t1an/Descargas/Res` (originales leídos, nunca modificados).

## 1. Cambios realizados

| Fichero | Cambio | MD5 nuevo |
|---|---|---|
| `assets/res_original/intermission.wav` | **NUEVO** (copia byte-idéntica de `Res/`; 57.600 B) | `566c0f2299b8a7ebef6372010fa6866e` |
| `tools/gen_pacman_res_assets.py` | `intermission.wav` añadido a `WAV_USED`/`EXPECTED_MD5`; eliminado de `EXCLUDED_FILES`; nuevo clip `LEVEL_CLEAR` (slot 10); `LOOP_FLAG_OVERRIDE={"GHOST_RESPAWN":0}`; docstring/cabeceras a 11 WAV | `12ca7dc0920d7f42083d8af30405d1da` |
| `assets/sfx_res.c` | Regenerado: array `pacasset_pcm_level_clear_0/1` (57.377 u8), tablas actualizadas; total PCM **184.411 B** | `8fa2edc5c0eb4da7d4ac0497fe6759c9` |
| `assets/sfx_res.h` | Cabecera: 11 WAV, slots con WAV `2,3,4,6,7,8,9,10,12,13,15`, `LEVEL_CLEAR=intermission`, nota loop de `GHOST_RESPAWN` | `5650ddfc656e42638a7bdf63b5626790` |
| `assets/LICENSE_RES.md` y `assets/res_original/LICENSE_RES.md` | Regenerados: "20 archivos" e `intermission.wav` listado | `78170b1eb22e5155a4186fe869a63c14` |
| `docs/GAME.md` | Sección de audio: "11 WAV", `LEVEL_CLEAR` usa `intermission`, nota del flag de `GHOST_RESPAWN` | `5bbdc45f58b7a88c2c7ad69bcfeae365` |

No cambiaron `sprites_res.*`, `font_arcade.*` ni los 10 WAV previos de `res_original/` (ver `before.sha256`/`after.sha256`). Solo se modificaron los ficheros previstos.

## 2. `intermission.wav` integrado (slot 10 LEVEL_CLEAR)

- Original: 57.600 B, PCM u8 mono 11025 Hz, 57.377 frames, 5,204263 s, pico −0,21 dBFS, 0 clipping, ya a 11.025 Hz (sin remuestreo).
- PCM generado: **57.377 muestras (5,204263 s)**, u8 mono 11025, normalizado al pico global del pipeline (117 LSB = **−0,71 dBFS**), DC **−0,368 LSB**, primera/última muestra `128/127` (sin click), **0 muestras con clipping**.
- Sin recorte de silencio: el clip conserva las 57.377 muestras (no pierde cola).
- **Troceado SB16: 2 chunks = 32.768 + 24.609 = 57.377** (ambos ≤ 32.768; `chunk_count[10]=2`, `chunk_len[10]={32768,24609}`), one-shot (`loop[10]=0`).
- El reproducir de forma automática por el código existente: `pacasset_sfx_res_chunks[]`/`chunk_len[]` son genéricos, no hay que hardcodear el slot en Linux/SereOS.

## 3. `pacasset_sfx_res_loop[GHOST_RESPAWN]=0`

- Se emite **`loop[15]=0`** mediante `LOOP_FLAG_OVERRIDE` (el audio PCM de `GHOST_RESPAWN` se mantiene igual: periodo de bucle de 2.935 muestras, 0,2662 s, seam 1 LSB, para que B2 lo reproduzca con `pac_audio_loop`). El resto del array de loops: `loop[12]=loop[13]=1`, todos los demás 0.
- Justificación: el efecto de respawn de ojos se pide en bucle por API (`pac_audio_loop`), no debe auto-loopearse al llamar `pac_audio_play` (tarea B2).

## 4. Tabla final de slots con datos

| Slot | Símbolo | Clip | Frames | Duración | Chunks | Loop flag |
|---:|---|---|---:|---:|---:|---:|
| 2 | START | game start | 46.676 | 4,2337 s | 2 (32768+13908) | 0 |
| 3 | WAKA1 | waka1 | 932 | 0,0845 s | 1 | 0 |
| 4 | WAKA2 | waka2 | 929 | 0,0843 s | 1 | 0 |
| 6 | EAT_GHOST | eat ghost | 6.324 | 0,5736 s | 1 | 0 |
| 7 | EAT_FRUIT | eat fruit | 4.845 | 0,4395 s | 1 | 0 |
| 8 | DEATH | pacman death | 16.916 | 1,5343 s | 1 | 0 |
| 9 | EXTRA_LIFE | extra life | 20.940 | 1,8993 s | 1 | 0 |
| **10** | **LEVEL_CLEAR** | **intermission** | **57.377** | **5,2043 s** | **2 (32768+24609)** | 0 |
| 12 | SIREN_CHASE | hunter siren | 1.470 | 0,1333 s | 1 | 1 |
| 13 | SIREN_HUNT | hunted siren | 4.412 | 0,4002 s | 1 | 1 |
| 15 | GHOST_RESPAWN | ghost respawn | 2.935 | 0,2662 s | 1 | **0** |

Sin WAV (data=0): 1 MENU, 5 POWER, 11 GAME_OVER, 14 SIREN_FRIGHT (y 0 NONE). **Total PCM: 184.411 B** (antes 127.034 B; +57.377 B), suma de los arrays del `.c` = 184.411 ✔.

## 5. Verificación (todo OK; ver `verify_fix.log` / `verify_fix.json`)

- 11/11 WAV de `Res` inventariados; `res_original/` contiene **11 WAV**, los 11 byte-idénticos a `Res` (MD5); los 10 previos no cambiaron; `Res` intacto.
- `LEVEL_CLEAR`: 57.377 frames, 2 chunks 32768+24609, loop=0; array **byte-idéntico** a la salida del generador.
- **Fidelidad byte a byte generador↔`sfx_res.c` en los 11 slots** y en las **8 variantes de sirena p0/p10/p20/p30** (frames 4.412/4.011/3.676/3.394 y 1.470/1.336/1.225/1.131; intactas).
- **0 muestras con clipping** (u8 0/255) en todo el PCM; pico 117 LSB (−0,71 dBFS).
- Tablas coherentes (`chunk_count`, `chunk_len`, suma por slot, `total_bytes`, `rate=11025`).
- **Determinismo:** segunda generación completa (`--out /tmp/regen2`) → `sfx_res.c/.h`, `sprites_res.*`, `font_arcade.*` y `LICENSE_RES.md` con **MD5 idénticos** (`determinism.txt`).
- `gcc -fsyntax-only -I assets assets/sfx_res.c` → **OK**.
- Diff de assets: solo cambian `sfx_res.c/.h`, los dos `LICENSE_RES.md` y el nuevo `res_original/intermission.wav` (`changed-files.txt`).

## 6. Cómo regenerar

```bash
PY=/home/t1an/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
cd "/home/t1an/Descargas/sereos02/Pac-man SereOS"
"$PY" tools/gen_pacman_res_assets.py            # regenera assets y res_original
"$PY" ../audit/fix-assets/verify_fix.py          # verificacion B1 (sale 0 si OK)
```

## 7. Notas de coordinación

- **B2 (core):** `LEVEL_CLEAR` dura 5,204 s; el `hold` de `game_audio.c` debe cubrir el clip (~5.300 ms). `GHOST_RESPAWN` debe pedirse con `pac_audio_loop` (flag por defecto 0).
- **B3 (Linux)/B4 (SereOS):** no requiere cambios de código: las tablas genéricas ya exponen el slot 10 con 2 chunks. Comprobar `make linux` sin warnings (solo datos generados).
- `docs/GAME.md`: actualizada la sección de audio (era la única referencia que afirmaba "10 WAV / intermission no se integra"). Si el Lead prefiere que B1 no toque docs, es un cambio aislado de 5 líneas reversible.

## 8. Evidencias (`audit/fix-assets/`)

`REPORT.md`, `generate.log`, `verify_fix.py`, `verify_fix.log`, `verify_fix.json`, `determinism.txt`, `before.sha256`, `after.sha256`, `changed-files.txt`, `sfx_tables.txt`.
