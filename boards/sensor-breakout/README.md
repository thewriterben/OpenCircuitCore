# sensor-breakout

A BME280 I2C breakout, and the first board here whose **connectivity comes from its schematic** rather than being asserted alongside it.

## Why it exists

`reference-esp32s3` proved the toolchain, but its schematic and board were generated independently — nothing tied them together, so nothing stopped them disagreeing. This board is generated from `make_reference_schematic.PARTS` (the same single source of truth as the schematic) and its pads are bound to nets read out of **the schematic's exported netlist**.

## Regenerate

```
# 1. schematic
python scripts/make_reference_schematic.py
kicad-cli sch erc --exit-code-violations --severity-error -o erc-report.txt sensor-subcircuit.kicad_sch
kicad-cli sch export netlist -o sensor-subcircuit.net sensor-subcircuit.kicad_sch

# 2. board, from that netlist
<KiCad>/bin/python.exe scripts/make_sensor_breakout.py
kicad-cli pcb drc --severity-error -o drc-report.txt sensor-breakout.kicad_pcb
```

## Current state

```
outline 22.0 x 26.0 mm, 4 component(s), 2 mounting hole(s)
nets from schematic: +3V3, GND, SCL, SDA

Found 0 violations
Found 10 unconnected items
```

**0 violations, 10 unconnected** is the correct and intended result. The board has real nets and an unrouted ratsnest — the state a router or a human takes over from. Verified from the saved file:

```
U2 [('1','GND'), ('2','+3V3'), ('3','SDA'), ('4','SCL'),
    ('5','GND'), ('6','+3V3'), ('7','GND'), ('8','+3V3')]
R1 [('1','+3V3'), ('2','SDA')]
```

That matches the schematic: CSB high for I2C, SDO low for address 0x76, R1 pulling SDA up to +3V3.

## Not done

- **Not routed.** No tracks, no copper pours. KiCad ships no autorouter and writing one is not this project's business; routing is interactive work, or an external router's.
- **No connector.** Power and I2C arrive at pads with no header footprint yet.
- Placement is hand-chosen in `PLACEMENT`, not optimised.
