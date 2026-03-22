# Domino Joint

## Overview

A **Festool Domino joint** is a loose tenon system: a flat oval wafer (domino) inserted into matching mortise pockets routed in both mating pieces. Unlike traditional mortise-and-tenon where the tenon is integral to one board, the domino is a separate piece that bridges the joint.

**When to use:** Three primary scenarios:
1. **M&T replacement** — Leg-to-seat, post-to-top, kick-to-side. Use `four_corners` for symmetric 4-leg joints, `single` for individual connections.
2. **Edge jointing** — Aligning boards side-by-side (tabletops, panels). Dominos ensure alignment during glue-up. Wide face parallel to board surface.
3. **Case/panel joints** — Side-to-back, shelf-to-back, any T-joint where one board's edge meets another board's face. Like bookshelf sides connecting to back panel.

**Strength:** High. The domino provides mechanical interlock and large glue surface within the mortise pockets. Comparable to traditional mortise-and-tenon for most furniture applications.

## Variants

| Variant | Description |
|---------|-------------|
| Standard blind | Domino hidden inside both pieces (most common) |
| Through domino | Mortise goes through one piece, domino visible on surface (decorative) |
| Floating shelf | Dominos connect shelf edge to panel face — invisible from outside |
| Mitered domino | Dominos reinforce a miter joint from inside |

## Parameters

Use **per-joint prefixes** (e.g., `dm_kick_*`, `dm_back_*`) so each joint gets domino dimensions that fit its specific boards. Shared params like `dm_width` cause problems when joints involve boards of different thicknesses.

| Parameter | Role | Constraint |
|-----------|------|------------|
| `dm_<joint>_w` | Domino narrow dimension | Must fit within the thinnest board at the joint |
| `dm_<joint>_h` | Domino long dimension | Runs along the longer dimension of the mating face |
| `dm_<joint>_d` | Mortise depth per side | Must be ≤ the thinnest piece at the joint |
| `dm_<joint>_count` | Number of dominos | Drives spacing via derived param |

