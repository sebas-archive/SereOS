# Avisos de terceros (third-party notices)

## Alcance de la licencia

El archivo [LICENSE](../LICENSE) (MIT) cubre **únicamente el código original** de
SereOS y de PAC-MAN SereOS: kernel, drivers, memoria, RAMFS, GUI, aplicaciones,
shell, herramientas y la lógica del juego.

**No** cubre, y no puede cubrir, los siguientes contenidos de terceros, que
conservan sus propias condiciones:

| Contenido | Ubicación | Condición |
|---|---|---|
| Recursos arcade de `Res` (sprites PNG y sonidos WAV) | `Pac-man SereOS/assets/res_original/` | Propiedad de sus autores; **no se autoriza su redistribución pública** ni el uso comercial. Ver `assets/res_original/LICENSE_RES.md`. |
| Datos derivados de esos recursos | `Pac-man SereOS/assets/sfx_res.c`, `sprites_res.c`, `font_arcade.c` | Derivados de los anteriores; misma restricción. |
| Fuente *Press Start K* (© 2001-2002 codeman38) | `Pac-man SereOS/assets/res_original/prstartk.ttf` | Sin licencia declarada en el archivo; uso privado/académico con atribución. Ver `assets/fonts/LICENSE_ARCADE.md`. |
| Tipografías **Inter** y **JetBrains Mono** | No se distribuyen como archivos: se usan en tiempo de compilación para generar `graphics/text_data.c` | SIL Open Font License 1.1. Ver `assets/fonts/LICENSE.md`. |
| Informe APA 7, presentación y diagramas | `documentacion/` | Documentos académicos del equipo; no se licencian bajo MIT. |

Los nombres y personajes de PAC-MAN son marcas de sus respectivos titulares
(Namco). Este proyecto no reclama autoría sobre ellos y no está afiliado ni
patrocinado por sus titulares.

## Cómo cumplir la licencia

- Puedes usar, copiar, modificar y redistribuir **el código** citando el aviso
  de copyright de [LICENSE](../LICENSE).
- Si redistribuyes o publicas el proyecto, **elimina** los recursos listados
  arriba como restringidos o pide permiso a sus autores.
- Las fuentes se conservan bajo OFL 1.1; mantén sus archivos de licencia si las
  redistribuyes.

## Contacto

Para permisos, dudas o retiradas: abre un *issue* en el repositorio
https://github.com/sebas-archive/SereOS
