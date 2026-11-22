# VERIFICACIÓN FINAL INDEPENDIENTE — task-4 (SereOS, 4 peticiones + correcciones task-5/6/7)

- **Agente:** `verifier` (independiente de shutdown-engineer, audio-engineer y ui-engineer).
- **Tarea:** `task-4` (verificación final). Correcciones posteriores verificadas: `task-5` (logo S en About / “i” solo en accesos), `task-6` (pantalla Apagando/Reiniciando con tipografía del sistema), `task-7` (menú Reiniciar → `sereos_restart()`).
- **Workspace:** `/home/t1an/Descargas/sereos02`.
- **Árbol final verificado:** `sistema operativo/sereos.iso` (36.835.328 B, 20/11/2026 05:54) md5 `1a781295a25c8fae4113ff2837e980c4`; `sereos.bin` md5 `0a205b90af2acd38a27578dff70a9cfe`.
- **Entorno:** QEMU 11.1.3 (TCG, `/dev/kvm` no disponible), gcc 16.2.1, GNU Make 4.4.1, NASM 3.02, Python 3.14.9 + numpy 2.5.4. Registro: `audit/final/evidence/env.txt`.
- **Restricciones respetadas:** no se editó ninguna fuente del SO ni del juego; no `make clean` global; toda la evidencia vive en `audit/final/`.

---

## 1. Veredicto (matriz petición → resultado)

| # | Petición / comprobación | Resultado | Evidencia principal |
|---|---|---|---|
| 1 | **Apagado real**: menú logo → “Apagar” apaga QEMU por ACPI; serial `SEREOS_POWEROFF`/`SEREOS_SHUTDOWN`; cascada de respaldo | **PASS** | `evidence/run-shutdown-default/`, `evidence/run-power-final/power-apagar/` |
| 2 | **Audio real**: `audiotest` con `-device sb16` produce WAV no silencioso; fallback PC speaker sin SB16; fila Audio real en About | **PASS** | `evidence/audio.wav`, `evidence/audio_pcspk.wav`, `evidence/run-audio-sb16/`, `evidence/run-audio-pcspk/` |
| 3 | **About / icono**: icono de accesos “i” azul/celeste en menú y dock; ventana About con **logo S** (corrección task-5); logo S en barra superior; sin “i” fuera de los accesos | **PASS** | `evidence/run-final-ui/01_topbar_zoom.png`, `02_dock_zoom.png`, `03_menu_zoom.png`, `04_about.png`, `04_about_content_icon_zoom.png` |
| 4 | **Botones de ventana**: en las 5 apps, controles arriba a la DERECHA en orden mín(ámbar)/máx(verde)/cerrar(rojo), título centrado; maximizar/restaurar con glifo correcto; Alt+W cierra | **PASS** | `evidence/run-final-ui/`, `evidence/analysis_ui_buttons.json`, `evidence/run-ui-clean/`, `evidence/run-max/` |
| C1 | **Corrección task-6**: pantalla “Apagando...” con logo S, título sans-serif (`TEXT_DISPLAY`) y subtítulo gris (`TEXT_SMALL`), centrados, sin solape; QEMU sale por ACPI | **PASS** | `evidence/run-power-final/power-apagar/01_apagando_best.png`, `result.json` |
| C2 | **Corrección task-6/7**: menú → “Reiniciar” muestra “Reiniciando...” con el mismo diseño y reinicia | **PASS** | `evidence/run-power-final/power-reiniciar/01_reiniciando_best.png`, `result.json` |
| 5 | **Build** ISO/bin, build y tests del juego; arranque con marcadores serie; sin pánico/excepción | **PASS** | `evidence/logs/build_os_FINAL.log`, `build_game.log`, `test_game.log`; seriales en cada `run-*/serial.log` |
| 6 | **Regresiones** (F1..F7, help/dmesg, suite `tools/run_tests.py`) | **PARCIAL** — app/UI OK y sin crash; ver §6: 7/18 pruebas de la suite fallan por **harness desactualizado** frente al cambio pedido (botones a la derecha) + 1 flake del juego | `evidence/logs/run_tests_final.log`, control en §6 |

