# Sistema de diseño de SereOS — «SereOS UI»

Este documento define la identidad visual única de SereOS Desktop. Todas las
aplicaciones y componentes usan **los mismos tokens**; no se permiten colores,
márgenes o tipografías hardcodeados fuera de `gui/theme.h`, `graphics/text.h` y
`gui/icons.h`.

> **Estado**: rediseño visual integral en integración. Los valores de este
> documento salen de las fuentes de verdad (`gui/theme.c`, `gui/theme.h`,
> `graphics/text.h`, `gui/ui.h`). La comparativa antes/después y la revisión
> final de capturas se completan en la validación con QEMU (ver
> [screenshots/](screenshots/) y [screenshots/compare_before_after.png](screenshots/compare_before_after.png)).

## 1. Principios

1. **Una sola identidad**: escritorio, ventanas, las 4 apps, splash y pantalla
   de pánico comparten paleta, tipografía, escala y radios.
2. **Jerarquía explícita**: un título por pantalla, etiquetas en semibold,
   metadatos atenuados; el color de acento solo para acciones y foco.
3. **Ritmo 4/8**: todo margen, tamaño y separación es múltiplo de 4 px
   (escala `SP_*`); el espaciado de bloques usa múltiplos de 8.
4. **Contraste medible**: texto principal ≥ 15:1 sobre superficie; texto
   secundario ≥ 7:1; ningún texto activo por debajo de 4.5:1.
5. **Contención**: el texto nunca se recorta ni se solapa; se mide con
   `text_width()` y se recorta con `text_draw_clipped()` cuando hay scroll.
6. **Sobriedad**: sombras sutiles (1 nivel), sin gradientes llamativos en
   ventanas; el brillo se reserva para el fondo del escritorio y el splash.
7. **Nativo**: todo se rasteriza en tiempo de compilación; en ejecución no hay
   dependencias, ni FPU, ni fuentes externas, ni asignaciones para dibujar.

## 2. Paleta (tokens semánticos)

Definida en `gui/theme.c` (`const theme_t theme`). Hex en formato `#RRGGBB`.

| Token | Hex | Uso |
|---|---|---|
| `bg` | `#0B0D12` | fondo del escritorio (carbón azulado) |
| `bg_elevated` | `#12151C` | paneles flotantes sobre el escritorio |
| `surface` | `#14171E` | superficie principal de ventana |
| `surface_2` | `#1A1E26` | barras, sidebar, tarjetas, título de ventana |
| `surface_3` | `#222732` | hover / selección suave |
| `border` | `#2A3040` | borde de 1 px |
| `border_strong` | `#3A4256` | borde de ventana enfocada |
| `shadow` | `#000000` | sombra (alfa `WIN_SHADOW_ALPHA=90`) |
| `text` | `#F2F4F8` | texto principal |
| `text_dim` | `#A8B0C0` | texto secundario / etiquetas |
| `text_faint` | `#6E7788` | metadatos y ayudas |
| `accent` | `#4C8DFF` | azul eléctrico: foco, acciones, selección |
| `accent_soft` | `#1E3A66` | relleno de selección / hover de acento |
| `cyan` | `#4CC9E0` | acento secundario y datos |
| `green` | `#4CC38A` | éxito / estado OK |
| `amber` | `#E0A84C` | advertencia / rango |
| `red` | `#E5534B` | error / peligro / semáforo cerrar |
| `white` / `black` | `#FFFFFF` / `#000000` | contraste puntual |

Contraste calculado (WCAG 2.1, sRGB):

| Combinación | Ratio |
|---|---|
| `text` sobre `bg` | **17,65:1** |
| `text` sobre `surface` | **16,29:1** |
| `text` sobre `surface_2` | **15,16:1** |
| `text_dim` sobre `surface` | **8,23:1** |
| `text_dim` sobre `surface_2` | **7,66:1** |
| `text_faint` sobre `surface` | **3,98:1** (solo metadatos no esenciales) |
| `accent` sobre `surface` | **5,60:1** |
| `cyan` / `green` / `amber` sobre `surface` | 9,17 / 8,10 / 8,43:1 |
| `red` sobre `surface` | **4,84:1** |
| `white` sobre `accent_soft` | **11,34:1** |

Semáforos de ventana: cerrar `#E5534B`, minimizar `#E0A84C`, maximizar
`#4CC38A` (mismos tokens `red/amber/green`).

## 3. Tipografía

