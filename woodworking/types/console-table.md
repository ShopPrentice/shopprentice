# Console Table

Long, narrow table against a wall — TV consoles, media consoles, credenzas, entry tables. Distinguished from dining tables by depth (typically 16–20" vs 30–36") and by often having doors, drawers, or compartments.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Case | Yes | Top, bottom, sides — the main enclosure |
| Frame | Optional | Leg frame below case (when case is elevated) |
| Dividers | Optional | Vertical partitions creating sections |
| Drawers | Optional | Drawer boxes in center or side sections |
| Doors | Optional | Inset or overlay door panels on side sections |
| Cleats | Optional | Connecting case bottom to leg frame |
| Back | Yes | Plywood back panel |

### Component relationships

```
Case (top, bottom, sides) forms the main box
Dividers split the case into sections
Drawers fit inside center section(s)
Doors close side section(s)
Frame (legs + rails) supports the case
Cleats connect case bottom to frame top rails
Back panel closes the rear
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Door openings | Case sides or face frame | Door body CUTs opening |
| Drawer openings | Between top, bottom, and dividers | Open front — no CUT needed |
| Hinge mortises | Case sides + door edges | Hinge template CUTs both |

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Case corners | Through dovetails | `dovetail` |
| Dividers to top/bottom | Dominos | `domino` |
| Frame leg-to-rail | Interlocking M&T | `mortise_tenon` |
| Cleat to frame rail | Blind tenon through rail | inline |
| Cleat to case bottom | Dominos | `domino` |
| Drawer boxes | Half-blind front, through back | `dovetailed_drawer` |
| Doors to case | Butt hinges with rebate mortise | `butt_hinge` |
| Back panel | Rabbet in sides | inline |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Door hinges | When doors exist | `butt_hinge` or Euro hinge |
| Drawer pulls | When drawers exist | `pull` or knob hardware |
| Door catches | When doors exist | magnetic catch |

## Build Order

```
1. Case boards (top, bottom, sides)
2. Dividers (if present)
3. Frame (legs + rails + interlocking M&T)
4. Cleats (connecting case to frame)
5. Drawer boxes (via dovetailed_drawer template)
6. Door panels
7. Back panel
8. Cross-component: case dovetails, divider dominos, cleat dominos
9. Hardware: door hinges, drawer pulls
10. Details: edge treatments
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After case | 4+ (top, bottom, sides, dividers) | Sections correct width |
| After frame | +8 (4 legs, 4 rails) | Frame centered under case |
| After drawers | +5×n_drawers | Drawers fit in sections |
| After doors | +n_doors | Doors inset with gap |
| Final | ~30–50 | Zero structural interferences |

## Common Mistakes

- Interlocking tenons not notched (perpendicular tenons collide inside leg)
- Cleat tenons not blind (visible through rail face)
- Door hinges not accounting for inset gap (rebate mortise depth = overlap - gap)
- Divider dominos not connecting to BOTH top and bottom boards
- Drawer section height not accounting for multiple drawers + gaps

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| console_w | 48–72 in | 60 in |
| console_d | 16–20 in | 18 in |
| case_h | 10–16 in | 12 in |
| leg_h | 4–8 in | 6 in |
| n_sections | 2–4 | 3 |
| board_thick | 0.75 in | 0.75 in |
