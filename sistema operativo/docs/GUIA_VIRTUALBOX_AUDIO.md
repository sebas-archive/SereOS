# Guía: configurar Oracle VirtualBox para oír SereOS por los altavoces

Respuesta corta: dale a la máquina virtual una **Sound Blaster 16** (SB16) y
activa la **salida de audio**. SereOS detecta el SB16 en `0x220`, IRQ 5, DMA 1
y reproduce PCM por ahí, así que VirtualBox lo mezcla en el sonido del host
(PipeWire/PulseAudio) y lo oyes por los altavoces. Los controladores
**ICH AC'97** e **Intel HD Audio** *no* sirven: SereOS no los reconoce y cae al
altavoz del PC, que VirtualBox no enruta → silencio.

Esta guía se ha comprobado con **VirtualBox 7.2.22r175245** en este equipo
(CachyOS + KDE Plasma Wayland + PipeWire 1.6.11). En otras versiones los
nombres de los menús pueden variar ligeramente; los valores de la CLI son los
mismos. En este equipo la prueba práctica ya está hecha y el resultado está en
la sección 7.

> **Atajo:** en este equipo ya existe la VM **`SereOS Audio`**, configurada con
> SB16 + PulseAudio y apagada. Abre VirtualBox Manager, selecciónala y pulsa
> **Iniciar**; después, en SereOS, pulsa **F2** y ejecuta `audiotest`.

---

## 0. Resumen en 4 pasos

1. **Apaga la VM** (no vale pausarla ni guardarla; los cambios de hardware de
   audio solo se aplican con la máquina apagada).
2. **Configuración → Audio**: marca **Habilitar audio**, pon
   **Controlador de audio = SoundBlaster 16** y
   **Controlador de audio anfitrión = PulseAudio**; comprueba que la
   **salida de audio** está activada.
3. Arranca la ISO de SereOS.
4. Dentro de SereOS pulsa **F2** (Terminal) y ejecuta `dmesg`; debe aparecer
   `[OK] Audio: SB16 0x220 IRQ5 DMA1`. Si aparece `[OK] Audio: solo PC speaker`,
   no habrá sonido real en VirtualBox.

---

## 1. Antes de empezar

- **Versión de VirtualBox:** se ha probado con `7.2.22r175245`. Comprueba la
  tuya con `VBoxManage --version`.
- **La VM debe estar apagada.** En VirtualBox la configuración de hardware
  (controlador de audio incluido) está deshabilitada mientras la máquina está
  encendida, en pausa o guardada. Si ya está arrancada, apágala desde el menú
  de la ventana o con
  `VBoxManage controlvm "NOMBRE" poweroff`.
- **ISO del proyecto:** `sistema operativo/sereos.iso` (o la que hayas
  compilado con `make`).
- Si aún no tienes la VM: VirtualBox Manager → **Nueva**, tipo
  *Other/Unknown (32-bit)*, 256 MB de RAM, **sin disco duro**, y en
  **Almacenamiento** monta la ISO en la unidad óptica. SereOS usa RAMFS y
  arranca por BIOS/GRUB (no hace falta activar EFI ni Guest Additions).
- No hace falta instalar ningún driver en SereOS: su kernel habla directamente
  con la SB16 emulada de VirtualBox.

---

## 2. Pasos por la interfaz gráfica (VirtualBox 7.2)

Los nombres se dan en español y, entre paréntesis, en inglés.

1. Abre **VirtualBox** (menú de aplicaciones o comando `virtualbox`).
2. Selecciona la VM de SereOS en la lista de la izquierda, **sin arrancarla**.
3. Pulsa **Configuración** (Settings) — el botón de la barra superior o
   *Máquina → Configuración*.
4. En la lista lateral elige **Audio**.
5. Marca la casilla **Habilitar audio** (*Enable Audio*). Si estaba
   desmarcada, este solo paso ya explica el silencio.
6. En **Controlador de audio anfitrión** (*Host Audio Driver*) elige
   **PulseAudio**. En este equipo PipeWire 1.6.11 expone una API PulseAudio
   compatible, así que es la opción correcta. Alternativas:
   - **Default** (suele resolver a PulseAudio solo),
   - **Audio ALSA** (*ALSA Audio*) si PulseAudio falla; con PipeWire también
     funciona a través de `pipewire-alsa`.