```python
# Example: two joints with different sizing
# Kick-to-side (both pieces are board_thick = 19.05mm)
params.add("dm_kick_w", adsk.core.ValueInput.createByString("5 mm"), "in", "")
params.add("dm_kick_h", adsk.core.ValueInput.createByString("30 mm"), "in", "")
params.add("dm_kick_d", adsk.core.ValueInput.createByString("15 mm"), "in", "")

# Shelf-to-back (thinnest piece is back_thick = 12.7mm)
params.add("dm_back_w", adsk.core.ValueInput.createByString("6 mm"), "in", "")
params.add("dm_back_h", adsk.core.ValueInput.createByString("40 mm"), "in", "")
params.add("dm_back_d", adsk.core.ValueInput.createByString("10 mm"), "in", "")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `dm_<joint>_spacing` | `joint_length / (dm_<joint>_count + 1)` | Even spacing between dominos |

## Sizing Rules

1. **`dm_depth` ≤ thinnest piece** — The mortise depth per side must not exceed the thickness of the thinnest board at the joint. Otherwise the domino pokes through. Example: shelf-to-back with `back_thick = 0.5" = 12.7mm` requires `dm_back_d ≤ 12 mm`.
2. **`dm_width` < perpendicular board dimension** — The narrow dimension must fit within the board face perpendicular to the mating surface (usually the board thickness of the piece the slot is sketched on).
3. **Different joints need different sizes** — A kick-to-side joint (two 3/4" boards) can use larger dominos than a shelf-to-back joint (3/4" shelf meeting 1/2" backboard). Always size per-joint.

## Orientation Rule

**The wide face of the domino must always be parallel to the board surface.** This maximizes glue area and mechanical interlock.

In practice, this means the `long_axis` should be chosen so the domino's wide dimension lies in the plane of the board face — never perpendicular to it.

| Joint Type | Board Surface | Long Axis | Why |
|-----------|---------------|-----------|-----|
| Edge joint (boards flat on XY) | XY plane | X (along board length) | Wide face lies flat in the board surface |
| Kick end face (board_thick × kick_height) | XZ plane | Z (vertical, along height) | Wide face parallel to side panel |
| Shelf-to-back (inner_width × board_thick) | XY plane | X (along width) | Wide face parallel to shelf surface |
| Side-to-back T-joint | XZ plane | Z (along height) | Wide face parallel to both boards at the joint |

**Never orient the domino so its wide face is perpendicular to the board surface** — that would create a weak joint with minimal glue contact on the face.

### Choosing `long_axis` by Grain Direction (Tested — bed frame, dining chair)

The domino's wide face must lie flat — parallel to both mating board surfaces. At any joint, identify the grain direction of each piece and the interface plane. The `long_axis` is the model axis that is:
1. **In the interface plane** (not the normal direction)
2. **Perpendicular to both boards' grain** (so the domino lies across the grain, not along it)

| Joint | Board A grain | Board B grain | Interface plane | `long_axis` |
|-------|--------------|--------------|----------------|-------------|
| Side rail (Y) → post (Z) | Y | Z | YZ (at X=const) | **x** — flat, perpendicular to both grains |
| Front rail (X) → post (Z) | X | Z | XZ (at Y=const) | **y** — flat, perpendicular to both grains |
| HB rail (X) → post (Z) | X | Z | XZ (at Y=const) | **y** — same as front rail |
| Side apron (Y) → leg (Z) | Y | Z | YZ (at X=const) | **x** — same as side rail |
| Ledger (Y) → side rail (Y) | Y | Y | YZ (at X=const) | **y** — along shared grain, domino lays flat |

**Rule of thumb:** the `long_axis` is the model axis that does NOT appear in either board's grain direction and is NOT the interface normal. If the interface is a YZ plane and the grains are Y and Z, the only remaining axis is X → `long_axis="x"`.

**When both boards share the same grain direction** (e.g., ledger strip Y-grain glued to side rail Y-grain), the `long_axis` runs along the shared grain direction — so the domino lays flat (wide face parallel to both board surfaces). Example: ledger Y + rail Y at a YZ interface → `long_axis="y"`.

### Sizing for Thin Boards (Tested — bed frame ledger)

The domino narrow dimension (`dm_t`) must fit within the thinnest board at the joint. Use separate domino parameters per joint when board thicknesses differ:

| Board thickness | Max cutter | Typical params |
|----------------|-----------|----------------|
| 0.75" (19mm) | 5mm | `ldm_t=5mm, ldm_w=30mm, ldm_d=15mm` |
| 1" (25mm) | 6mm | `dm_t=6mm, dm_w=20mm, dm_d=15mm` |
| 1.5"+ (38mm+) | 8mm | `dm_t=8mm, dm_w=40mm, dm_d=20mm` |

**Rule:** cutter diameter ≤ 1/3 of the thinnest board. A 0.75" ledger with an 8mm domino (42% of thickness) is too aggressive — the mortise walls are paper-thin.

## Geometry Workflow

The domino mortise is modeled as a **stadium-shaped void body** sketched on the mating surface and symmetric-extruded so it penetrates equally into both pieces. The stadium shape is two semicircles (radius = `dm_w / 2`) connected by two straight lines — use `sketch_slot` to draw this. After creation, the void is CUT from both pieces (with `keepTool=True` on the first CUT so it survives for the second).

**IMPORTANT — sketch on the mating face, not a construction plane.** Find the BRep face of the piece where the domino will be inserted and create the sketch directly on that face. This follows the "reference related pieces" principle. When the sketch is on a face, Fusion may project face edges and create multiple profiles — always select the **inner profile** (the slot itself, `profileLoops.count == 1`) not the surrounding face region.

### Void Body Approach

1. **Face** — Find the mating face on the piece (e.g., `body.faces` iteration by position or normal). Do NOT use a construction plane offset from origin.
2. **Sketch** — `sketch_slot` on that face:
   - Center: positioned at the domino location on the mating face
   - Size: `dm_<joint>_h` (long) × `dm_<joint>_w` (short)
   - Orientation: `vertical=True/False` per the orientation rule
3. **Extrude** — `ext_new_sym` with `NewBodyFeatureOperation`, distance = `dm_<joint>_d`:
   - Symmetric extrude extends `dm_<joint>_d / 2` into each piece
4. **Pattern** — `RectangularPatternFeature` along the joint:
   - Count: `dm_<joint>_count`
   - Spacing: `dm_<joint>_spacing`
5. **CUT piece A** — `combine(comp, piece_a, void_bodies, CUT, True)` — pockets in piece A, voids survive.
6. **CUT piece B** — `combine(root, piece_b_proxy, void_proxies, CUT, True)` — pockets in piece B via assembly proxy.

### Why Void Bodies Instead of Direct CUT

- **One shape, two pockets** — the same body cuts both mating pieces, guaranteeing alignment.
- **Pattern once, CUT twice** — pattern the void, then CUT each piece. No need to pattern CUT features.
- **Cross-component CUT** — void bodies can be proxied into root for assembly-level CUT operations.

## Replication

- **Multiple dominos per joint:** Pattern the void body along the joint axis.
- **Symmetric joints (left/right):** Mirror the void extrude + pattern across the midplane, then CUT each side independently.
- **Repeated joints (e.g., shelf pattern):** Body-pattern the combined void body along the same axis as the shelf pattern, then bulk CUT all void proxies from the receiving piece.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Domino pokes through board | `dm_depth` exceeds the thinnest piece at the joint | Use per-joint `dm_<joint>_d` sized ≤ thinnest board |
| Shared params don't fit all joints | One `dm_depth` used for joints with different board thicknesses | Define separate `dm_<joint>_*` params per joint |
| Pockets don't align | Different sketch origins for each piece | Use a single void body that spans both pieces |
| Pattern count off by one | Spacing includes endpoint | Use `dm_count` with `SpacingPatternDistanceType` |
| CUT fails on second piece | `keepTool=False` on first CUT consumed the void | Use `keepTool=True` on all CUTs except the last |
| Void body lost after JOIN | Joined void into a piece instead of CUTting | Void bodies should only be CUT tools, never JOINed into piece bodies |

## Example Snippet

Domino voids connecting a kick board to two side panels (symmetric left/right), using `sketch_slot` for stadium shape and `ext_new_sym` for symmetric extrude:

```python
# -- Kick-to-side domino voids (per-joint sizing) --
# Sketch plane at mating interface: inner face of left side
k_dm_pl = off_plane(kick_c, kick_c.yZConstructionPlane,
                    "board_thick", "KDm_Pl")

# Stadium void — vertical (kick end face is taller than wide)
_, pr = sketch_slot(kick_c, k_dm_pl,
    cxe="board_thick / 2",
    cye="dm_kick_zsp",
    long_e="dm_kick_h", short_e="dm_kick_w",
    vertical=True, name="KDm_Sk")

# Symmetric extrude: dm_kick_d/2 into each piece
ext_k_dm = ext_new_sym(kick_c, pr, "dm_kick_d", "KDm_Void")
k_dm_body = ext_k_dm.bodies.item(0)

# Pattern along Z
k_dm_pat = body_pattern(kick_c, k_dm_body,
    kick_c.zConstructionAxis, "dm_kick_count", "dm_kick_zsp", "KDm_PatZ")

# Collect void bodies
dm_left = [k_dm_body]
for i in range(k_dm_pat.bodies.count):
    dm_left.append(k_dm_pat.bodies.item(i))

# CUT kick board (keepTool=True — voids survive for side CUT)
combine(kick_c, kick_body, dm_left, CUT, True, "KDm_CutKick")

# Mirror extrude across XMid → right side voids + independent pattern
mir_k_dm = mirror_feat(kick_c, [ext_k_dm], k_XMid, "KDm_MirX")
# ... pattern right side, CUT right voids from kick ...

# CUT sides via assembly proxies in root
dm_left_proxies = [b.createForAssemblyContext(kick_occ) for b in dm_left]
combine(root, left_side_proxy, dm_left_proxies, CUT, True, "KickDomL")
# ... right side proxies ...
```
