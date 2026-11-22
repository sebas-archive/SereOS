# Logotipo oficial de SereOS

SereOS usa un **único logotipo oficial** en toda la interfaz: una **S blanca
sobre fondo azul**, proporcionada por el propietario del proyecto como
`assets/logo/official_logo.png`.

El componente que lo dibuja es reutilizable y está aislado en `gui/logo.h` +
`gui/logo.c`. Ningún punto de la interfaz redibuja la S ni usa tipografía:
todos llaman a `logo_draw*()`. Existen **dos fuentes de glifo** (ambas
proporcionadas por el propietario y extraídas a máscaras alfa 8bpp):

| Fuente | Fichero | Uso | Geometría del glifo |
|---|---|---|---|
| **OFICIAL** | `assets/logo/official_logo.png` (1296x1213 RGB) | splash, «Acerca de», pánico, menú, dock y compatibilidad PLAIN | caja de cobertura alfa 366 x 386 (0,948); núcleo visible **354 x 376 = 0,9415** |
| **RIBBON** | `assets/logo/ribbon_s_logo.png` (1296x1213 RGBA, PNG con transparencia) | **solo la barra superior**, como glifo suelto **sin fondo azul** | bbox alfa > 16 en (243,190): **834 x 944 = 0,8835** |

La marca general de SereOS sigue siendo la OFICIAL (con su contenedor azul
`#004EFD`): splash, «Acerca de», pánico, menú cabecera, dock y menú fila About.
La **top bar** usa el asset "Minimalist White Ribbon S Logo" por petición
explícita del usuario y, además, **sin fondo azul**: se dibuja únicamente el
glifo del PNG (S blanca con transparencia) sobre la barra oscura, mediante
`logo_draw_icon()` / `logo_draw_topbar()`. Su **altura es 10 px** (`TOPBAR_LOGO`,
ancho ≈ 9 px por la proporción 834/944), la misma altura visual que las
mayúsculas del wordmark, centrado en la línea del texto con un **gap de 8 px**.

## Fuente y proporción

| Propiedad | Valor |
|---|---|
| Fichero | `assets/logo/official_logo.png` |
| Dimensiones | **1296 x 1213 px** (RGB) |
| Proporción (ancho/alto) | **1,0685** (1296 / 1213) |
| Color de marca | azul dominante ≈ `#004EFD` (`LOGO_BRAND_BLUE`) |
| Glifo S | caja de cobertura alfa **366 x 386 px** (0,948; se usa para escalar); núcleo visible ≈ **354 x 376 px** (proporción nominal **0,9415**) |
| Diseño | S blanca centrada sobre azul, sin recortes ni deformación |

## Formas del componente

`logo_draw(cx, cy, size, shape, radius_pct, ring_alpha)` dibuja siempre un
**contenedor cuadrado de lado exactamente `size`** centrado en `(cx,cy)`, con el
glifo S blanco centrado encima. El glifo mide
`round(size * 56 / 100)` de alto (`LOGO_GLYPH_RATIO_PCT`) y conserva la
proporción oficial.

| Forma | Rasterizado | Uso |
|---|---|---|
| `LOGO_SHAPE_CIRCLE` | disco de radio `size/2` con caja exacta `size x size` | splash, menú cabecera, pánico (`logo_draw_brand`) |
| `LOGO_SHAPE_SQUIRCLE` | superelipse n=4: `((2u+1-size)²)² + ((2v+1-size)²)² <= size⁴` | icono de app / accesos |
| `LOGO_SHAPE_ROUNDED` | cuadrado con esquinas de radio `round(size*radius_pct/100)` (22 % por defecto) | «Acerca de» |
| `LOGO_SHAPE_PLAIN` | sprite oficial completo escalado (compatibilidad) | código antiguo |

Las formas se rasterizan con **cuentas enteras** (sin coma flotante ni heap) y
solo usan `gfx_*` (clip incluido), por lo que son seguras en el bucle de dibujo
y en la pantalla de pánico. `gfx_fill_circle()` no se usa para los contenedores
porque su diámetro es siempre impar (`2r+1`): el rasterizado propio por filas
garantiza la caja exacta `size x size`.

**Antialiasing (AA 4x4).** Los contenedores CIRCLE/SQUIRCLE/ROUNDED se dibujan
con **cobertura 4x4** (16 sub-muestras por píxel): el interior se rellena por
filas con `gfx_fill_rect()` y solo los píxeles de borde se mezclan con
`gfx_blend_pixel(x, y, LOGO_BRAND_BLUE, (cov*255+8)/16)`, donde `cov` es el
número de sub-muestras (0..16). Todo con enteros (`uint64_t` para la
superelipse), determinista y con coste marginal (solo borde). La cobertura no
se sale de la caja: el bbox sigue siendo **exactamente `size x size`**,
centrado en `(cx, cy)`. Esto elimina el escalonado del borde del splash y del
top bar, que antes era el único elemento sin AA de la pantalla de arranque.

Atajos semánticos usados por la interfaz:

