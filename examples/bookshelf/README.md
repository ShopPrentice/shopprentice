# Parametric Solid Wood Bookshelf

A parametric solid wood bookshelf modeled in Fusion 360 via Python script. 70"H x 30"W x 20"D, 3/4" board stock with through mortise-and-tenon shelf joints, hidden Festool Domino kick joints, 1/2" plywood backboard with domino connections, and through dovetail top joints.

![Bookshelf — iso top-right](screenshots/iso-top-right.png)

![Bookshelf — iso top-left](screenshots/iso-top-left.png)

<p float="left">
  <img src="screenshots/front.png" width="49%" />
  <img src="screenshots/right.png" width="49%" />
</p>

## Example Prompt

```
/woodworking
Build a 70" tall x 30" wide x 20" deep solid wood bookshelf in 3/4" stock. Use through
mortise-and-tenon joints for 5 adjustable shelves, hidden Festool Domino joints for the
kick board, domino connections for a 1/2" plywood backboard, and through dovetails to
attach the top. All joinery should be fully parametric.
```

### Appearance

```
apply_appearance(species="white oak")
```

---

## How to Run

**Via MCP (recommended):** If you have the [Fusion 360 MCP add-in](../../mcp/README.md) configured, just ask Claude to run it.

**Manual:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select this folder > Run

**Script:** [`bookshelf.py`](bookshelf.py)

---

## Dimensions

All exposed as User Parameters (Modify > Change Parameters):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `total_height` | 70 in | Overall height |
| `total_width` | 30 in | Overall width |
| `total_depth` | 20 in | Overall depth |
| `board_thick` | 0.75 in | Board stock thickness |
| `kick_height` | 4 in | Height of kick board |
| `back_thick` | 0.5 in | Backboard panel thickness |
| `n_shelves` | 5 | Number of interior shelves |
| `mt_tenon_w` | 2 in | Mortise & tenon width |
| `dm_kick_w` | 5 mm | Kick domino width (fits in board_thick) |
| `dm_kick_h` | 30 mm | Kick domino height (fits in kick_height) |
| `dm_kick_d` | 15 mm | Kick domino depth per side (fits in board_thick) |
| `dm_back_w` | 6 mm | Shelf-back domino width (fits in board_thick) |
| `dm_back_h` | 40 mm | Shelf-back domino height (fits along inner_width) |
| `dm_back_d` | 10 mm | Shelf-back domino depth per side (fits in back_thick) |
| `dm_kick_count` | 2 | Dominos per kick-to-side joint |
| `dm_back_count` | 3 | Dominos per shelf-to-backboard joint |
| `dt_angle` | 8 deg | Dovetail angle |
| `dt_tail_w` | 2 in | Dovetail tail width |
| `dt_tail_count` | 8 | Number of dovetail tails |

---

## Design

Features live inside their respective components. Cross-component CUT operations live in root via assembly proxies. No Python `for` loops — all replication uses Mirror and Rectangular Pattern features.

### Components and Features

| Component | Features |
|-----------|----------|
| **Sides** | 2 extrudes (left + right side boards) |
| **Shelves** | shelf extrude, tenon extrude, 2 mirrors, JOIN tenons, domino void extrude, pattern X, JOIN voids, CUT voids from shelf, body pattern shelf along Z, body pattern voids along Z |
| **Top** | top extrude, left tail extrude, mirror across XMid, 2 body patterns (left+right tails along Y), 2 JOINs |
| **Kick** | kick extrude (flush front), domino void extrude, pattern Z, JOIN left voids, mirror across XMid, JOIN right voids, CUT voids from kick |
| **Back** | backboard panel extrude |
| **Root** | 8 CUT features via assembly proxies (2 shelf mortise, 2 kick domino, 1 backboard domino, 2 dovetail socket) |

### Modeling Sequence

1. **Side boards** (Sides) — extrude left and right
2. **Shelf template** (Shelves) — extrude shelf + 1 tenon, mirror tenon across YMid and XMid, JOIN 4 tenons, domino voids for backboard, CUT voids from shelf, body pattern shelf along Z, body pattern voids along Z
3. **Shelf mortises** (root) — bulk CUT left side and right side with all shelf proxies
4. **Kick board** (Kick) — extrude kick (flush front), domino void extrude + pattern Z, JOIN left voids, mirror across XMid, JOIN right voids, CUT all voids from kick
5. **Kick domino cuts** (root) — CUT left side and right side with kick domino void proxies
6. **Backboard** (Back) — extrude 1/2" panel flush with back surface
7. **Backboard domino cuts** (root) — CUT backboard with shelf domino void proxies
8. **Top + dovetails** (Top) — extrude top + 1 left tail, mirror across XMid for right tail, body pattern left tails along Y, body pattern right tails along Y
9. **Dovetail sockets** (root) — bulk CUT left side with left tail proxies, right side with right tail proxies
10. **Join dovetails** (Top) — JOIN all left tails into top, JOIN all right tails into top

### Key Techniques

- **Body pattern replaces `for` loop** — one shelf template + pattern creates all 5 shelves as a single parametric feature
- **Tenon-as-tool joinery** — tenon bodies CUT mortises into side boards (keepTool=True), ensuring perfect fit
- **Domino void bodies** — rectangular void spans the interface between two pieces, CUT from both for perfectly aligned mortise pockets
- **Assembly proxies** — `body.createForAssemblyContext(occurrence)` enables cross-component CUT in root
- **Bulk CUT** — all shelf proxies passed as tools in a single Combine, not one CUT per shelf
- **Mirror before pattern** — for dovetails, mirror the template tail across XMid first, then create independent body patterns per side (Fusion 360 cannot mirror a pattern)

---

## Customization

Change any parameter in Fusion 360's Change Parameters dialog. Key relationships:

- `shelf_depth` = `total_depth - back_thick` — shelves recessed for backboard
- `back_height` = `total_height - board_thick - kick_height`
- `shelf_spacing` = `(total_height - 2 * board_thick - kick_height) / n_shelves`
- `inner_width` = `total_width - 2 * board_thick`
- `mt_tenon_y1` = `(total_depth - back_thick) / 4 - mt_tenon_w / 2`
- `dm_kick_zsp` = `kick_height / (dm_kick_count + 1)` — Z spacing for kick dominos
- `dm_back_xsp` = `inner_width / (dm_back_count + 1)` — X spacing for shelf-back dominos
- `dt_pin_w` = `total_depth / dt_tail_count - dt_tail_w` — derived from tail count
- `dt_pitch` = `total_depth / dt_tail_count`

Changing `n_shelves` updates the shelf body pattern count, domino void pattern count, backboard domino CUT, and bulk shelf mortise CUT operations automatically.

---

## Materials & Cut List

For the default 70"H x 30"W x 20"D bookshelf in 3/4" stock:

| Part | Qty | Dimensions (W x D x H) |
|------|-----|------------------------|
| Side boards | 2 | 3/4" x 20" x 70" |
| Top board | 1 | 28.5" x 20" x 3/4" |
| Shelves | 5 | 28.5" x 19.5" x 3/4" |
| Kick board | 1 | 28.5" x 3/4" x 4" |
| Backboard | 1 | 28.5" x 1/2" x 65.25" |
