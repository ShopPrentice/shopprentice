"""Hardware installation helper.

Imports real hardware STEP files from the catalog, positions them
in the model, and CUTs leaf rebates into boards.

Catalog and STEP files live in the shopprentice repo under hardware/.

4 hinge installation styles:

    lid_surface  — Horizontal pin, leaves on back face, visible with rebate.
                   Box lid flips up. Barrel behind back face.
    lid_flush    — Horizontal pin, leaves between boards, hidden.
                   Box lid, clean exterior. Barrel behind back face.
    door_surface — Vertical pin, overlay door, hinge inserted from side.
                   Folded closed, hidden at Y seam. Barrel at side edge.
    door_flush   — Vertical pin, leaves between boards, hidden.
                   Cabinet door, clean exterior.

STEP model reference frame (McMaster 1603A series):
    Pin along X, leaves in XZ plane, thin in Y.
    leaf_a = +Z side, leaf_b = -Z side.
    Leaf plate faces at Y = -0.1473 (screw/outer) and Y = -0.0838 (inner).
    Plate thickness ~ 0.025 in, but barrel extends to Y = +0.1473.

Usage:
    from helpers import hardware

    rec = hardware.recommend_hinge(lid_length_cm=25.4)

    result = hardware.install_butt_hinge(
        part_id="1603a3",
        comp=root,
        back_body=back,
        lid_body=lid,
        pin_position=(x, y, z),
        style="lid_surface",
        install_screws=True,
        ev=ctx.ev,
        name="Hinge1",
    )
"""

import adsk.core
import adsk.fusion
import json
import os

import math

Point3D = adsk.core.Point3D
Vector3D = adsk.core.Vector3D
Matrix3D = adsk.core.Matrix3D
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation

VALID_STYLES = ("lid_surface", "lid_flush", "door_surface", "door_flush")

# ── Catalog ──────────────────────────────────────────────────────────

def _find_hardware_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(here))
    hw_dir = os.path.join(repo_root, "hardware")
    if os.path.isdir(hw_dir):
        return hw_dir
    for candidate in [
        os.path.expanduser("~/projects/shopprentice/hardware"),
        os.path.expanduser("~/.shopprentice/hardware"),
    ]:
        if os.path.isdir(candidate):
            return candidate
    raise FileNotFoundError("Cannot find hardware directory.")


HARDWARE_DIR = _find_hardware_dir()
CATALOG_PATH = os.path.join(HARDWARE_DIR, "catalog.json")


def _load_catalog():
    if not os.path.isfile(CATALOG_PATH):
        return {"parts": {}}
    with open(CATALOG_PATH, "r") as f:
        return json.load(f)


def _save_catalog(catalog):
    os.makedirs(HARDWARE_DIR, exist_ok=True)
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)


def list_parts(category=None):
    catalog = _load_catalog()
    parts = []
    for pid, entry in catalog.get("parts", {}).items():
        if category and entry.get("category") != category:
            continue
        parts.append({
            "part_id": pid, "name": entry.get("name", pid),
            "category": entry.get("category", ""),
            "mcmaster_pn": entry.get("mcmaster_pn", ""),
            "dimensions": entry.get("dimensions", {}),
            "notes": entry.get("notes", ""),
        })
    return parts


def search(query, category=None):
    query_lower = query.lower()
    results = []
    for part in list_parts(category=category):
        searchable = (part.get("name", "") + " " + part.get("notes", "")).lower()
        if query_lower in searchable:
            results.append(part)
    return results


def get_part(part_id):
    catalog = _load_catalog()
    return catalog.get("parts", {}).get(part_id)


def register_part(part_id, name, category, step_file,
                   dimensions=None, anchor=None, mcmaster_pn=None,
                   notes=None):
    catalog = _load_catalog()
    if "parts" not in catalog:
        catalog["parts"] = {}
    entry = {"name": name, "category": category, "step_file": step_file}
    if dimensions:
        entry["dimensions"] = dimensions
    if anchor:
        entry["anchor"] = anchor
    if mcmaster_pn:
        entry["mcmaster_pn"] = mcmaster_pn
    if notes:
        entry["notes"] = notes
    catalog["parts"][part_id] = entry
    _save_catalog(catalog)
    return entry


# ── Hinge Selection ──────────────────────────────────────────────────

def recommend_hinge(lid_length_cm=None, lid_length_expr=None, ev=None):
    catalog = _load_catalog()
    guide = catalog.get("selection_guide", {}).get("hinge")
    if not guide:
        return {"part_id": "1603a3", "reason": "default medium hinge"}
    if lid_length_cm is None and lid_length_expr and ev:
        lid_length_cm = ev(lid_length_expr)
    if lid_length_cm is None:
        raise ValueError("Provide lid_length_cm or (lid_length_expr + ev)")
    lid_in = lid_length_cm / 2.54
    for rule in guide["rules"]:
        max_len = float(rule["max_lid_length"].replace(" in", ""))
        if lid_in <= max_len:
            part = get_part(rule["recommended"])
            return {
                "part_id": rule["recommended"],
                "name": part.get("name", rule["recommended"]) if part else rule["recommended"],
                "dimensions": part.get("dimensions", {}) if part else {},
                "reason": rule["reason"], "count": 2,
                "spacing_rule": guide.get("spacing", ""),
            }
    last = guide["rules"][-1]
    return {"part_id": last["recommended"], "reason": "largest available"}


# ── STEP Import + Per-Component Cache ────────────────────────────────

# Cache: (design_id, comp_id, part_id) -> template_occurrence
# Import STEP once per (component, part_id). Copy via TemporaryBRepManager
# for additional uses — no parametric dependency, templates can be deleted.
_comp_step_cache = {}

# Track hardware occurrences per parent component for cleanup_step_templates()
# Key: component entityToken, Value: list of (occurrence, parent_component)
_hardware_occurrences = []  # (occurrence, parent_component)
_root_baseline_count = -1  # root occurrence count before any imports


def clear_step_cache():
    """Clear the STEP template cache (call on design change)."""
    global _comp_step_cache, _hardware_occurrences, _root_baseline_count
    _comp_step_cache.clear()
    _hardware_occurrences.clear()
    _root_baseline_count = -1


def cleanup_step_templates():
    """Move hardware occurrences into _Hardware container components.

    Call after all install_butt_hinge / install calls are done.
    1. Moves installed hardware into _Hardware per parent component.
    2. Moves root-level STEP import artifacts into _Imports at root.
    """
    global _hardware_occurrences, _root_baseline_count
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent

    # ── 1. Move installed hardware into _Hardware per parent component ──
    if _hardware_occurrences:
        by_parent = {}
        for occ, parent_comp in _hardware_occurrences:
            if not occ.isValid:
                continue
            key = id(parent_comp)
            if key not in by_parent:
                by_parent[key] = (parent_comp, [])
            by_parent[key][1].append(occ)

        for _, (parent_comp, occs) in by_parent.items():
            if not occs:
                continue
            hw_occ = parent_comp.occurrences.addNewComponent(Matrix3D.create())
            hw_occ.component.name = "_Hardware"
            for occ in occs:
                if occ.isValid:
                    try:
                        occ.moveToComponent(hw_occ)
                    except Exception:
                        pass

    # ── 2. Collect root-level STEP artifacts ──
    # User-created furniture components have sketches or features in their
    # timeline. STEP import artifacts are pure geometry with no sketches.
    # Also skip _Hardware/_Imports containers.
    user_comp_tokens = set()
    for _, parent_comp in _hardware_occurrences:
        user_comp_tokens.add(parent_comp.entityToken)

    imports_to_move = []
    for i in range(root.occurrences.count):
        occ = root.occurrences.item(i)
        comp = occ.component
        if comp.entityToken in user_comp_tokens:
            continue
        if comp.name.startswith("_Hardware") or comp.name.startswith("_Imports"):
            continue
        # User-created components have sketches; STEP imports don't
        if comp.sketches.count > 0:
            continue
        imports_to_move.append(occ)

    if imports_to_move:
        imp_occ = root.occurrences.addNewComponent(Matrix3D.create())
        imp_occ.component.name = "_Imports"
        imp_occ.isLightBulbOn = False
        for occ in imports_to_move:
            if occ.isValid:
                try:
                    occ.moveToComponent(imp_occ)
                except Exception:
                    pass

    _hardware_occurrences.clear()
    _root_baseline_count = -1


