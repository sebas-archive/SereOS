#!/usr/bin/env python3
"""gen_audio.py - sintetizador de efectos de sonido ORIGINALES para SereOS.

Genera audio/sfx_data.c y audio/sfx_data.h con PCM 8 bits sin signo, mono,
11025 Hz (formato nativo del Sound Blaster 16 en modo 8-bit single-cycle).

Todos los efectos son sintetizados desde cero con osciladores square/triangle/
saw/sine, barridos de frecuencia, vibrato, envolventes y ruido determinista.
NO se usa ni se redistribuye ningun WAV de terceros (los WAV de referencia de
Paku-Paku solo inspiraron el estilo arcade, nunca se copiaron muestras).

Uso: python3 tools/gen_audio.py   (desde cualquier directorio)
"""
import math
import os

RATE = 11025
TARGET_PEAK = 0.72
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio")


class Rng:
    """xorshift32 determinista: el ruido es reproducible entre builds."""

    def __init__(self, seed):
        self.s = seed & 0xFFFFFFFF or 1

    def next(self):
        x = self.s
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.s = x & 0xFFFFFFFF
        return (self.s / 0xFFFFFFFF) * 2.0 - 1.0


def buf_for(duration):
    return [0.0] * int(round(duration * RATE))


def add_voice(buf, t0, t1, f0, f1, amp=0.5, wave="square", duty=0.5,
              attack=0.004, release=0.012, decay=0.0,
              vib_hz=0.0, vib_depth=0.0, noise=0.0, rng=None):
    """Suma una voz con barrido lineal de frecuencia f0->f1 en [t0,t1] s."""
    n0 = max(0, int(t0 * RATE))
    n1 = min(len(buf), int(t1 * RATE))
    if n1 <= n0:
        return
    span = n1 - n0
    ta = max(1, int(attack * RATE))
    tr = max(1, int(release * RATE))
    phase = 0.0
    for n in range(n0, n1):
        u = (n - n0) / max(1, span - 1)
        f = f0 + (f1 - f0) * u
        if vib_hz > 0.0:
            f *= 1.0 + vib_depth * math.sin(2.0 * math.pi * vib_hz * (n - n0) / RATE)
        phase += f / RATE
        phase -= math.floor(phase)
        if wave == "square":
            v = 1.0 if phase < duty else -1.0
        elif wave == "triangle":
            v = 4.0 * abs(phase - 0.5) - 1.0
        elif wave == "saw":
            v = 2.0 * phase - 1.0
        else:
            v = math.sin(2.0 * math.pi * phase)
        env = 1.0
        if n - n0 < ta:
            env *= (n - n0) / ta
        rem = n1 - 1 - n
        if rem < tr:
            env *= rem / tr
        if decay > 0.0:
            env *= math.exp(-decay * (n - n0) / RATE)
        sample = v * amp * env
        if noise > 0.0 and rng is not None:
            sample = sample * (1.0 - noise) + rng.next() * noise * amp * env
        buf[n] += sample


def add_notes(buf, notes, amp=0.5, **kw):
    for (t0, t1, f0, f1) in notes:
        add_voice(buf, t0, t1, f0, f1, amp=amp, **kw)


def fade_edges(buf, ms=5.0):
    n = max(1, int(RATE * ms / 1000.0))
    if len(buf) <= 2 * n:
        return
    for i in range(n):
        k = i / n
        buf[i] *= k
        buf[-1 - i] *= k


def normalize(buf, peak=TARGET_PEAK):
    m = max((abs(x) for x in buf), default=0.0)
    if m < 1e-9:
        return
    gain = peak / m
    for i in range(len(buf)):
        v = buf[i] * gain
        buf[i] = max(-1.0, min(1.0, v))


def to_pcm_u8(buf):
    out = []
    for x in buf:
        v = int(round(128.0 + x * 127.0))
        out.append(0 if v < 0 else (255 if v > 255 else v))
    return bytes(out)


# --------------------------------------------------------------------------
# Diseno de los efectos (todos originales, estilo arcade 16-bit)
# --------------------------------------------------------------------------
def make_menu():
    b = buf_for(0.24)
    add_notes(b, [(0.00, 0.09, 784.0, 784.0),
                  (0.08, 0.23, 1046.5, 1046.5)], amp=0.45, duty=0.5)
    add_voice(b, 0.08, 0.23, 2093.0, 2093.0, amp=0.08, wave="sine")
    return b


