# Tenon Wedge

## Overview

A **tenon wedge** is a small tapered piece of wood driven into a slot cut in the tenon end. When inserted it spreads the tenon to create a tighter mechanical lock in the mortise. The wedge grain runs along the taper direction; the slot is oriented perpendicular to the mortise piece's grain to prevent splitting.

**When to use:**
1. **Through tenon tightening** — wedge driven from the exposed end after assembly (most common)
2. **Fox wedging (blind tenons)** — wedge pre-loaded in the slot; the mortise bottom drives it home during assembly
3. **Round tenon locking** — Windsor chair spindles/stretchers through seats or legs

**Strength:** The wedge spreads the tenon against the mortise walls, creating a mechanical interlock independent of glue. Especially valuable for through tenons in workbenches, timber frames, and Windsor chairs where joints must resist racking loads.

## Variants

| Variant | Description |
|---------|-------------|
| Through rect | 2 wedges at 1/4 from each end of the tenon cross-section |
| Through round | 1 centred wedge, trimmed flush to the cylindrical tenon surface |
| Fox wedge (blind) | Same geometry as through, but tenon is blind — wedge sits inside the mortise |

## Parameters

| Parameter | Role | Default |
|-----------|------|---------|
| `tw_sw` | Slot width at the tenon surface | `0.1 in` |
| `tw_dr` | Wedge depth as a fraction of tenon depth | `2 / 3` |
| `tw_or` | Offset ratio — wedge position from each end (rect only) | `1 / 4` |
| `tw_theta` | Undercut / flare angle in degrees — the trapezoid's side slope (`rect(flare=True)`) | `6` |

## Mechanical Lock (flare) — `rect(flare=True)`

By default `rect()` cuts wedge slots into a **straight** tenon and the wedge bodies are
effectively decorative — the mortise is not undercut and the tenon halves are not
spread, so the mechanical lock is not represented. Pass **`flare=True`** to model the
real lock:

```python
# THROUGH-wedged: build the tenon proud, flare it, then CUT the mortise with the
# SOLID flared envelope = tenon + the 2 wedge bodies (which fill the kerfs), and JOIN.
res = tw.rect(comp, tenon_body=tenon, mortise_body=leg, tenon_axis="x",
              tenon_depth_expr="leg_w + mt_proud", slot_span_expr="mt_tt",
              offset_dim_expr="mt_tw", name="TW", ev=ev,
              flare=True, species="white_oak")     # res[0], res[1] = the 2 wedge bodies
sp.combine(leg, [tenon, res[0], res[1]], CUT, True, "Mortise")  # matching trapezoid void
sp.combine(rail, tenon, JOIN, False, "Join")

# FOX-wedged (blind): same call on a blind tenon, fox=True
res = tw.rect(comp, tenon_body=tenon, mortise_body=leg, tenon_axis="y",
              tenon_depth_expr="mt_td", slot_span_expr="mt_tt",
              offset_dim_expr="mt_tw", name="TW", ev=ev, flare=True, fox=True)
sp.combine(leg, [tenon, res[0], res[1]], CUT, True, "Mortise")
sp.combine(rail, tenon, JOIN, False, "Join")
```

**What it builds.** After the two wedges, a tapered **flare ear** is JOINed to each outer
(`off_dir`) tenon face — zero at the **kerf root** (`tenon_depth * tw_dr` inside the end
face) and growing, at the `tw_theta` undercut angle, to its full spread at the end. So
each ear's spread is `tenon_depth * tw_dr * tan(tw_theta)`, and the tenon's outer profile
becomes a **TRAPEZOID** — narrow at the shoulder/mouth, wide at the end — over the whole
wedged region. **Cut the mortise with the solid flared envelope** = the tenon **plus the
two wedge bodies** (which fill the kerfs); that void is then the **matching trapezoid**,
wider at the exit (or, for fox, the blind bottom) than at the mouth, so the wide end can't
pull back through the narrow mouth — the joint is **mechanically locked**. Because the
tenon-∪-wedges solid is the cut tool, there is **zero interference** (the solid is the
exact complement of the void) and the kerf stays ⟂ the mortise grain (the spread doesn't
cleave the long-grain cheeks). Same "let the cut transfer the shape" pattern as the
angled-corner dovetail. (Cut with the *slotted* tenon alone and the leg keeps protrusions
in the kerfs; cut with the *whole rail* and the shoulder overlaps the leg — both leave
interference, so cut with the tenon-∪-wedges envelope.)

**Through vs fox.** `fox=False` (default) = through-wedged (driven from the exposed
proud end after assembly). `fox=True` = blind fox-wedge (the mortise bottom drives the
wedges as the tenon seats); leave a mortise-bottom wall and note it cannot be
re-tightened.

**Strength gate.** With `flare=True`, `rect()` automatically runs
`sp.validate_wedged_tenon(...)` on the tenon before it is consumed — the
mechanical-interlock counterpart of `validate_joint_strength`. It reports the
glue-independent interlock withdrawal and **flags the brittle mortise-split mode**. The
geometry's undercut angle `tw_theta` (and the derived spread `depth * tw_dr * tan(tw_theta)`)
map directly to the strength model's `undercut_deg` / `flare_delta`
(`joint_strength.estimate_wedged_tenon`). See
`docs/joinery/grain-and-strength.md` for the interlock mechanics. Round tenons
(`round_tenon`) keep the straight-spread model for now; the flare lock is on `rect`.

## Orientation Rule

