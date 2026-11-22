# PAC-MAN SereOS

Videojuego arcade **original** del proyecto final SereOS, con **una sola
logica compartida** y **dos backends**: SereOS (nativo, freestanding) y Linux
(SDL2). Entrega privada/academica: usa recursos de `Res` (arte/audio arcade)
con atribucion y aviso de no redistribucion publica, y conserva el arte propio
como fallback. Tipografia arcade Press Start K + Inter/JetBrains Mono de
respaldo.

> Estado (2026-11-20): **version definitiva COMPLETA** (Fases 2/3/4). Backend
> Linux SDL2 (`build/pacman-sereos`) y libreria SereOS freestanding
> (`build/sereos/libpacman.a`, exporta `app_t *app_game(void)`). Incluye:
> assets privados de `Res` (16x16, fuente arcade Press Start K y 11 WAV -> PCM
> u8 11025, con `intermission` como LEVEL_CLEAR), audio PCM real en Linux y por
> SB16 en SereOS (fallback sintetizado para MENU/POWER/GAME_OVER; validado en
> QEMU), F11/fullscreen,
> menus arcade (attract, principal, pausa, game over, configuracion,
> continuar) y nombre visible exacto **PAC-MAN SereOS** en app_t, ventanas,
> menu, HUD y docs. `make linux`, `make sereos` y `make test` pasan sin
> warnings (209 checks de core + 7/7 pantallas smoke); la integracion final en
> la ISO la hace kernel-sys.
>
> Limitaciones honestas: no se implementan el replay `.pmg`/demo automática
> de `AttractMode.pmg`, el modo testing/overlay de IA ni el estilo
> clasico/moderno (settings solo sonido/fullscreen); Continuar solo conserva
> partida dentro de la sesion.

## Arquitectura en una frase

`src/core` (maquina de estados, laberinto, entidades, IA, input, audio events)
+ `src/render` (pantallas y HUD compartidos) + `src/platform/{sereos,linux}`
(primitivas, input, audio, tiempo, persistencia). El nucleo nunca incluye
headers de SereOS ni SDL; solo [`include/pac_platform.h`](include/pac_platform.h).

## Estructura

```
include/            contrato pac_platform + API pacman + tokens visuales
src/core/           logica del juego (sin plataforma)
src/render/         menús, HUD, overlays y kit visual compartido
src/platform/sereos app_t *app_game(void) + adaptador al OS
src/platform/linux  bucle SDL2, framebuffer software, audio, record
assets/             sprites RGB565 originales, fuentes OFL, preview
tools/              generadores originales de sprites/fuentes
tests/              harness de core (mock platform) + smoke Linux
docs/               arquitectura, integracion, notas del juego
```

## Build y ejecucion (Linux, objetivo por defecto)

Dependencias: `gcc`, `make`, `pkg-config`, SDL2 (`sdl2-config`/`pkg-config
sdl2`). En CachyOS/Arch: `sudo pacman -S --needed base-devel sdl2`.

```sh
make                # compila build/pacman-sereos
./run.sh            # comprueba SDL2, construye si hace falta y ejecuta
./build/pacman-sereos
make test           # 209 checks de core + 7/7 smoke (attract/menu/settings/play/pause/gameover/victory)
```

Ventana de 1024x768 con escalado entero. Los controles, estados y record son
los mismos que en SereOS.

## Build SereOS (libreria para el OS)

```sh
make sereos         # -> build/sereos/libpacman.a (app_t *app_game(void))
make sereos OS_DIR="/ruta/a/sistema operativo"
```

No usa SDL ni libc del host; se compila con las flags freestanding del kernel.
La integracion (excluir `apps/game/` y enlazar la libreria) la hace kernel-sys
siguiendo [`docs/INTEGRATION.md`](docs/INTEGRATION.md).

## Menus y estados (version definitiva)

- **Attract**: PAC-MAN SereOS, tabla de personajes/nicknames, HIGH SCORE y
  PRESS START; Enter/Espacio abre el menu principal.
- **Menu principal**: Iniciar partida, Continuar (si hay partida guardada en
  la sesion), Records, Instrucciones, Configuracion, Salir.
- **Pausa**: Continuar, Reiniciar, Configuracion, Menu principal, Salir.
- **Game over**: Reintentar, Menu principal, Salir.
- **Ajustes**: sonido on/off, pantalla completa on/off; persistidos en
  `$XDG_DATA_HOME/pacman-sereos/` (Linux) o RAMFS (SereOS).
- **Nivel completado** con transicion; READY!; `1UP`/`HI`, vidas, frutas
  comidas y nivel en el HUD; la llave dorada es un icono decorativo junto a
  NIVEL (no es fruta).
- No se implementa replay `.pmg`/demo automatica de `AttractMode.pmg` ni el
  modo testing de la referencia: documentado como diferencia (no simulado).

## Controles

| Accion | Teclas |
|---|---|
| Mover a Pac-man | Flechas o WASD |
| Confirmar en menus | Enter |
| Pausa / continuar | Esc |
| Reintentar / reiniciar partida | R |
| Volver al titulo (en pausa) | Q |
| Volver al escritorio / salir | Esc en menu o game over |
| Pantalla completa | F11 |
| Controles de referencia (opcional) | Z/X izquierda/derecha, suma a flechas/WASD |

## Estados forzados para QA (capturas sin jugar)

El binario Linux puede arrancar en cualquier pantalla y guardar un PPM del
ultimo frame, incluso sin display (SDL dummy):

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/pacman-sereos \
    --smoke 4 --scene pause --screenshot /tmp/pause.ppm

