# Informe de edición — demostracion_completa_aplicacion.mp4

## Resultado
- Archivo: `/home/t1an/Descargas/sereos02/documentacion/demostracion_completa_aplicacion.mp4` (~42 MB)
- Duración: **1588,3 s (26 min 28 s)** = móvil 328,15 s + transición 3,2 s + escritorio 1256,9 s
- Video: H.264 (libx264, CRF 18, preset medium, yuv420p), **1080 × 2400, 20 fps** constantes
- Audio: AAC 44,1 kHz estéreo 128 kbps (pista silenciosa, ver «Audio»)

## Archivos originales
Ubicación real (no existía `/mnt/data`): `/home/t1an/movil oracle bluetooth/videos/`
| Archivo | Resolución | FPS | Códec | Duración |
|---|---|---|---|---|
| `movil_completo.mp4` | 1080×2400 | 20 | H.264, sin audio | 328,15 s |
| `escritorio_completo.mp4` (versión reconstruida) | 1600×1000 | 20 | H.264, sin audio | 1256,9 s |
Los originales no se modificaron (el escritorio corrupto se respaldó en el espacio temporal de trabajo).

## Hallazgo clave: duplicado de 5:28
El `escritorio_completo.mp4` entregado antes tenía **1080×2400** y empezaba con la demostración móvil: eran **328 s = 5 min 28 s**, exactamente la duración del video móvil. Causa: dos ensamblados ejecutados a la vez compartían los mismos archivos temporales y se mezclaron clips móviles dentro del video de escritorio. No era contenido real de escritorio.
Corrección: se corrigió el script de ensamblado (carpeta temporal por modo) y se **regeneró el video de escritorio desde sus clips fuente**, ahora 1600×1000 sin ningún fotograma móvil. Por eso **no hubo que recortar 5:28**: el primer fotograma exclusivo de escritorio es el t=0 del archivo reconstruido (portada «Acceso: tema e idioma»).

## Plan y segmentos
| Sección | Fuente | Rango | Duración |
|---|---|---|---|
| 1. Aplicación móvil | `movil_completo.mp4` | 0–328,15 s (completo) + fundido de salida 0,5 s | 328,15 s |
| 2. Transición | tarjeta propia (`APLICACIÓN DE ESCRITORIO` + subtítulo) | fondo oscuro #0B1A16, acento verde del proyecto, fundido de entrada 0,8 s y salida 0,7 s | 3,2 s |
| 3. Aplicación de escritorio | `escritorio_completo.mp4` | 0–1256,9 s (completo) + fundido de entrada 0,5 s | 1256,9 s |
Descartado: nada de contenido funcional. Solo el duplicado móvil ya explicado (que estaba en el archivo corrupto, no en el reconstruido).

Contenido móvil conservado: catálogo, contar (arroz con dañados, nota y foto de galería, SKU fuera del catálogo), contado y corregir, pendientes, sincronizar, notificaciones, mi cuenta (tema, idioma, foto de perfil con editor), cierre de sesión y capturas de las pantallas que el emulador no puede mostrar en vivo.
Contenido de escritorio conservado: acceso, alta de cuentas, aprobación, dashboard y widgets, inventario con filtros y lecturas, foto de evidencia del arroz, CSV en hoja de cálculo, solicitudes, empleados, roles, auditoría, configuración, sincronización en vivo («Huawei P9 lite Sebastian»), respaldos y su carpeta en el explorador, notificaciones, perfil de Camila Restrepo, rol Inventario con Gráficas.

## Tratamiento de imagen
- Móvil: sin reescalado (ya 1080×2400).
- Escritorio (1600×1000, apaisado): escalado **proporcional** (Lanczos) a 1080×675 y centrado sobre fondo #0B1A16 hasta 1080×2400. Sin estirar ni recortar. Consecuencia: el escritorio ocupa el 28 % del alto del cuadro y el texto se ve más pequeño.
- Velocidad original en todo el material; sin aceleración ni cortes internos.

## Audio
Ningún original contiene audio (son grabaciones de pantalla). No hay audio que conservar ni normalizar. Se añadió una pista AAC **silenciosa** continua para que el MP4 tenga flujo de audio y sea compatible con reproductores que lo exigen. Sin música.

