from PIL import Image,ImageDraw,ImageFont
OUT="/home/t1an/Descargas/sereos02/documentacion/diagramas/"
FR="/usr/share/fonts/inter/InterVariable.ttf"
def F(sz,w='Regular'):
    f=ImageFont.truetype(FR,sz)
    try: f.set_variation_by_name(w)
    except Exception: pass
    return f
MONO=lambda sz: ImageFont.truetype("/usr/share/fonts/TTF/JetBrainsMono-Regular.ttf",sz)
BG=(255,255,255); INK=(28,34,48); MUTE=(96,106,124); LINE=(170,178,192)
C=dict(blue=(37,99,235),teal=(13,148,136),green=(22,128,61),amber=(180,83,9),red=(185,28,28),violet=(109,40,217),slate=(71,85,105),pink=(190,24,93))
LIGHT=dict(blue=(219,234,254),teal=(204,251,241),green=(220,252,231),amber=(254,243,199),red=(254,226,226),violet=(237,233,254),slate=(226,232,240),pink=(252,231,243))
class Cv:
    def __init__(s,w,h):
        s.im=Image.new('RGB',(w,h),BG); s.d=ImageDraw.Draw(s.im); s.w=w; s.h=h
    def text(s,xy,t,sz=28,w='Regular',fill=INK,anchor='la'):
        s.d.text(xy,t,font=F(sz,w),fill=fill,anchor=anchor)
    def box(s,x,y,w,h,title,sub=None,col='blue',tsz=28,ssz=22,fill=True):
        s.d.rounded_rectangle([x,y,x+w,y+h],radius=14,fill=LIGHT[col] if fill else BG,outline=C[col],width=3)
        if sub:
            s.text((x+w/2,y+h/2-ssz*0.75*(sub.count('\n')+1)/1.0+4),title,tsz,'Bold',INK,'mm')
            lines=sub.split('\n')
            for i,l in enumerate(lines):
                s.text((x+w/2,y+h/2+tsz*0.55+i*(ssz+6)-((len(lines)-1)*(ssz+6))/2),l,ssz,'Regular',MUTE,'mm')
        else:
            s.text((x+w/2,y+h/2),title,tsz,'Bold',INK,'mm')
    def arrow(s,x1,y1,x2,y2,col=MUTE,wd=4,dash=False,head=14):
        import math
        if dash:
            n=int(math.hypot(x2-x1,y2-y1)/16)
            for i in range(0,n,2):
                a=i/n;b=min((i+1)/n,1)
                s.d.line([x1+(x2-x1)*a,y1+(y2-y1)*a,x1+(x2-x1)*b,y1+(y2-y1)*b],fill=col,width=wd)
        else: s.d.line([x1,y1,x2,y2],fill=col,width=wd)
        ang=math.atan2(y2-y1,x2-x1)
        p=[(x2,y2),(x2-head*math.cos(ang-0.45),y2-head*math.sin(ang-0.45)),(x2-head*math.cos(ang+0.45),y2-head*math.sin(ang+0.45))]
        s.d.polygon(p,fill=col)
    def save(s,n): s.im.save(OUT+n,optimize=True); print(n,s.im.size)

