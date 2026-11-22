#!/bin/sh
# capture_sereos.sh - real native audio capture of PAC-MAN SereOS in QEMU.
#
# Two independent capture backends are supported:
#   pa  : QEMU -audiodev pa routed to a PulseAudio/PipeWire null sink and
#         recorded with parec (recommended; QEMU 11.1.3 writes broken RIFF
#         sizes with -audiodev wav, see audit/sereos-audit/REPORT.md).
#   wav : QEMU -audiodev wav file (cross-check; header sizes are zero but the
#         PCM payload is valid).
#
# Usage: capture_sereos.sh <pa|wav> <label> [seconds]
# Env: SYMBOLS="g_pcm_chunk,g_pcm_active,..." to sample guest globals.
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$ROOT" || exit 1
MODEV=${1:-pa}
LABEL=${2:-run}
DUR=${3:-50}
EV="$ROOT/audit/verify/evidence/sereos"
LOGD="$ROOT/audit/verify/evidence/logs"
ISO="$ROOT/sistema operativo/sereos.iso"
BIN="$ROOT/sistema operativo/sereos.bin"
H="$ROOT/audit/verify/harness"
mkdir -p "$EV" "$LOGD"

[ -f "$ISO" ] || { echo "ERROR: $ISO missing (make -C 'sistema operativo')" >&2; exit 1; }

SERIAL="$LOGD/sereos_${LABEL}.serial"
SOCK="$ROOT/audit/verify/evidence/tmp/sereos_${LABEL}.sock"
mkdir -p "$(dirname "$SOCK")"
rm -f "$SOCK" "$SERIAL"

if [ "$MODEV" = "pa" ]; then
    SINK=verify_null
    PREV=$(pactl get-default-sink)
    MOD=$(pactl load-module module-null-sink sink_name=$SINK \
          sink_properties=device.description=VerifyNull) || exit 1
    cleanup() {
        pactl set-default-sink "$PREV" >/dev/null 2>&1
        pactl unload-module "$MOD" >/dev/null 2>&1
    }
    trap cleanup EXIT INT TERM
    pactl set-default-sink "$SINK" || exit 1
    (
      timeout $((DUR + 8)) parec -d "$SINK.monitor" --raw --rate=48000 \
          --channels=2 --format=s16le > "$LOGD/sereos_${LABEL}.raw" 2>/dev/null
    ) &
    PAREC=$!
    AUDIO="-audiodev pa,id=snd0"
else
    AUDIO="-audiodev wav,id=snd0,path=$LOGD/sereos_${LABEL}.wav"
fi

qemu-system-i386 -m 256M -vga std -display none -boot d \
  -cdrom "$ISO" -serial file:"$SERIAL" \
  $AUDIO -device sb16,audiodev=snd0 -machine pcspk-audiodev=snd0 \
  -no-reboot -qmp unix:"$SOCK",server=on,wait=off \
  >"$LOGD/qemu_${LABEL}.log" 2>&1 &
QPID=$!
sleep 1.2
SYMS=${SYMBOLS:-}
python3 "$H/sereos_scenario.py" --sock "$SOCK" --bin "$BIN" \
    --symbols "$SYMS" --total "$DUR" \
    >"$LOGD/sereos_${LABEL}.probe.txt" 2>>"$LOGD/sereos_${LABEL}.probe.err"
sleep 1
kill $QPID 2>/dev/null
wait $QPID 2>/dev/null
[ "$MODEV" = "pa" ] && wait $PAREC 2>/dev/null
echo "=== serial markers ==="
tr -d '\r' < "$SERIAL" 2>/dev/null | grep -E "SEREOS_BOOT_OK|GUI_READY|APP_OPEN|GAME_MENU|LEVEL_START|GAME_START|PAC_DEATH|GAME_OVER|PAC_STATS" | head -30
echo "=== capture ==="
ls -l "$LOGD/sereos_${LABEL}".raw "$LOGD/sereos_${LABEL}".wav 2>/dev/null
echo "=== probe ==="
head -5 "$LOGD/sereos_${LABEL}.probe.txt" 2>/dev/null
echo "done: $LOGD"
