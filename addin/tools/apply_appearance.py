"""
Apply Appearance Tool

Apply wood appearances to bodies with grain direction aligned to fiber
direction. Fiber direction is determined by the longest axis of each body's
bounding box (matching woodworking convention: fibers run parallel to the
longest dimension).

The texture map Z-axis is rotated to match the grain direction per the
Fusion 360 TextureMapControl3D API.
"""

import json
import traceback
import math
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()

# Wood species → ordered appearance search terms. Terms are tried strictly
# in order, so later entries are stand-in species for libraries that lack
# the real one. The stock library ("Fusion Appearance Library", renamed from
# "Fusion 360 Appearance Library") ships woods named plainly ("Oak",
# "Walnut") — as of 2026-07: Bamboo, Cherry, Mahogany, Oak, Pine, Walnut
# plus "3D " procedural variants. Species beyond that set (teak, ash,
# hickory, ...) need a fallback chain ending in a stock wood; when a
# stand-in is used the tool reports it in the result's "note" field.
SPECIES_MAP = {
    "cherry":     ["Cherry", "Mahogany", "Walnut"],
    "walnut":     ["Walnut"],
    "oak":        ["Oak"],
    "white oak":  ["White Oak", "Oak, White", "Oak"],
    "red oak":    ["Red Oak", "Oak, Red", "Oak"],
    "maple":      ["Maple", "Beech", "Oak"],
    "ash":        ["Ash", "Oak"],
    "birch":      ["Birch", "Maple", "Oak"],
    "pine":       ["Pine", "Fir", "Oak"],
    "cedar":      ["Cedar", "Pine", "Oak"],
    "mahogany":   ["Mahogany", "Sapele", "Walnut"],
    "teak":       ["Teak", "Mahogany", "Walnut"],
    "beech":      ["Beech", "Maple", "Oak"],
    "poplar":     ["Poplar", "Oak"],
    "hickory":    ["Hickory", "Ash", "Oak"],
    "ebony":      ["Ebony", "Walnut"],
    "rosewood":   ["Rosewood", "Walnut"],
    "sapele":     ["Sapele", "Mahogany", "Walnut"],
    "bamboo":     ["Bamboo"],
    "douglas fir": ["Douglas Fir", "Fir", "Pine", "Oak"],
}

# Substrings that identify a wood appearance in the hint listing. The old
# check ("wood" in the appearance name) matched the pre-rename "Wood
# (Cherry)"-style names and finds nothing in the current library, where
# woods are named plainly ("Oak", "Walnut", "Bamboo Light - Semigloss").
_WOOD_TERMS = sorted(
    {t.lower() for terms in SPECIES_MAP.values() for t in terms} | {"wood"})


def _find_body_recursive(comp, name):
    """Walk all components to find a body by name."""
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        if b.name == name:
            return b
    for i in range(comp.occurrences.count):
        occ = comp.occurrences.item(i)
        result = _find_body_recursive(occ.component, name)
        if result:
            return result
    return None


def _all_bodies(comp):
    """Collect all bodies across all components."""
    bodies = []
    for i in range(comp.bRepBodies.count):
        bodies.append(comp.bRepBodies.item(i))
    for i in range(comp.occurrences.count):
        bodies.extend(_all_bodies(comp.occurrences.item(i).component))
    return bodies


def _grain_axis_longest(body):
    """Determine grain direction from body bounding box longest axis.

    Returns: "x", "y", or "z"
    """
    bb = body.boundingBox
    dims = {
        "x": abs(bb.maxPoint.x - bb.minPoint.x),
        "y": abs(bb.maxPoint.y - bb.minPoint.y),
        "z": abs(bb.maxPoint.z - bb.minPoint.z),
    }
    return max(dims, key=dims.get)


