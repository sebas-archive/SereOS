# Evidencia de audio (task-2, v1.9)

Verificacion **real** del audio de SereOS en QEMU: se arranca la ISO, se abre
la Terminal con **F2**, se ejecuta **`audiotest`** y se analiza el WAV
capturado con el backend `wav` de QEMU (numpy/FFT). Reproducible con
`verify_audio.py` (mismo directorio):

```sh
cd /home/t1an/Descargas/sereos02
python3 build/qa_audio/verify_audio.py A     # SB16 + WAV
python3 build/qa_audio/verify_audio.py B     # fallback pcspk enrutado a WAV
python3 build/qa_audio/verify_audio.py C     # sin dispositivo de audio
```

El script usa `sistema operativo/tools/qemu_ctrl.py` (monitor `sendkey` /
`screendump`), arranca sin KVM (TCG) y guarda el log COM1 de cada escenario.

## Entorno

| Elemento | Valor |
|---|---|
| QEMU | 11.1.3 (`qemu-system-i386`); sin KVM (no hay `/dev/kvm` usable) |
| VM | 256 MiB, `-vga std`, `-display none` |
| Toolchain | `gcc 16.2.1 -m32` (modo host del Makefile), `nasm 3.02`, `grub-mkrescue 2.16` |
| Analisis | Python 3.14 + numpy 2.5.4 |
| ISO | `make -j` sobre un arbol aislado identico al entregado |

## Comandos QEMU exactos

```sh
# A) SB16 + captura WAV
qemu-system-i386 -name sereos-qa -display none -m 256M -vga std \
  -cdrom sereos.iso -monitor unix:monitor.sock,server,nowait \
  -serial file:serial.log -qmp unix:qmp.sock,server,nowait -rtc base=localtime \
  -no-reboot -audiodev wav,id=snd0,path=A_sb16.wav -device sb16,audiodev=snd0

# B) sin SB16, altavoz del PC enrutado al WAV
qemu-system-i386 ... -audiodev wav,id=snd0,path=B_pcspk.wav \
  -machine pc,pcspk-audiodev=snd0

# C) sin ningun dispositivo de audio (equivalente a `make run`)
qemu-system-i386 ...            # sin -audiodev ni -device

# D) SB16 en un puerto base no habitual (valida el escaneo 0x220..0x280)
qemu-system-i386 ... -audiodev wav,id=snd0,path=D_0x240.wav \
  -device sb16,iobase=0x240,irq=5,dma=1,dma16=5,audiodev=snd0

# E) SB16 con IRQ distinta de la 5 (valida el fin de bloque por tiempo)
qemu-system-i386 ... -audiodev wav,id=snd0,path=E_irq7.wav \
  -device sb16,irq=7,audiodev=snd0
```

En todos: esperar `GUI_READY`, pulsar **F2**, escribir `audiotest` + Enter,
esperar `AUDIO_TEST_DONE` por COM1 y analizar el WAV.

## Resultados

| Escenario | AUDIO_TEST | AUDIO_DETAIL | WAV activo | peak | RMS | frecuencias (Hz) | AUDIO_TEST_DONE |
|---|---|---|---|---|---|---|---|
| A_sb16 | `AUDIO_TEST:sb16` | `AUDIO_DETAIL:SB16 0x220 IRQ5 DMA1` | 0.791 s | 23296 (-3.0 dBFS) | -3.4 dBFS | [442, 658, 883, 1317] | `AUDIO_TEST_DONE tones=4 irq=4 pit_hz=100 pit_ticks=80` |
| B_pcspk | `AUDIO_TEST:pcspk` | `AUDIO_DETAIL:solo PC speaker` | 0.787 s | 24576 (-2.5 dBFS) | -2.6 dBFS | [442, 658, 883, 1325] | `AUDIO_TEST_DONE tones=4 irq=0 pit_hz=100 pit_ticks=80` |
| D_scan_0x240 | `AUDIO_TEST:sb16` | `AUDIO_DETAIL:SB16 0x240 IRQ5 DMA1` | 0.788 s | 23296 (-3.0 dBFS) | -3.4 dBFS | [442, 658, 883, 1317] | `AUDIO_TEST_DONE tones=4 irq=4 pit_hz=100 pit_ticks=79` |
| E_irq_mismatch | `AUDIO_TEST:sb16` | `AUDIO_DETAIL:SB16 0x220 IRQ5 DMA1` | 0.797 s | 23296 (-3.0 dBFS) | -3.4 dBFS | [442, 658, 883, 1317] | `AUDIO_TEST_DONE tones=4 irq=0 pit_hz=100 pit_ticks=120` |

