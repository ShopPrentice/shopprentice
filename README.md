# autofusion

Fusion 360 parametric furniture modeling toolkit for AI coding assistants.

Provides a `/woodworking` skill (Claude Code) or system instructions (Codex CLI) that guide your AI through generating Fusion 360 Python scripts with proper parametric features, mirror/pattern replication, and joinery.

## Install

One command — no clone needed:

```bash
curl -sSL https://raw.githubusercontent.com/YLZha/autofusion/main/install.sh | bash
```

This auto-detects which tools you have installed (Claude Code, Codex CLI) and sets up accordingly.

### Options

```bash
# Explicit tool selection
curl ... | bash -s -- --claude-code
curl ... | bash -s -- --codex
curl ... | bash -s -- --codex --mcp

# Everything: both tools + MCP live execution
curl ... | bash -s -- --all
```

### Local install (from a clone)

```bash
git clone https://github.com/YLZha/autofusion.git
cd autofusion
./install.sh            # auto-detect tools
./install.sh --all      # all tools + MCP
```

## Supported Tools

| Tool | What gets installed | Invoke with |
|------|-------------------|-------------|
| **Claude Code** | `/woodworking` skill in `~/.claude/commands/` | `/woodworking` then describe your piece |
| **OpenAI Codex CLI** | System instructions in `~/.codex/AGENTS.md` | Describe your piece (instructions are always active) |

## Usage

### Claude Code

```
/woodworking
Build a 48" x 18" coffee table with tapered legs and a slatted top
```

### Codex CLI

```
Build a 48" x 18" coffee table with tapered legs and a slatted top
```

The autofusion instructions are loaded automatically from `AGENTS.md`.

## Examples

Each folder under `examples/` contains a complete Fusion 360 project with screenshots, a README, and the parametric Python script:

| Example | Description |
|---------|-------------|
| [pencil-box](examples/pencil-box/) | 9" x 3" dovetailed pencil box with sliding lid and grooved bottom |
| [bookshelf](examples/bookshelf/) | 70"H x 30"W parametric bookshelf with through M&T shelves and through dovetail top |
| [wood-planter](examples/wood-planter/) | 60" x 20" parametric planter with frame construction and T&G slat infill |

### Adding a new example

1. Create a folder under `examples/` (e.g. `examples/cabinet/`)
2. Add a `README.md` with screenshots and build spec
3. Add the `.py` Fusion 360 script
4. Commit

## Joinery Reference

The `joinery/` directory contains parametric modeling guides for 9 joint types. The AI reads the relevant file when a design needs that joint.

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

Mortise-and-tenon, tongue-and-groove, and gap filling rules remain inline in the skill. See [joinery/README.md](joinery/README.md) for the full selection guide and conventions.

## MCP Integration (AutoFusion Add-in)

Connect your AI assistant to a running Fusion 360 instance via the AutoFusion add-in — a built-in MCP-compatible JSON-RPC server.

```bash
# Include --mcp during install
curl -sSL https://raw.githubusercontent.com/YLZha/autofusion/main/install.sh | bash -s -- --mcp

# Or add MCP to an existing install
cd ~/.autofusion/repo && ./install.sh --mcp
```

The installer symlinks the `addin/` directory into Fusion 360's AddIns folder and configures MCP for your detected tools.

After install, enable it in Fusion 360: **Tools > Add-Ins > AutoFusion > Run**

### Available Tools

| Tool | Purpose |
|------|---------|
| `capture_design` | Full design introspection: parameters, component tree with body geometry, timeline features |
| `get_timeline_state` | Roll timeline to any index, capture body geometry, restore position |
| `execute_script` | Run a Python script in Fusion 360 with transaction wrapping |
| `get_screenshot` | Capture the viewport with optional camera orientation |

### Verify

```bash
curl http://localhost:9100/health          # {"status": "healthy", "server": "AutoFusion"}
curl http://localhost:9100/tools           # lists all 4 tools
```

## Updating

```bash
cd ~/.autofusion/repo && git pull && ./install.sh
```

This pulls the latest skill, joinery references, and re-installs to all detected tools.

## Uninstall

```bash
~/.autofusion/repo/uninstall.sh
```

Removes all autofusion-installed files: `~/.autofusion/`, the Claude Code skill, Codex AGENTS.md content, and MCP configurations.

## License

MIT — see [LICENSE](LICENSE).
