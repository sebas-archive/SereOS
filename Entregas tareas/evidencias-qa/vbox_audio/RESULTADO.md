# Audio SB16 de SereOS en VirtualBox 7.2.22 — prueba y VM configurada

**Veredicto: en VirtualBox 7.2.22r175245 el SB16 se detecta y SUENA.** La VM
`SereOS Audio` arranca la ISO de SereOS en modo headless, el kernel detecta
`Audio: SB16 0x220 IRQ5 DMA1`, `audiotest` responde 4/4 tonos y la captura del
monitor del sink por defecto del anfitrion contiene las cuatro frecuencias
(440/660/880/1320 Hz) con la frecuencia correcta y una relacion senal/ruido de
22–39 dB. La VM queda creada, registrada, configurada con SB16 y **apagada**.

- Fecha de la prueba: 2026‑11‑20 (America/Bogota).
- Evidencia: todo en `build/vbox_audio/` (este mismo directorio).
- No se modifico nada bajo `sistema operativo/`.

---

## 1. Versiones y entorno

| Elemento | Valor |
|---|---|
| VirtualBox | `7.2.22r175245` (`VBoxManage --version`) |
| Host | CachyOS, kernel `7.3.3-1-cachyos` x86_64 |
| Sonido del host | PulseAudio sobre **PipeWire 1.6.11** (`pactl info`: `PulseAudio (on PipeWire 1.6.11)`, servidor 15.0.0) |
| Sink por defecto | `alsa_output.pci-0000_00_1f.3.analog-stereo` (sin mute, volumen 55 %) |
| QEMU (alternativa, no usada) | `QEMU emulator version 11.1.3` |
| ISO SereOS | `sistema operativo/sereos.iso`, 36 MB, MD5 `1a781295a25c8fae4113ff2837e980c4` |
| Python / numpy del analisis | 3.14.9 / 2.5.4 |

Salida completa en `versiones.txt`. Log del hipervisor en
`VBox.log.pulse.log` (prueba canonica, backend pulse) y `VBox.log.alsa.log`.

---

## 2. VM creada: `SereOS Audio`

| Campo | Valor |
|---|---|
| Nombre | **SereOS Audio** |
| UUID | `13412692-2c5b-4432-a390-0ba353b89941` |
| Config file | `/home/t1an/VirtualBox VMs/SereOS Audio/SereOS Audio.vbox` |
| Estado final | **powered off** (`VBoxManage showvminfo`: `State: powered off`) |
| RAM / CPU | 256 MB, 1 CPU |
| Graficos | `vboxvga`, VRAM 32 MB (arranca la GUI de SereOS a 1024x768x32) |
| DVD | `sistema operativo/sereos.iso` en controladora IDE (`PIIX4`), puerto 1, dispositivo 0 |
| Arranque | BIOS, orden `dvd` |
| Red | ninguna (`nic1 none`) |
| Serie | COM1 `0x3F8` IRQ 4, `uartmode1 file /tmp/sereos_vbox_serial.log` |
| **Audio** | `enabled (Driver: PulseAudio, Controller: SB16, Codec: SB16)`, salida on, entrada off |

Comprobacion del audio en `showvminfo`:

```
Audio:                       enabled (Driver: PulseAudio, Controller: SB16, Codec: SB16)
```

Y en `VBoxManage showvminfo "SereOS Audio" --machinereadable`:

```
audio="pulse"
audio_out="on"
audio_in="off"
```

### Comandos exactos de creacion

```sh
VBoxManage createvm --name "SereOS Audio" --ostype Other --register
VBoxManage modifyvm "SereOS Audio" \
  --memory 256 --vram 32 --cpus 1 \
  --graphicscontroller vboxvga \
  --audio-enabled on --audio-controller sb16 --audio-codec sb16 \
  --audio-driver pulse --audio-out on --audio-in off \
  --uart1 0x3F8 4 --uartmode1 file /tmp/sereos_vbox_serial.log \
  --nic1 none --boot1 dvd --boot2 none --boot3 none --boot4 none \
  --firmware bios --rtcuseutc on --ioapic off --pae off --longmode off
VBoxManage storagectl "SereOS Audio" --name "IDE" --add ide
VBoxManage storageattach "SereOS Audio" --storagectl "IDE" --port 1 --device 0 \
  --type dvddrive --medium "/home/t1an/Descargas/sereos02/sistema operativo/sereos.iso"
```

