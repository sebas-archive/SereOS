#!/bin/sh
# env_check.sh - record the verification environment (reproducibility).
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$ROOT" || exit 1
OUT="$ROOT/audit/verify/evidence/env.txt"
mkdir -p "$(dirname "$OUT")"
{
  echo "# Verification environment - $(date -Is)"
  echo "## host"
  uname -a
  echo
  echo "## tools"
  for t in gcc make ffmpeg ffprobe python3 qemu-system-i386 pactl parec paplay \
           nm objdump grub-file grub-mkrescue; do
    if command -v "$t" >/dev/null 2>&1; then
      printf '%-20s %s\n' "$t" "$(command -v "$t")"
    else
      printf '%-20s MISSING\n' "$t"
    fi
  done
  echo
  echo "## versions"
  gcc --version | head -1
  make --version | head -1
  ffmpeg -version 2>/dev/null | head -1
  qemu-system-i386 --version | head -1
  python3 -c 'import numpy; print("numpy", numpy.__version__)' 2>&1
  PY=/home/t1an/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
  "$PY" -c 'import numpy, PIL; print("bundled numpy", numpy.__version__, "Pillow", PIL.__version__)' 2>&1
  pkg-config --modversion sdl2 2>&1
  echo
  echo "## audio server"
  pactl info 2>&1 | sed -n '1,14p'
  echo
  echo "## SDL2 audio drivers (probe)"
  if [ -x "$ROOT/audit/linux-audit/harness/probe_sdl" ]; then
    "$ROOT/audit/linux-audit/harness/probe_sdl" 2>&1 || true
  fi
  echo
  echo "## null sink capability"
  PREV=$(pactl get-default-sink 2>/dev/null)
  MOD=$(pactl load-module module-null-sink sink_name=verify_env_probe 2>&1) || MOD=""
  if [ -n "$MOD" ]; then
    pactl list short sinks | grep verify_env_probe
    pactl unload-module "$MOD" 2>/dev/null
    echo "null-sink: OK"
  else
    echo "null-sink: FAIL"
  fi
  echo "default sink: $PREV"
  echo
  echo "## qemu audio backends"
  qemu-system-i386 -audiodev help 2>&1 | head -20
  echo
  echo "## workspace"
  du -sh "$ROOT/audit/verify" 2>/dev/null
} > "$OUT" 2>&1
cat "$OUT"
