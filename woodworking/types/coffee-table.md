# Coffee Table

Low table for living room — coffee tables, cocktail tables. Height 14–18" (lower than dining tables). Coffee tables are one of the most free-form furniture types — designs range from minimal (just a top on tapered legs) to elaborate (with shelves, drawers, glass inserts).

## Components

| Component | Required | Role |
|-----------|----------|------|
| Top | Yes | Flat surface — rectangular, round, or organic shape |
| Legs | Yes | 4 supports, typically tapered for modern style |
| Aprons/Rails | Optional | Connect legs below top — many modern designs omit these entirely |
| Shelf | Optional | Lower shelf between legs for storage/display |
| Stretchers | Optional | Lower horizontal members for rigidity |

### Component relationships

```
Legs at 4 corners (or 3 for round, or trestle style)
Top attaches to legs via dominos, buttons, or pocket screws
Aprons (if present) connect adjacent legs
Shelf (if present) spans between legs or stretchers
```

**Note:** Modern coffee tables often have NO aprons — legs connect directly to the top underside via dominos. Stability comes from tapered leg geometry rather than a full apron frame. Only add aprons if the design calls for them or if the table is very large.

## Openings & Cavities

No openings needed — coffee tables are open on all sides.

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Leg to top (no apron) | Dominos directly into top underside | `domino` |
| Apron to leg (if aprons present) | Domino grid (2 per joint) | `domino.grid()` |
| Top to apron | Buttons or dominos | inline or `domino` |
| Shelf to legs | Resting on stretchers, in dados, or domino | inline |

## Build Order

```
1. Legs (build 1, mirror to all corners — taper if modern)
2. Top (solid panel)
3. Aprons (if present — build template, mirror)
4. Shelf (if present)
5. Domino joinery — leg-to-top or apron-to-leg (cross-component CUTs)
6. Details (edge treatments, leg taper)
```

## Common Mistakes

- **Over-building with unnecessary aprons** — many modern designs are just top + legs + dominos
- Proportions too square — coffee tables are often elongated (2:1 to 3.5:1 length:width ratio)
- Table too tall — 14–16" is standard, not 18" (lower than dining/side tables)
- Legs too thick — modern coffee tables use slim tapered legs (1.25–1.75")
- Shelf floating without support

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| table_l | 36–63 in | 48 in |
| table_w | 16–24 in | 20 in |
| table_h | 14–18 in | 16 in |
| top_thick | 0.75–1.5 in | 1 in |
| leg_size | 1.25–2 in | 1.5 in |
