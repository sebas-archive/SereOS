# -*- coding: utf-8 -*-
# Presentación SereOS con marcos vacíos para fotos reales. Coordenadas en px de un lienzo 1920x1080.
# Conversión: 1920 px = 13.333 in  ->  1 px = 1/144 in  ;  1 px = 0.5 pt (tamaños: 80px=40pt, 40px=20pt, 32px=16pt)
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

BG="12151D"; TXT="E8EAF0"; GRIS="8B93A7"; ACC="2F6DF6"; FRAME="1A1E27"; LINE="2A2F3A"
FT="Inter"; FM="JetBrains Mono"
OUT="/home/t1an/Descargas/sereos02/documentacion/presentacion/Presentacion_Final_SereOS_3.pptx"

prs=Presentation(); prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
prs.slide_master.background.fill.solid(); prs.slide_master.background.fill.fore_color.rgb=RGBColor.from_string(BG)
BLANK=prs.slide_layouts[6]
def P(v): return Inches(v/144)
def rgb(h): return RGBColor.from_string(h)

def tb(s,x,y,w,h,lines,size,color=TXT,font=FT,bold=False,align="l",spacing=0):
    b=s.shapes.add_textbox(P(x),P(y),P(w),P(h)); tf=b.text_frame; tf.word_wrap=True
    tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
    for i,t in enumerate(lines if isinstance(lines,list) else [lines]):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.alignment={"l":PP_ALIGN.LEFT,"c":PP_ALIGN.CENTER,"r":PP_ALIGN.RIGHT}[align]
        if spacing: p.space_after=Pt(spacing)
        r=p.add_run(); r.text=t; f=r.font; f.size=Pt(size); f.bold=bold; f.name=font; f.color.rgb=rgb(color)
    return b

def set_name(shape,name):
    shape._element.xpath('./*[1]/p:cNvPr')[0].set('name',name)

def frame(s,name,x,y,w,h,label):
    r=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,P(x),P(y),P(w),P(h))
    r.adjustments[0]=8/min(w,h); r.shadow.inherit=False
    r.fill.solid(); r.fill.fore_color.rgb=rgb(FRAME)
    r.line.color.rgb=rgb(LINE); r.line.width=Pt(1)
    tf=r.text_frame; tf.word_wrap=True; tf.vertical_anchor=MSO_ANCHOR.MIDDLE
    p=tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
    run=p.add_run(); run.text=label; run.font.size=Pt(16); run.font.name=FM; run.font.color.rgb=rgb(GRIS)
    set_name(r,name); return r

def line(s,x1,y1,x2,y2,color=LINE,w=1):
    c=s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,P(x1),P(y1),P(x2),P(y2))
    c.line.color.rgb=rgb(color); c.line.width=Pt(w)

def dot(s,x,y,d,color):
    o=s.shapes.add_shape(MSO_SHAPE.OVAL,P(x),P(y),P(d),P(d)); o.shadow.inherit=False
    o.fill.solid(); o.fill.fore_color.rgb=rgb(color); o.line.fill.background()

n=[0]
def slide(title=None):
    s=prs.slides.add_slide(BLANK); n[0]+=1
    if title: tb(s,120,96,1680,120,title,40,bold=True)
    tb(s,1560,1000,240,40,f"{n[0]:02d}/14",16,GRIS,FM,align="r")
    return s

# 01 PORTADA
s=prs.slides.add_slide(BLANK); n[0]+=1
tb(s,120,96,1200,40,"PROYECTO FINAL — SISTEMAS OPERATIVOS",16,GRIS,FM)
tb(s,120,300,1200,220,"SereOS",100,bold=True)
tb(s,120,560,1200,60,"Una presentación del proyecto",20,GRIS)
tb(s,120,860,1200,40,"Universidad Mariana (UMB) · Noviembre de 2026",16,GRIS)
tb(s,120,904,1200,40,"Integrantes: [nombres del equipo]",16,GRIS)
frame(s,"LOGOTIPO_OFICIAL",1520,120,280,280,"LOGOTIPO OFICIAL")
tb(s,1560,1000,240,40,f"{n[0]:02d}/14",16,GRIS,FM,align="r")

# 02 CONOCE SERESOS
s=slide("Conoce SereOS")
tb(s,120,300,680,300,"Sistema operativo propio de 32 bits para la arquitectura i686, con escritorio gráfico, terminal y un videojuego integrado.",20,TXT)
frame(s,"IMG_INTERFAZ_PRINCIPAL",880,240,920,680,"IMG_INTERFAZ_PRINCIPAL · captura de la interfaz de SereOS")

