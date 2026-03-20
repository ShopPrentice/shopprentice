# Bench

Multi-seat or utility seating — entryway benches, garden benches, dining benches, workbenches. Distinguished from stools by being multi-seat (wider), and from chairs by typically having no back (or a simple back rail).

## Components

| Component | Required | Role |
|-----------|----------|------|
| Seat/Top | Yes | Long flat surface |
| Legs | Yes | 4 or more supports |
| Stretchers | Recommended | Horizontal members connecting legs for rigidity |
| Back rest | Optional | Simple rail or board above seat (garden/park bench) |
| Aprons/Rails | Optional | Below seat connecting legs (like a table) |
| Shelf | Optional | Lower shelf between stretchers (entryway bench) |

### Component relationships

```
Seat spans between leg pairs
Legs at corners (or evenly spaced for long benches)
Stretchers connect legs at a lower height
Aprons (if present) connect legs at seat underside
Back rest (if present) extends from back legs above seat
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Leg mortises | Seat underside (if through-tenon) | Leg tenon CUTs through seat |
| Stretcher mortises | Legs | Stretcher tenon CUTs leg |

## Connections

| Connection | Joint type | Template | Notes |
|-----------|-----------|----------|-------|
| Apron to leg | Domino grid (2 per joint) | `domino.grid()` | 8 joints total |
| Stretcher to leg | Single domino per end | `domino.single()` | Lower in leg than aprons |
| Leg to seat | Seat rests on apron frame | — | Top attached via dominos or buttons |
| Back rest to legs | M&T or domino | `mortise_tenon` | Only if back rest present |
| Shelf to stretchers | Resting or dado | inline | Only if shelf present |

**Stretcher vs apron domino height:** Apron dominos are centered in the apron height. Stretcher dominos use a single centered domino. Both must be offset in Z so they don't collide inside the same leg — aprons are higher (near seat), stretchers are lower (near floor).

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Floor glides | Always | — (chamfer on leg bottoms) |

## Build Order

```
1. Seat board
2. Legs (build one pair, mirror/pattern)
3. Leg-to-seat joinery
4. Stretchers (build template, mirror)
5. Stretcher-to-leg joinery
6. Aprons (if present)
7. Back rest (if present)
8. Shelf (if present)
9. Details (seat edge rounding, leg chamfers, through-tenon wedges)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After seat + legs | 5 | Legs at correct positions/splay |
| After stretchers | 7–9 | Stretchers between correct leg pairs |
| Final | 7–12 | Zero interferences |

## Common Mistakes

- Through-tenon not trimmed flush with seat top
- Stretcher height conflicting with knee clearance
- Long bench sagging (need center support or thicker seat)
- Splayed legs not flat on ground plane

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| bench_l | 36–72 in | 48 in |
| bench_w | 12–18 in | 14 in |
| seat_h | 17–18 in | 18 in |
| seat_thick | 1–2 in | 1.5 in |
| leg_size | 1.5–2.5 in | 2 in |
