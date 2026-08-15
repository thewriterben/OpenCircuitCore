# Dependencies

| Dependency | Version | License | Role | Containment |
|---|---|---|---|---|
| atopile | ⟨pin on first use⟩ | MIT | Authoring compiler (.ato → KiCad project) | normal dependency |
| KiCad | ⟨pin major version⟩ | GPLv3 | ERC/DRC, libraries, output generation | **external process only — never linked** (ADR-0002) |
| OpenPartsCore | ⟨repo, schema v0⟩ | Apache-2.0 | Part ids, footprints/symbols/package links | data dependency |

Watch list (not dependencies): tscircuit (MIT) — browser preview UX candidate; ERC/DRC immature as of 2026-08.
