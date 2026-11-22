"""Montaje del video final de SereOS a partir de la grabación real.

Pasos:
 1. Clips de grabación real (fotogramas PPM de QEMU con sus marcas de tiempo),
    enmarcados en 16:9 con fondo difuminado y zoom digital suave donde aporta.
 2. Escenas de portada, arquitectura (diagramas) y cierre.
 3. Concatenación en H.264 1920x1080 30 fps.
 4. Cápsulas flotantes (estilo Dynamic Island) con animación de entrada/salida.
 5. Música original sintetizada + efectos de sonido, mezcla en AAC estéreo.
 6. Exporta SRT con los mismos tiempos.
"""
import bisect, json, os, subprocess, sys
import assets
import motion

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
BUILD = os.path.join(VIDEO, "build")
DIAG = os.path.join(VIDEO, "diagramas")
REC = os.path.join(VIDEO, "recursos")
AUDIO = os.path.join(VIDEO, "audio")
OUT = os.path.join(VIDEO, "Presentacion_Final_SereOS.mp4")
SRT = os.path.join(VIDEO, "Presentacion_Final_SereOS.srt")
W, H, FPS = 1920, 1080, 30
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
       "-profile:v", "high", "-level", "4.2", "-movflags", "+faststart", "-r", str(FPS)]

M = json.load(open(os.path.join(HERE, "markers.json")))
FRAMES = [(float(a), p.strip()) for a, p in (l.split("\t") for l in open(os.path.join(HERE, "frames_index.txt")))]
TS = [t for t, _ in FRAMES]


def ff(args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True).stdout
    return float(out.strip())


def raw_clip(name, t0, t1, zoom=1.0, speed=1.0, fade_in=True, fade_out=True):
    """Clip de grabación real entre los tiempos t0 y t1 (segundos de la captura)."""
    i0 = bisect.bisect_left(TS, t0)
    i1 = bisect.bisect_left(TS, t1)
    sel = FRAMES[i0:i1]
    lst = os.path.join(BUILD, name + ".txt")
    with open(lst, "w") as f:
        for k, (t, p) in enumerate(sel):
            nxt = sel[k + 1][0] if k + 1 < len(sel) else t + 0.04
            d = min(max(nxt - t, 0.02), 0.5)
            f.write(f"file '{p}'\nduration {d:.4f}\n")
        f.write(f"file '{sel[-1][1]}'\n")
    out = os.path.join(BUILD, name + ".mp4")
    if os.path.exists(out) and os.path.getsize(out) > 0 and not os.environ.get("REBUILD"):
        return out
    dur = t1 - t0
    # fondo: el mismo fotograma difuminado; primer plano: 1440x1080 con zoom digital suave
    dd = max(dur, 0.1)
    if zoom != 1.0:
        zw = f"1440*(1+{zoom - 1:.4f}*min(t,{dd:.3f})/{dd:.3f})"
        zh = f"1080*(1+{zoom - 1:.4f}*min(t,{dd:.3f})/{dd:.3f})"
    else:
        zw, zh = "1440", "1080"
    vf = (f"[0:v]split=2[a][b];"
          f"[a]scale={W}:{H},boxblur=40:3,eq=brightness=-0.42:saturation=0.85[bg];"
          f"[b]scale=w='{zw}':h='{zh}':eval=frame,"
          f"crop=1440:1080:(iw-1440)/2:(ih-1080)/2[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setpts=PTS/{speed},fps={FPS},format=yuv420p,"
          + (f"fade=t=in:st=0:d=0.5," if fade_in else "")
          + (f"fade=t=out:st={max(dur / speed - 0.5, 0):.3f}:d=0.5" if fade_out else "null")
          + "[v]")
    ff(["-f", "concat", "-safe", "0", "-i", lst, "-filter_complex", vf, "-map", "[v]",
        *ENC, "-an", out])
    return out


