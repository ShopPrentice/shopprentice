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
Same as dining table but lower height and different proportions.
Top sits on leg/apron frame
Shelf (if present) spans between legs/stretchers near floor
```

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Apron to leg | Blind M&T | `mortise_tenon` |
| Top to apron | Buttons or dominos | inline or `domino` |
| Shelf to legs | Dados or dominos | inline or `domino` |
| Stretcher to leg | M&T | `mortise_tenon` |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Floor glides | Always | — |

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| table_l | 36–54 in | 48 in |
| table_w | 18–30 in | 24 in |
| table_h | 16–20 in | 18 in |
| top_thick | 0.75–1.5 in | 1 in |
| leg_size | 1.5–2.5 in | 2 in |

Refer to `types/dining-table.md` for detailed build order, validation, and common mistakes — the construction is structurally identical, just shorter.
