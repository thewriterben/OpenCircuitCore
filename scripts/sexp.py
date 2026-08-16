"""Minimal S-expression reader/writer for KiCad files. Stdlib only.

KiCad's schematic and symbol formats are S-expressions. Symbol definitions
must be embedded in a .kicad_sch under `lib_symbols`, so generating a
schematic means lifting real definitions out of the stock .kicad_sym
libraries rather than inventing them.

A node is either a str (atom, quoted strings keep their quotes stripped and
are re-quoted on write) or a list whose first element is the tag.
"""
from __future__ import annotations


class Sym(str):
    """A bare atom — written without quotes."""


def parse(text: str):
    pos = 0
    length = len(text)

    def skip_ws() -> None:
        nonlocal pos
        while pos < length and text[pos] in " \t\r\n":
            pos += 1

    def read_node():
        nonlocal pos
        skip_ws()
        if text[pos] != "(":
            raise ValueError(f"expected '(' at {pos}")
        pos += 1
        items = []
        while True:
            skip_ws()
            if pos >= length:
                raise ValueError("unexpected end of input")
            char = text[pos]
            if char == ")":
                pos += 1
                return items
            if char == "(":
                items.append(read_node())
            elif char == '"':
                pos += 1
                chunk = []
                while text[pos] != '"':
                    if text[pos] == "\\":
                        pos += 1
                    chunk.append(text[pos])
                    pos += 1
                pos += 1
                items.append("".join(chunk))
            else:
                start = pos
                while pos < length and text[pos] not in ' \t\r\n()"':
                    pos += 1
                items.append(Sym(text[start:pos]))
        # unreachable

    node = read_node()
    return node


def dump(node, indent: int = 0) -> str:
    pad = "\t" * indent
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, str):
        escaped = node.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    parts = [dump(child, indent + 1) for child in node]
    single = "(" + " ".join(parts) + ")"
    if len(single) <= 110 and not any(isinstance(c, list) for c in node[1:]):
        return single
    body = "\n".join(f"{pad}\t{p}" for p in parts[1:])
    return f"({parts[0]}\n{body}\n{pad})"


def find(node, tag: str):
    """First direct child list whose tag matches."""
    for child in node:
        if isinstance(child, list) and child and str(child[0]) == tag:
            return child
    return None


def find_all(node, tag: str):
    return [
        child
        for child in node
        if isinstance(child, list) and child and str(child[0]) == tag
    ]
