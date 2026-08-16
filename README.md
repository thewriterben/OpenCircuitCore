# OpenCircuitCore

The electronics engine of the OpenDesignCore platform: circuits designed, verified, and manufactured through KiCad, scripted.

**Status:** pre-alpha. Toolchain decided and verified present (ADR-0003); no reference board yet.

## What it is

- **Substrate:** [KiCad](https://kicad.org) 10.x — schematic capture, ERC, PCB layout, DRC, footprint/symbol libraries, and fab outputs. Driven through `kicad-cli` and scripts, not by hand in the GUI.
- **BOM:** generated from the design, part references resolved against [OpenPartsCore](https://github.com/thewriterben/OpenPartsCore); pricing and stock fetched live from distributor APIs by consumers, never stored.
- **Co-design bridge:** `kicad-cli pcb export step|stl` emits board geometry that OpenDesignCore's mesh import boundary consumes — so an enclosure can be fitted to the actual board, not to a guess.
- **Boundary:** KiCad (GPLv3) is invoked strictly as an external tool — CLI/IPC, never linked (ADR-0002).

## Why not atopile

It was the original choice (ADR-0001) and was dropped the same day on evidence: the CLI is maintenance-only, 0.16+ moved to a hosted browser workspace, and the last CLI release will not install without a C++ toolchain. This platform is local-first and offline-capable everywhere else; the electronics half is not going to be the exception. Full reasoning in ADR-0003. tscircuit stays on the watch list.

## What it is not

- Not a parts database — that's OpenPartsCore.
- Not a fabricator — outputs hand off to local fabrication or the Project BINGO network.
- No invented component data: every part fact traces to OpenPartsCore (cited) or a datasheet.

## Planned shape (see ARCHITECTURE.md)

```
design scripts → KiCad project → ERC → DRC → gerbers + BOM + STEP/STL + provenance record
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