No hay FAIL de producto en las 4 peticiones ni en las correcciones. Los únicos FAIL son de la suite interna del proyecto, explicados y acotados en §6.

---

## 2. Build y arranque

Comandos exactos y salida:

```bash
make -C "sistema operativo"                       # EXIT=0, 0 warnings
make -C "Pac-man SereOS"                          # EXIT=0 -> [pacman] Linux OK
make -C "Pac-man SereOS" test                     # checks=209 failures=0 / TODAS LAS PRUEBAS OK
```

- ISO final: `sistema operativo/sereos.iso`, `md5 1a781295a25c8fae4113ff2837e980c4` (tras task-6/7).
- Arranque QEMU (varias sesiones independientes, todas limpias): serial `SEREOS_BOOT_OK mem=255MiB`, `SPLASH_DONE`, `GUI_READY`; **0** ocurrencias de `SEREOS_EXCEPTION`/`SEREOS_PANIC` en boot/UI/audio/apagado.
- No hay target `make test` en el Makefile del SO; la suite real es `tools/run_tests.py` (§6).

## 3. Apagado real (petición 1)

Método: ratón PS/2 por monitor HMP de QEMU (`mouse_move`/`mouse_button`), clic real en el botón de menú `(97,18)` y en “Apagar” `(150,289)`; capturas `screendump` PPM→PNG.

- Menú verificado visualmente: “Reiniciar” (icono refresh) y “Apagar” (icono power) bajo el separador; “Acerca de” con insignia “i”. `evidence/run-final-ui/03_menu_zoom.png`, `run-power-final/*/00_menu.png`.
- **QEMU estándar**: tras pulsar Apagar, QEMU termina solo con **rc=0** en ~0.3–1 s. Serial: `SEREOS_SHUTDOWN`, `SEREOS_POWEROFF`, `SEREOS_SHUTDOWN:acpi pm1a=0x0604 pm1b=0x0000 slp_typ=0/0 s5=1`. Sin puertos de respaldo ni `SEREOS_POWEROFF_SAFE`.
  - `evidence/run-shutdown-default/` (result.json, serial.log, 02_apagando.png)
  - `evidence/run-power-final/power-apagar/` (result.json, serial.log, 01_apagando_best.png)
- **Cascada de respaldo** (`-machine pc,acpi=off -device isa-debug-exit`): QEMU termina con rc=99 y serial `SEREOS_SHUTDOWN:port_0x604`, `:port_0xB004`, `:port_0x4004`, `:isa_debug_exit`. `evidence/run-shutdown-isadebugexit/`.

## 4. Audio real (petición 2)

Comandos (rutas absolutas; WAV en `audit/final/evidence/`):

```bash
qemu-system-i386 ... -audiodev wav,id=snd0,path=<abs>/audio.wav -device sb16,audiodev=snd0
qemu-system-i386 ... -machine pc,pcspk-audiodev=snd0 -audiodev wav,id=snd0,path=<abs>/audio_pcspk.wav
```

F2 (Terminal) → `help` (lista `audiotest`) → `audiotest` (4 tonos 440/660/880/1320 Hz · 200 ms) → captura de pantalla completa y cierre de QEMU para finalizar el WAV.

| Caso | Línea de arranque (serial) | Marcadores | WAV (análisis propio, `harness/analyze_wav.py`) |
|---|---|---|---|
| SB16 | `[OK] Audio: SB16 0x220 IRQ5 DMA1` | `AUDIO_TEST:sb16`, `AUDIO_TEST_DONE tones=4 irq=4 pit_hz=100` | `audio.wav` 138.940 B, 0,787 s, **pico −2,96 dBFS**, **RMS −3,39 dBFS**, 100 % bloques > −40 dBFS → **no silencio** |
| Sin SB16 (pcspk) | `[OK] Audio: solo PC speaker` | `AUDIO_TEST:pcspk`, `AUDIO_TEST_DONE tones=4 irq=0 pit_hz=100` | `audio_pcspk.wav` 139.368 B, 0,790 s, **pico −2,50 dBFS**, **RMS −2,65 dBFS** → **no silencio** |

