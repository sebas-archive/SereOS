# Sprites originales de PAC-MAN SereOS

Recursos graficos del juego **PAC-MAN SereOS** (SereOS Desktop v1.0, proyecto
final de Sistemas Operativos - UMB 2026).

**El build por defecto usa derivados privados de `Res`** (frutas, cuerpo de
fantasmas recoloreado y ojos) desde `assets/sprites_res.c`; se activan con
`PACMAN_USE_RES_ASSETS=1` (por defecto). Ver [`LICENSE_RES.md`](LICENSE_RES.md):
material de uso privado/academico, **no redistribuir publicamente**; los
originales usados estan en `res_original/`. El arte original del proyecto
sigue disponible como fallback con `-DPACMAN_USE_RES_ASSETS=0`.
De `Res` se integran **7 PNG** (5 frutas activas + 2 cuerpos de fantasma),
**10 WAV** y **1 TTF**. Ademas se copia `key.png` solo como procedencia de la
llave decorativa (su sprite es procedural, no se convierte).

**El arte original fue creado para este proyecto** con primitivas de
dibujo (Python puro) y verificado por el generador. No se copia ni se deriva
ningun pixel de Pac-Man / Namco ni de hojas de Paku-Paku; esos recursos solo
se usaron, si acaso, como referencia de *estilo de genero* (arcade de 16
bits). La paleta y los motivos siguen la identidad visual de SereOS Desktop
(navy profundo, azul electrico `#2E7BFF` y cian `#22D3EE`).

## Contenido

| Archivo | Descripcion |
|---|---|
| `sprites.h` | Contrato (tamanos, arrays, selector Res/fallback). |
| `sprites.c` | Arrays originales (Pac-Man, vida y fallback). |
| `sprites_res.h/.c` | Arrays definitivos derivados de `Res` (16x16, privado). |
| `font_arcade.h/.c` | Atlas alpha 8x16 de Press Start K (privado). |
| `sfx_res.h/.c` | PCM u8 mono 11025 de los 10 WAV de `Res`. |
| `LICENSE_RES.md` | Procedencia, hashes y aviso de no redistribucion. |
| `preview.png` | Hoja de prevision ampliada (damero = transparencia). |
| `../tools/gen_pacman_assets.py` | Generador reproducible + validacion. |

## Formato

- **16x16** pixeles por sprite, fila a fila, `uint16_t` **RGB565**
  (`r5 << 11 | g6 << 5 | b5`).
- **Transparente = `0xF81F`** (`GFX_TRANSPARENT`), usado como clave en
  `pac_sprite()`. La transparencia aparece **solo fuera de la figura**:
  el generador rellena con contorno cualquier hueco encerrado.
- **Contorno oscuro opaco `#182236`** en todo pixel de borde: separa el
  sprite del laberinto y del fondo. No se usa negro puro como falso
  transparente.
- Volumen en pixel art: luz asimetrica arriba/izquierda, sombra
  abajo/derecha y un brillo especular sobre el cuerpo.

## Contrato (ver `sprites.h`)

| Array | Dimension | Contenido |
|---|---|---|
| `pacman_frame[4][3][256]` | 4 direcciones x 3 bocas | 0=derecha, 1=izquierda, 2=arriba, 3=abajo; boca 0=cerrada, 1=semiabierta, 2=abierta. Ambar con brillo. |
| `ghost_frame[4][2][256]` | 4 colores x 2 frames | Rojo, rosa, cian y naranja originales; 2 frames de falda. Ojos blancos con pupila azul neutros (mirando al frente), segun contrato. |
| `ghost_fright_frame[2][256]` | 2 frames | Fantasma azul oscuro asustado: ojos redondos y boca en zigzag. |
| `ghost_flash_frame[2][256]` | 2 frames | Parpadeo final: cuerpo blanco con ojos/boca azul electrico. |
| `ghost_eyes_frame[4][256]` | 4 direcciones | Solo ojos y pupilas, mirando a derecha/izquierda/arriba/abajo (vuelta a la casa). |
| `fruit_sprite[5][256]` | 5 frutas | CEREZA, FRESA, NARANJA, MANZANA, UVAS. |
| `fruit_name[5]` | 5 cadenas | Nombres exactos para la interfaz. |
| `life_sprite[256]` | 1 | Vida extra: mini comecocos ambar. |
| `key_sprite[256]` | 1 | Llave dorada decorativa del indicador de NIVEL; no es fruta ni da puntos. |

Uso en el juego:

```c
#include "sprites.h"

pac_sprite(x, y, (const uint16_t *)pacasset_pacman_frame[dir][mouth], 16, 16);
pac_sprite(x, y, (const uint16_t *)pacasset_ghost_frame[color][anim], 16, 16);
pac_sprite(x, y, (const uint16_t *)pacasset_ghost_fright_frame[anim], 16, 16);
pac_sprite(x, y, (const uint16_t *)pacasset_fruit_sprite[fruit], 16, 16);
```

`sprite` se dibuja en coordenadas de pantalla absolutas; el motor ya aplica
el recorte del compositor.

