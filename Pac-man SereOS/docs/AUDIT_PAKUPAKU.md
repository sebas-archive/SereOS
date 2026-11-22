# AUDITORIA PAKU-PAKU -> PAC-MAN SereOS (task-33)

**Fecha:** 2026-11-20 · **Estado:** auditoria de solo lectura; no se ha
modificado codigo de juego ni el OS.

> **Nota de estado (integracion final):** esta auditoria es historica y
> describe la referencia Paku-Paku y el estado del juego **antes** de la
> integracion definitiva de `Res`. El juego final usa **5 frutas** (CEREZA,
> FRESA, NARANJA, MANZANA, UVAS) en ciclo `(nivel-1) % 5` con valores
> 100/300/500/700/1000, y **7 PNG** de `Res` (5 frutas + 2 cuerpos de
> fantasma). La llave dorada del HUD es un icono **decorativo** junto a NIVEL
> (sprite procedural; `key.png` solo como procedencia), no una fruta. Ver
> `docs/GAME.md`, `README.md` y `docs/AUDIT_RESOURCES.md`.

## 0. Fuentes y metodo

Abreviaturas de citas (todas verificadas leyendo el codigo real):

- `PP:` = `/home/t1an/Descargas/Paku-Paku/` (proyecto VB6 de referencia).
- `RES:` = `/home/t1an/Descargas/Res/` (recursos PNG/WAV/TTF).
- `PS:` = `/home/t1an/Descargas/sereos02/PAC-MAN SereOS/` (implementacion actual).
- `SO:` = `/home/t1an/Descargas/sereos02/sistema operativo/`.

Lineas citadas con `archivo:linea` o `archivo:linea-linea`. Los conteos de dots
y de recursos se obtuvieron con scripts de extraccion en `/tmp` a partir de los
ficheros originales (no de resumenes). Se revisaron tambien las auditorias
previas (`SO:docs/PAKU_AUDIT.md`, `SO:docs/reference/levels.csv`); su contenido
se contrasta al final, sin asumirlo como cierto.

---

## 1. Resumen ejecutivo (respuestas directas)

| Pregunta | Respuesta verificada | Evidencia |
|---|---|---|
| Laberintos/layouts distintos | **1 unico layout**, 28x31 tiles jugables (VB filas 1..31, columnas 1..28), 240 dots + 4 power pills | `PP:cMazeBuilder.cls:39-69` (tabla unica), `:71-98`, `:170-196`; no existe otra tabla de mapa en el proyecto |
| Niveles/configuraciones | **21 configuraciones** (niveles 1..21); nivel 22+ reutiliza la 21 | `PP:cMazeLevel.cls:28` (`mLevels(21)`), `:96-100` ("all levels after 21 are the same"), `:101-182` |
| Progresion | Nivel 1..infinito, mismo mapa reconstruido en cada nivel; fin de partida solo al quedarse sin vidas | `PP:cGame.cls:69-75`, `:81-125`, `:154-160`, `:290-295` |
| Vidas / vida extra | 3 vidas; +1 vida al cruzar 10.000 puntos (una vez) | `PP:cGame.cls:55,65,691-695` |
| Recursos usados | **10 PNG** (8 frutas + Ghost1/Ghost2), **10 WAV**, **1 TTF** (`prstartk`) | `PP:modMain.bas:32-61`; `PP:modSoundFX.bas:25-34` |
| Recursos presentes pero NO usados | 5 PNG (`Clydeeghost.png`, `dead.png`, `Key-icon.png`, `retroghost1.png`, `retroghost2.png`), 1 WAV (`intermission.wav`), 1 TTF (`atari full.ttf`) | busqueda exhaustiva de referencias (ver §9) |
| Menus | **No hay menu de opciones**: el "menu" es attract mode + demo replay; Ajustes existe como formulario muerto (no esta en el .vbp ni se invoca) | `PP:cGame.cls:716-794`; `PP:prjPac-Man.vbp:5-18` (no lista `frmSettings`), `PP:frmSettings.frm:1-57` |
| Pausa | **No existe pausa** en la referencia; Esc abandona la partida y vuelve a attract | `PP:cGame.cls:811-815` |
| Demo/replay | Si: attract con tabla de personajes, `AttractMode.pmg` (64 movimientos), replay/guardar/cargar `.pmg`, modo testing con IA aleatoria | `PP:modMain.bas:18,152-178`; `PP:cGame.cls:36-67,188-193,474-487,795-826`; `PP:AttractMode.pmg` |
| Audio | 10 efectos WAV DirectSound, volumen 70 %, waka alternado, sirenas en loop con frecuencia variable, sonido de respawn de ojos | `PP:modSoundFX.bas:16-58,88-133` |
| Estado SereOS | Jugable y con menus/estados modernos, pero **no es fiel a Paku-Paku** en varias reglas, assets, audio, attract/demo/settings y nombre visible | ver §10 y §11 |

Consecuencia para la "version definitiva": el trabajo no es "anadir niveles"
(no hay mas layouts), sino **alinear reglas/configuraciones, sustituir recursos
por los de `Res`, implementar attract/demo/replay/ajustes y audio**, y adaptar
la UI/identidad a **PAC-MAN SereOS** en mayusculas.

---

## 2. Laberinto real

### 2.1 Un solo mapa

`cMazeBuilder.BuildMaze` contiene una unica tabla ASCII de 31 cadenas de 28
caracteres (`PP:cMazeBuilder.cls:39-69`). No hay parametro de layout, ni mapas
alternativos, ni carga de mapas externos; `cMaze.BuildNew` llama siempre a
`cMazeBuilder.BuildMaze` (`PP:cMaze.cls:63-67`) y `cGame.InitLevel` la invoca en
cada nivel (`PP:cGame.cls:290-295`). Por tanto **todos los niveles usan el mismo
laberinto** con distinta configuracion.

Constantes: `ROWS=32`, `COLS=29` (`PP:modGameGlobals.bas:55`) son cotas del
array `gTiles(-1 To COLS+1, ROWS)` (`:57`) para el tunel/padding; el mapa real
usa filas 1..31 y columnas 1..28 (28x31). `SQ_SZ=8` px logicos por tile,
`DEFAULT_SPEED=1.25` px/frame, `FPS=60` (`:59-62`). En la implementacion actual
el mapa es identico con indices 0-based (`PS:src/core/game_maze.c:15-39`) y
constantes 28x31 (`PS:src/core/pac_game.h:28-30`), 240 dots / 4 power
(`PAC_DOTS_TOTAL/PAC_POWER_TOTAL`, `PS:src/core/pac_game.h:44-45`).

### 2.2 Mapa (caracteres originales, `PP:cMazeBuilder.cls:39-69`)