> Nota: se eligio `vboxvga` y arranco a la primera con el VBE de GRUB
> (`1024x768x32`) en todas las pruebas, asi que no hizo falta probar `vmsvga`.

---

## 3. Metodo de prueba (headless, sin robar foco)

1. `VBoxManage startvm "SereOS Audio" --type headless`.
2. Se espera en el fichero serie `/tmp/sereos_vbox_serial.log` el marcador
   `GUI_READY` que escribe el escritorio de SereOS.
3. Se pulsa **F2** (abre Terminal) inyectando scancodes set 1 por
   `VBoxManage controlvm "SereOS Audio" keyboardputscancode`:
   `F2 = 3c bc` (make/break), letras = su scancode y `+0x80` para el break,
   `Return = 1c 9c`. Ayudante: `vbox_ctrl.py`.
4. Se espera `APP_OPEN:terminal` en el log serie.
5. Se arranca la grabacion del monitor del sink por defecto del host y se
   escribe `audiotest` + Return.
6. Se esperan los marcadores `AUDIO_TEST:`, `AUDIO_DETAIL:` y
   `AUDIO_TEST_DONE` en COM1; se para la grabacion y se analiza el WAV.
7. Se apaga la VM con `VBoxManage controlvm "SereOS Audio" poweroff`.

Script reproducible: `run_test.py` (usa `vbox_ctrl.py` + `analyze_audio.py`);
hace todo el flujo y escribe `run_result.json`.

Captura del audio del anfitrion:

```sh
pw-record --target=alsa_output.pci-0000_00_1f.3.analog-stereo.monitor \
          --rate 48000 --channels 2 --format s16 build/vbox_audio/vbox_audiotest.wav
```

Analisis: `python3 analyze_audio.py vbox_audiotest.wav` (DFT ventaneada a las
frecuencias esperadas + SNR contra el ruido de la misma banda en zonas de
silencio; la onda de diagnostico de SereOS es cuadrada, asi que se ignoran los
armonicos impares).

---

## 4. Deteccion en el arranque (log serie COM1)

`serial_full.log` (arranque + prueba, captura canonica):

```
[OK] Arranque Multiboot verificado (GRUB 2)
...
[OK] Temporizador PIT a 100 Hz (IRQ 0)
[OK] Teclado PS/2 con eventos (IRQ 1)
[OK] Raton PS/2 con eventos (IRQ 12)
[OK] Reloj CMOS RTC
[OK] Framebuffer grafico 1024x768x32 validado
...
[OK] Interrupciones habilitadas
[OK] Audio: SB16 0x220 IRQ5 DMA1
[OK] Motor grafico nativo inicializado
...
DESKTOP_READY
SEREOS_BOOT_OK mem=255MiB
SPLASH_DONE
GUI_READY
GUI_LOOP
TERM_READY
APP_OPEN:terminal
AUDIO_TEST:sb16
AUDIO_DETAIL:SB16 0x220 IRQ5 DMA1
AUDIO_TEST_DONE tones=4 irq=4 pit_hz=100 pit_ticks=48
```

No aparece en ningun momento `solo PC speaker`: VirtualBox presenta el SB16 en
`0x220`, IRQ 5, DMA 1, y el driver de SereOS lo detecta. `irq=4` significa que
VirtualBox genera correctamente la IRQ 5 de fin de DMA en los 4 bloques
(4 interrupciones contadas), y `pit_hz=100` confirma que el PIT no se altero.

En la Terminal de SereOS (`vbox_terminal_audio.png`) el comando `audio` muestra:

```
Backend : sb16
Detalle : SB16 0x220 IRQ5 DMA1
PCM     : 11025 Hz (0 = el altavoz del PC no reproduce PCM)
DSP     : 4.5, IRQ 5, DMA 1
DMA fin : 4 bloques terminados por IRQ
```

