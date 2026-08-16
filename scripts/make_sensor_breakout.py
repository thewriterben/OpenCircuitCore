#!/usr/bin/env python3
"""Build the sensor breakout board from the same description as its schematic.

Run with KiCad's bundled Python:
    <KiCad>/bin/python.exe scripts/make_sensor_breakout.py

`make_reference_schematic.PARTS` is the single source of truth for what exists
and how it connects. This script places those parts as footprints and then
applies the **netlist exported from the schematic** to the pads, so the board's
connectivity is derived from the schematic rather than asserted alongside it.

That is the thing the reference board could not claim: there, schematic and
board were generated independently and nothing tied them together.

Routing is not attempted. The board comes out with correct nets and an
unrouted ratsnest, which is exactly the state a human or a router takes over
from -- and DRC reports the unconnected count honestly rather than pretending.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sexp
from make_reference_schematic import PARTS

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "boards" / "sensor-breakout"
BOARD_FILE = OUT_DIR / "sensor-breakout.kicad_pcb"
NETLIST = ROOT / "boards" / "reference-esp32s3" / "sensor-subcircuit.net"

BOARD_W_MM = 22.0
BOARD_H_MM = 26.0
HOLE_INSET_MM = 2.6
MIN_THROUGH_DRILL_MM = 0.2

# Placement, mm. Kept clear of the mounting holes; the BME280 sits centre-top
# so its vent is away from the board edge a connector would occupy.
PLACEMENT = {
    "U2": (11.0, 9.0),
    "R1": (5.0, 17.5),
    "R2": (11.0, 17.5),
    "C1": (17.0, 17.5),
}


def find_footprint_lib(name: str) -> str:
    roots = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad"),
        r"C:\Program Files\KiCad",
        "/usr/share/kicad",
    ]
    for root in roots:
        hits = glob.glob(os.path.join(root, "**", f"{name}.pretty"), recursive=True)
        if hits:
            return hits[0]
    raise SystemExit(f"footprint library {name}.pretty not found")


def read_netlist(path: Path) -> dict:
    """(reference, pad) -> net name, from the schematic's exported netlist."""
    if not path.exists():
        raise SystemExit(
            f"netlist not found: {path}\n"
            "Generate the schematic first, then:\n"
            "  kicad-cli sch export netlist -o sensor-subcircuit.net sensor-subcircuit.kicad_sch"
        )
    root = sexp.parse(path.read_text(encoding="utf-8"))
    nets_node = sexp.find(root, "nets")
    if nets_node is None:
        raise SystemExit(f"{path} has no (nets ...) section")

    mapping = {}
    for net in sexp.find_all(nets_node, "net"):
        name_node = sexp.find(net, "name")
        if name_node is None:
            continue
        net_name = str(name_node[1])
        for node in sexp.find_all(net, "node"):
            ref = sexp.find(node, "ref")
            pin = sexp.find(node, "pin")
            if ref and pin:
                mapping[(str(ref[1]), str(pin[1]))] = net_name
    return mapping


def add_outline(board) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_RECTANGLE)
    shape.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(0), pcbnew.FromMM(0)))
    shape.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(BOARD_W_MM), pcbnew.FromMM(BOARD_H_MM)))
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetWidth(pcbnew.FromMM(0.1))
    board.Add(shape)


def place_parts(board, netmap: dict) -> tuple[list, list]:
    """Place each schematic part and bind its pads to the schematic's nets."""
    placed, unbound = [], []
    nets: dict[str, object] = {}

    for part in PARTS:
        if part["ref"].startswith("#") or not part["footprint"]:
            continue  # power flags are schematic-only
        if part["ref"] not in PLACEMENT:
            raise SystemExit(f"{part['ref']} has no placement; add it to PLACEMENT")

        lib_name, fp_name = part["footprint"].split(":", 1)
        lib = find_footprint_lib(lib_name)
        footprint = pcbnew.FootprintLoad(lib, fp_name)
        if footprint is None:
            raise SystemExit(f"failed to load {part['footprint']}")

        x_mm, y_mm = PLACEMENT[part["ref"]]
        footprint.SetPosition(
            pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))
        )
        footprint.SetReference(part["ref"])
        footprint.SetValue(part["value"])
        if part["opc_id"]:
            footprint.SetField("opc_id", part["opc_id"])
        board.Add(footprint)

        for pad in footprint.Pads():
            key = (part["ref"], pad.GetNumber())
            net_name = netmap.get(key)
            if net_name is None:
                unbound.append(f"{key[0]}.{key[1]}")
                continue
            net = nets.get(net_name)
            if net is None:
                net = pcbnew.NETINFO_ITEM(board, net_name)
                board.Add(net)
                nets[net_name] = net
            pad.SetNet(net)

        placed.append({
            "ref": part["ref"], "value": part["value"],
            "footprint": part["footprint"], "opc_id": part["opc_id"],
            "x_mm": x_mm, "y_mm": y_mm,
        })

    return placed, unbound


def add_mounting_holes(board) -> list:
    lib = find_footprint_lib("MountingHole")
    candidates = sorted(Path(lib).glob("MountingHole_2.2mm_M2*.kicad_mod")) or \
        sorted(Path(lib).glob("MountingHole_3.2mm_M3*.kicad_mod"))
    if not candidates:
        raise SystemExit(f"no mounting-hole footprint in {lib}")
    fp_name = candidates[0].stem

    placed = []
    positions = [
        (HOLE_INSET_MM, BOARD_H_MM - HOLE_INSET_MM),
        (BOARD_W_MM - HOLE_INSET_MM, BOARD_H_MM - HOLE_INSET_MM),
    ]
    for index, (x_mm, y_mm) in enumerate(positions, start=1):
        footprint = pcbnew.FootprintLoad(lib, fp_name)
        footprint.SetPosition(
            pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))
        )
        footprint.SetReference(f"H{index}")
        board.Add(footprint)
        placed.append({"ref": f"H{index}", "footprint": fp_name,
                       "x_mm": x_mm, "y_mm": y_mm})
    return placed


def main() -> int:
    netmap = read_netlist(NETLIST)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    board = pcbnew.NewBoard(str(BOARD_FILE))
    board.GetDesignSettings().m_MinThroughDrill = pcbnew.FromMM(MIN_THROUGH_DRILL_MM)
    add_outline(board)
    components, unbound = place_parts(board, netmap)
    holes = add_mounting_holes(board)
    pcbnew.SaveBoard(str(BOARD_FILE), board)

    net_names = sorted({n for n in netmap.values()})
    manifest = {
        "board": "sensor-breakout",
        "outline_mm": {"x": BOARD_W_MM, "y": BOARD_H_MM},
        "components": components,
        "mounting_holes": holes,
        "nets": net_names,
        "netlist_source": str(NETLIST.relative_to(ROOT)).replace("\\", "/"),
        "kicad_version": pcbnew.GetBuildVersion(),
        "note": (
            "Connectivity is derived from the schematic's exported netlist, not "
            "restated here. Unrouted by design: correct nets, ratsnest pending "
            "a router or a human."
        ),
    }
    (OUT_DIR / "board.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"wrote {BOARD_FILE.relative_to(ROOT)}")
    print(f"  outline {BOARD_W_MM} x {BOARD_H_MM} mm, {len(components)} component(s), "
          f"{len(holes)} mounting hole(s)")
    print(f"  nets from schematic: {', '.join(net_names)}")
    if unbound:
        print(f"  NOTE {len(unbound)} pad(s) not in the netlist: {', '.join(unbound)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