def import_step(file_path, target_comp=None, view_fit=False):
    """Import a STEP file into a Fusion 360 component."""
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if target_comp is None:
        target_comp = design.rootComponent
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"STEP file not found: {file_path}")
    import_mgr = app.importManager
    step_opts = import_mgr.createSTEPImportOptions(file_path)
    step_opts.isViewFit = view_fit
    result = import_mgr.importToTarget2(step_opts, target_comp)
    if result is None:
        raise RuntimeError(f"STEP import failed: {file_path}")
    imported = []
    for i in range(result.count):
        occ = adsk.fusion.Occurrence.cast(result.item(i))
        if occ:
            bodies = [occ.component.bRepBodies.item(j)
                      for j in range(occ.component.bRepBodies.count)]
            imported.append((occ, bodies))
    return imported


def _resolve_step_path(step_file):
    if os.path.isabs(step_file):
        return step_file
    return os.path.join(HARDWARE_DIR, step_file)


def _import_or_copy(part_id, step_file, target_comp):
    """Import STEP once per (component, part_id), copy for additional uses.

    First call imports the STEP into target_comp as a hidden template.
    All calls (including first) return a copyPasteBodies copy.
    Template stays at origin, hidden. With mirror-based pair install,
    only 1 hinge + 1 screw STEP import per component.
    """
    global _comp_step_cache
    design = adsk.fusion.Design.cast(
        adsk.core.Application.get().activeProduct)
    key = (id(design), id(target_comp), part_id)

    # Check for valid cached template
    if key in _comp_step_cache:
        tmpl_occ = _comp_step_cache[key]
        if tmpl_occ.isValid:
            return _copy_from_template(tmpl_occ, target_comp)
        del _comp_step_cache[key]

    # First import — hidden template inside target_comp
    imported = import_step(step_file, target_comp)
    if not imported:
        return []
    tmpl_occ = imported[0][0]
    tmpl_occ.isLightBulbOn = False
    # Also hide individual bodies (isLightBulbOn can be unreliable
    # across different occurrence reference objects)
    for i in range(tmpl_occ.component.bRepBodies.count):
        tmpl_occ.component.bRepBodies.item(i).isVisible = False
    _comp_step_cache[key] = tmpl_occ
    _hardware_occurrences.append((tmpl_occ, target_comp))

    # Return a copy (template stays unmoved at origin for future copies)
    return _copy_from_template(tmpl_occ, target_comp)


def _copy_from_template(tmpl_occ, target_comp):
    """Copy bodies from a cached occurrence via copyPasteBodies."""
    tmpl_comp = tmpl_occ.component
    new_occ = target_comp.occurrences.addNewComponent(Matrix3D.create())
    new_comp = new_occ.component
    new_comp.name = tmpl_comp.name

    bodies = []
    for i in range(tmpl_comp.bRepBodies.count):
        src = tmpl_comp.bRepBodies.item(i)
        coll = adsk.core.ObjectCollection.create()
        coll.add(src)
        paste = new_comp.features.copyPasteBodies.add(coll)
        for j in range(paste.bodies.count):
            b = paste.bodies.item(j)
            b.name = src.name
            bodies.append(b)

    return [(new_occ, bodies)]


# ── Body Classification ──────────────────────────────────────────────

def _classify_hinge_bodies(bodies):
    """Classify imported hinge bodies into pin and leaves.

    Pin = smallest volume. Leaves sorted by Z midpoint (a=+Z, b=-Z).
    """
    if len(bodies) < 2:
        raise ValueError(f"Expected 2+ hinge bodies, got {len(bodies)}")
    sorted_bodies = sorted(bodies, key=lambda b: b.volume)
    pin_body = sorted_bodies[0]
    leaf_bodies = sorted_bodies[1:]

    def z_mid(b):
        bb = b.boundingBox
        return (bb.maxPoint.z + bb.minPoint.z) / 2
    leaf_bodies.sort(key=z_mid, reverse=True)
    return pin_body, leaf_bodies


# ── Plate Thickness ──────────────────────────────────────────────────

def _plate_thickness_cm(leaf_body):
    """Measure the flat plate thickness from STEP leaf geometry.

    The leaf body includes both the flat plate and knuckle barrels.
    The plate's two flat faces are the only planar faces with normal
    along Y (the thin direction in STEP reference frame).
    Returns the distance between them = plate thickness.
    """
    y_vals = set()
    for fi in range(leaf_body.faces.count):
        face = leaf_body.faces.item(fi)
        geom = face.geometry
        if hasattr(geom, 'normal') and abs(geom.normal.y) > 0.9:
            y_vals.add(round(geom.origin.y, 6))
    if len(y_vals) >= 2:
        return max(y_vals) - min(y_vals)
    # Fallback: use bounding box thin extent
    bb = leaf_body.boundingBox
    extents = [bb.maxPoint.x - bb.minPoint.x,
               bb.maxPoint.y - bb.minPoint.y,
               bb.maxPoint.z - bb.minPoint.z]
    return min(extents)


# ── Style Rotation ───────────────────────────────────────────────────

def _build_rotation(style):
    """Rotation for standard-frame assembly STEPs.

    Standard frame: pin along X, leaves in XZ plane, thin in Y, at origin.

    After rotation for each style:
      lid_surface  — pin X, leaves XZ, thin Y (identity)
      lid_flush    — pin X, leaves XY, thin Z (R_x +90°)
      door_surface — pin Z, leaves YZ, thin X (R_y -90° then R_z -90°)
      door_flush   — pin Z, leaves YZ, thin X (same rotation as door_surface;
                     fold closes leaf_b onto leaf_a afterward)

    Door styles use R_z(-90°) so leaf_a extends in +Y (into the side/case)
    and leaf_b extends in -Y (into the door). Folding then puts both at +Y.
    """
    mat = Matrix3D.create()
    if style == "lid_surface":
        pass  # pin horizontal, leaves on back face (XZ)
    elif style == "lid_flush":
        # Rotate 90° around X → leaves go from XZ to XY (horizontal)
        mat.setToRotation(math.pi / 2, Vector3D.create(1, 0, 0),
                          Point3D.create(0, 0, 0))
    elif style == "door_surface":
        # Rotate -90° around Y (pin vertical), then -180° around Z
        # → leaves extend in ±X (along boards), thin in Y (flat on seam)
        ry = Matrix3D.create()
        ry.setToRotation(-math.pi / 2, Vector3D.create(0, 1, 0),
                         Point3D.create(0, 0, 0))
        rz = Matrix3D.create()
        rz.setToRotation(-math.pi, Vector3D.create(0, 0, 1),
                         Point3D.create(0, 0, 0))
        ry.transformBy(rz)
        mat = ry
    elif style == "door_flush":
        # Rotate -90° around Y (pin vertical), then -90° around Z
        # → leaves extend in ±Y (into door/side), thin in X
        ry = Matrix3D.create()
        ry.setToRotation(-math.pi / 2, Vector3D.create(0, 1, 0),
                         Point3D.create(0, 0, 0))
        rz = Matrix3D.create()
        rz.setToRotation(-math.pi / 2, Vector3D.create(0, 0, 1),
                         Point3D.create(0, 0, 0))
        ry.transformBy(rz)
        mat = ry
    else:
        raise ValueError(f"Unknown hinge style: {style!r}")
    return mat


