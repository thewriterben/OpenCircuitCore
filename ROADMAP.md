# Roadmap

## Now
- [x] Toolchain decided and verified present: KiCad 10.0.5 + `kicad-cli` (ADR-0003, supersedes atopile) (2026-08-15)
- [x] Reference board: ESP32-S3 module + I2C sensor placed, **DRC clean**, STL/STEP exported (2026-08-15)
- [x] Schematic: netlist-described, **ERC clean**, netlist and BOM exported (2026-08-15)
- [x] BOM entries resolve to OpenPartsCore ids, including the generic 0603 passives (2026-08-15)
- [x] Gerbers and drill exported, and DRC run against a **cited** fab profile (JLCPCB 2-layer 1 oz): 0 violations (2026-08-15)
- [x] `sensor-node` fab package: routed, GND poured both layers, DRC 0 with its own proven `.kicad_dru`, 9 Gerber layers + drill + placement CSV under provenance (2026-11-05)
- [ ] JLCPCB assembly files: CPL column mapping plus per-package rotation offsets checked against the vendor preview; BOM with LCSC numbers
- [x] Provenance record emitted per build: sources, upstream netlist, outputs, ERC/DRC results, KiCad version, commit — canonical JSON, hash-comparable with OpenDesignCore and BINGO; refuses to emit when a check result is unreadable (2026-08-15)

- [x] Schematic drives the board: `boards/sensor-breakout` takes its parts from the shared description and its **nets from the schematic's exported netlist**; 0 DRC violations, unrouted ratsnest reported honestly (2026-08-15)

## Next
- [x] Routing: `scripts/route_board.py` drives FreeRouting 2.5.0 headlessly (DSN → SES → DRC, hashed in `routing.json`); `sensor-node` routed clean, 143 tracks / 8 vias / DRC 0 against the JLCPCB profile. Exits 3 with the DSN kept when no router is given. Still not writing one (2026-11-04)
- [x] Connectors: `boards/sensor-node` has a 1x04 sensor header and a 1x06 programming header, both registry entries (2026-11-04)
- [x] Firmware from the netlist: `scripts/make_firmware.py` derives I2C GPIOs and the BME280 address from the exported netlist, refuses strapping/USB pins from the cited registry list, proposes (never runs) the `espflash` deploy (2026-11-04)
- [ ] OBC-Prime `Board` const that consumes `firmware/pins.rs`; build and flash the sensor-node image once a board exists
- [x] Board → enclosure co-design: `pcb export step` into OpenDesignCore's mesh import boundary, enclosure fitted to the real board (2026-08-15)
- [ ] Distributor sourcing: BOM → live price/stock (Octopart/Mouser/LCSC) with price-break optimisation
- [ ] More fab profiles (PCBWay, OSH Park) alongside the JLCPCB one; each cited to the vendor's published capability
- [ ] Custom rule file (`.kicad_dru`) for the capabilities KiCad has no board-wide setting for: NPTH annular ring, min non-plated hole, via annular ring
- [ ] MCP surface: design / verify / bom as tools (ADR-0009 execute-vs-propose line)

## Not ever
- Linking KiCad (GPLv3 stays at the process boundary)
- Invented component values — OpenPartsCore or datasheet citation, else TODO(source)
- A hosted/SaaS dependency in the design path: this platform runs offline
