# reference-esp32s3

The first board through the toolchain. **Geometry only** — outline and mounting holes. No schematic, no netlist, no components yet; those are the next roadmap item. Its job is to prove the toolchain and the bridge into OpenDesignCore.

## Regenerate

```
<KiCad>/bin/python.exe scripts/make_reference_board.py
```

Deterministic: same inputs, same board.

## Verify and export

```
kicad-cli pcb drc --exit-code-violations -o drc-report.txt reference-esp32s3.kicad_pcb
kicad-cli pcb export step --subst-models -o reference-esp32s3.step reference-esp32s3.kicad_pcb
kicad-cli pcb export stl -o reference-esp32s3.stl reference-esp32s3.kicad_pcb
```

Current state: **0 violations, 0 unconnected** (see `drc-report.txt`).

## Co-design: fit an enclosure to the real board

```
OpenDesignCore run-cradle --stl reference-esp32s3.stl --units mm \
    --voxel-mm 0.2 --clearance-mm 0.4 --wall-mm 2.4 --split 0.9
```

That produces a cradle matched to the board's actual outline and mounting holes rather than to a nominal envelope — the ADR-0003 bridge, exercised.

**Note:** `kicad-cli` emits ASCII STL and there is no binary option. PicoGK refuses ASCII, so OpenDesignCore parses it at its import boundary (ODC PR #8). Anything else consuming these STLs should expect ASCII.

## Dimensions

| | |
|---|---|
| Outline | 30.0 × 40.0 mm |
| Mounting holes | 4 × M3 (3.2 mm), 3.5 mm inset from each corner |
| Module envelope it carries | ESP32-S3-WROOM-1, 18.0 × 25.5 × 3.1 mm |

The module envelope is cited (OpenPartsCore `boards/esp32-s3` → Espressif datasheet). **The 30 × 40 carrier size and the hole inset are design choices, not cited values** — they are placeholders until the schematic exists and real connector positions constrain them.
