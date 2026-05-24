# Screenshot Guide

How to take consistent, high-quality screenshots for example READMEs and documentation.

## MCP Tools (Primary Workflow)

Two MCP tools handle screenshots — use these instead of manual scripting:

| Tool | Use | Resolution | Cleanup |
|------|-----|-----------|---------|
| `get_screenshot` | Build validation | 1024×1024 | None (as-is) |
| `get_product_shots` | Final presentation | 2048×2048 | Auto-hides artifacts, restores state |

```
# Quick validation during builds
get_screenshot(view="iso-top-right")

# Final product shots (default: 3 views, high-res, cleaned up)
get_product_shots()

# Transparent view
get_product_shots(views=["iso-top-right"], style="transparent")

# Detail shot framing specific bodies
get_product_shots(views=["iso-top-right"], bodies=["Post_FL", "Rail_FrontBot"], fill=0.90)
```

## Internals: `sp.screenshot_cam()` — Dynamic Camera Positioning

The `screenshot_cam` helper computes camera distance automatically using the actual Fusion FOV and projected bounding box geometry. No manual multiplier tuning needed.

```python
from helpers import sp

# Overview: frame all visible bodies
sp.screenshot_cam(eye_dir=(1, -1, 0.7))

# Detail: frame only the dovetail tails at one corner
tails = [b for b in all_bodies if b.name.startswith("DT_FL")]
sp.screenshot_cam(eye_dir=(1, -1, 0.7), bodies=tails, fill=0.85)
```

### How It Works

1. Reads the actual Fusion perspective FOV (`camera.perspectiveAngle` — typically ~22°)
2. Computes the bounding box of the target bodies
3. Projects all 8 bbox corners onto the camera's view plane (right/up axes derived from eye direction)
4. Sets camera distance so the largest projected extent fills `fill` fraction of the frame
5. For elevation views where projected extent is small (flat face), enforces a minimum distance based on the 3D diagonal

### Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `eye_dir` | `(x, y, z)` | required | Camera direction from target |
| `bodies` | `[BRepBody]` | `None` | Bodies to frame. `None` = all visible bodies |
| `fill` | `float` | `0.80` | Fraction of frame the subject fills (0.0–1.0) |

### Standard Eye Directions

| Shot | `eye_dir` | Purpose |
|------|-----------|---------|
| iso-top-left | `(-1, -1, 0.7)` | Primary overview — front + left side |
| iso-top-right | `(1, -1, 0.7)` | Alternate overview — front + right side |
| front | `(0, -1, 0)` | Front elevation |
| right | `(1, 0, 0)` | Side elevation |

### Fill Guidelines

| Shot Type | Fill | Why |
|-----------|------|-----|
| Overview (iso) | `0.75–0.80` | Breathing room, grid visible |
| Front/side elevation | `0.80` | Min-distance clamp prevents flat-wall zoom |
| Joinery detail | `0.85–0.90` | Tight framing on the joint |
| Transparent overview | `0.70` | More context for internal structure |

## Choosing the Bounding Box

The `bodies` parameter controls what the camera frames. Choosing the right set of bodies is the key decision for each shot.

### Overview Shots

Pass `bodies=None` (default) — frames all visible bodies. Works for iso views, front, and side elevations.

### Joinery Detail Shots

Pass only the bodies directly involved in the joint. The camera zooms to their combined bounding box, ignoring everything else in the model.

**Think about what tells the story of the joint**, not just what's geometrically nearby:

| Joint | Bodies to Frame | Why |
|-------|----------------|-----|
| Dovetail corner | Tail bodies (e.g., `DT_FL*`) + adjacent pin board faces | Shows the interlocking geometry |
| M&T at one leg | The leg + the 2-3 rails that meet it | Shows how tenons weave inside |
| Domino joint | The domino void bodies + the 2 boards they connect | Shows mortise pockets straddling the interface |
| Hinge | Door + case side + hinge bodies | Shows rebate mortise and leaf placement |
| Drawer dovetails | All 5 drawer bodies (front, back, sides, bottom) | Shows half-blind vs through at each end |

