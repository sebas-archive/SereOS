/* PAC-MAN SereOS - tokens visuales compartidos (copia autocontenida del tema)
 *
 * Mismos colores que gui/theme.c de SereOS y sin simbolos del OS: el estado
 * se llama pac_theme para no colisionar con `theme` al enlazar el kernel.
 */
#include "pac_theme.h"

const pac_theme_t pac_theme = {
	.bg            = 0x0B0D12,
	.bg_elevated   = 0x12151C,
	.surface       = 0x14171E,
	.surface_2     = 0x1A1E26,
	.surface_3     = 0x222732,
	.border        = 0x2A3040,
	.border_strong = 0x3A4256,
	.shadow        = 0x000000,
	.text          = 0xF2F4F8,
	.text_dim      = 0xA8B0C0,
	.text_faint    = 0x6E7788,
	.accent        = 0x4C8DFF,
	.accent_soft   = 0x1E3A66,
	.cyan          = 0x4CC9E0,
	.green         = 0x4CC38A,
	.amber         = 0xE0A84C,
	.red           = 0xE5534B,
	.white         = 0xFFFFFF,
	.black         = 0x000000
};

uint32_t pac_color_blend(uint32_t fg, uint32_t bg, uint8_t alpha)
{
	uint32_t a = alpha;
	uint32_t ia = 255u - a;
	uint32_t fr = (fg >> 16) & 0xFFu, fgc = (fg >> 8) & 0xFFu, fb = fg & 0xFFu;
	uint32_t br = (bg >> 16) & 0xFFu, bgc = (bg >> 8) & 0xFFu, bb = bg & 0xFFu;
	uint32_t r = (fr * a + br * ia) / 255u;
	uint32_t g = (fgc * a + bgc * ia) / 255u;
	uint32_t b = (fb * a + bb * ia) / 255u;
	return (r << 16) | (g << 8) | b;
}
