"""Turned stretcher template — revolved spindle connecting two bodies.

Fully parametric: when leg positions, angles, or heights change,
the stretcher recomputes automatically.

Construction sequence:
  1. Mark points on each leg's center line at parametric distances
  2. Construction axis (Line A) through those points
  3. Profile sketch on a plane containing the axis
  4. Extend axis past each leg by leg_radius + ts_ext
  5. Draw turned profile with parametric constraints
  6. Revolve 360°

Usage::

    from woodworking.templates import turned_stretcher as ts
    ts.define_params(params)
    body = ts.build(comp, axis_a=fl_axis, axis_b=bl_axis,
                    dist_a="leg_h * 0.4", dist_b="leg_h * 0.4",
                    name="Str_Left", ev=ev)
"""

import adsk.core
import adsk.fusion
import math
from helpers import sp

NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
AL = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation
V = adsk.core.ValueInput.createByString
P = adsk.core.Point3D.create


# ── Public API ──────────────────────────────────────────────────────

def define_params(params, prefix="ts",
                  mid_dia="0.75 in", end_dia="0.5 in",
                  tenon_len="0.5 in", shoulder_len="0.25 in",
                  ext="0.1 in", barrel_dist="1.5 in", barrel_r=None):
    """Add turned stretcher parameters to the design.

    barrel_dist/barrel_r only used with profile='barrel'.
    barrel_r defaults to mid_dia/2 if not specified.
    """
    p = prefix
    if barrel_r is None:
        barrel_r = f"{mid_dia} / 2" if "/" not in mid_dia else mid_dia
    for pname, expr, unit, desc in [
        (f"{p}_mid_dia", mid_dia,         "in", "Stretcher body diameter"),
        (f"{p}_end_dia", end_dia,         "in", "Stretcher tenon diameter"),
        (f"{p}_tenon_len", tenon_len,     "in", "Tenon length"),
        (f"{p}_shoulder_len", shoulder_len,"in", "Shoulder transition length"),
        (f"{p}_ext", ext,                 "in", "Tenon extension beyond leg surface"),
        (f"{p}_barrel_dist", barrel_dist, "in", "Barrel control point dist from mid"),
        (f"{p}_barrel_r", barrel_r,       "in", "Barrel control point radius"),
    ]:
        # Only create if missing — don't overwrite user-modified values
        if not params.itemByName(pname):
            params.add(pname, V(expr), unit, desc)


