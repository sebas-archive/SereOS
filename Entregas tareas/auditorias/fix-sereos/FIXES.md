# B4 — Corrección integración nativa SereOS (task-8)

Fecha: 2026-11-20 · Autor: sereos-audit · Base: `audit/sereos-audit/REPORT.md` (A3)
Write scope respetado: `Pac-man SereOS/src/platform/sereos/`, `sistema operativo/audio/`,
`sistema operativo/drivers/sb16.c/.h`. No se tocó `src/core`, `src/platform/linux`,
`assets/sfx_res.c` ni `res_original/*`.

## Cambios (antes → después)

| ID A3 | Archivo:línea (después) | Antes | Después |
|---|---|---|---|
| D1 CRÍTICO | `Pac-man SereOS/src/platform/sereos/platform_sereos.c:429-446` (`pcm_play_chunk`) | `sb16_play(data_del_asset, len)` directo: `pacasset_pcm_game_start_1` @0x32ff40 + 13908 cruzaba 64 KiB → `sb16.c:134` devolvía 0 → START 2.97 s y 1.5 s de silencio | copia cada chunk a la bounce buffer DMA-safe del kernel (`audio_dma_bounce(&cap)`, 32 KiB alineados a 64 KiB, dirección 0x370000 < 16 MiB) y llama `sb16_play(dmabuf, len, 11025)`. Ningún chunk de asset puede violar el 8237 |
| D1 API | `sistema operativo/audio/audio.c:361-365` + `audio/audio.h:55-61` | no había forma de obtener un buffer DMA-safe fuera de `audio.c` | `uint8_t *audio_dma_bounce(uint32_t *capacity)` expone el bounce buffer interno (mismo contrato que ya usaba `sb16_start_clip`) |
| D2 ALTO | `platform_sereos.c:526-548` (`pac_audio_loop`) | si no había WAV Res (SIREN_FRIGHT=14) caía a `audio_loop()` sin parar el motor PCM: `pac_audio_update()` seguía rearmando SIREN_HUNT por debajo | `pcm_stop()` + `audio_stop_loop()` antes de `audio_loop(os)`: una sola sirena a la vez |
| D3 ALTO | `platform_sereos.c:507-524` (`pac_audio_play`) | fallback sintetizado sin parar el motor PCM (podía encolarse/starved tras el loop) | `pcm_stop()` + `audio_stop_loop()` antes de `audio_play(os)` |
| D3b | `platform_sereos.c:505-521` | `pac_audio_play` honraba `pacasset_sfx_res_loop[sfx]` (un `play` de GHOST_RESPAWN habría quedado en loop infinito) | `pac_audio_play` es siempre one-shot: `pcm_start(sfx, 0)`; el loop sólo se pide con `pac_audio_loop()` |
| D4 MEDIO | `sistema operativo/audio/audio.c:153-163,303-304` | el `pcspk_oneshot()` de fallback en backend SB16 (`audio.c:220`) sólo se apagaba en la rama PCSPK de `audio_update()` → podía quedar sonando | nuevo `pcspk_release_expired()` que se ejecuta al inicio de `audio_update()` para **todos** los backends |
| D4b | `audio/audio.c:266-281` (`audio_stop_loop`) | sólo paraba el DMA si `loop_playing` estaba a 1 (estado desincronizado dejaba el bucle rearmándose) | detecta `loop_sfx != NONE || loop_playing`, para DMA, resetea fase/next_tick |
| D4c | `audio/audio.c:285-299` (`audio_stop`) | no reseteaba `loop_phase/loop_next_tick/pcspk_off_tick` | resetea todo el estado de tiempo |
| D1b | `sistema operativo/drivers/sb16.c:226-239` | si fallaba `0x14` o la longitud, enmascaraba DMA pero dejaba el altavoz DSP encendido | `0xD3` (speaker off) en las rutas de fallo; documentado el contrato bounce/DMA en la cabecera |

## Verificación real (QEMU 11.1.3, TCG, sin KVM)
- Rebuild: `make sereos OS_DIR=...` (libpacman.a) + `make -j20` (SO/ISO) → exit 0. Binario integrado B1+B2+B4: `sereos.bin` 1 513 136 B, ISO 36 806 656 B, `grub-file --is-x86-multiboot` OK.
- Serial: `SEREOS_BOOT_OK mem=255MiB`, `GUI_READY`, `LEVEL_START 1`, `GAME_START`, `PAC_DEATH` (sin regresión de arranque/juego).
- Runtime (QMP `xp`, solo lectura): `backend=sb16`, DSP `0x0405`, base `0x220`, `rate=11025`; START: `sb_plays=1, chunk=0` durante 2.97 s y **a +3.00 s `sb_plays=2`, `playing=1`, `chunk=1`** (antes: `playing=0`, `active=0`, `sb_plays` sin subir).
- Captura PA null-sink (`capture-b4int.raw`, 44100 s16le):
  - START: run audible **12.20–16.50 s = 4.30 s** (asset 4.233 s; antes 3.00 s + 1.5 s silencio), chunk0 corr 100 ms **+0.992**, chunk1 corr en su ventana **-0.847** (magnitud alta: el segundo chunk suena).
  - SIREN_HUNT corr 100 ms **+0.997**; loop 0.4001 s.
  - Fallback PC speaker (sin `-device sb16`) sigue OK: tonos 950 (START), 520/390 (WAKA), 370/290 (siren hunt), 180 (DEATH) Hz.
- Evidencia: `fix-memprobe.log`, `memprobe-history.txt`, `analysis-final-fix.txt`, `analysis-fix-pcspk.txt`,
  `capture-b4int.raw`, `capture-b4pcspk.raw`, `serial-b4int.log`, `serial-pcspk.log`, `shot-b4int-*.png`,
  `fix-probe-b4int.log`, `fix-probe-pcspk.log`.

## Limitaciones que persisten (kernel; no se pueden eliminar sin reescribir el driver)
1. PCM **u8 mono 11025 Hz**; sin conversión de formato/estéreo (todos los assets ya son u8 mono 11025).
2. **Sin mezclador**: una sola voz DMA; no se pueden solapar sirena + efecto. La API sigue siendo "un clip a la vez" (cola kernel de 4 one-shots, con descarte si se llena).
3. **Sin IRQ5/terminal count**: fin por tiempo (PIT 100 Hz, resolución 10 ms), sin doble buffer; los loops los rearma la CPU cada frame (hueco ~1 frame/33 ms).
4. DMA 8 bits canal 1: <16 MiB y sin cruzar 64 KiB (ahora garantizado por `audio_dma_bounce`); bloque máx. 32768 B.
5. Altavoz del PC (PIT ch2): sólo tonos, sin PCM.
6. QEMU: SB16 sólo si se añade `-device sb16,audiodev=...`; sin KVM el guest va lento pero el tiempo del guest fue ≈ real.
7. `audio_init()` sigue siendo perezoso (lo llama el juego/monitor/acerca-de), no `kernel_main`.

## Pendiente / fuera de mi scope (otros agentes)
- B1: intermission.wav → slot 10 PCM (la ruta nativa lo usará automáticamente: `pacasset_sfx_res_available(10)` + chunks ≤32768 + bounce). En la build integrada probada aún no se completó un nivel, así que LEVEL_CLEAR PCM queda NO VERIFICADO en QEMU.
- B2: semántica fina de prioridades/holds de `src/core` (no tocado).
- Sigue sin poder probarse hardware SB16 físico (todo QEMU/TCG).
