#!/usr/bin/env python3
"""Verificacion de integracion sobre la ISO final del arbol compartido."""
import json, sys, time
from pathlib import Path
ROOT = Path("/home/t1an/Descargas/sereos02")
OS = ROOT / "sistema operativo"
OUT = ROOT / "build/qa_audio/evidence"
ISO = ROOT / "build/qa_audio/shared_iso/sereos.iso"
sys.path.insert(0, str(OS / "tools"))
sys.path.insert(0, str(ROOT / "build/qa_audio"))
from qemu_ctrl import QemuController
import verify_audio as v

wav = OUT / "shared_sb16.wav"
try: wav.unlink()
except FileNotFoundError: pass
vm = QemuController(ISO, OUT/"vm_shared", use_kvm=False,
                    extra_args=["-audiodev", f"wav,id=snd0,path={wav}",
                                "-device", "sb16,audiodev=snd0"])
res = {"iso": str(ISO), "iso_md5_note": "copia congelada de sistema operativo/sereos.iso",
       "checks": {}, "wav_analysis": None}
try:
    vm.start()
    vm.wait_marker("GUI_READY", 240)
    since = vm.marker_offset()
    vm.press("f2")
    vm.wait_marker_prefix("APP_OPEN:terminal", 60, since)
    time.sleep(1.0)
    t0 = vm.marker_offset()
    vm.type_line("audiotest", delay=0.08, settle=0.8)
    res["checks"]["AUDIO_TEST"] = vm.wait_marker_prefix("AUDIO_TEST:", 90, t0).line
    res["checks"]["AUDIO_DETAIL"] = vm.wait_marker_prefix("AUDIO_DETAIL:", 30, t0).line
    res["checks"]["AUDIO_TEST_DONE"] = vm.wait_marker_prefix("AUDIO_TEST_DONE", 90, t0).line
    time.sleep(0.5)
    vm.screendump(OUT/"terminal_audiotest_shared.ppm")
    # cerrar terminal y abrir Acerca de
    vm.sendkey("ctrl+w")
    time.sleep(1.5)
    since2 = vm.marker_offset()
    vm.press("f5")
    vm.wait_marker_prefix("APP_OPEN:about", 60, since2)
    time.sleep(2.5)
    vm.screendump(OUT/"about_shared.ppm")
    res["checks"]["boot_audio"] = next((l for l in vm.serial_text().splitlines()
                                        if l.startswith("[OK] Audio:")), None)
    res["checks"]["fatal_markers"] = vm.fatal_markers()
    res["serial_lines"] = vm.serial_text().splitlines()
finally:
    vm.stop()
if wav.exists():
    res["wav_analysis"] = v.analyze(wav, expected_hz=[440,660,880,1320])
(OUT/"results_shared.json").write_text(json.dumps(res, indent=2, default=str))
print(json.dumps({k: res["checks"][k] for k in res["checks"] if k != "fatal_markers"}, indent=1))
print("fatal:", res["checks"]["fatal_markers"])
wa = res["wav_analysis"]
print("wav:", {x: wa[x] for x in ("seconds_captured","peak_dbfs","rms_dbfs","distinct_freqs","all_expected_found","non_silent")} if wa else None)