def build(comp, axis_a, axis_b, dist_a, dist_b,
          body_dia_expr="leg_dia",
          profile="straight", prefix="ts", name="Str", ev=None):
    """Build a turned stretcher between two bodies.

    Args:
        axis_a, axis_b: Sketch lines — the center lines of the two
            bodies (e.g. leg revolve axes).  Points are found on these.
        dist_a, dist_b: Distance from the START of each axis to the
            connection point.  Parameter expression or cm float.
        body_dia_expr: Parameter expression for the mortise body
            diameter at the connection point (e.g. "leg_dia").
            Used to extend the axis past the body surface.
        profile: "straight" (default).
        prefix: Parameter prefix.
        name: Feature/body name.
        ev: Evaluator function.

    Returns the stretcher body.
    """
    ev = ev or _default_ev()

    dist_a_expr = f"{dist_a} cm" if isinstance(dist_a, (int, float)) else dist_a
    dist_b_expr = f"{dist_b} cm" if isinstance(dist_b, (int, float)) else dist_b

    # ── Step 1: Points on leg center lines ─────────────────────────
    # In each leg's axis sketch, draw a construction segment from the
    # axis start, collinear with the axis, dimensioned by dist.
    # The endpoint = the connection point ON the leg center line.

    pt_a, sk_a = _point_on_axis(comp, axis_a, dist_a_expr, f"{name}_PtA")
    pt_b, sk_b = _point_on_axis(comp, axis_b, dist_b_expr, f"{name}_PtB")

    if not pt_a or not pt_b:
        print(f"{name}: could not create connection points")
        return None

    # ── Step 2: Construction points + axis ─────────────────────────
    # Construction points in the axis's own component
    ax_comp = axis_a.component if hasattr(axis_a, 'component') else comp
    cp_a = _construction_point(ax_comp, pt_a, f"{name}_CpA")
    cp_b = _construction_point(ax_comp, pt_b, f"{name}_CpB")

    if not cp_a or not cp_b:
        print(f"{name}: could not create construction points")
        return None

    # Construction axis — build in same component as the points
    ax_inp = ax_comp.constructionAxes.createInput()
    ax_inp.setByTwoPoints(cp_a, cp_b)
    con_axis = ax_comp.constructionAxes.add(ax_inp)
    con_axis.name = f"{name}_Axis"

    # ── Step 3: Profile sketch plane ───────────────────────────────
    prof_pl_inp = comp.constructionPlanes.createInput()
    prof_pl_inp.setByAngle(con_axis, V("90 deg"),
                           comp.xYConstructionPlane)
    prof_pl = comp.constructionPlanes.add(prof_pl_inp)
    prof_pl.name = f"{name}_ProfPl"

    # ── Step 4: Profile sketch ─────────────────────────────────────
    sk = comp.sketches.add(prof_pl)
    sk.name = f"{name}_Sk"
    gc = sk.geometricConstraints
    dims = sk.sketchDimensions
    lines = sk.sketchCurves.sketchLines
    m2s = sk.modelToSketchSpace

    # Project the two construction points (not the axis)
    sk.project(cp_a)
    sk.project(cp_b)

    # Find the two projected points
    proj_pts = []
    for ci in range(sk.sketchCurves.count):
        pass  # points aren't in sketchCurves
    # Projected points appear as sketch points, find them by proximity
    s2m = sk.sketchToModelSpace
    cp_a_geo = cp_a.geometry
    cp_b_geo = cp_b.geometry
    pa_sk = m2s(cp_a_geo)
    pb_sk = m2s(cp_b_geo)

    # Find projected sketch points closest to cp_a and cp_b
    best_a = None; best_da = 1e10
    best_b = None; best_db = 1e10
    for pi in range(sk.sketchPoints.count):
        sp_pt = sk.sketchPoints.item(pi)
        if sp_pt == sk.originPoint:
            continue
        g = sp_pt.geometry
        da = math.sqrt((g.x - pa_sk.x)**2 + (g.y - pa_sk.y)**2)
        db = math.sqrt((g.x - pb_sk.x)**2 + (g.y - pb_sk.y)**2)
        if da < best_da:
            best_da = da; best_a = sp_pt
        if db < best_db:
            best_db = db; best_b = sp_pt

    if not best_a or not best_b or best_a == best_b:
        print(f"{name}: could not find projected construction points")
        return None

    pa_g = best_a.geometry
    pb_g = best_b.geometry

    # Center-to-center line (construction, constrained to projected points)
    ctr_line = lines.addByTwoPoints(
        P(pa_g.x, pa_g.y, 0), P(pb_g.x, pb_g.y, 0))
    ctr_line.isConstruction = True
    gc.addCoincident(ctr_line.startSketchPoint, best_a)
    gc.addCoincident(ctr_line.endSketchPoint, best_b)

    dx = pb_g.x - pa_g.x
    dy = pb_g.y - pa_g.y
    dd = math.sqrt(dx * dx + dy * dy)
    if dd < 0.01:
        print(f"{name}: points too close")
        return None
    ux, uy = dx / dd, dy / dd

    ext_val = ev(f"{prefix}_ext")
    body_r = ev(body_dia_expr) / 2
    ext_total = body_r + ext_val

    # Axis line: collinear with ctr_line, centered on ctr_line midpoint,
    # total length = ctr_distance + 2 * (body_dia/2 + ext).
    # Using midpoint constraint ensures extensions are symmetric and
    # direction-independent (no flipping when legs move).
    a_tip = P(pa_g.x - ux * ext_total, pa_g.y - uy * ext_total, 0)
    b_tip = P(pb_g.x + ux * ext_total, pb_g.y + uy * ext_total, 0)
    ax_line = lines.addByTwoPoints(a_tip, b_tip)
    gc.addCollinear(ax_line, ctr_line)

    # Midpoint of ctr_line = midpoint of ax_line → symmetric extensions
    # Create a construction point at ctr_line midpoint, constrain ax_line
    # midpoint to it
    ctr_mid_pt = P((pa_g.x + pb_g.x) / 2, (pa_g.y + pb_g.y) / 2, 0)
    ctr_mid_line = lines.addByTwoPoints(ctr_mid_pt,
        P(ctr_mid_pt.x - uy * 0.5, ctr_mid_pt.y + ux * 0.5, 0))
    ctr_mid_line.isConstruction = True
    gc.addMidPoint(ctr_mid_line.startSketchPoint, ctr_line)
    gc.addMidPoint(ctr_mid_line.startSketchPoint, ax_line)

    # Dimension: total axis length
    ax_len_dim = dims.addDistanceDimension(
        ax_line.startSketchPoint, ax_line.endSketchPoint, AL,
        P(ctr_mid_pt.x - uy * 3, ctr_mid_pt.y + ux * 3, 0))

    # Driven dimension on ctr_line for proportional profile reference
    len_dim = dims.addDistanceDimension(
        ctr_line.startSketchPoint, ctr_line.endSketchPoint, AL,
        P(ctr_mid_pt.x - uy * 5, ctr_mid_pt.y + ux * 5, 0),
        False)  # isDriving=False
    len_param = len_dim.parameter.name

    # Total axis = ctr_distance + 2 * extension
    ax_len_dim.parameter.expression = \
        f"{len_param} + 2 * ({body_dia_expr} / 2 + {prefix}_ext)"

    # ── Step 5: Profile ────────────────────────────────────────────
    anx, any_ = -uy, ux  # normal to axis

    end_r = ev(f"{prefix}_end_dia") / 2
    mid_r = ev(f"{prefix}_mid_dia") / 2
    t_len = ev(f"{prefix}_tenon_len")
    s_len = ev(f"{prefix}_shoulder_len")

    as_g = ax_line.startSketchPoint.geometry
    ae_g = ax_line.endSketchPoint.geometry
    ax_len = math.sqrt((ae_g.x - as_g.x)**2 + (ae_g.y - as_g.y)**2)

    def pt_abs(dist_from_start, radius):
        """Point at absolute distance from axis start + radius offset."""
        return P(as_g.x + ux * dist_from_start + anx * radius,
                 as_g.y + uy * dist_from_start + any_ * radius, 0)

    # L1: perpendicular from A tip
    L1 = lines.addByTwoPoints(P(as_g.x, as_g.y, 0), pt_abs(0, end_r))
    gc.addCoincident(L1.startSketchPoint, ax_line.startSketchPoint)
    gc.addPerpendicular(L1, ax_line)

    # L2: tenon — parallel to axis
    L2 = lines.addByTwoPoints(L1.endSketchPoint, pt_abs(t_len, end_r))
    gc.addParallel(L2, ax_line)

    # L3: angled shoulder
    # For barrel: shoulder connects at (end_r + mid_r) / 2, arc reaches mid_r
    # For straight: shoulder connects directly at mid_r
    shoulder_r = (end_r + mid_r) / 2 if profile == "barrel" else mid_r
    L3 = lines.addByTwoPoints(L2.endSketchPoint,
                               pt_abs(t_len + s_len, shoulder_r))

    # ── Body section: straight or barrel ───────────────────────────
    if profile == "barrel":
        # Curved body: fitted spline with 2 symmetric control points.
        # Control points are defined by distance from midpoint and
        # radius from axis.
        _design = adsk.fusion.Design.cast(
            adsk.core.Application.get().activeProduct)
        barrel_dist = ev(f"{prefix}_barrel_dist") if \
            _design.userParameters.itemByName(f"{prefix}_barrel_dist") else \
            (ax_len / 2 - t_len - s_len) * 0.4
        barrel_r = ev(f"{prefix}_barrel_r") if \
            _design.userParameters.itemByName(f"{prefix}_barrel_r") else \
            mid_r

        body_start = (t_len + s_len)
        body_end = ax_len - t_len - s_len
        body_mid = ax_len / 2

        l3_g = L3.endSketchPoint.geometry
        spline_pts = adsk.core.ObjectCollection.create()
        spline_pts.add(P(l3_g.x, l3_g.y, 0))
        spline_pts.add(pt_abs(body_mid - barrel_dist, barrel_r))
        spline_pts.add(pt_abs(body_mid + barrel_dist, barrel_r))
        spline_pts.add(pt_abs(body_end, shoulder_r))
        body_curve = sk.sketchCurves.sketchFittedSplines.add(spline_pts)
        try:
            gc.addCoincident(body_curve.startSketchPoint, L3.endSketchPoint)
        except Exception:
            pass
        body_end_pt = body_curve.endSketchPoint
    else:
        # Straight body: two parallel lines (L4 + L5)
        L4 = lines.addByTwoPoints(L3.endSketchPoint,
                                   pt_abs(ax_len / 2, mid_r))
        gc.addParallel(L4, ax_line)
        L5 = lines.addByTwoPoints(L4.endSketchPoint,
                                   pt_abs(ax_len - t_len - s_len, mid_r))
        gc.addParallel(L5, ax_line)
        body_end_pt = L5.endSketchPoint

    # L6: angled shoulder (symmetric)
    L6 = lines.addByTwoPoints(body_end_pt,
                               pt_abs(ax_len - t_len, end_r))

    # L7: tenon — parallel
    L7 = lines.addByTwoPoints(L6.endSketchPoint, pt_abs(ax_len, end_r))
    gc.addParallel(L7, ax_line)

    # L8: perpendicular to B tip
    L8 = lines.addByTwoPoints(L7.endSketchPoint, P(ae_g.x, ae_g.y, 0))
    gc.addCoincident(L8.endSketchPoint, ax_line.endSketchPoint)
    gc.addPerpendicular(L8, ax_line)

    # ── Symmetry via mirror line at axis midpoint ────────────────
    mid_pt = P((as_g.x + ae_g.x) / 2, (as_g.y + ae_g.y) / 2, 0)
    sym_line = lines.addByTwoPoints(
        mid_pt,
        P(mid_pt.x + anx * 3, mid_pt.y + any_ * 3, 0))
    sym_line.isConstruction = True
    gc.addPerpendicular(sym_line, ax_line)
    gc.addMidPoint(sym_line.startSketchPoint, ax_line)

    gc.addSymmetry(L1.endSketchPoint, L7.endSketchPoint, sym_line)
    gc.addSymmetry(L2.endSketchPoint, L6.endSketchPoint, sym_line)
    gc.addSymmetry(L3.endSketchPoint, body_end_pt, sym_line)
    if profile == "barrel":
        # Mirror the two control fit points
        ctrl_L = body_curve.fitPoints.item(1)
        ctrl_R = body_curve.fitPoints.item(2)
        gc.addSymmetry(ctrl_L, ctrl_R, sym_line)

    # ── Dimensions ─────────────────────────────────────────────────
    # Tenon radius
    dims.addDistanceDimension(
        L1.startSketchPoint, L1.endSketchPoint, AL,
        P(as_g.x + anx * 2, as_g.y + any_ * 2, 0)
    ).parameter.expression = f"{prefix}_end_dia / 2"

    # Tenon length
    dims.addDistanceDimension(
        L2.startSketchPoint, L2.endSketchPoint, AL,
        P(pt_abs(t_len, end_r).x + anx, pt_abs(t_len, end_r).y + any_, 0)
    ).parameter.expression = f"{prefix}_tenon_len"

    # Body radius
    if profile == "barrel":
        # Barrel: constrain ctrl_L fit point with 2 dimensions:
        # perpendicular distance from axis (barrel_r) and
        # distance from midpoint along axis (barrel_dist).
        ctrl_L_pt = body_curve.fitPoints.item(1)
        ctrl_con = lines.addByTwoPoints(
            P(mid_pt.x - ux * barrel_dist, mid_pt.y - uy * barrel_dist, 0),
            P(ctrl_L_pt.geometry.x, ctrl_L_pt.geometry.y, 0))
        ctrl_con.isConstruction = True
        gc.addPerpendicular(ctrl_con, ax_line)
        gc.addCoincident(ctrl_con.startSketchPoint, ax_line)
        gc.addCoincident(ctrl_con.endSketchPoint, ctrl_L_pt)
        dims.addDistanceDimension(
            ctrl_con.startSketchPoint, ctrl_con.endSketchPoint, AL,
            P(mid_pt.x + anx * 2, mid_pt.y + any_ * 2, 0)
        ).parameter.expression = f"{prefix}_barrel_r"
        dims.addDistanceDimension(
            ctrl_con.startSketchPoint, sym_line.startSketchPoint, AL,
            P(mid_pt.x - ux * 2, mid_pt.y - uy * 2, 0)
        ).parameter.expression = f"{prefix}_barrel_dist"
    else:
        # Straight: body_con at midpoint, dimensioned by mid_dia/2
        body_con = lines.addByTwoPoints(
            P(mid_pt.x, mid_pt.y, 0),
            P(mid_pt.x + anx * mid_r, mid_pt.y + any_ * mid_r, 0))
        body_con.isConstruction = True
        gc.addPerpendicular(body_con, ax_line)
        gc.addCoincident(body_con.startSketchPoint, sym_line.startSketchPoint)
        gc.addCoincident(body_con.endSketchPoint, L4.endSketchPoint)
        dims.addDistanceDimension(
            body_con.startSketchPoint, body_con.endSketchPoint, AL,
            P(mid_pt.x + anx * 2, mid_pt.y + any_ * 2, 0)
        ).parameter.expression = f"{prefix}_mid_dia / 2"

    # Shoulder length (absolute)
    dims.addDistanceDimension(
        L2.endSketchPoint, L3.endSketchPoint, AL,
        P(pt_abs(t_len + s_len, mid_r).x + anx,
          pt_abs(t_len + s_len, mid_r).y + any_, 0)
    ).parameter.expression = f"{prefix}_shoulder_len"

    # ── Step 6: Revolve ────────────────────────────────────────────
    prof = sp.smallest_profile(sk)
    if not prof:
        print(f"{name}: no profile ({sk.profiles.count} profiles)")
        return None

    rev = comp.features.revolveFeatures.createInput(prof, ax_line, NEWBODY)
    rev.setAngleExtent(False, V("360 deg"))
    rf = comp.features.revolveFeatures.add(rev)
    rf.name = name
    body = rf.bodies.item(0)
    body.name = name

    print(f"Built {name}")
    return body