Dos familias, **rasterizadas en tiempo de compilación** con
`tools/gen_ui_fonts.py` a atlases de cobertura alfa de 8 bits
(`graphics/text_data.c`); en ejecución no hay dependencias ni fuentes.

| Familia | Uso | Licencia |
|---|---|---|
| **Inter** (Regular / SemiBold) | interfaz: texto, etiquetas, títulos, HUD | SIL Open Font License 1.1 — © 2016 The Inter Project Authors |
| **JetBrains Mono** (Regular) | terminal, código, valores y datos técnicos | SIL Open Font License 1.1 — © 2020 The JetBrains Mono Project Authors |

Escala (definida en `graphics/text.h`, `text_style_t`):

| Estilo | Familia / peso | Tamaño | Uso |
|---|---|---|---|
| `TEXT_CAPTION` | Inter Regular | 10 px | metadatos, ayudas |
| `TEXT_SMALL` | Inter Regular | 11 px | texto secundario |
| `TEXT_BODY` | Inter Regular | 13 px | texto normal |
| `TEXT_LABEL` | Inter SemiBold | 12 px | etiquetas, título de ventana |
| `TEXT_TITLE` | Inter SemiBold | 16 px | título de sección |
| `TEXT_HEADLINE` | Inter SemiBold | 20 px | cabeceras |
| `TEXT_DISPLAY` | Inter SemiBold | 30 px | splash / pantalla de pánico |
| `TEXT_MONO` | JetBrains Mono | 13 px | terminal, código |
| `TEXT_MONO_SMALL` | JetBrains Mono | 11 px | detalles técnicos |

Reglas: usar `text_width()`/`text_ascent()` para maquetar (nunca medir a ojo);
el alto de línea y el interlineado salen de `text_height()`/`text_line_gap()`;
contenido que no cabe se recorta con `text_draw_clipped()` o se abrevia con
puntos suspensivos, nunca se dibuja fuera de la ventana. Cobertura **ASCII +
Latin-1 (acentos y ñ) vía UTF-8**: verificado en la captura real de pánico
(`Excepción 0: División por cero`, «Error crítico»); el teclado del sistema
sigue siendo US (no se pueden teclear acentos, ver
[LIMITATIONS.md](LIMITATIONS.md)).

Licencias OFL: se incluye el aviso en la cabecera de `graphics/text_data.c`
generado y en el generador. Los ficheros TTF de sistema no se redistribuyen;
solo los atlases rasterizados generados por el propio repositorio.

## 4. Espaciado, radios y sombras

Escala de espaciado (`gui/theme.h`): `SP_0=0`, `SP_1=4`, `SP_2=8`, `SP_3=12`,
`SP_4=16`, `SP_5=20`, `SP_6=24`, `SP_8=32`, `SP_10=40`, `SP_12=48`.
Los márgenes internos de ventana usan `SP_4` (16 px); entre bloques `SP_4`/
`SP_6`; márgenes externos `SP_2`/`SP_3`.

| Radio | Valor | Uso |
|---|---|---|
| `RADIUS_XS` | 4 px | barras de progreso, chips pequeños |
| `RADIUS_SM` | 6 px | controles, botones |
| `RADIUS_MD` | 10 px | ventanas (`WIN_RADIUS`), tarjetas |
| `RADIUS_LG` | 14 px | paneles flotantes / diálogos |
| `RADIUS_XL` | 18 px | dock (`DOCK_RADIUS=16`), superficies grandes |

Sombras: una sola sombra suave bajo ventanas/dock/menús con
`gfx_shadow()` y `WIN_SHADOW_ALPHA=90`; sin sombras duras ni múltiples capas.
Bordes: 1 px `border`; enfocado `border_strong`; nunca se usan bordes de color
de acento alrededor de ventanas completas.

## 5. Iconografía

* Iconos vectoriales/procedurales propios generados por
  `tools/gen_ui_icons.py` y empaquetados en `gui/icons_data.c`; mismo lenguaje
  visual (trazo, esquinas redondeadas, relleno plano + acento).
* Tamaños: 16/20/24/32/40 px según contexto; el dock usa `DOCK_ICON=40`.
* Estados: normal, hover (`surface_3`), activo/abierto (indicador de 3 px
  `DOCK_INDICATOR`), seleccionado (`accent_soft`).
* Todos los iconos caben en una caja cuadrada con 2 px de aire; se dibujan
  centrados y nunca se escalan a tamaños no previstos.

