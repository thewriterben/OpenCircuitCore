#!/usr/bin/env python3
"""Normalise files to LF in place.

    python scripts/lf.py FILE [FILE ...]

kicad-cli writes CRLF on Windows (reports, netlists). `.gitattributes` declares
`* text=auto eol=lf`, and the provenance record hashes what git will store, so a
CRLF file would verify today and fail the moment it is committed. Run this on
every kicad-cli output before `emit_provenance.py`. Exit 0; prints each file it
changed.
"""
import sys
from pathlib import Path


def to_lf(path: Path) -> bool:
    data = path.read_bytes()
    lf = data.replace(b"\r\n", b"\n")
    if lf == data:
        return False
    path.write_bytes(lf)
    return True


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip()); return 2
    for name in argv:
        if to_lf(Path(name)):
            print(f"LF: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
