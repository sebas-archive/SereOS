#!/usr/bin/env python3
"""analyze_wav.py - analisis independiente de un WAV capturado de QEMU.

QEMU 11 `-audiodev wav` puede escribir los tamanos RIFF/data a 0 mientras
graba; por eso, si el tamano declarado es 0 o supera el fichero, se usa el
resto del fichero como payload. Reporta duracion, pico/RMS en dBFS, duracion
activa (bloques con senal) y silence_ratio. Uso:

    python3 analyze_wav.py captura.wav [--json salida.json]
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np


def parse_wav(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"no es WAV RIFF: {path}")
    pos = 12
    fmt = None
    payload = None
    chunks = []
    file_size = len(data)
    while pos + 8 <= file_size:
        cid = data[pos:pos + 4]
        csize = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = pos + 8
        avail = file_size - body
        take = csize if 0 < csize <= avail else avail
        chunks.append((cid.decode("latin-1"), csize, take))
        if cid == b"fmt ":
            fmt = data[body:body + take]
        elif cid == b"data":
            payload = data[body:body + take]
            if csize == 0 or csize > avail:
                # tamano sin finalizar: todo el resto del fichero es audio
                payload = data[body:]
        pos = body + take + (take & 1)
        if cid == b"data" and csize and csize <= avail:
            pos = body + (csize + (csize & 1))
    if fmt is None or payload is None or len(fmt) < 16:
        raise ValueError(f"WAV sin fmt/data utilizables: chunks={chunks}")
    audio_format, channels, rate, _bps, block_align, bits = struct.unpack(
        "<HHIIHH", fmt[:16])
    if bits == 8:
        samples = np.frombuffer(payload, dtype=np.uint8).astype(np.float64)
        samples = (samples - 128.0) / 128.0
    elif bits == 16:
        samples = np.frombuffer(payload[: len(payload) // 2 * 2],
                                dtype="<i2").astype(np.float64) / 32768.0
    elif bits == 32:
        samples = np.frombuffer(payload[: len(payload) // 4 * 4],
                                dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"bits={bits} no soportado")
    ch = max(1, channels)
    samples = samples[: (len(samples) // ch) * ch].reshape(-1, ch)
    mono = samples.mean(axis=1) if ch > 1 else samples[:, 0]
    if block_align == 0:
        block_align = max(1, ch * bits // 8)
    duration = len(mono) / float(rate)
    peak = float(np.max(np.abs(mono))) if len(mono) else 0.0
    rms = float(np.sqrt(np.mean(mono ** 2))) if len(mono) else 0.0
    # bloques de 20 ms con senal por encima de -60 dBFS
    blk = max(1, int(rate * 0.02))
    nb = max(1, len(mono) // blk)
    blocks = mono[: nb * blk].reshape(nb, blk)
    brms = np.sqrt(np.mean(blocks ** 2, axis=1))
    thr = 10 ** (-60 / 20)
    active = int(np.sum(brms > thr))
    active_ratio = active / nb
    # picos por bloques para "hay audio audible" con umbral -40 dBFS
    thr40 = 10 ** (-40 / 20)
    blocks40 = int(np.sum(brms > thr40))
    return {
        "path": str(path),
        "file_size": file_size,
        "audio_format": audio_format,
        "channels": channels,
        "rate": rate,
        "bits": bits,
        "declared_chunks": [{"id": c, "declared_size": d, "used": u}
                            for c, d, u in chunks],
        "data_bytes": len(payload),
        "frames": int(len(mono)),
        "duration_s": round(duration, 4),
        "peak": round(peak, 6),
        "peak_dbfs": round(20 * np.log10(peak) if peak > 0 else -999.0, 2),
        "rms": round(rms, 6),
        "rms_dbfs": round(20 * np.log10(rms) if rms > 0 else -999.0, 2),
        "blocks_total": nb,
        "blocks_above_minus60db": active,
        "active_ratio": round(active_ratio, 4),
        "blocks_above_minus40db": blocks40,
        "nonsilent": bool(peak > 0.002 and blocks40 >= 1),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("uso: analyze_wav.py <captura.wav> [--json salida.json]",
              file=sys.stderr)
        return 2
    res = parse_wav(Path(argv[1]))
    text = json.dumps(res, indent=2, ensure_ascii=False)
    print(text)
    if "--json" in argv:
        out = Path(argv[argv.index("--json") + 1])
        out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
