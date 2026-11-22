# -*- coding: utf-8 -*-
from engine import *
def build_b(D):
    P,H,BUL,NUM,CODE,TABLE,FIG=D.P,D.H,D.BUL,D.NUM,D.CODE,D.TABLE,D.FIG
    # ===================== 6 DESARROLLO DEL KERNEL =====================
    H(1,"6. Desarrollo del kernel")
    H(2,"6.1 Evolución por versiones")
    P("El kernel creció en tres etapas, y las dos primeras ya estaban descritas en los avances. La tabla las junta con el estado actual para que se vea el recorrido completo.")
    TABLE("Evolución de SereOS",["Versión","Fecha","Qué se añadió","Tamaño del código"],[
        ["0.1","23 de octubre","Cabecera Multiboot, pila, terminal VGA 80x25 con colores y scroll, lectura de la memoria que informa GRUB, Makefile con ISO","5 archivos, 230 líneas"],
        ["0.2","30 de octubre","GDT propia, IDT con 32 excepciones, PIC remapeado, PIT a 100 Hz, teclado PS/2, cursor de hardware, shell de 8 comandos, pantalla de error","15 archivos, 674 líneas"],
        ["1.0","20 de noviembre","Ratón PS/2, RTC, puerto serie, Sound Blaster 16, marcos y paginación PSE, heap, tareas cooperativas, RAMFS, framebuffer, escritorio gráfico, cuatro aplicaciones, juego integrado, apagado","93 archivos entre .c, .s y .h (63 777 líneas, 46 880 de datos generados)"],
    ],[800,1500,4660,2400],sz=18)
    P("Para dejar constancia de cómo se veían las primeras versiones, recuperamos dos capturas del documento de avances. Se tomaron en QEMU, no en VirtualBox, y solo muestran la consola VGA de entonces.")
    FIG("capturas/00_historicas_avances/v01_kernel_qemu.png","SereOS 0.1 en QEMU (captura histórica)","Captura del documento de avances del 23 de octubre. Muestra el encabezado, el Hello, kernel World! del tutorial y las tres comprobaciones iniciales. No es una captura de esta validación.",w_in=4.9)
    FIG("capturas/00_historicas_avances/v02_arranque_qemu.png","SereOS 0.2 en QEMU (captura histórica)","Captura del documento de avances del 30 de octubre. Ya aparecen la barra de estado azul, las etapas con [ OK ] y el prompt de la shell. No es una captura de esta validación.",w_in=4.9)
    P("Al comparar los avances con el código actual encontramos diferencias que conviene dejar escritas, porque la documentación anterior ya no las refleja. Están en el anexo F. Las más visibles son que la pila inicial ahora mide 64 KiB (antes 16 KiB), que la shell pasó de 8 a 25 comandos, que el temporizador de GRUB es de 2 segundos (antes 3) y que la paginación y la memoria dinámica, que figuraban como pendientes de la versión 0.3, ya están implementadas.")
    H(2,"6.2 Punto de entrada")
    P("`boot/boot.s` es el único archivo que GRUB ejecuta directamente. Contiene la cabecera Multiboot, reserva una pila de 64 KiB en la sección `.bss`, empuja los registros EAX (número mágico) y EBX (puntero a la información de arranque) y llama a `kernel_main`. Si esa función regresara, detiene el procesador con `hlt`.")
    CODE("""section .multiboot
align 4
    dd MB_MAGIC            ; 0x1BADB002
    dd MB_FLAGS            ; alineacion | meminfo | video
    dd MB_CHECKSUM
    dd 0, 0, 0, 0, 0       ; campos del a.out kludge (sin usar)
    dd 0                   ; mode_type = 0: framebuffer lineal grafico
    dd 1024                ; ancho
    dd 768                 ; alto
    dd 32                  ; profundidad

_start:
    cli
    mov esp, stack_top
    push ebx               ; puntero a multiboot_info
    push eax               ; 0x2BADB002
    call kernel_main""","Fragmento de boot/boot.s")
    H(2,"6.3 Inicialización en kernel_main")
    P("`kernel/kernel.c` ejecuta la inicialización en un orden que respeta las dependencias: primero el puerto serie y el registro del kernel, para poder reportar errores; después la GDT y la IDT; luego los dispositivos de entrada y el temporizador; después el video y la memoria; y al final el sistema de archivos, las tareas, el audio y el escritorio. Cada paso importante escribe una línea con `[OK]` en el registro del kernel, que se puede ver con `dmesg` y que sale también por el puerto serie. La figura del capítulo 7 muestra la secuencia completa.")
    P("Si el número mágico de Multiboot no es el esperado, `boot_fail` escribe `[FAIL]` y detiene la máquina. Si GRUB no entrega un framebuffer válido, el kernel no entra al escritorio y arranca la consola de texto, que es justamente lo que hace la segunda entrada del menú de GRUB.")
    H(2,"6.4 GDT")
    P("La GDT de SereOS tiene cinco descriptores en modelo plano. Se carga con `lgdt` desde `kernel/gdt.c` y un pequeño código en ensamblador recarga los registros de segmento.")
    TABLE("Descriptores de la GDT",["Selector","Segmento","Byte de acceso","Anillo"],[
        ["0x00","Nulo (obligatorio)","0x00","-"],
        ["0x08","Código del kernel","0x9A","0"],
        ["0x10","Datos del kernel","0x92","0"],
        ["0x18","Código de usuario","0xFA","3"],
        ["0x20","Datos de usuario","0xF2","3"],
    ],[1500,3300,2500,2060])
    P("Todos los segmentos usan base 0, límite 0xFFFFFFFF y granularidad de 4 KiB (byte `0xCF`). Los descriptores de anillo 3 no se usan: ninguna aplicación se ejecuta en ese nivel.")
    H(2,"6.5 IDT, rutinas de interrupción y PIC")
    P("La IDT tiene entradas para los 32 vectores de excepción y para los 16 de las IRQ. Cada entrada apunta a una rutina de `boot/isr.s` que empuja el número de vector, guarda los registros y llama a `interrupt_handler()` en C. Las puertas son de interrupción de 32 bits en anillo 0 (byte `0x8E`).")
    P("Antes de habilitar las interrupciones, el PIC se reprograma para que las IRQ 0 a 15 lleguen a los vectores 32 a 47. Las cuatro palabras de inicialización (ICW) y la cascada del PIC esclavo en la línea 2 son las del manual del 8259:")
    CODE("""static void pic_remap(void) {
    outb(0x20, 0x11); io_wait(); outb(0xA0, 0x11); io_wait();  /* ICW1 */
    outb(0x21, 0x20); io_wait(); outb(0xA1, 0x28); io_wait();  /* ICW2 */
    outb(0x21, 0x04); io_wait(); outb(0xA1, 0x02); io_wait();  /* ICW3 */
    outb(0x21, 0x01); io_wait(); outb(0xA1, 0x01); io_wait();  /* ICW4 */
    outb(0x21, 0x00); outb(0xA1, 0x00);                        /* sin mascaras */
}""","Fragmento de kernel/idt.c")
    FIG("diagramas/d3_interrupciones.png","Camino de una interrupción en SereOS","Diagrama propio basado en boot/isr.s y kernel/idt.c. Si el vector es menor que 32 el kernel muestra la pantalla de error y se detiene. Si es 32 o mayor ejecuta el manejador registrado y envía el fin de interrupción al PIC.",w_in=6.3,max_h_in=6.2)
    P("`interrupt_handler()` distingue los dos casos. Con un vector menor que 32 llama a `panic_exception()`, que no regresa. Con uno mayor o igual, cuenta la interrupción, ejecuta el manejador registrado con `irq_install()` y envía el fin de interrupción (EOI) al PIC maestro y, si la IRQ es 8 o mayor, también al esclavo. Se probó con la excepción de división por cero (capítulo 10).")
    H(2,"6.6 Temporizador PIT")
    P("El PIT oscila a 1 193 182 Hz. SereOS divide esa frecuencia por 11 931 para obtener 100 interrupciones por segundo. El manejador de la IRQ 0 solo incrementa un contador de ticks, y todo lo demás (reloj de la barra superior, tiempo encendido, reposo de tareas) se calcula a partir de ese contador.")
    CODE("""void timer_init(uint32_t hz) {
    uint32_t divisor = PIT_BASE_HZ / hz;        /* 1193182 / 100 = 11931 */
    outb(0x43, 0x36);                           /* canal 0, modo 3 */
    outb(0x40, (uint8_t)(divisor & 0xFF));
    outb(0x40, (uint8_t)((divisor >> 8) & 0xFF));
    irq_install(0, timer_callback);             /* ticks++ */
}""","Fragmento de drivers/timer.c")
    P("En VirtualBox lo verificamos con el comando `ticks`: tras 34 segundos de funcionamiento informó 3 439 ticks a 100 Hz (34 390 ms), coherente con el tiempo real.")
    H(2,"6.7 Teclado y ratón PS/2")
    P("El teclado trabaja en el IRQ 1 con el conjunto de códigos 1 y la distribución de teclado de Estados Unidos. La rutina de interrupción comprueba el puerto de estado `0x64` antes de leer el dato en `0x60`, porque el ratón comparte ese puerto. Reconoce el prefijo `0xE0` de las teclas extendidas (flechas, Inicio, Fin), mantiene el estado de Shift, Control, Alt y Bloq Mayús, y deja los eventos en una cola circular de 512 posiciones (`drivers/input.c`) que consumen el escritorio, el juego y la consola de texto. La consola de texto usa además un buffer de 128 caracteres.")
    P("El ratón se inicializa con la secuencia del controlador 8042: habilita el puerto auxiliar, reescribe el byte de configuración para activar la IRQ 12, pide los valores por defecto y ejecuta la secuencia de Intellimouse (muestreo 200, 100 y 80 más el comando `0xF2`) para detectar si tiene rueda. Los paquetes son de 3 bytes, o de 4 con rueda. Si no hay ratón, el sistema sigue funcionando con teclado.")
    P("El teclado emite un evento al presionar y otro al soltar la tecla. Durante las pruebas con VirtualBox, la tecla Escape no fue reconocida por el juego cuando enviábamos la pulsación y la liberación casi juntas, y por eso la enviamos con una pausa de 150 ms entre ambas (capítulo 12).")
    H(2,"6.8 Reloj, puerto serie y registro del kernel")
    P("El reloj de tiempo real (CMOS, puertos `0x70` y `0x71`) se lee dos veces hasta obtener dos instantáneas iguales, para no mezclar campos de segundos distintos, y entiende los formatos BCD y binario. El puerto serie COM1 se configura a 115 200 baudios, 8N1, con FIFO. Es el canal por el que sale el registro del kernel y los marcadores de prueba, y en VirtualBox lo conectamos a un archivo para conservar la evidencia.")
    P("El registro del kernel (`kernel/log.c`) es un anillo de 96 entradas con marca de tiempo en ticks y nivel (información, correcto, fallo). Alimenta a `dmesg`, al texto del splash y al contador de errores del Monitor. Una nota de la documentación anterior decía que el puerto serie iba a 38 400 baudios. El código dice 115 200 (divisor 1), y eso es lo que se usó.")
    H(2,"6.9 Pantalla de error y apagado")
    P("Cuando el procesador lanza una excepción, `panic_exception()` arma un texto con el nombre de la excepción, el valor de EIP, CS, EFLAGS, EAX, EBX, ECX, EDX y el código de error. Lo escribe por el puerto serie y lo muestra en una pantalla de error crítico que se dibuja con primitivas estáticas, para que funcione aunque el estado del escritorio sea inconsistente. Después detiene el procesador.")
    P("`kernel/shutdown.c` implementa el apagado en tres fases: cierra las ventanas (el juego guarda su récord), muestra una pantalla de despedida y manda las órdenes de apagado conocidas para QEMU, Bochs y VirtualBox, con reinicio por el controlador de teclado como alternativa. Aparece en el menú del logotipo, pero no la ejecutamos en esta validación.")

    # ===================== 7 ARRANQUE Y GRUB =====================
    H(1,"7. Proceso de arranque y GRUB")
    H(2,"7.1 Del encendido al escritorio")
    FIG("diagramas/d2_arranque.png","Secuencia de arranque de SereOS desde la ISO","Diagrama propio. Arriba, las seis etapas desde la BIOS hasta el bucle del escritorio. Abajo, el orden de las 23 inicializaciones de kernel_main, tomado de kernel/kernel.c.",w_in=6.3,max_h_in=6.2)
    P("La BIOS de la máquina virtual encuentra la ISO en la unidad óptica, y el sector de arranque que escribió `grub-mkrescue` carga GRUB. GRUB lee `/boot/grub/grub.cfg`, muestra el menú, carga el kernel que se le pida y salta a su punto de entrada en modo protegido de 32 bits. Desde ahí el recorrido es el que muestra la figura.")
    H(2,"7.2 Configuración de GRUB")
    P("El archivo de configuración tiene dos entradas. La primera arranca el kernel pidiendo un modo gráfico de 1024x768x32 (con alternativas de 1280x1024, 800x600 y 1280x720). La segunda arranca una copia del kernel cuya cabecera Multiboot no pide video, lo que deja a GRUB en modo texto VGA y activa la consola de respaldo.")
    CODE("""set timeout=2
set default=0
insmod all_video

menuentry "SereOS 1.0 - SereOS Desktop" {
    set gfxmode=1024x768x32,1280x1024x32,800x600x32,1280x720x32,auto
    set gfxpayload=keep
    multiboot /boot/sereos.bin
    boot
}

menuentry "SereOS 1.0 - modo texto (diagnostico)" {
    set gfxpayload=text
    multiboot /boot/sereos-text.bin
    boot
}""","grub.cfg (idéntico al que está dentro de la ISO)")
    P("El comportamiento real, que comprobamos en VirtualBox, es este: el menú se muestra durante 2 segundos con la primera entrada seleccionada y, si no se pulsa nada, arranca el escritorio. Para fotografiar el menú pulsamos la flecha arriba varias veces apenas aparece GRUB, lo que detiene la cuenta atrás. No modificamos `grub.cfg` para obtener las capturas.")
    FIG("capturas/01_arranque/grub_menu.png","Menú de GRUB en VirtualBox","Captura de VirtualBox (GRUB 2.16). Muestra las dos entradas definidas en grub.cfg. La primera arranca el escritorio gráfico y la segunda la consola de texto de diagnóstico.",w_in=5.6)
    FIG("capturas/01_arranque/grub_seleccion_modo_texto.png","Selección de la entrada de modo texto","Captura de VirtualBox con la segunda entrada resaltada. Es la opción de recuperación y diagnóstico: no requiere framebuffer.",w_in=5.6)
    H(2,"7.3 Cabecera Multiboot y variante de modo texto")
    P("La cabecera de `boot.s` activa tres banderas: alinear los módulos a 4 KiB, pedir el mapa de memoria y pedir un modo de video. Para la entrada de modo texto, el Makefile ejecuta `tools/patch_multiboot_text.py`, que copia `sereos.bin`, cambia las banderas de `0x7` a `0x3` en el desplazamiento 4096 y recalcula la suma de comprobación. El resultado es `sereos-text.bin`, de idéntico tamaño (1 526 240 bytes). Ambos binarios superan `grub-file --is-x86-multiboot`.")
    H(2,"7.4 Mapa de memoria del kernel")
    P("El script de enlace coloca el kernel a partir de 2 MiB, la dirección clásica de GRUB, y alinea cada sección a 4 KiB. El programa ocupa unos 172 KiB de código, 1,2 MiB de datos de solo lectura (fuentes, iconos, logotipo, sonidos y sprites) y unos 19 MiB de `.bss`, que incluyen el heap de 8 MiB, el backbuffer del framebuffer y los mapas de bits del gestor de marcos. Las direcciones del diagrama salen de `readelf -lW sereos.bin`.")
    FIG("diagramas/d4_mapa_memoria.png","Mapa de memoria de SereOS","Diagrama propio basado en linker.ld, en las cabeceras de programa de sereos.bin y en las constantes de memory/page.c.",w_in=6.3,max_h_in=6.2)
    H(2,"7.5 Pantalla de inicio y transición")
    P("Al elegir la primera entrada, el kernel inicializa el hardware y muestra una pantalla de inicio de aproximadamente un segundo: el logotipo de SereOS, la versión, una línea de progreso y tres mensajes reales del registro del kernel. Termina con un fundido breve hacia el escritorio.")
    FIG("capturas/01_arranque/splash_inicio.png","Inicio de SereOS: logotipo y barra de progreso","Captura de VirtualBox tomada medio segundo después de elegir la entrada gráfica. La línea azul bajo la versión es el progreso de arranque.",w_in=4.3)
    FIG("capturas/01_arranque/splash_log_kernel.png","Splash con mensajes del registro del kernel","Captura de VirtualBox del final de la pantalla de inicio. Los tres mensajes son entradas reales de klog: audio SB16 en 0x220, IRQ 5 y DMA 1; motor gráfico nativo inicializado; y aplicaciones del escritorio registradas.",w_in=4.3)
    H(2,"7.6 Modo de diagnóstico y recuperación")
    P("SereOS tiene dos mecanismos de diagnóstico implementados y probados. El primero es la consola de texto, que no depende del framebuffer. El segundo es la pantalla de error crítico del capítulo 10. No hay un modo de recuperación más elaborado, como un arranque a un estado limpio: tras una excepción el sistema se detiene y hay que reiniciar la máquina.")
    FIG("capturas/03_terminal/modo_texto_arranque.png","Consola de texto de respaldo","Captura de VirtualBox tras elegir la segunda entrada de GRUB. La barra azul superior muestra el uptime; las líneas siguientes indican la distribución del teclado y los atajos del escritorio, que aquí no están disponibles.",w_in=5.6)

    # ===================== 8 SUBSISTEMAS =====================
    H(1,"8. Subsistemas del sistema operativo")
    H(2,"8.1 Gestión de memoria")
    P("La memoria se gestiona en tres capas.")
    BUL([
        "**Marcos físicos (`memory/page.c`).** Un mapa de bits estático con un bit por marco de 4 KiB, suficiente para 512 MiB (131 072 marcos). Se reservan la memoria baja (0 a 1 MiB), la imagen del kernel con un margen de 64 KiB y el framebuffer. El resto, según el mapa que da Multiboot, queda disponible para `page_alloc()` y `page_free()`. Con 256 MiB, VirtualBox informó 65 520 marcos totales, 59 992 libres y 5 528 usados.",
        "**Paginación.** `paging_init()` construye un directorio de páginas con entradas de 4 MiB (PSE) para los primeros 512 MiB y para el rango `0xE0000000` a `0xFFFFFFFF`, donde GRUB suele colocar el framebuffer. La primera entrada usa páginas de 4 KiB para mapear con más finura el código de bajo nivel. La identidad virtual igual a física se mantiene.",
        "**Heap (`memory/kmalloc.c`).** Un arena estático de 8 MiB dividido en bloques enlazados. Cada bloque lleva una cabecera de 24 bytes con tamaño, bandera de libre, número mágico y punteros. `kmalloc` busca el primer bloque libre suficiente y lo divide si sobra espacio; `kfree` fusiona el bloque con sus vecinos libres. No hay asignaciones desde las rutinas de interrupción, así que no hacen falta cerrojos.",
    ])
    P("Lo que no existe: espacios de direcciones por proceso, memoria bajo demanda, intercambio a disco ni protección de páginas. Un error de escritura de una aplicación puede dañar al kernel.")
    H(2,"8.2 Tareas y planificación")
    P("`process/task.c` mantiene una tabla de 32 ranuras. Cada tarea tiene un nombre de hasta 24 caracteres, un estado (sin usar, lista, dormida o terminada), una función de entrada y un argumento. No hay cambio de pila ni de contexto: el planificador llama a la función de cada tarea lista, y la función hace un paso corto y regresa. `task_sleep_ms()` no suspende al procesador. Marca la tarea como dormida con un plazo en ticks, y el planificador la despierta cuando vence.")
    P("`scheduler_tick()` se llama una vez por cuadro del escritorio. En cada llamada despierta las tareas cuyo plazo venció, ejecuta un paso de cada tarea lista empezando por un cursor rotativo (round-robin) y avanza ese cursor para que ninguna tarea tenga siempre el primer turno. El Monitor del sistema y el comando `sysinfo` muestran los contadores reales: en la captura de `sysinfo` había una tarea activa, 345 pasos y 345 activaciones; con tres ventanas abiertas, el Monitor mostró tres tareas (terminal, files y monitor).")
    H(2,"8.3 Sistema de archivos RAMFS")
    P("El RAMFS es un árbol real de nodos en una tabla estática. El nodo 0 es la raíz. Cada nodo es un archivo o un directorio con nombre, padre, tamaño y un buffer de datos. Se resuelven rutas absolutas y relativas, y `.` y `..` funcionan sin salirse de la raíz. Al arrancar se crean algunos directorios y archivos de ejemplo, como `/home` y `/docs`.")
    TABLE("Límites del RAMFS",["Recurso","Límite"],[
        ["Nodos (archivos y directorios)","64"],
        ["Tamaño de un archivo","1 024 bytes"],
        ["Longitud de un nombre","28 caracteres"],
        ["Longitud de una ruta","128 caracteres"],
        ["Persistencia","Ninguna: todo se pierde al apagar o reiniciar"],
    ],[4500,4860])
    P("El archivo `hola.txt` que creamos desde la terminal en VirtualBox aparece después en la aplicación Archivos, con sus 31 bytes, lo que prueba que ambas usan el mismo sistema (capítulos 10 y 11).")
    H(2,"8.4 Audio")
    P("`audio/audio.c` ofrece una capa de audio independiente del juego con dos motores. El primero es la Sound Blaster 16 (`drivers/sb16.c`), que se busca reiniciando el DSP en los puertos `0x220` a `0x280`, reproduce PCM de 8 bits mono por el DMA 1 y avisa el fin de cada bloque con la IRQ 5. El segundo, de respaldo, es el altavoz del PC, controlado por el canal 2 del PIT.")
    P("En VirtualBox, `dmesg` y el comando `audio` informaron `SB16 0x220 IRQ5 DMA1` y una frecuencia de 11 025 Hz, es decir, el dispositivo se detectó y se configuró. No verificamos con el oído que el sonido saliera por los altavoces del equipo. Por eso la reproducción queda como implementada y no probada en esta validación. El proyecto trae una guía para configurar el audio en VirtualBox (`docs/GUIA_VIRTUALBOX_AUDIO.md`) y una prueba que graba la salida de la SB16 en QEMU a un archivo WAV, que no repetimos.")
    P("La entrada, el registro del kernel y el puerto serie se describieron en el capítulo 6. En la arquitectura general, `input.c` es el punto donde se encuentran los controladores y las aplicaciones: las rutinas de interrupción producen eventos y el escritorio los consume sin bloquearse.")

    # ===================== 9 ENTORNO GRAFICO =====================
    H(1,"9. Entorno gráfico")
    H(2,"9.1 Framebuffer y motor de dibujo")
    P("GRUB negocia un modo lineal de 1024x768 a 32 bits y entrega su dirección en la estructura Multiboot. `graphics/framebuffer.c` la valida, reserva un backbuffer estático y expone el dibujo directo antes de que exista el motor gráfico. `graphics/graphics.c` implementa las primitivas: rectángulos, rectángulos redondeados, líneas, degradados, sombras, mezcla alfa, recorte y copia de imágenes. Todo se dibuja en el backbuffer y el sistema copia a la pantalla solo las regiones marcadas como sucias.")
    P("La tipografía no usa ninguna biblioteca. Los atlases de Inter (interfaz) y JetBrains Mono (terminal y datos) se rasterizan al compilar con un script de Python y quedan como tablas de cobertura alfa dentro del kernel. Cubren ASCII y Latin-1, así que se dibujan correctamente las tildes y la eñe, pero el teclado es el de Estados Unidos y no se pueden escribir desde el sistema.")
    H(2,"9.2 Escritorio")
    P("El compositor (`gui/desktop.c`) dibuja un fondo oscuro con formas abstractas sutiles, una barra superior de 30 píxeles y un dock flotante de 58 píxeles centrado abajo. La barra superior muestra el logotipo y el menú a la izquierda, el nombre de la aplicación activa al centro, y a la derecha la memoria usada, el tiempo encendido, la fecha y la hora real del RTC.")
    FIG("capturas/02_escritorio/escritorio_principal.png","Escritorio de SereOS en VirtualBox","Captura de VirtualBox con el sistema recién arrancado, sin ventanas. Se ven la barra superior (logotipo, menú, memoria, uptime, fecha y hora), el dock con los cinco iconos y el cursor del sistema.",w_in=6.2)
    P("El dock tiene cinco iconos que coinciden con las teclas de función: Archivos (F1), Terminal (F2), Monitor (F3), PAC-MAN SereOS (F4) y Acerca de (F5). Un punto bajo el icono indica que la aplicación tiene una ventana abierta.")
    H(2,"9.3 Ventanas")
    P("El gestor de ventanas (`gui/window.c`) mantiene un conjunto de hasta 8 ventanas en orden de profundidad, con una ventana enfocada. Las ventanas normales tienen una barra de título, esquinas redondeadas de 10 píxeles con recorte real y tres botones: minimizar (ámbar), maximizar o restaurar (verde) y cerrar (rojo). Según el código, se pueden mover arrastrando la barra, redimensionar por los bordes (mínimo 300x180) y maximizar con el botón verde o con doble clic en la barra de título. En esta validación solo ejercitamos el maximizado con el botón verde, el cierre y el foco. El cierre, el foco y la restauración se aplican al final de cada cuadro, para que una aplicación pueda cerrar una ventana desde su propio manejador sin liberar memoria que el compositor todavía usa.")
    FIG("capturas/04_aplicaciones/multiventana.png","Varias ventanas abiertas a la vez","Captura de VirtualBox con tres ventanas apiladas: Archivos, Monitor y Terminal, esta última con el foco. Las otras dos quedan atenuadas detrás, y el nombre de la ventana activa aparece al centro de la barra superior.",w_in=5.3)
    H(2,"9.4 Menú del logotipo, ayuda emergente y cursor")
    P("Estas tres funciones dependen del ratón, y VirtualBox no permite moverlo desde la línea de comandos. Las comprobamos en QEMU con la misma ISO, y por eso las capturas siguientes se rotulan como tomadas en QEMU. El menú del logotipo lista las cinco aplicaciones y, más abajo, Reiniciar y Apagar. También anuncia el atajo Alt+W para cerrar la ventana activa. El cursor es una flecha de 12x18 píxeles con contorno oscuro que se dibuja sobre el backbuffer y se restaura en el cuadro siguiente.")
    FIG("capturas/02_escritorio/qemu_menu_launcher.png","Menú del logotipo (QEMU)","Captura de QEMU 11.1.3 con la ISO final tras hacer clic en el botón de menú de la barra superior. Lista Acerca de, Archivos, Terminal, Monitor y PAC-MAN SereOS, además de Reiniciar y Apagar.",w_in=6.0)
    FIG("capturas/02_escritorio/qemu_dock_tooltip.png","Ayuda emergente del dock (QEMU)","Captura de QEMU con el cursor sobre el icono del juego. Aparece la etiqueta PAC-MAN SereOS sobre el dock.",w_in=6.0)
    H(2,"9.5 Maximizado y navegación adaptativa")
    P("Cuando una ventana se maximiza, el dock flotante desaparece y sus cinco accesos pasan al centro de la barra superior, con la aplicación activa resaltada. La ventana ocupa todo el espacio bajo la barra, sin esquinas redondeadas. Al restaurarla o cerrarla, el dock vuelve. Lo comprobamos en QEMU con el juego y con la terminal.")
    FIG("capturas/02_escritorio/qemu_juego_maximizado_topnav.png","Ventana maximizada y navegación superior (QEMU)","Captura de QEMU con PAC-MAN SereOS maximizado. El dock ya no se ve: los cinco accesos están en el centro de la barra superior, con el del juego resaltado. La ventana ocupa el área completa bajo la barra.",w_in=6.0)
    FIG("capturas/02_escritorio/qemu_juego_restaurado_dock.png","Ventana restaurada y dock de vuelta (QEMU)","Captura de QEMU después de pulsar el botón verde otra vez. El dock reaparece y la ventana recupera su tamaño normal.",w_in=6.0)
    FIG("capturas/02_escritorio/qemu_terminal_maximizada.png","Terminal maximizada (QEMU)","Captura de QEMU con la terminal maximizada. El contenido se adapta al nuevo tamaño y el indicador de la aplicación activa queda en la barra superior.",w_in=6.0)

    # ===================== 10 TERMINAL Y SHELL =====================
    H(1,"10. Terminal y shell")
    P("La shell (`shell/shell.c`, 809 líneas) no escribe en ningún dispositivo. Emite texto y cambios de color a través de una estructura de salida, de modo que la terminal gráfica y la consola VGA de respaldo ejecutan exactamente los mismos comandos. La terminal gráfica (`apps/terminal/terminal_app.c`) guarda 320 líneas de 100 columnas con un color por carácter, y se desplaza con Re Pág, Av Pág o la rueda. La edición de línea admite Retroceso y el historial de 16 líneas con las flechas arriba y abajo. No hay autocompletado, tuberías ni variables.")
    H(2,"10.1 Comandos disponibles")
    TABLE("Comandos de la shell de SereOS 1.0",["Comando","Qué hace"],[
        ["help, about, version, sysinfo","Ayuda, descripción del sistema, versión y resumen real del sistema"],
        ["mem, free, ticks","Memoria detectada, memoria libre y del heap, ticks del PIT y tiempo encendido"],
        ["dmesg","Registro del kernel con marcas de tiempo"],
        ["date, time","Fecha y hora del reloj CMOS"],
        ["clear, echo, scroll","Limpia la pantalla, repite un texto, imprime 30 líneas para probar el desplazamiento"],
        ["div0","Provoca una división por cero para probar la IDT"],
        ["audio, beep, audiotest","Backend de audio, tono con frecuencia y duración, y secuencia de prueba"],
        ["pwd, ls, cd","Directorio actual, listado y cambio de directorio"],
        ["mkdir, touch, rm","Crear un directorio, crear un archivo vacío, borrar"],
        ["cat, write","Mostrar un archivo y escribir texto en un archivo"],
    ],[3000,6360])
    P("En total son 25 comandos. La figura siguiente es la salida de `help` en VirtualBox.")
    FIG("capturas/03_terminal/cmd_help.png","Salida de help en la terminal gráfica","Captura de VirtualBox. La terminal muestra la lista de comandos con una descripción por línea, tal como la define la shell. Es la parte final de la lista, porque la ventana se desplaza al llegar al fondo.",w_in=5.0)
    H(2,"10.2 Información del sistema y del kernel")
    FIG("capturas/03_terminal/cmd_sysinfo_version.png","Resultado de sysinfo y version","Captura de VirtualBox. sysinfo informa 262 080 KiB de memoria, 65 520 marcos de 4 KiB, el heap de 8 192 KiB con una asignación, 5 nodos en el RAMFS, una tarea activa y 1 928 ticks a 100 Hz, con la hora del RTC. version indica la arquitectura i686, el kernel monolítico y el arranque con GRUB 2.",w_in=5.0)
    P("Los 262 080 KiB equivalen a unos 255 MiB: es la memoria que GRUB informa para una máquina de 256 MiB menos las reservas de la BIOS. Los valores de memoria de esta captura coinciden con los de `free` y con los del Monitor.")
    FIG("capturas/03_terminal/cmd_dmesg.png","Registro del kernel con dmesg","Captura de VirtualBox. Las 17 entradas del arranque aparecen con marca de tiempo y estado [OK], y el encabezado informa 0 errores. Coincide con la salida por el puerto serie del anexo D.",w_in=5.0)
    FIG("capturas/03_terminal/cmd_mem_free_ticks_date.png","Memoria, temporizador y fecha","Captura de VirtualBox con los comandos mem, free, ticks y date. free muestra tres bloques: memoria física, heap del kernel (8 192 KiB, 65 KiB usados) y RAMFS (5 nodos, 640 bytes). ticks informa 3 439 ticks a 100 Hz.",w_in=5.0)
    H(2,"10.3 Sistema de archivos y manejo de errores")
    P("Para probar el RAMFS creamos un directorio, escribimos un archivo y lo leímos. Después provocamos dos errores: leer un archivo que no existe y escribir un comando desconocido. Los mensajes se muestran en rojo y los resultados correctos en verde.")
    FIG("capturas/03_terminal/cmd_ramfs_errores.png","Archivos y manejo de errores en la terminal","Captura de VirtualBox. pwd devuelve la raíz; mkdir, cd y write crean pruebas/hola.txt con 31 bytes; cat lo lee; ls lo lista. Después cat noexiste.txt y un comando inválido producen mensajes de error en rojo.",w_in=5.0)
    FIG("capturas/03_terminal/cmd_audio_echo_about.png","Audio, echo y about","Captura de VirtualBox. audio informa el backend sb16, SB16 en 0x220 con IRQ 5 y DMA 1, PCM a 11 025 Hz y DSP 4.5. echo repite el texto. about describe el sistema.",w_in=5.0)
    H(2,"10.4 Excepción de división por cero")
    P("El comando `div0` ejecuta una división entera entre cero para comprobar que la IDT y el manejador de excepciones funcionan. El procesador lanza la excepción 0, `interrupt_handler()` reconoce que el vector es menor que 32 y el kernel muestra la pantalla de error con la dirección de la instrucción (EIP) y los registros. El sistema se detiene a propósito, así que hay que reiniciar la máquina. En el puerto serie quedó la línea `SEREOS_EXCEPTION EIP = 0x0021ec1d CS = 0x0008 EFLAGS = 0x00010246`.")
    FIG("capturas/03_terminal/panico_div0.png","Pantalla de error por división por cero","Captura de VirtualBox después de ejecutar div0. Indica Excepción 0: División por cero, con EIP 0x0021ec1d, CS 0x0008, EFLAGS 0x00010246 y los registros EAX, EBX, ECX y EDX. Pide reiniciar la máquina.",w_in=6.0)
    H(2,"10.5 Consola de texto de respaldo")
    P("La segunda entrada de GRUB arranca la misma shell sobre la consola VGA de 80x25. La probamos con `help` y `sysinfo`, y las respuestas son las mismas que en la terminal gráfica. Esa consola informa 0 tareas activas, porque sin escritorio no hay ventanas que creen tareas.")
    FIG("capturas/03_terminal/modo_texto_sysinfo.png","sysinfo en la consola de texto","Captura de VirtualBox en modo texto, con el final de help y la salida de sysinfo. La información es la misma que en el escritorio, salvo las tareas y el heap en uso.",w_in=5.6)

    # ===================== 11 APLICACIONES =====================
    H(1,"11. Aplicaciones y funcionalidades")
    P("El sistema incluye cuatro aplicaciones propias y el juego. Se registran en `apps/apps.c` en el orden del dock, que también es el orden de las teclas F1 a F5. Los atajos globales del escritorio son los de la tabla.")
    TABLE("Atajos de teclado del escritorio",["Tecla","Acción"],[
        ["F1, F2, F3","Abrir Archivos, Terminal, Monitor"],
        ["F4, F5","Abrir PAC-MAN SereOS, Acerca de"],
        ["F6","Pasar el foco a la ventana siguiente"],
        ["F7","Minimizar la ventana activa"],
        ["Ctrl+W o Alt+W","Cerrar la ventana activa"],
    ],[3000,6360])
    H(2,"11.1 Archivos")
    P("Es un explorador del RAMFS con una barra lateral de lugares (Raíz, /home y /docs), una barra de ruta, una tabla con nombre, tipo y tamaño, un panel de vista previa del archivo seleccionado y una barra de estado con el conteo de nodos y el espacio usado. Se maneja con Enter para abrir, Retroceso para subir y la tecla r para refrescar.")
    FIG("capturas/04_aplicaciones/explorador_archivos.png","Aplicación Archivos","Captura de VirtualBox. Muestra la carpeta pruebas creada desde la terminal con su archivo hola.txt de 31 bytes. El panel inferior previsualiza el contenido (Hola desde SereOS en VirtualBox) y la barra de estado informa 7 nodos y 671 bytes usados de 64 KiB.",w_in=5.3)
    H(2,"11.2 Monitor del sistema")
    P("El Monitor muestra datos reales del kernel en una rejilla de tarjetas: memoria RAM, heap, tiempo encendido, pantalla, tareas cooperativas y estado del kernel. Si un subsistema no está disponible, escribe «no disponible» en lugar de inventar un valor.")
    FIG("capturas/04_aplicaciones/monitor_sistema_foco.png","Monitor del sistema","Captura de VirtualBox con el Monitor al frente y Archivos detrás. Indica 21 MB usados de 255 MB, 71 KB de heap en uso, uptime de 00:01:25, pantalla de 1024x768 a 32 bpp y tres tareas (terminal, files y monitor) con sus contadores de pasos.",w_in=5.3)
    H(2,"11.3 Acerca de")
    P("Presenta el logotipo, la versión, la arquitectura, el cargador, la memoria detectada, el audio y una rejilla de 14 componentes con su estado. Consulta las funciones reales de cada subsistema, así que si uno fallara aparecería sin el punto verde.")
    FIG("capturas/04_aplicaciones/acerca_de.png","Aplicación Acerca de","Captura de VirtualBox con la ventana sobre otras dos. Muestra SereOS 1.0 Desktop, i686 / x86 32 bits, kernel monolítico, GRUB 2 / Multiboot 1, 255 MB de memoria y SB16 0x220 IRQ5 DMA1, y los 14 componentes marcados como disponibles.",w_in=5.3)
    H(2,"11.4 Terminal y juego")
    P("La terminal se describió en el capítulo 10. El juego tiene su propio capítulo (12 y 13) porque es un componente con arquitectura independiente.")