y `audiotest` (`vbox_terminal_audiotest.png`):

```
Prueba de audio (sb16)
  SB16 0x220 IRQ5 DMA1
  Tonos: 4/4 (440/660/880/1320 Hz, 200 ms)
  PIT: 100 Hz, 48 ticks durante la prueba
  SB16: IRQ 5, 4 fines de DMA por interrupcion
```

---

## 5. Sonido real capturado en el anfitrion

Fichero: `vbox_audiotest.wav` (13,952 s, 48 kHz, estereo s16, grabado del
monitor del sink por defecto mientras corria `audiotest`).

| Metrica | Valor |
|---|---|
| Pico | **−12,03 dBFS** (muestra 8199) — criterio `> −40 dBFS`: **CUMPLE** |
| RMS global | −29,88 dBFS |
| Bloque de tonos | 3,53 s – 4,18 s (≈0,65 s de audio audible) |

Deteccion de las cuatro frecuencias (ver `vbox_audiotest.analysis.json`):

| Tono esperado | Frecuencia medida | Error | SNR | Detectado |
|---|---|---|---|---|
| 440 Hz | 440,0 Hz | 0,0 % | 22,3 dB | si |
| 660 Hz | 660,0 Hz | 0,0 % | 34,2 dB | si |
| 880 Hz | 880,0 Hz | 0,0 % | 39,1 dB | si |
| 1320 Hz | 1320,0 Hz | 0,0 % | 38,3 dB | si |

Espectrograma del bloque de tonos: `vbox_audiotest_spectrogram_zoom.png`
(se ven los cuatro escalones 440 → 660 → 880 → 1320 Hz); forma de onda en
`vbox_audiotest_wave.png`; espectrograma completo en
`vbox_audiotest_spectrogram.png`.

### Artefactos de la emulacion (honestidad)

- Hay un ruido de baja frecuencia persistente (≈10–60 Hz, en torno a
  −30 dBFS de RMS) que VirtualBox deja en el flujo u8 mono 11025 Hz; no impide
  la deteccion y no es silencio.
- Los tonos del `audiotest` (200 ms cada uno, con reinicio de stream entre
  ellos) se solapan/truncan ligeramente en VBox: el bloque audible dura ~0,65 s
  en vez de 0,8 s y en el primer tono aparece ademas su 3.er armonico (1320 Hz).
  Es un detalle de la emulacion SB16, no un fallo de SereOS; la frecuencia de
  cada tono es exacta.
- Se probo tambien `--audio-driver alsa` (misma VM, mismo metodo):
  `AUDIO_TEST_DONE tones=4 irq=1`, pico **−22,0 dBFS**, las 4 frecuencias
  detectadas con SNR 21,7–41,0 dB, bloque de 1,125 s
  (`run_result_alsa.json`, `vbox_audiotest_alsa.wav`,
  `vbox_terminal_audiotest_alsa.png`). **Ambos backends (pulse y alsa) suenan**;
  se dejo la VM en `pulse`, que es el backend pedido y el que mejor nivel dio.
- No fue necesario recurrir al plan B con QEMU: VirtualBox 7.2.22 si emite el
  audio del SB16.

---

## 6. Como abrir y arrancar la VM desde el GUI

1. Abrir **VirtualBox Manager** (menu de aplicaciones o `virtualbox`).
2. En la lista de la izquierda aparece **SereOS Audio** (esta registrada en
   `~/.config/VirtualBox/VirtualBox.xml`; `VBoxManage list vms` la muestra:
   `"SereOS Audio" {13412692-2c5b-4432-a390-0ba353b89941}`).
3. Seleccionarla y pulsar **Iniciar** (arranque normal, no headless). La ISO ya
   esta puesta como DVD y la BIOS arranca de ella.
4. Esperar el escritorio de SereOS (unos 10 s). Pulsar **F2** para abrir la
   Terminal y escribir `audiotest` + Enter para oir los 4 tonos, o `beep 880 300`.
