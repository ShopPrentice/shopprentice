# Planter

Outdoor or indoor plant container — wood planters, window boxes, plant stands. Frame construction with slat infill panels. Must handle moisture (drainage, wood movement).

## Components

| Component | Required | Role |
|-----------|----------|------|
| Legs/Posts | Yes | Vertical corner members |
| Rails | Yes | Horizontal frame members (upper and lower) connecting posts |
| Slat panels | Yes | Infill boards between rails on each side |
| Bottom slats | Optional | Slatted bottom for drainage |

### Component relationships

```
Posts at 4 corners, spanning full height
Upper rails connect posts at top
Lower rails connect posts near bottom
Slat panels fill the space between upper and lower rails
Bottom slats (if present) span between lower rails
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Rail mortises | Posts (all 4 faces) | Rail tenon CUTs post |
| Slat grooves | Rails (inner faces) | Slat tongue CUTs groove in rail |
| Drainage gaps | Between bottom slats | Spacing between slat bodies |

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Rail to post | M&T (blind or through) | `mortise_tenon` |
| Slat to rail | Tongue & groove (T&G) | inline (slat tongue CUTs rail groove) |
| Bottom slats to rail | Dominos or sitting in dado | `domino` or inline |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| None typical | — | — |

## Build Order

```
1. Legs/posts (build one, mirror to 4 corners)
2. Long rails (front/back, upper + lower — build template, mirror)
3. Short rails (left/right, upper + lower — build template, mirror)
4. Rail-to-post M&T (cross-component CUTs)
5. Long side slats (T&G, template + pattern)
6. Short side slats (T&G, template + pattern)
7. Bottom slats (if present) + domino joinery
8. Details (chamfers on post tops)
```

## Validation Rules

| Phase | Expected bodies | Check |
|-------|----------------|-------|
| After frame | 4 posts + 8 rails = 12 | Frame dimensions match |
| After slats | +n_long×2 + n_short×2 | Slats fill panels |
| Final | ~20–40 | Zero interferences |

## Common Mistakes

- T&G grooves not stopped at post boundaries (visible grooves on post faces)
- Slat count not filling the space exactly (need gap-filler slat for remainders)
- Long and short rails colliding inside the post (need staggered mortise depths)
- Not accounting for wood movement in slat panels (T&G allows expansion)

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| planter_l | 12–36 in | 14 in |
| planter_w | 6–14 in | 4 in |
| planter_h | 6–14 in | 3.5 in |
| leg_size | 1–2 in | 1.5 in |
| board_thick | 0.5–0.75 in | 0.625 in |
| slat_width | 1.5–3 in | 2.5 in |