def still_clip(name, image, dur, zoom_to=1.04, fade=0.6):
    """Imagen fija con movimiento lento (Ken Burns) y fundidos."""
    out = os.path.join(BUILD, name + ".mp4")
    if os.path.exists(out) and os.path.getsize(out) > 0 and not os.environ.get("REBUILD"):
        return out
    n = int(dur * FPS)
    vf = (f"scale=8000:-1,zoompan=z='1+{zoom_to - 1:.4f}*on/{n}':x='iw/2-(iw/zoom/2)':"
          f"y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},format=yuv420p,"
          f"fade=t=in:st=0:d={fade},fade=t=out:st={dur - fade:.3f}:d={fade}")
    ff(["-loop", "1", "-i", image, "-vf", vf, "-t", f"{dur}", *ENC, "-an", out])
    return out


def animated_scene(out, base, rings, ring_cy, items, sweep, dur):
    """Escena de motion graphics:
    - fondo con fundido; anillos que se expanden y respiran alrededor del logotipo;
    - logotipo con escalado de entrada y respiración suave;
    - textos con deslizamiento vertical y fundido escalonados;
    - barrido de luz diagonal; salida con fundido a negro.
    items: dict(path, cx_or_none, y, enter, dur, slide, kind['text'|'logo'])."""
    S_RING = "(0.55+0.45*(1-pow(1-min(1,t/2.4),3)))"
    inputs = ["-loop", "1", "-i", base, "-loop", "1", "-i", rings]
    fc = [f"[0:v]scale={W}:{H},format=rgba,fade=t=in:st=0:d=1.2:alpha=1[bg0]",
          f"[1:v]format=rgba,fade=t=in:st=0.2:d=1.6:alpha=1,"
          f"scale=w='iw*{S_RING}':h='ih*{S_RING}':eval=frame[rg]",
          f"[bg0][rg]overlay=x='{W//2}-{W//2}*{S_RING}':y='{ring_cy}-{ring_cy}*{S_RING}':eval=frame[bg1]"]
    last = "bg1"
    idx = 2
    for k, it in enumerate(items):
        inputs += ["-loop", "1", "-i", it["path"]]
        st, d = it["enter"], it["dur"]
        prog = f"min(1,max(0,(t-{st})/{d}))"
        ease = f"(1-pow(1-{prog},3))"
        if it["kind"] == "logo":
            S_L = f"(0.6+0.4*{ease})*(1+0.012*sin(t*2.1))"
            fc.append(f"[{idx}:v]format=rgba,fade=t=in:st={st}:d={d}:alpha=1,"
                      f"scale=w='iw*{S_L}':h='ih*{S_L}':eval=frame[i{k}]")
            fc.append(f"[{last}][i{k}]overlay=x='{it['cx']}-w/2':y='{it['cy']}-h/2':eval=frame:"
                      f"enable='gte(t,{st})'[o{k}]")
        else:
            y = f"{it['y']}+(1-{ease})*{it['slide']}"
            fc.append(f"[{idx}:v]format=rgba,fade=t=in:st={st}:d={d}:alpha=1[i{k}]")
            fc.append(f"[{last}][i{k}]overlay=x=(W-w)/2:y='{y}':eval=frame:"
                      f"enable='gte(t,{st})'[o{k}]")
        last = f"o{k}"
        idx += 1
    # barrido de luz opcional (desactivado: las bandas resultaban duras)
    if sweep:
        inputs += ["-loop", "1", "-i", sweep["path"]]
        A, B = sweep["start"], sweep["len"]
        fc.append(f"[{idx}:v]format=rgba,colorchannelmixer=aa=0.13[sw]")
        fc.append(f"[{last}][sw]overlay=x='-420+(t-{A})*({W}+420)/{B}':y=0:eval=frame:"
                  f"enable='between(t,{A},{A + B})'[ws]")
        last = "ws"
    fc.append(f"[{last}]fade=t=out:st={dur - 1.2:.2f}:d=1.2,format=yuv420p[v]")
    ff([*inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-t", f"{dur}", *ENC, "-an", out])
    return out


def cover_clip(dur=12.0):
    out = os.path.join(BUILD, "s0_portada.mp4")
    if os.path.exists(out) and os.path.getsize(out) > 0 and not os.environ.get("REBUILD"):
        return out
    R = REC + "/"
    items = [
        dict(path=R + "portada_logo.png", kind="logo", cx=960, cy=280, enter=0.5, dur=1.4),
        dict(path=R + "portada_t1.png", kind="text", y=500, enter=1.5, dur=0.9, slide=34),
        dict(path=R + "portada_t2.png", kind="text", y=548, enter=1.8, dur=0.9, slide=34),
        dict(path=R + "portada_t3.png", kind="text", y=618, enter=2.3, dur=1.4, slide=60),
        dict(path=R + "portada_linea.png", kind="text", y=902, enter=3.6, dur=0.9, slide=0),
    ]
    sweep = None
    return animated_scene(out, R + "portada_fondo_base.png", R + "portada_fondo_rings.png", 280,
                          items, sweep, dur)


def closing_clip(dur=9.0):
    out = os.path.join(BUILD, "s9_cierre.mp4")
    if os.path.exists(out) and os.path.getsize(out) > 0 and not os.environ.get("REBUILD"):
        return out
    R = REC + "/"
    items = [
        dict(path=R + "cierre_logo.png", kind="logo", cx=960, cy=235, enter=0.2, dur=1.2),
        dict(path=R + "cierre_gracias.png", kind="text", y=330, enter=0.9, dur=1.2, slide=70),
        dict(path=R + "cierre_sereos.png", kind="text", y=620, enter=2.1, dur=0.9, slide=24),
        dict(path=R + "cierre_proyecto.png", kind="text", y=700, enter=2.6, dur=0.9, slide=18),
    ]
    sweep = None
    return animated_scene(out, R + "cierre_fondo_base.png", R + "cierre_fondo_rings.png", 235,
                          items, sweep, dur)


def xfade_pair(a, b, d, out):
    """Fundido cruzado suave entre dos clips (mismo formato)."""
    off = duration(a) - d
    ff(["-i", a, "-i", b, "-filter_complex",
        f"[0:v]settb=AVTB,fps={FPS},format=yuv420p[a];[1:v]settb=AVTB,fps={FPS},format=yuv420p[b];"
        f"[a][b]xfade=transition=fade:duration={d}:offset={off:.3f},format=yuv420p[v]",
        "-map", "[v]", *ENC, "-an", out])
    return out


def concat_video(parts, out):
    lst = os.path.join(BUILD, "concat_all.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    ff(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
    return out


def capsule_png(i, text):
    path = os.path.join(BUILD, f"pill_{i:02d}.png")
    assets.capsule(path, text, font_size=40)
    return path


# subtítulos anclados a marcas de la grabación:
#   (marca, desplazamiento_s, duración_s, texto)
RAW_SUBS = {
    "s1_grub": [
        ("grub_menu", 0.3, 3.0, "Iniciando SereOS con GRUB 2 (Multiboot)."),
        ("grub_enter", 0.7, 3.4, "Kernel: GDT, IDT, PIC, PIT y paginación."),
    ],
    "s2_escritorio": [
        ("escritorio_inicio", 0.8, 3.8, "Escritorio de SereOS: barra superior, dock y cursor."),
        ("escritorio_inicio", 7.0, 4.0, "Dock: archivos, terminal, monitor, juego e información."),
        ("lanzador_abierto", 0.6, 3.6, "Lanzador ≡: acceso a todas las aplicaciones."),
    ],
    "s3_apps": [
        ("archivos_abierto", 0.8, 3.8, "Explorador de archivos sobre el sistema RAMFS."),
        ("archivos_maximizado", -1.2, 3.4, "Doble clic en la barra de título: maximizar."),
        ("monitor_abierto", 0.4, 4.2, "Monitor del sistema: memoria, heap y tareas en vivo."),
        ("monitor_maximizado", -0.4, 3.0, "Ventanas maximizables y restaurables."),
    ],
    "s5_terminal": [
        ("terminal_abierta", 0.6, 3.6, "Terminal de SereOS: shell con comandos del kernel."),
        ("cmd_help", -2.0, 3.6, "help: lista de comandos disponibles."),
        ("cmd_sysinfo", -2.4, 3.8, "sysinfo: sistema, kernel y memoria detectada."),
        ("cmd_mem", -1.6, 3.0, "mem y ticks: memoria física y tiempo del PIT."),
        ("cmd_dmesg", -3.0, 4.0, "dmesg: registro del kernel con marcas de tiempo."),
    ],
    "s6_pacman": [
        ("pacman_abierto", 0.8, 4.0, "PAC-MAN SereOS: un videojuego integrado en el sistema."),
        ("pacman_partida", 0.4, 3.6, "Laberinto, puntos, fantasmas y vidas."),
        ("pacman_fin_ruta", -4.5, 3.8, "Fantasmas asustados: se pueden capturar."),
        ("pacman_fin_ruta", 3.0, 3.0, "Pausa y menú dentro del propio escritorio."),
        ("acerca_abierto", 0.5, 3.8, "Acerca de: 14 de 14 componentes verificados."),
    ],
}
DIAG_SUBS = {
    "s4_0_d1_capas": [(0.8, 4.0, "Seis capas: cada una usa la inferior.")],
    "s4_1_d2_arranque": [(0.8, 4.0, "Arranque: GRUB, boot.s y kernel_main.")],
    "s4_2_d3_interrupciones": [(0.8, 4.2, "Interrupciones: PIC remapeado a 32–47 y PIT a 100 Hz.")],
    "s4_3_d4_memoria": [(0.8, 4.2, "Memoria PSE hasta 512 MiB y planificador cooperativo.")],
}


def main():
    os.makedirs(BUILD, exist_ok=True)
    g = M
    raw_t0 = {
        "s1_grub": 0.0,
        "s2_escritorio": g["escritorio_inicio"] + 0.5,
        "s3_apps": g["lanzador_abierto"] + 0.5,
        "s5_terminal": g["terminal_abierta"] - 0.2,
        "s6_pacman": g["pacman_abierto"] - 0.3,
    }
    # 0-7: segmentos en orden; (nombre, ruta_clip)
    segs = []
    intro_p = os.path.join(BUILD, "s0_intro.mp4")
    if not os.path.exists(intro_p) or os.environ.get("REBUILD"):
        motion.intro(intro_p)
    segs.append(("s0_portada", intro_p))
    segs.append(("s1_grub", raw_clip("s1_grub", 0.0, g["escritorio_inicio"] + 0.5, zoom=1.10, fade_in=False)))
    segs.append(("s2_escritorio", raw_clip("s2_escritorio", raw_t0["s2_escritorio"], g["lanzador_abierto"] + 0.5)))
    segs.append(("s3_apps", raw_clip("s3_apps", raw_t0["s3_apps"], g["terminal_abierta"] - 0.2)))
    for i, name in enumerate(("d1_capas", "d2_arranque", "d3_interrupciones", "d4_memoria")):
        key = f"s4_{i}_{name}"
        segs.append((key, still_clip(key, os.path.join(DIAG, name + ".png"), 9.0)))
    segs.append(("s5_terminal", raw_clip("s5_terminal", raw_t0["s5_terminal"], g["pacman_abierto"] - 0.3, zoom=1.14)))
    segs.append(("s6_pacman", raw_clip("s6_pacman", raw_t0["s6_pacman"], g["fin_grabacion"], fade_out=False)))
    outro_p = os.path.join(BUILD, "s9_outro.mp4")
    if not os.path.exists(outro_p) or os.environ.get("REBUILD"):
        motion.outro(outro_p)
    segs.append(("s9_cierre", outro_p))

    # fundidos cruzados: apertura -> GRUB y PAC-MAN -> cierre
    XF = {"s1_grub": 1.0, "s9_cierre": 1.2}
    starts, acc = {}, 0.0
    for name, p in segs:
        acc -= XF.get(name, 0.0)
        starts[name] = acc
        acc += duration(p)
    d = dict(segs)
    a = xfade_pair(d["s0_portada"], d["s1_grub"], XF["s1_grub"], os.path.join(BUILD, "x_intro_grub.mp4"))
    b = xfade_pair(d["s6_pacman"], d["s9_cierre"], XF["s9_cierre"], os.path.join(BUILD, "x_pacman_cierre.mp4"))
    order = [a] + [p for n, p in segs if n not in ("s0_portada", "s1_grub", "s6_pacman", "s9_cierre")] + [b]
    video_only = concat_video(order, os.path.join(BUILD, "video_sin_audio.mp4"))
    total = duration(video_only)
    print("video base:", round(total, 2), "s (esperado", round(acc, 2), ")", flush=True)

    # subtítulos: (inicio_global, duracion, texto)
    subs = []
    for name, items in RAW_SUBS.items():
        for mark, off, dur, text in items:
            t_mark = g[mark] - raw_t0[name]
            subs.append((starts[name] + t_mark + off, dur, text))
    for name, items in DIAG_SUBS.items():
        for off, dur, text in items:
            subs.append((starts[name] + off, dur, text))
    subs.sort()
    # sin solapes: cada cápsula dura hasta el inicio de la siguiente como máximo
    for k in range(len(subs) - 1):
        s0, d0, tx = subs[k]
        if s0 + d0 > subs[k + 1][0] - 0.2:
            subs[k] = (s0, subs[k + 1][0] - 0.2 - s0, tx)

    write_srt(subs)
    pills = [capsule_png(i, t) for i, (_, _, t) in enumerate(subs)]

    # música original del total exacto + efectos de sonido
    import music
    music.main_for(total)
    sfx = []
    for name in ("s0_portada", "s1_grub", "s2_escritorio", "s3_apps", "s5_terminal", "s6_pacman", "s9_cierre"):
        sfx.append((starts[name], "sfx_whoosh.wav", 0.35))
    sfx.append((1.4, "sfx_chime.wav", 0.35))
    sfx.append((starts["s9_cierre"] + 1.0, "sfx_chime_alto.wav", 0.35))
    for mark in ("lanzador_abierto", "archivos_maximizado", "terminal_abierta"):
        sfx.append((starts["s2_escritorio"] + g[mark] - raw_t0["s2_escritorio"] if mark == "lanzador_abierto" else
                    starts["s3_apps"] + g[mark] - raw_t0["s3_apps"] if mark == "archivos_maximizado" else
                    starts["s5_terminal"] + 0.2, "sfx_click.wav", 0.6))
    sfx.append((starts["s6_pacman"] + g["pacman_partida"] - raw_t0["s6_pacman"], "sfx_chime_alto.wav", 0.4))

    compose(video_only, pills, subs, sfx, total)
    return


def write_srt(subs):
    def ts(x):
        h, rem = divmod(max(x, 0), 3600)
        m, sec = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{sec:06.3f}".replace(".", ",")
    with open(SRT, "w", encoding="utf-8") as f:
        for i, (s0, d, tx) in enumerate(subs, 1):
            f.write(f"{i}\n{ts(s0)} --> {ts(s0 + d)}\n{tx}\n\n")
    print("SRT:", SRT, len(subs), "subtítulos", flush=True)


def compose(video, pills, subs, sfx, total):
    args = ["-i", video, "-i", os.path.join(AUDIO, "musica_base.wav")]
    for p in pills:
        args += ["-loop", "1", "-i", p]
    for _, f, _ in sfx:
        args += ["-i", os.path.join(AUDIO, f)]
    fc = []
    # cápsulas flotantes: aparecen con deslizamiento vertical y fundido
    last = "0:v"
    for k, (s0, d, _) in enumerate(subs):
        idx = k + 2
        fc.append(f"[{idx}:v]format=rgba,fade=t=in:st=0:d=0.45:alpha=1,"
                  f"fade=t=out:st={max(d - 0.45, 0):.3f}:d=0.45:alpha=1,setpts=PTS+{s0:.3f}/TB[p{k}]")
        out = f"v{k}"
        fc.append(f"[{last}][p{k}]overlay=x=(W-w)/2:"
                  f"y='H-215+max(0,(0.45-(t-{s0:.3f}))/0.45)*40':eval=frame:"
                  f"enable='between(t,{s0:.3f},{s0 + d:.3f})'[{out}]")
        last = out
    # audio: música (-18 dB aprox.) + efectos
    base = 2 + len(pills)
    fc.append(f"[1:a]volume=0.55,atrim=0:{total:.3f}[m]")
    labels = ["[m]"]
    for j, (t, _, vol) in enumerate(sfx):
        idx = base + j
        ms = int(t * 1000)
        fc.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={vol},adelay={ms}|{ms}[s{j}]")
        labels.append(f"[s{j}]")
    fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0,"
              f"loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args,
           "-filter_complex", ";".join(fc),
           "-map", f"[{last}]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-level", "4.2", "-r", str(FPS), "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", "-t", f"{total:.3f}", OUT]
    subprocess.run(cmd, check=True)
    print("MP4:", OUT, flush=True)


if __name__ == "__main__":
    main()
