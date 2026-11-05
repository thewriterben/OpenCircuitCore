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
kicad-cli pcb drc --severity-error -o boards/sensor-node/drc-report.txt boards/sensor-node/sensor-node.kicad_pcb
python scripts/lf.py boards/sensor-node/drc-report.txt
<KiCad>/bin/python.exe scripts/route_board.py boards/sensor-node/sensor-node.kicad_pcb --freerouting <freerouting exe or jar>
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
board:     outline 44.0 x 52.0 mm, 11 components, 4 x M3 holes
DRC:       Found 0 violations, Found 34 unconnected items
routing:   router_missing -- sensor-node.dsn exported, routing.json says so
firmware:  I2C SDA=GPIO8 SCL=GPIO9, BME280 at 0x76 (SDO->GND, CSB->+3V3); strapping/USB pins clear
```

**34 unconnected is the honest state**: the ratsnest is correct and nothing is routed. `route_board.py` exits 3 and keeps the DSN when FreeRouting is not given. To route headlessly, download FreeRouting 2.5.0 for Windows x64 from <https://github.com/freerouting/freerouting/releases> and pass its path with `--freerouting`; the script exports DSN with `pcbnew.ExportSpecctraDSN`, runs `-de … -do … -mp 20 --gui.enabled=false`, imports the SES, re-runs DRC and writes `routing.json` with the hash of every input and output. FreeRouting is GPL-3.0 and stays a separate process, like KiCad (DECISIONS.md).

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
| 0.2 mm min through drill | module thermal vias | same relaxation as `reference-esp32s3` |

## Firmware hand-off

`firmware/pins.rs` is written for OBC-Prime's `Board { i2c: Option<(i32, i32)>, .. }`: `I2C = Some((8, 9))`, `BME280_I2C_ADDR = 0x76`. `firmware/pins.h` carries the same for an ESP-IDF build. `firmware.manifest.json` records the netlist sha256, both OpenPartsCore entry hashes, every derived value with the rule that produced it, and a **proposed** `espflash flash --monitor …` command with `executed: false`. The tool never flashes (ADR-0005; OpenDesignCore ADR-0009 execute-vs-propose). A netlist that puts SDA on a strapping pin is refused with the citation quoted (tested: exit 2, nothing written).

## Not done
- Routing (needs FreeRouting on disk, see above) and therefore gerbers.
- An OBC-Prime `Board` const for this node that `include!`s `pins.rs`; OBC-Prime targets pre-built dev boards today.
- Enclosure: `sensor-node.step` is exported for OpenDesignCore's mesh import; connector access features (OpenPartsCore ADR-0007) for J1/J2 are not yet written.
