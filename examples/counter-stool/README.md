# Counter Stool

A parametric bar-height stool with compound-splayed legs, Festool Domino joinery to the seat, stopped-tenon stretchers on all four sides, and a footrest.

![Counter Stool — iso top-left](screenshots/iso-top-left.png)

![Counter Stool — iso top-right](screenshots/iso-top-right.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a bar-height counter stool: 15.75" x 11" seat, 24" leg height, 4 splayed legs
(6° along length, 4° along width), Festool Domino joinery to seat, stopped-tenon
stretchers on all 4 sides, footrest on front stretcher. All parametric.
```

### Appearance

```
apply_appearance(species="white oak")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`counter_stool.py`](counter_stool.py) — 661 lines, fully parametric.

---

## Dimensions

All exposed as User Parameters (Modify > Change Parameters):

### Seat

| Parameter | Default | Description |
|-----------|---------|-------------|
| `seat_l` | 15.75 in | Seat length (X) |
| `seat_w` | 11 in | Seat width (Y) |
| `seat_t` | 1.5 in | Seat thickness |

### Legs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `leg_w` | 1.75 in | Leg width (front view) |
| `leg_d` | 1.5 in | Leg depth |
| `leg_h` | 24 in | Leg height to seat bottom |
| `leg_inset_x` | 1.25 in | Leg center from seat X edge |
| `leg_inset_y` | 1.25 in | Leg center from seat Y edge |
| `splay` | 6 deg | Leg splay along length |
| `splay_w` | 4 deg | Leg splay along width |

### Stretchers

| Parameter | Default | Description |
|-----------|---------|-------------|
| `str_t` | 1.25 in | Stretcher thickness |
| `str_w` | 0.875 in | Stretcher width |
| `front_str_h` | 7 in | Front stretcher center Z |
| `side_str_h` | 4.5 in | Side stretcher center Z |
| `st_w` | 1 in | Stopped tenon width |
| `st_d` | 0.375 in | Stopped tenon depth |
| `st_l` | 0.875 in | Stopped tenon length |

### Domino (Leg-to-Seat)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dm_t` | 8 mm | Domino thickness (cutter diameter) |
| `dm_w` | 22 mm | Domino width |
| `dm_l` | 40 mm | Domino length |

### Footrest

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fr_t` | 0.625 in | Footrest thickness |
| `fr_w` | 1.75 in | Footrest width |

---

## Design

### Bodies (14 total, root-only build)

| Body | Description |
|------|-------------|
| Seat | 15.75" x 11" solid top |
| Leg_NL, Leg_NR, Leg_FL, Leg_FR | 4 compound-splayed legs (6° length, 4° width) |
| DM_NL, DM_NR, DM_FL, DM_FR | 4 domino loose tenon voids (leg-to-seat) |
| Str_Back, Str_Front, Str_Left, Str_Right | 4 stretchers with stopped tenons |
| Footrest | Bar on front stretcher |

### Key Techniques

- **Compound splay** — Each leg is extruded vertically, then rotated with `MoveFeature` using compound angles (primary splay along length + secondary splay along width). The leg position is computed with `tan(splay)` offsets at foot height.
- **Splay-adjusted stretcher positions** — Stretcher endpoints are computed at the correct height along the splayed leg centerline, accounting for both splay angles. Stretchers connect between adjacent leg centers at their respective heights.
- **Stopped tenons** — Each stretcher has tenon bodies at both ends that CUT mortises into the legs. Tenons are shorter than the leg cross-section so they don't exit the other side.
- **Domino joinery** — Festool 8 × 22 × 40 mm domino voids at each leg-to-seat interface. Stadium-shaped bodies straddling the joint, CUT into both leg top and seat underside with `keepTool=True`.
- **Footrest** — Simple board sitting on top of the front stretcher, spanning between the front legs.
