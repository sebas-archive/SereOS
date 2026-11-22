# Auditoria tecnica de Paku-Paku (VB6) para el port "PAC-MAN SereOS"

> **Nota (v1.7):** esta auditoría histórica se conserva como referencia. La especificación vigente de la versión definitiva está en
> [`AUDIT_PAKUPAKU.md`](../Pac-man SereOS/docs/AUDIT_PAKUPAKU.md) y
> [`AUDIT_RESOURCES.md`](../Pac-man SereOS/docs/AUDIT_RESOURCES.md).

**Encargo:** task-8. Especificacion de portabilidad del proyecto de referencia
Paku-Paku (Visual Basic 6) al juego nativo de SereOS, contrastada con *The
Pac-Man Dossier* (J. Pittman, PDF de 48 paginas incluido en la referencia).

**Entradas auditadas (solo lectura):**
`/tmp/paku/Paku-Paku/` (3.438 lineas: 7 clases, 7 modulos, 2 formularios y
`Settings.ini`),
`/tmp/paku/Res/` (PNG/WAV/TTF) y `The Pac-Man Dossier.pdf`
(extraido con `pdftotext -layout` -> `/tmp/dossier.txt`, 1.955 lineas).

**Artefactos generados (esta auditoria):**

| Fichero | Contenido |
|---|---|
| `docs/reference/maze.txt` | laberinto ASCII completo 28x31 + mapa semantico + metadatos + validaciones |
| `docs/reference/maze.c` | array C `pk_maze[31][28]` con bits de tile y direccion, ASCII, constantes de inicio/pen/tunel/fruta y checks de compilacion |
| `docs/reference/gen_maze.py` | generador reproducible que replica el algoritmo de `cMazeBuilder.cls` |
| `docs/reference/levels.csv` | 21 niveles: fruta, velocidades (%, px/frame, px/s, 1/256 px), frightened, fases scatter/chase, Elroy |
| `docs/reference/gen_levels.py` | generador de `levels.csv` a partir de la logica de `cMazeLevel.cls` |
| `docs/reference/constants.md` | constantes del original con citas `archivo:linea` |

**Resumen ejecutivo.** Paku-Paku es un clon de Pac-Man bastante fiel: usa el
laberinto clasico exacto (28x31, **240 dots + 4 power pills** verificados al
reconstruirlo), las tablas de nivel del arcade (velocidades, fases scatter/chase,
tiempos de frightened, Cruise Elroy, frutas) y los objetivos de IA documentados
en el Dossier (Blinky directo, Pinky 4 por delante, Inky vector con Blinky, Clyde
distancia 8). La arquitectura es VB6 + bibliotecas de terceros (vbRichClient5/
Cairo para dibujar, DirectSound8 para audio) y **no es portable linea a linea**:
hay que reimplementar en C nativo. Desviaciones principales frente al arcade:
velocidad de fantasma asustado un 2,5% menor, liberacion de Clyde en el nivel 1 a
los 90 dots (arcade: 60), temporizador scatter/chase que no se reinicia al perder
una vida, "cuarta fase scatter" de 0,167 s (10 frames) en vez de 1/60 s, y
cornering/entrada simplificados. Los assets son de terceros (Namco/Midway y
fuentes/liberias ajenas) y **no deben redistribuirse**.

---

## 1. Arquitectura de Paku-Paku

### 1.1 Componentes

| Fichero | Rol | Puntos clave |
|---|---|---|
| `modMain.bas` | Punto de entrada (`Sub Main`) | Carga `vbRichClient5` sin registrar COM, inicializa Cairo, lee `Settings.ini`, registra fuente y recursos (PNG/WAV), carga `AttractMode.pmg`, crea `cGame` y llama `Game.Run` (`modMain.bas:11-23`). |
| `cGame.cls` (910 l.) | Orquestador y bucle de juego | Crea la ventana (`Cairo.WidgetForms`), fija 60 FPS reales con `QueryPerformanceCounter` (`cGame.cls:81-115`), lleva marcadores/score, resuelve colisiones, dibuja HUD/escenas y gestiona entrada. |
| `cMaze.cls` (84 l.) | Fachada del laberinto | Compone `cMazeBuilder` + `cMazeLevel`; expone `AvailableDirections` (`:46-56`), `DirectionIsValid` (`:57-59`), `DistanceBetweenTiles` euclidiana (`:60-62`), `BuildNew` (`:63-67`), `RemoveDot` (`:68-82`), `Completed` (`:30-32`). |
| `cMazeBuilder.cls` (343 l.) | Datos y dibujo del laberinto | Tabla ASCII de 31 cadenas (`:39-69`), construccion de `gTiles` (`:71-98`, `:133-152`), bitmask de caminos (`InitMazePaths`, `:170-196`), parche del pen (`:154-166`), render Cairo de paredes (`CreateWallPiece`, `:222-343`), lista de power pills. |
| `cMazeLevel.cls` (182 l.) | Tabla de niveles y fases | `LevelData` (`:16-26`), tabla 1..21 (`InitLevelData`, `:101-182`), niveles >21 reutilizan el 21 (`:96-100`), maquina de fases scatter/chase (`NextPhase`, `:43-59`). |
| `cPacMan.cls` (234 l.) | Pac-Man | Posicion/direccion/cornering (`SetDirection :50-92`, `Move :93-160`), animacion de boca (`:154`), vidas, sprite Cairo (`:194-231`), wrap del tunel (`:156`). |
| `cGhost.cls` (476 l.) | Un fantasma | Estado/modo/objetivo/velocidad, movimiento por tiles (`DoRoamingMove :80-126`, `DoCagedMove :127-173`), IA de objetivo (`CalcTargetTile :412-475`), maquina de estados del pen via excepciones de tiles (`:277-334`), sprite con ojos/flash (`:360-378`). |
| `cGhosts.cls` (68 l.) | Los cuatro fantasmas | Personalidades (`:17-20`), posiciones iniciales (`LevelInit :46-51`), difusion de fase/frightened/inversion (`:43-68`). |
| `modGameGlobals.bas` (76 l.) | Estado global | Objetos globales, enums (direcciones, bits de tile, personalidades, modos), `ROWS=32`/`COLS=29`, `gTiles`, `SQ_SZ=8`, `DEFAULT_SPEED=1.25`, `FPS=60`, `MAZE_BACKCOLOUR` y accesos `Inky/Pinky/Blinky/Clyde` (`:4-76`). |
| `modPacManAI.bas` (81 l.) | IA de pruebas | Solo para `eTesting`: paseo aleatorio + reflejo si un fantasma esta a <3 tiles (`:4-46`). No se usa con jugador humano; documenta orden de prueba de direcciones izquierda/arriba/derecha/abajo (`:47-81`). |
| `modSoundFX.bas` (135 l.) | Efectos de sonido | 10 buffers DirectSound8, volumen en centibeles, sirena en loop con frecuencia variable, alternativa waka1/waka2. |
| `modTrickDirectSound.bas` (464 l.) | Wrapper DirectSound8 VB6 | Carga RIFF/WAV/MP3 (ACM), crea/reproduce buffers; biblioteca de terceros ("DirectSound8 for Visual Basic 6.0 type library by The trick v1.00", `prjPac-Man.vbp:4`). |
| `modRegfreeDlls.bas` (79 l.) | Carga COM sin registro | Modulo de Olaf Schmidt (dic. 2014, `:1-12`) para cargar `vbRichClient5.dll`/`DirectCOM.dll` desde `Bin\`. |
| `modIniFile.bas` (35 l.) | INI Win32 | `GetPrivateProfileString`/`WritePrivateProfileString` para `Settings.ini`. |
| `frmMain.frm` | Formulario de arranque | Practicamente vacio; `cGame` crea su propia ventana. |
| `frmSettings.frm` | UI de ajustes | Solo dos `OptionButton` Classic/Modern; **no se referencia desde ningun modulo** (codigo muerto). |
| `Settings.ini` | Configuracion | Hi-score, sonido, nicknames, tile size, apariencia clasica, testing y semilla. |
| `AttractMode.pmg` | Demo grabada | Lista `frame=direccion,` reproducida en `eDemoGame` (`modMain.bas:152-166`). |

### 1.2 Dependencias y flujo

```
modMain.Main
  ├─ modRegfreeDlls.GetInstanceFromBinFolder("vbRichClient5")
  │     └─ vbRichClient5.dll (COM reg-free) ── Cairo (dibujo vectorial)
  ├─ modIniFile / Settings.ini
  ├─ modSoundFX ── modTrickDirectSound ── DirectSound8 (COM, dsvb.tlb)
  ├─ cGame (crea Cairo.WidgetForms "Paku Paku")
  │    ├─ cMaze ── cMazeBuilder (datos+dibujo) + cMazeLevel (niveles/fases)
  │    ├─ cPacMan
  │    ├─ cGhosts ── 4 x cGhost
  │    └─ modPacManAI (solo testing)
  └─ Game.Run -> bucle Run/LevelLoop