def _analyze_dovetail_constraints(design):
    """Scan the timeline for dovetail features and derive grain constraints.

    Core rule: a dovetailed edge is always end grain. Fiber (grain) must
    NEVER be parallel to a dovetailed edge. Since the dovetailed edge runs
    along the pattern/joint axis, that axis is excluded for all bodies
    participating in the joint.

    Detection strategy:

    1. Find DT_Pat (RectangularPattern with "dt" in name):
       - The pattern axis = joint axis = dovetailed edge direction.
       - All bodies in the pattern are tail boards → exclude joint axis.

    2. Find DT_Cut* (Combine/Cut with "dt" in name):
       - targetBody is the pin board → also exclude joint axis,
         because the pin board's dovetailed edges run the same direction.

    Returns: dict of {body_name: set_of_excluded_axes}
        e.g. {"Left": {"z"}, "Right": {"z"}, "Front": {"z"}, "Back": {"z"}}
    """
    constraints = {}  # body_name -> set of axes grain must NOT be along
    timeline = design.timeline

    # Collect all body names involved in dovetail features, and the
    # joint axis from the pattern.
    joint_axes = []   # list of (joint_axis_str, set_of_body_names)

    for ti in range(timeline.count):
        item = timeline.item(ti)
        try:
            entity = item.entity
        except Exception:
            continue
        if entity is None:
            continue

        name = getattr(entity, 'name', '')
        if 'dt' not in name.lower():
            continue

        # Pattern feature → extract joint axis and tail board names
        if isinstance(entity, adsk.fusion.RectangularPatternFeature):
            joint_axis = _pattern_axis(entity)
            if joint_axis:
                body_names = set()
                for bi in range(entity.bodies.count):
                    body_names.add(entity.bodies.item(bi).name)
                joint_axes.append((joint_axis, body_names))

        # Combine/Cut → pin board also has dovetailed edges
        if (isinstance(entity, adsk.fusion.CombineFeature)
                and entity.operation == adsk.fusion.FeatureOperations
                .CutFeatureOperation):
            try:
                target = entity.targetBody
                if target:
                    for ja, bnames in joint_axes:
                        try:
                            for tbi in range(entity.toolBodies.count):
                                if entity.toolBodies.item(tbi).name in bnames:
                                    bnames.add(target.name)
                                    break
                        except Exception:
                            pass
            except Exception:
                pass

        # Join extrude → the bodies it joins are tail boards.
        if (isinstance(entity, adsk.fusion.ExtrudeFeature)
                and entity.operation == adsk.fusion.FeatureOperations
                .JoinFeatureOperation):
            try:
                for bi in range(entity.bodies.count):
                    bname = entity.bodies.item(bi).name
                    for ja, bnames in joint_axes:
                        bnames.add(bname)
            except Exception:
                pass

    # Build constraints: for each joint axis, all involved bodies
    # must NOT have grain along that axis.
    for joint_axis, body_names in joint_axes:
        for bname in body_names:
            constraints.setdefault(bname, set())
            constraints[bname].add(joint_axis)

    return constraints


def _pattern_axis(pattern_feat):
    """Extract the dominant model axis from a RectangularPatternFeature's
    direction one entity."""
    try:
        dir_entity = pattern_feat.directionOneEntity
        if hasattr(dir_entity, 'geometry'):
            geom = dir_entity.geometry
            if hasattr(geom, 'direction'):
                return _vector_to_axis(geom.direction)
    except Exception:
        pass
    return None


def _vector_to_axis(vec):
    """Map a Vector3D to the dominant model axis name."""
    if vec is None:
        return None
    ax, ay, az = abs(vec.x), abs(vec.y), abs(vec.z)
    if ax > ay and ax > az:
        return "x"
    elif ay > ax and ay > az:
        return "y"
    elif az > ax and az > ay:
        return "z"
    return None