**Rule of thumb:** if two long boards are joined by dovetails at one end, don't frame both full boards — frame the tails and the area around the joint. The agent should collect the tail bodies and maybe a short section of each board near the joint.

### Finding Bodies for Detail Shots

```python
ctx = sp.DesignContext()

# By exact name
leg = ctx.find_body("Leg_FL")

# By glob pattern — all dovetail tails at front-left corner
dt_tails = ctx.find_bodies("DT_FL*")

# By component — all bodies in the Frame component
frame_occ = None
for i in range(root.occurrences.count):
    if root.occurrences.item(i).component.name == "Frame":
        frame_occ = root.occurrences.item(i)
        break
frame_bodies = [frame_occ.component.bRepBodies.item(i)
                for i in range(frame_occ.component.bRepBodies.count)]
```

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

## Standard Shot Set for Examples

Each example should have at minimum an **overview** shot. Full documentation uses:

| Shot | File | Purpose |
|------|------|---------|
| `iso-top-left.png` | Primary overview — shows front + left side |
| `iso-top-right.png` | Alternate overview — shows front + right side |
| `front.png` | Front elevation |
| `right.png` | Side elevation |

### Taking All Standard Shots

Use `get_product_shots` — one MCP call captures all views:
```
get_product_shots(views=["iso-top-right", "front", "right"])
```

Internally this calls `sp.screenshot_cam()` for each view, hides artifacts, and restores state.

## Transparent / Detail Views

For joinery documentation, **isolate the relevant bodies** — hide everything unrelated so the joint is clearly visible against an empty background.

### Technique: Isolated Body Detail Shots (Preferred)

For each joinery detail, show only the 2-3 bodies directly involved in the joint, then use `screenshot_cam(bodies=...)` to frame them:

```python
from helpers import sp

# 1. Hide everything
for i in range(root.occurrences.count):
    root.occurrences.item(i).isLightBulbOn = False
for i in range(root.bRepBodies.count):
    root.bRepBodies.item(i).isVisible = False

# 2. Show only the relevant bodies
ctx = sp.DesignContext()
detail_bodies = []
for name in ["Leg_FL", "FrontRail", "SideRailL"]:
    b = ctx.find_body(name)
    b.isVisible = True
    b.opacity = 0.15  # semi-transparent to show internal joinery
    detail_bodies.append(b)

# 3. Frame the detail bodies (not the whole model)
sp.screenshot_cam(eye_dir=(1, -1, 0.7), bodies=detail_bodies, fill=0.85)
# → get_screenshot(width=2048, height=2048)
```

This produces much cleaner images than making everything transparent — no visual noise from unrelated bodies, and the camera automatically zooms to the joint area.

### Technique: Full Transparent Overview

For overview shots showing all internal structure at once, set all bodies to low opacity:

```python
# Set ALL bodies to 0.15 opacity
for i in range(root.bRepBodies.count):
    root.bRepBodies.item(i).opacity = 0.15
for i in range(root.allOccurrences.count):
    occ = root.allOccurrences.item(i)
    occ.isLightBulbOn = True
    for j in range(occ.component.bRepBodies.count):
        occ.component.bRepBodies.item(j).opacity = 0.15

sp.screenshot_cam(eye_dir=(-1, -1, 0.7), fill=0.70)
```

### Restoring After Detail Shots

After taking transparent/isolated shots, restore everything:

```python
for i in range(root.bRepBodies.count):
    b = root.bRepBodies.item(i)
    b.isVisible = True; b.opacity = 1.0
for i in range(root.allOccurrences.count):
    occ = root.allOccurrences.item(i)
    occ.isLightBulbOn = True
    for j in range(occ.component.bRepBodies.count):
        b = occ.component.bRepBodies.item(j)
        b.isVisible = True; b.opacity = 1.0
```

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
