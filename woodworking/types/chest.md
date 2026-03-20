# Chest

Large lidded storage — blanket chests, toy boxes, hope chests, trunks. Distinguished from boxes by size (typically 24"+ wide), presence of feet/base, and often a drawer at the bottom.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Case | Yes | Front, back, left, right boards forming the main box |
| Bottom | Yes | Divider board between chest cavity and drawer (or floor if no drawer) |
| Lid | Yes | Hinged top panel for access |
| Lid edge banding | Style-dependent | Profiled molding around lid edges |
| Lid cleats/battens | Recommended | Cross-grain battens on lid underside to prevent warping |
| Base/Feet | Yes | Applied base (bracket feet) or simple kick |
| Drawer | Optional | Single drawer at bottom of case |
| Back panel | Yes | Plywood back panel for rigidity |

### Component relationships

```
Case boards join at corners (dovetails)
Bottom divides chest cavity from drawer space
  - If no drawer: bottom is the floor, sits in dados in case boards
  - If drawer: bottom sits above drawer space, drawer slides below
Lid hinges to case back edge
Lid cleats attach to lid underside (dominos or M&T)
Base extends beyond case sides (applied base) or is flush (kick)
Drawer slides inside case below bottom board
Back panel sits in rabbet in case sides
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| **Drawer opening** | **Front case board** | **CUT: rectangular opening at drawer height** |
| Bottom dados | All 4 case boards | Bottom body CUTs dado into each board |
| Back panel rabbet | Side boards | Rabbet CUT tool body |
| Hinge mortises | Case back board + lid back edge | Hinge template CUTs both |

**CRITICAL: If a drawer exists, the front case board MUST have an opening CUT for the drawer.** The drawer front fills this opening flush. The case front board is solid initially; the drawer opening is carved out. This is the most commonly missed detail.

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Case corners (4) | Through dovetails | `dovetail` |
| Bottom to case | Dados in all 4 case boards | inline (bottom CUTs case boards) |
| Lid to case | Butt hinges at back edge | `butt_hinge` |
| Lid cleats to lid | Dominos or M&T | `domino` or `mortise_tenon` |
| Base to case | Glue, screws, or dominos | `domino` or inline |
| Drawer box | Half-blind front, through back dovetails | `dovetailed_drawer` |
| Back panel | Rabbet in sides | inline |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Lid hinges (2) | Always | `butt_hinge` |
| Lid stay/chain | Recommended (prevents lid slamming) | lid_stay hardware |
| Drawer pull/knob | When drawer exists | `pull` or knob hardware |
| Lock/hasp | Optional (hope chests, valuable storage) | `chest_lock` |

## Build Order

```
1. Case boards (front, back, left, right)
2. Bottom board + dados into case boards
3. Base/feet boards + arch cutouts (if bracket feet)
4. Base transition molding (if applied base)
5. Drawer opening CUT in front case board
6. Drawer box (via dovetailed_drawer template)
7. Lid panel
8. Lid edge banding (if style calls for it)
9. Lid cleats/battens
10. Back panel + side rabbets
11. Case dovetails (cross-component)
12. Lid hinges
13. Details (edge treatments, cleat tapers)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After case | 4 | Case dimensions match |
| After bottom | 5 | Bottom divides space correctly |
| After base | 9 (4 case + 1 bottom + 4 feet) | Feet wider than case (if applied base) |
| After drawer | +5 drawer bodies | Drawer fits in opening |
| After lid | +1 lid + 2 cleats | Lid covers top opening |
| Final | ~20–25 | Zero structural interferences |

## Common Mistakes

- **Forgetting drawer opening in front case board** — most common error
- Drawer front not flush with case front (drawer positioned behind solid front)
- Lid floating on top without hinges
- Bottom board not mechanically connected (no dados, just sitting)
- Base flush with case instead of wider (if applied base style)
- Missing transition molding between case and wider base
- Cleats with square ends instead of tapered (style-dependent)
- Lid without edge banding or molding (style-dependent)
- Back panel rabbet cutting through dovetail tails (need stopped rabbet or rabbet before dovetails)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| case_w | 30–48 in | 36 in |
| case_d | 16–22 in | 20 in |
| case_h | 20–28 in | 24 in |
| board_thick | 0.75 in | 0.75 in |
| lid_thick | 0.75 in | 0.75 in |
| foot_h | 3–5 in | 4 in |
| drawer_h | 3–5 in | 4 in |
| dt_tail_count | 3–6 | 4 |

## Style Variations

| Style | Base | Lid treatment | Edge details |
|-------|------|--------------|-------------|
| Shaker | Applied bracket feet, arch cutouts, cove molding transition | Edge banding with tapered profile, tapered cleats | Through dovetails, chamfered edges |
| Modern | Flush recessed kick or hairpin legs | Clean square edge, minimal overhang | Hidden dominos, square edges |
| Rustic | Turned feet or thick slab base | Breadboard ends, heavy overhang | Through dovetails, rounded edges |
