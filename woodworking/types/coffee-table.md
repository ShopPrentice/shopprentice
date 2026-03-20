# Coffee Table

Low table for living room — coffee tables, cocktail tables. Height 16–20" (lower than dining tables). Often has a shelf below. Similar structure to dining table but lower and often squarer proportions.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Top | Yes | Flat surface |
| Legs | Yes | 4 short supports |
| Aprons/Rails | Yes | Connect legs below top |
| Shelf | Optional | Lower shelf between stretchers or legs |
| Stretchers | Optional | Connect legs at lower height |

### Component relationships

```
Legs at 4 corners
Aprons connect adjacent legs at top (front, back, left, right)
Top sits on aprons, attached with buttons or dominos
Shelf (if present) spans between legs near floor
```

## Openings & Cavities

No openings needed — coffee tables are open on all sides.

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Apron to leg | Domino grid (2 per joint) | `domino.grid()` |
| Top to apron | Buttons or dominos | inline or `domino` |
| Shelf to legs | Resting on stretchers or in dados | inline |
| Stretcher to leg | Single domino or M&T | `domino.single()` or `mortise_tenon` |

## Build Order

```
1. Legs (build FL, mirror to all 4 corners)
2. Aprons (build front + left, mirror for back + right)
3. Top (solid panel)
4. Shelf (if present)
5. Domino joinery — apron-to-leg at all 8 joints (cross-component CUTs)
6. Details (edge treatments)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After legs | 4 | Symmetrically placed |
| After aprons | 8 | Aprons between correct leg pairs |
| After top + shelf | 10 | Top spans full length/width |
| After dominos | +16 void bodies | Mortise pockets visible in legs and apron ends |

## Common Mistakes

- Apron-to-leg joints missing entirely (bodies just positioned with no connection)
- Domino voids placed at wrong height (should be centered vertically in apron)
- Aprons extending into leg volume (should butt against leg face, not overlap)
- Shelf floating without support (needs to rest on stretchers or sit in dado)
- Top glued to aprons across grain direction (restrict movement — use buttons)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| table_l | 36–54 in | 48 in |
| table_w | 18–30 in | 24 in |
| table_h | 16–20 in | 18 in |
| top_thick | 0.75–1.5 in | 1 in |
| leg_size | 1.5–2.5 in | 2 in |
| dm_count | 2 | Dominos per apron end |
| dm_t | 8 mm | Domino cutter diameter |