```
 1 oooooooooooooooooooooooooooo
 2 o............OO............o
 3 o.OOOO.OOOOO.OO.OOOOO.OOOO.o
 4 o+OOOO.OOOOO.OO.OOOOO.OOOO+o
 5 o.OOOO.OOOOO.OO.OOOOO.OOOO.o
 6 o..........................o
 7 o.OOOO.OO.OOOOOOOO.OO.OOOO.o
 8 o.OOOO.OO.OOOOOOOO.OO.OOOO.o
 9 o......OO....OO....OO......o
10 oooooo.OOOOO OO OOOOO.oooooo
11 XXXXXo.OOOOO OO OOOOO.oXXXXX
12 XXXXXo.OO          OO.oXXXXX
13 XXXXXo.OO oooppooo OO.oXXXXX
14 oooooo.OO oPPPPPPo OO.oooooo
15 TTTTTT.   oPPPPPPo   .TTTTTT
16 oooooo.OO oPPPPPPo OO.oooooo
17 XXXXXo.OO oooooooo OO.oXXXXX
18 XXXXXo.OO          OO.oXXXXX
19 XXXXXo.OO OOOOOOOO OO.oXXXXX
20 oooooo.OO OOOOOOOO OO.oooooo
21 o............OO............o
22 o.OOOO.OOOOO.OO.OOOOO.OOOO.o
23 o.OOOO.OOOOO.OO.OOOOO.OOOO.o
24 o+..OO.......  .......OO..+o
25 oOO.OO.OO.OOOOOOOO.OO.OO.OOo
26 oOO.OO.OO.OOOOOOOO.OO.OO.OOo
27 o......OO....OO....OO......o
28 o.OOOOOOOOOO.OO.OOOOOOOOOO.o
29 o.OOOOOOOOOO.OO.OOOOOOOOOO.o
30 o..........................o
31 oooooooooooooooooooooooooooo
```

Leyenda original: `PP:cMazeBuilder.cls:38`:
`O` pared interior gruesa, `o` borde fino, `p` puerta del pen, `P` interior del
pen, `.` dot, `+` power pill, `T` tunel, `X` zona exterior no jugable,
espacio = camino sin dot.

Conteos exactos (script sobre `PP:cMazeBuilder.cls:39-69`):
**240 `.`**, **4 `+`**, 12 `T` (6 por tunel), 18 `P`, 2 `p`, 60 `X`, 44 espacios.
Coincide con `SO:docs/reference/maze.txt` (maze reconstruido) y con la
implementacion SereOS (`PS:src/core/game_maze.c:38-65`, donde `.`/`+`/`P`/`p`/`T`
se clasifican en `classify()`).

### 2.3 Tunel, pen y puerta

- Tunel en fila VB 15 (fila C 14): 6 T por lado (`PP:cMazeBuilder.cls:53`).
  Parche de direcciones del tunel: `gTiles(0,15)`, `gTiles(-1,15)`,
  `gTiles(29,15)`, `gTiles(30,15)` (`:190-194`). Wrap de Pac-Man y fantasmas:
  `x > 30*SQ_SZ -> 0`, `x < 0 -> 30*SQ_SZ` (`PP:cPacMan.cls:156`,
  `PP:cGhost.cls:122`). En SereOS: fila C 14 marcada `T` y wrap en
  `PS:src/core/game_entities.c:32-39` (`wrap_axis_x`), con borde transitable en
  `PS:src/core/game_maze.c:258-265` (fila 14, col -1/28).
- Pen: filas VB 14-16, columnas 12-17 (`PP:cMazeBuilder.cls:51-55`), puerta en
  fila VB 13, columnas 14-15 (`:51`). Se parchea como `eIsPen` en `:154-166`.
  En SereOS: `PAC_PEN_COL0..1=11..16`, `PAC_PEN_ROW0..1=13..15`,
  `PAC_DOOR_ROW=12`, `PAC_DOOR_COL0..1=13..14` (`PS:src/core/pac_game.h:73-80`)
  (equivalente 0-based).
- Fruta: se dibuja en `(15*tile, 18.5*tile)` y se come cuando
  `Round(x/8)=15 && row=18` (`PP:cGame.cls:420,559`); equivale a tile C (14,17)
  y en SereOS es `PAC_FRUIT_COL/ROW=14/17` (`PS:src/core/pac_game.h:70-71`).

---

## 3. Niveles y configuraciones (21 reales)

`cMazeLevel.InitLevelData` recorre `i = 1 To 21` (`PP:cMazeLevel.cls:101-103`)
y rellena `mLevels(21)` (`:28`). `LevelData()` usa `mLevels(21)` para cualquier
nivel >21 (`:96-100`). Tabla exacta extraida de `PP:cMazeLevel.cls:106-178`:

| Nivel | Fruta (imagen) | Valor | Pac % | Cazador % | Ghost % | Fright s | PhaseTimes (scatter/chase...) | Elroy1 | Elroy2 |
|---:|---|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | Cherry | 100 | 80 | 90 | 75 | 6 | 7,20,7,20,5,20,5,-1 | 20 | 10 |
| 2 | Strawberry | 300 | 90 | 95 | 85 | 5 | 7,20,7,20,5,1033,0.16666,-1 | 30 | 15 |
| 3 | Peach | 500 | 90 | 95 | 85 | 4 | 7,20,7,20,5,1033,0.16666,-1 | 40 | 20 |
| 4 | Peach | 500 | 90 | 95 | 85 | 3 | 7,20,7,20,5,1033,0.16666,-1 | 40 | 20 |
| 5 | Apple | 700 | 100 | 100 | 95 | 2 | 5,20,5,20,5,1037,0.16666,-1 | 40 | 20 |
| 6 | Apple | 700 | 100 | 100 | 95 | 5 | 5,20,5,20,5,1037,0.16666,-1 | 50 | 25 |
| 7 | Grapes | 1000 | 100 | 100 | 95 | 2 | 5,20,5,20,5,1037,0.16666,-1 | 50 | 25 |
| 8 | Grapes | 1000 | 100 | 100 | 95 | 2 | 5,20,5,20,5,1037,0.16666,-1 | 50 | 25 |
| 9 | Galaxian | 2000 | 100 | 100 | 95 | 1 | 5,20,5,20,5,1037,0.16666,-1 | 60 | 30 |
| 10 | Galaxian | 2000 | 100 | 100 | 95 | 5 | 5,20,5,20,5,1037,0.16666,-1 | 60 | 30 |
| 11 | Bell | 3000 | 100 | 100 | 95 | 2 | 5,20,5,20,5,1037,0.16666,-1 | 60 | 30 |
| 12 | Bell | 3000 | 100 | 100 | 95 | 1 | 5,20,5,20,5,1037,0.16666,-1 | 80 | 40 |
| 13 | Key | 5000 | 100 | 100 | 95 | 1 | 5,20,5,20,5,1037,0.16666,-1 | 80 | 40 |
| 14 | Key | 5000 | 100 | 100 | 95 | 3 | 5,20,5,20,5,1037,0.16666,-1 | 80 | 40 |
| 15 | Key | 5000 | 100 | 100 | 95 | 1 | 5,20,5,20,5,1037,0.16666,-1 | 100 | 50 |
| 16 | Key | 5000 | 100 | 100 | 95 | 1 | 5,20,5,20,5,1037,0.16666,-1 | 100 | 50 |
| 17 | Key | 5000 | 100 | 100 | 95 | 0 | 5,20,5,20,5,1037,0.16666,-1 | 100 | 50 |
| 18 | Key | 5000 | 100 | 100 | 95 | 1 | 5,20,5,20,5,1037,0.16666,-1 | 100 | 50 |
| 19 | Key | 5000 | 100 | 100 | 95 | 0 | 5,20,5,20,5,1037,0.16666,-1 | 120 | 60 |
| 20 | Key | 5000 | 100 | 100 | 95 | 0 | 5,20,5,20,5,1037,0.16666,-1 | 120 | 60 |
| 21 | Key | 5000 | 90 | 100 | 95 | 0 | 5,20,5,20,5,1037,0.16666,-1 | 120 | 60 |

