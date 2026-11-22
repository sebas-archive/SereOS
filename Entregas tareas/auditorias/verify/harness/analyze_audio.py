#!/usr/bin/env python3
"""analyze_audio.py - Signal analysis of real captures (independent).

Supports:
  * raw S16LE interleaved files  (SDL disk driver / parec --raw)
  * RIFF/WAVE files              (QEMU -audiodev wav output)
  * PCM u8 mono 11025 from assets/sfx_res.c (via parse_assets.py)

Functions:
  load(path, rate, channels) -> float mono in [-1, 1], sample-rate
  active_segments(x, rate, thr_db) -> list of (start_s, end_s)
  measure(x, rate) -> dict(duration, active, peak_dbfs, rms_dbfs, clip,
                           dom_freq, dc)
  correlate(cap, ref_u8, cap_rate, ref_rate) -> best normalized corr + lag

CLI:
  python3 analyze_audio.py <capture> [--rate 48000] [--ch 2] [--wav]
        [--ref-sfx-res path --ref-slot N] [--json out.json]
"""
import json
import struct
import sys

import numpy as np

SFX_RES_C = "/home/t1an/Descargas/sereos02/Pac-man SereOS/assets/sfx_res.c"


# ---------------------------------------------------------------- loading
def load_wav(path):
    """Minimal RIFF/WAVE reader (PCM 8/16/32 int and float32)."""
    raw = open(path, "rb").read()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file: %s" % path)
    pos = 12
    fmt = None
    data = None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        body = raw[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = body
        elif cid == b"data":
            if size == 0:
                # QEMU 11.1.3 -audiodev wav writes RIFF/data size = 0 and keeps
                # appending PCM; use the rest of the file as data.
                data = raw[pos + 8:]
            else:
                data = body
        if size == 0:
            break
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise ValueError("missing fmt/data chunk")
    tag, ch, rate, _byterate, _align, bits = struct.unpack("<HHIIHH", fmt[:16])
    if tag == 0xFFFE and len(fmt) >= 40:  # WAVE_FORMAT_EXTENSIBLE
        tag = struct.unpack("<H", fmt[24:26])[0]
    if tag == 1:      # PCM int
        if bits == 8:
            x = (np.frombuffer(data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif bits == 16:
            x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
        elif bits == 32:
            x = np.frombuffer(data, dtype="<i4").astype(np.float32) / 2147483648.0
        else:
            raise ValueError("unsupported bits %d" % bits)
    elif tag == 3 and bits == 32:  # IEEE float
        x = np.frombuffer(data, dtype="<f4").astype(np.float32)
    else:
        raise ValueError("unsupported wav tag=%d bits=%d" % (tag, bits))
    frames = len(x) // ch
    x = x[:frames * ch].reshape(frames, ch)
    return x.mean(axis=1), rate


def load_raw(path, rate=48000, ch=2, dtype="<i2"):
    x = np.fromfile(path, dtype=dtype).astype(np.float32) / 32768.0
    frames = len(x) // ch
    return x[:frames * ch].reshape(frames, ch).mean(axis=1), rate


def load(path, rate=48000, ch=2):
    if path.lower().endswith(".wav"):
        return load_wav(path)
    return load_raw(path, rate, ch)


# ---------------------------------------------------------------- metrics
def active_segments(x, rate, thr_db=-50.0, min_ms=8.0):
    thr = 10.0 ** (thr_db / 20.0)
    env = np.abs(x)
    # 5 ms envelope max to avoid splitting on zero crossings
    w = max(1, int(rate * 0.005))
    k = np.ones(w) / w
    env = np.convolve(env, k, mode="same")
    on = env > thr
    segs = []
    i = 0
    n = len(on)
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            if (j - i) >= rate * min_ms / 1000.0:
                segs.append((i / rate, j / rate))
            i = j
        else:
            i += 1
    return segs


def measure(x, rate):
    n = len(x)
    peak = float(np.max(np.abs(x))) if n else 0.0
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) if n else 0.0
    clip = int(np.sum(np.abs(x) >= 0.999))
    segs = active_segments(x, rate)
    active = sum(b - a for a, b in segs)
    # dominant frequency on the loudest 200 ms window
    dom = 0.0
    if n > rate // 5:
        w = rate // 5
        seg = x
        best = 0.0
        step = max(1, w // 2)
        for s in range(0, n - w, step):
            e = float(np.sum(seg[s:s + w].astype(np.float64) ** 2))
            if e > best:
                best = e
                win = seg[s:s + w]
        if best > 0:
            spec = np.abs(np.fft.rfft(win * np.hanning(len(win))))
            freqs = np.fft.rfftfreq(len(win), 1.0 / rate)
            spec[:5] = 0
            dom = float(freqs[int(np.argmax(spec))])
    return {
        "samples": n, "duration_s": round(n / rate, 4),
        "active_s": round(active, 4),
        "segments": [(round(a, 3), round(b, 3)) for a, b in segs],
        "peak_dbfs": round(20 * np.log10(max(1e-9, peak)), 3),
        "rms_dbfs": round(20 * np.log10(max(1e-9, rms)), 3),
        "clipped_samples": clip,
        "dom_freq_hz": round(dom, 1),
        "dc": round(float(np.mean(x)), 5),
    }


# ---------------------------------------------------------------- matching
def resample_to(x, src_rate, dst_rate):
    """Linear resample (enough for 11025 -> 48000 correlation checks)."""
    if src_rate == dst_rate:
        return x.astype(np.float32)
    n_out = int(round(len(x) * dst_rate / float(src_rate)))
    idx = np.linspace(0, len(x) - 1, n_out)
    i0 = np.floor(idx).astype(int)
    i1 = np.minimum(i0 + 1, len(x) - 1)
    frac = idx - i0
    return (x[i0] * (1 - frac) + x[i1] * frac).astype(np.float32)


def normalize(x):
    x = x.astype(np.float32)
    x = x - np.mean(x)
    n = np.sqrt(np.sum(x * x))
    if n <= 0:
        return x
    return x / n


def best_corr(cap, ref, min_corr=0.0):
    """Normalized cross-correlation of ref inside cap (FFT based).
    Returns (corr, lag_seconds)."""
    if len(cap) < len(ref) or len(ref) < 16:
        return 0.0, 0.0
    a = normalize(cap)
    b = normalize(ref)
    n = 1
    while n < len(a) + len(b):
        n <<= 1
    fa = np.fft.rfft(a, n)
    fb = np.fft.rfft(b, n)
    cc = np.fft.irfft(fa * np.conj(fb), n)
    # valid lags only
    cc = cc[:len(a) - len(b) + 1]
    k = int(np.argmax(cc))
    return float(cc[k]), k


# ---------------------------------------------------------------- CLI
def main():
    argv = sys.argv
    if len(argv) < 2:
        raise SystemExit(__doc__)
    path = argv[1]
    rate = 48000
    ch = 2
    if "--rate" in argv:
        rate = int(argv[argv.index("--rate") + 1])
    if "--ch" in argv:
        ch = int(argv[argv.index("--ch") + 1])
    x, rate = load(path, rate, ch)
    m = measure(x, rate)
    out = {"file": path, "rate": rate, "metrics": m}

    if "--ref-sfx-res" in argv:
        sys.path.insert(0, "/home/t1an/Descargas/sereos02/audit/verify/harness")
        from parse_assets import parse_sfx_res, slot_report
        sfx = argv[argv.index("--ref-sfx-res") + 1]
        slot = int(argv[argv.index("--ref-slot") + 1])
        parsed = parse_sfx_res(sfx)
        ref_u8 = parsed["slots"][slot]["data"]
        ref = (ref_u8.astype(np.float32) - 128.0) / 128.0
        ref48 = resample_to(ref, parsed["rate"], rate)
        corr, lag = best_corr(x, ref48)
        out["ref"] = {"slot": slot, "len": len(ref_u8),
                      "duration_s": round(len(ref_u8) / float(parsed["rate"]), 4),
                      "corr": round(corr, 4), "lag_s": round(lag / float(rate), 4)}
        # best 3 candidate lags (for loop period / repeats)
        if len(x) > len(ref48):
            a = normalize(x)
            b = normalize(ref48)
            n = 1
            while n < len(a) + len(b):
                n <<= 1
            cc = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
            cc = cc[:len(a) - len(b) + 1]
            peaks = []
            for _ in range(3):
                k = int(np.argmax(cc))
                peaks.append((round(float(cc[k]), 4), round(k / float(rate), 4)))
                lo = max(0, k - int(rate * 0.05))
                hi = min(len(cc), k + int(rate * 0.05))
                cc[lo:hi] = -2
            out["ref"]["peaks"] = peaks

    print(json.dumps(out, indent=2))
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