## 6. Métricas de componentes

Barra superior (`TOPBAR_H=30`): marca = **PNG ribbon directo, sin contenedor
ni fondo azul** (`assets/logo/ribbon_s_logo.png`, altura 10 px `TOPBAR_LOGO`,
ancho ≈9 por ratio 834/944), a la altura visual del wordmark y centrada en su
misma línea (gap 8 px), padding horizontal
`TOPBAR_PAD_X=12`, reloj y datos a la derecha en `TEXT_LABEL`/`TEXT_CAPTION`;
fondo `topbar_bg` con línea inferior `border`. El título de la app activa se
centra en el **espacio libre** entre la marca/menú y los grupos de estado (no
en el centro absoluto de la pantalla, para no chocar con ellos). Comportamiento
responsive: fecha oculta por debajo de 900 px de ancho y uptime por debajo de
820 px; si el grupo de memoria no cabe, se omite completo.

Dock (`DOCK_HEIGHT=58`, `DOCK_RADIUS=16`, `DOCK_ICON=40`, `DOCK_ICON_GAP=6`,
`DOCK_PAD=8`, `DOCK_BOTTOM=8`): **centrado horizontalmente**, iconos separados
6 px, indicador de app abierta de 3 px, tooltip arriba con `TEXT_SMALL` sobre
`surface_2` con sombra. El tooltip del juego muestra «PAC-MAN SereOS» (verificado
con hover real, captura `02c_dock_tooltip`).

Ventanas (`WIN_RADIUS=10`, `WIN_TITLEBAR_H=34`, `WIN_BORDER=1`,
`WIN_MIN_W=300`, `WIN_MIN_H=180`): título de ventana en `TEXT_LABEL`, semáforos
de 12 px con 8 px de separación, contenido con 16 px de margen, sombra sutil y
cascada; máximo 8 ventanas. La geometría se **recorta al área útil**
(`window_work_area()`: márgenes `SP_3`, debajo de la barra y por encima del
dock) y respeta los tamaños mínimos, de modo que ninguna ventana queda cortada
ni tapa el dock en 800x600/1280x1024.

Controles: `CTRL_HEIGHT=28`, `CTRL_RADIUS=6`, `BAR_HEIGHT=6`,
`LIST_ROW_H=28`, `STATUS_DOT=6`; foco visible con `accent` y hover con
`surface_3`.

## 7. Movimiento y estados

* Transiciones cortas (≤ 150 ms equivalentes a ~9 frames a 60 fps): hover de
  dock, apertura/cierre de ventanas, splash.
* Sin animaciones que retrasen la interacción; el compositor repinta solo
  regiones sucias.
* Estados claros: normal, hover, pulsado, enfocado, deshabilitado y abierto
  (dock). El foco siempre es visible y no depende solo del color (también
  borde/indicador).

## 8. Resoluciones soportadas

| Resolución | Estado | Notas |
|---|---|---|
| **1024x768x32** | principal (GRUB y pruebas) | layout de referencia |
| 1280x1024x32 | soportada y verificada | topbar y dock conservan métricas; dock centrado |
| 800x600x32 | soportada y verificada | ventanas se recolocan respetando mínimos |

Las pruebas de resolución usan una ISO temporal en `/tmp` que parchea la
petición de vídeo de la cabecera Multiboot del kernel (GRUB da prioridad a la
cabecera sobre `set gfxmode`) y ejecuta la captura del escritorio con una app
abierta. Ver `tools/run_tests.py` (pruebas `resolution_1280` y
`resolution_800`) y las capturas `16_resolution_1280x1024.png` /
`17_resolution_800x600.png` (ver capturas
[16](screenshots/16_resolution_1280x1024.png) y
[17](screenshots/17_resolution_800x600.png)), y la maximizada full-height
con topnav en las mismas resoluciones (`31_max_1280`, `32_max_800`), con los
5 accesos centrados y el cluster derecho sin recortes.

## 9. Comparativa antes / después

