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

## Body Ownership

**Domino void bodies must live inside a component — never in root.** This is the same rule as mortise-and-tenon, drawbore, or any other joinery: the joint body belongs to the component of the primary connecting piece. Cross-component CUTs go through root via assembly proxies, but the void body itself stays inside its owning component.

Choose the **primary piece** (the one the domino is most naturally part of):
- Rail → post: void in the **rail's** component (the domino travels with the rail)
- Kick → side: void in the **kick's** component
- Ledger → side rail: void in the **ledger's** component
- Rung → ladder side: void in the **ladder** component

The void body appears in model.json like any other body, with its own dependency entry. For pattern copies, use the `replicas` glob field.

## Mating Surface

**Place dominos within the contact area — not based on the full body dimensions.** When body A meets body B at an interface, the contact area is the overlap of their cross-sections at that interface. Dominos placed outside this area miss the mating surface entirely.

This matters most when the two bodies have different sizes or when the joint interface is a partial overlap (angled connections, T-joints where one piece doesn't span the full face of the other).

**Before placing dominos, call `sp.mating_bounds()`:**

```python
# Example: rung (4" deep × 1.5" face) meeting ladder side (3" wide)
# Interface normal is 'x' (YZ plane)
mb = sp.mating_bounds(rung_body, ladder_side, 'x')
# mb = {'y_min': .., 'y_max': .., 'y_center': .., 'y_size': ..,
#        'z_min': .., 'z_max': .., 'z_center': .., 'z_size': ..}
# Rung is 4" deep but only 2" overlaps the ladder side.
# Dominos must fit within mb['y_size'], not the full 4" rung depth.
dm_y = mb['y_center']   # domino centered in the actual contact area
dm_z = mb['z_center']   # domino centered in Z overlap
```

`mating_bounds` raises `ValueError` if the bodies are gapped (not touching), overlapping (penetrating — CUT first), or have no shared mating surface. The error message includes axis ranges so you can diagnose and fix placement during the build — no need to wait for final validation.

**This applies to ALL joinery**, not just dominos. Whenever placing any joint at a partial-overlap interface, verify that the joint geometry falls within the contact area.

## Geometry Workflow

The domino mortise is modeled as a **stadium-shaped void body** sketched at the mating interface and symmetric-extruded so it penetrates equally into both pieces. The stadium shape is two semicircles (radius = `dm_w / 2`) connected by two straight lines — use `sketch_slot` or `sketch_slot_model` to draw this. After creation, the void is CUT from both pieces (with `keepTool=True` on the first CUT so it survives for the second).

**Sketch plane:** Use a construction plane at the interface or the BRep mating face of the primary piece. When using a face, Fusion may project face edges and create multiple profiles — always select the **inner profile** (the slot itself, `profileLoops.count == 1`) not the surrounding face region.

### Void Body Approach

1. **Mating bounds** — Determine the contact area between the two pieces at the interface (see Mating Surface above). All domino centers must fall within this area.
2. **Sketch** — `sketch_slot` or `sketch_slot_model` inside the **primary piece's component**:
   - Center: positioned within the mating bounds
   - Size: `dm_<joint>_h` (long) × `dm_<joint>_w` (short)
   - Orientation: `vertical=True/False` per the orientation rule
3. **Extrude** — `ext_new_sym` with `NewBodyFeatureOperation`, distance = `dm_<joint>_d`:
   - Symmetric extrude extends `dm_<joint>_d / 2` into each piece
4. **Exposure check** — `sp.check_domino_exposure(void, piece_a, piece_b, normal_axis)`:
   - Validates the void is fully inside both bodies on perpendicular axes
   - Raises `ValueError` if the mortise opens to a surface (exposed domino)
   - Call AFTER extrude, BEFORE CUT — catches placement errors early
5. **Pattern** — `RectangularPatternFeature` along the joint:
   - Count: `dm_<joint>_count`
   - Spacing: `dm_<joint>_spacing`
6. **CUT primary piece** — `combine(comp, piece_a, void_bodies, CUT, True)` — pockets in piece A, voids survive.
7. **CUT secondary piece** — Get assembly proxy of piece B, CUT via root: `combine(piece_b_proxy, void_proxies, CUT, True)` — pockets in piece B.

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

Domino voids connecting a kick board to two side panels (symmetric left/right). Note: void bodies are created inside `kick_c` (the kick component), not root. Cross-component CUTs go through assembly proxies.

```python
# -- Kick-to-side domino voids (per-joint sizing) --
# 1. Find the reference body and determine mating bounds
side_l = ctx.find_body("Side_L")
kick = ctx.find_body("Kick")
side_bb = side_l.boundingBox
kick_bb = kick.boundingBox
# Mating area at X = board_thick interface:
# Z overlap = max(kick_minZ, side_minZ) to min(kick_maxZ, side_maxZ)
# Y overlap = max(kick_minY, side_minY) to min(kick_maxY, side_maxY)

# 2. Sketch inside the kick component (void lives here)
k_dm_pl = off_plane(kick_c, kick_c.yZConstructionPlane,
                    "board_thick", "KDm_Pl")

_, pr = sketch_slot(kick_c, k_dm_pl,
    cxe="board_thick / 2",
    cye="dm_kick_zsp",   # within mating Z range
    long_e="dm_kick_h", short_e="dm_kick_w",
    vertical=True, name="KDm_Sk")

# 3. Extrude inside kick_c — void body stays in this component
ext_k_dm = ext_new_sym(kick_c, pr, "dm_kick_d", "KDm_Void")
k_dm_body = ext_k_dm.bodies.item(0)

# 4. Pattern along Z (inside kick_c)
k_dm_pat = body_pattern(kick_c, k_dm_body,
    kick_c.zConstructionAxis, "dm_kick_count", "dm_kick_zsp", "KDm_PatZ")

dm_left = [k_dm_body]
for i in range(k_dm_pat.bodies.count):
    dm_left.append(k_dm_pat.bodies.item(i))

# 5. CUT kick board (same component — no proxy needed)
combine(kick_body, dm_left, CUT, True, "KDm_CutKick")

# 6. CUT side panel via assembly proxy (cross-component)
dm_left_proxies = [b.createForAssemblyContext(kick_occ) for b in dm_left]
side_l_proxy = side_l.createForAssemblyContext(side_occ)
combine(side_l_proxy, dm_left_proxies, CUT, True, "KickDomL")

# Mirror for right side...
```

## Appearance

Domino loose tenons are **beech** by default — this matches real Festool dominos which are made from compressed beech. Apply `sp.apply_appearance("beech", bodies=[...])` to all domino void bodies after the build is complete. Use a different species only when the user explicitly requests it (e.g., walnut dominos for a visible through-domino joint).