Notas verificadas:
- Frutas por grupos: 1 Cherry; 2 Strawberry; 3-4 Peach; 5-6 Apple; 7-8
  Grapes; 9-10 Galaxian; 11-12 Bell; 13+ Key
  (`PP:cMazeLevel.cls:106-122`).
- Velocidades: L1 80/90/75; L2-4 90/95/85; L5-20 100/100/95; L21 90/100/95
  (`:124-132`). "Cazador" = velocidad de Pac-Man mientras dura el power pill
  (`PacmanAsHunterSpeed`, `:72-73`, aplicada en `PP:cGame.cls:585`).
- Frightened: L1=6; L2/6/10=5; L3=4; L4/14=3; L5/7/8/11=2;
  L9/12/13/15/16/18=1; resto 0 (`:163-178`).
- Elroy1/Elroy2 exactos (`:143-161`), Elroy2 = Elroy1/2 (`:161`).
- PhaseTimes: L1 `7,20,7,20,5,20,5,-1`; L2-4 `7,20,7,20,5,1033,0.16666,-1`;
  L5+ `5,20,5,20,5,1037,0.16666,-1` (`:134-141`). La maquina de fases alterna
  scatter/chase y usa `FPS=60` (`PP:cMazeLevel.cls:43-59`,
  `PP:modGameGlobals.bas:61`). Nivel 22+ = fila 21 (sin cambios).
- Nivel completado: `Maze.Completed` exige power pills=0 y dots=0
  (`PP:cMaze.cls:30-32`); `cGame.LevelLoop` termina y `DoEndOfLevelScene`
  parpadea el mapa 7 veces (~1,4 s, 200 ms por fase) y pasa al siguiente nivel
  (`PP:cGame.cls:115-120,156-181`; incremento en `:69-72`).
- No hay condicion de "victoria final": se juega indefinidamente.

### 3.1 Divergencias de niveles en SereOS

`PS:src/core/game_ai.c:34-56` contiene 21 filas, pero:
- **Clyde L1**: SereOS `exit_dots=60` (`PS:src/core/game_ai.c:204`); Paku es
  `150 dots restantes` = **90 comidos** (`PP:cGame.cls:207`). El comentario
  actual de `game_ai.c` y la auditoria previa lo reconocen como valor arcade,
  no Paku.
- **Frightened speed**: SereOS usa 50/55/60 % (`PS:src/core/game_ai.c:109-112`);
  Paku usa `GhostSpeed/2 + 10` = **47,5/52,5/57,5 %**
  (`PP:cGhost.cls:223-224`). `SO:docs/reference/levels.csv` ya recogia 47.5.
- **Fruit duration**: SereOS 9 s (`PAC_FRUIT_MS`, `PS:src/core/pac_game.h:49`);
  Paku 10 s (`mBonusFruitAvailableCounter = 10*FPS`, `PP:cGame.cls:225`).
- **Fruit images/names**: SereOS usa CEREZA, FRESA, NARANJA, MANZANA, UVAS,
  MELON, CAMPANA, ESTRELLA (`PS:assets/sprites.c:711-713`); Paku usa
  Cherry, Strawberry, **Peach**, Apple, Grapes, **Galaxian**, Bell, **Key**
  (`PP:modMain.bas:36`, `PP:cMazeLevel.cls:106-122`). Faltan Peach, Galaxian
  y Key; sobran Naranja/Melon/Estrella.
- **Fases tras muerte**: SereOS reinicia la tabla en cada muerte
  (`PS:src/core/game.c:227-228` llama a `pac_ai_level_init`); Paku conserva
  `mPhaseNumber/mPhaseCounter` al reaparecer (solo reinicia el nivel al
  empezar; `PP:cGame.cls:89,290-336`), otra divergencia ya senalada en
  `SO:docs/PAKU_AUDIT.md`.
- **Elroy en scatter**: correcto en SereOS (`PS:src/core/game_ai.c:312-320`)
  y en Paku (`PP:cGhost.cls:420-427`).

---

## 4. Pac-Man

