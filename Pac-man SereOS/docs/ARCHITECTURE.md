# Arquitectura de PAC-MAN SereOS (componente independiente)

Estado: **diseno y esqueleto de interfaces** (2026-11-20). La implementacion
se completa cuando kernel-sys confirme que `sistema operativo/` esta migrado y
estable; hasta entonces este documento y `include/` son el contrato congelado
del componente.

## 1. Objetivo

Un unico juego (logica + render + assets) con **dos backends**:

- **SereOS**: libreria estatica freestanding `build/sereos/libpacman.a` que
  exporta `app_t *app_game(void)`. El kernel enlaza la libreria como una app
  mas del escritorio (sin SDL, sin libc del host, sin FPU).
- **Linux**: ejecutable nativo `build/pacman-sereos` con SDL2, usando el mismo
  nucleo y el mismo render, y una implementacion de plataforma sobre un
  framebuffer software.

No se duplica fisica, colisiones, IA, puntuacion ni niveles: una sola copia
del nucleo y del render; solo cambian las primitivas de plataforma.

## 2. Capas y direccion de dependencias

```
                +-----------------------------+
                |  src/platform/sereos        |  app_t, tarea cooperativa,
                |  (game_app.c + platform)    |  gfx_*/text_*/audio_*/...
                +-------------+---------------+
                              |
+-----------------------------+-----------------------------+
|  src/core (logica)          |        src/render (comun)     |
|  maze, entities, ai, input, |  game_render.c, pac_ui.c,     |
|  audio events, game state   |  pac_theme.c                  |
+---------------+-------------+---------------+---------------+
                |                             |
                +-------- include/pac_platform.h ------------+
                              |                             |
                +-------------+---------------+---------------+
                |  src/platform/linux         |  SDL2 + framebuffer
                |  (main.c + platform)        |  software 1024x768
                +-----------------------------+
```

Reglas duras:

- `src/core` y `src/render` **solo** incluyen:
  - cabeceras estandar de C (`<stdint.h>`, `<stddef.h>`, `<string.h>`),
  - `include/pac_platform.h`, `include/pacman.h`,
  - cabeceras propias de core/render y `assets/`.
- Ningun header de SereOS (`gui/`, `graphics/`, `drivers/`, `audio/`, `fs.h`,
  `app.h`...) aparece en core/render.
- Ningun include de SDL fuera de `src/platform/linux`.
- El render comparte el 100% del codigo de pantallas: menus, instrucciones,
  record, HUD, pausa, game over y nivel completado se dibujan igual en ambos
  backends.

## 3. Estructura de directorios

```
PAC-MAN SereOS/
├── include/
│   ├── pac_platform.h     contrato de plataforma (render/input/time/audio/storage/log)
│   ├── pacman.h           API publica del nucleo (opaca) para los backends
│   ├── pac_theme.h        tokens visuales del sistema (mismos valores que SereOS)
│   └── pac_ui.h           tarjetas/superficies/separadores compartidos
├── src/
│   ├── core/              logica compartida (sin plataforma)
│   │   ├── pac_game.h        estado pac_game_t y API interna
│   │   ├── game.c            maquina de estados, puntuacion, vidas, niveles, record
│   │   ├── game_maze.c/.h    laberinto 28x31, dots, tuneles, casa
│   │   ├── game_entities.c/.h Pac-Man y 4 fantasmas
│   │   ├── game_ai.c/.h      objetivos, decisiones, scatter/chase/frightened/Elroy
│   │   ├── game_input.c/.h   teclado -> direccion solicitada/menus (pac_event_t)
│   │   └── game_audio.c/.h   eventos de juego -> pac_audio_* (sin backend)
│   ├── render/
│   │   ├── game_render.c/.h  todas las pantallas y HUD
│   │   ├── pac_ui.c          kit minimo (card/surface/divider)
│   │   └── pac_theme.c       tokens + blend
│   └── platform/
│       ├── sereos/
│       │   ├── game_app.c    app_t *app_game(), open/close/draw/event/task
│       │   └── platform_sereos.c  implementa pac_platform.h con el OS
│       └── linux/
│           ├── main.c        bucle SDL2, eventos, ventana, --smoke
│           ├── platform_linux.c  framebuffer 32bpp, input, audio, storage
│           └── text_linux.c  pac_text_* usando el atlas Inter/JetBrains Mono
├── assets/
│   ├── sprites.c/.h          sprites originales RGB565 (simbolos pacasset_*)
│   ├── preview.png
│   ├── README.md             documentacion del arte original
│   └── fonts/                atlas tipograficos (SIL OFL) para Linux
├── tools/                    generadores originales de sprites/fuentes
├── docs/                     ARCHITECTURE, INTEGRATION, GAME
├── tests/                    harness core con plataforma mock + smoke Linux
├── build/                    salidas (linux/, sereos/)
├── Makefile                  targets all/linux/sereos/clean/test
└── run.sh                    ejecutable Linux con chequeo de SDL2
```

