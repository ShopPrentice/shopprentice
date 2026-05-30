# Helpers Reference

Function signatures and usage for the `sp` helper library (`from helpers import sp`). Read this file when writing Fusion 360 scripts that use the helper functions.

## Standard Helpers

These reusable helpers form the foundation of the model-coordinate workflow. The caller specifies everything in model coordinates using parameter expressions; the helpers handle all sketch-space complexity.

### Helper Library (`from helpers import sp`)

The `af` helper library provides these functions as importable utilities, eliminating per-script boilerplate. Scripts can `from helpers import sp` and use them directly:

```python
from helpers import sp

def run(context):
    ctx = sp.DesignContext()          # app, design, root, params, units, ev()
    depth = ctx.ev("shelf_depth")     # evaluate parameter or expression → cm
    shelf = ctx.find_body("shelf_top")  # recursive body search by name
    shelves = ctx.find_bodies("shelf_*")  # glob pattern match

    # Queries
    top = sp.find_face(shelf, "z", +1)   # outermost planar face along axis
    at = sp.find_face_at(shelf, "z", 3.0)  # face at specific coordinate
    edges = sp.find_edges(shelf, "z")    # linear edges aligned with axis
    h, v = sp.probe_sketch_axes(sk)      # model axis → sketch H/V
    h, v, hs, vs = sp.probe_sketch_signs(sk)  # + sign detection
    p = sp.smallest_profile(sk)          # smallest-area profile in sketch

    # Spatial queries — body position relative to other bodies/faces
    side = sp.body_side(frag, seat, (0,0,1))     # 'inside'|'outside'|'opposite'
    side = sp.face_side(frag, top_face)           # 'normal'|'anti'|'on'
    groups = sp.classify_bodies(frags, leg)        # {'inside':[], 'outside':[], ...}

    # Mating surface — contact area between two bodies at their interface
    mb = sp.mating_bounds(rung, ladder_side, 'x')  # normal axis = 'x'
    # returns {'y_min': .., 'y_max': .., 'y_center': .., 'y_size': ..,
    #          'z_min': .., 'z_max': .., 'z_center': .., 'z_size': ..}
    # Raises ValueError if bodies are gapped, overlapping, or don't share
    # a mating surface — gives the agent diagnostic feedback during build.

    # Sketches — rectangles
    sk, prof = sp.sketch_rect(comp, plane, "0 cm", "0 cm", "w", "d",
                               name="Sk", ev=ctx.ev)
    sk2, prof2 = sp.sketch_rect_model(comp, plane,
                                       ("x0", "y0", "z0"),
                                       {"x": "width", "z": "height"},
                                       name="Sk2", ev=ctx.ev)

    # Sketches — stadium shapes (domino mortises, slot joints)
    sk3, prof3 = sp.sketch_slot(comp, plane, "cx", "cy",
                                 "dm_l", "dm_w", vertical=True,
                                 name="DM_Sk", ev=ctx.ev)
    sk4, prof4 = sp.sketch_slot_model(comp, plane,
                                       ("cx", "cy", "cz"), "z",
                                       "dm_l", "dm_w",
                                       name="DM_Sk", ev=ctx.ev)

    # Feature builders
    f = sp.ext_new(comp, prof, "board_thick", "FrontBoard")
    f = sp.ext_new_sym(comp, prof, "board_thick / 2", "Rail")  # total = board_thick
    f = sp.ext_op(comp, prof, "groove_depth", CUT, body, "Groove", flip=True)
    pl = sp.off_plane(comp, base_plane, "box_width / 2", "YMid")
    sp.combine(target, [tool1, tool2], CUT, True, "Mortise")
    m = sp.mirror_body(comp, body, mid_plane, "BackMirror")
    m = sp.mirror_bodies(comp, [b1, b2], mid_plane, "Mirror")
    m = sp.mirror_feats(comp, [ext_feat], mid_plane, "RabMirror")
    occ = sp.make_comp(root, "Shelves")
    pat = sp.feat_pattern(comp, feat, axis, "n_slats", "slat_pitch", "Pat")
    pat = sp.body_pattern(comp, body, axis, "n_shelves", "shelf_pitch", "Pat")
```

