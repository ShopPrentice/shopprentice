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

## Orientation Rule

The slot is always **perpendicular to the mortise piece's grain**. This prevents the wedge from splitting the mortise along its fibers. The template auto-detects mortise grain from the bounding box longest axis.

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

# Round tenon — 1 centred wedge
tw.round_tenon(comp, tenon_body=spindle_tenon, mortise_body=seat,
               tenon_axis="z", tenon_depth_expr="sp_td",
               tenon_diam_expr="sp_dia",
               name="TW_S1", ev=ev)
```

**Important:** `slot_span_expr` is the tenon extent in the **slot direction** (perpendicular to mortise grain). `offset_dim_expr` is the extent in the **offset direction** (parallel to mortise grain, where the 2 wedges are spaced). For a typical M&T: slot spans `mt_tt` (thin), wedges offset along `mt_tw` (wide).

## Usage Notes

- Works on both **standalone tenon bodies** (before JOIN) and **JOINed tenons** — the end face is found via `find_face` since the tenon tip protrudes furthest on any body.
- For rect tenons on JOINed bodies, the construction plane references the tenon's planar face (parametric). For round tenons, falls back to a computed offset.
- The wedge body remains separate (not JOINed) — it's a different piece of wood with cross-grain orientation.
- Apply a contrasting appearance to wedges for visibility (e.g., walnut wedges in white oak tenons).

## Common Pitfalls

| Error | Cause | Fix |
|-------|-------|-----|
| Wedge too wide, extends beyond tenon | `slot_span_expr` and `offset_dim_expr` swapped | Slot spans the thin direction (`mt_tt`), offset along the wide direction (`mt_tw`) |
| Wedge tapers wrong direction | `_detect_tenon_dir` returns wrong sign | Pass `tenon_dir` explicitly (+1 or -1) |
| Wedge protrudes beyond round tenon | No trim step | Use `round_tenon()` which intersects with the tenon body |
| `setByOffset` error on round tenon | Cylindrical face used as construction plane base | Template auto-falls back to component plane for non-planar faces |
| Diagonal grain on square mortise board | Ambiguous grain detection (equal bbox dimensions) | Make the mortise board clearly rectangular so longest axis is unambiguous |
