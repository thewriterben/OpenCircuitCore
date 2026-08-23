#!/usr/bin/env python3
"""Emit a provenance record for a board build.

    python scripts/emit_provenance.py <board-dir>

Records what produced the artifacts in a board directory: the design sources
and their hashes, the tool versions, the check results, and the output hashes.
An artifact without one is not a result -- the same rule OpenDesignCore holds
itself to (its ADR-0006), now true here as well.

Canonicalisation is deliberately identical to Project BINGO's kernel
(`json.dumps(obj, sort_keys=True, separators=(",",":"))`, ensure_ascii on) and
to OpenDesignCore's C# port, so a hash computed here is comparable with one
computed there. Floating-point values are refused for the same reason they are
refused in OpenDesignCore: their textual form is not stable across languages.
Quantities are strings with the unit in the key.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "occ/provenance/0.1"

# The .kicad_dru is a design source, not a side file: it determines what DRC
# actually checked. A record saying "DRC passed" without it omits the rules
# that passing was measured against.
DESIGN_SOURCES = ("*.kicad_sch", "*.kicad_pcb", "*.net", "*.kicad_dru")
OUTPUTS = (
    "*.stl", "*.step", "*.csv",
    # Fab package lands in fab/; gerber extensions are per-layer, not uniform.
    "fab/*.gbr", "fab/*.gbl", "fab/*.gtl", "fab/*.gbs", "fab/*.gts",
    "fab/*.gbo", "fab/*.gto", "fab/*.gbp", "fab/*.gtp", "fab/*.gba",
    "fab/*.gta", "fab/*.gm1", "fab/*.gbrjob", "fab/*.drl",
)
REPORTS = ("erc-report.txt", "drc-report.txt")


# `.gitattributes` declares `* text=auto eol=lf`, so git stores every text file
# with LF regardless of what wrote it — and `kicad-cli` on Windows writes CRLF.
# Hashing the working-tree bytes therefore records a hash git invalidates on the
# very next commit. That is not hypothetical: it is how every record in this repo
# came to be broken once already, silently, and it recurred on the first attempt
# to regenerate them.
#
# Refusing beats normalising here. Normalising would make the record describe
# something other than the file on disk, and the file on disk is what a reader
# hashes when they check. So: fail, name the file, and say what to do about it.
BINARY_SUFFIXES = {".step", ".png", ".3mf", ".vdb"}
CRLF = b"\r\n"


def sha256_file(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() not in BINARY_SUFFIXES and CRLF in data:
        raise SystemExit(
            f"{path.name} has CRLF line endings.\n\n"
            f".gitattributes declares `* text=auto eol=lf`, so git will store this "
            f"file with LF and\nthe hash recorded here would be wrong the moment it "
            f"is committed — the failure that\nbroke every record in this repo once "
            f"already.\n\nConvert it to LF and re-run:\n\n    dos2unix {path}\n"
        )
    return hashlib.sha256(data).hexdigest()


def canonical(obj) -> bytes:
    def reject_floats(node):
        if isinstance(node, float):
            raise SystemExit(
                "floating-point value in provenance; use a string with the unit "
                "in the key so the hash is stable across languages"
            )
        if isinstance(node, dict):
            for value in node.values():
                reject_floats(value)
        elif isinstance(node, list):
            for value in node:
                reject_floats(value)

    reject_floats(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def kicad_version() -> str:
    for candidate in (
        Path(r"C:\Users\Benji\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe"),
        Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"),
        Path("/usr/bin/kicad-cli"),
    ):
        if candidate.exists():
            out = subprocess.run(
                [str(candidate), "--version"], capture_output=True, text=True, timeout=30
            )
            if out.returncode == 0:
                return out.stdout.strip()
    return "unknown"


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, timeout=10,
        )
        value = out.stdout.strip()
        return value if out.returncode == 0 and len(value) == 40 else "unknown"
    except Exception:
        return "unknown"


def read_check(board_dir: Path, filename: str) -> dict | None:
    """Pull the headline counts out of an ERC or DRC report."""
    path = board_dir / filename
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    # KiCad writes "Found 0 DRC violations" / "Found 0 ERC violations" in the
    # report, but "Found 0 violations" on the console. Matching only the
    # console phrasing silently produced "unknown" and called it a build.
    # DRC reports say "Found 0 DRC violations"; ERC reports use an entirely
    # different shape, "** ERC messages: 0  Errors 0  Warnings 0". Two formats
    # from one tool -- worth reading both rather than assuming symmetry.
    violations = re.search(r"Found (\d+) (?:DRC |ERC )?violations", text)
    if violations is None:
        violations = re.search(r"ERC messages:\s*\d+\s+Errors (\d+)", text)
    unconnected = re.search(r"Found (\d+) unconnected", text)
    if violations is None:
        raise SystemExit(
            f"could not read a violation count from {filename}. Refusing to "
            "emit provenance claiming a check happened when its result is unknown."
        )
    return {
        "report": filename,
        "report_sha256": sha256_file(path),
        "violations": int(violations.group(1)),
        "unconnected": int(unconnected.group(1)) if unconnected else 0,
    }


def collect(board_dir: Path, patterns) -> list:
    seen = {}
    for pattern in patterns:
        for path in sorted(board_dir.glob(pattern)):
            if path.name.endswith(".provenance.json"):
                continue
            rel = path.relative_to(board_dir).as_posix()
            seen[rel] = {
                "name": rel,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
    return [seen[name] for name in sorted(seen)]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    board_dir = Path(sys.argv[1]).resolve()
    if not board_dir.is_dir():
        print(f"not a directory: {board_dir}", file=sys.stderr)
        return 1

    sources = collect(board_dir, DESIGN_SOURCES)
    if not sources:
        print(f"no design sources in {board_dir}", file=sys.stderr)
        return 1

    checks = [c for c in (read_check(board_dir, name) for name in REPORTS) if c]
    failing = [c for c in checks if c["violations"] > 0]

    # A board whose nets came from another directory's schematic must say so,
    # or its provenance omits the thing that determined its connectivity.
    upstream = []
    manifest_path = board_dir / "board.manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        netlist_rel = manifest.get("netlist_source")
        if netlist_rel:
            netlist_path = ROOT / netlist_rel
            if not netlist_path.exists():
                raise SystemExit(f"manifest names a netlist that is missing: {netlist_path}")
            upstream.append({
                "role": "netlist",
                "path": netlist_rel,
                "sha256": sha256_file(netlist_path),
            })

    record = {
        "schema": SCHEMA,
        "design": board_dir.name,
        "sources": sources,
        "upstream": upstream,
        "outputs": collect(board_dir, OUTPUTS),
        "checks": checks,
        "versions": {
            "kicad": kicad_version(),
            "generator": "opencircuitcore/emit_provenance.py",
        },
        "commit": git_commit(),
    }

    payload = canonical(record)
    digest = hashlib.sha256(payload).hexdigest()
    out_path = board_dir / f"{board_dir.name}.provenance.json"
    out_path.write_bytes(payload + b"\n")

    print(f"wrote {out_path.name}")
    print(f"  sha256:{digest}")
    print(f"  {len(sources)} source(s), {len(record['outputs'])} output(s), "
          f"{len(checks)} check report(s)")
    for check in checks:
        state = "PASS" if check["violations"] == 0 else "FAIL"
        extra = (f", {check['unconnected']} unconnected"
                 if check["unconnected"] > 0 else "")
        print(f"  {state} {check['report']}: {check['violations']} violation(s){extra}")

    if failing:
        print("  refusing to call this a clean build: violations present", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
