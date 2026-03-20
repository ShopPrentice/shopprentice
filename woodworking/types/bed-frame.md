# Bed Frame

Sleeping surface support — platform beds, traditional beds, four-poster beds. Holds a mattress with either a solid platform, slat system, or box spring.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Headboard | Yes | Tall panel or frame at the head end (slatted or solid) |
| Footboard | Optional | Shorter panel/rail at the foot end — much shorter than headboard |
| Side rails | Yes | Long boards connecting headboard to footboard |
| Slats | Yes | Flat boards spanning between side rails for mattress support |
| Legs/Posts | Yes | 4 corner posts (can be integrated into headboard/footboard) |
| Center support beam | Required for Queen+ | Longitudinal beam with legs under center of slats |
| Ledger strips | Yes | Cleats on inside of side rails for slats to rest on |

### Component relationships

```
Posts at 4 corners, integrated into headboard/footboard
Side rails connect head posts to foot posts
Ledger strips screwed/glued to inside face of side rails
Slats rest on ledger strips, spanning the bed width
Center support beam (Queen+) runs head-to-foot under slats
Headboard panel/slats sit between or behind head posts
```

## Key Proportions

- **Headboard height**: 34–40" from floor (significantly taller than side rails)
- **Footboard height**: 12–16" from floor (often just the side rail height)
- **This height difference is the defining proportion** — tall headboard / low footboard

## Openings & Cavities

| Opening | In which board | Created by |
|---------|---------------|------------|
| Rail fastener mortises | Posts + rail ends | Bed bolt or bed rail fastener hardware |

## Connections

| Connection | Joint type | Template/Hardware | Notes |
|-----------|-----------|-------------------|-------|
| Side rail to post | **Bed rail fastener** or bed bolt | Hardware (detachable) | Must be disassemblable for moving |
| Headboard panel to posts | M&T, dominos, or panel-in-groove | `mortise_tenon` or `domino` | Permanent |
| Slats to rails | Rest on ledger strips (loose) | inline | Not fastened — just sitting |
| Ledger strips to rails | Screwed or dominos | inline | Permanent |
| Center beam to frame | Rests on cross beam at head and foot | inline | Removable |

**Bed rail fasteners** are specialized detachable hardware — a hook plate on the rail interlocks with a strike plate mortised into the post. This allows the bed to be disassembled for moving. IKEA uses a variation called a bed bolt. These are new hardware types that need templates.

## Size Guide

| Size | Mattress W × L | Frame W (outer) | Frame L (outer) |
|------|---------------|----------------|----------------|
| Twin | 39 × 75 in | 42 in | 80 in |
| Full | 54 × 75 in | 57 in | 80 in |
| Queen | 60 × 80 in | 63 in | 85 in |
| King | 76 × 80 in | 79 in | 85 in |

**Center support beam**: required for Queen and larger. Full size can skip it. Twin never needs it.

## Build Order

```
1. Posts (4 corner posts — back pair taller for headboard)
2. Headboard (slatted or solid panel between back posts)
3. Footboard rail (between front posts, same height as side rails)
4. Side rails (long boards connecting head to foot)
5. Ledger strips (cleats on inside face of side rails)
6. Bed rail fastener hardware (mortised into posts + rail ends)
7. Slats (flat boards resting on ledger strips, patterned along length)
8. Center support beam + legs (Queen+ only)
9. Details (post tops, chamfers)
```

## Common Mistakes

- **Headboard and footboard same height** — footboard should be much shorter (12–16" vs 34–40")
- **No center support beam on Queen/King** — bed will sag in the middle
- **Slats not resting on anything** — need ledger strips on inside of side rails
- **Permanent rail-to-post joints** — beds must be disassemblable; use bed rail fasteners or bed bolts
- Side rails too thin (need 1.5"+ thick for strength under load)
- No ledger strips — slats have nothing to sit on

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| mattress_w | 39–76 in | 60 in (Queen) |
| mattress_l | 75–80 in | 80 in |
| rail_h | 8–12 in | 10 in |
| headboard_h | 34–40 in (from floor) | 36 in |
| footboard_h | 12–16 in (from floor) | 12 in |
| post_size | 2–4 in | 3 in |
| slat_count | 12–20 | 14 |
| slat_thick | 0.75 in | 0.75 in |
