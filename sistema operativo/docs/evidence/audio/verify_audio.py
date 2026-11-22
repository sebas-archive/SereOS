#!/usr/bin/env python3
"""Verificacion real del audio de SereOS en QEMU (task-2).

Escenarios:
  A) SB16 (-audiodev wav + -device sb16): arranca, F2 Terminal, `audiotest`,
     captura WAV y comprueba que hay senal PCM no silenciosa en 440/660/880/1320 Hz.
  B) Sin SB16 pero con PC speaker enrutado (-machine pcspk-audiodev=wav):
     `audiotest` debe usar el fallback pcspk, con audio_detail "solo PC speaker"
     y el PIT canal 2 generando tonos (captura WAV del pcspk).
  C) Sin ningun dispositivo de audio: fallback silencioso pero sin crash y
     audio_detail correcto.

Uso: python3 build/qa_audio/verify_audio.py [A|B|C]
"""
import json
import os
import sys
import time
import wave
from pathlib import Path

ROOT = Path("/home/t1an/Descargas/sereos02")
OS = ROOT / "sistema operativo"
TREE = ROOT / "build/qa_audio/tree/sistema operativo"
OUT = ROOT / "build/qa_audio/evidence"
sys.path.insert(0, str(OS / "tools"))

from qemu_ctrl import QemuController, MarkerTimeout, QemuError  # noqa: E402

ISO = Path(os.environ.get("SEREOS_ISO",
                        OS / "sereos.iso" if (OS / "sereos.iso").exists()
                        else TREE / "sereos.iso"))


def read_wav_pcm(path: Path):
    """QEMU deja los tamanos RIFF a 0 si se cierra sin finalizar: se parsean
    las chunks y se devuelven las muestras crudas + formato."""
    data = path.read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE", "no es un WAV RIFF"
    pos, fmt, raw = 12, None, b""
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        body = data[pos + 8:]
        if cid == b"fmt ":
            fmt = body[:size]
        elif cid == b"data":
            raw = body if size == 0 or size > len(body) else body[:size]
            break
        pos += 8 + size + (size & 1)
    assert fmt is not None, "sin chunk fmt"
    nch = int.from_bytes(fmt[2:4], "little")
    rate = int.from_bytes(fmt[4:8], "little")
    bits = int.from_bytes(fmt[14:16], "little")
    return raw, nch, rate, bits


