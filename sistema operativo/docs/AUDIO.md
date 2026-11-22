# AUDIO - subsistema de sonido de SereOS (SB16 + PC speaker)

SereOS tiene audio PCM real desde la version 1.0 con PAC-MAN SereOS.

> Guia practica para hacer sonar SereOS en QEMU/VirtualBox/VMware y en
> hardware real: **[AUDIO_VM.md](AUDIO_VM.md)**. Evidencia de las pruebas de
> audio en `docs/evidence/audio/`. La capa
`audio/` es **independiente del juego**: cualquier aplicacion puede llamar a
`audio_init()`, `audio_play()` y `audio_update()`. Si no hay Sound Blaster 16,
todo sigue funcionando con el altavoz del PC como fallback.

Los efectos de sonido son **originales, sintetizados para este proyecto** por
`tools/gen_audio.py` (osciladores square/triangle/sine, barridos, vibrato,
ruido determinista y envolventes). No se usa ni se redistribuye ningun WAV de
terceros; los audios de referencia (Paku-Paku) solo sirvieron de inspiracion
de estilo arcade y nunca se han copiado.

---

## 1. Arquitectura

```
juego / app
   |  audio_play(id) / audio_loop(id) / audio_stop()      (no bloqueante)
   v
audio/audio.c  ................ cola de 4 one-shots, loop de sirenas,
   |                            fallback, estadisticas, bounce buffer DMA
   +--> drivers/sb16.c  ....... DSP Sound Blaster 16 + DMA 8237 canal 1
   +--> drivers/speaker.c ..... altavoz del PC (PIT canal 2 + puerto 0x61)
   +--> audio/sfx_data.c ...... PCM 8-bit unsigned mono 11025 Hz
                                   (generado por tools/gen_audio.py)
```

| Fichero | Contenido |
|---|---|
| `audio/audio.h` | Contrato **congelado** de la capa de audio |
| `audio/audio.c` | Cola, mezcla de prioridades, sirenas, fallback, stats |
| `audio/sfx_data.h` | Formato `sfx_clip_t` + tabla de clips (generado) |
| `audio/sfx_data.c` | 14 SFX originales PCM 8-bit mono 11025 Hz (generado) |
| `drivers/sb16.h` | API del driver SB16 (no bloqueante) |
| `drivers/sb16.c` | Reset DSP, version, mixer, sample rate, DMA 8237, stop |
| `tools/gen_audio.py` | Sintetizador determinista de los SFX (Python puro) |
| `drivers/speaker.c` | Altavoz del PC (ya existia; se usa como fallback) |

### Modelo de ejecucion

Todo es **no bloqueante**:

- `audio_init()` detecta el hardware con el reset del DSP en **toda la
  ventana 0x220..0x280 (paso 0x10)**, que cubre 0x220/0x230/0x240/0x250/0x260/
  0x270/0x280, o selecciona `pcspk`. Es idempotente y tolerante a fallos: si no
  hay SB16 devuelve el backend del altavoz del PC y el sistema arranca igual.
  Se llama desde `kernel_main()` justo despues de habilitar las interrupciones
  y el resultado real se registra en el log de arranque (`[OK] Audio: ...`).
- `audio_detail()` describe el dispositivo detectado con la cadena que muestra
  la UI: `"SB16 0x220 IRQ5 DMA1"`, `"solo PC speaker"`
  o `"no disponible"`. Es el contrato que usa la fila "Audio" de Acerca de.
- `audio_test_tone(hz, ms)` y los comandos de shell `beep`/`audiotest` generan
  tonos de diagnostico por el backend activo (PCM por DMA o PIT canal 2).
- `audio_play()` dispara el hardware o encola (maximo 4 peticiones). Si la
  cola esta llena, la peticion se descarta y se incrementa `audio_underruns()`.
- `audio_loop()` arranca/reemplaza una sirena en bucle (chase/hunt/fright).
- `audio_update()` debe llamarse periodicamente desde el bucle principal o el
  `step()` cooperativo del juego: arranca el siguiente clip de la cola,
  rearma el bucle de sirena, apaga los tonos del altavoz del PC y detecta el
  final del DMA.
