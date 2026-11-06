# sensor-node

An ESP32-S3-WROOM-1 with a BME280 on I2C, a 4-pin sensor/power header and a 6-pin programming header. The first board here that is a **device**, and the first whose **firmware pin map is derived from the same netlist as the board** (OpenDesignCore `wiki/concepts/device-pipeline.md`, Phase 2).

## What is generated from what

```
scripts/make_sensor_node.py      PARTS (pin -> net)            -> sensor-node.kicad_sch
kicad-cli sch erc / export netlist                             -> erc-report.txt, sensor-node.net
scripts/make_sensor_node_board.py  PARTS + PLACEMENT + .net     -> sensor-node.kicad_pcb, board.manifest.json
scripts/route_board.py             .kicad_pcb (+ FreeRouting)   -> .dsn, .ses, routing.json, drc-report.txt
scripts/make_bom.py                opc_id fields + OpenPartsCore -> bom.csv, bom.json
scripts/make_firmware.py           .net + OpenPartsCore          -> firmware/{pins.rs, pins.h, firmware.manifest.json}
kicad-cli pcb export step|stl                                   -> sensor-node.step, .stl (enclosure co-design)
scripts/emit_provenance.py                                      -> sensor-node.provenance.json
```

Nothing downstream of the schematic restates connectivity. The board binds pads to the netlist's nets; the firmware reads GPIO numbers out of the netlist's module pin names (`IO8` on the SDA net, `IO9` on the SCL net) and the BME280 address out of where SDO is tied. Change a wire in `PARTS` and everything else follows or refuses.

## Regenerate

```
python scripts/make_sensor_node.py
cd boards/sensor-node
kicad-cli sch erc --exit-code-violations --severity-error -o erc-report.txt sensor-node.kicad_sch
kicad-cli sch export netlist -o sensor-node.net sensor-node.kicad_sch
cd ../..
python scripts/lf.py boards/sensor-node/erc-report.txt boards/sensor-node/sensor-node.net   # kicad-cli writes CRLF; provenance hashes LF
<KiCad>/bin/python.exe scripts/make_sensor_node_board.py
<KiCad>/bin/python.exe scripts/apply_fab_profile.py boards/sensor-node/sensor-node.kicad_pcb jlcpcb-2layer-1oz
kicad-cli pcb drc --severity-error -o boards/sensor-node/drc-report.txt boards/sensor-node/sensor-node.kicad_pcb
python scripts/lf.py boards/sensor-node/drc-report.txt
<KiCad>/bin/python.exe scripts/route_board.py boards/sensor-node/sensor-node.kicad_pcb --freerouting <freerouting-2.5.0.jar> --java <Java 25 java.exe>
<KiCad>/bin/python.exe scripts/add_ground_pour.py boards/sensor-node/sensor-node.kicad_pcb   # after routing, never before
kicad-cli pcb drc --severity-error -o boards/sensor-node/drc-report.txt boards/sensor-node/sensor-node.kicad_pcb
kicad-cli pcb export gerbers --layers "F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts" -o boards/sensor-node/fab/ boards/sensor-node/sensor-node.kicad_pcb
kicad-cli pcb export drill --format excellon -o boards/sensor-node/fab/ boards/sensor-node/sensor-node.kicad_pcb
kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp -o boards/sensor-node/fab/sensor-node-pos.csv boards/sensor-node/sensor-node.kicad_pcb
python scripts/lf.py boards/sensor-node/drc-report.txt boards/sensor-node/fab/*
<KiCad>/bin/python.exe scripts/make_bom.py boards/sensor-node/sensor-node.kicad_pcb ../OpenPartsCore
python scripts/make_firmware.py boards/sensor-node/sensor-node.net --openpartscore ../OpenPartsCore --out boards/sensor-node/firmware
kicad-cli pcb export step --subst-models -o boards/sensor-node/sensor-node.step boards/sensor-node/sensor-node.kicad_pcb
kicad-cli pcb export stl -o boards/sensor-node/sensor-node.stl boards/sensor-node/sensor-node.kicad_pcb
python scripts/lf.py boards/sensor-node/sensor-node.step boards/sensor-node/sensor-node.stl   # ASCII exports, same rule
python scripts/emit_provenance.py boards/sensor-node && python scripts/verify_provenance.py boards/sensor-node
```

