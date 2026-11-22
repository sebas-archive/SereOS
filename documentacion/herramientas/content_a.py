# -*- coding: utf-8 -*-
from engine import *
def build_a(D):
    P,H,BUL,NUM,CODE,TABLE,FIG=D.P,D.H,D.BUL,D.NUM,D.CODE,D.TABLE,D.FIG
    # ===================== INFORMACION DEL PROYECTO =====================
    H(1,"Información del proyecto")
    P("Este documento es la memoria técnica final del proyecto de Sistemas Operativos. Amplía el documento base del curso y recoge los avances que entregamos en octubre. Describe dos productos que se construyen y se ejecutan juntos: el sistema operativo **SereOS** y el videojuego **PAC-MAN SereOS**, que corre como una aplicación nativa dentro de él.")
    TABLE("Datos académicos y del proyecto",["Campo","Detalle"],[
        ["Proyecto","Proyecto final: sistema operativo y juego (SereOS y PAC-MAN SereOS)"],
        ["Institución y programa","Universidad Manuela Beltrán, Ingeniería de software"],
        ["Asignatura","Sistemas operativos"],
        ["Docente","Prof. Hernan Dario Cruz Bueno"],
        ["Integrantes","Miguel Eduardo Angulo Cantor\nKarol Asley Orjuela Mape\nJuan David Gómez Rojas\nSebastián Fernando Revelo Meneses"],
        ["Ciudad y fecha","Bogotá D.C., 20 de noviembre de 2026"],
        ["Versión descrita","SereOS 1.0 «Desktop» y PAC-MAN SereOS (versión definitiva)"],
        ["Entorno de desarrollo","CachyOS (Arch Linux), kernel Linux 7.3.3, gcc 16.2.1, NASM 3.02, GRUB 2.16"],
        ["Entorno de validación principal","Oracle VM VirtualBox 7.2.22r175245 (BIOS, 256 MiB, SoundBlaster 16)"],
        ["Código fuente","Carpeta ^^sereos02/^^ con los componentes ^^sistema operativo/^^ y ^^Pac-man SereOS/^^"],
    ],[2600,6760])
    H(2,"Cómo leer el estado de cada funcionalidad")
    P("En todo el documento usamos las mismas cinco etiquetas para decir qué tan cierta es una afirmación. Una funcionalidad solo aparece como probada si la vimos funcionar en la ejecución que se indica. El resto se describe a partir del código y se marca como tal.")
    TABLE("Etiquetas de estado utilizadas",["Etiqueta","Significado"],[
        ["Implementado y probado","El código existe y lo comprobamos en una ejecución real. Se indica dónde: VirtualBox, QEMU o CachyOS."],
        ["Implementado, no probado","El código existe pero no lo ejercitamos durante esta validación."],
        ["Parcial","Existe una versión reducida o con límites que se describen."],
        ["Planificado","Está en el plan de trabajo o en el trabajo futuro, sin código."],
        ["No implementado","No existe en el proyecto."],
    ],[2900,6460])

    # ===================== RESUMEN =====================
    H(1,"Resumen")
    P("SereOS es un sistema operativo propio para procesadores x86 de 32 bits, escrito en C y en ensamblador NASM. Arranca desde una imagen ISO con GRUB 2 mediante el estándar Multiboot 1, y no depende de Linux ni de ninguna biblioteca del sistema anfitrión. En su versión 1.0 incluye una GDT y una IDT propias, el controlador de interrupciones 8259, el temporizador PIT a 100 Hz, controladores de teclado y ratón PS/2, reloj CMOS, puerto serie, Sound Blaster 16, un gestor de memoria con marcos de 4 KiB, paginación con páginas de 4 MiB y un heap de 8 MiB, un planificador cooperativo, un sistema de archivos en memoria (RAMFS) y un escritorio gráfico con ventanas, dock, barra superior y cursor, dibujado sobre un framebuffer lineal de 1024x768 a 32 bits.")
    P("Sobre ese escritorio corren cuatro aplicaciones nativas (Terminal, Archivos, Monitor y Acerca de) y el videojuego **PAC-MAN SereOS**. El juego es un componente aparte: su lógica y su render son compartidos y solo dos adaptadores dependen de la plataforma, uno para SereOS y otro para Linux con SDL2. El componente se compila como una biblioteca estática (`libpacman.a`) que el Makefile del sistema enlaza al kernel.")
    P("Para esta entrega recompilamos todo desde cero, generamos una ISO nueva de 36 835 328 bytes (SHA-256 `4fe9ea95...c96d9`) y la arrancamos en Oracle VM VirtualBox. Allí comprobamos el menú de GRUB, el arranque del escritorio, la terminal con sus comandos, las aplicaciones, la pantalla de error de la excepción de división por cero y varias partidas completas de PAC-MAN SereOS. Todas las capturas del documento salen de esas ejecuciones, salvo las que se rotulan como tomadas en QEMU o en CachyOS.")
    P("**Palabras clave:** sistema operativo, kernel monolítico, x86, GRUB, Multiboot, framebuffer, escritorio gráfico, videojuego, VirtualBox.",align='left')

    # ===================== 1 INTRODUCCION =====================
    H(1,"1. Introducción")
    P("En el curso vimos de manera teórica cómo arranca una máquina, cómo el gestor de arranque le entrega el control al kernel, cómo el kernel atiende interrupciones y cómo reparte la memoria. Decidimos que la mejor forma de entender esos temas era construirlos. SereOS nació como el kernel mínimo del tutorial Bare Bones de OSDev, que imprime texto en pantalla, y fue creciendo por etapas hasta convertirse en un sistema con interfaz gráfica.")
    P("El documento sigue esa historia. La primera entrega de avances (23 de octubre) dejó un kernel de 5 archivos y 230 líneas que escribía en la memoria de video. La segunda (30 de octubre) añadió GDT, IDT, PIC, PIT, teclado y una shell de 8 comandos. Desde entonces el proyecto pasó de 15 archivos a 93 entre fuentes y cabeceras, y la interfaz de texto se convirtió en un escritorio gráfico. En paralelo se desarrolló el videojuego como componente independiente.")
    H(2,"1.1 Planteamiento del problema")
    P("Un sistema operativo suele estudiarse a través de sus conceptos y de ejemplos recortados. Eso deja sin respuesta preguntas prácticas: qué ocurre entre el momento en que GRUB salta al kernel y el momento en que aparece una ventana, cómo se coordinan un controlador de interrupciones, un temporizador y un teclado, o qué obliga a un programa de usuario a depender del kernel para dibujar y para leer teclas. Sin un sistema propio, y sin un programa real que lo use, esas preguntas se quedan en la teoría.")
    P("El problema que abordamos es construir un sistema operativo mínimo pero completo en su recorrido, desde el arranque hasta una aplicación interactiva, y demostrar con evidencias verificables que funciona sobre una máquina virtual estándar y no solo en el entorno del desarrollador.")
    H(2,"1.2 Justificación")
    P("Construir el sistema obliga a tomar las decisiones que un libro presenta ya resueltas: cuántos segmentos define la GDT, en qué vectores se remapea el PIC, qué hace el kernel cuando el procesador lanza una excepción, cómo se reparte el tiempo entre tareas que no pueden bloquearse. El videojuego aporta una carga de trabajo exigente y fácil de juzgar: si el temporizador, la entrada, el dibujo y el audio fallan, se nota en pantalla.")
    P("La integración también tiene valor de ingeniería de software. El juego se desarrolló como un componente con su propio Makefile, sus pruebas y un contrato de plataforma, y el sistema operativo lo consume como biblioteca. Esa separación permitió ejecutar el mismo juego en CachyOS durante el desarrollo y en SereOS en la entrega final.")
    H(2,"1.3 Alcance")
    P("El alcance cubre lo siguiente. El sistema operativo para x86 de 32 bits con arranque BIOS y GRUB 2, su kernel y drivers, la gestión de memoria, el planificador cooperativo, el RAMFS, el escritorio gráfico, la terminal y las aplicaciones nativas. El videojuego con su arquitectura, sus dos plataformas y su integración. La compilación, la generación de la ISO y su validación en VirtualBox.")
    P("Queda fuera de alcance, y así se documenta en el capítulo de limitaciones, lo que SereOS no hace: multitarea preemptiva, espacio de usuario con anillo 3, llamadas al sistema, red, USB, disco persistente, soporte de varios procesadores y ejecución en hardware físico.")
    H(2,"1.4 Metodología y fuentes de evidencia")
    P("Trabajamos en tres pasos. Primero revisamos los dos documentos de entrada y el código real del proyecto. Segundo, recompilamos el sistema y el juego desde cero y generamos una ISO nueva. Tercero, arrancamos esa ISO en VirtualBox, la usamos como lo haría un usuario y tomamos las capturas con el propio VirtualBox.")
    P("VirtualBox no tiene una función para mover el ratón de la máquina virtual desde la línea de comandos, así que las pruebas de ratón (menú del logotipo, ayuda emergente del dock y maximizado) las hicimos con QEMU y la misma ISO. Esas capturas se rotulan como tal. Las escenas del videojuego que no se pueden alcanzar jugando con comodidad, como la pantalla de nivel completado, se tomaron con el binario de CachyOS y también se rotulan. Ninguna imagen del documento procede de Internet ni de una herramienta de generación de imágenes. Los diagramas se dibujaron a partir de la estructura real del código.")
    TABLE("Procedencia de las capturas",["Procedencia","Qué incluye","Capítulos"],[
        ["VirtualBox 7.2.22 (VBoxManage controlvm screenshotpng)","GRUB, splash, escritorio, terminal, aplicaciones, modo texto, pantalla de error y PAC-MAN SereOS integrado","7, 9, 10, 11, 13"],
        ["QEMU 11.1.3 con la misma ISO","Menú del logotipo, ayuda emergente del dock, ventana maximizada con navegación superior","9"],
        ["PAC-MAN SereOS en CachyOS (SDL2, escenas forzadas)","Pantalla de nivel completado, inicio de partida, captura de fantasma, muerte, ajustes","13"],
        ["Documento de avances (QEMU, octubre)","Cuatro capturas históricas de las versiones 0.1 y 0.2","6"],
    ],[3300,4260,1800])
    P("El procedimiento paso a paso, los archivos de configuración de la máquina virtual y los registros del puerto serie están en los anexos.")

    # ===================== 2 OBJETIVOS =====================
    H(1,"2. Objetivos")
    H(2,"Objetivo general",pagebreak=False)
    P("Diseñar, implementar y validar un sistema operativo propio de 32 bits (SereOS) que arranque desde una ISO con GRUB y ofrezca un escritorio gráfico, y desarrollar un videojuego (PAC-MAN SereOS) que se ejecute de forma nativa dentro de ese sistema, documentando con evidencia reproducible lo que funciona y lo que no.")
    H(2,"Objetivos específicos",pagebreak=False)
    NUM([
        "Construir un kernel monolítico Multiboot en C y NASM con GDT, IDT, PIC, temporizador y controladores de teclado y ratón.",
        "Implementar la gestión de memoria (marcos de 4 KiB, paginación con PSE y heap), un planificador cooperativo y un sistema de archivos en memoria.",
        "Desarrollar un escritorio gráfico sobre el framebuffer que entrega GRUB, con ventanas, dock, barra superior, cursor y aplicaciones nativas.",
        "Ofrecer una shell con comandos de diagnóstico y de manejo de archivos, compartida entre la terminal gráfica y la consola VGA de respaldo.",
        "Desarrollar PAC-MAN SereOS como componente con lógica compartida y dos plataformas, e integrarlo al sistema como una aplicación nativa.",
        "Automatizar la compilación y la generación de una ISO arrancable que contenga el sistema y el juego.",
        "Validar la ISO en Oracle VM VirtualBox y documentar las pruebas, los resultados y las limitaciones con capturas de la ejecución real.",
    ])

    # ===================== 3 FUNDAMENTOS =====================
    H(1,"3. Fundamentos teóricos")
    P("Este capítulo resume los conceptos que usamos al construir el sistema. Cada apartado termina señalando dónde aparece el concepto en SereOS.")
    H(2,"3.1 Kernel monolítico")
    P("En un kernel monolítico todos los servicios (planificación, memoria, sistemas de archivos, controladores) viven en un único programa que se ejecuta con el máximo privilegio del procesador y comparte un solo espacio de direcciones (Tanenbaum y Bos, 2015). Es el diseño más sencillo de implementar y el más rápido en llamadas internas, pero un error en cualquier componente puede detener todo el sistema. SereOS sigue este modelo y lo lleva al extremo, porque las aplicaciones también se ejecutan en el mismo espacio y con los mismos privilegios.")
    H(2,"3.2 Procesador x86 en modo protegido")
    P("Los procesadores x86 arrancan en modo real de 16 bits. El modo protegido de 32 bits ofrece direcciones de 4 GiB, niveles de privilegio (anillos 0 a 3) y soporte para paginación (Intel Corporation, s. f.). GRUB deja el procesador ya en modo protegido, con la línea A20 habilitada, de modo que el kernel empieza a ejecutarse directamente en 32 bits.")
    H(2,"3.3 Arranque, Multiboot y GRUB")
    P("La especificación Multiboot define un contrato entre un gestor de arranque y un kernel: el kernel incluye una cabecera con un número mágico (`0x1BADB002`), banderas y una suma de comprobación; el gestor carga el kernel, deja en EAX el valor `0x2BADB002` y en EBX la dirección de una estructura con información de la máquina, como la memoria disponible y el framebuffer (Free Software Foundation, 2009). SereOS usa Multiboot 1 y pide a GRUB un modo gráfico de 1024x768 a 32 bits en su cabecera.")
    H(2,"3.4 GDT, IDT y excepciones")
    P("La tabla global de descriptores (GDT) define los segmentos de memoria. En el modelo plano todos los segmentos cubren los 4 GiB y solo cambian el tipo y el nivel de privilegio. La tabla de descriptores de interrupciones (IDT) asocia cada vector de interrupción con una rutina. Los vectores 0 a 31 los reserva Intel para excepciones como la división por cero (vector 0) o la falla de página (vector 14).")
    H(2,"3.5 Controlador de interrupciones y temporizador")
    P("El PIC 8259 recibe las interrupciones de los dispositivos (IRQ 0 a 15) y las entrega al procesador con un número de vector. Por defecto las IRQ 0 a 7 caen en los vectores 8 a 15, que chocan con las excepciones, por lo que el sistema operativo debe reprogramarlo. El temporizador PIT 8253/8254 divide un oscilador de 1 193 182 Hz para generar interrupciones periódicas, y esa señal es la base de la medición del tiempo y del reparto de turnos.")
    H(2,"3.6 Memoria física y paginación")
    P("Un gestor de memoria física lleva la cuenta de qué marcos de 4 KiB están libres. La paginación traduce direcciones virtuales a físicas mediante un directorio y tablas de páginas. Con la extensión PSE (page size extension) una entrada del directorio puede mapear directamente 4 MiB, lo que simplifica el mapa cuando no se necesita aislamiento fino. SereOS usa paginación de identidad con PSE.")
    H(2,"3.7 Planificación de tareas")
    P("Un planificador decide qué tarea usa el procesador. En el modelo preemptivo el kernel interrumpe a la tarea mediante el temporizador. En el modelo cooperativo cada tarea cede el control voluntariamente (Silberschatz, Galvin y Gagne, 2018). SereOS usa un planificador cooperativo con política round-robin, que fue una de las políticas que revisamos en las guías del curso.")
    H(2,"3.8 Framebuffer y composición de ventanas")
    P("Un framebuffer lineal es una zona de memoria cuyo contenido es la imagen de la pantalla, píxel por píxel. Un compositor dibuja las ventanas en un buffer intermedio y copia al framebuffer solo las regiones que cambiaron, para evitar parpadeos y trabajo innecesario. SereOS dibuja todo por software, sin aceleración gráfica.")
    H(2,"3.9 Sonido con Sound Blaster 16")
    P("La Sound Blaster 16 es una tarjeta de sonido que los emuladores reproducen con fidelidad. Se configura por puertos de entrada y salida, y reproduce muestras PCM mediante transferencias DMA, avisando con una interrupción al terminar cada bloque (Creative Technology, 1996). VirtualBox ofrece este dispositivo, y es el que SereOS detecta y usa.")

    # ===================== 4 HERRAMIENTAS =====================
    H(1,"4. Herramientas y tecnologías")
    P("Desarrollamos en CachyOS, una distribución basada en Arch Linux. Los números de versión de la tabla salen de las herramientas instaladas en el equipo donde compilamos y probamos.")
    TABLE("Herramientas y versiones utilizadas",["Herramienta","Versión","Uso en el proyecto"],[
        ["gcc","16.2.1","Compilación del kernel y de la biblioteca del juego con -m32 -ffreestanding"],
        ["NASM","3.02","Ensamblado de ^^boot/boot.s^^ y ^^boot/isr.s^^ (formato elf32)"],
        ["GNU Make","4.4.1","Compilación, ISO y ejecución con ^^make^^"],
        ["GRUB (grub-mkrescue, grub-file)","2.16","Creación de la ISO y validación de la cabecera Multiboot"],
        ["xorriso y mtools","1.5.8","Dependencias de grub-mkrescue; inspección de la ISO"],
        ["Python","3.14.9","Parcheo de la cabecera para el modo texto y herramientas de prueba"],
        ["Oracle VM VirtualBox","7.2.22r175245","Validación de la ISO final (máquina virtual BIOS)"],
        ["QEMU (qemu-system-i386)","11.1.3","Pruebas con ratón y arnés de pruebas automáticas del proyecto"],
        ["SDL2","sistema","Plataforma Linux de PAC-MAN SereOS para pruebas en CachyOS"],
    ],[2600,1700,5060])
    P("Los documentos anteriores indicaban que el kernel se compilaba con el compilador cruzado `i686-elf-gcc`. El Makefile actual lo usa si está en el PATH, pero en el equipo de esta validación no estaba instalado. El Makefile detecta eso y compila con el gcc del sistema en modo `-m32` (define `SEREOS_HOST_GCC`). El resultado es el mismo formato ELF32 para i386, y así se generó la ISO de esta entrega.")
    P("Todo el código del kernel se compila con `-ffreestanding -nostdlib` y con las instrucciones SSE y MMX desactivadas (`-mno-sse -mno-mmx -mno-sse2`), porque el kernel no inicializa la unidad de coma flotante. El juego, por la misma razón, hace sus cálculos con aritmética de punto fijo.")

    # ===================== 5 ARQUITECTURA GENERAL =====================
    H(1,"5. Arquitectura general de SereOS")
    P("SereOS es un kernel monolítico para i686 que se ejecuta íntegramente en el anillo 0. La figura siguiente muestra las capas del sistema, desde el hardware que emula VirtualBox hasta las aplicaciones.")
    FIG("diagramas/d1_arquitectura_capas.png","Arquitectura por capas de SereOS 1.0","Diagrama elaborado por nosotros a partir de la estructura de carpetas y de los módulos del código fuente. Cada recuadro corresponde a archivos reales del proyecto.",w_in=6.3,max_h_in=6.2)
    H(2,"5.1 Tipo de kernel y decisiones de diseño")
    P("Se eligió un kernel monolítico por simplicidad: no hay que implementar comunicación entre procesos, cambio de contexto con pilas separadas ni llamadas al sistema para que el escritorio y las aplicaciones funcionen. A cambio, SereOS no ofrece aislamiento. Las decisiones principales fueron estas:")
    BUL([
        "**Modelo plano de memoria.** La GDT tiene cinco descriptores y todos cubren los 4 GiB. Los dos de anillo 3 están definidos pero ningún código los usa.",
        "**Paginación de identidad con PSE.** La dirección virtual coincide con la física hasta los 512 MiB, más el rango donde GRUB coloca el framebuffer.",
        "**Planificación cooperativa.** Cada tarea es una función que ejecuta un paso corto y regresa. Es sencillo y predecible, pero una tarea que se quede esperando congela la interfaz.",
        "**Interrupciones del PIC clásico.** No se usan APIC ni ACPI, lo que limita el sistema a un procesador.",
        "**Dibujo por software sobre el framebuffer de GRUB.** No hay controlador de video propio.",
        "**Una sola shell para dos pantallas.** La terminal gráfica y la consola VGA de respaldo ejecutan el mismo intérprete.",
    ])
    H(2,"5.2 Módulos del proyecto")
    P("La tabla siguiente resume el código fuente. Los números de líneas salen de contar los archivos con `wc -l`. De las 63 777 líneas del árbol del sistema, 46 880 son tablas de datos generadas (fuentes tipográficas, iconos, logotipo y efectos de sonido), así que el código escrito a mano ronda las 16 900 líneas.")
    TABLE("Módulos del sistema operativo",["Carpeta","Archivos","Líneas","Función"],[
        ["boot/","2","166","Cabecera Multiboot, pila, punto de entrada y 48 rutinas de interrupción"],
        ["kernel/","10","1 239","GDT, IDT, PIC, inicio, registro del kernel, pantalla de error y apagado"],
        ["drivers/","16","2 087","PIT, teclado, ratón, RTC, serie, altavoz, SB16, cola de entrada, consola VGA"],
        ["memory/","4","528","Marcos de 4 KiB, paginación PSE y heap kmalloc"],
        ["process/","4","273","Tareas cooperativas y planificador round-robin"],
        ["filesystem/","2","484","RAMFS en memoria"],
        ["audio/","4","7 592","Capa de audio y efectos de sonido (casi todo son datos)"],
        ["graphics/","11","17 272","Framebuffer, primitivas 2D y motor tipográfico (casi todo son datos)"],
        ["gui/","25","30 812","Compositor, ventanas, dock, cursor, tema, iconos y logotipo"],
        ["apps/","9","2 166","Terminal, Archivos, Monitor y Acerca de"],
        ["shell/ y libc/","4","1 117","Intérprete de comandos y funciones de cadena y memoria"],
    ],[1700,1100,1300,5260])
    H(2,"5.3 Estado de implementación por componente")
    P("La tabla resume qué está implementado y qué tan verificado quedó en esta validación. La columna de prueba indica dónde lo vimos funcionar. El detalle de cada prueba está en el capítulo 16.")
    TABLE("Estado de los componentes de SereOS",["Componente","Estado","Dónde se probó"],[
        ["Arranque GRUB y Multiboot 1","Implementado y probado","VirtualBox"],
        ["GDT propia, IDT y excepciones","Implementado y probado","VirtualBox (excepción 0 con ^^div0^^)"],
        ["PIC 8259 remapeado y PIT a 100 Hz","Implementado y probado","VirtualBox (^^ticks^^, ^^dmesg^^)"],
        ["Teclado PS/2","Implementado y probado","VirtualBox"],
        ["Ratón PS/2","Implementado y probado","QEMU (movimiento y clic)"],
        ["Reloj CMOS, puerto serie","Implementado y probado","VirtualBox (^^date^^, registro serie)"],
        ["Sound Blaster 16 (detección)","Implementado y probado","VirtualBox (^^audio^^, ^^dmesg^^)"],
        ["Reproducción audible por la SB16","Implementado, no probado","No se escuchó durante esta validación"],
        ["Marcos, paginación PSE y heap","Implementado y probado","VirtualBox (^^free^^, ^^sysinfo^^, Monitor)"],
        ["Planificador cooperativo","Implementado y probado","VirtualBox (Monitor, ^^sysinfo^^)"],
        ["RAMFS","Implementado y probado","VirtualBox (terminal y Archivos)"],
        ["Escritorio, ventanas, dock y topbar","Implementado y probado","VirtualBox y QEMU"],
        ["Maximizar y redimensionar ventanas","Parcial: maximizar probado","QEMU; el redimensionado no se ejercitó"],
        ["Consola VGA de respaldo","Implementado y probado","VirtualBox (segunda entrada de GRUB)"],
        ["Apagado y reinicio (menú del logotipo)","Implementado, no probado","Solo se vio el menú"],
        ["Multitarea preemptiva, anillo 3, syscalls","No implementado","Ver limitaciones"],
        ["Disco, red, USB","No implementado","Ver limitaciones"],
    ],[3500,2900,2960],sz=18)
