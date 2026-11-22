#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificacion B1: intermission integrado en sfx_res + tablas coherentes.

Uso (Python bundled con NumPy/Pillow):
    python3 audit/fix-assets/verify_fix.py
Escribe audit/fix-assets/verify_fix.json y devuelve 0 si todo OK.
"""
import hashlib
import json
import math
import os
import re
import sys

import numpy as np

ROOT = "/home/t1an/Descargas/sereos02"
PROJ = os.path.join(ROOT, "Pac-man SereOS")
RES = "/home/t1an/Descargas/Res"
OUT = os.path.join(ROOT, "audit", "fix-assets")
sys.path.insert(0, os.path.join(PROJ, "tools"))
import gen_pacman_res_assets as G  # noqa: E402

FAIL = []


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def check(name, cond, detail=None):
    ok = bool(cond)
    print(("OK   " if ok else "FAIL ") + name + ("" if detail is None else " :: %s" % detail))
    if not ok:
        FAIL.append(name)
    return ok


src = open(os.path.join(PROJ, "assets", "sfx_res.c"), encoding="utf-8").read()
hdr = open(os.path.join(PROJ, "assets", "sfx_res.h"), encoding="utf-8").read()
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
slots = {int(m.group(1)): {"ptr": (None if m.group(2) in (None, "0")
                                      else m.group(2)),
                            "len": int(m.group(3))}
         for m in re.finditer(r"\[(\d+)\] = \{ (?:(\w+), )?(\d+)u \}", slot_tbl)}
loop = [int(x) for x in re.findall(r"\d+", sec("pacasset_sfx_res_loop"))][:16]
cc = [int(x) for x in re.findall(r"\d+", sec("pacasset_sfx_res_chunk_count"))][:16]
clens = [int(x) for x in re.findall(r"(\d+)u", sec("pacasset_sfx_res_chunk_len"))]
chunks_tbl = sec("pacasset_sfx_res_chunks")
chunk_rows = [re.findall(r"pacasset_pcm_\w+", r)
              for r in re.findall(r"\{ ([^}]*?) \}", chunks_tbl)]
total = int(re.search(r"pacasset_sfx_res_total_bytes = (\d+)u", src).group(1))
rate = int(re.search(r"pacasset_sfx_res_rate = (\d+)", src).group(1))

with_inter = [s for s in slots if slots[s]["ptr"]]
without = [s for s in slots if not slots[s]["ptr"]]
check("11 WAV usados -> 11 slots con datos (2,3,4,6,7,8,9,10,12,13,15)",
      with_inter == [2, 3, 4, 6, 7, 8, 9, 10, 12, 13, 15], with_inter)
check("slots sin WAV = 0,1,5,11,14", without == [0, 1, 5, 11, 14], without)
check("rate 11025", rate == 11025, rate)
check("total_bytes = 184411", total == 184411, total)
check("suma arrays = 184411", sum(len(v) for v in arrays.values()) == total,
      sum(len(v) for v in arrays.values()))

# LEVEL_CLEAR
lc_len = slots[10]["len"]
check("LEVEL_CLEAR len 57377", lc_len == 57377, lc_len)
check("LEVEL_CLEAR 2 chunks", cc[10] == 2, cc[10])
check("LEVEL_CLEAR chunk_len 32768+24609",
      clens[20:22] == [32768, 24609], clens[20:22])
check("LEVEL_CLEAR chunk_sum == len", sum(clens[20:22]) == lc_len)
check("LEVEL_CLEAR chunks <=32768", max(clens[20:22]) <= 32768)
check("LEVEL_CLEAR loop_flag=0", loop[10] == 0, loop[10])
check("LEVEL_CLEAR array == generador",
      np.array_equal(np.concatenate([arrays[n] for n in chunk_rows[10]]),
                     G.make_sfx(RES)["clips"]["LEVEL_CLEAR"]["pcm"]))

# loop flags: respawn 0, sirenas 1
check("loop flags = [0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0]",
      loop == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0], loop)
check("GHOST_RESPAWN loop_flag=0", loop[15] == 0, loop[15])

# fidelidad byte a byte generador <-> sfx_res en TODOS los slots
res = G.make_sfx(RES)
SYM = {2: "START", 3: "WAKA1", 4: "WAKA2", 6: "EAT_GHOST", 7: "EAT_FRUIT",
       8: "DEATH", 9: "EXTRA_LIFE", 10: "LEVEL_CLEAR", 12: "SIREN_CHASE",
       13: "SIREN_HUNT", 15: "GHOST_RESPAWN"}
fid = {}
for slot, sym in SYM.items():
    exp = res["clips"][sym]["pcm"]
    if chunk_rows[slot]:
        emb = np.concatenate([arrays[n] for n in chunk_rows[slot]])
    else:
        emb = np.array([], dtype=np.uint8)
    ok = (len(emb) == len(exp) and np.array_equal(emb, exp))
    fid[slot] = {"symbol": sym, "frames": int(len(exp)),
                 "bytes_identical": bool(ok),
                 "chunks": [int(x) for x in clens[slot * 2:slot * 2 + 2] if x]}
    check("slot %d %s byte-identico (%d fr)" % (slot, sym, len(exp)), ok)

# sirenas intactas: variantes y arrays p0/p10/p20/p30
siren_ok = True
sv = {}
for slot, sym, key in ((13, "SIREN_HUNT", "hunt"), (12, "SIREN_CHASE", "chase")):
    m = re.search(r"const pac_res_sfx_t pacasset_siren_" + key +
                  r"_res\[[^\]]*\] = \{(.*?)\};", src, re.S).group(1)
    ent = re.findall(r"\{ (\w+), (\d+)u \}", m)
    sv[key] = []
    for i, (ptr, ln) in enumerate(ent):
        exp_v = res["siren_variants"][sym][i]["pcm"]
        ok = (np.array_equal(arrays[ptr], exp_v) and int(ln) == len(exp_v))
        siren_ok = siren_ok and ok
        sv[key].append({"pct": res["siren_variants"][sym][i]["pct"],
                        "frames": int(len(exp_v)), "bytes_identical": bool(ok)})
check("sirenas variantes p0/p10/p20/p30 intactas", siren_ok, sv)

# clipping en todo el PCM (u8: 0/255)
mn = min(int(a.min()) for a in arrays.values()
         if a.size and not a.dtype == object)
mx = max(int(a.max()) for a in arrays.values())
clip = sum(int((a <= 0).sum() + (a >= 255).sum()) for a in arrays.values())
peak = max(mx - 128, 128 - mn)
check("0 muestras con clipping (u8 0/255)", clip == 0, clip)
check("pico PCM 117 LSB (-0.71 dBFS)", peak == 117, peak)

# intermission: metricas del PCM nuevo vs original
pcm = np.concatenate([arrays[n] for n in chunk_rows[10]]).astype(float)
x = (pcm - 128.0) / 128.0
orig_a, sr, ch, sw = G.load_wav_mono(os.path.join(RES, "intermission.wav"))
inter = {"frames": int(len(pcm)), "duration_s": round(len(pcm) / 11025.0, 6),
         "peak_lsb": int(np.max(np.abs(pcm - 128))),
         "peak_dbfs": round(20 * math.log10(np.max(np.abs(pcm - 128)) / 127.0), 3),
         "rms_dbfs": round(20 * math.log10(np.sqrt(np.mean(x ** 2))), 3),
         "dc_offset_lsb": round(float(np.mean(pcm) - 128), 3),
         "first_u8": int(pcm[0]), "last_u8": int(pcm[-1]),
         "source_frames": int(len(orig_a)), "source_rate": sr,
         "source_duration_s": round(len(orig_a) / sr, 6)}
check("intermission 57377 fr / 5.204263 s",
      inter["frames"] == 57377 and inter["duration_s"] == 5.204263, inter)

# res_original: 11 WAV y byte-identicos a Res
orig = os.path.join(PROJ, "assets", "res_original")
wavs = sorted(f for f in os.listdir(orig) if f.lower().endswith(".wav"))
check("res_original tiene 11 WAV", len(wavs) == 11, wavs)
same = all(md5(os.path.join(orig, f)) == md5(os.path.join(RES, f)) for f in wavs)
check("res_original WAV == Res byte a byte (11/11)", same)

# cabecera
check("cabecera menciona 11 WAV", "11 WAV" in hdr or "los 11 WAV" in hdr)
check("cabecera slots con WAV 2,3,4,6,7,8,9,10,12,13,15",
      "2,3,4,6,7,8,9,10,12,13,15" in hdr)
check("cabecera LEVEL_CLEAR=intermission", "intermission" in hdr)

out = {
    "ok": not FAIL, "failures": FAIL,
    "slots_with_data": with_inter, "slots_without_data": without,
    "total_pcm_bytes": total, "rate": rate,
    "loop_flags": loop, "chunk_count": cc,
    "level_clear": {"frames": lc_len, "chunks": clens[20:22],
                    "duration_s": round(lc_len / 11025.0, 6)},
    "fidelity": fid, "siren_variants": sv,
    "clipping_samples": clip, "peak_lsb": peak,
    "intermission": inter,
    "res_original_wav_count": len(wavs), "res_original_matches_res": same,
}
with open(os.path.join(OUT, "verify_fix.json"), "w") as f:
    json.dump(out, f, indent=1)
print("\nRESULTADO:", "OK" if not FAIL else "FALLOS: %s" % FAIL)
sys.exit(0 if not FAIL else 1)
