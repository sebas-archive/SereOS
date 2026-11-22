# PAC-MAN SereOS - constantes de referencia extraidas de Paku-Paku

Todas las cifras provienen del codigo VB6 de referencia (lineas citadas) y se han
contrastado con **The Pac-Man Dossier** cuando aplica. Las tablas grandes estan en
`levels.csv`; el laberinto en `maze.txt` / `maze.c`; el generador en `gen_maze.py`
y `gen_levels.py`.

## 1. Convenciones del original

| Constante | Valor | Cita |
|---|---|---|
| ROWS (filas de gTiles) | 32 (se usan 1..31) | `modGameGlobals.bas:55` |
| COLS (columnas de gTiles) | 29 (se usan 1..28) | `modGameGlobals.bas:55` |
| Rejilla jugable | 28 x 31 tiles | `cMazeBuilder.cls:39-69` |
| SQ_SZ (px logicos por tile) | 8 | `modGameGlobals.bas:59` |
| gTileSize (px fisicos por tile al dibujar) | 29 por defecto | `Settings.ini:11`, `modMain.bas:148` |
| FPS | 60 | `modGameGlobals.bas:61` |
| FRAME_MILLISECONDS | 1000/60 = 16.6667 | `modGameGlobals.bas:62` |
| DEFAULT_SPEED | 1.25 px logicos/frame (= 75 px/s = 9.375 tiles/s al 100%) | `modGameGlobals.bas:60` |
| MAZE_BACKCOLOUR | vbCyan (cian) | `modGameGlobals.bas:63` |
| gTiles rango | `(-1 To COLS+1, ROWS)` = cols -1..30, filas 0..32 | `modGameGlobals.bas:57` |
| Superficie del laberinto | `(COLS+1) x (ROWS+1.5)` tiles = 30 x 33.5 | `cMazeBuilder.cls:20` |
| Direcciones | Up=1, Right=2, Down=4, Left=8 | `modGameGlobals.bas:20-25` |
| Flags de tile | Dot=16, PowerPill=32, Tunnel=64, Pen=128 | `modGameGlobals.bas:27-32` |
| Modos de fantasma | Scattering=-1, Frightened=0, Chasing=1 | `modGameGlobals.bas:41-45` |
| Personalidades | Shadow(Blinky), Speedy(Pinky), Bashful(Inky), Pokey(Clyde) | `modGameGlobals.bas:34-39` |
| Pared/void | tile 0 | `cMazeBuilder.cls:95,147` |

Nota de coordenadas: el codigo original es **1-based** en tiles (Col 1..28, Row 1..31).
`maze.c` entrega los datos **0-based** (`[fila-1][col-1]`); las citas de este
documento usan coordenadas VB 1-based salvo que se indique "0-based".

## 2. Velocidades (porcentajes y punto fijo)

Formula del original: `PixelIncrements = DEFAULT_SPEED * speed_percent / 100`
(`cPacMan.cls:99`, `cGhost.cls:63`).

- 100% = 1.25 px/frame = 75 px/s = 9.375 tiles/s (tiles de 8 px).
- Incremento entero por frame en unidades de 1/256 px = `round(pct * 3.2)`.
  Todos los porcentajes usados dan entero exacto: 80%->256, 90%->288, 95%->304,
  100%->320, 75%->240, 85%->272, 160%->512, 40%->128, 47.5%->152, 52.5%->168,
  57.5%->184, 105%->336.

| Nivel | Pac-Man | Pac (cazador) | Fantasma normal | Elroy1 (+5%) | Elroy2 (+10%) | Tunel | Asustado | Ojos | En pen |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 80% | 90% | 75% | 80% | 85% | 40% | 47.5% | 160% | 40% |
| 2-4 | 90% | 95% | 85% | 90% | 95% | 45% | 52.5% | 160% | 40% |
| 5-20 | 100% | 100% | 95% | 100% | 105% | 50% | 57.5% | 160% | 40% |
| 21+ | 90% | 100% | 95% | 100% | 105% | 50% | 57.5% | 160% | 40% |

