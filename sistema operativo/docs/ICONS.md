# Iconografia de SereOS

Set de iconos **original** de SereOS: geometrico, lineal y minimalista.
No se usan iconos de terceros, ni SVG en tiempo de ejecucion, ni fuentes de
iconos: todo el arte esta definido en Python y se compila como mascaras de
cobertura alfa en el kernel.

## Reglas de estilo

- Rejilla de **24x24** unidades con margen interior de 3-4 unidades.
- Trazo unico de **1.75 px** (1.5-2 px) con esquinas y uniones redondeadas.
- **Un solo color por icono**: la mascara es cobertura alfa; el color se
  aplica al dibujar (tinte del tema). Sin 3D, sin sombras, sin emojis, sin
  texto ASCII y sin rellenos decorativos (solo puntos pequenos funcionales).
- Geometria coherente: circulos limpios, rectangulos con radios 1.5-5,
  chevrons y trazos con la misma inclinacion.
- Antialiasing por **supersampling 4x** con PIL y reduccion por area a
  cobertura 8bpp (0-255).
- Tamanos de atlas: **16, 20, 24, 32, 40, 48 y 64 px**. Al dibujar se elige
  el primer tamano del atlas mayor o igual al solicitado (nunca se escala en
  runtime), asi que el trazo se mantiene nitido.

## Identidad de la marca

`icons_draw_logo()` dibuja la **identidad oficial** de SereOS
(`assets/logo/official_logo.png`) compilada como sprites RGB565 por
`tools/gen_logo.py`; `size` es la altura y el ancho se deriva de la
proporcion original. `icons_logo_width(size)` devuelve ese ancho. El detalle
de formato y regeneracion esta en `docs/LOGO.md`. El id `sereos` es el glifo
lineal de la marca (squircle + S) usado en listas y menus.

## Ids

| id | uso |
|---|---|
| `sereos` | marca lineal (menus/listas) |
| `files`, `folder`, `file` | gestor de archivos |
| `terminal`, `monitor`, `settings`, `about` | aplicaciones y ajustes |
| `game` | juego PAC-MAN SereOS |
| `power` | apagar/reiniciar |
| `network` | red |
| `memory`, `ram`, `cpu`, `storage`, `disk` | hardware y sistema |
| `search` | buscar |
| `close`, `minimize`, `maximize`, `restore` | controles de ventana |
| `chevron_left`, `chevron_right` | navegacion |
| `play`, `pause`, `refresh` | reproduccion/recarga |
| `info`, `check`, `warning`, `error` | estados |
| `home`, `arrows`, `plus`, `minus`, `menu`, `clock` | navegacion y acciones |

## API (gui/icons.h)

- `icons_init()`: no-op; los datos del atlas son estaticos.
- `icons_draw_color(id, x, y, size, color)`: icono centrado en `(x,y)`.
- `icons_draw(id, x, y, size, hovered)`: tinte `theme.text` en hover,
  `theme.text_dim` en reposo (sin recuadros).
- `icons_draw_tile(id, cx, cy, tile_size, tint, hovered)`: tile redondeado
  `RADIUS_SM` con fondo `theme.surface_2` (hover `surface_3`), borde 1 px
  `theme.border` (hover `border_strong`) e icono tintado del color `tint`.
  Es el formato del dock/launcher.
- `icons_draw_logo(x, y, size)` / `icons_logo_width(size)`: logotipo oficial.

Todas las funciones respetan el clip del motor grafico (la composicion final
usa `gfx_blit_alpha8`).

## Generacion reproducible

Fuente del arte y rasterizador: `tools/gen_ui_icons.py` (PIL). Salida
generada: `gui/icons_data.c` (no editar a mano).

```bash
py=~/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
$py tools/gen_ui_icons.py                 # regenerate gui/icons_data.c
$py tools/gen_ui_icons.py --preview /tmp/ui_icons.png   # hoja de revision
```

El generador es determinista y valida: todos los iconos no vacios en los 7
tamanos, cobertura creciente con el tamano y ratio de tinta minima. Si un
icono queda vacio o escaso, falla con codigo 1 y no emite los datos.

## Licencia

Arte original creado para SereOS (proyecto final de Sistemas Operativos,
UMB 2026). Se distribuye con el propio proyecto; no contiene material de
terceros. Los datos generados y el generador pueden reutilizarse dentro de
SereOS.