```c
logo_draw_topbar(cx, cy, altura);   /* SOLO glifo RIBBON del PNG, SIN fondo (top bar) */
logo_draw_brand(cx, cy, size);      /* CIRCLE + glifo OFICIAL (menú, pánico) */
logo_draw_icon(cx, cy, h, glyph);   /* glifo suelto (sin contenedor), p.ej. h=10 ribbon */
logo_icon_width(h, glyph);          /* ancho real del glifo para esa altura */
logo_draw_splash(cx, cy, size);     /* CIRCLE + anillo, glifo OFICIAL */
logo_draw_about(cx, cy, size);      /* ROUNDED 22 %, glifo OFICIAL */
logo_draw_app_icon(cx, cy, size);   /* SQUIRCLE, glifo OFICIAL */
logo_draw(cx, cy, size, forma, radio, anillo);        /* glifo OFICIAL */
logo_draw_glyph(cx, cy, size, forma, radio, anillo, fuente); /* fuente libre */
```

El anillo del splash (`ring_alpha` 110) se dibuja a radio `size/2 + 4` con
**cobertura AA 4x4** de una banda radial de 1 px (`[R-0.5, R+0.5]`) mezclando
`theme.accent` con alfa `(cov*110+8)/16` mediante `gfx_blend_pixel()`: así se
lee como un anillo fino y continuo (no punteado) y sigue siendo discreto. Su
bounding box es `2 * (size/2 + LOGO_RING_GAP) + 1` px (97 px para `size` = 88)
y `logo_extent(size, ring_alpha)` devuelve exactamente ese valor. En el layout
del splash el anillo queda centrado: la fila extra cae en el hueco `SP_4`
anterior al wordmark, sin recorte.

## Máscaras alfa del glifo

El glifo se extrae de la **misma imagen oficial** (no hay fuente alternativa ni
S tipográfica). El generador calcula la cobertura alfa desde el canal R
(válido porque el fondo azul tiene R=0..4 y la S R=255):

```
alfa = clamp((R - 4) / (255 - 4))
```

Recorta la caja del glifo con el propio canal alfa (incluye el suavizado de los
bordes) y escala cada máscara con LANCZOS a la altura pedida conservando la
proporción nominal 354/376. Aclaración de las dos medidas que conviven:

* **366 x 386 px (0,948)**: caja de **cobertura alfa** del PNG oficial (incluye
  el suavizado de los bordes); es la región que se escala con LANCZOS.
* **354 x 376 px (0,9415)**: **núcleo visible** de la S (proporción nominal que
  usan `LOGO_GLYPH_ASPECT_NUM`/`DEN` y los tamaños derivados).

No se contradicen: la primera es la caja de muestreo, la segunda la proporción
visible de la marca. Las máscaras se guardan fila a fila (`w*h` bytes, sin
padding) en `gui/logo_data.c` y en runtime solo se tiñen y componen con
`gfx_blit_alpha8(x, y, w, h, mask, 0x00FFFFFF)`; **el kernel nunca escala**.

Alturas generadas (55 en total): **8..32 px paso 1**, **34..64 paso 2**,
**68..96 paso 4**, **104..128 paso 8**, más **43 y 49 px** (tamaños exactos de
splash). El componente elige la altura exacta si existe y, si no, la más
cercana; en los tamaños de la interfaz (18/20/22/24/40/60/76/88/96) siempre hay
altura exacta.

**Glifo RIBBON** (solo top bar, tabla independiente en
`gui/logo_ribbon_data.c/.h`): se extrae del **canal A** del asset
`assets/logo/ribbon_s_logo.png`. El PNG trae un halo de alfa 1..15 en casi todo
el lienzo (~78.000 px); por eso:

```
alfa = 0 si A < 16
alfa = clamp(round(A * 255 / 254)) si A >= 16   (cuerpo del glifo: A≈254)
```

Así la caja real es (243,190) **834 x 944** (0,8835) y el glifo se centra por
ese bbox (el centro del lienzo NO coincide). Cada máscara se escala con LANCZOS
a `round(h * 834 / 944)` de ancho. Alturas generadas (41): **8..32 paso 1** y
**34..64 paso 2** (la top bar usa 10 px: 9x10 exactos). La tabla OFICIAL no se
toca: `gui/logo_data.c` es byte-idéntico entre ejecuciones y entre fuentes
(md5 `4eb11dd0d1bd8afcd592fe6838d82b39`).

## Generación para el kernel

| Herramienta | Salida |
|---|---|
| `tools/gen_logo.py` | `gui/logo_data.c` + `gui/logo_data.h` (sprites RGB565 + 55 máscaras alfa del glifo OFICIAL) |
| `tools/gen_logo.py` | `gui/logo_ribbon_data.c` + `gui/logo_ribbon_data.h` (41 máscaras alfa del glifo RIBBON) |
| `assets/logo/official_logo.png` | fuente oficial (no editable por código) |
| `assets/logo/ribbon_s_logo.png` | fuente ribbon, copia byte a byte del asset del propietario (solo top bar) |

