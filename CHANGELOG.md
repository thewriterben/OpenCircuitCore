# Changelog

## [Unreleased]
### Added
- Repo scaffolded: ADR-0001 (atopile + KiCad), ADR-0002 (Apache-2.0, GPL containment), architecture, roadmap, dependency policy.

### Changed
- **ADR-0003 supersedes ADR-0001: KiCad directly, atopile dropped.** Established by installing it: the `atopile` CLI is maintenance-only (0.15.8 last release, pins Python 3.14, `zstd` has no cp314 wheel so it needs MSVC Build Tools), and 0.16+ moved to a hosted browser workspace. A SaaS dependency in the design path conflicts with a platform that is local-first everywhere else. Toolchain verified present: KiCad 10.0.5 with `kicad-cli` (`sch erc`, `sch export`, `pcb drc`, `pcb export` incl. gerbers, drill, ODB++, IPC-D-356, STEP, STL).
- Architecture updated: the board→enclosure co-design path is now a verified mechanism (`pcb export step|stl` into OpenDesignCore's mesh import boundary) rather than a "format TBD" placeholder.
