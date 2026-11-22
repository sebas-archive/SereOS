#!/usr/bin/env python3
"""Final evidence analysis for the SereOS native audio audit.

Inputs : capture-sb16scen.raw, capture-pcspkscen.raw (44100 stereo s16le, from
         the PulseAudio null-sink monitor), serial/scenario logs.
Outputs: analysis-sb16.txt / analysis-pcspk.txt and console summary.
"""
import os
import re

import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(BASE, "..", "..", "Pac-man SereOS")
OS = os.path.join(BASE, "..", "..", "sistema operativo")
RATE = 44100
out = []


def p(s=""):
    print(s)
    out.append(s)


def load(p):
    a = np.fromfile(p, dtype="<i2")
    a = a[: len(a) // 2 * 2].reshape(-1, 2)
    return a[:, 0].astype(np.float64)


def resample(x, src, dst):
    n = int(round(len(x) * dst / src))
    return np.interp(np.arange(n) * (src / dst), np.arange(len(x)), x)


def parse_arrays(path, regex):
    txt = open(path, "r", errors="replace").read()
    outd = {}
    for m in re.finditer(regex, txt, re.S):
        outd[m.group(1)] = np.array(
            [int(x, 0) for x in re.findall(r"0x[0-9A-Fa-f]+|\d+", m.group(2))],
            dtype=np.float64)
    return outd


game = parse_arrays(os.path.join(GAME, "assets", "sfx_res.c"),
                    r"const uint8_t\s+(pacasset_pcm_[A-Za-z0-9_]+)\s*\[[^\]]*\]\s*=\s*\{(.*?)\};")
os_sfx = parse_arrays(os.path.join(OS, "audio", "sfx_data.c"),
                      r"static const uint8_t\s+(clip_[A-Za-z0-9_]+)\s*\[[^\]]*\]\s*=\s*\{(.*?)\};")


def local_match(cap, clip, sr=11025, win_ms=100, search_s=None):
    """best normalised correlation of a clip (resampled to capture rate),
    using a sliding clip start and scoring the best contiguous 100 ms block."""
    e = resample(clip - clip.mean(), sr, RATE)
    if len(e) >= len(cap):
        return None
    nfft = 1 << int(np.ceil(np.log2(len(cap) + len(e))))
    cc = np.fft.irfft(np.fft.rfft(cap - cap.mean(), nfft) *
                      np.fft.rfft(e[::-1], nfft), nfft)[: len(cap) - len(e) + 1]
    c = cap - cap.mean()
    den = np.sqrt((c ** 2).sum() * (e ** 2).sum())
    cc = cc / den
    k = int(np.argmax(np.abs(cc)))
    local = []
    seg = min(int(RATE * win_ms / 1000), len(e))
    w = c[k:k + len(e)]
    for i in range(0, max(1, len(w) - seg + 1), seg):
        ww = w[i:i + seg]
        ee = e[i:i + seg]
        d = np.sqrt((ww ** 2).sum() * (ee ** 2).sum())
        local.append((ww * ee).sum() / d if d else 0.0)
    return {"t": k / RATE, "corr": float(cc[k]), "local_max": float(max(local, key=abs)),
            "local": [round(x, 2) for x in local[:8]]}


def analyse_sb16():
    cap = load(os.path.join(BASE, "capture-sb16scen.raw"))
    p("=" * 78)
    p("SB16 SCENARIO CAPTURE  (%s, %.2f s @ %d Hz mono)" %
      ("capture-sb16scen.raw", len(cap) / RATE, RATE))
    p("=" * 78)
    # activity timeline (0.1 s)
    win = RATE // 10
    env = np.array([np.sqrt((cap[i:i + win] ** 2).mean())
                    for i in range(0, len(cap) - win, win)])
    thr = 300.0
    p("audible windows (0.1 s bins, rms>300), contiguous runs:")
    i = 0
    while i < len(env):
        if env[i] > thr:
            j = i
            while j < len(env) and env[j] > thr:
                j += 1
            if (j - i) >= 2:
                p("   %6.2f - %6.2f s  (%.2f s)  peak rms %5.0f"
                  % (i * 0.1, j * 0.1, (j - i) * 0.1, env[i:j].max()))
            i = j
        else:
            i += 1
    p("")
    p("clip match (best global corr / best 100 ms local corr / t_start):")
    tests = [
        ("START chunk0 (PCM)", game.get("pacasset_pcm_game_start_0"), 11025),
        ("START chunk1 (PCM, rejected)", game.get("pacasset_pcm_game_start_1"), 11025),
        ("WAKA1 (PCM)", game.get("pacasset_pcm_waka1"), 11025),
        ("WAKA2 (PCM)", game.get("pacasset_pcm_waka2"), 11025),
        ("DEATH (PCM)", game.get("pacasset_pcm_pacman_death"), 11025),
        ("SIREN_HUNT (PCM loop)", game.get("pacasset_pcm_siren_hunt"), 11025),
        ("EAT_GHOST (PCM)", game.get("pacasset_pcm_eat_ghost"), 11025),
        ("GHOST_RESPAWN (PCM, unused)", game.get("pacasset_pcm_ghost_respawn"), 11025),
        ("GAME_OVER (OS synth fallback)", os_sfx.get("clip_game_over"), 11025),
        ("POWER (OS synth fallback)", os_sfx.get("clip_power"), 11025),
    ]
    for name, arr, sr in tests:
        if arr is None:
            p("   %-32s NOT PARSED" % name)
            continue
        r = local_match(cap, arr, sr)
        if r is None:
            p("   %-32s clip too long" % name)
            continue
        p("   %-32s corr=%+.3f  local100ms=%+.3f  t=%7.3f s  %s"
          % (name, r["corr"], r["local_max"], r["t"],
             "MATCH" if abs(r["local_max"]) > 0.6 else ("WEAK" if abs(r["local_max"]) > 0.3 else "no")))
    # START duration check: find the longest early activity run that matches chunk0
    r = local_match(cap, game["pacasset_pcm_game_start_0"])
    if r:
        p("")
        p("START: chunk0 found at t=%.2f s, asset duration 2.972 s -> audible run ends"
          " ~%.2f s; chunk1 (1.261 s) expected at t=%.2f..%.2f" %
          (r["t"], r["t"] + 2.972, r["t"] + 2.972, r["t"] + 4.233))
        a = int((r["t"] + 3.1) * RATE)
        b = int((r["t"] + 4.2) * RATE)
        p("capture RMS in the missing chunk1 window: %.1f (silence < 300)" %
          float(np.sqrt((cap[a:b] ** 2).mean())))


def analyse_pcspk():
    cap = load(os.path.join(BASE, "capture-pcspkscen.raw"))
    p("")
    p("=" * 78)
    p("PC SPEAKER FALLBACK CAPTURE (%s, %.2f s)" %
      ("capture-pcspkscen.raw", len(cap) / RATE))
    p("=" * 78)
    win = int(RATE * 0.1)
    env = np.array([np.sqrt((cap[i:i + win] ** 2).mean())
                    for i in range(0, len(cap) - win, win)])
    act = np.where(env > 200)[0]
    p("active 0.1 s windows: %d of %d; peak rms %.0f"
      % (len(act), len(env), env.max()))
    # dominant frequency histogram over active windows
    freqs = []
    for i in act:
        w = cap[i * win:(i + 1) * win]
        w = w - w.mean()
        sp = np.abs(np.fft.rfft(w * np.hanning(len(w))))
        f = np.fft.rfftfreq(len(w), 1 / RATE)
        k = int(np.argmax(sp[1:])) + 1
        if sp[k] > 10 * np.median(sp):
            freqs.append((round(f[k]), i * 0.1))
    from collections import Counter
    cnt = Counter(f for f, _ in freqs)
    p("dominant tones detected (Hz: count) -> %s" % dict(cnt.most_common(14)))
    expect = {520: "WAKA1", 390: "WAKA2", 950: "START", 880: "POWER",
              660: "EAT_GHOST", 1000: "EAT_FRUIT", 180: "DEATH",
              1250: "EXTRA_LIFE", 1000: "LEVEL_CLEAR", 140: "GAME_OVER",
              247: "siren chase", 196: "siren chase", 370: "siren hunt",
              294: "siren hunt", 165: "siren fright", 131: "siren fright",
              700: "MENU", 440: "generic", 1250: "siren?"}
    hits = [(f, n, expect[f]) for f, n in cnt.items() if f in expect]
    p("tones matching pcspk_map/pcspk_siren table: %s" % hits)


analyse_sb16()
analyse_pcspk()
open(os.path.join(BASE, "analysis-final.txt"), "w").write("\n".join(out) + "\n")
print("\nwritten:", os.path.join(BASE, "analysis-final.txt"))