| Elemento | Referencia (Paku-Paku) | Implementacion actual | Accion |
|---|---|---|---|
| Unidades/movimiento | Currency, `SQ_SZ=8`, px/frame = `1.25 * speed%/100`; 60 FPS (`PP:cPacMan.cls:99`, `PP:modGameGlobals.bas:59-62`) | Q8.8, tile 16 px, base 150 px/s (9,375 tiles/s), mismas escalas porcentuales (`PS:src/core/pac_game.h:35-41`, `PS:src/core/game_entities.c:170-200`) | Preservar (equivalencia de tiles/s verificada) |
| Inicio | `Init 14.5, 24, eLeft` -> `x=120` px logicos, tile VB col 15/fila 24 = tile C (14,23) (`PP:cGame.cls:316`; `PP:cPacMan.cls:24-31`) | `PAC_SPAWN_PAC_COL=13,ROW=23` (`PS:src/core/pac_game.h:60-61`) = tile C (13,23) | Adaptar (col -1 respecto a la referencia; mismo pasillo hueco, impacto bajo pero debe decidirse) |
| Velocidad por nivel | `PacmanSpeed` / `PacmanAsHunterSpeed` (`PP:cGame.cls:297,585`) | `pac_ai_pacman_speed` con `fright_ms` (`PS:src/core/game_ai.c:87-93`) | Preservar |
| Direccion solicitada | `SetDirection`: rechaza 0/actual/cornering/direccion invalida; acepta giro perpendicular con cornering; el input se lee cada frame (`PP:cPacMan.cls:50-92`, `PP:cGame.cls:464-552`) | `requested`, giro instantaneo al centro de tile o inversion inmediata; **sin cornering** (`PS:src/core/game_entities.c:150-215`, `PS:src/core/game_input.c`) | Implementar cornering / pre-turn point |
| Cornering | Deslizamiento durante el giro hasta completar el tile (`PP:cPacMan.cls:93-152`) | No existe; el giro solo ocurre en el centro (`PS:src/core/game_entities.c:200-215`) | Implementar |
| Tunel | wrap en 240 px logicos (`PP:cPacMan.cls:156`) | wrap en 448 px/16 px tile, bordes fila14 (`PS:src/core/game_entities.c:32-39`) | Adaptar/verificar equivalencia |
| Comer dot/power | digest 1 frame dot, 3 frames power (`PP:cGame.cls:565-588`); puntos 10/50 | digest 16/48 ms (`PS:src/core/game.c:105-118`) | Preservar (equivalente a 60 Hz) |
| Muerte | escena de giro+fade ~0,845 s + 1 s + fade 1 s + 1 s sleep (`PP:cGame.cls:632-676`) | `PAC_DEATH_MS=1700` (`PS:src/core/pac_game.h:47`) | Adaptar duracion/animacion |
| Animacion boca | angulo -15/frame, ciclo 270..360 (`PP:cPacMan.cls:154`) | 3 frames cada 70 ms (`PS:src/core/game_entities.c:230-235`) | Adaptar si se busca fidelidad |
| Controles | Z=izq, X=der, teclas 192/191 arriba/abajo (`PP:cGame.cls:479-482`) | Flechas/WASD (`PS:src/core/game_input.c:41-62`) | Decidir: preservar accesibilidad o mapear original; documentar |

El movimiento de SereOS es correcto en colision/paredes y velocidad global,
pero **no implementa el cornering ni el input de referencia**, y el spawn esta
una columna a la izquierda.

---

## 5. Fantasmas (IA, pen, velocidades)

### 5.1 Personalidades y objetivos (codigo real)

Tabla base en `PP:cGhost.cls:412-475` (comentario: Dossier).

| Fantasma | Modo chase | Modo scatter | Evidencia |
|---|---|---|---|
| Blinky (eShadow) | tile actual de Pac-Man | `(COLS-3, -2)`; **si esta en Cruise Elroy persigue tambien en scatter** | `PP:cGhost.cls:441-443,420-427` |
| Pinky (eSpeedy) | 4 tiles delante; si Pac-Man mira Up: `row-4` y `col-4` (bug original) | `(3, -2)` | `:450-458,430-431` |
| Inky (eBashful) | pivote = 2 tiles delante (con bug Up = `col-2,row-2`); objetivo = `2*pivote - tile(Blinky)` | `(COLS-1, ROWS)` | `:459-469,432-433` |
| Clyde (ePokey) | si distancia euclidea al tile de Pac-Man **<= 8** va a su esquina; si >8 persigue | `(1, ROWS)` | `:444-449,428-429` |

Constantes: `COLS=29`, `ROWS=32` (`PP:modGameGlobals.bas:55`); en C 0-based las
esquinas son (25,-3), (2,-3), (27,31), (0,31), que es exactamente lo que usa
SereOS (`PS:src/core/game_ai.c:290-298`). El resto de formulas coincide
(`PS:src/core/game_ai.c:323-360`), incluido el bug de Up de Pinky/Inky.

### 5.2 Decision en interseccion y modo frightened

- Orden de prueba: **Up, Left, Down, Right** con distancia euclidiana;
  no invierte; empate gana el primero (`PP:cGhost.cls:177-213`). SereOS usa el
  mismo orden con distancia al cuadrado (equivalente) (`PS:src/core/game_ai.c:361-430`).
- Frightened: **objetivo aleatorio** `Int(ROWS*Rnd), Int(COLS*Rnd)` y luego se
  elige direccion que minimiza distancia (`PP:cGhost.cls:435-436,187-211`).
  SereOS **elige una direccion aleatoria valida** (`PS:src/core/game_ai.c:397-404`), no un
  objetivo aleatorio: movimiento distinto.
- Zonas sin giro arriba: excepciones `(13,12),(16,12),(13,24),(16,24)` VB
  (`PP:cGhost.cls:383-387`), abiertas en frightened (`:241-245`). SereOS:
  `(12/15, 11/23)` 0-based (`PS:src/core/game_ai.c:365-372`), equivalente.
- Entrada/salida del pen: excepciones de tiles por fantasma
  (`PP:cGhost.cls:277-334`), regen en `(13/15/15/17,16)` VB
  (`:131-141`); SereOS usa BFS a `home_col` (14/12/16) fila 15
  (`PS:src/core/game_entities.c:340-390`), equivalente en destino.
- Inversion de direccion al cambiar modo (scatter<->chase) y al entrar en
  frightened solo si esta fuera del pen (`PP:cGhost.cls:229-255`). SereOS:
  invierte NORMAL/LEAVING sin comprobar pen
  (`PS:src/core/game_ai.c:216-235`), y si el nivel no tiene frightened
  (`fright_s=0`) **no invierte nada** (retorno temprano `:221-222`); Paku
  invierte igualmente (`PP:cGame.cls:586-588`).
- Ojos: velocidad 160 %, sin colision, vuelven a la casa y reaparecen con
  fade (`PP:cGhost.cls:147-155,217-218`). SereOS: 160 %, BFS, `REVIVING` 700 ms
  (`PS:src/core/game_ai.c:100-101`, `PS:src/core/game_entities.c:381-390`).

### 5.3 Velocidades reales

`cGhost.CurrentSpeed` (`PP:cGhost.cls:214-228`):
1. comido/ojos = **160 %**;
2. tunel = `(GhostSpeed+5)/2` = 40/45/50 %;
3. dentro del pen = **40 %**;
4. frightened = `GhostSpeed/2 + 10` = **47,5/52,5/57,5 %**;
5. normal = `mSpeed` (nivel + Elroy +5/+10).

SereOS implementa 160 % ojos, 40 % pen, tunel `(ghost+5)/2` y Elroy
(`PS:src/core/game_ai.c:95-124`), pero frightened usa 50/55/60 % (divergencia).

### 5.4 Salida del pen y Cruise Elroy (comportamiento exacto)

`cGame.CheckPreMoveCounters` (`PP:cGame.cls:195-245`):

- Al empezar el nivel / tras comer, si `mDotsRemainingAtLastPacmanDeath=240`:
  - dots restantes 240: sale **Pinky**; si nivel>1 tambien **Inky**; si
    nivel>2 tambien **Clyde** (`:197-201`);
  - 210: en nivel 1 sale **Inky** (30 comidos) (`:202-204`);
  - 190: en nivel 2 sale **Clyde** (50 comidos) (`:205-207`);
  - 150: en nivel 1 sale **Clyde** (90 comidos) (`:208`);
