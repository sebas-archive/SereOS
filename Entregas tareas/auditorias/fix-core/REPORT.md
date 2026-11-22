# CORRECCIÓN B2 — cableado de eventos y máquina de audio del núcleo

**Tarea:** task-6 · **Agente:** events-audit · **Fecha:** 2026-11-20
**Write scope respetado:** `Pac-man SereOS/src/core/` + `Pac-man SereOS/tests/`. No se tocó `src/platform/*`, `assets/`, ni el SO. Sin API nueva `pac_audio_*` (ABI intacta).
**Fuente:** `audit/events-audit/REPORT.md` (A4).

## Ficheros modificados

| Fichero | Cambio |
|---|---|
| `src/core/pac_game.h` | `PAC_LEVEL_CLEAR_MS 1400 → 5400` (cubre intermission 5204 ms); nuevos campos `audio_oneshot` (L259) y `siren_grace_ms` (L260). |
| `src/core/game_audio.c` | Holds reales: WAKA 100, EAT_GHOST 590, EAT_FRUIT 460, EXTRA_LIFE 1920, POWER 320, MENU 260, LEVEL_CLEAR 5300 (L47-58); prioridad de one-shots `effect_priority` (L66-81) + bloqueo en `pac_sound_play` (L89-103); validación `sfx < PAC_SFX_COUNT` (L89); `sound_reset`/limpieza en init/stop (L24-38, L131); `pac_sound_set_siren` ya no cachea estado si `audio_ok==0` (permite rearmar tras OFF→ON/foco). |
| `src/core/game.c` | `update_siren` (L438-468): ojos → loop `GHOST_RESPAWN`; frightened → `SIREN_CHASE` (slot 12, hunter); normal → `SIREN_HUNT` (slot 13); incluye `siren_grace_ms`. Reset de audio en `pac_start_new_game` (L386) y `restore_continue` (L245); sin `g->siren=` directo en `pac_start_level` (L376-378); `spawn_fruit_if_needed` ya no reproduce POWER (L645); MENU en attract/menú/navegación/pausa (L476, L498, L506, L561, L565); `pac_settings_apply` OFF→ON resincroniza (L186-200); foco/minimizado paran el loop (L867, L874); `game_tick` limpia `audio_oneshot` al terminar el hold y decae la gracia (L733-744); gracia 300 ms al comer dot (L290); DEATH ya no duplica el hold (L305-310). |
| `src/core/game_entities.c` | Eliminadas las 2 emisiones muertas `PAC_GAME_EVENT_GHOST_RESPAWN` (L379-399): el sonido lo gobierna `update_siren`; se conservan los seriales `GHOST_RETURNED`. |
| `tests/mock_platform.c/.h` | Log de secuencia de audio: `mock_audio_log_clear/count/at` (kind 0=play 1=loop 2=stop_loop 3=stop); `mock_audio_clear_counts` también limpia el log. Aditivo (no rompe API previa). |
| `tests/core_tests.c` | M1 actualizado a `PAC_LEVEL_CLEAR_MS==5400`; helper `audio_quiet`/`audio_log_has`; bloque nuevo `AUDIO-B2` (24 checks, L1375+) que cubre holds, prioridad EXTRA_LIFE vs WAKA, GHOST_RESPAWN por ojos, sirenas CHASE/HUNT, POWER no cortado, MENU, OFF→ON, foco, nivel completado. |

## Defectos cerrados

- **P0-1** `GHOST_RESPAWN` nunca sonaba → loop de estado mientras haya `PAC_GHOST_EATEN`; al volver los ojos retoma HUNT. Test: “GHOST_RESPAWN suena como loop mientras hay ojos”.
- **P0-2** `EXTRA_LIFE` pisada por WAKA → prioridad + hold 1920; el WAKA del mismo tick se descarta. Test: “el WAKA del mismo tick NO pisa EXTRA_LIFE”.
- **P0-3** sirenas invertidas → frightened usa slot 12 (hunter) y normal slot 13 (hunted). Tests: “frightened usa CHASE/hunter”, “fuera de frightened vuelve HUNT”.
- **P0-6** `PAC_SFX_MENU` nunca se llamaba → attract/menú/navegación/pausa. Tests: “MENU suena al navegar”, “MENU suena en attract→menú”.
- **P0-7** POWER cortado por FRIGHT y POWER espurio al aparecer la fruta → hold 320 + eliminada la llamada de `spawn_fruit_if_needed`. Tests: “FRIGHT no arranca durante el hold de POWER”, “al agotarse el hold de POWER sí arranca FRIGHT”.
- **P1-1..4** one-shots truncados por hold corto → holds = duración real + 15-20 ms (4 checks).
- **P1-5** sirena reiniciada en cada dot → `siren_grace_ms=300` tras EAT_DOT (test de gracia).
- **P1-6** foco/minimizado: loop no se paraba ni se rearmaba → para al perder foco y rearma al recuperarlo. Tests: “sin foco se para”, “al recuperar el foco se rearma”.
- **P1-7** OFF→ON dejaba la sirena muda → resync en `pac_settings_apply` + bookkeeping de `set_siren`. Tests: “OFF para la sirena”, “OFF→ON rearma la sirena”.
- **P1-8** `pac_start_level` asignaba `g->siren` directo → eliminado, ahora pasa por `set_siren`.
- **P1-9** `restore_continue` restauraba estado de audio obsoleto → `pac_sound_stop` tras restaurar.
- **P2-2/P2-3** limpieza de holds y evento de respawn; `PAC_GAME_EVENT_GHOST_RESPAWN` queda en el enum por compatibilidad pero ya no se emite.