## Direccion artistica

- **Pacman**: ambar dorado (`#FFC93C`) con luz `#FFE58A`, sombra `#E09A1E` y
  especular casi blanco. La boca es una cuna abierta al borde del circulo
  (0/22/40 grados por lado) y las otras direcciones se obtienen rotando o
  espejando el sprite base, de modo que las 12 bocas son coherentes.
- **Fantasmas**: silueta de domo clasico del genero (no derivada de Namco),
  colores propios: rojo `#FF4A5A`, rosa `#FF6CC4`, cian `#2ED6E2`, naranja
  `#FF9C37`, con luz/sombra calculadas por contraste. La falda alterna dos
  patrones de pies (3 pies, fase desplazada) para la animacion.
- **Ojos**: sclera blanca 4x4 con pupila 2x2 azul `#2E7BFF`; en el frame
  neutro la pupila va centrada y en `ghost_eyes_frame` se desplaza en la
  direccion de la mirada. El contorno de los ojos sin cuerpo es mas grueso
  para que se lean sobre el maze.
- **Asustado / parpadeo**: mismo cuerpo con azul oscuro `#3D62E8` y cara
  clara, o cuerpo blanco `#EFF4FF` con cara azul para el ultimo parpadeo.
- **Frutas**: 5 disenos propios legibles a 16x16 (formas redondeadas, hojas
  verdes, semillas y racimo de uvas).
- **Vida extra**: reutiliza el diseno de Pacman semiabierto para ser coherente.
- **Llave decorativa**: llave dorada con anilla, vastago y dos dientes, usada
  solo como icono del indicador de NIVEL en el HUD (no es una fruta). Las
  frutas campana y galaxian quedan eliminadas del juego.

El contorno se genera automaticamente despues de componer cada figura, de
modo que todas las siluetas comparten el mismo estilo "sticker" oscuro.

## Regeneracion reproducible

El generador usa solo la libreria estandar de Python para pintar y Pillow
para la hoja de prevision (viene incluida en el Python del entorno de
desarrollo). Es **determinista**: mismo codigo -> mismos bytes.

```bash
# Python bundled del harness (tiene Pillow); desde la raiz del repo:
~/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3 \
    tools/gen_pacman_assets.py

# Equivalente si el python3 del sistema tiene Pillow:
python3 tools/gen_pacman_assets.py
```

El script:

1. Pinta los 35 sprites con primitivas (circulos, elipses, filas, polilineas,
   capsulas).
2. Valida por sprite: 16x16, transparencia solo exterior (sin huecos),
   contorno oscuro opaco en el borde, minimo de pixeles opacos, ausencia de
   negro puro, frames/direcciones/colores distintos y orden de bocas.
3. Escribe `assets/sprites.c` y `assets/preview.png`
   (falla con codigo 1 si alguna validacion no se cumple).

## Compilacion y verificacion

Compilacion del asset con los flags freestanding del kernel (cero warnings):

```bash
gcc -m32 -std=gnu99 -ffreestanding -fno-pie -fno-stack-protector \
    -mno-sse -mno-mmx -O2 -Wall -Wextra -Iassets \
    -c assets/sprites.c -o /tmp/assets.o
```

Comprobacion adicional hecha con un test C temporal (`/tmp/verify_assets.c`):

- `sizeof` de los arrays coincide EXACTAMENTE con `sprites.h`
  (`4*3*256`, `4*2*256`, ...) mediante comprobaciones en tiempo de
  compilacion.
- Los 4 nombres de direccion y las 3 bocas se comportan como espera el
  contrato (la boca abierta apunta a su direccion y decrece el numero de
  pixeles opacos: cerrada > semi > abierta).
- Todos los sprites: transparencia solo exterior, contorno oscuro en el
  borde, sin negro puro, con minimo de pixeles.
- `fruit_name[]` coincide exactamente con CEREZA..UVAS y las 5 frutas son
  distintas entre si.

Resultado: **PASS** (contrato, dimensiones, transparencia `0xF81F`, contorno,
animaciones, direcciones y nombres correctos).

Ademas, los 35 sprites se dibujaron con el **motor grafico real** de SereOS
(`graphics.c` + `gfx_draw_sprite`) en un framebuffer 1024x768 sobre un fondo
navy con rejilla azul: la clave de transparencia `0xF81F` y la conversion
RGB565 funcionan sin halos ni cajas opacas alrededor de las figuras.

## Integracion y limitaciones

- Los sprites van centrados en 16x16 y el contorno ocupa el borde del tile
  (margen de 1 px en la mayoria), pensado para `pac_sprite(x, y, px, 16, 16)`.
- `ghost_frame` usa ojos neutros al frente, tal y como pide el contrato; la
  direccion de la mirada se aporta con `ghost_eyes_frame` (modo "ojos
  volviendo a casa").
- `sprites.h` es el contrato congelado: este modulo no lo modifica.
- Las 5 frutas y los nombres son originales; no representan marcas ni
  personajes de terceros.
