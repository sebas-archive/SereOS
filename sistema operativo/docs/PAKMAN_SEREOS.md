# PAC-MAN SereOS — documentación del juego

**PAC-MAN SereOS** es el videojuego arcade del proyecto final SereOS. Vive en
el **componente independiente `../Pac-man SereOS/`** (carpeta hermana de
`sistema operativo/`), con **una sola copia** de la lógica y el render y dos
backends: **SereOS nativo** (freestanding i686) y **Linux** (SDL2). El sistema
operativo lo integra mediante una `app_t` (id `game`, icono `game`, ventana
880x560) que se abre con **F4**; el nombre visible exacto —titlebar, topbar,
dock, menú y Acerca de— es **«PAC-MAN SereOS»**. El OS enlaza
`../Pac-man SereOS/build/sereos/libpacman.a`; no contiene código del juego.

Versión integrada: **definitiva v3 (M2/M3/M4 + correcciones finales)**, con
*attract mode*, menús arcade, un único laberinto real con 21 configuraciones,
recursos privados de `Res` (arte en `Res` + fuente arcade + PCM) y audio PCM
real por SB16. Correcciones v3: audio Game Start sin corte del chunk inicial,
respawn de fantasmas entre tiles y muerte que conserva laberinto, dots, score
y nivel. Verificación del componente: **131/131 checks de core + 7/7 pantallas
smoke** sin warnings.
Auditorías de referencia del componente:
[`AUDIT_PAKUPAKU.md`](../../Pac-man SereOS/docs/AUDIT_PAKUPAKU.md) (reglas y
mapa reales de Paku-Paku) y
[`AUDIT_RESOURCES.md`](../../Pac-man SereOS/docs/AUDIT_RESOURCES.md) (PNG/WAV/TTF
de `Res`, conversión y licencias).

> **Aviso de licencias:** los PNG/WAV de `Res` no incluyen licencia ni
> atribución y parecen material arcade de Pac-Man (Namco). Esta entrega es
> **privada/académica**: se usan con atribución y **no se autoriza su
> redistribución pública**. El arte propio del componente queda como fallback
> (`-DPACMAN_USE_RES_ASSETS=0`). Ver
> [`LICENSE_RES.md`](../../Pac-man SereOS/assets/LICENSE_RES.md) y
> [`LICENSE_ARCADE.md`](../../Pac-man SereOS/assets/fonts/LICENSE_ARCADE.md).

---

## 1. Arquitectura e integración

| Capa (en `Pac-man SereOS/`) | Responsabilidad |
|---|---|
| `src/core/` (`game.c`, `game_maze.c`, `game_entities.c`, `game_ai.c`, `game_input.c`, `game_audio.c`, `pac_util.c`) | máquina de estados, reglas, laberinto, entidades, IA, input y eventos de audio; **sin headers del OS ni SDL** |
| `src/render/` (`game_render.c`, `pac_ui.c`, `pac_theme.c`) | pantallas compartidas: attract, menús, HUD, overlays, pausa, game over, nivel completado |
| `src/platform/sereos/` (`game_app.c`, `platform_sereos.c`) | `app_t *app_game()` (ventana/tarea/eventos) y adaptador al OS (`gfx_*`, `text_*`, `input_*`, `audio_*`/`sb16_*`, `timer_*`, `fs_*`, `kmalloc`, `serial`) |
| `src/platform/linux/` | backend SDL2 (misma lógica y render; sin headers del OS) |
| `assets/` | sprites RGB565, fuente arcade Press Start K, PCM u8 de `Res`, originales en `res_original/` y previews |
| `include/` | contrato `pac_platform.h`, API `pacman.h`, tokens visuales |

Integración en el OS (sin duplicación):

```bash
# componente
cd "/home/t1an/Descargas/sereos02/Pac-man SereOS"
make              # Linux SDL2 -> build/pacman-sereos
make sereos       # build/sereos/libpacman.a (freestanding, app_game)
make test         # core + smoke Linux (131/131 checks + 7/7 pantallas)

# OS
cd "../sistema operativo"
make game-lib     # recompila el componente (OS_DIR=...)
make clean && make
```