La entrega incluye el set previo al rediseño en
[`screenshots/before/`](screenshots/before/) (22 capturas, generadas desde una
ISO congelada) y el set final en [`screenshots/`](screenshots/). El mosaico
comparativo se genera con `tools/make_comparison.py` en
`screenshots/compare_before_after.png` (filas: escritorio, zoom barra+dock,
tooltip del dock, terminal y «Acerca de»; ANTES a la izquierda, DESPUÉS a la
derecha). Capturas
finales obligatorias: `00_grub_menu` … `14_text_mode`, más `02b_topbar_dock`,
`02c_dock_tooltip` (hover real sobre el dock), `15_panic`,
`16_resolution_1280x1024`, `17_resolution_800x600`, `18_dock_window`,
`21_dock_restored`, `22_menu_logo`, `25_maximized_fullbleed`,
`26_restore_exact`, `27_doubleclick`, `28_minimize_restore`,
`29_max_terminal`, `30_resize`, `31_max_1280`, `32_max_800`,
`33_window_corners_clean` y los escenarios de navegación adaptativa
`34_topnav_maximized`, `35_topnav_active`, `36_topnav_restore_dock`,
`37_topnav_multiwindow`, `38_topnav_minimize_last`, `39_topnav_800` y
`40_topnav_1280` (**41 capturas finales** + comparativa).

| Antes | Después |
|---|---|
| fuente bitmap 8x16 ASCII única | Inter + JetBrains Mono (Latin-1) |
| paleta navy/azul con gradientes fuertes | carbón `#0B0D12` + superficies neutras + acento contenido |
| iconos y ventanas con bordes marcados | iconos consistentes, ventanas con sombra sutil y radio 10 |
| splash con estrellas y halos | splash minimalista con jerarquía tipográfica |
| pánico con gran panel rojo | pánico sobrio con `TEXT_DISPLAY` y detalle mono |

## 10. Logotipo oficial

SereOS usa un único logotipo oficial (S blanca sobre azul), definido en
[LOGO.md](LOGO.md), en lugar de las marcas procedurales anteriores:

* Fuente `assets/logo/official_logo.png`, **1296x1213 px**. `tools/gen_logo.py`
  extrae el glifo de la S como máscaras alfa en `gui/logo_data.c` y `gui/logo.c`
  lo compone sobre un contenedor **cuadrado** (círculo, squircle o cuadrado
  redondeado). Dos medidas conviven sin contradecirse: **caja de cobertura alfa
  366x386 px** (proporción 0,948; la que usa el generador para escalar) y
  **núcleo visible 354x376 px** (0,9415). El glifo mide el **56 %** del
  contenedor y conserva la proporción del glifo (354/376 en el núcleo visible):
  **nunca se deforma ni se recorta**.
* Formas y tamaños (todos son el lado del contenedor, tokens en `theme.h`):
  * **splash**: círculo **88 px** (`SPLASH_LOGO`; **76 px** con alto <600 px,
    `SPLASH_LOGO_SMALL`) + anillo exterior de 1 px separado
    `LOGO_RING_GAP=4` px, discreto; dibujado por `logo_draw_splash()`.
  * **barra superior**: glifo **ribbon** suelto (PNG) de **10 px de altura**
    (`TOPBAR_LOGO`, ancho ≈9 por ratio 834/944), **sin contenedor ni fondo
    azul**, a la altura visual de las mayúsculas del wordmark
    (`TEXT_LABEL` 12 px) y centrado en su misma línea con gap 8 px; dibujado
    por `logo_draw_topbar()`.
  * **cabecera del menú**: círculo **24 px** (`MENU_LOGO`).
  * **Acerca de**: cuadrado redondeado al **22 %** de **60 px** (`ABOUT_LOGO`),
    sin círculo exterior (`logo_draw_about()`).
  * **pantalla de pánico**: círculo **18 px** (`PANIC_LOGO`).
  * **icono de la app/acceso directo SereOS** (dock y fila «Acerca de» del
    menú): **squircle** de **40 px** (`APP_LOGO`, = `DOCK_ICON`), dibujado por
    `logo_draw_app_icon()`.
* La **marca de la barra superior** usa un segundo asset,
  `assets/logo/ribbon_s_logo.png` (glifo **ribbon**, bbox 834x944,
  proporción 0,8835), dibujado **directamente** por `logo_draw_topbar()`:
  sin contenedor, sin anillo y **sin fondo azul** (S blanca sobre el fondo de
  la barra). Es la **única** ubicación con el glifo ribbon. El azul de marca
  `#004EFD` se mantiene en la cabecera del menú (`logo_draw_brand()`), el
  splash, «Acerca de», el icono de app del dock y la pantalla de pánico, que
  siguen usando el glifo **oficial** (`assets/logo/official_logo.png`).
* Color de marca ≈ `#004EFD`; en las capturas el azul rasterizado mide
  proporción ≈1,00 (contenedor circular/squircle) y la S interior mantiene la
  proporción del glifo.
