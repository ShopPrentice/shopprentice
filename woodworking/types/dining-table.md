# Dining Table

Four-legged table for eating — dining tables, farm tables, harvest tables, kitchen tables. Also covers general-purpose work tables. Distinguished from desks by lack of drawers (typically) and from coffee/side tables by height (28–31").

## Components

| Component | Required | Role |
|-----------|----------|------|
| Legs | Yes | 4 vertical supports at corners |
| Aprons/Rails | Yes | Horizontal members connecting legs below the top |
| Top | Yes | Flat surface (solid panel, glue-up, or breadboard) |
| Stretchers | Optional | Lower horizontal members for additional rigidity |

### Component relationships

```
Legs at 4 corners
Aprons connect adjacent legs at top (front, back, left, right)
Top sits on aprons, attached with buttons or dominos
Stretchers (if present) connect legs at a lower height
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Apron mortises | Legs (2 adjacent faces each) | Apron tenons CUT legs |
| Stretcher mortises | Legs (below apron mortises) | Stretcher tenons CUT legs |
| Top attachment holes | Aprons (top edge, pocket or slot) | Button slot or domino |

**No front openings** — tables are open on all sides.

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Apron to leg | Blind M&T | `mortise_tenon` |
| Stretcher to leg | M&T or domino | `mortise_tenon` or `domino` |
| Top to apron | Buttons, figure-8s, or dominos | inline or `domino` |
| Breadboard ends (if present) | M&T with elongated slots | `breadboard_ends` |

**Top attachment must allow wood movement.** The top expands/contracts across its width (perpendicular to grain). Buttons or elongated slots let it move. Never glue the top directly to aprons across the grain.

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Table top buttons | When using button attachment | — (shop-made or catalog) |
| Floor glides | Always | — (chamfer on leg bottoms) |

## Build Order

```
1. Legs (build one, mirror to 4 corners)
2. Long aprons (front + back)
3. Short aprons (left + right)
4. Apron-to-leg M&T (cross-component CUTs)
5. Stretchers (if present) + stretcher-to-leg M&T
6. Top board (single panel or glue-up)
7. Top attachment (dominos or button slots)
8. Breadboard ends (if present)
9. Details (leg tapers, edge treatments)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After legs | 4 | Legs at correct splay (if any) |
| After aprons | 8 (4 legs + 4 aprons) | Aprons between adjacent legs |
| After top | 9 | Top centered on frame |
| Final | 9–15 | Zero interferences |

## Common Mistakes

- Apron tenons colliding inside the leg (stagger depths or notch tenons)
- Top glued to aprons across grain direction (causes cracking)
- Leg taper starting at wrong height (should start below apron, not at floor)
- Stretcher tenons conflicting with apron tenons inside the same leg

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| table_l | 48–96 in | 60 in |
| table_w | 30–42 in | 36 in |
| table_h | 28–31 in | 30 in |
| top_thick | 0.75–1.5 in | 1 in |
| leg_size | 1.5–3 in | 2 in |
| apron_h | 3–5 in | 4 in |
| apron_thick | 0.75 in | 0.75 in |
