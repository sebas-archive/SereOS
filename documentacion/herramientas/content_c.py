# -*- coding: utf-8 -*-
from engine import *
def build_c(D):
    P,H,BUL,NUM,CODE,TABLE,FIG=D.P,D.H,D.BUL,D.NUM,D.CODE,D.TABLE,D.FIG
    V="capturas/05_pacman_sereos_vbox/"
    # ===================== 12 ARQUITECTURA DEL JUEGO =====================
    H(1,"12. Arquitectura de PAC-MAN SereOS")
    H(2,"12.1 Objetivo del videojuego")
    P("PAC-MAN SereOS es un juego arcade de laberinto, con Pac-Man, cuatro fantasmas con inteligencia propia, puntos, píldoras de poder, frutas, vidas, récord y efectos de sonido. Su objetivo en el proyecto es doble. Como juego, debe ser jugable y fiel a las reglas clásicas. Como componente, debe demostrar que SereOS es capaz de ejecutar una aplicación interactiva de tiempo real con dibujo, teclado, temporización y audio.")
    P("Es un juego original en su código, su interfaz y sus menús. Sus recursos gráficos y de audio, en cambio, vienen de un paquete de archivos de apariencia arcade que nos facilitaron para uso académico (ver el capítulo de limitaciones).")
    H(2,"12.2 Justificación de la integración con SereOS")
    BUL([
        "Es una carga de trabajo exigente y fácil de juzgar. Si fallan el temporizador, la entrada, el dibujo o el audio del sistema, el juego lo muestra de inmediato.",
        "Obliga a definir una interfaz de aplicación en el escritorio: cómo se registra, cómo recibe eventos, cómo dibuja dentro de una ventana y cómo se cierra sin dejar memoria sin liberar.",
        "Permite desarrollar y depurar la lógica en CachyOS, con SDL2 y las herramientas habituales, y llevarla después al sistema sin reescribirla.",
        "Pone a prueba las limitaciones reales del sistema, como el modelo cooperativo y la aritmética sin coma flotante.",
    ])
    H(2,"12.3 Organización en capas")
    P("El diseño separa tres cosas: la lógica del juego, el dibujo de pantallas y la plataforma. El núcleo (`src/core`) nunca incluye cabeceras de SereOS ni de SDL; solo conoce el contrato `include/pac_platform.h`. El render compartido (`src/render`) dibuja menús, HUD y laberinto usando únicamente las primitivas de ese contrato. Dos adaptadores implementan el contrato: uno para SereOS y otro para Linux.")
    FIG("diagramas/d5_arquitectura_juego.png","Arquitectura de PAC-MAN SereOS","Diagrama propio basado en la estructura de carpetas del componente y en docs/ARCHITECTURE.md. Las líneas de código salen de contar src/core, src/render y los dos adaptadores.",w_in=6.3,max_h_in=6.2)
    TABLE("Módulos del juego",["Archivo","Función"],[
        ["src/core/game.c","Máquina de estados (atracción, menús, partida, pausa, fin de juego, nivel completado), puntuación, vidas y bucle de actualización"],
        ["src/core/game_maze.c","Mapa de 28x31, clasificación de casillas y laberinto prerrenderizado de 448x496 píxeles"],
        ["src/core/game_entities.c","Movimiento de Pac-Man y de los fantasmas, colisiones, frutas, ojos que regresan a la casa"],
        ["src/core/game_ai.c","Personalidades de los fantasmas, modos de dispersión y persecución, tabla de 21 niveles, Cruise Elroy"],
        ["src/core/game_input.c","Traducción de teclas lógicas a acciones del juego"],
        ["src/core/game_audio.c","Eventos de audio, prioridades y sirenas"],
        ["src/render/game_render.c","Dibujo del laberinto, personajes, HUD y pantallas"],
        ["src/render/pac_ui.c, pac_theme.c, arcade_text.c","Componentes visuales, colores y texto de estilo arcade"],
        ["src/platform/sereos/game_app.c","Adaptador al escritorio: expone app_t *app_game(void), crea la tarea cooperativa y recibe eventos"],
        ["src/platform/sereos/platform_sereos.c","Implementación del contrato con las funciones del kernel"],
        ["src/platform/linux/","Bucle SDL2, framebuffer por software, audio y escenas forzadas de prueba"],
        ["assets/","Sprites RGB565, fuente arcade y sonidos PCM convertidos a tablas C"],
        ["tests/","Pruebas del núcleo con una plataforma simulada y pruebas de humo en Linux"],
    ],[3300,6060],sz=18)
    H(2,"12.4 Contrato de plataforma")
    P("El archivo `include/pac_platform.h` (versión de ABI 1) es la única frontera entre el juego y el sistema. Agrupa estas funciones, que cada plataforma debe implementar:")
    TABLE("Grupos del contrato pac_platform.h",["Grupo","Qué ofrece"],[
        ["Ciclo de vida","Inicializar y cerrar, tamaño del lienzo, rectángulo de contenido, foco, minimizado, petición de cierre, pantalla completa"],
        ["Tiempo y memoria","Reloj monótono en milisegundos, reservar y liberar memoria"],
        ["Entrada","Eventos de teclado y ratón con teclas lógicas (pac_key_t)"],
        ["Dibujo","Recorte, rectángulos, rectángulos redondeados, líneas, imágenes RGB565 y RGB32, texto con estilos"],
        ["Audio","Iniciar, reproducir efectos (15 identificadores), sirenas y detener"],
        ["Almacenamiento","Lectura y escritura de pares clave y valor en texto, para el récord y los ajustes"],
        ["Depuración","Marcadores de prueba que en SereOS salen por el puerto serie"],
    ],[2300,7060])
    H(2,"12.5 Qué es compartido y qué depende de la plataforma")
    TABLE("Partes compartidas y específicas",["Aspecto","Compartido","Específico de la plataforma"],[
        ["Reglas, IA, puntuación, niveles","Todo","Nada"],
        ["Laberinto y colisiones","Todo","Nada"],
        ["Menús, HUD y dibujo del juego","Todo (usa solo primitivas del contrato)","Las primitivas: gfx del kernel en SereOS, framebuffer por software en Linux"],
        ["Entrada","Acciones y estado de teclas","Captura: eventos del escritorio en SereOS, SDL2 en Linux"],
        ["Tiempo","Paso fijo de 16 ms","Fuente del reloj: ticks del PIT en SereOS, SDL_GetTicks en Linux"],
        ["Audio","Eventos, prioridades y datos PCM","Salida: SB16 con DMA en SereOS, SDL2 en Linux"],
        ["Récord y ajustes","Claves y formato","Dónde se guardan: RAMFS en SereOS, XDG_DATA_HOME en Linux"],
        ["Ventana","Tamaño lógico 880x560","Quién la crea: el compositor en SereOS, SDL2 en Linux"],
    ],[2500,3200,3660],sz=18)
    H(2,"12.6 Renderizado")
    P("El laberinto no se dibuja tile por tile en cada cuadro. Se construye una sola vez en un buffer de 448x496 píxeles (28x31 casillas de 16 píxeles) y después se copia al lienzo con una única llamada. Encima se dibujan los puntos restantes, las píldoras que parpadean, la fruta, los fantasmas y Pac-Man. Los sprites son de 16x16 píxeles en RGB565. A los lados quedan dos paneles: a la izquierda 1UP, el récord (HI) y el nivel; a la derecha las vidas, las frutas y el estado del juego (READY, SCATTER, CHASE, FRIGHTENED, PAUSA).")
    P("La lógica avanza en pasos fijos de 16 ms, con hasta 6 pasos de recuperación si un cuadro se retrasa, y el dibujo se refresca cada 33 ms (unos 30 cuadros por segundo). Como el juego corre dentro de una ventana de 880x560, cuando la ventana se maximiza el contenido se adapta al área disponible.")
    H(2,"12.7 Entrada del teclado")
    P("Cada plataforma traduce su teclado a teclas lógicas. El núcleo mantiene un registro con el estado de las acciones y lo lee en cada paso de lógica.")
    TABLE("Controles de PAC-MAN SereOS",["Contexto","Tecla","Acción"],[
        ["Partida","Flechas o W, A, S, D","Mover a Pac-Man"],
        ["Menús","Flechas o W, S; Enter","Elegir y confirmar"],
        ["Partida","Esc","Pausa; en el menú o la pausa, volver"],
        ["Partida y fin de juego","R","Reiniciar la partida"],
        ["Pausa","Q","Volver al título"],
        ["Título","Esc","Salir al escritorio"],
        ["Linux","F11","Pantalla completa"],
    ],[2400,3000,3960])
    P("Una observación de las pruebas en VirtualBox: la tecla Escape no era reconocida cuando le enviábamos la pulsación y la liberación casi juntas, y sí cuando dejábamos unos 150 ms entre ambas. Las demás teclas respondieron con el envío rápido. Como el núcleo lee el estado de las teclas una vez por paso de lógica, una pulsación que empieza y termina dentro del mismo intervalo puede perderse. No investigamos más la causa, y con un teclado real el efecto no se presenta porque una pulsación humana dura mucho más.")
    H(2,"12.8 Lógica de movimiento")
    P("Las posiciones se guardan en punto fijo Q8.8 (un píxel son 256 unidades), porque el sistema no usa coma flotante. La velocidad base es de 150 píxeles por segundo, y cada nivel la escala con un porcentaje: Pac-Man va al 80 % en el nivel 1 y al 100 % desde el nivel 5, y los fantasmas al 75 % y al 95 %. Pac-Man tiene una dirección actual y una dirección pedida. Si el jugador pide girar, el giro se aplica en la primera casilla donde el camino lo permite. Durante la persecución con píldora, Pac-Man se mueve a la velocidad de cazador definida para el nivel.")
    H(2,"12.9 Laberinto y niveles")
    P("Hay un único laberinto de 28x31 casillas con 240 puntos y 4 píldoras de poder, tomado de la geometría original del juego clásico. El túnel de los lados conecta ambos extremos. El juego define 21 configuraciones de nivel y, a partir del nivel 21, repite la última. Cada configuración fija la fruta, su valor, las velocidades, la duración del estado asustado y la tabla de fases.")
    TABLE("Parámetros de algunos niveles",["Nivel","Fruta","Valor","Pac-Man","Fantasmas","Asustados"],[
        ["1","Cereza","100","80 %","75 %","6 s"],
        ["2","Fresa","300","90 %","85 %","5 s"],
        ["3","Naranja","500","90 %","85 %","4 s"],
        ["4","Manzana","700","90 %","85 %","3 s"],
        ["5","Uvas","1 000","100 %","95 %","2 s"],
        ["9","Manzana","700","100 %","95 %","1 s"],
        ["17","Fresa","300","100 %","95 %","0 s (solo invierten dirección)"],
        ["21","Cereza","100","90 %","95 %","0 s"],
    ],[900,1500,1100,1500,1700,2660])
    P("Entre niveles el juego muestra una pantalla de nivel completado durante unos 5,4 segundos, restaura los puntos y empieza la siguiente configuración.")
    H(2,"12.10 Puntuación, vidas y progresión")
    TABLE("Reglas de puntuación",["Evento","Puntos"],[
        ["Punto","10"],
        ["Píldora de poder","50"],
        ["Fantasma comido (en una misma píldora)","200, 400, 800 y 1 600"],
        ["Fruta (cereza, fresa, naranja, manzana, uvas)","100, 300, 500, 700 y 1 000 según el nivel"],
        ["Vida extra","Al llegar a 10 000 puntos"],
    ],[5400,3960])
    P("Se empieza con 3 vidas y se puede llegar a 9. Cada partida arranca con una pantalla READY! de 4,5 segundos; tras perder una vida, de 1,5 segundos. La animación de muerte dura 2,8 segundos. Al perder la última vida aparece la pantalla de fin de juego, con la puntuación, el récord y el nivel. El récord se guarda en el RAMFS (`/home/pacman_sereos.hi`), de modo que dura mientras el sistema esté encendido y se pierde al reiniciar.")
    H(2,"12.11 Inteligencia artificial de los fantasmas")
    P("Los cuatro fantasmas deciden en cada intersección. Eligen, entre las direcciones válidas que no invierten la marcha, la que minimiza la distancia euclidiana a una casilla objetivo. Lo que cambia entre ellos es el objetivo.")
    TABLE("Personalidades de los fantasmas",["Fantasma","Objetivo en persecución","Objetivo en dispersión"],[
        ["Blinky (rojo)","Pac-Man. Tiene el modo Cruise Elroy: cuando quedan pocos puntos persigue incluso durante la dispersión","Esquina superior derecha"],
        ["Pinky (rosa)","Cuatro casillas delante de Pac-Man. Si Pac-Man mira hacia arriba, reproduce el error del original y apunta cuatro arriba y cuatro a la izquierda","Esquina superior izquierda"],
        ["Inky (cian)","Vector doble desde Blinky hasta dos casillas delante de Pac-Man","Esquina inferior derecha"],
        ["Clyde (naranja)","Pac-Man si está a más de 8 casillas; si no, su esquina","Esquina inferior izquierda"],
    ],[1900,5060,2400],sz=18)
    P("Los fantasmas alternan dispersión y persecución con un reloj. En el nivel 1 la secuencia es 7 s de dispersión, 20 s de persecución, 7 s, 20 s, 5 s, 20 s, 5 s, y después persecución permanente. Los niveles posteriores usan otras tablas. Al comer una píldora, los fantasmas pasan a estado asustado: invierten la dirección, se vuelven azules y pueden comerse. Un fantasma comido se convierte en ojos que regresan a la casa, vuelve a salir y reaparece con un efecto propio. Los fantasmas salen de la casa por un contador de puntos comidos y, si Pac-Man no come, por un temporizador de 4 s (3 s desde el nivel 5).")
    H(2,"12.12 Frutas y bonificaciones")
    P("La fruta aparece en la casilla de debajo de la casa cuando Pac-Man ha comido 70 y 170 puntos, y permanece visible 10 segundos. El tipo y el valor dependen del nivel. Mientras está visible, el panel derecho marca la fruta como «en juego», y al comerla se muestra un destello y se suma su valor. En VirtualBox vimos aparecer la cereza y el aviso del panel. No logramos capturar el momento en que se come, así que ese caso queda sin demostrar con captura.")
    H(2,"12.13 Animaciones")
    P("El juego anima a Pac-Man (apertura y cierre de la boca y la secuencia de muerte), a los fantasmas (cuerpo, ojos y el balanceo dentro de la casa), el parpadeo de las píldoras, el estado asustado, el destello de la fruta y el rótulo READY!. Las pantallas de nivel completado y de fin de juego aparecen como paneles superpuestos sobre el laberinto atenuado.")
    H(2,"12.14 Audio")
    P("El núcleo traduce los eventos del juego a quince efectos: menú, inicio, dos tipos de «waka» al comer puntos, píldora, fantasma, fruta, muerte, vida extra, nivel completado, fin de juego, tres sirenas (persecución, caza y asustados) y reaparición de fantasmas. Cada efecto tiene una prioridad para que un sonido menor no corte a uno importante, y las sirenas se reinician con una ventana de gracia para que no se entrecorten al comer puntos. Los sonidos se convirtieron a PCM de 8 bits a 11 025 Hz y viven en tablas C dentro del componente. En SereOS salen por la Sound Blaster 16, y si no hay audio disponible el juego sigue funcionando en silencio.")
    P("En esta validación no escuchamos el audio en VirtualBox. La detección de la SB16 sí quedó registrada, pero la salida audible es una funcionalidad implementada y no probada por nosotros.")
    H(2,"12.15 Menús y pantallas")
    BUL([
        "**Atracción.** Título, tabla de personajes con sus apodos, récord y el rótulo PRESS START.",
        "**Menú principal.** Iniciar partida, Continuar (si hay una partida guardada en la sesión), Récords, Instrucciones, Configuración y Salir al escritorio.",
        "**Pausa.** Continuar, Reiniciar partida, Configuración, Menú principal y Salir al escritorio.",
        "**Fin de juego.** Reintentar, Menú principal y Salir al escritorio.",
        "**Configuración.** Sonido y pantalla completa, que se conservan mientras el sistema siga encendido (en SereOS) o en disco (en Linux).",
        "**Nivel completado.** Panel con el nivel y la puntuación.",
    ])
    H(2,"12.16 Ejecución en CachyOS para pruebas")
    P("El mismo núcleo y el mismo render se compilan en un ejecutable de Linux con SDL2 (`build/pacman-sereos`). Abre una ventana de 1024x768 con escalado entero, dibuja en un framebuffer por software y reproduce el audio con SDL. Sirve para iterar rápido y para las pruebas automáticas. También puede arrancar en una escena concreta y guardar el último cuadro, incluso sin pantalla (`--scene` y `--screenshot` con SDL en modo dummy), lo que permite alcanzar pantallas difíciles de provocar jugando, como el nivel completado.")
    P("Esa ejecución no es la ejecución nativa en SereOS y el documento no la presenta como tal. Las capturas de CachyOS se rotulan siempre como tales.")
    H(2,"12.17 Ejecución nativa dentro de SereOS")
    P("En SereOS el juego es una biblioteca estática que exporta una sola función, `app_t *app_game(void)`. El registro de aplicaciones del escritorio la llama y obtiene el descriptor de una aplicación con identificador `game`, nombre «PAC-MAN SereOS», ventana de 880x560 y las funciones de abrir, cerrar, dibujar y recibir eventos. Al abrirla se crea el estado del juego y una tarea cooperativa que ejecuta los pasos de lógica. Al cerrarla se mata la tarea, se guarda el récord, se detiene el audio y se libera la memoria. Si la ventana pierde el foco o se minimiza, el juego se congela, para no perder vidas sin que el jugador lo vea.")
    H(2,"12.18 Limitaciones del juego")
    BUL([
        "Un solo laberinto. Las 21 configuraciones cambian velocidades y tiempos, no el mapa.",
        "Sin la demostración automática (replay) del modo de atracción original ni modo de pruebas de IA.",
        "Sin elección entre estilos visuales: los ajustes se limitan a sonido y pantalla completa.",
        "El récord y los ajustes en SereOS se pierden al reiniciar, porque el RAMFS es volátil.",
        "El giro en diagonal y la entrada al túnel están simplificados respecto del original.",
        "Los recursos gráficos y sonoros son de terceros y solo se pueden usar con fines académicos (capítulo 19).",
    ])

    # ===================== 13 DESARROLLO E INTEGRACION =====================
    H(1,"13. Desarrollo e integración del videojuego")
    H(2,"13.1 Cómo se incorpora el juego a la ISO")
    P("La integración no copia archivos del juego a la imagen. El juego se compila como una biblioteca y el Makefile del sistema la enlaza dentro de `sereos.bin`. El procedimiento real, extraído de los Makefiles, es este:")
    NUM([
        "El objetivo `game-lib` del Makefile del sistema ejecuta `make -C \"../Pac-man SereOS\" sereos OS_DIR=...`.",
        "El Makefile del juego compila `src/core`, `src/render`, `src/platform/sereos` y `assets` con las mismas opciones del kernel (`-m32 -ffreestanding -mno-sse -mno-mmx -O2`) y arma `build/sereos/libpacman.a` con `ar rcs`.",
        "El enlace del kernel añade esa biblioteca después de los objetos y antes de `-lgcc`.",
        "`apps/apps.c` registra la aplicación llamando a `app_game()`. El juego no tiene copia dentro del árbol del sistema.",
        "`make` genera `sereos.iso` con ese `sereos.bin` dentro, que es lo que se arranca en VirtualBox.",
    ])
    P("Comprobamos el resultado de dos formas. `nm sereos.bin` muestra `app_game`, `game_open`, `game_draw` y las funciones `pac_*` dentro del kernel, y `strings` encuentra el nombre «PAC-MAN SereOS». También extrajimos `boot/sereos.bin` de la ISO y su SHA-256 coincide con el del binario recién compilado (ver el capítulo 14).")
    H(2,"13.2 Pruebas del componente")
    P("Ejecutamos `make test` en el componente. El resultado fue `checks=209 failures=0` en las pruebas del núcleo con plataforma simulada y siete pruebas de humo de Linux superadas (atracción, menú, ajustes, partida, pausa, fin de juego y nivel completado), con el mensaje final TODAS LAS PRUEBAS OK. El README del componente anunciaba 131 pruebas en una versión anterior. La cifra actual es 209, y esa es la que obtuvimos al ejecutar.")
    H(2,"13.3 Evidencia de ejecución en SereOS (VirtualBox)")
    P("Las capturas siguientes se tomaron con el juego corriendo dentro de SereOS, arrancado desde la ISO final en VirtualBox. Para llegar a los estados que exigen jugar (píldora, fantasma asustado, fruta) usamos un programa auxiliar que lee las capturas de VirtualBox y envía teclas; el juego no se modificó. Ese programa solo imita a un jugador, y el comportamiento del juego que se ve es el real. El registro del puerto serie confirma cada estado con marcadores como `GAME_START`, `PAC_DEATH` y `GHOST_EATEN`.")
    FIG(V+"02_attract.png","Pantalla de presentación (atracción)","Captura de VirtualBox tras abrir el juego con F4. Muestra el título, la tabla de personajes (Shadow Blinky, Speedy Pinky, Bashful Inky y Pokey Clyde), el récord y el rótulo PRESS START.",w_in=5.2)
    FIG(V+"03_menu_principal.png","Menú principal","Captura de VirtualBox tras pulsar Enter en la pantalla de atracción. Seis opciones; Continuar aparece atenuada y con la leyenda sin partida porque aún no se guardó ninguna.",w_in=5.2)
    FIG(V+"03c_instrucciones.png","Pantalla de instrucciones","Captura de VirtualBox. Lista los controles y explica el objetivo: comer todos los puntos y las cuatro píldoras, los valores de los fantasmas (200, 400, 800 y 1 600) y la vida extra a los 10 000 puntos.",w_in=5.2)
    FIG(V+"04_ready.png","Inicio de una partida","Captura de VirtualBox al empezar. El rótulo READY! cubre la casa de los fantasmas, Pac-Man está en su posición inicial (fila 23) y el panel muestra tres vidas y el estado READY.",w_in=5.2)
    FIG(V+"05_partida_dots_fantasmas.png","Partida en curso: puntos, fantasmas y marcador","Captura de VirtualBox durante el juego. Se ven los puntos del laberinto, las cuatro píldoras de las esquinas, Pac-Man y los fantasmas, con el estado SCATTER. El panel izquierdo muestra la puntuación (130), el récord (190) y el nivel 1.",w_in=5.2)
    FIG(V+"06_fantasmas_asustados.png","Fantasmas asustados tras comer una píldora","Captura de VirtualBox con el estado FRIGHTENED. Los fantasmas se ven de color azul y el panel derecho indica el estado. La puntuación es 410 y el récord se actualiza con ella.",w_in=5.2)
    FIG(V+"07_asustados_con_fruta.png","Estado asustado con fruta en el laberinto","Captura de VirtualBox con fantasmas azules, una cereza bajo la casa y el aviso «En juego» en el apartado de frutas del panel derecho. La puntuación es 880 y queda una vida.",w_in=5.2)
    FIG(V+"08_captura_de_fantasma.png","Captura de un fantasma","Captura de VirtualBox en el instante en que Pac-Man se come a un fantasma. Aparece la bonificación junto a Pac-Man y la puntuación es 1 490. En esa partida el registro serie anotó GHOST_EATEN, GHOST_RETURNED y GHOST_REVIVED.",w_in=5.2)
    FIG(V+"09_perdida_de_vida.png","Pérdida de una vida","Captura de VirtualBox durante la secuencia de muerte. Pac-Man es alcanzado por un fantasma cuando le quedaban dos vidas y la puntuación era 600. A continuación el registro serie anotó PAC_DEATH y PAC_STATS con lives=1.",w_in=5.2)
    FIG(V+"10_pausa.png","Pantalla de pausa","Captura de VirtualBox tras pulsar Esc. Panel con Continuar, Reiniciar partida, Configuración, Menú principal y Salir al escritorio, sobre el laberinto atenuado. El registro serie anotó GAME_PAUSE.",w_in=5.2)
    FIG(V+"12_game_over.png","Fin de juego","Captura de VirtualBox al perder la última vida. Muestra la puntuación (70), el récord (70) y el nivel (1), con las opciones Reintentar, Menú principal y Salir al escritorio. El registro serie anotó GAME_OVER.",w_in=5.2)
    H(2,"13.4 Marcadores del puerto serie")
    P("El juego escribe marcadores por el puerto serie en cada cambio de estado. En VirtualBox conectamos COM1 a un archivo, y el registro de una de las sesiones contiene, en este orden, el arranque del kernel, `DESKTOP_READY`, `GUI_READY`, `GAME_MENU`, `APP_OPEN:game`, `GAME_START` y después una secuencia de `PAC_DEATH`, `LIFE_START` y `PAC_STATS`. Un fragmento real:")
    CODE("""APP_OPEN:game
GAME_MENU
LEVEL_START 1
PAC_STATS dots=240 power=4 score=0 level=1 lives=3
GAME_START
PAC_DEATH
LIFE_START 2
PAC_STATS dots=227 power=4 score=130 level=1 lives=2
PAC_DEATH
LIFE_START 1
PAC_STATS dots=185 power=3 score=600 level=1 lives=1
GHOST_EATEN 2
GHOST_EATEN 1
GHOST_RETURNED 2
GHOST_RETURNED 1
GHOST_REVIVED 2
GHOST_REVIVED 1
PAC_DEATH
GAME_OVER""","Registro del puerto serie de VirtualBox (fragmento)")
    P("Se lee así: en la tercera vida se habían comido 55 puntos y una píldora (dots=185 power=3, puntuación 600), y se comieron dos fantasmas seguidos, con sus eventos de regreso y reaparición.")
    H(2,"13.5 Escenas obtenidas en CachyOS")
    P("Tres pantallas no las alcanzamos jugando en VirtualBox con comodidad: el nivel completado, el inicio de partida con su cuenta y los ajustes. Para documentarlas usamos las escenas forzadas del binario de Linux, que renderiza el mismo núcleo y el mismo render. No son capturas del juego dentro de SereOS.")
    FIG("capturas/06_pacman_cachyos/linux_victory.png","Nivel completado (CachyOS, escena forzada)","Captura del ejecutable de Linux con SDL en modo dummy y la opción --scene victory. Es el panel que SereOS muestra al comerse todos los puntos: Nivel completado, con el nivel y la puntuación, y la nota de que los puntos reaparecen. No se alcanzó este estado en VirtualBox.",w_in=6.0)
    FIG("capturas/06_pacman_cachyos/linux_settings.png","Configuración (CachyOS, escena forzada)","Captura del ejecutable de Linux con --scene settings. Muestra las dos opciones de ajustes: sonido y pantalla completa. Tampoco se capturó en VirtualBox.",w_in=6.0)
    H(2,"13.6 Cobertura de las capturas pedidas")
    TABLE("Estados del juego y evidencia disponible",["Estado","Evidencia","Dónde"],[
        ["Presentación y menú principal","Capturada","VirtualBox"],
        ["Inicio de partida y Pac-Man en el laberinto","Capturada","VirtualBox"],
        ["Fantasmas, puntos y píldoras","Capturada","VirtualBox"],
        ["Puntuación y vidas","Capturada","VirtualBox"],
        ["Fantasmas asustados y captura de un fantasma","Capturada","VirtualBox"],
        ["Pausa, pérdida de una vida y fin de juego","Capturada","VirtualBox"],
        ["Fruta visible","Capturada","VirtualBox"],
        ["Fruta comida","No capturada","El código existe; no se logró en las partidas de prueba"],
        ["Transición entre niveles","Solo escena forzada","CachyOS; no se alcanzó en VirtualBox"],
        ["Ejecución desde el escritorio de SereOS","Capturada","VirtualBox (F4) y QEMU (clic en el dock)"],
        ["Configuración","Solo escena forzada","CachyOS"],
        ["Récords","No capturada","Existe en el menú; no se abrió en esta validación"],
    ],[3900,2300,3160],sz=18)