The board and routing scripts normalise their own outputs (`.net`, `.kicad_pcb`, `.dsn`) to LF; `lf.py` covers the kicad-cli reports and the ASCII STEP/STL exports.

## Current state (2026-11-04)

```
schematic: 13 parts, 44 pin connections, nets: +3V3, EN, GND, IO0, RXD0, SCL, SDA, TXD0
ERC:       Found 0 violations    (every unused module pin carries an explicit no-connect)
board:     outline 44.0 x 52.0 mm, 11 components, 4 x M3 holes; design rules = fab-profiles/jlcpcb-2layer-1oz
routing:   FreeRouting 2.5.0 (jar, Java 25): 143 tracks, 8 vias, routed_clean in routing.json
pour:      GND on F.Cu and B.Cu (1185 / 1482 mm^2 filled), stops at the antenna keepout y = 13.25 mm
DRC:       Found 0 DRC violations, Found 0 unconnected pads   (after pour, JLCPCB profile + sensor-node.kicad_dru)
warnings:  silk only: 70 silk_overlap, 63 silk_over_copper, 2 silk_edge_clearance (fab clips silk off pads)
fab/:      9 Gerber layers + job file, 1 Excellon drill (34 holes: 12 x 0.20, 8 x 0.30, 10 x 1.00, 4 x 3.20 NPTH), placement CSV
firmware:  I2C SDA=GPIO8 SCL=GPIO9, BME280 at 0x76 (SDO->GND, CSB->+3V3); strapping/USB pins clear
```

**Routed.** `route_board.py` exports DSN with `pcbnew.ExportSpecctraDSN`, runs FreeRouting (`-de … -do … -mp 20 --gui.enabled=false --router.automatic_neckdown=false`), imports the SES, re-runs DRC and writes `routing.json` with the hash of every input and output (router jar sha256 f6f51bb0…). Without `--freerouting` it exits 3 and keeps the DSN, and the board stays at 34 unconnected, which is the honest unrouted state. FreeRouting is GPL-3.0 and stays a separate process, like KiCad (DECISIONS.md). Regenerating the board with `make_sensor_node_board.py` produces an unrouted board again: re-apply the profile and re-route, in that order, because the DSN is exported from whatever the board holds (a routed board exported to DSN keeps its tracks).

**Why the fab profile is applied before routing.** With KiCad's default 0.2 mm minimum, FreeRouting's fanout stage left 10–15 GND stubs at 0.15 mm where the module's 1.5 mm-pitch pads leave no room for 0.2 mm track plus 0.2 mm clearance; `--router.automatic_neckdown=false` reduced them (13 → 10 on this board) but did not remove them. JLCPCB's stated 2-layer minimum track is 0.10 mm (`fab-profiles/jlcpcb-2layer-1oz.json`, cited), so the board is checked against what the house will build, as `sensor-breakout` already is. Netclass widths stay 0.2 mm; only the minimums move.

**Use the `.jar`, not the native CLI.** `freerouting-cli-2.5.0-windows-x64.zip` (sha256 5750dc0b…) loads the DSN, then its routing thread dies on a GraalVM serialization error for `ComponentOutline` and the process hangs silently; `route_board.py` records `router_timeout`. Upstream freerouting/freerouting#957 confirms it and fixes it after 2.5.0. `freerouting-2.5.0.jar` needs Java 25 (class file 69; Java 21 fails with `UnsupportedClassVersionError`); pass the jar to `--freerouting` and the runtime to `--java` (default: `java` on PATH) and the script runs `java -jar`. Passing `-l en` makes it create an `en/freerouting.log` folder in the working directory; `route_board.py` does not pass it.

## Design notes, with sources

