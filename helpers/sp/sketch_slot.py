import adsk.core
import adsk.fusion
import math

from ._util import _make_ev
from .sketch import probe_sketch_axes

Point3D = adsk.core.Point3D
H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation


def sketch_slot(comp, plane, cx_expr, cy_expr, long_expr, short_expr,
                vertical, name="Sk", ev=None):
    """Stadium-shaped sketch on a construction plane (2 arcs + 2 lines).

    All dimensions are parametric. The long axis runs along sketch V when
    vertical=True, sketch H when False.

    Args:
        comp: Component to create sketch in.
        plane: Construction plane or BRepFace.
        cx_expr, cy_expr: Center position in sketch-space (parameter expressions).
        long_expr: Long dimension expression (e.g. "dm_l").
        short_expr: Short dimension expression (e.g. "dm_w").
        vertical: True → long axis along sketch Y; False → along sketch X.
        name: Sketch name.
        ev: Evaluator function. If None, creates one from active design.

    Returns:
        (sketch, profile)
    """
    if ev is None:
        ev = _make_ev()

    sk = comp.sketches.add(plane)
    sk.name = name
    slines = sk.sketchCurves.sketchLines
    sarcs = sk.sketchCurves.sketchArcs
    cx, cy = ev(cx_expr), ev(cy_expr)
    lg, sh = ev(long_expr), ev(short_expr)
    r = sh / 2
    hl = (lg - sh) / 2

    if vertical:
        br = Point3D.create(cx + r, cy - hl, 0)
        tr = Point3D.create(cx + r, cy + hl, 0)
        tc = Point3D.create(cx, cy + hl, 0)
        tl = Point3D.create(cx - r, cy + hl, 0)
        bl = Point3D.create(cx - r, cy - hl, 0)
        bc = Point3D.create(cx, cy - hl, 0)
        l_r = slines.addByTwoPoints(br, tr)
        a_t = sarcs.addByCenterStartSweep(tc, tr, math.pi)
        l_l = slines.addByTwoPoints(tl, bl)
        a_b = sarcs.addByCenterStartSweep(bc, bl, math.pi)
        sk.geometricConstraints.addVertical(l_r)
        sk.geometricConstraints.addVertical(l_l)
        sk.geometricConstraints.addTangent(l_r, a_t)
        sk.geometricConstraints.addTangent(a_t, l_l)
        sk.geometricConstraints.addTangent(l_l, a_b)
        sk.geometricConstraints.addTangent(a_b, l_r)
        # Join the line<->arc junctions: lines/arcs were built from independent
        # points, so tangent alone leaves sliding DOF. Coincident at all four
        # corners is what makes the stadium fully constrainable.
        sk.geometricConstraints.addCoincident(l_r.endSketchPoint, a_t.startSketchPoint)
        sk.geometricConstraints.addCoincident(a_t.endSketchPoint, l_l.startSketchPoint)
        sk.geometricConstraints.addCoincident(l_l.endSketchPoint, a_b.startSketchPoint)
        sk.geometricConstraints.addCoincident(a_b.endSketchPoint, l_r.startSketchPoint)
        d = sk.sketchDimensions
        d.addRadialDimension(a_b,
            Point3D.create(cx + r + 1, cy - hl, 0)
        ).parameter.expression = short_expr + " / 2"
        d.addDistanceDimension(
            a_b.centerSketchPoint, a_t.centerSketchPoint,
            V, Point3D.create(cx + r + 2, cy, 0)
        ).parameter.expression = long_expr + " - " + short_expr
        d.addDistanceDimension(
            sk.originPoint, a_b.centerSketchPoint,
            H, Point3D.create(cx / 2, cy - hl - 1, 0)
        ).parameter.expression = cx_expr
        d.addDistanceDimension(
            sk.originPoint, a_b.centerSketchPoint,
            V, Point3D.create(cx - r - 1, (cy - hl) / 2, 0)
        ).parameter.expression = cy_expr + " - (" + long_expr + " - " + short_expr + ") / 2"
    else:
        bsl = Point3D.create(cx - hl, cy - r, 0)
        bsr = Point3D.create(cx + hl, cy - r, 0)
        rc = Point3D.create(cx + hl, cy, 0)
        tsr = Point3D.create(cx + hl, cy + r, 0)
        tsl = Point3D.create(cx - hl, cy + r, 0)
        lc = Point3D.create(cx - hl, cy, 0)
        l_b = slines.addByTwoPoints(bsl, bsr)
        a_r = sarcs.addByCenterStartSweep(rc, bsr, math.pi)
        l_t = slines.addByTwoPoints(tsr, tsl)
        a_l = sarcs.addByCenterStartSweep(lc, tsl, math.pi)
        sk.geometricConstraints.addHorizontal(l_b)
        sk.geometricConstraints.addHorizontal(l_t)
        sk.geometricConstraints.addTangent(l_b, a_r)
        sk.geometricConstraints.addTangent(a_r, l_t)
        sk.geometricConstraints.addTangent(l_t, a_l)
        sk.geometricConstraints.addTangent(a_l, l_b)
        # Join the line<->arc junctions: lines/arcs were built from independent
        # points, so tangent alone leaves sliding DOF. Coincident at all four
        # corners is what makes the stadium fully constrainable.
        sk.geometricConstraints.addCoincident(l_b.endSketchPoint, a_r.startSketchPoint)
        sk.geometricConstraints.addCoincident(a_r.endSketchPoint, l_t.startSketchPoint)
        sk.geometricConstraints.addCoincident(l_t.endSketchPoint, a_l.startSketchPoint)
        sk.geometricConstraints.addCoincident(a_l.endSketchPoint, l_b.startSketchPoint)
        d = sk.sketchDimensions
        d.addRadialDimension(a_l,
            Point3D.create(cx - hl - 1, cy + r + 1, 0)
        ).parameter.expression = short_expr + " / 2"
        d.addDistanceDimension(
            a_l.centerSketchPoint, a_r.centerSketchPoint,
            H, Point3D.create(cx, cy - r - 2, 0)
        ).parameter.expression = long_expr + " - " + short_expr
        d.addDistanceDimension(
            sk.originPoint, a_l.centerSketchPoint,
            H, Point3D.create((cx - hl) / 2, cy - r - 1, 0)
        ).parameter.expression = cx_expr + " - (" + long_expr + " - " + short_expr + ") / 2"
        d.addDistanceDimension(
            sk.originPoint, a_l.centerSketchPoint,
            V, Point3D.create(cx - hl - 2, cy / 2, 0)
        ).parameter.expression = cy_expr
    return sk, sk.profiles.item(0)