The slot is always **perpendicular to the mortise piece's grain**. This prevents the wedge from splitting the mortise along its fibers.

### Grain Detection

The template auto-detects mortise grain using **principal axes of inertia** (`body.physicalProperties.getPrincipalAxes()`). The axis with the **smallest moment of inertia** is the elongation axis (grain direction). This works for any orientation — axis-aligned, splayed legs, compound-angle stretchers.

Falls back to bounding-box longest axis if the API call fails.

### grain_dir Override

When the mortise piece has **ambiguous proportions** (near-equal dimensions in multiple axes), the auto-detection may pick the wrong axis. Pass `grain_dir=(x, y, z)` to override:

```python
# Seat is 18" wide × 15" deep — nearly square, grain runs front-to-back
tw.round_tenon(comp, tenon_body=leg, mortise_body=seat,
               end_face=end, grain_dir=(0, 1, 0),  # Y = front-to-back
               tenon_depth_expr="seat_t", tenon_diam_expr="leg_tenon_dia",
               name="TW_FL", ev=ev)
```

**Always pass `grain_dir`** when the mortise piece is a wide panel (seat, tabletop, slab) where width ≈ depth. For elongated pieces (legs, rails, stretchers), auto-detection is reliable.

For a vertical leg (grain Z) with a horizontal rail tenon: the slot runs in the cross-grain direction of the leg.

## Geometry Workflow

1. **Detect orientation** — mortise grain (longest bbox axis) determines slot direction
2. **Find end face** — `find_face(body, tenon_axis, tenon_dir)` locates the tenon tip (works on standalone or JOINed tenon bodies)
3. **Triangle profile** — sketched on a plane perpendicular to the slot axis: base = `tw_sw` at end face, apex at `depth * tw_dr` inside
4. **Symmetric extrude** — spans the full tenon width in the slot direction
5. **CUT tenon** with the wedge body (`keepTool=True`) — creates the slot
6. **Round tenons only** — intersect the wedge with the tenon body to trim flush to the cylinder

## Template API

```python
from woodworking.templates import tenon_wedge as tw

tw.define_params(params)

# Rectangular tenon — 2 wedges
tw.rect(comp, tenon_body=tenon, mortise_body=leg,
        tenon_axis="x", tenon_depth_expr="mt_td",
        slot_span_expr="mt_tt", offset_dim_expr="mt_tw",
        name="TW_FL", ev=ev)

# Round tenon — 1 centred wedge (auto grain detection)
tw.round_tenon(comp, tenon_body=stretcher, mortise_body=leg,
               end_face=str_end, tenon_depth_expr="leg_dia",
               tenon_diam_expr="str_end_dia",
               name="TW_SL", ev=ev)

# Round tenon — explicit grain_dir for ambiguous mortise (seat)
tw.round_tenon(comp, tenon_body=leg, mortise_body=seat,
               end_face=leg_end, tenon_depth_expr="seat_t",
               tenon_diam_expr="leg_tenon_dia",
               grain_dir=(0, 1, 0),  # seat grain front-to-back
               name="TW_FL", ev=ev)
```

**Important:** `slot_span_expr` is the tenon extent in the **slot direction** (perpendicular to mortise grain). `offset_dim_expr` is the extent in the **offset direction** (parallel to mortise grain, where the 2 wedges are spaced). For a typical M&T: slot spans `mt_tt` (thin), wedges offset along `mt_tw` (wide).

## Usage Notes

- Works on both **standalone tenon bodies** (before JOIN) and **JOINed tenons** — the end face is found via `find_face` since the tenon tip protrudes furthest on any body.
- For rect tenons on JOINed bodies, the construction plane references the tenon's planar face (parametric). For round tenons, falls back to a computed offset.
- The wedge body remains separate (not JOINed) — it's a different piece of wood with cross-grain orientation.
- Apply a contrasting appearance to wedges for visibility (e.g., walnut wedges in white oak tenons).

## Verification

After building wedges, verify orientation with a **transparent view** so internal wedge bodies and slots are visible through the mortise piece:

```python
# Transparent view to verify wedge slot orientation
get_product_shots(views=["iso-top-right"], style="transparent")
```

**Check two things:**
1. **Taper axis** — wedge tip points INTO the tenon (away from the end face). Visually: the dark wedge body narrows as it goes deeper.
2. **Slot axis** — the slot line on the end face runs PERPENDICULAR to the mortise grain. Visually: for a vertical leg, the slot should be horizontal; for a horizontal rail, the slot should be vertical.

If the slot appears parallel to grain, the grain detection is wrong — pass `grain_dir=` explicitly.

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Wedge too wide, extends beyond tenon | `slot_span_expr` and `offset_dim_expr` swapped | Slot spans the thin direction (`mt_tt`), offset along the wide direction (`mt_tw`) |
| Wedge tapers wrong direction | `_detect_tenon_dir` returns wrong sign | Pass `tenon_dir` explicitly (+1 or -1) |
| Wedge protrudes beyond round tenon | No trim step | Use `round_tenon()` which intersects with the tenon body |
| `setByOffset` error on round tenon | Cylindrical face used as construction plane base | Template auto-falls back to component plane for non-planar faces |
| Slot parallel to grain instead of perpendicular | Ambiguous grain detection on near-square mortise (seat, slab) | Pass `grain_dir=(x, y, z)` explicitly |
| Grain texture rotated on turned bodies after wedge CUT | Wedge slot edges confuse `_grain_vector` in `apply_appearance` | Override grain in appearance section for turned bodies (legs, stretchers) |
