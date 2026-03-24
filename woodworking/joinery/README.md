# Joinery Reference

Reference files for parametric joinery in Fusion 360. Each file documents a joint type with parameters, geometry workflow, and example code snippets.

## Templates

Reusable Python templates in `addin/helpers/templates/` encapsulate complex joinery into single function calls. **Use templates when available** — they handle sketch geometry, CUT/JOIN operations, mirror/pattern replication, and parameter setup.

| Template | Import | Key Functions | Best For |
|----------|--------|---------------|----------|
| `mortise_tenon` | `from woodworking.templates import mortise_tenon` | `define_params()`, `blind()`, `through()`, `bulk_cut_mortises()` | Rail-to-leg, shelf-to-side |
| `drawbore` | `from woodworking.templates import drawbore` | `define_params()`, `through()`, `blind()` | Drawbore M&T with offset pins for stretchers, workbenches |
| `domino` | `from helpers.templates import domino` | `single()`, `grid()`, `four_corners()` | M&T replacement, edge jointing, case T-joints |
| `finger_joint` | `from helpers.templates import finger_joint` | `define_params()`, `box()` | Boxes, drawers, decorative corners |
| `dovetail` | `from helpers.templates import dovetail` | `define_params()`, `corner()`, `box()` | Box corners, drawer fronts |
| `half_blind_dovetail` | `from helpers.templates import half_blind_dovetail` | `define_params()`, `box()` | Drawer fronts (hides end grain) |
| `splayed_legs` | `from helpers.templates import splayed_legs` | `define_params()`, `build()`, `splay_offset()` | 4 compound-splayed legs with floor trim |
| `dovetailed_drawer` | `from helpers.templates import dovetailed_drawer` | `define_params()`, `build()`, `pattern()` | Complete drawer box |

Templates require the ShopPrentice add-in's `helpers/` directory on the Python path (automatic via `execute_script`). For standalone use, copy `addin/helpers/` alongside your script.

### When NOT to template

Dado/rabbet joints (2-3 features) and tongue & groove (inline in skill) are simple enough to write inline. Only joints with 4+ features and variant logic benefit from templates.

## Selection Guide

| Joint | Reference | Template | Strength | Best For |
|-------|-----------|----------|----------|----------|
| Dado & Rabbet | [dado-rabbet.md](dado-rabbet.md) | — (inline) | Medium | Shelves, case backs, drawer bottoms |
| Lap Joint | [lap-joint.md](lap-joint.md) | — | Medium | Frames, flat assemblies, cross braces |
| Box Joint | [box-joint.md](box-joint.md) | `finger_joint` | High | Boxes, drawers, decorative corners |
| Bridle Joint | [bridle-joint.md](bridle-joint.md) | — | High | Frame corners, T-connections |
| Dowel Joint | [dowel-joint.md](dowel-joint.md) | — | Medium | Edge joining, panel glue-ups, face frames |
| Spline Joint | [spline-joint.md](spline-joint.md) | — | Medium | Reinforced miters, decorative accents |
| Miter Joint | [miter-joint.md](miter-joint.md) | — | Low-Medium | Picture frames, trim, hidden end grain |
| Dovetail | [dovetail.md](dovetail.md) | `dovetail` | Very High | Drawer fronts, premium boxes, visible joints |
| Pocket Hole | [pocket-hole.md](pocket-hole.md) | — | Medium | Face frames, quick assemblies, tabletops |
| Domino Joint | [domino-joint.md](domino-joint.md) | `domino` | High | Hidden structural connections, kick boards, shelf-to-back |
| Mortise & Tenon | Inline in skill | `mortise_tenon` | Very High | Shelves, rails, stretchers |
| Drawbore M&T | [drawbore.md](drawbore.md) | `drawbore` | Very High | Stretchers, workbenches, timber frames |

## Also in woodworking.md

The main `/woodworking` skill includes inline rules for:
- **Tongue and Groove** — slat infill, inter-slat T&G, edge tongues
- **Gap Filling** — parametric remainder pieces for pattern arrays

## Conventions

All joinery files and templates follow these conventions:

- **Parametric only** — `ValueInput.createByString("expression")` for all dimensions
- **Sketch > Extrude** — never `TemporaryBRepManager`
- **`participantBodies = [body]`** — Python list, never `ObjectCollection`
- **Units** — `"in"` for dimensions, `""` for counts
- **Parameter prefixes** — 2-letter prefixes to avoid namespace collisions:

| Prefix | Joint |
|--------|-------|
| `dr_` | Dado & Rabbet |
| `lj_` | Lap Joint |
| `bj_` | Box Joint |
| `br_` | Bridle Joint |
| `dw_` | Dowel Joint |
| `sp_` | Spline Joint |
| `mj_` | Miter Joint |
| `dt_` | Dovetail |
| `ph_` | Pocket Hole |
| `dm_` | Domino Joint |
| `mt_` | Mortise & Tenon |
| `db_` | Drawbore M&T |

## How Claude Uses These Files

1. **Check for a template first.** If one exists for the joint type, use it — `from helpers.templates import <name>`. Call `define_params()` for parameter setup, then the build function.
2. **Read the reference file** for orientation rules, sizing constraints, and variant selection (e.g., blind vs through M&T, edge vs case domino).
3. **Write inline** only for simple joints without templates (dado, rabbet, tongue & groove).
