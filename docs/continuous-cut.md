# Continuous Cut Across Assembled Members (Saw-After-Glue-Up)

One sculpted curve must flow across a joint and stay continuous over the seam — an
arched apron sweeping into its legs, a flared foot whose curve wraps both show
faces. Build the members rectilinear, assemble them, then shape them all with a
SINGLE cut. The one feature shapes every member it crosses, so continuity across
each part boundary is exact by construction.

## When to Read

A continuous curve has to cross **≥2 separate bodies** meeting at a joint (arched/
cyma aprons into legs, ogee/flared feet, a scalloped rail running into its posts).
The discriminator is *separate participant bodies*, not how curvy the shape looks:
a curve that lives entirely within ONE body — even a glued-up panel modeled as one
body — is a normal per-part profile (`docs/organic-shapes.md`), not this pattern.

## Why hand-fitting fails

The naive approach gives each part its own curved edge and hopes the curves line up
where the parts meet. They don't — not exactly. Any mismatch in endpoint position,
tangent, or curvature shows as a kink or step at the joint line. The fix is the
cabinetmaker's: glue up the rectangular blanks first, THEN saw the curve across the
assembly in one pass. We do the digital equivalent: one cut tool, many target
bodies.

## The recipe

1. **Build every spanned member as a plain rectilinear blank.** Where the curve will
   eventually run, the blank keeps a STRAIGHT edge. Do not pre-curve the parts.
   (Bookcase: aprons are plain rectangles; the foot's inner edge stays straight —
   "the unified base-arch cut carves it together with the apron underside.")

2. **Position/assemble the blanks** in final place. Mirror/pattern the rectilinear
   bodies to the other corners/elevations BEFORE the cut.

3. **One sketch, one fitted spline** spanning the whole run, on a construction plane
   OFFSET outboard of the members so the profile sits in front of all of them and
   extrudes through. The spline's control points trace the full curve
   (leg-cyma → apron-arch → leg-cyma). *Units differ by generator: `base_arch_cut`
   half-points are authored in INCHES (converted ×2.54 internally); `foot_flare_cut`
   points are already in CENTIMETRES — see Pitfalls.*

4. **Close the open spline into a cut profile with a plain waste frame** — the
   throwaway side of the kerf. (base_arch_cut: a 3-line waste rail below the floor;
   foot_flare_cut: a 4-line frame — vertical plumb band + 3 clearance lines.)

5. **CUT with `participantBodies` = ALL spanned members.** The single Extrude-CUT
   lists every body the curve touches. Extrude well past the run so it clears each
   member's thickness. **The generators stop at the profile — the caller runs the
   `ext_op` CUT and owns the post-cut body-count guard (step in Pitfalls).**

```python
# One arch cut shaping the front/back aprons AND all four front feet at once.
# base_arch_cut returns (sketch, profile); the CALLER does the CUT across all targets.
sk, prof = sp.base_arch_cut(base_c, plane, "x", "case_w", FB_HALF,
                            "foot_bw - foot_kick",          # end_inset_expr
                            ev("0 in - 2 in"),              # off_axis_cm
                            "BaseArch_FB", ev=ev)
sp.ext_op(base_c, prof, "case_d + 4 in", CUT,
          [apron_f, apron_b, foot_fl_f, foot_fr_f, foot_bl_f, foot_br_f], "BaseArch_FB")
```

This is the **dual of rule 6** ("if it fits, it cuts"): rule 6 is one body cutting
one other to fit a void; this is one cut crossing MANY assembled bodies to share a
continuous edge.

## Use the certified generators first

Two generators in `helpers/sp/generators.py` already encode this topology, are
DOF-guarded, and are certified fully-constrained against Fusion's solver — reach for
them instead of re-deriving the constraint recipe:

| Generator | Shape | Branches |
|---|---|---|
| `sp.base_arch_cut` | symmetric arch, mirrored about the span centre, closed by a 3-line waste rail (leg→apron→leg) | `center-shared` (crest on the centreline) / `center-pair` (crest straddles it) |
| `sp.foot_flare_cut` | single asymmetric face-flare (floor → plumb top), closed by a 4-line waste frame | `default` |

