#!/usr/bin/env python3
"""Analiza capturas raw del driver 'disk' de SDL (S16LE 44100 Hz estereo).

Calcula duracion real, energia, frecuencia dominante, huecos de silencio y
estabilidad del tono de las sirenas. Genera CSV + tabla por stdout.
"""
import csv
import glob
import os
import re
import sys

import numpy as np

FS = 44100
EVID = "/home/t1an/Descargas/sereos02/build/audit_linux/evidence"
RAW = os.path.join(EVID, "raw")


def load(path):
    data = np.fromfile(path, dtype="<i2")
    if data.size % 2:
        data = data[:-1]
    st = data.reshape(-1, 2).astype(np.float32)
    mono = st.mean(axis=1)
    return mono


def db(x):
    return 20.0 * np.log10(max(x, 1e-12))


def analyze(name, mono):
    n = mono.size
    total = n / FS
    peak = float(np.max(np.abs(mono))) if n else 0.0
    if peak < 1:
        return dict(total=total, active=0.0, peak_db=-120, rms_db=-120,
                    freq=0.0, zcr=0.0, gaps=0, longest_gap=0.0,
                    fmin=0.0, fmax=0.0, onset=0.0, clipped=0)
    thr = max(64.0, peak * 0.01)
    act = np.abs(mono) > thr
    idx = np.flatnonzero(act)
    onset = idx[0] / FS
    end = idx[-1] / FS
    active = end - onset
    seg = mono[idx[0]:idx[-1] + 1]
    rms = float(np.sqrt(np.mean(seg * seg)))
    # frecuencia dominante (FFT con ventana Hann, ignorar DC)
    m = seg.size
    if m > 1:
        N = 1 << int(np.ceil(np.log2(min(m, 1 << 18))))
        w = np.hanning(seg.size)
        spec = np.abs(np.fft.rfft(seg * w, n=N))
        freqs = np.fft.rfftfreq(N, 1.0 / FS)
        spec[0:5] = 0
        k = int(np.argmax(spec))
        freq = float(freqs[k])
    else:
        freq = 0.0
        spec = np.zeros(8)
    # zero-crossings rate
    sign = np.signbit(seg)
    zc = float(np.count_nonzero(sign[1:] != sign[:-1]) / (2.0 * max(active, 1e-9)))
    # huecos de silencio dentro de la region activa (ventanas de 10 ms)
    win = int(0.01 * FS)
    gaps = 0
    longest = 0.0
    cur = 0
    if seg.size >= win:
        for i in range(0, seg.size - win, win):
            r = np.sqrt(np.mean(seg[i:i + win] ** 2))
            if r < peak * 0.02:
                cur += 1
                longest = max(longest, cur * 0.01)
            else:
                if cur:
                    gaps += 1
                cur = 0
        if cur:
            gaps += 1
    # estabilidad del tono por ventanas de 250 ms (solo si es largo)
    fmin = fmax = freq
    if active > 0.5:
        wl = int(0.25 * FS)
        vals = []
        for i in range(0, seg.size - wl, wl):
            s = seg[i:i + wl]
            N = 1 << int(np.ceil(np.log2(s.size)))
            sp = np.abs(np.fft.rfft(s * np.hanning(s.size), n=N))
            fr = np.fft.rfftfreq(N, 1.0 / FS)
            sp[0:5] = 0
            vals.append(float(fr[int(np.argmax(sp))]))
        if vals:
            fmin, fmax = min(vals), max(vals)
    clipped = int(np.count_nonzero(np.abs(mono) >= 32700))
    return dict(total=total, active=active, peak_db=db(peak / 32768.0),
                rms_db=db(rms / 32768.0), freq=freq, zcr=zc, gaps=gaps,
                longest_gap=longest, fmin=fmin, fmax=fmax, onset=onset,
                clipped=clipped)


def main():
    files = sorted(glob.glob(os.path.join(RAW, "*.raw")),
                   key=lambda p: (int(re.match(r"(\d+)_", os.path.basename(p)).group(1)),
                                  os.path.basename(p)))
    rows = []
    for path in files:
        m = re.match(r"(\d+)_(.+?)(?:_loop)?\.raw$", os.path.basename(path))
        slot, name = int(m.group(1)), m.group(2)
        mono = load(path)
        a = analyze(name, mono)
        rows.append(dict(slot=slot, name=name,
                         file=os.path.basename(path), **a))
    out = os.path.join(EVID, "analysis_slots.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"escrito {out}\n")
    hdr = (f"{'slot':>4} {'nombre':<14} {'tot_s':>6} {'act_s':>6} "
           f"{'peakdB':>7} {'rmsdB':>7} {'freqHz':>7} {'zcr':>6} "
           f"{'gaps':>4} {'gap_s':>6} {'fmin':>6} {'fmax':>6}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['slot']:>4} {r['name']:<14} {r['total']:6.3f} "
              f"{r['active']:6.3f} {r['peak_db']:7.2f} {r['rms_db']:7.2f} "
              f"{r['freq']:7.1f} {r['zcr']:6.0f} {r['gaps']:>4} "
              f"{r['longest_gap']:6.3f} {r['fmin']:6.1f} {r['fmax']:6.1f}")


if __name__ == "__main__":
    main()
