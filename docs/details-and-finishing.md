# Details and Finishing

Phase 3 features: fillets, chamfers, and edge treatments. Read this file when adding finishing details to a completed structure+joinery model.

## Fillet and Chamfer Features

Detail features that soften or break edges. Both require selecting edges from existing bodies — all structural geometry and joinery must be built first.

**API asymmetry (CRITICAL):**
- **Fillet:** `filletFeatures.createInput()` → `inp.addConstantRadiusEdgeSet(edges, radius, propagate)`
- **Chamfer:** `chamferFeatures.createInput2()` → `inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, distance, propagate)`

Note: chamfer uses `createInput2()` (not `createInput()`) and has a nested `.chamferEdgeSets` collection before the add method.

## Edge Selection Strategies

Edges must be selected programmatically. Three patterns by increasing specificity:

**1. All edges of a body** — full-body chamfer/fillet (e.g., lid):
```python
edges = adsk.core.ObjectCollection.create()
for edge in body.edges:
    edges.add(edge)
```

**2. Edges at a coordinate** — edge ring at a specific plane (e.g., top edges, bottom edges):
```python
edges = adsk.core.ObjectCollection.create()
target_z = ev("box_height")
for i in range(body.edges.count):
    e = body.edges.item(i)
    sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
    if abs(sv.z - target_z) < 0.01 and abs(ev2.z - target_z) < 0.01:
        edges.add(e)
```

**3. Edges of a face** — when the design intent is "fillet this face" (e.g., seat-to-leg transitions):
```python
face = sp.find_face(body, "z", +1)  # top face
edges = adsk.core.ObjectCollection.create()
added = set()
for i in range(face.edges.count):
    edge = face.edges.item(i)
    if edge.tempId not in added:
        edges.add(edge)
        added.add(edge.tempId)
```

**CRITICAL:** The fillet/chamfer API requires `BRepEdge` objects, never `BRepFace`. When the design intent is "fillet a face," iterate the face's edges and add them. Use `tempId` to deduplicate shared edges between adjacent faces.

**4. Exposed edges only (skip joint mating lines)** — chamfer visible edges but not where joints meet:
```python
# Select outer perimeter edges only (both vertices on bounding box boundary)
# Skip: mortise slot edges, tongue groove edges, tenon shoulder edges
bb = body.boundingBox
tol = 0.05
edges = adsk.core.ObjectCollection.create()
for i in range(body.edges.count):
    e = body.edges.item(i)
    sv, ev2 = e.startVertex.geometry, e.endVertex.geometry
    on_bb = lambda pt: (abs(pt.x - bb.minPoint.x) < tol or abs(pt.x - bb.maxPoint.x) < tol
                        or abs(pt.y - bb.minPoint.y) < tol or abs(pt.y - bb.maxPoint.y) < tol
                        or abs(pt.z - bb.minPoint.z) < tol or abs(pt.z - bb.maxPoint.z) < tol)
    if on_bb(sv) and on_bb(ev2):
        edges.add(e)
```

**Chamfer edge selection rules:**
- **Never chamfer joint mating lines** — mortise slot boundaries, tenon shoulders, tongue groove edges. These are structural interfaces.
- **Non-manifold edges crash chamfers** — groove/mortise cuts that touch the bounding box create non-manifold edges. Filter by specific face (Z=max for top, X=min/max for ends) instead of "all boundary edges."
- **Dog hole circles and perimeter segments** are safe to chamfer on the top face.
- **End edges** (at X=min/max for a bench top) are safe — no grooves intersect the end faces.

## Chamfer Types

| Type | Method | Use For |
|------|--------|---------|
| Equal distance | `addEqualDistanceChamferEdgeSet(edges, dist, propagate)` | Most common — uniform bevel |
| Two distances | `addTwoDistanceChamferEdgeSet(edges, d1, d2, propagate)` | Asymmetric bevel |
| Distance + angle | `addDistanceAndAngleChamferEdgeSet(edges, dist, angle, propagate)` | Angled cuts |

## Code Patterns

```python
# Fillet — constant radius
fillet_inp = comp.features.filletFeatures.createInput()
fillet_inp.addConstantRadiusEdgeSet(
    edges,
    adsk.core.ValueInput.createByString("fl_r"),
    True)  # propagate to tangent edges
fillet = comp.features.filletFeatures.add(fillet_inp)
fillet.name = "SeatFillet"

# Chamfer — equal distance
ch_inp = comp.features.chamferFeatures.createInput2()
ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
    edges,
    adsk.core.ValueInput.createByString("ch_d"),
    True)  # propagate
ch = comp.features.chamferFeatures.add(ch_inp)
ch.name = "LidChamfer"
```

## Parameters

Use 2-letter prefixes consistent with joinery conventions:
```python
params.add("fl_r", VI("0.125 in"), "in", "Fillet radius")
params.add("ch_d", VI("0.125 in"), "in", "Chamfer distance")
```

Common woodworking values: fillet 1/16"–1/4" (comfort, softening), chamfer 1/8"–1/4" (visual detail, splinter prevention).

## What to Chamfer / Fillet

Chamfers and fillets are for **exposed structural edges only**. Skip:

- **Joinery void bodies** (`DM_*`, domino loose tenons) — chamfering expands them beyond their mortise pockets, causing interference with mating bodies.
- **Cylindrical bodies** (spindles, dowels) — already round, no sharp edges to break.
- **Mortise pocket interiors** — chamfering pocket edges creates tiny interferences where the tenon/spindle meets the chamfered edge. If you chamfer an entire component's edges in one feature, the pocket edges get chamfered too. This is usually harmless (sub-mm overlap) but will show up in interference checks.

**Best practice:** Collect all edges from structural bodies in a component (skipping void bodies), apply one chamfer feature per component. This keeps the timeline clean (4-5 features instead of one per body) and naturally excludes void bodies.

## Sizing Constraints

- Fillet radius must be less than half the smallest adjacent face dimension — too large and the fillet fails.
- Chamfer distance must be less than the shortest edge length on any affected face.
- When in doubt, start small (1/8") and let the user adjust via Change Parameters.

## Leg Tapers — use the `taper_legs` template

Never hand-roll taper wedge sketches with raw coordinates on construction
planes — on the xZ plane sketch-Y maps to model **-Z**, so the wedge lands
below the floor and the CUT silently removes nothing (the feature still
reports a healthy body; only a volume check catches it).

```python
from woodworking.templates import taper_legs

taper_legs.define_params(params, amount="0.5 in", run="25 in")

# Standard 4-leg furniture: taper the two faces looking at the center.
# Orientation-agnostic — same call works on straight, raked, and
# splayed legs (apply AFTER any Move/rotation):
taper_legs.inner_pair(comp, leg_body,
    center=(ev("frame_l / 2"), ev("frame_w / 2"), 0),
    ev=ev, thick_expr="leg_size * 2", name="Taper")

# Single face:
taper_legs.cut(comp, leg_body, taper_face, ev=ev,
    thick_expr="leg_size * 2", name="TaperX")
```

The template anchors all geometry to the leg's own projected edges (no
plane coordinates anywhere), derives the cut direction from the face
normal, and RAISES if the cut removed no material. Taper one template
leg, then mirror/pattern it to the other corners as usual. Tested on
straight, 6° raked, and compound rake+splay legs with exact analytic
volume checks (`tests/test_template_taper_legs.py`).
