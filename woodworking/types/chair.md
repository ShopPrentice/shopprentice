# Chair

Seating with a back — dining chairs, side chairs, arm chairs. Distinguished from stools by having a backrest, and from benches by being single-seat.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Seat | Yes | Shaped sitting surface (flat or contoured) |
| Back legs | Yes | 2 rear supports extending from floor through seat to backrest height |
| Front legs | Yes | 2 front supports from floor to seat |
| Back rest | Yes | Horizontal or shaped board(s) between back legs above seat |
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
Back rest sits between back legs above seat
Seat sits on top of rail/apron frame
Stretchers (if present) connect legs at a lower height
Arms (if present) connect back leg top area to front leg top
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Rail mortises | All 4 legs | Rail tenons CUT legs |
| Back rest mortises | Back legs | Back rest tenon CUTs back legs |
| Stretcher mortises | Legs | Stretcher tenons CUT legs |

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Rail/apron to leg | Blind M&T | `mortise_tenon` |
| Back rest to back leg | M&T or domino | `mortise_tenon` or `domino` |
| Stretcher to leg | M&T or domino | `mortise_tenon` or `domino` |
| Seat to rails | Buttons, screws from below, or dominos | inline or `domino` |
| Arm to legs | M&T, dowels, or dominos | `mortise_tenon` |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Floor glides/pads | Always | — (chamfer on leg bottoms) |

## Build Order

```
1. Back legs (often compound shape — angled or curved)
2. Front legs
3. Side rails/aprons
4. Front rail
5. Back rail (if present)
6. Rail-to-leg M&T (cross-component CUTs)
7. Back rest board(s)
8. Back rest to back leg joinery
9. Stretchers (if present) + joinery
10. Seat board (shaped or flat)
11. Seat attachment
12. Arms (if present) + joinery
13. Details (leg chamfers, seat edge rounding, back rest shaping)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After legs | 4 | Back legs taller, correct angle |
| After rails | 7–8 | Rails connect adjacent legs |
| After back rest | 8–10 | Back rest between back legs |
| After seat | +1 | Seat sits on rail frame |
| Final | 10–15 | Zero interferences, all legs on Z=0 |

## Common Mistakes

- Back leg angle not accounted for in mortise positions (angled leg = angled mortise)
- Multiple tenons colliding inside leg at rail intersection
- Seat not allowing for wood movement (glued across grain)
- Back rest too thin for M&T depth
- Stretchers conflicting with rail tenons inside same leg
- Chair dimensions not ergonomic (seat height 17–18", seat depth 15–17", back angle 5–10°)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| seat_h | 17–18 in | 18 in |
| seat_w | 16–20 in | 18 in |
| seat_d | 15–17 in | 16 in |
| back_h | 32–36 in (total from floor) | 34 in |
| back_angle | 5–10 deg | 7 deg |
| leg_size | 1.25–2 in | 1.5 in |
| rail_h | 2.5–4 in | 3 in |
| seat_thick | 0.75–1 in | 0.75 in |
