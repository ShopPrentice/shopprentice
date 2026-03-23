# Bed Frame

Sleeping surface support — platform beds, traditional beds, four-poster beds. Holds a mattress with either a solid platform, slat system, or box spring.

## Components

| Component | Required | Role |
|-----------|----------|------|
| Posts | Yes | 4 corner posts — back pair taller for headboard, front pair shorter |
| Side rails | Yes | Long boards connecting head posts to foot posts |
| Foot rail | Yes | Short rail between front posts (acts as footboard on platform beds) |
| Headboard | Yes | Framed structure between back posts above the side rails (rails + vertical slats, or solid panel) |
| Ledger strips | Yes | Cleats on inside face of side rails — slats rest on these |
| Slats | Yes | Flat boards spanning the bed width for mattress support |
| Center support beam | Queen+ | Longitudinal beam with legs running head-to-foot under slats |

### Component relationships

```
Posts at 4 corners — back posts tall (headboard), front posts short (rail height + leg clearance)
Side rails centered on posts, raised off floor by leg_clearance
Foot rail between front posts at same height as side rails
Ledger strips on inside face of side rails, supporting slats from below
Slats rest on ledgers, span full width touching inner face of both side rails
  - Slat tops sit below rail top by mattress_recess (secures mattress)
Center support beam (Queen+) runs head-to-foot with 2 legs at 1/3 and 2/3 points
Headboard frame (top rail + bottom rail + vertical slats) between back posts above side rails
  - Headboard rails and slats centered on back post cross-section
```

## Key Proportions

- **Headboard height**: 34–40" from floor (significantly taller than side rails)
- **Front post height**: `leg_clearance + rail_h` (rails + clearance, no tall footboard)
- **Leg clearance**: 3–6" (space under rails — more = storage, less = low-profile)
- **Mattress recess**: 1–2" (how far slat tops sit below rail top — keeps mattress from sliding)
- **Rail top alignment**: rail top aligns with bottom of post chamfer (`rail_h - post_chamfer`)

## Headboard Styles

| Style | Components | Notes |
|-------|-----------|-------|
| **Vertical slats + rails** | Top rail + bottom rail + 3–7 vertical slats | Tested — see build below |
| **Solid panel** | Single panel between posts | Panel-in-groove or dominos to posts |
| **Horizontal slats** | 2–4 horizontal boards between posts | Through-mortise or dominos |
| **Upholstered** | Flat panel + fabric (not modeled in CAD) | Just the backing panel |

### Vertical slat headboard details (Tested — Queen platform bed)
- Top rail between posts at `headboard_h - hb_top_rail_h`
- Bottom rail between posts at `front_post_h` (top of side rail zone)
- Vertical slats with equal gaps: `hb_slat_gap = (end_rail_l - n_hb_slats * hb_slat_w) / (n_hb_slats + 1)`
- Slats have stub tenons (dm_d deep) inserting into both rails (CUT creates mortise)
- Rails and slats centered on post cross-section: `hb_face_y = outer_l - post_size/2 - hb_rail_thick/2`
- Rails connected to posts with dominos

## Openings & Cavities

| Opening | In which body | Created by |
|---------|---------------|------------|
| Rail domino mortises | All 4 posts | Domino CUTs |
| Headboard rail mortises | Back posts | Domino CUTs |
| HB slat mortises | HB top + bottom rails | Slat stub tenon CUTs |
| Ledger domino mortises | Side rails + ledger strips | Smaller domino CUTs (5mm for thin ledger) |

## Connections — Every Piece Must Be Mechanically Joined