All helpers accept explicit objects (body, component, sketch) rather than relying on module globals, so they work in both normal and sandbox mode. The `ev` parameter falls back to creating one from the active design when omitted.

**Key improvements over inline versions:**
- `sketch_rect` and `sketch_rect_model` always add explicit H/V geometric constraints (some older scripts omitted these)
- `find_face` uses `pointOnFace` coordinate, not normal sign (handles both-direction normals correctly)
- `DesignContext.find_body/find_bodies` walks all descendant components recursively

**What's NOT in sp.py** (write these inline when needed): project-specific face finders (e.g., `find_top_face`), `angled_tenon_end`, `splay_center`.

### Spatial Queries — Body Position Testing

Three functions for determining where bodies are relative to other bodies or faces. All use center-of-mass (`body.physicalProperties.centerOfMass`) as the test point, and `pointContainment` for inside/outside classification. These are general-purpose spatial tools — not joinery-specific.

**`body_side(body, reference, direction)`** — Is a body on a given side of another body?

Returns `'inside'` (COM inside reference), `'outside'` (COM outside, on the direction side), or `'opposite'` (outside, other side).

```python
# Is this fragment above the seat?
if sp.body_side(frag, seat_body, (0, 0, 1)) == 'outside':
    remove(frag)

# Is this piece in front of the back panel?
if sp.body_side(shelf, back_panel, (0, -1, 0)) == 'outside':
    print("shelf is in front of back panel")
```

**`face_side(body, face)`** — Which side of a face is a body on?

Uses the face's outward normal. Returns `'normal'` (on the normal side), `'anti'` (opposite side), or `'on'` (within 0.01 cm of surface). Ideal after `SplitBody` — classify fragments by which side of the splitting face they ended up on.

```python
# After splitting at seat top face:
for frag in fragments:
    if sp.face_side(frag, seat_top_face) == 'normal':
        remove(frag)  # above the surface → excess
```

**`classify_bodies(bodies, reference, direction=None)`** — Batch-classify a list of bodies.

Returns `{'inside': [...], 'outside': [...], 'opposite': [...]}`. If `direction` is omitted, all outside bodies go into `'outside'` (no side filtering).

```python
# After splitting stretchers at leg surface:
groups = sp.classify_bodies(fragments, leg_body)
for b in groups['inside']:
    sp.combine(stretcher, b, JOIN, False)  # tenon interior
for b in groups['outside']:
    comp.features.removeFeatures.add(b)  # excess tip

# After splitting legs at seat — remove only above:
groups = sp.classify_bodies(fragments, seat_body, (0, 0, 1))
for b in groups['outside']:
    comp.features.removeFeatures.add(b)
# groups['opposite'] stays (below seat — main leg body)
```

**When to use which:**
| Scenario | Function | Direction |
|----------|----------|-----------|
| Fragment above/below a surface | `face_side(frag, face)` | (uses face normal) |
| Fragment above/below a body | `body_side(frag, body, dir)` | `(0,0,1)` for above |
| Fragment inside/outside a body | `body_side(frag, body, dir)` or `classify_bodies` | any direction, or `None` |
| Batch classification after split | `classify_bodies(frags, ref)` | optional |

### `ev()` — Dual-Mode Parameter Access

Evaluates a parameter name or expression string → float in cm. Use for computing approximate sketch positions; actual parametric behavior comes from dimension expressions, not `ev()` values.

**Preferred:** `ctx.ev("shelf_depth")` via `sp.DesignContext`. **Inline fallback** (when not using af):
```python
def ev(e):
    p = params.itemByName(e)
    return p.value if p else design.unitsManager.evaluateExpression(e, "cm")
```

### `sketch_rect_model()` — Parametric Rectangle in Model Coordinates

Available as `sp.sketch_rect_model(comp, plane, model_origin, model_size, name, ev)`.

Creates a fully parametric rectangle on ANY plane (including non-XY construction planes and BRepFaces). Internally uses `modelToSketchSpace` to convert model coordinates to sketch space, adds explicit H/V geometric constraints, and creates 4 parametric dimensions (width, height, x-offset, y-offset).

