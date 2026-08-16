#!/usr/bin/env python3
"""Generate the reference board's geometry with KiCad's own pcbnew API.

Run with KiCad's bundled Python:
    <KiCad>/bin/python.exe scripts/make_reference_board.py

Deterministic: same inputs produce the same board. The module envelope comes
from OpenPartsCore's cited entry, not from memory.

This is board *geometry* only -- outline and mounting holes. Schematic capture,
ERC, and a netlist-driven BOM are the next roadmap item; the purpose here is to
prove the toolchain and the STEP/STL bridge into OpenDesignCore (ADR-0003).
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "boards" / "reference-esp32s3"
BOARD_FILE = OUT_DIR / "reference-esp32s3.kicad_pcb"

# Board envelope, mm. The WROOM-1 module is 18.0 x 25.5 (OpenPartsCore
# boards/esp32-s3 -> Espressif datasheet); the carrier adds margin.
BOARD_W_MM = 30.0
BOARD_H_MM = 40.0
HOLE_INSET_MM = 3.5


def find_footprint_lib(name: str) -> str:
    roots = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad"),
        r"C:\Program Files\KiCad",
        "/usr/share/kicad",
        "/Applications/KiCad/KiCad.app/Contents/SharedSupport",
    ]
    for root in roots:
        hits = glob.glob(os.path.join(root, "**", f"{name}.pretty"), recursive=True)
        if hits:
            return hits[0]
    raise SystemExit(f"footprint library {name}.pretty not found")


def add_outline(board) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_RECTANGLE)
    shape.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)))
    shape.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(BOARD_W_MM), pcbnew.FromMM(BOARD_H_MM)))
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetWidth(pcbnew.FromMM(0.1))
    board.Add(shape)


def add_mounting_holes(board) -> list:
    lib = find_footprint_lib("MountingHole")
    candidates = sorted(Path(lib).glob("MountingHole_3.2mm_M3*.kicad_mod"))
    if not candidates:
        raise SystemExit(f"no M3 mounting-hole footprint in {lib}")
    fp_name = candidates[0].stem

    placed = []
    positions = [
        (HOLE_INSET_MM, HOLE_INSET_MM),
        (BOARD_W_MM - HOLE_INSET_MM, HOLE_INSET_MM),
        (HOLE_INSET_MM, BOARD_H_MM - HOLE_INSET_MM),
        (BOARD_W_MM - HOLE_INSET_MM, BOARD_H_MM - HOLE_INSET_MM),
    ]
    for index, (x_mm, y_mm) in enumerate(positions, start=1):
        footprint = pcbnew.FootprintLoad(lib, fp_name)
        if footprint is None:
            raise SystemExit(f"failed to load {fp_name} from {lib}")
        footprint.SetPosition(
            pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))
        )
        footprint.SetReference(f"H{index}")
        board.Add(footprint)
        placed.append(
            {"ref": f"H{index}", "footprint": fp_name, "x_mm": x_mm, "y_mm": y_mm}
        )
    return placed


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    board = pcbnew.NewBoard(str(BOARD_FILE))
    add_outline(board)
    holes = add_mounting_holes(board)
    pcbnew.SaveBoard(str(BOARD_FILE), board)

    manifest = {
        "board": "reference-esp32s3",
        "outline_mm": {"x": BOARD_W_MM, "y": BOARD_H_MM},
        "mounting_holes": holes,
        "kicad_version": pcbnew.GetBuildVersion(),
        "envelope_source": (
            "OpenPartsCore boards/esp32-s3 (Espressif ESP32-S3-WROOM-1 datasheet, "
            "module 18.0 x 25.5 x 3.1 mm); carrier margin is a design choice, "
            "not a cited value"
        ),
    }
    (OUT_DIR / "board.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"wrote {BOARD_FILE.relative_to(ROOT)}")
    print(f"  outline {BOARD_W_MM} x {BOARD_H_MM} mm, {len(holes)} M3 mounting holes")
    print(f"  kicad {pcbnew.GetBuildVersion()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