| Connection | Joint type | Notes |
|-----------|-----------|-------|
| Side rail → post | **Bed rail fastener** (100mm) | Detachable — `bed_rail_fastener.install()`. STEP hardware imported, recesses CUT. Call `cleanup` in epilogue. |
| Foot rail → front posts | **Bed rail fastener** (100mm) | Same as side rails — detachable for moving |
| HB rails → back posts | Domino (1–2 per end) | Centered on post |
| HB slats → HB rails | Stub tenon (CUT) | Slat extends dm_d into each rail |
| Ledger → side rail | Domino (4 along length) | **Smaller dominos** (5mm cutter for 0.75" ledger — cutter ≤ 1/3 board thickness) |
| Slats → ledgers | Rest on ledgers (loose) | Not fastened — gravity holds them |
| Center beam legs → beam | Butted (glue or domino) | Removable for transport |

### Bed rail fastener installation
Rails connect to posts with detachable bed rail fasteners (mortise bedlocks), not permanent dominos. This allows the bed to be disassembled for moving.

```python
from helpers.templates import bed_rail_fastener as brf
from helpers import hardware as hw_mgr

# Install at each rail-to-post connection
brf.install(root, post_proxy, rail_proxy,
            interface_axis="y",           # axis where boards meet
            interface_coord=ev("post_size"),  # coordinate of the interface
            center_z=rail_center_z,       # Z center of the fastener
            size="100mm", name="BRF_RL_F", ev=ev)

# IMPORTANT: call cleanup in epilogue to hide STEP imports
# Consolidate all _Hardware/_Imports/BRF_* into one hidden _HW component
```

Three sizes: 80mm (light rails), **100mm (standard)**, 120mm (heavy/tall rails). STEP files at `~/.shopprentice/hardware/bed_rail_fastener/`. Generate with `tools/bed_rail_fastener.py` if missing.

**Hook direction rule:** Hooks always face OUTWARD from the rail they're attached to — toward the connecting post. The template auto-detects direction by comparing the rail body center vs interface coordinate. Each rail end gets the correct outward-facing hooks automatically.

**Hardware organization:** Installed hook plates go into `Rails/Hardwares/`, strike plates into `Posts/Hardwares/`. Only STEP templates go to hidden `_HW`.

### Domino orientation (permanent joints only)
Headboard rails and ledger strips use permanent dominos:
- **HB rail (grain X) → post (grain Z)**: `long_axis="z"`
- **Ledger (grain Y) → side rail (grain Y)**: `long_axis="y"` — along shared grain, domino lays flat

## Size Guide

| Size | Mattress W × L | Frame W (outer) | Frame L (outer) |
|------|---------------|----------------|----------------|
| Twin | 39 × 75 in | 45 in | 81 in |
| Full | 54 × 75 in | 60 in | 81 in |
| Queen | 60 × 80 in | 66 in | 86 in |
| King | 76 × 80 in | 82 in | 86 in |

Outer = mattress + 2 × post_size. **Center support beam**: required for Queen and larger.

## Build Order

```
1. Posts (4 corner posts — front: leg_clearance + rail_h, back: headboard_h)
2. Side rails (centered on posts, Z starts at leg_clearance, height = rail_h - post_chamfer)
3. Foot rail (between front posts, same Z as side rails)
4. Ledger strips (on inside face of side rails, Z = slat_z - ledger_h)
5. Headboard (top rail + bottom rail + vertical slats, centered on back posts)
6. Slats (spanning full width rail-to-rail, Z = rail_top - mattress_recess - slat_thick)
7. Center support beam + 2 legs (Queen+ only, at 1/3 and 2/3 of bed length)
8. Cross-component: HB slat stub-mortises into HB rails
9. Bed rail fasteners: side rails → posts, foot rail → posts (STEP import, 100mm)
10. Dominos (permanent): HB rails → posts, ledgers → rails
11. Details: post top chamfers
12. Hardware cleanup: consolidate _HW container, hide imports
13. Verify: check_interference = 0, no floating pieces
```

## Common Mistakes

- **Using permanent dominos for rail-to-post joints** — beds must be disassemblable for moving. Use bed rail fasteners (detachable), not dominos (permanent). Only headboard rails and ledger strips get dominos.
- **STEP import clutter on root** — always consolidate hardware imports into a hidden `_HW` component in the epilogue. Use `hw_mgr.import_step()` for tracked imports.
- **Rails and posts bottoms level** — most beds have space under the rails (leg_clearance). Without it, no airflow and no under-bed storage. Make leg_clearance an independent parameter.
- **Slats flush with rail top** — mattress slides off. Add mattress_recess (1–2") so slats sit below rail top, creating a pocket that holds the mattress.
- **Center beam as solid wall** — should be a beam with 2 discrete legs at 1/3 and 2/3 points, not a slab from floor to slat height.
- **Ledger dominos too large** — 0.75" ledger can't take an 8mm domino (42% of thickness). Use 5mm cutter: `ldm_t=5mm, ldm_w=30mm, ldm_d=15mm`.
- **Slats don't reach both rails** — slats must touch inner face of both side rails. `slat_l = outer_w - post_size - rail_thick`, not `bed_w`.
- **Headboard and footboard same height** — footboard should be much shorter
- **No center support beam on Queen/King** — bed will sag
- **Rail top above post chamfer** — rail top should align with chamfer bottom: `rail_top_z = leg_clearance + rail_h - post_chamfer`
- Side rails too thin (need 1.5"+ for strength)

## Parameter Suggestions

### Core

| Parameter | Range | Default | Notes |
|-----------|-------|---------|-------|
| bed_w | 39–76 in | 60 in | Mattress width (Queen) |
| bed_l | 75–80 in | 80 in | Mattress length |
| post_size | 2–4 in | 3 in | |
| rail_h | 8–12 in | 10 in | Side rail height |
| rail_thick | 1–2 in | 1.5 in | |
| leg_clearance | 0–8 in | 4 in | Space under rails (0 = platform on floor) |
| mattress_recess | 0–3 in | 1.5 in | Slat top below rail top (0 = flush) |
| headboard_h | 34–40 in | 36 in | From floor |

### Headboard

| Parameter | Range | Default |
|-----------|-------|---------|
| hb_top_rail_h | 2–4 in | 3 in |
| hb_bot_rail_h | 2–4 in | 3 in |
| hb_rail_thick | 0.75–1.5 in | 1 in |
| n_hb_slats | 3–7 | 5 |
| hb_slat_w | 2–3 in | 2.5 in |

### Slats & Support

| Parameter | Range | Default |
|-----------|-------|---------|
| n_slats | 10–20 | 13 |
| slat_w | 2.5–4 in | 3 in |
| slat_thick | 0.75 in | 0.75 in |
| ledger_h | 1–2 in | 1.5 in |
| ledger_thick | 0.75 in | 0.75 in |
| beam_w | 2–4 in | 3 in |
| beam_thick | 1–2 in | 1.5 in |

### Dominos

| Joint | Cutter | Params |
|-------|--------|--------|
| Rail/HB → post | 8mm | `dm_t=8mm, dm_w=40mm, dm_d=20mm` |
| Ledger → rail | 5mm | `ldm_t=5mm, ldm_w=30mm, ldm_d=15mm` |

### Details

| Parameter | Range | Default |
|-----------|-------|---------|
| post_chamfer | 0.125–0.5 in | 0.25 in |
