#!/usr/bin/env python3
"""Analyse the QEMU WAV capture against the PCM assets compiled into the OS.

- Parses capture.wav (QEMU wav audiodev: 44100 Hz stereo s16, header sizes 0)
- Extracts expected PCM arrays from Pac-man assets/sfx_res.c and OS audio/sfx_data.c
- Locates each expected clip in the capture with FFT cross-correlation
- Prints a timeline of audible intervals and per-clip best match
"""
import os
import re
import sys
import wave

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
GAME = os.path.join(ROOT, "Pac-man SereOS")
OS = os.path.join(ROOT, "sistema operativo")
CAP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "capture.wav")
OUT = os.path.join(BASE, "wav-analysis.txt")

lines = []


def p(s=""):
    print(s)
    lines.append(s)


def read_capture(path):
    raw = open(path, "rb").read()
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE", "not a wav"
    # walk chunks instead of trusting the (unfinalised) RIFF/data sizes
    pos = 12
    fmt = None
    data = None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        clen = int.from_bytes(raw[pos + 4:pos + 8], "little")
        body = raw[pos + 8:pos + 8 + clen]
        if cid == b"fmt ":
            fmt = body
        elif cid == b"data":
            data = raw[pos + 8:]  # QEMU leaves clen=0 until close
            break
        pos += 8 + clen + (clen & 1)
    assert fmt is not None and data is not None
    f = np.frombuffer(fmt[:16], dtype="<u2")
    tag, ch = int(f[0]), int(f[1])
    rate = int(f[2]) | (int(f[3]) << 16)
    align, bits = int(f[6]), int(f[7])
    p("WAV: format=%d channels=%d rate=%d align=%d bits=%d data_bytes=%d" %
      (tag, ch, rate, align, bits, len(data)))
    dtype = "<i2" if bits == 16 else np.uint8
    a = np.frombuffer(data[:len(data) // (2 if bits == 16 else 1) *
                           (2 if bits == 16 else 1)], dtype=dtype)
    a = a[: (len(a) // ch) * ch].reshape(-1, ch)
    mono = a.astype(np.float64).mean(axis=1)
    if bits == 8:
        mono -= 128.0
    return mono, int(rate), int(ch)


def parse_c_arrays(path, prefix):
    txt = open(path, "r", errors="replace").read()
    out = {}
    for m in re.finditer(r"const uint8_t\s+(" + prefix +
                         r"[A-Za-z0-9_]*)\s*\[\s*\]\s*=\s*\{(.*?)\};", txt, re.S):
        name = m.group(1)
        vals = [int(x, 0) for x in re.findall(r"0x[0-9A-Fa-f]+|\d+", m.group(2))]
        out[name] = np.array(vals, dtype=np.float64)
    return out


def resample(x, src, dst):
    n = int(round(len(x) * dst / src))
    idx = np.arange(n) * (src / dst)
    return np.interp(idx, np.arange(len(x)), x)


CAPTURE, RATE, CH = read_capture(CAP)
CAPTURE = CAPTURE - CAPTURE.mean()
dur = len(CAPTURE) / RATE
p("capture duration: %.3f s (%d samples mono @ %d Hz)" % (dur, len(CAPTURE), RATE))

# ---------------------------------------------------------------- timeline
win = int(RATE * 0.05)
env = np.sqrt(np.convolve(CAPTURE ** 2, np.ones(win) / win, mode="same"))
thr = max(env.max() * 0.02, 20.0)
active = env > thr
# merge intervals
iv = []
i = 0
while i < len(active):
    if active[i]:
        j = i
        while j < len(active) and active[j]:
            j += 1
        if (j - i) / RATE > 0.04:
            iv.append((i / RATE, j / RATE))
        i = j
    else:
        i += 1
p("audible intervals (start-end s, dur):")
for a, b in iv:
    p("  %8.3f - %8.3f  (%6.3f s)" % (a, b, b - a))
if env.max() > 0:
    peak = int(np.argmax(env))
    p("peak RMS %.1f at t=%.3f s" % (env.max(), peak / RATE))
p("max abs sample: %.0f (int16 full scale 32767)" % np.abs(CAPTURE).max())

# ---------------------------------------------------------------- assets
assets = parse_c_arrays(os.path.join(GAME, "assets", "sfx_res.c"), "pacasset_pcm_")
os_assets = parse_c_arrays(os.path.join(OS, "audio", "sfx_data.c"), "clip_")
p("game PCM arrays parsed: %d   OS synth arrays parsed: %d"
  % (len(assets), len(os_assets)))


def best_match(name, expected, sr=11025):
    """resample expected to capture rate and find best normalised correlation."""
    exp = resample(expected.astype(np.float64), sr, RATE)
    exp = exp - exp.mean()
    if len(exp) < 16 or len(exp) >= len(CAPTURE):
        return None
    n = 1 << int(np.ceil(np.log2(len(CAPTURE) + len(exp))))
    c = np.fft.rfft(CAPTURE, n)
    e = np.fft.rfft(exp[::-1], n)
    cc = np.fft.irfft(c * e, n)[: len(CAPTURE) - len(exp) + 1]
    denom = np.sqrt((CAPTURE ** 2).sum() * (exp ** 2).sum())
    if denom == 0:
        return None
    cc = cc / denom
    k = int(np.argmax(np.abs(cc)))
    t = k / RATE
    # local RMS of capture at the match window for a signal-vs-noise view
    w = CAPTURE[k:k + len(exp)]
    rms = float(np.sqrt((w ** 2).mean()))
    er = float(np.sqrt((exp ** 2).mean()))
    return float(cc[k]), t, rms, er


p("")
p("per-clip match (corr, t_start, capture_rms, expected_rms):")
cands = [
    ("START chunk0 (game_start_0)", assets.get("pacasset_pcm_game_start_0"), 11025),
    ("START chunk1 (game_start_1)", assets.get("pacasset_pcm_game_start_1"), 11025),
    ("WAKA1", assets.get("pacasset_pcm_waka1"), 11025),
    ("WAKA2", assets.get("pacasset_pcm_waka2"), 11025),
    ("DEATH", assets.get("pacasset_pcm_pacman_death"), 11025),
    ("EXTRA_LIFE", assets.get("pacasset_pcm_extra_life"), 11025),
    ("EAT_GHOST", assets.get("pacasset_pcm_eat_ghost"), 11025),
    ("EAT_FRUIT", assets.get("pacasset_pcm_eat_fruit"), 11025),
    ("SIREN_CHASE", assets.get("pacasset_pcm_siren_chase"), 11025),
    ("SIREN_HUNT", assets.get("pacasset_pcm_siren_hunt"), 11025),
    ("GHOST_RESPAWN", assets.get("pacasset_pcm_ghost_respawn"), 11025),
    ("OS synth POWER", os_assets.get("clip_power"), 11025),
    ("OS synth MENU", os_assets.get("clip_menu"), 11025),
    ("OS synth GAME_OVER", os_assets.get("clip_game_over"), 11025),
    ("OS synth LEVEL_CLEAR", os_assets.get("clip_level_clear"), 11025),
    ("OS synth SIREN_CHASE", os_assets.get("clip_siren_chase"), 11025),
]
for name, arr, sr in cands:
    if arr is None:
        p("  %-30s NOT PARSED" % name)
        continue
    r = best_match(name, arr, sr)
    if r is None:
        p("  %-30s too short/long" % name)
        continue
    corr, t, rms, er = r
    p("  %-30s corr=%+.3f  t=%7.3f s  capRMS=%8.1f  expRMS=%8.1f  %s"
      % (name, corr, t, rms, er, "MATCH" if corr > 0.55 else "no"))

# ---------------------------------------------------------------- START focus
gs0 = assets.get("pacasset_pcm_game_start_0")
gs1 = assets.get("pacasset_pcm_game_start_1")
if gs0 is not None:
    r = best_match("start0", gs0)
    p("")
    if r:
        corr, t0, _, _ = r
        p("START hypothesis: chunk0 best at t=%.3f s corr=%+.3f; expected len %.3f s"
          % (t0, corr, len(gs0) / 11025))
        if gs1 is not None:
            # energy in the window where chunk1 *would* have played
            t1 = t0 + len(gs0) / 11025
            a = int(t1 * RATE)
            b = int((t1 + len(gs1) / 11025) * RATE)
            w = CAPTURE[a:b]
            p("capture RMS in chunk1 slot (t=%.2f..%.2f s): %.1f"
              % (t1, b / RATE, float(np.sqrt((w ** 2).mean())) if len(w) else -1))
            p("expected chunk1 len %.3f s (%d samples) - dma_program rejects it "
              "(0x%x low16 + %d > 0x10000)"
              % (len(gs1) / 11025, len(gs1), 0xFF40, len(gs1)))

open(OUT, "w").write("\n".join(lines) + "\n")
print("\nwritten:", OUT)