- La finalizacion del bloque se detecta por la **IRQ 5** del SB16: el handler
  instalado con `irq_install(5, ...)` solo lee `base+0x0E` (acknowledge de la
  IRQ de 8 bits del DSP), marca la bandera de fin y cuenta la interrupcion; el
  EOI al PIC lo envia `interrupt_handler()` (kernel/idt.c). Como red de
  seguridad, `sb16_busy()` tambien libera el canal por tiempo
  (`duracion + 100 ms`) si la IRQ no llegara: una VM con el SB16 en otra IRQ
  sigue sonando (verificado con `-device sb16,irq=7`).

---

## 2. Hardware: Sound Blaster 16

### Puertos DSP

| Puerto | Uso |
|---|---|
| `base+0x06` | reset del DSP (escribir 1, esperar, escribir 0) |
| `base+0x0A` | lectura de datos del DSP |
| `base+0x0C` | escritura de comandos/datos; al leer, estado de escritura (bit 7 = ocupado) |
| `base+0x0E` | estado de lectura (bit 7 = hay dato); al leer, **acknowledge de la IRQ de 8 bits** |
| `base+0x04` | indice del mixer |
| `base+0x05` | datos del mixer |

Secuencia de inicializacion usada:

1. `outb(0x226, 1)`, esperar ~3 us, `outb(0x226, 0)`.
2. Sondear `0x22E` hasta bit 7 y leer `0x22A`: debe llegar `0xAA`.
3. Version con comando `0xE1` (QEMU devuelve `0x0405`, DSP 4.5).
4. Mixer al maximo: los registros del mixer son **atenuacion** (`0x00` = 0 dB,
   `0xFF` = -62 dB = silencio). Se programan `0x04`/`0x22` (voz/maestro del
   SB16) y `0x30..0x33` (maestro L/R y voz L/R, que son los que aplican QEMU,
   VirtualBox y las SB16 reales) todos a `0x00`. Escribir `0xFF` (como hacia la
   version anterior) silencia el altavoz en hardware real y en SB16 emuladas
   que respetan el mixer.
5. Altavoz on con `0xD1`; apagado con `0xD3`; halt DMA con `0xD0`.
6. IRQ 5 instalada en la IDT (`irq_install(5, ...)`) y desenmascarada en el PIC
   maestro (puerto 0x21); el fin de bloque lo avisa el DSP por esa IRQ.

### Sample rate

- SB16 (DSP >= 4): comando `0x41` con la frecuencia en 16 bits,
  **primero byte alto y despues bajo** (el DSP interpreta `hi, lo`).
- SB Pro (DSP 3): comando `0x40` con la constante de tiempo
  `256 - 1000000/rate`.

Los SFX estan a **11025 Hz**; `audio_sample_rate()` devuelve 11025 con SB16 y
0 con altavoz del PC (que no reproduce PCM).

### DMA 8237, canal 1 (8 bits, single-cycle)

```
outb(0x0A, 0x05)   enmascarar canal 1
outb(0x0C, 0x00)   limpiar flip-flop
outb(0x0B, 0x49)   single, incremento, READ = memoria -> dispositivo, canal 1
outb(0x02, addr & 0xFF); outb(0x02, addr >> 8)    direccion
outb(0x83, addr >> 16)                            pagina
outb(0x03, (len-1) & 0xFF); outb(0x03, (len-1) >> 8)   contador
outb(0x0A, 0x01)   desenmascarar canal 1
DSP: 0x14 + (len-1) bajo + (len-1) alto          single-cycle 8-bit DAC
```

El byte de modo es **0x49**: bits 7-6 = 01 (single), bit 5 = 0 (incremento),
bits 3-2 = **10 (READ = memoria -> dispositivo)** y bits 1-0 = 01 (canal 1).
El valor 0x45 de versiones anteriores ponia *WRITE* (dispositivo -> memoria):
en hardware real el 8237 habria machacado la bounce buffer en vez de leerla.

Restricciones reales del 8237 de 8 bits que el driver valida:

- buffer fisico **< 16 MiB** (SereOS usa identidad fisica = virtual);
- el bloque **no puede cruzar una pagina de 64 KiB**.

Por eso `audio.c` copia cada clip a una bounce buffer estatica de 32 KiB
alineada a 64 KiB: cumple ambas condiciones siempre. La finalizacion se
detecta por tiempo (`len / rate_real`) sin IRQ.

---

## 3. Formato y efectos

- PCM **8 bits sin signo** (128 = silencio), **mono**, **11025 Hz**.
- Total: **111133 muestras = 111133 bytes = 10,09 s** (< 200 KiB).
- `audio/sfx_data.c` es generado; no editar a mano.
  Regenerar con: `python3 tools/gen_audio.py`.

