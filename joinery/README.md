# Joinery Reference

Reference files for parametric joinery in Fusion 360. Each file documents a joint type with parameters, geometry workflow, and example code snippets.

## Selection Guide

| Joint | File | Strength | Best For |
|-------|------|----------|----------|
| Dado & Rabbet | [dado-rabbet.md](dado-rabbet.md) | Medium | Shelves, case backs, drawer bottoms |
| Lap Joint | [lap-joint.md](lap-joint.md) | Medium | Frames, flat assemblies, cross braces |
| Box Joint | [box-joint.md](box-joint.md) | High | Boxes, drawers, decorative corners |
| Bridle Joint | [bridle-joint.md](bridle-joint.md) | High | Frame corners, T-connections |
| Dowel Joint | [dowel-joint.md](dowel-joint.md) | Medium | Edge joining, panel glue-ups, face frames |
| Spline Joint | [spline-joint.md](spline-joint.md) | Medium | Reinforced miters, decorative accents |
| Miter Joint | [miter-joint.md](miter-joint.md) | Low-Medium | Picture frames, trim, hidden end grain |
| Dovetail | [dovetail.md](dovetail.md) | Very High | Drawer fronts, premium boxes, visible joints |
| Pocket Hole | [pocket-hole.md](pocket-hole.md) | Medium | Face frames, quick assemblies, tabletops |

## Also in woodworking.md

The main `/woodworking` skill includes inline rules for:
- **Mortise and Tenon** — frame-to-post connections, corner staggering
- **Tongue and Groove** — slat infill, inter-slat T&G, edge tongues
- **Gap Filling** — parametric remainder pieces for pattern arrays

## Conventions

All joinery files follow these conventions:

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

## How Claude Uses These Files

When a design requires a specific joint type, read the corresponding file before generating code. Each file provides:
1. Parameter definitions with `params.add()` examples
2. Step-by-step geometry workflow
3. Replication strategy (pattern/mirror)
4. Common pitfalls and fixes
5. A focused code snippet for the joint portion
