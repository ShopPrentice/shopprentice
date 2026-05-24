# Repository Refactoring Plan

## Problem

The repo has grown organically and the directory structure is confusing:
- Two `tools/` directories with different purposes
- Docs spread across `woodworking/` and loose `.md` files (codex/ is agent codex, not part of this)
- Duplicated files (`woodgrain/probe_wood_appearance.py` = `scripts/probe_wood_appearance.py`)
- `helpers/sp.py` is 2,797 lines — a monolith mixing sketching, appearance, camera, joinery, and validation
- `addin/tools/_capture_helpers.py` is 2,399 lines
- Top-level `tools/` (dev scripts) easily confused with `addin/tools/` (MCP handlers)

## Constraint: No Import Path Breakage

Users have saved `.py` scripts with hardcoded imports:
```python
from helpers import sp                        # 30+ files
from woodworking.templates import domino      # 20+ files
from helpers import hardware                  # 7 files
```

The add-in puts the repo root on `sys.path` (ShopPrentice.py:19-21), so these resolve as top-level packages. Renaming `helpers/` or `woodworking/templates/` breaks every saved user script on upgrade.

**Rule: `helpers/` and `woodworking/templates/` keep their current import paths.** We restructure within those packages (split into submodules) but never rename the package root.

## What Changes

### 1. Split `helpers/sp.py` → `helpers/sp/` package

Convert the single file into a package with submodules. The `__init__.py` re-exports everything so `from helpers import sp; sp.ext_new(...)` keeps working with zero call-site changes.

Current 2,797 lines → 12 modules averaging ~230 lines:

| New Module | Current Section | Lines | Key Exports |
|------------|----------------|-------|-------------|
| `context.py` | Design Context | 42 | `DesignContext` |
| `faces.py` | Face Queries + Edge Queries | 168 | `find_face`, `find_face_at`, `find_faces_at_offset`, `find_edges` |
| `sketch.py` | Sketch Helpers + Setup | 396 | `sketch_rect`, `sketch_rect_model`, `refs_to_construction`, `sketch_on_plane`, `drop_to_line`, `smallest_profile` |
| `sketch_slot.py` | Sketch Slot (Stadium) | 259 | `sketch_slot`, `sketch_slot_model` |
| `features.py` | Feature Builders | 278 | `ext_new`, `ext_new_sym`, `ext_op`, `off_plane`, `combine`, `mirror_body`, `mirror_feats`, `make_comp`, `feat_pattern`, `body_pattern` |
| `spatial.py` | Spatial Queries | 121 | `body_side`, `face_side`, `classify_bodies` |
| `mating.py` | Mating Surface + Joint Validation | 259 | `mating_bounds`, `check_domino_exposure`, `validate_joint_contact` |
| `appearance.py` | Appearance | 696 | `apply_appearance`, grain direction helpers |
| `camera.py` | Screenshot / Camera | 149 | `screenshot_cam` |
| `assembly.py` | Joint Registry & Feasibility | 170 | `register_joint`, `check_assembly_feasibility`, `combine_joint`, `mirror_vector` |
| `deps.py` | Dependency Tree Validation | 320 | `validate_dependencies` |
| `_util.py` | Internal Helpers | 90 | `_make_ev`, `_find_body_recursive` |

`helpers/sp/__init__.py`:
```python
# Re-export everything so `from helpers import sp; sp.ext_new(...)` works unchanged.
from helpers.sp.context import *
from helpers.sp.faces import *
from helpers.sp.sketch import *
from helpers.sp.sketch_slot import *
from helpers.sp.features import *
from helpers.sp.spatial import *
from helpers.sp.mating import *
from helpers.sp.appearance import *
from helpers.sp.camera import *
from helpers.sp.assembly import *
from helpers.sp.deps import *
from helpers.sp._util import *
```

Cross-module dependencies within `helpers/sp/`:
- `features.py` imports from `_util.py` (for `_make_ev`)
- `sketch.py` imports from `_util.py`
- `sketch_slot.py` imports from `sketch.py` (for `probe_sketch_axes`)
- `mating.py` imports from `features.py` (for `combine`)
- `appearance.py` imports from `faces.py`, `camera.py`
- `assembly.py` imports from `features.py` (for `combine`)

All intra-package imports use relative: `from .features import combine`.

### 2. Split `addin/tools/_capture_helpers.py` → `addin/tools/_capture/` package

Same approach — package with re-exporting `__init__.py`.

Current 2,399 lines → 7 modules:

| New Module | Current Sections | Lines |
|------------|-----------------|-------|
| `sketch.py` | Sketch (full) + summary + entity ID | 715 |
| `extrude.py` | Extrude + inference helpers | 370 |
| `pattern.py` | Rectangular Pattern | 340 |
| `combine.py` | Combine + tool body inference | 130 |
| `modifiers.py` | Mirror, Move, Chamfer, Fillet, Sweep, Split, Remove | 560 |
| `body.py` | Body geometry + edge helpers | 70 |
| `plane.py` | Construction Plane + Sketch Plane | 170 |

Only `capture_design.py` and `export_script.py` import from `_capture_helpers`. The `__init__.py` re-exports everything so those imports don't change.

### 3. Consolidate docs into `docs/`

Move knowledge-base markdown from `woodworking/` to `docs/`:

