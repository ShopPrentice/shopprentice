# Screenshot Guide

How to take consistent, high-quality screenshots for example READMEs and documentation.

## Standard Settings

```python
vp = app.activeViewport
vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle  # enum value 2
app.userInterface.activeSelections.clear()  # remove any blue highlights
```

**Resolution**: Always use `2048 x 2048` via `get_screenshot(width=2048, height=2048)`.

**Visual style**: `ShadedWithVisibleEdgesOnlyVisualStyle` (value 2) — shaded bodies with edge lines showing. This makes joints, panel gaps, and body boundaries clearly visible.

| Style Enum | Value | Use |
|---|---|---|
| `ShadedVisualStyle` | 0 | No edge lines (avoid for documentation) |
| `ShadedWithHiddenEdgesVisualStyle` | 1 | Hidden edges shown dashed |
| `ShadedWithVisibleEdgesOnlyVisualStyle` | 2 | **Default for screenshots** |
| `WireframeVisualStyle` | 3 | Wireframe only |

## Framing Rules

1. **Entire model inside the frame** — no body should be cut off at any edge. Pull the camera back enough.
2. **Model fills ~70-80% of the frame** — avoid excessive whitespace around the model.
3. **Center the subject** — the model (or detail area) should be centered in the frame, not off to one side.
4. **Grid is fine** — no need to hide the ground grid. It provides scale context.

### Camera Positioning

Use the bounding box to compute camera distance:

```python
# Get model bounding box
min_x = min_y = min_z = 1e10
max_x = max_y = max_z = -1e10
for i in range(root.allOccurrences.count):
    occ = root.allOccurrences.item(i)
    for j in range(occ.component.bRepBodies.count):
        proxy = occ.component.bRepBodies.item(j).createForAssemblyContext(occ)
        bb = proxy.boundingBox
        min_x, min_y, min_z = min(min_x, bb.minPoint.x), min(min_y, bb.minPoint.y), min(min_z, bb.minPoint.z)
        max_x, max_y, max_z = max(max_x, bb.maxPoint.x), max(max_y, bb.maxPoint.y), max(max_z, bb.maxPoint.z)

cx = (min_x + max_x) / 2
cy = (min_y + max_y) / 2
cz = (min_z + max_z) / 2
span = max(max_x - min_x, max_y - min_y, max_z - min_z)
```

Then position the camera with distance proportional to span:

```python
cam = vp.camera
cam.isFitView = False
cam.target = Point3D.create(cx, cy, cz)
# For iso-top-left: eye at (-X, -Y, +Z) from target
cam.eye = Point3D.create(cx - span*1.2, cy - span*1.2, cz + span*0.8)
cam.upVector = Vector3D.create(0, 0, 1)
vp.camera = cam
```

Adjust the multipliers (1.2, 0.8, etc.) to frame the model correctly. Start with `fit_view = True`, then fine-tune manually.

## Standard Shot Set for Examples

Each example should have at minimum an **overview** shot. Full documentation uses:

| Shot | Camera Position | Purpose |
|------|----------------|---------|
| `iso-top-left.png` | Eye at (-X, -Y, +Z) | Primary overview — shows front + left side |
| `iso-top-right.png` | Eye at (+X, -Y, +Z) | Alternate overview — shows front + right side |
| `front.png` | Eye at (cx, -far, cz) | Front elevation |
| `right.png` | Eye at (+far, cy, cz) | Side elevation |
| `overview.png` | Best angle for the piece | Alternative to iso pair for simpler models |

## Transparent / Detail Views

For joinery documentation, use body opacity to reveal internal structure:

```python
# Make case boards semi-transparent
for body in case_bodies:
    body.opacity = 0.2

# Hide entire component
some_occ.isLightBulbOn = False
```

### Common Detail Shots

| Shot | Technique | Shows |
|------|-----------|-------|
| Frame detail | Case transparent (0.2), frame opaque | M&T joints, rail connections |
| Case detail | Frame hidden, drawers opaque | Dovetails, dados, grooves |
| Joint close-up | Zoom to specific corner | Tenon fit, hinge mortise, brace triangle |

After taking transparent shots, **restore opacity** to 1.0 before taking opaque shots.

## Cleanup Before Screenshots

Always run this before taking any screenshot:

```python
app.userInterface.activeSelections.clear()

# Hide sketches and construction planes in all components
for comp in [root] + [root.allOccurrences.item(i).component
                       for i in range(root.allOccurrences.count)]:
    for sk in comp.sketches:
        sk.isVisible = False
    for cp in comp.constructionPlanes:
        cp.isLightBulbOn = False
    for ca in comp.constructionAxes:
        ca.isLightBulbOn = False
```

## Iterating on Framing

Getting the camera right often takes 2-3 attempts. Common adjustments:

- **Model cut off** → increase distance multipliers (move eye further from target)
- **Model too small** → decrease distance multipliers
- **Off-center** → shift target coordinates toward the model center
- **Wrong angle** → flip sign of eye offset components (e.g., -X → +X for opposite side)
