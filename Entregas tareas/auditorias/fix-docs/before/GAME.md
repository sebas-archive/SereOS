# PAC-MAN SereOS - mecanicas y motor

Documento tecnico del juego. La logica es unica y se comparte entre los
backends SereOS y Linux (`src/core` + `src/render`).

## Estados

`MENU` -> `INSTRUCTIONS` / `RECORD` / `PLAYING` -> `PAUSED` -> `PLAYING` |
`GAMEOVER` | `LEVEL_CLEAR` -> `PLAYING` (siguiente nivel).

- **Menu**: Jugar, Instrucciones, Record, Volver al escritorio. Flechas/WASD
  mueven la seleccion, Enter confirma, raton hace clic, Esc cierra.
- **Pausa**: Esc/Enter continua, R reinicia, Q vuelve al titulo.
- **Game over**: Enter reintenta, Esc cierra.
- **Nivel completado**: tras 2.4 s pasa al siguiente nivel (dots y power
  restaurados, casa reajustada).

Los seriales de QA (COM1 en SereOS, stderr en Linux) son `GAME_MENU`,
`GAME_START`, `GAME_PAUSE`, `GAME_OVER`, `GAME_WIN`, `GAME_EXIT`.

## Laberinto y reglas

- 28x31 tiles de 16x16 px (448x496 px). 240 dots (10 pts) + 4 power pills
  (50 pts), 2 tuneles laterales con wrap y casa de fantasmas.
- Pac-man aparece en (13,23); velocidad base 150 px/s escalada por nivel,
  movimiento en punto fijo Q8.8 y giro solo si la direccion es valida.
- 3 vidas, vida extra a 10.000 puntos, record persistente, niveles infinitos
  (tabla de 21 niveles + valores por defecto).

## Fidelidad a Paku-Paku (decisiones M1)

- Un unico laberinto real (28x31, 240 dots, 4 power pills); 21 configuraciones
  y L22+ = L21. No se inventan layouts.
- Salida del pen: L1 Pinky 0, Inky 30, **Clyde 90** dots comidos; L2 Clyde 50;
  L3+ todos al inicio. Tras morir: +7/+17/+32 dots. Si Pac-Man no come:
  liberacion cada 4 s (nivel <5) o 3 s (nivel >=5).
- Frightened: velocidad GhostSpeed/2+10 (47,5/52,5/57,5 %), objetivo de tile
  pseudoaleatorio (no direccion pura), e inversion solo fuera del pen; en
  niveles sin frightened (fright=0) los fantasmas solo invierten.
- Las fases scatter/chase no se reinician al morir; READY 1,5 s por nivel y
  4,5 s al iniciar partida con sonido; fruta 10 s.
- El giro de Pac-Man usa buffer de direccion en el siguiente centro; no se
  reproduce la animacion diagonal de cornering de la referencia (documentado).
- v3: audio Game Start corregido (SDL encolaba el total del clip desde el
  primer chunk, leyendo memoria fuera del chunk; ahora encola chunk a chunk,
  Start una sola vez, hold para que la sirena no lo corte, efecto/loop
  estricto). Fantasma capturado se centra en su tile antes del BFS de ojos
  (antes podia quedar con dir=NONE si se comia entre tiles). La muerte NO
  resetea laberinto (solo posiciones/timers; dots/power/score/nivel/frutas se
  conservan): test de regresion y seriales `PAC_DEATH/LIFE_START/PAC_STATS`
- Controles: flechas/WASD y ademas Z/X (referencia) para izquierda/derecha.

## Fantasmas (Pac-Man Dossier)

- **Blinky** (rojo): objetivo = tile de Pac-man. **Pinky** (rosa): 4 tiles
  delante (con el bug de mirar arriba incluido). **Inky** (cian): vector
  `2*(pivote - Blinky)`. **Clyde** (naranja): persigue si esta a >8 tiles,
  si no vuelve a su esquina.
- Decision en interseccion: direccion valida sin invertir que minimiza la
  distancia euclidea al objetivo; en frightened, direccion aleatoria valida.
- Modos scatter/chase con tablas por nivel (nivel 1: 7/20/7/20/5/20/5/inf),
  reverse al cambiar de modo, frightened 6 s nivel 1 bajando por nivel,
  velocidades 80/75/50/100 % (Pac/ghost/fright/ojos) y tunel al 40 %.