## Pendiente (fuera de este scope)

- **P0-4** `pcm_stop()` en la rama sintetizada de `pac_audio_loop` → task-7 (Linux B3).
- **P0-5** integración de `intermission.wav` en slot 10 → task-5 (assets B1). El core ya espera 5300/5400 ms y lo reproducirá automáticamente al existir el PCM.
- **P1-10** `pac_audio_play` de SereOS honrando el loop flag del recurso (`GHOST_RESPAWN` se pide por `pac_audio_loop`, no por `play`, por lo que no le afecta; limpieza recomendada) → task-8 (SereOS B4).
- **P2-4/P2-5** variantes de pitch 0/10/20/30 % de la sirena normal: requieren API nueva; aplazado por indicación del Lead (no ABI nueva en esta fase). Slot 14 `SIREN_FRIGHT` queda sin uso en el core (remapeado a slot 12).
- **Trade-off documentado:** sin mezclador, mientras EXTRA_LIFE suena 1.9 s se descartan los waka de ese intervalo; la gracia de 300 ms silencia la sirena durante rachas de dots y la reanuda al dejar de comer.

## Verificación (evidencia en este directorio)

- `make linux` → `[pacman] Linux OK -> build/pacman-sereos` (`make-linux.log`, rc=0, sin warnings nuevos).
- `make sereos` → `[pacman] SereOS OK -> build/sereos/libpacman.a` (`make-sereos.log`, rc=0) — compila el core `-m32 -ffreestanding`.
- `make test` → **194 checks, 0 failures** + “TODAS LAS PRUEBAS OK” (harness de core + 7 escenas smoke Linux) (`make-test.log`).
- Los 24 checks específicos de B2 en `audio-b2-checks.txt`.
- Re-verificado al final (misma sesión) con los cambios concurrentes de B1/B3/B4 ya presentes (sfx_res con intermission, platform_linux/sereos actualizados): `make linux` rc=0 y `make test` 194/0 OK.

Nota: el árbol ya traía cambios ajenos a B2 previos a esta tarea (fix del wrap del túnel en `game_entities.c` y tests de render `T9-T17`); se han conservado intactos.

---

# CORRECCIÓN B5 — silenciar one-shots al pausar/perder foco (task-10)

**Fecha:** 2026-11-20 · **Write scope:** `src/core/` + `tests/`. Sin API nueva.

## Cambios

| Fichero:línea | Cambio |
|---|---|
| `src/core/game.c:335-338` | `pac_set_state(PAUSED)` pasa de `pac_sound_set_siren(NONE)` a `pac_sound_stop(g)`: para sirena **y** one-shot (`pac_audio_stop()`) y resetea `audio_hold_ms=0`, `audio_oneshot=NONE`, `siren_grace_ms=0`. |
| `src/core/game.c:581-588` | Al reanudar (Esc o “Continuar”): `pac_sound_stop(g)` + estado PLAYING; `update_siren` rearma la sirena y **no** se reintenta el one-shot. |
| `src/core/game.c:866-884` | Minimizado / pérdida de foco: si hay audio activo (sirena/hold/oneshot/gracia) se llama `pac_sound_stop(g)` una sola vez (guarda para no repetir `pac_audio_stop` cada frame); al recuperar foco/minimizar=`0`, `update_siren` rearma la sirena. |
| `tests/core_tests.c:1529-1595` | Bloque `AUDIO-B5` (15 checks): pausa resetea hold/oneshot/gracia/sirena y pide `pac_audio_stop`; al reanudar NO se reintenta EAT_GHOST y vuelve HUNT; pérdida de foco y minimizado hacen lo mismo y rearman al volver. |

## Verificación

- `make linux` rc=0 (`make-linux.log`).
- `make test` → **209 checks, 0 failures** + `TODAS LAS PRUEBAS OK` (`make-test.log`); 24 B2 + **15 B5** checks específicos (`audio-b2-checks.txt`, `audio-b5-checks.txt`).
- Sin cambios fuera de `src/core/` y `tests/`; sin ABI nueva.
