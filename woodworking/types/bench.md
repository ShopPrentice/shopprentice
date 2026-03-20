# Bench

Multi-seat or utility seating — entryway benches, dining benches, garden benches, workbenches. Distinguished from stools by being multi-seat (wider), and from chairs by typically having no back (or a simple back rail).

## Components

| Component | Required | Role |
|-----------|----------|------|
| Seat/Top | Yes | Long flat surface — edges should be rounded for comfort |
| Legs | Yes | 4 or more supports |
| Aprons/Rails | Recommended | Below seat connecting legs |
| Stretchers | Optional | Lower horizontal members for additional rigidity |
| Back rest | Optional | Simple rail above seat (garden/park bench) |
| Shelf | Optional | Lower shelf between stretchers (entryway bench) |

### Component relationships

```
Seat spans between leg pairs
Legs at corners (or evenly spaced for long benches)
Aprons connect legs at seat underside
Stretchers (if present) connect legs at a lower height
```

## Ergonomic Notes

- **Seat height**: 17–18" (same as a chair)
- **Seat depth**: 11–14" (narrower than a chair — you sit upright, not leaning back)
- **Seat edges should be rounded** — square corners on a bench are uncomfortable and look unfinished

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Leg mortises | Seat underside (if through-tenon) | Leg tenon CUTs through seat |
| Stretcher mortises | Legs | Stretcher tenon CUTs leg |

## Connections

| Connection | Joint type | Template | Notes |
|-----------|-----------|----------|-------|
| Apron to leg | Domino grid (2 per joint) | `domino.grid()` | 8 joints total |
| Stretcher to leg | Single domino per end | `domino.single()` | Lower in leg than aprons — offset Z to avoid collision |
| Leg to seat | Seat rests on apron frame | — | Attached via dominos or buttons |
| Back rest to legs | M&T or domino | `mortise_tenon` | Only if back rest present |

**Stretcher vs apron domino height:** Apron dominos are centered in the apron height near the top of the leg. Stretcher dominos use a single centered domino lower in the leg. Both must be offset in Z so they don't collide inside the same leg.

## Build Order

```
1. Legs (build 1, mirror to all corners)
2. Aprons (build front, mirror for back; build left, mirror for right)
3. Stretchers (if present — build front, mirror for back)
4. Seat board
5. Domino joinery — apron-to-leg + stretcher-to-leg (cross-component CUTs)
6. Details (seat edge rounding, leg chamfers)
```

## Common Mistakes

- **No joinery at all** — bodies positioned but not mechanically connected
- Seat edges left square (should be rounded for comfort)
- Bench too deep — 11–14" is correct for upright sitting
- Long bench sagging (need center support or thicker seat for benches > 48")
- Stretcher dominos at same height as apron dominos (collision inside leg)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| bench_l | 36–72 in | 48 in |
| bench_w | 11–14 in | 12 in |
| seat_h | 17–18 in | 18 in |
| seat_thick | 1–2 in | 1.5 in |
| leg_size | 1.5–2.5 in | 2 in |