Fuentes: `cMazeLevel.cls:124-132` (Pac/Ghost), `cGhost.cls:214-228` (tunel,
asustado, ojos, pen), `cGame.cls:585` (Pac cazador), `cMazeLevel.cls:78-83`
(Elroy +5/+10 via `Blinky.Speed`).

**Desviacion respecto al Dossier** (Tabla A.1): el arcade usa fantasma asustado
50%/55%/60%; Paku-Paku calcula `GhostSpeed/2+10` = 47.5/52.5/57.5 (2.5 puntos
mas lento). Tunel 40/45/50 coincide; Elroy coincide; velocidades normales coinciden.
Los ficheros `levels.csv` incluyen ambos datos y las columnas `*_inc256`.

Pausas de Pac-Man al comer: dot = 1 frame (`cGame.cls:569`), power pill = 3
frames (`cGame.cls:578`). Coincide con el Dossier ("one frame"/"three frames").

## 3. Movimiento de Pac-Man

| Elemento | Valor | Cita |
|---|---|---|
| Posicion | mX/mY en px logicos (Currency), init `col*8+4`, `fila*8+4` | `cPacMan.cls:24-31` |
| Direccion inicial | eLeft desde VB (14.5, 24) -> x=120, y=196 | `cGame.cls:316` |
| Wrap del tunel | `x > 30*8 (=240) -> 0`; `x < 0 -> 240` | `cPacMan.cls:156` |
| Ciclo de boca | angulo -= 15/frame; si <270 -> 360 (ciclo de 7 frames) | `cPacMan.cls:154` |
| Cambio de direccion | solo si el tile actual tiene salida; si es perpendicular inicia "cornering" | `cPacMan.cls:50-92` |
| Cornering | desliza en diagonal mientras el pre-turn lo permite; al cruzar medio tile alinea y gira | `cPacMan.cls:93-152` |
| Parada | al entrar en tile sin salida en la direccion actual: direccion=0 y snap al centro | `cPacMan.cls:144-151` |
| Colision con fantasma | mismo tile **o** |dx|<2 y |dy|<2 px (arregla el bug de "pasar a traves") | `cGame.cls:607-617` |
| Muerte | freeze 1.5 s (90 frames) antes de la escena | `cGame.cls:627` |
| Escena de muerte | 360->0 step 30 cada 65 ms; luego 40->0 step 2 cada 50 ms; +1 s | `cGame.cls:632-675` |
| READY | 1500 ms (4500 ms en el primer nivel con sonido) | `cGame.cls:329` |
| Vidas iniciales | 3 | `cGame.cls:55,65` |
| Vida extra | al cruzar 10.000 puntos (una vez) | `cGame.cls:690-699` |

## 4. Fantasmas: objetivo, decision y casa

### 4.1 Objetivos (tiles VB 1-based)

| Modo | Blinky/SHADOW | Pinky/SPEEDY | Inky/BASHFUL | Clyde/POKEY |
|---|---|---|---|---|
| Scatter | (col 26, fila -2) | (col 3, fila -2) | (col 28, fila 32) | (col 1, fila 32) |
| Chase | tile de Pac-Man | 4 tiles delante (con bug de UP: col-4) | vector: T=2 delante, objetivo=2*T-Blinky | si dist>8 -> Pac-Man; si dist<=8 -> scatter |
| Frightened | aleatorio `Int(ROWS*Rnd), Int(COLS*Rnd)` | idem | idem | idem |
| Ojos comidos | (col 15, fila 12) puerta | idem | idem | idem |

Citas: `cGhost.cls:420-436` (scatter/frightened), `cGhost.cls:441-470` (chase;
comentario `:414` reconoce el Dossier), `cGhost.cls:272` (objetivo de ojos),
`cGhost.cls:131-141` (posiciones de regeneracion dentro del pen: filas 16 y cols
13/15/17).

Reglas de calculo:
- Bug original de UP recreado: al calcular "4 delante" o "2 delante" con Pac-Man
  mirando arriba se resta tambien 4/2 a la columna (`cGhost.cls:457,467`).
