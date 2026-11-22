# Evidencia QA visual del logotipo (top bar PNG sin fondo, alineada al texto)

Verificación real de las ubicaciones del logotipo de SereOS. La top bar usa
**SOLO el PNG ribbon** (S blanca sobre transparente, sin contenedor ni fondo
azul), escalado a la altura visual del wordmark "SereOS", centrado
verticalmente con él (equivalente a `align-items:center`) y a gap 8 px. El
resto de ubicaciones mantiene el glifo OFICIAL con su contenedor azul #004EFD.

Todas las capturas provienen de QEMU (KVM, `-vga std`, 1024x768 salvo las de
resolución) ejecutando la ISO del árbol restaurado.

## Artefacto verificado (tras la reversión externa del árbol)

El repositorio fue revertido por otra sesión a un checkpoint antiguo (sin el
sistema de logo) y restaurado de nuevo desde staging. La evidencia de esta
página corresponde al **árbol restaurado** verificado, NO a las capturas
antiguas (04:05) ni a la ISO vieja:

* Build canónico limpio (`make clean && make -j8`, exit 0, 0 warnings),
  congelado antes de medir en `/tmp/qa_final6/sereos_final6.iso`:
  * `sereos.bin` (kernel): **1.455.612 B**, md5
    **`b6fb0a553eee5b18c1ad70c36870377e`** (idéntico al binario indicado por el
    Lead para el árbol restaurado).
  * `sereos.iso`: **36.691.968 B**, md5
    **`2f79203cc0a9677f20a6b4dceb7ce1bd`**.
* Suite completa sobre esa ISO: **18/18 PASS** (`test-results.json`, 42
  capturas; las 6 principales + `07b_pacman_menu.png` son de este artefacto).
* Copia congelada de la evidencia: `/tmp/qa_evidence_0418/` (con md5s).

Identidad de fuentes del logo/UI verificadas en el árbol restaurado:

| Fichero | md5 |
|---|---|
| `gui/logo.c` | `b8f34c782e32ac27c98bc9bc7450ceb5` |
| `gui/logo.h` | `a2dea71d80887947bccdfa284f66c485` |
| `gui/logo_data.c` (oficial, intacta) | `4eb11dd0d1bd8afcd592fe6838d82b39` |
| `gui/logo_ribbon_data.c` (ribbon) | `4ea2ccb3e5bebfaef1f649e18e9ea5f9` |
| `assets/logo/ribbon_s_logo.png` | `c0b046c530cee75d3bdb37a52c0b670f` |
| `gui/theme.h` (TOPBAR_LOGO=10, TOPBAR_H=30) | `5e616f66bf0e4371def2e2feefdffc2c` |
| `gui/desktop.c` (call-site topbar, naming PAC-MAN) | `9bc5229df1abf9a8a80adef0664f61d5` |
| `gui/splash.c` / `gui/gui.c` | `21ba6fcd…` / `3c28cd89…` |
| `apps/about/about.c` (naming PAC-MAN) | `995cab0f89ba40e17288c09fe226d1ae` |

## Resultado

### Top bar: PNG ribbon a escala del wordmark (sin azul) — PASS

| Medida | Valor |
|---|---|
| Píxeles de azul #004EFD en toda la top bar | **0** |
| Glifo blanco (bbox) | **9x10** en (12,9) |
| Centro vertical del glifo | 13.5 vs centro del wordmark 14.0 ⇒ desvío **0.5 px** |
| Gap glifo→wordmark | layout **8 px** (origen del texto x=29; ink x=30 por bearing); visual 9 px |
| Alto de la barra | **30 px** (no cambia; la UI bajo la barra empieza en y=30) |
| Contenedor/círculo/fondo azul | no existe (solo máscara alfa blanca del PNG) |

El glifo usa la máscara ribbon a altura 10 (ancho `logo_icon_width(10)`=9),
centrada en la misma caja de línea que el texto (`cy = wy + text_height/2`).
El wordmark y el botón de menú se desplazan a la izquierda lo que deriva del
ancho del glifo (~9), sin cambiar la altura de la barra.

### Resto de ubicaciones: glifo OFICIAL con azul, sin cambios (6/6 PASS)

