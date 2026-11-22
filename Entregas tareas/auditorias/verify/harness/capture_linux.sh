#!/bin/sh
# capture_linux.sh - real-audio capture of PAC-MAN SereOS on Linux/CachyOS.
#
# Methodology (independent of the fixers' own scripts):
#   * a PipeWire/PulseAudio NULL SINK is made the DEFAULT sink for the run,
#   * parec records its monitor at 48 kHz s16le stereo (what the desktop hears),
#   * the REAL game binary runs with SDL_AUDIODRIVER=pulseaudio in QA scenes,
#   * a separate harness (public API only) plays each PCM/synth slot one by one.
# The previous default sink is restored on exit (trap).
#
# Output: audit/verify/evidence/linux/<name>.raw (+ .log + .txt analysis)
set -u
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$ROOT" || exit 1
OUT="$ROOT/audit/verify/evidence/linux"
LOG="$ROOT/audit/verify/evidence/logs"
BIN="$ROOT/Pac-man SereOS/build/pacman-sereos"
HARNESS="$ROOT/audit/verify/harness/harness_capture"
mkdir -p "$OUT" "$LOG"

SINK="verify_cap_$$"
PREV=$(pactl get-default-sink)
MOD=$(pactl load-module module-null-sink sink_name=$SINK \
      sink_properties=device.description=VerifyNull) || exit 1
cleanup() {
    pactl set-default-sink "$PREV" >/dev/null 2>&1
    pactl unload-module "$MOD" >/dev/null 2>&1
}
trap cleanup EXIT INT TERM
pactl set-default-sink "$SINK" || exit 1

# capture <name> <timeout_s> <cmd...>
capture() {
    name=$1; tmo=$2; shift 2
    echo "[capture] $name"
    (
      timeout "$tmo" parec -d "$SINK.monitor" --raw --rate=48000 --channels=2 \
          --format=s16le > "$OUT/$name.raw" 2>"$LOG/$name.parec.err"
    ) &
    par=$!
    sleep 1
    "$@" >"$LOG/$name.log" 2>&1
    rc=$?
    wait "$par" 2>/dev/null
    bytes=$(stat -c%s "$OUT/$name.raw" 2>/dev/null || echo 0)
    echo "  rc=$rc bytes=$bytes" | tee -a "$LOG/capture_summary.txt"
}

# ---- real binary, QA scenes -------------------------------------------------
if [ -x "$BIN" ]; then
    for spec in \
      "start:12:--scene gamestart --smoke 320" \
      "play:12:--scene play --smoke 320" \
      "frightened:12:--scene frightened --smoke 320" \
      "ghostcapture:12:--scene ghostcapture --smoke 320" \
      "death:12:--scene death --smoke 320" \
      "victory:16:--scene victory --smoke 480" \
      "gameover:10:--scene gameover --smoke 220" \
      "menu:10:--scene menu --smoke 200" \
      "pause:10:--scene pause --smoke 200" ; do
        name=${spec%%:*}; rest=${spec#*:}; tmo=${rest%%:*}; args=${rest#*:}
        # shellcheck disable=SC2086
        capture "real_$name" "$tmo" env SDL_VIDEODRIVER=dummy \
            SDL_AUDIODRIVER=pulseaudio "$BIN" $args
    done
    # sound OFF must be totally silent
    mkdir -p "$ROOT/audit/verify/evidence/tmp/xdg/pacman-sereos"
    printf 0 > "$ROOT/audit/verify/evidence/tmp/xdg/pacman-sereos/sound.txt"
    capture "real_soundoff" 10 env SDL_VIDEODRIVER=dummy \
        SDL_AUDIODRIVER=pulseaudio XDG_DATA_HOME="$ROOT/audit/verify/evidence/tmp/xdg" \
        "$BIN" --scene gamestart --smoke 320
else
    echo "ERROR: $BIN missing (run make linux first)" >&2
fi

# ---- per-slot harness (public API only) ------------------------------------
if [ -x "$HARNESS" ]; then
    for spec in \
      "slot2_START:play:7000" "slot3_WAKA1:play:600" "slot4_WAKA2:play:600" \
      "slot6_EAT_GHOST:play:1600" "slot7_EAT_FRUIT:play:1400" \
      "slot8_DEATH:play:2600" "slot9_EXTRA_LIFE:play:2600" \
      "slot10_LEVEL_CLEAR:play:6200" "slot15_GHOST_RESPAWN:play:900" \
      "slot12_SIREN_CHASE:loop:3200" "slot13_SIREN_HUNT:loop:3200" \
      "slot1_MENU_synth:play:1200" "slot5_POWER_synth:play:1200" \
      "slot11_GAME_OVER_synth:play:1800" "slot14_FRIGHT_synth:loop:2400" ; do
        name=${spec%%:*}; rest=${spec#*:}; mode=${rest%%:*}; ms=${rest#*:}
        slot=${name#slot}; slot=${slot%%_*}
        capture "h_$name" $((ms/1000 + 3)) env SDL_VIDEODRIVER=dummy \
            "$HARNESS" "$slot" "$mode" "$ms"
    done
    # one-shot precedence: EAT_GHOST then EAT_DOT must not truncate the ghost
    capture "h_oneshot_ghost_then_waka" 6 env SDL_VIDEODRIVER=dummy \
        "$HARNESS" 6 play 1200 3
else
    echo "ERROR: $HARNESS missing (compile harness_capture first)" >&2
fi

echo "done: $OUT"