Escenario C (sin audio): `AUDIO_TEST:pcspk`, `AUDIO_DETAIL:solo PC speaker`,
`AUDIO_TEST_DONE tones=4 irq=0 pit_hz=100 pit_ticks=80`, sin
`SEREOS_EXCEPTION`/`SEREOS_PANIC`.

Lectura:

- **No hay silencio**: peak -3,0 dBFS y RMS -3,4 dBFS; el WAV tiene ~0,79 s
  activos de los ~0,80 s que duran los cuatro tonos.
- **Tono correcto**: la FFT por ventanas detecta 441,7/658,3/883,3/1316,7 Hz
  para 440/660/880/1320 Hz (error < 0,5 %, limite de la ventana de analisis).
  `audio_test_tone()` usa un oscilador DDS de fase 16.16 y onda cuadrada.
- **Fin por IRQ 5**: `irq=4` = cuatro interrupciones, una por bloque DMA, con
  ack leyendo `base+0x0E` y EOI en `interrupt_handler`.
- **PIT intacto**: `pit_hz=100` y `pit_ticks` = 79/80 durante la prueba; el
  canal 2 del altavoz no perturba el canal 0 del reloj.
- **Escaneo 0x220..0x280**: con `iobase=0x240` se detecta en 0x240 y suena.
- **Robustez de IRQ**: con `irq=7` no llega la IRQ 5 y el audio sigue
  reproduciendose (fin por tiempo, `irq=0`, `pit_ticks=120` por el margen de
  100 ms por bloque).

## Arranque y contrato de UI

Serial de arranque (escenario A):

```
[OK] Audio: SB16 0x220 IRQ5 DMA1
...
AUDIO_TEST:sb16
AUDIO_DETAIL:SB16 0x220 IRQ5 DMA1
AUDIO_TEST_DONE tones=4 irq=4 pit_hz=100 pit_ticks=80
```

Captura de la Terminal tras `audiotest`: `terminal_audiotest_sb16.png`.
`audio_detail()` esta declarado en `audio/audio.h` y lo usa la fila "Audio" de
la ventana Acerca de: `about_audio_sb16.png` (`SB16 0x220 IRQ5 DMA1`) y
`about_audio_noaudio.png` (`solo PC speaker`). La cadena es compacta para
caber completa en la fila; el DSP (4.5) se informa en el log de arranque y en
el comando `audio`.

## Integracion final: ISO del arbol compartido

Ademas del arbol aislado, se congelo la ISO final generada en
`sistema operativo/` (md5 `2f271b702171122b5f7d903339b42871`, 36827136 B;
`sereos.bin` md5 `fe07c51db8c44ec845819f8c2826155b`) y se repitio la prueba con
`audiotest` y la ventana Acerca de:

| Comprobacion | Valor |
|---|---|
| `[OK] Audio:` | `[OK] Audio: SB16 0x220 IRQ5 DMA1` |
| AUDIO_TEST / DETAIL | `AUDIO_TEST:sb16` / `AUDIO_DETAIL:SB16 0x220 IRQ5 DMA1` |
| AUDIO_TEST_DONE | `AUDIO_TEST_DONE tones=4 irq=4 pit_hz=100 pit_ticks=79` |
| WAV | 0.788 s activos, peak -3.0 dBFS, RMS -3.4 dBFS, [442, 658, 883, 1317] Hz |
| Excepciones/panico | ninguna |
| Acerca de | fila Audio = `SB16 0x220 IRQ5 DMA1` (`about_audio_shared_iso.png`) |
| Terminal | `audiotest` con backend/detalle/tonos/IRQ (`terminal_audiotest_shared_iso.png`) |

