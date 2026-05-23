# Loft Bunk Bed with Desk and Ladder

A parametric loft bunk bed -- Twin 40"W x 75"L, elevated sleeping platform at 58" with integrated desk underneath and angled ladder with hook-tab sides.

---

**Script:** [`loft_bunk_bed.py`](loft_bunk_bed.py) -- 95 bodies (39 structural + 56 domino voids). Zero interferences. Full dependency validation.

**Style:** Modern

### Components

| Component | Bodies | Description |
|-----------|--------|-------------|
| Posts | 4 | 3" square posts, 78" tall with top chamfers |
| BedRails | 4 | Side rails (1.5" thick x 8" tall) + end rails, centered on posts |
| GuardRails | 5 | Top guard rails on 3 sides + partial front (ladder opening) + fence support post (3"×1") |
| Ledgers | 2 | 0.75" strips on inner rail faces supporting slats |
| Slats | 13 | Mattress support, patterned along bed length |
| Desk | 5 | Desktop + 2 front legs + front/back aprons, 30" surface height |
| Ladder | 6 | 2 angled sides with hook tabs + 4 rungs, 12-degree lean |

### Joinery -- 56 Domino Joints

All joinery uses Festool-style domino loose tenons. Void bodies live inside their owning component (not root), with cross-component CUTs via assembly proxies.

| Connection | Domino Size | Count | Details |
|-----------|-------------|-------|---------|
| Side rails to posts | 8mm x 40mm | 8 | 2 per end, at 1/3 and 2/3 rail height |
| End rails to posts | 8mm x 40mm | 8 | 2 per end, same Z positions |
| Guard rails to posts | 6mm x 30mm | 7 | 1 per connection point |
| Fence support to guard rail | 6mm x 30mm | 1 | XY interface at guard rail bottom |
| Desk back apron to posts | 6mm x 30mm | 2 | Rail between posts, dominos at inner X faces |
| Desk front apron to legs | 6mm x 30mm | 2 | At each desk leg |
| Ledger to side rail | 5mm x 30mm | 8 | 4 per side, patterned along length |
| Rung to ladder sides | 6mm x 20mm | 16 | 2 per end x 4 rungs x 2 sides |
| Ladder hook to side rail | 8mm x 40mm | 4 | 2 per ladder side |

### Ladder Design

The ladder uses a 6-vertex polygon profile (parallelogram + hook tab) that wraps around the side rail for a secure connection. Key features:
- **12-degree lean angle** with bottom pulled 2" closer to the bed
- **Hook tabs** extend from the top of each side piece, wrapping over and behind the side rail
- **Side rail CUT** creates a precise notch in each ladder side matching the rail cross-section
- **Rungs patterned** along a construction axis derived from the lean edge

### Dependency Validation

The build includes `model.json` metadata tracking all 25 body relationships:
- **Spatial checks**: body_side verification for all structural bodies
- **Source checks**: find_body() + boundingBox lookups for body-relative referencing
- **Completeness**: all 94 bodies tracked (structural + DM_* glob for voids)

### Key Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `bed_l` / `bed_w` | 75 / 40 in | Mattress dimensions (Twin) |
| `post_size` | 3 in | Square post cross-section |
| `post_h` | 78 in | Total post height |
| `loft_h` | 58 in | Bottom of bed rails from floor |
| `rail_h` | 8 in | Bed rail height |
| `desk_h` | 30 in | Desk surface height |
| `desk_depth` | 25 in | Desk depth front to back |
| `ladder_w` | 16 in | Ladder opening width |
| `n_rungs` | 4 | Number of ladder rungs |
| `n_slats` | 13 | Number of mattress slats |

### Appearance

```
apply_appearance(species="white oak")
```