`Makefile` del OS: `GAME_DIR` (por defecto `../Pac-man SereOS`), target
`game-lib`, `game-clean`; `sereos.bin` enlaza
`"$(GAME_DIR)/build/sereos/libpacman.a"` **después de los objetos y antes de
`-lgcc`**. `apps/apps.c` solo llama a `app_game()`; `apps/game/` ya no existe.
Ver [`BUILD.md`](BUILD.md) e
[`INTEGRATION.md`](../../Pac-man SereOS/docs/INTEGRATION.md).

## 2. Estados y menús

- **Attract** (estado inicial): título «PAC-MAN SereOS», tabla de personajes
  (SHADOW BLINKY, SPEEDY PINKY, BASHFUL INKY, POKEY CLYDE), HIGH SCORE y
  **PRESS START**. `Enter`/`Espacio` abre el menú principal.
- **Menú principal** (6 opciones): Iniciar partida, Continuar (si hay partida
  guardada en la sesión), Records, Instrucciones, Configuración, Salir.
- **Pausa** (5 opciones): Continuar, Reiniciar, Configuración, Menú principal,
  Salir.
- **Game over** (3 opciones): Reintentar, Menú principal, Salir.
- **Ajustes**: sonido on/off, pantalla completa on/off, controles clásicos;
  persistidos en RAMFS (`/home/pacman_sound.cfg`, `..._fullscreen.cfg`,
  `..._classic.cfg`).
- **Nivel completado** con transición, **READY!** (1,5 s por nivel, 4,5 s al
  iniciar partida con sonido), HUD con `1UP`/`HI`, vidas, frutas y nivel.

Marcadores de QA por COM1: `GAME_MENU` (attract y menú), `GAME_START`,
`GAME_PAUSE`, `GAME_OVER`, `GAME_WIN`, `GAME_EXIT`, más los hitos v3
`LEVEL_START <n>`, `GHOST_EATEN/RETURNED/REVIVED <id>`, `PAC_DEATH`,
`LIFE_START <vidas>` y `PAC_STATS dots=.. power=.. score=.. level=.. lives=..`;
el escritorio añade `APP_OPEN:game`/`APP_CLOSE:game`. Escenas de QA del
binario Linux: `--scene gamestart`, `--scene ghostcapture` (fuerza la captura
real de un fantasma: ojos → retorno → reaparición) y `--scene death` (come
dots y fuerza la muerte para evidenciar que el laberinto no se reinicia).

### Controles

| Acción | Teclas |
|---|---|
| Mover a Pac-Man | Flechas o WASD (además Z/X de la referencia) |
| Confirmar en menús | Enter (Espacio en attract) |
| Pausa / continuar | Esc |
| Reintentar / reiniciar | R |
| Volver al título (en pausa) | Q |
| Volver al escritorio / salir | Esc en menú o game over |
| Pantalla completa | F11 |

## 3. Laberinto y reglas (auditadas)

- **Un único layout real** de **28x31 tiles** de 16x16 px (448x496 px):
  **240 dots** (10 pts) + **4 power pills** (50 pts), dos **túneles** laterales
  con wrap y **casa de fantasmas** con puerta. No se inventan mapas: el mapa
  proviene de la tabla única de Paku-Paku
  ([`AUDIT_PAKUPAKU.md`](../../Pac-man SereOS/docs/AUDIT_PAKUPAKU.md) §2).
- **21 configuraciones reales** (niveles 1..21); **L22+ = L21** (tabla de
  `cMazeLevel`, no hay más layouts).
- Pac-Man: posición Q8.8, velocidad base 150 px/s escalada por nivel, giro solo
  en dirección válida con buffer en el siguiente centro; 3 vidas y vida extra
  al cruzar 10.000 puntos (una vez).
