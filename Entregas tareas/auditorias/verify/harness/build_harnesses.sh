#!/bin/sh
# build_harnesses.sh - compile the independent verification harnesses.
# Output binaries live in audit/verify/harness/ only; project sources are
# never modified.
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
P="$ROOT/Pac-man SereOS"
H="$ROOT/audit/verify/harness"
L="$ROOT/audit/verify/evidence/logs"
mkdir -p "$L"
fail=0

echo "== harness_capture (public platform API + real platform_linux.c) =="
gcc -O2 -g -std=c99 -I"$P/include" -I"$P/src/core" -I"$P/src/render" \
    -I"$P/assets" -I"$P/assets/fonts" $(pkg-config --cflags sdl2) \
    "$H/harness_capture.c" \
    "$P/src/platform/linux/platform_linux.c" "$P/src/platform/linux/text_linux.c" \
    "$P/assets/sfx_res.c" "$P/assets/fonts/text_data.c" \
    -o "$H/harness_capture" $(pkg-config --libs sdl2) -lm \
    >"$L/build_harness_capture.log" 2>&1 \
    || { echo "FAIL harness_capture"; fail=1; }
[ -x "$H/harness_capture" ] && echo "OK harness_capture"

echo "== harness_flow_verify (real core + ld --wrap audio logging) =="
gcc -O2 -g -std=c99 -I"$P/include" -I"$P/src/core" -I"$P/src/render" \
    -I"$P/assets" -I"$P/tests" \
    "$H/harness_flow_verify.c" "$P/tests/mock_platform.c" \
    "$P/tests/legacy_font.c" "$P/tests/legacy_font_data.c" \
    "$P"/src/core/*.c "$P"/src/render/*.c "$P"/assets/*.c -lm \
    -Wl,--wrap=pac_audio_play -Wl,--wrap=pac_audio_loop \
    -Wl,--wrap=pac_audio_stop_loop -Wl,--wrap=pac_audio_stop \
    -o "$H/harness_flow_verify" \
    >"$L/build_harness_flow.log" 2>&1 \
    || { echo "FAIL harness_flow_verify"; fail=1; }
[ -x "$H/harness_flow_verify" ] && echo "OK harness_flow_verify"

exit $fail
