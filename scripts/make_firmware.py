#!/usr/bin/env python3
"""Derive firmware pin definitions from a board's exported netlist.

    python scripts/make_firmware.py boards/sensor-node/sensor-node.net \
        --openpartscore ../OpenPartsCore --out boards/sensor-node/firmware

Reads the KiCad netlist (the same file the board's pads were bound from), finds
the ESP32-S3 module and the BME280, and derives:
- which module GPIO carries the sensor's SDI (SDA) and SCK (SCL) lines, from the
  module's pin *names* in the netlist (IO8 -> GPIO 8) -- never from a hand-kept map;
- the BME280 I2C address from where SDO is tied (GND -> 0x76, VDDIO -> 0x77) and
  that CSB is high (I2C mode), per Bosch BME280 datasheet section 6.2;
- that neither bus pin is a strapping pin or a USB pin, from the module's
  OpenPartsCore entry (attributes.strapping_pins, cited to the Espressif datasheet).

Writes pins.rs (for OBC-Prime's `Board { i2c: Some((sda, scl)) }`), pins.h (for
ESP-IDF builds) and firmware.manifest.json with the netlist hash, every derived
value with its rule, and a *proposed* espflash command (`executed: false`;
ADR-0005 / OpenDesignCore ADR-0009: this tool proposes, a human deploys).

Refuses (exit 2, nothing written) when a value cannot be derived from the
netlist plus cited registry data. It never guesses a pin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sexp  # noqa: E402

TOOL = {"name": "opencircuitcore/make_firmware.py", "version": "0.1.0"}
BME280_ADDR_RULE = (
    "Bosch BME280 datasheet, section 6.2 I2C interface: CSB high selects I2C; "
    "SDO connected to GND gives address 0x76, SDO connected to VDDIO gives 0x77. "
    "SDO must not float."
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_components(root) -> dict:
    comps = {}
    node = sexp.find(root, "components")
    if node is None:
        raise SystemExit("netlist has no (components ...) section")
    for comp in sexp.find_all(node, "comp"):
        ref = str(sexp.find(comp, "ref")[1])
        libsource = sexp.find(comp, "libsource")
        part = str(sexp.find(libsource, "part")[1]) if libsource else ""
        opc_id = ""
        for prop in sexp.find_all(comp, "property"):
            name = sexp.find(prop, "name")
            value = sexp.find(prop, "value")
            if name and value and str(name[1]) == "opc_id":
                opc_id = str(value[1])
        value = sexp.find(comp, "value")
        comps[ref] = {"ref": ref, "part": part, "opc_id": opc_id,
                      "value": str(value[1]) if value else ""}
    return comps


def read_nets(root) -> dict:
    """net name -> [(ref, pin number, pin function)]"""
    nets = {}
    node = sexp.find(root, "nets")
    if node is None:
        raise SystemExit("netlist has no (nets ...) section")
    for net in sexp.find_all(node, "net"):
        name = str(sexp.find(net, "name")[1])
        nodes = []
        for n in sexp.find_all(net, "node"):
            ref = str(sexp.find(n, "ref")[1])
            pin = str(sexp.find(n, "pin")[1])
            fn = sexp.find(n, "pinfunction")
            fn = str(fn[1]) if fn else ""
            # KiCad's netlist writer de-duplicates pin names by suffixing the pin
            # number (GND_1, GND_7, CSB_2); strip that to get the symbol's name.
            if fn.endswith(f"_{pin}"):
                fn = fn[: -len(pin) - 1]
            nodes.append((ref, pin, fn))
        nets[name] = nodes
    return nets


def pin_net(nets: dict, ref: str, function: str) -> tuple[str, str] | None:
    """(net name, pin number) of `ref`'s pin named `function`."""
    for name, nodes in nets.items():
        for r, pin, fn in nodes:
            if r == ref and fn == function:
                return name, pin
    return None


def module_gpio_on_net(nets: dict, module_ref: str, net_name: str) -> tuple[int, str] | None:
    for r, pin, fn in nets.get(net_name, []):
        if r == module_ref:
            m = re.fullmatch(r"IO(\d+)", fn)
            if m:
                return int(m.group(1)), pin
    return None