def _make_body_proxy(body, top_occ, body_occ_map=None):
    """Create a proxy for a body using its pre-computed occurrence mapping.

    body_occ_map maps entityToken -> full-path occurrence (since Fusion
    returns different Python wrappers for the same body, id() is unstable).
    """
    if top_occ is None:
        return body
    if body_occ_map:
        token = body.entityToken
        occ_for_body = body_occ_map.get(token)
        if occ_for_body:
            return body.createForAssemblyContext(occ_for_body)
    return body.createForAssemblyContext(top_occ)


def _hinge_combined_bbox(occ, bodies, body_occ_map=None):
    """Combined bounding box of all hinge bodies (leaves + pin + screws).

    Returns a BoundingBox3D-like object with min/max points covering all bodies.
    Used for rebate pocket sizing so the pocket clears the full barrel.
    """
    min_x = min_y = min_z = 1e10
    max_x = max_y = max_z = -1e10
    for b in bodies:
        bb = _leaf_proxy_bbox(occ, b, body_occ_map)
        min_x = min(min_x, bb.minPoint.x)
        min_y = min(min_y, bb.minPoint.y)
        min_z = min(min_z, bb.minPoint.z)
        max_x = max(max_x, bb.maxPoint.x)
        max_y = max(max_y, bb.maxPoint.y)
        max_z = max(max_z, bb.maxPoint.z)

    # Return as a simple namespace with minPoint/maxPoint
    class _BB:
        pass
    class _Pt:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z
    result = _BB()
    result.minPoint = _Pt(min_x, min_y, min_z)
    result.maxPoint = _Pt(max_x, max_y, max_z)
    return result


def _leaf_proxy_bbox(occ, leaf_body, body_occ_map=None):
    if occ is not None:
        proxy = _make_body_proxy(leaf_body, occ, body_occ_map)
        return proxy.boundingBox
    return leaf_body.boundingBox


# ── Rebate Cutting ───────────────────────────────────────────────────

def _recess_hinge(comp, occ, bodies, direction, distance_cm, name,
                  body_occ_map=None):
    """Move all hinge bodies into the rebate pockets."""
    if occ is None:
        return None
    coll = adsk.core.ObjectCollection.create()
    for b in bodies:
        proxy = _make_body_proxy(b, occ, body_occ_map)
        coll.add(proxy)
    if coll.count == 0:
        return None
    mat = Matrix3D.create()
    mat.translation = Vector3D.create(
        direction.x * distance_cm,
        direction.y * distance_cm,
        direction.z * distance_cm)
    move_input = comp.features.moveFeatures.createInput2(coll)
    move_input.defineAsFreeMove(mat)
    feat = comp.features.moveFeatures.add(move_input)
    feat.name = f"{name}_Recess"
    return feat


def _fold_leaf_closed(comp, occ, leaf_bodies, pin_axis_world, pin_center,
                      body_occ_map=None):
    """Fold leaf_b 180 around the pin axis to close the hinge."""
    coll = adsk.core.ObjectCollection.create()
    for b in leaf_bodies:
        proxy = _make_body_proxy(b, occ, body_occ_map)
        coll.add(proxy)
    if coll.count == 0:
        return None
    fold = Matrix3D.create()
    fold.setToRotation(math.pi, pin_axis_world, pin_center)
    move_input = comp.features.moveFeatures.createInput2(coll)
    move_input.defineAsFreeMove(fold)
    feat = comp.features.moveFeatures.add(move_input)
    feat.name = "Fold_Close"
    return feat


def _door_flush_rebate_depths(gap_cm, barrel_d_cm, plate_t_cm):
    """Compute rebate depths for door_flush based on gap-to-hinge ratio.

    Returns (rebate_a, rebate_b) where:
      rebate_a = depth into door (board_a)
      rebate_b = depth into case side (board_b)

    Cases:
      gap > barrel_d  → ValueError
      gap ≈ barrel_d  → (0, 0) — surface mount, no rebate
      barrel_d - plate_t ≤ gap < barrel_d → (0, barrel_d - gap) — one-side (case only)
      gap < barrel_d - plate_t → symmetric split into both boards
    """
    tol = 0.001  # 10µm

    if gap_cm > barrel_d_cm + tol:
        raise ValueError(
            f"Gap ({gap_cm:.4f} cm) exceeds barrel diameter "
            f"({barrel_d_cm:.4f} cm). Use a smaller gap or larger hinge.")

    if gap_cm >= barrel_d_cm - tol:
        return 0.0, 0.0  # No rebate

    if gap_cm >= barrel_d_cm - plate_t_cm - tol:
        return 0.0, barrel_d_cm - gap_cm  # One-side (case only)

    # Two-side: symmetric split
    excess = barrel_d_cm - gap_cm
    half = excess / 2
    return half, half


def _sketch_rebate_pocket(comp, plane, origin_yz, size_yz, depth_cm,
                          board, name, ev, flip, margin=0.02):
    """Cut an oversized rectangular rebate pocket into a board.

    Uses sketch+extrude (fast) with a small margin to clear barrel
    knuckle geometry that extends beyond the leaf plate bounding box.

    Args:
        plane: Construction plane for the sketch (at the board face)
        origin_yz: (y, z) model-space origin of the pocket
        size_yz: (y_size, z_size) pocket dimensions
        depth_cm: Pocket depth in cm (+ margin is added automatically)
        board: Target board body
        flip: True for CUT into -X, False for +X
        margin: Extra depth/size added for barrel clearance (cm)
    """
    from helpers import sp
    cuts = []
    y0, z0 = origin_yz
    yw, zh = size_yz
    # Oversized pocket: margin on all sides + depth
    sk, pr = sp.sketch_rect_model(comp, plane,
        (0, y0 - margin, z0 - margin),  # X is ignored (on-plane)
        {"y": yw + 2 * margin, "z": zh + 2 * margin},
        f"{name}_Sk", ev)
    feat = sp.ext_op(comp, pr, f"{depth_cm + margin} cm", CUT, board,
                     f"{name}", flip=flip)
    sk.isVisible = False
    if feat:
        cuts.append(feat)
    return cuts


