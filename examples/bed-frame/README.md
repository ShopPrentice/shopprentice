# Queen Platform Bed Frame

A parametric modern platform bed — Queen 60"W x 80"L, framed headboard with vertical slats, center support beam with legs, full domino joinery.

![Queen Platform Bed](screenshots/queen-platform.png)

---

**Script:** [`queen_platform.py`](queen_platform.py) — 32 bodies (4 posts, 5 rails/ledgers, 7 headboard parts, 13 slats, 3 support). All domino-connected. Zero interferences.

### Key parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `bed_w` / `bed_l` | 60 / 80 in | Change for Twin (39×75) or King (76×80) |
| `leg_clearance` | 4 in | Space under rails (0 = platform on floor) |
| `mattress_recess` | 1.5 in | Slat top below rail top (secures mattress) |
| `post_chamfer` | 0.25 in | Rails align with chamfer bottom |
| `n_hb_slats` | 5 | Headboard vertical slats |

### Joinery
- Rail/HB → posts: 8mm dominos (2 per end)
- Ledger → rail: 5mm dominos (4 along length, sized for 0.75" stock)
- HB slats → rails: stub tenon (CUT)
- Center beam with 2 legs at 1/3 and 2/3 points

---

# Twin Bed — Live Edge Slab Headboard with Bowties

A Nakashima-inspired twin bed with a 2" thick slab headboard and 3 decorative bowtie (butterfly key) inlays spanning a horizontal crack.

![Twin Bed — live edge slab headboard](screenshots/twin-live-edge-slab.png)

---

**Script:** [`twin_live_edge_slab.py`](twin_live_edge_slab.py) — 24 bodies (4 posts, 5 rails/ledgers, 4 headboard/bowties, 10 slats). Zero interferences.

**Style:** [Nakashima / Live Edge](../../woodworking/styles/nakashima.md)

### Key features
- **Slab headboard** — 2" thick, spanning between posts (notched around them), stops below post chamfer
- **3 bowtie inlays** — vertical orientation (perpendicular to horizontal crack/grain), evenly spaced at slab center height. Depth = 1/3 of slab thickness.
- **Bowtie template** — `from helpers.templates import bowtie` → `bowtie.row()` for reusable inlay placement
- **All joints connected** — dominos at every rail/slab-to-post connection, smaller 5mm dominos for thin ledger strips
- No center support beam (not needed for Twin size)

### Bowtie parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `bt_len` | 3 in | Bowtie length (perpendicular to crack) |
| `bt_end_w` | 1.5 in | Width at the wide ends |
| `bt_waist_w` | 0.5 in | Width at the narrow waist |
| `bt_depth` | 0.67 in | Inlay depth (~1/3 of 2" slab) |
| `n_bowties` | 3 | Number along crack line |
