# Splayed (Compound-Angle) Dovetail

## Overview

Through dovetails for boxes whose sides **lean outward** — rice measures
(米斗), splayed trays, knife boxes, wash-tub style carriers. Every corner
interface is tilted, so nothing about the joint is square:

- The **tail baselines follow the slanted shoulder line**, so each tail's
  two flanks have different lengths (laid out along the joint line, the
  way a maker marks a splayed board end).
- The **pins run horizontally, parallel to the pin board's grain** — the
  tail block is *swept* along the pin board's fiber direction, not
  extruded along the tail board's face normal.
- Tails and pins land **flush with the mating outer faces by
  construction** — no overlong-and-trim step survives in the model (and
  none is needed; see Geometry Workflow).

**When to use:** any four-cornered case with equal outward splay that
wants visible corner joinery. For square (untilted) boxes use the plain
`dovetail` template instead.

**Status:** Tested (examples/midou-box — full build plus live recompute
at three different geometries). **v1 scope: SQUARE frustum**, equal splay
on all sides, centered on the origin, sitting on Z=0. Rectangular plans
and unequal splays are future work.

## Template

```python
from woodworking.templates import splayed_dovetail as sdt

cfg = sdt.define_params(
    design.userParameters, prefix="sdt",
    top_w_expr="top_w", bot_w_expr="bot_w",
    height_expr="box_h", thick_expr="board_t",
    angle="10 deg", tail_w="1.9 cm", tail_count="6", pad="0.6 cm")

frame  = sdt.frame(case, cfg, ev=ctx.ev)     # base sketch + face planes
bodies = sdt.boards(case, cfg, frame, ev=ctx.ev)   # 4 swept boards
feats  = sdt.corners(case, cfg, frame,
                     bodies["Front"], bodies["Back"],
                     bodies["Left"], bodies["Right"], ev=ctx.ev)
```

The three layers are separable: call `frame()` + `corners()` with your
own boards **only if** they are the same exact-sweep construction —
the joint's flush fits depend on the board end faces lying exactly on
the shoulder/corner planes.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `{p}_angle` | 10 deg | Dovetail flank angle (7–14°) |
| `{p}_tail_w` | 1.9 cm | Tail base width **along the slanted joint line** |
| `{p}_tail_count` | 6 | Tails per corner (script re-run after changing) |
| `{p}_pad` | 0.6 cm | Edge padding beyond the half-pin at both joint ends |
| `{p}_tilt` | derived | `atan((top_w − bot_w) / 2 / height)` (or pass `tilt_expr`) |
| `{p}_joint_len` | derived | 3D length of the slanted corner joint line |
| `{p}_pitch` / `{p}_pin_w` | derived | `(joint_len − 2·pad)/count`, `pitch − tail_w` |
| `{p}_shoulder_ang` | derived | In-face angle between joint line and grain |

All layout values are measured **along the 3D joint line**, not
vertically — `joint_len = sqrt(2·((top_w−bot_w)/2)² + height²)`.

## Geometry Workflow (why it recomputes)

The key fact: **the horizontal X/Y directions lie inside every mating
plane** of the splayed box — the shoulder planes (pin-board inner
faces), the board face planes, and the box-corner planes. Hence:

1. **Boards are exact oblique sweeps.** Each board's outer-face outline
   (drawn on an angled construction plane, anchored to a projected base
   sketch line) is swept along a horizontal path by `thick/cos(tilt)`.
   End faces land flush on the mating planes by construction — zero
   SplitBody trims. Tail boards (outline between the shoulder lines) and
   pin boards (full outer width, end edges on the box corner lines) are
   **different shapes**; a circular pattern of one board is wrong.
2. **One fan trapezoid makes every tail.** Base corners coincident on a
   slanted *shoulder reference line*, tip corners on the *box-corner
   reference line*, flanks by angular dims (`shoulder_ang ± angle`).
   Swept along the pin board's grain it is flush with both wall planes.
3. **Body pattern along the shoulder line.** Translation along the
   interface line maps every mating plane onto itself, so each copy
   lands correctly. Mirrors replicate to the other three corners.
4. **Tails CUT the pin boards (keepTool), then JOIN their tail boards.**
   Pins emerge automatically between the sockets, grain-parallel.

## Common Pitfalls

| Error | Cause | Fix (already in the template) |
|-------|-------|------|
| Boards vanish on parameter change | SplitBody + remove fragments classified at script time — does not survive recompute | Exact oblique sweeps, no trims |
| Geometry rotates ~9 cm on dim assign | Angular dims measure the **supplement** when a projected reference line comes back direction-reversed | Read the as-drawn value, assign `expr` or `180° − expr` (`_set_ang`) |
| Ghost bodies (count ≠ 4 after joins) | Pattern-template fan sketch projected a body edge that later gets CUT → pattern recomputes mid-timeline and replays | Fan anchors only to projected **base-sketch** lines + drawn construction references |
| Wrong tool lists for CUT/JOIN | `feature.bodies` on pattern/mirror features **includes the input bodies** | Dedupe by `entityToken` (`_uniq`/`_minus`) |
| Tails poke above the rim | Tail extruded along the tilted face normal (+Z component) | Sweep along the horizontal pin-board grain instead |
| `{p}_tail_count` change breaks corners | Mirror features capture a fixed body set | Documented: re-run the script after count changes |

## See Also

- `examples/midou-box/` — full build (boards + joint + rabbeted bottom
  panel), product shots, and the prompt history.
- `docs/joinery/dovetail.md` — square-corner through dovetails and the
  proportion guidance (`angle`, `tail_count`, tail:pin ratio) that
  applies here unchanged.
- `docs/angled-construction.md` — splay math and Move-feature caveats
  for other angled work.