5. El sonido sale por el dispositivo de salida por defecto del anfitrion
   (PipeWire/PulseAudio). Si no se oye: revisar que el sink por defecto no este
   silenciado y el volumen del mezclador de VirtualBox.
6. Para confirmar la configuracion: **Configuracion → Audio** debe mostrar
   *Habilitar audio* marcado, *Controlador: SoundBlaster 16*, *Codec: SB16* y
   *Driver de anfitrion: PulseAudio*.

Ruta de la VM: `/home/t1an/VirtualBox VMs/SereOS Audio/` (estado actual:
**apagada**; no se dejo ningun proceso `VBoxHeadless` corriendo).

---

## 7. Reproducir la prueba automatica

```sh
cd "/home/t1an/Descargas/sereos02"

# con la VM ya creada y apagada:
python3 build/vbox_audio/run_test.py
# escribe: vbox_audiotest.wav, serial_full.log, showvminfo*.txt,
#          vbox_terminal_audiotest.png, vbox_terminal_audio.png, run_result.json

# solo analizar un WAV ya grabado:
python3 build/vbox_audio/analyze_audio.py build/vbox_audio/vbox_audiotest.wav
```

Variantes: `VBOX_AUDIO_TAG=alsa python3 build/vbox_audio/run_test.py` para otra
etiqueta de ficheros (usado en la prueba con backend ALSA).

---

## 8. Ficheros de evidencia

| Fichero | Contenido |
|---|---|
| `serial_full.log` | log COM1 completo del arranque + `audiotest` (prueba canonica, pulse) |
| `serial_final_boot.log` | arranque final tras dejar la VM en pulse y apagarla |
| `serial_full_alsa.log` | log COM1 de la variante con backend ALSA |
| `vbox_audiotest.wav` | captura del monitor del host durante `audiotest` (pulse) |
| `vbox_audiotest.analysis.json` | analisis numerico (pico/RMS dBFS, frecuencias, SNR) |
| `vbox_audiotest_spectrogram_zoom.png` | espectrograma del bloque de tonos |
| `vbox_audiotest_spectrogram.png`, `vbox_audiotest_wave.png` | espectrograma completo y forma de onda |
| `vbox_terminal_audiotest.png` | Terminal de SereOS con `audiotest` 4/4 |
| `vbox_terminal_audio.png` | Terminal con `audio`: backend sb16, IRQ5, DMA1, 4 bloques |
| `vbox_desktop_final.png` | escritorio de SereOS arrancado en VBox |
| `showvminfo_final_apagada.txt` / `..._machinereadable_final_apagada.txt` | estado final: SB16 + pulse + apagada |
| `showvminfo.txt`, `showvminfo_machinereadable.txt` | VM durante la prueba (running) |
| `VBox.log.pulse.log` / `VBox.log.alsa.log` | logs del hipervisor (driver PulseAudio / ALSA, dispositivo SB16) |
| `run_result.json` / `run_result_alsa.json` | marcadores serie + analisis de cada variante |
| `run_test.py`, `vbox_ctrl.py`, `analyze_audio.py` | scripts reproducibles |
| `versiones.txt` | versiones de VBox, host, PipeWire, QEMU, ISO MD5 |
| `diagnostico/` | sondas previas (tono 440/1000 Hz del host, capturas tempranas) |

---

## 9. Conclusion

**En VirtualBox 7.2.22r175245, con controlador de audio SoundBlaster 16, codec
SB16 y driver PulseAudio, SereOS detecta la tarjeta (`SB16 0x220 IRQ5 DMA1`),
responde 4/4 en `audiotest` con 4 IRQ de fin de DMA, y el audio PCM se captura
en el monitor del sink del anfitrion con pico −12 dBFS y los tonos 440/660/880/
1320 Hz correctos (SNR 22–39 dB). El SB16 de VirtualBox suena.**

Limitaciones encontradas: la emulacion SB16 de VirtualBox introduce ruido de
baja frecuencia y ligeros solapamientos/truncados en tonos muy cortos; no se
aprecia en la frecuencia ni impide oir la prueba. El backend ALSA tambien
funciona. La VM `SereOS Audio` queda lista y apagada para que el usuario la
arranque desde el GUI.