def make_start():
    b = buf_for(0.90)
    add_notes(b, [(0.00, 0.16, 523.25, 523.25),
                  (0.15, 0.31, 659.25, 659.25),
                  (0.30, 0.46, 783.99, 783.99),
                  (0.45, 0.62, 1046.5, 1046.5),
                  (0.62, 0.90, 783.99, 1046.5)], amp=0.42, duty=0.45)
    add_voice(b, 0.00, 0.46, 261.6, 392.0, amp=0.12, wave="triangle")
    add_voice(b, 0.45, 0.90, 523.25, 523.25, amp=0.10, wave="sine")
    return b


def make_waka1():
    b = buf_for(0.11)
    add_voice(b, 0.0, 0.11, 470.0, 210.0, amp=0.62, duty=0.28,
              attack=0.003, release=0.02)
    add_voice(b, 0.0, 0.11, 940.0, 420.0, amp=0.10, wave="sine")
    return b


def make_waka2():
    b = buf_for(0.11)
    add_voice(b, 0.0, 0.11, 210.0, 470.0, amp=0.62, duty=0.28,
              attack=0.003, release=0.02)
    add_voice(b, 0.0, 0.11, 420.0, 940.0, amp=0.10, wave="sine")
    return b


def make_power():
    b = buf_for(0.48)
    add_notes(b, [(0.00, 0.08, 261.6, 261.6),
                  (0.07, 0.15, 329.6, 329.6),
                  (0.14, 0.22, 392.0, 392.0),
                  (0.21, 0.30, 523.25, 523.25),
                  (0.29, 0.48, 659.25, 880.0)], amp=0.44, duty=0.5,
              vib_hz=11.0, vib_depth=0.02)
    add_voice(b, 0.29, 0.48, 1318.5, 1760.0, amp=0.10, wave="triangle")
    return b


def make_eat_ghost():
    b = buf_for(0.30)
    rng = Rng(0x9E3779B9)
    add_notes(b, [(0.00, 0.065, 659.25, 659.25),
                  (0.06, 0.125, 523.25, 523.25),
                  (0.12, 0.185, 392.0, 392.0),
                  (0.18, 0.30, 294.0, 220.0)], amp=0.5, duty=0.5,
              noise=0.05, rng=rng)
    return b


def make_eat_fruit():
    b = buf_for(0.34)
    add_notes(b, [(0.00, 0.08, 880.0, 880.0),
                  (0.07, 0.15, 1318.5, 1318.5),
                  (0.14, 0.22, 1046.5, 1046.5),
                  (0.21, 0.34, 1568.0, 2093.0)], amp=0.42, duty=0.35)
    return b


def make_death():
    b = buf_for(1.34)
    rng = Rng(0x1BADB002)
    add_notes(b, [(0.00, 0.26, 900.0, 700.0),
                  (0.25, 0.52, 700.0, 520.0),
                  (0.51, 0.78, 520.0, 380.0),
                  (0.77, 1.04, 380.0, 260.0),
                  (1.03, 1.34, 260.0, 140.0)], amp=0.52, duty=0.5,
              vib_hz=6.0, vib_depth=0.08, noise=0.03, rng=rng)
    add_voice(b, 0.00, 1.34, 450.0, 70.0, amp=0.18, wave="triangle",
              vib_hz=6.0, vib_depth=0.08)
    return b


def make_extra_life():
    b = buf_for(0.68)
    add_notes(b, [(0.00, 0.12, 659.25, 659.25),
                  (0.11, 0.23, 783.99, 783.99),
                  (0.22, 0.34, 987.77, 987.77),
                  (0.33, 0.48, 1318.5, 1318.5),
                  (0.47, 0.68, 1318.5, 1975.5)], amp=0.42, duty=0.4)
    add_voice(b, 0.47, 0.68, 659.25, 987.77, amp=0.12, wave="triangle")
    return b


def make_level_clear():
    b = buf_for(1.24)
    add_notes(b, [(0.00, 0.13, 783.99, 783.99),
                  (0.12, 0.25, 1046.5, 1046.5),
                  (0.24, 0.37, 1318.5, 1318.5),
                  (0.36, 0.55, 1568.0, 1568.0),
                  (0.54, 0.70, 1318.5, 1318.5),
                  (0.69, 0.85, 1046.5, 1046.5),
                  (0.84, 1.24, 783.99, 783.99)], amp=0.40, duty=0.45)
    add_voice(b, 0.84, 1.24, 261.6, 261.6, amp=0.14, wave="triangle")
    add_voice(b, 0.84, 1.24, 392.0, 392.0, amp=0.10, wave="triangle")
    return b


