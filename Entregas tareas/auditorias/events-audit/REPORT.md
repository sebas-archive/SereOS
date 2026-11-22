# AUDITORÍA A4 — Cableado eventos→audio de PAC-MAN SereOS

**Ámbito:** `Pac-man SereOS/` (núcleo `src/core/`, plataformas `src/platform/linux|sereos/`, assets `assets/`).
**Fase:** SOLO LECTURA. No se ha editado ningún fichero del proyecto (evidencias en este directorio: `REPORT.md` + `harness-out.txt`).
**Referencia de comportamiento:** `/home/t1an/Descargas/Paku-Paku/` (VB6): `modSoundFX.bas`, `cGame.cls`, `cGhost.cls`; y documentos `docs/AUDIT_PAKUPAKU.md`, `docs/AUDIT_RESOURCES.md`, `docs/GAME.md`.
**Método:** lectura estática + arnés de simulación determinista que enlaza el **núcleo real** (`game.c`, `game_audio.c`, `game_entities.c`, `game_maze.c`, `game_ai.c`) contra una copia instrumentada de `tests/mock_platform.c` que registra la secuencia exacta de `pac_audio_play/loop/stop_loop` con timestamps. Log completo: `harness-out.txt`. 40/40 comprobaciones OK (el arnés confirma los defectos, no implementa correcciones).

---

## 0. Resumen ejecutivo (top 8)

| # | Defecto | Prio |
|---|---|---|
| 1 | **`GHOST_RESPAWN` nunca suena**: `pac_emit_event()` no tiene `case`; el slot 15 (WAV 266 ms) es código muerto. "Regreso de fantasmas" sin audio. | **P0** |
| 2 | **`EXTRA_LIFE` inaudible**: se pide en `pac_add_score()` y el mismo tick lo tapa el WAKA/EAT_GHOST/EAT_FRUIT; además `hold=900` < clip 1899 ms. | **P0** |
| 3 | **Sirenas con semántica invertida**: la "sirena de persecución" normal tardía usa el *hunter siren* (= ambiente de frightened en el original) y la sirena frightened usa un slot VACÍO; el original usa hunted 0/10/20/30 % y hunter sólo con power pill. | **P0** |
| 4 | **Linux: dos sirenas simultáneas durante frightened**: `pac_audio_loop()` en la rama sintetizada no hace `pcm_stop()`, así que el loop PCM de HUNT sigue sonando debajo del loop sintetizado de FRIGHT. | **P0** |
| 5 | **Nivel completado sin sonido**: `LEVEL_CLEAR` no tiene WAV e `intermission.wav` (Res, 5.204 s) no está integrado; `PAC_LEVEL_CLEAR_MS=1400` es incompatible con 5204 ms. | **P0** |
| 6 | **`PAC_SFX_MENU` no se reproduce nunca** (0 llamadas; el enum existe y el fallback sintetizado existe). Menú/attract silenciosos. | **P0** |
| 7 | **POWER**: `hold=0` ⇒ el loop FRIGHT lo sustituye a los ~16 ms en Linux; además al **aparecer** la fruta se dispara POWER (`game.c:610`), sonido no asociado al evento. | **P0/P1** |
| 8 | **One-shots truncados por `hold` corto**: WAKA 70 ms vs clip 84.5 ms; EAT_GHOST 300 vs 574; EAT_FRUIT 250 vs 440; EXTRA_LIFE 900 vs 1899. Además la sirena se **reinicia en cada dot** (3 reinicios/3 dots, ver log C). | **P1** |

---

## 1. Matriz completa evento → disparo → slot → WAV → reproducción real

Slots (`assets/sfx_res.h`, `include/pac_platform.h:92-110`):
`0 NONE · 1 MENU · 2 START · 3 WAKA1 · 4 WAKA2 · 5 POWER · 6 EAT_GHOST · 7 EAT_FRUIT · 8 DEATH · 9 EXTRA_LIFE · 10 LEVEL_CLEAR · 11 GAME_OVER · 12 SIREN_CHASE · 13 SIREN_HUNT · 14 SIREN_FRIGHT · 15 GHOST_RESPAWN`.

Duraciones reales (muestras @11025 mono u8, `assets/sfx_res.c:6427-6490`): START 46676 = **4233.8 ms** (2 trozos 32768+13908); WAKA1 932 = **84.5 ms**; WAKA2 929 = **84.3 ms**; EAT_GHOST 6324 = **573.6 ms**; EAT_FRUIT 4845 = **439.5 ms**; DEATH 16916 = **1534.6 ms**; EXTRA_LIFE 20940 = **1899.3 ms**; SIREN_CHASE 1470 = **133.3 ms** (loop); SIREN_HUNT 4412 = **400.2 ms** (loop); GHOST_RESPAWN 2935 = **266.2 ms** (loop flag = 1). Sin WAV: 1, 5, 10, 11, 14.

