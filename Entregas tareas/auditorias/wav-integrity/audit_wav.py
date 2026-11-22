#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria de audio WAV de PAC-MAN SereOS (solo lectura).

Reproduce las mediciones de REPORT.md:
  1) inventario + metricas de los 11 WAV de /home/t1an/Descargas/Res
  2) comparacion byte a byte del PCM embebido en assets/sfx_res.c con la
     salida del generador tools/gen_pacman_res_assets.py
  3) fidelidad (SNR de cuantizacion y SNR total frente al WAV original)

Uso (Python bundled del harness, necesita NumPy + Pillow):
    python3 audit_wav.py [--json] [--res DIR] [--project DIR]

No modifica el proyecto ni los WAV. No escribe en /tmp salvo las previews
del generador (make_sfx), que van a /tmp/res_gen en la maquina de ejecucion.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import wave

import numpy as np

RATE = 11025
SB16_MAX_BLOCK = 32768
EXPECTED = ["game start", "waka1", "waka2", "eat ghost", "eat fruit",
            "extra life", "ghost respawn", "hunted siren", "hunter siren",
            "pacman death", "intermission"]
CLIPS = [(2, "game start.wav", False), (3, "waka1.wav", False),
         (4, "waka2.wav", False), (6, "eat ghost.wav", False),
         (7, "eat fruit.wav", False), (8, "pacman death.wav", False),
         (9, "extra life.wav", False), (12, "hunter siren.wav", True),
         (13, "hunted siren.wav", True), (15, "ghost respawn.wav", True)]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def parse_riff(raw):
    out = {"file_size": len(raw), "chunks": []}
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("no RIFF/WAVE")
    riff_size = int(np.frombuffer(raw[4:8], "<u4")[0])
    end = 8 + riff_size
    off, fmt, data_off, data_len = 12, None, None, None
    while off + 8 <= min(end, len(raw)):
        cid = raw[off:off + 4].decode("latin-1", "replace")
        csz = int(np.frombuffer(raw[off + 4:off + 8], "<u4")[0])
        body = raw[off + 8:off + 8 + csz]
        if cid == "fmt ":
            fmt = tuple(int(x) for x in np.frombuffer(body[:16], "<u2")[0:6])
        elif cid == "data":
            data_off, data_len = off + 8, csz
        out["chunks"].append({"id": cid, "size": csz})
        off += 8 + csz + (csz & 1)
    out["fmt"] = fmt
    out["data_offset"] = data_off
    out["data_len"] = data_len
    out["riff_ok"] = (end == len(raw))
    out["bytes_after_data"] = (len(raw) - (data_off + data_len)
                               if data_off is not None else None)
    out["extra_chunks"] = [c["id"] for c in out["chunks"]
                           if c["id"] not in ("fmt ", "data")]
    return out