| Ubicación | Contenedor | Forma | Glifo bbox / aspecto | Desvío | Color | Anillo |
|---|---|---|---|---|---|---|
| Acerca de (F5) | 60x60 | rounded r=13.3 px (22.2 %) | 32x34 / 0.941 | 0.0 px | #004EFD | no |
| Splash 1024x768 | 88x88 (468,228) | círculo | 46x49 / 0.939 | +0.5 px | #004EFD | r=48, α≈110/255 |
| Splash 1280x1024 | 88x88 | círculo | 46x49 / 0.939 | +0.5 px | #004EFD | r=48 |
| Splash 800x600 / 640x480 | 88 / 76 | círculo | 46x49 / 40x43 | +0.5 px | #004EFD | r=48 / r=42 |
| Dock About | 40x40 | squircle n=4 | 21x22 / 0.955 | +0.5 px | #004EFD | no |
| Menú cabecera | 24x24 | círculo | 12x13 / 0.923 | +0.5 px | #004EFD | no |
| Menú fila About | 18x18 | squircle n=4 | 9x10 / 0.900 | +0.5 px | #004EFD | no |
| Pantalla de pánico | 18x18 | círculo | 9x10 / 0.900 | +0.5 px | #004EFD | no |

(El menú desplegable se desplaza a la izquierda lo que deriva del ancho del
glifo; no es un defecto.)

## Suite completa: 18/18 PASS

`tools/run_tests.py` (versión externa actual, adaptada de forma mínima y
documentada — sin sustituirla):

1. **Top bar:** el test de boot verifica tinta blanca del glifo suelto
   (9x10 ±2), centrado vertical respecto a la tinta del wordmark (≤1 px), gap
   7..9 px (layout 8), **0 px de azul #004EFD** en la barra y `TOPBAR_H == 30`.
   El test de maximizado exige `n_top==0` + `n_bottom==0` + `n_mid==0` y
   comprueba aparte que la marca blanca sigue presente; `topbar_layout` toma la
   posición de la marca de la tinta blanca. No se relajó ninguna aserción de
   forma/centrado ni de splash/About/dock/menú.
2. **Flujo PAC-MAN SereOS:** se conserva el flujo externo (título/attract →
   menú arcade → segundo Enter → `GAME_START`) y la captura
   `07b_pacman_menu`.

Resultado sobre la ISO final: **18/18 PASS** (boot, terminal, files, monitor,
about, maximize, corners, dock, topnav, game, audio, window_close,
window_focus, text_fallback, panic, resolution_1280, resolution_800,
no_fatal). Log: `task14_fullsuite_final.log`.

## Ficheros de evidencia

* `topbar_10px_6x.png` / `topbar_10px_8x.png` — top bar final SIN azul con el
  glifo a escala del wordmark, alineado y a gap 8 px (x6 y detalle x8).
* `00_topbar_alineacion_antes_despues.png` — top bar x6 ANTES (logo 22 px, más
  alto que el texto) / DESPUÉS (logo ~10 px alineado con el wordmark).
* `glifos_topbar_png_vs_oficial.png` — topbar PNG sin contenedor frente a menú
  cabecera 24 oficial y Acerca de 60 oficial (ambos con azul).
* `07b_pacman_menu.png` — menú arcade del flujo PAC-MAN SereOS.
* `00_logo_componente_variantes.png`, `00_logo_AA_antes_despues.png` —
  preview/comparativa del componente (logo-core).
* `splash_88_anillo_4x.png`, `about_60_4x.png`, `dock_40_4x.png` — recortes de
  ubicaciones con glifo oficial.
* `01_splash.png`, `02_desktop.png`, `02b_topbar_dock.png`, `06_about.png`,
  `22_menu_logo.png`, `16_resolution_1280x1024.png`,
  `17_resolution_800x600.png`, `15_panic.png` — capturas principales.

Nota: los scripts de medida viven en `/tmp/qa_visual/` y no forman parte del
entregable del repo. Las capturas de 04:05 (árbol revertido, diseño viejo)
fueron reemplazadas por las de este artefacto restaurado.
