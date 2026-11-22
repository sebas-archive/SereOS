# Referencias técnicas de PAC-MAN SereOS

Material **de referencia** usado para especificar el juego. No forma parte del
binario de SereOS y **no se redistribuye ningún recurso gráfico o de audio de
terceros**: son datos y constantes derivados de código/documentación de
referencia, más generadores reproducibles propios.

| Fichero | Contenido | Origen |
|---|---|---|
| `maze.txt` | laberinto ASCII completo 28x31 + mapa semántico, metadatos y validaciones | reconstruido de `cMazeBuilder.cls` (Paku-Paku, VB6) |
| `maze.c` | array C `pk_maze[31][28]` con bits de tile, constantes de inicio/pen/túnel/fruta y checks de compilación | generado desde `maze.txt` |
| `gen_maze.py` | generador reproducible del laberinto | propio |
| `levels.csv` | 21 niveles: fruta, velocidades (%, px/frame, px/s, 1/256 px), frightened, fases scatter/chase y Elroy | portado de `cMazeLevel.cls` |
| `gen_levels.py` | generador de `levels.csv` | propio |
| `constants.md` | constantes del original con citas `archivo:línea`, contrastadas con *The Pac-Man Dossier* | auditoría propia |

La auditoría completa (qué se adaptó, qué se reescribió y qué desviaciones hay
respecto al arcade) está en [../PAKU_AUDIT.md](../PAKU_AUDIT.md). La
documentación del juego implementado está en
[../PAKMAN_SEREOS.md](../PAKMAN_SEREOS.md).

## Aviso de licencias

* *Pac-Man* es una marca registrada de Bandai Namco; este proyecto no está
  afiliado ni patrocinado.
* El clon VB6 **Paku-Paku** y sus recursos (PNG/WAV/TTF y bibliotecas COM)
  son de terceros y **no se han copiado ni redistribuido** en SereOS. Solo se
  estudiaron su lógica y sus tablas como referencia técnica.
* Los sprites, la fuente y los efectos de sonido de SereOS son originales y se
  generan con los scripts propios del repositorio
  (`tools/gen_pacman_assets.py`, `tools/gen_audio.py`).
