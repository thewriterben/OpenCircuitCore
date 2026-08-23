#!/usr/bin/env python3
"""Verify that every provenance record still describes the files it claims.

    python scripts/verify_provenance.py

A provenance record here carries a sha256 and a byte count for every **source**,
every **output**, and the DRC/ERC **report** itself. That makes the chain
checkable without KiCad: if a `.kicad_pcb` changes and nobody regenerates, the
source hash stops matching, and the committed `drc-report.txt` beside it is
revealed as describing a board that no longer exists.

**This does not re-run DRC, and must not be read as if it did.** It verifies that
the recorded chain is intact — sources, checks and outputs all hash-linked to one
another. Re-running the checks needs KiCad, which is a much heavier CI job and a
separate decision. What this catches is the failure that is otherwise invisible:
a committed report going stale against the design it reports on.

## Why a mismatch gets classified rather than just reported

The first run of this script found all 32 text artifacts mismatching, and a bare
"HASH MISMATCH" would have sent somebody looking for a corrupted board. They were
not corrupt: the recorded hashes were taken on CRLF content, and
`.gitattributes` (`* text=auto eol=lf`) normalised every text file to LF
afterwards without provenance being regenerated. Byte-identical designs, every
hash wrong.

So a mismatch is re-tested against the same content with CRLF endings before it
is reported. A failure that names its own cause is worth the extra ten lines.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify(path: Path, expected_sha: str, expected_bytes: int | None) -> tuple[str, str]:
    """('ok' | 'crlf' | 'changed' | 'missing', detail)."""
    if not path.exists():
        return "missing", "the record names a file that is not here"

    data = path.read_bytes()
    if digest(data) == expected_sha:
        if expected_bytes is not None and len(data) != expected_bytes:
            return "changed", f"hash matches but byte count differs ({len(data)} vs {expected_bytes})"
        return "ok", ""

    # The recorded hash may predate a line-ending normalisation. Same content,
    # different bytes — worth distinguishing from a design that actually moved.
    if b"\r\n" not in data:
        as_crlf = data.replace(b"\n", b"\r\n")
        if digest(as_crlf) == expected_sha:
            return "crlf", (f"content is identical; the recorded hash was taken on CRLF "
                            f"({len(as_crlf)} bytes) and this file is LF ({len(data)} bytes)")

    return "changed", (f"content differs ({len(data)} bytes here, {expected_bytes} recorded). "
                       f"Either the artifact was edited without regenerating provenance, or "
                       f"the design moved and the record beside it is describing a board that "
                       f"no longer exists")


def check_report_counts(board: Path, check: dict) -> list[str]:
    """The record says '0 violations'; the report is the thing that said it."""
    problems = []
    report = board / check["report"]
    if not report.exists():
        return [f"{check['report']}: named by the record, not present"]
    text = report.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"Found (\d+) (?:DRC|ERC) violations", text)
    if match and "violations" in check and int(match.group(1)) != check["violations"]:
        problems.append(
            f"{check['report']}: the record claims {check['violations']} violations, "
            f"the report itself says {match.group(1)}")
    return problems


def main() -> int:
    records = sorted((ROOT / "boards").rglob("*.provenance.json"))
    if not records:
        print("No provenance records found under boards/. Failing rather than "
              "passing a check that checked nothing.", file=sys.stderr)
        return 1

    total = ok = 0
    crlf: list[str] = []
    changed: list[str] = []
    missing: list[str] = []
    counts: list[str] = []

    for record in records:
        data = json.loads(record.read_text(encoding="utf-8"))
        board = record.parent
        name = data.get("design", board.name)

        for kind in ("sources", "outputs"):
            for entry in data.get(kind, []):
                total += 1
                state, detail = classify(board / entry["name"],
                                         entry["sha256"], entry.get("bytes"))
                line = f"{name}/{entry['name']} ({kind[:-1]}): {detail}"
                if state == "ok":
                    ok += 1
                elif state == "crlf":
                    crlf.append(line)
                elif state == "missing":
                    missing.append(line)
                else:
                    changed.append(line)

        for check in data.get("checks", []):
            total += 1
            state, detail = classify(board / check["report"], check["report_sha256"], None)
            line = f"{name}/{check['report']} (check report): {detail}"
            if state == "ok":
                ok += 1
            elif state == "crlf":
                crlf.append(line)
            elif state == "missing":
                missing.append(line)
            else:
                changed.append(line)
            counts.extend(f"{name}/{c}" for c in check_report_counts(board, check))

    print(f"{len(records)} provenance record(s), {total} hashed artifact(s): "
          f"{ok} verified")

    for label, items in (("MISSING", missing), ("CHANGED", changed),
                         ("STALE COUNT", counts)):
        for item in items:
            print(f"  {label}: {item}")

    if crlf:
        print(f"\n  {len(crlf)} artifact(s) are byte-identical apart from line endings.")
        print("  The recorded hashes were taken on CRLF content and these files are LF,")
        print("  which is what `.gitattributes` (`* text=auto eol=lf`) enforces. Nothing")
        print("  is corrupt and no design moved — the records simply predate that")
        print("  normalisation and were never regenerated. Regenerating them is a")
        print("  deliberate act: it re-asserts that the committed reports describe the")
        print("  committed sources, which is true here only because the change was")
        print("  whitespace.")
        for item in crlf[:5]:
            print(f"    {item}")
        if len(crlf) > 5:
            print(f"    ... and {len(crlf) - 5} more")

    problems = len(missing) + len(changed) + len(counts) + len(crlf)
    print(f"\n{'all records intact' if not problems else str(problems) + ' problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
