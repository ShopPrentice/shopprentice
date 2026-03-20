# Bed Frame

Sleeping surface support — platform beds, traditional beds, four-poster beds. Holds a mattress with either a solid platform, slat system, or box spring.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Headboard | Yes | Tall panel or frame at the head end |
| Footboard | Optional | Shorter panel or frame at the foot end |
| Side rails | Yes | Long boards connecting headboard to footboard |
| Slats or platform | Yes | Mattress support spanning between side rails |
| Legs/Posts | Yes | 4 corner posts (can be integrated into headboard/footboard) |
| Center support | Recommended | Center rail + legs for large mattresses (Queen+) |

### Component relationships

```
Posts at 4 corners, integrated into headboard/footboard or separate
Side rails connect headboard posts to footboard posts
Slats span between side rails, resting on ledger strips
Center support (if present) runs headboard to footboard under slats
Headboard panel sits between or behind head posts
```

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Rail mortises | Posts | Rail tenon or bed bolt CUTs post |
| Slat slots | Ledger strips on side rails | Slat body sitting in dado or on ledger |

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Side rail to post | Bed bolt hardware or M&T | `bed_rail` or `mortise_tenon` |
| Headboard to posts | M&T, dominos, or panel-in-groove | `mortise_tenon` or `domino` |
| Slats to rails | Rest on ledger strips (loose) | inline (ledger strip screwed to rail) |
| Center support | Rests on cross beam at head and foot | inline |

## Hardware Checklist

| Hardware | When needed | Template/catalog |
|----------|------------|-----------------|
| Bed bolts/rail brackets | When disassembly is needed (most beds) | `bed_rail` hardware |
| Slat center supports | For wide mattresses | — |

## Build Order

```
1. Posts (4 corner posts)
2. Headboard panel/frame
3. Footboard panel/frame (if present)
4. Side rails
5. Rail-to-post connection (M&T or bed bolt)
6. Ledger strips on side rails
7. Slats
8. Center support beam (if needed)
9. Details (post finials, chamfers)
```

## Common Mistakes

- Side rails not strong enough for weight (need thick stock, 1.5"+)
- Bed bolt holes not aligned between rail and post
- Slats too far apart (max 3" gap for most mattresses)
- No center support on Queen/King beds (mattress sags)
- Headboard not allowing for different mattress thicknesses

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| mattress_w | 39 in (Twin) – 76 in (King) | 60 in (Queen) |
| mattress_l | 75–80 in | 80 in |
| rail_h | 8–12 in | 10 in |
| headboard_h | 36–54 in (from floor) | 44 in |
| post_size | 2–4 in | 3 in |
| slat_count | 12–20 | 15 |
