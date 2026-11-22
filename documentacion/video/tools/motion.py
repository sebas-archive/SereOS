"""Apertura y cierre de SereOS con un lenguaje de animación común.

Lenguaje de movimiento (idéntico en ambas secuencias):
  - curva ease-out cúbica en todas las entradas;
  - el título principal aparece con un barrido de máscara suave (izquierda a
    derecha) y una subida de 18 px;
  - textos secundarios: fundido + subida corta; la línea de acento crece desde
    el centro;
  - textura de registro real del kernel con deriva vertical muy lenta;
  - acercamiento global del 2,5 % durante toda la escena (empuje de cámara);
  - las transiciones hacia/desde el contenido son fundidos cruzados (build.py).
"""
import os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
MARCA = os.path.join(VIDEO, "recursos", "marca")
BUILD = os.path.join(VIDEO, "build")
W, H, FPS = 1920, 1080, 30
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
       "-profile:v", "high", "-level", "4.2", "-movflags", "+faststart", "-r", str(FPS)]
ICONS = ["cpu", "memory-stick", "keyboard", "monitor", "square-terminal"]


def size(name):
    out = subprocess.run(["magick", "identify", "-format", "%w %h", os.path.join(MARCA, name)],
                         capture_output=True, text=True, check=True).stdout.split()
    return int(out[0]), int(out[1])


def ease(st, d):
    return f"(1-pow(1-clip((t-{st})/{d},0,1),3))"


class Scene:
    def __init__(self, dur, background):
        self.dur = dur
        self.inputs = []
        self.fc = []
        self.n = 0
        bg = self.add(background)
        self.fc.append(f"[{bg}:v]format=rgba[base]")
        self.last = "base"

    def add(self, name):
        self.inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{self.dur}",
                        "-i", os.path.join(MARCA, name)]
        i = self.n
        self.n += 1
        return i

    def _over(self, src, x, y, st):
        lab = f"o{len(self.fc)}"
        self.fc.append(f"[{self.last}][{src}]overlay=x='{x}':y='{y}':eval=frame:"
                       f"enable='gte(t,{st})'[{lab}]")
        self.last = lab

    def texture(self, name, x, y, st, opacity, drift=-26):
        """Columna de registro real: fundido a baja opacidad y deriva lenta."""
        i = self.add(name)
        lab = f"tx{i}"
        self.fc.append(f"[{i}:v]format=rgba,colorchannelmixer=aa={opacity},"
                       f"fade=t=in:st={st}:d=1.8:alpha=1[{lab}]")
        self._over(lab, x, f"{y}+{drift}*t/{self.dur}", st)

    def reveal(self, name, y, st, d=0.8, rise=14, x=None, alpha=1.0):
        """Fundido + subida con ease-out."""
        i = self.add(name)
        w, _ = size(name)
        lab = f"rv{i}"
        mix = f",colorchannelmixer=aa={alpha}" if alpha < 1 else ""
        self.fc.append(f"[{i}:v]format=rgba{mix},fade=t=in:st={st}:d={d}:alpha=1[{lab}]")
        xx = x if x is not None else (W - w) // 2
        self._over(lab, xx, f"{y}+(1-{ease(st, d)})*{rise}", st)

    def wipe(self, name, y, st, d=1.3, rise=18, edge=140):
        """Barrido de máscara suave (izquierda a derecha) + subida."""
        i = self.add(name)
        w, _ = size(name)
        lab = f"wp{i}"
        p = f"(1-pow(1-clip((T-{st})/{d},0,1),3))"
        self.fc.append(f"[{i}:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
                       f"a='alpha(X,Y)*clip((({w}+{edge})*{p}-X)/{edge},0,1)'[{lab}]")
        self._over(lab, (W - w) // 2, f"{y}+(1-{ease(st, d)})*{rise}", st)

    def logo(self, name, cy, st, d=1.0):
        """Logotipo: escala 0,92 -> 1 con ease-out y fundido."""
        i = self.add(name)
        lab = f"lg{i}"
        s = f"(0.92+0.08*{ease(st, d)})"
        self.fc.append(f"[{i}:v]format=rgba,fade=t=in:st={st}:d={d}:alpha=1,"
                       f"scale=w='iw*{s}':h='ih*{s}':eval=frame[{lab}]")
        self._over(lab, f"{W // 2}-w/2", f"{cy}-h/2", st)

    def rule(self, name, y, st, d=0.7, full=160):
        """Línea de acento que crece desde el centro."""
        i = self.add(name)
        lab = f"rl{i}"
        self.fc.append(f"[{i}:v]format=rgba,scale=w='max(2,{full}*{ease(st, d)})':h=3:eval=frame[{lab}]")
        self._over(lab, f"{W // 2}-w/2", y, st)

    def render(self, out, fade_in=None, fade_out=None, push=0.025):
        tail = (f"[{self.last}]scale=w='{W}*(1+{push}*t/{self.dur})':h='{H}*(1+{push}*t/{self.dur})':"
                f"eval=frame,crop={W}:{H}:(iw-{W})/2:(ih-{H})/2")
        if fade_in:
            tail += f",fade=t=in:st=0:d={fade_in}"
        if fade_out:
            tail += f",fade=t=out:st={self.dur - fade_out:.2f}:d={fade_out}"
        tail += ",format=yuv420p[v]"
        self.fc.append(tail)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *self.inputs,
                        "-filter_complex", ";".join(self.fc), "-map", "[v]",
                        "-t", f"{self.dur}", *ENC, "-an", out], check=True)
        return out


def intro(out, dur=12.0):
    """Apertura: el nombre SereOS como protagonista, subtítulo jerárquico y
    los cinco pilares técnicos del proyecto con iconos Lucide."""
    s = Scene(dur, "fondo_intro.png")
    s.texture("log_izq.png", 70, 250, 0.5, 0.16)
    s.texture("log_der.png", 1410, 220, 0.9, 0.16)
    s.logo("logo_intro.png", 256, 0.7, 1.0)
    s.wipe("wordmark.png", 330, 1.3, 1.4)
    s.rule("regla.png", 655, 2.6)
    s.reveal("subtitulo.png", 690, 2.9, 0.9, 12)
    for k, name in enumerate(ICONS):
        s.reveal(f"cell_{name}.png", 860, 3.7 + 0.14 * k, 0.8, 16, x=310 + 260 * k, alpha=0.85)
    return s.render(out, fade_in=1.2)


def outro(out, dur=10.0):
    """Cierre: agradecimiento protagonista, la marca SereOS con su lema y
    salida suave a negro."""
    s = Scene(dur, "fondo_outro.png")
    s.texture("log_izq.png", 70, 250, 0.0, 0.12)
    s.texture("log_der.png", 1410, 220, 0.3, 0.12)
    s.wipe("gracias.png", 370, 1.0, 1.4)
    s.rule("regla.png", 580, 2.3)
    s.reveal("lockup.png", 640, 2.7, 0.9, 12)
    s.reveal("firma.png", 960, 3.5, 1.0, 8)
    return s.render(out, fade_out=2.4)


if __name__ == "__main__":
    os.makedirs(BUILD, exist_ok=True)
    print(intro(os.path.join(BUILD, "s0_intro.mp4")))
    print(outro(os.path.join(BUILD, "s9_outro.mp4")))