def _cut_rebates(comp, style, occ, leaf_a, leaf_b, bodies,
                 board_a, board_b, pos, raw_pos,
                 plate_t_cm, barrel_d_cm, barrel_d_str, name, ev, gap_cm=0,
                 body_occ_map=None):
    """Cut rebate pockets into boards for hinge installation.

    Uses oversized sketch-based rectangular pockets for performance.
    A small margin (0.02 cm = 0.2 mm) is added beyond the combined
    hinge bounding box to clear barrel knuckle geometry.

    lid_surface  — sketch rebate both boards, then recess hinge
    lid_flush    — sketch rebate both boards
    door_surface — body-CUT mortise (hinge visible, exact fit desired)
    door_flush   — sketch rebate based on gap logic
    """
    from helpers import sp
    cuts = []

    def _offset_expr(idx):
        v = raw_pos[idx]
        return v if isinstance(v, str) else f"{pos[idx]} cm"

    if style == "lid_surface":
        # Sketch rebates on back face plane (XZ at Y = pin_pos[1])
        cut_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                              _offset_expr(1), f"{name}_CutPl")
        cut_pl.isLightBulbOn = False

        hinge_bb = _hinge_combined_bbox(occ, bodies, body_occ_map)

        for board, sfx, flip in [(board_a, "A", True), (board_b, "B", True)]:
            sk, pr = sp.sketch_rect_model(comp, cut_pl,
                (hinge_bb.minPoint.x - 0.02, pos[1],
                 hinge_bb.minPoint.z - 0.02),
                {"x": (hinge_bb.maxPoint.x - hinge_bb.minPoint.x) + 0.04,
                 "z": (hinge_bb.maxPoint.z - hinge_bb.minPoint.z) + 0.04},
                f"{name}_Reb{sfx}_Sk", ev)
            feat = sp.ext_op(comp, pr, f"{plate_t_cm + 0.02} cm", CUT,
                             board, f"{name}_Reb{sfx}", flip=flip)
            sk.isVisible = False
            if feat:
                cuts.append(feat)

        # Recess hinge into pockets by plate thickness
        recess = _recess_hinge(comp, occ, bodies,
                               Vector3D.create(0, -1, 0),
                               plate_t_cm, name,
                               body_occ_map=body_occ_map)
        if recess:
            cuts.append(recess)

    elif style == "lid_flush":
        # Seam plane at Z = joint_line
        cut_pl = sp.off_plane(comp, comp.xYConstructionPlane,
                              _offset_expr(2), f"{name}_CutPl")
        cut_pl.isLightBulbOn = False

        hinge_bb = _hinge_combined_bbox(occ, bodies, body_occ_map)
        barrel_r = max(abs(hinge_bb.maxPoint.z - pos[2]),
                       abs(hinge_bb.minPoint.z - pos[2]))

        for board, sfx, flip in [(board_a, "A", False), (board_b, "B", True)]:
            sk, pr = sp.sketch_rect_model(comp, cut_pl,
                (hinge_bb.minPoint.x - 0.02,
                 hinge_bb.minPoint.y - 0.02, pos[2]),
                {"x": (hinge_bb.maxPoint.x - hinge_bb.minPoint.x) + 0.04,
                 "y": (hinge_bb.maxPoint.y - hinge_bb.minPoint.y) + 0.04},
                f"{name}_Reb{sfx}_Sk", ev)
            feat = sp.ext_op(comp, pr, f"{barrel_r + 0.02} cm", CUT,
                             board, f"{name}_Reb{sfx}", flip=flip)
            sk.isVisible = False
            if feat:
                cuts.append(feat)

    elif style == "door_surface":
        # Body-CUT mortise into both boards (hinge visible, exact fit)
        for b in bodies:
            proxy = _make_body_proxy(b, occ, body_occ_map) if occ else b
            for board in [board_b, board_a]:
                try:
                    c = sp.combine(board, [proxy], CUT, True,
                                   f"{name}_Cut_{board.name}_{b.name}")
                    if c:
                        cuts.append(c)
                except Exception:
                    pass

    elif style == "door_flush":
        # Per-leaf bboxes from the already-positioned, folded hinge
        bb_a = _leaf_proxy_bbox(occ, leaf_a, body_occ_map)
        bb_b = _leaf_proxy_bbox(occ, leaf_b, body_occ_map)

        # Detect door side: is door (board_a) at +X or -X of pin?
        door_bb = board_a.boundingBox
        door_cx = (door_bb.minPoint.x + door_bb.maxPoint.x) / 2
        door_at_plus_x = door_cx > pos[0]

        # Compute rebate depth from actual leaf overlap with each board.
        # How far each leaf extends past the board face into the board.
        if door_at_plus_x:
            depth_b = max(pos[0] - bb_b.minPoint.x, 0)   # leaf into -X
            depth_a = max(bb_a.maxPoint.x - (pos[0] + gap_cm), 0)  # leaf into +X
        else:
            depth_b = max(bb_b.maxPoint.x - pos[0], 0)    # leaf into +X
            depth_a = max((pos[0] - gap_cm) - bb_a.minPoint.x, 0)  # leaf into -X

        def _open_mortise_yz(leaf_bb, board):
            """Pocket sized to leaf, extended to nearest board edge."""
            brd_bb = board.boundingBox
            leaf_cy = (leaf_bb.minPoint.y + leaf_bb.maxPoint.y) / 2
            if abs(leaf_cy - brd_bb.minPoint.y) < abs(leaf_cy - brd_bb.maxPoint.y):
                y_min = brd_bb.minPoint.y      # open at near edge
                y_max = leaf_bb.maxPoint.y
            else:
                y_min = leaf_bb.minPoint.y
                y_max = brd_bb.maxPoint.y       # open at near edge
            return (y_min, leaf_bb.minPoint.z,
                    y_max - y_min, leaf_bb.maxPoint.z - leaf_bb.minPoint.z)

        # Case side rebate (leaf_b → board_b)
        if depth_b > 0.001:
            cut_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                                  _offset_expr(0), f"{name}_CutPl")
            cut_pl.isLightBulbOn = False
            py, pz, pyw, pzh = _open_mortise_yz(bb_b, board_b)
            cuts.extend(_sketch_rebate_pocket(
                comp, cut_pl, (py, pz), (pyw, pzh), depth_b,
                board_b, f"{name}_RebB", ev,
                flip=door_at_plus_x, margin=0))

        # Door rebate (leaf_a → board_a)
        if depth_a > 0.001:
            gap_sign = 1 if door_at_plus_x else -1
            if gap_cm > 0.001:
                door_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                                       f"{pos[0] + gap_sign * gap_cm} cm",
                                       f"{name}_DoorPl")
                door_pl.isLightBulbOn = False
            else:
                door_pl = cut_pl  # reuse case side plane
            py, pz, pyw, pzh = _open_mortise_yz(bb_a, board_a)
            cuts.extend(_sketch_rebate_pocket(
                comp, door_pl, (py, pz), (pyw, pzh), depth_a,
                board_a, f"{name}_RebA", ev,
                flip=not door_at_plus_x, margin=0))

    return cuts


# ── Screw Installation ──────────────────────────────────────────────

def _screw_into_board_dir(occ, leaf_body, board_body):
    """Compute direction from leaf surface into the board (for screw tip)."""
    proxy = leaf_body.createForAssemblyContext(occ)
    bb = proxy.boundingBox
    extents = [bb.maxPoint.x - bb.minPoint.x,
               bb.maxPoint.y - bb.minPoint.y,
               bb.maxPoint.z - bb.minPoint.z]
    thin_idx = extents.index(min(extents))
    leaf_mid = [(bb.minPoint.x + bb.maxPoint.x) / 2,
                (bb.minPoint.y + bb.maxPoint.y) / 2,
                (bb.minPoint.z + bb.maxPoint.z) / 2]
    bbb = board_body.boundingBox
    board_mid = [(bbb.minPoint.x + bbb.maxPoint.x) / 2,
                 (bbb.minPoint.y + bbb.maxPoint.y) / 2,
                 (bbb.minPoint.z + bbb.maxPoint.z) / 2]
    delta = board_mid[thin_idx] - leaf_mid[thin_idx]
    sign = 1.0 if delta >= 0 else -1.0
    vec = [0.0, 0.0, 0.0]
    vec[thin_idx] = sign
    return Vector3D.create(*vec)