| From | To |
|------|-----|
| `woodworking/joinery.md` | `docs/joinery.md` |
| `woodworking/joinery/*.md` | `docs/joinery/*.md` |
| `woodworking/fusion-api-rules.md` | `docs/fusion-api-rules.md` |
| `woodworking/appearance.md` | `docs/appearance.md` |
| `woodworking/angled-construction.md` | `docs/angled-construction.md` |
| `woodworking/details-and-finishing.md` | `docs/details-and-finishing.md` |
| `woodworking/hardware-installation.md` | `docs/hardware-installation.md` |
| `woodworking/helpers-reference.md` | `docs/helpers-reference.md` |
| `woodworking/incremental-updates.md` | `docs/incremental-updates.md` |
| `woodworking/loft.md` | `docs/loft.md` |
| `woodworking/mcp-advanced.md` | `docs/mcp-advanced.md` |
| `woodworking/optimizing-models.md` | `docs/optimizing-models.md` |
| `woodworking/organic-shapes.md` | `docs/organic-shapes.md` |
| `woodworking/screenshots.md` | `docs/screenshots.md` |
| `woodworking/templates-and-hardware.md` | `docs/templates-and-hardware.md` |
| `woodworking/types/*.md` | `docs/types/*.md` |
| `woodworking/styles/*.md` | `docs/styles/*.md` |

After this, `woodworking/` contains only `templates/` (Python code). 

**Do NOT move:**
- `codex/` — agent codex, separate concern
- `commands/` — Claude Code slash commands

**Update references:** SKILL.md, CLAUDE.md, commands/*.md, and template docstrings that reference `woodworking/*.md` paths must be updated to `docs/*.md`.

### 4. Rename top-level `tools/` → `dev/`

Disambiguates from `addin/tools/`. Contains developer-only scripts not run inside Fusion:

| From | To |
|------|-----|
| `tools/search_build.py` | `dev/search_build.py` |
| `tools/generate.py` | `dev/generate.py` |
| `tools/introspect.py` | `dev/introspect.py` |
| `tools/introspect_bodies.py` | `dev/introspect_bodies.py` |
| `tools/simulate.py` | `dev/simulate.py` |
| `tools/bed_rail_fastener.py` | `dev/bed_rail_fastener.py` |

Only one internal import (`addin/server/action_log.py` imports from `tools`). Update that.

### 5. Consolidate `scripts/` and `woodgrain/` → `dev/`

| From | To |
|------|-----|
| `woodgrain/probe_wood_appearance.py` | `dev/woodgrain/probe_wood_appearance.py` |
| `woodgrain/refresh_appearance.py` | `dev/woodgrain/refresh_appearance.py` |
| `scripts/wood_texture_*.py` | `dev/textures/wood_texture_*.py` |
| `scripts/wood_veneer_rectify.py` | `dev/textures/wood_veneer_rectify.py` |
| `scripts/probe_wood_appearance.py` | Delete (duplicate of `woodgrain/` version) |

### 6. Add `plans/` directory

Checked-in design plans for features in progress:

| From | To |
|------|-----|
| `.context/plans/*.md` | `plans/*.md` |
| `.claude/plans/*.md` | Reference only (user-private) |

## What Does NOT Change

| Directory | Why |
|-----------|-----|
| `helpers/` package path | User scripts import `from helpers import sp` |
| `woodworking/templates/` package path | User scripts import `from woodworking.templates import domino` |
| `codex/` | Agent codex, separate concern |
| `commands/` | Claude Code slash commands |
| `addin/` structure | Already well-organized |
| `examples/` | Already well-organized |
| `tests/` | Already well-organized |
| `hardware/` | STEP files, no code |
| `textures/` | Assets, no code |
| `mcp/` | Setup docs |

## execute_script.py Module Clearing

Currently clears `helpers.*` from `sys.modules` before each run:
```python
for _k in list(_sys.modules):
    if _k.startswith('helpers'):
        del _sys.modules[_k]
```

After sp.py split, this still works — `helpers.sp.faces`, `helpers.sp.sketch`, etc. all start with `helpers`. No change needed.

## Execution Order

### Session 1: sp.py split
1. Create `helpers/sp/` directory
2. Move `helpers/sp.py` → `helpers/sp/_monolith.py` (temporary)
3. Extract sections into submodules one at a time
4. Write `helpers/sp/__init__.py` with re-exports
5. Delete `_monolith.py`
6. Run all 17 template fixtures

### Session 2: _capture_helpers.py split
1. Create `addin/tools/_capture/` directory
2. Split into submodules
3. Write `__init__.py` with re-exports
4. Update imports in `capture_design.py` and `export_script.py`
5. Run capture_design on a built model

### Session 3: Directory cleanup
1. `git mv` docs from `woodworking/` to `docs/`
2. `git mv` `tools/` to `dev/`
3. Consolidate `scripts/` and `woodgrain/` into `dev/`
4. Create `plans/`
5. Delete `scripts/probe_wood_appearance.py` (duplicate)
6. Update all doc cross-references (SKILL.md, CLAUDE.md, commands/, template docstrings)
7. Run all fixtures

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| sp.py split breaks internal cross-references | High | Extract one section at a time, run fixtures after each |
| Doc path changes break SKILL.md references | Medium | Grep all `.md` files for old paths, update systematically |
| `tools/` → `dev/` breaks action_log import | Low | Single import to update |
| `woodworking/` still exists (templates only) — confusing? | Low | Add README.md explaining it's code, not docs |