# 03 PROPÓSITO
s=slide("¿Qué buscamos resolver?")
cols=[("PROBLEMA","Entre el gestor de arranque y la primera ventana hay pasos que los libros suelen dar por resueltos."),
      ("NECESIDAD","Un sistema completo, de principio a fin, que pueda verificarse en una máquina virtual estándar."),
      ("SOLUCIÓN","SereOS: un kernel propio, drivers, escritorio y un juego que se ejecuta dentro del sistema.")]
for i,(lab,txt) in enumerate(cols):
    x=120+i*580
    tb(s,x,300,520,30,lab,16,ACC,FM)
    tb(s,x,360,520,260,txt,20,TXT)
line(s,680,300,680,800); line(s,1260,300,1260,800)

# 04 VISIÓN GENERAL
s=slide("Un sistema, múltiples componentes")
tb(s,120,200,1680,40,"Kernel, drivers, escritorio y aplicaciones conviven en un único sistema.",20,GRIS)
frame(s,"IMAGEN_GENERAL_DEL_SISTEMA",120,280,1680,620,"IMAGEN GENERAL DEL SISTEMA · captura del escritorio con varias ventanas")

# 05 ARQUITECTURA
s=slide("Arquitectura del sistema")
frame(s,"ARQUITECTURA_REAL",120,240,1680,680,"DIAGRAMA · ARQUITECTURA REAL POR CAPAS (siete capas, de hardware a aplicaciones)")
tb(s,120,940,1680,40,"Cada capa usa la inferior. Las aplicaciones comparten el anillo 0 con el kernel.",16,GRIS)

# 06 TECNOLOGÍAS
s=slide("Tecnología detrás de SereOS")
techs=[("GRUB 2","cargador de arranque, Multiboot 1"),("NASM 3.02","ensamblador, formato elf32"),
       ("gcc 16.2.1","compilación con -m32"),("GNU Make 4.4.1","automatiza compilación e ISO"),
       ("VirtualBox 7.2.22","Oracle VM, máquina virtual de validación"),("SDL2","plataforma Linux del juego, solo pruebas")]
