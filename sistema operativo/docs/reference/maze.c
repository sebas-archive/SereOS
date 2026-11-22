/* docs/reference/maze.c - Laberinto de PAC-MAN SereOS (referencia Paku-Paku)
 *
 * GENERADO por gen_maze.py a partir de cMazeBuilder.cls (VB6), replicando
 * su algoritmo exacto. No editar a mano: regenerar con el script.
 *
 * Coordenadas: 0-based, fila 0..30 y columna 0..27.
 * VB original usa gTiles(Col,Row) con Col 1..28 / Row 1..31, asi que
 * pk_maze[fila_vb-1][col_vb-1] == pk_maze_local(col_vb,row_vb).
 *
 * Bits por tile (identicos a modGameGlobals.bas):
 *   UP=1 RIGHT=2 DOWN=4 LEFT=8   DOT=16 POWER=32 TUNNEL=64 PEN=128
 *   Un tile 0 es pared/zona externa (no transitable).
 *
 * Reglas del original que dependen de esta rejilla:
 *  - gTiles(0,15),(-1,15),(29,15),(30,15) son sentinelas de tunel.
 *  - wrap horizontal en x: x>30*SQ_SZ -> 0 ; x<0 -> 30*SQ_SZ.
 *  - tiles 0-based del tunel: fila 14, cols 0..27 (VB fila 15, cols 1..28)
 *    con direcciones LEFT en col 0 y RIGHT en col 27.
 *  - casa de fantasmas: filas 13..15, cols 11..16 (VB 14..16, 12..17).
 *  - puerta: fila 12, cols 13 y 14 (VB fila 13, cols 14 y 15).
 *  - Pac-Man inicia en VB (col 14.5, fila 24); ver PK_PAC_START_X/Y.
 *
 * Validacion: 240 dots (16) + 4 power pills (32) + 8 tiles de tunel (64).
 */
#include <stdint.h>

#define PK_ROWS 31
#define PK_COLS 28
#define PK_TILE_SQ 8        /* SQ_SZ: pixeles logicos por tile en Paku-Paku */

#define PK_UP        1u   /* eUp */
#define PK_RIGHT     2u   /* eRight */
#define PK_DOWN      4u   /* eDown */
#define PK_LEFT      8u   /* eLeft */
#define PK_DOT      16u   /* eHasDot */
#define PK_POWER    32u   /* eHasPowerPill */
#define PK_TUNNEL   64u   /* eIsTunnel */
#define PK_PEN     128u   /* eIsPen */

#define PK_PEN_COL0   11    /* casa: cols 11..16 */
#define PK_PEN_ROW0   13    /* casa: filas 13..15 */
#define PK_PEN_COLS    6
#define PK_PEN_ROWS    3
#define PK_DOOR_ROW   12    /* fila de la puerta */
#define PK_DOOR_COL0  13
#define PK_DOOR_COL1  14
#define PK_TUNNEL_ROW 14

/* Posiciones iniciales en unidades de 8 px logicos (SQ_SZ), tal como
 * las calcula el original: x = col*8+4, y = fila*8+4 (col/fila VB). */
#define PK_PAC_START_X      120   /* VB col 14.5 -> 14.5*8+4 */
#define PK_PAC_START_Y      196   /* VB fila 24   -> 24*8+4   */
#define PK_PAC_START_DIR    PK_LEFT
#define PK_BLINKY_START_X   120   /* VB 14.5,12 */
#define PK_BLINKY_START_Y   100
#define PK_PINKY_START_X    120   /* VB 14.5,15 */
#define PK_PINKY_START_Y    124
#define PK_INKY_START_X     104   /* VB 12.5,15 */
#define PK_INKY_START_Y     124
#define PK_CLYDE_START_X    136   /* VB 16.5,15 */
#define PK_CLYDE_START_Y    124

#define PK_FRUIT_TILE_COL  15    /* colision: Round(x/8)==15 y fila 18 */
#define PK_FRUIT_TILE_ROW  18
#define PK_FRUIT_X         120   /* centro: 15*8, 18.5*8 */
#define PK_FRUIT_Y         148

#define PK_DOTS_TOTAL      240
#define PK_POWER_PILLS     4