## Comprobaciones realizadas
- FFprobe del final: H.264 1080×2400 20 fps + AAC 44,1 kHz estéreo; duración 1588,30 s (suma esperada 1588,25 s).
- Fotogramas revisados: inicio (t=1), final del móvil (326 s), transición completa (328,5–331,5 s), entrada del escritorio (332–334 s), puntos intermedios (400, 700, 1000, 1300, 1500 s) y final (1587 s).
- `blackdetect` (≥1 s): ningún tramo negro accidental.
- `freezedetect` (≥45 s): un tramo estático de 46,8 s (1085,05–1131,85 s del maestro) en la sección de escritorio, pantalla de Perfil/Respaldos esperando la animación lenta de la app. Se **conservó** (no se recorta contenido funcional); si se quiere, se puede recortar ese intervalo exacto.
- Audio presente y continuo (pista silenciosa), sin desincronización posible.
- No se tocó código fuente ni otros entregables.

---

# Auditoría final — versión 2 (vigente)

Archivo vigente: `demostracion_completa_aplicacion.mp4` (v2). Respaldo de la versión anterior: `demostracion_completa_aplicacion_v1_respaldo.mp4` (v1, 1080×2400). Los videos originales no se modificaron.

## Resultado v2
- Duración **1591,75 s (26 min 32 s)** = móvil 328,15 + transición 3,2 + escritorio 1260,4
- Video H.264 (CRF 16, preset medium, yuv420p), **1920 × 1080 horizontal, 20 fps** · Audio AAC 44,1 kHz estéreo (pista silenciosa; los originales no tienen audio)
- Escritorio 1260,4 s = 1256,9 (original) − 10,5 (recorte) + 14 (final extendido)

## 1. Tramo estático (v1, 18:05–18:52)
Análisis por diferencia entre fotogramas a 0,5 s: el intervalo corresponde a **Respaldos** (crear respaldos, diálogo «Restaurar», edición de «conservar los últimos» y toast «Respaldo automático guardado»). Es una **espera de la aplicación** (render lento en el entorno de grabación): el cambio entre fotogramas es ≈ 0 (diferencia media < 0,05) durante 11,5 s seguidos (1106,5–1118,0 s de v1). No es una pantalla congelada ni una operación relevante.
Recorte aplicado: **10,5 s** (v1 1107,0–1117,5 s = escritorio original 775,65–786,15 s), conservando el contexto 0,5 s antes y después. Se verificó que el diálogo, el foco del campo, el toast y el resto de la secuencia siguen presentes. No se cambió la velocidad.

## 2. Legibilidad de escritorio — cambio de composición
En v1 el escritorio (1600×1000) iba escalado a 1080×675 dentro de un lienzo vertical 1080×2400: ocupaba 28 % del alto y el texto salía pequeño. En v2 el lienzo es **1920×1080 horizontal**:
- Escritorio a 1728×1080 (escala 1,08, proporcional, sin recortes ni deformación), centrado con márgenes de 96 px en fondo discreto #0B1A16 → texto, tablas y menús notablemente más grandes.
- Móvil a 486×1080 (escala 0,45 desde 1080×2400, proporcional), centrado sobre el mismo fondo. Texto de la app legible (se revisó un fotograma al 100 %).
- Transición reconstruida en 1920×1080 (mismo texto y estética).
Compromiso: la sección móvil queda con barras laterales oscuras; era el precio de duplicar la legibilidad del escritorio, que es la parte más larga y densa.

## 3. Final
En v1 el video terminaba con el editor de foto aún abierto (cortado antes de pulsar «Aplicar»). En v2 se añadieron 14 s del mismo clip original (la foto de Carlos se aplica y aparece «Foto de perfil actualizada») y un fundido de salida de 0,5 s. Los pasos posteriores del clip (cambio de contraseña) se siguen omitiendo.

## 4. Control de calidad realizado
- FFprobe: H.264 1920×1080 20 fps + AAC; duración 1591,75 s (coincide con la suma esperada).
- Sin tramos negros ≥ 1 s (`blackdetect`).
- Móvil completo (328,15 s): títulos, conteo con foto de galería, contado/pendientes, sincronizar, notificaciones, mi cuenta, foto de perfil y capturas finales; revisado por muestreo.
- Escritorio completo: todas las secciones del original; sin fotogramas móviles ni duplicados (el duplicado de 5:28 de la versión previa venía de un error de ensamblado ya corregido).
- Transición revisada en fotogramas (fundido de entrada, texto, fundido de salida, entrada del escritorio).
- Corte del recorte revisado a 1 s, 1,5 s y 2 s alrededor; final revisado (1590,5 s).
- `freezedetect` (≥ 15 s) aún marca varias esperas del mismo tipo (≈ 15–30 s: p. ej. 650 s, 969 s, 991 s, 1455 s del maestro v1). Son esperas de la aplicación o retenciones sobre contenido (hoja de cálculo, explorador de archivos, editor de foto); se **conservaron** porque no eran el objetivo de esta auditoría y no se revisaron una a una. Si se desea, se pueden recortar con el mismo criterio.
- No se aceleró ninguna parte, no se añadió música, no se tocó el código ni otros entregables.