for i,(nm,ds) in enumerate(techs):
    cx=120+(i%3)*580; cy=240+(i//3)*400
    frame(s,f"LOGO_TECNOLOGIA_{i+1:02d}",cx,cy,240,240,"LOGO REAL")
    tb(s,cx,cy+260,520,40,nm,20,TXT,bold=True)
    tb(s,cx,cy+306,520,30,ds,16,GRIS)

# 07 INTERACTUAR
s=slide("Diseñado para interactuar")
frame(s,"IMG_INTERFAZ_PRINCIPAL_07",288,200,1344,756,"IMG_INTERFAZ_PRINCIPAL · captura de SereOS")
tb(s,288,980,1344,30,"Escritorio, barra superior, dock y ventanas.",16,GRIS)

# 08 FUNCIONALIDADES
s=slide("Lo que hace SereOS")
feats=[("Escritorio","Barra superior, dock y ventanas con foco sobre un compositor propio."),
       ("Terminal","Shell de 25 comandos en la terminal gráfica y en la consola de respaldo."),
       ("Monitor y archivos","Monitor del sistema y explorador de archivos sobre un RAMFS en memoria."),
       ("PAC-MAN SereOS","Videojuego nativo que se ejecuta dentro del sistema.")]
for i,(t,d) in enumerate(feats):
    x=120+i*420
    frame(s,f"IMG_FUNCIONALIDAD_{i+1:02d}",x,240,380,240,f"IMG_FUNCIONALIDAD_{i+1:02d}")
    tb(s,x,510,380,36,t,20,TXT,bold=True)
    tb(s,x,560,380,120,d,16,GRIS)

# 09 FUNCIONAMIENTO
s=slide("SereOS en funcionamiento")
frame(s,"DEMOSTRACION",120,240,1680,680,"DEMOSTRACIÓN · captura panorámica de SereOS con varias aplicaciones")
tb(s,120,940,1680,30,"Ejecutándose en Oracle VM VirtualBox 7.2.22.",16,GRIS)

# 10 FLUJO
s=slide("Así funciona")
line(s,120,360,1800,360,LINE,1)
steps=[("Arranque","GRUB 2 carga el kernel con cabecera Multiboot."),
       ("Preparación","boot.s configura la pila y llama a kernel_main."),
       ("Inicialización","kernel_main ejecuta 23 pasos y registra cada uno."),
       ("Escritorio","Se muestra el splash y se inicia el escritorio."),
       ("Respaldo","Sin framebuffer, el sistema arranca en modo texto.")]
for i,(t,d) in enumerate(steps):
    x=120+i*336
    tb(s,x,300,300,30,f"{i+1:02d}",16,ACC,FM)
    dot(s,x,354,12,ACC if i==0 else GRIS)
    tb(s,x,420,300,40,t,20,TXT,bold=True)
    tb(s,x,470,300,120,d,16,GRIS)

# 11 COMPONENTES
s=slide("Cada componente tiene un propósito")
comps=[("Kernel","GDT, IDT, PIC y PIT: interrupciones y temporización a 100 Hz.",120,240),
       ("Memoria","Marcos de 4 KiB, paginación PSE e identidad hasta 512 MiB.",1000,240),
       ("Terminal","Shell compartida entre la terminal gráfica y la consola VGA de respaldo.",120,600),
       ("PAC-MAN SereOS","Lógica común del juego y contrato de plataforma pac_platform.h.",1000,600)]
for i,(t,d,x,y) in enumerate(comps):
    frame(s,f"COMPONENTE_{i+1:02d}",x,y,800,200,f"COMPONENTE_{i+1:02d}")
    tb(s,x,y+220,800,36,t,20,TXT,bold=True)
    tb(s,x,y+262,800,30,d,16,GRIS)

# 12 HITOS
s=slide("De la idea a la implementación")
line(s,120,520,1800,520,LINE,1)
hitos=[("23 oct","Versión 0.1","Cabecera Multiboot, terminal VGA y Makefile con ISO.","5 archivos · 230 líneas"),
       ("30 oct","Versión 0.2","GDT, IDT, PIC, PIT a 100 Hz, teclado y shell.","15 archivos · 674 líneas"),
       ("20 nov","Versión 1.0","Escritorio, aplicaciones y PAC-MAN SereOS.","93 archivos · 63 777 líneas (46 880 son datos generados)"),
       ("Pruebas","Validación","24 pruebas en VirtualBox y 209 comprobaciones del juego.","2 pruebas de ratón en QEMU")]
for i,(f,t,d,dd) in enumerate(hitos):
    x=120+i*420
    tb(s,x,440,380,30,f,16,ACC,FM)
    dot(s,x,512,16,ACC if i==2 else GRIS)
    tb(s,x,560,380,40,t,20,TXT,bold=True)
    tb(s,x,610,380,120,d,16,GRIS)
    tb(s,x,770,380,120,dd,16,GRIS)
tb(s,120,940,1680,30,"Cifras tomadas del informe de validación del proyecto.",16,GRIS)

# 13 RESULTADO
s=slide("El resultado: SereOS")
tb(s,120,200,1000,120,"Un sistema operativo de 32 bits que arranca desde una ISO en VirtualBox y ejecuta escritorio, terminal, aplicaciones y PAC-MAN.",20,TXT)
frame(s,"IMG_RESULTADO",120,360,1000,560,"IMG_RESULTADO · captura final del escritorio")
frame(s,"CAPTURA_01",1160,360,360,240,"CAPTURA 01 · terminal")
frame(s,"CAPTURA_02",1160,640,360,240,"CAPTURA 02 · PAC-MAN")
tb(s,1160,910,640,60,"Pendiente: multitarea preemptiva, anillo 3, disco, red y pruebas en hardware físico.",16,GRIS)

# 14 CIERRE
s=prs.slides.add_slide(BLANK); n[0]+=1
line(s,(1920-120)/2,330,(1920+120)/2,330,ACC,1.5)
tb(s,0,380,1920,220,"SereOS",100,bold=True,align="c")
tb(s,0,600,1920,40,"GRACIAS POR SU ATENCIÓN",20,TXT,align="c")
tb(s,0,960,1920,40,"PROYECTO FINAL — SISTEMAS OPERATIVOS",16,GRIS,FM,align="c")
tb(s,1560,1000,240,40,f"{n[0]:02d}/14",16,GRIS,FM,align="r")

prs.save(OUT); print("saved", OUT, len(prs.slides))