def probe_sketch_signs(sk):
    """Return (h_axis, v_axis, h_sign, v_sign) for a sketch.

    Extends probe_sketch_axes with sign detection: h/v_sign is +1 if
    increasing model coordinate → increasing sketch coordinate, else -1.
    Use the sign when building offset expressions on non-XY planes.
    """
    h_axis, v_axis = probe_sketch_axes(sk)
    sc = sk.modelToSketchSpace(Point3D.create(0, 0, 0))
    delta = {
        "x": Point3D.create(1, 0, 0),
        "y": Point3D.create(0, 1, 0),
        "z": Point3D.create(0, 0, 1),
    }
    sd_h = sk.modelToSketchSpace(delta[h_axis])
    sd_v = sk.modelToSketchSpace(delta[v_axis])
    h_sign = 1 if (sd_h.x - sc.x) > 0 else -1
    v_sign = 1 if (sd_v.y - sc.y) > 0 else -1
    return h_axis, v_axis, h_sign, v_sign


def sketch_slot_model(comp, plane, model_center, long_model_axis,
                      long_expr, short_expr, name="Sk", ev=None,
                      anchor=None):
    """Stadium-shaped sketch positioned in model coordinates.

    Handles axis flips on non-XY planes automatically via sign detection.
    Use this instead of sketch_slot when working in model-space coordinates.

    Two modes:

    * ORIGIN mode (``anchor=None``, default, BACKWARD-COMPATIBLE): the slot
      center is positioned with two ``addDistanceDimension(sk.originPoint,...)``
      dims. Correct for ROOT sketches; FAILS the validator for non-root ones
      (deps rules 1 & 2).

    * ANCHORED mode (``anchor=dict(...)``): the two origin center-position dims
      are replaced by offset dims from a PROJECTED parent corner, so no dim
      touches the sketch origin and the slot is anchored to real parent
      geometry (deps rules 1 & 2). The line↔arc junctions already carry
      coincident (shared endpoints) + tangent constraints so the ends can't
      slide; the radial + length dims plus the two anchor dims fully constrain
      the slot (deps rule 3).

    Args:
        comp: Component to create sketch in.
        plane: Construction plane or BRepFace (can be non-XY).
        model_center: (x_expr, y_expr, z_expr) — center in model-space expressions.
        long_model_axis: 'x', 'y', or 'z' — which model axis the long dim runs along.
        long_expr: Long dimension expression.
        short_expr: Short dimension expression.
        name: Sketch name.
        ev: Evaluator function. If None, creates one from active design.
        anchor: Optional dict enabling ANCHORED mode. Keys:
            parent_body, parent_occ, face_axis, face_dir — as in
            ``sketch_rect_model``'s ``anchor`` (the parent reference face).
            anchor_xyz: (x_expr, y_expr, z_expr) — model point on the parent
                face whose projected corner the slot is anchored to (must not
                coincide with the sketch-origin projection).
            off: ((axis1, expr1), (axis2, expr2)) — the two offset dims from
                the anchored parent corner to the slot's reference arc center.
                POSITIVE magnitudes; axes are model axis names. The reference
                arc center is the arc on the ``-`` side along each axis (the
                same arc the origin dims used).

    Returns:
        (sketch, profile)
    """
    if ev is None:
        ev = _make_ev()

    sk = comp.sketches.add(plane)
    sk.name = name
    h_axis, v_axis = probe_sketch_axes(sk)

    mcx = ev(model_center[0])
    mcy = ev(model_center[1])
    mcz = ev(model_center[2])
    sc = sk.modelToSketchSpace(Point3D.create(mcx, mcy, mcz))
    cx, cy = sc.x, sc.y

    vertical = (long_model_axis == v_axis)

    axis_expr = {
        "x": model_center[0], "y": model_center[1], "z": model_center[2]
    }
    h_expr = axis_expr[h_axis]
    v_expr = axis_expr[v_axis]

    lg, sh = ev(long_expr), ev(short_expr)
    r = sh / 2
    hl = (lg - sh) / 2
    slines = sk.sketchCurves.sketchLines
    sarcs = sk.sketchCurves.sketchArcs

    delta_pt = {
        "x": Point3D.create(mcx + 1, mcy, mcz),
        "y": Point3D.create(mcx, mcy + 1, mcz),
        "z": Point3D.create(mcx, mcy, mcz + 1),
    }
    sd_h = sk.modelToSketchSpace(delta_pt[h_axis])
    sd_v = sk.modelToSketchSpace(delta_pt[v_axis])
    h_sign = 1 if (sd_h.x - sc.x) > 0 else -1
    v_sign = 1 if (sd_v.y - sc.y) > 0 else -1

    half_str = "(" + long_expr + " - " + short_expr + ") / 2"
    v_bot_op = " - " if v_sign > 0 else " + "
    h_left_op = " - " if h_sign > 0 else " + "

    if vertical:
        br = Point3D.create(cx + r, cy - hl, 0)
        tr = Point3D.create(cx + r, cy + hl, 0)
        tc = Point3D.create(cx, cy + hl, 0)
        tl = Point3D.create(cx - r, cy + hl, 0)
        bl = Point3D.create(cx - r, cy - hl, 0)
        bc = Point3D.create(cx, cy - hl, 0)
        l_r = slines.addByTwoPoints(br, tr)
        a_t = sarcs.addByCenterStartSweep(tc, tr, math.pi)
        l_l = slines.addByTwoPoints(tl, bl)
        a_b = sarcs.addByCenterStartSweep(bc, bl, math.pi)
        sk.geometricConstraints.addVertical(l_r)
        sk.geometricConstraints.addVertical(l_l)
        sk.geometricConstraints.addTangent(l_r, a_t)
        sk.geometricConstraints.addTangent(a_t, l_l)
        sk.geometricConstraints.addTangent(l_l, a_b)
        sk.geometricConstraints.addTangent(a_b, l_r)
        # Join the line<->arc junctions: lines/arcs were built from independent
        # points, so tangent alone leaves sliding DOF. Coincident at all four
        # corners is what makes the stadium fully constrainable.
        sk.geometricConstraints.addCoincident(l_r.endSketchPoint, a_t.startSketchPoint)
        sk.geometricConstraints.addCoincident(a_t.endSketchPoint, l_l.startSketchPoint)
        sk.geometricConstraints.addCoincident(l_l.endSketchPoint, a_b.startSketchPoint)
        sk.geometricConstraints.addCoincident(a_b.endSketchPoint, l_r.startSketchPoint)
        d = sk.sketchDimensions
        d.addRadialDimension(a_b,
            Point3D.create(cx + r + 1, cy - hl, 0)
        ).parameter.expression = short_expr + " / 2"
        d.addDistanceDimension(
            a_b.centerSketchPoint, a_t.centerSketchPoint,
            V, Point3D.create(cx + r + 2, cy, 0)
        ).parameter.expression = long_expr + " - " + short_expr
        ref_center = a_b.centerSketchPoint   # arc center the position dims anchor
        if anchor is None:
            d.addDistanceDimension(
                sk.originPoint, a_b.centerSketchPoint,
                H, Point3D.create(cx / 2, cy - hl - 1, 0)
            ).parameter.expression = h_expr
            d.addDistanceDimension(
                sk.originPoint, a_b.centerSketchPoint,
                V, Point3D.create(cx - r - 1, (cy - hl) / 2, 0)
            ).parameter.expression = v_expr + v_bot_op + half_str
    else:
        bsl = Point3D.create(cx - hl, cy - r, 0)
        bsr = Point3D.create(cx + hl, cy - r, 0)
        rc = Point3D.create(cx + hl, cy, 0)
        tsr = Point3D.create(cx + hl, cy + r, 0)
        tsl = Point3D.create(cx - hl, cy + r, 0)
        lc = Point3D.create(cx - hl, cy, 0)
        l_b = slines.addByTwoPoints(bsl, bsr)
        a_r = sarcs.addByCenterStartSweep(rc, bsr, math.pi)
        l_t = slines.addByTwoPoints(tsr, tsl)
        a_l = sarcs.addByCenterStartSweep(lc, tsl, math.pi)
        sk.geometricConstraints.addHorizontal(l_b)
        sk.geometricConstraints.addHorizontal(l_t)
        sk.geometricConstraints.addTangent(l_b, a_r)
        sk.geometricConstraints.addTangent(a_r, l_t)
        sk.geometricConstraints.addTangent(l_t, a_l)
        sk.geometricConstraints.addTangent(a_l, l_b)
        # Join the line<->arc junctions: lines/arcs were built from independent
        # points, so tangent alone leaves sliding DOF. Coincident at all four
        # corners is what makes the stadium fully constrainable.
        sk.geometricConstraints.addCoincident(l_b.endSketchPoint, a_r.startSketchPoint)
        sk.geometricConstraints.addCoincident(a_r.endSketchPoint, l_t.startSketchPoint)
        sk.geometricConstraints.addCoincident(l_t.endSketchPoint, a_l.startSketchPoint)
        sk.geometricConstraints.addCoincident(a_l.endSketchPoint, l_b.startSketchPoint)
        d = sk.sketchDimensions
        d.addRadialDimension(a_l,
            Point3D.create(cx - hl - 1, cy + r + 1, 0)
        ).parameter.expression = short_expr + " / 2"
        d.addDistanceDimension(
            a_l.centerSketchPoint, a_r.centerSketchPoint,
            H, Point3D.create(cx, cy - r - 2, 0)
        ).parameter.expression = long_expr + " - " + short_expr
        ref_center = a_l.centerSketchPoint   # arc center the position dims anchor
        if anchor is None:
            d.addDistanceDimension(
                sk.originPoint, a_l.centerSketchPoint,
                H, Point3D.create((cx - hl) / 2, cy - r - 1, 0)
            ).parameter.expression = h_expr + h_left_op + half_str
            d.addDistanceDimension(
                sk.originPoint, a_l.centerSketchPoint,
                V, Point3D.create(cx - hl - 2, cy / 2, 0)
            ).parameter.expression = v_expr

    if anchor is not None:
        # ANCHORED mode: replace the two origin position dims with offset dims
        # from a PROJECTED parent corner to the reference arc center, so no dim
        # touches the sketch origin (deps rules 1 & 2). The slot's line↔arc
        # junctions already carry coincident + tangent constraints, so anchoring
        # the one arc center plus the radial/length dims fully constrains it.
        from .anchoring import project_face, anchor_pt, rdim
        from .sketch import probe_orientations

        project_face(sk, anchor["parent_body"], anchor.get("parent_occ"),
                     anchor["face_axis"], anchor["face_dir"])
        ax_pt = anchor["anchor_xyz"]
        aP = anchor_pt(sk, ev(ax_pt[0]), ev(ax_pt[1]), ev(ax_pt[2]))
        orient = probe_orientations(sk, mcx, mcy, mcz)
        (o1, o2) = anchor["off"]
        if aP is not None:
            rdim(sk, sk.sketchDimensions, aP, ref_center, orient, o1[0], o1[1])
            rdim(sk, sk.sketchDimensions, aP, ref_center, orient, o2[0], o2[1])

    return sk, sk.profiles.item(0)
