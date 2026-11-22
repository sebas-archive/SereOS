# Integracion de `libpacman.a` en SereOS (para kernel-sys)

Este documento es el contrato de integracion del componente **PAC-MAN SereOS**
con el sistema operativo. Lo mantiene el equipo del juego; kernel-sys solo
necesita:

1. Compilar la libreria con `make -C "PAC-MAN SereOS" sereos`.
2. Enlazarla en `sereos.bin` y excluir `apps/game/` del build del OS.
3. No cambiar la firma ni el registro de la app.

## 1. API exportada

El objeto `build/sereos/libpacman.a` exporta:

```c
/* gui/app.h */
app_t *app_game(void);
```

`app_t` tiene exactamente el contrato actual:

| campo | valor |
|---|---|
| `id` | `"game"` |
| `name` | `"PAC-MAN SereOS"` |
| `icon` | `"game"` |
| `default_width` | `880` |
| `default_height` | `560` |
| `init` | `NULL` |
| `open` | crea estado + `task_create("game", ...)` |
| `close` | mata tarea + guarda record + `audio_stop` + free |
| `draw` | render compartido con el clip del compositor |
| `event` | teclas/raton del escritorio |
| `update` | `NULL` (avanza la tarea cooperativa) |

`apps/apps.c` de SereOS ya llama a `app_game()`; no hay que modificarlo.

## 2. Compilacion de la libreria

Desde el directorio raiz del proyecto final:

```sh
make -C "PAC-MAN SereOS" sereos
```

El target usa `OS_DIR` (por defecto `../sistema operativo`) y genera:

```
PAC-MAN SereOS/build/sereos/libpacman.a
```

Flags usados (freestanding i686, igual que el kernel):

```
-m32 -std=gnu99 -ffreestanding -fno-pie -fno-pic -fno-stack-protector
-fno-asynchronous-unwind-tables -march=i686 -mno-sse -mno-mmx
-O2 -Wall -Wextra -Wno-unused-parameter
```

Incluye: `src/core`, `src/render`, `src/platform/sereos` y
`assets/sprites.c`. **No** incluye `assets/fonts` ni SDL (SereOS usa su propio
motor tipografico vía `pac_platform.h`).

Si el OS vive en otra ruta:

```sh
make -C "PAC-MAN SereOS" sereos OS_DIR="/ruta/a/sistema operativo"
```

## 3. Cambios necesarios en el Makefile del OS (los hace kernel-sys)

1. **Excluir** `apps/game/` del build del OS (`find` / `SRCS_C`), porque su
   `app_game`, sus assets y su `game_render` colisionarian con la libreria y ya
   no deben compilarse. El resto de apps se mantiene.
2. **Anadir la libreria** a la linea de enlace, antes de `-lgcc`:

```make
PACMAN_LIB := PAC-MAN SereOS/build/sereos/libpacman.a

$(PACMAN_LIB):
	$(MAKE) -C "PAC-MAN SereOS" sereos

sereos.bin: $(OBJS) $(PACMAN_LIB) linker.ld
	$(LD) $(LDFLAGS) -o $@ $(OBJS) $(PACMAN_LIB) -lgcc
```

3. **Orden**: la libreria va despues de los objetos del OS que la usan
   (`apps/apps.o` referencia `app_game`) y antes de `-lgcc`. No se necesita
   `--whole-archive` porque `apps/apps.o` fuerza la referencia.

## 4. Simbolos y colisiones

La libreria define **solo** simbolos propios:

- `app_game` (unico simbolo con nombre "del OS", como antes),
- todo el nucleo/render con prefijo `pac_` (`pac_game_*`, `pac_render_*`,
  `pac_ui_*`, `pac_theme*`, `pac_platform_*` internos del backend),
- assets con prefijo `pacasset_*` (sprites RGB565, frutas, vida).

**No define** ningun simbolo del OS: `gfx_*`, `text_*`, `ui_*`, `theme`,
`audio_*`, `keyboard_*`, `task_*`, `kmalloc/kfree`, `fs_*`, `serial_*`.
Todos los referencia y los resuelve el kernel al enlazar. Esto evita duplicados
(por ejemplo con `gui/theme.c`, `graphics/text.c`, `gui/ui.c`).

Comprobacion rapida recomendada:

```sh
nm -g --defined-only "PAC-MAN SereOS/build/sereos/libpacman.a" | grep -v ' pac\| app_game'
```

(La salida debe ser vacia o solo simbolos internos del compilador.)

## 5. Dependencias del OS que la libreria espera

Resueltas por el kernel, con los headers congelados actuales:

- `gui/app.h`, `gui/window.h`, `drivers/input.h` (solo en `src/platform/sereos`).
- `drivers/sb16.h` para PCM real (el adaptador usa SB16 si esta presente y
  cae a `audio_*` sintetizado si no).
- `graphics/graphics.h`, `graphics/text.h` (render/texto).
- `drivers/timer.h`, `drivers/serial.h`, `drivers/speaker.h`/`audio/audio.h`.
- `memory/kmalloc.h`, `filesystem/fs.h`, `process/task.h`, `kernel/log.h`.

El record se guarda en `/home/pacman_sereos.hi` vía `fs_writefile` (tolera
fallo y usa 0); settings en `/home/pacman_sound.cfg`,
`/home/pacman_fullscreen.cfg`, `/home/pacman_classic.cfg`. La libreria incluye
los assets privados de `Res` (sprites/fuente/PCM); ver `assets/LICENSE_RES.md`.

## 6. Comportamiento observable para QA

- F4 abre la ventana "PAC-MAN SereOS" (880x560), menu de titulo.
- Seriales (COM1): `APP_OPEN:game`, `GAME_MENU`, `GAME_START`, `GAME_PAUSE`,
  `GAME_OVER`, `GAME_WIN`, `GAME_EXIT`, `APP_CLOSE:game`.
- Controles: flechas/WASD mover, Enter confirmar, Esc pausa/atras, R reiniciar,
  Q volver al titulo desde pausa; Esc en titulo/game over cierra la ventana.
- Cierre/reabrir repetido debe reconstruir los 240 dots + 4 power pills
  (regresion cubierta por el harness del componente).
- Sin panicos ni excepciones; no modifica el escritorio ni su Makefile desde
  el componente.

## 7. Verificacion de integracion sugerida

```sh
make -C "PAC-MAN SereOS" sereos        # debe compilar con cero warnings
make -C "PAC-MAN SereOS" test          # harness core + smoke Linux
make -C "sistema operativo"            # enlaza libpacman.a en sereos.bin
python3 "sistema operativo/tools/qemu_ctrl.py" --keys "f4" --marker "APP_OPEN:game" --marker "GAME_MENU" --shot /tmp/pac.png
```

Si `make sereos` falla por cabeceras, revisar `OS_DIR`; si falla el enlace por
simbolos duplicados, confirmar que `apps/game/` no se compila.