---

# Versión 3 — Producción audiovisual definitiva

## Resultado
- Archivo maestro: `demostracion_completa_aplicacion.mp4`: **1234,7 s (20 min 35 s)**, 85 MB.
- Video: H.264 High, CRF 16, yuv420p, **1920 × 1080 (16:9), 20 fps** constantes.
- Audio: AAC-LC 192 kbps, 48 kHz estéreo. Sonoridad integrada −16 LUFS, pico máximo de −1 dBFS aproximadamente.
- Respaldos:
  - `demostracion_completa_aplicacion_v2_respaldo.mp4`: copia exacta de la V2 (1591,75 s).
  - `demostracion_completa_aplicacion_v1_respaldo.mp4`: se conserva sin cambios.
- Archivos complementarios: `guion_narracion.md` y `subtitulos.srt` (la misma temporización que las cápsulas incrustadas).

## Fuentes
- `videos/movil_completo.mp4` y `videos/escritorio_completo.mp4`: grabaciones reales sin cambios.
- Capturas de las pruebas en `docs/img/movil/`.
- No se usó material de terceros.

## Tiempos muertos
- Se detectaron 95 tramos estáticos con `freezedetect` (umbral n=0,002, duración ≥ 4 s) y se revisaron uno por uno.
- Todos eran esperas de pantalla sin interacción.
- Cada tramo se acorta a un tope fijo: 4 s en general, 6 s para el visor de la foto y el explorador de respaldos, y 7 s para la hoja de cálculo. Así se conservan los mensajes de confirmación y las notificaciones.
- Se eliminaron unos 377 s de espera. No se aceleró ni se ralentizó ninguna grabación y no se quitó ninguna función.

## Diseño
- **Portada:** muestra:
  - el logotipo de la aplicación;
  - el título «Inventario BT»;
  - el subtítulo «Presentación y demostración integral del sistema»;
  - tres indicadores en rectángulos redondeados: Aplicación móvil, Aplicación de escritorio y Gestión y administración.

  Las capas entran de forma escalonada.
- **Tarjetas:**
  - Las de parte («Aplicación móvil» y «Aplicación de escritorio») llevan icono de dispositivo y chips de funciones.
  - Las 22 mini-tarjetas numeradas van antes de cada módulo.
- **Composición:** las grabaciones van en marcos redondeados con sombra sobre el fondo oscuro de la marca: escritorio a 1536 × 960 y móvil a 432 × 960.
- **Cierre:** «GRACIAS POR SU ATENCIÓN» con el subtítulo «Una solución integral para la gestión y administración del inventario.» Tiene una animación suave y, al final, la imagen y la música se desvanecen a la vez.
- **Tipografía e iconos:** tipografía Inter. Los iconos son Lucide (licencia ISC), los mismos de la aplicación de escritorio.

## Narración
- Piper TTS, ejecutado en local, con la voz `es_MX-claude-high` (español latinoamericano) a velocidad 1,05.
- 52 frases y 232 s de voz.
- El texto se basa solo en las funciones que se ven en pantalla. No menciona contraseñas.
- Cada frase se coloca dentro del bloque de su módulo, empezando sobre su mini-tarjeta.
- Tratamiento de la voz: filtro paso alto, compresión suave y normalización.

## Subtítulos
- 57 cápsulas tipo Dynamic Island, **abajo y centradas**.
- Diseño:
  - fondo grafito semitransparente con un borde blanco tenue;
  - sombra difusa que da profundidad;
  - bordes completamente redondeados y ancho que se ajusta al texto;
  - texto blanco Inter Medium de 34 px, como máximo 2 líneas.
- Animación: entrada con fundido y una escala del 94 % al 100 % en 0,22 s; salida con fundido.
- Las frases largas se dividen en dos cápsulas consecutivas.

## Música
- Pista instrumental original, sintetizada con numpy para este video sin muestras externas, así que no hay licencias de terceros.
- Contenido:
  - progresión Am9 – Fmaj7 – Cmaj7 – G6 a 84 BPM;
  - pads, bajo y un arpegio suave a partir del segundo 16;
  - un pulso tenue en las secciones intermedias;
  - reverberación por convolución.
