# Limitaciones conocidas de SereOS v1.0

Documento honesto de lo que SereOS **no** hace o hace con restricciones. Nada
de esta lista está oculto en la documentación de funcionalidades
([FEATURES.md](FEATURES.md)).

## Modelo de ejecución y protección

* **Multitarea cooperativa, no preemptiva.** No hay cambio de pila ni de
  contexto: cada tarea es una función que ejecuta un paso corto desde el bucle
  del escritorio (`scheduler_tick()`). Una tarea que se bloquee o tarde
  demasiado congela la interfaz; no hay aislamiento temporal ni prioridades.
* **No hay espacio de usuario ni syscalls.** Aunque la GDT define descriptores
  de anillo 3, ningún proceso se ejecuta en anillo 3: kernel y aplicaciones
  comparten el mismo espacio y privilegios. Un fallo de una app puede tumbar
  todo el sistema (no hay *fault isolation*).
* **Sin protección de memoria entre apps.** La paginación es de identidad
  (virtual = física) y no crea espacios de direcciones separados ni páginas de
  solo lectura/NX. No es un sistema multiusuario ni seguro frente a código
  malicioso.
* **Un solo núcleo (SMP no soportado)**, sin APIC ni ACPI; se usan las
  interrupciones legacy (PIC 8259) y no hay gestión de energía ni apagado por
  ACPI. Para apagar la máquina hay que cerrar QEMU.
* **Sin FPU/SIMD**: el kernel y las apps se compilan con `-mno-sse -mno-mmx
  -mno-sse2`; las matemáticas con decimales se hacen con punto fijo (el juego
  usa Q8.8). No hay coma flotante hardware.

## Memoria

* Heap del kernel **estático de 8 MiB** (arena en `.bss`) con *first-fit*: no
  crece ni se compacta; puede fragmentarse.
* La identidad de paginación con PSE cubre hasta **512 MiB**; por encima de ese
  límite no se mapea (se arranca con 256 MiB).
* El allocator de marcos usa el mapa de memoria de Multiboot y no conoce
  huecos reservados por el firmware más allá de lo que reporta GRUB.
* Sin swap, sin memoria virtual bajo demanda, sin `mmap` de usuario.

## Sistema de archivos

* **RAMFS volátil**: todo se pierde al apagar o reiniciar. No hay disco, ni
  particiones, ni sistema de archivos persistente (no hay driver ATA/AHCI/USB).
* Límites fijos: **64 nodos**, **1024 bytes por archivo**, nombres de 28
  caracteres, rutas de 128 caracteres. No hay enlaces, permisos, marcas de
  tiempo ni archivos grandes.
* No hay caché en disco ni journaling (no aplica al ser RAM).

## Entrada/salida y periféricos

* **Sin red** de ningún tipo (ni Ethernet ni Wi-Fi).
* **Sin USB**: teclado y ratón son PS/2 emulados por QEMU; en hardware real sin
  puerto PS/2 no habría entrada (el sistema avisa y el escritorio sigue siendo
  navegable por teclado, pero no se probó en hardware físico).
* **Ratón PS/2 relativo**: no hay tableta absoluta ni soporte de ratón USB. Las
  pruebas automatizadas usan atajos de teclado; el movimiento/clic por QMP es
  *best-effort*.
* **Audio limitado a efectos 8 bits mono**: el driver de Sound Blaster 16 usa
  PCM de 8 bits y un solo canal (sin mezcla ni streaming de música). Si no hay
  tarjeta se cae al PC speaker (tonos cuadrados) o a silencio. Depende del
  backend de audio de QEMU/anfitrión: con `make run-audio-wav` se verifica de
  forma objetiva, pero en hardware real puede requerir IRQ/DMA distintos.
* **Serie solo COM1** y a 38400 baudios; es el canal de diagnóstico/pruebas.
* No hay impresoras, ni temporizadores de alta resolución (PIT a 100 Hz).

## Gráficos

* **Renderizado por software**: se compone en un *backbuffer* y se copia al
  framebuffer; no hay aceleración 2D/3D (GPU, VBE en modo protegido ni
  virtio-gpu).