| item | choice | source |
|---|---|---|
| Module pins | pad numbers from KiCad `RF_Module:ESP32-S3-WROOM-1`; GND 1/40/41, 3V3 2, EN 3, IO0 27, RXD0 36, TXD0 37, IO8 12 (SDA), IO9 17 (SCL) | KiCad stock symbol; OpenPartsCore `electronic/esp32-s3-wroom-1` |
| Bus pins not strapping/USB | GPIO8/9 checked against `attributes.strapping_pins` {0, 3, 45, 46} and USB {19, 20} | OpenPartsCore entry, cited to the ESP32-S3-WROOM-1 datasheet "Strapping Pins" |
| BME280 I2C, address 0x76 | CSB → 3V3, SDO → GND | Bosch BME280 datasheet §6.2 |
| EN: 10k to 3V3 + 100n to GND; module supply 10u ∥ 100n | R3, C4; C2, C3 | Espressif ESP32-S3 Hardware Design Guidelines (power supply, chip enable). TODO(source): pin the section numbers |
| I2C pull-ups 4.7k | R1, R2 | design choice at 3.3 V |
| IO0 on PROG header, no pull-up | GPIO0 has the chip's internal weak pull-up; a programmer pulls it low | ESP32-S3 datasheet strapping description. TODO(source): confirm the module datasheet does not require an external resistor |
| Headers 2.54 mm 1x04 / 1x06 | J1 SENSOR (3V3, GND, SDA, SCL); J2 PROG (GND, TXD0, RXD0, IO0, EN, 3V3) | OpenPartsCore `electronic/pinheader-2.54-1x04`, `-1x06` (cited to the KiCad footprints; MPN-level data TODO) |
| Mounting holes below y = 17 mm | antenna keepout spans the board width above it | measured on `reference-esp32s3` |
| GND pour, both layers | clearance 0.30 mm, min width 0.25 mm, thermal reliefs 0.30 gap / 0.30 spoke, unconnected islands removed | design choice, wider than the profile's 0.10 mm so the pour never sets the tightest gap; `scripts/add_ground_pour.py`. The module footprint's own keepout rule area keeps copper out from under the antenna |
| `sensor-node.kicad_dru`: `npth_min_hole` 0.50 mm | JLCPCB "Min. Non-plated holes 0.50mm" | copied from `sensor-breakout`, **re-proven here**: at 5.0 mm it reports H1–H4 and nothing else (ADR-0006) |
| Design rules from `jlcpcb-2layer-1oz` | min track 0.10, clearance 0.10, through drill 0.15, via 0.25, hole-to-hole 0.45, copper-edge 0.20 mm | `fab-profiles/jlcpcb-2layer-1oz.json`, cited to JLCPCB's capabilities page; applied with `scripts/apply_fab_profile.py` (the board script's 0.2 mm drill relaxation for the module's thermal vias is superseded by the profile's 0.15) |

## Firmware hand-off

`firmware/pins.rs` is written for OBC-Prime's `Board { i2c: Option<(i32, i32)>, .. }`: `I2C = Some((8, 9))`, `BME280_I2C_ADDR = 0x76`. `firmware/pins.h` carries the same for an ESP-IDF build. `firmware.manifest.json` records the netlist sha256, both OpenPartsCore entry hashes, every derived value with the rule that produced it, and a **proposed** `espflash flash --monitor …` command with `executed: false`. The tool never flashes (ADR-0005; OpenDesignCore ADR-0009 execute-vs-propose). A netlist that puts SDA on a strapping pin is refused with the citation quoted (tested: exit 2, nothing written).

## Not done
- **An assembly order.** `fab/sensor-node-pos.csv` is KiCad's placement file (Ref, Val, Package, PosX, PosY, Rot, Side). JLCPCB's CPL wants Designator / Mid X / Mid Y / Layer / Rotation, and its rotation zero differs per package from KiCad's. Mapping columns is mechanical, but the rotation offsets have to be checked against JLCPCB's placement preview. They are not invented here. The BOM has no LCSC part numbers either, because OpenPartsCore entries are families, not MPNs.
- Silkscreen tidy-up: reference labels overlap at this placement density (warnings only).
- Stitching vias between the two GND pours; the router's GND tracks and vias carry the connection today.
- An OBC-Prime `Board` const for this node that `include!`s `pins.rs`; OBC-Prime targets pre-built dev boards today.
- Enclosure: `sensor-node.step` is exported for OpenDesignCore's mesh import; connector access features (OpenPartsCore ADR-0007) for J1/J2 are not yet written.