def _grain_axis(body, excluded_axes=None):
    """Determine grain direction considering dovetail constraints.

    1. Start with the longest bounding box axis (default rule).
    2. If that axis is excluded by a dovetail constraint (end grain
       cannot be along the grain), pick the next longest axis that
       isn't excluded.

    Args:
        body: BRepBody
        excluded_axes: set of axis names ("x","y","z") that grain
            must NOT run along (because those are end-grain directions
            at dovetail joints).

    Returns: "x", "y", or "z"
    """
    bb = body.boundingBox
    dims = {
        "x": abs(bb.maxPoint.x - bb.minPoint.x),
        "y": abs(bb.maxPoint.y - bb.minPoint.y),
        "z": abs(bb.maxPoint.z - bb.minPoint.z),
    }
    excluded = excluded_axes or set()

    # Sort axes by dimension, longest first
    sorted_axes = sorted(dims, key=dims.get, reverse=True)

    for axis in sorted_axes:
        if axis not in excluded:
            return axis

    # All axes excluded (shouldn't happen) — fall back to longest
    return sorted_axes[0]


def _grain_transform(grain_dir):
    """Build a Matrix3D that orients the texture so the grain (texture Z)
    aligns with the specified model axis.

    Fusion 360 TextureMapControl3D docs:
      "For wood grain, the Z direction of the defined coordinate system
       is the direction of the grain."

    Default texture Z = model Z (grain vertical). We rotate to align
    texture Z with the desired grain axis.
    """
    m = adsk.core.Matrix3D.create()  # identity

    if grain_dir == "z":
        # Default: texture Z = model Z. No rotation needed.
        pass
    elif grain_dir == "x":
        # Rotate texture so Z maps to model X.
        # Rotation: 90° around model Y axis
        m.setToRotation(math.pi / 2, adsk.core.Vector3D.create(0, 1, 0),
                        adsk.core.Point3D.create(0, 0, 0))
    elif grain_dir == "y":
        # Rotate texture so Z maps to model Y.
        # Rotation: -90° around model X axis
        m.setToRotation(-math.pi / 2, adsk.core.Vector3D.create(1, 0, 0),
                        adsk.core.Point3D.create(0, 0, 0))
    return m


def _iter_library_appearances():
    """Yield (library, appearance) across all material libraries.

    Guarded per library — some libraries (material-only or cloud libraries)
    can raise when their appearances are enumerated, and one bad library
    must not abort the whole scan.
    """
    libs = app.materialLibraries
    for li in range(libs.count):
        lib = libs.item(li)
        try:
            lib_appearances = lib.appearances
            n = lib_appearances.count
        except Exception:
            continue
        for ai in range(n):
            try:
                yield lib, lib_appearances.item(ai)
            except Exception:
                continue


def _find_appearance(species):
    """Search Fusion material libraries for a wood appearance matching the
    given species name.

    Search terms are tried strictly in order, so a stand-in species (e.g.
    walnut for teak) is only used when no earlier term matches. Per term:
    1. the design's local appearances win (user may have customized),
    2. then all material libraries, preferring appearance libraries (both
       the current "Fusion Appearance Library" and the pre-rename
       "Fusion 360 Appearance Library" names contain "appearance"), exact
       name matches, and non-"3D" variants.

    Returns: (Appearance, source_description, matched_term)
             or (None, error_msg, None)
    """
    design = adsk.fusion.Design.cast(app.activeProduct)
    species_lower = species.lower().strip()
    search_terms = SPECIES_MAP.get(species_lower, [species])

    for term in search_terms:
        t = term.lower()

        # 1. Design-local appearances
        for i in range(design.appearances.count):
            a = design.appearances.item(i)
            if t in a.name.lower():
                return a, f"design:{a.name}", term

        # 2. Material libraries, ranked
        best = None
        best_rank = None
        best_source = ""
        for lib, a in _iter_library_appearances():
            a_name = a.name.lower()
            if t not in a_name:
                continue
            rank = (0 if "appearance" in lib.name.lower() else 1,
                    0 if not a.name.startswith("3D ") else 1,
                    0 if a_name == t else 1,
                    len(a_name))
            if best_rank is None or rank < best_rank:
                best, best_rank = a, rank
                best_source = f"{lib.name}:{a.name}"
        if best:
            return best, best_source, term

    return None, f"No appearance found for species '{species}'", None