| Enum | Nombre | Duracion | Tipo | Disparo en Pacman |
|---|---|---|---|---|
| `AUDIO_MENU` | menu | 240 ms | one-shot | navegacion/menu |
| `AUDIO_START` | start | 900 ms | one-shot | empezar partida |
| `AUDIO_WAKA1` | waka1 | 110 ms | one-shot | comer punto (alterna) |
| `AUDIO_WAKA2` | waka2 | 110 ms | one-shot | comer punto (alterna) |
| `AUDIO_POWER` | power | 480 ms | one-shot | power pellet |
| `AUDIO_EAT_GHOST` | eat_ghost | 300 ms | one-shot | comer fantasma |
| `AUDIO_EAT_FRUIT` | eat_fruit | 340 ms | one-shot | comer fruta |
| `AUDIO_DEATH` | death | 1340 ms | one-shot | morir |
| `AUDIO_EXTRA_LIFE` | extra_life | 680 ms | one-shot | vida extra |
| `AUDIO_LEVEL_CLEAR` | level_clear | 1240 ms | one-shot | nivel completado |
| `AUDIO_GAME_OVER` | game_over | 1540 ms | one-shot | fin de partida |
| `AUDIO_SIREN_CHASE` | siren_chase | 1000 ms | loop | modo chase |
| `AUDIO_SIREN_HUNT` | siren_hunt | 1000 ms | loop | modo hunt |
| `AUDIO_SIREN_FRIGHT` | siren_fright | 800 ms | loop | modo fright |

Los clips de sirena tienen 4 ms de fade de entrada/salida para que el
rearranque del bucle no produzca clics.

### Integracion con el juego

`Pac-man SereOS/src/core/game_audio.c` traduce los eventos del juego a su
interfaz de plataforma y `Pac-man SereOS/src/platform/sereos/platform_sereos.c`
la conecta con el OS. La versión definitiva usa **SB16 directo con PCM u8 mono
11025 Hz de los WAV de `Res`** (`assets/sfx_res.c`, trozos ≤32 KiB y cola en
`pac_audio_update`) y cae a esta capa si no hay SB16 (`pac_audio_*` ->
`audio_*`):

- `pac_audio_init()` -> `audio_init()` / `audio_available()`.
- `pac_audio_play(sfx)` -> `audio_play()`.
- `pac_audio_loop(sfx)` / `pac_audio_stop_loop()` -> `audio_loop()` /
  `audio_stop_loop()`.
- `pac_audio_update()` -> `audio_update()` desde el `step` cooperativo.
- `pac_audio_stop()` -> `audio_stop()` al cerrar la ventana.

El componente `Pac-man SereOS/` mantiene una sola copia de los eventos de
sonido para sus backends SereOS y Linux; el OS solo expone `audio/` (este
módulo), independiente del juego. Verificación de integración final (QEMU
11.1.3, SB16 + `-audiodev wav`): WAV con **4,58 s activos**, peak **29.952**
(91,4 % FS) y RMS **11.830** (36,1 % FS), todos los tramos de 100 ms con
señal; serial sin `SEREOS_EXCEPTION`/`SEREOS_PANIC`.

---

## 4. Fallback: altavoz del PC

Si no se detecta SB16, `audio_backend()` devuelve `"pcspk"` y
`audio_available()` sigue devolviendo 1 (el altavoz del PC es universal).
`audio_play()` programa tonos cortos con `speaker_tone()` y `audio_update()`
los apaga al vencer; `audio_loop()` alterna dos frecuencias por fase.

| Efecto | Hz | ms |
|---|---|---|
| menu | 700 | 110 |
| start | 950 | 220 |
| waka1 / waka2 | 520 / 390 | 70 |
| power | 880 | 180 |
| eat_ghost | 660 | 140 |
| eat_fruit | 1000 | 150 |
| death | 180 | 420 |
| extra_life | 1250 | 260 |
| level_clear | 1000 | 350 |
| game_over | 140 | 520 |
| siren_chase | 196 / 247 | 250 |
| siren_hunt | 294 / 370 | 125 |
| siren_fright | 131 / 165 | 180 |

El fallback es una aproximacion monofonica (no es PCM): sirve para que el
juego tenga feedback sonoro en hardware sin SB16.

---

## 5. Compilacion y verificacion