Both return `(sketch, profile)`; the caller does the `ext_op` CUT with the spanned
members as targets. A sketch they produce is stamped, so `validate_design`'s
dependency check trusts it without the ~seconds-each solver pass.

**Component placement (important):** the spline endpoints anchor to the *sketch
origin*, so run these in a component whose local origin coincides with the **world
origin** — the root component, OR a sub-component created at the **identity
transform** (like the bookcase's `Base = sp.make_comp(root, "Base")`), with the
floor at model z=0. Do NOT call them in a component placed with a non-identity
transform: the origin-anchored endpoints would land in the wrong world location and
the cut mis-places silently. (The generators' own docstrings say "root/origin
component" as shorthand for exactly this — the deps origin-dim exemption applies to
the component holding the origin root body, which must be world-origin-coincident.)

If you need a genuinely different frame (a different line count or anchoring), that's
a NEW generator with its own certification — keep the constraint topology fixed and
let only the data/dimensions vary.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `VCS_SKETCH_OVER_CONSTRAINTS` dimensioning the spline ends (base_arch_cut-style 3-line rail) | closing the waste frame BEFORE the endpoint dims — the closed loop already fixes the symmetric endpoints, so the dims are redundant | **For base_arch_cut:** dimension the spline ENDPOINTS first (spline only), THEN the rail lines + H/V, THEN the depth dim. (`foot_flare_cut` deliberately does the OPPOSITE — frame then all 6 dims — because its endpoints carry *independent* floor/show-face anchors, not a redundant loop. Follow each generator's own order; don't port one onto the other.) |
| Whole curve silently scales ~2.54×, "collapsed shape" | mismatching the per-generator unit contract | `base_arch_cut` caller passes half-points in **INCHES** (the generator converts ×2.54); `foot_flare_cut` caller passes points in **CENTIMETRES**. Pass the units each expects — don't pre-convert base_arch_cut inputs, don't forget for a hand-rolled variant. |
| The cut splits a member into 2 bodies instead of shaping it | the waste frame's outer boundary fell inside the blank's (often oversized) corner end | The generator bakes an outboard margin (`foot_flare_cut`'s `waste_expr` default `(kick)+1.2 in`; the arch rail clears below the floor). The **post-cut body-count check is the caller's job**: after `ext_op`, assert the component still has the expected body count and raise "widen the waste margin" if not. |
| Wrong/sliver profile extruded; cut removes almost nothing | a projected/reference edge split the sketch into fragments | Call `sp.refs_to_construction(sk)` AFTER dimensioning, BEFORE selecting the profile, then `sp.smallest_profile(sk)`. (In the two certified generators this is a *defensive no-op* — they never project geometry — but it matters the moment you author a variant that projects a parent face/edge.) |
| Dims land on the wrong axis on the offset plane | sketch H/V map to different model axes on a non-XY plane | `sp.probe_orientations(sk, ...)` to get the orientation per model axis before dimensioning. |
| Interior of the curve won't drag / re-bake | fit points got fixed | Leave spline INTERIOR fit points free (only start/end are dimensioned) — that's the drag-to-shape, re-bakeable workflow the deps check exempts. |

## Applies vs. not

**Applies** when one continuous sculpted curve must flow across ≥2 separate members
meeting at a joint and you need exact continuity across the seam — and the spanned
interface is **axis-aligned** (a planar offset-plane cut along a model x or y axis).
Range guards: `base_arch_cut` — span > 2·end-inset, half-curve strictly increasing
along the span axis, first point on the floor (z=0); `foot_flare_cut` — kick > 0,
height > plumb, first point z=0, waste frame outboard of the blank end.

**Does NOT apply** when the curve lives entirely within one body (no seam — use a
per-part profile), or when the curve must cross a **tilted / non-axis-aligned**
interface (flowing a curve across a tilt is an escalation case, not this pattern).
That escalation is **per-CUT, not per-piece**: a part can have a tilted mitered
corner — handled as a plain vertical cut on the invariant seam plane — AND still use
this pattern for its axis-aligned arched aprons / face flares, exactly as the
bookcase does.

**See also:** `docs/organic-shapes.md` (single-body sculpted forms),
`docs/joinery.md` (Combine-Based Joinery — the inverse: many tools → one receiver),
`docs/angled-construction.md` (SplitBody, single-tool, for non-axis-aligned cases).