def _list_wood_appearances(limit=30):
    """Names of wood appearances across all libraries, for error hints."""
    names = []
    seen = set()
    for _lib, a in _iter_library_appearances():
        n = a.name.lower()
        if a.name not in seen and any(t in n for t in _WOOD_TERMS):
            seen.add(a.name)
            names.append(a.name)
    return names[:limit]


def _copy_to_design(appearance):
    """Copy a library appearance into the active design so it can be
    assigned to bodies. Returns the design-local copy."""
    design = adsk.fusion.Design.cast(app.activeProduct)

    # Check if already in design
    existing = design.appearances.itemByName(appearance.name)
    if existing:
        return existing

    return design.appearances.addByCopy(appearance, appearance.name)


def handler(species: str, bodies: list = None,
            grain_overrides: dict = None) -> dict:
    """Apply a wood appearance to bodies with correct grain orientation.

    Args:
        species: Wood species name (e.g. "cherry", "walnut", "oak")
        bodies: List of body names. If empty/null, applies to ALL bodies.
        grain_overrides: Optional dict of {body_name: "x"|"y"|"z"} to
            override auto-detected grain direction for specific bodies.
    """
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True
            }

        root = design.rootComponent
        grain_overrides = grain_overrides or {}

        # Analyze dovetail constraints from timeline
        dt_constraints = _analyze_dovetail_constraints(design)

        # Species with real texture files in the repo (teak & friends):
        # build the design-local SP_<species> appearance via helpers so the
        # actual wood texture is used instead of a stand-in stock species.
        species_key = species.lower().strip()
        local_appearance = None
        source = ""
        note = None
        try:
            from helpers.sp import appearance as sp_appearance
            if species_key in sp_appearance._SPECIES_TEXTURE:
                local_appearance = sp_appearance.ensure_custom_appearance(
                    species_key)
                if local_appearance:
                    source = f"custom-texture:{local_appearance.name}"
        except Exception:
            local_appearance = None

        if local_appearance is None:
            # Find a library appearance
            appearance, source, matched_term = _find_appearance(species)
            if appearance is None:
                available = _list_wood_appearances()
                avail_str = ", ".join(available)
                return {
                    "content": [{"type": "text", "text": json.dumps({
                        "error": source,
                        "availableWoodAppearances": available,
                        "hint": f"Available: {avail_str}"
                    }, indent=2)}],
                    "isError": True
                }

            primary = SPECIES_MAP.get(species_key, [species])[0]
            if matched_term != primary:
                note = (f"No '{primary}' appearance in the installed "
                        f"libraries; used closest stock match "
                        f"'{appearance.name}'.")

            # Copy to design
            local_appearance = _copy_to_design(appearance)

        # Resolve target bodies
        if bodies:
            target_bodies = []
            not_found = []
            for name in bodies:
                b = _find_body_recursive(root, name)
                if b:
                    target_bodies.append(b)
                else:
                    not_found.append(name)
        else:
            target_bodies = _all_bodies(root)
            not_found = []

        # Apply appearance and orient grain
        applied = []
        errors = []

        for body in target_bodies:
            try:
                # Set appearance
                body.appearance = local_appearance

                # Determine grain direction
                if body.name in grain_overrides:
                    grain = grain_overrides[body.name]
                else:
                    excluded = dt_constraints.get(body.name, set())
                    grain = _grain_axis(body, excluded)

                # Orient texture map — use Box projection for reliable grain control
                adsk.doEvents()  # let Fusion process the appearance assignment
                tmc = body.textureMapControl
                if tmc:
                    ptmc = adsk.core.ProjectedTextureMapControl.cast(tmc)
                    tmc3d = adsk.core.TextureMapControl3D.cast(tmc)
                    if ptmc:
                        # Box projection respects the transform orientation;
                        # Automatic projection may override it
                        ptmc.projectedTextureMapType = (
                            adsk.core.ProjectedTextureMapTypes
                            .BoxTextureMapProjection)
                        ptmc.transform = _grain_transform(grain)
                    elif tmc3d:
                        tmc3d.transform = _grain_transform(grain)

                applied.append({
                    "body": body.name,
                    "grain": grain,
                    "appearance": local_appearance.name
                })
            except Exception as e:
                errors.append({
                    "body": body.name,
                    "error": str(e)
                })

        result = {
            "species": species,
            "appearance": local_appearance.name,
            "source": source,
            "applied": applied,
            "appliedCount": len(applied),
        }
        if note:
            result["note"] = note
        if dt_constraints:
            result["dovetailConstraints"] = {
                k: list(v) for k, v in dt_constraints.items()
            }
        if not_found:
            result["bodiesNotFound"] = not_found
        if errors:
            result["errors"] = errors

        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": False,
            "message": f"Applied {local_appearance.name} to {len(applied)} body(s)"
        }

    except Exception as e:
        app.log(f"apply_appearance error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text":
                         f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True
        }


