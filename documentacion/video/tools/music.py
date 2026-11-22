"""Música instrumental original y efectos de sonido (sintetizados, sin samples
de terceros). Genera WAV estéreo 48 kHz para mezclar con ffmpeg.

Uso: python3 music.py <duracion_segundos> <salida_dir>
"""
import os, sys, wave
import numpy as np

SR = 48000
BPM = 96
BEAT = 60.0 / BPM


def env(n, a, d, s, r, sustain_level=0.6):
    """ADSR simple sobre n muestras."""
    out = np.zeros(n)
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    ns = max(0, n - na - nd - nr)
    i = 0
    if na:
        out[:na] = np.linspace(0, 1, na)
    i = na
    if nd:
        out[i:i + nd] = np.linspace(1, sustain_level, nd)
    i += nd
    out[i:i + ns] = sustain_level
    i += ns
    if nr and i < n:
        out[i:] = np.linspace(out[i - 1] if i > 0 else 0, 0, n - i)
    return out


def note_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def pad(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    # tres osciladores ligeramente desafinados para dar cuerpo
    y = np.zeros(n)
    for det in (-0.6, 0.0, 0.7):
        f = freq * 2 ** (det / 1200)
        y += np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t)
    y /= 3.0
    return y * env(n, 0.9, 0.4, 0, 0.9, 0.7)


def pluck(freq, dur, vol=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * 2 * freq * t)
    decay = np.exp(-t * 5.5)
    return vol * y * decay


def bass(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * 2 * freq * t)
    return 0.55 * y * np.exp(-t * 2.2)


def hat(dur=0.06, vol=0.12):
    n = int(dur * SR)
    rng = np.random.default_rng(7)
    y = rng.standard_normal(n)
    # paso alto simple
    y = np.diff(y, prepend=0)
    return vol * y * np.exp(-np.arange(n) / SR * 60)


def kick(dur=0.22, vol=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 18) + 42
    phase = 2 * np.pi * np.cumsum(f) / SR
    return vol * np.sin(phase) * np.exp(-t * 14)


# progresión: Am - F - C - G (en 8 compases)
CHORDS = [
    (57, [57, 60, 64]),  # Am  (La menor)
    (53, [53, 57, 60]),  # F
    (48, [48, 52, 55]),  # C
    (55, [55, 59, 62]),  # G
]


def section_energy(t):
    """Intensidad 0..1 según el guion: intro suave, demo progresiva,
    punto destacado (PAC-MAN) y cierre elegante."""
    if t < 20:
        return 0.25 + 0.25 * (t / 20)
    if t < 90:
        return 0.5 + 0.2 * ((t - 20) / 70)
    if t < 200:
        return 0.7
    if t < 240:
        return 0.9  # PAC-MAN SereOS: momento destacado
    return max(0.35, 0.8 - 0.35 * ((t - 240) / 60))