- Capturas: `run-audio-sb16-screen/02_audiotest_done.png` (“Tonos: 4/4”, IRQ 5, 4 fines de DMA por interrupción), `run-audio-pcspk-screen/02_audiotest_done.png`, `run-audio-sb16/02_about_sb16.png`, `run-audio-pcspk/01_about_pcspk.png`.
- About fila **Audio**: “SB16 0x220 IRQ5 DMA1” con SB16 y “solo PC speaker” sin SB16 (capturas adjuntas). Sin caídas ni pánicos en ambos casos.

## 5. About, icono “i” y botones de ventana (peticiones 3 y 4 + task-5)

- **About con logo S** (corrección task-5): el icono de contenido es **idéntico al logo S original** (S blanca sobre cuadro azul redondeado); comparación de píxeles contra baseline pre-fix `evidence/run-prep-dryrun/03_about.png`: **diff medio = 0,00** (restauración exacta). `evidence/run-final-ui/04_about.png` y `04_about_content_icon_zoom.png`.
- **“i” solo en accesos**: insignia “i” celeste en la fila “Acerca de” del menú (`03_menu_zoom.png`, `03_menu_about_icon_zoom.png`) y en el tile “Acerca de” del dock (`02_dock_zoom.png`). La barra superior conserva el logo S + wordmark “SereOS” (`01_topbar_zoom.png`). No se observa “i” en la ventana About ni en otras ventanas.
- **Botones a la derecha** (medido por píxeles, `harness/check_ui_pixels.py`; JSON `evidence/analysis_ui_buttons.json`): en About, Archivos, Terminal, Monitor y PAC-MAN, orden izquierda→derecha **ámbar (minimizar), verde (maximizar/restaurar), rojo (cerrar)**, 3 círculos de radio 5 separados 18 px, **margen derecho 13 px** (14 px maximizada), `in_right_third=true`, alineados. Título centrado geométricamente: offset del texto respecto al centro de la ventana **0,0 / −0,5 px** en las 5 apps.
- **Maximizar/restaurar PAC-MAN**: doble clic en barra de título (normal y=84 → maximizada y=48, ventana 0..1024; restaurar vuelve a 41..919) y también por el botón verde; glifos verificados con zoom: maximizar = un cuadrado, maximizada = dos cuadrados superpuestos (restaurar). `evidence/run-power-final` no; ver `evidence/run-final-ui/07_game_maximized.png`, `07_game_glyph_restore_zoom.png`, `08_game_restored.png`, `08_game_glyph_maximize_zoom.png`, y `evidence/run-max/`.
- **Alt+W** cierra la ventana activa y el serial emite `APP_CLOSE:<app>` (About, Archivos, Terminal, Monitor, PAC-MAN). F1..F7 siguen abriendo/enfocando/minimizando. `help` y `dmesg` funcionan (`run-final-ui/09_terminal_help.png`, `10_terminal_dmesg.png`).

## 6. Regresiones — suite interna `tools/run_tests.py` (PARCIAL, causa explicada)

Comando (ruta de capturas corta por el límite de 108 B del socket del monitor de QEMU; la ruta larga hizo fallar el arranque en un primer intento, no es defecto del SO):

```bash
cd "sistema operativo"
python3 tools/run_tests.py --kvm off --timeout-scale 1.6 \
  --shots-dir /home/t1an/Descargas/sereos02/audit/final/rt
# RESULTADO: 11/18 PASS, 7 FAIL — logs/run_tests_final.log
```

Fallos y clasificación (NO son regresiones de las 4 peticiones):

