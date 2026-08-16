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
- `scripts/emit_provenance.py`: every board build now emits a provenance record — design sources and their hashes, upstream netlist (so a board whose nets came from another directory's schematic says so), outputs, ERC/DRC results, KiCad version, commit. Canonicalisation is byte-identical to Project BINGO's kernel and OpenDesignCore's C# port, so hashes computed here are comparable there; floats are refused for the same reason. Closes the invariant this repo was failing while OpenDesignCore held it.
- Two parsing bugs found by running it rather than trusting it: KiCad writes `Found 0 DRC violations` in reports but `Found 0 violations` on the console, and **ERC reports use an entirely different shape** (`** ERC messages: 0  Errors 0  Warnings 0`). The first version silently recorded "unknown" and called it a build; it now refuses to emit a record claiming a check happened whose result it could not read.
- `fab-profiles/jlcpcb-2layer-1oz.json` + `scripts/apply_fab_profile.py`: a manufacturer's published capability, **cited to the vendor's page**, applied to a board's design settings so DRC asks the question that matters — not "is this self-consistent" but "will this house build it". `sensor-breakout` passes JLCPCB's stated 2-layer 1 oz minimums with 0 violations. The script refuses to apply a profile with no citation.
- Four capabilities are listed as **deliberately not encoded** rather than approximated, including the via annular minimum: the vendor states a PTH annular ring but no via-specific figure, and deriving one would have been inventing a tolerance. Marked TODO(source).
- Gerbers and drill exported to `boards/sensor-breakout/fab/` (25 layer files + drill); all 26 now hashed into the provenance record.
