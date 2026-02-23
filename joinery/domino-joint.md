# Domino Joint

## Overview

A **Festool Domino joint** is a loose tenon system: a flat oval wafer (domino) inserted into matching mortise pockets routed in both mating pieces. Unlike traditional mortise-and-tenon where the tenon is integral to one board, the domino is a separate piece that bridges the joint.

**When to use:** Hidden structural connections where traditional M&T is overkill or where the joint should be invisible from the outside. Kick boards, rail-to-panel, shelf-to-back, face frame assembly. Ideal for joints that don't need decorative expression.

**Strength:** High. The domino provides mechanical interlock and large glue surface within the mortise pockets. Comparable to traditional mortise-and-tenon for most furniture applications.

## Variants

| Variant | Description |
|---------|-------------|
| Standard blind | Domino hidden inside both pieces (most common) |
| Through domino | Mortise goes through one piece, domino visible on surface (decorative) |
| Floating shelf | Dominos connect shelf edge to panel face — invisible from outside |
| Mitered domino | Dominos reinforce a miter joint from inside |

## Parameters

| Parameter | Expression | Unit | Description |
|-----------|------------|------|-------------|
| `dm_width` | `"8 mm"` | `"in"` | Domino narrow dimension (fits within board thickness) |
| `dm_height` | `"40 mm"` | `"in"` | Domino long dimension (runs along board) |
| `dm_depth` | `"20 mm"` | `"in"` | Mortise depth per side (half the domino length) |
| `dm_count` | `"2"` | `""` | Number of dominos along the joint |

```python
params = design.userParameters
params.add("dm_width", adsk.core.ValueInput.createByString("8 mm"), "in", "Domino width")
params.add("dm_height", adsk.core.ValueInput.createByString("40 mm"), "in", "Domino height")
params.add("dm_depth", adsk.core.ValueInput.createByString("20 mm"), "in", "Domino depth per side")
params.add("dm_count", adsk.core.ValueInput.createByString("2"), "", "Dominos per joint")
```

## Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `dm_spacing` | `joint_length / (dm_count + 1)` | Even spacing between dominos |

```python
params.add("dm_spacing", adsk.core.ValueInput.createByString("joint_length / (dm_count + 1)"), "in", "Domino spacing")
```

## Geometry Workflow

The domino mortise is modeled as a **void body** — a rectangular block that spans the interface between two mating pieces. The void extends `dm_depth` into each piece. After creation, the void is CUT from both pieces (with `keepTool=True` on the first CUT so it survives for the second).

### Void Body Approach

1. **Plane** — Offset plane at the mating interface minus `dm_depth` (so the void starts inside piece A).
2. **Sketch** — Rectangle on that plane:
   - Position: centered on board thickness, offset along joint length by `dm_spacing`
   - Size: `dm_height` × `dm_width` (height runs along board, width fits within thickness)
3. **Extrude** — `NewBodyFeatureOperation`, distance = `dm_depth * 2`:
   - The void spans `dm_depth` into piece A and `dm_depth` into piece B
4. **Pattern** — `RectangularPatternFeature` along the joint:
   - Count: `dm_count`
   - Spacing: `dm_spacing`
5. **JOIN** — Combine all void bodies into one combined void (simplifies later CUT operations).
6. **CUT piece A** — `combine(comp, piece_a, combined_void, CUT, True)` — pockets in piece A, void survives.
7. **CUT piece B** — `combine(comp, piece_b, combined_void, CUT, False)` — pockets in piece B, void consumed.

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
| Void doesn't span interface | Plane offset wrong — void entirely inside one piece | Offset plane = interface position minus `dm_depth` |
| Pockets don't align | Different sketch origins for each piece | Use a single void body that spans both pieces |
| Pattern count off by one | Spacing includes endpoint | Use `dm_count` with `SpacingPatternDistanceType` |
| CUT fails on second piece | `keepTool=False` on first CUT consumed the void | Use `keepTool=True` on all CUTs except the last |
| Void body lost after JOIN | Joined void into a piece instead of CUTting | Void bodies should only be CUT tools, never JOINed into piece bodies |

## Example Snippet

Domino voids connecting a kick board to two side panels (symmetric left/right):

```python
# -- Domino voids for kick-to-side joint --
# Offset plane at left interface (inside left side board)
dm_pl = off_plane(kick_c, kick_c.yZConstructionPlane,
                  "board_thick - dm_depth", "DmKick_Pl")

# One domino void rect
_, pr = sketch_rect(kick_c, dm_pl,
    "board_thick / 2 - dm_width / 2",   # Y: centered on board thickness
    "dm_spacing - dm_height / 2",         # Z: first domino position
    "dm_width", "dm_height", "DmKick_Sk")

# Extrude void spanning interface
ext_dm = ext_new(kick_c, pr, "dm_depth * 2", "DmKick_Void")

# Pattern along Z for dm_count
dm_pat = body_pattern(kick_c, ext_dm.bodies.item(0),
    kick_c.zConstructionAxis, "dm_count", "dm_spacing", "DmKick_Pat")

# Collect all void bodies
dm_voids = [ext_dm.bodies.item(0)]
for i in range(dm_pat.bodies.count):
    dm_voids.append(dm_pat.bodies.item(i))

# JOIN voids into one combined body
combined = dm_voids[0]
if len(dm_voids) > 1:
    combine(kick_c, combined, dm_voids[1:], JOIN, False, "DmKick_JoinVoids")

# CUT kick board (keepTool=True — void survives for side CUT)
combine(kick_c, kick_body, combined, CUT, True, "DmKick_CutKick")

# Mirror across XMid for right side
mir_dm = mirror_feat(kick_c, [ext_dm, dm_pat], k_XMid, "DmKick_MirX")

# CUT sides via assembly proxies in root
dm_left_proxy = combined.createForAssemblyContext(kick_occ)
combine(root, left_side_proxy, dm_left_proxy, CUT, True, "DmKickL")
# ... mirror proxies for right side ...
```
