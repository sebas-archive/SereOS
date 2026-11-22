# Informe de validación APA 7 — ProyectoFinal_sistemas_operativos_APA7

Origen: `ProyectoFinal_sistemas_operativos_FINAL.docx` (intacto). Salida: `..._APA7.docx` y `..._APA7.pdf` (114 páginas).
Verificación hecha con LibreOffice y análisis del XML; **no** se abrió en Microsoft Word.

## 1. Criterios cumplidos (verificados)

| Criterio | Resultado |
|---|---|
| Fuente Times New Roman 12 | Estilo base y todos los estilos usados; PDF solo usa Times New Roman (más Consolas sustituida, ver 2) |
| Color negro | 0 nodos de color, sombreado, resaltado o subrayado en todo el documento (antes: 319 azules, 111 grises, 80 blancos, 611 sombreados) |
| Interlineado doble | 747 párrafos con interlineado 2.0: cuerpo, títulos, pies de figura y tabla, notas, índice, listas y referencias |
| Alineación izquierda | Sin justificado. Solo centrados: portada, títulos nivel 1 e imágenes |
| Márgenes 2,54 cm | 4 lados, en las 2 secciones |
| Sangría primera línea 1,27 cm | 389 párrafos del cuerpo (720 twips) |
| Espaciado anterior/posterior 0 pt | 0 valores distintos de cero en todo el documento |
| Sin líneas en blanco de relleno | 28 párrafos vacíos eliminados |
| Número de página arriba a la derecha | Encabezado en todas las páginas, incluida la portada |
| Títulos | Nivel 1: centrado, negrita (28). Nivel 2: izquierda, negrita (96). No existen niveles 3–5 en el documento |
| Código | 19 bloques (195 líneas): Consolas 9 pt, negro, sin fondo ni borde, espacios e indentación originales restaurados (desde BACKUP5), texto idéntico al original |
| Código en línea | 180 fragmentos: Consolas 10 pt, negro, sin sombreado |
| Tablas (28) | Estilo APA: regla superior, regla bajo encabezado, regla inferior, sin líneas verticales ni rellenos, texto negro |
| Pies de tabla y figura (28 + 45) | Número en negrita, título en cursiva en la línea siguiente, encima del elemento |
| Notas de figura (45) | "Nota." en cursiva + texto normal, debajo de la imagen |
| Figuras | 46 imágenes idénticas byte a byte; sin deformar; colores de capturas intactos |
| Referencias | 11 entradas, orden alfabético verificado, sangría francesa 1,27 cm, cursivas en títulos, URL conservadas |
| Citas | 1 corregida a APA 7: "(Silberschatz, Galvin y Gagne, 2018)" → "(Silberschatz et al., 2018)" (3 o más autores) |
| Contenido | Comparación palabra por palabra con el original: solo cambian números de página del índice, la separación número/título en pies y la cita anterior |
| Índice, lista de figuras, lista de tablas | 194 entradas recalculadas desde el PDF; 0 discrepancias |
| Páginas vacías | Ninguna. Se corrigió una página en blanco causada por el cierre de campo de la lista de figuras |

## 2. Excepciones y límites (decisión tomada, revisar si no convienen)

1. **Consolas no está instalada** en este equipo. En el .docx está declarada Consolas; en el PDF LibreOffice usó Noto Sans Mono. En Word se verá Consolas y los saltos de línea del código pueden variar levemente.
2. **Tablas a 10 pt e interlineado sencillo**, y **código con interlineado sencillo**. APA 7 lo permite (tablas 8–14 pt, cualquier interlineado). Con 12 pt doble, tablas como la de hashes SHA-256 no caben.
3. **Sin espacio tras tablas y bloques de código**: por la regla de 0 pt, el texto que sigue queda pegado.
4. **Índice y listas a doble espacio**, como pediste. Ocupa 12 páginas.
5. **Negritas del cuerpo** (nombres de producto, viñetas con encabezado en negrita) y cursivas se conservaron: son énfasis, no color.
6. **Números de página del índice**: calculados con la paginación de LibreOffice. En Word, pulsa Ctrl+A y F9 para actualizar campos.
7. Se restableció el encabezado con número de página, que en una tarea anterior se había quitado, porque APA 7 lo exige.

## 3. Criterios no verificables

- Aspecto final en Word (paginación, ajuste de línea de Consolas, saltos de página).
- Capitalización de títulos según APA 7 en español (oración vs. título): no se modificó texto.
- Ortografía: los fragmentos de código van marcados "no revisar".

## 4. Elementos que requieren corrección manual

1. **Referencias sin cita en el texto (7 de 11)**: GNU Project (GRUB), Intel Corporation, Oracle (VirtualBox), OSDev Wiki, Pittman (Pac-Man dossier), QEMU Project, Simple DirectMedia Layer. Solo 4 se citan (Creative Technology, Free Software Foundation, Silberschatz et al., Tanenbaum y Bos). Hay que citarlas en el texto o quitarlas. No se inventaron citas.
2. **Todas las citas del texto tienen referencia** (4 de 4). Las citas son todas parentéticas; no hay narrativas.
3. **Intel Corporation**: sin URL ni año (s. f.), y el editor repite al autor ("Intel."), que APA 7 omite.
4. **Creative Technology Ltd.**: la cita dice "Creative Technology" y la referencia "Creative Technology Ltd."; deben coincidir.
5. **Referencias "(s. f.)"**: 7 sin fecha. Si el sitio muestra año, hay que completarlo; no se asumió ninguno.
6. **DOI**: ninguna referencia tiene; no se agregó ninguno.
7. **Portada**: APA 7 pide título, autores, departamento y universidad, curso, docente y fecha. Aquí "Sistemas operativos" (el curso) va pegado a la línea de la institución, y falta el número del curso.
8. **Nota bajo la Tabla 22** ("La compilación y los hashes son de la sesión…") quedó en cursiva sin el rótulo "Nota.". Igual los demás párrafos explicativos tras tablas.
9. **Títulos numerados** ("1.1 Planteamiento…"): APA 7 no numera títulos; se dejó la numeración existente.
10. **Párrafo posterior a la lista de referencias** ("Las fuentes tipográficas Inter…"): no es una referencia; conviene moverlo a una nota o a anexos.
11. **Figuras**: las notas indican el origen técnico de cada captura o diagrama; APA 7 pide además la fuente o los derechos si la imagen no es propia (por ejemplo, el logotipo de la portada). No se verificó.