7. En **Controlador de Audio** (*Audio Controller*) elige
   **SoundBlaster 16**. **No** elijas *ICH AC'97* ni *Intel HD Audio*: si lo
   haces, SereOS arranca en modo `solo PC speaker` y no oirás nada.
8. Activa la **salida de audio**. En VirtualBox 7.2 la entrada y la salida se
   controlan por separado y, de hecho, **una VM recién creada tiene la
   reproducción desactivada aunque el audio figure como "habilitado"**.
   - En la misma página, grupo **Características** (*Features*), comprueba que
     **Salida de audio** (*Audio Output*) está marcada.
   - Si no ves esa casilla ahí: con la VM encendida está en el menú
     **Dispositivos → Audio → Salida de audio** (*Devices → Audio → Audio
     Output*), que se puede activar en caliente.
   - Equivale a `--audio-out on` por CLI (sección 3).
9. Pulsa **Aceptar/OK** y arranca la VM.

### Sobre el "Códec de audio"

En la build **7.2.22** de este equipo la página **Audio** *no* muestra un
desplegable de códec (solo *Habilitar audio*, *Controlador de Audio
Anfitrión*, *Controlador de Audio* y *Características*). No es un problema:
el códec va implícito en el controlador y, al elegir **SoundBlaster 16**,
VirtualBox fija **Códec: SB16** automáticamente (verificado con
`VBoxManage showvminfo`, sección 3). Si quieres dejarlo escrito de forma
explícita, usa la CLI `--audio-codec sb16`; es válida y redundante con SB16.

### "Salida de audio = altavoces/salida por defecto"

VirtualBox 7.2 no tiene un selector de dispositivo de salida del host: envía
el audio de la VM al **sink por defecto de PipeWire/PulseAudio**. Para
cambiarlo al dispositivo que quieras (altavoces, auriculares, HDMI…) se
cambia en el host, no en VirtualBox:

```sh
pactl get-default-sink                 # sink por defecto actual
pactl list short sinks                 # todos los sinks disponibles
pactl set-default-sink NOMBRE_DEL_SINK # p. ej. alsa_output...analog-stereo
pavucontrol &                          # o elige "Altavoces" en la pestaña Salida
```

Dentro de `pavucontrol` (pestaña **Reproducción**) verás el flujo de
VirtualBox y podrás mandarlo a otro dispositivo y subirle el volumen.

---

## 3. Equivalentes por línea de comandos (copiar y pegar)

Con la VM **apagada**:

```sh
VM="SereOS Audio"

# Configuración recomendada (SB16 + salida de audio por PulseAudio)
VBoxManage modifyvm "$VM" \
  --audio-enabled on \
  --audio-controller sb16 \
  --audio-codec sb16 \
  --audio-driver pulse \
  --audio-out on \
  --audio-in on
```

Notas:

- `--audio-driver pulse` es el backend PulseAudio (PipeWire en este equipo).
  Alternativas válidas en este host, comprobadas con
  `VBoxManage modifyvm --help`:
  - `--audio-driver alsa` (si PulseAudio falla),
  - `--audio-driver default` (deja que VirtualBox elija; en esta build
    aparece como *Driver: Default*),
  - `--audio-driver none` no sirve para oír nada (solo para pruebas).
- `--audio-controller` solo admite `ac97 | hda | sb16`; para SereOS **sb16**.
- `--audio-codec` solo admite `stac9700 | ad1980 | stac9221 | sb16`. El
  controlador manda: `ac97` acepta `stac9700`/`ad1980`, `hda` acepta
  `stac9221` y `sb16` acepta `sb16`. Si pones un códec incompatible,
  VBoxManage da error. Con `--audio-controller sb16` el códec SB16 se
  selecciona solo, así que `--audio-codec sb16` es opcional pero explícito.
- `--audio-in on` activa la entrada de audio (micrófono). SereOS no graba
  audio, así que puedes ponerlo en `on` o `off`; para escuchar solo importa
  `--audio-out on`.

### Comprobar que quedó bien configurada