## 4. Contrato de plataforma (`include/pac_platform.h`)

Funciones que cada backend implementa (detalle en el header):

| Grupo | Funciones |
|---|---|
| ciclo de vida/ventana | `pac_platform_init/shutdown`, `width/height`, `content_rect`, `focused`, `minimized`, `request_close`, `present`, `mark_dirty`, `log` |
| tiempo/memoria | `pac_time_ms`, `pac_alloc/free` |
| persistencia | `pac_storage_read/write` (clave `"record"`) |
| render | `pac_set_clip/reset_clip/get_clip`, `fill_rect[_alpha]`, `draw_rect`, `fill_round_rect[_alpha]`, `draw_round_rect`, `blit_rgb`, `sprite[_alpha]` |
| texto | `pac_text_width/height/ascent/line_gap`, `pac_text_draw[_alpha/_center/_right]` con `pac_text_style_t` |
| audio | `pac_audio_init/available/play/loop/stop_loop/stop/update` con `pac_audio_sfx_t` |
| input | `pac_input_key_down`, `pac_mouse_x/y` |

Modelo de eventos: el backend entrega `pac_event_t` al core via
`pac_game_event()`; el core no conoce SDL ni la cola de entrada del OS. Las
teclas mantenidas se consultan con `pac_input_key_down()` (fisica/menus). El
raton usa coordenadas absolutas de ventana; el core hace hit-testing con el
ultimo viewport.

## 5. Refactor de los modulos existentes (sin reescribir logica)

Se reutiliza `sistema operativo/apps/game/` tal cual en su mayoria; los cambios
son de desacoplamiento, no de comportamiento:

| Actual (`apps/game/...`) | Destino | Cambios |
|---|---|---|
| `game.h` | `src/core/pac_game.h` | quita `app.h/window.h/graphics.h/input.h`; incluye `pac_platform.h`; `pac_game_t` opaca fuera de core; anade `want_close`, `viewport`, reloj de plataforma |
| `game.c` | `src/core/game.c` + backends | la logica (estados, score, vidas, nivel, record) queda en core; open/close/task/window pasan a `platform/sereos/game_app.c`; bucle/ventana a `platform/linux/main.c`; `pac_game_create/destroy/event/tick/draw/wants_close` en core |
| `game_maze.c/.h` | `src/core/game_maze.c/.h` | sin cambios de logica; sin `window/graphics` (ya no los usaba) |
| `game_entities.c/.h` | `src/core/game_entities.c/.h` | sin cambios de logica/colisiones/velocidades |
| `game_ai.c/.h` | `src/core/game_ai.c/.h` | sin cambios de personalidades/modos/decision |
| `game_input.c/.h` | `src/core/game_input.c/.h` | `event_t` -> `pac_event_t`; sin `window.h`; usa `pac_platform_*` |
| `game_audio.c/.h` | `src/core/game_audio.c/.h` | `audio_*` -> `pac_audio_*` + enum `pac_audio_sfx_t` |
| `game_render.c/.h` | `src/render/game_render.c/.h` | `gfx_*` -> `pac_*`; `text_*` -> `pac_text_*`; `theme` -> `pac_theme`; `ui_*` -> `pac_ui_*`; `window_content_*` -> viewport recibido |
| `assets/assets.c/.h` | `assets/sprites.c/.h` | copia; simbolos renombrados `pacasset_*` para no colisionar con el OS |
| `gui/theme.h`, `gui/ui.h` | `include/pac_theme.h`, `include/pac_ui.h` | copia autocontenida (sin simbolos `theme`/`ui_*` globales) |
| `graphics/text.h` (tipo `text_style_t`) | `pac_text_style_t` en `pac_platform.h` | mapeo 1:1 por indice y tamano |

La logica de fisica/IA/colisiones/puntuacion/niveles **no se toca**. Los
cambios son mecanicos (prefijos y adaptadores) y se validan con el harness
existente (131 checks).

## 6. Backend SereOS (`src/platform/sereos`)

