# OpenCircuitCore

The electronics engine of the OpenDesignCore platform: circuits authored as code, verified and emitted through KiCad.

**Status:** pre-alpha. Toolchain decided (ADR-0001); no reference board yet.

## What it is

- **Authoring:** [atopile](https://atopile.io) — circuits as reviewable, diffable code that compiles to KiCad projects.
- **Verification & outputs:** KiCad — ERC/DRC, footprint/symbol libraries, Gerbers/drill/pick-and-place, fab-accepted everything.
- **BOM:** generated from the design, part ids resolved against [OpenPartsCore](../OpenPartsCore); pricing/stock fetched live from distributor APIs by consumers.
- **Boundary:** KiCad (GPLv3) is invoked strictly as an external tool — CLI/IPC, never linked (DEPENDENCIES.md).

## What it is not

- Not a schematic drawing app. Authoring is code; KiCad's GUI remains available on the compiled project.
- Not a parts database — that's OpenPartsCore.
- Not a fabricator — outputs hand off to local printing/milling or the Project BINGO network.
- No invented component data: every part fact traces to OpenPartsCore (cited) or a datasheet.

## Planned shape (see ARCHITECTURE.md)

```
design (.ato) → compile → KiCad project → ERC/DRC → gerbers + BOM + provenance record
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
