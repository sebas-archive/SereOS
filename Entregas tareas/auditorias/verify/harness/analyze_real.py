#!/usr/bin/env python3
"""analyze_real.py - event-level analysis of the REAL Linux binary captures.

For each QA scene capture (null sink + parec) it reports:
  * duration / active duration / peak / clipping
  * when START is audible (proper locally-normalised Pearson correlation of the
    embedded clip against the capture): number of appearances and completeness
  * a timeline of which PCM siren loop is audible per 250 ms window
    (slot 12 CHASE vs slot 13 HUNT vs 15 RESPAWN), so a simultaneous overlap
    of two sirens WOULD be visible as a window where both correlate.
  * intermission (slot 10) presence for the victory scene.
"""
import json
import os
import sys

import numpy as np

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(H)))
sys.path.insert(0, H)
from analyze_audio import load, measure, resample_to  # noqa: E402
from parse_assets import parse_sfx_res  # noqa: E402

EV = os.path.join(ROOT, "audit/verify/evidence")
L = os.path.join(EV, "linux")
parsed = parse_sfx_res(os.path.join(ROOT, "Pac-man SereOS/assets/sfx_res.c"))


def ref(slot, rate):
    d = parsed["slots"][slot]["data"].astype(np.float32)
    return resample_to((d - 128.0) / 128.0, parsed["rate"], rate)


def corr_curve(cap, rf):
    """Locally normalised Pearson correlation of rf sliding over cap.
    Returns array cc where cc[i] = corr(cap[i:i+len(rf)], rf)."""
    n = len(rf)
    if len(cap) < n:
        return np.zeros(0)
    Ln = 1
    while Ln < len(cap) + n:
        Ln <<= 1
    rfz = rf.astype(np.float64) - rf.mean()
    num = np.fft.irfft(np.fft.rfft(cap.astype(np.float64), Ln) *
                       np.conj(np.fft.rfft(rfz, Ln)), Ln)
    num = num[:len(cap) - n + 1]
    cs = np.concatenate([[0.0], np.cumsum(cap.astype(np.float64))])
    s1 = cs[n:] - cs[:-n]                       # sum of window
    cs2 = np.concatenate([[0.0], np.cumsum(cap.astype(np.float64) ** 2)])
    s2 = cs2[n:] - cs2[:-n]                     # sum of squares
    mean = s1 / n
    var = np.maximum(s2 - n * mean * mean, 1e-12)
    den = np.sqrt(var * float(np.sum(rfz ** 2)))
    return num / den


def windows_present(cc, cap_len, n, rate, win=0.25, thresh=0.55, step=0.1):
    """Intervals (start_s, end_s) where the max local corr in a window > thresh."""
    segs = []
    total = cap_len / float(rate)
    t = 0.0
    on = None
    while t < total - win:
        a = int(t * rate)
        b = int(min(len(cc), (t + win) * rate))
        m = float(np.max(cc[a:b])) if b > a else 0.0
        if m > thresh:
            if on is None:
                on = t
        else:
            if on is not None:
                segs.append((round(on, 2), round(t, 2)))
                on = None
        t += step
    if on is not None:
        segs.append((round(on, 2), round(total, 2)))
    return segs


def max_corr(cc):
    return round(float(cc.max()), 4) if len(cc) else 0.0


CASES = ["real_start", "real_play", "real_frightened", "real_ghostcapture",
         "real_death", "real_victory", "real_gameover", "real_pause",
         "real_menu", "real_soundoff"]
out = {}
for name in CASES:
    p = os.path.join(L, name + ".raw")
    if not os.path.exists(p):
        out[name] = {"error": "missing"}
        continue
    x, rate = load(p)
    m = measure(x, rate)
    e = {"metrics": m}
    # siren presence timeline
    pres = {}
    for slot in (12, 13, 15):
        cc = corr_curve(x, ref(slot, rate))
        pres[str(slot)] = {"max": max_corr(cc),
                           "present_s": windows_present(cc, len(x), None, rate)}
    e["sirens"] = pres
    # simultaneous overlap: same 0.25 s window where BOTH sirens correlate
    cc12 = corr_curve(x, ref(12, rate))
    cc13 = corr_curve(x, ref(13, rate))
    overlap = []
    win = 0.25
    t = 0.0
    limit = min(len(cc12), len(cc13)) / float(rate)
    while t < limit - win:
        a = int(t * rate); b = int(min(limit, (t + win) * rate))
        if b > a:
            m12 = float(np.max(np.abs(cc12[a:b])))
            m13 = float(np.max(np.abs(cc13[a:b])))
            if m12 > 0.55 and m13 > 0.55:
                overlap.append(round(t, 2))
        t += 0.05
    e["siren_overlap_windows"] = overlap
    # START: 0.2 s excerpts of the embedded clip searched in the capture with
    # per-excerpt best lag (guest/host clock drift makes fixed lag useless)
    full2 = ref(2, rate)
    step = int(0.2 * rate)
    exs = []
    pos = 0
    while pos + step <= len(full2):
        rf = full2[pos:pos + step]
        ccx = corr_curve(x, rf)
        if len(ccx):
            k = int(np.argmax(np.abs(ccx)))
            exs.append({"clip_ms": round(pos * 1000.0 / parsed["rate"], 1),
                        "corr": round(float(ccx[k]), 4),
                        "lag_s": round(k / rate, 4)})
        pos += step
    good = [q for q in exs if q["corr"] > 0.8]
    e["start"] = {
        "excerpts": exs,
        "n_excerpts": len(exs),
        "n_matched_corr_gt_0.8": len(good),
        "min_corr": min([q["corr"] for q in exs]) if exs else 0,
        "span_s": round(good[-1]["lag_s"] - good[0]["lag_s"] + 0.2, 3) if good else 0,
        "appearances": 1 if good else 0,
    }
    # intermission
    if name == "real_victory":
        cc10 = corr_curve(x, ref(10, rate))
        e["level_clear"] = {"max_corr": max_corr(cc10),
                            "present_s": windows_present(cc10, len(x), None, rate,
                                                         win=0.5, thresh=0.55)}
    out[name] = e
    print("%-18s active=%.3f peak=%.1f clip=%d | START %s | 12:%s 13:%s 15:%s | overlap=%s"
          % (name, m["active_s"], m["peak_dbfs"], m["clipped_samples"],
             (e["start"]["appearances"], e["start"]["span_s"],
              e["start"]["min_corr"]), pres["12"]["present_s"],
             pres["13"]["present_s"], pres["15"]["present_s"],
             e["siren_overlap_windows"]))

with open(os.path.join(EV, "real_analysis.json"), "w") as f:
    json.dump(out, f, indent=2, default=str)
print("wrote real_analysis.json")
