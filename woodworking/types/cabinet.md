# Cabinet

Enclosed storage with doors — kitchen cabinets, pantry cabinets, cupboards, hutches, display cabinets. Distinguished from dressers by having doors (not just drawers) and from bookshelves by having doors that close.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Case | Yes | Top, bottom, sides — the main box |
| Face frame | Optional | Hardwood frame on the front (traditional) — or frameless (Euro) |
| Doors | Yes | Inset or overlay panels that close the front |
| Shelves | Optional | Fixed (dado) or adjustable (shelf pins) |
| Drawers | Optional | Drawer boxes in upper or lower sections |
| Dividers | Optional | Vertical partitions creating sections |
| Back | Yes | Plywood back panel for rigidity |
| Base/Kick | Yes | Toe kick, plinth base, or legs |

### Component relationships

```
Case (top, bottom, sides) forms the box
Face frame (if present) attaches to case front edges
Doors hinge to case sides or face frame stiles
Shelves sit in dados or on shelf pins inside case
Dividers split case into sections
Back panel sits in rabbet in case sides
Base below case
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Door opening | Face frame (if present) or case front | Door body CUTs face frame opening |
| Drawer opening | Face frame (if present) | Drawer front CUTs face frame |
| Shelf dados | Side boards | Shelf bodies CUT dados |
| Shelf pin holes | Side boards | `shelf_pins` template |
| Hinge mortises | Case side or face frame + door edge | Hinge template |
| Back panel rabbet | Side boards | Rabbet tool body |

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Case corners | Dados, rabbets, or dovetails | inline or `dovetail` |
| Face frame | Dominos or pocket screws to case | `domino` |
| Face frame corners | Blind M&T | `mortise_tenon` |
| Doors to case/frame | Hinges (butt or Euro concealed) | `butt_hinge` or Euro |
| Fixed shelves | Dados | inline |
| Adjustable shelves | Shelf pins | `shelf_pins` |
| Drawer boxes | Half-blind front, through back | `dovetailed_drawer` |
| Back panel | Rabbet in sides | inline |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Door hinges | Always | `butt_hinge` (traditional) or Euro hinge (modern) |
| Door catches | Usually (unless push-to-open) | Magnetic catch |
| Door pulls/knobs | Usually | Knob or pull hardware |
| Drawer pulls | When drawers exist | Knob or pull hardware |
| Shelf pins | When shelves are adjustable | `shelf_pins` |
| Drawer slides | Optional (traditional = no slides) | Side-mount hardware |

## Build Order

```
1. Case boards (top, bottom, sides)
2. Dividers (if present)
3. Fixed shelf dados or shelf pin holes
4. Face frame (if present) — stiles, rails, M&T
5. Base/kick
6. Drawer boxes (via dovetailed_drawer template)
7. Door panels
8. Back panel + side rabbets
9. Case joinery (dovetails or dados at corners)
10. Face frame attachment (dominos to case)
11. Hardware: door hinges, catches, pulls, shelf pins
12. Adjustable shelves (loose — not attached)
13. Details: edge treatments
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After case | 4–6 (top, bottom, sides, dividers) | Interior divided correctly |
| After face frame | +4–6 stiles and rails | Frame flush with case front |
| After doors | +n_doors | Doors inset with even gap |
| After drawers | +5×n_drawers | Drawers fit in openings |
| Final | ~20–40 | Zero structural interferences |

## Common Mistakes

- Door hinge rebate not accounting for inset gap (rebate depth = overlap - gap)
- Face frame not flush with case edges (oversized or undersized)
- Shelf pin holes too close to front/back edges
- Fixed shelf dados visible on case front (need stopped dados)
- Door overlay vs inset confusion (affects hinge selection and gap calculation)
- Adjustable shelves colliding with fixed shelves or drawer boxes

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| case_w | 18–36 in | 24 in |
| case_d | 12–24 in | 16 in |
| case_h | 30–84 in | 36 in |
| board_thick | 0.75 in | 0.75 in |
| n_doors | 1–2 | 2 |
| door_gap | 0.0625 in | 0.0625 in |
| n_shelves | 1–4 | 2 |
