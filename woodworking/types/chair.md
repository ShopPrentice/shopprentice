# Chair

Seating with a back — dining chairs, side chairs, arm chairs. Distinguished from stools by having a backrest, and from benches by being single-seat.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Seat | Yes | Shaped sitting surface (flat or contoured/deepened for comfort) |
| Back legs | Yes | 2 rear supports extending from floor through seat to backrest height |
| Front legs | Yes | 2 front supports from floor to seat |
| Back rest | Yes | Horizontal slats or rails between back legs (ladder-back, splat, etc.) |
| Side rails/aprons | Yes | Connect front legs to back legs below seat |
| Front rail/apron | Yes | Connects front legs below seat |
| Back rail | Optional | Lower rail between back legs below seat |
| Stretchers | Optional | Lower horizontal braces between legs |
| Arms | Optional | Armrests from back legs to front legs (arm chairs) |

### Component relationships

```
Back legs are continuous from floor to backrest top (often angled/curved)
Front legs connect to seat and front rail
Side rails span between front and back legs at seat height
Front rail spans between front legs
Back rest slats sit between back legs above seat
Seat sits on top of rail/apron frame
```

## Ergonomic Requirements

These are functional, not just aesthetic:
- **Seat height**: 17–18" (standard dining height)
- **Seat depth**: 15–17" (deeper than a stool — you lean back)
- **Back height**: 36–40" total from floor (high back prevents fatigue)
- **Back angle**: 5–10° (slight recline for comfort)
- **Seat contour**: A deepened/curved seat distributes weight and improves comfort. A flat seat board is acceptable but less comfortable.

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Rail mortises | All 4 legs | Rail tenons CUT legs |
| Back rest mortises | Back legs | Back rest slat tenons CUT back legs |

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Rail/apron to leg | Blind M&T or domino | `mortise_tenon` or `domino` |
| Back rest slats to back leg | M&T or domino | `mortise_tenon` or `domino` |
| Stretcher to leg | M&T or domino | `mortise_tenon` or `domino` |
| Seat to rails | Buttons, screws from below, or dominos | inline or `domino` |
| Arm to legs | M&T, dowels, or dominos | `mortise_tenon` |

## Build Order

```
1. Back legs (taller, possibly angled)
2. Front legs (shorter)
3. Side rails/aprons
4. Front rail + back rail (if present)
5. Rail-to-leg joinery (cross-component CUTs)
6. Back rest slats (2–4 horizontal slats between back legs)
7. Back rest to back leg joinery
8. Seat board
9. Seat attachment
10. Arms (if present) + joinery
11. Details (leg chamfers, seat edge rounding)
```

## Common Mistakes

- **Back too short** — should be 36–40" from floor, not 34"
- **Seat too shallow** — 15–17" deep for leaning back, not 12"
- **No back rest slats** — a single rail doesn't provide back support; need 2–4 horizontal slats (ladder-back) or a solid splat
- Back leg angle not accounted for in mortise positions
- Multiple tenons colliding inside leg at rail intersection
- Seat not allowing for wood movement (glued across grain)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| seat_w | 16–20 in | 18 in |
| seat_d | 15–17 in | 16 in |
| seat_h | 17–18 in | 18 in |
| back_h | 36–40 in (total from floor) | 38 in |
| back_angle | 5–10 deg | 7 deg |
| leg_size | 1.25–2 in | 1.5 in |
| rail_h | 2.5–4 in | 3 in |
| seat_thick | 0.75–1 in | 0.75 in |
| n_back_slats | 2–4 | 3 |
