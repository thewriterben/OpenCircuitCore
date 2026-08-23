#!/usr/bin/env python3
"""Every BOM line must resolve to a real OpenPartsCore id.

    python scripts/verify_bom.py [--parts <dir>]

README: "part references resolved against OpenPartsCore" and "No invented
component data: every part fact traces to OpenPartsCore (cited) or a datasheet."
Nothing checked either claim.

An `opc_id` that does not resolve fails in the worst available way — it looks
exactly like one that does. The BOM renders, the board builds, and the failure
surfaces at sourcing, where somebody orders against a name the registry has never
heard of. Same shape as OpenBuildCore's referential checks, which exist because
an unresolvable `part_id` is indistinguishable from an ordinary gap.

Stdlib only, and it imports nothing from OpenPartsCore: it reads the data files,
which already had to exist.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARTS = ROOT.parent / "OpenPartsCore"


def load_registry(parts: Path) -> set[str]:
    data = parts / "data"
    if not data.exists():
        raise SystemExit(
            f"OpenPartsCore not found at {data}.\n"
            f"Every opc_id would have nothing to resolve against, and an unresolvable\n"
            f"id is indistinguishable from a resolvable one until somebody tries to\n"
            f"order it. Pass --parts, or check the repo out beside this one."
        )
    return {json.loads(p.read_text(encoding="utf-8"))["id"]
            for p in sorted(data.rglob("*.json"))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts", type=Path, default=DEFAULT_PARTS)
    args = parser.parse_args()

    registry = load_registry(args.parts)
    boms = sorted((ROOT / "boards").rglob("*bom.json"))
    if not boms:
        print("No BOMs found under boards/. Failing rather than passing a check "
              "that checked nothing.", file=sys.stderr)
        return 1

    problems, lines = [], 0
    for bom in boms:
        data = json.loads(bom.read_text(encoding="utf-8"))
        where = bom.relative_to(ROOT)
        for component in data.get("components", []):
            lines += 1
            opc_id = component.get("opc_id")
            refs = component.get("refs", "?")
            if not opc_id:
                problems.append(f"{where}: {refs} ({component.get('value','?')}) "
                                f"has no opc_id — it traces to nothing")
            elif opc_id not in registry:
                problems.append(f"{where}: {refs} cites '{opc_id}', which is not in the "
                                f"registry — this reads as a real part right up until "
                                f"somebody tries to order it")
            elif not (component.get("citation") or "").strip():
                problems.append(f"{where}: {refs} resolves to '{opc_id}' but carries no "
                                f"citation")

    print(f"{len(boms)} BOM(s), {lines} line(s) against {len(registry)} registry part(s)")
    for problem in problems:
        print(f"  FAIL {problem}")
    print("all resolve" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