- **Casa/pen**: salidas por contador de dots (L1: Pinky 0, Inky 30, Clyde 90;
  L2: Clyde 50; L3+: todos al inicio), +7/+17/+32 dots tras morir, y
  liberación por tiempo si Pac-Man no come (4 s niveles <5, 3 s niveles ≥5).
- **Frightened**: velocidad `GhostSpeed/2+10` (47,5/52,5/57,5 %), objetivo de
  tile pseudoaleatorio, inversión solo fuera del pen; power pills de 6 s en
  nivel 1 bajando por nivel; duración y parpadeo final.
- **Scatter/Chase** con la tabla del Pac-Man Dossier; no se reinician al morir.
- **Cruise Elroy** de Blinky al quedar 20/10 dots; velocidades
  80/75/50/100 % (Pac/fantasma/fright/ojos) y túnel al 40 %.
- **Fruta** a los 70 y 170 dots (9-10 s), 8 frutas de `Res`, valores
  100/300/500/700/1000/2000/3000/5000 según nivel e historial de 8 en el HUD.
- Puntuación: dots 10, power 50, fantasmas 200/400/800/1600, fruta por nivel,
  vida extra a 10.000. Récord persistente en RAMFS
  (`/home/pacman_sereos.hi`), recuperado al abrir el juego.

## 4. IA de los fantasmas

Objetivos reales por personalidad (Pac-Man Dossier): Blinky persigue el tile de
Pac-Man; Pinky apunta 4 tiles por delante (con el bug de mirar arriba); Inky
usa el vector `2*(pivote − Blinky)`; Clyde persigue si está a más de 8 tiles y
si no vuelve a su esquina. En intersecciones se elige la dirección válida sin
invertir que minimiza la distancia euclidiana (orden arriba/izquierda/abajo/
derecha); en *frightened* la elección es pseudoaleatoria. Ojos comidos vuelven
a la casa por BFS y se regeneran. Detalle y citas del código original:
[`AUDIT_PAKUPAKU.md`](../../Pac-man SereOS/docs/AUDIT_PAKUPAKU.md) §5 y
[`GAME.md`](../../Pac-man SereOS/docs/GAME.md).

## 5. Audio

- **Recursos `Res`**: 10 WAV convertidos a **PCM 8 bits sin signo, mono,
  11025 Hz** en `assets/sfx_res.c` (intermission excluido): menu, start,
  waka1/waka2, power, eat_ghost, eat_fruit, death, extra_life, level_clear,
  game_over, sirenas chase/hunt/fright y respawn de ojos.
- **SereOS**: el adaptador usa **SB16 real** (`drivers/sb16.h`, PCM por DMA en
  trozos ≤32 KiB con cola en `pac_audio_update`) cuando está presente; si no,
  usa la capa `audio/` de SereOS (fallback sintetizado y altavoz del PC).
- En Linux: PCM real con SDL2 y fallback sintetizado; misma semántica de
  eventos. La música/`intermission.wav` no se usa (no hay streaming).

Ver [`AUDIO.md`](AUDIO.md) para la capa de audio del OS.

## 6. Recursos, licencias y atribución

- **Uso real de `Res`**: 10 PNG (8 frutas + `ghost1/ghost2` recoloreados y
  recompuestos con ojos), **10 WAV** y la fuente **Press Start K**
  (`prstartk`). Recursos presentes pero no usados: `retroghost1/2`,
  `Clydeeghost`, `dead`, `Key-icon`, `intermission.wav`, `atari full.ttf`.
  Inventario, conversión y métricas:
  [`AUDIT_RESOURCES.md`](../../Pac-man SereOS/docs/AUDIT_RESOURCES.md).
- **Licencias**: PNG/WAV de `Res` **sin licencia ni atribución**, con apariencia
  de material arcade de Pac-Man (Namco); TTF sin licencia acreditada. Se usan
  **solo en esta entrega privada/académica con atribución**, **sin
  redistribución pública**. Press Start K: aviso en
  [`LICENSE_ARCADE.md`](../../Pac-man SereOS/assets/fonts/LICENSE_ARCADE.md);
  Inter/JetBrains Mono (SIL OFL 1.1) para el resto del texto.
