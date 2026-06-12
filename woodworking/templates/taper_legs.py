"""Leg taper template — wedge cuts on the inner faces of furniture legs.

Tapers a leg from full cross-section at ``run`` along the leg above the
foot down to ``leg_size - amount`` at the foot. The classic modern/Shaker
detail: taper the two INNER faces so the outer silhouette stays plumb.

Orientation-agnostic: all geometry is anchored to the leg's own BRep —
the profile is drawn from the projected shared edges between the leg's
faces, dimensioned with ALIGNED dims along those edges, and the cut
direction is derived from the face normal. The same call works for:

  * straight (axis-aligned) legs
  * raked legs        (blank rotated about one axis via Move)
  * splayed legs      (compound rake + splay rotation)

Apply the taper AFTER any Move/rotation — the cut anchors to the rotated
faces, and the removed volume is rotation-invariant, so analytic volume
checks stay exact.

Why this template exists: hand-rolled taper sketches with raw coordinates
on the xZ construction plane land at model -Z (sketch-Y maps to model -Z)
— the wedge is drawn below the floor and the CUT silently removes nothing
while reporting a healthy body. This template cannot make that mistake
(no raw plane coordinates anywhere) and additionally RAISES if the cut
removed no material.

Usage:
    from woodworking.templates import taper_legs

    taper_legs.define_params(params, amount="0.5 in", run="25 in")

    # High level: taper the two side faces that look toward the
    # table/stool center (works for straight AND angled legs):
    taper_legs.inner_pair(comp, leg_body,
        center=(ev("frame_l / 2"), ev("frame_w / 2"), 0),
        ev=ev, thick_expr="leg_size * 2", name="Taper")

    # Low level: taper one explicit face:
    taper_legs.cut(comp, leg_body, taper_face, ev=ev,
        thick_expr="leg_size * 2", name="TaperX")

    # Then mirror_body / pattern the finished leg as usual.
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
ALIGNED = adsk.fusion.DimensionOrientations.AlignedDimensionOrientation
P3 = adsk.core.Point3D.create

METADATA = {
    "name": "taper_legs",
    "category": "details",
    "description": "Wedge taper cuts on leg inner faces, anchored to the "
                   "leg's own edges — works on straight, raked, and "
                   "splayed legs",
    "variants": {
        "cut": {
            "description": "Taper one face (wedge cut anchored to the "
                           "foot corner, run measured along the leg edge)",
            "best_for": ["single-face tapers", "custom face selection"],
        },
        "inner_pair": {
            "description": "Taper the two side faces facing a center "
                           "point — the standard 4-leg furniture detail",
            "best_for": ["tables", "stools", "benches", "desks"],
        },
    },
    "params": {
        "amount": "Taper amount at the foot (per face)",
        "run": "Taper length, measured along the leg edge from the foot",
    },
}


def define_params(params, prefix="tp", amount="0.5 in", run="24 in"):
    """Define taper parameters: {prefix}_amt, {prefix}_run."""
    VI = adsk.core.ValueInput.createByString
    if not params.itemByName(f"{prefix}_amt"):
        params.add(f"{prefix}_amt", VI(amount), "in",
                   "Leg taper amount at foot")
    if not params.itemByName(f"{prefix}_run"):
        params.add(f"{prefix}_run", VI(run), "in",
                   "Leg taper run from foot along the leg")
    return {"amt": f"{prefix}_amt", "run": f"{prefix}_run"}


def _shared_edge(face_a, face_b):
    """The BRepEdge shared by two faces of the same body."""
    ids = {face_b.edges.item(i).tempId for i in range(face_b.edges.count)}
    for i in range(face_a.edges.count):
        e = face_a.edges.item(i)
        if e.tempId in ids:
            return e
    return None


def _shared_vertex(edge_a, edge_b):
    """The BRepVertex shared by two edges."""
    for va in (edge_a.startVertex, edge_a.endVertex):
        for vb in (edge_b.startVertex, edge_b.endVertex):
            if va.tempId == vb.tempId:
                return va
    return None


def _other_vertex(edge, vertex):
    if edge.startVertex.tempId == vertex.tempId:
        return edge.endVertex
    return edge.startVertex


def _planar_faces(body):
    out = []
    for i in range(body.faces.count):
        f = body.faces.item(i)
        if isinstance(f.geometry, adsk.core.Plane):
            out.append(f)
    return out


def _outward_normal(face):
    ok, n = face.evaluator.getNormalAtPoint(face.pointOnFace)
    return n if ok else face.geometry.normal


def foot_face(body):
    """The leg's bottom (foot) face: lowest planar face with a mostly
    downward normal. Tolerates rake/splay up to ~45 degrees."""
    best, best_z = None, 1e18
    for f in _planar_faces(body):
        n = _outward_normal(f)
        if n.z < -0.5 and f.pointOnFace.z < best_z:
            best, best_z = f, f.pointOnFace.z
    return best


def _profile_face_for(body, taper_face, end_face):
    """A side face adjacent to taper_face to host the wedge sketch:
    shares an edge with BOTH taper_face and the foot, isn't either of
    them, and has the largest area among candidates."""
    t_ids = {taper_face.edges.item(i).tempId
             for i in range(taper_face.edges.count)}
    e_ids = {end_face.edges.item(i).tempId
             for i in range(end_face.edges.count)}
    best, best_area = None, -1.0
    for f in _planar_faces(body):
        if f.tempId in (taper_face.tempId, end_face.tempId):
            continue
        f_ids = {f.edges.item(i).tempId for i in range(f.edges.count)}
        if not (f_ids & t_ids) or not (f_ids & e_ids):
            continue
        if f.area > best_area:
            best, best_area = f, f.area
    return best


def cut(comp, body, taper_face, ev, amt_expr="tp_amt", run_expr="tp_run",
        thick_expr=None, end_face=None, name="Taper"):
    """Wedge-cut ``taper_face`` from ``run`` above the foot to ``amount``
    at the foot. All sketch geometry is anchored to projected leg edges
    (no plane coordinates), so it is valid for any leg orientation.

    Args:
        comp: Component owning ``body`` (sketch + cut live here).
        body: The leg body.
        taper_face: The planar face to taper (an inner face, usually).
        ev: Evaluator function.
        amt_expr / run_expr: Positive parameter expressions.
        thick_expr: Cut depth through the leg. Pass a parametric
            expression like "leg_size * 2"; default bakes 2x the body's
            bbox diagonal (prints a note — fine for fixtures, prefer an
            expression in real builds).
        end_face: The foot face; auto-detected (lowest face) if None.
        name: Feature name prefix.

    Returns:
        The cut ExtrudeFeature.

    Raises:
        RuntimeError if the cut removed no material (zero-impact guard).
    """
    if end_face is None:
        end_face = foot_face(body)
    if end_face is None:
        raise RuntimeError(f"{name}: could not find the leg's foot face")

    profile_face = _profile_face_for(body, taper_face, end_face)
    if profile_face is None:
        raise RuntimeError(
            f"{name}: no side face adjacent to both the taper face and "
            f"the foot — is taper_face a side face of a prismatic leg?")

    e_taper = _shared_edge(profile_face, taper_face)
    e_foot = _shared_edge(profile_face, end_face)
    if e_taper is None or e_foot is None:
        raise RuntimeError(f"{name}: profile face does not share edges "
                           f"with taper/foot faces")
    v_corner = _shared_vertex(e_taper, e_foot)
    if v_corner is None:
        raise RuntimeError(f"{name}: taper edge and foot edge share no "
                           f"corner vertex")
    v_top = _other_vertex(e_taper, v_corner)
    v_far = _other_vertex(e_foot, v_corner)

    # Sketch on a 0-offset plane from the side face (NOT the BRepFace
    # itself — projecting a sketch's host face yields non-reference
    # curves that can't anchor geometry).
    plane = sp.off_plane(comp, profile_face, "0 in", f"{name}_Pl")
    sk = comp.sketches.add(plane)
    sk.name = f"{name}_Sk"

    proj_t = sk.project(e_taper).item(0)   # leg edge on the taper side
    proj_f = sk.project(e_foot).item(0)    # foot edge
    sp.refs_to_construction(sk)

    m2s = sk.modelToSketchSpace

    def _nearest_endpoint(line, model_pt):
        target = m2s(model_pt)
        s, e = line.startSketchPoint, line.endSketchPoint
        ds = (s.geometry.x - target.x) ** 2 + (s.geometry.y - target.y) ** 2
        de = (e.geometry.x - target.x) ** 2 + (e.geometry.y - target.y) ** 2
        return s if ds <= de else e

    b_pt = _nearest_endpoint(proj_t, v_corner.geometry)

    amt_v = ev(amt_expr)
    run_v = ev(run_expr)

    def _lerp(p_from, p_to, dist):
        dx = p_to.x - p_from.x
        dy = p_to.y - p_from.y
        dz = p_to.z - p_from.z
        ln = (dx * dx + dy * dy + dz * dz) ** 0.5
        f = dist / ln
        return P3(p_from.x + dx * f, p_from.y + dy * f, p_from.z + dz * f)

    a_model = _lerp(v_corner.geometry, v_top.geometry, run_v)
    c_model = _lerp(v_corner.geometry, v_far.geometry, amt_v)
    a_sk = m2s(a_model)
    c_sk = m2s(c_model)

    lines = sk.sketchCurves.sketchLines
    l_run = lines.addByTwoPoints(b_pt, P3(a_sk.x, a_sk.y, 0))
    l_amt = lines.addByTwoPoints(b_pt, P3(c_sk.x, c_sk.y, 0))
    lines.addByTwoPoints(l_run.endSketchPoint, l_amt.endSketchPoint)

    gc = sk.geometricConstraints
    gc.addCollinear(l_run, proj_t)
    gc.addCollinear(l_amt, proj_f)

    d = sk.sketchDimensions
    bg = b_pt.geometry
    d.addDistanceDimension(
        l_run.startSketchPoint, l_run.endSketchPoint, ALIGNED,
        P3((bg.x + a_sk.x) / 2 + 0.4, (bg.y + a_sk.y) / 2 + 0.4, 0)
    ).parameter.expression = run_expr
    d.addDistanceDimension(
        l_amt.startSketchPoint, l_amt.endSketchPoint, ALIGNED,
        P3((bg.x + c_sk.x) / 2 - 0.4, (bg.y + c_sk.y) / 2 - 0.4, 0)
    ).parameter.expression = amt_expr

    # Cut INTO the body: positive extrude follows the sketch normal,
    # flip when that normal points outward from the profile face.
    if thick_expr is None:
        bb = body.boundingBox
        diag = ((bb.maxPoint.x - bb.minPoint.x) ** 2 +
                (bb.maxPoint.y - bb.minPoint.y) ** 2 +
                (bb.maxPoint.z - bb.minPoint.z) ** 2) ** 0.5
        thick_expr = f"{2 * diag:.4f} cm"
        print(f"{name}: thick_expr defaulted to baked {thick_expr} — "
              f"pass a parametric expression for production builds")
    nrm = sk.xDirection.crossProduct(sk.yDirection)
    out = _outward_normal(profile_face)
    flip = (nrm.dotProduct(out) > 0)

    vol_before = body.volume
    feat = sp.ext_op(comp, sp.smallest_profile(sk), thick_expr,
                     CUT, body, f"{name}_Cut", flip=flip)
    removed = vol_before - body.volume
    if removed <= 0.01:
        raise RuntimeError(
            f"{name}: taper cut removed nothing (volume {vol_before:.2f} "
            f"-> {body.volume:.2f} cm3) — wedge missed the leg")
    print(f"{name}: removed {removed:.2f} cm3")
    return feat


def inner_pair(comp, body, center, ev, amt_expr="tp_amt",
               run_expr="tp_run", thick_expr=None, name="Taper"):
    """Taper the two side faces of a leg that face a center point —
    the standard inner-face taper on 4-leg furniture. ``center`` is an
    (x, y, z) tuple in cm (e.g. the table footprint center); z is
    ignored. Face selection uses outward normals, so it works for
    straight, raked, and splayed legs alike.

    Returns the two cut features.
    """
    cx, cy = center[0], center[1]
    candidates = []
    for f in _planar_faces(body):
        n = _outward_normal(f)
        if abs(n.z) > 0.7:
            continue                     # top/bottom, not a side
        p = f.pointOnFace
        toward = n.x * (cx - p.x) + n.y * (cy - p.y)
        if toward > 0:
            candidates.append((toward, f, n))
    if len(candidates) < 2:
        raise RuntimeError(f"{name}: found {len(candidates)} inner side "
                           f"face(s), expected 2 — check center point")
    candidates.sort(key=lambda t: -t[0])
    first = candidates[0]
    second = None
    for cand in candidates[1:]:
        if abs(first[2].dotProduct(cand[2])) < 0.7:
            second = cand
            break
    if second is None:
        raise RuntimeError(f"{name}: could not find two perpendicular "
                           f"inner faces")

    f1 = cut(comp, body, first[1], ev, amt_expr, run_expr,
             thick_expr, None, f"{name}A")
    # Re-detect the foot for the second cut — the first cut shrank it.
    f2 = cut(comp, body, second[1], ev, amt_expr, run_expr,
             thick_expr, None, f"{name}B")
    return f1, f2
