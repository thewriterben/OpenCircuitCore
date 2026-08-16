#!/usr/bin/env python3
"""Apply a cited fab profile's constraints to a board, then it can be DRC'd.

    <KiCad>/bin/python.exe scripts/apply_fab_profile.py <board.kicad_pcb> <profile-id>

A fab profile is a manufacturer's published capability, cited, in
`fab-profiles/`. Applying one means the board's DRC now asks the question that
matters: not "is this self-consistent" but "will this house actually build it".

Constraints are strings in the profile so no float ever round-trips through
JSON; they are converted here at one place.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "fab-profiles"

# Profile key -> DesignSettings attribute. Only keys listed here are applied;
# anything else in the profile is a documentation field and stays out of DRC.
SETTINGS = {
    "track_min_width": "m_TrackMinWidth",
    "min_clearance": "m_MinClearance",
    "min_through_drill": "m_MinThroughDrill",
    "vias_min_size": "m_ViasMinSize",
    "hole_to_hole_min": "m_HoleToHoleMin",
    "copper_edge_clearance": "m_CopperEdgeClearance",
    "silk_clearance": "m_SilkClearance",
    "min_silk_text_height": "m_MinSilkTextHeight",
    "min_silk_text_thickness": "m_MinSilkTextThickness",
}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    board_path = Path(sys.argv[1]).resolve()
    profile_path = PROFILES / f"{sys.argv[2]}.json"

    if not board_path.exists():
        print(f"board not found: {board_path}", file=sys.stderr)
        return 1
    if not profile_path.exists():
        available = ", ".join(sorted(p.stem for p in PROFILES.glob("*.json")))
        print(f"unknown profile '{sys.argv[2]}'. Available: {available}", file=sys.stderr)
        return 1

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not profile.get("source", {}).get("citation", "").strip():
        print("profile has no citation; refusing to apply invented tolerances",
              file=sys.stderr)
        return 1

    board = pcbnew.LoadBoard(str(board_path))
    settings = board.GetDesignSettings()

    applied = {}
    for key, value in profile["constraints_mm"].items():
        attribute = SETTINGS.get(key)
        if attribute is None:
            print(f"  note: '{key}' has no board-wide setting; not applied")
            continue
        setattr(settings, attribute, pcbnew.FromMM(float(value)))
        applied[key] = value

    pcbnew.SaveBoard(str(board_path), board)

    print(f"applied {profile['id']} to {board_path.name}")
    print(f"  {profile['name']}")
    for key, value in sorted(applied.items()):
        print(f"    {key:<26} {value} mm")
    if profile.get("not_encoded"):
        print(f"  {len(profile['not_encoded'])} capability/ies deliberately not encoded "
              "(see the profile's not_encoded list)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
