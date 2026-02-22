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

## Joinery Reference

The `joinery/` directory contains parametric modeling guides for 9 joint types. Claude reads the relevant file when a design needs that joint.

| Joint | File | Best For |
|-------|------|----------|
| Dado & Rabbet | [joinery/dado-rabbet.md](joinery/dado-rabbet.md) | Shelves, case backs |
| Lap Joint | [joinery/lap-joint.md](joinery/lap-joint.md) | Frames, cross braces |
| Box Joint | [joinery/box-joint.md](joinery/box-joint.md) | Boxes, drawers |
| Bridle Joint | [joinery/bridle-joint.md](joinery/bridle-joint.md) | Frame corners |
| Dowel Joint | [joinery/dowel-joint.md](joinery/dowel-joint.md) | Panel glue-ups |
| Spline Joint | [joinery/spline-joint.md](joinery/spline-joint.md) | Reinforced miters |
| Miter Joint | [joinery/miter-joint.md](joinery/miter-joint.md) | Picture frames, trim |
| Dovetail | [joinery/dovetail.md](joinery/dovetail.md) | Drawer fronts, premium boxes |
| Pocket Hole | [joinery/pocket-hole.md](joinery/pocket-hole.md) | Face frames, quick assembly |

Mortise-and-tenon, tongue-and-groove, and gap filling rules remain inline in the `/woodworking` skill. See [joinery/README.md](joinery/README.md) for the full selection guide and conventions.

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

MIT — see [LICENSE](LICENSE).
