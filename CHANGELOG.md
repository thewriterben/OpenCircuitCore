# Changelog

## [Unreleased]
### Added
- Repo scaffolded: ADR-0001 (atopile + KiCad), ADR-0002 (Apache-2.0, GPL containment), architecture, roadmap, dependency policy.

### Changed
- **ADR-0003 supersedes ADR-0001: KiCad directly, atopile dropped.** Established by installing it: the `atopile` CLI is maintenance-only (0.15.8 last release, pins Python 3.14, `zstd` has no cp314 wheel so it needs MSVC Build Tools), and 0.16+ moved to a hosted browser workspace. A SaaS dependency in the design path conflicts with a platform that is local-first everywhere else. Toolchain verified present: KiCad 10.0.5 with `kicad-cli` (`sch erc`, `sch export`, `pcb drc`, `pcb export` incl. gerbers, drill, ODB++, IPC-D-356, STEP, STL).
- Architecture updated: the board→enclosure co-design path is now a verified mechanism (`pcb export step|stl` into OpenDesignCore's mesh import boundary) rather than a "format TBD" placeholder.

### Added
- `scripts/make_reference_board.py` + `boards/reference-esp32s3/`: first board through the toolchain, generated deterministically with KiCad's own `pcbnew` API — 30 × 40 mm outline, 4 × M3 mounting holes. **DRC: 0 violations, 0 unconnected.** STEP and STL exported.
- Co-design bridge exercised for real: the exported STL feeds OpenDesignCore's mesh import boundary and produces an enclosure fitted to the actual board geometry (ODC run 3). This turned ADR-0003's claimed path into a tested one — and surfaced that `kicad-cli` emits **ASCII** STL, which PicoGK refuses; fixed in OpenDesignCore PR #8.

Scope note: geometry only. No schematic, netlist, or components yet — the carrier size and hole inset are placeholders, not cited values, until a schematic constrains them.
- `boards/sensor-breakout` + `scripts/make_sensor_breakout.py`: the first board whose **connectivity is derived from its schematic**. Parts come from `make_reference_schematic.PARTS` (one source of truth for both) and pads are bound to nets parsed from the schematic's exported netlist, using `NETINFO_ITEM` + `pad.SetNet`. Result: **0 DRC violations, 10 unconnected items** — correct nets, unrouted ratsnest, which is the honest state to hand to a router. Verified from the saved file that U2's pads carry GND/+3V3/SDA/SCL as the schematic specifies.
- Closes the gap named in `reference-esp32s3`: there, schematic and board were generated independently with nothing stopping them disagreeing.
