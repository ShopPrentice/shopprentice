# autofusion

Fusion 360 parametric furniture modeling toolkit for Claude Code.

Provides a `/woodworking` skill that guides Claude through generating Fusion 360 Python scripts with proper parametric features, mirror/pattern replication, and joinery.

## Install

Clone the repo and run the installer:

```bash
git clone <repo-url>
cd autofusion
./install.sh
```

This copies the `/woodworking` skill to `~/.claude/commands/` so it's available in any Claude Code session.

## Usage

In Claude Code, invoke the skill then describe your piece:

```
/woodworking
Build a 48" x 18" coffee table with tapered legs and a slatted top
```

## Models

Each folder under `models/` contains a complete Fusion 360 project:

| Model | Description |
|-------|-------------|
| [wood-planter](models/wood-planter/) | 60" x 20" parametric planter with frame construction and T&G slat infill |

### Adding a new model

1. Create a folder under `models/` (e.g. `models/bookshelf/`)
2. Add an `INSTRUCTIONS.md` with the build spec
3. Add the `.py` Fusion 360 script
4. Commit

## Samples

MIT-licensed reference scripts from open-source Fusion 360 projects. These are read-only references that demonstrate API patterns the `/woodworking` skill can draw on.

| Sample | Description | Key Patterns |
|--------|-------------|--------------|
| [spur-gear](samples/spur-gear/) | Parametric involute spur gear | Splines, circular pattern, construction planes |
| [bolt](samples/bolt/) | Hex bolt with threads | Extrude, chamfer, fillet, revolve cut, threads |
| [bottle](samples/bottle/) | Revolved bottle with shell | Revolve, shell, fillet, threads, scale, material |
| [pipe](samples/pipe/) | Hollow pipe along a path | Sweep, shell, construction plane on path |
| [box-maker](samples/box-maker/) | Parametric box with finger joints | Finger joints, multi-plane sketching, move features |
| [surface-text](samples/surface-text/) | Text embossed on curved surfaces | Surface evaluators, text engraving, coordinate transforms |
| [voronoi](samples/voronoi/) | Voronoi decorative patterns | SVG import, profile analysis, decorative cuts |
| [helix-generator](samples/helix-generator/) | Helical spline curves | Fitted splines from math, sweep paths |
| [duplicate-component](samples/duplicate-component/) | Component array duplication | Matrix transforms, bounding box, component copies |

See [samples/README.md](samples/README.md) for full details and attribution.

## MCP Integration

Connect Claude Code to a running Fusion 360 instance to execute scripts live via the Model Context Protocol.

```bash
cd mcp && ./setup.sh
```

This installs [mycelia1/fusion360-mcp-server](https://github.com/mycelia1/fusion360-mcp-server) which provides `execute_api_script`, `get_screenshot`, and 11+ other tools. An alternative [official Autodesk sample](https://github.com/AutodeskFusion360/FusionMCPSample) is also documented.

See [mcp/README.md](mcp/README.md) for full setup instructions and Claude Desktop configuration.

## Updating the skill

1. Edit `commands/woodworking.md` in this repo
2. Commit
3. Run `./install.sh` to copy the latest version to `~/.claude/commands/`

## Uninstall

```bash
./uninstall.sh
```

Removes only the skill files that `install.sh` installed.

## License

MIT — see [LICENSE](LICENSE). Sample scripts in `samples/` retain their original MIT licenses from their respective authors.
