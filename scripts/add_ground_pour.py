#!/usr/bin/env python3
"""Add a ground pour to a routed board and fill it.

Run with KiCad's bundled Python, after scripts/route_board.py:
    <KiCad>/bin/python.exe scripts/add_ground_pour.py <board.kicad_pcb> [--net GND]

One zone per copper layer, outline = the board's Edge.Cuts bounding box. The
filler applies the board's copper-to-edge clearance and any footprint keepout
(the ESP32-S3 module's antenna rule area forbids copper pours), so the outline
does not have to restate either. Islands that end up connected to nothing are
removed rather than left floating. Run this after routing: FreeRouting sees a
filled zone as an obstacle, and the pour is what is left once the tracks exist.
Re-running replaces the zones this script added (matched by name).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pcbnew

ZONE_NAME = "occ-ground-pour"
# Design choices, not fab limits (fab-profiles/jlcpcb-2layer-1oz: clearance 0.10 mm).
# Wider than the minimum so the pour never sets the board's tightest gap.
CLEARANCE_MM = 0.30
MIN_THICKNESS_MM = 0.25
THERMAL_GAP_MM = 0.30
THERMAL_SPOKE_MM = 0.30


def to_lf(path: Path) -> None:
    data = path.read_bytes()
    lf = data.replace(b"\r\n", b"\n")
    if lf != data:
        path.write_bytes(lf)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("board")
    ap.add_argument("--net", default="GND")
    ap.add_argument("--layers", default="F.Cu,B.Cu")
    args = ap.parse_args()

    path = Path(args.board).resolve()
    board = pcbnew.LoadBoard(str(path))
    net = board.FindNet(args.net)
    if net is None:
        raise SystemExit(f"net {args.net!r} not on the board")

    for zone in list(board.Zones()):
        if zone.GetZoneName() == ZONE_NAME:
            board.Remove(zone)

    edge = board.GetBoardEdgesBoundingBox()
    corners = [(edge.GetLeft(), edge.GetTop()), (edge.GetRight(), edge.GetTop()),
               (edge.GetRight(), edge.GetBottom()), (edge.GetLeft(), edge.GetBottom())]

    added = []
    for name in args.layers.split(","):
        layer = board.GetLayerID(name.strip())
        if layer < 0:
            raise SystemExit(f"unknown layer {name!r}")
        zone = pcbnew.ZONE(board)
        zone.SetZoneName(ZONE_NAME)
        zone.SetLayer(layer)
        zone.SetNet(net)
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in corners:
            outline.Append(x, y)
        zone.SetLocalClearance(pcbnew.FromMM(CLEARANCE_MM))
        zone.SetMinThickness(pcbnew.FromMM(MIN_THICKNESS_MM))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetThermalReliefGap(pcbnew.FromMM(THERMAL_GAP_MM))
        zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(THERMAL_SPOKE_MM))
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        board.Add(zone)
        added.append((name.strip(), zone, layer))

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(path), board)
    to_lf(path)

    print(f"poured {args.net} on {path.name}")
    for name, zone, layer in added:
        area_mm2 = zone.GetFilledPolysList(layer).Area() / 1e12
        print(f"  {name:5} filled {area_mm2:7.1f} mm^2 (clearance {CLEARANCE_MM} mm, thermal reliefs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
