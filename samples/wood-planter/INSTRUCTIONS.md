# Fusion 360 Parametric Wood Planter -- Complete Build Instructions

## Overview

Build a Fusion 360 Python script that generates a parametric wood planter with frame construction, mortise-and-tenon joinery, grooved rails, and tongue-and-groove vertical slat infill. The model should be built exactly like a human woodworker would design it in Fusion 360 -- build one piece, then use Copy/Mirror/Pattern for the rest.

**File:** `~/tmp/WoodPlanterV2/WoodPlanterV2.py`
**Run:** Fusion 360 -> Utilities -> Add-Ins -> My Scripts -> (+) -> select folder -> Run

---

## 1. Design Philosophy

### Build Like a Human
- **Never build every piece from scratch.** Build one instance, then replicate with Mirror and Pattern features. This makes the model manageable and editable.
- **Use feature-based modeling** (Sketch -> Extrude), NOT `TemporaryBRepManager`. BRep bodies created with `TemporaryBRepManager` go into `BaseFeature` blocks that are static -- parameters exist in "Change Parameters" but changing them does NOT update geometry.
- **Organize with components.** Group related bodies into named components (Legs, LongRails, ShortRails, Slats, Bottom).
- **Everything parametric.** When the user changes `planter_length` from 60" to 48" in Change Parameters, the entire model should recompute automatically -- rail lengths, mirror positions, slat counts, everything.

### Do NOT
- Use `TemporaryBRepManager` -- it creates non-parametric geometry
- Use `createByReal(value_in_cm)` for parameter creation -- it shows confusing cm values
- Hardcode slat counts with Python `int()` at script time -- use `floor()` in parameter expressions instead
- Build all 4 sides of slats individually -- use mirror for opposite sides

---

## 2. Planter Specification

### Dimensions (all exposed as User Parameters)
| Parameter | Default | Description |
|-----------|---------|-------------|
| `planter_length` | 60 in | Overall planter length |
| `planter_width` | 20 in | Overall planter width |
| `total_height` | 40 in | Total height including legs |
| `leg_below_body` | 10 in | Leg height below body |
| `leg_size` | 3 in | Leg cross-section, square |
| `rail_thickness` | 2 in | Rail thickness |
| `rail_height` | 3 in | Rail height |
| `tenon_depth` | 2 in | Tenon depth into mortise |
| `tenon_width` | 1.25 in | Tenon width |
| `tenon_height` | 1.25 in | Tenon height |
| `groove_width` | 0.375 in | Frame groove width |
| `groove_depth` | 0.375 in | Frame groove depth |
| `frame_tongue_thick` | 0.34 in | Tongue thickness for frame grooves |
| `bottom_thickness` | 0.75 in | Bottom panel thickness |
| `slat_width` | 4 in | Slat face width |
| `slat_thickness` | 0.5 in | Slat body thickness |
| `slat_tg_width` | 0.25 in | Slat-to-slat T&G width |
| `slat_tg_depth` | 0.25 in | Slat-to-slat T&G depth |

### Construction
- **Frame:** 4 corner legs, 4 long rails (front/back, upper/lower), 4 short rails (left/right, upper/lower)
- **Joinery:** Mortise and tenon at all rail-to-leg connections. Tenons are staggered in Z so long and short rail tenons don't collide inside the corner legs.
- **Slats:** Vertical tongue-and-groove slats fill the openings between rails. Tongues on top/bottom insert into rail grooves. Adjacent slats joined to each other with T&G. First and last slats have edge tongues into leg grooves.
- **Bottom:** Single panel resting on lower rails.

---

## 3. Fusion 360 API Architecture

### Design Mode
```python
design.designType = adsk.fusion.DesignTypes.ParametricDesignType
```
Must be set BEFORE accessing `design.userParameters`. Without this, you get `RuntimeError: 3 : this is not a parametric design`.

### User Parameters
Create with `ValueInput.createByString("60 in")` so the Change Parameters dialog shows readable values with units:
```python
params.add("planter_length",
           adsk.core.ValueInput.createByString("60 in"),
           "in", "Overall planter length")
```

### Derived Parameters
Use expression strings that reference other parameters. These auto-recompute:
```python
params.add("long_shoulder",
           adsk.core.ValueInput.createByString("planter_length - 2 * leg_size"),
           "in", "Long rail shoulder length")
```

### Dimensionless Parameters (slat counts)
For counts derived from `floor()`, use empty string `""` as the unit:
```python
params.add("n_long_slats",
           adsk.core.ValueInput.createByString("floor(long_shoulder / slat_width)"),
           "", "Number of slats per long side")
```
These update automatically when `planter_length`, `leg_size`, or `slat_width` change.

### Feature-Based Workflow
Every shape is: **Sketch rectangle -> Constrain dimensions parametrically -> Extrude**

