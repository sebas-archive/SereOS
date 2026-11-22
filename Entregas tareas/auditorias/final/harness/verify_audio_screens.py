#!/usr/bin/env python3
"""verify_audio_screens.py - capturas finales del audiotest YA terminado.

Sesion A con SB16 (audiodev none: el sonido se descarta, pero el guest detecta
la tarjeta real) y sesion B sin SB16 (solo PC speaker). Captura la salida
completa: "Tonos: 4/4", PIT, IRQ y AUDIO_TEST_DONE.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS))
from vmkit import EVID, Vm  # noqa: E402


def run(name: str, extra_args=None) -> dict:
    out = EVID / f"run-{name}"
    out.mkdir(parents=True, exist_ok=True)
    res = {"name": name, "steps": [], "ok": False}
    vm = Vm(name, extra_args=extra_args)
    try:
        vm.start(gui_timeout=150)
        time.sleep(0.4)
        vm.key("f2", settle=0.8)
        vm.wait("APP_OPEN:terminal", 20)
        time.sleep(0.5)
        vm.type_line("audio", settle=0.6)
        vm.shot("01_audio_cmd")
        vm.type_line("audiotest", settle=0.2)
        vm.wait("AUDIO_TEST_DONE", 25)
        time.sleep(0.5)
        vm.shot("02_audiotest_done")
        res["serial_audio"] = [ln for ln in vm.vm.serial_lines()
                               if ln.startswith("AUDIO")]
        res["fatals"] = vm.fatals()
        vm.save_serial()
        res["ok"] = not res["fatals"] and any(
            ln.startswith("AUDIO_TEST_DONE") for ln in res["serial_audio"])
    except Exception as exc:  # noqa: BLE001
        res["error"] = str(exc)
        res["traceback"] = traceback.format_exc()
        print("ERROR:", exc, file=sys.stderr)
        try:
            vm.save_serial()
        except Exception:  # noqa: BLE001
            pass
    finally:
        vm.stop()
    (out / "result.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return res


def main() -> int:
    r = {
        "sb16": run("audio-sb16-screen",
                    ["-audiodev", "none,id=snd0", "-device", "sb16,audiodev=snd0"]),
        "pcspk": run("audio-pcspk-screen"),
    }
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if all(v.get("ok") for v in r.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
