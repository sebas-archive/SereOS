#!/usr/bin/env python3
"""analyze_sereos.py - native SereOS capture analysis (QEMU SB16 -> wav).

Verifies, from the recorded audio only:
  * START completeness: 0.2 s excerpts of the embedded clip are searched in the
    capture with a *locally normalised, signed* correlation.  A sample-clock
    drift between guest (11025 Hz) and the QEMU wav backend makes a single
    fixed-lag correlation useless, so every excerpt gets its own best lag.
  * chunk0 (samples 0..32768) and chunk1 (32768..46676) separately: signed
    correlation, inverted-reference check and best lag -> detects polarity
    inversion, missing tail or mis-ordered chunks.
  * siren loops: period from autocorrelation (0.1333 s CHASE / 0.4002 s HUNT).
  * any long silence gap inside/after START (the old D1 defect: START cut at
    2.97 s followed by ~1.5 s of silence).
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
parsed = parse_sfx_res(os.path.join(ROOT, "Pac-man SereOS/assets/sfx_res.c"))


def ref(slot, rate, a=None, b=None):
    d = parsed["slots"][slot]["data"].astype(np.float32)
    if a is not None:
        d = d[a:b]
    return resample_to((d - 128.0) / 128.0, parsed["rate"], rate)


def local_corr(cap, rf):
    """Max signed Pearson correlation of rf sliding over cap + lag."""
    n = len(rf)
    if len(cap) < n:
        return 0.0, 0
    Ln = 1
    while Ln < len(cap) + n:
        Ln <<= 1
    rfz = rf.astype(np.float64) - rf.mean()
    num = np.fft.irfft(np.fft.rfft(cap.astype(np.float64), Ln) *
                       np.conj(np.fft.rfft(rfz, Ln)), Ln)
    num = num[:len(cap) - n + 1]
    cs = np.concatenate([[0.0], np.cumsum(cap.astype(np.float64))])
    s1 = cs[n:] - cs[:-n]
    cs2 = np.concatenate([[0.0], np.cumsum(cap.astype(np.float64) ** 2)])
    s2 = cs2[n:] - cs2[:-n]
    mean = s1 / n
    var = np.maximum(s2 - n * mean * mean, 1e-12)
    cc = num / np.sqrt(var * float(np.sum(rfz ** 2)))
    k = int(np.argmax(cc))
    kmin = int(np.argmin(cc))
    if abs(cc[kmin]) > abs(cc[k]):
        return float(cc[kmin]), kmin
    return float(cc[k]), k


def excerpts(cap, rate, slot, step_s=0.2, a=None, b=None):
    """For each 0.2 s excerpt of the slot clip, best signed corr+lag in cap."""
    d = parsed["slots"][slot]["data"]
    lo = 0 if a is None else a
    hi = len(d) if b is None else b
    step = int(step_s * parsed["rate"])
    out = []
    pos = lo
    idx = 0
    while pos + step <= hi:
        rf = ref(slot, rate, pos, pos + step)
        c, lag = local_corr(cap, rf)
        out.append({"excerpt": idx, "clip_ms": round(pos * 1000.0 / parsed["rate"], 1),
                    "corr": round(c, 4), "lag_s": round(lag / rate, 4),
                    "expected_lag_s": None})
        pos += step
        idx += 1
    # expected lag = first excerpt lag + clip offset (relative continuity)
    if out:
        base = out[0]["lag_s"] - out[0]["clip_ms"] / 1000.0
        for o in out:
            o["expected_lag_s"] = round(base + o["clip_ms"] / 1000.0, 4)
    return out


def periodicity(x, rate):
    """Autocorrelation period of the siren part (last 3 s)."""
    seg = x[-int(3 * rate):]
    seg = seg - seg.mean()
    ac = np.correlate(seg, seg, mode="full")[len(seg) - 1:]
    ac /= ac[0] if ac[0] else 1
    best = []
    lo = int(0.05 * rate)
    hi = min(len(ac) - 1, int(0.6 * rate))
    for target in (0.1333, 0.4002):
        pass
    # top local peaks
    for i in range(lo + 1, hi):
        if ac[i] > ac[i - 1] and ac[i] > ac[i + 1] and ac[i] > 0.3:
            best.append((round(i / rate, 4), round(float(ac[i]), 3)))
    best.sort(key=lambda p: -p[1])
    return best[:5]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        EV, "logs/sereos_final.wav")
    x, rate = load(path)
    m = measure(x, rate)
    out = {"file": path, "rate": rate, "metrics": m}
    print("duration=%.3f active=%.3f peak=%.1f clip=%d segments=%s"
          % (m["duration_s"], m["active_s"], m["peak_dbfs"],
             m["clipped_samples"], m["segments"][:6]))
    print("periodicity (s, corr):", periodicity(x, rate))

    # START chunk 0 and chunk 1
    n0 = len(parsed["slots"][2]["chunks"][0])
    print("START chunk0 len", n0, "chunk1 len",
          parsed["slots"][2]["len"] - n0)
    for label, a, b in (("chunk0", 0, n0),
                        ("chunk1", n0, parsed["slots"][2]["len"])):
        ex = excerpts(x, rate, 2, 0.2, a, b)
        mags = [e["corr"] for e in ex]
        lags = [e["lag_s"] for e in ex]
        print("%s: n=%d min_corr=%.3f max_corr=%.3f mean_corr=%.3f "
              "neg=%d lag_span=%.3f"
              % (label, len(ex), min(mags), max(mags), float(np.mean(mags)),
                 sum(1 for c in mags if c < 0), (max(lags) - min(lags)) if lags else 0))
        out[label] = {"n": len(ex), "min_corr": round(min(mags), 4),
                      "max_corr": round(max(mags), 4),
                      "mean_corr": round(float(np.mean(mags)), 4),
                      "negative": sum(1 for c in mags if c < 0),
                      "lags": lags,
                      "excerpts": ex}
    # inverted reference check for chunk1
    rf = ref(2, rate, n0, parsed["slots"][2]["len"])
    c, lag = local_corr(x, rf)
    ci, lagi = local_corr(x, -rf)
    print("chunk1 full: signed corr=%.4f lag=%.3f | inverted corr=%.4f lag=%.3f"
          % (c, lag / rate, ci, lagi / rate))
    out["chunk1_full"] = {"corr": round(c, 4), "lag_s": round(lag / rate, 4),
                          "inverted_corr": round(ci, 4),
                          "inverted_lag_s": round(lagi / rate, 4)}
    # START full clip continuity: total span from first chunk0 match to last chunk1 match
    p0 = out["chunk0"]["excerpts"][0]["lag_s"] if out["chunk0"]["excerpts"] else 0
    p1 = out["chunk1"]["excerpts"][-1]["lag_s"] if out["chunk1"]["excerpts"] else 0
    out["start_span_s"] = round(p1 - p0 + 0.2, 3) if p1 else 0
    print("START audible span (first->last excerpt):", out["start_span_s"], "s (clip 4.234 s)")
    # longest silence inside the span
    a = int(max(0, p0 * rate)); b = int(min(len(x), (p1 + 0.2) * rate))
    seg = x[a:b]
    env = np.abs(seg)
    w = max(1, int(0.02 * rate))
    env = np.convolve(env, np.ones(w) / w, mode="same")
    sil = env < 0.006
    runs = []
    i = 0
    while i < len(sil):
        if sil[i]:
            j = i
            while j < len(sil) and sil[j]:
                j += 1
            runs.append((j - i) / rate)
            i = j
        else:
            i += 1
    out["longest_silence_in_start_s"] = round(max(runs) if runs else 0.0, 3)
    print("longest internal silence in START span:",
          out["longest_silence_in_start_s"], "s")
    with open(os.path.join(EV, "sereos_analysis.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("wrote sereos_analysis.json")


if __name__ == "__main__":
    main()
