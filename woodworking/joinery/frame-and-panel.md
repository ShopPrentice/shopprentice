# Frame-and-Panel Construction

Read this file when building frame-and-panel assemblies: cabinet doors, chest lids, table tops, side panels, wainscoting. Use the `frame_and_panel` template for standard builds; write inline for non-standard configurations.

## Template API

```python
from woodworking.templates import frame_and_panel as fp
```

### `fp.define_params()` — Create user parameters

```python
fp.define_params(params, prefix="fp",
    frame_w="2 in", frame_t="0.75 in",
    groove_w="0.25 in", groove_d="0.375 in",
    panel_t="0.5 in", tongue_l="0.25 in")
```

| Parameter | Prefix default | Description |
|-----------|---------------|-------------|
| `fp_fw` | `frame_w` | Frame member width (visible face dimension) |
| `fp_ft` | `frame_t` | Frame thickness (extrusion depth) |
| `fp_gw` | `groove_w` | Groove width = tongue thickness = tenon thickness |
| `fp_gd` | `groove_d` | Groove depth = tenon length into mating rail |
| `fp_pt` | `panel_t` | Panel total thickness (tongue + field) |
| `fp_tl` | `tongue_l` | Panel tongue protrusion length |

### `fp.build()` — Build the frame-and-panel assembly

```python
result = fp.build(
    comp=door_comp,
    base_plane=xz_plane,
    origin=("0 in", "0 in", "0 in"),
    rail_axis="x", rail_len="door_w",
    stile_axis="z", stile_len="door_h",
    frame_t="fp_ft", frame_w="fp_fw",
    groove_w="fp_gw", groove_d="fp_gd",
    panel_t="fp_pt", tongue_l="fp_tl",
    div_along_stile=1,               # vertical dividers
    div_along_rail=0,                # horizontal dividers
    corner_joint="stub_tenon",       # or "mitered_mt"
    prefix="Door", ev=ev)

# Returns: {rails, stiles, dividers_v, dividers_h, panels,
#           panel_positions, all_bodies}
```

### `fp.add_battens()` — Sliding dovetail battens (穿带)

```python
battens = fp.add_battens(
    comp=top_comp,
    panel_body=result['panels'][0][0],
    base_plane=plane,
    rail_axis="x", stile_axis="y",
    rail_len="table_l", stile_len="table_w",
    frame_w="fp_fw", frame_t="fp_ft",
    panel_t="fp_pt", groove_d="fp_gd",
    count=2, batten_w="1.25 in",
    slot_depth_ratio="0.4", dovetail_angle_deg=12,
    prefix="BT", ev=ev)
```

### `fp.add_raised_bevel()` — Raised bevel panel profile

```python
fp.add_raised_bevel(
    comp=door_comp,
    panel_bodies=[result['panels'][0][0]],
    panel_positions=[result['panel_positions'][0]],
    rail_axis="x", stile_axis="z",
    frame_t="fp_ft", panel_t="fp_pt",
    groove_w="fp_gw", tongue_l="fp_tl",
    bevel_width="1.5 in",
    prefix="Bev", ev=ev)
```

## Positioning

The `base_plane` defines the frame's outer face. The frame extrudes perpendicular to this plane by `frame_t`. The origin's **ext-axis component must be "0 in"** — use `sp.off_plane()` for positioning:

```python
lid_plane = sp.off_plane(comp, root.xYConstructionPlane, "open_height", "LidPl")
fp.build(comp, lid_plane, origin=("0 in", "0 in", "0 in"), ...)
```

## Orientation

| Application | base_plane | rail_axis | stile_axis | Extrude axis |
|-------------|-----------|-----------|------------|-------------|
| Cabinet door | XZ | x | z | y |
| Chest lid | XY (offset) | x | y | z |
| Side panel | YZ | y | z | x |

## How It Works

### Frame Construction

1. **Rails** — rectangular bodies spanning full `rail_len`
2. **Stiles** — rectangular bodies between rails (`stile_len - 2*frame_w`)
3. **Stub tenons** — JOINed onto stiles at `groove_w` thickness, CUT into rails to create mortises
4. **Panels** — full-thickness body with symmetric edge rabbets creating centered tongues (`groove_w` thick)
5. **Panel CUTs** — panels CUT into all frame members (groove = tongue width = mortise width)

### Tongue Centering

Symmetric rabbets from both panel faces ensure the tongue is exactly `groove_w` thick, centered on the frame thickness. This guarantees the panel groove and the tenon mortise are the same width — a common real-world requirement.

### Divider Handling

- **Vertical dividers** (parallel to stiles): continuous between rails, tenons into both rails
- **Horizontal dividers** (parallel to rails): **segmented** between adjacent vertical members to prevent crossing overlaps

## Corner Joint Types

### Stub Tenon (`corner_joint="stub_tenon"`, default)

The stile has a stub tenon at `groove_w` thickness that fits into the rail's continuous groove. Simple and strong for most applications. The rail end grain is visible at the corners.

### Mitered / 格角榫 (`corner_joint="mitered_mt"`)

45° miter on the visible face at each corner — no visible end grain. Behind the miter, the stub tenon still provides connection through the shared groove. The miter is applied as a post-processing step: a triangular prism is CUT from the rail and JOINed to the stile at each corner.

```python
result = fp.build(..., corner_joint="mitered_mt", ...)
```

## Panel Profile Types

### Flat (default)

Panel field flush with or near the frame face. Achieved by setting `panel_t` close to `frame_t`.

| Variation | How to achieve |
|-----------|---------------|
| **Flush** | `panel_t ≈ frame_t` |
| **Proud** (Shaker) | `panel_t > frame_t` |
| **Recessed** | `panel_t < frame_t` |
| **Sunken / 落堂** | Small `panel_t` + small `tongue_l` |