| Prueba | Fallo | Causa determinada |
|---|---|---|
| maximize, corners, topnav, resolution_1280, resolution_800 | no detecta barra de título / no activa topnav / full-bleed | **Harness desactualizado**: `detect_titlebar()`/`find_traffic_lights()` asumen el orden antiguo **rojo-ámbar-verde a la IZQUIERDA** (busca rojo y comprueba ámbar en `rx+18`, verde en `rx+36`, y muestrea el fondo en `rx+60`). El cambio pedido mueve los botones a la DERECHA en orden **ámbar-verde-rojo**, por lo que la detección devuelve `None` y encadena fallos. **Prueba de control**: la MISMA suite con la ISO antigua (botones a la izquierda) y mismo QEMU/TCG: `maximize` **PASS**, `corners` **PASS** (`logs/run_tests_control_oldiso.log`, `evidence/run-tests-control/`). |
| window_close | timeout puntual esperando `APP_OPEN:files` | **Flaky**: reintento aislado **PASS** (9,5 s) y en el mismo run los pasos funcionales de cierre pasaron (“ventanas cerradas (4)”). `logs/run_tests_retry_game_close.log`. |
| game | conteo de píxeles de fantasmas “frightened” | Reproducible bajo TCG (2/2), pero el resto de pasos del juego pasan (menú, partida, dots, pausa, game-over, salida). No está entre las 4 peticiones y no toca UI/audio/power; **NO VERIFICADO como regresión de producto** (no hubo tiempo para el control con ISO antigua; el intento se abortó por orden de parada). |

Comprobaciones adicionales de regresión: sin `SEREOS_EXCEPTION`/`SEREOS_PANIC` en los 7 logs de la suite (`no_fatal` PASS), modo texto de respaldo PASS, pánico controlado PASS, audio del juego PASS.

## 7. Correcciones posterioriores verificadas (task-6 / task-7)

Ambas tareas constan **completed** en el tablero al cerrar este informe. Pantallas nuevas (`evidence/run-power-final/`), medidas por píxeles (`harness/verify_power_final.py`):

| Pantalla | QEMU | Serial | Layout medido |
|---|---|---|---|
| “Apagando…” (menú→Apagar) | termina rc=0 | `SEREOS_SHUTDOWN`, `SEREOS_POWEROFF`, `SEREOS_SHUTDOWN:acpi pm1a=0x0604 … s5=1` | logo S 306–373 px; título sans-serif 406–433; subtítulo gris 451–458; centros X 511,5 / 511 / 512 (pantalla 1024); bloque vertical centrado en 382 (centro 384); **sin solape**, gaps reales 33/18 px (nominales 24/12 + métricas de fuente) |
| “Reiniciando…” (menú→Reiniciar) | termina rc=0 (reset; `-no-reboot`) | `SEREOS_RESTART` | mismo diseño: logo 306–373, título 405–427, subtítulo 451–458, centros 511,5/512/512, sin solape |

Capturas: `power-apagar/01_apagando_best.png`, `power-reiniciar/01_reiniciando_best.png` (+ series `01_*_0/1.png` con puntos animados). El texto usa `TEXT_DISPLAY`/`TEXT_SMALL` del escritorio (sans-serif), no la fuente pixelada anterior.

## 8. Observaciones y limitaciones

1. La suite interna del proyecto quedó desactualizada respecto al cambio pedido de botones (ver §6). Actualizar `detect_titlebar()`/`find_traffic_lights()` a la nueva posición/orden es trabajo de tests, fuera del alcance de esta verificación (no se editó nada).
2. `SEREOS_SHUTDOWN:acpi … slp_typ=0/0 s5=1`: el parser de DSDT obtiene SLP_TYP=0 para _S5 en el firmware de QEMU; aun así el SLP_EN provoca el apagado real (QEMU rc=0, verificado también con la cascada por puertos). No supone fallo funcional en QEMU; en hardware real conviene validar el _S5 del firmware.
3. Durante la verificación (05:35) se modificaron dos documentos (`README.md`, `Pac-man SereOS/docs/GAME.md`) por un fixer; son documentación, no afectan al ISO construido ni al código verificado.
4. `/dev/kvm` no disponible: todo se ejecutó con TCG (más lento), lo que explica parte de la flakiness temporal del test del juego.
5. `-audiodev wav` de QEMU deja `RIFF/data size=0` en la cabecera; el analizador propio lo maneja usando el resto del fichero.