```sh
VBoxManage showvminfo "$VM" | grep -E '^Audio'
```

Salida esperada en este equipo (VirtualBox 7.2.22):

```
Audio:                       enabled (Driver: PulseAudio, Controller: SB16, Codec: SB16)
Audio playback:              enabled
Audio capture:               enabled
```

(Si pusiste `--audio-in off`, la última línea dirá `disabled`; no afecta al
sonido de salida, que es lo que importa para escuchar.)

> **Ojo con el comando que suele circular:**
> `VBoxManage showvminfo "$VM" --machinereadable | grep -i '^audio'` es útil,
> pero **en 7.2.22 no muestra el controlador ni el códec**, solo el driver y
> los interruptores:
>
> ```
> audio="pulse"
> audio_out="on"
> audio_in="on"
> ```
>
> Por eso, para verificar el controlador hay que usar `showvminfo` normal
> (sin `--machinereadable`) y mirar la línea `Audio: ...`. Los valores
> `audio_out`/`audio_in` sí son fiables para saber si la reproducción está
> activada.

### Si algo sale mal por CLI

- Error `Invalid --audiocontroller argument` / `Invalid --audio-driver
  argument` / `Invalid --audiocodec argument`: revisa la ortografía del valor
  (minúsculas) o consulta `VBoxManage modifyvm --help`.
- Error al modificar una VM encendida: apágala primero
  (`VBoxManage controlvm "$VM" poweroff`).
- Para deshacer: `VBoxManage modifyvm "$VM" --audio-enabled off`.

---

## 4. Comprobar el audio dentro de SereOS

Arranca la VM, espera al escritorio de SereOS y pulsa **F2** para abrir la
**Terminal**. Atajos: F1 Archivos, F2 Terminal, F3 Monitor.

### 4.1 `dmesg` — lo primero que hay que mirar

```text
dmesg
```

Busca la línea del arranque:

- ✅ Correcto (hay SB16 y, con la configuración de esta guía, sonido real):

  ```text
  [OK] Audio: SB16 0x220 IRQ5 DMA1
  ```

- ❌ Sin SB16 (VirtualBox no enruta el altavoz del PC: no se oirá nada):

  ```text
  [OK] Audio: solo PC speaker
  ```

Si sale `solo PC speaker`, vuelve a la sección 2: el controlador no es
SoundBlaster 16, o la VM no tiene audio, o la salida está desactivada.

### 4.2 `audio` — estado y detalle real

```text
audio
```

Salida esperada con todo bien (los valores de SFX/DSP varían):

```text
Audio de SereOS
  Backend : sb16
  Detalle : SB16 0x220 IRQ5 DMA1
  PCM     : 11025 Hz (0 = el altavoz del PC no reproduce PCM)
  SFX     : 0 reproducciones, 0 descartadas
  DSP     : 4.5, IRQ 5, DMA 1
  DMA fin : 0 bloques terminados por IRQ
  Pruebas : beep [hz] [ms]  |  audiotest
```

Si `Backend` es `pcspk` y `Detalle` es `solo PC speaker`, SereOS no ve la SB16
y `PCM: 0 Hz`.

### 4.3 `beep` y `audiotest` — prueba de sonido

```text
beep 880 200
```

Debe sonar un tono de 880 Hz durante 200 ms por el SB16. Luego:

```text
audiotest
```

Reproduce 440/660/880/1320 Hz, 200 ms cada uno, y deja marcas en el puerto
serie COM1. En pantalla debe verse algo como:

```text
Prueba de audio (sb16)
  SB16 0x220 IRQ5 DMA1
  Tonos: 4/4 (440/660/880/1320 Hz, 200 ms)
  PIT: 100 Hz, N ticks durante la prueba
  SB16: IRQ 5, 4 fines de DMA por interrupcion
```

Señales de que todo va bien:

- `Tonos: 4/4`;
- `SB16: IRQ 5, 4 fines de DMA por interrupcion`: la IRQ 5 del SB16 está
  funcionando de verdad (4 tonos = 4 interrupciones);
- el PIT sigue a `100 Hz` (el altavoz del PC no ha estorbado al reloj).

Con la VM configurada de forma headless y salida serie a fichero puedes
comprobar lo mismo desde el host:

```sh
VBoxManage startvm "SereOS Audio" --type headless
tail -f /tmp/sereos_vbox_serial.log   # si arrancaste con --uartmode1 file:...
# busca: Audio: SB16 0x220 IRQ5 DMA1 / AUDIO_TEST:sb16 / AUDIO_TEST_DONE tones=4
```

---

## 5. Diagnóstico y problemas frecuentes

### 5.1 El host está silenciado o en el sink equivocado

VirtualBox mezcla el audio de la VM en el host; si el host está silenciado,
no se oye nada aunque la VM esté perfecta.

```sh
pactl info                            # servidor: PipeWire/PulseAudio
pactl get-default-sink                # sink activo
pactl list short sinks                # sinks disponibles
wpctl get-volume @DEFAULT_AUDIO_SINK@ # p. ej. "Volume: 0.55"; si dice [MUTED]...
wpctl set-mute   @DEFAULT_AUDIO_SINK@ 0
wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.8
pavucontrol &                         # revisar pestañas Salida / Reproducción
```

Mientras SereOS suena, este comando debe mostrar un flujo de VirtualBox:

```sh
pactl list short sink-inputs
# ejemplo en este host: ... PipeWire u8 1ch 11025Hz   <- PCM mono de SereOS
```

Si aparece el flujo pero no oyes: sube el volumen en `pavucontrol`
(pestaña Reproducción, VirtualBox) y comprueba que la salida no está muteada.
Si no aparece ningún flujo, el problema está dentro de la VM (controlador o
salida de audio desactivada).

### 5.2 La VM tiene audio "habilitado" pero la reproducción desactivada

En VirtualBox 7.2 una VM nueva arranca con la **reproducción desactivada**.
Compruébalo:

```sh
VBoxManage showvminfo "SereOS Audio" | grep -E '^Audio'
# Audio playback: disabled  -> no sonará nada
VBoxManage modifyvm "SereOS Audio" --audio-out on   # VM apagada
```

En la GUI equivale a marcar **Salida de audio** en *Configuración → Audio →
Características*, o *Dispositivos → Audio → Salida de audio* con la VM
encendida.

### 5.3 Controlador equivocado (AC'97 / Intel HD Audio)

SereOS solo entiende **SB16** (o el altavoz del PC). Si la VM presenta
AC'97 o HDA, `dmesg` dirá `solo PC speaker` y no oirás nada. Cambia el
controlador a **SoundBlaster 16** con la VM apagada.

### 5.4 Cambias los ajustes con la VM encendida

Los cambios de **controlador de audio** y de **driver del host** no se
aplican en caliente: apaga la VM, cámbialos y vuelve a arrancar. Solo la
entrada/salida de audio (los interruptores) se puede tocar en marcha.

### 5.5 VirtualBox 7.2 no ofrece SoundBlaster 16 o no suena

En la build 7.2.22 el SB16 sí está disponible y **se ha verificado que suena**
con `pulse` y con `alsa` (sección 7). Si tu versión no ofrece SB16, o si tras
configurarlo no hay forma de oírlo, usa **QEMU**, que es la vía recomendada por
el proyecto y está verificada con capturas de audio:

```sh
cd "sistema operativo"
make run-audio
```

o el comando manual (equivalente):

```sh
cd "sistema operativo"
qemu-system-i386 -m 256M -vga std -cdrom sereos.iso \
  -audiodev pipewire,id=snd0 \
  -device sb16,audiodev=snd0
```

- En modo headless, graba el audio a un WAV y compruébalo sin tarjeta:

  ```sh
  make run-audio-wav        # genera audio-capture.wav
  # o manual:
  qemu-system-i386 -m 256M -vga std -display none -cdrom sereos.iso \
    -audiodev wav,id=snd0,path=/tmp/sereos_audio.wav \
    -device sb16,audiodev=snd0
  ```

- Si PipeWire/PulseAudio no está disponible:
  `make run-audio AUDIODEV="alsa,id=snd0"`.
- No uses máquina `q35`: no tiene bus ISA y `-device sb16` falla; usa la
  `pc`/i440fx por defecto.