- Inky usa la posicion actual de Blinky (`cGhost.cls:460`).
- Clyde mide distancia euclidiana `Sqr(dx^2+dy^2)` a Pac-Man (`cMaze.cls:60-62`).
- Blinky en Cruise Elroy ignora el scatter y persigue a Pac-Man (`cGhost.cls:423-426`).
- Scatter y chase comparten el mismo pathfinding; solo cambia el objetivo
  (Dossier, Target Tiles).

### 4.2 Decision en interseccion

- Mira **un tile por delante** en la direccion actual y elige alli (`cGhost.cls:177-189`).
- Prohibido invertir la marcha: excluye la direccion opuesta (`cGhost.cls:193-211`).
- Distancia euclidiana desde el tile candidato al objetivo; **orden de desempate:
  ARRIBA, IZQUIERDA, ABAJO, DERECHA** (`cGhost.cls:193-211`, strictly `<`).
  Coincide con el Dossier (up, left, down, right).
- En cada tile nuevo se replanifica la direccion (`cGhost.cls:116-117`).

### 4.3 Zonas con reglas especiales

- **Prohibido girar arriba** (excepto asustado) en tiles VB
  `(col,row) = (13,12), (16,12), (13,24), (16,24)` -> solo Left+Right
  (`cGhost.cls:242-245` y `:384-387`; 0-based: (12,11),(15,11),(12,23),(15,23)).
  Son las cuatro entradas verticales de los laterales del laberinto.
- **Tunel**: velocidad especial, siempre activa (`cGhost.cls:216-220`); pac no.
- **Pen**: cada fantasma tiene su propia coleccion de excepciones de tiles
  (`cGhost.cls:277-334`). Los tiles 13:15..17:16 y 15:13/15:14 forman el pen;
  la puerta es 15:12/15:13/15:14 (`OpenPenForExit`), y para entrar
  (`OpenPenForEntry`) se abren 15:12..15:15 en bajada y se enruta segun
  personalidad. Esto permite que cada fantasma entre/salga sin afectar a los demas.

### 4.4 Casa, liberaciones y Cruise Elroy

- Inicios (VB): Blinky (14.5, 12, Up), Pinky (14.5, 15, Down), Inky (12.5, 15, Up),
  Clyde (16.5, 15, Up) (`cGhosts.cls:46-51`). En px logicos:
  Blinky (120,100), Pinky (120,124), Inky (104,124), Clyde (136,124).
- Blinky empieza fuera del pen; su plan inicial es moverse a la izquierda
  (`cGhost.cls:32-37`).
- Libres por contador de dots al empezar nivel (`cGame.cls:195-208`):
  - dots restantes = 240: Pinky siempre; Inky si nivel>1; Clyde si nivel>2.
  - dots restantes = 210: Inky en nivel 1 (30 dots comidos).
  - dots restantes = 190: Clyde en nivel 2 (50 dots comidos).
  - dots restantes = 150: Clyde en nivel 1 (90 dots comidos).
- Tras perder una vida, contador global relativo (`cGame.cls:209-218`):
  Pinky a los 7 dots, Inky a los 17, Clyde a los 32.
- Temporizador de inactividad (`cGame.cls:231-239`): si no se come ningun dot,
  cada 4 s (niveles 1-4) o 3 s (nivel 5+) sale el fantasma mas preferente
  (orden Pinky, Inky, Clyde).
- Cruise Elroy: Blinky acelera +5% cuando quedan <=Elroy1 dots y +10% cuando
  quedan <=Elroy2 (`cGame.cls:227-229`); al liberarse Clyde tras una muerte se
  re-evalua (`cGame.cls:242-245`). Tabla por nivel en `levels.csv`.
- Los fantasmas comidos vuelven como "ojos" a 160% de velocidad; al llegar a su
  tile de regeneracion recuperan el modo previo, se abren las puertas para salir
  inmediatamente, giran y reaparecen con fade-in (`cGhost.cls:127-172`).
- Salida del pen: al subir por encima de y=12.5*8=100 se alinean, se cierra el pen
  y salen hacia la izquierda (`cGhost.cls:142-146`).

## 5. Modos y temporizadores

