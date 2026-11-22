/* gui/theme.c - tokens visuales de SereOS (paleta unica del sistema)
 *
 * Los valores de color son los definidos en gui/theme.h. Los alias legacy
 * (bg_deep, surface_hi, titlebar, etc.) se rellenan de forma coherente para
 * que el codigo antiguo siga compilando durante la transicion; el codigo
 * nuevo usa exclusivamente los nombres semanticos (bg, surface, accent...).
 */
#include "theme.h"
#include "text.h"

const theme_t theme = {
	/* fondos y superficies */
	.bg            = 0x0B0D12,   /* carbon azulado profundo */
	.bg_elevated   = 0x12151C,
	.surface       = 0x14171E,
	.surface_2     = 0x1A1E26,
	.surface_3     = 0x222732,
	.border        = 0x2A3040,
	.border_strong = 0x3A4256,
	.shadow        = 0x000000,

	/* texto */
	.text       = 0xF2F4F8,
	.text_dim   = 0xA8B0C0,
	.text_faint = 0x6E7788,

	/* acentos y estados */
	.accent      = 0x4C8DFF,
	.accent_soft = 0x1E3A66,
	.cyan        = 0x4CC9E0,
	.green       = 0x4CC38A,
	.amber       = 0xE0A84C,
	.red         = 0xE5534B,
	.white       = 0xFFFFFF,
	.black       = 0x000000,

	/* alias de compatibilidad */
	.bg_deep           = 0x0B0D12,
	.bg_mid            = 0x10131A,
	.bg_glow           = 0x16233A,
	.surface_hi        = 0x222732,
	.surface_low       = 0x0F1218,
	.border_hi         = 0x3A4256,
	.accent2           = 0x4CC9E0,
	.yellow            = 0xE0A84C,
	.window_bg         = 0x14171E,
	.titlebar          = 0x1A1E26,
	.titlebar_inactive = 0x14171E,
	.dock_bg           = 0x14171E,
	.topbar_bg         = 0x0B0D12,
	.menu_bg           = 0x1A1E26
};

uint32_t gui_color_blend(uint32_t fg, uint32_t bg, uint8_t alpha) {
	uint32_t a = alpha;
	uint32_t ia = 255u - a;
	uint32_t fr = (fg >> 16) & 0xFFu;
	uint32_t fg_c = (fg >> 8) & 0xFFu;
	uint32_t fb = fg & 0xFFu;
	uint32_t br = (bg >> 16) & 0xFFu;
	uint32_t bg_c = (bg >> 8) & 0xFFu;
	uint32_t bb = bg & 0xFFu;
	uint32_t r = (fr * a + br * ia) / 255u;
	uint32_t g = (fg_c * a + bg_c * ia) / 255u;
	uint32_t b = (fb * a + bb * ia) / 255u;

	return (r << 16) | (g << 8) | b;
}
