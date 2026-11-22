#!/usr/bin/env python3
"""Sonda: arranca la VM, F2, ejecuta un comando de SereOS y captura el monitor
del sink por defecto mientras suena. Usada para diagnosticar el tono.

Uso: python3 probe_beep.py "beep 1000 1000" [segundos_grabacion] [etiqueta]
"""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_test import DEFAULT_SINK, MONITOR, analyze, poweroff_vm, start_vm  # noqa: E402
from vbox_ctrl import OUT, key, marker_offset, screenshot, type_text, vbox  # noqa: E402
from vbox_ctrl import wait_marker  # noqa: E402

cmd = sys.argv[1] if len(sys.argv) > 1 else "beep 1000 1000"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
tag = sys.argv[3] if len(sys.argv) > 3 else "probe"
wav = OUT / f"{tag}.wav"


def main() -> int:
    poweroff_vm()
    start_vm()
    key("f2")
    wait_marker("APP_OPEN:terminal", 60)
    time.sleep(1.0)
    rec = subprocess.Popen(
        ["pw-record", f"--target={MONITOR}", "--rate", "48000",
         "--channels", "2", "--format", "s16", str(wav)],
        stdout=open(OUT / f"{tag}_pwrecord.log", "w"), stderr=subprocess.STDOUT)
    t0 = time.time()
    time.sleep(1.5)
    since = marker_offset()
    type_text(cmd)
    key("enter")
    # esperar al prompt / fin: los comandos de audio no marcan nada salvo audiotest
    time.sleep(max(0.0, secs - (time.time() - t0)))
    if rec.poll() is None:
        rec.send_signal(signal.SIGINT)
    try:
        rec.wait(timeout=5)
    except subprocess.TimeoutExpired:
        rec.kill()
    screenshot(OUT / f"{tag}.png")
    si = subprocess.run(["pactl", "list", "short", "sink-inputs"],
                        capture_output=True, text=True).stdout
    vbox("showvminfo", "SereOS Audio", "--machinereadable")
    poweroff_vm()
    res = {"cmd": cmd, "sink_inputs_during": si, "wav": str(wav)}
    if wav.exists() and wav.stat().st_size > 1000:
        res["analysis"] = analyze(wav)
    (OUT / f"{tag}_result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
