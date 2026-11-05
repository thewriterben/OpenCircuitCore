#!/usr/bin/env python3
"""Generate the sensor-node schematic: ESP32-S3-WROOM-1 + BME280 + headers.

    python scripts/make_sensor_node.py

The first board here that is a *device* rather than a subcircuit: an MCU
module, a sensor on its I2C bus, a 4-pin sensor/power header and a 6-pin
programming header (GND, TXD0, RXD0, IO0, EN, 3V3). Same mechanism as
make_reference_schematic.py: parts + (pin -> net); geometry is derived.

Why the pin map lives here and nowhere else: make_firmware.py reads the
GPIO numbers for SDA/SCL back out of the *exported netlist*, not out of this
file, so the firmware cannot disagree with the board (see
OpenDesignCore wiki/concepts/device-pipeline.md).

Component choices and their sources:
- Module pins: KiCad stock symbol RF_Module:ESP32-S3-WROOM-1 (pin numbers are
  the module's pad numbers; names are Espressif's).
- EN pull-up 10k + 100n to GND, and 10u || 100n on 3V3 at the module:
  Espressif "ESP32-S3 Series Hardware Design Guidelines", power-supply and
  chip-enable sections. TODO(source): pin the exact section numbers once the
  guideline PDF is pinned in OpenPartsCore.
- BME280 in I2C mode (CSB high), SDO low -> address 0x76: Bosch BME280
  datasheet section 6.2 (I2C interface).
- I2C pull-ups 4.7k: design choice, within the BME280's I2C spec at 3.3 V.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_reference_schematic import build  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "boards" / "sensor-node" / "sensor-node.kicad_sch"
PROJECT = "sensor-node"

R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"

PARTS = [
    {
        "ref": "U1", "lib": "RF_Module", "name": "ESP32-S3-WROOM-1",
        "value": "ESP32-S3-WROOM-1", "at": (60.0, 100.0),
        "footprint": "RF_Module:ESP32-S3-WROOM-1",
        "opc_id": "electronic/esp32-s3-wroom-1",
        # pad number -> net. Only what the design uses; the rest stay open.
        "nets": {
            "1": "GND", "40": "GND", "41": "GND",
            "2": "+3V3",
            "3": "EN",
            "27": "IO0",            # GPIO0: boot-mode strapping, exposed on J2
            "36": "RXD0", "37": "TXD0",
            "12": "SDA",            # GPIO8
            "17": "SCL",            # GPIO9
        },
    },
    {
        "ref": "U2", "lib": "Sensor", "name": "BME280", "value": "BME280",
        "at": (170.0, 80.0),
        "footprint": "Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering",
        "opc_id": "electronic/bme280",
        "nets": {"1": "GND", "7": "GND", "6": "+3V3", "8": "+3V3",
                 "2": "+3V3",        # CSB high: I2C mode
                 "5": "GND",         # SDO low: address 0x76
                 "3": "SDA", "4": "SCL"},
    },
    {"ref": "R1", "lib": "Device", "name": "R", "value": "4.7k", "at": (205.0, 80.0),
     "footprint": R0603, "opc_id": "electronic/r-0603", "nets": {"1": "+3V3", "2": "SDA"}},
    {"ref": "R2", "lib": "Device", "name": "R", "value": "4.7k", "at": (215.0, 80.0),
     "footprint": R0603, "opc_id": "electronic/r-0603", "nets": {"1": "+3V3", "2": "SCL"}},
    {"ref": "R3", "lib": "Device", "name": "R", "value": "10k", "at": (225.0, 80.0),
     "footprint": R0603, "opc_id": "electronic/r-0603", "nets": {"1": "+3V3", "2": "EN"}},
    {"ref": "C1", "lib": "Device", "name": "C", "value": "100n", "at": (235.0, 80.0),
     "footprint": C0603, "opc_id": "electronic/c-0603", "nets": {"1": "+3V3", "2": "GND"}},
    {"ref": "C2", "lib": "Device", "name": "C", "value": "10u", "at": (245.0, 80.0),
     "footprint": C0603, "opc_id": "electronic/c-0603", "nets": {"1": "+3V3", "2": "GND"}},
    {"ref": "C3", "lib": "Device", "name": "C", "value": "100n", "at": (255.0, 80.0),
     "footprint": C0603, "opc_id": "electronic/c-0603", "nets": {"1": "+3V3", "2": "GND"}},
    {"ref": "C4", "lib": "Device", "name": "C", "value": "100n", "at": (265.0, 80.0),
     "footprint": C0603, "opc_id": "electronic/c-0603", "nets": {"1": "EN", "2": "GND"}},
    {
        "ref": "J1", "lib": "Connector_Generic", "name": "Conn_01x04", "value": "SENSOR",
        "at": (170.0, 150.0),
        "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
        "opc_id": "electronic/pinheader-2.54-1x04",
        "nets": {"1": "+3V3", "2": "GND", "3": "SDA", "4": "SCL"},
    },
    {
        "ref": "J2", "lib": "Connector_Generic", "name": "Conn_01x06", "value": "PROG",
        "at": (205.0, 150.0),
        "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
        "opc_id": "electronic/pinheader-2.54-1x06",
        "nets": {"1": "GND", "2": "TXD0", "3": "RXD0", "4": "IO0", "5": "EN", "6": "+3V3"},
    },
    {"ref": "#FLG01", "lib": "power", "name": "PWR_FLAG", "value": "PWR_FLAG",
     "at": (245.0, 145.0), "footprint": "", "opc_id": "", "nets": {"1": "+3V3"}},
    {"ref": "#FLG02", "lib": "power", "name": "PWR_FLAG", "value": "PWR_FLAG",
     "at": (255.0, 145.0), "footprint": "", "opc_id": "", "nets": {"1": "GND"}},
]


def main() -> int:
    n_labels, nets = build(PARTS, OUT, PROJECT)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(PARTS)} parts, {n_labels} pin connections, nets: {', '.join(nets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