* Resolución dependiente de lo que conceda GRUB (pensado para **1024x768x32**;
  con otros modos el escritorio escala/adapta pero no se garantiza el mismo
  aspecto). La consola de texto usa VGA 80x25.
* **Tipografía rasterizada en compilación**: Inter (UI) y JetBrains Mono
  (datos) cubren ASCII + **Latin-1 (acentos y ñ)**, pero el **teclado es US**:
  no se pueden teclear acentos desde el sistema, pero las cadenas de UI que
  los usan **se dibujan correctamente** (verificado en la captura de pánico:
  «Excepción», «División», «crítico»). No hay
  escalado tipográfico fuera de los 9 estilos, ni fuentes vectoriales,
  kerning avanzado ni ligaduras.
* **Tema oscuro único**: no hay modo claro, alto contraste ni control de
  escala/HiDPI; los tamaños están fijados en píxeles (escala 4/8). El texto
  `text_faint` (`#6E7788`, 3,98:1 sobre superficie) se reserva para metadatos
  no esenciales.
* **Métricas fijas**: barra superior de 30 px, dock de 58 px y ventanas de
  mínimo 300x180; por debajo de ~800x600 la interfaz no tiene un layout
  alternativo (las resoluciones soportadas y verificadas son 1024x768,
  1280x1024 y 800x600).
* Sin transparencias reales de hardware: el alfa se simula mezclando colores
  por software. Sin vsync; el refresco es por *dirty rectangles*.
* Máximo **8 ventanas** simultáneas (`WINDOW_MAX`); no hay escritorios
  virtuales ni ventanas fuera de pantalla (sin *virtual desktop*).
* **Navegación adaptativa**: con una ventana maximizada no hay dock (los 5
  accesos están en la topbar central); no hay apps fijadas, agrupación,
  bandeja interactiva ni configuración de la nav (posición/tamaño fijos). Los
  indicadores ocultan los grupos que no caben a 800x600 en lugar de
  compactarlos. No hay snapping ni mosaicos.
* El **logotipo oficial** se sirve en las alturas pre-rasterizadas del
  generador (16–128 px); no hay escalado vectorial en ejecución.
* **Ventanas**: las maximizadas son full-bleed fijas y **cuadradas** (sin
  radios, por diseño); solo las normales tienen esquinas redondeadas de radio
  10 px y se redimensionan por bordes (8 px) con mínimo 300x180. No hay
  snapping, mosaicos ni multi-monitor.

## Aplicaciones y shell

* Shell **sin pipes, redirecciones, variables de entorno, comodines ni trabajos
  en segundo plano**; una orden por línea y sin scripting.
* Historial de solo 16 líneas y edición de línea básica (sin autocompletado).
* Solo **5 aplicaciones** (terminal, archivos, monitor, acerca de y juego); no
  hay lanzador de apps ni instalación de software.
* **PAC-MAN SereOS** (versión definitiva): **un único laberinto real** de
  28x31 (240 dots + 4 power pills) con **21 configuraciones** (a partir del 21
  se repite la tabla del nivel 21); no hay editor ni layouts externos. Incluye
  *attract* con PRESS START, menú principal/pausa/game over/ajustes y
  **Continuar** (partida guardada en la sesión). El récord y los ajustes se
  guardan en el RAMFS (`/home/pacman_sereos.hi`, `/home/pacman_*.cfg`):
  persisten mientras el sistema está encendido y **se pierden al reiniciar**.
  La IA reproduce objetivos, pen, frightened, Elroy y tabla scatter/chase del
  original; el *cornering* diagonal y la entrada al túnel están simplificados.
  **No** hay replay `.pmg`/demo automática ni modo testing de la referencia.
* **Licencias de recursos del juego**: la versión definitiva usa PNG/WAV de
  `Res` (sin licencia/atribución, apariencia arcade) para uso **privado
  académico con atribución y sin redistribución pública**; la fuente arcade
  Press Start K tiene su propio aviso. El arte propio del componente queda como
  *fallback*. Ver [PAKMAN_SEREOS.md](PAKMAN_SEREOS.md) y
  [AUDIT_RESOURCES.md](../Pac-man SereOS/docs/AUDIT_RESOURCES.md).