- Tras morir: umbrales relativos a los dots restantes al morir: Pinky -7,
  Inky -17, Clyde -32 (`:209-218`); SereOS usa `dots_eaten+7/+17/+32`
  (`PS:src/core/game.c:229-232`), equivalente.
- Si Pac-Man no come: cada **4 s (nivel <5) o 3 s (nivel >=5)** libera el
  siguiente fantasma (`:231-239`). SereOS usa **4 s fijos** y libera uno por
  ciclo (`PS:src/core/game_ai.c:251-267`).
- Cruise Elroy: al alcanzar los dots de Elroy1/Elroy2, `Blinky.Speed += 5`
  (o se fija a `GhostSpeed+5/+10` si Clyde ya salio) (`:227-229,241-245`).
  SereOS aplica +5/+10 por umbral a Blinky (`PS:src/core/game_ai.c:115-122`)
  y en scatter persigue (`:312-320`), fiel.

**Divergencias de release**: SereOS L1 Clyde a 60 (deberia 90); timer fijo 4 s
(deberia 4/3 s); reinicio de fases tras muerte (Paku no lo hace); spawn de
Blinky/Pinky una columna a la izquierda (ver §6).

---

## 6. Posiciones iniciales reales vs SereOS

`PP:cGhosts.cls:46-51`:

| Fantasma | VB Init (col,row) | px logicos (x,y) | Tile VB (1-based) | Tile C (0-based) | SereOS spawn C |
|---|---|---|---|---|---|
| Inky | 12.5, 15 | 104,124 | 13,15 | **12,14** | 12,14 (`PS:src/core/pac_game.h:66-67`) OK |
| Pinky | 14.5, 15 | 120,124 | 15,15 | **14,14** | 13,14 (**-1 col**) |
| Blinky | 14.5, 12 | 120,100 | 15,12 | **14,11** | 13,11 (**-1 col**) |
| Clyde | 16.5, 15 | 136,124 | 17,15 | **16,14** | 16,14 OK |
| Pac-Man | 14.5, 24 | 120,196 | 15,24 | **14,23** | 13,23 (**-1 col**) |

Conversion: `x=col*8+4`; `col_tile=Int(x/8)` (`PP:cPacMan.cls:24-31,167-169`;
`PP:cGhost.cls:344-347`). La diferencia es de una columna en Pac-Man,
Blinky y Pinky; Inky/Clyde coinciden. Impacto: posiciones de salida y el
"bug de Clyde" que depende de `x/8>15` (`PP:cGhost.cls:158`) pueden cambiar.

Direcciones iniciales: `PP:cGhosts.cls:47-50` Inky Up, Pinky Down, Blinky Up
(Shadow fuerza `NextPlannedDirection=Left` y abre pen,
`PP:cGhost.cls:32-37`), Clyde Up. SereOS: Blinky Left, resto Up
(`PS:src/core/game_entities.c:96-110`); Pinky Down no se reproduce
(impacto solo en el bob inicial).

---

## 7. Puntuacion, vidas, fruta, high score

| Elemento | Referencia | SereOS | Accion |
|---|---|---|---|
| Dot | 10 (`PP:cGame.cls:565-570`) | 10 (`PS:src/core/game.c:108-113`) | Preservar |
| Power pill | 50 (`:575-588`) | 50 (`PS:src/core/game.c:114-119`) | Preservar |
| Fantasmas | 200,400,800,1600; reset al terminar power; al 4º termina frightened (`PP:cGame.cls:249-259,690-698`) | 200<<idx, max 1600; al 4º termina fright (`PS:src/core/game_entities.c:455-480`) | Preservar |
| Fruta | valor por nivel (100..5000), 10 s, se come en tile (15,18) (`PP:cGame.cls:225,418-425,559-563`) | valores por nivel, 9 s, tile (14,17) C (`PS:src/core/game.c:315-323`, `PS:src/core/game_entities.c:243-260`) | Adaptar 10 s |
| Vidas | 3 (`PP:cGame.cls:55,65`); game over si 0 (`:74,706-715`) | 3 (`PAC_LIVES_START`; `PS:src/core/game.c:204`) | Preservar |
| Vida extra | al cruzar 10.000 una vez (`PP:cGame.cls:690-698`) | `PAC_EXTRA_LIFE_AT=10000` + flag (`PS:src/core/game.c:50-61`) | Preservar |
| High score | `Settings.ini [SCORES] Hi Score`, se escribe al terminar si `mScore>=gHiScore` (`PP:cGame.cls:75,136`; `PP:modMain.bas:123-148`) | RAMFS `/home/pacman_sereos.hi` en SereOS; XDG en Linux (`PS:src/core/game.c:63-98`, `PS:src/platform/linux/platform_linux.c` storage) | Adaptar persistencia (misma semantica) |
| HUD vidas/frutas | vidas dibujadas en fondo; frutas de niveles completados en fila inferior; "1 UP"/"HI" (`PP:cGame.cls:337-368,677-698`) | panel lateral VIDAS/FRUTAS/RÉCORD/NIVEL/ESTADO (`PS:src/render/game_render.c:321-427`) | Implementar HUD arcade (o adaptar diseno) |

---

## 8. Estados, menus, attract/demo, settings

### 8.1 Referencia

- `enumGameMode`: `eAttractMode`, `eHumanPlayer`, `eActionReplay`,
  `eDemoGame`, `eTesting` (`PP:modGameGlobals.bas:11-18`).
- `Game.Run` (`PP:cGame.cls:35-79`): attract (salvo testing), partida,
  vidas/game over, high score INI. No hay menu con opciones.
- **Attract mode** (`PP:cGame.cls:716-794`): pantalla negra + `1 UP`/`HI`
  score; tabla CHARACTER/NICKNAME con nicknames del INI y colores (SHADOW rojo,
  SPEEDY rosa, BASHFUL cian, POKEY naranja); sprites de fantasmas con ojos;
  Pac-Man; fantasmas asustados; dots/power de ejemplo; `10 PTS`/`50 PTS`;
  `(C) 1980 MIDWAY MFG. CO.`; `CREDIT 01`; espera **150*50 ms = 7,5 s** y pasa a
  `eDemoGame`.
- **Demo/replay**: `AttractMode.pmg` (64 pares `frame=direccion`, frames
  65..2710; direcciones 1/2/4/8) se reproduce en `eDemoGame`; en
  `eActionReplay` se puede cargar/salvar `.pmg`; se muestra `PRESS START`
  (demo) o `REPLAY` (`PP:modMain.bas:18,152-178`; `PP:cGame.cls:36-67,188-193,
  464-487,795-826`). Al pulsar Enter/Space/1 se inicia `eHumanPlayer`
  (`:816-820`).
