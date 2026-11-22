/* gui/logo_ribbon_data.h - glifo RIBBON de SereOS (solo top bar)
 *
 * Segunda fuente de marca: assets/logo/ribbon_s_logo.png
 * (1296x1213 RGBA, S blanca sobre transparente), proporcionada
 * por el propietario del proyecto para la barra superior.
 * El resto de la interfaz usa el glifo OFICIAL (gui/logo_data.h).
 *
 * Mascaras de cobertura alfa 8bpp del canal A, umbral > 16
 * (elimina el halo de alfa 1..15) y normalizadas 255/254.
 * Caja real 834x944, proporcion 0.8835; el glifo se centra por
 * bbox sin deformar.
 *
 * GENERADO AUTOMATICAMENTE por tools/gen_logo.py; no editar a mano.
 * La tabla OFICIAL (gui/logo_data.*) es independiente y no cambia.
 */
#ifndef SEREOS_LOGO_RIBBON_DATA_H
#define SEREOS_LOGO_RIBBON_DATA_H
#include <stdint.h>

#define LOGO_RIBBON_COUNT 41u
#define LOGO_RIBBON_MIN_HEIGHT 8
#define LOGO_RIBBON_MAX_HEIGHT 64
#define LOGO_RIBBON_SRC_W 834
#define LOGO_RIBBON_SRC_H 944

typedef struct {
	uint16_t w, h;
	const uint8_t *mask;  /* cobertura alfa 8bpp, w*h bytes */
} logo_ribbon_glyph_t;

/* una entrada por altura de glifo ribbon generada (ascendente) */
extern const logo_ribbon_glyph_t logo_ribbon_glyphs[LOGO_RIBBON_COUNT];
extern const uint16_t logo_ribbon_heights[LOGO_RIBBON_COUNT];

#endif /* SEREOS_LOGO_RIBBON_DATA_H */