def load_wav(path):
    with wave.open(path, "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    else:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    return a.reshape(n, ch), sr, ch, sw, raw


def db(x):
    return float(20.0 * math.log10(max(abs(float(x)), 1e-12)))


def rms_db(x):
    r = float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0
    return db(r) if r > 0 else -240.0


def silence_bounds(x, thr_db=-60.0):
    thr = 10 ** (thr_db / 20.0)
    nz = np.where(np.abs(x) > thr)[0]
    if len(nz) == 0:
        return len(x), len(x), 0, 0
    return int(nz[0]), int(len(x) - 1 - nz[-1]), int(nz[0]), int(nz[-1])


def loop_metrics(x, sr):
    n = len(x)
    if n < sr // 8:
        return None
    off = int(n * 0.25)
    seg = (x - x.mean())[off:]
    nfft = 1 << int(np.ceil(np.log2(2 * len(seg))))
    F = np.fft.rfft(seg, nfft)
    ac = np.fft.irfft(F * np.conj(F), nfft)[:len(seg)]
    ac /= ac[0] + 1e-12
    lo, hi = int(sr * 0.08), min(int(sr * 0.65), len(seg) - 1)
    if hi <= lo:
        return None
    lag = lo + int(np.argmax(ac[lo:hi]))
    wl = min(int(sr * 0.02), n - lag - 1)
    best = (1e9, off)
    if wl > 50:
        for st in range(off, max(off + 1, n - lag - wl + 1), max(1, sr // 200)):
            err = float(np.mean(np.abs(x[st:st + wl] - x[st + lag:st + lag + wl])))
            if err < best[0]:
                best = (err, st)
    st = best[1]
    loop = x[st:st + lag]
    return {"period_s": round(lag / sr, 6), "period_frames": int(lag),
            "ac_peak": round(float(ac[lag]), 4),
            "start_s": round(st / sr, 6),
            "match_err_lsb": round(best[0] * 127.0, 3),
            "seam_lsb": round(float(abs(loop[0] - loop[-1]) * 127.0), 2)}


def wav_metrics(path):
    riff = parse_riff(open(path, "rb").read())
    a, sr, ch, sw, raw = load_wav(path)
    n = a.shape[0]
    x = a[:, 0] if ch == 1 else a.mean(axis=1)
    lead, trail, first, last = silence_bounds(x)
    rec = {
        "file": os.path.basename(path), "bytes": len(raw), "md5": md5(path),
        "sha256": sha256(path), "format": riff["fmt"],
        "rate": sr, "channels": ch, "bits": sw * 8, "frames": n,
        "duration_s": round(n / sr, 6),
        "bitrate_bps": round(len(raw) * 8 / (n / sr)),
        "peak_dbfs": round(db(np.max(np.abs(a))), 4),
        "rms_dbfs": round(rms_db(x), 4),
        "dc_offset": round(float(np.mean(x)), 6),
        "clipping_samples": int(np.sum(np.abs(a) >= (1.0 if sw == 1 else 0.999969))),
        "silence_lead_s": round(lead / sr, 6),
        "silence_trail_s": round(trail / sr, 6),
        "last_sample_dbfs": round(db(x[-1]), 2),
        "tail50_peak_dbfs": round(db(np.max(np.abs(x[-max(1, int(sr * .05)):]))), 4),
        "riff_ok": riff["riff_ok"],
        "bytes_after_data": riff["bytes_after_data"],
        "extra_chunks": riff["extra_chunks"],
        "dual_mono": bool(ch == 2 and np.array_equal(a[:, 0], a[:, 1])),
    }
    rec["loop"] = loop_metrics(x, sr) if n > sr // 4 else None
    return rec


def parse_sfx_c(path):
    src = open(path, encoding="utf-8").read()
    arrays = {}
    for m in re.finditer(r"const uint8_t (\w+)\[\] = \{(.*?)\};", src, re.S):
        arrays[m.group(1)] = np.array(
            [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", m.group(2))],
            dtype=np.uint8)

    def sec(name):
        m = re.search(r"const\s+[^;{]*?" + name +
                      r"(?:\[[^\]]*\])+\s*=\s*\{(.*?)\};", src, re.S)
        return m.group(1)

    slot_tbl = re.search(r"const pac_res_sfx_t pacasset_sfx_res\[[^\]]*\] = \{(.*?)\};",
                         src, re.S).group(1)
    slots = {int(m.group(1)): {"ptr": m.group(2), "len": int(m.group(3))}
             for m in re.finditer(r"\[(\d+)\] = \{ (?:(\w+), )?(\d+)u \}", slot_tbl)}
    loop = [int(x) for x in re.findall(r"\d+", sec("pacasset_sfx_res_loop"))][:16]
    cc = [int(x) for x in re.findall(r"\d+", sec("pacasset_sfx_res_chunk_count"))][:16]
    clens = [int(x) for x in re.findall(r"(\d+)u", sec("pacasset_sfx_res_chunk_len"))]
    total = int(re.search(r"pacasset_sfx_res_total_bytes = (\d+)u", src).group(1))
    rate = int(re.search(r"pacasset_sfx_res_rate = (\d+)", src).group(1))
    return arrays, slots, loop, cc, clens, total, rate


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="/home/t1an/Descargas/Res")
    ap.add_argument("--project",
                    default="/home/t1an/Descargas/sereos02/Pac-man SereOS")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv[1:])
    sys.path.insert(0, os.path.join(args.project, "tools"))
    import gen_pacman_res_assets as G  # noqa: E402

    out = {"res": args.res, "project": args.project, "wav": {}, "embedded": {}}
    files = sorted(f for f in os.listdir(args.res) if f.lower().endswith(".wav"))
    out["inventory"] = {"count": len(files),
                        "missing": [e for e in EXPECTED if e + ".wav" not in files],
                        "extra": [f for f in files
                                  if os.path.splitext(f)[0] not in EXPECTED]}
    for f in files:
        out["wav"][f] = wav_metrics(os.path.join(args.res, f))

    arrays, slots, loop, cc, clens, total, rate = parse_sfx_c(
        os.path.join(args.project, "assets", "sfx_res.c"))
    res = G.make_sfx(args.res)
    sym = {2: "START", 3: "WAKA1", 4: "WAKA2", 6: "EAT_GHOST", 7: "EAT_FRUIT",
           8: "DEATH", 9: "EXTRA_LIFE", 12: "SIREN_CHASE", 13: "SIREN_HUNT",
           15: "GHOST_RESPAWN"}
    # filas de la tabla de chunks (16 x 2)
    rows = re.findall(r"\{ ([^}]*?) \}", re.search(
        r"pacasset_sfx_res_chunks\[[^\]]*\]\[[^\]]*\] = \{(.*?)\};",
        open(os.path.join(args.project, "assets", "sfx_res.c"),
             encoding="utf-8").read(), re.S).group(1))
    chunk_rows = [re.findall(r"pacasset_pcm_\w+", r) for r in rows]

    def snr(sig, err):
        s, n = float(np.sum(sig ** 2)), float(np.sum(err ** 2))
        return None if n == 0 else round(10 * math.log10(s / n), 2)

    for slot, fname, is_loop in CLIPS:
        exp = res["clips"][sym[slot]]["pcm"]
        emb = (np.concatenate([arrays[n] for n in chunk_rows[slot]])
               if chunk_rows[slot] else np.array([], dtype=np.uint8))
        a, sr, ch, sw = G.load_wav_mono(os.path.join(args.res, fname))
        r = G.resample_sinc(a, sr, RATE) if sr != RATE else a.copy()
        thr = 10 ** (-55.0 / 20.0)
        idx = np.where(np.abs(r) > thr)[0]
        s = max(0, int(idx[0]) - int(RATE * 0.002))
        e = min(len(r), int(idx[-1]) + int(RATE * 0.002) + 1)
        b = G.normalize(r[s:e])
        linfo = None
        if is_loop:
            b, linfo = G.make_loop(b, RATE)
        ref = b
        hat = (exp.astype(float) - 128.0) / 127.0
        up = G.resample_sinc(hat, RATE, sr)
        start_src = int(round((s + (linfo["start"] if linfo else 0)) * sr / RATE))
        n = min(len(up), len(a) - start_src)
        m0, m1 = int(0.02 * sr), n - int(0.02 * sr)
        src = a[start_src + m0:start_src + m1]
        rec = up[m0:m1]
        gain = float(np.dot(src, rec) / np.dot(rec, rec)) if len(rec) else 0.0
        out["embedded"][slot] = {
            "symbol": sym[slot], "wav": fname,
            "table_len": slots[slot]["len"], "array_len": int(len(emb)),
            "expected_len": int(len(exp)),
            "bytes_equal": bool(np.array_equal(emb, exp)),
            "chunks": [int(x) for x in clens[slot * 2:slot * 2 + 2] if x],
            "loop_flag": bool(loop[slot]), "rate": rate,
            "pcm_peak_lsb": int(np.max(np.abs(exp.astype(int) - 128))),
            "quant_snr_db": snr(ref, hat - ref),
            "source_snr_db": snr(src, src - gain * rec),
            "loop": linfo,
        }
    out["embedded"]["total_bytes"] = total
    out["embedded"]["sum_arrays"] = int(sum(len(v) for v in arrays.values()))
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