def _find_screw_holes(occ, leaf_body, target_d_cm=None, tol=0.02):
    """Find screw hole positions from leaf geometry.

    Filters cylindrical faces by thin-direction axis alignment,
    picks smallest diameter set, groups by proximity.
    """
    proxy = leaf_body.createForAssemblyContext(occ)
    bb = proxy.boundingBox
    extents = [bb.maxPoint.x - bb.minPoint.x,
               bb.maxPoint.y - bb.minPoint.y,
               bb.maxPoint.z - bb.minPoint.z]
    thin_idx = extents.index(min(extents))
    axis_vecs = [Vector3D.create(1, 0, 0), Vector3D.create(0, 1, 0),
                 Vector3D.create(0, 0, 1)]
    thin_dir = axis_vecs[thin_idx]

    through_holes = []
    for fi in range(proxy.faces.count):
        face = proxy.faces.item(fi)
        geom = face.geometry
        if not hasattr(geom, 'radius'):
            continue
        dot = abs(geom.axis.x * thin_dir.x +
                  geom.axis.y * thin_dir.y +
                  geom.axis.z * thin_dir.z)
        if dot < 0.9:
            continue
        d = geom.radius * 2
        through_holes.append((geom.origin.copy(), geom.axis.copy(), d))

    if not through_holes:
        return []

    if target_d_cm:
        filtered = [(o, a) for o, a, d in through_holes
                     if abs(d - target_d_cm) < tol]
    else:
        min_d = min(d for _, _, d in through_holes)
        filtered = [(o, a) for o, a, d in through_holes
                     if abs(d - min_d) < tol]
    if not filtered:
        min_d = min(d for _, _, d in through_holes)
        filtered = [(o, a) for o, a, d in through_holes
                     if abs(d - min_d) < tol]

    groups = []
    group_tol = min(extents) * 2 if min(extents) > 0.01 else 0.5
    for center, axis in filtered:
        merged = False
        for g in groups:
            ref = g[0][0]
            dist = ((center.x - ref.x)**2 + (center.y - ref.y)**2 +
                    (center.z - ref.z)**2) ** 0.5
            if dist < group_tol:
                g.append((center, axis))
                merged = True
                break
        if not merged:
            groups.append([(center, axis)])

    result = []
    for g in groups:
        avg_x = sum(c.x for c, _ in g) / len(g)
        avg_y = sum(c.y for c, _ in g) / len(g)
        avg_z = sum(c.z for c, _ in g) / len(g)
        result.append((Point3D.create(avg_x, avg_y, avg_z), g[0][1]))
    return result


def install_hinge_screws(hinge_result, comp, ev=None, name="Screw",
                         leaf_boards=None):
    """Install screws into a positioned hinge's screw holes.

    Imports a screw STEP for each hole, positions it so the head is
    flush with the outer leaf surface, and CUTs a countersink pocket
    into the lesp.

    Args:
        hinge_result: Dict from install_butt_hinge().
        comp: Component.
        ev: Evaluator.
        name: Name prefix.
        leaf_boards: Dict {id(leaf) -> board_body} for screw direction.
    """
    from helpers import sp

    part = hinge_result["part"]
    screw_id = part.get("screw")
    if not screw_id:
        return []
    screw_part = get_part(screw_id)
    if screw_part is None:
        return []
    dims = part.get("dimensions", {})
    hole_d_str = dims.get("screw_hole_diameter")
    if not hole_d_str:
        return []

    design = adsk.fusion.Design.cast(
        adsk.core.Application.get().activeProduct)
    hole_d_cm = design.unitsManager.evaluateExpression(hole_d_str, "cm")

    screw_step = _resolve_step_path(screw_part["step_file"])
    occ = hinge_result["occurrence"]
    leaf_bodies = hinge_result["leaves"]
    plate_t_cm = hinge_result.get("plate_t_cm", 0.0635)

    results = []
    screw_idx = 0

    for leaf in leaf_bodies:
        holes = _find_screw_holes(occ, leaf, hole_d_cm)

        into_board = None
        if leaf_boards and id(leaf) in leaf_boards:
            board = leaf_boards[id(leaf)]
            if board is not None:
                into_board = _screw_into_board_dir(occ, leaf, board)

        for hole_center, hole_axis in holes:
            # Direct STEP import — each screw is a clean occurrence
            imported = import_step(screw_step, comp)
            if not imported:
                continue
            screw_occ, screw_bodies = imported[0]

            screw_dir = into_board.copy() if into_board else hole_axis.copy()

            screw_bb = screw_bodies[0].boundingBox
            head_x = screw_bb.minPoint.x
            half_plate = plate_t_cm / 2
            delta = -half_plate - head_x

            adjusted = Point3D.create(
                hole_center.x + delta * screw_dir.x,
                hole_center.y + delta * screw_dir.y,
                hole_center.z + delta * screw_dir.z)

            screw_x = Vector3D.create(1, 0, 0)
            rotation = Matrix3D.create()
            cross = screw_x.crossProduct(screw_dir)
            dot = screw_x.dotProduct(screw_dir)
            if cross.length > 1e-6:
                angle = math.acos(max(-1, min(1, dot)))
                rotation.setToRotation(angle, cross, Point3D.create(0, 0, 0))
            elif dot < 0:
                rotation.setToRotation(math.pi, Vector3D.create(0, 1, 0),
                                       Point3D.create(0, 0, 0))

            transform = Matrix3D.create()
            transform.transformBy(rotation)
            translate = Matrix3D.create()
            translate.translation = Vector3D.create(
                adjusted.x, adjusted.y, adjusted.z)
            transform.transformBy(translate)

            screw_name = f"{name}_{screw_idx}"
            _move_occurrence(comp, screw_occ, transform, screw_name)
            screw_occ.component.name = screw_name

            # CUT countersink into leaf
            leaf_proxy = lesp.createForAssemblyContext(occ)
            for sb in screw_bodies:
                screw_proxy = sb.createForAssemblyContext(screw_occ)
                try:
                    sp.combine(leaf_proxy, [screw_proxy], CUT, True,
                               f"{screw_name}_CSink")
                except Exception:
                    pass

            screw_idx += 1
            results.append({
                "occurrence": screw_occ,
                "bodies": screw_bodies,
            })

    return results


# ── Positioning ──────────────────────────────────────────────────────

def _build_transform(position, anchor):
    mat = Matrix3D.create()
    anchor_origin = anchor.get("origin", [0, 0, 0])
    dx = position[0] - anchor_origin[0]
    dy = position[1] - anchor_origin[1]
    dz = position[2] - anchor_origin[2]
    mat.translation = Vector3D.create(dx, dy, dz)
    return mat


def _move_occurrence(comp, occ, transform, name="HW"):
    """Move all bodies in an occurrence (including nested child occurrences)."""
    coll = adsk.core.ObjectCollection.create()
    _collect_all_body_proxies(comp, occ, coll)
    if coll.count == 0:
        return None
    move_input = comp.features.moveFeatures.createInput2(coll)
    move_input.defineAsFreeMove(transform)
    feat = comp.features.moveFeatures.add(move_input)
    feat.name = f"{name}_Move"
    return feat


def _collect_all_body_proxies(comp, top_occ, coll):
    """Collect body proxies for all bodies in an occurrence tree.

    Uses comp.allOccurrences to get full-path occurrences (relative to comp)
    that can create valid proxies.
    """
    # Bodies directly in the top occurrence's component
    top_comp = top_occ.component
    for i in range(top_comp.bRepBodies.count):
        body = top_comp.bRepBodies.item(i)
        proxy = body.createForAssemblyContext(top_occ)
        coll.add(proxy)

    # Get local name of top_occ within comp
    parts = top_occ.fullPathName.split("+")
    local_name = parts[-1]

    # Bodies in nested child occurrences
    all_occs = comp.allOccurrences
    for i in range(all_occs.count):
        full_occ = all_occs.item(i)
        fp = full_occ.fullPathName
        if fp.startswith(local_name + "+"):
            child_comp = full_occ.component
            for j in range(child_comp.bRepBodies.count):
                body = child_comp.bRepBodies.item(j)
                proxy = body.createForAssemblyContext(full_occ)
                coll.add(proxy)


# ── Install (high-level) ─────────────────────────────────────────────