* La suite verifica el logo por análisis de píxeles y comprueba que no quedan
  referencias a `logo_badge`/`logo_s`/`logo_mono` en fuentes ni binario.

## 11. Navegación adaptativa: dock y topnav

La navegación es **un único estado global** del compositor
(`desktop_bar_state()`); nunca hay dock y topnav a la vez:

| Estado | Cuándo | Qué se ve |
|---|---|---|
| **Dock flotante** (`DESKTOP_BAR_DOCK`) | ninguna ventana maximizada | dock centrado inferior (58+8 px), topbar con logo+menú a la izquierda, nombre de app centrado e indicadores a la derecha |
| **Topnav** (`DESKTOP_BAR_TOPNAV`) | al menos una ventana maximizada visible | **el dock desaparece** (inset inferior 0) y los 5 accesos pasan a la **topbar central**; no hay ninguna barra inferior |

* **5 accesos** (Archivos, Terminal, Monitor, Pacman, Información) con los
  mismos iconos/tintes del dock (`TOPBAR_NAV_TILE=24`, `TOPBAR_NAV_ICON=18`,
  `TOPBAR_NAV_GAP=2`; total 128 px) **centrados en la pantalla**:
  1024→`448..575` (centros 460…564), 800→`336..463`, 1280→`576..703`. Iconos
  cerrados en `text_faint`; abiertos con sus tintes; el cluster derecho
  (memoria/uptime/fecha/hora) no se desplaza.
* **Indicador activo**: tile `accent_soft` (24x24) + **subrayado accent de
  2 px**; apps abiertas no activas con punto accent de 3 px; exactamente un
  activo.
* **Clics**: app cerrada → abre; abierta no activa → enfoca; app activa →
  minimiza/restaura. Nunca duplica `APP_OPEN`.
* **Transición** (`nav_anim`, 0…1000, ~145 ms, switch 500): el dock baja y
  **se deja de dibujar antes** de que aparezca la nav (`<500` solo dock;
  `≥500` nav y dock ya no se pinta), de modo que **no hay iconos duplicados
  simultáneos**; a la inversa al restaurar.
* **Geometría full-height**: con topnav `desktop_bottom_inset()=0`; la
  maximizada ocupa `x=0, y=30, w=sw, h=sh-30` y **llega al último píxel**
  (1024: y=30..767; 800: y=30..599; 1280: y=30..1023), sin dock ni barra
  inferior, franjas ni fondo reservado.
* **Multi-ventana**: con 2 maximizadas se mantiene topnav; minimizar una deja
  topnav; al minimizar/restaurar la **última** vuelve el dock. Restaurar una
  maximizada desde el dock/icono la devuelve **maximizada** (was_maximized).
* **Resoluciones**: nav centrada y tray responsivo en 1024, 1280 y 800 (a 800
  se ocultan fecha/uptime como en el dock; memoria+hora visibles).
* **Capturas**: `34_topnav_maximized`, `35_topnav_active`,
  `36_topnav_restore_dock`, `37_topnav_multiwindow`,
  `38_topnav_minimize_last`, `39_topnav_800`, `40_topnav_1280`, más
  `18_dock_window` y `21_dock_restored`.

## 12. Gestor de ventanas y maximización full-bleed

* **Geometría maximizada (full-height)**: `window_toggle_maximize()` asigna
  `x=0, y=TOPBAR_H (30), w=sw, h=sh-30`; la ventana llega al **último píxel**
  (1024: `0,30 1024x738`, y=30..767; 1280: `0,30 1280x994`, y=30..1023; 800:
  `0,30 800x570`, y=30..599). Sin radio de esquinas, sombra ni margen, **sin
  dock ni barra inferior** y sin wallpaper en el área; la topbar (y=0..29) sigue
  siendo la única barra global y en ella viven los 5 accesos (topnav).
* **Estados** (`WIN_STATE_NORMAL/MINIMIZED/MAXIMIZED`): al maximizar se guarda
  el rect normal (`saved_*`) y al restaurar se aplica **exactamente** (p.ej.
  `x=31,y=66,w=898` antes y después). Restaurar no vuelve a abrir la app
  (`APP_OPEN` no se repite).
* **Entradas**: semáforo **verde** y **doble clic** en la barra de título
  (≤350 ms, mismo punto) alternan maximizar/restaurar.
