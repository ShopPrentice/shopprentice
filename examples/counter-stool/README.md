# Counter Stool

Bar-height stool with splayed legs, domino joinery, stretchers, and footrest.

![Counter Stool](screenshots/overview.png)

## Features

- **Seat**: 15.75" x 11" x 1.5" solid top
- **4 splayed legs**: compound splay (6° along length, 4° along width) via Move rotation
- **Domino joinery**: Festool 8 x 22 x 40 mm dominos connecting legs to seat underside
- **4 stretchers**: front, back, left, right — positioned at leg splay-adjusted heights with stopped tenons
- **Footrest**: front-side rail at 7" height

## Construction

Root-only build (no sub-components). 14 bodies total:
- 1 Seat
- 4 Legs (NL, NR, FL, FR)
- 4 Domino voids
- 4 Stretchers (Back, Front, Left, Right)
- 1 Footrest

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `seat_l` | 15.75 in | Seat length (X) |
| `seat_w` | 11 in | Seat width (Y) |
| `seat_t` | 1.5 in | Seat thickness |
| `leg_w` | 1.75 in | Leg width |
| `leg_h` | 24 in | Leg height to seat bottom |
| `splay` | 6 deg | Leg splay along length |
| `splay_w` | 4 deg | Leg splay along width |
| `str_t` | 1.25 in | Stretcher thickness |
| `front_str_h` | 7 in | Front stretcher center Z |
| `side_str_h` | 4.5 in | Side stretcher center Z |

## Script

[`counter_stool.py`](counter_stool.py) — 661 lines, fully parametric.
