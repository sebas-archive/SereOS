"""Genera recursos gráficos del video: portada, cierre y cápsulas de subtítulos
(estilo Dynamic Island). Usa el logotipo oficial de SereOS sin modificarlo."""
import math, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
ASSETS = os.path.join(VIDEO, "recursos")
LOGO = "/home/t1an/Descargas/sereos02/sistema operativo/assets/logo/official_logo.png"
FONT = "/usr/share/fonts/inter/InterVariable.ttf"
FONT_B = "/usr/share/fonts/inter/Inter.ttc"  # familia completa (con pesos)
W, H = 1920, 1080


def run(args):
    subprocess.run(args, check=True)


def text_size(text, pointsize, font=FONT):
    out = subprocess.run(["magick", "-font", font, "-pointsize", str(pointsize),
                          f"label:{text}", "-format", "%w %h", "info:"],
                         capture_output=True, text=True, check=True).stdout.split()
    return int(out[0]), int(out[1])


def base_bg(path):
    """Fondo oscuro con degradado radial azulado, coherente con el escritorio."""
    run(["magick", "-size", f"{W}x{H}", "radial-gradient:#16233a-#06080d",
         "-attenuate", "0.25", "+noise", "Gaussian", "-attenuate", "0.05",
         "-colorspace", "sRGB", path])


def logo_layer(path, height=260):
    """Marca oficial recortada en círculo (forma CIRCLE de gui/logo.c), sin deformar."""
    d = height
    run(["magick", LOGO, "-resize", f"{d}x{d}^", "-gravity", "center", "-extent", f"{d}x{d}",
         "(", "-size", f"{d}x{d}", "xc:none", "-fill", "white",
         "-draw", f"circle {d/2},{d/2} {d/2},0", ")",
         "-compose", "CopyOpacity", "-composite", f"PNG32:{path}"])


def light_band(path, w=420, h=H):
    """Banda de luz diagonal y suave para el barrido de la animación."""
    half = w // 2
    run(["magick", "-size", f"{half}x{h}", "gradient:rgba(255,255,255,0)-rgba(255,255,255,0.9)",
         "(", "-size", f"{half}x{h}", "gradient:rgba(255,255,255,0.9)-rgba(255,255,255,0)", ")",
         "+append", f"PNG32:{path}"])


def decor(path, cx=960, cy=540):
    """Fondo con elementos gráficos en los espacios vacíos: anillos concéntricos,
    arcos, retícula de puntos y marcas de esquina (estilo del escritorio)."""
    d = []
    rings = [(230, 0.30), (330, 0.22), (450, 0.16), (600, 0.11), (780, 0.07), (980, 0.05)]
    for r, a in rings:
        d.append(f"-stroke rgba(91,140,255,{a}) -strokewidth 2 -fill none -draw \"circle {cx},{cy} {cx+r},{cy}\"")
    # arcos tenues con ángulos distintos
    for r, a0, a1, alpha in ((390, 200, 290, 0.22), (560, 300, 20, 0.16), (720, 60, 150, 0.10)):
        import math
        x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
        x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
        d.append(f"-stroke rgba(120,170,255,{alpha}) -strokewidth 3 -fill none -draw \"path 'M {x0:.1f},{y0:.1f} A {r},{r} 0 0 1 {x1:.1f},{y1:.1f}'\"")
    # nodos brillantes sobre los anillos
    for r, ang in ((330, 35), (450, 140), (600, 300), (780, 210), (230, 320)):
        x, y = cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang))
        d.append(f"-stroke none -fill rgba(120,170,255,0.55) -draw \"circle {x:.1f},{y:.1f} {x+3:.1f},{y:.1f}\"")
        d.append(f"-fill rgba(120,170,255,0.12) -draw \"circle {x:.1f},{y:.1f} {x+9:.1f},{y:.1f}\"")
    # retícula de puntos en los márgenes
    for gx in range(60, W, 60):
        for gy in range(60, H, 60):
            if abs(gx - cx) > 620 or abs(gy - cy) > 380:
                d.append(f"-stroke none -fill rgba(140,170,220,0.10) -draw \"circle {gx},{gy} {gx+1.6},{gy}\"")
    # marcas de esquina
    for x, y, sx, sy in ((70, 70, 1, 1), (W - 70, 70, -1, 1), (70, H - 70, 1, -1), (W - 70, H - 70, -1, -1)):
        d.append(f"-stroke rgba(91,140,255,0.45) -strokewidth 3 -fill none -draw \"path 'M {x},{y} l {sx*60},0 M {x},{y} l 0,{sy*60}'\"")
    import shlex
    rings_path = path[:-4] + "_rings.png"
    args = ["magick", "-size", f"{W}x{H}", "xc:none"]
    for item in d:
        args += shlex.split(item)
    args.append(f"PNG32:{rings_path}")
    run(args)
    base = path[:-4] + "_base.png"
    base_bg(base)
    run(["magick", base, rings_path, "-composite", f"PNG32:{path}"])
    return rings_path


