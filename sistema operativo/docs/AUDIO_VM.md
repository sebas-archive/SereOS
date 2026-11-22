# AUDIO EN MAQUINAS VIRTUALES - como hacer que SereOS suene

SereOS tiene dos backends de audio:

| Backend | Hardware | `audio_backend()` | `audio_detail()` |
|---|---|---|---|
| SB16 | DSP Sound Blaster 16 + DMA 8237 (base 0x220..0x280, IRQ 5, DMA 1) | `"sb16"` | `"SB16 0x220 IRQ5 DMA1"` |
| PC speaker | PIT canal 2 + puerta del puerto 0x61 | `"pcspk"` | `"solo PC speaker"` |
| ninguno | ni SB16 ni altavoz utilizable | `"ninguno"` | `"no disponible"` |

En el arranque el kernel escribe la deteccion real en el log serie y en
`dmesg`:

```
[OK] Audio: SB16 0x220 IRQ5 DMA1
[OK] Audio: solo PC speaker
```

Compruebelo en la Terminal (F2) con los comandos `audio`, `beep [hz] [ms]` y
`audiotest` (este ultimo emite `AUDIO_TEST:<backend>` por COM1 para
verificacion automatica).

> **Aviso importante**: el fallback de altavoz del PC **no suena** en la
> mayoria de las VM. El altavoz del PC no es una tarjeta de sonido: es la
> salida del PIT canal 2 por el puerto 0x61, y cada hipervisor la emula (o no)
> de forma distinta. Si `dmesg` dice `solo PC speaker` en una VM, lo mas
> probable es que no oiga nada aunque el hardware este correctamente
> programado. Para oir sonido en una VM hay que darle un **SB16** a la VM.

---

## 1. QEMU (recomendado)

SereOS necesita una maquina con bus ISA: use la maquina por defecto
(`pc`/`i440fx`). En `q35` no hay ISA y `-device sb16` falla.

### 1.1 QEMU moderno (7.x, 8.x, 9.x, 10.x, 11.x)

SB16 por DMA con salida de audio del anfitrion (PipeWire/PulseAudio/ALSA):

```sh
cd "sistema operativo"
qemu-system-i386 -m 256M -vga std -cdrom sereos.iso \
  -audiodev pipewire,id=snd0 \
  -device sb16,audiodev=snd0
```

- Backend de audio: `pipewire`, `pa`, `alsa`, `sdl`, `oss`, `dsound`, `coreaudio`
  segun el sistema anfitrion. En un servidor sin servidor de sonido use
  `-audiodev none,id=snd0` (no oye nada, pero la deteccion y el WAV de
  verificacion siguen funcionando).
- `-device sb16` usa por defecto `iobase=0x220, irq=5, dma=1, dma16=5`, que es
  justo lo que espera el driver. Se puede forzar otro puerto base
  (`-device sb16,iobase=0x240,...`): SereOS escanea 0x220..0x280 de 0x10 en
  0x10.
- `-soundhw sb16` fue **eliminado** en QEMU 7; en versiones antiguas funciona
  como alias.

Solo altavoz del PC (fallback de SereOS, PCM no; tonos del PIT):

```sh
qemu-system-i386 -m 256M -vga std -cdrom sereos.iso \
  -audiodev pipewire,id=snd0 \
  -machine pc,pcspk-audiodev=snd0
```

Capture el audio a un WAV (verificacion automatica, sin tarjeta en el host):

```sh
qemu-system-i386 -m 256M -vga std -display none -cdrom sereos.iso \
  -audiodev wav,id=snd0,path=/tmp/sereos_audio.wav \
  -device sb16,audiodev=snd0
```

Con el sistema arrancado: F2 -> `audiotest` -> Enter. El log serie debe
mostrar `AUDIO_TEST:sb16` y `AUDIO_TEST_DONE tones=4 irq=4 ...`; el WAV debe
tener senal en 440/660/880/1320 Hz (ver `docs/evidence/audio/`).

### 1.2 QEMU antiguo (5.x, 6.x)

```sh
qemu-system-i386 -m 256M -vga std -cdrom sereos.iso \
  -soundhw sb16 \
  -audiodev pa,id=snd0        # opcional: backend de audio del host
```

`-soundhw pcspk` habilita el altavoz del PC en esas versiones. Si el backend
de audio del host falla, use `SDL_AUDIODRIVER=dummy` o `-audiodev none`.

### 1.3 Makefile del proyecto

```sh
make run              # QEMU sin tarjeta de sonido (solo fallback pcspk)
make run-audio        # QEMU + SB16 con PipeWire (por defecto)
make run-audio-wav    # headless + captura audio-capture.wav
```

Si PipeWire/PulseAudio no esta disponible en el host, `make run-audio` puede
fallar al crear el backend: en ese caso use `make run-audio-wav` (no necesita
servidor de sonido) o pase `AUDIODEV`:

```sh
make run-audio AUDIODEV="alsa,id=snd0"
make run-audio AUDIODEV="none,id=snd0"
```

---

## 2. VirtualBox

1. Con la VM apagada: **Configuracion -> Audio**.
2. Marque **Habilitar audio**.
3. **Controlador de audio: SoundBlaster 16**. Los controladores
   *Intel HD Audio* y *ICH AC'97* **no** son SB16: SereOS no los detecta y cae
   al altavoz del PC, que VirtualBox no enruta (silencio).