| # | Evento (enunciado) | Quién dispara (archivo:línea) | `pac_sound_*` → slot | ¿WAV? | ¿Se reproduce? | Resultado real / defecto |
|---|---|---|---|---|---|---|
| 1 | **Inicio de partida** | `game.c:390` (`pac_start_new_game`) ← menú `game.c:479`, pausa-reiniciar `534/556`, gameover `591`, tecla R `621`; QA `886,889,901,920,923,927,934,941` | `play(PAC_SFX_START)` slot 2 | **Sí** 4233.8 ms / 2 trozos ≤32768 | Sí, exactamente 1 vez por partida (log B); `hold=4500` = `READY_START_MS` | OK. `hold 4500` deja **266 ms de silencio** al final del clip (4233.8→4500); no es un fallo, es margen. No se repite en attract/replay (no existen) ni al cambiar de nivel (correcto: original sólo nivel 1). |
| 2 | **Consumo de puntos (waka)** | `game_entities.c:245-247` → `pac_emit_event(EAT_DOT)`; `game.c:280-284` | `play(WAKA1/2)` slots 3/4 alternando por paridad `dots_eaten&1` | **Sí** 84.5/84.3 ms | Sí, 1 vez por dot (sin duplicado; log C) | **P1**: `hold=70` ms < clip 84.5 ⇒ el último 14-15 % se corta; y cada dot hace `STOP_LOOP` + re-arranque de sirena (stutter audible). |
| 3 | **Superpunto** | `game_entities.c:245` → `EAT_POWER`; `game.c:286-292` | `play(PAC_SFX_POWER)` slot 5 (tras `pac_ai_frighten`) | **NO** → sintetizado (Linux `g_sfx_freq[5]=1200 Hz/160 ms`; SereOS `AUDIO_POWER`) | Se pide, pero `hold=0` ⇒ no para el loop; en Linux `update_siren` arranca FRIGHT (sintetizado) en el tick siguiente y mata el beep (~16 ms, log E) | **P0/P1** ver §3.2. **No existe sonido específico de superpunto en Res**; el fallback sintetizado es legítimo, pero hoy es inaudible. |
| 4 | **Captura de fantasma** | `game_entities.c:463-495` (`ghost_eat`) → `EAT_GHOST`; `game.c:293-295` | `play(PAC_SFX_EAT_GHOST)` slot 6 | **Sí** 573.6 ms | Sí 1 vez (log O) | **P1**: `hold=300` ⇒ a los 300 ms vuelve la sirena y corta 274 ms del clip (log O: PLAY 19590 → LOOP 19890). |
| 5 | **Regreso de fantasmas (ojos)** | `game_entities.c:375` y `:384` emiten `PAC_GAME_EVENT_GHOST_RESPAWN` | `pac_emit_event` **no tiene case** → cae en `default` (`game.c:310-311`) | Slot 15 **Sí** (266.2 ms, loop=1) | **NUNCA** (log F: 0 eventos de audio) | **P0**: evento principal sin sonido. Además el emisor actual (llegada a casa) es el punto donde el original **termina** el bucle de respawn, no donde lo empieza (`modSoundFX.bas:120-132`, `cGhost.cls:150`). |
| 6 | **Consumo de fruta** | `game_entities.c:249-263` → `EAT_FRUIT`; `game.c:296-298` | `play(PAC_SFX_EAT_FRUIT)` slot 7 | **Sí** 439.5 ms | Sí 1 vez | **P1**: `hold=250` corta 190 ms. **P0/P1 añadido**: al **aparecer** la fruta suena POWER (`game.c:610`), no al comerla (log G: WAKA + POWER simultáneos); en el original sólo suenan `EatDot`/`EatFruit` al comer (`cGame.cls:562,570`); la aparición no tiene `PlaySound`. |
| 7 | **Vida adicional** | `pac_add_score` (`game.c:101-111`) → `pac_check_extra_life` (`game.c:113-124`) → `play(EXTRA_LIFE)` slot 9 | **Sí** 1899.3 ms | Se pide, pero **inaudible** | **P0**: dentro del mismo evento que suma los puntos, la línea siguiente (`game.c:283/294/297/262`) pide WAKA/EAT_GHOST/EAT_FRUIT, que **sustituye** el one-shot (Linux `SDL_ClearQueuedAudio`, SereOS `sb16_stop`) y **pisa `audio_hold_ms` 900→70/300/250** (log D: play EXTRA_LIFE + play WAKA en el mismo ms, hold final=70). |
| 8 | **Muerte de Pac-Man** | `game_entities.c:524-530` → `EAT... DEATH`; `game.c:299-303` | `play(PAC_SFX_DEATH)` slot 8 + `audio_hold_ms=2000` (redundante con `effect_hold_ms`) | **Sí** 1534.6 ms | Sí (log J, M) | OK. `hold 2000 > clip`; la animación dura 2800 ms y bloquea la sirena por `death_ms>0`; al morir con vidas restantes la sirena vuelve **exactamente** tras 2800+1500 = 4300 ms (log M). |
| 9 | **Sirena de persecución (normal)** | `update_siren` `game.c:427-440` | `set_siren(SIREN_HUNT)` slot 13 normal; `set_siren(SIREN_CHASE)` slot 12 si `dots_left+power_left<=50` | **Sí** ambas (loop) | Sí: arranca al acabar READY (log B2), se para en pausa/menú/muerte/gameover/nivel (log H, J, K) | **P0 semántica**: slot 12 = *hunter siren* (`sfx_res.c:6460`; `tools/gen_pacman_res_assets.py:1015`), que en Paku-Paku es el ambiente **del power pill/frightened**, no el de persecución normal. El boost de frecuencia por dots (hunted +10/20/30 %) no se usa: las 4 variantes `pacasset_siren_hunt_res` (y `_chase_res`) están generadas pero **ningún código las consume**. |
| 10 | **Sirena frightened** | `update_siren` `game.c:434-435` | `set_siren(SIREN_FRIGHT)` slot 14 | **NO** (data=NULL) | Sintetizada (Linux loop 440 Hz; SereOS `AUDIO_SIREN_FRIGHT`) | **P0**: el sonido real de frightened existe ya en Res (`hunter siren.wav`, slot 12, 133.3 ms loop) y no se usa; en Linux además se solapa con el loop PCM de HUNT (ver D-P0-4). |
| 11 | **Transición entre niveles** | `tick_playing` `game.c:674-677` → `pac_set_state(LEVEL_CLEAR)` `game.c:336-340` | `play(PAC_SFX_LEVEL_CLEAR)` slot 10 | **NO** → sintetizado (Linux 1760 Hz/450 ms) | Sí 1 vez (log K) | **P0**: sin WAV; `intermission.wav` (Res, 57377 muestras = 5204 ms) no integrado (`assets/sfx_res.h:1-13`, `docs/GAME.md:90-93`). Estado dura 1400 ms: incompatible con el clip (log N). Doble `STOP_LOOP` redundante en el mismo tick (`pac_set_state`+`pac_sound_play`, log K). |
| 12 | **Game over** | `pac_after_pacman_death` `game.c:400-403` → `pac_set_state(GAMEOVER)` `game.c:331-335` | `play(PAC_SFX_GAME_OVER)` slot 11 + `hold=1200` | **NO** → sintetizado (Linux 165 Hz/600 ms) | Sí 1 vez (log J) | Aceptable: **no hay clip en Res**; el sintetizado cubre el requisito. `hold 1200` > beep 600 sin daño. |
| 13 | **Menú** | — (no hay ninguna llamada) | `PAC_SFX_MENU` slot 1 | **NO** → sintetizado disponible (Linux 660 Hz/240 ms; SereOS `AUDIO_MENU`) | **Nunca** (log A: 0 plays tras navegar attract/menú/instrucciones) | **P0**: evento requerido sin audio; sólo falta el llamador (no hace falta material de Res). |
| 14 | **Intermission / nivel completado** | igual que #11 | slot 10 (hoy sintetizado) | **NO** integrado; `intermission.wav` existe en `/home/t1an/Descargas/Res/` (11025 Hz mono u8, 57377 muestras, 5.204 s) | No | **P0**: integrar como LEVEL_CLEAR y alargar estado; ver §5. |
| 15 | **Pausa** | `pac_set_state(PAUSED)` `game.c:328-330`; reanudar `game.c:544-553` | `set_siren(NONE)` | — | Sí: para y reanuda la sirena (log H) | OK, salvo que al reanudar la sirena **reinicia** desde el principio (no hay reanudación por posición; aceptable con API actual). |
| 16 | **Attract** | `tick_attract` `game.c:445-454` | — | — | Silencio total | **P0/P2**: se cubre al añadir MENU (#13). |
| 17 | **Pérdida de foco / minimizado** | `pac_game_tick` early-return `game.c:822-831` | no toca audio | — | La sirena **no se para**; al recuperar el foco **no se rearma** (`g->siren` sigue HUNT, `set_siren` retorna por igualdad) | **P1** (log L, L2). En Linux el loop PCM se agota al dejar de llamar a `pac_audio_update`; en SereOS el SB16 no se rearma. |
| 18 | **Ajuste sonido OFF→ON** | `pac_settings_apply` `game.c:186-197` | `pac_audio_stop()`; no resetea `g->siren` | — | Al reactivar, `audio_ok=1` pero **la sirena no vuelve** (log I) | **P1**: `pac_sound_set_siren` hace early-return `g->siren == sfx` (`game_audio.c:59-60`) y además asigna `g->siren` antes de comprobar `audio_ok` (`game_audio.c:61-63`). |

### Eventos definidos pero muertos
- `PAC_GAME_EVENT_EXTRA_LIFE` (`pac_game.h:156`, `game.c:304-306`): nunca se emite; la vida extra se dispara directa desde `pac_check_extra_life`.
- `PAC_GAME_EVENT_LEVEL_CLEAR` (`pac_game.h:157`, `game.c:307-309`): nunca se emite; el sonido lo dispara `pac_set_state`.
- `PAC_GAME_EVENT_GHOST_RESPAWN` (`pac_game.h:158`): se emite 2 veces (`game_entities.c:375,384`) y **no se maneja**.
- `pacasset_siren_hunt_res[4]` / `pacasset_siren_chase_res[4]` (variantes pitch, `assets/sfx_res.c:6492-6505`): sin consumidores.
- `pacasset_sfx_res_loop[15]=1` (GHOST_RESPAWN): inconsistente con el uso one-shot previsto; en SereOS `pac_audio_play` honra ese flag (`platform_sereos.c:482-489`) ⇒ si se arreglase #1 llamando a `pac_audio_play`, el clip de 266 ms quedaría **en bucle infinito**.

---

## 2. Máquina de estados de audio — análisis (`src/core/game_audio.c` 85 líneas + `game.c`)

### 2.1 Piezas
- `g->audio_hold_ms`: "efecto en curso"; se decrementa una vez por tick lógico en `game_tick` (`game.c:698-702`), DT=16 ms.
- `g->siren`: **última** sirena pedida, no el estado real del backend. `pac_sound_set_siren` hace early-return si `g->siren == sfx` (`game_audio.c:59-60`).
- `pac_sound_play`: si `hold>0` → `g->siren=NONE`, `pac_audio_stop_loop()`, fija `audio_hold_ms`; luego `pac_audio_play(sfx)` (`game_audio.c:38-53`).
- `update_siren` (`game.c:427-440`): si no está en PLAYING/READY/muerte/hold → `set_siren(NONE)`; si no, elige FRIGHT / CHASE / HUNT.
- Backends: Linux = 2 dispositivos (síntesis S16 22050 + PCM u8 11025); un solo clip PCM a la vez (`SDL_ClearQueuedAudio`). SereOS = SB16 un canal + cola de one-shots del SO, loops re-armados en `pac_audio_update`.

### 2.2 Fallos estructurales del diseño
1. **No hay noción de "one-shot en curso" con prioridad.** El único estado es `audio_hold_ms`; cualquier `pac_sound_play` posterior reemplaza el clip y reescribe el hold. De ahí EXTRA_LIFE (P0-2), POWER (P0-7) y que el waka pise cosas.
2. **`g->siren` se usa como caché de idempotencia, pero se desincroniza del backend** cuando: (a) `pac_sound_play` con `hold>0` lo pone a NONE sin pasar por `set_siren`; (b) `pac_start_level` lo asigna directamente (`game.c:369`); (c) el backend deja de sonar (pérdida de foco/toggle de sonido) sin que nadie lo sepa. Resultado: sirenas que "no vuelven" (log I, L2).
3. **`pac_sound_set_siren` escribe `g->siren` antes de mirar `audio_ok`** (`game_audio.c:61-63`): mientras `sound_on=0` el estado sigue evolucionando y al reactivar todo parece "ya puesto".
4. **El modelo "hold corta la sirena y luego update_siren la reanuda" es incompatible con un único canal**: cada dot → stop loop + waka + re-loop (stutter cada ~106 ms de juego). En el original waka y sirena **suenan a la vez** (DirectSound multicanal). Sin mezclador, hay que elegir: (a) hold exacto del clip y aceptar el stutter, (b) ventana de gracia que silencie la sirena mientras se encadenan dots y la reanude ~250-300 ms después del último dot (recomendado), (c) mezcla software en plataforma (futuro).
5. **Holds no derivados de la duración real**: tabla `effect_hold_ms` (`game_audio.c:21-36`) hardcodeada; 4 de 8 valores son menores que el clip (ver §1). POWER y MENU no tienen hold.
6. **Sirenas**: el mapeo semántico está cruzado con los recursos (ver §3). El original: `HuntedSiren` = ambiente normal (con boost 0/10/20/30 % a 85/61/12 dots restantes) y `HunterSiren` = sólo durante power pill (`modSoundFX.bas:16-34,88-133`; `cGame.cls:279-280,582-583`).
7. **Linux**: `pac_audio_loop` sintetizado no llama a `pcm_stop()` (`platform_linux.c:395-403`) ⇒ el loop PCM anterior sigue sonando: **dos sirenas simultáneas** durante frightened (HUNT PCM + FRIGHT synth). SereOS sí corta (`audio/audio.c:237-241`).
8. **`pac_sound_play` no valida `sfx < PAC_SFX_COUNT`**, sólo `<= NONE` (`game_audio.c:42`); con `int` vale hoy pero es frágil si se añaden slots.

### 2.3 Respuestas concretas a las preguntas del encargo
- **¿Waka duplicado?** No: un `EAT_DOT` por dot (verificado: 3 dots → 3 plays, alternancia 1/2 correcta, log C). El problema no es duplicación sino truncado + reinicio de sirena.
- **¿POWER en cada superpunto o 2 llamadas?** 1 llamada por power pill (`game.c:289`), pero hay una **segunda llamada espuria** al aparecer la fruta (`game.c:610`). No es "cada superpunto", es "evento equivocado".
- **¿START repetido en reset/attract/replay?** No dentro de una partida: sólo `pac_start_new_game`. No hay attract automático ni replay en el componente. Repetir R/“Reiniciar” vuelve a lanzar el Game Start completo (4.5 s) por diseño (nivel 1). En QA, `pac_game_debug_scene("gamestart"/"play"/…)` lo relanza en cada llamada.
- **¿Hold 4500 mal ajustado?** No: clip convertido = 4233.8 ms; 4500 ms = READY_START y deja 266 ms de silencio. Correcto pero debe documentarse que el clip viene recortado (original 4378 ms).
- **¿EAT_GHOST/EAT_FRUIT tapados por POWER?** No exactamente: se truncan por `hold` corto; POWER sí puede ser tapado por FRIGHT. Colateral: en `spawn_fruit_if_needed` el POWER puede tapar el WAKA del mismo tick (fruta aparece justo tras comer el dot 70/170; log G).
- **¿Waka interrumpe sirenas o viceversa?** Waka **para** el loop y la sirena **re-arranca** desde el principio 70 ms después; no hay mezcla. Con la corrección propuesta (ventana de gracia) se evita el arpegio de reinicios.

---

## 3. Defectos priorizados

Convención: `RUTA:LÍNEA` relativa a `Pac-man SereOS/`.

### P0 — rompen requisitos funcionales del usuario

#### D-P0-1 · `GHOST_RESPAWN` nunca se reproduce (regreso de fantasmas sin sonido)
- **Evidencia:** `pac_emit_event` (`src/core/game.c:275-313`) no tiene `case PAC_GAME_EVENT_GHOST_RESPAWN`; los emisores `src/core/game_entities.c:375,384`; slot 15 con WAV `assets/sfx_res.c:6438,6457`; arnés log F (0 llamadas).
- **Parche mínimo:** añadir a `pac_emit_event`:
```c
case PAC_GAME_EVENT_GHOST_RESPAWN:
    pac_sound_play(g, PAC_SFX_GHOST_RESPAWN);
    break;
```
- **Parche recomendado (fiel a Paku-Paku, donde el respawn es un LOOP que dura hasta que vuelve la sirena):** no usar el evento; gobernar la sirena por estado en `update_siren`:
```c
/* ojos volviendo a casa: bucle de respawn, como modSoundFX.bas:120-132 */
for (i = 0; i < PAC_GHOST_COUNT; i++)
    if (g->ghosts[i].state == PAC_GHOST_EATEN) {
        pac_sound_set_siren(g, PAC_SFX_GHOST_RESPAWN);
        return;
    }
```
y borrar/ignorar las dos emisiones `PAC_GAME_EVENT_GHOST_RESPAWN` de `game_entities.c` (o dejarlas sin `case`, como log/QA).
- **Requisito asociado:** `src/platform/sereos/platform_sereos.c:482-489`: `pac_audio_play` no debe honrar `pacasset_sfx_res_loop[]` (un one-shot no puede enlazar). Cambiar `pcm_start(sfx, loop)` por `pcm_start(sfx, 0)`; el loop se pide sólo por `pac_audio_loop`. Alternativa: `pacasset_sfx_res_loop[15]=0` en el generador.

#### D-P0-2 · `EXTRA_LIFE` inaudible (vida adicional sin efecto sonoro)
- **Evidencia:** `src/core/game.c:101-111` (`pac_add_score` → `pac_check_extra_life`) + `game.c:113-124` (play) + líneas siguientes del mismo evento `game.c:283`, `game_entities.c:494`, `game.c:297/262`; `src/core/game_audio.c:38-53` (sin prioridad); clip 1899 ms vs hold 900. Arnés log D: `PLAY EXTRA_LIFE` y `PLAY WAKA1` en el mismo ms, `audio_hold_ms` final 70.
- **Parche:** (a) añadir campo `int audio_oneshot;` a `struct pac_game` (`src/core/pac_game.h:207-272`); (b) en `game_audio.c`:
```c
static int effect_priority(int sfx)
{
    switch (sfx) {
    case PAC_SFX_DEATH:        return 100;
    case PAC_SFX_GAME_OVER:    return 90;
    case PAC_SFX_EXTRA_LIFE:   return 80;
    case PAC_SFX_LEVEL_CLEAR:  return 75;
    case PAC_SFX_START:        return 70;
    case PAC_SFX_EAT_GHOST:    return 60;
    case PAC_SFX_EAT_FRUIT:    return 50;
    case PAC_SFX_POWER:        return 40;
    case PAC_SFX_GHOST_RESPAWN:return 35;
    case PAC_SFX_MENU:         return 20;
    case PAC_SFX_WAKA1:
    case PAC_SFX_WAKA2:        return 10;
    default:                   return 0;
    }
}

void pac_sound_play(pac_game_t *g, int sfx)
{
    int hold;
    if (!g || !g->audio_ok || sfx <= PAC_SFX_NONE || sfx >= PAC_SFX_COUNT)
        return;
    /* un one-shot más importante en curso no se pisa */
    if (g->audio_oneshot > PAC_SFX_NONE && g->audio_hold_ms > 0 &&
        effect_priority(sfx) < effect_priority(g->audio_oneshot))
        return;
    hold = effect_hold_ms(sfx);
    if (hold > 0) {
        g->siren = PAC_SFX_NONE;
        pac_audio_stop_loop();
        g->audio_hold_ms = hold;
        g->audio_oneshot = sfx;
    }
    pac_audio_play(sfx);
}
```
(c) en `game_tick` (`game.c:698-702`), al llegar el hold a 0: `g->audio_oneshot = PAC_SFX_NONE;`
(d) en `pac_start_new_game` antes de `pac_sound_play(START)`: `g->audio_hold_ms = 0; g->audio_oneshot = PAC_SFX_NONE;` (si no, un GAME_OVER activo bloquearía el START).
- **Trade-off a documentar:** mientras suena EXTRA_LIFE (1.9 s) se pierden los waka/ghost/fruit de ese intervalo (no hay mezclador). Es preferible a que la vida extra no se oiga; alternativa futura: cola de one-shots.

#### D-P0-3 · Sirenas invertidas: persecución normal usa el sonido de frightened; frightened usa un slot vacío
- **Evidencia:** `src/core/game.c:434-439`; `assets/sfx_res.c:6460` (`[12]=hunter siren`), `:6461` (`[13]=hunted siren`); `tools/gen_pacman_res_assets.py:1014-1015`; original `modSoundFX.bas:102-133` + `cGame.cls:279-280,582-583` (HuntedSiren normal, HunterSiren con power pill); `docs/AUDIT_PAKUPAKU.md:419-425`.
- **Parche mínimo (sin tocar assets ni ABI):**
```c
if (g->fright_ms > 0) {
    /* hunter siren = ambiente del power pill (Res: slot 12, 133 ms loop) */
    pac_sound_set_siren(g, PAC_SFX_SIREN_CHASE);
    return;
}
/* hunted siren normal (slot 13); el boost de pitch se añade en el parche completo */
pac_sound_set_siren(g, PAC_SFX_SIREN_HUNT);
```
(y eliminar el corte en 50: slot 12 pasa a significar "hunter/fright" y slot 13 "hunted/normal").
- **Parche completo (boost 0/10/20/30 %):** API nueva `void pac_audio_loop_variant(int sfx, int variant);` en `include/pac_platform.h`, implementada por Linux (`pcm_start` variante), SereOS (`pcm_start` variante) y mock; en core:
```c
static void set_siren_variant(pac_game_t *g, int sfx, int variant)
{
    int key = sfx * 8 + variant;          /* clave estable para idempotencia */
    if (g->siren == key) return;
    g->siren = key;
    if (!g->audio_ok) return;
    if (sfx == PAC_SFX_NONE) pac_audio_stop_loop();
    else pac_audio_loop_variant(sfx, variant);
}
/* thresholds Paku: dots restantes <=85/61/12 -> +10/+20/+30 % */
```
Riesgo: cambia el contrato de plataforma (ABI 1 → 2) y el mock; los arrays `pacasset_siren_hunt_res[4]/chase_res[4]` ya existen (usar `pacasset_siren_hunt_res[variant].data/len`). Alternativa sin ABI: añadir slots 16-18 a `pac_audio_sfx_t` (`SIREN_HUNT_P10/P20/P30`) y regenerar `assets/sfx_res.c` (arrays de 19) — más invasivo en el enum compartido con `audio/audio.h` del SO.

#### D-P0-4 · Linux: dos sirenas simultáneas durante el power pill
- **Evidencia:** `src/platform/linux/platform_linux.c:384-404`: la rama sintetizada de `pac_audio_loop` no detiene el dispositivo PCM; `pac_audio_update:420-437` sigue re-encolando el loop PCM (`g_pcm_loop`). Secuencia real: HUNT = PCM loop → POWER (sintetizado) → `update_siren` pide FRIGHT (sin WAV) → `pac_audio_loop` sintetizado → **PCM HUNT + FRIGHT synth a la vez** durante todo el frightened.
- **Parche:** al inicio de la rama sintetizada de `pac_audio_loop`, añadir `pcm_stop();` (y simétricamente en la rama sintetizada de `pac_audio_play` si se quiere semántica "un solo efecto"; con D-P0-2/P0-7 no es necesario porque todo `pac_sound_play` con hold ya para el loop):
```c
g_audio_playing = 1;
g_audio_loop = 1;
pcm_stop();                 /* no dejar sonando el loop PCM anterior */
```
- **Nota:** el parche de D-P0-3 (FRIGHT→slot 12 con WAV) ya evita este caso concreto, pero el `pcm_stop()` debe quedar por robustez (p. ej. menú/POWER sintetizados mientras suena una sirena PCM).

#### D-P0-5 · Nivel completado / intermission: sin WAV y con duración incompatible
- **Evidencia:** `src/core/game.c:674-677` + `:336-340`; `assets/sfx_res.c:6445` (slot 10 vacío); `assets/sfx_res.h:1-13`; `docs/GAME.md:90-93`; clip `intermission.wav` verificado en `/home/t1an/Descargas/Res/intermission.wav`: PCM u8 mono 11025 Hz, **57377 muestras = 5204 ms** (`docs/AUDIT_RESOURCES.md:296,360`); `PAC_LEVEL_CLEAR_MS` = 1400 (`src/core/pac_game.h:49`), arnés log N.
- **Parche (3 pasos):**
  1. `tools/gen_pacman_res_assets.py`: añadir `intermission.wav` al pipeline (hoy excluido en líneas 97, 131, 1131) con destino slot `LEVEL_CLEAR`, `loop=False`, y **2 trozos** `32768 + 24609` (ambos ≤ `SB16_MAX_BUFFER`); copiar el WAV a `assets/res_original/` (hoy falta) y actualizar la tabla/hash y `assets/sfx_res.h` (“10 WAV” → 11).
  2. `src/core/pac_game.h:49`: `#define PAC_LEVEL_CLEAR_MS 5400` (5204 + margen 200); `src/core/game_audio.c:27`: `case PAC_SFX_LEVEL_CLEAR: return 5300;`.
  3. Verificar `tests/core_tests.c:857-880` (ya usa `PAC_LEVEL_CLEAR_MS`) y el smoke `victory`; recalcular presupuesto de memoria (+57.377 B ≈ 56 KiB sobre 127034 B actuales, `assets/sfx_res.c:6516`).
- **Alternativa si no se aprueba tocar assets:** dejar el sintetizado y **documentar** que “nivel completado” usa fallback; el estado seguiría en 1400 ms. No se puede “derivar” intermission de otro clip sin falsear el recurso.

#### D-P0-6 · El sonido de menú no suena nunca
- **Evidencia:** `include/pac_platform.h:94` (enum), `assets/sfx_res.c:6429` (slot 1 sin WAV), **0 llamadas** en `src/` (grep); arnés log A. El fallback sintetizado existe: `src/platform/linux/platform_linux.c:64-71` (`g_sfx_freq[1]=660 Hz`, `g_sfx_ms[1]=240`) y `sistema operativo/audio/audio.h:13` (`AUDIO_MENU`).
- **Parche** en `src/core/game.c`:
  - `tick_attract` (`:447`): antes de `pac_set_state(MENU)` → `pac_sound_play(g, PAC_SFX_MENU);`
  - `tick_menu` (`:460-475`): si cambia `menu_sel` → `pac_sound_play(g, PAC_SFX_MENU);`; y en cada `confirm_pressed`/acción → idem (al menos en navegación y aceptar).
  - Opcional pausa/settings: mismo blip en `up/down`.
  - Añadir `case PAC_SFX_MENU: return 260;` en `effect_hold_ms` para que el blip no se corte y ordene el hold con los demás.
- **Nota:** no existe clip de menú en `Res`; el sintetizado es la solución legítima (no inventar WAV).

#### D-P0-7 · POWER: se come el beep y además suena al aparecer la fruta
- **Evidencia:** `src/core/game.c:289` (`play POWER`, hold 0) → `src/core/game_audio.c:34` (default 0) → `game.c:434-435` arranca FRIGHT en el tick siguiente: arnés log E (PLAY 5940 → LOOP 5950, ~10-16 ms). Y `src/core/game.c:602-612`: `spawn_fruit_if_needed` llama `pac_sound_play(g, PAC_SFX_POWER)` al aparecer la fruta (arnés log G: WAKA y POWER en el mismo ms).
- **Parche:**
  - `game_audio.c:21-36`: `case PAC_SFX_POWER: return 320;` (beep sintetizado 160 ms + margen; bloquea la sirena mientras suena).
  - `game.c:610`: **eliminar** la línea (el original no suena al aparecer la fruta; en el original sólo suenan `EatDot`/`EatFruit` al comer, `cGame.cls:562,570`); si se quiere feedback de aparición, usar `PAC_SFX_MENU` (blip UI) **sólo si el usuario lo aprueba**, nunca POWER.
  - Prioridad POWER=40 (D-P0-2) evita que WAKA/EAT_FRUIT del mismo tick lo pisen.

### P1 — defectos audibles/gestionables

| ID | Defecto | Evidencia | Parche |
|---|---|---|---|
| D-P1-1 | WAKA truncado (70 ms vs 84.5 ms) | `game_audio.c:32-33`; `sfx_res.c:6430-6431`; log C | `case WAKA1/2: return 100;` (clip + ~15 ms) |
| D-P1-2 | EAT_GHOST truncado (300 vs 574) | `game_audio.c:30`; log O (LOOP a +300) | `return 590;` |
| D-P1-3 | EAT_FRUIT truncado (250 vs 440) | `game_audio.c:31` | `return 460;` |
| D-P1-4 | EXTRA_LIFE truncado (900 vs 1899) | `game_audio.c:28`; log D | `return 1920;` (junto con D-P0-2) |
| D-P1-5 | Sirena reiniciada en cada dot (stutter) | `game_audio.c:45-51`+`game.c:427-440`; log C: 3 dots → 3 STOP_LOOP + 3 LOOP | Ventana de gracia: campo `int siren_grace_ms;` en `pac_game_t`; en `EAT_DOT`: `g->siren_grace_ms = 300;`; decrementar en `game_tick`; en `update_siren` añadir `g->siren_grace_ms > 0` a las condiciones de silencio. La sirena se reanuda al dejar de comer (aprox. arcade sin mezclador). Alternativa mínima: aceptar y documentar. |
| D-P1-6 | Pérdida de foco: loop sigue y no se rearma al volver | `game.c:822-831`; log L/L2 | En ambas ramas early-return: `pac_sound_set_siren(g, PAC_SFX_NONE);` antes de `return` (para el loop y deja `g->siren=NONE`, de modo que `update_siren` lo rearma al recuperar foco). |
| D-P1-7 | Sonido OFF→ON: la sirena no vuelve | `game.c:186-197`; `game_audio.c:55-68`; log I | En `pac_settings_apply`: `if (!g->sound_on) { pac_sound_set_siren(g, PAC_SFX_NONE); g->audio_ok = 0; pac_audio_stop(); } else { pac_audio_stop(); g->audio_ok = pac_audio_available(); g->siren = PAC_SFX_NONE; }`. Además en `pac_sound_set_siren`, mover la asignación `g->siren = sfx;` **después** del chequeo de `audio_ok` sólo cuando `sfx==NONE`, o mantener un flag `audio_loop_on` separado. |
| D-P1-8 | `pac_start_level` asigna `g->siren = PAC_SFX_NONE` directamente y el `set_siren(NONE)` siguiente hace early-return: si hubiera un loop activo no se pararía | `game.c:369-371` | Eliminar la línea 369; dejar sólo `pac_sound_set_siren(g, PAC_SFX_NONE);` (que para el loop y actualiza el estado). |
| D-P1-9 | `restore_continue` restaura `audio_hold_ms`, `siren`, `audio_oneshot` del snapshot sin sincronizar el backend | `game.c:229-245` | Tras `*g = tmp;`: `g->audio_hold_ms = 0; g->audio_oneshot = PAC_SFX_NONE; g->siren = PAC_SFX_NONE; pac_audio_stop_loop();` |
| D-P1-10 | SereOS: `pac_audio_play` honra el flag loop del recurso | `src/platform/sereos/platform_sereos.c:482-489` | `pcm_start(sfx, 0)`; el loop sólo por `pac_audio_loop` |

### P2 — limpieza / fidelidad opcional

| ID | Defecto | Evidencia | Propuesta |
|---|---|---|---|
| D-P2-1 | Holds hardcodeados, no derivados del clip | `game_audio.c:21-36` | Tabla estática `sfx_clip_ms[]` con valores de `sfx_res.c` + 15-20 ms, o API `uint32_t pac_audio_clip_ms(int sfx)` en `pac_platform.h` implementada por ambos backends (mock incluido). |
| D-P2-2 | Eventos muertos `EXTRA_LIFE`/`LEVEL_CLEAR` en `pac_emit_event` | `game.c:304-309` | Eliminarlos o usarlos (p. ej. `pac_check_extra_life` → `pac_emit_event` reordenando el audio) para que la tabla evento→audio sea única. |
| D-P2-3 | Doble `pac_audio_stop_loop()` en el mismo tick al entrar en LEVEL_CLEAR/GAMEOVER | `pac_set_state` llama `set_siren(NONE)` y `pac_sound_play` (hold>0) vuelve a parar; log K | Cosmético; se puede quitar el `set_siren(NONE)` de `PAC_STATE_LEVEL_CLEAR/GAMEOVER` porque `pac_sound_play` ya para el loop. |
| D-P2-4 | Variantes de pitch de sirena generadas y sin usar | `assets/sfx_res.c:6492-6505` | Ligado a D-P0-3 (API variantes) |
| D-P2-5 | Umbral de sirena usa `dots_left+power_left` y un único corte en 50 | `game.c:436` | Original: 3 boosts a 85/61/12 dots restantes (`modSoundFX.bas:88-101`); usar `dots_left + power_left` con 85/61/12 y variante de pitch |
| D-P2-6 | `hold=4500` del START vs clip 4233.8 ms | `game_audio.c:24` | Correcto (266 ms de margen); sólo documentar en `docs/GAME.md` que el clip convertido es 4.234 s |
| D-P2-7 | `PAC_GAME_OVER` hold 1200 > beep 600 | `game_audio.c:26` | Sin impacto (estado GAMEOVER bloquea sirena); opcional 700 |
| D-P2-8 | `pac_sound_play` no valida cota superior | `game_audio.c:42` | `sfx >= PAC_SFX_COUNT` → return |
| D-P2-9 | En Linux, el loop PCM se re-encola sólo desde `pac_audio_update` (una vez por tick lógico, 16 ms). El loop CHASE dura 133 ms: con un parón de >~120 ms hay hueco | `platform_linux.c:420-437` | Re-encolar en un callback/antes del underrun o subir el margen de re-encolado; no crítico hoy |
| D-P2-10 | Alineación de enums | `include/pac_platform.h:92-110` vs `sistema operativo/audio/audio.h:11-25`: idénticos 0..14; `PAC_SFX_GHOST_RESPAWN=15` es extensión y `os_sfx()` la traduce (`platform_sereos.c:467-476`); `assets/sfx_res.h` = 16 slots | **Alineado hoy**. Añadir comprobación de compilación en `platform_sereos.c`: `typedef char pac_sfx_abi_check[(AUDIO_COUNT == PAC_SFX_COUNT - 1) ? 1 : -1];` para que un reordenamiento futuro del enum del SO falle en compilación. |

---

## 4. Integración menú/attract: conclusiones
- `PAC_SFX_MENU` **existe** en los 3 enum (pac, OS, sfx_res) y está alineado (slot 1), pero **no tiene llamador** y **no tiene WAV**. El fallback sintetizado sí está implementado en ambos backends (Linux `g_sfx_freq/g_sfx_ms[1]`, SereOS `AUDIO_MENU`). Por tanto el arreglo es **sólo añadir llamadas** (D-P0-6), sin tocar assets.
- Attract no emite audio alguno (`tick_attract`): al añadir MENU en la transición attract→menú y en la navegación queda cubierto.
- Enums: **sí están alineados** (§D-P2-10), con la extensión documentada GHOST_RESPAWN. Riesgo: `os_sfx()` depende del cast directo para 0..14; añadir el `typedef` de comprobación.

---

## 5. Propuesta de mapeo para slots ausentes (sólo material de Res + sintetizado declarado)

| Slot | Situación | ¿Qué puede usarse legítimamente? | Propuesta |
|---|---|---|---|
| 1 `MENU` | sin WAV | **No existe** clip de menú en `Res/` (inventario `docs/AUDIT_RESOURCES.md:88-123`). Sintetizado ya existe en ambos backends | Mantener sintetizado; **añadir llamadas** (D-P0-6). No fabricar WAV. |
| 5 `POWER` | sin WAV | **No existe** clip de power-up en `Res/`. Derivarlo de otra sirena/waka sería inventar semántica | Mantener sintetizado; `hold=320` (D-P0-7). |
| 10 `LEVEL_CLEAR` | sin WAV; `intermission.wav` **sí existe** (`/home/t1an/Descargas/Res/intermission.wav`, 57377 muestras, 5.204 s, mono u8 11025) y no lo usa Paku-Paku (`docs/AUDIT_PAKUPAKU.md:419-425`) | Recurso Res legítimo para "nivel completado"/intermission | **Integrar** en slot 10 (2 trozos ≤32768) + `PAC_LEVEL_CLEAR_MS=5400` + hold 5300 (D-P0-5). Actualizar generador, `sfx_res.h`, docs y presupuesto de memoria. |
| 11 `GAME_OVER` | sin WAV | **No existe** clip de game over en `Res/` | Mantener sintetizado (165 Hz/600 ms). No derivar del death (duplicaría el evento). |
| 14 `SIREN_FRIGHT` | sin WAV | **Sí existe** el sonido que el original usa con power pill: `hunter siren.wav` = slot 12 (`sfx_res.c:6460`, `gen_pacman_res_assets.py:1015`) | **No hace falta WAV nuevo**: remapear `fright_ms>0` → `PAC_SFX_SIREN_CHASE` (slot 12). Si se quiere conservar el slot 14, copiar `pacasset_pcm_siren_chase` a `[14]` con `loop=1` (mismo material, sin inventar). |
| 15 `GHOST_RESPAWN` | **Sí tiene WAV** (2935 muestras, 266.2 ms, loop=1) pero nunca se usa | Recurso Res legítimo (`ghost respawn.wav`) | Usarlo como **loop de estado** mientras haya ojos volviendo (D-P0-1) y arreglar el flag loop en `pac_audio_play` de SereOS. |
| 12/13 sirenas | WAV existentes, pero 12 mal usado y variantes pitch muertas | `hunted siren.wav` (normal, boosts 10/20/30 % ya cocinados en `pacasset_siren_hunt_res`) y `hunter siren.wav` (power pill) | `normal → hunt[0..3]` según dots restantes 85/61/12; `fright → hunter (slot 12)`. Requiere API de variante o 3 slots extra (D-P0-3). |

**Lo que NO existe y no debe inventarse:** clip de menú, clip de power-up, clip de game over. Se cubren con los sintetizados actuales y así debe declararse en docs/README.

---

## 6. Plan de corrección propuesto (archivos y orden)

1. `src/core/game_audio.c`: reescribir `effect_hold_ms` con duraciones reales; añadir `effect_priority`, `audio_oneshot`, holds de POWER/MENU; validar cota de `sfx`.
2. `src/core/pac_game.h`: campos `audio_oneshot`, `siren_grace_ms`; `PAC_LEVEL_CLEAR_MS 5400`.
3. `src/core/game.c`: `update_siren` (respawn loop + fright→CHASE + thresholds 85/61/12); `pac_sound_play` reset en `start_new_game`; quitar `g->siren=` directo de `pac_start_level`; quitar POWER de `spawn_fruit_if_needed`; MENU en menú/attract; `pac_settings_apply` reset de siren; foco/minimizado paran loop; `restore_continue` resetea audio; `game_tick` limpia `audio_oneshot`; gracia anti-stutter.
4. `src/core/game_entities.c`: quitar las 2 emisiones `PAC_GAME_EVENT_GHOST_RESPAWN` (si se adopta el estado en `update_siren`).
5. `src/platform/linux/platform_linux.c`: `pcm_stop()` en rama sintetizada de `pac_audio_loop`.
6. `src/platform/sereos/platform_sereos.c`: `pcm_start(sfx, 0)` en `pac_audio_play`; `typedef` de comprobación del enum.
7. `tests/mock_platform.c/.h`: añadir `mock_audio_loop_variant` si se adopta la API de variantes; tests nuevos de secuencia (extra life, respawn, menú, hold).
8. `assets/` + `tools/gen_pacman_res_assets.py`: integrar `intermission.wav` (slot 10, 2 trozos), `loop[15]=0` (o dejarlo, si el player no lo honra); `assets/res_original/intermission.wav`; regenerar `sfx_res.c/h`.
9. Docs: `docs/GAME.md:90-93` (audio definitivo 11 WAV, intermission sí, MENU/POWER/GAME_OVER sintetizados), `assets/sfx_res.h` cabecera, `docs/AUDIT_RESOURCES.md` §12.4, `README` si lista sonidos.

**Tests a actualizar:** `tests/core_tests.c:392` (espera `AUDIO_POWER` como last play: sigue valiendo, ya que `pac_audio_loop` no actualiza `last_play`), `:842-863` (START 1 vez, sigue), añadir: EXTRA_LIFE sobrevive al waka; GHOST_RESPAWN se pide al haber ojos; FRIGHT usa slot 12; MENU se pide en menú; POWER hold; pausa/foco; toggle sonido.

---

## 7. Evidencia del arnés (resumen; log completo en `harness-out.txt`)

Reproducción: se copió `tests/mock_platform.c` a un fichero temporal y se sustituyeron las 6 funciones `pac_audio_*` por versiones que registran `{ms, play|loop|stop_loop|stop, sfx}` (≈30 líneas); se compiló el **núcleo real** con:

```
cc -O2 -std=c99 -Iinclude -Isrc/core -Isrc/render -Iassets -Itests \
   harness.c probe_platform.c tests/legacy_font.c tests/legacy_font_data.c \
   src/core/*.c src/render/*.c assets/*.c -lm
```

Hechos verificados (40/40 comprobaciones):
- B: START 1 vez, `hold≈4500`; sirena HUNT arranca a los 4500 ms.
- C: 3 dots → WAKA1/WAKA2/WAKA1 (alternancia correcta, sin duplicados) y **3 STOP_LOOP + 3 LOOP** de sirena (reinicio por dot).
- D: `PLAY EXTRA_LIFE` + `PLAY WAKA` en el mismo ms y `audio_hold_ms=70` (el 900 de EXTRA_LIFE se pisa).
- E: `PLAY POWER` seguido de `LOOP SIREN_FRIGHT` en el tick siguiente (separación 10 ms).
- F/O: `GHOST_RESPAWN` jamás se pide, ni al comer fantasma ni al volver los ojos.
- G: al aparecer la fruta se pide POWER junto al WAKA del mismo tick.
- H: pausa para la sirena y reanudar la re-arranca.
- I: OFF→ON deja `audio_ok=1`, `g->siren=HUNT` y **0 llamadas de loop** (sirena muda).
- J: DEATH 1 vez; al agotar vidas GAME_OVER 1 vez (sintetizado).
- K: LEVEL_CLEAR 1 vez (sin WAV); transición a nivel 2 sin START.
- L/L2: sin foco el loop no se para; al recuperarlo no se rearma.
- M: muerte con vidas restantes → sirena vuelve a los 4300 ms exactos (2800 animación + 1500 READY).
- N: `PAC_LEVEL_CLEAR_MS=1400` < intermission 5204 ms.

<!-- fin del informe -->
