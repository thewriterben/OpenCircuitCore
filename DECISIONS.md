# Decisions

Append-only. Newest at the bottom.

---

## ADR-0001 — atopile for authoring, KiCad as verification and output substrate

**Date:** 2026-08-15
**Status:** **superseded by ADR-0003** the same day, on evidence from actually installing atopile: its CLI is maintenance-only and the product has moved to a hosted workspace. Retained as written, per the append-only rule.

**Context.** The platform needs deterministic, diffable, agent-writable circuit design with real verification and fab-accepted outputs. Candidates surveyed 2026-08: KiCad scripted directly (mature ERC/DRC, but designs live as GUI-oriented files); atopile (MIT, active, code-as-schematic compiling to KiCad projects incl. BOM and fab files); tscircuit (MIT, React/TS, active — but ERC/DRC incomplete as of v0.0.x, and it bypasses KiCad's verification).

**Decision.** Author in atopile; compile to KiCad projects; run KiCad ERC/DRC and output generation on the result. tscircuit stays on watch for browser preview UX only.

**Consequences.** Two toolchain dependencies to pin (atopile release, KiCad major version) — recorded per design in provenance, mirroring OpenDesignCore ADR-0003's treatment of voxel size. Designs are text and review like code. KiCad's GUI remains an escape hatch on the compiled project, with the caveat that GUI edits are downstream artifacts, not source. If atopile stalls, the KiCad projects it emitted remain usable — the exit cost is authoring, not data.

---

## ADR-0002 — Apache-2.0; KiCad invoked at arm's length

**Date:** 2026-08-15
**Status:** accepted (PD-4)

Repo licence Apache-2.0, uniform with OpenDesignCore and OpenPartsCore. KiCad is GPLv3: it is executed as an external process (CLI/IPC) and never linked; its outputs (our designs) are ours. atopile is MIT. Not legal advice; revisit with counsel if commercial weight arrives.

---

## ADR-0003 — KiCad directly; atopile dropped

**Date:** 2026-08-15
**Status:** accepted. **Supersedes ADR-0001** (and platform decision PD-1), which chose atopile for authoring.

**Context.** ADR-0001 was decided on a premise that turned out to be stale within the day. Verified by installing it:

- The `atopile` package resolves to **0.12.6**, which prints on startup: *"atopile 0.12 is no longer supported. The CLI has been replaced by the app at app.atopile.io (atopile 0.16+). If you need the classic CLI a little longer, upgrade to atopile 0.15.8 — the last CLI release, in maintenance mode only."*
- **0.15.8 is the last CLI release and is maintenance-only.** It pins `Python >=3.14,<3.15`, and its `zstd` dependency ships no cp314 wheel, so installing it requires MSVC C++ Build Tools. Two install attempts failed on that wheel build.
- **0.16+ is a hosted browser workspace** ("instant cloud workspace, no install needed"), with a VS Code/Cursor extension as the recommended entry point.

A hosted workspace is a reasonable product and a poor foundation for this platform, which is local-first and offline-capable everywhere else in the stack — a pinned geometry kernel, a stdlib-only settlement layer, a local-first print studio. Building the electronics half on either a frozen CLI or a SaaS dependency would be the one component that cannot run on a bench with the network unplugged.

ADR-0001 anticipated exactly this: *"If atopile stalls, the KiCad projects it emitted remain usable — the exit cost is authoring, not data."* That exit clause is now live, and it is cheap because nothing has been authored yet.

**Options considered.**
1. Install MSVC Build Tools and pin atopile 0.15.8 — preserves code-as-schematic ergonomics on a tool whose vendor has moved on, plus a multi-GB build prerequisite for every contributor.
2. tscircuit (MIT, active, React/TS) — attractive, but ERC/DRC were incomplete as of 2026-08, so KiCad would remain the verification substrate anyway; adopting it would add a layer rather than replace one. Stays on the watch list.
3. KiCad directly.

**Decision.** Option 3. KiCad is the authoring, verification, and output substrate. Verified present and working here: **KiCad 10.0.5**, `kicad-cli` exposing `sch erc`, `sch export` (netlist, BOM, PDF), `pcb drc`, and `pcb export` (Gerbers, drill, position, ODB++, IPC-D-356, **STEP**, **STL**, VRML), plus a bundled Python 3.11 for scripting. KiCad remains an **external process only — CLI/IPC, never linked** (ADR-0002 GPL containment is unchanged and now carries more weight).

**Consequences.** Authoring ergonomics get worse: schematics become KiCad files rather than reviewable text, which is a real loss and the thing atopile was chosen for. Mitigations: KiCad's formats are S-expression text and diffable; generation and edits go through scripts under version control; netlist and BOM are exported for review. In exchange, the electronics half now rests on a tool that is genuinely open, offline, long-lived, and already installed.

**A gain that was not the motivation but matters:** `pcb export step|stl` gives a verified path from board geometry into OpenDesignCore's mesh import boundary — board outline, components, and mounting holes as a solid the enclosure model can fit around. The board↔enclosure co-design in the platform's use-case map now has a concrete mechanism instead of a hope.
