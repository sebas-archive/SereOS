#!/bin/sh
# verify_static.sh - static checks of task-9 (builds, tests, assets).
# Everything is logged under audit/verify/evidence/logs/.
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$ROOT" || exit 1
E="$ROOT/audit/verify/evidence"
L="$E/logs"
P="$ROOT/Pac-man SereOS"
SO="$ROOT/sistema operativo"
mkdir -p "$L" "$E/tmp"
fail=0

record() { echo "$1" | tee -a "$L/static_summary.txt"; }
check() { # check <name> <0-ok>
    if [ "$2" -eq 0 ]; then record "PASS  $1"; else record "FAIL  $1"; fail=1; fi
}

echo "===== 1. clean builds =====" | tee "$L/static_summary.txt"
# -- Linux game (clean build)
( cd "$P" && make clean ) >"$L/make_clean.log" 2>&1
( cd "$P" && make linux ) >"$L/make_linux.log" 2>&1
check "make linux (clean build)" $?
grep -icE "warning:" "$L/make_linux.log" > "$E/tmp/warn_linux.txt"
record "INFO  make linux warnings: $(cat "$E/tmp/warn_linux.txt")"

# -- SereOS freestanding library
( cd "$P" && make sereos ) >"$L/make_sereos_lib.log" 2>&1
check "make sereos (libpacman.a)" $?

# -- Native OS + ISO
( cd "$SO" && make -j"$(nproc)" ) >"$L/make_sereos_iso.log" 2>&1
check "make -C 'sistema operativo' (ISO)" $?
[ -f "$SO/sereos.iso" ] && record "INFO  sereos.iso $(stat -c%s "$SO/sereos.iso") bytes"

# -- unit tests / smoke
( cd "$P" && make test ) >"$L/make_test.log" 2>&1
check "make test" $?
tail -5 "$L/make_test.log" >> "$L/static_summary.txt"

echo "===== 2. asset integrity =====" >> "$L/static_summary.txt"
python3 "$ROOT/audit/verify/harness/verify_assets.py" \
    >"$E/tmp/assets_check.json" 2>"$L/verify_assets.err"
check "assets check" $?
cat "$E/tmp/assets_check.json" >> "$L/static_summary.txt"

echo "===== 3. generator determinism =====" >> "$L/static_summary.txt"
PY=/home/t1an/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
rm -rf "$E/tmp/regen"
"$PY" "$P/tools/gen_pacman_res_assets.py" --out "$E/tmp/regen" \
    >"$L/regen.log" 2>&1
if cmp -s "$E/tmp/regen/assets/sfx_res.c" "$P/assets/sfx_res.c" && \
   cmp -s "$E/tmp/regen/assets/sfx_res.h" "$P/assets/sfx_res.h"; then
    record "PASS  generator deterministic (sfx_res.c/h byte-identical)"
else
    record "FAIL  generator deterministic (sfx_res.c/h differ)"; fail=1
fi

echo "===== 4. no scratch binaries in sources =====" >> "$L/static_summary.txt"
SCRATCH=$(find "$P/src" "$P/include" "$P/assets" "$SO/audio" "$SO/drivers" \
    -maxdepth 2 \( -name "*.o" -o -name "*.raw" -o -name "*.wav" -o -name "*.tmp" \
    -o -name "a.out" \) 2>/dev/null | grep -v res_original)
if [ -z "$SCRATCH" ]; then
    record "PASS  no scratch binaries inside sources"
else
    record "FAIL  scratch files in sources:"; echo "$SCRATCH" >> "$L/static_summary.txt"; fail=1
fi

record "===== RESULT: $fail failures ====="
exit $fail
