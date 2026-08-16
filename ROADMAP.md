# Roadmap

## Now
- [x] Toolchain decided and verified present: KiCad 10.0.5 + `kicad-cli` (ADR-0003, supersedes atopile) (2026-08-15)
- [x] Reference board: ESP32-S3 module + I2C sensor placed, **DRC clean**, STL/STEP exported (2026-08-15)
- [x] Schematic: netlist-described, **ERC clean**, netlist and BOM exported (2026-08-15)
- [x] BOM entries resolve to OpenPartsCore ids, including the generic 0603 passives (2026-08-15)
- [ ] Gerbers and drill files exported and checked against a fab's rules
- [ ] Provenance record emitted per build (design hash, KiCad version, DRC ruleset, output hashes) — OpenDesignCore does this; this repo does not yet

- [x] Schematic drives the board: `boards/sensor-breakout` takes its parts from the shared description and its **nets from the schematic's exported netlist**; 0 DRC violations, unrouted ratsnest reported honestly (2026-08-15)

## Next
- [ ] Routing: interactive in KiCad, or an external router. Not writing one.
- [ ] A connector on the breakout so power and I2C have somewhere to land
- [x] Board → enclosure co-design: `pcb export step` into OpenDesignCore's mesh import boundary, enclosure fitted to the real board (2026-08-15)
- [ ] Distributor sourcing: BOM → live price/stock (Octopart/Mouser/LCSC) with price-break optimisation
- [ ] Fab DRC profiles (JLC/PCBWay/OSH Park rule sets, versioned)
- [ ] MCP surface: design / verify / bom as tools (ADR-0009 execute-vs-propose line)

## Not ever
- Linking KiCad (GPLv3 stays at the process boundary)
- Invented component values — OpenPartsCore or datasheet citation, else TODO(source)
- A hosted/SaaS dependency in the design path: this platform runs offline
