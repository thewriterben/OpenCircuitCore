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
BOARD_W_MM = 34.0
BOARD_H_MM = 46.0
HOLE_INSET_MM = 3.5

# The ESP32-S3-WROOM-1 footprint carries an antenna keepout that reaches past
# the module body; the first placement put mounting holes inside it and DRC
# said so. Components sit clear of the corners as a result.
#
# The module's thermal vias are 0.2 mm, below KiCad's 0.3 mm default minimum.
# 0.2 mm is within normal fab capability, so the constraint is relaxed
# deliberately here rather than the design being bent around a default.
MIN_THROUGH_DRILL_MM = 0.2

# Lowest y at which a mounting hole clears U1's antenna keepout, measured from
# the placed footprint (keepout spans the full width up to y = 13.25 mm) plus
# a margin. Not a guess -- see the note in add_mounting_holes.
KEEPOUT_CLEAR_Y_MM = 17.0

# Components, each bound to an OpenPartsCore id. The `opc_id` field on the
# footprint is what make_bom.py resolves against the registry -- the BOM is
# never assembled from designator guesswork.
COMPONENTS = [
    {
        "ref": "U1",
        "lib": "RF_Module",
        "footprint": "ESP32-S3-WROOM-1",
        "value": "ESP32-S3-WROOM-1",
        "opc_id": "boards/esp32-s3",
        "x_mm": 17.0,
        "y_mm": 20.0,
        "rot_deg": 0.0,
    },
    {
        "ref": "U2",
        "lib": "Package_LGA",
        "footprint": "Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering",
        "value": "BME280",
        "opc_id": "electronic/bme280",
        "x_mm": 17.0,
        "y_mm": 38.0,
        "rot_deg": 0.0,
    },
]


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

    # Hole positions are dictated by the module's antenna keepout, measured
    # from the placed footprint: it spans the full board width up to
    # y = 13.25 mm. Nothing may sit inside it, so the upper pair moves down
    # below that line rather than living in the corners.
    placed = []
    positions = [
        (HOLE_INSET_MM, KEEPOUT_CLEAR_Y_MM),
        (BOARD_W_MM - HOLE_INSET_MM, KEEPOUT_CLEAR_Y_MM),
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


def add_components(board) -> list:
    placed = []
    for spec in COMPONENTS:
        lib = find_footprint_lib(spec["lib"])
        footprint = pcbnew.FootprintLoad(lib, spec["footprint"])
        if footprint is None:
            raise SystemExit(f"failed to load {spec['footprint']} from {lib}")
        footprint.SetPosition(
            pcbnew.VECTOR2I(
                pcbnew.FromMM(spec["x_mm"]), pcbnew.FromMM(spec["y_mm"])
            )
        )
        footprint.SetReference(spec["ref"])
        footprint.SetValue(spec["value"])
        # The registry binding travels with the footprint, so the BOM is
        # resolved from the design, not reconstructed from designators.
        footprint.SetField("opc_id", spec["opc_id"])
        board.Add(footprint)
        placed.append(
            {
                "ref": spec["ref"],
                "value": spec["value"],
                "footprint": f"{spec['lib']}:{spec['footprint']}",
                "opc_id": spec["opc_id"],
                "x_mm": spec["x_mm"],
                "y_mm": spec["y_mm"],
            }
        )
    return placed


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    board = pcbnew.NewBoard(str(BOARD_FILE))
    settings = board.GetDesignSettings()
    settings.m_MinThroughDrill = pcbnew.FromMM(MIN_THROUGH_DRILL_MM)
    add_outline(board)
    holes = add_mounting_holes(board)
    components = add_components(board)
    pcbnew.SaveBoard(str(BOARD_FILE), board)

    manifest = {
        "board": "reference-esp32s3",
        "outline_mm": {"x": BOARD_W_MM, "y": BOARD_H_MM},
        "mounting_holes": holes,
        "components": components,
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
    print(f"  {len(components)} component(s): " + ", ".join(
        f"{c['ref']}={c['opc_id']}" for c in components))
    print(f"  kicad {pcbnew.GetBuildVersion()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