def _import_assembly(part_id, part, comp, bare=False):
    """Import a hinge assembly STEP (Pin + LeafA + LeafB sub-components).

    Returns (top_occ, child_occs, pin_bodies, leaf_a_bodies,
             leaf_b_bodies, all_bodies, body_occ_map).
    Falls back to bare hinge STEP if no assembly_step in catalog.
    When bare=True, forces the simple STEP (no screws, fewer bodies).
    """
    assembly_path = part.get("assembly_step") if not bare else None
    if assembly_path:
        step_file = _resolve_step_path(assembly_path)
    else:
        step_file = _resolve_step_path(part["step_file"])

    imported = import_step(step_file, comp)
    if not imported:
        raise RuntimeError(f"No geometry imported from {step_file}")

    top_occ = imported[0][0]
    top_comp = top_occ.component

    # If it's an assembly STEP, it has child occurrences named Pin/LeafA/LeafB
    pin_bodies = []
    leaf_a_bodies = []
    leaf_b_bodies = []
    child_occs = {}

    for i in range(top_comp.occurrences.count):
        child = top_comp.occurrences.item(i)
        cname = child.component.name
        # Fusion appends " (N)" to duplicate component names — match by prefix
        if cname.startswith("Pin"):
            key = "Pin"
        elif cname.startswith("LeafA"):
            key = "LeafA"
        elif cname.startswith("LeafB"):
            key = "LeafB"
        else:
            key = cname
        child_occs[key] = child
        child_comp = child.component
        for j in range(child_comp.bRepBodies.count):
            b = child_comp.bRepBodies.item(j)
            if key == "Pin":
                pin_bodies.append(b)
            elif key == "LeafA":
                leaf_a_bodies.append(b)
            elif key == "LeafB":
                leaf_b_bodies.append(b)

    if leaf_a_bodies and leaf_b_bodies:
        # Assembly STEP with sub-components — build body→full_path_occ map
        all_bodies = pin_bodies + leaf_a_bodies + leaf_b_bodies
        body_occ_map = _build_body_occ_map(comp, top_occ)
        return (top_occ, child_occs, pin_bodies, leaf_a_bodies,
                leaf_b_bodies, all_bodies, body_occ_map)

    # Flat assembly or bare hinge — bodies directly in top component
    all_bodies = []
    for i in range(top_comp.bRepBodies.count):
        all_bodies.append(top_comp.bRepBodies.item(i))

    if not all_bodies:
        all_bodies = imported[0][1]

    # Classify flat assembly bodies by volume and geometry.
    # Assembly has 3 distinct hinge bodies (2 leaves = largest, 1 pin = medium)
    # plus optional screws (smallest, often identical volumes).
    # Separate screws from hinge parts using volume clustering.
    sorted_by_vol = sorted(all_bodies, key=lambda b: b.volume, reverse=True)
    volumes = [b.volume for b in sorted_by_vol]

    # Find the 3 hinge bodies: 2 leaves (largest) + 1 pin (next largest)
    # Screws are significantly smaller than the pin.
    if len(all_bodies) >= 3:
        # Leaves = 2 largest, pin = 3rd largest, rest = screws
        leaf_candidates = sorted_by_vol[:2]
        pin_body = sorted_by_vol[2]
        screw_bodies = sorted_by_vol[3:]

        # Sort leaves by Z midpoint: a = +Z side, b = -Z side
        def z_mid(b):
            bb = b.boundingBox
            return (bb.maxPoint.z + bb.minPoint.z) / 2
        leaf_candidates.sort(key=z_mid, reverse=True)

        leaf_a_bodies = [leaf_candidates[0]]
        leaf_b_bodies = [leaf_candidates[1]]
        pin_bodies = [pin_body]

        # Assign screws to leaf_a (+Z) or leaf_b (-Z) by Z midpoint
        for s in screw_bodies:
            if z_mid(s) > 0:
                leaf_a_bodies.append(s)
            else:
                leaf_b_bodies.append(s)

        all_bodies_ordered = pin_bodies + leaf_a_bodies + leaf_b_bodies
        body_occ_map = {b.entityToken: top_occ for b in all_bodies}
        return (top_occ, {}, pin_bodies, leaf_a_bodies,
                leaf_b_bodies, all_bodies_ordered, body_occ_map)

    # Fallback: bare hinge STEP (< 3 bodies)
    pin_body, leaf_bodies = _classify_hinge_bodies(all_bodies)
    leaf_a_bodies = [leaf_bodies[0]]
    leaf_b_bodies = [leaf_bodies[1]] if len(leaf_bodies) > 1 else []
    pin_bodies = [pin_body]
    body_occ_map = {b.entityToken: top_occ for b in all_bodies}
    return (top_occ, {}, pin_bodies, leaf_a_bodies,
            leaf_b_bodies, all_bodies, body_occ_map)


def _build_body_occ_map(comp, top_occ):
    """Build mapping: entityToken -> full-path occurrence for proxy creation.

    Uses entityToken as key since Fusion returns different Python wrappers
    for the same underlying body (id() is unstable across calls).

    comp.allOccurrences returns paths relative to comp, so the top_occ
    local name (e.g. "_ExportTemp:1") is used for prefix matching.
    """
    body_map = {}
    top_comp = top_occ.component

    # Direct bodies in top component
    for i in range(top_comp.bRepBodies.count):
        b = top_comp.bRepBodies.item(i)
        body_map[b.entityToken] = top_occ

    # Get the local name of top_occ within comp (strip parent path)
    top_full = top_occ.fullPathName
    # fullPathName may be "S1:1+_ExportTemp:1" — we need just "_ExportTemp:1"
    parts = top_full.split("+")
    local_name = parts[-1]  # last segment = local occurrence name

    # Bodies in child occurrences — find via local-path matching
    all_occs = comp.allOccurrences
    for i in range(all_occs.count):
        full_occ = all_occs.item(i)
        fp = full_occ.fullPathName  # relative to comp, e.g. "_ExportTemp:1+Pin:1"
        if fp.startswith(local_name + "+"):
            child_comp = full_occ.component
            for j in range(child_comp.bRepBodies.count):
                body = child_comp.bRepBodies.item(j)
                body_map[body.entityToken] = full_occ

    return body_map


