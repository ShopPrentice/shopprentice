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
face = af.find_face(body, "z", +1)  # top face
edges = adsk.core.ObjectCollection.create()
added = set()
for i in range(face.edges.count):
    edge = face.edges.item(i)
    if edge.tempId not in added:
        edges.add(edge)
        added.add(edge.tempId)
```

**CRITICAL:** The fillet/chamfer API requires `BRepEdge` objects, never `BRepFace`. When the design intent is "fillet a face," iterate the face's edges and add them. Use `tempId` to deduplicate shared edges between adjacent faces.

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

## Sizing Constraints

- Fillet radius must be less than half the smallest adjacent face dimension — too large and the fillet fails.
- Chamfer distance must be less than the shortest edge length on any affected face.
- When in doubt, start small (1/8") and let the user adjust via Change Parameters.
