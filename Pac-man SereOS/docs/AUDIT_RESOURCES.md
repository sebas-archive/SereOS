# Auditoría técnica de recursos — PAC-MAN SereOS definitivo (Fase 1)

- **Tarea:** `task-34` (Fase 1 obligatoria: auditoría de recursos, sin modificar el juego).
- **Autor:** `gfx-core` (ingeniería de gráficos).
- **Fecha:** 2026-11-20.
- **Fuente de recursos:** `/home/t1an/Descargas/Res/` (15 PNG + 11 WAV + 2 TTF).
- **Proyecto destino:** `PAC-MAN SereOS/` (núcleo compartido SereOS + Linux; assets actuales en `assets/`).
- **Referencia de comportamiento:** `/home/t1an/Descargas/Paku-Paku/` (VB6; se conserva su diseño y reglas).
- **Estado:** Fase 1 **completada**. Solo se ha documentado y se han generado prototipos en `/tmp`; **no se ha modificado código ni assets del juego**.

> **Documento complementario:** la auditoría de mecánicas/reglas de Paku-Paku
> está en [`docs/AUDIT_PAKUPAKU.md`](AUDIT_PAKUPAKU.md) (task-33); este documento
> cubre **recursos y pipeline de conversión** (PNG/WAV/TTF). No se solapan.
>
> **Aviso de licencias (resumen):** los PNG y WAV de `Res/` **no traen licencia ni
> atribución**; su origen y fechas sugieren material arcade de Pac-Man (Namco).
> Los TTF tampoco acreditan licencia en sus metadatos. Antes de redistribuir el
> juego hay que decidir entre uso privado/académico con atribución o sustitución
> por assets propios/OFL (ver §6). Este documento **no reclama autoría** sobre
> ningún recurso de `Res/`.

---

## 0. Resumen ejecutivo

1. **Los 15 PNG son utilizables y encajan con el juego**, pero con matices:
   - **5 frutas activas** (`cherry`, `strawberry`, `peach`, `apple`, `grapes`)
     son las que integra el juego definitivo: CEREZA, FRESA, NARANJA (`peach.png`),
     MANZANA y UVAS, por índice 0..4. El resto de PNG de fruta del arcade no se usa.
     Sustitución **directa por índice**; valores de nivel 100/300/500/700/1000 en
     ciclo `(nivel-1) % 5`.
   - **`ghost1.png` / `ghost2.png`** son el **cuerpo** naranja del fantasma en sus
     2 frames de falda, **sin ojos**: Paku-Paku los recolorea en tiempo de ejecución
     (4 colores) y superpone los ojos procedurales con dirección de mirada
     (`CreateColouredGhost` / `CreateEyeOverlay` / `cGhost.Sprite`). El pipeline
     propuesto replica esto **en tiempo de compilación** y pre-cocina los combos.
   - **No existe ningún PNG de Pac-Man**: Paku-Paku lo dibuja vectorialmente
     (`cPacMan.cls`, arco de 22 px sobre lienzo 48×48). Se mantiene la generación
     procedural actual (o se pre-cocina desde la misma fórmula).
   - **4 PNG no los usa Paku-Paku**: `retroghost1/2` (fantasmas pixel-art, ideales
     para un modo "Retro"), `Clydeeghost` (242×238, arte pixel grande para
     menú/attract) y `dead` (estallido de muerte amarillo). Son contenido nuevo
     opcional, no reemplazos; el icono de UI de la referencia se excluye.
2. **Los 11 WAV son convertibles a PCM 8 bits sin signo, mono, 11025 Hz**, que es
   exactamente lo que acepta el SB16 de SereOS. 10 los usa Paku-Paku;
   `intermission.wav` no se usa allí pero sirve para "nivel completado".
   Conversión medible: SNR 29–44 dB frente a una referencia ideal limitada a
   4,8 kHz; ganancia de normalización necesaria sobre todo en sirenas/respawn
   (−12 a −18 dBFS de origen). Dos clips superan el máximo de bloque del SB16
   (`game start` 48.272 muestras, `intermission` 57.377 > 32.768) → requieren
   reproducción por trozos.
3. **El sprite objetivo recomendado es 32×32** (2× el tile de 16 px), no 16×16:
   es la proporción real del arcade (48 px sobre tile de 24 en Paku-Paku) y evita
   perder detalle en frutas y fantasmas (PSNR 21,5 dB vs 18,5 dB en cereza;
   21,1 vs 14,9 en fantasma). Cambiar el contrato `sprites.h` es decisión
   de `game-dev` (ver §5.4).
