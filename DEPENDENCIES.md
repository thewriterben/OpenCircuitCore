# Dependencies

| Dependency | Version | License | Role | Containment |
|---|---|---|---|---|
| KiCad | pin major `10.x` (verified 10.0.5) | GPLv3 | Schematic capture, ERC, layout, DRC, libraries, all outputs | **external process only — never linked** (ADR-0002) |
| OpenPartsCore | schema v0 | Apache-2.0 | Part ids, footprint/symbol/datasheet links | data dependency |

Dropped: **atopile** (ADR-0003). Its CLI is maintenance-only, 0.16+ moved to a hosted browser workspace, and the last CLI release (0.15.8) pins Python 3.14 with a `zstd` dependency that has no cp314 wheel — it will not install without MSVC C++ Build Tools.

Watch list (not dependencies): **tscircuit** (MIT) — actively developed React/TS authoring; ERC/DRC incomplete as of 2026-08, so KiCad would remain the verification substrate. Revisit if its verification matures.
