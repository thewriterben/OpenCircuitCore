# Architecture

## Pipeline

```
  requirements / device spec
        │
  design scripts ───────── version-controlled; KiCad files are the artifacts they produce
        │  kicad-cli (pinned major version)
  KiCad project ────────── schematic + layout + netlist
        │
  sch erc / pcb drc ────── fail loudly; a design that does not pass does not export
        │
  outputs: gerbers, drill, position, ODB++, IPC-D-356, BOM, STEP/STL
        │
  provenance record: design source hash, KiCad version, DRC ruleset id,
                     part ids resolved, output hashes
```

## Verified toolchain (2026-08-15)

KiCad **10.0.5**, `kicad-cli` at `%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe`:

| Command | Use |
|---|---|
| `sch erc` | Electrical rules check, with report |
| `sch export netlist \| bom \| pdf` | Netlist and BOM for review and downstream resolution |
| `pcb drc` | Design rules check, with report |
| `pcb export gerbers \| drill \| pos` | Fabrication and assembly outputs |
| `pcb export step \| stl \| vrml` | **Board geometry for enclosure co-design** |
| `pcb export odb \| ipcd356` | Modern fab interchange and netlist test |

A Python 3.11 runtime ships alongside for `pcbnew` scripting where the CLI is not enough.

## Boundaries

- **Parts:** every component reference resolves to an OpenPartsCore id (`electronic/...`). Footprint, symbol, and datasheet links live there. No component facts are invented here.
- **KiCad:** external process only (GPLv3 containment, ADR-0002). Pin the major version; record it in provenance.
- **Fabrication:** outputs hand off to AdvancedStudio (local) or Project BINGO (network). A BINGO asset can reference this repo's provenance record the same way it references OpenDesignCore's (see ODC wiki: bingo-odc-provenance-contract).
- **Co-design with OpenDesignCore:** `pcb export step` (or `stl`) produces the board solid; ODC imports it at its mesh boundary — units declared, content-addressed — and fits the enclosure to it. This replaces the "contract file, format TBD" that stood here before, with a mechanism that exists.
- **MCP surface (later):** design / verify / bom as tools, following ADR-0009 in OpenDesignCore — effects inside our own stores execute, anything reaching a fabricator proposes.

## Determinism

Same design source, same pinned KiCad version, same DRC ruleset → identical outputs. Where a step is nondeterministic (autorouting, if ever used), its output is committed as source rather than regenerated in CI.
