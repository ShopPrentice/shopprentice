"""Japanese Scarf Joint (Kanawa Tsugi) template.

Splices two timbers end-to-end with an oblique interlocking joint.
The kanawa tsugi uses an angled cut, stepped rabbets, and a central
wedge keyway to create a strong mechanical connection without glue.

Construction approach:
  1. Extrude full cross-section as NewBody spanning scarf_length
  2. CUT scarf zone from both timbers (clears material for interlock)
  3. Create oblique construction plane at scarf_tilt
  4. Split scarf body at oblique plane into two halves
  5. Cut wedge keyway through both halves
  6. Create wedge body
  7. JOIN each half into its respective timber

Usage:
    from woodworking.templates import scarf_joint as sj

    sj.define_params(params, prefix="sj",
        scarf_length="13 in", scarf_notch="(5/8) * 1 in")

    result = sj.kanawa_tsugi(
        comp,
        body_a=post1,
        body_b=post2,
        splice_face=sp.find_face(post1, "z", +1),
        grain_axis="z",
        cross_axis="x",
        name="SJ1",
        ev=ctx.ev,
    )
    # result keys: half_a, half_b, wedge, features
"""

import adsk.core
import adsk.fusion

from helpers import sp

Point3D = adsk.core.Point3D
VI = adsk.core.ValueInput.createByString

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

METADATA = {
    "name": "scarf_joint",
    "category": "joinery",
    "variants": {
        "kanawa_tsugi": {
            "description": "Oblique rabbeted scarf with wedge keyway — "
                           "strongest traditional Japanese splice",
            "best_for": ["timber framing", "post splicing", "beam extension",
                         "pergola posts"],
        },
    },
    "params": {
        "scarf_length": "Length of the oblique splice along the grain",
        "scarf_notch": "Step/notch size for rabbets and keyway",
    },
}


def define_params(params, prefix="sj",
                  scarf_length="13 in", scarf_notch="(5/8) * 1 in"):
    """Define scarf joint parameters.

    Returns:
        Dict of parameter names: {"sl", "sn", "tilt"}.
    """
    p = prefix
    params.add(f"{p}_sl", VI(scarf_length), "in", "Scarf joint length")
    params.add(f"{p}_sn", VI(scarf_notch), "in", "Scarf notch size")
    params.add(f"{p}_tilt", VI(f"asin({p}_sn / {p}_sl)"), "deg",
               "Scarf tilt angle (derived)")

    return {"sl": f"{p}_sl", "sn": f"{p}_sn", "tilt": f"{p}_tilt"}


def _base_plane(comp, axis):
    return {
        "x": comp.yZConstructionPlane,
        "y": comp.xZConstructionPlane,
        "z": comp.xYConstructionPlane,
    }[axis]


def _body_dim(body, axis):
    bb = body.boundingBox
    return getattr(bb.maxPoint, axis) - getattr(bb.minPoint, axis)


def _body_min(body, axis):
    return getattr(body.boundingBox.minPoint, axis)


def _body_center(body, axis):
    bb = body.boundingBox
    return (getattr(bb.minPoint, axis) + getattr(bb.maxPoint, axis)) / 2