4. **`atari full.ttf` no debe entrar en la versión definitiva** (sin licencia, marca
   "Atari", sin Latin-1 ni `\`). **`prstartk.ttf`** (Press Start K) es perfecto
   técnicamente (monoespaciada, avance = tamaño, 8/16/24 nítidas, Latin-1 casi
   completo) pero **tampoco acredita licencia**: atribuir a codeman38 y validar
   términos, o sustituir por *Press Start 2P* (OFL).
5. **Plan recomendado:** generar assets derivados (`sprites_res.c`, `sfx_res.c`,
   `font_res.c`) con un `tools/gen_pacman_res_assets.py` reproducible, mantener
   `assets/` originales como *fallback*, y activar `Res/` con un flag de build.
   No commitear `Res/` al repo (derechos inciertos).

---

## 1. Alcance, metodología y evidencias

### 1.1 Ficheros auditados

`Res/` contiene 29 ficheros útiles (más `desktop.ini` y `Thumbs.db` de Windows,
ignorables), con estos hashes MD5 (evidencia reproducible):

```
cf56cd2b32d26f4c15dc508e5153521f  apple.png          9234915891b6cc3439f88864ebbcf685  peach.png
14c9d053d854452f5b8dda84e4c32273  atari full.ttf    4e9a195e88e19adc94992d05f63db8ac  prstartk.ttf
dc19b4c029e36134774f8a4ef2964ff3  bell.png           8c87f1008ffeb8efc407e80c5c50315b  retroghost1.png
5e618304f090913d6065ef1509f41235  cherry.png         f52993153d6c199a7b2f1448374b9cc5  retroghost2.png
c55feb5101453920af779236897727cf  Clydeeghost.png   fe5c52249b327b58d0f0d09e45322ddb  strawberry.png
1c53f193f0558a0cefeddc33912e6fff  dead.png          514eeeeb192e8ca45ca92aa308f61f63  eat fruit.wav
ab55212d73c89f0b1d51055a7653ace3  galaxian.png      61d4ded9e6249e64b735982f6ced3ec5  eat ghost.wav
521be1b68ff40fc6efaca2ee6a078016  ghost1.png        27991f5575aec8695f0f9a68925b9df8  extra life.wav
4ec74e51c6f8923fd84929e0d946c51b  ghost2.png        07914ee70de9f5f1166ed3e9b35fc9db  game start.wav
43fae1a4447f5026f8f23a9d9dd02b95  ghost respawn.wav 8d5759b619045b5f6879ec83175d67a9  hunted siren.wav
ddfadec1107f87d89d9fea074f27016d  grapes.png        d35ceeea5823f2ea9c1a3d2107826b92  hunter siren.wav
566c0f2299b8a7ebef6372010fa6866e  intermission.wav  da12fac58c50c79361d76dfef25e9315  Key-icon.png
8a426c989a35a3a436837c4d0fd64177  key.png           9e3c8eb9b4d7af04971b12c9af3e5bb4  waka1.wav
b5cacf9a37e6a4fd396f6fd914168780  pacman death.wav  0452cd64893e3fbd3503190e9ff318c7  waka2.wav
```

Observaciones de contexto:

- `Paku-Paku/Res/` **está vacío**; los recursos llegaron aparte en
  `/home/t1an/Descargas/Res/`. No hay `README`, `LICENSE`, ni `desktop.ini` con
  autoría dentro de `Res/`.
- Herramientas con las que se generaron (metadatos embebidos):
  - `apple/grapes/peach/strawberry.png` → `tEXt Software = www.inkscape.org`.
  - `bell.png` → `tEXt Software = Adobe ImageReady`.
  - WAV: chunks `LIST/INFO` con `ICRD` 1994-11-30 (`eat fruit`, `intermission`),
    1996-02-02 (`extra life`); `ISFT` "Lavf58.2.100" (`game start`, FFmpeg) y
    "WHAM 1.31 by Andrew Bulhak" (`pacman death`); chunk propietario `SAUR 1.3.0.0`
    en `ghost respawn`, `hunted/hunter siren`, `waka1/2`, `eat ghost`.
  - TTF: `prstartk.ttf` incluye la URL `http://www.high-logic.com/` (FontCreator);
    `atari full.ttf` no incluye URL ni licencia.

### 1.2 Herramientas usadas

Python bundled del harness con **Pillow 12.3** y **NumPy 2.3**; `wave`, `struct`,
`hashlib`. Ningún recurso del repo se ha modificado. Prototipos y evidencias en
`/tmp/res_proto/`, `/tmp/res_audit/` y `/tmp/audit_png_sheet.png`.

### 1.3 Uso real en Paku-Paku (fuente de verdad)

| Recurso | Dónde se usa en Paku-Paku | Evidencia |
|---|---|---|
| 8 frutas de `Res/` | `Cairo.ImageList.AddImage Fruit(i)` con `Fruit = "Cherry,Strawberry,Peach,Apple,Grapes,Galaxian,Bell,Key"` | `modMain.bas:36-41` |
| `ghost1.png`, `ghost2.png` | Cuerpos base recolorados a 4 colores (Blinky/Pinky/Inky/Clyde) + ojos procedurales | `modMain.bas:42-60`, `CreateColouredGhost`, `CreateEyeOverlay` |
| ojos | `"Eyes" & dirección` superpuesto en `cGhost.Sprite()` (offsets ±3); asustado/parpadeo usa `HuntedEyes` | `cGhost.cls:360-380`, `modMain.bas:44-51` |
| `prstartk.ttf` | `InstallFont "prstartk"` + `AddFontResourceEx` | `modMain.bas:32, 114-120` |
| 10 WAV | `DSCreateSoundBufferFromFile(...)` para start, waka1/2, eat ghost, sirenas, eat fruit, extra life, ghost respawn, death | `modSoundFX.bas:22-38` |
| `intermission.wav` | **no usado** por Paku-Paku | grep sin referencias |
| `retroghost1/2`, `Clydeeghost`, `dead`, `Key-icon` | **no usados** por Paku-Paku | grep sin referencias |
| `atari full.ttf` | **no usado** por Paku-Paku | solo se instala `prstartk` |
| sirenas | `HunterSiren` en persecución normal, `HuntedSiren` en modo asustado; `SetFrequency` sube el tono según dots restantes | `cGame.cls:279, 333, 582`, `modSoundFX.bas:96-108, 120-132` |
| frutas por nivel | orden/valores 100/300/500/700/1000/2000/3000/5000 | `cMazeLevel.cls:104-122` |

---

## 2. PNG — inventario, análisis y uso

### 2.1 Tabla de inventario (15)

`alpha_lv` = niveles de alfa distintos; `soft` = píxeles con alfa 1..254
(bordes suavizados); `bbox`/`pad` = caja de tinta y márgenes (izq, arriba, der,
abajo); `vis` = píxeles con alfa > 0.

| # | Archivo | Dimensiones | Modo | vis | alpha_lv | soft | bbox | pad (L,T,R,B) | Uso Paku-Paku | Uso propuesto |
|---|---|---|---:|---:|---:|---|---|---|---|
| 1 | `apple.png` | 32×32 | P+tRNS | 608 | 69 | 128 | 3,0–29,32 | 3,0,3,0 | Fruta 4 (700) | Fruta directa, 32×32 |
| 2 | `bell.png` | 48×48 | RGBA | 1338 | 174 | 341 | 3,3–47,47 | 3,3,1,1 | Fruta 7 (3000) | **Excluido**: no es fruta activa |
| 3 | `cherry.png` | 48×48 | RGBA | 1060 | 135 | 270 | 4,0–44,48 | 4,0,4,0 | Fruta 1 (100) | Fruta, downscale 32 |
| 4 | `Clydeeghost.png` | 242×238 | P (4 colores) | 57596 | **1** (255) | 0 | 0,0–242,238 | 0,0,0,0 | **No** | Arte de menú/attract; quitar fondo blanco y reducir |
| 5 | `dead.png` | 48×48 | RGBA | 612 | 121 | 304 | 1,1–47,47 | 1,1,1,1 | **No** | Frame final de muerte/estallido (opcional) |
| 6 | `galaxian.png` | 32×32 | RGBA | 690 | 45 | 128 | 0,2–32,31 | 0,2,0,1 | Fruta 6 (2000) | **Excluido**: no es fruta activa |
| 7 | `ghost1.png` | 48×48 | RGBA | 1879 | 167 | 413 | 1,1–47,47 | 1,1,1,1 | Cuerpo fantasma frame 1 | Recolorear 4 colores, ojos, 32×32 |
| 8 | `ghost2.png` | 48×48 | RGBA | 1889 | 171 | 418 | 1,1–47,47 | 1,1,1,1 | Cuerpo fantasma frame 2 | Recolorear 4 colores, ojos, 32×32 |
| 9 | `grapes.png` | 32×32 | P+tRNS | 552 | 124 | 257 | 0,0–32,32 | 0,0,0,0 | Fruta 5 (1000) | Fruta directa, 32×32 |
| 10 | `key.png` | 48×48 | RGBA | 1167 | 147 | 498 | 0,0–48,48 | 0,0,0,0 | Fruta 8 (5000) | **No convertido**: procedencia de la llave decorativa (sprite procedural) |
| 11 | `Key-icon.png` | 48×48 | RGBA | 700 | 97 | 416 | 5,4–44,42 | 5,4,4,6 | **No** | **Excluido** del build |
| 12 | `peach.png` | 32×32 | P+tRNS | 689 | 84 | 123 | 2,0–30,32 | 2,0,2,0 | Fruta 3 (500) | Fruta directa, 32×32 |
| 13 | `retroghost1.png` | 48×48 | RGBA | 1760 | 21 | 650 | 0,0–48,48 | 0,0,0,0 | **No** | Skin "Retro" (frame 1), 32×32 |
| 14 | `retroghost2.png` | 48×48 | RGBA | 1754 | 20 | 608 | 0,0–48,48 | 0,0,0,0 | **No** | Skin "Retro" (frame 2), 32×32 |
| 15 | `strawberry.png` | 32×32 | P+tRNS | 571 | 92 | 150 | 4,0–28,32 | 4,0,4,0 | Fruta 2 (300) | Fruta directa, 32×32 |

**Nota de integración final:** de estas 15 PNG se convierten **7**: las 5 frutas
activas (`cherry`, `strawberry`, `peach`, `apple`, `grapes`) y los 2 cuerpos de
fantasma (`ghost1`, `ghost2`). Ademas se copia `key.png` solo como procedencia de
la llave decorativa del indicador NIVEL (el sprite de la llave es procedural, no
se convierte). Las frutas del arcade restantes y el icono de UI quedan excluidos
del build (ver §5.2 y §12).

Hoja de contactos con fondo de damero: `/tmp/audit_png_sheet.png`.

### 2.2 Lectura por grupos

**Frutas (8 en `Res/`; 5 activas).** Estilo glossy/vectorial, no pixel-art. Seis vienen en 32×32
(5 son PNG indexados con `tRNS`, es decir alfa indexada suave) y tres en 48×48
(`bell`, `cherry`, `key`) por haber pasado por otras herramientas. Tienen margen
transparente interno variable (0–4 px) y no están centradas exactamente; el
pipeline debe **recortar a la caja de tinta y centrar en el lienzo destino**
(no reescalar por separado borde y contenido).

**Fantasmas (2).** 48×48, cuerpo naranja con sombreado propio, **sin ojos** y
con alfa suave (bordes antialiasados). Su silueta coincide con el fantasma
arcade clásico (domo + falda de 3 ondas), y `ghost1`/`ghost2` solo difieren en
la fase de la falda. Son **máscaras/tintes base**, no sprites finales.

**Fantasmas retro (2).** 48×48, plano/naranja, sin sombreado, con falda de 3
pies pixelada y "colores" limitados. Estilo **pixel-art plano**. Encajan como
skin alternativa del modo Retro (Paku-Paku ya tiene un toggle `Classic`).

**`Clydeeghost.png`.** 242×238, PNG indexado de **4 colores**, **sin alfa**
(fondo blanco opaco) y borde pixelado irregular. Es Clyde a gran tamaño (arte
pixel upscaleado). No tiene uso en Paku-Paku; sí es buen arte de menú/attract o
de la pantalla "Acerca de", previo *key-out* del blanco y reducción.

**`dead.png`.** 48×48, estallido/estrella amarilla con centro negro (frame de
muerte tipo arcade). No usado por Paku-Paku (allí la muerte es vectorial con
arcos y partículas). Opcional como efecto de muerte final.

**`Key-icon.png`.** 48×48 con alfa real, llave dorada "glossy" con mucho margen
(5,4,4,6). Candidata a icono de UI (récords/ayuda); su estilo no casa con la
iconografía lineal del rediseño SereOS, pero puede convivir dentro de la
pantalla arcade.

**Inconsistencia artística.** Conviven 4 estilos: vector glossy (frutas,
`Key-icon`), 3D suave (`ghost1/2`), pixel-art plano (`retroghost*`,
`Clydeeghost`) y vector plano (`dead`). La versión definitiva debe **elegir uno
por skin** (Classic vs Retro) y no mezclarlos en la misma pantalla sin criterio.

### 2.3 Transparencia y canal alfa

- 5 PNG son modo `P` con `tRNS` (alfa **suave** indexada); el resto `RGBA`
  directo. Ninguno usa *color key* puro: el fondo es alfa=0 real.
- El formato del juego (`assets/sprites.h`) es **RGB565 con clave 1 bit
  `0xF81F`**: no puede representar alfa suave. Opciones:
  - **A — compatible (ya prototipada):** downscale LANCZOS + umbral de alfa 128
    + contorno oscuro de 1 px en píxeles transparentes adyacentes. Resuelve
    legibilidad sobre el laberinto oscuro, pero endurece bordes.
  - **B — calidad (recomendada):** añadir una **máscara de cobertura 8bpp** al
    sprite (`RGB565 + uint8_t coverage[]`) y dibujar con `gfx_blit_alpha8`
    (SereOS ya la tiene) / textura con alfa en SDL. Coste +1 KiB/sprite a 32×32.
  - **C — precomponer sobre el fondo** del laberinto: descartada, porque el
    mismo sprite se ve sobre celdas distintas y sobre el panel de pausa.
- El contorno oscuro actual (`#182236`) es un recurso del proyecto original;
  con la opción B puede rebajarse o eliminarse para un look más fiel.

### 2.4 Prototipos PNG y métricas

Generados para `ghost1`, `cherry`, `key`, `dead` a **16×16 y 32×32**:

- `/tmp/res_proto/png/compare_16_32.png` — original vs RGB565 16 y 32 (damero).
- `/tmp/res_proto/png/ghost_recolor.png` — recolor 4 colores + ojos (ver §2.5).
- `/tmp/res_proto/png/*_16.png`, `*_32.png` — sprites con clave `0xF81F` y contorno.
- `/tmp/res_audit/png_analysis.json`, `png_metrics.json`.

Calidad (MSE/PSNR del RGB565+clave frente a la referencia con alfa compuesta):

| Sprite | 16×16 | 32×32 | Mejora |
|---|---|---|---|
| `ghost1` | 14,9 dB | **21,1 dB** | +6,2 dB |
| `cherry` | 18,5 dB | **21,5 dB** | +3,0 dB |
| `key` | 13,0 dB | **17,2 dB** | +4,2 dB |
| `dead` | 6,1 dB | **8,3 dB** | +2,2 dB |

Los valores absolutos bajos de `dead`/`key` se deben a que la referencia
conserva alfa suave y el prototipo usa clave 1 bit (pérdida de bordes finos,
rayos y dientes). Aun así, la comparación relativa confirma que **32×32 es
claramente mejor** y que `dead.png` necesitará tratamiento especial (o quedarse
en 48×48 escalado, o usarse solo como ráfaga final).

### 2.5 Reconstrucción de fantasmas (recolor + ojos)

Paku-Paku no usa el naranja directamente:

1. `CreateColouredGhost(Colour, "Ghost1")`: pinta el color con `CAIRO_OPERATOR_ATOP`,
   luego un degradado lineal blanco→color→negro (paradas gaussianas 0,3/0/0,3,
   alfa 0,30) y una capa de brillo `DEST_OVER`.
2. `CreateEyeOverlay`: dos elipses blancas (centros 16,22 y 32,22; radios 14×16;
   trazo negro al 60 %) y dos pupilas azules (r=9) desplazadas ±3 según la
   dirección de la mirada. `HuntedEyes` lleva las pupilas "fuera de límites"
   (sin pupila visible).
3. `cGhost.Sprite(Flash)`: elige `HuntedGhost`, `FlashingGhost` o el cuerpo
   normal; superpone `Eyes<dirección>` salvo en modo asustado.

**Prototipo `/tmp/res_proto/png/ghost_recolor.png`:** cuerpo `ghost1` recoloreado
a rojo/rosa/cian/naranja + ojos con elipse blanca y pupila azul, a 48 y 32 px.
La silueta y el sombreado se conservan; los ojos requieren un ajuste fino
(geometría/tamaño) comparando con el juego real antes de fijar el pipeline.
Variantes asustado/parpadeo en `/tmp/res_proto/png/ghost1_fright_32.png`,
`ghost1_flash_32.png`.

**Plan de pre-cocinado (todo en build):**

| Grupo | Frames | Bytes aprox. (32×32 RGB565) |
|---|---|---:|
| Cuerpo fantasma 4 colores × 2 falda | 8 | 16 KiB |
| Ojos por dirección (4) | 4 | 8 KiB (o 4 KiB si máscara) |
| Asustado 2 frames + parpadeo 2 | 4 | 8 KiB |
| Ojos solos (volviendo a casa) 4 direcciones | 4 | 8 KiB |
| **Total fantasmas** | **20** | **≈40 KiB** |

Alternativa (opción B): cuerpos + máscaras de ojos como overlay alfa; baja el
coste de datos pero exige compositing por capas en el render (que ya existe).

---

## 3. WAV — inventario, análisis y conversión

### 3.1 Tabla de inventario (11)

`pk` = pico (amplitud 0..127 en 8 bits sin signo; dBFS aprox.), `L/R` = diferencia
media entre canales (0 = idénticos). Duración y tamaño reales del archivo.

| # | Archivo | ch | bits | Hz | Duración | Tamaño | pk (dBFS) | L/R | Uso Paku-Paku | Tipo |
|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| 1 | `eat fruit.wav` | 1 | 8 | 11025 | 0,439 s | 5.120 B | 124 (−0,3) | — | EatFruit (one-shot) | one-shot |
| 2 | `eat ghost.wav` | 1 | 8 | 11025 | 0,574 s | 6.408 B | 125 (−0,2) | — | EatGhost (one-shot) | one-shot |
| 3 | `extra life.wav` | 1 | 8 | 11025 | 1,899 s | 21.248 B | 120 (−0,6) | — | ExtraLife (one-shot) | one-shot |
| 4 | `game start.wav` | 2 | 8 | 48000 | 4,378 s | 420.408 B | 79 (−4,2) | 0,00 | GameStart (nivel 1) | one-shot |
| 5 | `ghost respawn.wav` | 2 | 8 | 48000 | 0,545 s | 52.390 B | 26 (−13,8) | 0,00 | GhostRespawn (bucle hasta ambient) | loop |
| 6 | `hunted siren.wav` | 2 | 8 | 48000 | 1,181 s | 113.494 B | 16 (−18,1) | 0,00 | HuntedSiren (asustado) | loop |
| 7 | `hunter siren.wav` | 2 | 8 | 48000 | 2,404 s | 230.902 B | 30 (−12,6) | 0,00 | HunterSiren (persecución) | loop |
| 8 | `intermission.wav` | 1 | 8 | 11025 | 5,204 s | 57.600 B | 125 (−0,2) | — | **no usado** | one-shot |
| 9 | `pacman death.wav` | 1 | 8 | 11025 | 1,534 s | 17.008 B | 119 (−0,6) | — | PacmanDeath | one-shot |
| 10 | `waka1.wav` | 2 | **16** | 48000 | 0,085 s | 16.320 B | 8159 (−12,1) | 0,00 | EatDot (alterna) | one-shot |
| 11 | `waka2.wav` | 2 | **16** | 48000 | 0,084 s | 16.256 B | 8159 (−12,1) | 0,00 | EatDot (alterna) | one-shot |

Notas:

- No hay chunk `smpl`/`cue` con puntos de bucle en ningún WAV; los RIFF contienen
  solo `fmt `, `data`, y en algunos `LIST/INFO`, `fact`, `SAUR`.
- Los 6 archivos a 48 kHz estéreo tienen **canales idénticos** (diferencia media
  0,00), así que el downmix es trivial (basta un canal).
- Las sirenas y `ghost respawn` son muy silenciosas (−12…−18 dBFS) porque
  originalmente se reproducían con **volumen/frecuencia dinámicos** de DirectSound;
  hay que normalizarlas en la conversión.
- `waka1/2` son los únicos 16 bits; el resto ya es PCM 8 bits sin signo.

### 3.2 Formato destino

**PCM 8 bits sin signo, mono, 11025 Hz** (128 = silencio), igual que
`audio/sfx_data.h` de SereOS y compatible con:

- **SereOS SB16** (`drivers/sb16.h`): PCM 8 bits sin signo mono, rate
  4000–44100, bloque ≤ 32.768 B y sin cruzar frontera de 64 KiB (la capa
  `audio/audio.c` usa *bounce buffer* alineado).
- **Linux/SDL**: abrir `AUDIO_U8` mono 11025 (SDL convierte al dispositivo);
  el backend actual usa `AUDIO_S16SYS` 22050 con síntesis, habrá que cambiarlo
  al reproductor de clips compartido.

Se descarta 22050 Hz para no duplicar tamaño ni complicar el SB16; 11025 Hz
conserva de sobra el ancho de banda de estos SFX (la referencia de calidad se
mide con corte a 4,8 kHz).

### 3.3 Pipeline de conversión

1. Leer WAV con `wave` (soporta PCM 8/16 y estéreo).
2. Downmix: si estéreo, `(L+R)/2` (aquí L≡R) → mono.
3. Anti-alias + remuestreo a 11025 con **sinc ventaneada** (Hamming, 49 taps,
   corte 0,45·11025 ≈ 4,96 kHz). Para los ya nativos a 11025 no se remuestrea.
4. Recorte de silencio (< −55 dBFS) dejando 2 ms de margen.
5. **Normalización** de pico a 0,92 (−0,7 dBFS) para compensar las sirenas
   silenciosas; el resto se normaliza igual para nivelar la mezcla.
6. Cuantización a 8 bits sin signo (`clip(round(x·127+128))`).
7. Bucles: detectar el periodo natural por autocorrelación FFT sobre el tramo
   final, elegir el inicio con menor error de empalme y recortar a un periodo.
   Si el salto de wrap supera 2 LSB, aplicar *crossfade* de 5 ms.
8. Validar: `len ≤ 32768` (SB16) o marcar para reproducción por trozos; DC
   < ±2 LSB; sin clipping (pico ≤ 250); duración > 20 ms.
9. Emitir arrays `const uint8_t[]` + tabla `sfx_clip_t {data, length, rate,
   loopable}` (idéntica a `audio/sfx_data.h`) y previsualizaciones WAV.

### 3.4 Prototipos y métricas

Prototipos en `/tmp/res_proto/wav/` (`*.wav` 8-bit mono 11025 y `*.u8` crudos),
datos en `/tmp/res_audit/wav_proto.json`.

| Clip destino | Frames | Duración | Bytes | SB16 | SNR vs ref. 4,8 kHz | Loop |
|---|---:|---:|---:|---|---:|---|
| `sfx_eat_fruit` | 4.845 | 0,439 s | 4.845 | OK | nativo | — |
| `sfx_eat_ghost` | 6.324 | 0,574 s | 6.324 | OK | nativo | — |
| `sfx_extra_life` | 20.940 | 1,899 s | 20.940 | OK | nativo | — |
| `sfx_game_start` | 48.272 | 4,378 s | 48.272 | **2 trozos** | 40,1 dB | — |
| `sfx_ghost_respawn` | 2.935 | 0,266 s | 2.935 | OK | 38,0 dB | periodo 2.935 (0,266 s), seam 22,8 LSB → crossfade |
| `sfx_siren_hunted` | 4.412 | 0,400 s | 4.412 | OK | 43,9 dB | periodo 4.412 (0,400 s), seam 4,0 LSB → limpio |
| `sfx_siren_hunter` | 1.470 | 0,133 s | 1.470 | OK | 29,0 dB | periodo 1.470 (0,133 s), seam 27 LSB → crossfade o bucle completo |
| `sfx_intermission` | 57.377 | 5,204 s | 57.377 | **2 trozos** | nativo | — |
| `sfx_death` | 16.916 | 1,534 s | 16.916 | OK | nativo | — |
| `sfx_waka1` | 932 | 0,085 s | 932 | OK | 32,0 dB | — |
| `sfx_waka2` | 929 | 0,084 s | 929 | OK | 32,0 dB | — |

**Total PCM: ≈ 165.200 B (161 KiB)**, frente a 111.133 B (14 clips sintetizados)
actuales. La cuantización 16→8 bits de `waka` mide 38,4 dB de SNR (coherente con
una señal a −12 dBFS); el remuestreo 48→11 kHz da 29–44 dB frente a la referencia
ideal, suficiente para efectos arcade.

### 3.5 Limitaciones específicas de audio

- **Bloques largos:** `game start` (48.272) e `intermission` (57.377) superan
  `SB16_MAX_BUFFER = 32768`. Opciones: (a) ampliar `audio.c` con reproducción
  encadenada por trozos (recomendado, 2 trozos por clip), (b) recortar el clip
  (empeora), (c) bajar la tasa (pierde brillo). La misma cola sirve para Linux.
- **Modulación de sirena:** Paku-Paku sube la frecuencia de `hunted siren` un
  0/10/20/30 % según dots restantes (`SetSirenFrequency`). Con PCM fijo en SB16
  hay que **pre-cocinar 4 variantes por sirena** remuestreando el bucle
  (0,4 s · 4 ≈ 16 KiB para la asustada; 0,133 s · 4 ≈ 6 KiB la de caza) y elegir
  variante en el juego, o aceptar perder la modulación.
- **Faltan sonidos propios:** menú, power-up, game over y level-clear no tienen
  clip en `Res/`. Propuesta híbrida: conservar los sintetizados actuales
  (`audio/sfx_data.c`) para menú/power/game-over, usar `intermission` para
  level-clear y `ghost respawn` como bucle de "ojos volviendo".
- **`intermission.wav` no lo usa Paku-Paku**, pero encaja en "nivel completado"
  (5,2 s) o pantalla de intermedio; requiere troceado.
- **Licencia:** los WAV son casi con certeza material arcade (Namco) o
  recreaciones; no hay licencia. Ver §6.

---

## 4. TTF — metadatos, cobertura y atlas propuesto

### 4.1 Metadatos y licencia

| Archivo | Familia | Copyright | Versión | Licencia embebida | ¿Usado por Paku-Paku? |
|---|---|---|---|---|---|
| `prstartk.ttf` | **Press Start K** | © 2001-2 **codeman38** (Cody Boisclair) | 1.01 | **No hay campo de licencia**; solo URL de herramienta (high-logic.com) | **Sí** (`InstallFont "prstartk"`) |
| `atari full.ttf` | Atari Font Full Version | **Genshichi Yasui** | 1.2 | **No hay campo de licencia** | No |

Investigación externa (no vinculante, citada como referencia): Press Start K es
una fuente pixel de **2001** de Cody Boisclair ([Zone38/codeman38 en Devroye](https://luc.devroye.org/fonts-70942.html));
la familia *Press Start 2P* (2003) **sí** está publicada con **OFL** en
[Google Fonts](https://fonts.google.com/specimen/Press+Start+2P/license), pero es
**otra fuente**. `atari full.ttf` no declara licencia y además usa la marca
"Atari" (riesgo de marca registrada).

**Conclusión:** no se puede afirmar una licencia permisiva para `prstartk.ttf`
ni para `atari full.ttf`. Opciones:

1. Atribuir "Press Start K © 2001-2002 codeman38" y usar el atlas **solo en
   builds privados/académicos** (coherente con el uso del resto de `Res/`).
2. Sustituir por **Press Start 2P (SIL OFL 1.1)** — misma estética, licencia
   verificable — si el juego se publica.
3. **`atari full.ttf`: no incluir** en la versión definitiva (sin licencia +
   marca + sin Latin-1). Como mucho, uso local opcional.

### 4.2 Cobertura y métricas

| Fuente | Tamaños | Glifos 32..255 | ASCII 33..126 | Latin-1 (ñ/Ñ/á/é/í/ó/ú/ü/¿/¡) | Monoespaciada | Avance |
|---|---:|---:|---|---|---|---|
| Press Start K | 8/16/24 px | 174 | **completo** | **completo** | **sí** (avance = tamaño exacto) | 8/16/24 px |
| Atari Full | 8/16/24 px | **93** (solo ASCII) | falta `\` | **no tiene** | no (mitades de ancho) | ~tamaño, variable |

- Press Start K: `line_height = tamaño` (8/16/24), `ascent = tamaño−1`, render
  nítido en múltiplos enteros. Faltan solo signos Latin-1 secundarios
  (`§ ¨ ª ¬ SHY ¯ ² ³ ´ µ ¶ · ¸ ¹ º ¼ ½ ¾ ...`); **ñ, Ñ, á, é, í, ó, ú, ü, ¿, ¡
  sí existen**, que es lo que necesita la UI en español.
- Atari Full: no sirve para texto en español; solo cifras/HUD ASCII, y con
  riesgo legal. Descartada.

### 4.3 Atlas bitmap propuesto (8/16/24)

Prototipo en `/tmp/res_proto/ttf/prstartk_{8,16,24}.png` y
`/tmp/res_audit/ttf_proto.json`. Rasterizado con Pillow (FreeType) a tamaño
exacto, recorte a caja de tinta, `bearing_x/bearing_y` y avance.

| Tamaño | Glifos | Bytes de máscara (Latin-1) | Bytes ASCII-only | Niveles de gris |
|---|---:|---:|---:|---|
| 8 px | 174 | 6.827 B | ≈2,6 KiB | 5 (antialias leve) |
| 16 px | 174 | 27.268 B | ≈10,1 KiB | 4 |
| 24 px | 174 | 61.323 B | ≈22,5 KiB | 5 |

Para el look arcade conviene **binarizar** (cobertura > 50 % → 1bpp) o usar una
máscara de cobertura 8bpp como en el motor `text_*` de SereOS. Con los 3 tamaños
se cubren HUD (8/16), títulos (24) y escalado entero sin pérdida (16→32 no
recomendado para pixel-font: escalar por vecino más cercano a 2× sí es válido).
Fallback: si falta un carácter, usar la tipografía Inter ya incluida.

---

## 5. Assets actuales de `PAC-MAN SereOS/` y comparación

### 5.1 Formato y contenido actual

- `assets/sprites.h` (contrato): 16×16, `uint16_t` RGB565, transparente
  `0xF81F`, 35 sprites con contorno oscuro `#182236` y arte **original**.
- `assets/sprites.c`: 8.704 valores (`≈17,0 KiB` opacos incluyendo
  transparencia); generado por `tools/gen_pacman_assets.py` (≈40 KiB, Python
  puro determinista), con validaciones (transparencia solo exterior, contorno,
  frames distintos, nombres).
- Contenido: `pacman_frame[4][3]` (12), `ghost_frame[4][2]` (8),
  `ghost_fright_frame[2]`, `ghost_flash_frame[2]`, `ghost_eyes_frame[4]`,
  `fruit_sprite[5]` (CEREZA, FRESA, NARANJA, MANZANA, UVAS), `life_sprite`,
  `key_sprite` (llave decorativa del indicador NIVEL, no fruta) y `fruit_name[5]`.
- `assets/fonts/text_data.c` (1,24 MB fuente, 9 estilos Inter/JetBrains Mono,
  OFL) — es la tipografía del rediseño SereOS, no fuente arcade.
- `assets/preview.png` (1260×1000), `docs/captures/*.png` (7 capturas 1024×768),
  generador de sprites y de fuentes.
- Integración: `build/sereos/libpacman.a` se enlaza en
  `sistema operativo/Makefile` (`GAME_LIB`); el backend SereOS (`game_app.c`)
  usa `pac_game_*` y `pac_platform_*`; audio del núcleo en `audio/audio.c`
  (SFX sintetizados propios, 11025 Hz u8) y SDL sintetizado en Linux.

### 5.2 Mapa: elemento del juego → recurso `Res/` → acción

| Elemento del juego | Recurso `Res/` | Estado actual (SereOS) | Acción propuesta |
|---|---|---|---|
| Pac-Man (4 dir × 3 bocas) | **ninguno** (Paku-Paku vectorial) | sprites propios 16×16 | Mantener/generar 32×32 con la geometría de `cPacMan.cls` (arco r=22) |
| Muerte de Pac-Man | `dead.png` (no usado) | sprites/secuencia propia | Opcional como ráfaga final; secuencia se queda procedural |
| Fantasmas Blinky/Pinky/Inky/Clyde ×2 frames | `ghost1/2.png` | sprites propios 4 colores | Recolorear `ghost1/2` a 4 colores, pre-cocinar 32×32 (§2.5) |
| Ojos por dirección | procedural en Paku-Paku | `ghost_eyes_frame[4]` propio | Pre-cocinar 4 overlays desde la geometría de `CreateEyeOverlay` y ajustarlos |
| Asustado / parpadeo | derivados | 2+2 frames propios | Derivar del cuerpo recoloreado (azul/blanco) y ojos "hunted" |
| Ojos sin cuerpo (vuelta a casa) | derivados | `ghost_eyes_frame[4]` propio | Regenerar a 32×32 |
| Fruta 1 CEREZA (100) | `cherry.png` (48) | `pacasset_fruit_sprite_res[0]` | **Integrada** |
| Fruta 2 FRESA (300) | `strawberry.png` (32) | `pacasset_fruit_sprite_res[1]` | **Integrada** |
| Fruta 3 NARANJA (500) | `peach.png` (32) | `pacasset_fruit_sprite_res[2]` | **Integrada** |
| Fruta 4 MANZANA (700) | `apple.png` (32) | `pacasset_fruit_sprite_res[3]` | **Integrada** |
| Fruta 5 UVAS (1000) | `grapes.png` (32) | `pacasset_fruit_sprite_res[4]` | **Integrada** |
| Frutas 6-8 del arcade (2000/3000/5000) | sin PNG activo | **excluidas** | No integradas: el juego usa 5 frutas |
| Vida extra | ninguno | `life_sprite` propia | Derivar de un frame de Pac-Man |
| Llave decorativa (icono NIVEL) | `key.png` (solo procedencia) | `pacasset_key_sprite` procedural | **Integrada** como adorno del HUD, no como fruta |
| Skin retro de fantasmas | `retroghost1/2.png` (no usados) | no existe | Nuevo modo visual "Retro" (opcional) |
| Arte de menú/attract | `Clydeeghost.png` (no usado) | panel UI tipográfico | Fondo/mascota del menú (quitar blanco, reducir) |
| Fuente arcade (HUD, títulos) | `prstartk.ttf` | Inter/JetBrains Mono | Atlas 8/16/24 de Press Start K (atribución; validar licencia) |
| Sonido start / waka / comer / muerte / vida / sirena / respawn | 10 WAV | 14 SFX sintetizados propios | Convertir a PCM u8 11025; tabla nueva; fallback |
| Intermedio / nivel completado | `intermission.wav` (no usado en Paku-Paku) | sintetizado | Usar para nivel completado (troceado) |
| Menú, power-up, game over | **sin recurso** | sintetizados | Mantener sintetizados o derivar (`intermission`) |

### 5.3 Qué se puede sustituir directamente

- **Frutas:** sí, índice a índice para las 5 frutas activas (CEREZA, FRESA,
  NARANJA, MANZANA, UVAS) con el ciclo `(nivel-1) % 5` y valores
  100/300/500/700/1000; el cambio es de **assets y nombres**, no de lógica.
- **Fantasmas:** sí, pero con reconstrucción (recolor + ojos), no copiando el PNG.
- **Fuente arcade:** sí, añadiendo atlas nuevo; la UI general sigue con Inter.
- **SFX:** sí, reemplazando la tabla de clips y mapeando eventos existentes.

### 5.4 Qué falta y riesgos de contrato

- **No hay sprite de Pac-Man ni arte del laberinto** en `Res/`; el laberinto debe
  seguir siendo procedural y Pac-Man generado (o mantener los actuales).
- **No hay frames de asustado/parpadeo/ojos**; se derivan.
- **El contrato `sprites.h` (16×16) es congelado.** Usar 32×32 implica:
  - cambiar `PAC_SPRITE_SIZE`/tamaños de arrays y que `game_render` dibuje
    32×32 centrado en el tile de 16 (como el arcade dibuja 48 sobre 24);
  - revisar colisiones/HUD (los sprites 2× tile se solapan con paredes vecinas,
    igual que en el original, pero hay que verlo en capturas);
  - actualizar `tools/gen_pacman_assets.py` y las validaciones (`sizeof`,
    transparencia, contorno).
  Alternativa conservadora: mantener 16×16 para Fase 2 y usar el pipeline a 32
  solo si `game-dev`/Lead aceptan el cambio de contrato. La auditoría **recomienda
  32×32**, con 16×16 como plan B.
- **Memoria estimada** de assets nuevos a 32×32: fantasmas ≈40 KiB, frutas
  16 KiB, Pac-Man ≈32 KiB (16 frames), muerte ≈16 KiB, fuente arcade 7–61 KiB
  según tamaños, audio ≈161 KiB. Total **≈270–330 KiB** de `const` en
  `.rodata`, aceptable para el kernel actual (ya lleva ~204 KiB de `text_data` y
  174 KiB de fuentes del escritorio), pero debe confirmarse con QA en QEMU
  (256 MiB).
- **Estilos mezclados:** no usar glossy + pixel-art en la misma pantalla sin una
  skin coherente.
- **Regresión funcional:** cualquier cambio de assets debe re-ejecutar el
  arnés `tests/` y las capturas de `docs/captures/`.

---

## 6. Licencias y atribución (importante)

### 6.1 PNG y WAV

- **No hay licencia, autoría ni atribución** en `Res/`; los WAV incluyen fechas
  1994/1996 y herramientas de edición, y los PNG/Pixel-art reproducen elementos
  reconocibles de **Pac-Man** (personajes, frutas, sonidos). Esto es material de
  terceros/arcade, **no arte original del proyecto**.
- Consecuencias:
  1. La afirmación actual de `assets/README.md` ("todo el arte es original") y
     del `README.md` del juego **dejará de ser cierta** si se embeben estos
     recursos: hay que actualizar la documentación y atribuir la procedencia
     ("recursos proporcionados para el proyecto; derechos de sus autores").
  2. Para un trabajo académico privado el riesgo es bajo, pero **no se deben
     publicar** los PNG/WAV originales ni un ISO con ellos sin permiso.
  3. Recomendación: no commitear `Res/`; generar arrays C derivados solo en
     builds locales con `PACMAN_USE_RES_ASSETS=1` (o empaquetar el ISO final como
     entrega privada), y mantener el arte propio actual como *fallback* público.
- Si el usuario confirma autoría/permiso, documentarlo con una nota de licencia
  (autor, origen, fecha) en `assets/` y en este directorio.

### 6.2 TTF

- `prstartk.ttf`: © 2001-2002 codeman38; **sin licencia verificable en el
  archivo**. Atribuir siempre; validar términos con el autor/fuente o sustituir
  por *Press Start 2P* (OFL).
- `atari full.ttf`: sin licencia + marca "Atari"; **no distribuir**; excluir de
  la versión definitiva salvo confirmación explícita.
- Los atlas rasterizados son obras derivadas: si se usan, mantener el aviso de
  copyright del autor correspondiente junto a los datos generados.

---

## 7. Pipeline de conversión propuesto (reproducible, aún NO integrado)

Herramienta nueva propuesta: `tools/gen_pacman_res_assets.py` (Python bundled
con Pillow + NumPy; determinista). Entrada: `--res /home/t1an/Descargas/Res`.
Salidas (a integrar en Fase 2):

```
assets/res/sprites_res.c   assets/res/sprites_res.h   (RGB565 [± máscara alfa])
assets/res/sfx_res.c       assets/res/sfx_res.h       (PCM u8 11025 + tabla)
assets/res/font_res.c      assets/res/font_res.h      (atlas Press Start K 8/16/24)
assets/res/preview_res.png                            (hoja de validación)
assets/res/audit_res.json                             (métricas y avisos)
```

Pasos del generador:

1. **Sprites** (32×32 y 16×16; elegir con `--sprite-size`):
   - frutas: recortar tinta, centrar, LANCZOS a 32, umbral alfa 128 o máscara
     8bpp, generar `rgb565` con `0xF81F` en transparente;
   - fantasmas: recolor 4 colores replicando `CreateColouredGhost`, ojos por
     dirección replicando `CreateEyeOverlay`, variantes frightened/flash, ojos
     solos; salida por frames;
   - Pac-Man: generar arcos (r=22 sobre lienzo 48, centrado) para 4 direcciones
     × 4 bocas + muerte (12 frames + partículas) — misma geometría que
     `cPacMan.cls`;
   - `dead.png`: opcional como ráfaga final;
   - `Clydeeghost.png`: key-out del blanco + recorte + reducción para menú
     (p. ej. 160×160) con máscara alfa;
   - `Key-icon.png`: 24×24/32×32 para icono de UI;
   - `retroghost1/2.png`: frames del skin Retro.
2. **SFX**: paso §3.3 para los 11 WAV; nombres `sfx_*`; tabla con `rate` y
   `loopable`; variantes de sirena +0/10/20/30 %; validación SB16 y troceado.
3. **Fuente**: rasterizar `prstartk.ttf` a 8/16/24 (Pillow), recortar glifos,
   cobertura 8bpp o binarizada, fallback a `?`/Inter, validar cobertura Latin-1
   requerida (ñ/Ñ/á/é/í/ó/ú/¿/¡) y saltar el resto.
4. **Validación automática** (falla con código ≠ 0): dimensiones exactas, clave
   `0xF81F` solo en exterior, sprites no vacíos, frames distintos, pico PCM ≤
   250, DC < ±2, duración > 20 ms, loop seam < 2 LSB (o crossfade aplicado),
   glifos requeridos con tinta.
5. **Determinismo**: mismo Python/Pillow/fuentes → mismos bytes; imprimir hashes.

Comandos de la Fase 1 (evidencias ya generadas):

```bash
PY=~/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
$PY /tmp/audit_png.py                    # inventario PNG -> /tmp
$PY /tmp/png_proto.py                    # prototipos RGB565 16/32
$PY /tmp/sprite_compare.py               # hoja original vs 16 vs 32
$PY /tmp/ghost_proto.py                  # recolor + ojos (4 colores)
$PY /tmp/wav_proto3.py                   # WAV -> PCM u8 11025 + loops + SNR
$PY /tmp/ttf_proto.py                    # atlas Press Start K/Atari 8/16/24
```

Integración propuesta en Fase 2: `assets/res/*` como tablas alternativas
seleccionadas por `#ifdef PACMAN_USE_RES_ASSETS`; `pac_sprite`/`pac_sprite_alpha`
para 32×32; `pac_audio_*` leyendo la tabla Res; `pac_text` con estilo arcade;
flag de build en el Makefile del componente (sin tocar el Makefile del OS). El
arte actual queda como fallback y para tests de regresión.

---

## 8. Plan Fase 2 propuesto (no ejecutado)

| # | Tarea | Responsable sugerido |
|---|---|---|
| 1 | Decidir licencia/uso: privado vs sustitución OFL; decidir commitear o no `Res/` | Lead/usuario |
| 2 | Implementar `tools/gen_pacman_res_assets.py` + validaciones + preview | `gfx-core` (con revisión de `game-dev`) |
| 3 | Ajustar contrato de sprites (32×32 o 16×16+máscara) y `pac_sprite`/render | `game-dev` |
| 4 | Recolor de fantasmas + ojos (pre-cocinado) y modo Retro | `gfx-core`/`game-dev` |
| 5 | Frutas Res por índice + nombres (CEREZA/FRESA/NARANJA/MANZANA/UVAS) | `game-dev` |
| 6 | Tabla PCM Res + troceado en `audio.c` + variantes de sirena | `kernel-sys`/`game-dev` |
| 7 | Atlas Press Start K + estilo de texto arcade y fallback Inter | `gfx-core` |
| 8 | Menú con `Clydeeghost` y `Key-icon`; actualizar `dead` | `game-dev`/`apps-ui` |
| 9 | Actualizar `README`, `assets/README.md`, `docs/GAME.md`, licencias | `game-dev`/`qa-verify` |
| 10 | Capturas 1024×768 / 1280×1024 / 800×600 y regresión `tests/` | `qa-verify` |

---

## 9. Limitaciones y riesgos técnicos

1. **Licencias** (lo más importante): sin licencia en `Res/`; riesgo de derechos
   de Pac-Man/Namco y de marca "Atari".
2. **Falta Pac-Man y el laberinto** en `Res/`; se mantiene generación procedural.
3. **Alfa suave vs clave 1 bit**: pérdida de calidad si no se adopta máscara
   alfa (§2.3); `dead` y `key` son los más sensibles.
4. **Downscale 48→32** (frutas de 48 px y fantasmas): pérdida de detalle;
   se mitiga con LANCZOS y, si se adopta, máscara alfa.
5. **Ojos/estilo de fantasmas**: la geometría de ojos de Paku-Paku es una
   aproximación de la clásica; hay que ajustarla con capturas reales.
6. **Audio 11025 Hz**: techo de agudos ~5 kHz; suficiente para SFX arcade.
   Los clips largos necesitan troceado y las sirenas, variantes pre-cocinadas.
7. **SB16**: bloque ≤ 32 KiB, sin cruzar 64 KiB, PCM u8 mono; ya soportado por
   `audio.c` (bounce buffer), solo falta el troceado de 2 clips.
8. **Contrato congelado** de sprites/16×16: el cambio a 32×32 toca render,
   validaciones y tamaño de ventana; coordinar con `game-dev` y QA.
9. **Memoria**: +270–330 KiB de `.rodata` con lo propuesto; verificar en QEMU
   (el kernel ya soporta fuentes de escritorio de ~174 KiB).
10. **Inconsistencia artística** entre grupos de PNG: elegir skins y no mezclar.
11. **Reproducibilidad**: el generador depende de Pillow/FreeType y de las
    fuentes del host; documentar versiones y fijar los datos derivados en el
    repo (C) para builds sin host.

---

## 10. Evidencias en `/tmp` (Fase 1)

| Evidencia | Contenido |
|---|---|
| `/tmp/audit_png_sheet.png` | Hoja de contactos de los 15 PNG sobre damero |
| `/tmp/res_proto/png/compare_16_32.png` | Original 48 vs RGB565 16 y 32 de ghost1/cherry/key/dead |
| `/tmp/res_proto/png/ghost_recolor.png` | Recolor 4 colores + ojos (48 y 32) |
| `/tmp/res_proto/png/ghost1_fright_32.png`, `ghost1_flash_32.png` | Variantes asustado/parpadeo |
| `/tmp/res_proto/png/*_16.png`, `*_32.png` | Sprites RGB565 con clave `0xF81F` |
| `/tmp/res_proto/wav/*.wav`, `*.u8` | Conversiones PCM u8 mono 11025 (11 clips + waka2) |
| `/tmp/res_proto/ttf/prstartk_{8,16,24}.png`, `atari_*` | Previews de fuente |
| `/tmp/res_audit/png_analysis.json` | Inventario PNG (tamaños, bbox, alfa) |
| `/tmp/res_audit/png_metrics.json` | MSE/PSNR de los prototipos 16 vs 32 |
| `/tmp/res_audit/wav_proto.json` | Formato, duración, frames, SNR, loops |
| `/tmp/res_audit/ttf_proto.json` | Glifos, atlas, cobertura, métricas |

---

## 11. Decisiones pendientes (para Lead/usuario)

1. **Licencia:** ¿la entrega definitiva es privada/académica (se pueden embeber
   los recursos con atribución) o pública (hay que sustituir PNG/WAV y fuente
   por material propio/OFL)?
2. **Contrato de sprites:** ¿32×32 (recomendado) o mantener 16×16?
3. **Máscara alfa** para sprites (calidad) vs clave `0xF81F` (compatibilidad).
4. **¿Se commitea `Res/` o solo los datos C derivados?** (recomendado: solo C
   derivado + generador documentado).
5. **Fuente arcade:** ¿Press Start K con atribución (riesgo) o Press Start 2P
   OFL (segura)?
6. **Alcance de audio:** ¿troceado en `audio.c` y variantes de sirena, o se
   acepta un subconjunto simplificado en Fase 2?

---

### Anexo A — Resumen de acción por archivo

| Recurso | Acción Fase 2 | Prioridad |
|---|---|---|
| `cherry, strawberry, peach, apple, grapes` | Frutas RGB565 16×16 por índice (CEREZA/FRESA/NARANJA/MANZANA/UVAS) | Alta |
| `ghost1, ghost2` | Recolor 4 colores + ojos, 32×32, frightened/flash/ojos | Alta |
| `game start, waka1/2, eat ghost, eat fruit, extra life, pacman death` | PCM u8 11025 one-shot | Alta |
| `hunter/hunted siren` | PCM loop + 4 variantes de tono | Alta |
| `ghost respawn` | PCM loop con crossfade (ojos volviendo) | Media |
| `intermission` | PCM one-shot (2 trozos) para nivel completado | Media |
| `prstartk.ttf` | Atlas 8/16/24 + atribución/validación de licencia | Alta |
| `dead.png` | Ráfaga final de muerte (opcional) | Baja |
| `retroghost1/2` | Skin Retro de fantasmas | Baja |
| `Clydeeghost.png` | Arte de menú/attract (key-out blanco) | Baja |
| `Key-icon.png` | Icono UI (récords/ayuda) | Baja |
| `atari full.ttf` | **Excluir** (licencia/marca/cobertura) | — |

### Anexo B — Tabla de estilos detectados

| Grupo | Estilo | Uso recomendado |
|---|---|---|
| Frutas (8) | Vector glossy con alfa suave | Skin "Classic" |
| `ghost1/2` | 3D suave recoloreable con ojos | Skin "Classic" |
| `retroghost1/2` | Pixel-art plano | Skin "Retro" (nueva opción) |
| `dead`, `galaxian` | Vector plano/arcade | Arcade |
| `Clydeeghost` | Pixel-art grande (4 colores, fondo blanco) | Menú/attract |
| `Key-icon` | Icono glossy | UI arcade |

### Anexo C — Cómo reproducir la auditoría

```bash
PY=~/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
cd /tmp
$PY /tmp/audit_all.py
$PY /tmp/audit_wav4.py
$PY /tmp/png_proto.py
$PY /tmp/sprite_compare.py
$PY /tmp/ghost_proto.py
$PY /tmp/wav_proto3.py
$PY /tmp/ttf_proto.py
$PY /tmp/final_metrics.py
```

Los scripts usan solo Pillow/NumPy del Python bundled y las rutas absolutas a
`/home/t1an/Descargas/Res`.

---

## 12. Fase 2 ejecutada (task-36) — decisiones aprobadas y artefactos

> Aprobado por el Lead: entrega **privada/académica** con los recursos de
> `Res/` y aviso de no redistribución; sprites **16×16 RGB565**; fuente
> **Press Start K** (atribución codeman38); audio **PCM u8 mono 11025**;
> `intermission.wav` **no** se usa. Sin tocar core/render/platform ni los
> assets actuales (`sprites.c/h`, `preview.png`).

### 12.1 Artefactos generados

| Archivo | Tamaño | Contenido |
|---|---:|---|
| `assets/sprites_res.c` | 45.126 B | 5 frutas + 4 colores × 2 frames + asustado/parpadeo + ojos 4 dirs (16×16 RGB565, `0xF81F`) |
| `assets/sprites_res.h` | 2.419 B | símbolos y constantes (`pacasset_fruit_sprite_res`, `pacasset_ghost_frame_res`, ...) |
| `assets/font_arcade.c` | 218.603 B | atlas alpha 8bpp 224 celdas 8×16 (28.672 B de cobertura) |
| `assets/font_arcade.h` | 2.464 B | `pac_arcade_font_cov[224][16][8]`, métricas y helpers |
| `assets/sfx_res.c` | 772.741 B | PCM 8 bits sin signo mono 11025 (127.034 B útiles) + tablas |
| `assets/sfx_res.h` | 3.835 B | descriptores, chunks, loops y variantes de sirena |
| `assets/LICENSE_RES.md` | 3.146 B | procedencia, hashes, no redistribución, exclusiones |
| `assets/fonts/LICENSE_ARCADE.md` | 1.125 B | atribución codeman38 y aviso user-supplied |
| `assets/res_original/` | 960 KiB | 19 originales (18 usados + `key.png` de procedencia), byte-idénticos, + `LICENSE_RES.md` |
| `tools/gen_pacman_res_assets.py` | 56.016 B | generador reproducible (Pillow+NumPy) |

MD5 de los datos generados (deterministas, misma entrada → mismos bytes):

```
5ebbc187274a38338ffbffa491b43492  assets/sprites_res.c
f4468770ec8d9a12765754e06803ea36  assets/sprites_res.h
e525288944a6e0d3184543756563cf34  assets/font_arcade.c
65d122176eb84d1f94e05accd440c20b  assets/font_arcade.h
f00b14fbed4413daded2310db3988485  assets/sfx_res.c
479ebca8c61fd9809fb642229e4ee8e5  assets/sfx_res.h
```

### 12.2 Símbolos exactos entregados

```c
/* sprites_res.h (16x16, 0xF81F) */
extern const uint16_t pacasset_fruit_sprite_res[5][256];
extern const uint16_t pacasset_ghost_frame_res[4][2][256];
extern const uint16_t pacasset_ghost_fright_frame_res[2][256];
extern const uint16_t pacasset_ghost_flash_frame_res[2][256];
extern const uint16_t pacasset_ghost_eyes_frame_res[4][256];
extern const char *const pacasset_fruit_name_res[5]; /* CEREZA..UVAS */
/* llave dorada decorativa del indicador NIVEL: vive en assets/sprites.c
   (arte procedural, no derivada de Res) y NO es una fruta */
extern const uint16_t pacasset_key_sprite[256];

/* font_arcade.h */
#define PAC_ARCADEFONT_W 8
#define PAC_ARCADEFONT_H 16
#define PAC_ARCADEFONT_FIRST 32
#define PAC_ARCADEFONT_LAST 255
extern const uint8_t pac_arcade_font_cov[224][16][8]; /* 8bpp por pixel */
extern const uint8_t pac_arcade_font_present[224];
extern const uint8_t pac_arcade_font_missing_count;
extern const uint16_t pac_arcade_font_missing_cps[];
extern const uint8_t pac_arcade_font_advance;      /* 8 */
extern const uint8_t pac_arcade_font_ascent;       /* 8 */
extern const uint8_t pac_arcade_font_line_height;  /* 16 */
static inline const uint8_t *pac_arcade_font_glyph(uint32_t cp);
static inline int pac_arcade_font_covers(uint32_t cp);

/* sfx_res.h */
#define PACASSET_RES_SFX_SLOTS 16   /* = pac_audio_sfx_t + GHOST_RESPAWN */
#define PACASSET_RES_SFX_MAX_CHUNKS 2
typedef struct { const uint8_t *data; uint32_t len; } pac_res_sfx_t;
extern const pac_res_sfx_t pacasset_sfx_res[16];
extern const uint8_t pacasset_sfx_res_loop[16];
extern const uint8_t pacasset_sfx_res_chunk_count[16];
extern const uint8_t *const pacasset_sfx_res_chunks[16][2];
extern const uint32_t pacasset_sfx_res_chunk_len[16][2];
extern const pac_res_sfx_t pacasset_siren_hunt_res[4];  /* +0/10/20/30% */
extern const pac_res_sfx_t pacasset_siren_chase_res[4];
extern const uint8_t pacasset_siren_variant_pct[4];
```

### 12.3 Formato de la fuente (aclaración)

Press Start K es una fuente **cuadrada** por diseño (8×8, 16×16, 24×24…).
Para cumplir el contrato de game-dev (celdas 8×16, avance 8) se rasteriza a
**8 px** y se coloca sobre la celda de 16 filas con la línea base en la fila 8:
cada glifo ocupa las filas ~1..8 y las filas 9..15 quedan libres. Métricas:
`advance=8`, `ascent=8`, `line_height=16`. La cobertura conserva 8bpp (niveles
de gris 1..255). Cobertura Latin-1: ñ/Ñ/á/é/í/ó/ú/ü/Á/É/Í/Ó/Ú/Ü/¿/¡ presentes;
ausentes solo signos secundarios (`§ ¨ ª ¬ SHY ¯ ² ³ ´ µ ¶ · ¸ ¹ º ¼ ½ ¾` y
controles C1), exportados en `pac_arcade_font_missing_cps`; para ellos se dibuja
`?` y game-dev puede recurrir a Inter. Si se prefiere un glifo más grande para
títulos, se puede añadir un atlas 16×16 nativo en una iteración posterior (no
entregado ahora por alcance).

### 12.4 Audio entregado (10 WAV, sin intermission)

| Slot | Clip | Frames | Duración | Chunks SB16 | Loop |
|---|---|---:|---:|---:|---|
| 2 START | game start | 46.676 | 4,234 s | **2** | no |
| 3 WAKA1 | waka1 | 932 | 0,085 s | 1 | no |
| 4 WAKA2 | waka2 | 929 | 0,084 s | 1 | no |
| 6 EAT_GHOST | eat ghost | 6.324 | 0,574 s | 1 | no |
| 7 EAT_FRUIT | eat fruit | 4.845 | 0,440 s | 1 | no |
| 8 DEATH | pacman death | 16.916 | 1,534 s | 1 | no |
| 9 EXTRA_LIFE | extra life | 20.940 | 1,899 s | 1 | no |
| 12 SIREN_CHASE | hunter siren | 1.470 | 0,133 s | 1 | sí (xfade 5 ms) |
| 13 SIREN_HUNT | hunted siren | 4.412 | 0,400 s | 1 | sí (xfade 5 ms) |
| 15 GHOST_RESPAWN | ghost respawn | 2.935 | 0,266 s | 1 | sí (xfade 5 ms) |

Sirenas con 4 variantes de pitch (+0/10/20/30 %): `siren_hunt` 4.412/4.011/3.676/3.394
frames y `siren_chase` 1.470/1.336/1.225/1.131. Pico normalizado a 234/255
(≈ −0,7 dBFS), sin clipping. Total PCM 127.034 B. Los slots MENU(1), POWER(5),
LEVEL_CLEAR(10), GAME_OVER(11) y SIREN_FRIGHT(14) quedan con `data=NULL/len=0`
para el fallback sintetizado actual.

### 12.5 Validación ejecutada

- Generador determinista: dos ejecuciones → MD5 idénticos (sección 12.1).
- Test C de assets (`/tmp/test_res_assets.c`): **0 fallos** — tamaños de
  arrays, transparencia/contorno, frames/colores/ojos distintos, nombres,
  cobertura Latin-1 requerida, lista de ausentes, chunks y suma de longitudes,
  loops, variantes de sirena y total PCM.
- Compilación con flags del proyecto (`-m32 -ffreestanding -O2 -Wall -Wextra`):
  `sprites_res.c`, `font_arcade.c`, `sfx_res.c` → **cero warnings**.
- `make linux` y `make sereos` en copia limpia → OK (los nuevos `.c` entran por
  el glob de `assets/` y enlazan sin tocar core/render/platform).
- Orígenes copiados byte-idénticos (19/19, MD5 verificados) y excluidos
  (`intermission.wav`, `atari full.ttf`, `dead.png`, `retroghost1/2.png`,
  `Clydeeghost.png`) no copiados.
- Preview con el motor real de SereOS (framebuffer + `gfx_draw_sprite` +
  `gfx_blend_pixel`): `/tmp/res_gen/render_from_assets.png` (sprites, HUD,
  acentos) y `/tmp/res_gen/sprites_res_sheet.png`, `font_arcade_preview.png`,
  `sfx_waveforms.png`. El 32×32 se generó **solo** como preview en
  `/tmp/res_gen/sprites_res_32_preview.png`, no entregado.

### 12.6 Integración para game-dev

Añadir `#include "sprites_res.h"` / `"font_arcade.h"` / `"sfx_res.h"` y un
selector `PACMAN_USE_RES_ASSETS` (por defecto ON) con el arte actual como
fallback. Los arrays son `const` y no requieren inicialización. Para audio:
usar `pacasset_sfx_res[slot]` con `pacasset_sfx_res_loop[]`; si
`chunk_count>1`, enviar los trozos de `pacasset_sfx_res_chunks[slot][i]` (cada
uno ≤ 32768) para SB16; en Linux se puede reproducir el total. Para sirenas,
elegir variante con `pacasset_siren_hunt_res[0..3]` según dots restantes.
