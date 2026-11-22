# Logotipos oficiales de SereOS

En este directorio viven las dos fuentes de marca del proyecto. Ambas se
incluyen sin modificar; el kernel solo usa tablas ya generadas por
`tools/gen_logo.py` (nunca lee PNG en tiempo de ejecucion).

## `official_logo.png` (marca OFICIAL)

`official_logo.png` es la **identidad oficial de SereOS**, proporcionada por
el propietario del proyecto (imagen original: "Minimal White S Logo on
Blue.png"). Se usa en el splash, «Acerca de», pánico, menú, dock y como
compatibilidad PLAIN.

- Es la marca oficial de SereOS: **no se rediseña, recorta ni deforma**.
- Solo se escala con calidad (LANCZOS) preservando la proporcion original
  **1296/1213 = 1.0684**.
- En el kernel se usa a traves de `logo_draw()`, `logo_draw_splash()`,
  `logo_draw_about()`, `logo_draw_app_icon()`, `logo_draw_brand()` y de la
  compatibilidad `icons_draw_logo()` / `icons_logo_width()`.
- Los sprites RGB565 y las mascaras alfa 8bpp del glifo se generan con
  `tools/gen_logo.py` (ver `gui/logo_data.c`, `gui/logo_data.h` y
  `docs/LOGO.md`).

## `ribbon_s_logo.png` (marca RIBBON, solo top bar)

`ribbon_s_logo.png` es el asset **"Minimalist White Ribbon S Logo"**
proporcionado por el propietario del proyecto para la **barra superior**
(peticion del usuario: "en la top bar usa Minimalist White Ribbon S Logo").
Es un PNG RGBA de **1296x1213** con la S blanca (RGB ≈251,251,251) sobre
transparente; se copia byte a byte del original y no se modifica.

- Uso: **exclusivamente la top bar** (glifo `LOGO_GLYPH_RIBBON` via
  `logo_draw_topbar()`). El resto de la interfaz mantiene la marca oficial.
- Glifo real (alfa > 16): bbox **(243,190) 834x944 px**, proporcion
  **834/944 = 0,8835**. El PNG trae ~78.000 px de halo con alfa 1..15 que se
  descartan con umbral > 16; el alfa del cuerpo (≈254) se normaliza a 255.
- Sus mascaras alfa 8bpp (8..64 px) se generan con `tools/gen_logo.py` en
  `gui/logo_ribbon_data.c` / `gui/logo_ribbon_data.h`; la tabla oficial
  (`gui/logo_data.*`) no se toca.
- No se redibuja, recorta ni deforma: se centra por su bbox y se escala
  preservando 834/944.

## Propiedad y licencia

Ambos recursos fueron proporcionados por el propietario del proyecto para uso
exclusivo en SereOS (proyecto final de Sistemas Operativos, UMB 2026). No
redistribuir los logotipos fuera del proyecto sin permiso del propietario. Los
archivos originales se conservan sin modificaciones en este directorio.