- `game_app.c`: define `app_t *app_game(void)` con id `"game"`, nombre visible
  **"PAC-MAN SereOS"**, icono `"game"`, ventana 880x560, `update = NULL`.
  - `open()`: `pac_game_create()` (usa `pac_alloc`->`kmalloc`), guarda el
    puntero en `window_data`, `window_set_title("PAC-MAN SereOS")`,
    `task_create("game", game_step, w)` y `window_invalidate`.
  - `game_step()`: llama a `pac_game_tick`; si devuelve 1 -> `window_invalidate`;
    si `pac_game_wants_close` -> `window_close(w)` (cierre diferido; nunca
    libera a mano).
  - `event()`: traduce `event_t` (drivers/input.h) a `pac_event_t` y llama a
    `pac_game_event`; Esc en menu/game over lo resuelve el core con
    `wants_close`.
  - `draw()`: `pac_game_draw(&viewport)` con `window_content_x/y/w/h`.
  - `close()`: mata la tarea, `pac_game_destroy` (guarda record, detiene audio),
    `window_set_data(NULL)`.
- `platform_sereos.c`: implementa `pac_platform.h` con APIs del OS:
  - render -> `gfx_fill_rect*`, `gfx_draw_rect`, `gfx_fill_round_rect*`,
    `gfx_draw_round_rect`, `gfx_blit_rgb`, `gfx_draw_sprite[_alpha]`,
    `gfx_set_clip/reset_clip/get_clip`, `gfx_mark_dirty`.
  - texto -> `text_*` del OS (mismo atlas Inter/JetBrains Mono del sistema).
  - input -> `input_key_down` y traduccion de `keycode_t`; raton `input_mouse_x/y`.
  - tiempo -> `timer_uptime_ms`.
  - audio -> `audio_*`.
  - memoria -> `kmalloc/kfree`.
  - storage -> `fs_readfile/fs_writefile` con clave `"record"` ->
    `/home/pacman_sereos.hi`.
  - log -> `serial_write(marker); serial_write("\n")`.
  - cierre/foco/ventana -> `window_close`, `window_active`, `window_minimized`.
- La libreria **no define** simbolos del OS (`gfx_*`, `text_*`, `ui_*`,
  `theme`, `audio_*`): solo los referencia. El OS los aporta al enlazar.

## 7. Backend Linux (`src/platform/linux`)

- `main.c`: ventana SDL2 1024x768 (`SDL_RenderSetIntegerScale` para escalado
  entero si el usuario redimensiona), bucle de ~60 Hz, eventos SDL -> `pac_event_t`,
  `pac_game_tick`, render al framebuffer software y `SDL_RenderPresent`.
  - Cierre con ventana/Esc segun estado; `--smoke N` ejecuta N frames sin
    intervencion (para `SDL_VIDEODRIVER=dummy`) y `--screenshot RUTA` guarda
    un BMP/PNG del ultimo frame; `--frames`/`--record` opcionales.
- `platform_linux.c`: framebuffer 32bpp 1024x768 en memoria; primitivas con
  clipping y alpha; sprites RGB565; texto via `text_linux.c`; input con estado
  de teclado SDL; reloj `SDL_GetTicks`; audio SDL sintetizado (onda cuadrada de
  frecuencias conocidas por efecto, sirenas en loop); storage en
  `$XDG_DATA_HOME/pacman-sereos/record.txt` (fallback `~/.local/share/...`,
  `./record.txt`); log a stderr (marcadores `GAME_*` utiles para QA).
- `text_linux.c`: adaptacion del motor tipografico del OS (mismo formato de
  atlas y mismas metricas) que implementa `pac_text_*`. Los atlas
  `text_data.c` + `text_internal.h` se copian a `assets/fonts/` (Inter y
  JetBrains Mono, SIL OFL 1.1; se documenta atribucion). Asi el render comun
  mide y dibuja igual en ambos backends.
- Sin headers ni archivos del OS en el build Linux; solo `pkg-config sdl2`.

## 8. Modelo de tiempo, input y cierre

- `pac_game_tick()` lee `pac_time_ms()`, acumula en ms con limite (120 ms),
  ejecuta pasos fijos de 16 ms (~62.5 Hz) y decide redibujar a 30 fps
  (33 ms), igual que el juego actual. Sin esperas bloqueantes.
- Si `pac_platform_focused()==0` o `pac_platform_minimized()`, el core congela
  la simulacion y no acumula tiempo.
- Cierre: el core solo marca `want_close`; cada backend lo traduce a
  `window_close()` (SereOS, diferido por el compositor) o a salir del bucle
  (Linux).
- Esc: en menu/game over -> quiere cerrar; en pausa -> reanudar; Q en pausa ->
  volver al titulo. Controles: flechas/WASD, Enter, Esc, R.

