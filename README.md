# autofusion

Fusion 360 parametric furniture modeling toolkit for Claude Code.

Provides a `/furniture` skill that guides Claude through generating Fusion 360 Python scripts with proper parametric features, mirror/pattern replication, and joinery.

## Install

Clone the repo and run the installer:

```bash
git clone <repo-url>
cd autofusion
./install.sh
```

This copies the `/furniture` skill to `~/.claude/commands/` so it's available in any Claude Code session.

## Usage

In Claude Code, invoke the skill then describe your piece:

```
/furniture
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

## Updating the skill

1. Edit `commands/furniture.md` in this repo
2. Commit
3. Run `./install.sh` to copy the latest version to `~/.claude/commands/`

## Uninstall

```bash
./uninstall.sh
```

Removes only the skill files that `install.sh` installed.