* **Minimizar conservando estado**: `was_maximized` recuerda si la ventana
  estaba maximizada; minimizarla devuelve el dock (si no queda otra
  maximizada) y al restaurarla desde el dock/icono de la topnav vuelve
  **maximizada full-height**, sin relanzar la app.
* **Resize**: solo ventanas normales, por bordes/esquinas de 8 px
  (`RZ_LEFT/RZ_RIGHT/RZ_BOTTOM`); respeta el work area y los mínimos
  `WIN_MIN_W=300`, `WIN_MIN_H=180`. Verificado con arrastre QMP: ancho
  `898→946` (+48 px) manteniendo origen, y clamp a 300 al encoger.
* **Clipping de esquinas redondeadas**: el compositor guarda el fondo real
  (wallpaper/ventanas inferiores/sombra) bajo las cuatro esquinas de 16x16 px
  **antes** de pintar la ventana y, tras dibujar el contenido, restaura
  **solo los píxeles fuera** del rectángulo redondeado
  (`inside_round_window()`, `WIN_RADIUS=10`), redibujando el contorno
  (`border_strong`). Así la barra de estado/contenido llega hasta el arco sin
  parches cuadrados de 14x14 del color del cuerpo (bug v1.3). Verificado por
  píxeles: dentro del arco BR = `surface_2` (26,30,38), fuera = fondo
  (10,13,24), **0 px del color de cuerpo (20,23,30) fuera**, también con
  ventana superpuesta y resize; mosaico 10x en
  `33_window_corners_clean.png`. Las maximizadas siguen **square full-bleed**
  (sin radios) por diseño.
* **Apps adaptadas**: Archivos (preview proporcional), Terminal (más filas),
  Monitor (tarjetas/tareas), About (centrado) y Pacman (tablero centrado,
  dots/power visibles también al reabrir). Todas comprobadas maximizadas
  full-height con `wallpaper_ratio ≤ 0.0001`, una sola topbar (sin barra
  inferior ni UI del shell dentro del contenido).
* **Capturas**: `25_maximized_fullbleed`, `26_restore_exact`,
  `27_doubleclick`, `28_minimize_restore`, `29_max_terminal`, `30_resize`,
  `31_max_1280`, `32_max_800`, `33_window_corners_clean` y las de navegación
  adaptativa `34_topnav_maximized` … `40_topnav_1280`.

## 13. Verificación visual (QA)

La suite `tools/run_tests.py` genera las capturas obligatorias y comprueba
automáticamente: que no haya pantallas en negro, resoluciones reales,
coherencia dot/fantasmas/frightened del juego, pánico real por `div0` y cero
excepciones inesperadas.

**Resultado de la pasada oficial sobre la ISO final: 18/18 PASS, 0 FAIL,
0 SKIP** (`KVM=si`, QEMU 11.1.3), con **41 capturas PNG** en
[`screenshots/`](screenshots/) más la comparativa
[`compare_before_after.png`](screenshots/compare_before_after.png) y el set
previo en [`screenshots/before/`](screenshots/before/).

La revisión **visual** de cada captura (jerarquía, alineación, tipografía,
contraste, espaciado, recortes y solapamientos) no encontró defectos
bloqueantes: logotipo oficial correcto en splash/topbar/menú/About/pánico, dock
centrado a 1024/1280/800, navegación adaptativa con dock oculto y 5 accesos
centrados en la topbar, topbar adaptativa sin solapes,
ventanas con sombra sutil y dentro del work area, splash y pánico sobrios, y
acentos Latin-1 correctos (ver [`15_panic.png`](screenshots/15_panic.png)).
Tras la revisión se ajustaron dos detalles: el tooltip del dock dice ya
«PAC-MAN SereOS» (verificado con hover real en
[`02c_dock_tooltip.png`](screenshots/02c_dock_tooltip.png)) y los fantasmas
*frightened* usan ahora un azul claro `#3D62E8` (contraste ~3,8:1) con flash
más brillante, visible en
[`10_pacman_frightened.png`](screenshots/10_pacman_frightened.png). La escena
multiventana mantiene el solape natural de la cascada (por diseño). No quedan
defectos visuales bloqueantes. La prueba `maximize` verifica por píxeles el
full-bleed (0 % de wallpaper en el área), esquina (0,30) de titlebar, unicidad
de barras y restauración exacta; `game` reabre Pacman y comprueba dots/power
reales (1869 px de dot, 308 px de power, frightened 419 px).