Log COM1 completo: `serial_shared_iso.log`; resultados: `results_shared.json`;
datos de build: `build_shared.json`.

## Comandos `audio`, `beep` y `audiotest` en la ISO final

Una ultima ejecucion sobre `sistema operativo/sereos.iso` (build 0 warnings,
`sereos.bin` md5 `fe07c51db8c44ec845819f8c2826155b`) con la Terminal (F2)
ejecutando `audio`, `beep 660 150` y `audiotest`:

| Comprobacion | Valor |
|---|---|
| Login serie | `[OK] Audio: SB16 0x220 IRQ5 DMA1` |
| `AUDIO_TEST` / `AUDIO_TEST_DONE` | `AUDIO_TEST:sb16` / `AUDIO_TEST_DONE tones=4 irq=5 pit_hz=100 pit_ticks=80` |
| WAV | 0.94 s (= 0,15 s del `beep` + 0,79 s del `audiotest`), peak -3.0 dBFS, RMS -3.4 dBFS |
| Frecuencias | [442, 658, 883, 1317] Hz (660 del beep + 440/660/880/1320 del audiotest) |
| IRQ | `irq=5` = 5 bloques DMA terminados por IRQ 5 (beep + 4 tonos) |
| Excepciones | ninguna |
| Captura | `terminal_audio_beep_audiotest.png` |

Log COM1: `serial_final_beep_audiotest.log`; analisis WAV:
`../build/qa_audio/evidence/final_beep_audiotest.json` (no versionado).

## Bounce buffer del DMA

```
$ nm -n sereos.bin | grep " audio_dma$"
00370000 b audio_dma          # 3,44 MiB < 16 MiB y alineada a 64 KiB
```

## Ficheros de este directorio

| Fichero | Contenido |
|---|---|
| `serial_A_sb16.log` | log COM1 completo del escenario SB16 |
| `serial_B_pcspk.log` | log COM1 del fallback pcspk enrutado |
| `serial_C_noaudio.log` | log COM1 sin dispositivos de audio |
| `serial_D_scan_0x240.log` | log COM1 con SB16 en 0x240 |
| `serial_E_irq7_mismatch.log` | log COM1 con SB16 en IRQ 7 |
| `results.json` | resultados estructurados + analisis WAV de los 5 escenarios |
| `audiotest_sb16_clip.wav` | recorte WAV valido (0.791 s) de los 4 tonos |
| `terminal_audiotest_sb16.png` | captura de la Terminal con `audiotest` |
| `about_audio_sb16.png` | Acerca de con SB16 (fila Audio = `SB16 0x220 IRQ5 DMA1`) |
| `about_audio_noaudio.png` | Acerca de sin SB16 (fila Audio = `solo PC speaker`) |
| `serial_shared_iso.log` | log COM1 de la ISO final del arbol compartido |
| `results_shared.json`, `build_shared.json` | resultados + md5 de la ISO final |
| `terminal_audiotest_shared_iso.png` | `audiotest` en la ISO final |
| `about_audio_shared_iso.png` | Acerca de en la ISO final |
| `serial_final_beep_audiotest.log` | log COM1 con `audio`/`beep`/`audiotest` |
| `terminal_audio_beep_audiotest.png` | captura de esos comandos |
| `verify_audio.py` | script reproducible (QEMU + numpy) |

> Nota: el `/tmp` de esta sesion es efimero; los WAV crudos y los PPM de las
> VM quedan en `build/qa_audio/evidence/` (no versionado) y aqui se conservan
> el recorte WAV, los logs, las capturas y el analisis.
