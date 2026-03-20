# Stool

Backless seating — counter stools, bar stools, step stools, shop stools. Distinguished from chairs by having no back, and from benches by being single-seat.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Seat | Yes | Flat sitting surface |
| Legs | Yes | 3 or 4 legs supporting the seat |
| Stretchers | Optional | Horizontal members connecting legs for rigidity |
| Footrest | Optional | Bar at comfortable foot height (bar/counter stools) |

### Component relationships

```
Legs attach to underside of seat (M&T, domino, or through-tenon)
Stretchers connect between adjacent legs at a specific height
Footrest (if present) sits on or spans between front stretchers/legs
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Leg mortises | Seat underside | Leg tenon or domino CUTs seat |
| Stretcher mortises | Legs | Stretcher tenon CUTs leg |

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Leg to seat | Dominos, blind M&T, or through-tenon | `domino` or `mortise_tenon` |
| Stretcher to leg | Stopped tenon or domino | `mortise_tenon` or `domino` |
| Footrest to leg/stretcher | Sits on stretcher or tenon into leg | inline or `mortise_tenon` |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Floor glides | Always (protect floors) | — (chamfer on leg bottoms) |

## Build Order

```
1. Seat board
2. Legs (build one, mirror/pattern to 3 or 4)
3. Leg-to-seat joinery (dominos or M&T)
4. Stretchers (if present — build template, mirror)
5. Stretcher-to-leg joinery
6. Footrest (if present)
7. Details (seat edge roundover, leg bottom chamfer)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After seat + legs | 4–5 | Legs positioned at correct splay |
| After stretchers | +2–4 | Stretchers connect adjacent legs |
| Final | 5–12 | Zero interferences, legs touch ground plane |

## Common Mistakes

- Splayed legs not accounting for compound angles in stretcher positioning
- Stretcher tenons colliding inside the leg (need staggered heights or notched tenons)
- Seat too thin for domino depth (check seat_thick > 2 × domino_depth)
- Forgetting floor trim on splayed legs (legs must be flat on Z=0 plane)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| seat_w | 12–18 in | 15 in |
| seat_d | 10–14 in | 12 in |
| seat_thick | 1–2 in | 1.5 in |
| leg_h | 16–30 in | 24 in |
| splay | 0–8 deg | 6 deg |
| n_legs | 3–4 | 4 |