# ---- D1: arquitectura por capas
c=Cv(1600,1180)
c.text((800,34),"Arquitectura por capas de SereOS 1.0",38,'Bold',INK,'ma')
layers=[
 ("Aplicaciones","violet",[("Terminal","shell compartida"),("Archivos","explorador RAMFS"),("Monitor","datos del kernel"),("Acerca de","14 componentes"),("PAC-MAN SereOS","libpacman.a")]),
 ("Escritorio (gui/)","blue",[("Compositor","desktop.c"),("Ventanas","window.c"),("Barra y dock","topbar, menú"),("Cursor","cursor.c"),("Tema y UI","theme.c, ui.c")]),
 ("Gráficos (graphics/)","teal",[("Framebuffer","LFB 1024x768x32"),("Motor 2D","graphics.c"),("Tipografía","Inter, JetBrains Mono"),("Backbuffer","regiones sucias")]),
 ("Subsistemas","green",[("Memoria","marcos, PSE, kmalloc"),("Tareas","round-robin cooperativo"),("RAMFS","64 nodos"),("Audio","SB16 / PC speaker"),("Shell","25 comandos")]),
 ("Drivers (drivers/)","amber",[("PIT","100 Hz"),("Teclado PS/2","IRQ 1"),("Ratón PS/2","IRQ 12"),("RTC","CMOS"),("COM1","serie"),("SB16","DMA 1, IRQ 5")]),
 ("Núcleo (kernel/, boot/)","red",[("boot.s / isr.s","Multiboot, 48 ISR"),("GDT","5 segmentos"),("IDT + PIC","vectores 32-47"),("Log y pánico","klog, panic"),("Apagado","shutdown.c")]),
 ("Arranque y hardware","slate",[("GRUB 2","Multiboot 1, BIOS"),("CPU i686","modo protegido"),("RAM, VGA/LFB","256 MiB"),("PIC, PIT, PS/2","SB16, RTC, COM1")]),
]
y=100;H=140;gap=12
for name,col,items in layers:
    c.d.rounded_rectangle([20,y,1580,y+H],radius=16,fill=(248,250,252),outline=LINE,width=2)
    c.text((40,y+12),name,26,'Bold',C[col])
    n=len(items); bw=(1520-(n-1)*14)/n
    for i,(t,s) in enumerate(items):
        c.box(40+i*(bw+14)-20+20,y+50,bw,H-62,t,s,col,tsz=24,ssz=20)
    y+=H+gap
c.save("d1_arquitectura_capas.png")

# ---- D2: flujo de arranque
c=Cv(1600,980)
c.text((800,30),"Secuencia de arranque de SereOS desde la ISO",38,'Bold',INK,'ma')
steps=[("BIOS","carga el sector\nde arranque\nde la ISO","slate"),("GRUB 2","menú 2 s,\nMultiboot 1,\nmodo 1024x768x32","amber"),("boot.s","pila 64 KiB,\npush EAX, EBX,\ncall kernel_main","red"),("kernel_main","init del\nkernel y drivers","blue"),("splash_run","logo y log\nreal del kernel","teal"),("gui_run","escritorio,\nbucle de eventos","violet")]
bw=210;gx=(1600-6*bw)/7
for i,(t,s,col) in enumerate(steps):
    x=gx+i*(bw+gx); c.box(x,110,bw,190,t,s,col,tsz=28,ssz=21)
    if i<5: c.arrow(x+bw+6,205,x+bw+gx-8,205,wd=5)
c.text((800,350),"Orden de inicialización dentro de kernel_main (kernel/kernel.c)",28,'Bold',INK,'ma')
seq=["serial","terminal","klog","Multiboot","GDT","IDT+PIC","input","PIT","teclado","ratón","RTC","speaker","framebuffer","marcos","heap","paginación","RAMFS","tareas","sti","audio","gfx_init","apps","gui_init"]
cols=6; cw=250; ch=62; x0=(1600-cols*cw-(cols-1)*14)/2
for i,s in enumerate(seq):
    r,cc=divmod(i,cols)
    x=x0+cc*(cw+14); yy=410+r*(ch+14)
    col='red' if i<6 else 'amber' if i<12 else 'green' if i<20 else 'violet'
    c.d.rounded_rectangle([x,yy,x+cw,yy+ch],radius=12,fill=LIGHT[col],outline=C[col],width=2)
    c.text((x+14,yy+ch/2),f"{i+1}",22,'Bold',C[col],'lm'); c.text((x+cw/2+10,yy+ch/2),s,24,'Regular',INK,'mm')
c.d.rounded_rectangle([60,780,1540,940],radius=16,fill=(248,250,252),outline=LINE,width=2)
c.text((90,796),"Si no hay framebuffer válido",26,'Bold',C['red'])
c.text((90,840),"kernel_main no entra al escritorio: escribe 'SEREOS_TEXT_MODE' por COM1 y llama a shell_run_text(),",24,'Regular',INK)
c.text((90,876),"la consola VGA 80x25 con la misma shell. Es la segunda entrada del menú de GRUB (sereos-text.bin).",24,'Regular',INK)
c.save("d2_arranque.png")