* Las **escenas forzadas de QA** (`--scene gamestart|ghostcapture|death`)
  existen solo en el binario Linux del componente; en SereOS la verificación
  de esos casos se hace con partida real y los marcadores serie
  (`PAC_DEATH`, `GHOST_EATEN/RETURNED/REVIVED`, `LIFE_START`, `PAC_STATS`).
* El juego **se congela si la ventana pierde el foco** o se minimiza (decisión
  de diseño para evitar muertes injustas), igual que la física se detiene si
  el escritorio no puede darle paso cooperativo.
* Las apps cooperativas comparten el frame del escritorio: si una tarda, baja
  los FPS de todo el escritorio.

## Arranque y plataforma

* **BIOS + GRUB 2 con Multiboot 1**; no se soporta arranque UEFI nativo ni
  Multiboot 2.
* Probado en **QEMU i386** (KVM/TCG) con 256 MiB; **no validado en hardware
  físico**. Puede requerir ajustes de vídeo/PS2 en máquinas reales.
* Depende del framebuffer que GRUB deje preparado; si no hay, solo queda la
  consola de texto (fallback intencionado).
* Sin cargador de módulos, sin initramfs, sin actualizaciones.

## Limitaciones del arnés de pruebas (honestidad sobre la verificación)

* Las capturas se validan por **estadísticas de píxeles** (no negra, colores
  distintos, diferencias entre capturas) y por **marcadores del log serie**;
  **no se hace OCR** del texto dibujado, así que la suite no comprueba el
  contenido literal de cada línea de la terminal.
* La selección de la 2ª entrada de GRUB por teclado es **sensible al timing**
  (timeout de 2 s): el arnés reintenta hasta 3 veces y, si falla, genera una
  ISO auxiliar con `default=1` y `timeout=0` en `docs/screenshots/raw/`.
* El cierre de ventanas usa el atajo de QA **Ctrl+W**; el clic real en el
  semáforo rojo con ratón PS/2 se intenta como *fallback* y puede no ser
  fiable bajo QMP. En la última pasada funcionó el cierre por teclado.
* La verificación del juego usa **colores medidos en capturas reales** (dots,
  cuerpos de los 4 fantasmas, cuerpo azul *frightened*): si el tema gráfico o
  los sprites cambian, los umbrales deben recalibrarse (pasó con el rediseño:
  el color de dot cambió a `#FFE0B0`).
* Las pruebas de resolución y de pánico usan **ISOs temporales en /tmp** que
  parchean la petición de vídeo de la cabecera Multiboot; no tocan el repo.
  El pánico (`div0`) es intencionado: su log se excluye del chequeo global de
  excepciones y se verifica que el marcador `SEREOS_EXCEPTION` aparezca.
* El arnés reconecta el monitor de QEMU una vez si la conexión se pierde con
  QEMU aún vivo (robustez ante EPIPE transitorios), pero no puede recuperar
  QEMU si el proceso muere.
* QEMU con `-audiodev wav` **puede no finalizar los tamaños del RIFF** al
  cerrar; la prueba de audio parsea los chunks y usa los bytes reales del
  chunk `data` (el WAV puede sonar igualmente). El backend del anfitrión puede
  no existir: por eso la verificación objetiva se hace grabando a WAV.
* El arnés no debe enviar `sendkey` con *holds* solapados: eso deja sorda a la
  entrada de QEMU. Todas las pruebas usan pulsaciones simples con espera.
* Todo se ejecuta en QEMU con emulación de PS/2 y VGA estándar: no sustituye a
  una prueba en hardware real ni a pruebas de estrés prolongadas.
* La suite no provoca el comando `div0` (que detiene el sistema a propósito)
  porque exige ausencia de `SEREOS_EXCEPTION`/`SEREOS_PANIC`.

## Resumen de límites numéricos

| Recurso | Límite |
|---|---|
| Ventanas | 8 |
| Tareas cooperativas | 32 |
| Nodos del RAMFS | 64 |
| Tamaño de archivo | 1024 bytes |
| Nombre de archivo | 28 caracteres |
| Heap del kernel | 8 MiB |
| Identidad mapeada (PSE) | 512 MiB |
| Historial de shell | 16 líneas |
| Entradas del menú GRUB | 2 |
| Juego | laberinto único de 28×31 tiles (16×16 px) |
