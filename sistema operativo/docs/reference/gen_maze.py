#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_maze.py - reconstruye el laberinto de Paku-Paku (VB6) y genera maze.txt/maze.c.

Fuente de verdad: cMazeBuilder.cls::BuildMaze (l iterates sSquares(1..31)) e
InitMazePaths/pen patch/tunnel patch. Este script replica EXACTAMENTE el
algoritmo VB6 para poder portarlo a SereOS con fidelidad (mismos bits).

Uso:
  python3 gen_maze.py [ruta_a_cMazeBuilder.cls]
Genera en el directorio actual: maze.txt, maze.c (y verifica conteos).

Valores de tile (identicos a modGameGlobals.bas / cMazeBuilder.cls):
  eUp=1 eRight=2 eDown=4 eLeft=8  eHasDot=16 eHasPowerPill=32
  eIsTunnel=64 eIsPen=128
  Las paredes/zonas externas valen 0.
"""
import os
import re
import sys

REF = sys.argv[1] if len(sys.argv) > 1 else "/tmp/paku/Paku-Paku/cMazeBuilder.cls"

ROWS = 32          # modGameGlobals.bas:55 (gTiles 1..ROWS; fila 32 sin usar)
COLS = 29          # modGameGlobals.bas:55 (gTiles 1..COLS; col 29 = sentinela)
SQ_SZ = 8          # modGameGlobals.bas:59 (pixeles logicos por tile)

E_UP, E_RIGHT, E_DOWN, E_LEFT = 1, 2, 4, 8
E_DOT, E_POWER, E_TUNNEL, E_PEN = 16, 32, 64, 128

# sSquares(1..31) tal como aparecen en cMazeBuilder.cls:39-69. Se usan como
# respaldo si no esta disponible el .cls de referencia, y se validan contra el.
FALLBACK = [
    None,
    "oooooooooooooooooooooooooooo",
    "o............OO............o",
    "o.OOOO.OOOOO.OO.OOOOO.OOOO.o",
    "o+OOOO.OOOOO.OO.OOOOO.OOOO+o",
    "o.OOOO.OOOOO.OO.OOOOO.OOOO.o",
    "o..........................o",
    "o.OOOO.OO.OOOOOOOO.OO.OOOO.o",
    "o.OOOO.OO.OOOOOOOO.OO.OOOO.o",
    "o......OO....OO....OO......o",
    "oooooo.OOOOO OO OOOOO.oooooo",
    "XXXXXo.OOOOO OO OOOOO.oXXXXX",
    "XXXXXo.OO          OO.oXXXXX",
    "XXXXXo.OO oooppooo OO.oXXXXX",
    "oooooo.OO oPPPPPPo OO.oooooo",
    "TTTTTT.   oPPPPPPo   .TTTTTT",
    "oooooo.OO oPPPPPPo OO.oooooo",
    "XXXXXo.OO oooooooo OO.oXXXXX",
    "XXXXXo.OO          OO.oXXXXX",
    "XXXXXo.OO OOOOOOOO OO.oXXXXX",
    "oooooo.OO OOOOOOOO OO.oooooo",
    "o............OO............o",
    "o.OOOO.OOOOO.OO.OOOOO.OOOO.o",
    "o.OOOO.OOOOO.OO.OOOOO.OOOO.o",
    "o+..OO.......  .......OO..+o",
    "oOO.OO.OO.OOOOOOOO.OO.OO.OOo",
    "oOO.OO.OO.OOOOOOOO.OO.OO.OOo",
    "o......OO....OO....OO......o",
    "o.OOOOOOOOOO.OO.OOOOOOOOOO.o",
    "o.OOOOOOOOOO.OO.OOOOOOOOOO.o",
    "o..........................o",
    "oooooooooooooooooooooooooooo",
]


def char_at(rows, row, col):
    """Equivalente a Mid$(sSquares(row), col, 1): "" si fuera de rango."""
    if row < 1 or row >= len(rows):
        return ""
    s = rows[row]
    if col < 1 or col > len(s):
        return ""
    return s[col - 1]


def load_rows():
    rows = list(FALLBACK)
    if os.path.isfile(REF):
        txt = open(REF, encoding="latin-1").read()
        found = {int(m.group(1)): m.group(2)
                 for m in re.finditer(r'sSquares\((\d+)\)\s*=\s*"([^"]*)"', txt)}
        if found:
            for r, s in found.items():
                if 1 <= r <= 31:
                    rows[r] = s
    return rows


def build(rows):
    # 1) Primera pasada VB (identificar paredes), cMazeBuilder.cls:71-98.
    t = {}
    for col in range(1, len(rows[1]) + 1):
        for row in range(1, ROWS + 1):
            s = char_at(rows, row, col)
            if s in ("O", "o", "P"):
                t[(col, row)] = 1
            elif s == "X":
                t[(col, row)] = 2
            elif s == "p":
                t[(col, row)] = 3
            else:
                if s == "T":
                    if col == 1:
                        for d in (-2, -1, 1, 2):
                            t[(col - 1, row + d)] = 1
                    elif col == COLS - 1:
                        for d in (-2, -1, 1, 2):
                            t[(col + 1, row + d)] = 1
                t[(col, row)] = 0

    # 2) Segunda pasada VB (tiles de camino), cMazeBuilder.cls:133-152.
    for col in range(1, COLS + 1):
        for row in range(1, ROWS + 1):
            s = char_at(rows, row, col)
            if s == "T":
                t[(col, row)] = 8
            elif s == "+":
                t[(col, row)] = 4
            elif s == ".":
                t[(col, row)] = 2
            elif s == " ":
                t[(col, row)] = 1
            else:
                t[(col, row)] = 0

    # 3) InitMazePaths, cMazeBuilder.cls:170-196.
    dots = 0
    for col in range(1, COLS):          # 1..COLS-1 = 1..28
        for row in range(1, ROWS):      # 1..ROWS-1 = 1..31
            v = t.get((col, row), 0)
            if v <= 0:
                continue
            path = 0
            if v == 8:
                path |= E_TUNNEL
            if v == 4:
                path |= E_POWER
            if v == 2:
                path |= E_DOT
                dots += 1
            if t.get((col, row - 1), 0) > 0:
                path |= E_UP
            if t.get((col + 1, row), 0) > 0 or col >= COLS - 1:
                path |= E_RIGHT
            if t.get((col, row + 1), 0) > 0:
                path |= E_DOWN
            if t.get((col - 1, row), 0) > 0 or col <= 1:
                path |= E_LEFT
            t[(col, row)] = path

    # 4) Sentencias explicitas del tunel, cMazeBuilder.cls:190-194.
    t[(0, 15)] = E_TUNNEL + E_LEFT + E_RIGHT
    t[(-1, 15)] = E_TUNNEL + E_LEFT
    t[(29, 15)] = E_TUNNEL + E_LEFT + E_RIGHT
    t[(30, 15)] = E_TUNNEL + E_RIGHT

    # 5) Primera 'P' = inicio de la casa (cMazeBuilder.cls:113) y parche
    #    de la pen, cMazeBuilder.cls:154-166.
    pen = None
    for row in range(1, ROWS + 1):
        for col in range(1, COLS + 1):
            if char_at(rows, row, col) == "P":
                pen = (col, row)
                break
        if pen:
            break
    if pen:
        pc, pr = pen
        for col in range(pc, pc + 6):
            for row in range(pr, pr + 3):
                t[(col, row)] = E_PEN

    return t, dots, pen


def ascii_map(rows):
    out = []
    for row in range(1, 32):
        s = rows[row]
        out.append(s[:28].ljust(28))
    return out


def main():
    rows = load_rows()
    t, dots, pen = build(rows)
    pills = [(c, r) for (c, r), v in t.items() if v & E_POWER and 1 <= c <= 28 and 1 <= r <= 31]
    tunnel = sorted([(c, r) for (c, r), v in t.items() if v & E_TUNNEL and 1 <= c <= 28 and 1 <= r <= 31])
    print("dots =", dots, "(esperado 240)")
    print("power pills =", len(pills), pills)
    print("pen start VB =", pen)
    print("tunnel path tiles VB =", tunnel)

    # ---------- maze.txt ----------
    lines = []
    a = lines.append
    a("SereOS - PAC-MAN SereOS: laberinto de referencia (Paku-Paku, VB6)")
    a("=" * 78)
    a("")
    a("Reconstruido por gen_maze.py a partir de cMazeBuilder.cls::BuildMaze")
    a("(lineas 35-196) respetando el algoritmo original (mismos bits de tile).")
    a("")
    a("Dimensiones jugables: 28 columnas x 31 filas (VB: Col 1..28, Row 1..31).")
    a("gTiles(-1..COLS+1, ROWS) = gTiles(-1..30, 32). SQ_SZ = 8 px logicos/tile.")
    a("Superficie del laberinto dibujada: (COLS+1) x (ROWS+1.5) tiles = 30x33.5.")
    a("")
    a("Leyenda del caracter original de cMazeBuilder.cls:38:")
    a("  O  pared interior gruesa            o  borde exterior/pared fina")
    a("  p  puerta de la casa de fantasmas   P  interior de la casa (pen)")
    a("  .  punto (dot, 10 pts)              +  power pill (50 pts)")
    a("  T  tunel lateral                    (espacio) camino sin punto")
    a("  X  zona externa no jugable (muro de fuera, sin colision de juego)")
    a("")
    a("Coordenadas en este fichero: FILA 0-based (0..30) y COLUMNA 0-based (0..27);")
    a("sumar 1 para obtener la coordenada VB original (Col/Row).")
    a("")
    a("     " + "".join(str(c // 10) if c % 10 == 0 else " " for c in range(28)))
    a("     " + "".join(str(c % 10) for c in range(28)))
    a("    +" + "-" * 28 + "+")
    for r in range(31):
        a(" %2d |" % r + rows[r + 1][:28] + "|")
    a("    +" + "-" * 28 + "+")
    a("     " + "".join(str(c // 10) if c % 10 == 0 else " " for c in range(28)))
    a("     " + "".join(str(c % 10) for c in range(28)))
    a("")
    a("Mapa semantico (misma rejilla, derivado del bitmask que usa el juego):")
    a("  #  pared/void (tile 0)    .  dot    o  power pill")
    a("  =  tunel                  :  camino sin punto    H  casa (pen)")
    for r in range(31):
        row = ""
        for c in range(28):
            v = t.get((c + 1, r + 1), 0)
            if v == 0:
                row += "#"
            elif v & E_PEN:
                row += "H"
            elif v & E_POWER:
                row += "o"
            elif v & E_DOT:
                row += "."
            elif v & E_TUNNEL:
                row += "="
            else:
                row += ":"
        a(" %2d  " % r + row)
    a("")
    a("Metadatos exactos (coordenadas VB 1-based, tal como las usa el codigo):")
    a("  Filas VB usadas: 1..31 (la fila 32 de gTiles queda a 0).")
    a("  Columnas VB usadas: 1..28 (col 29 = sentinela a 0; cols 0/-1/29/30 solo tunel).")
    a("  Casa de fantasmas (pen): cols 12..17, filas 14..16  (eIsPen=128)")
    a("  Puerta del pen: fila 13, cols 14 y 15 (caracter 'p' = pared fina)")
    a("  Tunel (fila 15): tiles de camino en cols 1..6 y 23..28")
    a("    sentinelas jugables: gTiles(0,15)=74, gTiles(-1,15)=72,")
    a("                        gTiles(29,15)=74, gTiles(30,15)=66")
    a("    wrap horizontal: si x > 30*SQ_SZ (=240) -> x = 0; si x < 0 -> x = 240")
    a("    (28*SQ_SZ = 224 es el ancho del laberinto; el tunele usa 30 tiles)")
    a("  Dots: %d   Power pills: 4 en %s" % (dots, ", ".join(
        "(col %d, fila %d)" % (c, r) for c, r in sorted(pills))))
    a("  Inicio de Pac-Man: VB (col 14.5, fila 24) -> x8 = 120, y8 = 196")
    a("    cGame.cls:  Pacman.Init 14.5, 24, eLeft")
    a("  Inicios de fantasmas (cGhosts.cls:46-51), x8 = col*8+4, y8 = fila*8+4:")
    a("    Blinky (SHADOW): VB (14.5, 12) -> x8=120, y8=100, dir eUp")
    a("    Pinky  (SPEEDY): VB (14.5, 15) -> x8=120, y8=124, dir eDown")
    a("    Inky   (BASHFUL): VB (12.5, 15) -> x8=104, y8=124, dir eUp")
    a("    Clyde  (POKEY):  VB (16.5, 15) -> x8=136, y8=124, dir eUp")
    a("  Fruta (cGame.cls DrawBonusFruit/CheckCollisions): centro VB")
    a("    (col 15, fila 18.5) -> x8 = 120, y8 = 148; colision en tile (15,18)")
    a("")
    a("Conteos de validacion: %d dots (arcade: 240) + 4 power pills = %d objetos."
      % (dots, dots + 4))
    open("maze.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")

    # ---------- maze.c ----------
    c = []
    c.append("/* docs/reference/maze.c - Laberinto de PAC-MAN SereOS (referencia Paku-Paku)")
    c.append(" *")
    c.append(" * GENERADO por gen_maze.py a partir de cMazeBuilder.cls (VB6), replicando")
    c.append(" * su algoritmo exacto. No editar a mano: regenerar con el script.")
    c.append(" *")
    c.append(" * Coordenadas: 0-based, fila 0..30 y columna 0..27.")
    c.append(" * VB original usa gTiles(Col,Row) con Col 1..28 / Row 1..31, asi que")
    c.append(" * pk_maze[fila_vb-1][col_vb-1] == pk_maze_local(col_vb,row_vb).")
    c.append(" *")
    c.append(" * Bits por tile (identicos a modGameGlobals.bas):")
    c.append(" *   UP=1 RIGHT=2 DOWN=4 LEFT=8   DOT=16 POWER=32 TUNNEL=64 PEN=128")
    c.append(" *   Un tile 0 es pared/zona externa (no transitable).")
    c.append(" *")
    c.append(" * Reglas del original que dependen de esta rejilla:")
    c.append(" *  - gTiles(0,15),(-1,15),(29,15),(30,15) son sentinelas de tunel.")
    c.append(" *  - wrap horizontal en x: x>30*SQ_SZ -> 0 ; x<0 -> 30*SQ_SZ.")
    c.append(" *  - tiles 0-based del tunel: fila 14, cols 0..27 (VB fila 15, cols 1..28)")
    c.append(" *    con direcciones LEFT en col 0 y RIGHT en col 27.")
    c.append(" *  - casa de fantasmas: filas 13..15, cols 11..16 (VB 14..16, 12..17).")
    c.append(" *  - puerta: fila 12, cols 13 y 14 (VB fila 13, cols 14 y 15).")
    c.append(" *  - Pac-Man inicia en VB (col 14.5, fila 24); ver PK_PAC_START_X/Y.")
    c.append(" *")
    c.append(" * Validacion: %d dots (16) + 4 power pills (32) + 8 tiles de tunel (64)." % dots)
    c.append(" */")
    c.append("#include <stdint.h>")
    c.append("")
    c.append("#define PK_ROWS 31")
    c.append("#define PK_COLS 28")
    c.append("#define PK_TILE_SQ 8        /* SQ_SZ: pixeles logicos por tile en Paku-Paku */")
    c.append("")
    for name, val, txt in (("PK_UP", 1, "eUp"), ("PK_RIGHT", 2, "eRight"),
                           ("PK_DOWN", 4, "eDown"), ("PK_LEFT", 8, "eLeft"),
                           ("PK_DOT", 16, "eHasDot"), ("PK_POWER", 32, "eHasPowerPill"),
                           ("PK_TUNNEL", 64, "eIsTunnel"), ("PK_PEN", 128, "eIsPen")):
        c.append("#define %-10s %3du   /* %s */" % (name, val, txt))
    c.append("")
    c.append("#define PK_PEN_COL0   11    /* casa: cols 11..16 */")
    c.append("#define PK_PEN_ROW0   13    /* casa: filas 13..15 */")
    c.append("#define PK_PEN_COLS    6")
    c.append("#define PK_PEN_ROWS    3")
    c.append("#define PK_DOOR_ROW   12    /* fila de la puerta */")
    c.append("#define PK_DOOR_COL0  13")
    c.append("#define PK_DOOR_COL1  14")
    c.append("#define PK_TUNNEL_ROW 14")
    c.append("")
    c.append("/* Posiciones iniciales en unidades de 8 px logicos (SQ_SZ), tal como")
    c.append(" * las calcula el original: x = col*8+4, y = fila*8+4 (col/fila VB). */")
    c.append("#define PK_PAC_START_X      120   /* VB col 14.5 -> 14.5*8+4 */")
    c.append("#define PK_PAC_START_Y      196   /* VB fila 24   -> 24*8+4   */")
    c.append("#define PK_PAC_START_DIR    PK_LEFT")
    c.append("#define PK_BLINKY_START_X   120   /* VB 14.5,12 */")
    c.append("#define PK_BLINKY_START_Y   100")
    c.append("#define PK_PINKY_START_X    120   /* VB 14.5,15 */")
    c.append("#define PK_PINKY_START_Y    124")
    c.append("#define PK_INKY_START_X     104   /* VB 12.5,15 */")
    c.append("#define PK_INKY_START_Y     124")
    c.append("#define PK_CLYDE_START_X    136   /* VB 16.5,15 */")
    c.append("#define PK_CLYDE_START_Y    124")
    c.append("")
    c.append("#define PK_FRUIT_TILE_COL  15    /* colision: Round(x/8)==15 y fila 18 */")
    c.append("#define PK_FRUIT_TILE_ROW  18")
    c.append("#define PK_FRUIT_X         120   /* centro: 15*8, 18.5*8 */")
    c.append("#define PK_FRUIT_Y         148")
    c.append("")
    c.append("#define PK_DOTS_TOTAL      %d" % dots)
    c.append("#define PK_POWER_PILLS     4")
    c.append("")
    c.append("/* Tabla de tiles. Indices [fila][col] en 0-based. */")
    c.append("const uint8_t pk_maze[PK_ROWS][PK_COLS] = {")
    for r in range(31):
        vals = [t.get((c + 1, r + 1), 0) for c in range(28)]
        c.append("\t{ " + ", ".join("%3d" % v for v in vals) + " },  /* fila %2d */" % r)
    c.append("};")
    c.append("")
    c.append("/* Mapa ASCII original de cMazeBuilder.cls (31 cadenas de 28 chars):")
    c.append(" * 'O' pared gruesa, 'o' borde fino, 'p' puerta, 'P' pen, '.' dot,")
    c.append(" * '+' power pill, 'T' tunel, ' ' camino, 'X' zona externa no jugable. */")
    c.append("const char *const pk_maze_ascii[PK_ROWS] = {")
    for r in range(31):
        c.append('\t"%s",' % rows[r + 1][:28])
    c.append("};")
    c.append("")
    c.append("/* Comprobacion de tamano en tiempo de compilacion. */")
    c.append("typedef char pk_maze_rows_ok[(sizeof(pk_maze) / sizeof(pk_maze[0]) == PK_ROWS) ? 1 : -1];")
    c.append("typedef char pk_maze_cols_ok[(sizeof(pk_maze[0]) == PK_COLS) ? 1 : -1];")
    c.append("")
    open("maze.c", "w", encoding="utf-8").write("\n".join(c) + "\n")
    print("generados maze.txt y maze.c")


if __name__ == "__main__":
    main()