```

Ciclo de un frame (`cGame.cls:88-114`): si toca, `InitLevel`; se copia la imagen
pre-renderizada del laberinto al buffer; `CheckPreMoveCounters`; `MoveSprites`
(entrada, Pac-Man, fantasmas); `DrawSprites`; `CheckCollisions`; `UpdateScore`;
`CheckPostMoveCounters`; volcado a pantalla; `DoEvents`; espera activa hasta
`Freq/60`. **En SereOS esto se sustituye por un paso fijo de 1/60 s desde el
bucle cooperativo y sin esperas activas.**

Todas las coordenadas de juego son **pixeles logicos de 8 px por tile**
(`SQ_SZ`); al dibujar se escala por `gTileSize/SQ_SZ` (`cGame.cls:382`). El
laberinto se dibuja una sola vez en una superficie Cairo y se reutiliza; los
dots se borran de esa superficie al comerlos (`cMaze.cls:77-81`).

---

## 2. Movimiento de Pac-Man

### 2.1 Representacion y velocidad

- `mX`, `mY` son `Currency` (punto fijo de 4 decimales) en pixeles logicos.
  Se inicializa al centro de un tile: `x = col*8 + 4`, `y = fila*8 + 4`
  (`cPacMan.cls:24-31`). El sprite (48x48 de origen) se dibuja como 2x2 tiles
  logicos: `x-8, y-8` con tamano 16x16 (`cGame.cls:402-403`).
- Inicio de nivel: **VB (col 14.5, fila 24), direccion Left** ->
  `x=120, y=196` (`cGame.cls:316`).
- Velocidad: `mSpeed` es un porcentaje (80 por defecto, `cPacMan.cls:21`) y cada
  frame avanza `PixelIncrements = 1.25 * mSpeed/100` px (`cPacMan.cls:99`).
  Por nivel, `cGame.cls:297` asigna `Maze.Level.PacmanSpeed`; tras un power pill,
  `PacmanAsHunterSpeed` (`cGame.cls:585`). Valores exactos en `levels.csv`.
- Pausas: al comer un dot `mDigestionCounter = 1` frame; power pill = 3 frames
  (`cGame.cls:569,578`); mientras `mDigestionCounter > 0` no se mueve
  (`cGame.cls:465-475`). Esto reproduce la ralentizacion efectiva del arcade
  (~71%/79%/87% con dots, Dossier p.16).

### 2.2 Direccion solicitada, giros y esquinas

`SetDirection` (`cPacMan.cls:50-92`):
1. Rechaza 0 o la direccion actual.
2. Rechaza si esta en medio de un cornering.
3. Rechaza si el **tile actual** no tiene salida en esa direccion
   (`Maze.DirectionIsValid(Int(x/8), Int(y/8), dir)`, `:56`).
4. Si es la opuesta, gira de inmediato (`:70-73`).
5. Si es perpendicular, activa cornering: calcula si esta en el "pre-turn point"
   (fraccion 0.5 del tile segun la direccion, `:76-83`); si se paso, invierte
   temporalmente el movimiento para volver a entrar, y fija
   `mCorneringDirection`, `mCorneringFromTileIndex`, `mOrientation` (`:74-89`).
   `Move` desliza en diagonal hasta alinearse y completar el giro
   (`cPacMan.cls:93-152`). Es una aproximacion del cornering del arcade
   (pre-turn/post-turn con doble velocidad durante el giro, Dossier pp.17-18),
   suficiente para jugar pero no pixel-perfect.
6. Si en el centro del tile la direccion actual ya no tiene salida, se para
   (`mDirection = 0`) y se alinea al centro (`:144-151`).

`MoveSprites` (`cGame.cls:464-552`) lee el teclado cada frame: izquierda = `Z`,
derecha = `X`, arriba/derecha = **codigos 192/191** de `GetAsyncKeyState`
(`cGame.cls:479-482`). Esos codigos no son VK estandar de flechas (VK_UP=38, VK_DOWN=40),
lo que es un defecto/ambiguedad del original; en el port usar flechas + WASD.
Se mantiene "direccion mas reciente" horizontal/vertical y se intenta aplicar
cada frame; el buffer de giro es, por tanto, "aplicar cuando el tile actual
tenga la salida", no una cola de 1 tile explicita como en el arcade. Tambien hay
soporte de replay (`gPacmanMoves`, `.pmg`) para demo/QA (`:479-487`).

### 2.3 Tunel, boca, muerte y reinicio

- Wrap del tunel: `x > 30*8 (=240) -> x = 0`; `x < 0 -> x = 240`
  (`cPacMan.cls:156`); el laberinto mide 28 tiles (224 px), por lo que el tunel
  usa 30 tiles con dos tiles virtuales.
- Boca: `mMouthAngle` empieza en 280; cada frame resta 15 y al bajar de 270
  vuelve a 360 (`cPacMan.cls:154`); ciclo de 7 frames (~0.117 s).
- Colision: mismo tile **o** `|dx| < 2 && |dy| < 2` px
  (`cGame.cls:607-617`); primero se comprueban los fantasmas no asustados
  (muerte) y despues los asustados. La tolerancia de 2 px corrige el "pass
  through bug" del arcade.
- Muerte: `Pacman.Alive = False` y `mDigestionCounter = 1.5*FPS` (90 frames de
  congelacion, `cGame.cls:625-628`); escena de muerte (`:632-675`: sprite
  360->0 cada 65 ms, luego 40->0 con fade cada 50 ms, +1 s); resta vida y
  `InitLevel` reposiciona a todos sin reconstruir el laberinto (los dots comidos
  se conservan; `cGame.cls:290-336`).
- Power pill: frightened = `GhostFrightenedTime*FPS` frames
  (`cGame.cls:579-585`); pausa el temporizador de fases (`cGame.cls:276-287`);
  `mGhostKillValue = 200`; velocidad de Pac = `PacmanAsHunterSpeed`.
- Si `GhostFrightenedTime == 0`: no hay modo azul, solo `Ghosts.ReverseDirection()`
  (`cGame.cls:586-588`).

---

## 3. Fantasmas

### 3.1 Estructura y personalidades

Cada `cGhost` guarda posicion (`mX,mY`), velocidad (`mSpeed`), direccion actual y
planificada, modo, objetivo, `mEaten`, personalidad, frame de animacion y alpha
de regeneracion (`cGhost.cls:16-21`). `cGhosts` contiene las 4 personalidades
(`cGhosts.cls:17-20`) y difunde cambios de fase/velocidad/frightened.

| Fantasma | Personalidad | Nombre | Color |
|---|---|---|---|
| Blinky | `eShadow` | SHADOW | rojo |
| Pinky | `eSpeedy` | SPEEDY | rosa `RGB(255,184,255)` |
| Inky | `eBashful` | BASHFUL | cian |
| Clyde | `ePokey` | POKEY | naranja `RGB(255,184,81)` |

### 3.2 Posiciones iniciales y casa

`cGhosts.LevelInit` (`cGhosts.cls:46-51`), en tiles VB 1-based:

| Fantasma | Col | Fila | Direccion | x8 | y8 |
|---|---|---|---|---|---|
| Blinky | 14.5 | 12 | Up | 120 | 100 |
| Pinky | 14.5 | 15 | Down | 120 | 124 |
| Inky | 12.5 | 15 | Up | 104 | 124 |
| Clyde | 16.5 | 15 | Up | 136 | 124 |

`x8 = col*8+4`, `y8 = fila*8+4` (`cGhost.cls:22-24`). Blinky empieza **fuera**
del pen, encima de la puerta; los otros tres dentro. El pen ocupa cols 12..17,
filas 14..16; la puerta es la fila 13, cols 14-15 (`cMazeBuilder.cls:154-166`).

### 3.3 Movimiento, alineacion y velocidad

- Avance por frame igual que Pac-Man (`cGhost.cls:60-79`).
- **Planificacion por tile**: cuando el fantasma cruza el punto medio de un tile
  (cambia el "nearest tile") decide la direccion del siguiente tile
  (`cGhost.cls:84-119`); al girar alinea al centro y conserva el "surplus" de
  pixeles en la nueva direccion (`:99-113`). Los fantasmas no pueden girar en
  mitad de un tile (a diferencia de Pac-Man).
- Velocidad actual (`CurrentSpeed`, `cGhost.cls:214-228`), por prioridad:
  1. comido (ojos): **160%** (2 px/frame, 1/4 de tile) — `:217-218`
  2. en tunel: `(GhostSpeed+5)/2` = 40/45/50% — `:219-220`
  3. dentro del pen: **40%** (0,5 px/frame) — `:221-222`
  4. asustado: `GhostSpeed/2 + 10` = 47,5/52,5/57,5% — `:223-224`
  5. normal: `mSpeed` (velocidad de nivel o boost Elroy) — `:225-226`
- `mSpeed` se inicializa a 75 (`cGhost.cls:381`) y `cGame` lo fija por nivel
  (`cGame.cls:298`).

### 3.4 Calculo del tile objetivo (`CalcTargetTile`, `cGhost.cls:412-475`)

Los comentarios del propio autor citan el Dossier (`:414`).

| Modo | Blinky | Pinky | Inky | Clyde |
|---|---|---|---|---|
| Scatter | col 26, fila -2 | col 3, fila -2 | col 28, fila 32 | col 1, fila 32 |
| Chase | tile actual de Pac-Man | 4 por delante; si Pac mira Up: ademas `col-4` (bug original recreado) | T = 2 por delante (con el mismo bug de Up: `col-2`); objetivo = `2*T - tile(Blinky)` | si distancia > 8 -> Pac-Man; si <= 8 -> objetivo scatter (esquina inferior izquierda) |
| Frightened | `(Int(ROWS*Rnd), Int(COLS*Rnd))` aleatorio | idem | idem | idem |
| Ojos comidos | (col 15, fila 12) = puerta del pen | idem | idem | idem |

Citas: scatter/frightened `cGhost.cls:420-436`; chase `:441-470` (Pinky `:450-458`,
Inky `:459-469`, Clyde `:444-449`); objetivo de ojos `:270-276`; coordenadas de
regeneracion `:131-141` (fila 16; col 13 Inky, 15 Blinky/Pinky, 17 Clyde).
Blinky en Cruise Elroy persigue a Pac-Man **incluso en scatter** (`:423-426`).
En modo frightened el objetivo se recalcula en cada tile (movimiento pseudoaleatorio
equivalente al del arcade, aunque por mecanismo distinto: el arcade elige
direccion con PRNG y gira en sentido horario si esta bloqueada, Dossier p.15).

### 3.5 Decision en interseccion

`PlanNextDirection` (`cGhost.cls:177-213`):
1. Se situa en el tile **siguiente** al actual segun la direccion (`:180-185`).
2. Calcula el objetivo con `CalcTargetTile` (`:187`).
3. Para cada salida valida excluye la direccion opuesta (no se puede invertir
   voluntariamente) (`:193-211`).
4. Calcula distancia euclidiana del tile candidato al objetivo
   (`cMaze.cls:60-62`) y se queda con la menor; empate -> gana el primero
   comprobado porque usa `<` estricto. Orden de comprobacion:
   **ARRIBA, IZQUIERDA, ABAJO, DERECHA**. Coincide con el Dossier
   ("up, left, down, right", p.28).
5. Replanifica en cada tile nuevo (`:116-117`).

No hay pathfinding A*: el fantasma solo mira un tile por delante y elige por
distancia al objetivo (Dossier, "Looking Ahead" / "Intersections", pp.27-28).

### 3.6 Zonas restringidas y excepciones del pen

Cada fantasma tiene su propia coleccion de excepciones de tiles
(`mMazeRuleExceptions`) que sustituyen el bitmask del laberinto solo para el
(`cMaze.AvailableDirections` con excepciones, `cMaze.cls:46-56`). Esto se usa
para dos cosas:

**a) Zonas de giro prohibido hacia arriba** (activas en scatter/chase; en
frightened se permite subir). Tiles VB `(col,row)`: `(13,12)`, `(16,12)`,
`(13,24)`, `(16,24)` -> solo Left+Right (`cGhost.cls:242-245`, inicializacion
`:384-387`). En 0-based: `(12,11)`, `(15,11)`, `(12,23)`, `(15,23)`. Son las
cuatro entradas verticales explotables del arcade (Dossier, "Areas To Exploit",
p.22). En el laberinto reconstruido corresponden a los pasos superiores de las
columnas centrales.

**b) Maquina de estados del pen.** Excepciones completas (VB col:row):
- *Cerrado* (`cGhost.cls:277-291`): `15:12=L+R`; `15:14=Pen`; `13:15/15:15/17:15=Pen+U+D`;
  `14:15/16:15=Pen`; `13:16..17:16=Pen`.
- *Salida* (`OpenPenForExit`, `:292-306`): `15:12=Pen+U`, `15:13=Pen+U`,
  `15:14=Pen+U`, `15:15=Pen+U`, `15:16=Pen+U`; `13:15/14:15=Pen+R`;
  `16:15/17:15=Pen+L`; `13:16/14:16=Pen+R`; `16:16=Pen+L`; `17:16=Pen+L`.
- *Entrada de ojos* (`OpenPenForEntry`, `:307-334`): `15:12..15:15=Pen+Down`;
  resto de tiles del pen a `Pen`; y rutas horizontales distintas para
  Bashful (`13:16..15:16=Pen+Left`) y Pokey (`15:16..17:16=Pen+Right`), con
  neutralizacion de las otras filas.

Maquina de movimiento en el pen (`DoCagedMove`, `cGhost.cls:127-173`):
- Ojos comidos que llegan a la fila 12: se alinean a `x = 15*8 = 120`, bajan y
  fijan su tile de regeneracion (fila 16; col 13/15/15/17 segun personalidad).
- Ojos que alcanzan su tile de casa: snap exacto, suena el ambiente, `mEaten =
  False`, se restaura el modo previo, se abre el pen para salir de inmediato,
  giran 180 grados y reaparecen con fade-in desde alpha 0,05 (`:147-155`).
- Fantasma normal que sube por encima de `y/8 < 12.5` (y=100): se alinea, cierra
  el pen y sale **hacia la izquierda** (`:142-146`).
- En el resto del pen: si el tile es `Pen+Up+Down` sigue rebotando; si es solo
  `Pen` invierte; si hay salida horizontal/vertical la toma (`:156-171`).
  La salida es, por defecto, siempre hacia la izquierda (desviacion menor: el
  arcade puede salir a la derecha si hubo cambios de modo dentro de la casa,
  Dossier p.20; Paku no lo implementa).

`IsInsidePen` consulta si el tile actual tiene el bit `eIsPen` con las
excepciones del fantasma (`cGhost.cls:174-176`).

### 3.7 Liberacion de los fantasmas de la casa

Reglas reales de Paku-Paku (en `cGame.CheckPreMoveCounters`):

**Al empezar el nivel** (`cGame.cls:195-208`, usando dots restantes; el nivel
empieza con 240):
- `DotsRemaining == 240`: sale **Pinky**; en nivel >1 tambien **Inky**; en
  nivel >2 tambien **Clyde**.
- `DotsRemaining == 210`: en nivel 1 sale **Inky** (30 dots comidos).
- `DotsRemaining == 190`: en nivel 2 sale **Clyde** (50 dots comidos).
- `DotsRemaining == 150`: en nivel 1 sale **Clyde** (90 dots comidos).
- Blinky empieza fuera del pen y no participa en estas reglas.

**Tras perder una vida** (`cGame.cls:209-218`): se usan umbrales relativos a los
dots que quedaban al morir: **Pinky a los 7 dots, Inky a los 17, Clyde a los 32**
(el "global dot counter" del Dossier p.20).

**Temporizador de inactividad** (`cGame.cls:231-239`): si Pac-Man no come dots,
se libera el fantasma mas preferente cada **4 s** (niveles 1-4) o **3 s**
(nivel 5+), en orden Pinky -> Inky -> Clyde.

Diferencias con el Dossier: el arcade usa contadores personales por fantasma con
limites 30/60 (nivel 1), 0/50 (nivel 2), 0/0 (nivel 3+), y el contador global se
desactiva al llegar a 32 con Clyde dentro. Paku-Paku simplifica: usa umbrales
absolutos de dots restantes al empezar el nivel y umbrales relativos tras una
muerte. En el nivel 1 eso retrasa a Clyde hasta 90 dots en vez de 60.

### 3.8 Cruise Elroy (Blinky)

- Umbrales por nivel (`cMazeLevel.cls:143-161`, tabla en `levels.csv`):
  Elroy1 = 20, 30, 40 (niv. 3-5), 50 (6-8), 60 (9-11), 80 (12-14), 100 (15-18),
  120 (19+); Elroy2 = mitad exacta.
- Efecto: `Blinky.Speed = Blinky.Speed + 5` y luego `+5` mas
  (`cGame.cls:227-229`), es decir +5% y +10% sobre la velocidad de fantasma.
  En Elroy Blinky ignora su esquina y persigue a Pac-Man tambien en scatter
  (`cGhost.cls:423-426`).
- Si muere Pac-Man, Elroy queda suspendido hasta que Clyde se libere; al hacerlo
  se re-evalua el dot count y se aplica +5/+10 (`cGame.cls:242-245`).
- Coincide con Dossier Tabla A.1 (Elroy dot counts y velocidades
  Elroy1 80/90/100%, Elroy2 85/95/105%).

### 3.9 Inversion de direccion

- Al cambiar de modo: chase<->scatter y transicion a frightened -> giro 180
  forzado; al volver de frightened -> sin giro; fantasmas comidos -> sin giro
  (`cGhost.cls:229-249`). El giro se aplica cuando el fantasma entra en el
  siguiente tile (`mForceDirectionReversal` consumido en `DoRoamingMove`,
  `cGhost.cls:88-92`). Coincide con el Dossier (los giros no son simultaneos).
- `ReverseDirection` publico usado por power pill en niveles sin frightened
  (`cGhosts.cls:63-68`, `cGame.cls:586-588`).

---

## 4. Modos de fantasma y temporizadores

### 4.1 Maquina de fases scatter/chase (`cMazeLevel.cls:43-64`)

- `PhaseTimes` es una lista de duraciones en segundos que alterna
  **Scatter (fase 1), Chase (2), Scatter (3), Chase (4), Scatter (5), Chase (6),
  Scatter (7), Chase (8...)**, `cMazeLevel.cls:43-59`.
- `mPhaseCounter = PhaseTimes[n] * FPS` frames (`:50`); cada frame del juego se
  decrementa si no hay frightened (`cGame.cls:286`, `DecrementPhaseCounter`
  `cMazeLevel.cls:39-42`); al llegar a 0 se avanza de fase y se llama
  `Ghosts.SetPhaseMode` (`:55`), lo que fuerza el giro de los fantasmas.
- `-1` en la lista produce un contador negativo y el modo queda **chase
  permanente** (`:48-53`).
- Tabla exacta (segundos) y valores efectivos:

| Nivel | Scatter | Chase | Scatter | Chase | Scatter | Chase | Scatter | Chase final |
|---|---|---|---|---|---|---|---|---|
| 1 | 7 | 20 | 7 | 20 | 5 | 20 | 5 | indefinido |
| 2-4 | 7 | 20 | 7 | 20 | 5 | 1033 | 0.16666 | indefinido |
| 5+ | 5 | 20 | 5 | 20 | 5 | 1037 | 0.16666 | indefinido |

El Dossier (p.13-14) da 1/60 s (1 frame) para la 4.a fase scatter; Paku-Paku usa
0,16666 s -> `0.16666*60 = 9,9996` -> **10 frames**. Desviacion menor (visualmente
un giro breve). Las demas duraciones coinciden exactamente.

**Desviacion importante:** el temporizador de fases **no se reinicia al perder
una vida**. `cGame.InitLevel` no toca `cMazeLevel`; solo reposiciona fantasmas
(`cGhost.Init` pone modo `eScattering`), pero el contador de fase sigue donde
estaba. En el arcade el temporizador se reinicia y los fantasmas salen en la
primera fase scatter (Dossier p.14). En el port conviene corregirlo (reiniciar
fase a scatter y contador 0 al reaparecer).

### 4.2 Frightened

- Duracion exacta por nivel: `6,5,4,3,2,5,2,2,1,5,2,1,1,3,1,1,0,1,0,0,0`
  segundos para niveles 1..21 (`cMazeLevel.cls:163-178`; `levels.csv`
  `frightened_s` y `frightened_frames`). Coincide con los valores clasicos.
- Entrada: power pill -> `Ghosts.Frighten` (todos a `eFrightened`),
  `mPowerPillCounter = fri*FPS`; los fantasmas que estan fuera del pen invierten
  la marcha, los que estan dentro no (`cGhost.cls:229-249`).
- Durante frightened el temporizador scatter/chase se pausa y se reanuda al
  terminar (`cGame.cls:276-287`).
- Fin: se restaura el modo de fase previo, la velocidad normal, y
  `mGhostKillValue = 200`. Si se comen los 4 fantasmas, `mPowerPillCounter = 1`
  adelanta el final (`cGame.cls:252-257`).
- Aviso: los ultimos **108 frames (1,8 s)** el sprite parpadea en ventanas de
  12 frames encendido / 12 apagado (`cGame.cls:411-417`); el sprite azul es
  "HuntedGhost", el blanco "FlashingGhost".
- Niveles con tiempo 0 (17, 19, 20, 21+): no hay modo azul; solo se invierte la
  direccion (`cGame.cls:586-588`).
- Velocidad durante frightened: 47,5 / 52,5 / 57,5% (ver 3.3 y desviacion en 8.1).

---

## 5. Laberinto

### 5.1 Datos y geometria

- Rejilla jugable **28 columnas x 31 filas** (tiles VB 1..28 / 1..31). La matriz
  global es `gTiles(-1 To COLS+1, ROWS)` = cols -1..30, filas 0..32
  (`modGameGlobals.bas:55,57`); la fila 32 y la columna 29 no se usan.
- `SQ_SZ = 8` px logicos por tile (`modGameGlobals.bas:59`). La superficie del
  laberinto que dibuja el original mide `(COLS+1) x (ROWS+1.5)` tiles = 30 x 33.5
  (`cMazeBuilder.cls:20`).
- El mapa es el del arcade: 240 dots, 4 power pills en (2,4), (2,24), (27,4),
  (27,24), casa central (cols 12..17, filas 14..16), puerta fila 13 cols 14-15,
  tunel en la fila 15 (cols 1..6 y 23..28) y las cuatro zonas de giro prohibido.

### 5.2 Como se construye (`cMazeBuilder.cls:35-196`)

1. `sSquares(1..31)` contiene 31 cadenas de 28 caracteres (`:39-69`) con
   leyenda propia (`:38`): `O` pared interior gruesa, `o` borde/pared fina,
   `p` puerta del pen, `P` interior del pen, `.` dot, `+` power pill, `T` tunel,
   ` ` camino sin punto, `X` zona externa ignorada.
2. Primera pasada (`:71-98`): clasifica paredes (`O/o/P`->1, `X`->2, `p`->3,
   resto->0) y, si encuentra `T` en los bordes, marca paredes virtuales fuera del
   laberinto para que el tunel se dibuje bien (`:81-94`). Es solo para el render.
3. Segunda pasada (`:133-152`): clasifica caminos en bruto
   `T`->8, `+`->4, `.`->2, ` `->1, resto->0 y llama `InitMazePaths`.
4. `InitMazePaths` (`:170-196`): convierte cada tile de camino en un bitmask:
   bits del tile + `eHasDot`/`eHasPowerPill`/`eIsTunnel` + bits de direccion
   `Up/Right/Down/Left` segun vecinos transitables. En los bordes laterales
   fuerza Left/Right para permitir el tunel. Cuenta los dots (`mNumberOfDots`).
5. Parche explicito del tunel (`:190-194`): `gTiles(0,15)=74`,
   `gTiles(-1,15)=72`, `gTiles(29,15)=74`, `gTiles(30,15)=66`.
6. Parche del pen (`:154-166`): localiza la primera `P` (col 12, fila 14) y pone
   `eIsPen` en su rectangulo de 6x3 (cols 12..17, filas 14..16).
7. El dibujo (`:100-131`, `CreateWallPiece :222-343`) es puramente cosmetico:
   rectangulos redondeados/fills/strokes en Cairo, borde fino o grueso, puerta
   rosa, dots como elipses de 0.3 tiles y power pills de 0.875 tiles que
   parpadean (8 frames on / 8 off, `cGame.cls:426-437`). **No afecta a la logica
   y no es portable**: en SereOS se sustituye por un tileset propio.

Todo esto esta reproducido fielmente por `docs/reference/gen_maze.py`, que
genera `maze.txt` y `maze.c`. Validaciones ejecutadas: 240 dots, 4 power pills,
12 tiles de tunel, 18 tiles de pen, simetria de los bits de direccion en todos
los tiles, y compilacion del array C con las flags freestanding de SereOS.

### 5.3 Configuracion de tiles (`maze.c`)

Bits por tile (identicos al original): `UP=1 RIGHT=2 DOWN=4 LEFT=8`,
`DOT=16 POWER=32 TUNNEL=64 PEN=128`; 0 = pared/void. `pk_maze[fila][col]` esta en
0-based (fila 0..30, col 0..27). El fichero incluye ademas:
- `pk_maze_ascii[31]` con el mapa original.
- Constantentes de casa: `PK_PEN_COL0=11`, `PK_PEN_ROW0=13` (6x3 en 0-based),
  puerta fila 12 cols 13-14, tunel fila 14.
- Inicios: `PK_PAC_START_X/Y=120/196`, Blinky 120/100, Pinky 120/124,
  Inky 104/124, Clyde 136/124; fruta centro 120/148 y tile de colision (15,18).
- `PK_DOTS_TOTAL=240`, `PK_POWER_PILLS=4` y comprobaciones de tamano en compilacion.

**Recomendacion de port:** usar `maze.c` tal cual, leer el bitmask para
movimiento/decision (equivale a `AvailableDirections`) y limpiar los bits
`DOT`/`POWER` al comer (como `cMaze.RemoveDot`). Las posiciones se mantienen en
la rejilla logica de 8 px internamente; con tiles de render de 16 px basta
multiplicar por 2.

---

## 6. Reglas y puntuacion

| Concepto | Valor | Cita |
|---|---|---|
| Dot normal | 10 puntos | `cGame.cls:568` |
| Power pill | 50 puntos | `cGame.cls:577` |
| Fantasmas con una misma power pill | 200, 400, 800, 1600 | `cGame.cls:256-257,584,620-622` |
| Cuarto fantasma | termina el frightened (`mPowerPillCounter=1`) | `cGame.cls:257` |
| Fruta | valor por nivel (100..5000) | `cMazeLevel.cls:106-122` |
| Vida extra | 10.000 puntos (una vez) | `cGame.cls:690-699` |
| Vidas | 3 iniciales | `cGame.cls:55,65` |
| Nivel completado | 0 dots y 0 power pills | `cMaze.cls:30-32` |
| Fin de nivel | 6 flashes de 200 ms, siguiente nivel | `cGame.cls:156-181` |
| Hi-score | `Settings.ini [SCORES] HI SCORE` (134780 en el fichero) | `cGame.cls:75`, `Settings.ini:1-2` |
| Progresion | niveles ilimitados; datos a partir del 21 | `cGame.cls:69-72`, `cMazeLevel.cls:96-100` |
| GAME OVER | al quedarse sin vidas (escena + reinicio de partida) | `cGame.cls:74,706-714` |

**Fruta**: aparece cuando el marcador de dots restantes llega a **170** y a
**70** (`cGame.cls:220-225`), dura **10 s** (`10*FPS`), se consume cuando
`Round(Pacman.SpriteX/8) == 15 y fila == 18` (`cGame.cls:559-562`) y muestra su
valor ~2 s tras comerse (`:271-274`, `:419-425`). El Dossier (p.11) confirma el
disparo a 70/170 dots y que la duracion varia por nivel; Paku usa 10 s fijos
(desviacion menor). Tabla de fruta y valores: `levels.csv` (idem a la Tabla A.1
del Dossier).

**Progresion de nivel:** `Maze.Completed` -> escena de flash -> `Maze.Level++`;
`LevelData` limita a 21 (`i > UBound -> 21`), asi que de 21 en adelante se repite
la misma tabla (velocidad de Pac 90%, fantasmas 95%). El arcade real desborda el
contador a los 255 niveles; irrelevante en la practica.

**Al morir:** no se reconstruye el laberinto; se conservan los dots comidos y se
reposicionan Pac-Man y fantasmas (`cGame.cls:290-336`). El marcador de dots no
cambia; solo se reinician temporizadores/counters del nivel y se re-aplica la
velocidad del nivel.

---

## 7. Audio

Motor: `modSoundFX` crea 10 buffers con DirectSound8 (via `modTrickDirectSound`)
al arrancar (`modSoundFX.bas:16-38`), volumen inicial 70% (`:36`) convertido a
centibeles (`:46`), y reproduce uno a uno (`PlaySound`, `:102-134`). Solo hay
un sonido de ambiente en loop a la vez; la sirena normal y la de "cazado" se
alternan.

| Evento | Sonido / WAV | Loop | Cita |
|---|---|---|---|
| Inicio de partida (nivel 1) | `game start.wav` | no | `cGame.cls:294`, `modSoundFX.bas:108` |
| Comer dot | `waka1.wav` / `waka2.wav` alternados | no | `cGame.cls:570`, `modSoundFX.bas:113-119` |
| Comer fantasma | `eat ghost.wav` | no | `cGame.cls:620` |
| Regeneracion de fantasma | `ghost respawn.wav` | si | `cGame.cls:253-255`, `modSoundFX.bas:120-123` |
| Ambiente normal (scatter/chase) | `hunted siren.wav` | si | `cGame.cls:334-335`, `modSoundFX.bas:124-132` |
| Ambiente frightened | `hunter siren.wav` | si | `cGame.cls:582-584` |
| Comer fruta | `eat fruit.wav` | no | `cGame.cls:562` |
| Vida extra | `extra life.wav` | no (no se detiene) | `cGame.cls:692`, `modSoundFX.bas:83` |
| Muerte de Pac-Man | `pacman death.wav` | no | `cGame.cls:641` |
| — | `intermission.wav` | — | **sin uso** (no hay intermissions) |

- La frecuencia de la sirena normal se incrementa en `0.1/0.2/0.3` cuando quedan
  `<=85/61/12` dots (`modSoundFX.bas:88-101`, disparada en `cGame.cls:220-222`).
- `KillAllSounds` detiene todo menos `extra life` (`modSoundFX.bas:73-87`).
- En modo demo/testing no suena nada (`modSoundFX.bas:105`).
- Formatos reales del recurso (auditados con `wave`): waka1/2 48 kHz estereo
  16 bits (~85 ms); sirenas y game start 48 kHz estereo 8 bits; eat fruit/eat
  ghost/pacman death/intermission 11025 Hz mono 8 bits. Formatos mezclados.

**Port:** SereOS solo tiene PC speaker (`drivers/speaker.h`, `speaker_tone`
no bloqueante). Recomendacion: sintetizar en C ondas cuadradas propias
(waka alternado ~2 notas, sirena con barrido de frecuencia por dots restantes,
"power pill", muerte, comer fantasma, fruta, vida extra) y no reproducir WAVs.
Si en el futuro hay driver SB16, mapear la tabla de eventos anterior.

---

## 8. Diferencias con el Pac-Man clasico (Dossier) y recomendaciones de porte

### 8.1 Desviaciones detectadas en Paku-Paku

1. **Velocidad de fantasma asustado**: 47,5/52,5/57,5% en vez de 50/55/60%
   (Formula `GhostSpeed/2+10`, `cGhost.cls:224`). El resto de velocidades
   (normales, tunel, Elroy, ojos, Pac-Man) coinciden.
2. **Liberacion de Clyde en el nivel 1**: 90 dots comidos en vez de 60
   (umbral absoluto 150 dots restantes, `cGame.cls:206-207`). Nivel 2 coincide
   (50); nivel 3+ coincide (inmediato).
3. **El temporizador scatter/chase no se reinicia al perder una vida**; ademas
   los fantasmas salen de la casa en el modo que les pone `cGhost.Init`
   (`eScattering`), pero el contador de fase continua. El arcade reinicia a la
   primera fase scatter (Dossier p.14).
4. **4.a fase scatter de 0,16666 s (10 frames)** en niveles 2+ en vez de 1/60 s
   (1 frame) del arcade. Efecto visual similar (un giro breve).
5. **Sin contadores personales de dots** por fantasma ni desactivacion del
   contador global a 32 con Clyde dentro (Dossier p.20); usa umbrales absolutos
   al empezar nivel y relativos tras muerte (7/17/32).
6. **Salida de la casa siempre hacia la izquierda**; el arcade puede salir a la
   derecha si hubo cambios de modo dentro de la casa (Dossier p.20).
7. **Cornering de Pac-Man aproximado**: deslizamiento diagonal, no reproduce
   pixel a pixel los pre-turn/post-turn del arcade (Dossier pp.17-18). El
   beneficio de "cornering" existe pero no es identico.
8. **Frightened por objetivo aleatorio** en cada tile: el arcade usa un PRNG
   para elegir direccion en cada interseccion y prueba en sentido horario si
   esta bloqueada (Dossier p.15). Resultado parecido; la secuencia no es la misma.
   Paku ademas re-inicializa `Rnd` con semilla fija al empezar nivel/morir
   (`cGame.cls:332`), lo que hace el comportamiento deterministico.
9. **Objetivos scatter** con filas -2/32 y cols 26/3/28/1 (VB): ligeramente
   distintas de las coordenadas off-grid clasicas, pero apuntan a las mismas
   esquinas.
10. **Entrada con teclas Z/X y codigos 192/191** para arriba/abajo
    (`cGame.cls:479-482`); los codigos no son VK estandar (posible bug). En el
    port: flechas + WASD.
11. **Duracion de la fruta fija en 10 s** (el arcade varia entre 9 y 10 s por
    nivel, Dossier p.11; es una diferencia menor).
12. **Sin intermissions ni escenas de café**, sin demo jugada por IA (la demo
    es una grabacion `AttractMode.pmg`), sin dificultad "hard" (Tabla A.2),
    sin contador de nivel >13 (dibuja "N x"). Niveles ilimitados con datos del
    21 (el arcade satura a 255).
13. **Colision con 2 px de tolerancia** para evitar el bug de atravesar
    fantasmas (`cGame.cls:607-617`): mejora consciente sobre el original.
14. **Patrones de animacion** de muerte/fin de nivel aproximados a los del
    arcade (tiempos 65/50 ms, 6 flashes de 200 ms), no identicos.

### 8.2 Recomendaciones concretas para PAC-MAN SereOS (C, sin libc, sin FPU)

**Arquitectura propuesta (equivalencia con el original):**

| Original | SereOS |
|---|---|
| `modMain` + `cGame` (ventana/bucle) | `apps/game/game.c`: maquina de estados (menu, jugando, pausa, gameover, win) y avance por paso cooperativo; el escritorio ya aporta ventana/eventos. |
| `cGame` orquestacion | `game.c` (counters, score, escenas) + `task_create("game", step, w)` con dt fijo. |
| `cMazeBuilder` + `cMaze` | `game_maze.c` con `pk_maze[][]` de `maze.c` (bitmask) y funciones `maze_available_dirs`, `maze_remove_dot`, `maze_completed`. |
| `cMazeLevel` | tabla const en `game_level.c` generada desde `levels.csv`. |
| `cPacMan` | `game_pacman.c` (posicion 1/256 px, cornering simplificado o cola de giro). |
| `cGhost`/`cGhosts` | `game_ghosts.c` (4 structs, target, planificacion por tile, pen). |
| `modSoundFX` | `game_audio.c` con PC speaker (o silencio). |
| `Settings.ini` | RAMFS (`fs_readfile/fs_writefile`) en `/home/pacman.cfg` para hi-score/ajustes. |
| PNG/WAV de terceros | **sprites y audio originales** generados por el equipo (RGB565/ASCII art propio). |

**Modelo de datos y bucle:**
- Mantener internamente la rejilla logica de **8 px** de `maze.c`; render a
  **16 px/tile** (28x16=448 px de ancho, 31x16=496 px de alto) centrado en la
  ventana del juego, con HUD arriba/abajo. (El original usaba 29 px/tile y
  ventana de 438x353 px; 16 px encaja mejor en 880x560.)
- Posiciones en punto fijo **1/256 px** (`int32_t x8_256`); velocidades por frame
  ya estan en `levels.csv` (`*_inc256`) y son todas enteras. Alternativa: 1/1024
  si se quiere mas precision; con 1/256 no hay error perceptible.
- Bucle de logica a **60 Hz fijos**: `acc_ms += dt_ms; while (acc_ms >= 1000/60)
  { step_game(); acc_ms -= 1000/60; }`. Con PIT a 100 Hz, `dt_ms = 10` cada
  tick (0 o 2 pasos con acumulador). Evitar `float`/`double`/`__udivdi3` en el
  bucle: usar enteros y comparaciones de **distancia al cuadrado** (el orden de
  `d²` coincide con el de `d`, no hace falta `sqrt`).
- PRNG determinista propio (LCG 32 bits) con semilla configurable, para
  reproducir patrones y para QA (marcadores serie).
- Animacion: Pac-Man con ciclo de 7 frames de boca a 60 Hz; fantasmas con 2
  frames cada 15 pasos (`mAnimFrame\15`, `cGhost.cls:362`); parpadeo de frightened
  en las ventanas de 12/12 frames; power pills 8/8; muerte y fin de nivel con
  temporizadores en frames (no `Sleep`).
- Entrada: `app->event` (KEY_DOWN/UP) + `input_key_down` para teclas mantenidas
  (el escritorio ya enruta solo a la ventana con foco); mantener
  "direccion mas reciente" y aplicarla cuando el tile actual tenga salida
  (equivalente al original). Flechas/WASD; P/Esc para pausa; Enter en menus.
- Render: solo el contenido del juego (el compositor fija el clip); usar
  `gfx_fill_rect`/`gfx_draw_sprite` RGB565 con transparencia `GFX_TRANSPARENT`;
  fondo de laberinto pre-renderizado en un buffer estatico; borrar dots solo en
  su celda (dirty rect). Sprites originales 16x16 o 24x24 por tile.
- Estados y puntuacion segun seccion 6; hi-score en RAMFS; marcador serial
  `GAME_START/GAME_PAUSE/GAME_OVER/GAME_WIN` para QA.
- No portar: Cairo, DirectSound, COM, INI de Windows, MP3/ACM, formularios VB6.

**Prioridad de implementacion sugerida:** (1) maze.c + dot logic; (2) Pac-Man
con movimiento/giro; (3) fantasmas con fase scatter/chase y AI; (4) frightened,
comer fantasmas, vidas/muerte; (5) fruta/puntuacion/HUD; (6) casa/liberaciones y
Elroy; (7) audio original y menus; (8) pulido/QA.

---

## 9. Licencias, atribucion y riesgo de redistribucion

**Del proyecto Paku-Paku:**
- No hay cabecera de licencia, autor ni copyright propio en ninguno de los
  ficheros fuente (revisados todos). El unico aviso es la pantalla de attract
  con `"(C) 1980 MIDWAY MFG. CO."` (`cGame.cls:776`), que es el copyright del
  arcade original, no una licencia del clon. `Settings.ini` incluye un hi-score
  de 134.780 (dato de partida del autor) y nicknames de fantasmas.
- Nombre de proyecto `prjPacMan`, ejecutable `Pac-Man.exe` (`prjPac-Man.vbp:21-23`):
  uso de marcas de Namco/Midway sin licencia.

**Bibliotecas de terceros (dependencias del original, no del port):**
- `vbRichClient5.dll` (Olaf Schmidt) — biblioteca COM con Cairo; cargada reg-free
  por `modRegfreeDlls.bas`, modulo tambien de Olaf Schmidt (dic. 2014,
  `modRegfreeDlls.bas:1-12`). El directorio `Bin\` que la contendria esta vacio
  en la extraccion. Licencia de vbRichClient: gratuita para uso no comercial,
  sujeta a sus terminos; **no redistribuir** sin comprobarla.
- `dsvb.tlb` "DirectSound8 for Visual Basic 6.0 type library by The trick
  v1.00" (`prjPac-Man.vbp:4`) y `modTrickDirectSound.bas`: wrapper de terceros;
  no reutilizable en C sin permiso/licencia.
- `DirectCOM.dll` (necesaria para el reg-free) referenciada en `modRegfreeDlls`.

**Fuentes tipograficas:**
- `prstartk.ttf` es "Press Start K", fuente bitmap de codeman38 (freeware,
  habitualmente libre para uso no comercial; verificar antes de redistribuir).
- `atari full.ttf` (272 KB) no se usa en el codigo; licencia desconocida.
- No se incluyen avisos de licencia en `Res/`.

**Imagenes y audio (riesgo alto):**
- `ghost1.png`/`ghost2.png` (48x48), frutas (32x32 o 48x48), `dead.png`,
  `retroghost1/2.png`, `Clydeeghost.png` (242x238), `Key-icon.png`: tamanos
  compatibles con rips/escalados del arcade o fan-art de Pac-Man. Los personajes,
  frutas y nombre son propiedad de Namco/Midway.
- WAVs: `eat fruit.wav`, `eat ghost.wav`, `extra life.wav`, `pacman death.wav`
  son de abril de 2004 y `intermission.wav` de 2004; `game start.wav` de 2017;
  `waka1/2`, `hunted/hunter siren`, `ghost respawn` de 2018. El origen
  (MAME/arcade o ediciones) no esta documentado. **Riesgo claro de infraccion
  si se redistribuyen.**
- `AttractMode.pmg` y `Thumbs.db`, `desktop.ini` son artefactos de Windows sin
  interes para el port.

**Recomendacion (obligatoria para SereOS):**
1. **NO incluir en el repositorio** ningun PNG/WAV/TTF de `Res/` ni el `.pmg`.
2. Crear **arte y audio originales** para PAC-MAN SereOS (sprites RGB565 propios,
   paleta y personajes originales o claramente diferenciados; el enunciado del
   proyecto pide un juego original inspirado en el genero, no un clon con assets
   de Namco). El laberinto/datos de juego pueden reproducirse como referencia de
   mecanicas, pero conviene un skin visual propio.
3. Audio sintetizado en C (PC speaker o SB16 propio), sin muestras de terceros.
4. No copiar codigo VB6 de terceros (`modTrickDirectSound`, `modRegfreeDlls`);
   el port reescribe todo en C nativo.
5. En la documentacion del juego, atribuir la inspiracion:
   *"Mecanicas inspiradas en Pac-Man (Namco, 1980); referencia de implementacion
   Paku-Paku (VB6, autor desconocido, sin licencia). Codigo, arte y audio de
   SereOS son originales."*

---

## 10. Que se adapta de Paku-Paku vs que se implementa nuevo

| Aspecto | Se adapta / reutiliza de Paku-Paku | Se implementa nuevo para PAC-MAN SereOS |
|---|---|---|
| Laberinto | Layout 28x31, 240 dots, 4 power pills, casa, puerta, tunel, zonas de giro prohibido (`maze.c`) | Render tileset propio 16 px; datos ya generados |
| Tiles y direcciones | Bitmask UP/RIGHT/DOWN/LEFT + DOT/POWER/TUNNEL/PEN (identico) | Estructura C y funciones de consulta/borrado |
| Tabla de niveles | 21 niveles: velocidades, fases, frightened, Elroy, fruta (`levels.csv`) | Tabla const C generada desde el CSV |
| Movimiento Pac-Man | Reglas de velocidad, wrap, pausas por dot/pill, giro en interseccion | Movimiento en punto fijo 1/256 px, cornering simplificado propio |
| IA de fantasmas | Objetivos por personalidad, orden de desempate, look-ahead 1 tile, zonas restringidas, Elite Elroy | Pathfinding entero sin FPU (distancias al cuadrado), PRNG propio |
| Casa/liberaciones | Umbrales de dots por nivel, post-muerte 7/17/32, timer 4/3 s (con correcciones) | Maquina de estados propia del pen y respawn |
| Modos | Fases scatter/chase exactas, frightened por nivel, parpadeo, pausas | Temporizadores en frames controlados por el paso cooperativo |
| Puntuacion | 10/50/200-400-800-1600, fruta 100-5000, vida extra 10k | Logica y HUD propios |
| Audio | Mapa de eventos (waka, sirenas, muerte, etc.) | Sintesis propia con PC speaker/SB16 (sin WAVs) |
| Render | Composicion por capas, animaciones de boca/ojos, colores de fantasmas | Motor grafico SereOS (gfx primitives + sprites RGB565) |
| Entrada | Idea de "direccion mas reciente" | Flechas/WASD via eventos del escritorio (sin GetAsyncKeyState) |
| Persistencia | Hi-score (idea) | RAMFS `/home/pacman.cfg` (sin INI de Windows) |
| Menu/atract | Referencia de pantallas (READY/GAME OVER/creditos) | Menu original, sin demo grabada ni assets de terceros |
| Dependencias | — | Nada de VB6/COM/Cairo/DirectSound; todo C nativo y sin libc |

---

## Anexo A. Inventario de ficheros auditados

| Fichero | Lineas | Uso en esta auditoria |
|---|---|---|
| `cGame.cls` | 910 | bucle, niveles, marcadores, colisiones, fruta, sonido, escenas |
| `cGhost.cls` | 476 | IA, movimiento, pen, velocidades, objetivos |
| `cMazeBuilder.cls` | 343 | mapa ASCII, tiles, render |
| `cPacMan.cls` | 234 | movimiento, giro, sprite, tunel |
| `cMazeLevel.cls` | 182 | tabla de niveles y fases |
| `modMain.bas` | 180 | arranque, recursos, settings |
| `modGameGlobals.bas` | 76 | constantes, enums y estado global |
| `modSoundFX.bas` | 135 | audio |
| `cMaze.cls` | 84 | API del laberinto |
| `modPacManAI.bas` | 81 | IA de testing |
| `modRegfreeDlls.bas` | 79 | carga COM |
| `cGhosts.cls` | 68 | contenedor de fantasmas |
| `frmSettings.frm` | 57 | codigo muerto |
| `modIniFile.bas` | 35 | INI |
| `modTrickDirectSound.bas` | 464 | wrapper DirectSound (no portado) |
| `frmMain.frm` | 19 | formulario dummy |
| `Settings.ini` | 15 | configuracion |
| **Total** | **3.438** | |

Recursos en `/tmp/paku/Res/`: 15 PNG (48x48 y 32x32 + promo 242x238), 12 WAV
(11.025 kHz mono 8 bits y 48 kHz estereo, 0.08-5.2 s), 2 TTF (`prstartk.ttf`,
`atari full.ttf`), `Thumbs.db`, `desktop.ini`. `Paku-Paku/Res/` esta vacio (los
recursos se distribuyen en el nivel superior). `Bin/` vacio (faltan DLLs COM).

## Anexo B. Defectos / rarezas del original detectadas

1. Entrada arriba/abajo con `GetAsyncKeyState(192)`/`(191)` — codigos no VK
   estandar; posible funcionamiento incorrecto segun teclado.
2. Fase scatter/chase no reiniciada al perder vida (seccion 8.1 punto 3).
3. Liberacion de Clyde en nivel 1 a 90 dots (arcade: 60).
4. Velocidad de fantasma asustado 2,5% menor que el arcade.
5. 4.a fase scatter de 10 frames en vez de 1.
6. `DoCagedMove` asigna en algunos casos un bitmask de varias direcciones a
   `mDirection` (`cGhost.cls:166-169`); funciona por el orden posterior de
   comprobaciones pero es fragil.
7. `frmSettings` no se usa; `Res/` duplicado y `Bin/` vacio: el proyecto tal cual
   no arranca sin las DLLs.
8. Assets y fuentes de terceros sin licencia; audio de formatos mezclados.
9. `mRegularCounter` y efectos de flash dependen de contadores que se reinician
   de forma peculiar (`:263-264`); el parpadeo exacto del arcade no se reproduce.
10. La demo/attract usa movimientos grabados (`AttractMode.pmg`), no IA; y el modo
    testing usa `modPacManAI` (paseo aleatorio), no la IA real de fantasmas.
11. Sin intermissions, sin dificultad hard, sin joystick; "nivel" dibujado como
    "N x" a partir del 14.
12. `modSoundFX` mezcla formatos/longitudes de buffer y `KillAllSounds` no
    detiene `SFXgamestart` ni `SFXextralife` (el de inicio queda sonando).

---

*Auditoria realizada leyendo integramente las fuentes VB6 y el PDF extraido con
`pdftotext -layout`. No se modifico ningun fichero de `/tmp/paku` ni del codigo
de SereOS; los unicos ficheros escritos son los de `docs/`.*