def build_music(total):
    n = int(total * SR) + SR * 4
    mix = np.zeros((n, 2))
    bar = 4 * BEAT
    t = 0.0
    bi = 0
    while t < total:
        root, chord = CHORDS[bi % len(CHORDS)]
        e = section_energy(t)
        # pad sostenido del acorde
        for k, midi in enumerate(chord):
            p = pad(note_freq(midi - 12), bar)
            pan = -0.3 + 0.3 * k
            i0 = int(t * SR)
            mix[i0:i0 + len(p), 0] += p * 0.16 * e * (1 - max(pan, 0))
            mix[i0:i0 + len(p), 1] += p * 0.16 * e * (1 + min(pan, 0))
        # bajo en corcheas suaves
        for s in range(8):
            st = t + s * (BEAT / 2)
            if e > 0.45 and s % 2 == 0:
                b = bass(note_freq(root - 24), BEAT * 0.9)
                i0 = int(st * SR)
                mix[i0:i0 + len(b), :] += (b * 0.7 * e)[:, None]
        # arpegio de pluck (más presente en las secciones intensas)
        arp = [chord[0], chord[1], chord[2], chord[1]] * 4
        for s in range(16):
            st = t + s * (BEAT / 4)
            p = pluck(note_freq(arp[s % len(arp)] + 12), BEAT * 0.9, vol=0.12 * (0.4 + e))
            i0 = int(st * SR)
            pan_l = 0.85 if s % 2 == 0 else 0.55
            mix[i0:i0 + len(p), 0] += p * pan_l
            mix[i0:i0 + len(p), 1] += p * (1.0 - pan_l + 0.3)
        # percusión suave (solo a partir de la introducción)
        if e > 0.4:
            for s in range(4):
                st = t + s * BEAT
                k = kick(vol=0.22 * e)
                i0 = int(st * SR)
                mix[i0:i0 + len(k), :] += k[:, None]
            for s in range(8):
                st = t + s * (BEAT / 2) + BEAT / 4
                h = hat(vol=0.05 * e)
                i0 = int(st * SR)
                mix[i0:i0 + len(h), :] += h[:, None] * 0.7
        t += bar
        bi += 1
    mix = mix[: int(total * SR)]
    # fundido de entrada y salida
    fade_in = np.minimum(1, np.arange(len(mix)) / (SR * 4))
    fade_out = np.minimum(1, (len(mix) - np.arange(len(mix))) / (SR * 6))
    mix *= (fade_in * fade_out)[:, None]
    # limitador suave para evitar clipping
    peak = np.max(np.abs(mix)) or 1
    mix = np.tanh(mix / peak * 1.4) * 0.5
    return mix


def sfx_whoosh(dur=0.9):
    n = int(dur * SR)
    rng = np.random.default_rng(3)
    y = rng.standard_normal(n)
    # filtro pasa-bajos móvil simple
    out = np.zeros(n)
    acc = 0.0
    for i in range(n):
        cut = 0.02 + 0.2 * (i / n)
        acc += cut * (y[i] - acc)
        out[i] = acc
    return out * np.sin(np.linspace(0, np.pi, n)) * 0.6


def sfx_chime(freq=880, dur=1.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 2.76 * t)
    return 0.25 * y * np.exp(-t * 4.0)


def sfx_click(dur=0.05):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(11)
    return 0.3 * rng.standard_normal(n) * np.exp(-t * 180)


def write_wav(path, data):
    data = np.clip(data, -1, 1)
    pcm = (data * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    total = float(sys.argv[1]) if len(sys.argv) > 1 else 300
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "..", "audio")
    os.makedirs(out, exist_ok=True)
    write_wav(os.path.join(out, "musica_base.wav"), build_music(total))
    # efectos de sonido sueltos
    for name, data in (("sfx_whoosh.wav", sfx_whoosh()),
                       ("sfx_chime.wav", sfx_chime()),
                       ("sfx_chime_alto.wav", sfx_chime(1320, 0.9)),
                       ("sfx_click.wav", sfx_click())):
        d = data if data.ndim == 2 else np.stack([data, data], axis=1)
        write_wav(os.path.join(out, name), d)
    print("audio generado en", os.path.abspath(out), "duracion", total)


if __name__ == "__main__":
    main()


def main_for(total, out=None):
    """Genera música y efectos con la duración exacta del video."""
    out = out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio")
    os.makedirs(out, exist_ok=True)
    write_wav(os.path.join(out, "musica_base.wav"), build_music(total))
    for name, data in (("sfx_whoosh.wav", sfx_whoosh()),
                       ("sfx_chime.wav", sfx_chime()),
                       ("sfx_chime_alto.wav", sfx_chime(1320, 0.9)),
                       ("sfx_click.wav", sfx_click())):
        d = data if data.ndim == 2 else np.stack([data, data], axis=1)
        write_wav(os.path.join(out, name), d)
    print("audio generado", total, "s", flush=True)
