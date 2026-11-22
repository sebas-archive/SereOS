# -*- coding: utf-8 -*-
from engine import *
def build_d(D):
    P,H,BUL,NUM,CODE,TABLE,FIG=D.P,D.H,D.BUL,D.NUM,D.CODE,D.TABLE,D.FIG
    # ===================== 14 COMPILACION E ISO =====================
    H(1,"14. Compilación y generación de la ISO")
    H(2,"14.1 Dependencias")
    P("Las dependencias son las que documenta `docs/BUILD.md`. En CachyOS se instalan con un comando, y con él se tiene lo necesario para compilar, crear la ISO y probarla en QEMU:")
    CODE("sudo pacman -S --needed base-devel nasm grub xorriso mtools qemu-system-x86","Instalación de dependencias (Arch Linux y CachyOS)")
    P("El Makefile usa `i686-elf-gcc` si existe. Si no, compila con el `gcc` del sistema en modo `-m32`, que en Arch requiere el repositorio multilib y `lib32-gcc-libs`. Para probar en VirtualBox solo hace falta que esté instalado `virtualbox` con su módulo de kernel cargado (`vboxdrv`), como estaba en el equipo.")
    H(2,"14.2 Compilación desde cero")
    P("Antes de generar la ISO limpiamos los dos componentes para no reutilizar nada de compilaciones anteriores. Los comandos, ejecutados en la carpeta `sistema operativo`, fueron estos:")
    CODE("""cd "sistema operativo"
make clean        # borra build/, sereos.bin, sereos-text.bin, sereos.iso, isodir/
make game-clean   # borra build/ del componente "Pac-man SereOS"
make -j8          # game-lib (libpacman.a) + kernel + ISO""","Comandos de compilación")
    P("`make` equivale a `make all`, cuyo objetivo es `game-lib sereos.iso`. Primero compila el componente del juego en `../Pac-man SereOS/build/sereos/libpacman.a`; después compila los 50 archivos del sistema, los enlaza con la biblioteca, valida las cabeceras Multiboot, genera la variante de modo texto y arma la ISO. La compilación terminó con código de salida 0 y sin ninguna advertencia del compilador. Las últimas líneas de la salida fueron:")
    CODE("""[OK] kernel multiboot valido
multiboot text: flags 0x7 -> 0x3 en offset 4096
[OK] kernel multiboot modo texto valido
[OK] sereos.iso generada""","Salida final de make")
    H(2,"14.3 Opciones de compilación")
    TABLE("Opciones del compilador y del enlazador",["Opción","Razón"],[
        ["-m32 -march=i686","Código de 32 bits para i686"],
        ["-std=gnu99 -O2 -Wall -Wextra","Lenguaje C99 con extensiones GNU, optimización y advertencias"],
        ["-ffreestanding -nostdlib","El kernel no usa la biblioteca estándar del anfitrión"],
        ["-fno-pie -fno-pic -no-pie","El kernel se carga en una dirección fija (2 MiB)"],
        ["-fno-stack-protector","No hay soporte de protector de pila"],
        ["-fno-omit-frame-pointer","Conserva marcos de pila para depurar"],
        ["-mno-sse -mno-mmx -mno-sse2","El kernel no inicializa la FPU ni las unidades vectoriales"],
        ["-T linker.ld","Coloca el kernel en 2 MiB y alinea las secciones a 4 KiB"],
        ["-lgcc","Funciones auxiliares del compilador (por ejemplo, división de 64 bits)"],
    ],[3300,6060],sz=18)
    H(2,"14.4 Objetivos del Makefile")
    TABLE("Objetivos del Makefile del sistema",["Objetivo","Qué hace"],[
        ["make","Compila la biblioteca del juego, el kernel y la ISO"],
        ["make game-lib / game-clean","Recompila o limpia solo el componente del juego"],
        ["make run","Arranca la ISO en QEMU, con KVM si está disponible"],
        ["make run-audio","QEMU con Sound Blaster 16 y salida de audio del anfitrión"],
        ["make run-audio-wav","QEMU sin ventana que graba la salida de la SB16 en audio-capture.wav"],
        ["make run-headless","QEMU sin ventana; el registro serie queda en serial.log"],
        ["make clean","Borra los artefactos del sistema"],
    ],[3300,6060])
    H(2,"14.5 Generación y estructura de la ISO")
    P("El objetivo `sereos.iso` arma un directorio temporal `isodir/` con el kernel, la variante de modo texto y la configuración de GRUB, y le pide a `grub-mkrescue` que cree la imagen:")
    CODE("""mkdir -p isodir/boot/grub
cp sereos.bin       isodir/boot/sereos.bin
cp sereos-text.bin  isodir/boot/sereos-text.bin
cp grub.cfg         isodir/boot/grub/grub.cfg
grub-mkrescue -o sereos.iso isodir""","Pasos del objetivo sereos.iso")
    FIG("diagramas/d6_pipeline_iso.png","Cadena de construcción de la ISO","Diagrama propio basado en los Makefiles del sistema y del juego. Muestra cómo las fuentes del juego se convierten en libpacman.a y se enlazan al kernel antes de empaquetar la ISO.",w_in=6.3,max_h_in=6.2)
    P("La imagen resultante es híbrida: tiene registro de arranque El Torito para BIOS y también tablas MBR, GPT y APM, y contiene los módulos de GRUB para i386-pc, i386-efi y x86_64-efi. SereOS solo arranca por BIOS con Multiboot 1. La ubicación del kernel dentro de la ISO es `/boot/sereos.bin`.")
    H(2,"14.6 Verificación de la ISO")
    P("Para no usar una ISO antigua por error comprobamos que la imagen correspondía a la última compilación. Antes de recompilar, la ISO existente tenía el mismo tamaño pero otro SHA-256, y después de la compilación cambió su hash y su fecha. También extrajimos `boot/sereos.bin` de la ISO nueva y su SHA-256 es idéntico al del `sereos.bin` compilado.")
    TABLE("Artefactos de la compilación",["Archivo","Tamaño (bytes)","SHA-256"],[
        ["sereos.iso","36 835 328","4fe9ea95131e571082a6ea07a471aaf4cb1549aaa2ad702a68ea87599d7c96d9"],
        ["sereos.bin","1 526 240","ca9bf32ab10b9894c0b44fd568f65e7f2b42947ef66cb56a541475ad477cc1f4"],
        ["sereos-text.bin","1 526 240","627bcc1fde2bd51ff945bda1c4bde255f213a0f5b4e4bad8cf1261212482ce07"],
        ["libpacman.a","337 972 (330,1 KiB)","b20b7f98193fabbc71617ea63b0878e70b50f2559575e092b6a728bb72478301"],
        ["ISO anterior","36 835 328","44d94650f148b62618b036a68cafe504fab269852ed43a5e98edaf8aedd85ba9"],
    ],[2000,1900,5460],sz=17,note="La compilación y los hashes son de la sesión del 20 de noviembre de 2026. La ISO anterior es la que había antes de ejecutar make clean y se muestra solo para comparar.")
    P("El contenido de `/boot` en la imagen es `sereos.bin`, `sereos-text.bin` y la carpeta `grub` con `grub.cfg` y los módulos. El `grub.cfg` de la imagen es el mismo archivo de la raíz del proyecto. La imagen pesa 35,1 MiB, casi todo por los módulos y las fuentes de GRUB y por los datos incrustados en el kernel.")
    P("**Una ISO bien generada no está validada solo por eso.** La validación de esta ISO es la que se describe en los capítulos 15 y 16, donde se arranca y se usa.")

    # ===================== 15 VIRTUALBOX =====================
    H(1,"15. Configuración y ejecución en Oracle VM VirtualBox")
    H(2,"15.1 Máquina virtual")
    P("Creamos una máquina nueva, «SereOS Final», sin tocar la que ya existía en el equipo para las pruebas de audio («SereOS Audio»). La configuración sigue lo que el sistema necesita: arranque por BIOS, un procesador, 256 MiB de memoria, controlador gráfico VBoxVGA (el que expone un framebuffer lineal compatible con VBE que GRUB sabe usar), sin disco duro y con la ISO en una unidad óptica IDE.")
    TABLE("Configuración de la máquina virtual",["Parámetro","Valor"],[
        ["Nombre y tipo","SereOS Final, Other/Unknown"],
        ["Memoria y procesadores","256 MiB, 1 CPU"],
        ["Chipset y firmware","PIIX3, BIOS (sin EFI)"],
        ["Controlador gráfico","VBoxVGA, 32 MiB de memoria de video"],
        ["APIC, HPET, PAE","Desactivados (SereOS usa el PIC clásico)"],
        ["Almacenamiento","Controlador IDE PIIX4; ISO en el maestro del canal secundario; sin disco"],
        ["Orden de arranque","DVD primero, resto ninguno"],
        ["Audio","SoundBlaster 16, salida activada, entrada desactivada, controlador del anfitrión PulseAudio"],
        ["Red","Sin adaptador"],
        ["Teclado y ratón","PS/2"],
        ["Puerto serie","COM1 (0x3F8, IRQ 4) conectado a un archivo del anfitrión"],
        ["Versión de VirtualBox","7.2.22r175245 con el paquete de extensión 7.2.22"],
    ],[3000,6360],sz=18)
    H(2,"15.2 Comandos usados")
    CODE("""VBoxManage createvm --name "SereOS Final" --ostype Other --register
VBoxManage modifyvm "SereOS Final" --memory 256 --vram 32 --cpus 1 \\
    --chipset piix3 --firmware bios --graphicscontroller vboxvga \\
    --ioapic off --hpet off --pae off --boot1 dvd --boot2 none \\
    --boot3 none --boot4 none --nic1 none --audio-driver pulse \\
    --audio-controller sb16 --audio-enabled on --audio-out on \\
    --audio-in off --mouse ps2 --keyboard ps2
VBoxManage storagectl "SereOS Final" --name IDE --add ide \\
    --controller PIIX4 --bootable on
VBoxManage storageattach "SereOS Final" --storagectl IDE --port 1 \\
    --device 0 --type dvddrive --medium ".../sistema operativo/sereos.iso"
VBoxManage modifyvm "SereOS Final" --uart1 0x3F8 4 --uartmode1 file RUTA.log
VBoxManage startvm "SereOS Final" --type headless""","Creación y arranque de la máquina virtual")
    H(2,"15.3 Cómo se tomaron las capturas")
    P("Iniciamos la máquina en modo `headless`, sin ventana, y la manejamos con `VBoxManage controlvm`. Las capturas se obtienen con `screenshotpng`, que guarda el contenido del framebuffer virtual a su resolución nativa, y las teclas se envían con `keyboardputscancode`. Es la forma de tomar una captura directamente desde VirtualBox, sin pasar por el escritorio del anfitrión.")
    CODE("""VBoxManage controlvm "SereOS Final" screenshotpng captura.png
VBoxManage controlvm "SereOS Final" keyboardputscancode 3c bc   # F2 (pulsar y soltar)
VBoxManage controlvm "SereOS Final" keyboardputstring "help"
VBoxManage controlvm "SereOS Final" reset""","Control de la máquina durante las pruebas")
    P("Dos cosas conviene decir con claridad. Primero, no usamos la ventana del Administrador de VirtualBox, porque la máquina corrió sin interfaz. Segundo, VirtualBox no ofrece una orden para mover el ratón de la máquina virtual, así que las pruebas de ratón se hicieron en QEMU. En el equipo no instalamos Guest Additions, que SereOS no tiene.")
    H(2,"15.4 Procedimiento de prueba")
    NUM([
        "Arrancar la máquina y detener la cuenta atrás de GRUB con la flecha arriba para fotografiar el menú.",
        "Elegir la primera entrada y fotografiar la transición, el splash y el escritorio.",
        "Abrir la terminal con F2 y ejecutar los comandos de la shell, fotografiando cada grupo.",
        "Abrir Archivos, Monitor y Acerca de con F1, F3 y F5, y comprobar el cierre con Ctrl+W.",
        "Abrir el juego con F4, recorrer los menús y jugar varias partidas.",
        "Provocar la excepción con div0 y reiniciar.",
        "Reiniciar y elegir la segunda entrada de GRUB para probar la consola de texto.",
        "Guardar el registro del puerto serie de cada sesión.",
    ])
    P("**Resultado de la prueba de arranque.** Con la ISO final, la máquina mostró el logotipo de VirtualBox, después el menú de GRUB, y al elegir la primera entrada llegó al escritorio. El registro serie contiene `SEREOS_BOOT_OK mem=255MiB`, `SPLASH_DONE`, `GUI_READY` y `GUI_LOOP`, y la barra superior marcaba un tiempo encendido de 6 segundos cuando tomamos la captura del escritorio.")

    # ===================== 16 PRUEBAS FUNCIONALES =====================
    H(1,"16. Pruebas funcionales")
    P("La tabla recoge las pruebas que ejecutamos en esta validación. En la columna de resultado, OK significa que el comportamiento observado coincide con lo esperado y que hay evidencia (captura o registro) citada en el capítulo indicado. No se incluyen pruebas que no hicimos.")
    TABLE("Pruebas ejecutadas y resultado",["Id","Prueba","Entorno","Resultado","Evidencia"],[
        ["P01","La ISO existe, es nueva y su kernel coincide con el compilado","CachyOS","OK","Cap. 14"],
        ["P02","Cabecera Multiboot válida en sereos.bin y sereos-text.bin","CachyOS","OK","Cap. 14"],
        ["P03","Compilación limpia sin advertencias","CachyOS","OK","Anexo A"],
        ["P04","GRUB muestra dos entradas y cuenta 2 s","VirtualBox","OK","Cap. 7"],
        ["P05","Arranque gráfico hasta el escritorio","VirtualBox","OK","Cap. 9, Anexo D"],
        ["P06","Splash con mensajes del kernel","VirtualBox","OK","Cap. 7"],
        ["P07","Detección de la SB16","VirtualBox","OK","dmesg, audio"],
        ["P08","Terminal con F2; help, sysinfo, version","VirtualBox","OK","Cap. 10"],
        ["P09","dmesg: 17 entradas, 0 errores","VirtualBox","OK","Cap. 10"],
        ["P10","mem, free, ticks (3 439 ticks en 34 s), date","VirtualBox","OK","Cap. 10"],
        ["P11","RAMFS: mkdir, cd, write, cat, ls","VirtualBox","OK","Cap. 10"],
        ["P12","Errores: archivo inexistente y comando inválido","VirtualBox","OK","Cap. 10"],
        ["P13","Archivos muestra lo creado desde la terminal","VirtualBox","OK","Cap. 11"],
        ["P14","Monitor con datos reales","VirtualBox","OK","Cap. 11"],
        ["P15","Acerca de: 14 de 14 componentes","VirtualBox","OK","Cap. 11"],
        ["P16","Varias ventanas y cierre con Ctrl+W","VirtualBox","OK","Cap. 9"],
        ["P17","Consola de texto: help y sysinfo","VirtualBox","OK","Cap. 10"],
        ["P18","Excepción 0 con div0 y pantalla de error","VirtualBox","OK","Cap. 10, Anexo D"],
        ["P19","Menú del logotipo y ayuda del dock","QEMU","OK","Cap. 9"],
        ["P20","Maximizar y restaurar con navegación superior","QEMU","OK","Cap. 9"],
        ["P21","Abrir el juego con F4 desde el escritorio","VirtualBox","OK","Cap. 13"],
        ["P22","Atracción, menú e instrucciones del juego","VirtualBox","OK","Cap. 13"],
        ["P23","Partida: movimiento, puntos, puntuación y vidas","VirtualBox","OK","Cap. 13, Anexo D"],
        ["P24","Píldora de poder y estado asustado","VirtualBox","OK","Cap. 13"],
        ["P25","Captura de fantasmas (GHOST_EATEN)","VirtualBox","OK","Cap. 13, Anexo D"],
        ["P26","Aparece la fruta","VirtualBox","OK","Cap. 13"],
        ["P27","Muerte de Pac-Man y pérdida de vida","VirtualBox","OK","Cap. 13"],
        ["P28","Pausa con Esc","VirtualBox","OK","Cap. 13"],
        ["P29","Fin de juego y reintento","VirtualBox","OK","Cap. 13"],
        ["P30","Pruebas del componente: 209 comprobaciones y 7 de humo","CachyOS","OK","Anexo E"],
    ],[600,3900,1400,1100,2360],sz=17)
    P("De estas 30 pruebas, 24 se ejecutaron en VirtualBox, 4 en CachyOS (herramientas del anfitrión y pruebas del componente) y 2 en QEMU. Las 30 dieron el resultado esperado. Esto no demuestra que no haya errores, y la lista siguiente es lo que no probamos o no logramos reproducir.")
    TABLE("Lo que no se probó o no se logró",["Funcionalidad","Estado","Motivo"],[
        ["Sonido audible por los altavoces","Implementado, no probado","No lo escuchamos; solo se verificó la detección de la SB16"],
        ["Apagar y reiniciar desde el menú","Implementado, no probado","Solo se vio el menú"],
        ["Mover y redimensionar ventanas","Implementado, no probado","Se probó maximizar y cerrar"],
        ["Comer la fruta","Implementado, no probado","No se capturó ese instante"],
        ["Pasar de nivel en VirtualBox","Implementado, no probado en VirtualBox","El estado se mostró con la escena forzada de CachyOS"],
        ["Pantalla de récords","Implementado, no probado","No se abrió"],
        ["Arranque en hardware físico","No probado","No se dispuso de él"],
        ["Ejecución del arnés automático de 18 pruebas del proyecto","No repetida","Se citan sus resultados anteriores, sin presentarlos como nuestros"],
    ],[3300,2700,3360],sz=18)

    # ===================== 17 EVIDENCIAS =====================
    H(1,"17. Evidencias y capturas")
    P("Todas las capturas originales están en la carpeta `documentacion/capturas/`, organizadas por categoría. Se conservaron sin edición, salvo el recorte ampliado del cursor, que se rotula.")
    TABLE("Carpetas de evidencias",["Carpeta","Contenido","Procedencia"],[
        ["01_arranque/","Menú de GRUB, selección de modo texto, splash","VirtualBox"],
        ["02_escritorio/","Escritorio y escenas del dock, menú y maximizado","VirtualBox y QEMU (nombres con prefijo qemu_)"],
        ["03_terminal/","Comandos, pantalla de error y modo texto","VirtualBox"],
        ["04_aplicaciones/","Archivos, Monitor, Acerca de y multiventana","VirtualBox"],
        ["05_pacman_sereos_vbox/","El juego dentro de SereOS","VirtualBox"],
        ["06_pacman_cachyos/","Escenas del binario de Linux y resultado de make test","CachyOS (SDL2)"],
        ["07_virtualbox/","Registros del puerto serie de cada sesión","VirtualBox y QEMU"],
        ["00_historicas_avances/","Cuatro capturas de los avances de octubre","QEMU, documento de avances"],
    ],[2800,3800,2760],sz=18)
    FIG("capturas/02_escritorio/cursor_ampliado.png","Cursor del sistema, ampliado diez veces","Recorte de 36x36 píxeles de la captura del escritorio en VirtualBox, ampliado con interpolación por vecino más cercano. Se ve la flecha de 12x18 píxeles con contorno oscuro que dibuja gui/cursor.c.",w_in=2.0,max_h_in=2.3)
    H(2,"17.1 Registros del puerto serie")
    P("Junto a las imágenes guardamos el registro del puerto serie de cada sesión, que es una evidencia que no depende de la interfaz: contiene el registro del kernel, los marcadores de aplicación y los de la excepción. Son archivos de texto en `documentacion/capturas/07_virtualbox/`.")

    # ===================== 18 RESULTADOS =====================
    H(1,"18. Resultados obtenidos")
    TABLE("Cumplimiento de los objetivos específicos",["Objetivo","Resultado"],[
        ["1. Kernel Multiboot con GDT, IDT, PIC, temporizador y entrada","Cumplido y probado en VirtualBox"],
        ["2. Memoria, planificador cooperativo y RAMFS","Cumplido; la planificación es cooperativa, no preemptiva"],
        ["3. Escritorio gráfico con ventanas, dock, barra y aplicaciones","Cumplido y probado; mover y redimensionar sin probar"],
        ["4. Shell compartida con 25 comandos","Cumplido y probado en la terminal gráfica y en la consola de texto"],
        ["5. PAC-MAN SereOS integrado como aplicación nativa","Cumplido y probado en VirtualBox con partidas reales"],
        ["6. Compilación y ISO automáticas","Cumplido: una sola orden make genera la ISO"],
        ["7. Validación en VirtualBox con evidencia","Cumplido, con las excepciones de la sección 16"],
    ],[5200,4160],sz=18)
    TABLE("Cifras de la ejecución",["Medida","Valor","Fuente"],[
        ["Tamaño de la ISO","36 835 328 bytes (35,1 MiB)","ls y xorriso"],
        ["Tamaño del kernel","1 526 240 bytes","ls"],
        ["Memoria detectada","262 080 KiB (255 MiB)","sysinfo, Acerca de"],
        ["Marcos de 4 KiB","65 520 en total, 59 992 libres","sysinfo, free"],
        ["Memoria usada tras el arranque","21 MB (8 %)","Barra superior, Monitor"],
        ["Entradas del registro del kernel","17, sin errores","dmesg"],
        ["Frecuencia del temporizador","100 Hz; 3 439 ticks en 34,4 s","ticks"],
        ["Tiempo desde GRUB hasta el escritorio","Unos 6 s con GRUB a 2 s","Barra superior"],
        ["Comprobaciones del núcleo del juego","209, sin fallos","make test"],
    ],[3500,3300,2560],sz=18)
    P("En las partidas de prueba el registro serie recogió `PAC_STATS` con la puntuación, los puntos restantes y las vidas en cada pérdida de vida. En una partida se llegó a 1 490 puntos y se capturaron fantasmas, lo que prueba que la lógica de puntuación, el estado asustado y la IA funcionan sobre el sistema.")

    # ===================== 19 LIMITACIONES =====================
    H(1,"19. Limitaciones actuales")
    P("Esta lista reúne las limitaciones del propio proyecto (comprobadas contra el código y el documento `docs/LIMITATIONS.md`) y las de esta validación.")
    H(2,"19.1 Del sistema operativo")
    BUL([
        "Planificación cooperativa. Una tarea que no cede el control congela el escritorio.",
        "Sin espacio de usuario ni llamadas al sistema. Kernel y aplicaciones comparten privilegios y memoria, y un fallo de una aplicación puede detener todo.",
        "Paginación de identidad sin aislamiento entre aplicaciones.",
        "Un solo procesador, sin APIC ni ACPI. El apagado se hace con las órdenes de apagado de los emuladores.",
        "Sin coma flotante en el kernel.",
        "RAMFS volátil con límites fijos: 64 nodos, 1 024 bytes por archivo. No hay disco, red ni USB.",
        "Audio de 8 bits y un canal, a 11 025 Hz.",
        "Renderizado por software. Está pensado para 1024x768, con 1280x1024 y 800x600 como alternativas que verificó el proyecto en QEMU.",
        "Máximo de 8 ventanas, 32 tareas y un historial de 16 líneas en la shell.",
        "Teclado de distribución de Estados Unidos.",
        "Arranque por BIOS con Multiboot 1. No hay arranque UEFI nativo.",
    ])
    H(2,"19.2 Del juego")
    P("Las limitaciones del juego están en la sección 12.18. Los recursos gráficos y sonoros provienen de archivos de terceros con apariencia del juego original, sin licencia declarada, y el proyecto los documenta como material para uso académico y sin redistribución pública. Por eso la ISO de esta entrega, que incluye esos datos, no se debe publicar. La licencia se detalla en `Pac-man SereOS/assets/LICENSE_RES.md`.")
    H(2,"19.3 De esta validación")
    BUL([
        "No se probó en hardware físico.",
        "No se verificó el sonido con los oídos.",
        "No se usó la interfaz gráfica de VirtualBox. La máquina corrió sin ventana y se controló con VBoxManage.",
        "Las pruebas de ratón se hicieron en QEMU porque VirtualBox no permite moverlo desde la línea de comandos.",
        "Los estados del juego difíciles de alcanzar (nivel completado) se muestran con escenas forzadas del binario de Linux.",
        "Nos apoyamos en un programa auxiliar que lee las capturas y teclea para llegar a algunos estados del juego. No modifica el juego, pero no es un jugador humano.",
    ])
    H(2,"19.4 Discrepancias entre documentos y proyecto")
    P("Encontramos varias diferencias entre los documentos anteriores y el estado verificable del proyecto. En todos los casos usamos el estado verificable. La lista completa está en el anexo F.")

    # ===================== 20 CONCLUSIONES =====================
    H(1,"20. Conclusiones")
    P("SereOS cumple lo que prometía la primera entrega: un kernel propio que arranca con GRUB y se puede usar. Lo que empezó como cinco archivos que escribían texto en la pantalla es hoy un sistema con interrupciones, memoria, tareas, sistema de archivos, audio y un escritorio gráfico, y la ISO final arrancó en VirtualBox sin ayuda del sistema anfitrión.")
    P("La prueba más convincente no fue una captura del escritorio, sino jugar. Una partida de PAC-MAN SereOS usa a la vez el temporizador, la cola de entrada, el compositor, el heap y las tareas. Que las partidas funcionaran sobre la ISO, con fantasmas que persiguen, píldoras que los asustan y vidas que se pierden, dice más del sistema que cualquier lista de componentes. El registro del puerto serie nos dio algo que las imágenes no dan: la confirmación de cada estado por el propio sistema.")
    P("También aprendimos qué se pierde al elegir un diseño sencillo. El modelo cooperativo y la falta de espacio de usuario hicieron la implementación manejable, pero dejan al sistema sin ninguna protección: un error en una aplicación se lleva el kernel. Esa es la limitación que más pesa, y el trabajo futuro empieza por ahí.")
    P("Por último, la validación mostró que documentar es parte del trabajo técnico. Los documentos anteriores describían una pila de 16 KiB, una shell de 8 comandos y una paginación pendiente que ya no eran ciertas. Tuvimos que contrastar cada afirmación con el código y con la ejecución, y dejar por escrito lo que no pudimos probar: el sonido audible, el apagado, el nivel completado dentro de VirtualBox y el hardware físico.")

    # ===================== 21 TRABAJO FUTURO =====================
    H(1,"21. Trabajo futuro")
    P("Lo que sigue es una propuesta y no un compromiso. Está ordenado de mayor a menor impacto sobre las limitaciones actuales.")
    NUM([
        "**Multitarea preemptiva.** Cambio de contexto con pilas separadas y uso de la interrupción del PIT para repartir turnos. Era la etapa 4 del plan de los avances y quedó en su versión cooperativa.",
        "**Espacio de usuario.** Usar los descriptores de anillo 3 que la GDT ya define, con llamadas al sistema y páginas separadas por proceso.",
        "**Almacenamiento persistente.** Un controlador de disco y un sistema de archivos que sobreviva a los reinicios, para guardar el récord del juego y los archivos del usuario.",
        "**Pruebas en hardware físico**, con entrada USB, que hoy no está soportada.",
        "**Ratón absoluto.** Soporte para el ratón absoluto de las máquinas virtuales, para evitar las diferencias de movimiento relativo.",
        "**Más contenido en el juego.** Laberintos adicionales, modo de demostración y un selector de estilo visual.",
        "**Pruebas de interfaz con ratón en VirtualBox**, con la ventana del Administrador, para completar la cobertura que aquí se hizo en QEMU.",
        "**Sustitución de los recursos de terceros** del juego por arte y sonido propios, para poder publicar la ISO.",
    ])

    # ===================== REFERENCIAS =====================
    H(1,"Referencias")
    refs=[
        "Creative Technology Ltd. (1996). ^^Sound Blaster Series hardware programming guide^^. Creative Labs.",
        "Free Software Foundation. (2009). ^^Multiboot specification, version 0.6.96^^. https://www.gnu.org/software/grub/manual/multiboot/multiboot.html",
        "GNU Project. (s. f.). ^^GNU GRUB manual 2.12^^. https://www.gnu.org/software/grub/manual/grub/grub.html",
        "Intel Corporation. (s. f.). ^^Intel 64 and IA-32 architectures software developer's manual^^. Intel.",
        "Oracle. (s. f.). ^^Oracle VM VirtualBox user manual^^. https://www.virtualbox.org/manual/",
        "OSDev Wiki. (s. f.). ^^Bare Bones^^. https://wiki.osdev.org/Bare_Bones",
        "Pittman, J. (2009). ^^The Pac-Man dossier^^. Game Developer. https://www.gamedeveloper.com/design/the-pac-man-dossier",
        "QEMU Project. (s. f.). ^^QEMU documentation^^. https://www.qemu.org/docs/master/",
        "Silberschatz, A., Galvin, P. B. y Gagne, G. (2018). ^^Operating system concepts^^ (10.ª ed.). Wiley.",
        "Simple DirectMedia Layer. (s. f.). ^^SDL2 documentation^^. https://www.libsdl.org/",
        "Tanenbaum, A. S. y Bos, H. (2015). ^^Modern operating systems^^ (4.ª ed.). Pearson.",
    ]
    for r in refs:
        D.body.append(D.para(D.runs(r),'<w:spacing w:before="0" w:after="100" w:line="300" w:lineRule="auto"/><w:ind w:left="720" w:hanging="720"/><w:jc w:val="left"/>'))
    P("Las fuentes tipográficas Inter y JetBrains Mono usan la licencia SIL Open Font License 1.1. La fuente arcade Press Start K es de codeman38. Los datos de los documentos internos del proyecto (README, CHANGELOG y la carpeta docs de cada componente) se citan por su nombre de archivo en el texto.",sz=21,color=GREY)

    # ===================== ANEXOS =====================
    H(1,"Anexos")
    H(2,"Anexo A. Salida de la compilación")
    P("Resumen del registro de la compilación completa. Hubo 49 invocaciones de gcc, 2 de NASM, ninguna advertencia y el código de salida fue 0. Se muestra una invocación representativa (acortada) y la salida final.")
    CODE("""gcc -m32 -std=gnu99 -ffreestanding -fno-pie -fno-pic -fno-stack-protector \\
  -fno-asynchronous-unwind-tables -fno-omit-frame-pointer -march=i686 -m32 \\
  -mno-sse -mno-mmx -mno-sse2 -O2 -Wall -Wextra -Wno-unused-parameter \\
  -Wno-address-of-packed-member -DSEREOS_HOST_GCC -I. -Iinclude -Iboot ... \\
  -MMD -MP -c shell/shell.c -o build/shell/shell.o
nasm -f elf32 boot/boot.s -o build/boot/boot.o
nasm -f elf32 boot/isr.s  -o build/boot/isr.o
gcc -m32 -m32 -T linker.ld -ffreestanding -nostdlib -no-pie -Wl,--build-id=none \\
  -o sereos.bin build/.../*.o "../Pac-man SereOS/build/sereos/libpacman.a" -lgcc
[OK] kernel multiboot valido
multiboot text: flags 0x7 -> 0x3 en offset 4096
[OK] kernel multiboot modo texto valido
[OK] sereos.iso generada""","Extracto de make")
    P("Cabeceras del programa del kernel (`readelf -lW sereos.bin`):")
    CODE("""Type  Offset   VirtAddr   PhysAddr   FileSiz MemSiz  Flg Align
LOAD  0x001000 0x00200000 0x00200000 0x2b192 0x2b192 R E 0x1000
LOAD  0x02d000 0x0022c000 0x0022c000 0x12e5c0 0x12e5c0 R   0x1000
LOAD  0x16b000 0x0035b000 0x0035b000 0x00150 0x132c8e0 RW  0x10000
Entry point 0x21fba0    Class: ELF32    Machine: Intel 80386""","Programa de sereos.bin")
    H(2,"Anexo B. Estructura del proyecto")
    CODE("""sereos02/
  sistema operativo/          kernel, drivers, escritorio y aplicaciones
    boot/        boot.s, isr.s
    kernel/      gdt.c, idt.c, kernel.c, log.c, panic.c, shutdown.c
    drivers/     timer, keyboard, mouse, rtc, serial, speaker, sb16, input
    memory/      page.c (marcos y paginacion), kmalloc.c (heap)
    process/     task.c, scheduler.c
    filesystem/  fs.c (RAMFS)
    audio/       audio.c, sfx_data.c
    graphics/    framebuffer.c, graphics.c, text.c, font.c, datos de fuentes
    gui/         desktop.c, window.c, gui.c, cursor.c, splash.c, theme.c, ui.c...
    apps/        terminal/, filemanager/, sysmonitor/, about/, apps.c
    shell/       shell.c      libc/ string.c     include/ version y tipos
    tools/       generadores de fuentes e iconos, pruebas con QEMU
    docs/        BUILD, RUN, FEATURES, LIMITATIONS, DESIGN, AUDIO, capturas
    grub.cfg  linker.ld  Makefile  sereos.bin  sereos-text.bin  sereos.iso
  Pac-man SereOS/             videojuego (componente independiente)
    src/core, src/render, src/platform/sereos, src/platform/linux
    include/ assets/ tests/ tools/ docs/  Makefile  run.sh
  documentacion/              capturas, diagramas y evidencias de esta entrega""","Estructura de carpetas")
    H(2,"Anexo C. Configuración de la máquina virtual")
    P("Extracto de `VBoxManage showvminfo \"SereOS Final\" --machinereadable`. El archivo completo está en `documentacion/evidencias/vm_showvminfo.txt`.")
    CODE("""name="SereOS Final"            ostype="Other/Unknown"
memory=256                     vram=32            cpus=1
chipset="piix3"                firmware="BIOS"    ioapic="off"   hpet="off"
graphicscontroller="vboxvga"   boot1="dvd"
storagecontrollername0="IDE"   storagecontrollertype0="PIIX4"
"IDE-1-0"=".../sistema operativo/sereos.iso"
nic1="none"                    audio_out="on"     audio_in="off"
uart1="0x03f8,4"               uartmode1="file,.../serial_vbox.log"
VBoxManage 7.2.22r175245""","Configuración de la máquina")
    H(2,"Anexo D. Registro del puerto serie en VirtualBox")
    P("Arranque del kernel hasta el escritorio, tal como lo escribió SereOS en COM1 y recogió VirtualBox:")
    CODE("""[OK] Arranque Multiboot verificado (GRUB 2)
[OK] GDT propia: 5 segmentos (kernel y usuario)
[OK] IDT: 32 excepciones + 16 IRQ (PIC remapeado a 32-47)
[OK] Temporizador PIT a 100 Hz (IRQ 0)
[OK] Teclado PS/2 con eventos (IRQ 1)
[OK] Raton PS/2 con eventos (IRQ 12)
[OK] Reloj CMOS RTC
[OK] Framebuffer grafico 1024x768x32 validado
[OK] Allocator de marcos fisicos inicializado
[OK] Heap del kernel (kmalloc/kfree) inicializado
[OK] Paginacion activada (identidad, PSE 4 MiB)
[OK] RAMFS montado en /
[OK] Planificador cooperativo round-robin listo
[OK] Interrupciones habilitadas
[OK] Audio: SB16 0x220 IRQ5 DMA1
[OK] Motor grafico nativo inicializado
[OK] Aplicaciones del escritorio registradas
DESKTOP_INIT  DESKTOP_READY  SEREOS_BOOT_OK mem=255MiB
SPLASH_DONE   GUI_READY      GUI_LOOP""","Arranque (sesión de VirtualBox)")
    P("Excepción de división por cero y arranque en modo texto, de otras dos sesiones:")
    CODE("""APP_OPEN:terminal
SEREOS_EXCEPTION EIP = 0x0021ec1d   CS = 0x0008   EFLAGS = 0x00010246
EAX = 0x0000000a   EBX = 0x00d90988   ECX = 0x00000005   EDX = 0x00000000
Codigo de error = 0x00000000
...
Iniciando consola de texto de respaldo
SEREOS_TEXT_MODE""","Excepción y modo texto")
    H(2,"Anexo E. Resultado de las pruebas del juego en CachyOS")
    CODE("""PASS B5: al recuperar el foco rearma la sirena
PASS B5: minimizar resetea el one-shot en curso
...
checks=209 failures=0
[OK] harness de core
== smoke Linux (SDL dummy: menu/play/pause/gameover/victory) ==
[OK] smoke attract    [OK] smoke menu     [OK] smoke settings
[OK] smoke play       [OK] smoke pause    [OK] smoke gameover
[OK] smoke victory
TODAS LAS PRUEBAS OK""","Salida de make test en Pac-man SereOS")
    P("El binario de Linux de esta compilación (`build/pacman-sereos`) tiene SHA-256 `5d341dc2b5dc2df4f4938332de08aec2c27c30c897a7b34edbbfad287c04a6ae`. No coincide con la suma MD5 que citaba el README del componente, porque lo recompilamos en esta validación.")
    H(2,"Anexo F. Discrepancias entre documentos y proyecto")
    TABLE("Diferencias detectadas",["Tema","Documento anterior","Estado verificado"],[
        ["Pila inicial del kernel","16 KiB (avances)","64 KiB (boot/boot.s)"],
        ["Compilador","i686-elf-gcc (avances y README)","gcc -m32 del sistema, porque el cruzado no estaba instalado; el Makefile soporta ambos"],
        ["Comandos de la shell","8 (avances v0.2)","25"],
        ["Temporizador de GRUB","3 s, GRUB 2.12 (avances)","2 s, GRUB 2.16"],
        ["Paginación y kmalloc","Pendientes en v0.3 (avances)","Implementadas (PSE y heap de 8 MiB)"],
        ["Multitarea","Preemptiva prevista en v0.4","Cooperativa round-robin implementada; la preemptiva no existe"],
        ["Velocidad del puerto serie","38 400 baudios (LIMITATIONS.md)","115 200 baudios (drivers/serial.c)"],
        ["Tamaño de la ISO","36 282 368 bytes (README)","36 835 328 bytes (ISO generada hoy)"],
        ["Pruebas del juego","131 comprobaciones (README)","209 comprobaciones (make test hoy)"],
        ["Archivos del sistema","15 archivos y 674 líneas (avances v0.2)","93 archivos y 63 777 líneas, de las cuales 46 880 son datos generados"],
        ["Apagado por ACPI","Sin ACPI (LIMITATIONS.md)","Apagado con órdenes de emuladores (QEMU, Bochs, VirtualBox), sin parser ACPI"],
    ],[2400,3300,3660],sz=17)
    H(2,"Anexo G. Archivos y contrato del juego (extracto)")
    CODE("""/* include/pac_platform.h (ABI 1), funciones del ciclo de vida y el tiempo */
int      pac_platform_init(void);
void     pac_platform_shutdown(void);
int      pac_platform_width(void);
int      pac_platform_height(void);
void     pac_platform_content_rect(pac_rect_t *out);
int      pac_platform_focused(void);        /* el nucleo congela si es 0 */
int      pac_platform_minimized(void);
void     pac_platform_request_close(void);
void     pac_platform_log(const char *marker);   /* serie en SereOS */
uint32_t pac_time_ms(void);
void    *pac_alloc(size_t size);            /* kmalloc en SereOS */
void     pac_free(void *ptr);
int      pac_storage_read(const char *key, void *buf, int max_len);
int      pac_storage_write(const char *key, const void *buf, int len);""","Extracto del contrato de plataforma")