- Casa: salidas por contador de dots (Pinky 0, Inky 30, Clyde 60 en nivel 1)
  y temporizadores; ojos vuelven por BFS a la casa y se regeneran; comer
  fantasma asustado suma 200/400/800/1600.
- **Cruise Elroy**: Blinky acelera al quedar 20/10 dots.
- Colisiones: fantasma normal mata (animacion ~1.7 s), frightened se come,
  la cuarta comida termina el frightened.

## Fruta y puntuacion

- Fruta a los 70 y 170 dots, 10 s en pantalla. Hay 5 frutas en ciclo por
  nivel, indice `(nivel-1) % 5`, con valores 100/300/500/700/1000:
  nivel 1 CEREZA (100), 2 FRESA (300), 3 NARANJA (500), 4 MANZANA (700),
  5 UVAS (1000), 6 vuelve a CEREZA (100), y asi sucesivamente.
- Panel FRUTAS: sprite + "xN" por cada tipo comido, despues "TOTAL: N";
  mientras no se haya comido ninguna muestra "Ninguna aun". Junto a NIVEL se
  dibuja la llave dorada como icono decorativo (no es fruta ni da puntos).
- Dots 10, power 50, fantasma 200/400/800/1600, fruta por nivel, vida extra
  a 10.000. El record se guarda al superar la marca y al cerrar.

## Menus, settings y audio

- Attract (PAC-MAN SereOS, CHARACTER/NICKNAME, HIGH SCORE, PRESS START),
  menu principal de 6 opciones, pausa de 5 opciones, game over de 3 opciones,
  ajustes (sonido y pantalla completa, persistidos con claves
  `sound/fullscreen/classic` en storage), continuar partida guardada en la
  sesion, F11 pantalla completa.
- Audio definitivo: PCM u8 mono 11025 de los 11 WAV de Res en Linux (SDL,
  one-shots y loops) y SereOS (SB16 con trozos <=32 KiB y cola en
  `pac_audio_update`); slots sin WAV usan la sintesis existente. Slots
  nuevos: `PAC_SFX_LEVEL_CLEAR` (10, `intermission.wav`, one-shot en 2 trozos)
  y `PAC_SFX_GHOST_RESPAWN` (15; PCM con periodo de bucle, flag loop=0 por
  defecto: el bucle se pide con `pac_audio_loop`).
- Diferencias documentadas: no hay replay `.pmg`, demo automatica de
  AttractMode.pmg, modo testing ni overlay de IA; el estilo clasico/moderno
  de la referencia no se aplica (settings solo sonido/fullscreen).

## Render compartido

- Laberinto pre-renderizado a un buffer RGB32 (448x496) y blit por frame;
  sprites RGB565 originales (`assets/sprites.c`, simbolos `pacasset_*`).
- HUD lateral (o compacto en ventanas pequenas): PUNTUACION, RECORD, VIDAS,
  FRUTAS, NIVEL y ESTADO (READY/FRIGHTENED/CHASE/SCATTER/PAUSA).
- Menus/pantallas con tipografia arcade Press Start K (atlas 8x16) para
  titulos/menu/HUD, Inter para textos que el atlas no cubre; tarjetas y
  acentos del tema SereOS.
- Identidad visible exacta: **PAC-MAN SereOS** (menu, HUD, titlebar, app_t.name
  y ventana Linux). app_t.id sigue siendo `game`.

## Backends

- **SereOS**: `src/platform/sereos` implementa `pac_platform.h` con gfx_*,
  text_*, input_*, timer_*, audio_*, fs_*, serial_*, kmalloc y window_*;
  `game_app.c` exporta `app_t *app_game(void)` y usa una tarea cooperativa.
- **Linux**: `src/platform/linux` usa SDL2, framebuffer software ARGB8888
  1024x768 (escalado entero), texto arcade + Inter, audio PCM de los WAV de
  Res (SDL) y record/settings en `$XDG_DATA_HOME/pacman-sereos/`.

## QA y capturas

El binario Linux permite forzar estados para capturas (sin jugar):

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./build/pacman-sereos \
    --smoke 4 --scene play --screenshot /tmp/play.ppm
```

Escenas: `attract`, `menu`, `settings`, `play`, `pause`, `gameover` (deja
record 1500 para probar persistencia), `victory` (nivel completado),
`frightened`. Capturas de referencia en `docs/captures/` y checks del core en
`tests/core_tests.c` (131 casos). `intermission.wav` no se usa (Paku no lo
usa).