- Entra con un fundido de 5 s y sale con otro de 7 s.
- Ducking con `sidechaincompress` activado por la narración: la música queda unos 8 dB por debajo de la voz en los tramos sin narración y baja más mientras se habla.

## Control de calidad
- ffprobe: H.264 High a 1920×1080, 20/1 fps; AAC estéreo a 48 kHz; duración de 1234,74 s.
- `blackdetect` (≥ 0,5 s): sin tramos negros fuera del fundido final.
- Fotogramas revisados: portada, tarjeta móvil, clip móvil, diapositivas de pruebas, clip de escritorio con cápsula, perfil y cierre. Las cápsulas aparecen abajo, centradas y legibles.
- Están todos los módulos de la V2: 4 bloques móviles, 2 diapositivas de pruebas y 18 bloques de escritorio, en el mismo orden.
- Nota: la pantalla de crear cuenta (captura de pruebas) y la de perfil del escritorio dejan ver campos de contraseña enmascarados, que forman parte del diseño de la aplicación. No se escribe ni se muestra ninguna contraseña. Las dos pantallas ya estaban en la V2.

---

# Versión 4 — Sin narrador, música corporativa, puntero y gráficas

## Resultado
- **Archivo maestro:** `demostracion_completa_aplicacion.mp4`.
  - Duración: **1252,0 s (20 min 52 s)**, 83 MB.
  - Imagen: H.264 High, CRF 16, 1920 × 1080 (16:9), 20 fps.
  - Audio: AAC 192 kbps, 48 kHz estéreo, −17 LUFS.
- **Respaldos:**
  - `demostracion_completa_aplicacion_v3_respaldo.mp4`: la versión 3 (con narración).
  - La V1 y la V2 se conservan sin cambios.
- **Archivos de la V3 renombrados:**
  - `guion_narracion.md` pasa a llamarse `guion_narracion_v3.md`.
  - `subtitulos.srt` pasa a llamarse `subtitulos_v3.srt`.
  - Ya no corresponden al video, porque este no tiene voz.

## 1. Narrador eliminado
- La pista de voz y las 57 cápsulas de subtítulos de la narración se han quitado.
- Lo único que explica el video son las tarjetas de sección y las demostraciones.
- Las tarjetas vuelven a sus duraciones originales: portada 8 s, partes 7 s, mini-tarjetas 3 s y cierre 10 s.

## 2. Música nueva
- **Origen:** pista original sintetizada con numpy para este video, sin muestras ni material de terceros.
- **Estilo:** pop electrónico corporativo a 112 BPM en Re mayor.
- **Progresión:** I–V–vi–IV, con una variación ii–IV–I/3–V.
- **Instrumentos:**
  - acordes pulsados sincopados y pad suave;
  - bajo con un bombeo ligero;
  - batería discreta: bombo, palmas, charles;
  - un motivo de campana breve.
- **Secciones**, alineadas a compás con la línea de tiempo:
  - introducción en la portada;
  - parte móvil con el ritmo completo;
  - transición más ligera con subida en la tarjeta de escritorio;
  - parte de escritorio con el motivo cada 8 compases;
  - cierre que resuelve en el acorde de tónica, con fundido de 4,5 s.
- **Volumen uniforme:** el rango de sonoridad (LRA) es de 0,9 LU.

## 3. Puntero en el móvil
- Las grabaciones del móvil solo mostraban el ripple, así que se añadió un puntero circular minimalista:
  - aro blanco con contorno oscuro, relleno translúcido y punto central;
  - animación al pulsar, con hundimiento y onda expansiva;
  - acompaña los deslizamientos y se desplaza entre toques seguidos.
- **Posición real:** las coordenadas salen de los comandos `adb input tap/swipe` que se usaron al grabar. Son 68 eventos.
- **Sincronización:**
  - Cada toque se cuadró con el inicio del ripple en esa coordenada.
  - Se revisó fotograma a fotograma en hojas de verificación.
  - Se corrigieron a mano 9 tiempos y se descartó un toque que no hacía nada.
- En el escritorio se ve el cursor real del sistema, que ya estaba en las grabaciones.