def install_butt_hinge(part_id, comp, back_body=None, lid_body=None,
                       pin_position=None, pin_axis="x",
                       style="lid_surface",
                       door_body=None, case_body=None,
                       gap=0, install_screws=False,
                       bare=False,
                       ev=None, name="Hinge"):
    """Install a butt hinge with integrated rebate CUTs.

    Imports the assembly STEP (hinge + screws as Pin/LeafA/LeafB
    sub-components), positions, folds (flush styles), and cuts
    rebate pockets. Screws are included in the assembly and move
    with their leaf during folding.

    install_screws parameter is accepted for backward compatibility
    but ignored — screws are always included via the assembly STEP.
    """
    if style not in VALID_STYLES:
        raise ValueError(f"Unknown style: {style!r}. Valid: {VALID_STYLES}")

    part = get_part(part_id)
    if part is None:
        raise ValueError(f"Part '{part_id}' not found in catalog.")

    dims = part.get("dimensions", {})
    anchor = part.get("anchor", {"origin": [0, 0, 0]})

    raw_pos = list(pin_position)
    pos = []
    for p in pin_position:
        if isinstance(p, str):
            pos.append(ev(p) if ev else 0)
        else:
            pos.append(p)

    barrel_d_str = dims.get("leaf_thickness", "0.050 in")
    barrel_d_cm = ev(barrel_d_str) if ev else 0.127

    # ── Early gap validation (before STEP import) ──
    if style == "door_flush" and gap:
        gap_cm_val = ev(gap) if isinstance(gap, str) and ev else float(gap)
        if gap_cm_val > barrel_d_cm + 0.001:
            raise ValueError(
                f"Gap ({gap_cm_val:.4f} cm) exceeds barrel diameter "
                f"({barrel_d_cm:.4f} cm). Use a smaller gap or larger hinge.")

    # ── Import assembly STEP ──
    (top_occ, child_occs, pin_bodies, leaf_a_bodies, leaf_b_bodies,
     all_bodies, body_occ_map) = _import_assembly(part_id, part, comp,
                                                   bare=bare)

    # Leaf body = largest body in each leaf sub-component
    leaf_a = max(leaf_a_bodies, key=lambda b: b.volume)
    leaf_b = max(leaf_b_bodies, key=lambda b: b.volume) if leaf_b_bodies else None
    leaf_bodies = [leaf_a] + ([leaf_b] if leaf_b else [])

    # Measure actual plate thickness from STEP geometry
    plate_t_cm = _plate_thickness_cm(leaf_a)

    # ── Build rotation + translation transform ──
    # Assembly STEPs are at origin: pin along X, leaves in XZ, thin in Y.
    rotation = _build_rotation(style)
    is_surface = style in ("lid_surface",)

    thin_dir = Vector3D.create(0, 1, 0)
    thin_dir.transformBy(rotation)

    leaf_bb = leaf_a.boundingBox
    leaf_min_y = leaf_bb.minPoint.y  # inner face Y in STEP frame

    if is_surface:
        surface_offset_cm = -leaf_min_y
    else:
        surface_offset_cm = 0

    # For door_flush with gap: shift hinge toward the door so barrel
    # splits correctly between door and case side.
    if style == "door_flush" and gap:
        gap_cm_val = ev(gap) if isinstance(gap, str) and ev else float(gap)
        _, rebate_b_cm = _door_flush_rebate_depths(
            gap_cm_val, barrel_d_cm, plate_t_cm)
        surface_offset_cm = barrel_d_cm / 2 - rebate_b_cm
        # Flip offset direction if door is at -X of pin (right-side hinge)
        if door_body is not None:
            door_bb = door_body.boundingBox
            door_cx = (door_bb.minPoint.x + door_bb.maxPoint.x) / 2
            if door_cx < pos[0]:
                surface_offset_cm = -surface_offset_cm

    anchor_origin = anchor.get("origin", [0, 0, 0])

    transform = Matrix3D.create()
    transform.transformBy(rotation)
    translate = Matrix3D.create()
    translate.translation = Vector3D.create(
        pos[0] - anchor_origin[0] + thin_dir.x * surface_offset_cm,
        pos[1] - anchor_origin[1] + thin_dir.y * surface_offset_cm,
        pos[2] - anchor_origin[2] + thin_dir.z * surface_offset_cm)
    transform.transformBy(translate)

    _move_occurrence(comp, top_occ, transform, name)
    top_occ.component.name = name
    _hardware_occurrences.append((top_occ, comp))

    # ── Flush styles: fold leaf_b closed (all bodies in LeafB move together) ──
    if not is_surface and leaf_b_bodies:
        pin_dir = Vector3D.create(1, 0, 0)
        pin_dir.transformBy(rotation)
        pin_center = Point3D.create(
            pos[0] + thin_dir.x * surface_offset_cm,
            pos[1] + thin_dir.y * surface_offset_cm,
            pos[2] + thin_dir.z * surface_offset_cm)
        # Fold ALL bodies in LeafB sub-component (leaf + screws)
        _fold_leaf_closed(comp, top_occ, leaf_b_bodies, pin_dir, pin_center,
                          body_occ_map=body_occ_map)

    # ── Cut rebates into boards ──
    if style.startswith("lid_"):
        board_a, board_b = lid_body, back_body
    else:
        board_a, board_b = door_body, case_body

    gap_cm = 0
    if gap:
        gap_cm = ev(gap) if isinstance(gap, str) and ev else float(gap)

    cuts = []
    if board_a is not None and board_b is not None:
        # Only CUT structural hinge bodies (leaves + pin) — NOT screws.
        # Screw holes are CUT separately below to avoid splitting boards
        # when screw heads extend past the board face.
        structural_bodies = [leaf_a, leaf_b, pin_bodies[0]] if pin_bodies else [leaf_a, leaf_b]
        # Use root for CUTs when target boards are in different components
        # from the hinge import component — root can access all sub-components.
        cut_comp = comp
        if (board_a.parentComponent != comp or board_b.parentComponent != comp):
            design = adsk.fusion.Design.cast(
                adsk.core.Application.get().activeProduct)
            cut_comp = design.rootComponent
        cuts = _cut_rebates(cut_comp, style, top_occ, leaf_a, leaf_b,
                            structural_bodies,
                            board_a, board_b, pos, raw_pos,
                            plate_t_cm, barrel_d_cm, barrel_d_str, name, ev,
                            gap_cm=gap_cm, body_occ_map=body_occ_map)

    # ── Distribute leaf bodies across components ──
    # When boards are in different components, copy the "foreign" leaf
    # into the other board's component so each leaf lives with its board.
    if (board_a is not None and board_b is not None and
            board_a.parentComponent != board_b.parentComponent):
        design = adsk.fusion.Design.cast(
            adsk.core.Application.get().activeProduct)
        root_comp = design.rootComponent

        # Find the full hinge occurrence in the root assembly tree
        full_occ = None
        for i in range(root_comp.allOccurrences.count):
            occ_i = root_comp.allOccurrences.item(i)
            if occ_i.component.name == top_occ.component.name:
                full_occ = occ_i
                break

        if full_occ and len(leaf_bodies) == 2:
            # Identify which leaf is closer to each board
            p0 = leaf_bodies[0].createForAssemblyContext(full_occ)
            p1 = leaf_bodies[1].createForAssemblyContext(full_occ)
            bb_a = board_a.boundingBox
            bb_b = board_b.boundingBox
            a_center = [(bb_a.minPoint.x + bb_a.maxPoint.x) / 2,
                        (bb_a.minPoint.y + bb_a.maxPoint.y) / 2,
                        (bb_a.minPoint.z + bb_a.maxPoint.z) / 2]
            l0_center = [(p0.boundingBox.minPoint.x + p0.boundingBox.maxPoint.x) / 2,
                         (p0.boundingBox.minPoint.y + p0.boundingBox.maxPoint.y) / 2,
                         (p0.boundingBox.minPoint.z + p0.boundingBox.maxPoint.z) / 2]
            l1_center = [(p1.boundingBox.minPoint.x + p1.boundingBox.maxPoint.x) / 2,
                         (p1.boundingBox.minPoint.y + p1.boundingBox.maxPoint.y) / 2,
                         (p1.boundingBox.minPoint.z + p1.boundingBox.maxPoint.z) / 2]
            dist0 = sum((a - b) ** 2 for a, b in zip(l0_center, a_center))
            dist1 = sum((a - b) ** 2 for a, b in zip(l1_center, a_center))

            if dist0 < dist1:
                leaf_for_a, leaf_for_b = leaf_bodies[0], leaf_bodies[1]
            else:
                leaf_for_a, leaf_for_b = leaf_bodies[1], leaf_bodies[0]

            # The hinge was imported into comp (board_a's or board_b's parent,
            # or a neutral component). Whichever leaf is NOT in its board's
            # component needs to be copied there.
            for leaf, board in [(leaf_for_a, board_a), (leaf_for_b, board_b)]:
                target_comp = board.parentComponent
                if target_comp != comp:
                    proxy = leaf.createForAssemblyContext(full_occ)
                    coll = adsk.core.ObjectCollection.create()
                    coll.add(proxy)
                    copy_feat = target_comp.features.copyPasteBodies.add(coll)
                    for bi in range(copy_feat.bodies.count):
                        copy_feat.bodies.item(bi).name = f"{name}_Leaf"
                    leaf.isVisible = False

            # Name remaining visible bodies
            for leaf in leaf_bodies:
                if leaf.isVisible:
                    leaf.name = f"{name}_Leaf"
            if pin_bodies:
                pin_bodies[0].name = f"{name}_Pin"

    result = {
        "occurrence": top_occ,
        "bodies": all_bodies,
        "pin": pin_bodies[0] if pin_bodies else None,
        "leaves": leaf_bodies,
        "part": part,
        "barrel_d_cm": barrel_d_cm,
        "plate_t_cm": plate_t_cm,
        "cuts": cuts,
        "screws": [],
    }

    return result


