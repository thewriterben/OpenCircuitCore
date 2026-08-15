# Roadmap

## Now
- [ ] Pin toolchain: atopile release + KiCad major version; record install steps
- [ ] Reference board end to end: ESP32-S3 module + one I2C sensor in .ato → KiCad project → ERC/DRC clean → gerbers + BOM
- [ ] BOM entries resolve to OpenPartsCore ids (drives the `electronic` namespace's first entries)
- [ ] Provenance record emitted per build

## Next
- [ ] Distributor sourcing: BOM → live price/stock (Octopart/Mouser/LCSC APIs) with price-break optimisation
- [ ] Fab DRC profiles (JLC/PCBWay/OSH Park rule sets, versioned)
- [ ] Board-outline contract file for OpenDesignCore enclosure co-design
- [ ] MCP surface: compile / verify / bom as tools

## Not ever
- Linking KiCad (GPLv3 stays at process boundary)
- Invented component values — OpenPartsCore or datasheet citation, else TODO(source)
- GUI-first design files as source of truth (.ato is source; KiCad projects are build artifacts)
