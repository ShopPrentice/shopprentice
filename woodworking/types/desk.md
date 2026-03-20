# Desk

Writing or computer desk — desks, writing desks, computer desks, secretaries. Distinguished from tables by typically having drawers or compartments, and from dressers by having a work surface as the primary function.

**Two common forms:**
- **Writing desk**: narrow (16–20" deep), just enough for a laptop. Often minimal — no aprons, tapered legs, single shallow drawer.
- **Computer desk**: deeper (24–30"), accommodates monitor + keyboard. May have aprons, multiple drawers, cable management.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Top | Yes | Work surface (solid panel or breadboard) |
| Legs | Yes | 4 supports — tapered for writing desk, square for computer desk |
| Aprons/Rails | Style-dependent | Writing desks may omit aprons; computer desks typically have them |
| Drawers | Optional | 1–3 drawers below top surface |
| Modesty panel | Optional | Panel between back legs hiding the underside |
| Stretchers | Optional | Lower braces between legs |

### Component relationships

```
Top sits on leg frame (with or without aprons)
Aprons (if present) connect adjacent legs at top
Drawers hang from runners or sit on guides between aprons
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Drawer opening | Front apron (if present) — or no front apron, drawer front fills the space | Drawer front body or rectangular CUT |
| Apron mortises | Legs | Apron tenon CUTs legs |
| Cable hole | Top (if computer desk) | Circular CUT |

**If drawers exist in the apron area, the front apron must have an opening, OR the front apron is omitted entirely and the drawer front acts as the visible face.**

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Leg to top (no apron) | Dominos directly into top underside | `domino` |
| Apron to leg (if aprons) | Domino grid or blind M&T | `domino.grid()` or `mortise_tenon` |
| Top to apron | Buttons, figure-8s, or dominos | inline or `domino` |
| Drawer box | Half-blind front, through back | `dovetailed_drawer` |
| Breadboard ends | M&T with elongated slots | `breadboard_ends` |

## Build Order

```
1. Legs (tapered or square)
2. Aprons/rails (if present — with drawer opening if needed)
3. Apron-to-leg joinery (or leg-to-top dominos if no aprons)
4. Top board
5. Top attachment
6. Drawer runners/guides (if drawers)
7. Drawer box(es) via template
8. Details (leg tapers, edge treatments)
```

## Common Mistakes

- Using computer desk depth (28") for a writing desk (should be 16–20")
- Drawer opening not CUT in front apron (or: forgetting to omit front apron)
- Top attachment restricting wood movement across width
- Adding unnecessary aprons to a minimal writing desk

## Parameter Suggestions

### Writing Desk
| Parameter | Typical range | Default |
|-----------|--------------|---------|
| desk_l | 42–54 in | 48 in |
| desk_w | 16–20 in | 18 in |
| desk_h | 28–30 in | 30 in |
| top_thick | 0.75–1 in | 0.75 in |
| leg_size | 1.25–1.75 in | 1.5 in |

### Computer Desk
| Parameter | Typical range | Default |
|-----------|--------------|---------|
| desk_l | 48–60 in | 48 in |
| desk_w | 24–30 in | 28 in |
| desk_h | 28–30 in | 30 in |
| top_thick | 1–1.25 in | 1 in |
| leg_size | 1.5–2.5 in | 2 in |