def install(part_id, comp, position, board=None,
            orientation=None, mortise=True, keep_tool=True,
            appearance=None, ev=None, name=None):
    """Install a generic hardware part (pulls, locks, etc.)."""
    part = get_part(part_id)
    if part is None:
        raise ValueError(f"Part '{part_id}' not found in catalog.")
    step_file = _resolve_step_path(part["step_file"])
    anchor = part.get("anchor", {"origin": [0, 0, 0]})
    if ev is not None:
        pos = [ev(p) if isinstance(p, str) else p for p in position]
    else:
        pos = list(position)
    imported = _import_or_copy(part_id, step_file, comp)
    if not imported:
        raise RuntimeError(f"No geometry imported from {step_file}")
    occ, bodies = imported[0]
    transform = _build_transform(pos, anchor)
    _move_occurrence(comp, occ, transform, name or "HW")
    if name:
        occ.component.name = name
    _hardware_occurrences.append((occ, comp))
    cut_result = None
    if mortise and board is not None and bodies:
        from helpers import sp
        tool_proxies = [b.createForAssemblyContext(occ) for b in bodies]
        root = adsk.fusion.Design.cast(
            adsk.core.Application.get().activeProduct).rootComponent
        cut_name = f"{name}_Mort" if name else "HW_Mort"
        cut_result = sp.combine(board, tool_proxies, CUT,
                                keep_tool, cut_name)
    if appearance:
        from helpers import sp
        for b in bodies:
            sp.apply_appearance(b, appearance)
    return {"occurrence": occ, "bodies": bodies, "cut": cut_result, "part": part}


def install_pair(part_id, comp,
                 board_a, position_a, board_b, position_b,
                 orientation=None, mortise=True, ev=None, name="HW"):
    result_a = install(part_id, comp, position_a, board=board_a,
                       orientation=orientation, mortise=mortise,
                       ev=ev, name=f"{name}_A")
    result_b = install(part_id, comp, position_b, board=board_b,
                       orientation=orientation, mortise=mortise,
                       ev=ev, name=f"{name}_B")
    return {"a": result_a, "b": result_b}


def install_butt_hinge_pair(part_id, comp, pin_y, pin_z,
                            lid_length_cm=None, lid_length_expr=None,
                            back_body=None, lid_body=None,
                            door_body=None, case_body=None,
                            style="lid_surface", gap=0,
                            install_screws=False,
                            pin_axis="x", ev=None, name="Hinge"):
    """Install a pair of hinges using mirror.

    Installs the left hinge fully (with screws + CUTs), then mirrors
    all hinge/screw bodies across the midplane for the right hinge.
    Only 1 STEP import per part type (hinge + screw).
    """
    from helpers import sp

    if lid_length_cm is None and lid_length_expr and ev:
        lid_length_cm = ev(lid_length_expr)
    inset = lid_length_cm / 5.0

    # Install left hinge (with screws and all CUTs)
    left = install_butt_hinge(
        part_id, comp, back_body, lid_body,
        pin_position=(inset, pin_y, pin_z),
        pin_axis=pin_axis, style=style,
        door_body=door_body, case_body=case_body,
        gap=gap, install_screws=install_screws,
        ev=ev, name=f"{name}_L")

    # Compute gap_cm for door_flush style
    gap_cm = 0
    if gap:
        gap_cm = ev(gap) if isinstance(gap, str) and ev else float(gap)

    # Create midplane for mirror (at half the lid length along pin axis)
    mid_offset = f"{lid_length_cm / 2} cm"
    mid_plane = sp.off_plane(comp, comp.yZConstructionPlane,
                             mid_offset, f"{name}_MidPl")
    mid_plane.isLightBulbOn = False

    # Mirror hinge bodies (all in same sub-component)
    hinge_occ = left["occurrence"]
    hinge_proxies = [b.createForAssemblyContext(hinge_occ)
                     for b in left["bodies"]]
    hinge_mirror = sp.mirror_bodies(comp, hinge_proxies, mid_plane,
                                    f"{name}_R_Mirror")

    # Mirror screw bodies separately
    # First screw has an occurrence (direct import), rest are move-copies
    # (bodies directly in comp)
    screw_mirrors = []
    for idx, screw in enumerate(left.get("screws", [])):
        screw_bodies_to_mirror = []
        if "occurrence" in screw:
            screw_occ = screw["occurrence"]
            for b in screw["bodies"]:
                screw_bodies_to_mirror.append(
                    b.createForAssemblyContext(screw_occ))
        else:
            # Move-copied bodies are already in comp space
            screw_bodies_to_mirror = list(screw["bodies"])
        if screw_bodies_to_mirror:
            sm = sp.mirror_bodies(comp, screw_bodies_to_mirror, mid_plane,
                                  f"{name}_R_Sc{idx}_Mirror")
            screw_mirrors.append(sm)

    # Create sketch-based rebate CUTs for the right side (same approach
    # as left, but at mirrored pin position).
    right_pin_x = lid_length_cm - inset
    right_pos = [right_pin_x, pin_y, pin_z]
    right_raw_pos = [right_pin_x, pin_y, pin_z]

    if style.startswith("lid_"):
        board_a, board_b = lid_body, back_body
    else:
        board_a, board_b = door_body, case_body

    right_cuts = []
    if board_a is not None and board_b is not None:
        # Classify mirrored hinge bodies to find leaves
        mirrored_hinge = [hinge_mirror.bodies.item(i)
                          for i in range(hinge_mirror.bodies.count)]
        mirrored_hinge.sort(key=lambda b: b.volume)
        if len(mirrored_hinge) >= 3:
            mirrored_leaves = mirrored_hinge[1:]  # skip pin
        else:
            mirrored_leaves = mirrored_hinge

        def z_mid(b):
            bb = b.boundingBox
            return (bb.maxPoint.z + bb.minPoint.z) / 2
        mirrored_leaves.sort(key=z_mid, reverse=True)
        r_leaf_a = mirrored_leaves[0] if len(mirrored_leaves) > 0 else None
        r_leaf_b = mirrored_leaves[1] if len(mirrored_leaves) > 1 else None

        plate_t = left.get("plate_t_cm", 0.0635)
        barrel_d = left.get("barrel_d_cm", 0.127)
        dims = left["part"].get("dimensions", {})
        barrel_d_str = dims.get("leaf_thickness", "0.050 in")

        # Use the hinge mirror occurrence context for leaf bboxes.
        # Mirror creates bodies in comp directly, so no proxy needed.
        right_cuts = _cut_rebates(
            comp, style, None, r_leaf_a, r_leaf_b, mirrored_hinge,
            board_a, board_b, right_pos, right_raw_pos,
            plate_t, barrel_d, barrel_d_str, f"{name}_R", ev,
            gap_cm=gap_cm)

    right = {
        "hinge_mirror": hinge_mirror,
        "screw_mirrors": screw_mirrors,
        "cuts": right_cuts,
    }

    return {"left": left, "right": right}
