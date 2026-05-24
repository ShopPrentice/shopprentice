# Assembly Feasibility Validation System

## Context

Agents sometimes create joinery (e.g., dovetail-shaped tenons intended to insert perpendicular to their taper) that is physically impossible to assemble. There is no check today that validates whether a joint's pieces can actually be moved into position during assembly. This system adds assembly vector tracking and geometric feasibility checking to the joinery pipeline.

## Approach Summary

1. **Joint registry** in `sp.py` — accumulates assembly metadata during script execution
2. **Templates auto-register** — each template knows its assembly vector and registers it after CUT
3. **Inline joinery registers explicitly** — via `sp.register_joint()` or `sp.combine_joint()` convenience wrapper
4. **`validate_design` gains a third check** — detects ALL joints from timeline CUTs, cross-references the registry, flags unregistered joints and checks feasibility via face-normal undercut analysis
5. **`capture_design` includes joint metadata** — so the agent sees assembly info in build output

## Data Model

### Joint Record (stored as design attribute)
```python
{
    "name": str,                    # Combine CUT feature name
    "template": str | None,        # "domino", "dovetail", etc.
    "assembly_vector": [x, y, z],  # Unit vector — insertion direction
    "tool_body": str,              # Tool body name
    "target_body": str,            # Target (mortise) body name
    "sequence": int,               # Assembly order (default 1)
    "feasibility": "ok" | "undercut",
    "undercut_count": int,
}
```

### Storage
- Module-level `_joint_registry: list` in `sp.py` during script execution
- Flushed to `design.attributes.add("shopprentice", "joints", json.dumps(...))` after script completes
- Cleared at start of each `clean=True` execution

## Assembly Feasibility Check Algorithm

**Face-normal undercut detection** — for each face of the tool body:

1. Get outward normal `N` at face centroid
2. `along = dot(N, assembly_vector)` — component along insertion direction
3. `perp = |N - along * assembly_vector|` — component perpendicular
4. If `along < -0.05` AND `perp > 0.05` → **undercut** (face hooks against insertion)

**Why this works:**
- **Rectangular M&T** (correct direction): side normals perpendicular to assembly (along=0). Entry face: along=-1, perp=0. Neither triggers. PASS.
- **Dovetail along taper** (correct): angled side normals perpendicular to slide axis (along~0). PASS.
- **Dovetail perpendicular to taper** (wrong): angled side normals have negative along AND positive perp. UNDERCUT detected. FAIL.
- **Domino**: stadium prism, all side normals perpendicular. PASS.

## Implementation Steps

### Step 1: Core infrastructure in `helpers/sp.py`

Add after existing combine functions (~line 796):

- `_joint_registry: list = []` — module-level state
- `_non_joint_cuts: set = set()` — feature names explicitly marked as non-joints
- `_normalize_vector(v)` — normalize 3-tuple to unit length
- `axis_vector(axis_name, direction=1)` — `"x" → (1,0,0)` etc.
- `check_assembly_feasibility(tool_body, assembly_vector, threshold=0.05)` — the face-normal undercut algorithm. Returns `{"feasible": bool, "undercut_count": int, "undercut_faces": [...]}`
- `register_joint(name, tool_body, target_body, assembly_vector, template=None, sequence=1)` — adds to registry, runs feasibility check immediately, prints warning if undercuts found
- `combine_joint(target, tool_bodies, op, keep_tool, name, assembly_vector, ...)` — convenience: `combine()` + `register_joint()` in one call
- `mark_non_joint(feature_name)` — adds to `_non_joint_cuts` (for trims, rabbets, material removal)
- `clear_joint_registry()` — resets both `_joint_registry` and `_non_joint_cuts`
- `flush_joint_registry(design=None)` — serializes registry to design attribute

### Step 2: Hook into `addin/tools/execute_script.py`

- After `_clean_design()` call (line 392): add `sp.clear_joint_registry()`
- After script execution succeeds (line 429 area, after transaction commit, before returning): add `sp.flush_joint_registry()`
- Import sp at top of the relevant block

### Step 3: Assembly check in `addin/tools/validate_design.py`

Add `_check_assembly(root_comp)` function:

**Part A — Read registry:**
- Read `design.attributes.itemByName("shopprentice", "joints")`
- Parse JSON → list of joint records

**Part B — Detect all CUTs from timeline:**
- Walk `design.timeline` for all `CombineFeature` with `operation == CutFeatureOperation`
- Collect feature names

**Part C — Cross-reference:**
- Registered CUT names vs. detected CUT names
- Any detected CUT not in registry AND not in `_non_joint_cuts` → unregistered warning
- Apply exclusion patterns: CUTs named `*_Trim*`, `*_Rab*`, `*_EdgeCut*`, `*_Groove*` are likely non-joint material removal — flag as "excluded" rather than error

