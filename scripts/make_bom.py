#!/usr/bin/env python3
"""Generate a BOM from the board, resolved against OpenPartsCore.

Run with KiCad's bundled Python:
    <KiCad>/bin/python.exe scripts/make_bom.py <board.kicad_pcb> <openpartscore-dir>

Every line resolves through the footprint's `opc_id` field to a cited registry
entry. A component without an `opc_id`, or with one the registry does not know,
is an error -- not a blank cell. An unresolved BOM line is how wrong parts get
ordered.

Mounting hardware (references starting H) is reported separately: it is real,
orderable, and not yet in the registry.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import pcbnew


def load_registry(opc_dir: Path) -> dict:
    entries = {}
    for path in sorted((opc_dir / "data").rglob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        entries[entry["id"]] = entry
    if not entries:
        raise SystemExit(f"no registry entries under {opc_dir / 'data'}")
    return entries


def collect(board_path: Path, registry: dict) -> tuple[list, list, list]:
    board = pcbnew.LoadBoard(str(board_path))
    grouped: dict[tuple, list] = defaultdict(list)
    hardware: dict[str, list] = defaultdict(list)
    errors: list[str] = []

    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        fpid = footprint.GetFPID().GetUniStringLibId()

        if ref.startswith("H"):
            hardware[fpid].append(ref)
            continue

        opc_id = ""
        if footprint.HasField("opc_id"):
            opc_id = footprint.GetFieldText("opc_id").strip()

        if not opc_id:
            errors.append(f"{ref} ({fpid}): no opc_id field -- cannot resolve to a part")
            continue
        if opc_id not in registry:
            errors.append(f"{ref} ({fpid}): opc_id '{opc_id}' is not in the registry")
            continue

        grouped[(opc_id, fpid, footprint.GetValue())].append(ref)

    lines = []
    for (opc_id, fpid, value), refs in sorted(grouped.items()):
        entry = registry[opc_id]
        lines.append(
            {
                "refs": " ".join(sorted(refs)),
                "qty": len(refs),
                "value": value,
                "footprint": fpid,
                "opc_id": opc_id,
                "name": entry["name"],
                "citation": entry["source"]["citation"],
            }
        )

    hw = [
        {"refs": " ".join(sorted(refs)), "qty": len(refs), "footprint": fpid}
        for fpid, refs in sorted(hardware.items())
    ]
    return lines, hw, errors


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    board_path = Path(sys.argv[1])
    opc_dir = Path(sys.argv[2])
    if not board_path.exists():
        print(f"board not found: {board_path}", file=sys.stderr)
        return 1

    registry = load_registry(opc_dir)
    lines, hardware, errors = collect(board_path, registry)

    if errors:
        for message in errors:
            print(f"UNRESOLVED {message}", file=sys.stderr)
        print(
            f"{len(errors)} component(s) could not be resolved; no BOM written.",
            file=sys.stderr,
        )
        return 1

    out_dir = board_path.parent
    (out_dir / "bom.json").write_text(
        json.dumps(
            {
                "board": board_path.stem,
                "components": lines,
                "mounting_hardware": hardware,
                "note": (
                    "Resolved from footprint opc_id fields against OpenPartsCore. "
                    "No netlist yet: this board has no schematic, so the BOM covers "
                    "placed parts only. Pricing and stock are deliberately absent -- "
                    "fetch them live from distributors keyed by these ids."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with (out_dir / "bom.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["refs", "qty", "value", "footprint", "opc_id", "name", "citation"]
        )
        writer.writeheader()
        writer.writerows(lines)

    print(f"wrote {(out_dir / 'bom.csv').name} and bom.json")
    for line in lines:
        print(f"  {line['refs']:6} x{line['qty']}  {line['value']:22} -> {line['opc_id']}")
    for item in hardware:
        print(f"  {item['refs']:6} x{item['qty']}  (mounting hardware, not in registry)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