- **Testing**: `Settings.ini [SETTINGS] TESTING` y `TEST SEED VALUE`; modo
  automático con `modPacManAI.RandomDirection` (`PP:modMain.bas:136-145`;
  `PP:cGame.cls:38,57-60,472-473`).
- **Teclas de referencia** (`PP:cGame.cls:795-826`): `L` cargar `.pmg`,
  `R` replay, `S` guardar `LastGame.pmg`, `A` overlay de IA,
  `Esc` volver a attract, `1/Espacio/Enter` empezar, `+/-` volumen ±10.
  **No hay pausa**.
- **Settings**: `frmSettings.frm` solo Classic/Modern, y **no esta en
  `prjPac-Man.vbp` ni se invoca** (`PP:prjPac-Man.vbp:5-18`,
  `PP:frmSettings.frm:24-49`, sin referencias en `.cls/.bas`). La apariencia
  se controla por `Settings.ini [APPEARANCE] CLASSIC` y `TILE SIZE`
  (`PP:modMain.bas:147-148`); valores actuales: Hi Score 134780, sonido 1,
  Tile Size 29, Classic 1, Testing 0, seed 332 (`PP:Settings.ini:1-15`).
- **Nicknames**: `Settings.ini [GHOST NICKNAMES]` se muestran en attract
  (`PP:cGame.cls:738-744`).

### 8.2 SereOS actual

Implementa menu moderno (Jugar/Instrucciones/Récord/Volver), pausa y overlays
(`PS:src/core/game.c:265-303`; `PS:src/render/game_render.c:531-611,726-910`),
pero **no tiene attract mode, demo/replay, testing, ajustes, ghost nicknames,
overlay de IA ni controles de referencia**. La pausa es una adicion de SereOS,
no de Paku. El nombre visible actual es **"PAC-MAN SereOS"**
(`PS:src/core/pac_game.h:18`, `PS:src/platform/sereos/game_app.c:70`,
`PS:src/platform/linux/platform_linux.c:359`), no `PAC-MAN SereOS`
(mayusculas) como pide la directiva.

---

## 9. Audio y recursos

### 9.1 Audio real (10 WAV, DirectSound8)

Carga en `PP:modSoundFX.bas:25-34`; reproduccion/loop en `:102-133`:
Game Start, waka1, waka2, eat ghost, hunted siren, hunter siren, eat fruit,
extra life, ghost respawn, pacman death. Volumen por defecto **70 %**, pasos
de ±10 % (`:36,39-58`); waka alterna 1/2 (`:113-119`); sirenas en loop; la
frecuencia base de `hunted siren` es **48000 Hz** + boost 0,1/0,2/0,3 segun
dots <=85/61/12 (`:88-101`); `GhostRespawn` se reproduce en loop y se detiene
al volver la sirena (`:120-132`); en demo/testing no suena (`:105`).
`intermission.wav` **no se usa** (no aparece en `modSoundFX.bas` ni en
`modTrickDirectSound.bas`; busqueda exhaustiva = 0 referencias).

SereOS usa un enum sintetizado (`PS:include/pac_platform.h:91-109`) y un
sintetizador de onda cuadrada en Linux (`PS:src/platform/linux/platform_linux.c:54-64`);
el OS SereOS solo ofrece efectos sintetizados (`SO:audio/audio.h:1-40`), **sin
reproduccion de WAV/PCM de fichero**. Consecuencia: para usar los WAV reales
en SereOS hace falta una extension del API de audio del kernel (kernel-sys) o
un reproductor PCM en el adaptador; no es viable solo con el scope actual.

### 9.2 Inventario de recursos (`/home/t1an/Descargas/Res`)

| Tipo | Total | Usados | No usados | Evidencia |
|---|---:|---:|---|---|
| PNG | 15 | **10**: cherry, strawberry, peach, apple, grapes, galaxian, bell, key, Ghost1, Ghost2 | 5: `Clydeeghost.png`, `dead.png`, `Key-icon.png`, `retroghost1.png`, `retroghost2.png` | `PP:modMain.bas:36,40,42-43`; busqueda de cada nombre en `*.cls/*.bas/*.frm/*.vbp` = 0 referencias |
| WAV | 11 | **10** (ver §9.1) | 1: `intermission.wav` | `PP:modSoundFX.bas:25-34`; 0 referencias a intermission |
| TTF | 2 | **1**: `prstartk.ttf` (font "Press Start K", `PP:modMain.bas:32,118`) | 1: `atari full.ttf` | 0 referencias a "atari full" |

Ademas el codigo usa fuentes del sistema no incluidas: Arial
(`PP:cMazeBuilder.cls:200`), Impact (`PP:cGame.cls:348,391,422`).
Los PNG de `Res` son de terceros (Namco/Midway) y los TTF/WAV tambien tienen
procedencia externa; la auditoria previa ya advirtio de **no redistribuirlos**
(`SO:docs/PAKU_AUDIT.md:35-36`). Antes de copiarlos al componente hace falta
decision explicita del usuario/Lead sobre derechos; la alternativa es
reproducir el mismo contenido con arte/audio originales.

---

## 10. Estado actual de PAC-MAN SereOS (mapa de correspondencia)

Tabla resumida (Archivo SereOS con lineas). Accion: **P**=Preservar,
**A**=Adaptar, **I**=Implementar, **N**=No aplica.