# escenas: attract | menu | settings | play | pause | gameover | victory | frightened
#          gamestart | ghostcapture | death   (escenas de QA v3)
# `gameover` deja record 1500 para comprobar persistencia
```

Capturas de referencia en [`docs/captures/`](docs/captures/) (9 ficheros):

- `attract.png` — pantalla attract/PRESS START.
- `menu.png` — menu principal.
- `settings.png` — configuracion (sonido/pantalla completa).
- `play.png` — partida con HUD arcade.
- `pause.png` — pausa con opciones.
- `gameover.png` — game over (record 1500).
- `victory.png` — nivel completado.
- `frightened.png` — power pill/frightened.
- `menu_record_1500.png` — menu tras persistir el record 1500.

## Marcadores serial de QA v3

Ademas de `GAME_MENU/START/PAUSE/OVER/WIN/EXIT`, el core emite por el log de
plataforma (COM1 en SereOS, stderr en Linux): `LEVEL_START <n>`,
`GHOST_EATEN <id>`, `GHOST_RETURNED <id>`, `GHOST_REVIVED <id>`,
`PAC_DEATH`, `LIFE_START <vidas>` y `PAC_STATS dots=.. power=.. score=..
level=.. lives=..` en los hitos. Escenas QA: `--scene gamestart`,
`--scene ghostcapture` (fuerza captura real) y `--scene death` (come 10 dots
y fuerza muerte para demostrar que el laberinto no se resetea).

## Record persistente (Linux)

- Ruta: `$XDG_DATA_HOME/pacman-sereos/record.txt`
  (fallback `~/.local/share/pacman-sereos/record.txt`, y si no hay HOME
  `./pacman-sereos-record.txt`).
- Se guarda en game over, nivel completado y al cerrar. Para probarlo:
  `./run.sh --scene gameover` y volver a abrir; el menu muestra HIGH SCORE 1500.

## Contenido del juego

- Laberinto 28x31 (448x496 px) con 240 dots y 4 power pills, dos tuneles con
  wrap, casa de fantasmas y checkpoint de nivel por dots.
- Pac-man y 4 fantasmas con personalidades reales (Blinky, Pinky, Inky, Clyde),
  modos scatter/chase con la tabla del Pac-Man Dossier, frightened, ojos de
  vuelta a la casa, Cruise Elroy y contadores de salida de la casa.
- 3 vidas, puntuacion, vida extra a 10.000, 5 frutas en ciclo por nivel
  (CEREZA, FRESA, NARANJA, MANZANA, UVAS; valores 100/300/500/700/1000),
  record persistente, pause, game over, nivel completado y niveles infinitos
  (datos del 21 en adelante). Las frutas campana y galaxian quedan eliminadas;
  la llave dorada es solo un icono decorativo junto a NIVEL, no una fruta.
- Render compartido: menu/titulo, instrucciones, record, HUD, pausa, game over
  y nivel completado con el sistema de diseno de SereOS.

## Assets y licencias

- Sprites por defecto: derivados **privados** de `Res` (frutas, cuerpo de
  fantasmas recoloreado, ojos) en `assets/sprites_res.c`; Pac-Man, vida y la
  llave decorativa del indicador de NIVEL siguen siendo arte propio.
  Originales en `assets/res_original/` y aviso en
  [`assets/LICENSE_RES.md`](assets/LICENSE_RES.md): uso privado/academico, no
  redistribucion publica. El arte original queda como fallback con
  `-DPACMAN_USE_RES_ASSETS=0`.
- Fuente arcade: Press Start K (codeman38) en `assets/font_arcade.c`; aviso en
  [`assets/fonts/LICENSE_ARCADE.md`](assets/fonts/LICENSE_ARCADE.md). Inter/
  JetBrains Mono siguen disponibles para texto no cubierto
  ([`assets/fonts/LICENSE.md`](assets/fonts/LICENSE.md)).
- Audio: **11 WAV** de `Res` convertidos a PCM u8 mono 11025 en
  `assets/sfx_res.c`: `intermission.wav` incluido como **LEVEL_CLEAR (slot 10,
  5,204 s, 2 trozos de <=32 KiB)**; sirenas 13 (hunted, normal) y 12 (hunter,
  frightened; el slot 14 se remapea al 12); `GHOST_RESPAWN` (15) buclea via
  `pac_audio_loop`. Slots sin clip en Res (1 MENU, 5 POWER, 11 GAME_OVER) usan
  el fallback sintetizado.

## Documentacion

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): capas, contrato de
  plataforma, refactor de los modulos, backends, tiempo, input, build, tests.
- [`docs/INTEGRATION.md`](docs/INTEGRATION.md): enlace de `libpacman.a` en el
  kernel, simbolos, flags y comprobaciones QA.
- [`docs/GAME.md`](docs/GAME.md): mecanicas, IA, niveles y puntuacion (se
  completa con la implementacion).

## Limites conocidos (estado de diseno)

- La implementacion del componente aun no esta copiada: depende de que
  kernel-sys confirme `sistema operativo/` estable.
- El audio usa PCM u8 mono 11025 de los 11 WAV de Res (sin musica de fondo):
  misma semantica de eventos en Linux (SDL2) y SereOS (SB16); los slots sin
  clip en Res usan sintesis simple.
- El render usa un lienzo fijo de 1024x768 en Linux (escalado entero); en
  SereOS es el area de contenido de la ventana (880x560 nominales).
