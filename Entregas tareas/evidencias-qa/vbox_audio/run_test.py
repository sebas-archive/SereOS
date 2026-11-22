#!/usr/bin/env python3
"""Prueba de audio SB16 de SereOS en VirtualBox 7.2 (task-1).

Flujo:
 1. apaga la VM si estaba encendida y borra el log serie;
 2. arranca "SereOS Audio" en headless y espera GUI_READY por COM1;
 3. F2 -> espera APP_OPEN:terminal;
 4. lanza pw-record sobre el monitor del sink por defecto del host;
 5. escribe `audiotest` + Enter con keyboardputscancode;
 6. espera AUDIO_TEST / AUDIO_DETAIL / AUDIO_TEST_DONE;
 7. para la grabacion, guarda logs/salidas y analiza el WAV;
 8. apaga la VM.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vbox_ctrl import (  # noqa: E402
    OUT, SERIAL, VM, key, marker_offset, screenshot, serial_text,
    type_text, vbox, wait_marker,
)
from analyze_audio import analyze  # noqa: E402

TAG = os.environ.get("VBOX_AUDIO_TAG", "").strip()
SUF = f"_{TAG}" if TAG else ""

DEFAULT_SINK = subprocess.run(
    ["pactl", "get-default-sink"], capture_output=True, text=True, check=True
).stdout.strip()
MONITOR = f"{DEFAULT_SINK}.monitor"
WAV = OUT / f"vbox_audiotest{SUF}.wav"
REC_SECONDS = 14


def vm_state() -> str:
    out = vbox("showvminfo", VM, "--machinereadable").stdout
    for line in out.splitlines():
        if line.startswith("VMState="):
            return line.split("=", 1)[1].strip('"')
    return "unknown"


def poweroff_vm(timeout: float = 20.0) -> None:
    state = vm_state()
    if state != "running":
        print(f"VM estado={state}, no hace falta apagar")
        return
    vbox("controlvm", VM, "poweroff", check=False)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if vm_state() != "running":
            print("VM apagada")
            return
        time.sleep(0.3)
    raise RuntimeError("la VM no se apago")


def start_vm() -> None:
    try:
        SERIAL.unlink()
    except FileNotFoundError:
        pass
    vbox("startvm", VM, "--type", "headless")
    off, line = wait_marker("GUI_READY", 180)
    print(f"GUI_READY tras {off} bytes de serie: {line}")


def record_and_run() -> dict:
    since = marker_offset()
    print("F2 -> Terminal")
    key("f2")
    off, line = wait_marker("APP_OPEN:terminal", 60, since)
    print(f"  {line}")
    time.sleep(0.8)

    for f in (WAV, OUT / f"pw-record{SUF}.log"):
        try:
            Path(f).unlink()
        except FileNotFoundError:
            pass
    rec_log = open(OUT / f"pw-record{SUF}.log", "w")
    print(f"grabando {REC_SECONDS}s del monitor {MONITOR}")
    rec_start = time.time()
    rec = subprocess.Popen(
        ["pw-record", f"--target={MONITOR}", "--rate", "48000",
         "--channels", "2", "--format", "s16", str(WAV)],
        stdout=rec_log, stderr=subprocess.STDOUT,
    )
    time.sleep(2.0)

    since = marker_offset()
    print("escribiendo 'audiotest' + Enter")
    type_text("audiotest")
    key("enter")
    res = {}
    for marker in ("AUDIO_TEST:", "AUDIO_DETAIL:", "AUDIO_TEST_DONE"):
        off, line = wait_marker(marker, 90, since)
        res[marker] = line
        print(f"  {line}")

    # deja terminar la cola de audio y el buffering de PulseAudio/VBox
    remaining = REC_SECONDS - (time.time() - rec_start)
    if remaining > 0:
        time.sleep(remaining)
    if rec.poll() is None:
        rec.send_signal(signal.SIGINT)
    try:
        rec.wait(timeout=5)
    except subprocess.TimeoutExpired:
        rec.kill()
        rec.wait()
    rec_log.close()

    time.sleep(0.5)
    shot = OUT / f"vbox_terminal_audiotest{SUF}.png"
    screenshot(shot)
    res["screenshot"] = str(shot)
    # evidencia del comando `audio` (backend/detalle) en la Terminal
    type_text("audio")
    key("enter")
    time.sleep(1.0)
    shot2 = OUT / f"vbox_terminal_audio{SUF}.png"
    screenshot(shot2)
    res["screenshot_audio"] = str(shot2)
    return res


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    poweroff_vm()
    start_vm()
    res = record_and_run()
    # log serie completo del arranque + prueba
    (OUT / f"serial_full{SUF}.log").write_text(serial_text())
    (OUT / f"showvminfo_machinereadable{SUF}.txt").write_text(
        vbox("showvminfo", VM, "--machinereadable").stdout)
    (OUT / f"showvminfo{SUF}.txt").write_text(vbox("showvminfo", VM).stdout)
    poweroff_vm()
    if WAV.exists() and WAV.stat().st_size > 1000:
        res["wav_analysis"] = analyze(WAV)
    else:
        res["wav_analysis"] = None
    (OUT / f"run_result{SUF}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
