# Queen Platform Bed Frame

A parametric modern platform bed — Queen 60"W x 80"L, framed headboard with vertical slats, center support beam with legs, full joinery.

![Queen Platform Bed](screenshots/queen-platform.png)

### Transparent View — Joinery Detail

![Queen Transparent](screenshots/queen-transparent.png)

---

**Script:** [`queen_platform.py`](queen_platform.py) — 33 structural bodies + hardware. Zero interferences.

### Joinery

| Connection | Type | Details |
|-----------|------|---------|
| Side rails → posts | **Bed rail fastener** (100mm) | Detachable — STEP hardware imported, recesses CUT. Lift rail to disconnect. |
| Foot rail → front posts | **Bed rail fastener** (100mm) | Same as side rails |
| Back rail → back posts | **Bed rail fastener** (80mm) | Smaller size for shorter rail |
| Headboard rails → back posts | Domino (8mm) | Permanent joint |
| Headboard slats → rails | Stub tenon (CUT) | Slats insert into rails |
| Ledger strips → side rails | Domino (5mm) | Smaller for 0.75" stock, `long_axis="y"` (flat along grain) |

### Key parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `bed_w` / `bed_l` | 60 / 80 in | Change for Twin (39×75) or King (76×80) |
| `leg_clearance` | 4 in | Space under rails (0 = platform on floor) |
| `mattress_recess` | 1.5 in | Slat top below rail top (secures mattress) |
| `back_rail_h` | 5 in | Shorter back rail (headboard adds rigidity) |
| `post_chamfer` | 0.25 in | Rails align with chamfer bottom |
| `n_hb_slats` | 5 | Headboard vertical slats |

### Appearance

```
apply_appearance(species="white oak")
```
---

# Twin Bed — Live Edge Slab Headboard with Bowties

A Nakashima-inspired twin bed with a 2" thick slab headboard and 3 decorative bowtie (butterfly key) inlays spanning a horizontal crack.

![Twin Bed](screenshots/twin-live-edge-slab.png)

### Transparent View — Joinery & Bowties

![Twin Transparent](screenshots/twin-transparent.png)

---

**Script:** [`twin_live_edge_slab.py`](twin_live_edge_slab.py) — 24 structural bodies + hardware. Zero interferences.

**Style:** [Nakashima / Live Edge](../../docs/styles/nakashima.md)

### Joinery

| Connection | Type | Details |
|-----------|------|---------|
| Side rails → posts | **Bed rail fastener** (100mm) | Detachable |
| Foot rail → front posts | **Bed rail fastener** (100mm) | Detachable |
| Back rail → back posts | **Bed rail fastener** (80mm) | Smaller for shorter rail |
| Slab → back posts | Domino (8mm) | Permanent — slab notched around posts |
| Ledger strips → side rails | Domino (5mm) | Smaller for 0.75" stock |
| Bowties → slab | CUT inlay pockets | Decorative — perpendicular to grain/crack |

### Key features

- **Slab headboard** — 2" thick, spanning between posts (notched around them), stops below post chamfer
- **3 bowtie inlays** — vertical orientation (perpendicular to horizontal crack/grain), evenly spaced at slab center height
- **Back rail** — 5" tall between back posts, forward of slab, 80mm fasteners
- **Bowtie template** — `from helpers.templates import bowtie` → `bowtie.row()`

### Bowtie parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `bt_len` | 3 in | Bowtie length (perpendicular to crack) |
| `bt_end_w` | 1.5 in | Width at wide ends |
| `bt_waist_w` | 0.5 in | Width at narrow waist |
| `bt_depth` | 0.67 in | Inlay depth (~1/3 of 2" slab) |
| `n_bowties` | 3 | Number along crack line |

### Appearance

```
apply_appearance(species="white oak")
apply_appearance(species="walnut", bodies=[bowtie_names])
```
