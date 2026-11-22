"""Guion de grabación real de SereOS (QEMU + SereOS sin modificar).

Cada fase registra su marca de tiempo en markers.json para poder montar
el video con la sincronización exacta de la grabación.
"""
import json, os, time
import rec

HERE = os.path.dirname(os.path.abspath(__file__))
MARKERS = os.path.join(HERE, "markers.json")
markers = {}


def mark(name, t0):
    markers[name] = round(time.monotonic() - t0, 3)
    print(f"[{markers[name]:7.2f}s] {name}", flush=True)


def main():
    proc = rec.start_qemu()
    m = rec.Mon()
    m.connect()
    r = rec.Recorder(m, "s")
    t0 = time.monotonic()
    r.t0 = t0
    r.start()
    mark("inicio_qemu", t0)

    # ---- ESCENA 2: GRUB y arranque -------------------------------------
    time.sleep(1.2)
    m.key("up")                       # detiene la cuenta atrás y deja el menú visible
    mark("grub_menu", t0)
    time.sleep(3.0)
    m.key("enter")                    # arranca "SereOS 1.0 - SereOS Desktop"
    mark("grub_enter", t0)
    rec.wait_serial("GUI_LOOP", 90)
    mark("escritorio_listo", t0)
    time.sleep(2.5)

    # ---- ESCENA 3: escritorio y dock -----------------------------------
    mark("escritorio_inicio", t0)
    m.goto(330, 300, 1.8)
    m.goto(470, 520, 1.2)
    time.sleep(0.4)
    for x in (411, 461, 511, 561, 611):
        m.goto(x, 728, 0.7)
        time.sleep(1.1)               # tooltip del dock
    mark("dock_fin", t0)
    m.goto(95, 14, 1.0)               # icono del lanzador (≡)
    m.click()
    time.sleep(1.4)
    mark("lanzador_abierto", t0)
    for y in (99, 130, 160, 190, 219):
        m.goto(150, y, 0.55)
        time.sleep(0.5)
    time.sleep(0.8)
    m.key("esc")
    time.sleep(0.8)

    # ---- ESCENA 4: aplicaciones y ventanas -----------------------------
    m.goto(95, 14, 0.8)
    m.click()
    time.sleep(0.8)
    m.goto(150, 130, 0.6)
    m.click()                         # abre "Archivos" desde el lanzador
    time.sleep(1.6)
    mark("archivos_abierto", t0)
    m.goto(287, 198, 0.9)
    m.click()
    time.sleep(0.9)
    m.key("enter")                    # abre la carpeta "docs"
    time.sleep(1.8)
    m.key("bs")                       # vuelve a la raíz
    time.sleep(1.2)
    m.goto(400, 103, 0.8)             # barra de título: doble clic = maximizar
    m.dclick()
    time.sleep(2.6)
    mark("archivos_maximizado", t0)
    m.goto(512, 46, 0.6)              # barra de título ya maximizada
    m.dclick()                        # restaurar
    time.sleep(1.8)
    mark("archivos_restaurado", t0)
    m.goto(511, 728, 0.9)             # dock: Monitor
    m.click()
    time.sleep(3.2)
    mark("monitor_abierto", t0)
    m.goto(528, 122, 0.8)
    m.dclick()                        # maximizar Monitor
    time.sleep(2.8)
    mark("monitor_maximizado", t0)
    m.goto(512, 46, 0.8)
    m.dclick()                        # restaurar
    time.sleep(1.8)

    # ---- ESCENA 5: terminal y kernel -----------------------------------
    m.goto(461, 728, 0.9)             # dock: Terminal
    m.click()
    time.sleep(1.2)
    mark("terminal_abierta", t0)
    m.goto(480, 330, 0.8)
    m.click()                         # foco en la terminal
    time.sleep(0.4)
    for cmd, pause in (("help", 3.4), ("sysinfo", 3.6), ("version", 2.2),
                       ("mem", 2.4), ("ticks", 2.0), ("dmesg", 4.2),
                       ("date", 2.2)):
        m.type_text(cmd + "\n", 0.11)
        time.sleep(pause)
        mark(f"cmd_{cmd}", t0)

    # ---- ESCENA 7: PAC-MAN SereOS --------------------------------------
    m.goto(561, 728, 0.9)             # dock: juego
    m.click()
    time.sleep(0.8)
    mark("pacman_abierto", t0)
    time.sleep(4.0)                   # pantalla de presentación (attract)
    m.key("enter")                    # menú principal
    time.sleep(2.5)
    mark("pacman_menu", t0)
    m.key("enter")                    # inicio de partida
    mark("pacman_partida", t0)
    time.sleep(3.0)
    route = (["left"] * 4 + ["up"] * 3 + ["right"] * 5 + ["down"] * 3 +
             ["left"] * 6 + ["up"] * 2 + ["right"] * 6 + ["down"] * 4)
    for k in route:
        m.key(k, 0.05)
        time.sleep(0.55)
    mark("pacman_fin_ruta", t0)
    time.sleep(2.5)
    m.key("esc")
    time.sleep(1.5)

    # ---- ESCENA 4 (cierre): Acerca de ----------------------------------
    m.goto(95, 14, 0.8)
    m.click()
    time.sleep(0.8)
    m.goto(150, 99, 0.6)
    m.click()
    time.sleep(4.0)
    mark("acerca_abierto", t0)
    time.sleep(1.5)
    mark("fin_grabacion", t0)

    r.stop()
    with open(MARKERS, "w") as f:
        json.dump(markers, f, indent=1)
    with open(os.path.join(HERE, "frames_index.txt"), "w") as f:
        for t, p in r.frames:
            f.write(f"{t - t0:.3f}\t{p}\n")
    proc.kill()
    print("frames:", len(r.frames), "duracion:", round(r.frames[-1][0] - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