| Elemento | Referencia (Paku-Paku) | Estado SereOS (archivo:linea) | Accion |
|---|---|---|---|
| Laberinto unico 28x31, 240 dots, 4 power | `PP:cMazeBuilder.cls:39-69,170-196` | Identico en ASCII/constantes (`PS:src/core/game_maze.c:15-39`, `PS:src/core/pac_game.h:27-45`) | P |
| Tunel fila 15 VB, wrap | `PP:cPacMan.cls:156`; `PP:cGhost.cls:122`; `PP:cMazeBuilder.cls:190-194` | `PS:src/core/game_entities.c:32-39`; `PS:src/core/game_maze.c:258-265` | P (verificar equivalencia de bordes) |
| Pen/door/fruta posiciones | `PP:cMazeBuilder.cls:51-55,154-166`; `PP:cGame.cls:420,559` | `PS:src/core/pac_game.h:70-80`; `PS:src/core/game_entities.c:243-260` | P |
| 21 configuraciones, >21=21 | `PP:cMazeLevel.cls:28,96-100,101-182` | 21 filas (`PS:src/core/game_ai.c:34-56`), `ai_level` satura a 21 (`:57-64`) | A (faltan matices) |
| Frutas/images/valores | `PP:cMazeLevel.cls:106-122`; `PP:modMain.bas:36` | Valores ok pero imagenes CEREZA/NARANJA/MELON/ESTRELLA (`PS:assets/sprites.c:711-713`) | I (sustituir por Peach/Galaxian/Key/Res) |
| Frightened speed 47,5/52,5/57,5 | `PP:cGhost.cls:223-224` | 50/55/60 (`PS:src/core/game_ai.c:109-112`) | A |
| Frightened = objetivo aleatorio | `PP:cGhost.cls:435-436` | direccion aleatoria (`PS:src/core/game_ai.c:397-404`) | A |
| Inversion solo fuera del pen; tambien si fright=0 | `PP:cGhost.cls:229-255`; `PP:cGame.cls:586-588` | invierte LEAVING; retorno si fright=0 (`PS:src/core/game_ai.c:216-235`) | A |
| Salida de casa 0/30/50/90/0/50/0 | `PP:cGame.cls:195-208` | 0/30/**60**/0/50/0 (`PS:src/core/game_ai.c:200-213`) | A |
| Timer de liberacion 4 s/3 s | `PP:cGame.cls:231-239` | 4 s fijo (`PS:src/core/game_ai.c:251-267`) | A |
| Fases no se reinician al morir | `PP:cGame.cls:89,290-336` | reinicia (`PS:src/core/game.c:227-228`) | A |
| Cruise Elroy (+5/+10, persigue en scatter) | `PP:cGame.cls:227-229,241-245`; `PP:cGhost.cls:420-427` | implementado (`PS:src/core/game_ai.c:71-82,115-122,312-320`) | P |
| Objetivos Blinky/Pinky/Inky/Clyde | `PP:cGhost.cls:412-475` | formulas equivalentes (`PS:src/core/game_ai.c:300-360`) | P |
| Sin giro arriba (13/16, 12/24) VB | `PP:cGhost.cls:383-387` | (12/15, 11/23) C (`PS:src/core/game_ai.c:365-372`) | P |
| Ojos 160 %, pen 40 %, tunel | `PP:cGhost.cls:214-228` | igual salvo frightened (`PS:src/core/game_ai.c:95-124`) | P/A |
| Spawn Pac/Blinky/Pinky | `PP:cGame.cls:316`; `PP:cGhosts.cls:46-51` | col -1 en Pac/Blinky/Pinky (`PS:src/core/pac_game.h:60-68`) | A |
| Cornering/input | `PP:cPacMan.cls:50-160`; `PP:cGame.cls:464-552` | sin cornering (`PS:src/core/game_entities.c:150-235`) | I |
| Digestion dot/power 1/3 frames | `PP:cGame.cls:565-588` | 16/48 ms (`PS:src/core/game.c:105-118`) | P |
| Muerte animacion ~2,8 s | `PP:cGame.cls:632-676` | 1,7 s (`PS:src/core/pac_game.h:47`) | A |
| Nivel completado parpadeo 7x200 ms | `PP:cGame.cls:156-181` | overlay 2,4 s (`PS:src/core/game.c:386-390`; `PS:src/core/pac_game.h:48`) | A |
| READY: 1,5 s (nivel) / 4,5 s (inicio) | `PP:cGame.cls:320-330` | 2,2 s (`PS:src/core/pac_game.h:46`) | A |
| Puntuacion dot/power/ghost/fruta | `PP:cGame.cls:565-588,607-630,690-698` | igual (`PS:src/core/game.c:100-140`; `PS:src/core/game_entities.c:455-480`) | P |
| 3 vidas / extra life 10000 | `PP:cGame.cls:55,65,691-695` | igual (`PS:src/core/game.c:50-61,204`) | P |
| High score INI | `PP:cGame.cls:75,136`; `PP:modMain.bas:123-148` | storage plataforma (`PS:src/core/game.c:63-98`) | A (misma semantica, distinta persistencia) |
| Estados: attract/demo/replay/testing | `PP:cGame.cls:35-79,716-826`; `PP:modMain.bas:18,152-178` | No existen (`PS:src/core/pac_game.h:107-115` solo menu/instrucciones/record/juego/pausa/gameover/level) | I |
| Pausa | No existe en Paku | Existe (`PS:src/core/game.c:265-303`; `PS:src/render/game_render.c:783-821`) | N/decidir |
| Settings Classic/Modern, tile size, nicknames, testing | `PP:Settings.ini`; `PP:modMain.bas:120-150` | No existen | I |
| HUD "1 UP"/"HI"/vidas/frutas completadas | `PP:cGame.cls:337-368,677-698` | panel moderno (`PS:src/render/game_render.c:321-427`) | I/A |
| Audio WAV/sirenas/volumen/respawn | `PP:modSoundFX.bas:16-133` | sintesis por enum (`PS:include/pac_platform.h:91-109`; `PS:src/core/game.c:100-140`) | I/A (depende de audio PCM) |
| Assets PNG/ghost/fuentes arcade | `PP:modMain.bas:29-61` | sprites propios y fuentes OFL Inter (`PS:assets/sprites.c`; `PS:src/render/game_render.c`) | I (con decision de licencias) |
| Nombre visible | "Paku Paku" (`PP:frmMain.frm:4`; `PP:cGame.cls:129`) | "PAC-MAN SereOS" (`PS:src/core/pac_game.h:18`) | A -> "PAC-MAN SereOS" mayusculas |
| Demo grabada | `AttractMode.pmg` 64 movimientos | No existe | I |
| Controles | Z/X/192/191 | flechas/WASD (`PS:src/core/game_input.c:41-62`) | Decidir/adaptar |
| Persistencia record | Settings.ini | RAMFS/XDG (`PS:src/core/game.c:63-98`) | P (adaptacion de plataforma) |
| Integracion OS app_t | N/A (VB6) | `app_game`, name "PAC-MAN SereOS", 880x560 (`PS:src/platform/sereos/game_app.c:48-171`) | A (mayusculas) |

---

## 11. Divergencias priorizadas

**P0 - bloquean la "version definitiva" pedida**

1. **Assets/fuentes/audio no son los de `Res`**: sprites propios, frutas
   distintas, fuente Inter en vez de PrStartK, audio sintetizado en vez de los
   10 WAV. Requiere decision de licencias y conversion (ver §9.2/§12).
2. **Reglas de fantasmas no fieles a Paku**: Clyde L1 60 vs 90; frightened
   50/55/60 vs 47,5/52,5/57,5; movimiento frightened aleatorio por direccion
   vs objetivo aleatorio; inversion en pen/fright=0; timer 4 s fijo vs 4/3 s;
   spawn Pac/Blinky/Pinky desplazado; fases reiniciadas tras muerte.
3. **Faltan attract/demo/replay/testing/settings/nicknames/AI overlay**;
   la UI actual es un menu moderno SereOS, no la pantalla arcade.
4. **Audio**: SereOS no reproduce WAV (API solo sintetizada); hace falta
   extension del kernel o plan B documentado.