def text_layer(path, text, pointsize, color="#e8edf5", tracking=0, font=FONT, weight=None):
    args = ["magick", "-background", "none", "-font", font, "-pointsize", str(pointsize),
            "-fill", color, f"label:{text}", f"PNG32:{path}"]
    if tracking:
        args = ["magick", "-background", "none", "-font", font, "-pointsize", str(pointsize),
                "-fill", color, "-kerning", str(tracking), f"label:{text}", f"PNG32:{path}"]
    run(args)


def capsule(path, text, font_size=40, pad_x=60, pad_y=26):
    """Cápsula flotante estilo Dynamic Island: fondo oscuro translúcido, esquinas
    totalmente redondeadas, texto Inter SemiBold con interletrado ligero y sombra
    suave para legibilidad sobre cualquier fondo."""
    tw, th = text_size(text, font_size, FONT)
    w = tw + pad_x * 2
    h = max(th, font_size) + pad_y * 2
    r = h // 2
    pad = 48
    W2, H2 = w + pad * 2, h + pad * 2
    font = "Inter-SemiBold"
    run(["magick", "-size", f"{W2}x{H2}", "xc:none",
         "-fill", "rgba(0,0,0,0.42)", "-draw", f"roundrectangle {pad},{pad+8} {pad+w},{pad+h+8} {r},{r}",
         "-blur", "0x12",
         "-fill", "rgba(12,15,22,0.82)", "-stroke", "rgba(255,255,255,0.14)", "-strokewidth", "2",
         "-draw", f"roundrectangle {pad},{pad} {pad+w},{pad+h} {r},{r}",
         "-stroke", "none", "-font", font, "-pointsize", str(font_size),
         "-kerning", "0.4",
         "(", "-size", f"{W2}x{H2}", "xc:none", "-font", font, "-pointsize", str(font_size),
         "-kerning", "0.4", "-fill", "rgba(0,0,0,0.35)", "-gravity", "center",
         "-annotate", "+0+2", text, "-blur", "0x2", ")", "-composite",
         "-font", font, "-pointsize", str(font_size), "-kerning", "0.4",
         "-fill", "#ffffff", "-gravity", "center", "-annotate", "+0+0", text,
         "-trim", "+repage", "-bordercolor", "none", "-border", str(pad), f"PNG32:{path}"])
    return tw, h


def make_cover():
    """Portada: logotipo protagonista, nombre SereOS grande, textos de apoyo con tracking."""
    decor(os.path.join(ASSETS, "portada_fondo.png"), 960, 280)
    logo = os.path.join(ASSETS, "portada_logo.png")
    logo_layer(logo, 300)
    t1 = os.path.join(ASSETS, "portada_t1.png")
    text_layer(t1, "PROYECTO FINAL", 40, "#8fa6c8", tracking=14)
    t2 = os.path.join(ASSETS, "portada_t2.png")
    text_layer(t2, "SISTEMAS OPERATIVOS", 40, "#8fa6c8", tracking=14)
    t3 = os.path.join(ASSETS, "portada_t3.png")
    text_layer(t3, "SereOS", 210, "#ffffff", tracking=-4)
    rule = os.path.join(ASSETS, "portada_linea.png")
    run(["magick", "-size", "180x2", "xc:#5b8cff", f"PNG32:{rule}"])


def make_closing():
    """Cierre: GRACIAS con protagonismo, después la marca y el nombre del proyecto."""
    decor(os.path.join(ASSETS, "cierre_fondo.png"), 960, 235)
    logo = os.path.join(ASSETS, "cierre_logo.png")
    logo_layer(logo, 130)
    t1 = os.path.join(ASSETS, "cierre_gracias.png")
    text_layer(t1, "GRACIAS", 200, "#ffffff", tracking=10)
    t2 = os.path.join(ASSETS, "cierre_sereos.png")
    text_layer(t2, "SereOS", 56, "#8fa6c8", tracking=2)
    t3 = os.path.join(ASSETS, "cierre_proyecto.png")
    text_layer(t3, "PROYECTO FINAL — SISTEMAS OPERATIVOS", 30, "#5d6b82", tracking=6)
    rule = os.path.join(ASSETS, "cierre_linea.png")
    run(["magick", "-size", "120x2", "xc:#5b8cff", f"PNG32:{rule}"])


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    light_band(os.path.join(ASSETS, "banda_luz.png"))
    make_cover()
    make_closing()
    print("recursos generados en", ASSETS)