El `Makefile` ya incluye `-Iaudio` y descubre `audio/*.c` y `drivers/*.c`
automaticamente. Los archivos compilan sin warnings con los flags del proyecto.

```bash
make                       # kernel + ISO
make run-audio             # QEMU con SB16 audible (backend pipewire)
make run-audio-wav         # QEMU headless con captura audio-capture.wav
```

### Verificacion con el comando `audiotest` (v1.9)

`docs/evidence/audio/verify_audio.py` arranca la ISO con `tools/qemu_ctrl.py`,
abre F2 (Terminal), escribe `audiotest` y analiza el WAV con numpy. Resultado
(QEMU 11.1.3, TCG, 256 MiB; evidencia completa en `docs/evidence/audio/`):

| Escenario | Serial | WAV |
|---|---|---|
| SB16 (`-audiodev wav -device sb16`) | `Audio: SB16 0x220 IRQ5 DMA1`; `AUDIO_TEST_DONE tones=4 irq=4 pit_hz=100` | 0,788 s activos, peak **-3,0 dBFS**, RMS **-3,4 dBFS**, tonos **441,7/658,3/883,3/1316,7 Hz** (440/660/880/1320 esperados) |
| Solo PC speaker (`-machine pc,pcspk-audiodev=...`) | `Audio: solo PC speaker`; `AUDIO_TEST:pcspk`; `tones=4 irq=0` | 0,797 s activos, peak -2,5 dBFS, mismos 4 tonos |
| Sin audio (`make run`) | `solo PC speaker`, sin excepcion | (no hay backend que capturar) |
| SB16 en 0x240 | `SB16 0x240 IRQ5 DMA1` | 4 tonos + `irq=4` (valida el escaneo 0x220..0x280) |
| SB16 con IRQ 7 | `tones=4 irq=0` | 4 tonos; fin por tiempo, PIT 100 Hz (robustez) |

La IRQ 5 funciona de verdad: cuatro tonos = cuatro interrupciones
(`irq=4`), y el temporizador sigue a 100 Hz durante la prueba (`pit_ticks`
coincide con la duracion de los tonos), lo que ademas confirma que el PIT
canal 2 del altavoz no altera el canal 0 del reloj.

### Verificacion real realizada (v1.8)

Kernel de prueba independiente en `/tmp/ks_audio` (usa `boot/`, `gdt`, `idt`,
`serial`, `timer`, `speaker`, `drivers/sb16.c`, `audio/audio.c`,
`audio/sfx_data.c`) que reproduce los 11 one-shots, las 3 sirenas y termina.

```bash
qemu-system-i386 -m 256M -vga std -display none \
  -serial file:/tmp/ks_audio/serial_wav3.log \
  -audiodev wav,id=snd0,path=/tmp/audio_test.wav \
  -device sb16,audiodev=snd0 -cdrom /tmp/ks_audio/audio_test.iso
python3 /tmp/ks_audio/analyze_wav.py /tmp/audio_test.wav \
  --sfx audio/sfx_data.c
```

Resultado de la captura (`/tmp/audio_test.wav`, QEMU 11.1.3, SB16 en `0x220`,
DSP 4.5, DMA 1, 11025 Hz -> 44100 Hz estereo 16 bits):

```
WAV: 470933 frames a 44100 Hz = 10.679 s
peak = 23296 (71.1 % FS)   rms = 14530 (44.34 % FS)
correlacion muestra a muestra con sfx_data.c remuestreado 4x:
  menu 1.00000  start 1.00001  waka1 1.00000  waka2 1.00000
  power 1.00000  eat_ghost 1.00000  eat_fruit 0.99997  death 1.00002
  extra_life 0.99998  level_clear 1.00001  game_over 1.00004
sirenas (ZCR): chase 190..250 Hz  hunt 280..380 Hz  fright 130..180 Hz
duracion del tramo de sirenas 149881 frames (esperado 149940, error 0.04%)
duracion total 470933 frames (esperado 470992, error 0.01%)
RESULTADO: PASS (20 comprobaciones, 0 fallos)
```

La correlacion ~1.0 demuestra que el DSP, el DMA y el driver entregan
exactamente el PCM generado y a la velocidad correcta. Si la frecuencia del
DSP fuera incorrecta, la correlacion y la duracion fallarian: el orden de
bytes (`hi, lo`) del comando `0x41` es un detalle critico que se detecto y
corrigio durante el desarrollo con el log `-d guest_errors` de QEMU.

