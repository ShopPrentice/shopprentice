# Hall Bench

A parametric modern hall bench — 60"L x 18"D x 34"H with 1.5" thick slab seat, back frame with 3 vertical slats, and domino joinery at all connections. White oak.

![Hall Bench — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

### Transparent Views — Domino Joinery

All bodies at 0.15 opacity — reveals 18 domino voids at apron-to-leg joints (2 per joint), top rail-to-post connections, and slat stub tenons.

<p float="left">
  <img src="screenshots/transparent-iso-top-left.png" width="49%" />
  <img src="screenshots/transparent-iso-top-right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a 60" hall bench with a back: 18"D seat, 18"H seat height, 34"H total.
Thick slab seat, square legs, back frame with 3 vertical slats, domino joinery
at all connections. All parametric.
```

### Appearance

```
apply_appearance(species="white oak")
```

---

**Script:** [`hall_bench.py`](hall_bench.py) — 13 structural bodies + 18 domino voids. Zero interferences.

### Joinery

| Connection | Type | Details |
|-----------|------|---------|
| Aprons → legs | Domino grid (8mm) | 2 per end, 8 joints total |
| Top rail → back posts | Domino single (8mm) | 1 per end |
| Slats → rails | Stub tenon (body pattern) | Slats fit between top rail and back apron |
| Seat | Slab on apron frame | Rests on apron frame, overhangs legs |

### Key parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `bench_l` | 60 in | Overall length |
| `bench_d` | 18 in | Overall depth |
| `seat_h` | 18 in | Seat height |
| `back_h` | 34 in | Total back height |
| `seat_thick` | 1.5 in | Slab seat thickness |
| `leg_size` | 2 in | Leg cross-section (square) |
| `n_slats` | 3 | Back slats (parametric count) |

### Components

| Component | Bodies | Notes |
|-----------|--------|-------|
| Legs | 4 | FL, FR (short, seat height), BL, BR (tall, back height) |
| Aprons | 4 | Front, Back (mirror), Left, Right (mirror) |
| Seat | 1 | Full-width slab, overhangs legs |
| Back | 4 | Top rail + 3 vertical slats (body pattern) |
