# Hardware Installation

Rules for importing, positioning, and organizing STEP hardware (bed rail fasteners, hinges, catches, etc.) in Fusion 360 models. Read this topic only when the design requires detachable or mechanical hardware — most furniture uses joinery templates instead.

## When to Read

- Bed rail fasteners (detachable rail-to-post connections)
- Butt hinges from STEP files (lid/door hinges)
- Any hardware imported from external STEP/IGES files
- Catches, latches, or other mechanical hardware

## STEP File Management

### Split STEP per part
If two hardware parts need different orientations (e.g., hook plate vs strike plate), generate **separate STEP files**. Never put opposite-facing parts in one STEP — you can't rotate them independently within one occurrence.

```
~/.shopprentice/hardware/bed_rail_fastener/
  hook_plate_100mm.step    # hook plate + its screws
  strike_plate_100mm.step  # strike plate + its screws
```

### Import once, copy many
Use a **module-level cache** keyed by `part_id` string. Do NOT rely on `hardware._import_or_copy()` — its cache key uses `id(design)` which changes every Python API call (new wrapper objects), so the cache never hits.

```python
_plate_cache = {}  # module-level

def _get_or_import(part_id, step_file, root):
    global _plate_cache
    if part_id in _plate_cache:
        tmpl = _plate_cache[part_id]
        if tmpl.isValid:
            return hw_mgr._copy_from_template(tmpl, root)
    # First import — hidden template
    imported = hw_mgr.import_step(step_file, root)
    tmpl_occ = imported[0][0]
    tmpl_occ.isLightBulbOn = False
    for bi in range(tmpl_occ.component.bRepBodies.count):
        tmpl_occ.component.bRepBodies.item(bi).isVisible = False
    _plate_cache[part_id] = tmpl_occ
    hw_mgr._hardware_occurrences.append((tmpl_occ, root))
    return hw_mgr._copy_from_template(tmpl_occ, root)
```

Result: 1 STEP import per part type, lightweight `copyPasteBodies` copies for each use.

## Positioning Rules

### Direction-aware rotation (Tested — bed rail fastener)
Hardware that faces outward (hooks, hinge barrels) must detect which side of the interface the parent board is on:

```python
rail_center = (rail_bb.minPoint.y + rail_bb.maxPoint.y) / 2
rail_on_positive_side = rail_center > iface
hook_dir = -1 if rail_on_positive_side else +1
```

Use paired rotations: `Ry(90°)` for +direction, `Ry(-90°)` for -direction.

### Center on the CUT target
The hardware body is used as a CUT tool to create the recess pocket. Center it on the **body being CUT**, not the mating body:

| Hardware | CUTs into | Center on |
|----------|----------|-----------|
| Hook plate | Rail | `rail_center` on the other axis |
| Strike plate | Post | `post_center` on the other axis |

**Why:** Rail center ≠ post center. The rail sits at the edge of the post (e.g., rail X center = 1.5 cm but post X center = 3.81 cm). Using post_center for hook plate CUT causes it to miss the rail entirely.

### Determinant validation
Every 3×3 rotation sub-matrix MUST have determinant = +1. Fusion rejects det = -1 (reflections) with `RuntimeError: invalid transform`.

**Common trap:** Flipping one axis to change direction gives det = -1. You must flip TWO axes (or zero) to maintain det = +1.

```python
# WRONG — det = -1 (reflection)
[0, 1, 0]    # model_X = STEP_Y
[0, 0, -1]   # model_Y = -STEP_Z (flipped for direction)
[1, 0, 0]    # model_Z = STEP_X
# det = 0 - 1(0-(-1)) + 0 = -1  ← REJECTED

# RIGHT — det = +1 (flip X too to compensate)
[0, -1, 0]   # model_X = -STEP_Y (also flipped)
[0, 0, -1]   # model_Y = -STEP_Z
[1, 0, 0]    # model_Z = STEP_X
# det = 0 - (-1)(0-(-1)) + 0 = 1  ← OK
```

**Always verify determinant before `defineAsFreeMove()`.**

## Component Organization

### Hardwares folder
Move installed hardware into a **"Hardwares" sub-folder** inside the parent component — the component of the board the hardware is attached to:

```
Root
  +-- Posts
  |     +-- Hardwares/          ← strike plates (8 for queen bed)
  +-- Rails
  |     +-- Hardwares/          ← hook plates (8 for queen bed)
  +-- _HW (hidden)              ← STEP templates only (4 files)
```

```python
def _get_hw_folder(parent_occ):
    for j in range(parent_occ.childOccurrences.count):
        ch = parent_occ.childOccurrences.item(j)
        if "Hardwares" in ch.component.name:
            return ch  # reuse existing folder
    hw = parent_occ.component.occurrences.addNewComponent(Matrix3D.create())
    hw.component.name = "Hardwares"
    return hw
```

### Cleanup pattern
In the script epilogue, move only **templates** (hidden originals at the STEP origin) into `_HW`. Installed copies stay visible in their parent's Hardwares folder.

```python
furniture_names = {"Posts", "Rails", "Headboard", "Slats", "Support"}
templates = [occ for occ in root.occurrences
             if occ.component.name not in furniture_names]
if templates:
    hw_container = root.occurrences.addNewComponent(Matrix3D.create())
    hw_container.component.name = "_HW"
    hw_container.isLightBulbOn = False
    for occ in templates:
        if occ.isValid:
            occ.moveToComponent(hw_container)
```

## STEP Coordinate Pitfall

Split STEP files retain the original generator coordinates, including spacing offsets (e.g., the 100mm plates are at STEP_X ≈ 16-26 from `idx * gap_x` in the generator). The `hp_cx` / `sp_cx` center values include these offsets. The rotation + translation math must use the actual STEP-space bounding box centers, not assumed zero-origin positions.

## Available Hardware Templates

| Hardware | Template | STEP Files | Status |
|----------|----------|-----------|--------|
| Bed rail fastener | `woodworking/templates/bed_rail_fastener.py` | `~/.shopprentice/hardware/bed_rail_fastener/` | Tested (queen + twin beds) |
| Butt hinge | `woodworking/templates/butt_hinge.py` | Inline (parametric, no STEP) | Tested (pencil box, wrap box) |
| Bowtie inlay | `woodworking/templates/bowtie.py` | Inline (parametric, no STEP) | Tested (twin bed) |