/* Tabla de tiles. Indices [fila][col] en 0-based. */
const uint8_t pk_maze[PK_ROWS][PK_COLS] = {
	{   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0 },  /* fila  0 */
	{   0,  22,  26,  26,  26,  26,  30,  26,  26,  26,  26,  26,  28,   0,   0,  22,  26,  26,  26,  26,  26,  30,  26,  26,  26,  26,  28,   0 },  /* fila  1 */
	{   0,  21,   0,   0,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,   0,   0,  21,   0 },  /* fila  2 */
	{   0,  37,   0,   0,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,   0,   0,  37,   0 },  /* fila  3 */
	{   0,  21,   0,   0,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,   0,   0,  21,   0 },  /* fila  4 */
	{   0,  23,  26,  26,  26,  26,  31,  26,  26,  30,  26,  26,  27,  26,  26,  27,  26,  26,  30,  26,  26,  31,  26,  26,  26,  26,  29,   0 },  /* fila  5 */
	{   0,  21,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,  21,   0 },  /* fila  6 */
	{   0,  21,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,  21,   0 },  /* fila  7 */
	{   0,  19,  26,  26,  26,  26,  29,   0,   0,  19,  26,  26,  28,   0,   0,  22,  26,  26,  25,   0,   0,  23,  26,  26,  26,  26,  25,   0 },  /* fila  8 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   0,   0,   0,   5,   0,   0,   5,   0,   0,   0,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila  9 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   0,   0,   0,   5,   0,   0,   5,   0,   0,   0,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila 10 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   6,  10,  10,  11,  10,  10,  11,  10,  10,  12,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila 11 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   5,   0,   0,   0,   0,   0,   0,   0,   0,   5,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila 12 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   5,   0, 128, 128, 128, 128, 128, 128,   0,   5,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila 13 */
	{  74,  74,  74,  74,  74,  74,  31,  10,  10,  13,   0, 128, 128, 128, 128, 128, 128,   0,   7,  10,  10,  31,  74,  74,  74,  74,  74,  74 },  /* fila 14 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   5,   0, 128, 128, 128, 128, 128, 128,   0,   5,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila 15 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   5,   0,   0,   0,   0,   0,   0,   0,   0,   5,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila 16 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   7,  10,  10,  10,  10,  10,  10,  10,  10,  13,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila 17 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   5,   0,   0,   0,   0,   0,   0,   0,   0,   5,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila 18 */
	{   0,   0,   0,   0,   0,   0,  21,   0,   0,   5,   0,   0,   0,   0,   0,   0,   0,   0,   5,   0,   0,  21,   0,   0,   0,   0,   0,   0 },  /* fila 19 */
	{   0,  22,  26,  26,  26,  26,  31,  26,  26,  27,  26,  26,  28,   0,   0,  22,  26,  26,  27,  26,  26,  31,  26,  26,  26,  26,  28,   0 },  /* fila 20 */
	{   0,  21,   0,   0,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,   0,   0,  21,   0 },  /* fila 21 */
	{   0,  21,   0,   0,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,  21,   0,   0,   0,   0,  21,   0 },  /* fila 22 */
	{   0,  35,  26,  28,   0,   0,  23,  26,  26,  30,  26,  26,  27,  10,  10,  27,  26,  26,  30,  26,  26,  29,   0,   0,  22,  26,  41,   0 },  /* fila 23 */
	{   0,   0,   0,  21,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,  21,   0,   0,   0 },  /* fila 24 */
	{   0,   0,   0,  21,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,  21,   0,   0,   0 },  /* fila 25 */
	{   0,  22,  26,  27,  26,  26,  25,   0,   0,  19,  26,  26,  28,   0,   0,  22,  26,  26,  25,   0,   0,  19,  26,  26,  27,  26,  28,   0 },  /* fila 26 */
	{   0,  21,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  21,   0 },  /* fila 27 */
	{   0,  21,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  21,   0,   0,  21,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  21,   0 },  /* fila 28 */
	{   0,  19,  26,  26,  26,  26,  26,  26,  26,  26,  26,  26,  27,  26,  26,  27,  26,  26,  26,  26,  26,  26,  26,  26,  26,  26,  25,   0 },  /* fila 29 */
	{   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0 },  /* fila 30 */
};

/* Mapa ASCII original de cMazeBuilder.cls (31 cadenas de 28 chars):
 * 'O' pared gruesa, 'o' borde fino, 'p' puerta, 'P' pen, '.' dot,
 * '+' power pill, 'T' tunel, ' ' camino, 'X' zona externa no jugable. */
const char *const pk_maze_ascii[PK_ROWS] = {
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
};

/* Comprobacion de tamano en tiempo de compilacion. */
typedef char pk_maze_rows_ok[(sizeof(pk_maze) / sizeof(pk_maze[0]) == PK_ROWS) ? 1 : -1];
typedef char pk_maze_cols_ok[(sizeof(pk_maze[0]) == PK_COLS) ? 1 : -1];

