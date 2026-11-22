"""Recursos de marca para la apertura y el cierre (dirección artística común).

- Paleta y tipografías tomadas de la presentación de referencia
  (documentacion/presentacion/fuente/config.py): fondo #12151D, texto #E8EAF0,
  gris #9AA1B2, acento #2F6DF6; Inter + JetBrains Mono.
- Iconos vectoriales reales de Lucide (ISC), leídos de un paquete lucide-react
  instalado localmente; se convierten a SVG sin redibujarlos.
- Textura técnica auténtica: líneas reales del registro serie de arranque de
  SereOS (tools/serial_rec.log), capturado durante la grabación.
"""
import os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
OUT = os.path.join(VIDEO, "recursos", "marca")
LUCIDE = "/home/t1an/UMB-proyecto-cardiaco/web/node_modules/lucide-react/dist/esm/icons"
LOGO = "/home/t1an/Descargas/sereos02/sistema operativo/assets/logo/official_logo.png"
SERIAL = os.path.join(HERE, "serial_rec.log")

W, H = 1920, 1080
BG = "#12151D"
TXT = "#E8EAF0"
GRIS = "#9AA1B2"
ACENTO = "#2F6DF6"
F_DISPLAY = "Inter-Display-SemiBold"
F_DISPLAY_MED = "Inter-Display-Medium"
F_TEXT = "Inter-Medium"
F_MONO = "JetBrains-Mono-Medium"

# icono Lucide -> etiqueta técnica respaldada por el proyecto
ICONS = [
    ("cpu", "i686 · 32 bits"),
    ("memory-stick", "Paginación PSE"),
    ("keyboard", "PS/2"),
    ("monitor", "1024×768×32"),
    ("square-terminal", "Shell"),
]


def run(args):
    subprocess.run(args, check=True)