4. Salida de audio del anfitrion: el dispositivo por defecto (o el que use su
   sistema).
5. Arranque la ISO y compruebe en `dmesg`/Terminal: `[OK] Audio: SB16
   detectado en 0x220 IRQ5 DMA1`.

Si VirtualBox no muestra la opcion "SoundBlaster 16" (algunas versiones y
sistemas no la ofrecen), use QEMU con `-device sb16` para probar el audio.

Detalle tecnico: VirtualBox aplica el volumen del mixer del SB16 a partir de
los registros 0x30..0x33 (maestro izquierdo/derecho y voz izquierdo/derecho).
SereOS los programa a `0x00` = 0 dB (volumen maximo); en versiones anteriores
del driver se escribia `0xFF` en 0x04/0x22, que en una SB16 real es
atenuacion maxima (-62 dB, silencio).

---

## 3. VMware (Workstation/Player/ESXi)

VMware **no emula Sound Blaster 16** ni el altavoz del PC. La VM presenta
normalmente un controlador AC'97/HDA propietario que SereOS no soporta, por lo
que `audio_detail()` devolvera `"solo PC speaker"` y no se oira nada.

Opciones:
- usar QEMU (seccion 1) o VirtualBox con SB16 para la demostracion de audio;
- en hardware real, una SB16 ISA o una Sound Blaster compatible conectada a
  la maquina (ver seccion 4).

---

## 4. Hardware real (referencia)

- SB16 ISA con `iobase` en 0x220..0x280 (jumpers o PnP configurado), IRQ 5,
  DMA 8 bits 1 y DMA 16 bits 5.
- El driver programa el mixer a volumen maximo (0x00 en 0x04, 0x22 y
  0x30..0x33), activa el altavoz con `0xD1` y reproduce PCM u8 mono por DMA.
- El altavoz del PC funciona en placas con buzzer conectado al PIT canal 2;
  su volumen es fijo (no hay amplificador).

---

## 5. Diagnostico rapido

| Sintoma | Causa habitual | Solucion |
|---|---|---|
| `dmesg` dice `solo PC speaker` y no se oye | la VM no tiene SB16 (o tiene AC'97/HDA) | anada `-device sb16,audiodev=snd0` en QEMU o elija SoundBlaster 16 en VirtualBox |
| `dmesg` dice `SB16 0x220 ...` pero no se oye | backend de audio del host mal elegido / silenciado | pruebe otro `-audiodev` (`alsa`, `pa`, `sdl`) o `make run-audio-wav` y analice el WAV |
| `audiotest` muestra `irq=0` | la VM tiene el SB16 en otra IRQ distinta de 5 | el audio sigue funcionando (fin por tiempo), pero configure `irq=5` para la via IRQ |
| `audiotest` muestra `irq=4` y WAV con tonos | todo correcto | - |
| En VirtualBox con SB16 no se oye nada | controlador elegido distinto de SB16, o audio de la VM deshabilitado | revise Configuracion -> Audio |
| VMware | no hay SB16 | use QEMU/VirtualBox |

Comandos en SereOS (Terminal, F2):

```
audio                 # backend, detalle, PCM, IRQ y contadores
beep 880 200          # un tono por el backend activo
audiotest             # 440/660/880/1320 Hz + AUDIO_TEST y AUDIO_TEST_DONE por COM1
dmesg                 # linea "[OK] Audio: ..." del arranque
```

---

## 6. Verificacion realizada (evidencia)

Capturas y logs en `docs/evidence/audio/`; el script reproducible es
`docs/evidence/audio/verify_audio.py` (tambien en `build/qa_audio/`).

| Escenario | Comando QEMU | Resultado |
|---|---|---|
| A. SB16 + WAV | `-audiodev wav,id=snd0,path=A.wav -device sb16,audiodev=snd0` | `Audio: SB16 0x220 IRQ5 DMA1`; `AUDIO_TEST_DONE tones=4 irq=4 pit_hz=100`; WAV 0,788 s, peak -3,0 dBFS, RMS -3,4 dBFS, 440/660/880/1320 Hz detectados |
| B. Solo PC speaker | `-audiodev wav,... -machine pc,pcspk-audiodev=snd0` | `Audio: solo PC speaker`; `AUDIO_TEST:pcspk`; WAV 0,797 s con los 4 tonos (el PIT canal 2 suena); PIT sigue a 100 Hz |
| C. Sin dispositivos de audio | sin `-audiodev` ni `-device` | `solo PC speaker`, sin crash ni excepcion; `pit_hz=100` |
| D. SB16 en 0x240 | `-device sb16,iobase=0x240,...` | detectado en `0x240`; WAV con los 4 tonos y `irq=4` |
| E. SB16 con IRQ 7 (mismatch) | `-device sb16,irq=7,...` | audio correcto por fin por tiempo (`irq=0`, PIT 100 Hz), demostrando que la IRQ es solo una optimizacion |

QEMU 11.1.3, sin KVM (TCG), 256 MiB, `-vga std`. Los tonos del `audiotest`
se sintetizan con un oscilador DDS y se comparan con FFT: frecuencias medidas
441,7/658,3/883,3/1316,7 Hz (error < 0,5 % por la resolucion de la ventana).