### Raised Bevel

Thick center field with angled bevel transition to the tongue. Call `add_raised_bevel()` after `build()`:

```python
fp.add_raised_bevel(comp, [panel], [position],
    rail_axis="x", stile_axis="z",
    frame_t="fp_ft", panel_t="fp_pt",
    groove_w="fp_gw", tongue_l="fp_tl",
    bevel_width="1.5 in", prefix="Bev", ev=ev)
```

Cross-section:
```
  FIELD (flat top)  ╲              TONGUE (thin)
  ──────────────────╲             ┌──────
                     ╲  bevel     │
                      ╲           │
                       ╲──────────┘
                  bevel_width
```

The bevel is created by triangular wedge CUT bodies on each of the 4 panel edges (outer face only). A small quirk at the field/bevel junction is authentic to traditional raised panel construction.

## Structural Additions

### Sliding Dovetail Battens (穿带)

Cross-grain battens on the panel underside in dovetail grooves. Prevents panel warping while allowing cross-grain expansion. Essential for Chinese table tops.

The batten is a rectangular body with dovetail chamfers on the two longitudinal bottom edges, then CUT into the panel (keepTool=True). The dovetail cross-section:
- Wide base (inside groove): `batten_w`
- Narrow opening (at panel surface): `batten_w - 2 * slot_depth * tan(angle)`
- Typical angle: 10°–14° per side

```python
battens = fp.add_battens(comp, panel, base_plane,
    rail_axis, stile_axis, rail_len, stile_len,
    frame_w, frame_t, panel_t, groove_d,
    count=2, batten_w="1.25 in",
    slot_depth_ratio="0.4", dovetail_angle_deg=12,
    prefix="BT", ev=ev)
```

## Chinese Traditional (攒边打槽装板)

Complete Chinese table top = mitered frame + flat panel + dovetail battens:

```python
# Mitered frame
result = fp.build(comp, plane, origin,
    rail_axis="x", rail_len="table_l",
    stile_axis="y", stile_len="table_w",
    ..., corner_joint="mitered_mt", ...)

# Dovetail battens underneath
battens = fp.add_battens(comp, result['panels'][0][0], plane,
    ..., count=2, dovetail_angle_deg=12, ...)
```

### Key Differences from Western

| Aspect | Western | Chinese |
|--------|---------|---------|
| Corner joint | Square shoulder (visible end grain) | 格角榫 mitered (no end grain) |
| Panel position | Centered in frame thickness | Often flush with top surface |
| Warping control | Floating panel only | 穿带 dovetail battens |
| Panel types | Raised common | Flat or 鼓面 (convex) |

### Chinese Panel Types

| Name | Description |
|------|-------------|
| **平板** (flat) | Flush or slightly recessed; Ming-style |
| **鼓面** (drum-face) | Convex center rising above frame |
| **落堂** (sunken) | Recessed below frame surface |
| **活板** (removable) | Slides out one end |
| **棂格** (lattice) | Geometric bar pattern |

## Applications Quick Reference

| Application | Typical config | Panel type | Additions |
|-------------|---------------|-----------|-----------|
| Cabinet door | XZ, stub_tenon | Flat or raised bevel | — |
| Wide cabinet door | XZ, 1 v-divider | Flat or raised | — |
| Chest lid | XY offset, 0–1 v-div | Flat | — |
| Chinese table top | XY, mitered_mt | Flat flush | 穿带 battens |
| Headboard | XZ, 1v+1h div | Raised bevel | — |
| Side panel | YZ, stub_tenon | Flat | — |
| Wainscoting | XZ, N v-dividers | Flat recessed | — |

## Dimensional Relationships

```
groove_w ≤ frame_t / 2       (groove centered on frame thickness)
tongue_l ≤ groove_d           (tongue fits inside groove)
panel_t > groove_w            (field thicker than tongue)
groove_w = tenon thickness    (shared groove)
bevel_width < (rail_len - 2*frame_w) / 2   (bevel fits inside field)
```

## Validated Configurations

| Test | Bodies | Interferences |
|------|--------|---------------|
| Single-panel door (XZ, stub_tenon) | 5 | 0 |
| 2-panel door (XZ, 1 v-div) | 7 | 0 |
| 2×2 grid (XZ, 1v+1h) | 11 | 0 |
| Lid at Z=5" (XY offset) | 7 | 0 |
| Side panel (YZ) | 5 | 0 |
| Mitered door (XZ, mitered_mt) | 5 | 0 |
| Table + battens (XY, 2 battens) | 7 | 0 |
| Chinese table (XY, mitered + battens) | 7 | 0 |
| Raised bevel door (XZ + bevel) | 5 | 0 |

## Common Pitfalls

1. **Origin ext-axis must be "0 in"** — use `sp.off_plane()` for positioning
2. **Module caching** — use `importlib.reload(fp)` after editing template source
3. **Panel CUT order** — panels CUT frame AFTER mortises; mitered corners re-CUT panels after miter JOIN
4. **Cross-divider segmentation** — h-dividers auto-segment between vertical members
5. **Groove = mortise width** — symmetric rabbets guarantee this; asymmetric rabbets would create mismatched grooves

## Not Yet Implemented

| Feature | Description |
|---------|-------------|
| Raised cove / ogee | Curved bevel profiles (need sweep or loft) |
| Cope-and-stick | Molded frame edge + coped rail ends |
| Haunched M&T | Full tenon + haunch fills groove at corner |
| Cathedral arch | Curved top rail with matching panel |
| Rabbet + molding | Back-loaded panel with applied molding strip |
| Lattice / 棂格 | Geometric bar pattern replacing solid panel |
