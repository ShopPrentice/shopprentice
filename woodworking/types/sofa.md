# Sofa

Upholstered seating for multiple people — sofas, couches, settees, loveseats. The wood frame provides structure; cushions and upholstery provide comfort.

**Note:** ShopPrentice models the wood frame only. Upholstery, cushions, springs, and webbing are not modeled — they are specified in the README as finishing details.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Seat frame | Yes | Rectangular frame supporting seat cushions |
| Back frame | Yes | Angled frame supporting back cushions |
| Arms | Yes | Side supports (can be wood or upholstered) |
| Legs | Yes | 4–6 supports |
| Seat support | Yes | Webbing cleats, slats, or plywood deck |

### Component relationships

```
Seat frame is a horizontal rectangle of rails
Back frame angles backward from seat frame rear
Arms span from back frame to seat frame front
Legs support seat frame at corners
Seat support spans inside seat frame
```

## Connections

| Connection | Joint type | Template |
|-----------|-----------|----------|
| Seat rail to leg | Blind M&T or domino | `mortise_tenon` or `domino` |
| Back rail to seat | Angled M&T | `mortise_tenon` (with angle) |
| Arm to back/seat frame | M&T or domino | `mortise_tenon` |
| Seat support (plywood) | Sits on ledger strips | inline |
| Seat support (webbing) | Tacked to frame edges | — (not modeled) |

## Parameter Suggestions

| Parameter | Typical range | Default |
|-----------|--------------|---------|
| sofa_l | 60–90 in | 72 in |
| seat_d | 20–24 in | 22 in |
| seat_h | 17–19 in | 18 in |
| back_h | 30–36 in (from floor) | 34 in |
| back_angle | 10–15 deg | 12 deg |
| arm_h | 24–28 in (from floor) | 26 in |
| rail_size | 2–3 in | 2.5 in |
