#!/usr/bin/env python3
"""parse_assets.py - Independent parser for Pac-man SereOS PCM assets.

Reads assets/sfx_res.c (generated file) and extracts every `pacasset_pcm_*`
array plus the slot/chunk/loop tables.  It does NOT import or run any project
code: it only parses the C source text, so it can be used to independently
check what the fixers' generator produced.

Public API:
    parse_sfx_res(path) -> dict with:
        arrays:  {name: np.uint8[...]}
        slots:   {slot: {"len":.., "data": np.ndarray, "chunks":[...]}}
        loop:    {slot: 0/1}
        rate:    int
        total_bytes: int
    inventory(assets_dir) -> basic listing of source WAVs.

CLI:
    python3 parse_assets.py <path/to/sfx_res.c> [--json out.json]
"""
import json
import os
import re
import sys

import numpy as np

ARRAY_RE = re.compile(r"const\s+uint8_t\s+(pacasset_\w+)\s*\[\s*\]\s*=\s*\{(.*?)\};", re.S)
BYTE_RE = re.compile(r"0x([0-9a-fA-F]{2})|(\d+)")
SLOT_RE = re.compile(r"\[\s*(\d+)\s*\]\s*=\s*\{\s*(\w+)\s*,\s*(\d+)u?\s*\}")


def _parse_arrays(text):
    arrays = {}
    for m in ARRAY_RE.finditer(text):
        name = m.group(1)
        body = m.group(2)
        vals = []
        for bm in BYTE_RE.finditer(body):
            if bm.group(1) is not None:
                vals.append(int(bm.group(1), 16))
            else:
                vals.append(int(bm.group(2)))
        arrays[name] = np.asarray(vals, dtype=np.uint8)
    return arrays


def parse_sfx_res(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    arrays = _parse_arrays(text)

    # main slot table
    slots = {}
    m = re.search(r"pacasset_sfx_res\s*\[[^\]]*\]\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        raise SystemExit("cannot find pacasset_sfx_res[] table")
    for sm in SLOT_RE.finditer(m.group(1)):
        slot = int(sm.group(1))
        arr = sm.group(2)
        length = int(sm.group(3))
        if arr in arrays:
            data = arrays[arr][:length]
        else:
            data = np.zeros(length, dtype=np.uint8)
        slots[slot] = {"len": length, "data": data, "chunks": [], "table_array": arr}

    # chunk table: { ptr0, ptr1 }
    m = re.search(r"pacasset_sfx_res_chunks\s*\[[^\]]*\]\[[^\]]*\]\s*=\s*\{(.*?)\};", text, re.S)
    chunk_slot_re = re.compile(r"\{\s*([^}]*?)\}", re.S)
    if m:
        slot_i = -1
        for cm in chunk_slot_re.finditer(m.group(1)):
            slot_i += 1
            names = re.findall(r"pacasset_\w+", cm.group(1))
            if slot_i in slots:
                slots[slot_i]["chunks"] = [
                    arrays[n] if n in arrays else None for n in names if n != "0"
                ]

    # rebuild full audio from chunks where available (START/LEVEL_CLEAR)
    for slot, s_ in slots.items():
        ch = [c for c in s_["chunks"] if c is not None and len(c)]
        if ch:
            s_["data"] = np.concatenate(ch)
            if s_["len"] != len(s_["data"]):
                s_["len_note"] = "declared %d != concatenated %d" % (s_["len"], len(s_["data"]))

    # loop flags
    loop = {}
    m = re.search(r"pacasset_sfx_res_loop\s*\[[^\]]*\]\s*=\s*\{(.*?)\};", text, re.S)
    if m:
        nums = [int(x) for x in re.findall(r"(?<![0-9.])([0-9]+)(?:u)?(?=[,\s}])", m.group(1))]
        for i, v in enumerate(nums[:16]):
            loop[i] = v

    rate_m = re.search(r"pacasset_sfx_res_rate\s*=\s*(\d+)", text)
    rate = int(rate_m.group(1)) if rate_m else 11025
    tot_m = re.search(r"pacasset_sfx_res_total_bytes\s*=\s*(\d+)", text)
    total = int(tot_m.group(1)) if tot_m else sum(s["len"] for s in slots.values())

    return {"arrays": arrays, "slots": slots, "loop": loop,
            "rate": rate, "total_bytes": total, "text": text}


SLOT_NAMES = {1: "MENU", 2: "START", 3: "WAKA1", 4: "WAKA2", 5: "POWER",
              6: "EAT_GHOST", 7: "EAT_FRUIT", 8: "DEATH", 9: "EXTRA_LIFE",
              10: "LEVEL_CLEAR", 11: "GAME_OVER", 12: "SIREN_CHASE",
              13: "SIREN_HUNT", 14: "SIREN_FRIGHT", 15: "GHOST_RESPAWN"}


def slot_report(parsed):
    rows = []
    rate = parsed["rate"]
    for slot in sorted(parsed["slots"]):
        s = parsed["slots"][slot]
        d = s["data"]
        n = len(d)
        row = {
            "slot": slot,
            "name": SLOT_NAMES.get(slot, "?"),
            "len": s["len"],
            "pcm_samples": n,
            "ms": round(n * 1000.0 / rate, 3) if rate else 0,
            "chunks": [len(c) for c in s["chunks"]],
            "chunk_count": len([c for c in s["chunks"] if c is not None and len(c)]),
            "loop": parsed["loop"].get(slot, 0),
            "zero": bool(n == 0),
        }
        if n:
            row["peak"] = int(d.max())
            row["min"] = int(d.min())
            row["peak_dbfs"] = round(20 * np.log10(max(1, int(d.max()) - 128) / 128.0), 3)
            row["clipped_0_255"] = int(np.sum((d == 0) | (d == 255)))
            row["dc_lsb"] = round(float(d.astype(np.float64).mean() - 128.0), 3)
            row["rms_dbfs"] = round(
                20 * np.log10(max(1e-9, float(np.sqrt(np.mean((d.astype(np.float64) - 128.0) ** 2))) / 128.0)), 3)
        rows.append(row)
    return rows


def inventory(assets_dir):
    """List the WAV files actually present in a directory (res_original etc.)."""
    out = []
    for name in sorted(os.listdir(assets_dir)):
        if name.lower().endswith(".wav"):
            p = os.path.join(assets_dir, name)
            out.append({"name": name, "bytes": os.path.getsize(p),
                        "md5": md5(p), "sha256": sha256(p)})
    return out


def md5(p):
    import hashlib
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha256(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    parsed = parse_sfx_res(sys.argv[1])
    rows = slot_report(parsed)
    print(json.dumps({"rate": parsed["rate"], "total_bytes": parsed["total_bytes"],
                      "slots": rows}, indent=2))
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        with open(out, "w") as f:
            json.dump({"rate": parsed["rate"], "total_bytes": parsed["total_bytes"],
                       "slots": rows}, f, indent=2)
        print("wrote", out, file=sys.stderr)
