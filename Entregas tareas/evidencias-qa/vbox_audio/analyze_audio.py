#!/usr/bin/env python3
"""Analiza el WAV capturado del monitor del anfitrion durante `audiotest`.

SereOS genera los tonos de diagnostico como onda cuadrada u8 a 11025 Hz; los
cuatro tonos (440/660/880/1320 Hz, 200 ms cada uno) tienen ademas armonicos
impares. La deteccion se hace por DFT ventaneada (Goertzel) en cada frecuencia
esperada, comparando la energia del tono con el ruido de la misma banda en
zonas de silencio (SNR), para no confundir el ruido de baja frecuencia con los
tonos.

Uso: python3 analyze_audio.py [wav] [salida.json]
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

EXPECTED_HZ = (440, 660, 880, 1320)
WIN_MS = 100          # ventana de analisis
HOP_MS = 25


def read_wav(path: Path):
    w = wave.open(str(path))
    nch, rate, bits, n = w.getnchannels(), w.getframerate(), w.getsampwidth(), w.getnframes()
    raw = w.readframes(n)
    w.close()
    if bits != 2:
        raise ValueError(f"se esperaba PCM 16 bits, hay {bits * 8}")
    a = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    if nch > 1:
        a = a.reshape(-1, nch).mean(axis=1)
    return a, rate, nch


def goertzel_mag(seg: np.ndarray, rate: int, freq: float, win: np.ndarray) -> float:
    t = np.arange(seg.size) / rate
    return float(abs(np.dot((seg - seg.mean()) * win, np.exp(-2j * np.pi * freq * t))))


def analyze(path: Path) -> dict:
    a, rate, nch = read_wav(path)
    n = a.size
    peak = float(np.abs(a).max()) if n else 0.0
    rms = float(np.sqrt((a ** 2).mean())) if n else 0.0
    res = {
        "file": str(path), "rate": rate, "channels": nch, "bits": 16,
        "frames": n, "seconds_captured": round(n / rate, 3),
        "peak_sample": int(peak),
        "peak_dbfs": round(20 * np.log10(max(peak, 1) / 32768.0), 2),
        "rms_sample": round(rms, 1),
        "rms_dbfs": round(20 * np.log10(max(rms, 1) / 32768.0), 2),
    }

    # --- actividad (energia de banda 200-4000 Hz) --------------------------
    S = np.fft.rfft(a)
    f = np.fft.rfftfreq(n, 1.0 / rate)
    S[(f < 200) | (f > 4000)] = 0
    bp = np.fft.irfft(S, n)
    fl = max(1, rate // 100)                     # tramas de 10 ms
    nf = n // fl
    env = np.array([np.sqrt((bp[i * fl:(i + 1) * fl] ** 2).mean()) for i in range(nf)])
    noise = float(np.median(env))
    thr = max(noise * 3.0, float(env.max()) * 0.08, 100.0)
    active = env > thr
    regions = []
    i = 0
    while i < nf:
        if active[i]:
            j = i
            while j < nf and active[j]:
                j += 1
            if (j - i) * 10 >= 60:               # >= 60 ms
                if regions and i * fl / rate - regions[-1]["end_s"] < 0.12:
                    regions[-1]["end_s"] = round(j * fl / rate, 3)
                else:
                    regions.append({"start_s": round(i * fl / rate, 3),
                                    "end_s": round(j * fl / rate, 3)})
            i = j
        else:
            i += 1
    res["active_regions"] = regions
    res["active_seconds"] = round(sum(r["end_s"] - r["start_s"] for r in regions), 3)
    res["noise_floor_rms_sample"] = round(noise, 1)

    # --- deteccion por tono ------------------------------------------------
    wl = max(256, int(rate * WIN_MS / 1000))
    hop = max(1, int(rate * HOP_MS / 1000))
    win = np.hanning(wl)
    starts = list(range(0, max(1, n - wl), hop))
    tone = {hz: [] for hz in EXPECTED_HZ}
    for s in starts:
        seg = a[s:s + wl]
        for hz in EXPECTED_HZ:
            tone[hz].append(goertzel_mag(seg, rate, hz, win))
    # tamano de un tono (200 ms) en ventanas
    per_tone = max(1, int(200 / WIN_MS))

    def amax(seg_vals):
        """maximo y centro (tiempo) de la mejor racha de `per_tone` ventanas
        consecutivas (energia integrada), para no premiar picos de un solo
        cuadro por un clic."""
        best, best_i = -1.0, 0
        for k in range(0, len(seg_vals) - per_tone + 1):
            v = float(np.sum(np.square(seg_vals[k:k + per_tone])))
            if v > best:
                best, best_i = v, k
        vals = seg_vals[best_i:best_i + per_tone]
        return float(np.max(vals)), float(np.mean(vals)), best_i

    # ruido de la misma banda en zonas sin actividad (>=0.5 s del tono)
    quiet = []
    for s in starts:
        t = s / rate
        if any(r["start_s"] - 0.6 <= t <= r["end_s"] + 0.6 for r in regions):
            continue
        seg = a[s:s + wl]
        quiet.append([goertzel_mag(seg, rate, hz, win) for hz in EXPECTED_HZ])
    quiet = np.array(quiet) if quiet else np.zeros((1, len(EXPECTED_HZ)))
    noise_mag = {hz: float(np.median(quiet[:, i])) for i, hz in enumerate(EXPECTED_HZ)}

    hits = []
    for hz in EXPECTED_HZ:
        vals = tone[hz]
        mx, mean, best_i = amax(vals)
        snr = 20 * np.log10(max(mx, 1e-9) / max(noise_mag[hz], 1e-9))
        # frecuencia medida por FFT de la mejor ventana
        s = starts[best_i]
        seg = a[s:s + wl]
        spec = np.abs(np.fft.rfft((seg - seg.mean()) * np.hanning(seg.size),
                                  4 * wl))
        fr = np.fft.rfftfreq(4 * wl, 1.0 / rate)
        band = (fr > hz - 40) & (fr < hz + 40)
        k = int(np.argmax(np.where(band, spec, 0)))
        got = float(fr[k])
        hits.append({
            "want_hz": hz,
            "measured_hz": round(got, 1),
            "freq_error_pct": round(abs(got - hz) / hz * 100, 2),
            "peak_mag": round(mx, 1),
            "mean_mag": round(mean, 1),
            "noise_mag": round(noise_mag[hz], 1),
            "snr_db": round(snr, 1),
            "tone_start_s": round(starts[best_i] / rate, 3),
            "ok": bool(snr > 15.0 and abs(got - hz) / hz < 0.06),
        })
    res["tones"] = hits
    res["all_expected_found"] = all(h["ok"] for h in hits)
    res["peak_above_minus40"] = bool(res["peak_dbfs"] > -40.0)
    res["non_silent"] = bool(res["all_expected_found"] and res["peak_above_minus40"])
    # duracion del bloque de tonos a partir de la mejor ventana de cada tono
    if hits:
        first = min(h["tone_start_s"] for h in hits)
        last = max(h["tone_start_s"] + 0.2 for h in hits)
        res["tone_block"] = {"first_s": round(first, 3),
                             "last_s": round(last, 3),
                             "duration_s": round(last - first, 3)}
    return res


def main() -> int:
    wav = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path("/home/t1an/Descargas/sereos02/build/vbox_audio/vbox_audiotest.wav")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else wav.with_suffix(".analysis.json")
    res = analyze(wav)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res["non_silent"] else 2


if __name__ == "__main__":
    sys.exit(main())
