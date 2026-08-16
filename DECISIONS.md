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

---

## ADR-0004 — Netlist-as-source: ADR-0003's authoring concession was overstated

**Date:** 2026-08-15
**Status:** accepted. Amends the *consequences* of ADR-0003; the decision itself (KiCad, not atopile) stands.

**Context.** ADR-0003 accepted a real cost when it dropped atopile: *"Authoring ergonomics get worse: schematics become KiCad files rather than reviewable text, which is a real loss and the thing atopile was chosen for."* Building the first schematic showed that concession was larger than the facts required.

`scripts/make_reference_schematic.py` declares a circuit as parts plus `(part, pin) → net` and derives all geometry. Every connection is a global label placed exactly on the pin's connection point, so nets form by name and there is no wire routing to get subtly wrong. Symbol definitions are lifted verbatim from KiCad's stock libraries into `lib_symbols`, as the format requires.

**Decision.** The netlist description is the source; the `.kicad_sch` is a build artifact, regenerated and not hand-edited. Reviews read the netlist. This is recorded so nobody re-opens the atopile question on the grounds of a loss we have largely recovered.

**Consequences.** Most of what atopile offered — diffable, reviewable, agent-writable circuit source — is available without a hosted dependency or a maintenance-only CLI. What remains genuinely worse: no type system over connections, no package manager for reusable modules, and no schematic *layout* aesthetics (generated sheets are functional, not pretty). Editing a generated schematic in KiCad's GUI puts the artifact ahead of its source, which is a hazard to warn about in CONTRIBUTING rather than to prevent mechanically. Current limits: rotation-0 placement only, and generated sheets do not yet drive the board's netlist.

---

## ADR-0005 — The MCP surface inspects and verifies; it does not regenerate

**Date:** 2026-08-15
**Status:** accepted. Applies OpenDesignCore ADR-0009's execute-vs-propose line to this repo.

**Context.** ADR-0009 draws the line at the store boundary: effects confined to a peer's own content-addressed stores execute, anything reaching beyond stops at a proposal. That rule does not transfer cleanly here, because this repo's writes are not content-addressed artifacts — they are **design source files a human also edits**. `make_sensor_breakout.py` overwrites `sensor-breakout.kicad_pcb`. ADR-0004 already names the hazard: editing a generated file in KiCad's GUI puts the artifact ahead of its source.

Combine the two and the failure is concrete: a person spends an evening routing a board in KiCad, an agent calls a `regenerate` tool for an unrelated reason, and the routing is gone. There is no undo, and git will only help if the work was committed.

**Options considered.**
1. Expose regeneration and execute it — fastest for agents, and destroys human work the first time it is wrong.
2. Expose it as a proposal — requires an approval mechanism this repo does not have and would have to invent. ODC could propose to AdvancedStudio because the studio already owns an approval queue; there is no equivalent here.
3. Do not expose it. Building is a person's action at the CLI.

**Decision.** Option 3. The surface is `list_boards`, `get_bom`, `get_provenance`, `list_fab_profiles`, and `verify`. All execute: their only writes are regenerable ERC/DRC reports, and none can alter a design. Tools that would overwrite design files, export fab packages, or apply a fab profile are absent, and `get_provenance` names the CLI command to run when a record is missing rather than quietly producing one.

**Consequences.** An agent can answer everything worth asking about a design — what is on it, what it costs in parts, whether it passes, against whose rules — and cannot damage one. The cost is that agent-driven design iteration stops at inspection, which is the right trade until this repo has something that can distinguish "regenerate a file nobody has touched" from "regenerate over a human's work". A git-cleanliness check would be that something, and is the obvious way to revisit this; it is not worth building before a real workflow needs it.

**Not a general rule.** ADR-0009's store-boundary test still holds where writes really are content-addressed. This repo is the case where the boundary is a working tree instead, and the answer differs.
