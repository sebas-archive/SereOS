/* gui/logo_data.h - logotipo OFICIAL de SereOS
 *
 * Identidad oficial proporcionada por el propietario del proyecto
 * (assets/logo/official_logo.png, 1296x1213, fondo azul y S blanca).
 *
 * Sprites RGB565 completos (LOGO_SHAPE_PLAIN): escalados con LANCZOS
 * preservando la proporcion original; NO se redisenan, recortan ni
 * deforman.
 *
 * Mascaras alfa 8bpp del glifo S (FORMAS DE CONTENEDOR): extraidas del
 * mismo PNG oficial con alfa = clamp((R - 4)/(255 - 4)); en runtime
 * solo se tintan con gfx_blit_alpha8() y se centran en el contenedor.
 *
 * GENERADO AUTOMATICAMENTE por tools/gen_logo.py; no editar a mano.
 * Ambas tablas estan ordenadas por altura ascendente: se elige la
 * altura exacta si existe o, en su defecto, la mas cercana.
 */
#ifndef SEREOS_LOGO_DATA_H
#define SEREOS_LOGO_DATA_H
#include <stdint.h>

#define LOGO_SIZE_COUNT 13u

typedef struct {
	uint16_t w, h;
	const uint16_t *px;   /* RGB565, w*h pixeles, sin transparencia */
} logo_bitmap_t;

/* una entrada por altura generada (ascendente) */
extern const logo_bitmap_t logo_bitmaps[LOGO_SIZE_COUNT];
extern const uint16_t logo_heights[LOGO_SIZE_COUNT];

/* ------------------------------------------------------------------ */
/* glifo S blanco: mascaras de cobertura alfa 8bpp (fila a fila)      */
/* ------------------------------------------------------------------ */
#define LOGO_GLYPH_COUNT 55u
#define LOGO_GLYPH_MIN_HEIGHT 8
#define LOGO_GLYPH_MAX_HEIGHT 128
#define LOGO_GLYPH_SRC_W 366
#define LOGO_GLYPH_SRC_H 386

typedef struct {
	uint16_t w, h;
	const uint8_t *mask;  /* cobertura alfa 8bpp, w*h bytes */
} logo_official_glyph_t;

/* gui/logo.h define el enum logo_glyph_t (OFICIAL/RIBBON).  Para no
 * colisionar con ese nombre, aqui el struct se llama
 * logo_official_glyph_t; se mantiene el alias historico solo para el
 * codigo generado que aun usa logo_glyph_t. */
#ifndef SEREOS_LOGO_GLYPH_T_DEFINED
typedef logo_official_glyph_t logo_glyph_t;
#endif

/* una entrada por altura de glifo generada (ascendente) */
extern const logo_official_glyph_t logo_glyphs[LOGO_GLYPH_COUNT];
extern const uint16_t logo_glyph_heights[LOGO_GLYPH_COUNT];

#endif /* SEREOS_LOGO_DATA_H */