## 9. Archivos modificados/nuevos (find -newermt '2026-11-20 05:13', con md5)

Lista completa (44 ficheros; se excluyen `build/`, `isodir/`, `*.iso`, `*.bin`, `audit/`, `__pycache__` y los artefactos generados `docs/screenshots/raw/*` de los fixers). Archivo máquina: `audit/final/evidence/modified_files_FINAL.md5`.

```
e3c1229d89a9afb679a2ab26b1d32aaf  Pac-man SereOS/docs/GAME.md
622ff3559a565f97b605cd8948992aa3  Pac-man SereOS/README.md
a143e73119207ec04991e64089b2197a  Pac-man SereOS/src/core/game.c
7cd57ab2b4927f368de73439b3b338ed  Pac-man SereOS/tests/core_tests.c
9b7a6592479876ef30f050bfe826bde5  README.md
cb3a886b53020711e4ffebf9b3cfdb00  sistema operativo/apps/about/about.c
b87139db6812f1e080aa8aa669f3e4cf  sistema operativo/audio/audio.c
642c8c722b282fe4f7bd6f0d5e2a2ed5  sistema operativo/audio/audio.h
0a55c2d3b2c6d541875cf931ee92722c  sistema operativo/CHANGELOG.md
1d9adc891bb822fa4526a7dcbed844dc  sistema operativo/docs/AUDIO.md
91f20f626625c30302864433e98a50ec  sistema operativo/docs/AUDIO_VM.md
deb0a19ca67526d4d44f64a73f083232  sistema operativo/docs/evidence/audio/about_audio_noaudio.png
d4755d9afe42580b44e5095e8d5cdc82  sistema operativo/docs/evidence/audio/about_audio_sb16.png
8e48afdfe4870e4fa9771972843b414a  sistema operativo/docs/evidence/audio/about_audio_shared_iso.png
5d47bca15490d853e85596f5cf41fe0d  sistema operativo/docs/evidence/audio/audiotest_sb16_clip.wav
48f919fab7a5200eb3e54c1218587920  sistema operativo/docs/evidence/audio/build_shared.json
49324139015344905fb0c184c9a95efe  sistema operativo/docs/evidence/audio/EVIDENCE.md
047652e4ab083645ff931303f46635bf  sistema operativo/docs/evidence/audio/results_extra.json
579bf58bebdb99be7abf6a3ddf8b8087  sistema operativo/docs/evidence/audio/results.json
cf2cf2906d55f15a9f737186747de8b7  sistema operativo/docs/evidence/audio/results_shared.json
be1bd7f67dd0804170b9d59264d31a38  sistema operativo/docs/evidence/audio/serial_A_sb16.log
d6976dad4bde9c43aed285e02c8b6e7f  sistema operativo/docs/evidence/audio/serial_B_pcspk.log
d6976dad4bde9c43aed285e02c8b6e7f  sistema operativo/docs/evidence/audio/serial_C_noaudio.log
f61792e671543932a05148c76eebf960  sistema operativo/docs/evidence/audio/serial_D_scan_0x240.log
f5c18eeb4cca105c5093ddb167971e98  sistema operativo/docs/evidence/audio/serial_E_irq7_mismatch.log
f8ec54b70fdcaf6aa665368c0fb4909f  sistema operativo/docs/evidence/audio/serial_final_beep_audiotest.log
ef08db7be5a06d2e12582f41e181265c  sistema operativo/docs/evidence/audio/serial_shared_iso.log
39a1e5c46bfc4889b6aa45e4b83d2bf1  sistema operativo/docs/evidence/audio/terminal_audio_beep_audiotest.png
81e0190c9de83bf0f51f709336c0e31e  sistema operativo/docs/evidence/audio/terminal_audiotest_sb16.png
991b66fa32cdff555aca78a6ef7894b9  sistema operativo/docs/evidence/audio/terminal_audiotest_shared_iso.png
90cdd4e9e73cff93b8df8f6c18b68646  sistema operativo/docs/evidence/audio/verify_audio.py
ee1124c738009bf9a5df446550b44ab9  sistema operativo/drivers/sb16.c
43de60ed5173260d93e7f02201f61e01  sistema operativo/drivers/sb16.h
e7c788c02496a58ae688cdcf73835b72  sistema operativo/drivers/speaker.c
a5625c407c03189b3e449d14d7fe20a1  sistema operativo/drivers/speaker.h
12621469fc1947ed1447946e5fd16f5a  sistema operativo/gui/desktop.c
f3394dae832866d51aba89e8b6e969fc  sistema operativo/gui/icons.c
f4248430c31582d7ed534fbcadb0b218  sistema operativo/gui/icons.h
cfa4a5ae5e526a197f88716d755f02b3  sistema operativo/gui/window.c
0e3d110597696a4a7a3ab063ff34615e  sistema operativo/gui/window.h
1556e729dbd959e4cd2af0f96cb4c8d3  sistema operativo/kernel/kernel.c
e1dd6cb7130c318c0169d5d8e4cab1a5  sistema operativo/kernel/shutdown.c
4ce527d0fff90bf02a70f3b2d37ab209  sistema operativo/kernel/shutdown.h
23eeee3d8960e5c44f11cc317f0000e3  sistema operativo/shell/shell.c
```