## 4. Rol Inventario: «Añadir gráfica»
- **Bug encontrado:** la grabación anterior mostraba un recuadro negro. Era un error real de la app: `desktop/app/views/menu_flotante.py:316` usaba `Qt.PenJoin`, que no existe en PyQt6, y el menú fallaba al pintarse.
- **Corrección:** con la autorización del usuario se cambió a `Qt.PenJoinStyle`. El cambio está en el repositorio, sin commit.
- **Nueva toma**, grabada en el entorno aislado con el usuario Carlos Nuevo Perez (rol Inventario):
  1. Se muestra el panel de gráficas.
  2. Se pulsa «Personalizar gráficas».
  3. Se quita «Lecturas por hora (UTC)» con el botón rojo.
  4. Se pulsa «Añadir gráfica» y el selector muestra todas las opciones, con las ya añadidas marcadas.
  5. Se elige «Lecturas por operador», que ocupa el hueco libre.
  6. Se recorre el resultado y se pulsa «Listo».
- Al terminar se restauró la distribución predeterminada.
- La toma sustituye al tramo de 20,5 s que tenía el recuadro negro.

## Control de calidad
- No queda ninguna pista de voz: el audio es solo música.
- ffprobe confirma 1920×1080, 20 fps, H.264 + AAC estéreo, 1251,97 s.
- `blackdetect` no encuentra tramos negros.
- Fotogramas revisados: portada, tarjetas, el puntero sobre «Catálogo», «Dañados» y otros controles, el selector de gráficas con sus opciones visibles y el cierre.
- Se mantienen todas las funciones de la V3.

---

# Versión 5 — Continuidad de la foto de perfil del administrador

## Resultado
- **Archivo maestro:** `demostracion_completa_aplicacion.mp4`.
  - Duración: **1257,1 s (20 min 57 s)**, 85 MB.
  - Imagen y audio con las mismas especificaciones que la V4: 1920×1080, 20 fps, H.264 CRF 16, AAC 192 kbps estéreo y −16,9 LUFS.
- **Respaldo:** `demostracion_completa_aplicacion_v4_respaldo.mp4`. La V1, la V2 y la V3 se conservan.

## Problema
Los clips del administrador se grabaron en momentos distintos. Por eso, en el pie de la barra lateral aparecían dos avatares antes del cambio de foto:
- la foto de Camila Restrepo, en Foto de evidencia, Exportar a CSV, Respaldos en disco y Notificaciones;
- una imagen de rayas de una prueba antigua, en Sincronización y Notificaciones.

Además, en Perfil se pulsaba «Eliminar foto» cuando todavía no había ninguna foto cargada.

## Corrección
1. **Avatar predeterminado hasta el cambio.** En todos los clips del administrador anteriores a Perfil, el avatar de la barra lateral se sustituyó por el avatar real de la app: «C» blanca sobre círculo verde.
   - El avatar se toma de un fotograma de la propia grabación (Auditoría). No se ha dibujado.
   - Se ajusta al brillo de cada fotograma, así que también encaja cuando hay un diálogo abierto que atenúa la pantalla.
   - Solo se aplica cuando se ve el pie de la barra lateral con el nombre «Camila Restrepo». Las ventanas superpuestas (LibreOffice, el visor de foto) no se tocan, salvo el borde del avatar que queda visible junto al visor, que también se corrigió.
   - Nombres, datos y el resto de la interfaz no cambian.
2. **Secuencia de Perfil regrabada** en el entorno aislado, con la app real y la foto real de Camila Restrepo:
   1. Avatar «C».
   2. Cambio de tema (Oscuro, Sistema, Claro) y de idioma (English, Español), como en la toma original.
   3. «Poner foto»: se elige la foto y se pulsa «Aplicar». La foto aparece en el perfil y en la barra lateral.
   4. «Eliminar foto»: se confirma en el aviso y la app responde «Se volverá a mostrar tu inicial». Vuelve la «C».
   5. «Poner foto» otra vez: se ajustan el zoom y el encuadre en el editor y se pulsa «Aplicar». Esta es la foto definitiva.
3. **Después del cambio definitivo** no hay más clips del administrador. El siguiente es el rol Inventario, con Carlos Nuevo Perez.

## Verificación fotograma a fotograma
Se analizaron los 20 fps del pie de la barra lateral en todos los clips del administrador del video final:
- **Antes de Perfil:** 0 fotogramas con foto. Todos muestran «C», salvo los fundidos y las ventanas superpuestas.
- **En Perfil:**
  - «C» desde el inicio (17:00,5);
  - foto cargada en 17:32,9;
  - «C» tras eliminarla en 17:44,6;
  - foto definitiva en 18:08,4, que se mantiene hasta el final del clip.
- En la lista de Empleados, la fila de Camila también muestra «C».
- `blackdetect` no encuentra tramos negros.