```python
sk, prof = sp.sketch_rect_model(comp, comp.xZConstructionPlane,
    ("0 in", "0 in", "0 in"),
    {"x": "box_length", "z": "box_height"},
    "Front_Sk", ev=ctx.ev)
```

- `model_origin`: `(x_expr, y_expr, z_expr)` — model-space corner expressions
- `model_size`: `{axis: expr, axis: expr}` — 2 model-axis size expressions
- Returns: `(sketch, profile)`

**Non-root sketches must be ANCHORED, not origin-positioned.** In its default form `sketch_rect_model` positions the rectangle with two `addDistanceDimension(sk.originPoint, …)` dims. That is correct ONLY for the root body's own sketch; for any non-root sketch it fails `validate_deps` (origin reference + not anchored to a parent). Make non-root rectangles compliant one of two ways:

**(a) `anchor=` mode — compliant from the start:**
```python
sk, prof = sp.sketch_rect_model(comp, plane, (x0,y0,z0), {"x":"w","y":"d"}, "Shelf_Sk", ev=ev,
    anchor=dict(parent_body=side_left, parent_occ=sides_occ, face_axis="z", face_dir=+1,
                anchor_xyz=("0 in","board_thick","z0"), off1=("x","w_off"), off2=("y","d_off")))
```
`anchor` projects the parent face, draws the rectangle from explicit model corners with H/V on all four edges, and dimensions a non-origin corner from a projected parent corner (`off1`/`off2` are positive-magnitude offsets). `which=` selects which corner to anchor; `size_far=True` sizes the far edges so a part whose own corner sits at world (0,0) never dimensions the origin vertex. The same `anchor=` dict shape is accepted by `sketch_slot_model` (key `off=((ax,expr),(ax,expr))`) and the joinery templates.

**(b) `sp.reanchor(...)` after the fact — retrofit any origin-mode sketch:**
```python
sk, prof = sp.sketch_rect_model(comp, plane, (x0,y0,z0), {"x":"w","y":"d"}, "Shelf_Sk", ev=ev)
sp.reanchor(sk, side_left, sides_occ, "z", +1, ("table_l", "0 in", "z0"))
```
This also resolves the old "position dimensions are always positive" problem — `reanchor` rewrites each offset as `abs(<orig expr> - <anchor expr>)`, so arbitrarily-positioned parts (splay-adjusted stretchers, etc.) get the correct sign automatically, with geometry unchanged. **Do NOT** use a manual `addTwoPointRectangle` with width/height only and no position dims — it leaves the sketch under-constrained and fails the validator.

### Feature Builder Reference (`sp.*`)