- Detalles y evidencia: [AUDIO_VM.md](AUDIO_VM.md) secciones 1 y 6;
  [README.md](../../README.md) sección «Audio en QEMU: que suene de verdad».

### 5.6 VMware

VMware **no emula Sound Blaster 16** ni enruta el altavoz del PC. Con VMware
SereOS arrancará en `solo PC speaker` y no se oirá nada. Usa VirtualBox con
SB16 (esta guía) o QEMU.

---

## 6. Tabla síntoma → causa → solución

| Síntoma | Causa habitual | Solución |
|---|---|---|
| `dmesg` dice `[OK] Audio: solo PC speaker` y no se oye nada | la VM no tiene SB16 (tiene AC'97/HDA) o el audio está deshabilitado | Configuración → Audio → **SoundBlaster 16** + **Habilitar audio**, con la VM apagada |
| `dmesg` dice `SB16 0x220 IRQ5 DMA1` pero no se oye | host silenciado / sink equivocado / salida de audio de la VM desactivada | Revisa `wpctl get-volume @DEFAULT_AUDIO_SINK@`, `pavucontrol`, y pon `--audio-out on` |
| `VBoxManage showvminfo` muestra `Audio playback: disabled` | VM creada con la reproducción desactivada (comportamiento por defecto en 7.2) | `VBoxManage modifyvm "NOMBRE" --audio-out on` (VM apagada) o *Dispositivos → Audio → Salida de audio* |
| La opción **SoundBlaster 16** no aparece en la GUI | versión de VirtualBox antigua o distinta build | Actualiza VirtualBox o fija el controlador por CLI; si no, usa QEMU (`make run-audio`) |
| Cambio el controlador con la VM encendida y no se aplica | VirtualBox no permite cambiar hardware de audio en caliente | Apaga la VM, cambia y arranca |
| `beep`/`audiotest` no se oyen pero `audio` dice `sb16` | flujo de VirtualBox muteado o en otro sink en `pavucontrol` | Pestaña Reproducción de `pavucontrol`: elige el dispositivo correcto y sube el volumen |
| `audiotest` suena entrecortado o con clics | carga de CPU del host (emulación sin aceleración) | Cierra aplicaciones pesadas; en QEMU usa KVM si `/dev/kvm` es accesible |
| Solo se oyen pitidos tipo PC speaker (no el PCM del juego) | SereOS está en backend `pcspk`; el PCM de 11025 Hz requiere SB16 | Corrige el controlador de audio de la VM a SB16 |
| Se oye un ruido grave de fondo y/o los tonos cortos se solapan un poco | artefacto de la emulación SB16 de VirtualBox (no es fallo de SereOS) | normal: la frecuencia de cada tono es exacta; para una demo limpia usa QEMU con `-device sb16` (sección 5.5) |
| Con VMware no hay sonido | VMware no emula SB16 | Usa VirtualBox con SB16 o QEMU |
| `VBoxManage` da `Invalid --audiocontroller argument` | valor mal escrito | Usa `sb16`; ver `VBoxManage modifyvm --help` |

---

## 7. Resultado medido en este equipo

**Sí funciona: en VirtualBox 7.2.22r175245 el SB16 de SereOS se detecta y
suena.** Verificación empírica realizada el 2026-11-20 en este equipo
(CachyOS + PipeWire 1.6.11), con el dictamen completo y los comandos exactos en
[`Entregas tareas/evidencias-qa/vbox_audio/RESULTADO.md`](../../Entregas tareas/evidencias-qa/vbox_audio/RESULTADO.md).

### 7.1 Veredicto y configuración medida

Con **Driver: PulseAudio, Controller: SB16, Codec: SB16** y salida de audio
activada:

```text
Audio:                       enabled (Driver: PulseAudio, Controller: SB16, Codec: SB16)
Audio playback:              enabled
```

- El log serie COM1 del arranque contiene `[OK] Audio: SB16 0x220 IRQ5 DMA1`
  y **en ningún momento** aparece `solo PC speaker`.
- `audiotest` responde `AUDIO_TEST:sb16` y
  `AUDIO_TEST_DONE tones=4 irq=4 pit_hz=100`: los 4 tonos suenan y las 4 IRQ
  de fin de DMA del SB16 se generan correctamente.
- La captura del monitor del sink por defecto del host contiene los cuatro
  tonos del `audiotest` con la frecuencia exacta:

  | Tono esperado | Frecuencia medida | SNR |
  |---|---|---|
  | 440 Hz | 440,0 Hz | 22,3 dB |
  | 660 Hz | 660,0 Hz | 34,2 dB |
  | 880 Hz | 880,0 Hz | 39,1 dB |
  | 1320 Hz | 1320,0 Hz | 38,3 dB |

  Pico de la captura: **−12,03 dBFS** (RMS global −29,88 dBFS), con el sink
  por defecto del host sin mute y a 55 % de volumen. Es decir: el flujo llega
  al anfitrión y es audible.

- La VM queda creada, registrada y **apagada** con esta configuración:
  **`SereOS Audio`** (`/home/t1an/VirtualBox VMs/SereOS Audio/`). Puedes
  abrirla desde VirtualBox Manager y arrancarla directamente; ya tiene la ISO
  montada y el audio SB16 listo.
- También se probó `--audio-driver alsa` con la misma VM: **también suena**
  (`AUDIO_TEST_DONE tones=4 irq=1`, pico −22,0 dBFS, los 4 tonos detectados).
  Se dejó configurado `pulse`, que es el backend recomendado en este host.

### 7.2 Artefactos de la emulación (no son fallos de SereOS)

- Hay un ruido grave de baja frecuencia (≈10–60 Hz) en el flujo u8 mono de
  VirtualBox; no impide oír los efectos ni la detección.
- Los tonos muy cortos (200 ms del `audiotest`) se solapan/truncan un poco
  dentro de VirtualBox: el bloque audible dura ~0,65 s en vez de 0,8 s y el
  primer tono arrastra su 3.er armónico. La **frecuencia de cada tono es
  exacta**; si estos artefactos te molestan para una demostración, usa QEMU
  con `-device sb16` (sección 5.5).

### 7.3 Evidencia

- Dictamen completo y comandos reproducibles:
  [`Entregas tareas/evidencias-qa/vbox_audio/RESULTADO.md`](../../Entregas tareas/evidencias-qa/vbox_audio/RESULTADO.md)
- Log serie del arranque + prueba:
  [`serial_full.log`](../../Entregas tareas/evidencias-qa/vbox_audio/serial_full.log)
- Captura del monitor del host durante `audiotest`:
  [`vbox_audiotest.wav`](../../Entregas tareas/evidencias-qa/vbox_audio/vbox_audiotest.wav) y su
  análisis numérico
  [`vbox_audiotest.analysis.json`](../../Entregas tareas/evidencias-qa/vbox_audio/vbox_audiotest.analysis.json)
- Espectrograma del bloque de tonos (440 → 660 → 880 → 1320 Hz):
  [`vbox_audiotest_spectrogram_zoom.png`](../../Entregas tareas/evidencias-qa/vbox_audio/vbox_audiotest_spectrogram_zoom.png)
- Terminal de SereOS con `audiotest` 4/4:
  [`vbox_terminal_audiotest.png`](../../Entregas tareas/evidencias-qa/vbox_audio/vbox_terminal_audiotest.png)
- Estado final de la VM (SB16 + pulse + apagada):
  [`showvminfo_final_apagada.txt`](../../Entregas tareas/evidencias-qa/vbox_audio/showvminfo_final_apagada.txt)
- Variante con backend ALSA:
  [`run_result_alsa.json`](../../Entregas tareas/evidencias-qa/vbox_audio/run_result_alsa.json)

---

## 8. Referencias del proyecto

- [AUDIO_VM.md](AUDIO_VM.md) — audio en máquinas virtuales (QEMU/VirtualBox/VMware), diagnóstico y evidencia verificada.
- [AUDIO.md](AUDIO.md) — arquitectura del subsistema de audio de SereOS (SB16 + PC speaker).
- [RUN.md](RUN.md) — cómo arrancar y probar SereOS; atajos F1–F7.
- [README.md](../../README.md) — sección «Audio en QEMU: que suene de verdad».
- Evidencia de audio del proyecto: [`evidence/audio/`](evidence/audio/).
