#!/usr/bin/env python3
"""verify_assets.py - independent asset verification for task-9.

Checks
  1. the 11 source WAVs in /home/t1an/Descargas/Res keep their MD5 from
     audit/wav-integrity/REPORT.md (the originals must never change),
  2. assets/res_original/ contains 11 WAV byte-identical to Res,
  3. assets/sfx_res.c declares PCM in slots 2,3,4,6,7,8,9,10,12,13,15,
     LEVEL_CLEAR = intermission (5.204 s, 2 chunks), no clipping,
     loop flags 12=1, 13=1, 15=0, total bytes as expected,
  4. the embedded START clip is 46676 samples split 32768+13908.
Exit code 0 only if every check passes.  JSON on stdout.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_assets import parse_sfx_res, md5  # noqa: E402

ROOT = "/home/t1an/Descargas/sereos02"
RES = "/home/t1an/Descargas/Res"
ORIG = ROOT + "/Pac-man SereOS/assets/res_original"
SFX = ROOT + "/Pac-man SereOS/assets/sfx_res.c"

EXPECTED_MD5 = {
    "game start.wav": "07914ee70de9f5f1166ed3e9b35fc9db",
    "waka1.wav": "9e3c8eb9b4d7af04971b12c9af3e5bb4",
    "waka2.wav": "0452cd64893e3fbd3503190e9ff318c7",
    "eat ghost.wav": "61d4ded9e6249e64b735982f6ced3ec5",
    "eat fruit.wav": "514eeeeb192e8ca45ca92aa308f61f63",
    "extra life.wav": "27991f5575aec8695f0f9a68925b9df8",
    "ghost respawn.wav": "43fae1a4447f5026f8f23a9d9dd02b95",
    "hunted siren.wav": "8d5759b619045b5f6879ec83175d67a9",
    "hunter siren.wav": "d35ceeea5823f2ea9c1a3d2107826b92",
    "pacman death.wav": "b5cacf9a37e6a4fd396f6fd914168780",
    "intermission.wav": "566c0f2299b8a7ebef6372010fa6866e",
}
EXPECTED_SLOTS = [2, 3, 4, 6, 7, 8, 9, 10, 12, 13, 15]
EXPECTED_TOTAL = 184411

fails = []
info = {}


def chk(cond, name, detail=""):
    info.setdefault("checks", []).append(
        {"name": name, "ok": bool(cond), "detail": detail})
    if not cond:
        fails.append(name + (" (" + detail + ")" if detail else ""))


# 1. source originals untouched
if not os.path.isdir(RES):
    chk(False, "Res directory present", RES)
else:
    for name, want in EXPECTED_MD5.items():
        p = os.path.join(RES, name)
        got = md5(p) if os.path.exists(p) else None
        chk(got == want, "Res MD5 unchanged: " + name, str(got))
    chk(len([f for f in os.listdir(RES) if f.lower().endswith(".wav")]) == 11,
        "Res has exactly 11 WAV")

# 2. res_original byte-identical
orig_wavs = sorted(f for f in os.listdir(ORIG) if f.lower().endswith(".wav")) \
    if os.path.isdir(ORIG) else []
chk(len(orig_wavs) == 11, "res_original has 11 WAV", str(len(orig_wavs)))
for name in EXPECTED_MD5:
    a = md5(os.path.join(ORIG, name)) if os.path.exists(os.path.join(ORIG, name)) else None
    chk(a == EXPECTED_MD5[name], "res_original byte-identical: " + name, str(a))

# 3/4. embedded PCM
parsed = parse_sfx_res(SFX)
slots = parsed["slots"]
present = [s for s in sorted(slots) if slots[s]["len"] > 0]
chk(present == EXPECTED_SLOTS, "sfx_res PCM slots", str(present))
chk(parsed["total_bytes"] == EXPECTED_TOTAL,
    "sfx_res total PCM bytes", "%d (expected %d)" % (parsed["total_bytes"], EXPECTED_TOTAL))
chk(parsed["rate"] == 11025, "sfx_res rate", str(parsed["rate"]))

s2 = slots.get(2, {})
chk(s2.get("len") == 46676, "START len 46676", str(s2.get("len")))
chk([len(c) for c in s2.get("chunks", [])] == [32768, 13908],
    "START chunks 32768+13908", str([len(c) for c in s2.get("chunks", [])]))

s10 = slots.get(10, {})
chk(s10.get("len") == 57377, "LEVEL_CLEAR = intermission 57377 samples",
    str(s10.get("len")))
chk([len(c) for c in s10.get("chunks", [])] == [32768, 24609],
    "LEVEL_CLEAR chunks 32768+24609", str([len(c) for c in s10.get("chunks", [])]))

chk(parsed["loop"].get(12) == 1 and parsed["loop"].get(13) == 1,
    "loop flags 12/13 = 1", str({12: parsed["loop"].get(12), 13: parsed["loop"].get(13)}))
chk(parsed["loop"].get(15) == 0,
    "loop flag 15 = 0 (one-shot; loop only via pac_audio_loop)",
    str(parsed["loop"].get(15)))

clip_total = 0
for slot in EXPECTED_SLOTS:
    d = slots[slot]["data"]
    clip_total += int(((d == 0) | (d == 255)).sum())
chk(clip_total == 0, "no clipped samples in embedded PCM", str(clip_total))

# expected durations (ms) for the report table
durations = {slot: round(slots[slot]["len"] * 1000.0 / 11025.0, 3)
             for slot in EXPECTED_SLOTS}
info["durations_ms"] = durations

info["fails"] = fails
info["ok"] = not fails
print(json.dumps(info, indent=2))
sys.exit(0 if not fails else 1)
