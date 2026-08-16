# Roadmap

## Now
- [x] Toolchain decided and verified present: KiCad 10.0.5 + `kicad-cli` (ADR-0003, supersedes atopile) (2026-08-15)
- [ ] Reference board end to end: ESP32-S3 module + one I2C sensor → KiCad project → ERC clean → DRC clean → gerbers + BOM
- [ ] BOM entries resolve to OpenPartsCore ids (drives the first cited `electronic` entries with footprint/symbol links)
- [ ] Provenance record emitted per build (design hash, KiCad version, DRC ruleset, output hashes)

## Next
- [ ] Board → enclosure co-design: `pcb export step` into OpenDesignCore's mesh import boundary, enclosure fitted to the real board
- [ ] Distributor sourcing: BOM → live price/stock (Octopart/Mouser/LCSC) with price-break optimisation
- [ ] Fab DRC profiles (JLC/PCBWay/OSH Park rule sets, versioned)
- [ ] MCP surface: design / verify / bom as tools (ADR-0009 execute-vs-propose line)

## Not ever
- Linking KiCad (GPLv3 stays at the process boundary)
- Invented component values — OpenPartsCore or datasheet citation, else TODO(source)
- A hosted/SaaS dependency in the design path: this platform runs offline
