# Chair

Seating with a back — dining chairs, side chairs, arm chairs. Distinguished from stools by having a backrest, and from benches by being single-seat.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Seat | Yes | Sitting surface (flat or contoured) |
| Back legs | Yes | 2 rear supports, floor to backrest top |
| Front legs | Yes | 2 front supports, floor to seat underside |
| Backrest | Yes | Structure between back legs above the seat (see Backrest Styles below) |
| Side aprons | Yes | Connect front legs to back legs below seat |
| Front apron | Yes | Connects front legs below seat |
| Back apron | Usually | Connects back legs below seat |
| Stretchers | Optional | Lower horizontal braces between legs for stability |
| Arms | Optional | Armrests from back legs to front legs |

## Back Leg Profiles

The back legs define the chair's character. Choose based on the design:

| Profile | When to use | Construction |
|---------|------------|--------------|
| **Bent-back** | Most dining chairs — vertical below seat, angled above | Profile sketch on YZ plane (6-line closed shape), extrude by leg_size. Fillet at bend. See `angled-construction.md` "Angled Chair Backrests". |
| **Straight raked** | Simple/rustic chairs — continuous angle from floor to top | Single rectangular extrude + MoveFeature to rotate entire leg. Simpler but less comfortable (leg footprint shifts backward). |
| **Fully vertical** | Formal/Shaker — no rake, backrest attached flat | Simple rectangular extrude, same as front legs but taller. Backrest pieces mount directly. |
| **Curved** | Windsor, steam-bent — continuous curve | Sweep along a spline path, or profile sketch with arcs. Advanced. |

**Bent-back is the most common and recommended default.** The bend gives comfortable rake without moving the floor footprint backward.

## Backrest Styles

The backrest is the most variable part of a chair. Each style has different components and joinery:

| Style | Components | Connections to posts | Between-component connections |
|-------|-----------|---------------------|------------------------------|
| **Ladder-back (horizontal rails)** | 2–4 horizontal rails spanning between posts | Each rail: through-mortise (extend rail full seat_w, CUT into posts) OR dominos at each end | None needed — rails are independent |
| **Vertical slats + rails** | Top rail + bottom rail + 3–5 vertical slats | Rails → posts: tilted dominos | Slats → rails: stub tenons (CUT) |
| **Splat** | Top rail + single wide board | Rail → posts: dominos or through-mortise. Splat → posts: tenons at each side | Splat → rail: stub tenon at top |
| **Panel + frame** | Top rail + bottom rail + panel between | Rails → posts: M&T. Panel: groove in rails | Panel floats in groove (no glue) |

### Ladder-back details
The simplest and most robust backrest. Each rail is an independent horizontal board spanning between the back posts. Rails are typically 2–3" tall, 0.75–1" thick, evenly spaced in the backrest zone.

- **Through-mortise approach**: make rails full `seat_w` wide, CUT into both posts. Simple, strong.
- **Domino approach**: rails span only between posts (`short_apron_l` wide), tilted dominos at each end.
- Rails centered on post cross-section: `back_face_y = seat_d - leg_size/2 - rail_thick/2`
- All rails rotated together with the same back_rake transform as the backrest.

### Vertical slat + rail details (Tested — NORDVIKEN-style dining chair)
- Top rail between posts, offset 0.5" below post top ("ear" detail)
- Bottom rail at bend point
- Vertical slats with equal gaps: `slat_gap = (short_apron_l - n_slats * slat_w) / (n_slats + 1)`
- Slats have stub tenons (dm_d deep) inserting into both rails (CUT creates mortise)
- Rails connected to posts with tilted dominos (see `angled-construction.md`)
- All back pieces rotated together by back_rake around the bend pivot

## Ergonomic Requirements

- **Seat height**: 17–18" (standard dining)
- **Seat depth**: 15–17"
- **Back height**: 32–38" total from floor
- **Back angle**: 5–10° (8° is comfortable for dining; 5° is barely noticeable)
- **Bend point** (bent-back legs): 1–3" above seat height

## Connections — Every Piece Must Be Mechanically Joined