def make_game_over():
    b = buf_for(1.54)
    add_notes(b, [(0.00, 0.20, 392.0, 392.0),
                  (0.19, 0.39, 369.99, 369.99),
                  (0.38, 0.58, 349.23, 349.23),
                  (0.57, 0.82, 329.63, 329.63),
                  (0.81, 1.12, 261.63, 261.63),
                  (1.11, 1.54, 196.0, 130.81)], amp=0.44, duty=0.5,
              vib_hz=5.0, vib_depth=0.01)
    add_voice(b, 0.00, 1.54, 196.0, 65.4, amp=0.16, wave="triangle")
    return b


def make_siren_chase():
    b = buf_for(1.00)
    seg = 0.25
    for k, f in enumerate((196.0, 246.94, 196.0, 246.94)):
        t0 = k * seg
        add_voice(b, t0, t0 + seg, f, f, amp=0.40, duty=0.5,
                  vib_hz=5.0, vib_depth=0.012, release=0.03)
        add_voice(b, t0, t0 + seg, f * 2.0, f * 2.0, amp=0.07, wave="sine")
    add_voice(b, 0.0, 1.0, 98.0, 98.0, amp=0.08, wave="triangle")
    fade_edges(b, 4.0)
    return b


def make_siren_hunt():
    b = buf_for(1.00)
    seg = 0.125
    for k, f in enumerate((293.66, 369.99, 293.66, 369.99,
                           293.66, 369.99, 293.66, 369.99)):
        t0 = k * seg
        add_voice(b, t0, t0 + seg, f, f, amp=0.38, duty=0.4,
                  vib_hz=9.0, vib_depth=0.02, release=0.015)
    add_voice(b, 0.0, 1.0, 146.83, 146.83, amp=0.07, wave="triangle")
    fade_edges(b, 4.0)
    return b


def make_siren_fright():
    b = buf_for(0.80)
    rng = Rng(0xDEADBEEF)
    add_voice(b, 0.0, 0.80, 130.81, 164.81, amp=0.46, wave="triangle",
              vib_hz=11.0, vib_depth=0.14, release=0.05,
              noise=0.02, rng=rng)
    add_voice(b, 0.0, 0.80, 65.4, 82.4, amp=0.10, wave="sine",
              vib_hz=11.0, vib_depth=0.14)
    fade_edges(b, 4.0)
    return b


# --------------------------------------------------------------------------
# Tabla: nombre del enum -> (simbolo C, generador, bucle)
# --------------------------------------------------------------------------
SOUNDS = [
    ("AUDIO_MENU",        "menu",        make_menu,        False),
    ("AUDIO_START",       "start",       make_start,       False),
    ("AUDIO_WAKA1",       "waka1",       make_waka1,       False),
    ("AUDIO_WAKA2",       "waka2",       make_waka2,       False),
    ("AUDIO_POWER",       "power",       make_power,       False),
    ("AUDIO_EAT_GHOST",   "eat_ghost",   make_eat_ghost,   False),
    ("AUDIO_EAT_FRUIT",   "eat_fruit",   make_eat_fruit,   False),
    ("AUDIO_DEATH",       "death",       make_death,       False),
    ("AUDIO_EXTRA_LIFE",  "extra_life",  make_extra_life,  False),
    ("AUDIO_LEVEL_CLEAR", "level_clear", make_level_clear, False),
    ("AUDIO_GAME_OVER",   "game_over",   make_game_over,   False),
    ("AUDIO_SIREN_CHASE", "siren_chase", make_siren_chase, True),
    ("AUDIO_SIREN_HUNT",  "siren_hunt",  make_siren_hunt,  True),
    ("AUDIO_SIREN_FRIGHT", "siren_fright", make_siren_fright, True),
]


def c_array(symbol, pcm):
    lines = []
    per = 16
    for i in range(0, len(pcm), per):
        chunk = ", ".join("0x%02X" % b for b in pcm[i:i + per])
        lines.append("        " + chunk + ",")
    return ("static const uint8_t clip_%s[%d] = {\n%s\n};\n"
            % (symbol, len(pcm), "\n".join(lines)))


