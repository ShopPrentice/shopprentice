# Pekovich Floating-Top Table (Rachel's Table)

A parametric Arts & Crafts side table modeled in Fusion 360 via Python script. 26"W x 14"D x 27"H, based on Mike Pekovich's design. Features bridle joints, through-tenons, arched side rails, tapered legs with drawbore pins, and a floating top with filleted edges, beveled underside, and cleats.

![Rachel's Table — iso top-right](screenshots/iso-top-right.png)

![Rachel's Table — iso top-left](screenshots/iso-top-left.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a Pekovich-style Arts & Crafts side table: 26"W x 14"D x 27"H with 1-3/8" square
legs, 3/4" rails, bridle joints at front/back corners, through-tenons on side rails,
arched lower edges on all rails, tapered legs, drawbore pins, and a floating top with
filleted edges and cleats. All joinery fully parametric.
```

### Appearance

```
apply_appearance(species="white oak")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`rachels_table.py`](rachels_table.py)

---

## Dimensions

All exposed as User Parameters (Modify > Change Parameters):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `table_w` | 26 in | Overall width (X) |
| `table_d` | 14 in | Overall depth (Y) |
| `table_h` | 27 in | Overall height (Z) |
| `leg_size` | 1.375 in | Leg square cross-section |
| `leg_h` | 26 in | Leg height (floor to leg top) |
| `rail_thick` | 0.75 in | Rail thickness |
| `front_rail_h` | 2 in | Front/back rail height |
| `side_rail_h` | 2 in | Side rail height |
| `top_thick` | 0.75 in | Top panel thickness |
| `top_overhang` | 1 in | Top overhang beyond base |
| `cleat_thick` | 1.75 in | Cleat board thickness |
| `cleat_w` | 1.25 in | Cleat width (X direction) |
| `tt_proud` | 0.25 in | Through-tenon proud amount |
| `tt_shoulder` | 0.3 in | Through-tenon Z shoulder |
| `arch_rise` | 1 in | Side rail arch rise at center |
| `front_arch_rise` | 0.5 in | Front/back rail arch rise |
| `leg_taper` | 0.25 in | Leg taper amount at foot |
| `pin_dia` | 0.25 in | Drawbore pin diameter |
| `pin_inset` | 0.75 in | Pin inset from rail edge |
| `top_bevel_face` | 0.1 in | Top underside bevel face distance |
| `top_bevel_depth` | 0.7 in | Top underside bevel depth |
| `top_fillet` | 0.10 in | Top edge fillet radius |
| `cleat_arch` | 0.5 in | Cleat arch rise |

### Derived Parameters

| Parameter | Expression | Description |
|-----------|------------|-------------|
| `base_w` | `table_w - 2 * top_overhang` | Base width |
| `base_d` | `table_d - 2 * top_overhang` | Base depth |
| `br_slot_w` | `leg_size / 3` | Bridle slot width |
| `br_cheek` | `(leg_size - br_slot_w) / 2` | Bridle cheek thickness |
| `tt_tenon_h` | `side_rail_h - 2 * tt_shoulder` | Through-tenon height |
| `rail_cheek` | `(rail_thick - br_slot_w) / 2` | Rail cheek waste width |
| `taper_start` | `leg_h - front_rail_h - side_rail_h` | Z where leg taper begins |

---

## Design

### Components and Features

| Component | Features |
|-----------|----------|
| **Legs** | FL leg extrude, bridle slot CUT, through-mortise CUT, X/Y taper CUTs, pin bodies + pin hole CUTs, mirror all 4 legs + pins |
| **Rails** | Front rail + bridle tenon JOIN + mirror tenon to FR + arch CUT, mirror to back; Left side rail + through-tenon JOIN + mirror tenon to BL + arch CUT, mirror to right |
| **Top** | Top panel at leg_h, left cleat with arch CUT, mirror right cleat |
| **Root** | Pin hole CUTs into front/back rails, cleat mortise CUTs into front/back rails (cross-component via assembly proxies) |

### Key Techniques

- **Bridle joints** — tool body CUTs slot in leg, tenon body JOINs to rail, mirror replicates to opposite end
- **Through-tenons** — tenon proud on outside face, tool body CUTs mortise through leg
- **Arched rails** — arc sketch on construction plane, CUT from rail underside, `smallest_profile()` selects arch region
- **Drawbore pins** — cylindrical bodies CUT holes through rail+leg intersection
- **Floating top** — cleats inside rails with through-mortises into front/back rails
- **Leg tapers** — X and Y direction CUTs starting below rail zone

---

## Customization

Change any parameter in Fusion 360's Change Parameters dialog. Key relationships:

- `base_w = table_w - 2 * top_overhang` — base frame inset from top edge
- `br_slot_w = leg_size / 3` — bridle slot is 1/3 of leg
- `tt_tenon_h = side_rail_h - 2 * tt_shoulder` — tenon centered in rail height
- `taper_start = leg_h - front_rail_h - side_rail_h` — taper begins below both rail zones

Changing `leg_size` updates bridle slot width, cheek thickness, and all mirror positions automatically.