```python
# Draw approximate rectangle, then constrain with parametric dimensions
sk = comp.sketches.add(plane)
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
    adsk.core.Point3D.create(x0, y0, 0),
    adsk.core.Point3D.create(x0 + w, y0 + h, 0))

# Width dimension linked to parameter expression
d_w = sk.sketchDimensions.addDistanceDimension(
    rect[0].startSketchPoint, rect[0].endSketchPoint,
    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
    adsk.core.Point3D.create(...))
d_w.parameter.expression = "slat_width"  # parametric!

# Extrude with parametric distance
ext_input = comp.features.extrudeFeatures.createInput(
    profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
ext_input.setDistanceExtent(False,
    adsk.core.ValueInput.createByString("body_h"))  # parametric!
```

### Extrude Operations
| Operation | Use For |
|-----------|---------|
| `NewBodyFeatureOperation` | Creating new bodies (legs, rails, slat bodies) |
| `CutFeatureOperation` | Mortises, grooves, slat-to-slat grooves |
| `JoinFeatureOperation` | Tenons, tongues (adds material to existing body) |

### participantBodies (CRITICAL for gap slats)
When doing Cut or Join near other bodies, you MUST specify which body to target. Otherwise the operation may accidentally merge with or cut adjacent bodies:
```python
ext_input.participantBodies = [target_body]  # Python list, NOT ObjectCollection!
```
**Important:** Fusion 360 API expects a Python `list`, not `adsk.core.ObjectCollection`. Using `ObjectCollection` causes `TypeError`.

---

## 4. Component Structure

```
Root
  +-- Legs         (4 legs: build FL, mirror -> FR, BL, BR)
  +-- LongRails    (4 rails: build front lower+upper, mirror -> back)
  +-- ShortRails   (4 rails: build left lower+upper, mirror -> right)
  +-- Slats        (all slats: template+pattern per side, mirror template)
  +-- Bottom       (1 panel)
```

Create components with:
```python
occ = rootComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
occ.component.name = "Legs"
```

---

## 5. Mirror & Pattern Strategy

