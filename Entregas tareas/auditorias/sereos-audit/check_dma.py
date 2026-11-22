#!/usr/bin/env python3
"""Verify every SFX chunk used by platform_sereos.c against the 8237 8-bit DMA
constraints checked by sb16.c:dma_program() (addr < 16 MiB, no 64 KiB crossing).
Reads symbols from the linked kernel (sereos.bin) with nm and the chunk tables
straight from Pac-man assets/sfx_res.c."""
import re, subprocess, sys
os_dir = sys.argv[1] if len(sys.argv) > 1 else "."
game = sys.argv[2] if len(sys.argv) > 2 else "../Pac-man SereOS"
txt = open(game + "/assets/sfx_res.c", errors="replace").read()
nm = subprocess.check_output(["nm", "-n", os_dir + "/sereos.bin"], text=True)
sym = {p[2]: int(p[0], 16) for p in (l.split() for l in nm.splitlines()) if len(p) == 3}
def arr(name):
    m = re.search(r'const [^=\n]*?' + re.escape(name) + r'\[[^=]*\]\s*=\s*\{(.*?)\};', txt, re.S)
    return m.group(1)
rows = re.findall(r'\{\s*([^}]*?)\s*\}', arr('pacasset_sfx_res_chunks'))
lrows = re.findall(r'\{\s*([^}]*?)\s*\}', arr('pacasset_sfx_res_chunk_len'))
def tok(x):
    x = x.strip()
    return None if x in ('0', '0u') else x
bad = []
print("slot ch symbol                           addr     len     low16+len   verdict")
for slot in range(16):
    row = [tok(t) for t in rows[slot].split(',')]
    lrow = [t.strip().rstrip('u') for t in lrows[slot].split(',')]
    for ch, s in enumerate(row):
        if not s:
            continue
        ln = int(lrow[ch]); a = sym.get(s)
        if a is None:
            print(f"{slot:>2} {ch} {s} MISSING"); bad.append(s); continue
        low = a & 0xFFFF
        cross = (low + ln) > 0x10000
        below = a + ln <= 0x1000000
        ok = below and not cross
        if not ok:
            bad.append((slot, ch, s, ln, a))
        print(f"{slot:>2} {ch} {s:<32} 0x{a:06x} {ln:>6} 0x{low:04x}+{ln:<6} {'OK' if ok else 'FAIL cross64K=' + str(cross) + ' <16M=' + str(below)}")
print("\nbad:", bad if bad else "none")
