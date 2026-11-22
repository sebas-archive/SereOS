#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_levels.py - extrae la tabla de niveles de Paku-Paku (cMazeLevel.cls) a CSV.

Replica exactamente InitLevelData (cMazeLevel.cls:101-182) y LevelData
(cMazeLevel.cls:96-100: niveles > 21 reutilizan el 21).
Genera levels.csv.
"""
import csv

FPS = 60                # modGameGlobals.bas:61
DEFAULT_SPEED = 1.25    # modGameGlobals.bas:60, pixeles logicos (SQ_SZ=8) por frame

def inc256(pct):
    """Incremento por frame en unidades de 1/256 px logico (base 1.25 px/frame)."""
    return int(round(DEFAULT_SPEED * pct / 100.0 * 256.0))

rows = []
for i in range(1, 22):
    if i == 1:
        fruit, value = "Cherry", 100
    elif i < 3:
        fruit, value = "Strawberry", 300
    elif i < 5:
        fruit, value = "Peach", 500
    elif i < 7:
        fruit, value = "Apple", 700
    elif i < 9:
        fruit, value = "Grapes", 1000
    elif i < 11:
        fruit, value = "Galaxian", 2000
    elif i < 13:
        fruit, value = "Bell", 3000
    else:
        fruit, value = "Key", 5000

    if i == 1:
        pac, hunter, ghost = 80, 90, 75
    elif i < 5:
        pac, hunter, ghost = 90, 95, 85
    elif i < 21:
        pac, hunter, ghost = 100, 100, 95
    else:
        pac, hunter, ghost = 90, 100, 95

    if i == 1:
        phases = "7,20,7,20,5,20,5,-1"
    elif i < 5:
        phases = "7,20,7,20,5,1033,0.16666,-1"
    else:
        phases = "5,20,5,20,5,1037,0.16666,-1"

    if i == 1:
        elroy1 = 20
    elif i == 2:
        elroy1 = 30
    elif i < 6:
        elroy1 = 40
    elif i < 9:
        elroy1 = 50
    elif i < 12:
        elroy1 = 60
    elif i < 15:
        elroy1 = 80
    elif i < 19:
        elroy1 = 100
    else:
        elroy1 = 120
    elroy2 = elroy1 // 2

    if i == 1:
        fright = 6
    elif i in (2, 6, 10):
        fright = 5
    elif i == 3:
        fright = 4
    elif i in (4, 14):
        fright = 3
    elif i in (5, 7, 8, 11):
        fright = 2
    elif i in (9, 12, 13, 15, 16, 18):
        fright = 1
    else:
        fright = 0

    def px_frame(p):
        return "%.4f" % (DEFAULT_SPEED * p / 100.0)

    def px_s(p):
        return "%.2f" % (DEFAULT_SPEED * p / 100.0 * FPS)

    # fase: las cadenas se alternan scatter(impar), chase(par); -1 -> chase permanente
    parts = phases.split(",")
    expanded = []
    for idx, p in enumerate(parts):
        mode = "scatter" if (idx + 1) % 2 == 1 else "chase"
        if float(p) < 0:
            expanded.append("%s:PERMANENTE" % mode)
        else:
            expanded.append("%s:%ss" % (mode, p))

    rows.append(dict(
        nivel=i,
        fruta=fruit,
        valor_fruta=value,
        vel_pacman_pct=pac,
        vel_pacman_px_frame=px_frame(pac),
        vel_pacman_px_s=px_s(pac),
        vel_pacman_cazador_pct=hunter,
        vel_pacman_cazador_px_frame=px_frame(hunter),
        vel_pacman_cazador_px_s=px_s(hunter),
        vel_pacman_inc256=inc256(pac),
        vel_pacman_cazador_inc256=inc256(hunter),
        vel_fantasma_pct=ghost,
        vel_fantasma_inc256=inc256(ghost),
        vel_fantasma_elroy1_inc256=inc256(ghost + 5),
        vel_fantasma_elroy2_inc256=inc256(ghost + 10),
        vel_fantasma_px_frame=px_frame(ghost),
        vel_fantasma_px_s=px_s(ghost),
        vel_fantasma_tunel_pct="%.1f" % ((ghost + 5) / 2.0),
        vel_fantasma_tunel_px_frame="%.4f" % (DEFAULT_SPEED * (ghost + 5) / 2.0 / 100.0),
        vel_fantasma_tunel_inc256=inc256((ghost + 5) / 2.0),
        vel_fantasma_ojos_pct=160,
        vel_fantasma_ojos_px_frame=px_frame(160),
        vel_fantasma_ojos_inc256=inc256(160),
        vel_fantasma_pen_pct=40,
        vel_fantasma_pen_px_frame=px_frame(40),
        vel_fantasma_pen_inc256=inc256(40),
        vel_fantasma_asustado_pct="%.1f" % (ghost / 2.0 + 10),
        vel_fantasma_asustado_px_frame="%.4f" % (DEFAULT_SPEED * (ghost / 2.0 + 10) / 100.0),
        vel_fantasma_asustado_inc256=inc256(ghost / 2.0 + 10),
        frightened_s=fright,
        frightened_frames=fright * FPS,
        phase_times=phases,
        fases=expanded and " | ".join(expanded),
        scatter1_s=parts[0], chase1_s=parts[1], scatter2_s=parts[2], chase2_s=parts[3],
        scatter3_s=parts[4], chase3_s=parts[5], scatter4_s=parts[6],
        chase_final=parts[7],
        elroy1_dots=elroy1,
        elroy2_dots=elroy2,
        elroy_extra_speed_pct="+5 / +10",
    ))

cols = list(rows[0].keys())
with open("levels.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("levels.csv generado:", len(rows), "niveles")
print("nivel 22+ usa los datos del 21 (cMazeLevel.cls:96-100)")