- Fases scatter/chase por nivel (`cMazeLevel.cls:134-141`), en segundos y
  alternando Scatter primero desde la fase 1 (`cMazeLevel.cls:43-59`):
  - Nivel 1: `7,20,7,20,5,20,5,-1`
  - Niveles 2-4: `7,20,7,20,5,1033,0.16666,-1`
  - Niveles 5+: `5,20,5,20,5,1037,0.16666,-1`
  - `-1` = chase permanente. Se convierten a frames con `* FPS`
    (`cMazeLevel.cls:50`). Contraste con Dossier: identico (7/20/7/20/5/20/5,
    1033 y 1037 s, 1/60 s).
- Frightened por nivel (`cMazeLevel.cls:163-178`), segundos:
  `6,5,4,3,2,5,2,2,1,5,2,1,1,3,1,1,0,1,0,0,0` para niveles 1..21.
- Duracion en frames = `frightened_s * 60` (`cGame.cls:581`).
- Durante frightened el temporizador scatter/chase se **pausa** y se reanuda al
  terminar (`cGame.cls:276-287`).
- Si `frightened_s == 0` (niveles 17, 19, 20, 21+) no hay modo azul: solo se
  fuerza la inversion de direccion (`cGame.cls:586-588`).
- Fin de frightened: se restaura el modo de fase, la velocidad de Pac-Man y el
  valor de fantasma a 200 (`cGame.cls:278-284`).
- Parpadeo de aviso: el sprite parpadea en las ventanas de frames
  97-108, 73-84, 49-60, 25-36 y 1-12 (12 frames encendido / 12 apagado),
  es decir, ultimos 108 frames = 1.8 s (`cGame.cls:411-417`).
- Al cambiar de modo (chase<->scatter y hacia frightened) los fantasmas giran
  180 grados; no giran al volver de frightened; las victimas comidas no giran
  (`cGhost.cls:229-249`). Coincide con Dossier.
- Flash de los power pills: 8 frames visible / 8 oculto (`cGame.cls:426-437`).

## 6. Puntuacion y progresion

| Concepto | Valor | Cita |
|---|---|---|
| Dot | 10 | `cGame.cls:568` |
| Power pill | 50 | `cGame.cls:577` |
| Fantasmas asustados (por power pill) | 200, 400, 800, 1600 | `cGame.cls:256-257,584,620-622` |
| Tras el 4.o fantasma | termina frightened (`mPowerPillCounter = 1`) | `cGame.cls:257` |
| Vida extra | 10.000 puntos (una vez) | `cGame.cls:690-699` |
| Hi-score | Settings.ini `[SCORES] HI SCORE`; se guarda al terminar | `cGame.cls:75`, `Settings.ini:1-2` |
| Nivel completado | 0 dots y 0 power pills | `cMaze.cls:30-32` |
| Fin de nivel | 6 flashes de 200 ms y siguiente nivel | `cGame.cls:156-181` |
| Niveles | ilimitados; datos del 21 en adelante | `cGame.cls:69-72`, `cMazeLevel.cls:96-100` |
| Vidas iniciales | 3; GAME OVER al llegar a 0 | `cGame.cls:55,65,74` |

Fruta: aparece a **170 y 70 dots restantes**, dura 10 s (`10*FPS`), se come en
el tile VB (col 15, fila 18) con `Round(x/8)==15`, y muestra su valor ~2 s
(`cGame.cls:223-225,559-562,418-425`). Valores por nivel: `levels.csv` /
`cMazeLevel.cls:106-122` (Cherry 100, Strawberry 300, Peach 500, Apple 700,
Grapes 1000, Galaxian 2000, Bell 3000, Key 5000). Dossier Table A.1: identico.

## 7. Laberinto (resumen; detalle en `maze.txt`/`maze.c`)

