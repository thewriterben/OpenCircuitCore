#!/usr/bin/env python3
"""Generate the sensor subcircuit schematic from a netlist description.

    python scripts/make_reference_schematic.py

The circuit is declared as parts + (part, pin) -> net. Geometry is derived:
every connection is a global label placed exactly on the pin's connection
point, so nets are formed by name and there is no wire routing to get subtly
wrong. That keeps the source reviewable as a netlist -- which is what
"circuits as code" was supposed to buy, and what ADR-0003 conceded losing.

Symbol definitions are lifted verbatim from KiCad's stock libraries into
`lib_symbols`, as the format requires. Nothing about a symbol is invented.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sexp
from sexp import Sym

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "boards" / "reference-esp32s3" / "sensor-subcircuit.kicad_sch"
PROJECT = "sensor-subcircuit"

SYMDIRS = [
    Path(r"C:\Users\Benji\AppData\Local\Programs\KiCad\10.0\share\kicad\symbols"),
    Path(r"C:\Program Files\KiCad\10.0\share\kicad\symbols"),
    Path("/usr/share/kicad/symbols"),
]

# --- the circuit, declared ------------------------------------------------
# BME280 in I2C mode: CSB tied high selects I2C, SDO tied low sets addr 0x76.
PARTS = [
    {
        "ref": "U2", "lib": "Sensor", "name": "BME280", "value": "BME280",
        "at": (100.0, 100.0),
        "footprint": "Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering",
        "opc_id": "electronic/bme280",
        "nets": {"1": "GND", "7": "GND", "6": "+3V3", "8": "+3V3",
                 "2": "+3V3", "5": "GND", "3": "SDA", "4": "SCL"},
    },
    {
        "ref": "R1", "lib": "Device", "name": "R", "value": "4.7k",
        "at": (140.0, 100.0), "footprint": "Resistor_SMD:R_0603_1608Metric",
        "opc_id": "electronic/r-0603", "nets": {"1": "+3V3", "2": "SDA"},
    },
    {
        "ref": "R2", "lib": "Device", "name": "R", "value": "4.7k",
        "at": (150.0, 100.0), "footprint": "Resistor_SMD:R_0603_1608Metric",
        "opc_id": "electronic/r-0603", "nets": {"1": "+3V3", "2": "SCL"},
    },
    {
        "ref": "C1", "lib": "Device", "name": "C", "value": "100n",
        "at": (160.0, 100.0), "footprint": "Capacitor_SMD:C_0603_1608Metric",
        "opc_id": "electronic/c-0603", "nets": {"1": "+3V3", "2": "GND"},
    },
    # Power flags: without them ERC reports power inputs as undriven.
    {
        "ref": "#FLG01", "lib": "power", "name": "PWR_FLAG", "value": "PWR_FLAG",
        "at": (175.0, 95.0), "footprint": "", "opc_id": "", "nets": {"1": "+3V3"},
    },
    {
        "ref": "#FLG02", "lib": "power", "name": "PWR_FLAG", "value": "PWR_FLAG",
        "at": (185.0, 95.0), "footprint": "", "opc_id": "", "nets": {"1": "GND"},
    },
]


def find_symdir() -> Path:
    for path in SYMDIRS:
        if path.exists():
            return path
    raise SystemExit("KiCad symbol directory not found")


def load_symbol(symdir: Path, lib: str, name: str):
    path = symdir / f"{lib}.kicad_sym"
    if not path.exists():
        raise SystemExit(f"symbol library missing: {path}")
    root = sexp.parse(path.read_text(encoding="utf-8"))
    for sym in sexp.find_all(root, "symbol"):
        if len(sym) > 1 and str(sym[1]) == name:
            embedded = [child for child in sym]
            embedded[1] = f"{lib}:{name}"   # lib_symbols keys are lib:name
            return embedded
    raise SystemExit(f"symbol {lib}:{name} not found in {path}")


def pin_points(symbol_def) -> dict:
    """Pin number -> (x, y) in symbol coordinates (y up)."""
    points = {}
    for sub in sexp.find_all(symbol_def, "symbol"):
        for pin in sexp.find_all(sub, "pin"):
            at = sexp.find(pin, "at")
            number = sexp.find(pin, "number")
            if at and number:
                points[str(number[1])] = (float(at[1]), float(at[2]))
    return points


def uid() -> str:
    return str(uuid.uuid4())


def effects(size: float = 1.27, hide: bool = False, justify: str | None = None):
    node = [Sym("effects"), [Sym("font"), [Sym("size"), Sym(str(size)), Sym(str(size))]]]
    if justify:
        node.append([Sym("justify"), Sym(justify)])
    if hide:
        node.append([Sym("hide"), Sym("yes")])
    return node


def prop(key: str, value: str, x: float, y: float, hide: bool = True):
    return [
        Sym("property"), key, value,
        [Sym("at"), Sym(str(x)), Sym(str(y)), Sym("0")],
        effects(hide=hide),
    ]


def main() -> int:
    symdir = find_symdir()
    root_uuid = uid()

    # Embed each distinct symbol definition once.
    defs = {}
    for part in PARTS:
        key = f"{part['lib']}:{part['name']}"
        if key not in defs:
            defs[key] = load_symbol(symdir, part["lib"], part["name"])

    doc = [
        Sym("kicad_sch"),
        [Sym("version"), Sym("20250114")],
        [Sym("generator"), "opencircuitcore"],
        [Sym("generator_version"), "1.0"],
        [Sym("uuid"), root_uuid],
        [Sym("paper"), "A4"],
        [Sym("lib_symbols")] + list(defs.values()),
    ]

    labels = []
    for part in PARTS:
        key = f"{part['lib']}:{part['name']}"
        sym_x, sym_y = part["at"]
        points = pin_points(defs[key])

        instance = [
            Sym("symbol"),
            [Sym("lib_id"), key],
            [Sym("at"), Sym(str(sym_x)), Sym(str(sym_y)), Sym("0")],
            [Sym("unit"), Sym("1")],
            [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("yes")],
            [Sym("on_board"), Sym("yes")],
            [Sym("dnp"), Sym("no")],
            [Sym("uuid"), uid()],
            prop("Reference", part["ref"], sym_x, sym_y - 12.7, hide=False),
            prop("Value", part["value"], sym_x, sym_y + 12.7, hide=False),
            prop("Footprint", part["footprint"], sym_x, sym_y),
            prop("Datasheet", "", sym_x, sym_y),
            prop("Description", "", sym_x, sym_y),
        ]
        if part["opc_id"]:
            instance.append(prop("opc_id", part["opc_id"], sym_x, sym_y))
        instance.append([
            Sym("instances"),
            [Sym("project"), PROJECT,
             [Sym("path"), f"/{root_uuid}",
              [Sym("reference"), part["ref"]], [Sym("unit"), Sym("1")]]],
        ])
        doc.append(instance)

        # A global label sitting exactly on the pin's connection point joins
        # that pin to the net. Schematic y grows downward; symbol y grows up.
        for pin_number, net in part["nets"].items():
            if pin_number not in points:
                raise SystemExit(f"{part['ref']}: symbol has no pin {pin_number}")
            px, py = points[pin_number]
            labels.append([
                Sym("global_label"), net,
                [Sym("shape"), Sym("bidirectional")],
                [Sym("at"), Sym(str(round(sym_x + px, 4))),
                 Sym(str(round(sym_y - py, 4))), Sym("0")],
                effects(justify="left"),
                [Sym("uuid"), uid()],
            ])

    doc.extend(labels)
    doc.append([Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(sexp.dump(doc) + "\n", encoding="utf-8")

    nets = sorted({net for part in PARTS for net in part["nets"].values()})
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(PARTS)} parts, {len(labels)} pin connections, nets: {', '.join(nets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