## 9. Persistencia y marcadores

- Clave logica `"record"` (texto entero). SereOS:
  `/home/pacman_sereos.hi`. Linux: fichero de usuario XDG. Los fallos se
  ignoran (record 0), nunca rompen la partida.
- Marcadores de QA via `pac_platform_log`: `GAME_MENU`, `GAME_START`,
  `GAME_PAUSE`, `GAME_OVER`, `GAME_WIN`, `GAME_EXIT`. En SereOS van a COM1; en
  Linux a stderr.

## 10. Build

- `make` (default) -> `build/pacman-sereos` (SDL2, host gcc).
- `make sereos` -> `build/sereos/libpacman.a` con flags freestanding
  `-m32 -ffreestanding -fno-pie -fno-pic -mno-sse -mno-mmx -O2`; incluye
  core+render+platform/sereos+assets/sprites; incluye headers del OS desde
  `../sistema operativo/` via `OS_DIR` (configurable). No necesita SDL.
- `make test` -> harness de core nativo + smoke Linux sin display.
- `make clean` -> borra `build/`.

## 11. Pruebas

1. **Harness de core** (`tests/`): plataforma mock con framebuffer en memoria,
   reloj e input simulados, audio/storage/log mock. Migra los 131 checks del
   harness actual (`/tmp/ptest`): conectividad BFS de 240 dots + 4 pills,
   Pac-Man sin atravesar paredes, casa/fantasmas sin atascos, objetivos por
   personalidad, power pill/frightened/comer fantasma, muertes/vidas/game over,
   nivel completado, fruta, vida extra, pausa, record, reapertura (regresion
   del bug de segunda apertura), layouts a 878x523 / 798x563 / 1022x731 /
   300x200.
2. **Smoke Linux**: `SDL_VIDEODRIVER=dummy ./build/pacman-sereos --smoke 300`
   + captura; valida arranque, estados y record persistente.
3. **Manual Linux real**: ejecutar `./run.sh`, capturas de menu, juego, pausa,
   game over/nivel completado; guardar en `docs/captures/`.

## 12. Plan de migracion (cuando kernel-sys confirme)

1. Copiar `sistema operativo/apps/game/*` a `src/core`/`src/render` (mover, no
   duplicar) y `apps/game/assets/*` a `assets/`.
2. Copiar de `sistema operativo/graphics/`: `text_data.c`, `text_internal.h`,
   `text.c` -> `assets/fonts/` + `src/platform/linux/text_linux.c` (adaptado);
   `font_data.c`/`font.c` solo si se necesita fallback.
3. Aplicar refactor mecanico: renombrar `gfx_*`->`pac_*`, `text_*`->`pac_text_*`,
   `theme`->`pac_theme`, `ui_*`->`pac_ui_*`; sustituir includes; aislar app_t en
   platform/sereos.
4. Implementar `platform_linux.c` + `text_linux.c` + `main.c`; compilar y
   corregir hasta cero warnings.
5. Implementar `platform_sereos.c` + `game_app.c`; `make sereos` con headers
   del OS; revisar simbolos (`nm`) y que solo exporte `app_game` + API `pac_*`.
6. Migrar el harness a mock de `pac_platform.h`; ejecutar 131 checks.
7. Capturas Linux reales + smoke; `README`/docs finales; reportar a lead.

## 13. Riesgos y decisiones abiertas

- **Nombres/colisiones**: el componente renombra sprites a `pacasset_*` y no
  define simbolos del OS. Si kernel-sys mantiene compilado `apps/game`, habria
  duplicados de `app_game`/assets: la integracion debe excluir ese directorio
  del build del OS (lo hace kernel-sys).
- **Texto**: se reutiliza el atlas del OS (Inter/JetBrains Mono, SIL OFL). Si
  kernel-sys prefiere no copiar `text_data.c` al componente, la alternativa es
  generar un atlas propio con `tools/gen_ui_fonts.py` y documentar licencia.
- **Libc en sereos**: core usa `memset/memcpy/strlen/atoi/itoa/snprintf`; el
  target sereos los resuelve con `../sistema operativo/libc` (el OS ya los
  aporta). No se enlaza libc del host.
- **Ventana Linux**: 1024x768 con escalado entero; SereOS mantiene 880x560
  (area de contenido ~878x523). El render es responsive a `pac_platform_content_rect`.
- **Audio Linux**: sintesis propia simple (sin WAVs ni recursos de terceros).
  Si SDL audio no esta disponible, el juego funciona en silencio.