# ── Private helpers ─────────────────────────────────────────────────

def _default_ev():
    design = adsk.fusion.Design.cast(
        adsk.core.Application.get().activeProduct)
    def _ev(e):
        if isinstance(e, (int, float)):
            return float(e)
        p = design.userParameters.itemByName(e)
        if p:
            return p.value
        return design.unitsManager.evaluateExpression(e, "cm")
    return _ev


def _point_on_axis(comp, axis, dist_expr, name):
    """Create a dimensioned point on an axis (ConstructionAxis or SketchLine).

    For ConstructionAxis: creates a sketch on a plane through the axis,
    projects it, and dimensions a point along the projection.

    For SketchLine: works directly in the line's parent sketch.

    Returns (sketch_point, sketch) — the point and its parent sketch.
    """
    design = adsk.fusion.Design.cast(
        adsk.core.Application.get().activeProduct)

    if hasattr(axis, 'parentSketch'):
        # It's a sketch line — work in its sketch directly
        sk = axis.parentSketch
        proj_line = axis
    else:
        # It's a ConstructionAxis — create a sketch, project the two
        # construction points that define the axis (not the infinite axis
        # line, which projects with arbitrary endpoints).
        ax_comp = axis.component if hasattr(axis, 'component') else comp
        pl_inp = ax_comp.constructionPlanes.createInput()
        pl_inp.setByAngle(axis, V("90 deg"), ax_comp.xYConstructionPlane)
        pl = ax_comp.constructionPlanes.add(pl_inp)
        pl.name = f"{name}_Pl"

        sk = ax_comp.sketches.add(pl)
        sk.name = f"{name}_Sk"

        # Find the two construction points that define this axis
        # They were created by _leg_axis as {name}_End0 and {name}_End1
        cp0 = None; cp1 = None
        ax_name_base = axis.name.replace("_Ax", "")
        for ci in range(ax_comp.constructionPoints.count):
            cp = ax_comp.constructionPoints.item(ci)
            if cp.name == f"{ax_name_base}_End0":
                cp0 = cp
            elif cp.name == f"{ax_name_base}_End1":
                cp1 = cp

        if not cp0 or not cp1:
            # Fallback: project the axis (infinite line — less accurate)
            sk.project(axis)
            sp.refs_to_construction(sk)
            proj_line = None
            for ci in range(sk.sketchCurves.count):
                c = sk.sketchCurves.item(ci)
                if c.objectType.endswith('SketchLine') and \
                   (c.isConstruction or c.isReference):
                    proj_line = c
                    break
            if not proj_line:
                print(f"{name}: could not find projected axis")
                return None, None
        else:
            # Project the two endpoints and draw a line between them
            sk.project(cp0)
            sk.project(cp1)
            m2s = sk.modelToSketchSpace
            p0 = m2s(cp0.geometry)
            p1 = m2s(cp1.geometry)
            # Find projected sketch points
            best0 = None; best1 = None; d0 = 1e10; d1 = 1e10
            for pi in range(sk.sketchPoints.count):
                pt = sk.sketchPoints.item(pi)
                if pt == sk.originPoint: continue
                g = pt.geometry
                dd0 = math.sqrt((g.x-p0.x)**2 + (g.y-p0.y)**2)
                dd1 = math.sqrt((g.x-p1.x)**2 + (g.y-p1.y)**2)
                if dd0 < d0: d0 = dd0; best0 = pt
                if dd1 < d1: d1 = dd1; best1 = pt
            if not best0 or not best1 or best0 == best1:
                print(f"{name}: could not find projected endpoints")
                return None, None
            # Draw axis line between projected endpoints
            proj_line = sk.sketchCurves.sketchLines.addByTwoPoints(
                P(best0.geometry.x, best0.geometry.y, 0),
                P(best1.geometry.x, best1.geometry.y, 0))
            proj_line.isConstruction = True
            sk.geometricConstraints.addCoincident(
                proj_line.startSketchPoint, best0)
            sk.geometricConstraints.addCoincident(
                proj_line.endSketchPoint, best1)

    gc = sk.geometricConstraints
    dims = sk.sketchDimensions
    lines = sk.sketchCurves.sketchLines

    start = proj_line.startSketchPoint.geometry
    end = proj_line.endSketchPoint.geometry
    dx = end.x - start.x
    dy = end.y - start.y
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.01:
        return None, None
    ux, uy = dx / length, dy / length

    try:
        dist_val = design.unitsManager.evaluateExpression(dist_expr, "cm")
    except Exception:
        dist_val = length * 0.4

    approx = P(start.x + ux * dist_val, start.y + uy * dist_val, 0)

    seg = lines.addByTwoPoints(P(start.x, start.y, 0), approx)
    seg.isConstruction = True

    gc.addCoincident(seg.startSketchPoint, proj_line.startSketchPoint)
    gc.addCollinear(seg, proj_line)
    dims.addDistanceDimension(
        seg.startSketchPoint, seg.endSketchPoint, AL,
        P(approx.x + 1, approx.y + 1, 0)
    ).parameter.expression = dist_expr

    return seg.endSketchPoint, sk


def _construction_point(comp, sketch_point, name):
    """Create a construction point from a sketch point."""
    try:
        cp_inp = comp.constructionPoints.createInput()
        cp_inp.setByPoint(sketch_point)
        cp = comp.constructionPoints.add(cp_inp)
        cp.name = name
        return cp
    except Exception as e:
        print(f"{name}: construction point failed: {e}")
        return None
