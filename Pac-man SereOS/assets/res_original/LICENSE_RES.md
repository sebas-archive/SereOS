# Licencia y procedencia de los recursos originales de PAC-MAN SereOS

**Entrega privada/académica.** Los recursos de `assets/res_original/`
fueron suministrados por el usuario del proyecto desde
`/home/t1an/Descargas/Res` y se copian **sin modificaciones** solo
para trazabilidad. **No se autoriza su redistribución pública** (ni
los originales ni los datos derivados de `assets/*.c` que los
contienen) sin permiso de sus autores.

Los PNG y WAV tienen origen arcade/terceros (personajes, frutas y
sonidos reconocibles de Pac-Man, marca de Namco); no se reclama
autoría. `prstartk.ttf` es *Press Start K* (© 2001-2002 codeman38),
sin licencia declarada en el archivo: uso user-supplied/privado con
atribución. Ver también `assets/fonts/LICENSE_ARCADE.md`.

## Originales usados (20 archivos, copiados sin modificar)

| Archivo | MD5 | Formato | Uso |
|---|---|---|---|
| `cherry.png` | `5e618304f090913d6065ef1509f41235` | 48x48 RGBA | fruta Res |
| `strawberry.png` | `fe5c52249b327b58d0f0d09e45322ddb` | 32x32 P | fruta Res |
| `peach.png` | `9234915891b6cc3439f88864ebbcf685` | 32x32 P | fruta Res |
| `apple.png` | `cf56cd2b32d26f4c15dc508e5153521f` | 32x32 P | fruta Res |
| `grapes.png` | `ddfadec1107f87d89d9fea074f27016d` | 32x32 P | fruta Res |
| `ghost1.png` | `521be1b68ff40fc6efaca2ee6a078016` | 48x48 RGBA | cuerpo fantasma Res |
| `ghost2.png` | `4ec74e51c6f8923fd84929e0d946c51b` | 48x48 RGBA | cuerpo fantasma Res |
| `key.png` | `8a426c989a35a3a436837c4d0fd64177` | 48x48 RGBA | llave decorativa: procedencia (sprite procedural) |
| `game start.wav` | `07914ee70de9f5f1166ed3e9b35fc9db` | 2ch 8b 48000Hz | sfx Res |
| `waka1.wav` | `9e3c8eb9b4d7af04971b12c9af3e5bb4` | 2ch 16b 48000Hz | sfx Res |
| `waka2.wav` | `0452cd64893e3fbd3503190e9ff318c7` | 2ch 16b 48000Hz | sfx Res |
| `eat ghost.wav` | `61d4ded9e6249e64b735982f6ced3ec5` | 1ch 8b 11025Hz | sfx Res |
| `eat fruit.wav` | `514eeeeb192e8ca45ca92aa308f61f63` | 1ch 8b 11025Hz | sfx Res |
| `extra life.wav` | `27991f5575aec8695f0f9a68925b9df8` | 1ch 8b 11025Hz | sfx Res |
| `ghost respawn.wav` | `43fae1a4447f5026f8f23a9d9dd02b95` | 2ch 8b 48000Hz | sfx Res |
| `hunted siren.wav` | `8d5759b619045b5f6879ec83175d67a9` | 2ch 8b 48000Hz | sfx Res |
| `hunter siren.wav` | `d35ceeea5823f2ea9c1a3d2107826b92` | 2ch 8b 48000Hz | sfx Res |
| `pacman death.wav` | `b5cacf9a37e6a4fd396f6fd914168780` | 1ch 8b 11025Hz | sfx Res |
| `intermission.wav` | `566c0f2299b8a7ebef6372010fa6866e` | 1ch 8b 11025Hz | sfx Res (nivel completado) |
| `prstartk.ttf` | `4e9a195e88e19adc94992d05f63db8ac` | Press Start K | atlas de fuente arcade |

## Recursos excluidos (documentados, NO copiados)

- `retroghost1.png`: No usado por Paku-Paku; candidato a skin Retro futuro.
- `retroghost2.png`: No usado por Paku-Paku; candidato a skin Retro futuro.
- `Clydeeghost.png`: No usado; arte grande para menu (no se integra en v1).
- `dead.png`: No usado; rafaga final de muerte (no es la secuencia arcade).
- `atari full.ttf`: Sin licencia clara, marca Atari, sin Latin-1; excluido.

## Conversión

- PNG -> `assets/sprites_res.c` (RGB565 16x16, clave `0xF81F`).
- WAV -> `assets/sfx_res.c` (PCM u8 mono 11025 Hz, normalizado).
- TTF -> `assets/font_arcade.c` (cobertura alfa 8bpp 8x16).
- Regenerar: `python3 tools/gen_pacman_res_assets.py`.
