# Desk

Writing surface with optional storage — writing desks, computer desks, secretaries. Distinguished from tables by typically having drawers or compartments, and from dressers by having a work surface as the primary function.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Top | Yes | Work surface (solid panel or breadboard) |
| Legs | Yes | 4 supports, can be turned, tapered, or square |
| Aprons/Rails | Yes | Connect legs below top |
| Drawers | Optional | 1–3 drawers below top surface |
| Modesty panel | Optional | Panel between back legs hiding the underside |
| Stretchers | Optional | Lower braces between legs |
| Hutch | Optional | Upper shelf/compartment unit on top |

### Component relationships

```
Top sits on leg/apron frame
Aprons connect adjacent legs at top
Drawers hang from runners or sit on guides between aprons
Modesty panel (if present) spans between back legs
Hutch (if present) sits on top
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Drawer opening | Front apron (CUT to create opening) | Drawer front body or rectangular CUT |
| Apron mortises | Legs | Apron tenon CUTs legs |
| Cable management hole | Top (if computer desk) | Circular CUT |

**CRITICAL: If drawers exist in the apron area, the front apron must have an opening.** Either the apron is split around the drawer, or the drawer front replaces a section of the apron.

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Apron to leg | Blind M&T | `mortise_tenon` |
| Top to apron | Buttons, figure-8s, or dominos | inline or `domino` |
| Drawer box | Half-blind front, through back | `dovetailed_drawer` |
| Drawer runners | Dado in side apron or separate runner | inline |
| Breadboard ends | M&T with elongated slots | `breadboard_ends` |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Drawer pulls | When drawers exist | Knob or pull hardware |
| Drawer slides | Optional (traditional = wood runners) | Side-mount hardware |
| Floor glides | Always | — |

## Build Order

```
1. Legs
2. Aprons/rails (with drawer opening CUT if needed)
3. Apron-to-leg M&T
4. Top board
5. Top attachment
6. Drawer runners/guides
7. Drawer box(es)
8. Modesty panel (if present)
9. Stretchers (if present)
10. Breadboard ends (if present)
11. Hardware (drawer pulls)
12. Details (leg tapers, edge treatments)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After frame | 8 (4 legs + 4 aprons) | Correct height, drawer opening present |
| After top | 9 | Top centered on frame |
| After drawers | +5×n_drawers | Drawers fit in openings |
| Final | 12–20 | Zero interferences |

## Common Mistakes

- Drawer opening not CUT in front apron
- Drawer runners not supporting drawer properly
- Top attachment restricting wood movement across width
- Drawer depth limited by back apron (drawer must clear back apron)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| desk_l | 42–60 in | 48 in |
| desk_w | 24–30 in | 28 in |
| desk_h | 28–30 in | 30 in |
| top_thick | 0.75–1.25 in | 1 in |
| leg_size | 1.5–2.5 in | 2 in |
| n_drawers | 1–3 | 1 |