Backend `wav` de QEMU: **solo escribe mientras hay una voz activa**, por eso
los silencios de 140 ms entre efectos no aparecen en el WAV; la captura es la
concatenacion del audio activo. El analizador lo tiene en cuenta y comprueba
que 7,28 s de one-shots + 3,40 s de sirenas = 10,68 s.

### Integracion en el ISO del proyecto

Con Pacman ya integrado se arranco `sereos.iso` con SB16 + WAV, se abrio la
app Juego (F4), se pulso Enter (JUGAR) y se jugo unos segundos:

- marcadores serie: `GAME_MENU`, `APP_OPEN:game`, `GAME_START`;
- captura `/tmp/pacman_audio.wav`: 421636 frames (9.561 s activos),
  peak 23296 (71.1 % FS), rms 18093 (55.2 % FS);
- ZCR dominante 275-375 Hz (sirena hunt 294/370 Hz) y picos de 500-1050 Hz
  durante el jingle de inicio;
- captura de pantalla con Pacman jugando (puntuacion 40, modo CHASE).

### Caso sin SB16 (fallback)

Misma ISO sin `-device sb16`:

```
[OK] Audio: solo PC speaker
AUDIO_TEST:pcspk
AUDIO_DETAIL:solo PC speaker
AUDIO_TEST_DONE tones=4 irq=0 pit_hz=100 pit_ticks=80
```

Sin ningun dispositivo de audio en la VM (`make run`) el sistema no cae: cae
al altavoz del PC, `audio_detail()` devuelve `"solo PC speaker"` y el PIT
sigue a 100 Hz. Si se enruta el altavoz del PC a un backend de QEMU
(`-audiodev wav,id=snd0 -machine pc,pcspk-audiodev=snd0`) el fallback **si se
oye y se puede capturar**: la verificacion de v1.9 obtuvo un WAV de 0,797 s
con los cuatro tonos de `audiotest` a 440/660/880/1320 Hz, peak -2,5 dBFS.

En VirtualBox/VMware el altavoz del PC no esta enrutado al audio de la VM, por
eso el fallback es practicamente inaudible ahi: para esas VM hay que usar
SB16 (VirtualBox) o QEMU (ver `docs/AUDIO_VM.md`).

---

## 6. Limitaciones conocidas

- Un solo canal PCM a 8 bits y 11025 Hz; no hay mezcla de voces simultaneas
  (las peticiones concurrentes se encolan o se descartan).
- Fin de bloque por IRQ 5 (ack leyendo `base+0x0E` en el handler) con red de
  seguridad por tiempo (`duracion + 100 ms`); si la IRQ del SB16 no es la 5
  (VM mal configurada) el audio sigue sonando, pero el canal se libera por
  tiempo y se anade ~100 ms de silencio entre bloques.
- Bounce buffer estatica de 32 KiB alineada a 64 KiB: clips mayores no se
  reproducen (ninguno de los actuales se acerca al limite). En el kernel real
  compilado queda en `0x00370000` (3,44 MiB), por debajo de los 16 MiB que
  permite el DMA de 8 bits y alineada a 64 KiB (nunca cruza pagina).
- El altavoz del PC no puede reproducir los PCM: solo aproxima tonos.
- El mixer se fija al maximo (`0x00`); no hay control de volumen por software.
- El altavoz del PC no suena en VirtualBox/VMware (no lo enrutan) y en QEMU
  requiere `-machine pcspk-audiodev=<audiodev>`; el backend `wav` de QEMU no
  graba los silencios entre efectos.
- `sb16_init()` solo sondea la IRQ 5 y el DMA 1 (los valores por defecto de
  QEMU y del ajuste SB16 de VirtualBox); no hay deteccion de IRQ/DMA por
  software ni soporte de PnP.
- No hay soporte de audio 16 bits, estereo ni streaming (no es necesario para
  los SFX de esta version).

---

## 7. Licencias

- `audio/sfx_data.c` y `audio/sfx_data.h`: **generados originalmente para
  SereOS** por `tools/gen_audio.py` (autor: proyecto SereOS, UMB 2026). Se
  pueden redistribuir con el sistema.
- No se incluyen ni se han copiado WAV de Paku-Paku ni de ningun otro
  proyecto; esos audios son de terceros y **no se redistribuyen**.
- El resto del codigo sigue la licencia del proyecto SereOS.