5. **Nombre visible**: debe ser `PAC-MAN SereOS` (mayusculas) y hoy es
   `PAC-MAN SereOS`; afecta app_t/window/menu/docs/capturas.

**P1 - fidelidad de juego/UI**

6. Cornering/input de Pac-Man no implementado; spawn una columna a la
   izquierda; animacion de muerte y tiempos READY/level-clear distintos;
   fruta 9 s vs 10 s.
7. HUD arcade (`1 UP`, `HI`, vidas, frutas de niveles completados) no existe.
8. No hay frutas Peach/Galaxian/Key; los valores economicos si coinciden.
9. Pausa (extra de SereOS) y controles flechas/WASD difieren de la referencia;
   decidir si se conservan como mejora de accesibilidad (documentar).

**P2 - menores**

10. Direccion inicial de Pinky (Down vs Up), animacion de boca, colores
    Classic/Modern, tile size configurable, semilla/testing, mensajes
    "PRESS START"/"REPLAY", copyright/credit de attract, high score INI vs
    storage de plataforma, limite de nivel 255 en SereOS vs infinito.

---

## 12. Plan de implementacion propuesto (por fases)

### Fase A - Decisiones y assets (bloqueantes)
1. Resolver licencias: los PNG/WAV/TTF de `Res` son de terceros (Namco/Midway
   y autores externos); `SO:docs/PAKU_AUDIT.md:35-36` recomienda no
   redistribuirlos. Opciones: (a) permiso explicito para empaquetar `Res`,
   (b) reproducir el mismo contenido con arte/audio originales equivalentes.
2. Definir fuente arcade: `prstartk.ttf` solo se usa como recurso privado de
   Windows; para SereOS/Linux hay que generar un atlas bitmap original
   inspirado en la estetica (Press Start 2P es OFL, verificar licencia del
   fichero concreto) o mantener Inter y documentar el cambio.
3. Convertir 10 PNG a RGB565 y los 10 WAV a PCM 8/16 bits embebido; comparar
   con los actuales. Incluir preview y documentar los 5 PNG/1 WAV/1 TTF no
   usados como "no portar".

### Fase B - Niveles/reglas (core)
4. Mantener **un solo laberinto** (no crear layouts nuevos).
5. Corregir release: L1 Clyde a 90; timer 4 s (<5) / 3 s (>=5); spawn
   Pac/Blinky/Pinky a columna C14; fases que no se reinician al morir.
6. Frightened: velocidad `GhostSpeed/2+10`; objetivo aleatorio por tile;
   inversion solo fuera del pen y tambien en niveles con fright=0.
7. Fruta 10 s; imagenes Peach/Galaxian/Key; HUD de frutas completadas.
8. Cornering/pre-turn point y animacion de boca; tiempos READY 1,5/4,5 s,
   muerte y parpadeo de nivel segun referencia.
9. Tests de regresion (referencia vs C): tabla de configuración, release,
   objetivos, frightened, colisiones, puntuación, vidas/extra life.

### Fase C - Estados arcade/menus
10. Attract mode: tabla CHARACTER/NICKNAME, puntos, copyright, credit,
    nicknames desde INI, 7,5 s.
11. Demo replay `AttractMode.pmg` (64 movimientos) y `eDemoGame`;
    action replay (L/S/R), testing (semilla), overlay AI (A), teclas
    documentadas; PRESS START/REPLAY.
12. Sustituir/envolver el menu actual: la directiva pide menus arcade; decidir
    si se conserva lanzador SereOS como pantalla externa o se elimina.
13. Settings: Classic/Modern, tile size, sound, nicknames, testing, seed,
    high score (o mapa a storage de plataforma).
14. Nombre `PAC-MAN SereOS` en app_t, window, menu, HUD, docs y capturas.

### Fase D - Audio
15. En Linux: reproducir los 10 WAV (SDL audio/streaming) con volumen 70 %,
    waka alternado, sirenas, respawn.
16. En SereOS: evaluar extension del API `audio` de kernel-sys para PCM; si no,
    aproximar con el sintetizador actual y documentar la limitacion (no se
    puede tocar el OS desde el componente).

### Fase E - Integracion SereOS y QA
17. `app_game`/`PAC_APP_NAME` mayusculas; ventana/titlebar; seriales
    GAME_*; record; teclas; build freestanding `libpacman.a`; enlace por
    kernel-sys.
18. Pruebas: harness de core ampliado (comparar tablas numericas contra
    `PP:cMazeLevel.cls`), smoke Linux, capturas de attract/partida/pausa/
    game over/nivel completado; QEMU real.

### Riesgos
- **Licencias de `Res`**: alto; sin permiso no se puede empaquetar.
- **Audio PCM en SereOS**: depende de kernel-sys; el componente no modifica el
  OS.
- **Replay determinista**: `AttractMode.pmg` esta indexado por frame a 60 FPS;
  SereOS usa paso fijo de 16 ms (62,5 Hz) y Linux 60 Hz; hay que fijar un reloj
  de 60 Hz o remapear frames, o la demo divergira.
- **Un solo laberinto**: la peticion de "todos los niveles" no implica mapas
  distintos; hay que comunicarlo para no inventar layouts.
- **Conflicto de diseno**: la UI moderna SereOS (task-30) choca con la estetica
  arcade solicitada; hay que decidir el alcance (menus arcade dentro del
  juego + lanzador SereOS fuera).
- **Regresiones**: el harness actual cubre 131 checks, pero esta calibrado con
  reglas arcade/Dossier, no con Paku; habra que actualizar expectativas
  (Clyde 90, fright 47.5, fases persistentes, etc.).

---

## 13. Verificacion de auditorias previas

- `SO:docs/PAKU_AUDIT.md` (772 lineas) es consistente con el codigo real en
  lo revisado: 1 mapa 28x31, 240 dots/4 power, tabla 1..21, formulas de IA,
  release y avisos de licencias; ademas ya detectaba las desviaciones de Paku
  frente al arcade (frightened 47,5 %, Clyde 90 en L1, fases que no se
  reinician al morir, fase scatter de 0,167 s). **Se confirma** con
  `PP:cGhost.cls:223-224`, `PP:cGame.cls:195-245,290-336`,
  `PP:cMazeLevel.cls:134-141`.
- `SO:docs/reference/levels.csv` coincide en los valores comprobados
  (fruta/valor, velocidades, frightened, fases, Elroy) con
  `PP:cMazeLevel.cls:101-182`; los valores de frightened 47,5/52,5/57,5 son
  correctos para Paku.
- La implementacion actual **no aplico esas correcciones de Paku**: conserva
  valores del Dossier/arcade (Clyde 60, frightened 50/55/60, fases
  reiniciadas, release 4 s fijo); los comentarios del codigo lo admiten
  (`PS:src/core/game_ai.c:109-112`). Esto es la brecha principal a cerrar en
  la fase B.