**Part D — Re-verify feasibility:**
- For each registered joint where tool body still exists (keepTool=True bodies), re-run `check_assembly_feasibility()`
- For joints where tool body was consumed (after JOIN), trust the stored feasibility result from registration time

**Return structure:**
```python
{
    "feasible": bool,          # all registered joints pass
    "registeredJoints": int,
    "feasibleJoints": int,
    "unfeasibleJoints": int,
    "unregisteredCuts": int,
    "details": [...],          # per-joint results
    "unregistered": [...],     # unregistered CUT features
}
```

Update `passed` condition: `connectivity_ok AND interference_ok AND assembly_ok`

### Step 4: Template auto-registration

Each template adds `sp.register_joint()` calls after its CUT combines. Assembly vector derivation per template:

| Template | Assembly Vector | Derivation |
|----------|----------------|------------|
| `domino.py` | Interface normal (perp to mating plane) | `_plane_normal(plane)` on the construction plane arg |
| `mortise_tenon.py` (through) | Extrude direction (tenon into mortise) | Normal of the sketch plane arg |
| `mortise_tenon.py` (blind) | Same — but CUT is external, so return `assembly_vector` in result dict for caller to register |
| `dovetail.py` (box/corner) | Along `ext_axis` (NOT thick_axis) | `axis_vector(ext_axis)` — the axis the tail boards slide along |
| `finger_joint.py` | Along ext_axis | Same pattern as dovetail |
| `half_blind_dovetail.py` | Along ext_axis | Same pattern as dovetail |
| `drawbore.py` | Tenon: extrude direction. Pins: perpendicular (sequence=2) | Two registrations with different sequence values |
| `tenon_wedge.py` | Tenon: extrude direction. Wedge: perpendicular (sequence=2) | Two registrations |

**Dovetail example** (in `box()`, after line 538):
```python
av = axis_vector(ext_axis)
sp.register_joint(f"{name}_CutFront", left, front, av, template="dovetail")
if cut_back:
    sp.register_joint(f"{name}_CutBack", left, back, av, template="dovetail")
```

### Step 5: Capture integration in `addin/tools/capture_design.py`

In the summary builder, add:
```python
attr = design.attributes.itemByName("shopprentice", "joints")
if attr:
    summary["joints"] = json.loads(attr.value)
```

### Step 6: Documentation updates

**`woodworking/joinery.md`** — add new section "Assembly Feasibility" after "Combine-Based Joinery":
- Every joint must declare an assembly vector
- Templates do this automatically
- Inline joinery: call `sp.register_joint()` or use `sp.combine_joint()`
- `validate_design` checks: registered joints for geometric feasibility + all CUTs for registration completeness

**`CLAUDE.md`** — update `validate_design` description in the Quick Reference table to mention assembly feasibility

**Template docstrings** — note that each template auto-registers assembly vectors

## Critical Files

| File | Change |
|------|--------|
| `helpers/sp.py` (~line 796) | Joint registry, registration API, feasibility check, helper functions |
| `addin/tools/execute_script.py` (lines 392, 429) | Registry lifecycle hooks |
| `addin/tools/validate_design.py` | New `_check_assembly()` function + updated pass/fail |
| `addin/tools/capture_design.py` | Joint metadata in capture output |
| `woodworking/templates/domino.py` | Auto-register after CUT |
| `woodworking/templates/mortise_tenon.py` | Auto-register (through) / return vector (blind) |
| `woodworking/templates/dovetail.py` | Auto-register with ext_axis vector |
| `woodworking/templates/finger_joint.py` | Auto-register |
| `woodworking/templates/half_blind_dovetail.py` | Auto-register |
| `woodworking/templates/drawbore.py` | Multi-step registration |
| `woodworking/templates/tenon_wedge.py` | Multi-step registration |
| `woodworking/joinery.md` | Assembly feasibility docs |
| `CLAUDE.md` | Quick reference update |

## Verification

1. **Unit test**: Build a rectangular tenon body, run `check_assembly_feasibility()` along all 3 axes — should pass for all (uniform cross-section)
2. **Unit test**: Build a trapezoidal prism (dovetail tail), run check along taper axis (PASS) and perpendicular (FAIL with undercut faces)
3. **Integration test**: Execute a script with dovetail template → `validate_design` should show registered joints with feasibility=ok
4. **Integration test**: Execute a script with inline dado + `sp.register_joint()` → validate_design passes
5. **Negative test**: Execute a script with a CUT that has no registration → validate_design flags it as unregistered
6. **End-to-end**: Build a full piece (bench or box example) → validate_design reports all joints registered and feasible

## Open Questions

1. **Should unregistered CUTs be errors or warnings?** Recommendation: errors (fail validate_design) to enforce registration. But provide `mark_non_joint()` escape hatch for intentional non-joint CUTs.
2. **Mirrored/patterned joints**: Should the template register each mirror/pattern copy separately, or register the template joint and note that it's patterned? Recommendation: register the template joint once with a `"patterned": true` flag — the pattern copies inherit the same assembly vector.