### Legs: Build 1, Mirror to 4
1. Build front-left (FL) leg at origin corner with:
   - 4 mortise cuts (staggered Z so long/short tenons don't collide)
   - 2 groove cuts (X-face for front slats, Y-face for left slats)
2. Create midplanes: YZ at `planter_length / 2`, XZ at `planter_width / 2`
3. Mirror FL across YZ midplane -> FR
4. Mirror [FL, FR] across XZ midplane -> BL, BR

### Rails: Build 2, Mirror to 4
1. Build front lower + upper rails with tenons and grooves
2. Mirror both across XZ midplane -> back rails
3. Same for short rails: build left, mirror across YZ midplane -> right

### Slats: Mirror Template, Independent Patterns (THE CORRECT APPROACH)

**Why not mirror the pattern feature?** Fusion 360 cannot properly mirror a `RectangularPatternFeature`. When you mirror a list of features that includes a pattern, only the template body and gap body get mirrored -- the pattern copies are lost. The mirror "only selects first and last slats."

**Why not mirror bodies?** When you mirror bodies (e.g., `pat_front.bodies`), you capture a fixed set of bodies at script time. When the user later increases `planter_length`, the pattern creates more bodies, but the mirror still references the original set -- leaving a gap on the mirrored side.

**Correct approach: Mirror the template, then pattern each side independently.**

```
Front slats:
1. Build front template (body + T&G + frame tongues) -> front_tmpl_feats[]
2. Mirror front_tmpl_feats across XZ midplane -> back template
3. Pattern front template along X with count = n_long_slats
4. Pattern back template along X with count = n_long_slats (separate pattern!)
5. Add front edge tongue -> mirror to back
6. Add front gap slat (conditional) -> mirror gap features to back

Left slats:
7. Build left template (body + T&G + frame tongues) -> left_tmpl_feats[]
8. Mirror left_tmpl_feats across YZ midplane -> right template
9. Pattern left template along Y with count = n_short_slats
10. Pattern right template along Y with count = n_short_slats (separate pattern!)
11. Add left edge tongue -> mirror to right
12. Add left gap slat (conditional) -> mirror gap features to right
```

Each side gets its own independent `RectangularPatternFeature` referencing the same parametric count expression (`n_long_slats` or `n_short_slats`). When the user changes dimensions, ALL patterns update independently.

### Pattern Feature Setup
```python
pat_feats = comp.features.rectangularPatternFeatures
body_coll = adsk.core.ObjectCollection.create()
body_coll.add(template_body)
pat_input = pat_feats.createInput(body_coll,
    comp.xConstructionAxis,
    adsk.core.ValueInput.createByString("n_long_slats"),  # parametric count!
    adsk.core.ValueInput.createByString("slat_width"),
    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
pattern = pat_feats.add(pat_input)
```

### Mirror Features Helper
```python
def mirror_features(comp, features, plane, name="Mirror"):
    mirror_feats = comp.features.mirrorFeatures
    feat_coll = adsk.core.ObjectCollection.create()
    for f in features:
        feat_coll.add(f)
    mirror_input = mirror_feats.createInput(feat_coll, plane)
    feat = mirror_feats.add(mirror_input)
    feat.name = name
    return feat
```

---

## 6. Slat Template Construction (per side)

Each slat template consists of:
1. **Body:** `slat_width x slat_thickness`, extruded `body_h`
2. **Left face groove:** `slat_tg_depth x slat_tg_width` cut (receives previous slat's tongue)
3. **Right edge tongue:** `slat_tg_depth x slat_tg_width` join (goes into next slat's groove)
4. **Top frame tongue:** `slat_width x frame_tongue_thick x groove_depth` join
5. **Bottom frame tongue:** same

After pattern, add:
6. **Left-edge frame tongue** on original only: `groove_depth x frame_tongue_thick x full_slat_h` (into leg groove)

### Gap Slat (fills remainder between last patterned slat and leg)
Since `floor(long_shoulder / slat_width)` typically leaves a remainder, add a gap-filling slat:
- Width = `long_shoulder - slat_width * n_long_slats` (parametric expression)
- Position = `leg_size + slat_width * n_long_slats`
- Has left groove (receives last patterned slat's tongue)
- Has right edge tongue (into leg groove)
- Has top/bottom frame tongues
- **Use `participantBodies`** on all cut/join operations to prevent merging with adjacent patterned slat

Gap slat is conditional: only build if the gap width > 0.01 cm at script time.

---

## 7. Construction Planes

All positioned with parametric offset expressions:
- `body_z = leg_below_body + rail_height` -- slat visible area bottom
- `hi_z = total_height - rail_height` -- upper rail Z
- `lo_z + rail_height - groove_depth` -- bottom tongue plane
- `mid_x = planter_length / 2` -- YZ midplane for left/right mirror
- `mid_y = planter_width / 2` -- XZ midplane for front/back mirror

---

## 8. Tenon Stagger Pattern

At corner legs, long and short rail tenons enter from adjacent faces. To prevent collision inside the leg, they are staggered in Z:
- Long tenon Z offset: `(rail_height - 2 * tenon_height) / 3`
- Short tenon Z offset: `2 * (rail_height - 2 * tenon_height) / 3 + tenon_height`

**Critical:** Mortise sketch profiles must be positioned INSIDE the leg body (starting at `leg_size - tenon_depth`), not outside it. Drawing mortises outside the leg causes "No target body found to cut" errors.

---

## 9. Body Naming Convention

- Legs: `Leg_FL`, `Leg_FR`, `Leg_BL`, `Leg_BR`
- Rails: `LongRail_Front_Lower`, `LongRail_Back_Upper`, etc.
- Slats: `Slat_Front_1`, `Slat_Front_2`, ..., `Slat_Back_1`, ..., `Slat_Left_1`, ..., `Slat_Right_1`, ...

Pattern copies named sequentially: `Slat_Front_{i+2}` for pattern body `i`.

---

## 10. Verification Checklist

1. Run in Fusion 360 -> component tree shows: Legs, LongRails, ShortRails, Slats, Bottom
2. Timeline shows: leg features -> mirror, rail features -> mirror, slat template -> mirror -> pattern x4 -> edge tongues -> gap slats
3. Change `planter_length` 60" -> 48" -> verify ALL FOUR sides' slat count decreases
4. Change `slat_width` 4" -> 3" -> verify slat count increases on all 4 sides
5. Change `planter_width` -> verify left/right slat count updates
6. Section Analysis -> verify T&G alignment between adjacent slats
7. Verify tenons don't overlap inside corner legs

---

## 11. Lessons Learned (Bug History)

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| `RuntimeError: this is not a parametric design` | Accessed `userParameters` before setting `ParametricDesignType` | Set `design.designType` first |
| `RuntimeError: A valid targetBaseFeature is required` | Used `TemporaryBRepManager` without `BaseFeature` | Switch to Sketch->Extrude feature-based modeling |
| `RuntimeError: No target body found to cut` | Mortise sketch drawn outside the leg body | Position sketch at `leg_size - tenon_depth` (inside) |
| Parameters don't update geometry | Used `TemporaryBRepManager` (static BRep in BaseFeature) | Use Sketch->Extrude features with param expressions |
| Mirrored side doesn't update slat count | Mirrored bodies are a fixed set captured at script time | Mirror only the template, create independent patterns per side |
| Mirror only creates first and last slat | Can't mirror a RectangularPatternFeature | Don't include pattern in mirror; create separate patterns |
| Gap slat merges with adjacent slat | Cut/Join without `participantBodies` affects all intersecting bodies | Use `participantBodies = [target_body]` (Python list) |
| `TypeError` on participantBodies | Passed `ObjectCollection` instead of Python `list` | Use `ext_input.participantBodies = [body]` |
| Slat count doesn't update | Used Python `int(pval(...))` at script time for pattern count | Use `floor()` in Fusion parameter expressions |
