"""OpenCircuitCore stdio MCP server.

Lets an agent inspect and verify designs: what is on a board, what it will
cost you in parts, whether it passes ERC and DRC, and what fab profile it was
checked against.

**Regeneration is deliberately not exposed** -- see ADR-0005. Running
`make_reference_schematic.py` or `make_sensor_breakout.py` overwrites design
files, and ADR-0004 already warns that GUI edits put the artifact ahead of its
source. An agent silently regenerating would destroy a human's routing work
with no undo. Building is a person's action at the CLI.

Package is `occ_mcp`, not `mcp`, because the latter shadows the SDK.

Run:
    python -m occ_mcp.server

Requires:  pip install -r occ_mcp/requirements.txt
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
from pathlib import Path

try:
    # SDK 2.x: MCPServer replaced FastMCP; mcp.server.fastmcp is gone.
    from mcp.server import MCPServer
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing or too-old dependency. Run: pip install -r occ_mcp/requirements.txt"
    ) from exc

ROOT = Path(__file__).resolve().parent.parent
BOARDS = ROOT / "boards"
PROFILES = ROOT / "fab-profiles"

server = MCPServer("opencircuitcore")


def _kicad_cli() -> Path:
    override = os.getenv("KICAD_CLI")
    if override:
        return Path(override)
    for candidate in (
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\KiCad\10.0\bin\kicad-cli.exe")),
        Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"),
        Path("/usr/bin/kicad-cli"),
    ):
        if candidate.exists():
            return candidate
    raise RuntimeError("kicad-cli not found; set KICAD_CLI")


def _board_dir(board: str) -> Path:
    path = BOARDS / board
    if not path.is_dir():
        known = ", ".join(sorted(p.name for p in BOARDS.iterdir() if p.is_dir()))
        raise ValueError(f"unknown board '{board}'. Known: {known}")
    return path


@server.tool()
def list_boards() -> list:
    """Every board in the repo, with its manifest summary and last check results."""
    out = []
    for path in sorted(p for p in BOARDS.iterdir() if p.is_dir()):
        manifest_path = path / "board.manifest.json"
        provenance_path = path / f"{path.name}.provenance.json"
        entry: dict = {"board": path.name}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry.update({
                "outline_mm": manifest.get("outline_mm"),
                "components": [c["ref"] for c in manifest.get("components", [])],
                "nets": manifest.get("nets", []),
                "netlist_source": manifest.get("netlist_source"),
            })
        if provenance_path.exists():
            record = json.loads(provenance_path.read_text(encoding="utf-8"))
            entry["checks"] = record.get("checks", [])
            entry["provenance"] = f"{path.name}.provenance.json"
        out.append(entry)
    return out


@server.tool()
def get_bom(board: str) -> list:
    """A board's BOM, each line carrying the OpenPartsCore id it resolved to.

    An empty `opc_id` means the part is not in the registry — treat that as a
    gap to fix, not as a part with no identity.
    """
    directory = _board_dir(board)
    rows: list = []
    for path in sorted(directory.glob("*bom*.csv")):
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                row["_file"] = path.name
                rows.append(row)
    if not rows:
        raise ValueError(f"no BOM csv in {directory.name}; generate one first")
    return rows


@server.tool()
def get_provenance(board: str) -> dict:
    """The board's provenance record: sources, upstream netlist, outputs, checks."""
    directory = _board_dir(board)
    path = directory / f"{board}.provenance.json"
    if not path.exists():
        raise ValueError(
            f"no provenance record for {board}. Run scripts/emit_provenance.py "
            f"boards/{board} — this server does not write design artifacts."
        )
    return json.loads(path.read_text(encoding="utf-8"))


@server.tool()
def list_fab_profiles() -> list:
    """Manufacturer capability profiles, with their citations.

    Every profile states where its numbers came from; a profile without a
    citation is refused when applied.
    """
    out = []
    for path in sorted(PROFILES.glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        out.append({
            "id": profile["id"],
            "name": profile["name"],
            "constraints_mm": profile.get("constraints_mm", {}),
            "citation": profile.get("source", {}).get("citation", ""),
            "url": profile.get("source", {}).get("url", ""),
            "not_encoded": profile.get("not_encoded", []),
        })
    return out


@server.tool()
def verify(board: str) -> dict:
    """Run ERC and DRC on a board and return the counts.

    This executes rather than proposes: its only writes are regenerable check
    reports, and it cannot alter a design. `unconnected` counts the ratsnest —
    a board with correct nets and no routing reports zero violations and a
    non-zero unconnected count, which is a true statement about an unrouted
    board, not a failure.
    """
    directory = _board_dir(board)
    cli = _kicad_cli()
    result: dict = {"board": board, "checks": []}

    for schematic in sorted(directory.glob("*.kicad_sch")):
        out = subprocess.run(
            [str(cli), "sch", "erc", "--severity-error",
             "-o", "erc-report.txt", schematic.name],
            cwd=directory, capture_output=True, text=True, timeout=300,
        )
        result["checks"].append({
            "kind": "erc", "file": schematic.name,
            "stdout": out.stdout.strip().splitlines()[-3:],
        })

    for pcb in sorted(directory.glob("*.kicad_pcb")):
        out = subprocess.run(
            [str(cli), "pcb", "drc", "--severity-error",
             "-o", "drc-report.txt", pcb.name],
            cwd=directory, capture_output=True, text=True, timeout=600,
        )
        result["checks"].append({
            "kind": "drc", "file": pcb.name,
            "stdout": out.stdout.strip().splitlines()[-3:],
        })

    if not result["checks"]:
        raise ValueError(f"no schematic or board files in {directory.name}")
    return result


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
