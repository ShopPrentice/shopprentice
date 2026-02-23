# Parametric Solid Wood Bookshelf

## Overview

A parametric solid wood bookshelf modeled in Fusion 360 via Python script. 70"H x 30"W x 20"D, 3/4" board stock with through mortise-and-tenon shelf joints and through dovetail top joints.

**File:** `bookshelf.py`
**Run:** Fusion 360 > Utilities > Scripts and Add-Ins > (+) > select folder > Run

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
| `kick_inset` | 1 in | Kick board inset from front |
| `n_shelves` | 5 | Number of interior shelves |
| `mt_tenon_w` | 2 in | Mortise & tenon width |
| `dt_angle` | 8 deg | Dovetail angle |
| `dt_tail_w` | 2 in | Dovetail tail width |
| `dt_tail_count` | 8 | Number of dovetail tails |

---

## Architecture

Features live inside their respective components. Cross-component CUT operations live in root via assembly proxies. No Python `for` loops — all replication uses Mirror and Rectangular Pattern features.

### Components and Features

| Component | Features |
|-----------|----------|
| **Sides** | 2 extrudes (left + right side boards) |
| **Shelves** | shelf extrude, tenon extrude, 2 mirrors, JOIN, body pattern (n_shelves along Z) |
| **Top** | top extrude, left tail extrude, mirror across XMid, 2 body patterns (left+right tails along Y), 2 JOINs |
| **Kick** | kick extrude, tenon extrude, 2 mirrors, JOIN |
| **Root** | 6 CUT features via assembly proxies (2 shelf mortise, 2 kick mortise, 2 dovetail socket) |

### Modeling Sequence

1. **Side boards** (Sides) — extrude left and right
2. **Shelf template** (Shelves) — extrude shelf + 1 tenon, mirror tenon across YMid and XMid, JOIN 4 tenons into shelf, body pattern along Z
3. **Shelf mortises** (root) — bulk CUT left side and right side with all shelf proxies
4. **Kick board** (Kick) — extrude kick + 1 tenon, mirror across KZMid and XMid, JOIN 4 tenons into kick
5. **Kick mortises** (root) — CUT left side and right side with kick proxy
6. **Top + dovetails** (Top) — extrude top + 1 left tail, mirror across XMid for right tail, body pattern left tails along Y, body pattern right tails along Y
7. **Dovetail sockets** (root) — bulk CUT left side with left tail proxies, right side with right tail proxies
8. **Join dovetails** (Top) — JOIN all left tails into top, JOIN all right tails into top
9. **Fit view**

### Key Techniques

- **Body pattern replaces `for` loop**: one shelf template + pattern creates all 5 shelves as a single parametric feature
- **Tenon-as-tool joinery**: tenon bodies CUT mortises into side boards (keepTool=True), ensuring perfect fit
- **Assembly proxies**: `body.createForAssemblyContext(occurrence)` enables cross-component CUT in root
- **Bulk CUT**: all shelf proxies passed as tools in a single Combine, not one CUT per shelf
- **Mirror before pattern**: for dovetails, mirror the template tail across XMid first, then create independent body patterns per side (Fusion 360 cannot mirror a pattern)

---

## Customization

Change any parameter in Fusion 360's Change Parameters dialog. Key relationships:

- `shelf_spacing` = `(total_height - 2 * board_thick - kick_height) / n_shelves`
- `inner_width` = `total_width - 2 * board_thick`
- `dt_pin_w` = `total_depth / dt_tail_count - dt_tail_w` (derived from tail count)
- `dt_pitch` = `total_depth / dt_tail_count`

Changing `n_shelves` updates the shelf body pattern count AND the bulk CUT operations automatically.

---

## Materials & Cut List

For the default 70"H x 30"W x 20"D bookshelf in 3/4" stock:

| Part | Qty | Dimensions (W x D x H) |
|------|-----|------------------------|
| Side boards | 2 | 3/4" x 20" x 70" |
| Top board | 1 | 28.5" x 20" x 3/4" |
| Shelves | 5 | 28.5" x 20" x 3/4" |
| Kick board | 1 | 28.5" x 3/4" x 4" |
