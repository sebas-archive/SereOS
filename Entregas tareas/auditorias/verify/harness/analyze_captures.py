#!/usr/bin/env python3
"""analyze_captures.py - analyze the verification captures and emit a table.

Reads audit/verify/evidence/linux/*.raw (48 kHz s16le stereo, parec) and
optionally audit/verify/evidence/sereos/*.raw|.wav, measures each sound and
correlates it with the embedded PCM of assets/sfx_res.c (parsed independently).

Outputs:
  * evidence/analysis.json   (all metrics, one entry per capture)
  * evidence/analysis.csv    (report table)
  * evidence/linux/wav/*.wav (listenable conversions)
"""
import glob
import json
import os
import subprocess
import sys
import wave

import numpy as np

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(H)))
sys.path.insert(0, H)
from analyze_audio import (active_segments, best_corr, load, measure,  # noqa: E402
                           normalize, resample_to)
from parse_assets import parse_sfx_res  # noqa: E402

SFX = os.path.join(ROOT, "Pac-man SereOS/assets/sfx_res.c")
EV = os.path.join(ROOT, "audit/verify/evidence")
SLOT = {1: "MENU", 2: "START", 3: "WAKA1", 4: "WAKA2", 5: "POWER",
        6: "EAT_GHOST", 7: "EAT_FRUIT", 8: "DEATH", 9: "EXTRA_LIFE",
        10: "LEVEL_CLEAR", 11: "GAME_OVER", 12: "SIREN_CHASE",
        13: "SIREN_HUNT", 14: "SIREN_FRIGHT", 15: "GHOST_RESPAWN"}
# capture basename -> slot used as reference
CASES = {
    "real_start": 2, "real_play": 13, "real_frightened": 12,
    "real_ghostcapture": 15, "real_death": 8, "real_victory": 10,
    "real_gameover": 11, "real_menu": 1, "real_pause": 13,
    "real_soundoff": None,
    "h_slot2_START": 2, "h_slot3_WAKA1": 3, "h_slot4_WAKA2": 4,
    "h_slot6_EAT_GHOST": 6, "h_slot7_EAT_FRUIT": 7, "h_slot8_DEATH": 8,
    "h_slot9_EXTRA_LIFE": 9, "h_slot10_LEVEL_CLEAR": 10,
    "h_slot15_GHOST_RESPAWN": 15, "h_slot12_SIREN_CHASE": 12,
    "h_slot13_SIREN_HUNT": 13, "h_slot1_MENU_synth": 1,
    "h_slot5_POWER_synth": 5, "h_slot11_GAME_OVER_synth": 11,
    "h_slot14_FRIGHT_synth": 14, "h_oneshot_ghost_then_waka": 6,
}

parsed = parse_sfx_res(SFX)


def ref_wave(slot, rate):
    d = parsed["slots"][slot]["data"].astype(np.float32)
    x = (d - 128.0) / 128.0
    return resample_to(x, parsed["rate"], rate)


def chunk_corr(cap, ref, rate, chunks=4):
    """Correlation of ref chunks around the best global lag, with polarity."""
    out = []
    corr, lag = best_corr(cap, ref)
    # allow per-chunk re-alignment +-60 ms around the global lag
    span = int(rate * 0.06)
    n = 1
    for k in range(chunks):
        a0 = len(ref) * k // chunks
        a1 = len(ref) * (k + 1) // chunks
        seg = ref[a0:a1]
        best = (0.0, 0.0, 0)
        lo = int(max(0, lag - span))
        hi = int(min(len(cap) - len(seg), lag + span))
        if hi <= lo:
            out.append({"chunk": k, "corr": 0.0, "lag_s": 0.0, "polarity": 1})
            continue
        a = normalize(cap[lo:hi + len(seg)])
        # windowed search using direct dot products in steps (coarse)
        b = normalize(seg)
        step = max(1, rate // 200)
        for start in range(0, int(hi - lo), int(step)):
            w = a[start:start + len(seg)]
            if len(w) != len(seg):
                break
            c = float(np.dot(w, b))
            if abs(c) > abs(best[0]):
                best = (float(c), (lo + start) / float(rate), 1 if c >= 0 else -1)
        out.append({"chunk": k, "corr": round(abs(best[0]), 4),
                    "corr_signed": round(best[0], 4),
                    "lag_s": round(best[1], 4), "polarity": best[2]})
    return {"global_corr": round(corr, 4), "global_lag_s": round(lag / rate, 4),
            "chunks": out}


def to_wav(raw_path, wav_path):
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le",
                        "-ar", "48000", "-ac", "2", "-i", raw_path, wav_path],
                       check=False)
    except FileNotFoundError:
        pass


def main():
    targets = sys.argv[1:] or sorted(CASES)
    results = {}
    csv = ["capture,slot,duration_s,active_s,peak_dbfs,rms_dbfs,"
           "clipped,dom_freq_hz,ref_duration_s,corr,corr_lag_s,chunk0,chunk1"]
    os.makedirs(os.path.join(EV, "linux/wav"), exist_ok=True)
    for name in targets:
        p = os.path.join(EV, "linux", name + ".raw")
        if not os.path.exists(p):
            print("MISS", name); continue
        x, rate = load(p)
        m = measure(x, rate)
        slot = CASES.get(name)
        row = [name, str(slot or ""), "%.3f" % m["duration_s"],
               "%.3f" % m["active_s"], "%.1f" % m["peak_dbfs"],
               "%.1f" % m["rms_dbfs"], str(m["clipped_samples"]),
               "%.1f" % m["dom_freq_hz"]]
        entry = {"file": p, "slot": slot, "metrics": m}
        if slot:
            ref = ref_wave(slot, rate)
            cc = chunk_corr(x, ref, int(rate))
            entry["ref"] = {"slot": slot, "name": SLOT[slot],
                            "duration_s": round(len(ref) / rate, 4), **cc}
            row += ["%.3f" % (len(ref) / rate), "%.4f" % cc["global_corr"],
                    "%.4f" % cc["global_lag_s"],
                    "%.3f" % cc["chunks"][0]["corr"] if cc["chunks"] else "",
                    "%.3f" % cc["chunks"][1]["corr"] if len(cc["chunks"]) > 1 else ""]
        else:
            row += ["", "", "", "", ""]
        csv.append(",".join(row))
        results[name] = entry
        to_wav(p, os.path.join(EV, "linux/wav", name + ".wav"))
        print("OK", name, "active=%.2fs peak=%.1f corr=%s" % (
            m["active_s"], m["peak_dbfs"],
            ("%.3f" % entry["ref"]["global_corr"]) if slot else "-"))
    with open(os.path.join(EV, "analysis.json"), "w") as f:
        json.dump(results, f, indent=2)
    with open(os.path.join(EV, "analysis.csv"), "w") as f:
        f.write("\n".join(csv) + "\n")
    print("wrote", os.path.join(EV, "analysis.json"))


if __name__ == "__main__":
    main()
