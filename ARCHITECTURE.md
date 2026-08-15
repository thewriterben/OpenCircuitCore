# Architecture

## Pipeline

```
  requirements / device spec
        │
  .ato source  ──────────── authored by humans or agents; reviewed as code
        │  atopile compile (pinned version)
  KiCad project ─────────── schematic + layout + netlist
        │  KiCad CLI (pinned version)
  ERC / DRC ─────────────── fail loudly; a design that doesn't pass doesn't export
        │
  outputs: gerbers, drill, pick-and-place, BOM, 3D
        │
  provenance record: .ato source hash, atopile version, KiCad version,
                     DRC ruleset id, part ids resolved, output hashes
```

## Boundaries

- **Parts:** every component reference resolves to an OpenPartsCore id (`electronic/...`). Footprint/symbol/atopile-package links live there. No component facts are invented here.
- **KiCad:** external process only (GPLv3 containment, ADR-0002). Pin the major version; record it in provenance.
- **Fabrication:** outputs hand off to AdvancedStudio (local) or Project BINGO (network). A BINGO asset can reference this repo's provenance record the same way it references OpenDesignCore's (see ODC wiki: bingo-odc-provenance-contract).
- **Co-design with OpenDesignCore:** board outline, mounting holes, and connector positions are exported as a contract file consumed by enclosure models; format TBD with the ODC thin thread.
- **MCP surface (later):** compile/verify/BOM as tools, following the ecosystem convention — reads execute, writes propose.

## Determinism

Same .ato source, same pinned atopile + KiCad versions, same DRC ruleset → identical outputs. Where a tool is nondeterministic (autorouting, if ever used), its output is committed as source, not regenerated in CI.