Alturas de sprite completo (compatibilidad `LOGO_SHAPE_PLAIN`): 16, 18, 20, 22,
24, 28, 32, 40, 48, 56, 64, 96 y 128 px; el ancho de cada una es
`round(h * 1296 / 1213)` (p. ej. 18 px → 19 px, 48 px → 51 px). El generador es
determinista, valida proporción, caja del glifo, cobertura y centroide, y falla
si algo no se cumple.

```bash
py=~/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
$py tools/gen_logo.py                        # regenera logo_data.c/h
$py tools/gen_logo.py --preview /tmp/logo_sizes.png
```

El PNG de origen no se embebe en la ISO: en tiempo de ejecución solo existen las
tablas ya generadas, sin dependencias externas.

## Dónde se usa

| Punto de la interfaz | Implementación | Tamaño |
|---|---|---|
| Splash de arranque | `gui/splash.c` (`logo_draw_splash`, OFICIAL) | 88 px (76 px en pantallas bajas) |
| **Barra superior** | `gui/desktop.c` (`logo_draw_topbar`, **glifo RIBBON suelto, sin fondo azul**) | **altura 10 px** (`TOPBAR_LOGO`, alineada con el wordmark y gap 8 px) → ancho ≈ **9 px** |
| Cabecera del menú principal | `gui/desktop.c` (`logo_draw_brand`, OFICIAL) | **24 px** |
| «Acerca de SereOS» | `apps/about/about.c` (`logo_draw_about`, OFICIAL) | **60 px** |
| Icono de app / acceso directo | dock y menú (`logo_draw_app_icon`, OFICIAL) | **40 px** (`DOCK_ICON`) |
| Pantalla de pánico | `gui/gui.c` (`logo_draw_brand`, OFICIAL) | 18 px |

`icons_draw_logo(x, y, altura)` e `icons_logo_width(altura)` siguen existiendo
en `gui/logo.h` como **compatibilidad** (sprite completo, `LOGO_SHAPE_PLAIN`);
los puntos migrados ya no las usan. `gui/icons.h` incluye `gui/logo.h`.

## Verificación

La suite `tools/run_tests.py` comprueba en capturas reales:

* **Splash** (`01_splash.png`): caja del logo ≈ circular (proporción ~1,0),
  anillo exterior fino y S centrada.
* **Barra superior** (`02_desktop.png`): glifo ribbon suelto de 10 px
  (`9x10`), alineado con el wordmark, gap 8 px y sin azul de marca.
* **Identidad**: se escanea el binario para asegurar que **no** quedan
  referencias a `logo_badge`, `logo_s` ni `logo_mono`, y que el generador usa
  `assets/logo/official_logo.png`.
* **Menú** (`22_menu_logo.png`), **About** (`06_about.png`) y **pánico**
  (`15_panic.png`) se revisan visualmente.

Además, el generador valida numéricamente: bbox del glifo, cobertura ≈52 %,
centroide centrado y ausencia de la clave de transparencia `0xF81F`; y los
previews (scripts temporales en `/tmp`, fuera del repo) renderizan las 4
variantes a 18/22/24/40/60/88 px replicando la misma geometría del C,
incluido el AA:

* `/tmp/logo_preview.png`: rejilla de las 4 variantes + ubicaciones reales.
* `/tmp/logo_aa_before_after.png`: comparación QEMU real **antes** (sin AA)
  vs réplica **después** (AA 4x4), recorte x4 LANCZOS del splash.
* `/tmp/logo_aa_ring_compare.png`: anillo del splash antes/pués ampliado.
* `/tmp/logo_topbar_icon_preview.png`: top bar (barra de 30 px) con el glifo
  RIBBON suelto de 9x10 px, **sin ningún píxel azul**, centrado con el wordmark.
* `/tmp/logo_ribbon_compare_22.png`: 22 px RIBBON vs OFICIAL a x8 NEAREST.

Comprobaciones de la top bar (10 px): se dibuja SOLO el glifo ribbon, con
altura exacta 10 px y ancho 9 px (`round(10*834/944)`), blanco sobre la barra
oscura, centrado verticalmente en la MISMA caja de línea que el wordmark
(`cy = wy + text_height(TEXT_LABEL)/2`), con gap 8 px y **0 píxeles del azul de
marca `#004EFD`**.
El resto de ubicaciones conservan su contenedor azul y el glifo OFICIAL sin
cambios (menú cabecera 24, fila About 18, About 60, splash 88, dock 40 y
pánico 18).

Comprobaciones automáticas del preview con AA: bbox del contenedor exactamente
`size x size` y centrado, glifo centrado (≤1 px), proporción 354/376, altura de
la S ≈56 % del contenedor, bbox del anillo `2R+1` y continuidad angular del
anillo (0/72 sectores vacíos).

## Licencia y atribución

El logotipo oficial es un recurso del proyecto SereOS (proporcionado por el
propietario del proyecto para esta entrega). Se usa únicamente dentro de la
interfaz de SereOS y se distribuye con el proyecto. No se ha copiado ni
derivado de logotipos de terceros; el resto de iconos siguen siendo
iconografía lineal original generada por `tools/gen_ui_icons.py`.
