#!/usr/bin/env python3
"""Build the sensor-node board from its schematic's exported netlist.

Run with KiCad's bundled Python:
    <KiCad>/bin/python.exe scripts/make_sensor_node_board.py

Parts come from make_sensor_node.PARTS; pad connectivity comes from the
netlist kicad-cli exported from the generated schematic (same discipline as
make_sensor_breakout.py). Placement is declared below. Routing is a separate
step (scripts/route_board.py) so that an unrouted board is never mistaken
for a finished one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_sensor_breakout import find_footprint_lib, read_netlist  # noqa: E402
from make_sensor_node import PARTS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "boards" / "sensor-node"
BOARD_FILE = OUT_DIR / "sensor-node.kicad_pcb"
NETLIST = OUT_DIR / "sensor-node.net"

# Outline, mm. Module 18.0 x 25.5 (OpenPartsCore electronic/esp32-s3-wroom-1)
# at the top with its antenna over the board edge; a passives row below it;
# both headers along the bottom edge between the lower mounting holes.
BOARD_W_MM = 44.0
BOARD_H_MM = 52.0
HOLE_INSET_MM = 3.5
# Lowest y clear of the module's antenna keepout (measured on reference-esp32s3
# with the module at the same y; see make_reference_board.KEEPOUT_CLEAR_Y_MM).
KEEPOUT_CLEAR_Y_MM = 17.0
# The module's thermal vias are 0.2 mm (below KiCad's 0.3 mm default).
MIN_THROUGH_DRILL_MM = 0.2


def to_lf(path: Path) -> None:
    """KiCad writes CRLF on Windows. .gitattributes stores LF, and provenance hashes
    what git stores, so every design source is normalised the moment it is written."""
    data = path.read_bytes()
    lf = data.replace(b"\r\n", b"\n")
    if lf != data:
        path.write_bytes(lf)

# ref -> (x_mm, y_mm, rotation_deg). Headers rotated 90 so their pins run
# along x; the position is pin 1.
PLACEMENT = {
    "U1": (22.0, 20.0, 0.0),
    "U2": (8.0, 38.0, 0.0),
    "C1": (13.0, 38.0, 0.0),
    "R1": (18.0, 38.0, 0.0),
    "R2": (23.0, 38.0, 0.0),
    "R3": (28.0, 38.0, 0.0),
    "C2": (33.0, 38.0, 0.0),
    "C3": (13.0, 43.0, 0.0),
    "C4": (28.0, 43.0, 0.0),
    "J1": (9.0, 48.5, 90.0),
    "J2": (21.0, 48.5, 90.0),
}


def add_outline(board) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_RECTANGLE)
    shape.SetStart(pcbnew.VECTOR2I(0, 0))
    shape.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(BOARD_W_MM), pcbnew.FromMM(BOARD_H_MM)))
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetWidth(pcbnew.FromMM(0.1))
    board.Add(shape)


def place_parts(board, parts: list, placement: dict, netmap: dict) -> tuple[list, list]:
    placed, unbound = [], []
    nets: dict[str, object] = {}
    for part in parts:
        if part["ref"].startswith("#") or not part["footprint"]:
            continue
        if part["ref"] not in placement:
            raise SystemExit(f"{part['ref']} has no placement; add it to PLACEMENT")
        lib_name, fp_name = part["footprint"].split(":", 1)
        footprint = pcbnew.FootprintLoad(find_footprint_lib(lib_name), fp_name)
        if footprint is None:
            raise SystemExit(f"failed to load {part['footprint']}")
        x_mm, y_mm, rot = placement[part["ref"]]
        footprint.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm)))
        if rot:
            footprint.SetOrientationDegrees(rot)
        footprint.SetReference(part["ref"])
        footprint.SetValue(part["value"])
        if part["opc_id"]:
            footprint.SetField("opc_id", part["opc_id"])
        board.Add(footprint)

        for pad in footprint.Pads():
            if not pad.GetNumber():
                continue  # unnumbered thermal/paste pads carry no net
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

        # Pads only: the module's antenna keepout legitimately reaches past the edge.
        bbox = None
        for pad in footprint.Pads():
            bbox = pad.GetBoundingBox() if bbox is None else bbox
            bbox.Merge(pad.GetBoundingBox())
        placed.append({
            "ref": part["ref"], "value": part["value"], "footprint": part["footprint"],
            "opc_id": part["opc_id"], "x_mm": x_mm, "y_mm": y_mm, "rotation_deg": rot,
            "pads_bbox_mm": [round(pcbnew.ToMM(bbox.GetLeft()), 2), round(pcbnew.ToMM(bbox.GetTop()), 2),
                        round(pcbnew.ToMM(bbox.GetRight()), 2), round(pcbnew.ToMM(bbox.GetBottom()), 2)],
        })
    return placed, unbound


def add_mounting_holes(board) -> list:
    lib = find_footprint_lib("MountingHole")
    candidates = sorted(Path(lib).glob("MountingHole_3.2mm_M3*.kicad_mod"))
    if not candidates:
        raise SystemExit(f"no M3 mounting-hole footprint in {lib}")
    fp_name = candidates[0].stem
    positions = [
        (HOLE_INSET_MM, KEEPOUT_CLEAR_Y_MM),
        (BOARD_W_MM - HOLE_INSET_MM, KEEPOUT_CLEAR_Y_MM),
        (HOLE_INSET_MM, BOARD_H_MM - HOLE_INSET_MM),
        (BOARD_W_MM - HOLE_INSET_MM, BOARD_H_MM - HOLE_INSET_MM),
    ]
    placed = []
    for index, (x_mm, y_mm) in enumerate(positions, start=1):
        footprint = pcbnew.FootprintLoad(lib, fp_name)
        footprint.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm)))
        footprint.SetReference(f"H{index}")
        board.Add(footprint)
        placed.append({"ref": f"H{index}", "footprint": fp_name, "x_mm": x_mm, "y_mm": y_mm})
    return placed


def main() -> int:
    to_lf(NETLIST)  # kicad-cli exported it with CRLF; downstream hashes (firmware, provenance) see LF
    netmap = read_netlist(NETLIST)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    board = pcbnew.NewBoard(str(BOARD_FILE))
    board.GetDesignSettings().m_MinThroughDrill = pcbnew.FromMM(MIN_THROUGH_DRILL_MM)
    add_outline(board)
    components, unbound = place_parts(board, PARTS, PLACEMENT, netmap)
    holes = add_mounting_holes(board)
    pcbnew.SaveBoard(str(BOARD_FILE), board)
    to_lf(BOARD_FILE)

    outside = [c["ref"] for c in components
               if c["pads_bbox_mm"][0] < 0 or c["pads_bbox_mm"][1] < 0
               or c["pads_bbox_mm"][2] > BOARD_W_MM or c["pads_bbox_mm"][3] > BOARD_H_MM]
    net_names = sorted(set(netmap.values()))
    manifest = {
        "board": "sensor-node",
        "outline_mm": {"x": BOARD_W_MM, "y": BOARD_H_MM},
        "components": components,
        "mounting_holes": holes,
        "nets": net_names,
        "netlist_source": str(NETLIST.relative_to(ROOT)).replace("\\", "/"),
        "kicad_version": pcbnew.GetBuildVersion(),
        "routing": "none in this file; scripts/route_board.py writes routing.json beside it",
        "note": "Connectivity is derived from the schematic's exported netlist, not restated here.",
    }
    (OUT_DIR / "board.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(f"wrote {BOARD_FILE.relative_to(ROOT)}")
    print(f"  outline {BOARD_W_MM} x {BOARD_H_MM} mm, {len(components)} component(s), {len(holes)} hole(s)")
    print(f"  nets from schematic: {', '.join(net_names)}")
    for c in components:
        print(f"  {c['ref']:3} pads {c['pads_bbox_mm']}")
    if unbound:
        print(f"  NOTE {len(unbound)} pad(s) not in the netlist (left open): {', '.join(unbound)}")
    if outside:
        print(f"  ERROR footprints outside the outline: {', '.join(outside)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