def kanawa_tsugi(comp, body_a, body_b, splice_face,
                 grain_axis="z", cross_axis="x",
                 prefix="sj", name="SJ",
                 ev=None):
    """Create a kanawa tsugi (oblique rabbeted scarf) joint.

    Args:
        comp: Component to create features in.
        body_a: First timber body (splice_face belongs to this body).
        body_b: Second timber body (abutting body_a at splice_face).
        splice_face: BRepFace where the timbers meet (end face of body_a).
        grain_axis: Axis along the timber grain ("x", "y", or "z").
        cross_axis: Axis across the timber width, perpendicular to grain.
        prefix: Parameter prefix used in define_params.
        name: Feature name prefix.
        ev: Evaluator function. If None, creates one from active design.

    Returns:
        Dict with half_a (=body_a), half_b (=body_b), wedge, features.
    """
    if ev is None:
        ev = sp._make_ev()

    p = prefix
    sl_expr = f"{p}_sl"
    sn_expr = f"{p}_sn"
    tilt_expr = f"{p}_tilt"

    sl = ev(sl_expr)
    sn = ev(sn_expr)

    all_axes = ["x", "y", "z"]
    depth_axis = [a for a in all_axes
                  if a != grain_axis and a != cross_axis][0]

    sp.validate_joint_contact(body_a, body_b, joint_axis=grain_axis)

    timber_w = _body_dim(body_a, cross_axis)
    timber_d = _body_dim(body_a, depth_axis)

    splice_pos = getattr(splice_face.pointOnFace, grain_axis)
    a_before_b = _body_center(body_a, grain_axis) < _body_center(body_b, grain_axis)
    grain_dir = 1 if a_before_b else -1

    cs_min_cross = _body_min(body_a, cross_axis)
    cs_min_depth = _body_min(body_a, depth_axis)

    features = []

    # ── STEP 1: Scarf body (full cross-section) ─────────────────
    sk1 = comp.sketches.add(splice_face)
    sk1.name = f"{name}_Scarf_Sk"

    o = {grain_axis: splice_pos, cross_axis: cs_min_cross,
         depth_axis: cs_min_depth}
    far = {grain_axis: splice_pos,
           cross_axis: cs_min_cross + timber_w,
           depth_axis: cs_min_depth + timber_d}
    sk_o = sk1.modelToSketchSpace(
        Point3D.create(o["x"], o["y"], o["z"]))
    sk_f = sk1.modelToSketchSpace(
        Point3D.create(far["x"], far["y"], far["z"]))

    rect = sk1.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(sk_o.x, sk_o.y, 0),
        Point3D.create(sk_f.x, sk_f.y, 0))
    gc = sk1.geometricConstraints
    gc.addHorizontal(rect[0])
    gc.addHorizontal(rect[2])
    gc.addVertical(rect[1])
    gc.addVertical(rect[3])

    prof = sk1.profiles.item(0)

    # Extrude into body_a (away from body_b)
    ext_inp = comp.features.extrudeFeatures.createInput(prof, NEWBODY)
    if grain_dir > 0:
        ext_inp.setOneSideExtent(
            adsk.fusion.DistanceExtentDefinition.create(VI(sl_expr)),
            adsk.fusion.ExtentDirections.NegativeExtentDirection)
    else:
        ext_inp.setDistanceExtent(False, VI(sl_expr))
    scarf_ext = comp.features.extrudeFeatures.add(ext_inp)
    scarf_ext.name = f"{name}_Scarf_Ext"
    scarf_body = scarf_ext.bodies.item(0)
    scarf_body.name = f"{name}_scarf"
    features.append(scarf_ext)

    # ── STEP 2: CUT scarf zone from both timbers ────────────────
    cut_a = sp.combine(body_a, [scarf_body], CUT, True,
                       f"{name}_CutZone_A")
    features.append(cut_a)
    cut_b = sp.combine(body_b, [scarf_body], CUT, True,
                       f"{name}_CutZone_B")
    features.append(cut_b)

    # ── STEP 3: Oblique construction plane at scarf midpoint ─────
    mid_grain = splice_pos - grain_dir * sl / 2
    mid_depth = cs_min_depth + timber_d / 2

    mid_plane = sp.off_plane(comp, _base_plane(comp, grain_axis),
                             f"{mid_grain} cm", f"{name}_Mid_Pl")
    features.append(mid_plane)

    sk_helper = comp.sketches.add(mid_plane)
    sk_helper.name = f"{name}_Helper_Sk"
    sp.refs_to_construction(sk_helper)

    # Line along cross_axis through the timber center
    pt_a = {grain_axis: mid_grain, cross_axis: cs_min_cross,
            depth_axis: mid_depth}
    pt_b = {grain_axis: mid_grain, cross_axis: cs_min_cross + timber_w,
            depth_axis: mid_depth}
    sk_a = sk_helper.modelToSketchSpace(
        Point3D.create(pt_a["x"], pt_a["y"], pt_a["z"]))
    sk_b = sk_helper.modelToSketchSpace(
        Point3D.create(pt_b["x"], pt_b["y"], pt_b["z"]))
    cross_line = sk_helper.sketchCurves.sketchLines.addByTwoPoints(
        Point3D.create(sk_a.x, sk_a.y, 0),
        Point3D.create(sk_b.x, sk_b.y, 0))

    # Tilt around cross_line relative to the depth-normal plane
    # Line along cross_axis, plane normal = depth_axis → not perpendicular ✓
    depth_ref_plane = _base_plane(comp, depth_axis)
    pl_inp = comp.constructionPlanes.createInput()
    pl_inp.setByAngle(cross_line, VI(tilt_expr), depth_ref_plane)
    oblique_plane = comp.constructionPlanes.add(pl_inp)
    oblique_plane.name = f"{name}_Oblique_Pl"
    features.append(oblique_plane)

    # ── STEP 4: Split scarf body at oblique plane ────────────────
    split_inp = comp.features.splitBodyFeatures.createInput(
        scarf_body, oblique_plane, True)
    split_feat = comp.features.splitBodyFeatures.add(split_inp)
    split_feat.name = f"{name}_Split"
    features.append(split_feat)

    # Find the two halves (everything except the two timbers)
    halves = []
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        if b != body_a and b != body_b:
            halves.append(b)

    # Sort: half closer to body_a = half_a
    a_center = _body_center(body_a, grain_axis)
    halves.sort(key=lambda b: abs(_body_center(b, grain_axis) - a_center))
    half_a_body = halves[0]
    half_a_body.name = f"{name}_half_a"
    half_b_body = halves[1]
    half_b_body.name = f"{name}_half_b"

    # ── STEP 5: Wedge keyway on the oblique face ────────────────
    # Find the oblique face (normal has components in both grain and depth)
    oblique_face = None
    for i in range(half_a_body.faces.count):
        f = half_a_body.faces.item(i)
        geom = f.geometry
        if isinstance(geom, adsk.core.Plane):
            n = geom.normal
            g = abs(getattr(n, grain_axis))
            d = abs(getattr(n, depth_axis))
            c = abs(getattr(n, cross_axis))
            if g > 0.01 and d > 0.01 and c < 0.1:
                oblique_face = f
                break

    sk_key = comp.sketches.add(oblique_face)
    sk_key.name = f"{name}_Key_Sk"
    fc = oblique_face.pointOnFace
    sk_fc = sk_key.modelToSketchSpace(fc)
    half_sn = sn / 2

    key_rect = sk_key.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(sk_fc.x - half_sn, sk_fc.y - half_sn, 0),
        Point3D.create(sk_fc.x + half_sn, sk_fc.y + half_sn, 0))
    kgc = sk_key.geometricConstraints
    kgc.addHorizontal(key_rect[0])
    kgc.addHorizontal(key_rect[2])
    kgc.addVertical(key_rect[1])
    kgc.addVertical(key_rect[3])

    kd = sk_key.sketchDimensions
    kd.addDistanceDimension(
        key_rect[0].startSketchPoint, key_rect[0].endSketchPoint,
        H, Point3D.create(sk_fc.x, sk_fc.y - half_sn - 1, 0)
    ).parameter.expression = sn_expr
    kd.addDistanceDimension(
        key_rect[1].startSketchPoint, key_rect[1].endSketchPoint,
        V, Point3D.create(sk_fc.x + half_sn + 1, sk_fc.y, 0)
    ).parameter.expression = sn_expr

    key_prof = sp.smallest_profile(sk_key)
    timber_w_expr = f"{timber_w} cm"

    key_ext = sp.ext_new(comp, key_prof, timber_w_expr, f"{name}_Key_Ext")
    key_tool = key_ext.bodies.item(0)
    key_tool.name = f"{name}_key_tool"
    features.append(key_ext)

    sp.combine(half_a_body, [key_tool], CUT, True,
               f"{name}_Key_Cut_A")
    sp.combine(half_b_body, [key_tool], CUT, True,
               f"{name}_Key_Cut_B")

    # ── STEP 6: Wedge body ──────────────────────────────────────
    sk_w = comp.sketches.add(oblique_face)
    sk_w.name = f"{name}_Wedge_Sk"
    sk_wc = sk_w.modelToSketchSpace(fc)

    w_rect = sk_w.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(sk_wc.x - half_sn, sk_wc.y - half_sn, 0),
        Point3D.create(sk_wc.x + half_sn, sk_wc.y + half_sn, 0))
    wgc = sk_w.geometricConstraints
    wgc.addHorizontal(w_rect[0])
    wgc.addHorizontal(w_rect[2])
    wgc.addVertical(w_rect[1])
    wgc.addVertical(w_rect[3])

    wdim = sk_w.sketchDimensions
    wdim.addDistanceDimension(
        w_rect[0].startSketchPoint, w_rect[0].endSketchPoint,
        H, Point3D.create(sk_wc.x, sk_wc.y - half_sn - 1, 0)
    ).parameter.expression = sn_expr
    wdim.addDistanceDimension(
        w_rect[1].startSketchPoint, w_rect[1].endSketchPoint,
        V, Point3D.create(sk_wc.x + half_sn + 1, sk_wc.y, 0)
    ).parameter.expression = sn_expr

    wedge_body = sp.ext_new(
        comp, sp.smallest_profile(sk_w), timber_w_expr,
        f"{name}_Wedge_Ext").bodies.item(0)
    wedge_body.name = f"{name}_wedge"

    # ── STEP 7: JOIN halves into timbers ────────────────────────
    join_a = sp.combine(body_a, [half_a_body], JOIN, False,
                        f"{name}_Join_A")
    features.append(join_a)
    join_b = sp.combine(body_b, [half_b_body], JOIN, False,
                        f"{name}_Join_B")
    features.append(join_b)

    # Clean up key tool
    if key_tool.isValid:
        key_tool.isVisible = False

    return {
        "half_a": body_a,
        "half_b": body_b,
        "wedge": wedge_body,
        "features": features,
    }