All feature builders take `comp` as first arg. Available via `from helpers import sp`.

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `ext_new` | `(comp, prof, dist, name)` | ExtrudeFeature | Body via `f.bodies.item(0)` |
| `ext_new_sym` | `(comp, prof, dist, name)` | ExtrudeFeature | Symmetric about sketch plane. **`dist` is the HALF-thickness** — extends `dist` on each side, creating a body of total thickness `2 × dist`. Use `"board_t / 2"` for a body of thickness `board_t`. |
| `ext_op` | `(comp, prof, dist_expr, op, body, name, flip)` | ExtrudeFeature | `flip=True` for NegativeExtentDirection (CUT into body on face sketches) |
| `off_plane` | `(comp, base, expr, name)` | ConstructionPlane | Offset construction plane |
| `combine` | `(comp, target, tool_bodies, op, keep_tool, name)` | CombineFeature | `tool_bodies` accepts single body or list |
| `mirror_body` | `(comp, body, plane, name)` | MirrorFeature | Mirrored body via `m.bodies.item(0)` |
| `mirror_bodies` | `(comp, bodies, plane, name)` | MirrorFeature | Multiple bodies at once |
| `mirror_feats` | `(comp, features, plane, name)` | MirrorFeature | Replays feature operations on mirrored side |
| `make_comp` | `(root_comp, name)` | Occurrence | Component via `occ.component` |
| `feat_pattern` | `(comp, feat, axis, count_expr, spacing_expr, name)` | RectangularPatternFeature | Feature pattern along axis |
| `body_pattern` | `(comp, body, axis, count_expr, spacing_expr, name)` | RectangularPatternFeature | **WARNING:** replays full feature tree — creates ghost bodies if template has CUT/JOIN history. Use Python `for` loop instead for complex bodies. |
| `sketch_slot` | `(comp, plane, cx_expr, cy_expr, long_expr, short_expr, vertical, name, ev)` | (sketch, profile) | Stadium shape in sketch-space coords. Use for domino mortises. |
| `sketch_slot_model` | `(comp, plane, model_center, long_model_axis, long_expr, short_expr, name, ev, anchor=None)` | (sketch, profile) | Stadium shape in model-space coords with auto sign detection. Pass `anchor=dict(parent_body, parent_occ, face_axis, face_dir, anchor_xyz, off=((ax,expr),(ax,expr)))` to anchor a NON-root slot to a projected parent (else origin mode → fails the validator). |
| `probe_sketch_signs` | `(sk)` | (h_axis, v_axis, h_sign, v_sign) | Extends `probe_sketch_axes` with sign detection for non-XY planes. |
| `mating_bounds` | `(body_a, body_b, normal_axis, tol=0.1)` | dict | Contact area between two bodies at interface. Returns `{ax_min, ax_max, ax_center, ax_size}` for each axis parallel to the interface. **Raises ValueError** if bodies are gapped (not touching), overlapping (penetrating — CUT first), or have no shared mating surface. Provides diagnostic messages with axis ranges so the agent can fix placement during the build. |
| `check_domino_exposure` | `(void, body_a, body_b, normal_axis, tol=0.05)` | None | Checks that a domino void creates blind pockets in both mating pieces. On axes perpendicular to the interface normal, the void must be fully contained within each body's bounding box. **Raises ValueError** if the void extends beyond either body — the mortise opens to a surface (exposed domino). Call AFTER creating the void body but BEFORE CUTting. Error message includes axis ranges and overshoot distance for diagnosis. |
| `sketch_on_plane` | `(comp, plane, project=None, intersect=None, identify=None, name="Sk")` | (sketch, found_pts) | **A one-call way to anchor a child sketch to a parent body/face** (project + identify together). Creates the sketch, projects each entity in `project` (proxy faces/bodies/edges from `createForAssemblyContext`), optionally intersects bodies, auto-converts all references to construction, and — for each `{name: model_Point3D}` in `identify` — returns the nearest resulting SketchPoint. The identify point is only a *locator* (it selects which projected vertex); the anchor's real position comes from the projected geometry, so nothing is computed. Draw new geometry FROM the returned points. |
| `drop_to_line` | `(sketch, point, ref_line, approximate_target=None)` | SketchPoint | Drops a perpendicular construction line from a SketchPoint to a reference line and returns the associative projected point (updates when source/reference move). |
| `refs_to_construction` | `(sk)` | None | Converts all projected/reference lines in a sketch to construction geometry so only drawn curves define profiles. Called automatically by `sketch_on_plane`. Note: demotes LINES; projected circles/arcs stay reference curves (still usable by `anchor_pt`). |
| `project_face` | `(child_sk, parent_body, parent_occ, axis, direction)` | None | Projects the parent body's outermost `axis`/`direction` face (assembly-context proxy when `parent_occ` is given) into the child sketch as a construction/reference, satisfying "project real parent geometry". |
| `anchor_pt` | `(child_sk, mx, my, mz, include_centers=True, exclude_origin=True)` | SketchPoint or None | Nearest projected-reference point to a model point — for anchoring drawn geometry. Considers line start/end AND circle/arc **centres** (round/turned parts) and reference curves; **auto-skips the sketch origin**. Returns None if nothing eligible was projected. |
| `rdim` | `(sk, d, p1, p2, orient, axis, expr)` | None | Tolerant relative distance dimension between two sketch points along a model `axis` (`orient` from `probe_orientations`). Skips (with a **logged** warning, not silently) if it would over-constrain — so an unexpected skip that leaves a sketch under-constrained is traceable. Use POSITIVE magnitude expressions. |
| `reanchor` | `(sk, parent_body, parent_occ, face_axis, face_dir, anchor_xyz)` | int (dims retargeted) | **One-call fix for a non-root sketch built in origin mode.** Projects the parent face, finds a non-origin anchor, and retargets every `sk.originPoint` dimension to it as `abs(<orig expr> - <anchor axis expr>)`. DOF + geometry preserved. `anchor_xyz` = `(x,y,z)` model exprs of a real parent corner. The anchored vertex must not itself be at world (0,0) — for that use `sketch_rect_model(anchor=…, size_far=True)`. |
| `validate_deps` | `(ctx, metadata_path=None)` | bool or None | Validates the dependency tree from `model.json`. Hard checks (affect pass/fail): (1) single origin root — only 1 body may reference `"origin"`; (2) sketch origin — non-root sketches must not dimension from `sk.originPoint`; (3) **sketch traceability** — every non-root sketch must project real reference geometry, use no Fix/Ground constraint on drawn geometry, and be fully constrained relative to that reference (Fusion's `sketch.isFullyConstrained` is the judge — a rigid sketch that floats is not fully constrained; only fit-point spline interiors may remain free, and their start/end must anchor); (4) no bodies in the root component. Advisory: completeness (tracked-body coverage). Returns `True`/`False`/`None` (no metadata). Dep entries support optional `"replicas": "glob_pattern"` for pattern copies. A body's `"ref"` may be a single parent name OR a list of names — multi-contact joints reference more than one parent (e.g. a wedge bearing on a post AND riding a stretcher; a shelf tenoned into two sides). Only the `"origin"` root is unique; every other body needs ≥1 parent but is not capped at one. |

### Cross-Component Proxy Projection

Use `sketch_on_plane` with `project=` and `identify=` when a child component's sketch needs to anchor to a parent body in another component. New geometry is drawn FROM the identified projected points, so there is no origin-based parameter math and no computed coordinate to drift.

```python
# Example: Position a shelf sketch relative to a side panel in another component
parent_occ = root.allOccurrencesByComponent(side_comp).item(0)
side_proxy = side_body.createForAssemblyContext(parent_occ)
inner_face = sp.find_face(side_proxy, "y", +1)   # inner face of side panel

# Read the locator from REAL parent geometry (bounding box), not parameters.
bb = side_body.boundingBox
corner_seed = adsk.core.Point3D.create(bb.minPoint.x, bb.minPoint.y, bb.maxPoint.z)

# Project the proxy face into the child sketch and identify the anchor point.
sk, anchors = sp.sketch_on_plane(
    shelf_comp, shelf_plane,
    project=[inner_face],
    identify={"corner": corner_seed},
    name="ShelfSk")
pt = anchors["corner"]          # associative projected point — moves with the parent

# Draw FROM the anchor point. The shelf inset is a parametric dimension measured
# from the projected reference, not a coordinate computed in Python.
line = sk.sketchCurves.sketchLines.addByTwoPoints(pt, other_anchor)
d = sk.sketchDimensions
d.addDistanceDimension(pt, line.endSketchPoint, H, placement
).parameter.expression = "shelf_inset"
```

**For a standard rectangle, slot, or dovetail in a non-root component, prefer the `anchor=` mode** (or `sp.reanchor(...)` after the fact) of the shape helpers instead of wiring this by hand — see the `sketch_rect_model()` section above for both, with examples. `sketch_slot_model`, `trapezoid_sketch` (the dovetail template helper in `woodworking/templates/`, not an `sp.*` function), and the joinery templates accept the same `anchor=`; under the hood they call `project_face` / `anchor_pt` / `rdim`.

> **Anti-pattern — do NOT do this.** Computing corner coordinates from parameters
> (`P(inset, depth, h)`), placing the geometry there, and then deleting the
> origin dimensions to "pass" the deps check. That satisfies the origin check on
> paper while the numbers simply moved from a dimension into a Python variable —
> the sketch is still floating, not referenced. The traceability check in
> `validate_deps` now catches this: a sketch with no projected reference, or that
> isn't fully constrained against it (spline interiors excepted), fails.
