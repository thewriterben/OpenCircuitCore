# Decisions

Append-only. Newest at the bottom.

---

## ADR-0001 — atopile for authoring, KiCad as verification and output substrate

**Date:** 2026-08-15
**Status:** accepted (platform decision PD-1, recorded in OpenDesignCore `wiki/concepts/platform-decisions.md`)

**Context.** The platform needs deterministic, diffable, agent-writable circuit design with real verification and fab-accepted outputs. Candidates surveyed 2026-08: KiCad scripted directly (mature ERC/DRC, but designs live as GUI-oriented files); atopile (MIT, active, code-as-schematic compiling to KiCad projects incl. BOM and fab files); tscircuit (MIT, React/TS, active — but ERC/DRC incomplete as of v0.0.x, and it bypasses KiCad's verification).

**Decision.** Author in atopile; compile to KiCad projects; run KiCad ERC/DRC and output generation on the result. tscircuit stays on watch for browser preview UX only.

**Consequences.** Two toolchain dependencies to pin (atopile release, KiCad major version) — recorded per design in provenance, mirroring OpenDesignCore ADR-0003's treatment of voxel size. Designs are text and review like code. KiCad's GUI remains an escape hatch on the compiled project, with the caveat that GUI edits are downstream artifacts, not source. If atopile stalls, the KiCad projects it emitted remain usable — the exit cost is authoring, not data.

---

## ADR-0002 — Apache-2.0; KiCad invoked at arm's length

**Date:** 2026-08-15
**Status:** accepted (PD-4)

Repo licence Apache-2.0, uniform with OpenDesignCore and OpenPartsCore. KiCad is GPLv3: it is executed as an external process (CLI/IPC) and never linked; its outputs (our designs) are ours. atopile is MIT. Not legal advice; revisit with counsel if commercial weight arrives.
