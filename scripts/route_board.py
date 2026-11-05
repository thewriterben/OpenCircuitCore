#!/usr/bin/env python3
"""Route a board headlessly: pcbnew DSN export -> FreeRouting -> SES import -> DRC.

Run with KiCad's bundled Python (pcbnew is needed for the DSN/SES step;
kicad-cli has no Specctra export):
    <KiCad>/bin/python.exe scripts/route_board.py boards/sensor-node/sensor-node.kicad_pcb \
        --freerouting <path to freerouting-2.x executable or .jar> [--passes 20]

Writes, beside the board:
    <board>.dsn        the design as handed to the router
    <board>.ses        the router's session file (only when it ran)
    drc-report.txt     kicad-cli pcb drc after import
    routing.json       what ran, with sha256 of every input and output

Exit codes: 0 routed, DRC clean, nothing unconnected · 1 routed but DRC or
unconnected items remain (board saved, report says what) · 3 router not
available: the DSN is kept so a human can route or run FreeRouting by hand.

FreeRouting is GPL-3.0 and stays at the process boundary, like KiCad
(DECISIONS.md). It is not vendored: pass its path. Flags per the FreeRouting
2.x CLI (-de design in, -do session out, -mp max passes, --gui.enabled=false).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent


def to_lf(path: Path) -> None:
    """KiCad writes CRLF on Windows; .gitattributes stores LF and provenance hashes what git stores."""
    data = path.read_bytes()
    lf = data.replace(b"\r\n", b"\n")
    if lf != data:
        path.write_bytes(lf)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kicad_cli() -> str:
    beside = Path(sys.executable).with_name("kicad-cli.exe")
    if beside.exists():
        return str(beside)
    found = shutil.which("kicad-cli")
    if found:
        return found
    raise SystemExit("kicad-cli not found beside this python nor on PATH")


def run_drc(board_file: Path) -> dict:
    report = board_file.parent / "drc-report.txt"
    proc = subprocess.run(
        [kicad_cli(), "pcb", "drc", "--severity-error", "-o", str(report), str(board_file)],
        capture_output=True, text=True,
    )
    text = report.read_text(encoding="utf-8", errors="replace") if report.exists() else ""
    viol = re.search(r"Found (\d+) violations", text)
    unconn = re.search(r"Found (\d+) unconnected items", text)
    return {
        "report": report.name,
        "report_sha256": sha256(report) if report.exists() else None,
        "violations": int(viol.group(1)) if viol else None,
        "unconnected": int(unconn.group(1)) if unconn else None,
        "kicad_cli_exit": proc.returncode,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--freerouting", default=None, help="FreeRouting executable or .jar")
    ap.add_argument("--passes", type=int, default=20, help="FreeRouting -mp (max passes)")
    ap.add_argument("--timeout", type=int, default=1200, help="seconds before the router is killed")
    args = ap.parse_args()

    board_file = Path(args.board).resolve()
    if not board_file.exists():
        raise SystemExit(f"board not found: {board_file}")
    out_dir = board_file.parent
    dsn = board_file.with_suffix(".dsn")
    ses = board_file.with_suffix(".ses")
    routing_json = out_dir / "routing.json"

    board = pcbnew.LoadBoard(str(board_file))
    if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
        raise SystemExit("pcbnew.ExportSpecctraDSN returned false")
    to_lf(dsn)
    record: dict = {
        "record": "occ-routing/0.1",
        "board": board_file.name,
        "board_sha256_before": sha256(board_file),
        "dsn": {"file": dsn.name, "sha256": sha256(dsn)},
        "kicad_version": pcbnew.GetBuildVersion(),
    }

    router = Path(args.freerouting).resolve() if args.freerouting else None
    if router is None or not router.exists():
        record["status"] = "router_missing"
        record["note"] = (
            "FreeRouting not given or not found. DSN exported; route it interactively "
            "in KiCad or run FreeRouting on the DSN and re-run this script with --freerouting."
        )
        routing_json.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {dsn.relative_to(ROOT)} (router missing; routing.json records that)")
        return 3

    if router.suffix.lower() == ".jar":
        java = shutil.which("java")
        if not java:
            raise SystemExit("--freerouting is a .jar but java is not on PATH")
        cmd = [java, "-jar", str(router)]
    else:
        cmd = [str(router)]
    cmd += ["-de", str(dsn), "-do", str(ses), "-mp", str(args.passes), "--gui.enabled=false"]
    if ses.exists():
        ses.unlink()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        record["status"] = "router_timeout"
        record["router"] = {"path": str(router), "sha256": sha256(router), "command": cmd}
        routing_json.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"router exceeded {args.timeout}s; routing.json records that")
        return 1
    record["router"] = {
        "name": "freerouting", "path": str(router), "sha256": sha256(router),
        "command": cmd, "exit": proc.returncode, "passes": args.passes,
        "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:],
    }
    if not ses.exists():
        record["status"] = "router_failed"
        routing_json.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("router produced no session file; see routing.json")
        return 1

    record["ses"] = {"file": ses.name, "sha256": sha256(ses)}
    if not pcbnew.ImportSpecctraSES(board, str(ses)):
        record["status"] = "ses_import_failed"
        routing_json.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("pcbnew.ImportSpecctraSES returned false; see routing.json")
        return 1
    pcbnew.SaveBoard(str(board_file), board)
    to_lf(board_file)
    record["board_sha256_after"] = sha256(board_file)
    record["tracks"] = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_TRACK")
    record["vias"] = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")

    drc = run_drc(board_file)
    record["drc"] = drc
    clean = drc["violations"] == 0 and drc["unconnected"] == 0
    record["status"] = "routed_clean" if clean else "routed_with_findings"
    routing_json.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"routed: {record['tracks']} tracks, {record['vias']} vias; "
          f"DRC {drc['violations']} violations, {drc['unconnected']} unconnected")
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
