# Dresser

Multi-drawer case piece for clothing storage. Distinguished from cabinets by having primarily drawers (not doors/shelves) and from chests by having multiple drawer slots rather than a single open cavity.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Sides | Yes | Left + right side panels (mirror pair) |
| Top | Yes | Top board, optionally with overhang |
| Bottom | Yes | Bottom board at top of kick, between sides |
| Drawers | Yes | N dovetailed drawer boxes stacked vertically |
| Kick/Base | Yes | Plinth base or feet below the case |
| Back | Yes | Plywood back panel closing the rear |

### Component relationships

```
Sides span from kick_h to case_h
Top sits on sides (dovetails or dados)
Bottom sits between sides at top of kick
Drawers stack vertically inside case between bottom and top
Kick boards form base below case
Back panel sits in rabbet in sides
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Drawer slots | Between top, bottom, and dividers | No opening CUT needed — drawers slide into open front |
| Back panel rabbet | Side boards (back edge) | Rabbet CUT tool body |

**Note:** Dressers typically have an open front — no face frame. Each drawer front IS the visible surface. No opening CUT is needed in a case board because there is no front case board.

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Top/bottom to sides | Through dovetails or dados | `dovetail` or inline dado |
| Drawer boxes | Half-blind front, through back dovetails | `dovetailed_drawer` |
| Kick corners | Dominos or M&T | `domino` |
| Kick to bottom | Dominos | `domino` |
| Back panel | Rabbet in sides | inline |
| Drawer front pulls | Groove or knob | `pull` or hardware |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Drawer pulls/knobs | Always (one per drawer) | `pull` or knob hardware |
| Drawer slides | Optional (traditional = no slides) | side-mount slide hardware |

## Build Order

```
1. Side boards (mirror pair)
2. Top board
3. Bottom board
4. Kick boards + kick corner dominos + kick-to-bottom dominos
5. Drawer boxes via dovetailed_drawer template (one template, pattern along Z)
6. Back panel
7. Case dovetails (top/bottom to sides, cross-component)
8. Side rabbets for back panel
9. Details (drawer pulls, edge treatments)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After sides | 2 | Mirror symmetry |
| After case | 4–5 (sides + top + bottom + back) | Case dimensions |
| After kick | +4 kick boards + domino voids | Kick below case |
| After drawers | +5×n_drawers | Drawers fit inside case |
| Final | ~25–40 total | Zero structural interferences |

## Common Mistakes

- Forgetting pull grooves or knob holes on drawer fronts
- Drawer height not accounting for gaps between drawers
- Kick-to-bottom connection missing (floating bottom board)
- Using body_pattern on drawers with dovetail history (creates ghost bodies)
- Back panel rabbet cutting through dovetail tails

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| case_w | 30–60 in | 48 in |
| case_d | 18–24 in | 20 in |
| case_h | 30–40 in | 34 in |
| n_drawers | 3–6 | 3 |
| board_thick | 0.75 in | 0.75 in |
| drawer_gap | 0.0625–0.125 in | 0.125 in |
| kick_h | 3–5 in | 4 in |