def load_opc_entry(opc_dir: Path, opc_id: str) -> tuple[dict, str]:
    path = opc_dir / "data" / f"{opc_id}.json"
    if not path.exists():
        raise SystemExit(f"OpenPartsCore entry missing: {path}")
    data = path.read_bytes()
    return json.loads(data), sha256_bytes(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("netlist")
    ap.add_argument("--openpartscore", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--board-name", default=None)
    ap.add_argument("--elf", default="target/xtensa-esp32s3-espidf/release/obc-esp32-s3",
                    help="path the proposed espflash command would flash")
    args = ap.parse_args()

    netlist = Path(args.netlist).resolve()
    if not netlist.exists():
        raise SystemExit(f"netlist not found: {netlist}")
    net_bytes = netlist.read_bytes()
    root = sexp.parse(net_bytes.decode("utf-8"))
    comps = read_components(root)
    nets = read_nets(root)
    opc_dir = Path(args.openpartscore).resolve()
    refusals: list[str] = []

    modules = [c for c in comps.values() if c["part"].startswith("ESP32-S3")]
    sensors = [c for c in comps.values() if c["part"] == "BME280"]
    if len(modules) != 1:
        raise SystemExit(f"expected exactly one ESP32-S3 module, found {len(modules)}")
    if len(sensors) != 1:
        raise SystemExit(f"expected exactly one BME280, found {len(sensors)}")
    module, sensor = modules[0], sensors[0]
    for c in (module, sensor):
        if not c["opc_id"]:
            refusals.append(f"{c['ref']} has no opc_id in the netlist")
    if refusals:
        raise SystemExit("refused:\n  " + "\n  ".join(refusals))
    module_entry, module_entry_sha = load_opc_entry(opc_dir, module["opc_id"])
    sensor_entry, sensor_entry_sha = load_opc_entry(opc_dir, sensor["opc_id"])

    strapping = module_entry.get("attributes", {}).get("strapping_pins")
    if not strapping or "gpios" not in strapping or "usb_gpios" not in strapping:
        raise SystemExit(
            f"refused: {module['opc_id']} has no attributes.strapping_pins "
            "(gpios, usb_gpios, source); the check cannot run without a cited list")
    reserved = {int(g): "strapping" for g in strapping["gpios"]}
    reserved.update({int(g): "usb" for g in strapping["usb_gpios"]})

    # Sensor side: where do SDI, SCK, SDO, CSB go?
    sdi = pin_net(nets, sensor["ref"], "SDI")
    sck = pin_net(nets, sensor["ref"], "SCK")
    sdo = pin_net(nets, sensor["ref"], "SDO")
    csb = pin_net(nets, sensor["ref"], "CSB")
    for label, hit in (("SDI", sdi), ("SCK", sck), ("SDO", sdo), ("CSB", csb)):
        if hit is None:
            refusals.append(f"{sensor['ref']} pin {label} is not on any net")
    if refusals:
        raise SystemExit("refused:\n  " + "\n  ".join(refusals))

    def is_ground(net: str) -> bool:
        return net.upper() in {"GND", "GNDREF", "VSS", "0V"}

    def is_vddio(net: str) -> bool:
        return net.upper() in {"+3V3", "3V3", "VDD", "VDDIO", "VCC", "3.3V"}

    csb_net = csb[0]
    if not is_vddio(csb_net):
        refusals.append(f"CSB is on net '{csb_net}', not VDDIO: BME280 is not in I2C mode")
    sdo_net = sdo[0]
    if is_ground(sdo_net):
        address = "0x76"
    elif is_vddio(sdo_net):
        address = "0x77"
    else:
        address = None
        refusals.append(f"SDO is on net '{sdo_net}': address undetermined (must be GND or VDDIO)")

    sda = module_gpio_on_net(nets, module["ref"], sdi[0])
    scl = module_gpio_on_net(nets, module["ref"], sck[0])
    if sda is None:
        refusals.append(f"no module IOnn pin on the SDI net '{sdi[0]}'")
    if scl is None:
        refusals.append(f"no module IOnn pin on the SCK net '{sck[0]}'")
    if sda and scl:
        if sda[0] == scl[0]:
            refusals.append(f"SDA and SCL both resolve to GPIO{sda[0]}")
        for label, (gpio, _pad) in (("SDA", sda), ("SCL", scl)):
            if gpio in reserved:
                refusals.append(
                    f"{label} is GPIO{gpio}, a {reserved[gpio]} pin per {module['opc_id']} "
                    f"({strapping.get('source', {}).get('citation', 'no citation')})")
    if refusals:
        raise SystemExit("refused:\n  " + "\n  ".join(refusals))

    board_name = args.board_name or netlist.stem
    sda_gpio, sda_pad = sda
    scl_gpio, scl_pad = scl
    header = (f"Generated by {TOOL['name']} {TOOL['version']} from {netlist.name} "
              f"(sha256 {sha256_bytes(net_bytes)}). Do not edit: regenerate.")
    pins_rs = f"""// {header}
// Pins are read from the netlist's module pin names; the address from where
// SDO/CSB are tied ({BME280_ADDR_RULE.split(':')[0]}).
pub const BOARD_NAME: &str = "{board_name}";
pub const I2C_SDA_GPIO: i32 = {sda_gpio}; // {module['ref']} pad {sda_pad}, net {sdi[0]}
pub const I2C_SCL_GPIO: i32 = {scl_gpio}; // {module['ref']} pad {scl_pad}, net {sck[0]}
pub const I2C: Option<(i32, i32)> = Some(({sda_gpio}, {scl_gpio}));
pub const BME280_I2C_ADDR: u8 = {address};
"""
    pins_h = f"""/* {header} */
#pragma once
#define BOARD_NAME "{board_name}"
#define I2C_SDA_GPIO {sda_gpio} /* {module['ref']} pad {sda_pad}, net {sdi[0]} */
#define I2C_SCL_GPIO {scl_gpio} /* {module['ref']} pad {scl_pad}, net {sck[0]} */
#define BME280_I2C_ADDR {address}
"""
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pins.rs").write_text(pins_rs, encoding="utf-8", newline="\n")
    (out_dir / "pins.h").write_text(pins_h, encoding="utf-8", newline="\n")

    deploy_cmd = ["espflash", "flash", "--monitor", args.elf]
    manifest = {
        "record": "occ-firmware/0.1",
        "board": board_name,
        "netlist": {"file": netlist.name, "sha256": sha256_bytes(net_bytes)},
        "parts": {
            "module": {"ref": module["ref"], "part": module["part"], "opc_id": module["opc_id"],
                       "opc_entry_sha256": module_entry_sha},
            "sensor": {"ref": sensor["ref"], "part": sensor["part"], "opc_id": sensor["opc_id"],
                       "opc_entry_sha256": sensor_entry_sha},
        },
        "derived": {
            "i2c_sda_gpio": sda_gpio, "i2c_sda_module_pad": sda_pad, "i2c_sda_net": sdi[0],
            "i2c_scl_gpio": scl_gpio, "i2c_scl_module_pad": scl_pad, "i2c_scl_net": sck[0],
            "bme280_i2c_address": address,
            "bme280_sdo_net": sdo_net, "bme280_csb_net": csb_net,
            "bme280_address_rule": BME280_ADDR_RULE,
            "reserved_gpios_checked": {str(k): v for k, v in sorted(reserved.items())},
            "reserved_gpios_source": strapping.get("source"),
        },
        "outputs": {
            "pins.rs": sha256_bytes(pins_rs.encode()),
            "pins.h": sha256_bytes(pins_h.encode()),
        },
        "deploy": {
            "tool": "espflash",
            "command": deploy_cmd,
            "executed": False,
            "note": ("Proposal only. Build OBC-Prime with these pins, then a human runs the "
                     "command with the board on USB. This tool never flashes."),
        },
        "tool": TOOL,
    }
    (out_dir / "firmware.manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out_dir / 'pins.rs'}, pins.h, firmware.manifest.json")
    print(f"  I2C SDA=GPIO{sda_gpio} SCL=GPIO{scl_gpio}, BME280 at {address} "
          f"(SDO->{sdo_net}, CSB->{csb_net}); strapping/USB pins clear")
    print(f"  deploy (not executed): {' '.join(deploy_cmd)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            sys.exit(2)
        raise
