# occ_mcp — MCP surface

Lets an agent inspect and verify designs without being able to damage one.

## Install and register

```
pip install -r occ_mcp/requirements.txt
claude mcp add opencircuitcore --scope user -- python <abs-path>/occ_mcp/server.py
```

Use the **absolute path**, not `python -m occ_mcp.server`: `-m` resolves against the client's working directory, so a module-style registration works from this repo and fails from anywhere else. Found by registering it that way and watching it fail.

`KICAD_CLI` overrides kicad-cli discovery.

## Tools

| Tool | Does |
|---|---|
| `list_boards` | Boards with outline, components, nets, and last check results |
| `get_bom` | BOM lines, each carrying the OpenPartsCore id it resolved to |
| `get_provenance` | Sources, upstream netlist, outputs, checks, KiCad version, commit |
| `list_fab_profiles` | Manufacturer capabilities **with their citations** |
| `verify` | Runs ERC and DRC, returns the counts |

## What is deliberately missing

**Nothing regenerates a design** — no build tool, no fab export, no profile application. See ADR-0005.

The short version: this repo's writes are not content-addressed artifacts, they are design files a human also edits. A person routes a board for an evening; an agent calls `regenerate` for an unrelated reason; the routing is gone, with no undo. Building stays a person's action at the CLI until there is something that can tell "regenerate a file nobody touched" from "regenerate over a human's work".

`verify` executes because its only writes are regenerable check reports and it cannot alter a design. Note that a correct unrouted board reports **0 violations with a non-zero unconnected count** — that is a true statement about an unrouted board, not a failure.

## SDK note

Written against MCP Python SDK **2.x** (`MCPServer`; `mcp.server.fastmcp` no longer exists). Package named `occ_mcp` so it cannot shadow the SDK.