def lucide_svg(name, color, stroke=1.5, size=96):
    src = open(os.path.join(LUCIDE, name + ".mjs")).read()
    node = src[src.index("node: ["):src.index("]\n};")]
    parts = []
    for tag, attrs in re.findall(r'\["(\w+)", \{([^}]*)\}\]', node):
        kv = [(k, v) for k, v in re.findall(r'(\w+): "([^"]*)"', attrs) if k != "key"]
        parts.append(f"<{tag} " + " ".join(f'{k}="{v}"' for k, v in kv) + "/>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-linejoin="round">' + "".join(parts) + "</svg>")


def text_png(path, text, font, size, color, kerning=0):
    run(["magick", "-background", "none", "-font", font, "-pointsize", str(size),
         "-kerning", str(kerning), "-fill", color, f"label:{text}", f"PNG32:{path}"])


def background(path, glow_y=500):
    """Fondo #12151D con luz azul tenue tras el título y viñeta: profundidad sin efectos."""
    run(["magick", "-size", f"{W}x{H}", f"xc:{BG}",
         "(", "-size", f"{W}x{H}", "xc:none", "-fill", "rgba(47,109,246,0.42)",
         "-draw", f"ellipse 960,{glow_y} 560,300 0,360", "-blur", "0x160", ")",
         "-compose", "over", "-composite",
         "(", "-size", f"{W}x{H}", "radial-gradient:rgba(0,0,0,0)-rgba(0,0,0,0.6)", ")",
         "-compose", "over", "-composite",
         "-attenuate", "0.10", "+noise", "Gaussian", f"PNG32:{path}"])


def log_texture(path, lines, width=440, side="left"):
    """Columna de registro del kernel (texto real), con desvanecido vertical."""
    txt = "\n".join(lines)
    tmp = path + ".raw.png"
    run(["magick", "-background", "none", "-font", F_MONO, "-pointsize", "19",
         "-interline-spacing", "9", "-fill", GRIS, f"label:{txt}", f"PNG32:{tmp}"])
    h = int(subprocess.run(["magick", "identify", "-format", "%h", tmp],
                           capture_output=True, text=True).stdout)
    w = int(subprocess.run(["magick", "identify", "-format", "%w", tmp],
                           capture_output=True, text=True).stdout)
    # máscara: transparente arriba y abajo, opaca al centro
    run(["magick", tmp, "(", "-size", f"{w}x{h}", "gradient:black-white",
         "(", "-size", f"{w}x{h}", "gradient:white-black", ")", "-compose", "multiply", "-composite",
         "-level", "0,50%", ")", "-alpha", "off", "-compose", "CopyOpacity", "-composite",
         f"PNG32:{path}"])
    # combinar con el alfa original del texto
    run(["magick", tmp, path, "-compose", "DstIn", "-composite", f"PNG32:{path}"])
    os.remove(tmp)
    # recorte lateral (inicio de las líneas) con desvanecido hacia el centro
    grad = "gradient:white-black" if side == "left" else "gradient:black-white"
    run(["magick", path, "-crop", f"{width}x{h}+0+0", "+repage",
         "(", "-size", f"{h}x{width}", grad, "-rotate", "-90", "-level", "0,60%",
         "-alpha", "copy", ")", "-compose", "DstIn", "-composite", f"PNG32:{path}"])


def logo_round(path, d):
    run(["magick", LOGO, "-resize", f"{d}x{d}^", "-gravity", "center", "-extent", f"{d}x{d}",
         "(", "-size", f"{d}x{d}", "xc:none", "-fill", "white",
         "-draw", f"circle {d / 2},{d / 2} {d / 2},1", ")",
         "-compose", "CopyOpacity", "-composite", f"PNG32:{path}"])


def icon_strip(path, color=GRIS):
    """Fila de iconos Lucide con su etiqueta técnica en JetBrains Mono."""
    cells = []
    for name, label in ICONS:
        svg = os.path.join(OUT, f"ico_{name}.svg")
        png = os.path.join(OUT, f"ico_{name}.png")
        with open(svg, "w") as f:
            f.write(lucide_svg(name, color, 1.5, 56))
        run(["rsvg-convert", "-w", "56", "-h", "56", "-o", png, svg])
        lab = os.path.join(OUT, f"lab_{name}.png")
        text_png(lab, label, F_MONO, 22, color, 1)
        cell = os.path.join(OUT, f"cell_{name}.png")
        run(["magick", png, "(", "-size", "1x18", "xc:none", ")", lab,
             "-background", "none", "-gravity", "center", "-append",
             "-gravity", "center", "-extent", "260x110", f"PNG32:{cell}"])
        cells.append(cell)
    run(["magick", *cells, "-background", "none", "+append", f"PNG32:{path}"])


def lockup(path):
    """Logotipo circular + «SereOS» + lema, alineados en una sola línea."""
    lg = os.path.join(OUT, "lk_logo.png")
    logo_round(lg, 76)
    name = os.path.join(OUT, "lk_name.png")
    text_png(name, "SereOS", F_DISPLAY, 56, TXT)
    tag = os.path.join(OUT, "lk_tag.png")
    text_png(tag, "—  Ingeniería desde los fundamentos.", F_TEXT, 40, GRIS)
    run(["magick", lg, "(", "-size", "26x1", "xc:none", ")", name,
         "(", "-size", "22x1", "xc:none", ")", tag,
         "-background", "none", "-gravity", "center", "+append", f"PNG32:{path}"])


def accent_rule(path, w=160):
    run(["magick", "-size", f"{w}x3", f"xc:{ACENTO}", f"PNG32:{path}"])


def main():
    os.makedirs(OUT, exist_ok=True)
    background(os.path.join(OUT, "fondo_intro.png"), 470)
    background(os.path.join(OUT, "fondo_outro.png"), 470)
    log = [l.rstrip() for l in open(SERIAL, errors="ignore") if l.strip()]
    ok = [l for l in log if l.startswith("[OK]")] + [l for l in log if l.isupper() and "_" in l]
    half = len(ok) // 2 + 1
    log_texture(os.path.join(OUT, "log_izq.png"), ok[:half], side="left")
    log_texture(os.path.join(OUT, "log_der.png"), ok[half - 4:], side="right")
    logo_round(os.path.join(OUT, "logo_intro.png"), 132)
    text_png(os.path.join(OUT, "wordmark.png"), "SereOS", F_DISPLAY, 230, TXT, -3)
    text_png(os.path.join(OUT, "subtitulo.png"), "PROYECTO FINAL  —  SISTEMAS OPERATIVOS",
             F_MONO, 30, GRIS, 6)
    accent_rule(os.path.join(OUT, "regla.png"))
    icon_strip(os.path.join(OUT, "iconos.png"))
    text_png(os.path.join(OUT, "gracias.png"), "Gracias por acompañarnos", F_DISPLAY, 124, TXT, -1)
    lockup(os.path.join(OUT, "lockup.png"))
    text_png(os.path.join(OUT, "firma.png"), "PROYECTO FINAL  —  SISTEMAS OPERATIVOS",
             F_MONO, 22, "#5d6577", 5)
    print("marca lista en", OUT)


if __name__ == "__main__":
    main()