def analyze(path: Path, expected_hz=None):
    import numpy as np
    raw, nch, rate, bits = read_wav_pcm(path)
    assert bits == 16, f"se esperaba PCM 16 bits, hay {bits}"
    a = np.frombuffer(raw, dtype="<i2")
    if nch > 1:
        a = a.reshape(-1, nch)
        mono = a.mean(axis=1)
    else:
        mono = a.astype(np.float64)
    n = len(mono)
    peak = float(np.abs(mono).max()) if n else 0.0
    rms = float(np.sqrt((mono.astype(np.float64) ** 2).mean())) if n else 0.0
    active = mono[np.abs(mono) > 200]
    res = {
        "file": str(path), "rate": rate, "channels": nch, "bits": bits,
        "frames": n, "seconds_captured": round(n / rate, 3) if rate else 0,
        "peak": round(peak, 1), "rms_full": round(rms, 1),
        "peak_dbfs": round(20 * np.log10(max(peak, 1) / 32768.0), 1),
        "rms_dbfs": round(20 * np.log10(max(rms, 1) / 32768.0), 1),
        "active_frames": int(active.size),
        "active_seconds": round(active.size / rate, 3) if rate else 0,
    }
    # segmentos activos (>=40 ms) y frecuencia dominante de cada uno
    win = max(1, rate // 100)
    env = np.abs(mono)
    segs, in_seg, start = [], False, 0
    for i in range(0, n, win):
        loud = env[i:i + win].max() > 200 if i < n else False
        if loud and not in_seg:
            in_seg, start = True, i
        elif not loud and in_seg:
            in_seg = False
            if i - start >= rate * 0.04:
                segs.append((start, min(i, n)))
    if in_seg and n - start >= rate * 0.04:
        segs.append((start, n))
    # ventanas deslizantes de 120 ms: QEMU concatena los bloques activos sin
    # silencios, asi que varios tonos seguidos forman un solo segmento
    tones = []
    wl = max(64, int(rate * 0.12))
    hop = max(1, wl // 2)
    for s in range(0, max(1, n - wl), hop):
        seg = mono[s:s + wl]
        if float(np.abs(seg).max()) <= 200:
            continue
        seg = seg - seg.mean()
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        freqs = np.fft.rfftfreq(len(seg), 1.0 / rate)
        if len(spec) < 3:
            continue
        k = int(np.argmax(spec[1:]) + 1)
        tones.append({
            "start_s": round(s / rate, 3), "dur_s": round(wl / rate, 3),
            "freq_hz": round(float(freqs[k]), 1),
            "peak": int(np.abs(seg).max()),
        })
    res["windows"] = len(tones)
    res["tones"] = tones
    res["distinct_freqs"] = sorted({round(t["freq_hz"]) for t in tones})
    if expected_hz:
        hits = []
        for want in expected_hz:
            hit = min(tones, key=lambda t: abs(t["freq_hz"] - want)) if tones else None
            ok = bool(hit and abs(hit["freq_hz"] - want) / want < 0.10)
            hits.append({"want_hz": want,
                         "got_hz": hit["freq_hz"] if hit else None, "ok": ok})
        res["expected"] = hits
        res["all_expected_found"] = all(h["ok"] for h in hits)
    res["non_silent"] = bool(peak > 1000 and rms > 300 and res["active_seconds"] > 0.2)
    return res


def run_scenario(tag: str, extra_args, wav_path=None, want_audio=True):
    wd = OUT / f"vm_{tag}"
    for p in (wd / "serial.log",):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    if wav_path:
        try:
            Path(wav_path).unlink()
        except FileNotFoundError:
            pass
    vm = QemuController(ISO, wd, use_kvm=False, extra_args=extra_args)
    result = {"scenario": tag, "cmd": None, "serial": None, "wav_analysis": None,
              "checks": {}}
    try:
        vm.start()
        result["cmd"] = " ".join(vm.cmdline)
        vm.wait_marker("GUI_READY", 240)
        since = vm.marker_offset()
        vm.press("f2")
        vm.wait_marker_prefix("APP_OPEN:terminal", 40, since)
        time.sleep(1.0)
        test_since = vm.marker_offset()
        vm.type_line("audiotest", delay=0.08, settle=0.8)
        hit = vm.wait_marker_prefix("AUDIO_TEST:", 90, test_since)
        result["checks"]["serial_AUDIO_TEST"] = hit.line
        done = vm.wait_marker_prefix("AUDIO_TEST_DONE", 90, test_since)
        result["checks"]["serial_AUDIO_TEST_DONE"] = done.line
        try:
            det = vm.wait_marker_prefix("AUDIO_DETAIL:", 10, test_since)
            result["checks"]["serial_AUDIO_DETAIL"] = det.line
        except MarkerTimeout:
            result["checks"]["serial_AUDIO_DETAIL"] = None
        time.sleep(0.5)
        shot = vm.screendump(OUT / f"terminal_audiotest_{tag}.ppm")
        result["screenshot"] = str(shot)
        time.sleep(2.0)
        fatal = vm.fatal_markers()
        result["checks"]["fatal_markers"] = fatal
        result["serial"] = vm.serial_text()
    finally:
        vm.stop()
    if wav_path and Path(wav_path).exists() and Path(wav_path).stat().st_size > 44:
        result["wav_analysis"] = analyze(Path(wav_path),
                                         expected_hz=[440, 660, 880, 1320])
    return result


def main(which):
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    if "A" in which:
        results["A_sb16"] = run_scenario(
            "A_sb16",
            ["-audiodev", f"wav,id=snd0,path={OUT/'A_sb16.wav'}",
             "-device", "sb16,audiodev=snd0"],
            wav_path=OUT / "A_sb16.wav")
    if "B" in which:
        results["B_pcspk"] = run_scenario(
            "B_pcspk",
            ["-audiodev", f"wav,id=snd0,path={OUT/'B_pcspk.wav'}",
             "-machine", "pc,pcspk-audiodev=snd0"],
            wav_path=OUT / "B_pcspk.wav")
    if "C" in which:
        results["C_noaudio"] = run_scenario("C_noaudio", [])
    (OUT / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ABC")