# ---- D3: interrupciones
c=Cv(1600,900)
c.text((800,30),"Camino de una interrupción en SereOS",38,'Bold',INK,'ma')
b=[("Dispositivo","PIT, teclado,\nratón","slate",50,150),("PIC 8259","IRQ 0-15 →\nvectores 32-47","green",345,150),("CPU + IDT","consulta la\npuerta 0x8E","amber",640,150),("isr.s / irq N","guarda\nregistros","red",935,150),("interrupt_handler()","kernel/idt.c","blue",1230,150)]
for t,s2,col,x,yy in b: c.box(x,yy,240,170,t,s2,col,tsz=25,ssz=21)
for i in range(4): c.arrow(b[i][3]+246,235,b[i+1][3]-6,235,wd=5)
c.box(1030,420,330,150,"irq_handlers[n]","timer_callback\nkeyboard_callback\nmouse_callback","teal",tsz=26,ssz=21)
c.box(1230+0,640,300,130,"EOI al PIC","outb(0x20, 0x20)\n(+0xA0 si IRQ ≥ 8)","slate",tsz=26,ssz=21)
c.arrow(1365,325,1195,418,wd=5); c.arrow(1195,572,1330,638,wd=5)
c.text((1400,380),"n ≥ 32",22,'Bold',MUTE)
c.box(520,420,330,150,"panic_exception()","n < 32: pantalla de\nerror crítico y hlt","pink",tsz=26,ssz=21)
c.arrow(1235,300,860,445,col=C['pink'],wd=4,dash=True)
c.text((1000,420),"n < 32",22,'Bold',C['pink'])
c.box(70,650,360,130,"iret","restaura registros y\nvuelve al programa","blue",tsz=26,ssz=21)
c.arrow(1225,705,440,715,wd=4,dash=True)
c.text((800,690),"retorno",22,'Regular',MUTE,'mm')
c.save("d3_interrupciones.png")

# ---- D4: mapa de memoria
c=Cv(1600,1100)
c.text((800,30),"Mapa de memoria del kernel (linker.ld y sereos.bin)",38,'Bold',INK,'ma')
segs=[("0x00000000 - 0x000FFFFF","Memoria baja (BIOS, VGA, EBDA)","reservada por page.c","slate",100),
("0x00200000 - 0x0022B191","Sección .text","176 KiB: código, cabecera Multiboot","red",100),
("0x0022C000 - 0x0035A5BF","Sección .rodata","1,2 MiB: fuentes, iconos, logo, SFX, sprites","amber",120),
("0x0035B000 - 0x01687 8DF".replace(' ',''),"Secciones .data y .bss","19,2 MiB: heap de 8 MiB, backbuffer, bitmaps de marcos, pila de 64 KiB","blue",150),
("hasta 0x1FFFFFFF (512 MiB)","Identidad con páginas PSE de 4 MiB","marcos libres para page_alloc()","green",120),
("0xE0000000 - 0xFFFFFFFF","Rango del framebuffer lineal","mapeado con PSE; el LFB de GRUB cae aquí","teal",120)]
y=110
for a,b2,c2,col,h in segs:
    c.d.rectangle([420,y,1240,y+h],fill=LIGHT[col],outline=C[col],width=3)
    c.text((830,y+h/2-16),b2,28,'Bold',INK,'mm'); c.text((830,y+h/2+22),c2,21,'Regular',MUTE,'mm')
    c.text((400,y+h/2),a,22,'Regular',INK,'rm')
    y+=h+14
c.text((1260,300),"kernel_start = 2 MiB",22,'Regular',C['red'])
c.text((1260,440),"kernel_end ≈ 22,5 MiB",22,'Regular',C['blue'])
c.text((800,1040),"Direcciones tomadas de readelf -lW sereos.bin y de las constantes de memory/page.c",22,'Regular',MUTE,'mm')
c.save("d4_mapa_memoria.png")

