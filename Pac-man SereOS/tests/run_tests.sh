#!/bin/sh
# tests/run_tests.sh - pruebas del componente PAC-MAN SereOS
#
#   1. harness de core con plataforma mock (framebuffer en memoria)
#   2. smoke Linux con SDL_VIDEODRIVER=dummy
#
# Requiere build/linux/pacman-sereos (lo compila el target `test`).
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT" || exit 1
fail=0

echo "== harness de core =="
if [ -f tests/core_tests.c ] && [ -f tests/mock_platform.c ]; then
    mkdir -p build/tests
    if cc -O2 -g -Wall -Wextra -Wno-unused-parameter -std=c99 \
          -Iinclude -Isrc/core -Isrc/render -Iassets -Itests \
          -o build/tests/core_tests \
          tests/core_tests.c tests/mock_platform.c \
          tests/legacy_font.c tests/legacy_font_data.c \
          $(ls src/core/*.c 2>/dev/null) $(ls src/render/*.c 2>/dev/null) \
          $(ls assets/*.c 2>/dev/null) -lm; then
        if ./build/tests/core_tests; then
            echo "[OK] harness de core"
        else
            echo "[FAIL] harness de core"; fail=1
        fi
    else
        echo "[FAIL] compilacion del harness"; fail=1
    fi
else
    echo "[PENDIENTE] tests/core_tests.c y tests/mock_platform.c"
    fail=1
fi

echo "== smoke Linux (SDL dummy: menu/play/pause/gameover/victory) =="
if [ -x build/pacman-sereos ]; then
    mkdir -p build/smoke
    for scene in attract menu settings play pause gameover victory; do
        SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
            ./build/pacman-sereos --smoke 4 --scene "$scene" \
            --screenshot "build/smoke/$scene.ppm" >/dev/null 2>&1
        rc=$?
        if [ "$rc" -eq 0 ]; then
            echo "[OK] smoke $scene (build/smoke/$scene.ppm)"
        else
            echo "[FAIL] smoke $scene rc=$rc"; fail=1
        fi
    done
else
    echo "[PENDIENTE] build/pacman-sereos (make linux)"
    fail=1
fi

if [ "$fail" -eq 0 ]; then
    echo "TODAS LAS PRUEBAS OK"
else
    echo "HAY FALLOS"
fi
exit "$fail"