# ── Tool definition ──

TOOL_DESCRIPTION = \
"""Apply a wood appearance to bodies with grain direction aligned to fiber direction.

Grain direction is determined by two rules:
1. **Default**: grain = longest bounding box axis (legs=Z, rails=X/Y, panels=longest)
2. **Dovetail constraint**: if a body has dovetail joints, the end-grain axis
   (the extrude direction of the dovetail join) is excluded — grain must NOT
   run along that axis. This reflects the physical truth that dovetailed edges
   are always end grain.

The tool scans the design timeline for dovetail features (DT_Join*, DT_Cut*,
DT_Pat*) and derives constraints automatically. When the default longest-axis
rule conflicts with a dovetail constraint, the next-longest non-excluded axis
is chosen.

The texture map is rotated so the wood grain pattern aligns with the detected
(or overridden) fiber direction.

Supported species: cherry, walnut, oak, white oak, red oak, maple, ash, birch,
pine, cedar, mahogany, teak, beech, poplar, hickory, ebony, rosewood, sapele,
bamboo, douglas fir.

Species with bundled texture files (teak and variants, brazilian rosewood,
cocobolo, ziricote, spalted maple) get a real texture via the repo's
textures/wood/ library. Other species missing from the installed Fusion
appearance libraries fall back to the closest stock wood (stock woods:
Bamboo, Cherry, Mahogany, Oak, Pine, Walnut); the result's "note" field
reports when a stand-in was used.

Examples:
  Apply cherry to all bodies:
    {"species": "cherry"}

  Apply walnut to specific bodies:
    {"species": "walnut", "bodies": ["Front", "Back", "Left", "Right"]}

  Override grain direction for legs (if auto-detect is wrong):
    {"species": "cherry", "grain_overrides": {"Leg_FL": "z", "Leg_FR": "z"}}
"""

tool = Tool.create_simple(
    name="apply_appearance",
    description=TOOL_DESCRIPTION
).add_input_property(
    "species",
    {
        "type": "string",
        "description": "Wood species name (e.g. 'cherry', 'walnut', 'oak', 'maple')"
    }
).add_required_input(
    "species"
).add_input_property(
    "bodies",
    {
        "type": "array",
        "description": "Body names to apply appearance to. If omitted, applies to ALL bodies.",
        "items": {"type": "string"}
    }
).add_input_property(
    "grain_overrides",
    {
        "type": "object",
        "description": "Override auto-detected grain direction for specific bodies. Keys are body names, values are 'x', 'y', or 'z'.",
        "additionalProperties": {
            "type": "string",
            "enum": ["x", "y", "z"]
        }
    }
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