- El arte propio original del componente se conserva como **fallback**
  (`-DPACMAN_USE_RES_ASSETS=0`); PAC-MAN SereOS no reclama autoría sobre los
  recursos de `Res`.
- *Pac-Man* es una marca de Bandai Namco; este proyecto académico no está
  afiliado. La lógica clásica se estudió con documentación pública y el clon
  VB6 Paku-Paku (sin redistribuir su código ni recursos fuera del uso
  descrito).

## 7. Verificación de integración (QEMU)

Sobre la ISO final de SereOS (i386, KVM, 1024x768):

- `F4` → `APP_OPEN:game` + `GAME_MENU`: **attract** con PRESS START; topbar,
  titlebar y tooltip del dock con el nombre exacto **«PAC-MAN SereOS»**.
- `Enter` → menú principal arcade (`GAME_MENU`); `Enter` → `GAME_START`;
  partida con READY!, dots, 4 fantasmas y power pills.
- `Esc` → `GAME_PAUSE` (menú de pausa); `Esc` reanuda; `Esc`+`Q`+`Esc` vuelve
  al escritorio con `GAME_EXIT` y `APP_CLOSE:game`.
- **0** `SEREOS_EXCEPTION`/`SEREOS_PANIC`; escritorio recuperado sin restos.
- **Audio SB16**: QEMU con `-audiodev wav,... -device sb16` captura PCM no
  silencioso del juego (4,58 s activos, peak 29.952 / 91,4 % FS, RMS 11.830 /
  36,1 % FS en la verificación de integración).
- Capturas y logs de la verificación en `/tmp/final_pacman` (regeneradas por
  QA en `docs/screenshots/` para la entrega final).

## 8. Diferencias y limitaciones conocidas

- **No** se implementa replay `.pmg` ni demo automática de `AttractMode.pmg`,
  ni el modo *testing* con IA aleatoria de la referencia: el attract es una
  pantalla de presentación y el juego no simula esa funcionalidad.
- No se reproduce la animación diagonal de *cornering* de Pac-Man.
- **Un solo laberinto real** (240 dots, 4 power pills) y **21
  configuraciones**; L22+ reutiliza L21 (como la referencia).
- **Ajustes**: la referencia no tiene menú de opciones funcional; SereOS añade
  un menú de ajustes (sonido/pantalla completa/controles) persistido en RAMFS,
  como extensión de producto.
- **Demo/attract**: no hay reproducción automática de partidas.
- Recursos `Res` con la restricción de licencia descrita (uso privado
  académico, no redistribución pública); sin esos recursos el juego compila y
  funciona con el arte propio y el audio sintetizado.
- Sin gamepad ni música en streaming; audio PCM 8 bits mono.

## 9. Documentación relacionada

- [`AUDIT_PAKUPAKU.md`](../../Pac-man SereOS/docs/AUDIT_PAKUPAKU.md) — auditoría
  técnica del clon VB6: mapa único, 21 niveles, IA, reglas, puntuación.
- [`AUDIT_RESOURCES.md`](../../Pac-man SereOS/docs/AUDIT_RESOURCES.md) — PNG,
  WAV y TTF de `Res`: inventario, conversión, prototipos y licencias.
- [`ARCHITECTURE.md`](../../Pac-man SereOS/docs/ARCHITECTURE.md) — capas y
  contrato de plataforma del componente.
- [`INTEGRATION.md`](../../Pac-man SereOS/docs/INTEGRATION.md) — enlace de
  `libpacman.a`, símbolos y flags.
- [`GAME.md`](../../Pac-man SereOS/docs/GAME.md) — mecánicas y motor.
- [`BUILD.md`](BUILD.md) y [`AUDIO.md`](AUDIO.md) — build del OS y capa de audio.
