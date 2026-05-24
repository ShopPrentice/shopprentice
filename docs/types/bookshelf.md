# Bookshelf

Open-front shelving unit for books and display. Distinguished from cabinets by having no doors and from shelf (wall-mount) by being freestanding.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Sides | Yes | Left + right side panels (mirror pair) |
| Shelves | Yes | Horizontal boards between sides |
| Top | Yes | Top board (can be a shelf or a cap) |
| Back | Optional | Plywood back panel for rigidity |
| Kick/Base | Optional | Plinth or recessed kick below bottom shelf |

### Component relationships

```
Sides span full height
Shelves sit in dados or on shelf pins between sides
Top caps the sides (dovetails, dados, or flush)
Back panel (if present) sits in rabbet in sides
Kick (if present) is below the bottom shelf
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Shelf dados | Side boards | Shelf bodies CUT dados via combine |
| Back panel rabbet | Side boards (back edge) | Rabbet CUT tool body |

**No front openings needed** — bookshelves are open-front by definition.

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Fixed shelves to sides | Through dados | inline (shelf CUTs side) |
| Adjustable shelves | Shelf pin holes | `shelf_pins` (when available) |
| Top to sides | Through M&T, dovetails, or dados | `mortise_tenon` or `dovetail` |
| Back panel | Rabbet in sides | inline |
| Shelf-to-back (if back panel) | Dominos for alignment | `domino` |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Shelf pins | When shelves are adjustable | `shelf_pins` |
| Wall anchor bracket | When bookshelf is tall (tip-over risk) | — |

## Build Order

```
1. Side boards (mirror pair)
2. Top board
3. Shelf template (one shelf, positioned parametrically)
4. Shelf pattern along Z (count = n_shelves)
5. Cross-component: shelf CUTs dados into sides
6. Back panel (if present)
7. Side rabbets for back panel
8. Kick/base (if present)
9. Details (edge treatments)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After sides + top | 3 | Dimensions match |
| After shelves | 3 + n_shelves | Shelves evenly spaced |
| Final | 4–8 + n_shelves | Zero interferences |

## Common Mistakes

- Shelf spacing not parametric (hardcoded positions instead of derived from count)
- Dados not stopped at front edge (visible groove on shelf front face)
- Back panel rabbet cutting through top/bottom dovetails
- Shelves extending into side board thickness (should be inner_w)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| case_w | 24–48 in | 36 in |
| case_d | 8–14 in | 12 in |
| case_h | 36–84 in | 72 in |
| n_shelves | 3–6 | 4 |
| board_thick | 0.75 in | 0.75 in |
| shelf_thick | 0.75 in | 0.75 in |