# ---- D5: arquitectura del juego
c=Cv(1600,1060)
c.text((800,30),"PAC-MAN SereOS: una lógica, dos plataformas",38,'Bold',INK,'ma')
c.box(120,110,1360,150,"src/core (3270 líneas)","máquina de estados, laberinto 28x31, entidades, IA de fantasmas, puntuación,\nentrada lógica y eventos de audio. No incluye cabeceras de SereOS ni de SDL","blue",tsz=30,ssz=22)
c.box(120,300,1360,130,"src/render (1426 líneas)","pantallas, HUD, menús arcade, overlays y kit visual compartido (pac_theme, pac_ui)","teal",tsz=30,ssz=22)
c.box(120,470,1360,110,"include/pac_platform.h  (contrato, ABI 1)","tiempo, memoria, entrada, primitivas 2D, texto, audio, almacenamiento, marcadores de QA","amber",tsz=28,ssz=22)
c.box(120,640,650,170,"platform/sereos (756 líneas)","game_app.c: app_t *app_game(void)\nplatform_sereos.c: gfx, text, input,\ntimer, audio SB16, RAMFS, serie","violet",tsz=27,ssz=21)
c.box(830,640,650,170,"platform/linux (1821 líneas)","SDL2, framebuffer por software,\naudio PCM, ajustes en XDG_DATA_HOME,\nescenas forzadas para QA","slate",tsz=27,ssz=21)
for xx in (445,1155):
    c.arrow(xx,435,xx,468,wd=4); c.arrow(xx,585,xx,638,wd=4)
c.box(120,880,650,130,"libpacman.a  →  sereos.bin","se enlaza al kernel antes de -lgcc;\napps.c solo llama a app_game()","red",tsz=27,ssz=21)
c.box(830,880,650,130,"build/pacman-sereos","ejecutable nativo en CachyOS (pruebas)\nmismo núcleo, mismo render","green",tsz=27,ssz=21)
c.arrow(445,812,445,878,wd=4); c.arrow(1155,812,1155,878,wd=4)
c.save("d5_arquitectura_juego.png")

# ---- D6: pipeline de compilación
c=Cv(1600,940)
c.text((800,30),"Cadena de construcción de la ISO",38,'Bold',INK,'ma')
c.box(40,120,330,150,"Fuentes del OS","50 archivos .c/.s\n(boot, kernel, drivers,\ngui, apps...)","blue",tsz=26,ssz=20)
c.box(40,330,330,150,"Fuentes del juego","src/core, src/render,\nplatform/sereos, assets","violet",tsz=26,ssz=20)
c.box(450,120,330,150,"gcc -m32 / nasm","-ffreestanding -O2\n-mno-sse -mno-mmx\nobjetos en build/","amber",tsz=26,ssz=20)
c.box(450,330,330,150,"make sereos","gcc -m32 + ar rcs\n→ libpacman.a","amber",tsz=26,ssz=20)
c.box(860,225,330,150,"gcc -T linker.ld","-nostdlib ... libpacman.a\n-lgcc → sereos.bin","red",tsz=26,ssz=20)
c.box(1240,120,330,130,"patch_multiboot_text.py","flags 0x7 → 0x3\n→ sereos-text.bin","slate",tsz=24,ssz=20)
c.box(1240,300,330,130,"grub-file","--is-x86-multiboot\nvalida ambos binarios","green",tsz=26,ssz=20)
c.box(860,560,330,150,"isodir/","boot/sereos.bin\nboot/sereos-text.bin\nboot/grub/grub.cfg","teal",tsz=26,ssz=20)
c.box(450,560,330,150,"grub-mkrescue","xorriso + mtools\n→ sereos.iso (35 MiB)","red",tsz=26,ssz=20)
c.box(40,560,330,150,"VirtualBox","IDE secundario,\nBIOS, 256 MiB,\nSB16","violet",tsz=26,ssz=20)
for a in [(375,195,445,195),(375,405,445,405),(785,195,855,285),(785,405,855,320),(1190,300,1235,190),(1190,300,1235,360)]: c.arrow(*a,wd=4)
c.arrow(1400,435,1400,500,wd=4); c.arrow(1400,500,1030,556,wd=4)
c.arrow(855,635,785,635,wd=4); c.arrow(445,635,375,635,wd=4)
c.text((800,780),"Los pasos 1 a 3 los ejecuta make; el paso VirtualBox es manual (VBoxManage o interfaz).",24,'Regular',MUTE,'mm')
c.save("d6_pipeline_iso.png")