| Elemento | Coordenadas VB (1-based) |
|---|---|
| Rejilla jugable | cols 1..28, filas 1..31 (28x31) |
| Casa de fantasmas (pen) | cols 12..17, filas 14..16 |
| Puerta | fila 13, cols 14-15 |
| Tunel | fila 15, camino en cols 1..6 y 23..28; sentinelas (0,15)=74, (-1,15)=72, (29,15)=74, (30,15)=66 |
| Wrap | x>240 -> 0; x<0 -> 240 |
| Dots / power pills | 240 dots; pills en (2,4),(2,24),(27,4),(27,24) |
| Inicio Pac-Man | (14.5, 24) -> x8=120, y8=196; direccion Left |
| Fruta | centro (col 15, fila 18.5) -> x8=120, y8=148 |
| Pantalla del laberinto | 30 x 33.5 tiles (`cMazeBuilder.cls:20`) |

El mapa coincide con el laberinto clasico del arcade (mismo numero de dots,
pills, casa central, tunel en la fila 15 y zonas de giro prohibido).

## 8. Audio (WAV -> evento)

| Clave | WAV | Cuando | Cita |
|---|---|---|---|
| GameStart | `game start.wav` | inicio de partida (nivel 1) | `cGame.cls:294` |
| EatDot | `waka1.wav` / `waka2.wav` alternados | cada dot | `cGame.cls:570`, `modSoundFX.bas:113-119` |
| EatGhost | `eat ghost.wav` | comer fantasma asustado | `cGame.cls:620` |
| GhostRespawn | `ghost respawn.wav` (loop) | tras el efecto de comer fantasma, hasta volver al pen | `cGame.cls:253-255`, `modSoundFX.bas:120-123` |
| HuntedSiren | `hunted siren.wav` (loop) | ambiente normal (scatter/chase) | `modSoundFX.bas:124-132`, `cGame.cls:334-335` |
| HunterSiren | `hunter siren.wav` (loop) | ambiente durante frightened | `cGame.cls:582-583` |
| EatFruit | `eat fruit.wav` | comer fruta | `cGame.cls:562` |
| ExtraLife | `extra life.wav` | vida extra a 10.000 | `cGame.cls:692` |
| PacmanDeath | `pacman death.wav` | escena de muerte | `cGame.cls:641` |
| — | `intermission.wav` | **no usado** (sin intermissions) | sin referencias |

- Frecuencia de la sirena: 48000 Hz + boost 0.1/0.2/0.3 cuando quedan <=85/61/12
  dots (`modSoundFX.bas:88-101`, `cGame.cls:220-222`).
- Volumen inicial 70% (`modSoundFX.bas:36`), mapeado a centibeles de DirectSound
  (`modSoundFX.bas:46`); ajuste +/-10 con teclas +/- del teclado numerico
  (`cGame.cls:202-205`).
- El sonido no se reproduce en demo/testing (`modSoundFX.bas:105`).
- Formatos del recurso: waka1/2 48 kHz estereo 16 bits; huntedsiren/huntersiren/
  gamestart/ghostresp 48 kHz estereo 8 bits; eatfruit/eatghost/extralife/
  pacmandeath/intermission 11025 Hz mono 8 bits.

## 9. Render y otros

- Sprites: Pac-Man 48x48 y fantasmas 48x48 de origen, dibujados como
  `SQ_SZ*2` tiles (2x2 tiles logicos = 16x16 px logicos).
- Fantasmas: dos frames de animacion (`mAnimFrame\15`), ojos superpuestos segun
  direccion; asustado = sprite azul + ojos; flash = sprite blanco.
- Z-order por frame: fantasmas asustados, Pac-Man, fantasmas perseguidores; los
  ojos comidos pueden dibujarse aparte (`cGame.cls:380-398`).
- HUD: "1UP"/"HI", puntuacion, vidas (iconos de Pac-Man), frutas de niveles
  completados, READY!/GAME OVER, "(C) 1980 MIDWAY MFG. CO." en attract mode
  (`cGame.cls:677-688,706-714,716-793,776`).
- Attract mode: pantalla de creditos 7.5 s y demo game grabado (AttractMode.pmg);
  en modo testing no se usa (`cGame.cls:716-793`, `modMain.bas:18`).
- Ajustes (`Settings.ini`): Hi Score, sonido on/off, nicknames de fantasmas,
  tile size, apariencia clasica, modo testing y semilla.
