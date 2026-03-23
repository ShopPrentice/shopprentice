# Hall Bench with Raked Back

A parametric hall bench — 60"L x 18"D, 18"H seat height, ~32"H back. Profiled back posts with smooth 6" fillet transition from vertical to 8° angled backrest. Wide back board, slab seat, full domino joinery. White oak.

![Hall Bench — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

---

**Script:** [`hall_bench.py`](hall_bench.py) — 10 structural bodies + 18 joinery voids. Zero interferences.

### Appearance

```
apply_appearance(species="white oak")
```

**Style:** Modern

### Key Features

- **Raked back posts** — single profiled extrusion per post, vertical below seat then 8° backward lean with smooth curved transition (6" fillet radius)
- **Square post tops** — cut perpendicular to the rake angle
- **20 cm back board** — domino-joined to posts, rotated to match rake
- **1.5" slab seat** — notched around back posts, rounded front edge (0.5" fillet)
- **Chamfers** — bottom edges on all legs/posts, vertical edges on front legs, extrusion edges on posts

### Joinery

| Connection | Type | Details |
|-----------|------|---------|
| Aprons → legs/posts | Domino (8mm) | 2 per end, standard grid |
| Back board → posts | Domino (8mm) | 1 per end, at raked position |
| Seat → posts | Notch (CUT) | Seat notched around back posts |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `bench_l` | 60 in | Overall length |
| `bench_d` | 18 in | Overall depth |
| `seat_h` | 18 in | Seat height |
| `back_rake` | 8° | Back rake angle |
| `bend_above` | 2 in | Height above seat where bend starts |
| `bend_r` | 6 in | Bend fillet radius |
| `back_board_w` | 20 cm | Back board width |
| `back_board_offset` | 7 in | Distance along post from bend to board center |
| `leg_size` | 2 in | Leg cross-section (square) |