def generate():
    clips = []
    total = 0
    for enum_name, symbol, maker, loop in SOUNDS:
        buf = maker()
        normalize(buf)
        pcm = to_pcm_u8(buf)
        clips.append((enum_name, symbol, pcm, loop))
        total += len(pcm)

    # ---------------- sfx_data.h ----------------
    h = []
    h.append("/* audio/sfx_data.h - SFX ORIGINALES sintetizados para SereOS.")
    h.append(" *")
    h.append(" * GENERADO por tools/gen_audio.py - NO editar a mano.")
    h.append(" * PCM 8 bits sin signo (128 = silencio), mono, %d Hz." % RATE)
    h.append(" * Todos los sonidos fueron sintetizados desde cero para este proyecto")
    h.append(" * (square/triangle/sine + barridos, vibrato, ruido determinista y")
    h.append(" * envolventes). No se redistribuye ningun WAV de terceros.")
    h.append(" *")
    h.append(" * %-20s %10s %8s  %s" % ("Clip", "muestras", "ms", "tipo"))
    for enum_name, symbol, pcm, loop in clips:
        ms = 1000.0 * len(pcm) / RATE
        h.append(" * %-20s %10d %8.1f  %s" % (enum_name, len(pcm), ms,
                                               "loop" if loop else "one-shot"))
    h.append(" *")
    h.append(" * Total: %d bytes de PCM (%.1f s)." % (total, total / float(RATE)))
    h.append(" */")
    h.append("#ifndef SEREOS_SFX_DATA_H")
    h.append("#define SEREOS_SFX_DATA_H")
    h.append("#include <stdint.h>")
    h.append('#include "audio.h"')
    h.append("")
    h.append("#define SFX_DATA_RATE %d" % RATE)
    h.append("#define SFX_DATA_BYTES %d" % total)
    h.append("")
    h.append("typedef struct {")
    h.append("\tconst uint8_t *data;   /* muestras PCM 8 bits sin signo */")
    h.append("\tuint32_t       length; /* numero de muestras */")
    h.append("\tuint16_t       rate;   /* frecuencia de muestreo en Hz */")
    h.append("\tuint8_t        loopable;")
    h.append("} sfx_clip_t;")
    h.append("")
    h.append("extern const sfx_clip_t sfx_clips[AUDIO_COUNT];")
    h.append("")
    h.append("#endif /* SEREOS_SFX_DATA_H */")
    h.append("")

    # ---------------- sfx_data.c ----------------
    c = []
    c.append("/* audio/sfx_data.c - SFX ORIGINALES sintetizados para SereOS.")
    c.append(" *")
    c.append(" * GENERADO por tools/gen_audio.py - NO editar a mano.")
    c.append(" * Ejecutar `python3 tools/gen_audio.py` para regenerar.")
    c.append(" *")
    c.append(" * Formato: PCM 8 bits sin signo (128 = silencio), mono, %d Hz." % RATE)
    c.append(" * Licencia: efectos originales creados para SereOS; no se usan")
    c.append(" * muestras de terceros (los WAV de referencia no se redistribuyen).")
    c.append(" */")
    c.append('#include "sfx_data.h"')
    c.append("")
    for enum_name, symbol, pcm, loop in clips:
        c.append(c_array(symbol, pcm))
    c.append("const sfx_clip_t sfx_clips[AUDIO_COUNT] = {")
    c.append("\t[AUDIO_NONE] = { 0, 0, 0, 0 },")
    for enum_name, symbol, pcm, loop in clips:
        c.append("\t[%s] = { clip_%s, %d, SFX_DATA_RATE, %d },"
                 % (enum_name, symbol, len(pcm), 1 if loop else 0))
    c.append("};")
    c.append("")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "sfx_data.h"), "w", encoding="utf-8") as f:
        f.write("\n".join(h))
    with open(os.path.join(OUT_DIR, "sfx_data.c"), "w", encoding="utf-8") as f:
        f.write("\n".join(c))
    print("gen_audio: %d efectos, %d bytes PCM (%.2f s) -> %s"
          % (len(clips), total, total / float(RATE), os.path.normpath(OUT_DIR)))
    for enum_name, symbol, pcm, loop in clips:
        print("  %-20s %6d muestras %7.1f ms %s"
              % (enum_name, len(pcm), 1000.0 * len(pcm) / RATE,
                 "loop" if loop else "one-shot"))


if __name__ == "__main__":
    generate()
