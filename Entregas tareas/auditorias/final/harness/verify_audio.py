#!/usr/bin/env python3
"""verify_audio.py - verificacion AUDIO real task-4.

Sesion A: QEMU -audiodev wav + -device sb16 -> F2, "audiotest", serial
AUDIO_TEST:sb16/AUDIO_TEST_DONE, captura, se cierra QEMU y se analiza el WAV.
Sesion B: sin SB16 (-machine pc,pcspk-audiodev=wav) -> "solo PC speaker",
About real, audiotest y WAV del altavoz.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS))
from vmkit import EVID, Vm, ppm_to_png  # noqa: E402
import analyze_wav  # noqa: E402


def crop_zoom(png, out, box, scale=2):
    img = ppm_to_png.read_png(png)
    c = ppm_to_png.crop(img, *box)
    ppm_to_png.write_png(out, ppm_to_png.scale_nearest(c, box[2] * scale, box[3] * scale))


def boot_audio_line(vm) -> str | None:
    for ln in vm.vm.serial_lines():
        if "[OK] Audio:" in ln or "Audio:" in ln:
            return ln
    return None


def run_sb16() -> dict:
    name = "audio-sb16"
    out = EVID / f"run-{name}"
    out.mkdir(parents=True, exist_ok=True)
    wav = EVID / "audio.wav"
    if wav.exists():
        wav.unlink()
    res = {"name": name, "steps": [], "ok": False,
           "qemu_args": ["-audiodev", f"wav,id=snd0,path={wav}",
                         "-device", "sb16,audiodev=snd0"]}
    vm = Vm(name, extra_args=res["qemu_args"])
    try:
        vm.start(gui_timeout=150)
        step = lambda n, **kw: (res["steps"].append({"step": n, **kw}),
                                print(f"[{n}] {kw}", flush=True))
        step("GUI_READY")
        res["boot_audio_line"] = boot_audio_line(vm)
        step("boot_audio_line", line=res["boot_audio_line"])
        time.sleep(0.5)
        vm.shot("01_desktop_sb16")

        # About: fila Audio con el dispositivo detectado
        vm.key("f5", settle=0.7)
        vm.wait("APP_OPEN:about", 20)
        time.sleep(0.8)
        p = vm.shot("02_about_sb16")
        crop_zoom(p, out / "02_about_sb16_row_crop.png", (145, 140, 700, 220), 2)
        vm.key("alt+w", settle=0.6)
        vm.wait("APP_CLOSE:about", 15)
        step("about_sb16_capturado")

        # Terminal: help + audiotest
        vm.key("f2", settle=0.8)
        vm.wait("APP_OPEN:terminal", 20)
        time.sleep(0.6)
        vm.type_line("help", settle=0.9)
        p = vm.shot("03_terminal_help")
        crop_zoom(p, out / "03_terminal_help_crop.png", (0, 60, 700, 500), 1)
        vm.type_line("audiotest", settle=0.3)
        got_test = False
        try:
            vm.wait("AUDIO_TEST:sb16", 20)
            got_test = True
        except Exception as exc:  # noqa: BLE001
            step("AUDIO_TEST:sb16", error=str(exc)[:300])
        res["serial_audio_test"] = [ln for ln in vm.vm.serial_lines()
                                    if ln.startswith("AUDIO_TEST")]
        step("serial_audio_test", lines=res["serial_audio_test"])
        p = vm.shot("04_terminal_audiotest")
        crop_zoom(p, out / "04_terminal_audiotest_crop.png", (0, 60, 760, 420), 1)
        # dejar terminar la secuencia de tonos
        time.sleep(3.5)
        vm.save_serial("serial.log")
        res["serial_tail"] = vm.vm.serial_lines()[-25:]
        res["fatals"] = vm.fatals()
    except Exception as exc:  # noqa: BLE001
        res["error"] = str(exc)
        res["traceback"] = traceback.format_exc()
        try:
            vm.save_serial()
        except Exception:  # noqa: BLE001
            pass
    finally:
        vm.stop()   # cierra QEMU -> finaliza cabecera WAV

    res["wav_exists"] = wav.exists()
    res["wav_size"] = wav.stat().st_size if wav.exists() else 0
    if res["wav_exists"]:
        try:
            a = analyze_wav.parse_wav(wav)
            res["wav_analysis"] = a
            res["ok"] = bool(
                a["nonsilent"] and a["duration_s"] > 0.5 and
                a["peak_dbfs"] > -30 and res.get("serial_audio_test") and
                not res.get("fatals") and
                (res.get("boot_audio_line") or "").find("SB16") >= 0)
        except Exception as exc:  # noqa: BLE001
            res["wav_error"] = str(exc)
    (out / "result.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return res


def run_pcspk() -> dict:
    name = "audio-pcspk"
    out = EVID / f"run-{name}"
    out.mkdir(parents=True, exist_ok=True)
    wav = EVID / "audio_pcspk.wav"
    if wav.exists():
        wav.unlink()
    res = {"name": name, "steps": [], "ok": False,
           "qemu_args": ["-machine", "pc,pcspk-audiodev=snd0",
                         "-audiodev", f"wav,id=snd0,path={wav}"]}
    vm = Vm(name, extra_args=res["qemu_args"])
    try:
        vm.start(gui_timeout=150)
        step = lambda n, **kw: (res["steps"].append({"step": n, **kw}),
                                print(f"[{n}] {kw}", flush=True))
        step("GUI_READY")
        res["boot_audio_line"] = boot_audio_line(vm)
        step("boot_audio_line", line=res["boot_audio_line"])
        time.sleep(0.5)
        vm.key("f5", settle=0.7)
        vm.wait("APP_OPEN:about", 20)
        time.sleep(0.8)
        p = vm.shot("01_about_pcspk")
        crop_zoom(p, out / "01_about_pcspk_row_crop.png", (145, 140, 700, 220), 2)
        vm.key("alt+w", settle=0.6)
        vm.wait("APP_CLOSE:about", 15)
        vm.key("f2", settle=0.8)
        vm.wait("APP_OPEN:terminal", 20)
        time.sleep(0.6)
        vm.type_line("audiotest", settle=0.3)
        try:
            vm.wait("AUDIO_TEST:pcspk", 20)
        except Exception as exc:  # noqa: BLE001
            step("AUDIO_TEST:pcspk", error=str(exc)[:300])
        res["serial_audio_test"] = [ln for ln in vm.vm.serial_lines()
                                    if ln.startswith("AUDIO_TEST")]
        step("serial_audio_test", lines=res["serial_audio_test"])
        vm.shot("02_terminal_audiotest_pcspk")
        time.sleep(4.0)
        vm.save_serial("serial.log")
        res["serial_tail"] = vm.vm.serial_lines()[-25:]
        res["fatals"] = vm.fatals()
    except Exception as exc:  # noqa: BLE001
        res["error"] = str(exc)
        res["traceback"] = traceback.format_exc()
        try:
            vm.save_serial()
        except Exception:  # noqa: BLE001
            pass
    finally:
        vm.stop()

    res["wav_exists"] = wav.exists()
    res["wav_size"] = wav.stat().st_size if wav.exists() else 0
    if res["wav_exists"]:
        try:
            a = analyze_wav.parse_wav(wav)
            res["wav_analysis"] = a
        except Exception as exc:  # noqa: BLE001
            res["wav_error"] = str(exc)
    detail = (res.get("boot_audio_line") or "")
    res["ok"] = bool("PC speaker" in detail and not res.get("fatals") and
                     res.get("serial_audio_test") and
                     res.get("wav_analysis", {}).get("nonsilent"))
    (out / "result.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return res


def main() -> int:
    results = {"sb16": run_sb16(), "pcspk": run_pcspk()}
    (EVID / "audio_result_all.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, r in results.items():
        print(f"== {k}: ok={r.get('ok')} audio_line={r.get('boot_audio_line')!r} "
              f"serial={r.get('serial_audio_test')} wav={r.get('wav_size')} "
              f"analysis={ {kk: r.get('wav_analysis', {}).get(kk) for kk in ('duration_s','peak_dbfs','rms_dbfs','nonsilent')} }")
    return 0 if all(r.get("ok") for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
