# CORRECCIÓN B6 — Docs obsoletas de audio (GAME.md + 2 READMEs)

- **Agente:** `wav-integrity` — **Tarea:** `task-11` (docs; residual BAJA cerrada).
- **Fecha:** 2026-11-20. **Solo docs**: no se tocó código ni assets (hashes de `sfx_res.c/.h` y generador sin cambios, `verify-docs.log` §5).

## 1. Cambios (estado actual corregido; histórico 1.7/1.8 intacto)

| Fichero | Antes | Después |
|---|---|---|
| `Pac-man SereOS/README.md:13-20` | "PCM u8 11025" genérico, "fallback sintetizado; QEMU pendiente", "131 checks" | 11 WAV → PCM (intermission como LEVEL_CLEAR), fallback para MENU/POWER/GAME_OVER, validado en QEMU; **209 checks** |
| `Pac-man SereOS/README.md:58` | `make test # 131 checks` | **209 checks** |
| `Pac-man SereOS/README.md:176-181` | "10 WAV … (intermission excluido); fallback sintetizado para slots sin WAV" | **11 WAV** (intermission = LEVEL_CLEAR slot 10, 5,204 s, 2 trozos); sirenas 13 normal / 12 frightened (14→12); GHOST_RESPAWN (15) por `pac_audio_loop`; sintetizados 1/5/11 |
| `Pac-man SereOS/README.md:196-197` | "El audio Linux es sintesis simple" (falso) | PCM u8 11025 de los 11 WAV (sin música); misma semántica Linux/SereOS; síntesis solo en slots sin clip |
| `docs/GAME.md:136` | "(194 casos)" | **209 casos** (además de la sección de audio corregida en B6: 11 WAV, LEVEL_CLEAR, 1/5/11 sintetizados, 14→12, GHOST_RESPAWN loop) |
| `README.md` (raíz) `:142/:166/:193/:230` | 194 | **209** (make test, QA, tabla de pruebas y changelog 1.9) |

**Histórico conservado a propósito:** filas `1.7` ("10 WAV", 107 checks) y `1.8` (131 checks) del changelog raíz, correctas para esas versiones.

## 2. Verificación (`verify-docs.log`)

- **Grep global** en `Pac-man SereOS/README.md`, `README.md` y `Pac-man SereOS/docs/GAME.md` de `10 WAV`, `intermission excluido`, `no se usa…intermission`, `194`, `131`, `1 WAV no usado`, `slots sin WAV`: **0 coincidencias de estado actual**. Único hit del patrón "131": `README.md:204` (`1316,7 Hz`, una frecuencia del test de audio VM; falso positivo, no es recuento de checks). Las filas históricas 1.7/1.8 se excluyen conscientemente.
- **Realidad medida:** `audit/fix-core/make-test.log` → `checks=209 failures=0`; `sfx_res.h` → 11 WAV, slots `2,3,4,6,7,8,9,10,12,13,15`; `sfx_res.c` → total 184.411 B, LEVEL_CLEAR 2 trozos, loop `[12]=[13]=1`, `[15]=0`; `game.c` frightened→12 y respawn→`PAC_SFX_GHOST_RESPAWN`; `res_original` = 11 WAV.
- Diffs: `PROJECT_README.md.diff` (57 líneas), `README.md.diff` (62), `GAME.md.diff` (27); hashes antes/después en `verify-docs.log` §4.

## 3. Evidencias (`audit/fix-docs/`)

`REPORT.md`, `PROJECT_README.md.diff`, `README.md.diff`, `GAME.md.diff`, `before/{PROJECT_README,README,GAME}.md`, `verify-docs.log`.