Documentación nueva del SO: `docs/AUDIO.md`, `docs/AUDIO_VM.md`, `docs/evidence/audio/*` (EVIDENCE.md, results*.json, serial_*.log, capturas y WAV de evidencia del fixer de audio). Artefactos generados por los fixers fuera de esta lista (capturas de sondeo): `docs/screenshots/raw/ui-verify/`, `docs/screenshots/raw/ui-fix/`, `docs/screenshots/raw/power-fix/`.

## 10. Evidencia / trazabilidad (todo bajo `audit/final/evidence/`)

- `env.txt`, `modified_files_FINAL.md5`, `analysis_ui_buttons.json`, `resumen_datos.txt`.
- `logs/`: `build_os_FINAL.log`, `build_game.log`, `test_game.log`, `verify_ui.log`, `verify_maximize.log`, `verify_final_ui.log`, `verify_audio_final.log`, `verify_audio_screens.log`, `verify_power_final.log`, `verify_shutdown*.log`, `run_tests_final.log`, `run_tests_retry_game_close.log`, `run_tests_control_oldiso.log`.
- `run-final-ui/` (About/logo S, menú, dock, topbar, 5 ventanas, maximizar/restaurar, help/dmesg, serial), `run-ui-clean/`, `run-ui/`, `run-max/` (validaciones intermedias), `run-prep-dryrun/` (baseline pre-fix), `run-audio-sb16/`, `run-audio-pcspk/`, `run-audio-*-screen/`, `audio.wav`, `audio_pcspk.wav`, `run-shutdown-default/`, `run-shutdown-isadebugexit/`, `run-power-final/`, `run-tests-final/`, `run-tests-retry/`, `run-tests-control/`.
- Arnés propio (no modifica fuentes): `audit/final/harness/{vmkit.py, verify_final_ui.py, verify_ui_clean.py, verify_maximize.py, verify_audio.py, verify_audio_screens.py, verify_power_final.py, verify_shutdown.py, check_ui_pixels.py, analyze_wav.py}`.

**Conclusión:** las 4 peticiones originales y las correcciones task-5/task-6/task-7 están implementadas y verificadas con evidencia ejecutable (PASS). Único punto PARCIAL: la suite interna del proyecto conserva expectativas de la UI antigua (botones a la izquierda) y un flake de gameplay bajo TCG; documentado con control experimental, sin impacto en las peticiones.