Universal connections (all chair styles):

| Connection | Joint type | Key rule |
|-----------|-----------|----------|
| Apron → leg | Domino or M&T | Apron must sit within leg's cross-section range (rule 10) |
| Back apron → back leg | Domino | Flush with OUTER face of back legs (not inner face) |
| Stretcher → leg | Domino (1 per end) | Center stretchers on legs for balanced mortise |
| Seat → back legs | Notch (CUT) | Back legs pass through seat |

Backrest connections: see the Backrest Styles table above — varies by style.

**Positioning rule**: parts must overlap with the leg body in BOTH the X and Y ranges for dominos to CUT into both pieces. Front apron at Y=[0, apron_thick] works because it's within front leg Y=[0, leg_size]. Back apron must be at Y=[seat_d-apron_thick, seat_d] for the same reason.

## Build Order

```
1. Front legs (vertical, rectangular extrude)
2. Back legs (profile depends on leg style — see Back Leg Profiles)
3. Aprons (4 — back apron flush with OUTER face of back legs)
4. Stretchers (if present — centered on legs)
5. Seat (extrude, notch around back legs)
6. Backrest (style-dependent):
   - Ladder-back: build N rails, rotate by back_rake, CUT or domino to posts
   - Vertical slats: build rails + slats, rotate, CUT slats into rails, dominos rails to posts
   - Splat: build rail + splat board, rotate, M&T connections
7. Cross-component CUTs (seat notch, backrest joinery)
8. Dominos (aprons + stretchers to legs)
9. Details (leg chamfers, seat fillet)
10. Verify: check_interference = 0, no floating pieces
```

## Common Mistakes

- **Back apron at inner face of legs** — zero Y overlap, dominos miss the leg. Flush with outer face.
- **Two-piece back leg JOIN** — creates notch on inner face. Use single profile sketch + extrude for bent-back legs.
- **Stretchers flush with outer face** — unbalanced mortise. Center: `leg_size/2 - str_thick/2`.
- **Vertical dominos on angled backrest joints** — misaligned with rail cross-section. Use tilted dominos.
- **Backrest pieces just touching, no joinery** — every piece needs mechanical connection.
- **Back too short** — 32" minimum for dining (lower back support)
- **Back rake too small** — 5° is barely noticeable. Use 8° for comfortable dining.
- Multiple tenons colliding inside leg at rail intersection — offset Z positions

## Parameter Suggestions

### Core (all chairs)

| Parameter | Range | Default |
|-----------|-------|---------|
| seat_w | 16–20 in | 18 in |
| seat_d | 15–17 in | 17 in |
| seat_h | 17–18 in | 18 in |
| back_h | 32–38 in | 34 in |
| back_rake | 5–10 deg | 8 deg |
| leg_size | 1.25–2 in | 1.5 in |
| apron_h | 2.5–4 in | 3 in |
| apron_thick | 0.75–1 in | 0.75 in |
| seat_thick | 0.75–1 in | 0.75 in |

### Bent-back legs

| Parameter | Range | Default |
|-----------|-------|---------|
| bend_above | 1–3 in | 2 in |
| bend_r | 4–8 in | 6 in |

### Stretchers (when present)

| Parameter | Range | Default |
|-----------|-------|---------|
| str_h | 1–2 in | 1.5 in |
| str_thick | 0.75–1 in | 1 in |
| str_z | 3–6 in | 4 in |

### Backrest (style-dependent)

| Parameter | Applies to | Range | Default |
|-----------|-----------|-------|---------|
| n_rails | Ladder-back | 2–4 | 3 |
| rail_h | Any with rails | 2–3 in | 2.5 in |
| rail_thick | Any with rails | 0.75–1 in | 1 in |
| top_rail_off | Vertical slats | 0.25–0.75 in | 0.5 in |
| n_slats | Vertical slats | 3–5 | 3 |
| slat_w | Vertical slats | 1.5–2.5 in | 2 in |
| slat_thick | Vertical slats | 0.5–0.75 in | 0.75 in |
| splat_w | Splat | 6–10 in | 8 in |
