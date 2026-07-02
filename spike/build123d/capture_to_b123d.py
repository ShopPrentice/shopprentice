"""Deterministic Fusion-capture -> build123d converter (migration route 2).

Input:  a full capture_design JSON from the Fusion add-in (solved sketch
        coordinates, feature timeline, parameter table, per-body ground truth).
Output: the same solids rebuilt headless on OpenCASCADE, PARITY-CHECKED
        against the capture's per-body volume + bbox, exported for the viewer.

Feature vocabulary (pencil-box tier): Sketch, Extrude (Distance), Combine,
RectangularPattern, ConstructionPlane (no-op: sketches carry their own world
frame), ComponentCreation (no-op: grouping only).

The one thing the capture does NOT record is extrude DIRECTION. It is
resolved deterministically by building both candidate prisms and scoring:
  Cut        -> exact intersection volume with the participant solids
                (a cut that removes nothing is the wrong way)
  Join/New   -> bbox-overlap volume with the body's FINAL captured bbox
                (falls back to the whole-model bbox for intermediate bodies)
Pattern direction signs are resolved the same way against the target's
final bbox.
"""
import json
import math
import re
import sys

from build123d import Solid, Face, Wire, Edge, Vector, Location, Plane
from b123d_common import Model

UNIT = {"in": 2.54, "mm": 0.1, "cm": 1.0, "m": 100.0,
        "deg": math.pi / 180.0, "rad": 1.0}
_LIT = re.compile(r"(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(in|mm|cm|m|deg|rad)\b")
AXIS = {"X": Vector(1, 0, 0), "Y": Vector(0, 1, 0), "Z": Vector(0, 0, 1)}


class Expr:
    """Evaluate Fusion parameter expressions. Captured parameter values are
    already in internal units (cm / rad), so only literals need converting."""

    def __init__(self, params):
        self.env = {p["name"]: p["value"] for p in params}
        self.env.update(tan=math.tan, sin=math.sin, cos=math.cos,
                        atan=math.atan, sqrt=math.sqrt, abs=abs, pi=math.pi,
                        floor=math.floor, ceil=math.ceil, round=round,
                        max=max, min=min)

    def __call__(self, expr):
        s = _LIT.sub(lambda m: "(%s*%r)" % (m.group(1), UNIT[m.group(2)]),
                     str(expr))
        return float(eval(s, {"__builtins__": {}}, dict(self.env)))


# ---------------------------------------------------------------------------
# sketch reconstruction
# ---------------------------------------------------------------------------
def _close(a, b, tol=1e-6):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def _arc_pts(c, n=17):
    """Sample an Arc curve's 2D points. Direction is not captured; use the
    MINOR arc (wrapped half-delta) — sweepAngle, when present, overrides."""
    (sx, sy), (ex, ey) = c["start"], c["end"]
    cx, cy = c["center"]
    r = c["radius"]
    a0 = math.atan2(sy - cy, sx - cx)
    a1 = math.atan2(ey - cy, ex - cx)
    delta = (a1 - a0) % (2 * math.pi)
    if delta > math.pi:
        delta -= 2 * math.pi                      # minor arc
    mid = c.get("mid")
    if mid:
        # capture records an exact on-arc midpoint: pick whichever of the
        # two candidate arcs passes through it (no convention needed)
        am = a0 + delta / 2
        p_minor = (cx + r * math.cos(am), cy + r * math.sin(am))
        if math.hypot(p_minor[0] - mid[0], p_minor[1] - mid[1]) > 1e-2:
            delta = math.copysign(2 * math.pi - abs(delta), -delta)
    return [(cx + r * math.cos(a0 + delta * k / (n - 1)),
             cy + r * math.sin(a0 + delta * k / (n - 1))) for k in range(n)]


def _pts_of(c):
    return c["fitPoints"] if c["type"] == "FittedSpline" else c["points"]


def _ends(c):
    if c["type"] == "FittedSpline":
        p = _pts_of(c)
        return tuple(p[0]), tuple(p[-1])
    # EllipticalArc: start/end come from the shared sketch points (exact
    # match with neighbours); the sampled "points" drift ~1e-3
    return tuple(c["start"]), tuple(c["end"])


def sketch_loops(sk):
    """Chain solid Line/Arc/FittedSpline curves into closed loops (lists of
    curve dicts). Full Circles are single-curve loops of their own.

    Fusion profiles may be BOUNDED by projected reference curves (scripts
    convert refs to construction only after using the profile, so flags
    can't be trusted): when strict chaining dead-ends, bridge to the nearest
    dangling endpoint that shares a reference line with the current end."""
    solid_curves = [c for c in sk["curves"]
                    if not c.get("isConstruction") and not c.get("isReference")]
    loops = [[c] for c in solid_curves if c["type"] == "Circle"]
    pool = [c for c in solid_curves
            if c["type"] in ("Line", "Arc", "FittedSpline", "EllipticalArc")]
    refs = [c for c in sk["curves"]
            if c.get("isReference") and c["type"] == "Line"]

    def on_ref(p, q):
        for L in refs:
            (ax, ay), (bx, by) = L["start"], L["end"]
            vx, vy = bx - ax, by - ay
            ln = math.hypot(vx, vy)
            if ln < 1e-9:
                continue
            if all(abs((px - ax) * vy - (py - ay) * vx) / ln < 2e-3
                   and -0.05 < ((px - ax) * vx + (py - ay) * vy) / (ln * ln) < 1.05
                   for px, py in (p, q)):
                return True
        return False

    while pool:
        c = pool.pop()
        chain, (start, end) = [c], _ends(c)
        while not _close(end, start):
            for k, s in enumerate(pool):
                sa, sb = _ends(s)
                if _close(sa, end):
                    chain.append(pool.pop(k)); end = sb; break
                if _close(sb, end):
                    chain.append(pool.pop(k)); end = sa; break
            else:
                cands = []
                if math.hypot(end[0] - start[0], end[1] - start[1]) > 1e-6 \
                        and on_ref(end, start):
                    cands.append((math.hypot(end[0] - start[0],
                                             end[1] - start[1]), start))
                for s in pool:
                    for pt in _ends(s):
                        if on_ref(end, pt):
                            cands.append((math.hypot(end[0] - pt[0],
                                                     end[1] - pt[1]), pt))
                cands = [c_ for c_ in cands if c_[0] > 1e-6]
                if not cands:
                    raise ValueError(f"open loop in sketch {sk['name']}")
                _, pt = min(cands)
                chain.append({"type": "Line", "start": list(end), "end": list(pt)})
                end = tuple(pt)
        loops.append(chain)
    return loops


def _loop_pts2d(loop):
    pts = []
    for c in loop:
        if c["type"] == "Circle":
            cx, cy = c["center"]; r = c["radius"]
            pts += [(cx - r, cy - r), (cx + r, cy + r)]
            continue
        if c["type"] in ("FittedSpline", "EllipticalArc"):
            pts += [tuple(q) for q in _pts_of(c)]
            continue
        pts.extend([tuple(c["start"]), tuple(c["end"])])
        if c["type"] == "Arc":
            pts.extend(_arc_pts(c))
    return pts


_ASSIGN_CACHE = {}


def _assign_regions(sk, regions_2d):
    """Partition arrangement regions among a sketch's profiles EXCLUSIVELY:
    profiles claim regions in ascending recorded-area order (most
    constrained first), so a large profile cannot steal a sliver that a
    smaller overlapping profile needs to reach its exact area."""
    profs = sk.get("profiles") or []
    order = sorted((p_ for p_ in profs if "area" in p_),
                   key=lambda p_: p_["area"])
    assigned = {}
    taken = set()
    tol, near = 2e-2, 0.35
    for p_ in order:
        pmin, pmax, target = p_["min"], p_["max"], p_["area"]
        cands = [i for i, (fc, (umin, vmin, umax, vmax)) in enumerate(regions_2d)
                 if i not in taken
                 and umin > pmin[0] - tol and vmin > pmin[1] - tol
                 and umax < pmax[0] + tol and vmax < pmax[1] + tol]
        got = sum(regions_2d[i][0].area for i in cands)
        if got < target - max(0.001 * target, 0.02):
            extra = [i for i, (fc, (umin, vmin, umax, vmax)) in enumerate(regions_2d)
                     if i not in taken and i not in cands
                     and umin > pmin[0] - near and vmin > pmin[1] - near
                     and umax < pmax[0] + near and vmax < pmax[1] + near]
            extra.sort(key=lambda i: regions_2d[i][0].area)
            for i in extra:
                a_ = regions_2d[i][0].area
                if got + a_ <= target * 1.01 + 0.01:
                    cands.append(i); got += a_
                if got >= target - max(0.001 * target, 0.02):
                    break
        if got > target * 1.01 + 0.01:
            cands.sort(key=lambda i: -regions_2d[i][0].area)
            kept, tot = [], 0.0
            for i in cands:
                a_ = regions_2d[i][0].area
                if tot + a_ <= target * 1.01 + 0.01:
                    kept.append(i); tot += a_
            cands, got = kept, tot
        assigned[p_["index"]] = cands
        taken.update(cands)
    return assigned


def _arrangement_face(sk, profile_index):
    """Planar-arrangement fallback: Fusion profiles can be bounded by
    projected reference geometry meeting at ref/ref corners, which loop
    chaining cannot synthesize. Split a large plane face by every live curve
    (solid + reference lines) and bbox-match the resulting region."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Splitter
    from OCP.TopTools import TopTools_ListOfShape
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    prof = sk["profiles"][profile_index]
    pmin, pmax = prof["min"], prof["max"]
    o = Vector(*sk["sketchOrigin"])
    xd = Vector(*sk["sketchXDir"]); yd = Vector(*sk["sketchYDir"])

    def w(p):
        return o + xd * p[0] + yd * p[1]

    curves = [c for c in sk["curves"] if not
              (c.get("isConstruction") and not c.get("isReference"))]
    pts2 = []
    edges = []
    for c in curves:
        try:
            if c["type"] == "Line":
                a, b = tuple(c["start"]), tuple(c["end"])
                if _close(a, b):
                    continue
                edges.append(Edge.make_line(w(a), w(b)))
                pts2 += [a, b]
            elif c["type"] == "Arc":
                pth = _arc_pts(c)
                edges.append(Edge.make_three_point_arc(
                    w(c["start"]), w(pth[len(pth) // 2]), w(c["end"])))
                pts2 += pth
            elif c["type"] in ("FittedSpline", "EllipticalArc"):
                pp = _pts_of(c)
                edges.append(Edge.make_spline([w(q) for q in pp]))
                pts2 += [tuple(q) for q in pp]
            elif c["type"] == "Circle":
                pl = Plane(origin=w(c["center"]), x_dir=xd, z_dir=xd.cross(yd))
                edges.append(Edge.make_circle(c["radius"], pl))
                cx, cy = c["center"]; r = c["radius"]
                pts2 += [(cx - r, cy - r), (cx + r, cy + r)]
        except Exception:
            pass
    if not edges:
        raise ValueError(f"no curves for arrangement in {sk['name']}")
    xs = [p[0] for p in pts2]; ys = [p[1] for p in pts2]
    m = 5.0
    big = Face(Wire.make_polygon([
        w((min(xs) - m, min(ys) - m)), w((max(xs) + m, min(ys) - m)),
        w((max(xs) + m, max(ys) + m)), w((min(xs) - m, max(ys) + m))]))
    sp = BRepAlgoAPI_Splitter()
    args = TopTools_ListOfShape(); args.Append(big.wrapped)
    tools = TopTools_ListOfShape()
    for e in edges:
        tools.Append(e.wrapped)
    sp.SetArguments(args); sp.SetTools(tools)
    sp.SetFuzzyValue(1e-3)
    sp.Build()
    # collect every region INSIDE the profile bbox and fuse them: reference
    # curves crossing the region split it into sub-faces (their construction
    # flags at profile-consume time are unrecoverable), but the union of
    # inside-regions is exactly the Fusion profile
    def _rebuild_poly(fc):
        """Rebuild a splitter-output face as a fresh polygonal face —
        splitter faces carry pcurve baggage that can poison later pairwise
        booleans (cuts silently no-op against long-boolean-chain targets)."""
        try:
            pts = []
            for e_ in fc.outer_wire().order_edges():
                n_ = max(2, int(e_.length / 0.05) + 1)
                seg = [e_.position_at(k_ / (n_ - 1)) for k_ in range(n_)]
                if pts and (seg[0] - pts[-1]).length > 1e-4:
                    seg = seg[::-1]
                pts.extend(seg if not pts else seg[1:])
            if (pts[-1] - pts[0]).length < 1e-4:
                pts = pts[:-1]
            # drop near-duplicate consecutive points
            clean = [pts[0]]
            for q_ in pts[1:]:
                if (q_ - clean[-1]).length > 1e-4:
                    clean.append(q_)
            return Face(Wire.make_polygon(clean))
        except Exception:
            return fc

    exp = TopExp_Explorer(sp.Shape(), TopAbs_FACE)
    regions_2d = []
    tol = 2e-2
    near = 0.35
    big_area = big.area
    while exp.More():
        fc = Face(TopoDS.Face_s(exp.Current()))
        exp.Next()
        u, v = [], []
        for vt in fc.vertices():
            rel = Vector(vt.X, vt.Y, vt.Z) - o
            u.append(rel.dot(xd)); v.append(rel.dot(yd))
        if u and fc.area < big_area * 0.9:
            regions_2d.append((fc, (min(u), min(v), max(u), max(v))))
    # exclusive assignment when the sketch has multiple area-recorded
    # profiles (overlapping bboxes can otherwise steal each other's slivers)
    profs = sk.get("profiles") or []
    if len(profs) > 1 and all("area" in p_ for p_ in profs):
        key = id(sk)
        if key not in _ASSIGN_CACHE:
            _ASSIGN_CACHE[key] = _assign_regions(sk, regions_2d)
        idxs = _ASSIGN_CACHE[key].get(profile_index, [])
        if idxs:
            return [_rebuild_poly(regions_2d[i][0]) for i in idxs], xd.cross(yd)
    inside, outside = [], []
    for fc, (umin, vmin, umax, vmax) in regions_2d:
        if umin > pmin[0] - tol and vmin > pmin[1] - tol \
                and umax < pmax[0] + tol and vmax < pmax[1] + tol:
            inside.append(fc)
        elif umin > pmin[0] - near and vmin > pmin[1] - near \
                and umax < pmax[0] + near and vmax < pmax[1] + near:
            outside.append(fc)
    target_area = prof.get("area")
    if inside and target_area:
        got = sum(f_.area for f_ in inside)
        if got < target_area - max(0.001 * target_area, 0.02) and outside:
            # union UNDER the recorded area: pull in the nearest excluded
            # regions (e.g. overshoot slivers past the strict bbox tol)
            outside.sort(key=lambda f_: f_.area)
            for f_ in outside:
                if got + f_.area <= target_area * 1.01 + 0.01:
                    inside.append(f_); got += f_.area
                if got >= target_area - max(0.001 * target_area, 0.02):
                    break
        if got > target_area * 1.01 + 0.01:
            # prune extra slivers: greedily keep largest regions up to the
            # recorded profile area
            inside.sort(key=lambda f_: -f_.area)
            kept, tot = [], 0.0
            for f_ in inside:
                if tot + f_.area <= target_area * 1.01 + 0.01:
                    kept.append(f_); tot += f_.area
            if kept and abs(tot - target_area) <= target_area * 0.02 + 0.01:
                inside = kept
    if not inside:
        # relaxed tier: some separating curves only partially cross a region
        # (Fusion still splits profiles there; the splitter does not). Accept
        # the smallest region CONTAINING the profile bbox within tight slack
        # — the excess is a sliver that neighbouring profiles would claim.
        slack = 0.12
        exp = TopExp_Explorer(sp.Shape(), TopAbs_FACE)
        cands = []
        while exp.More():
            fc = Face(TopoDS.Face_s(exp.Current()))
            exp.Next()
            u, v = [], []
            for vt in fc.vertices():
                rel = Vector(vt.X, vt.Y, vt.Z) - o
                u.append(rel.dot(xd)); v.append(rel.dot(yd))
            if u and min(u) > pmin[0] - slack and min(v) > pmin[1] - slack \
                    and max(u) < pmax[0] + slack and max(v) < pmax[1] + slack \
                    and max(u) - min(u) < (pmax[0] - pmin[0]) + 2 * slack:
                cands.append(fc)
        if cands:
            if target_area:
                pick = min(cands, key=lambda f_: abs(f_.area - target_area))
            else:
                pick = min(cands, key=lambda f_: f_.area)
            return [_rebuild_poly(pick)], xd.cross(yd)
        raise ValueError(
            f"arrangement: no region matches profile {profile_index} of {sk['name']}")
    return [_rebuild_poly(f_) for f_ in inside], xd.cross(yd)


def profile_face(sk, profile_index):
    """The face for profiles[profile_index], selected by 2D-bbox match."""
    prof = sk["profiles"][profile_index]
    pmin, pmax = prof["min"], prof["max"]
    o = Vector(*sk["sketchOrigin"])
    xd = Vector(*sk["sketchXDir"]); yd = Vector(*sk["sketchYDir"])

    def w(p):
        return o + xd * p[0] + yd * p[1]

    try:
        loops = sketch_loops(sk)
    except ValueError:
        faces, nrm = _arrangement_face(sk, profile_index)
        return faces, nrm
    for loop in loops:
        pts = _loop_pts2d(loop)
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        if not (abs(min(xs) - pmin[0]) < 5e-3 and abs(min(ys) - pmin[1]) < 5e-3
                and abs(max(xs) - pmax[0]) < 5e-3 and abs(max(ys) - pmax[1]) < 5e-3):
            continue
        if all(c["type"] == "Line" for c in loop):
            poly = [tuple(loop[0]["start"]), tuple(loop[0]["end"])]
            for c in loop[1:]:
                nxt = tuple(c["end"]) if _close(tuple(c["start"]), poly[-1]) \
                    else tuple(c["start"])
                poly.append(nxt)
            return [Face(Wire.make_polygon([w(p) for p in poly[:-1]]))], xd.cross(yd)
        if len(loop) == 1 and loop[0]["type"] == "Circle":
            c = loop[0]
            pl = Plane(origin=w(c["center"]), x_dir=xd, z_dir=xd.cross(yd))
            return [Face(Wire([Edge.make_circle(c["radius"], pl)]))], xd.cross(yd)
        edges, cur = [], _ends(loop[0])[0]
        for c in loop:
            ca, cb = _ends(c)
            flip = not _close(ca, cur)
            a, b = (cb, ca) if flip else (ca, cb)
            if c["type"] == "Line":
                edges.append(Edge.make_line(w(a), w(b)))
            elif c["type"] in ("FittedSpline", "EllipticalArc"):
                inner = [w(q) for q in _pts_of(c)[1:-1]]
                if flip:
                    inner = inner[::-1]
                # chain-exact endpoints; sampled points only for the interior
                edges.append(Edge.make_spline([w(a)] + inner + [w(b)]))
            else:
                # endpoints from the chain (exact match with the neighbour
                # lines); only the MID point comes from the sampled arc --
                # recomputed endpoints drift ~1e-3 off the rounded capture
                p = _arc_pts(c)
                edges.append(Edge.make_three_point_arc(
                    w(a), w(p[len(p) // 2]), w(b)))
            cur = tuple(b)
        return [Face(Wire(edges))], xd.cross(yd)
    return _arrangement_face(sk, profile_index)


# ---------------------------------------------------------------------------
# direction scoring
# ---------------------------------------------------------------------------
def _bb_overlap(a_bb, lo, hi):
    v = 1.0
    for mn, mx, l, h in ((a_bb.min.X, a_bb.max.X, lo[0], hi[0]),
                         (a_bb.min.Y, a_bb.max.Y, lo[1], hi[1]),
                         (a_bb.min.Z, a_bb.max.Z, lo[2], hi[2])):
        d = min(mx, h) - max(mn, l)
        if d <= 0:
            return 0.0
        v *= d
    return v


def _mesh_rebuild(solid, defl=0.05):
    """Rebuild a solid as a sewn triangle shell (mesh) — the nuclear option
    for OCCT pairwise-boolean pathology. Tiny volume error (deflection)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopoDS import TopoDS
    from OCP.ShapeFix import ShapeFix_Shell, ShapeFix_Solid
    verts, tris = solid.tessellate(defl)
    sew = BRepBuilderAPI_Sewing(1e-5)
    for t in tris:
        pts = [verts[i] for i in t]
        try:
            sew.Add(Face(Wire.make_polygon([Vector(p.X, p.Y, p.Z) for p in pts])).wrapped)
        except Exception:
            pass
    sew.Perform()
    exp = TopExp_Explorer(sew.SewedShape(), TopAbs_SHELL)
    fx = ShapeFix_Shell(TopoDS.Shell_s(exp.Current())); fx.Perform()
    sol = BRepBuilderAPI_MakeSolid(fx.Shell()).Solid()
    sfx = ShapeFix_Solid(sol); sfx.Perform()
    return Solid(sfx.Solid())


def _inter_vol(a, b):
    try:
        r = a & b
        return r.volume if r is not None else 0.0
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# the converter
# ---------------------------------------------------------------------------
def convert(capture_path, verbose=True):
    cap = json.load(open(capture_path))
    ev = Expr(cap["userParameters"])

    # ground truth: final body name -> (volume, bbox) and the model envelope
    truth = {}

    def walk(node):
        for b in node.get("bodies", []):
            truth[b["name"]] = (b["volume"],
                                b["boundingBox"]["min"], b["boundingBox"]["max"])
        for ch in node.get("children", []):
            walk(ch)
    walk(cap["components"])
    env_lo = [min(t[1][i] for t in truth.values()) for i in range(3)]
    env_hi = [max(t[2][i] for t in truth.values()) for i in range(3)]

    sketches = {}          # name -> sketch feature
    bodies = {}            # live body name -> solid
    feats = {}             # feature name -> LIST of {tool, op, targets}
    unnamed = []           # NewBody tools whose captured name list was empty
    warnings = []

    def resolve_tool(name, target):
        """A combine references a tool body the capture never named (its
        creating feature's bodies list was empty — consumed downstream).
        Pick the pooled unnamed solid that actually intersects the target."""
        if name in bodies:
            return bodies.pop(name) if False else bodies[name]
        if not unnamed:
            raise KeyError(f"unknown tool body {name!r}")
        best = max(range(len(unnamed)),
                   key=lambda i: _inter_vol(unnamed[i], target)
                   if target is not None else -i)
        return unnamed.pop(best)

    def consumer_of(body_name, after_index):
        """The first later Combine that uses body_name as a tool."""
        for g in cap["timeline"]:
            if (g["type"] == "Combine" and g["index"] > after_index
                    and body_name in g.get("toolBodies", [])):
                return g
        return None

    def mate_overlap(pr, exclude):
        """Tie-breaker: overlap with OTHER final bodies' bboxes. A cut void
        is normally occupied by a mating part (that's what joinery is), so
        the correct cutter direction tracks the mate's final bbox."""
        return max((_bb_overlap(pr.bounding_box(), lo, hi)
                    for n, (_, lo, hi) in truth.items() if n not in exclude),
                   default=0.0)

    def extrude_faces(faces, vec):
        out = None
        for fc in faces:
            pr = Solid.extrude(fc, vec)
            out = pr if out is None else out + pr
        return out

    def pick_direction(faces, normal, dist, f, sk=None):
        # improved captures record the end-face centroid: the direction sign
        # is sign(dot(endFaceCentroid - sketchOrigin, normal)) — exact, no
        # scoring needed
        endc = f.get("endFaceCentroid")
        if endc and sk:
            d = (Vector(*endc) - Vector(*sk["sketchOrigin"])).dot(normal)
            if abs(d) > 1e-6:
                mag = abs(dist)   # expression may be negative ("-apron_t")
                return extrude_faces(faces, normal * (mag if d > 0 else -mag))
        cands = [extrude_faces(faces, normal * (s * dist)) for s in (1, -1)]
        op = f["operation"]
        parts = f.get("participantBodies") or f.get("bodies") or []
        # bodies this feature acts on (directly, or via the combine that
        # will consume it) don't count as "mates" for the tie-breaker
        exclude = set(parts)
        cons = None
        names = f.get("bodies") or []
        if op == "NewBody" and names and names[0] not in truth:
            cons = consumer_of(names[0], f["index"])
            if cons:
                exclude.add(cons["targetBody"])
        scores = []
        for pr in cands:
            if op == "Cut":
                # the right way removes material from the participants -- and
                # must keep each participant in ONE piece: the capture records
                # this feature outputting len(bodies) bodies, so a direction
                # that splits a participant into extra lumps is wrong even
                # when the removed volume ties (the lid-rabbet failure mode:
                # both directions remove 50 cm^3, one severs the slab).
                s, intact = 0.0, True
                for p in parts:
                    if p not in bodies:
                        continue
                    s += _inter_vol(pr, bodies[p])
                    try:
                        if len((bodies[p] - pr).solids()) > 1:
                            intact = False
                    except Exception:
                        intact = False
                s = (1 if intact else 0, s)
            elif op == "Join":
                # the right way ADDS material: inside the final bbox but
                # NOT already inside the target (a join into existing stock
                # is a no-op — the lid-lip failure mode)
                ref = [truth[n] for n in parts if n in truth]
                s = (sum(_bb_overlap(pr.bounding_box(), r[1], r[2]) for r in ref)
                     if ref else _bb_overlap(pr.bounding_box(), env_lo, env_hi))
                s -= 2.0 * sum(_inter_vol(pr, bodies[p]) for p in parts if p in bodies)
            else:                                   # NewBody
                ref = [truth[n] for n in names if n in truth]
                if ref:
                    s = sum(_bb_overlap(pr.bounding_box(), r[1], r[2]) for r in ref)
                else:
                    # intermediate tool body: score against the target of the
                    # Combine that consumes it (looked up above)
                    tgt = bodies.get(cons["targetBody"]) if cons else None
                    if tgt is not None and cons["operation"] == "Cut":
                        s = _inter_vol(pr, tgt)
                    elif tgt is not None:
                        lo, hi = truth.get(cons["targetBody"], (0, env_lo, env_hi))[1:]
                        s = _bb_overlap(pr.bounding_box(), lo, hi) - 2 * _inter_vol(pr, tgt)
                    else:
                        s = _bb_overlap(pr.bounding_box(), env_lo, env_hi)
            # quantize: OCCT boolean volumes carry ~1e-15 noise; without
            # rounding, a genuinely-tied primary score never ties and the
            # mate tie-breaker never fires (the LGB failure mode)
            def q(v):
                return tuple(q(x) for x in v) if isinstance(v, tuple) else round(v, 6)
            scores.append((q(s), q(mate_overlap(pr, exclude))))
        if scores[0] == scores[1]:
            warnings.append(f"direction tie on {f['name']} — using +normal")
        import os
        if os.environ.get("CONV_DEBUG"):
            print(f"    dir {f['name']:<14} +:{scores[0]}  -:{scores[1]}  "
                  f"-> {'+' if scores[0] >= scores[1] else '-'}")
        return cands[0] if scores[0] >= scores[1] else cands[1]

    def apply(op, targets, tool, ctx):
        for t in targets:
            if t not in bodies:
                raise KeyError(f"{ctx}: unknown target body {t!r}")
            before = None
            try:
                before = bodies[t].volume
            except Exception:
                pass
            bodies[t] = bodies[t] - tool if op == "Cut" else bodies[t] + tool
            try:
                noop = (before is not None
                        and abs(bodies[t].volume - before) < 1e-6)
            except Exception:
                noop = False
            if noop and op == "Cut":
                # OCCT can silently no-op a cut when the TARGET's b-rep has
                # been degraded by long boolean chains: heal it and retry
                # (then a fuzzy boolean as last resort)
                from OCP.ShapeFix import ShapeFix_Shape
                from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
                from OCP.TopTools import TopTools_ListOfShape
                from build123d import Compound as _Comp
                try:
                    # exact-coincidence pair pathology: a micro-nudged deep
                    # copy of the tool (0.1 um) usually unsticks OCCT
                    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
                    cp_ = BRepBuilderAPI_Copy(tool.wrapped, True)
                    t_copy = _Comp(cp_.Shape())
                    tcs = t_copy.solids()
                    t_copy = tcs[0] if len(tcs) == 1 else t_copy
                    nudged = t_copy.moved(Location((1e-5, 1e-5, 1e-5)))
                    result = bodies[t] - nudged
                    if abs(result.volume - before) > 1e-6:
                        bodies[t] = result
                        print(f"  ++ {ctx}: nudged-cut recovered "
                              f"dV={result.volume - before:+.3f}")
                        continue
                    fx = ShapeFix_Shape(bodies[t].wrapped); fx.Perform()
                    hc = _Comp(fx.Shape()); hs = hc.solids()
                    healed = hs[0] if len(hs) == 1 else hc
                    result = healed - tool
                    if abs(result.volume - before) > 1e-6:
                        bodies[t] = result
                        print(f"  ++ {ctx}: healed-cut recovered "
                              f"dV={result.volume - before:+.3f}")
                        continue
                    cut = BRepAlgoAPI_Cut()
                    l1 = TopTools_ListOfShape(); l1.Append(healed.wrapped)
                    l2 = TopTools_ListOfShape(); l2.Append(tool.wrapped)
                    cut.SetArguments(l1); cut.SetTools(l2)
                    cut.SetFuzzyValue(1e-4); cut.Build()
                    out = _Comp(cut.Shape()); sols = out.solids()
                    fixed = sols[0] if len(sols) == 1 else out
                    if abs(fixed.volume - before) > 1e-6:
                        bodies[t] = fixed
                        print(f"  ++ {ctx}: fuzzy-cut recovered "
                              f"dV={fixed.volume - before:+.3f}")
                        continue
                    # nuclear: rebuild the tool as a sewn triangle mesh
                    mt = _mesh_rebuild(tool)
                    result = bodies[t] - mt
                    if abs(result.volume - before) > 1e-6:
                        bodies[t] = result
                        print(f"  ++ {ctx}: mesh-rebuilt-cut recovered "
                              f"dV={result.volume - before:+.3f}")
                    else:
                        print(f"  ~~ {ctx}: {op} on {t} NO-OP (all retries)")
                except Exception as e_:
                    print(f"  ~~ {ctx}: retry failed {str(e_)[:60]}")
            elif noop:
                print(f"  ~~ {ctx}: {op} on {t} was a NO-OP")
            try:
                if bodies[t].volume < 1e-9:
                    tb = tool.bounding_box()
                    print(f"  !! {ctx}: {t} became EMPTY after {op}; tool bbox "
                          f"x[{tb.min.X:.2f},{tb.max.X:.2f}] y[{tb.min.Y:.2f},{tb.max.Y:.2f}] "
                          f"z[{tb.min.Z:.2f},{tb.max.Z:.2f}]")
            except Exception:
                print(f"  !! {ctx}: {t} volume unreadable after {op}")

    for f in cap["timeline"]:
        ft = f["type"]
        if ft in ("ConstructionPlane", "ComponentCreation"):
            continue
        if ft == "Sketch":
            sketches[f["name"]] = f
            continue
        if ft == "Extrude":
            if f.get("hasTwoExtents") or f["extentType"] not in ("Distance", "Symmetric"):
                raise NotImplementedError(f"{f['name']}: {f['extentType']}")
            faces, normal = profile_face(sketches[f["sketch"]], f.get("profileIndex", 0))
            if f["extentType"] == "Symmetric":
                # isFullLength=True -> distance is TOTAL; False/absent ->
                # distance applies PER SIDE (sp.ext_sym convention)
                d2_ = ev(f["distance"])
                if f.get("isFullLength"):
                    d2_ /= 2
                tool = (extrude_faces(faces, normal * d2_)
                        + extrude_faces(faces, normal * -d2_))
            else:
                tool = pick_direction(faces, normal, ev(f["distance"]), f,
                                      sk=sketches[f["sketch"]])
            op = f["operation"]
            if op == "NewBody":
                for n in f["bodies"]:
                    bodies[n] = tool
                feats[f["name"]] = [{"tool": tool, "op": op, "targets": list(f["bodies"])}]
            elif op in ("Cut", "Join"):
                targets = f.get("participantBodies") or f["bodies"]
                apply(op, targets, tool, f["name"])
                feats[f["name"]] = [{"tool": tool, "op": op, "targets": list(targets)}]
            else:
                raise NotImplementedError(f"{f['name']}: extrude op {op}")
            continue
        if ft == "Combine":
            tgt_solid = bodies.get(f["targetBody"])
            tool = None
            for tb in f["toolBodies"]:
                t_ = bodies[tb] if tb in bodies else resolve_tool(tb, tgt_solid)
                tool = t_ if tool is None else tool + t_
            apply(f["operation"], [f["targetBody"]], tool, f["name"])
            if not f.get("isKeepToolBodies"):
                for tb in f["toolBodies"]:
                    bodies.pop(tb, None)
            continue
        if ft == "Remove":
            # capture buries the body name in the feature name
            n = (f.get("removedBody") or f.get("inputBody")
                 or f["name"].replace("RemoveBody-", "", 1))
            bodies.pop(n, None)
            continue
        if ft == "Sweep":
            sk = sketches[f["sketch"]]
            idxs = f.get("profileIndices") or [f.get("profileIndex", 0)]
            # resolve the world path from the captured sketch-curve entities
            pts = []
            for pe in f.get("path", []):
                if pe.get("source") != "SketchCurve" or "start" not in pe:
                    raise NotImplementedError(
                        f"{f['name']}: non-line sweep path ({pe.get('curveType')})")
                psk = sketches[pe["parentSketch"]]
                po = Vector(*psk["sketchOrigin"])
                pxd = Vector(*psk["sketchXDir"]); pyd = Vector(*psk["sketchYDir"])
                pts.append((po + pxd * pe["start"][0] + pyd * pe["start"][1],
                            po + pxd * pe["end"][0] + pyd * pe["end"][1]))
            # chain segments end-to-end -> overall start/end
            P0, P1 = pts[0]
            for a, b in pts[1:]:
                P1 = b if (a - P1).length < 1e-4 else a
            tools = []
            for pi in idxs:
                pfaces, _n = profile_face(sk, pi)
                c = pfaces[0].center()
                # sweep away from whichever path end the profile sits on
                vec = (P1 - P0) if (c - P0).length <= (c - P1).length else (P0 - P1)
                tools.append(extrude_faces(pfaces, vec))
            tool = tools[0]
            for t_ in tools[1:]:
                tool = tool + t_
            op = f["operation"]
            if op == "NewBody":
                if not f.get("bodies"):
                    unnamed.append(tool)     # name lost to downstream consume
                for n in f.get("bodies", []):
                    bodies[n] = tool
                feats[f["name"]] = [{"tool": tool, "op": op,
                                     "targets": list(f.get("bodies", []))}]
            else:
                targets = f.get("participantBodies") or f.get("bodies") or []
                apply(op, targets, tool, f["name"])
                feats[f["name"]] = [{"tool": tool, "op": op, "targets": list(targets)}]
            continue
        if ft == "Move":
            from OCP.gp import gp_Trsf
            from OCP.TopLoc import TopLoc_Location
            m16 = f.get("matrix")
            if m16:
                t = gp_Trsf()
                t.SetValues(*[float(x) for x in m16[:12]])
                loc = Location(TopLoc_Location(t))
            elif f.get("translation"):
                loc = Location(Vector(*f["translation"]))
            else:
                raise NotImplementedError(f"{f['name']}: Move without matrix")
            for n in (f.get("inputs") or f.get("bodies") or []):
                if n in bodies:
                    bodies[n] = bodies[n].moved(loc)
            continue
        if ft == "Loft":
            # OCCT ThruSections picks its own (sometimes self-crossing)
            # vertex correspondence, so polygon-section lofts are built as a
            # manually triangulated shell: correspondence = min total ruling
            # length across rotation/reversal of the second section.
            secs = f.get("sections", [])
            if not all(sec.get("outerVertices") for sec in secs) or len(secs) != 2:
                raise NotImplementedError(f"{f['name']}: unsupported loft sections")
            A = [Vector(*q) for q in secs[0]["outerVertices"]]
            s1_ = [Vector(*q) for q in secs[1]["outerVertices"]]
            if len(A) != len(s1_):
                raise NotImplementedError(f"{f['name']}: section vertex counts differ")
            best_, bestd_ = None, None
            for rev_ in (False, True):
                Bb_ = s1_[::-1] if rev_ else s1_
                for k_ in range(len(Bb_)):
                    B_ = Bb_[k_:] + Bb_[:k_]
                    d_ = sum((B_[i_] - A[i_]).length for i_ in range(len(B_)))
                    if bestd_ is None or d_ < bestd_:
                        bestd_, best_ = d_, B_
            B = best_
            n_ = len(A)
            tris = [(A[0], A[1], A[2]), (A[0], A[2], A[3]),
                    (B[0], B[2], B[1]), (B[0], B[3], B[2])] if n_ == 4 else []
            if n_ != 4:
                tris = [(A[0], A[i_], A[i_ + 1]) for i_ in range(1, n_ - 1)] + \
                       [(B[0], B[i_ + 1], B[i_]) for i_ in range(1, n_ - 1)]
            for i_ in range(n_):
                a_, b_ = A[i_], A[(i_ + 1) % n_]
                a2_, b2_ = B[i_], B[(i_ + 1) % n_]
                tris += [(a_, b_, b2_), (a_, b2_, a2_)]
            from OCP.BRepBuilderAPI import (BRepBuilderAPI_Sewing,
                                            BRepBuilderAPI_MakeSolid)
            from OCP.TopExp import TopExp_Explorer
            from OCP.TopAbs import TopAbs_SHELL
            from OCP.TopoDS import TopoDS
            from OCP.ShapeFix import ShapeFix_Shell, ShapeFix_Solid
            sew = BRepBuilderAPI_Sewing(1e-4)
            for t_ in tris:
                sew.Add(Face(Wire.make_polygon(list(t_))).wrapped)
            sew.Perform()
            exp_ = TopExp_Explorer(sew.SewedShape(), TopAbs_SHELL)
            fxs = ShapeFix_Shell(TopoDS.Shell_s(exp_.Current())); fxs.Perform()
            sol_ = BRepBuilderAPI_MakeSolid(fxs.Shell()).Solid()
            sfx = ShapeFix_Solid(sol_); sfx.Perform()
            tool = Solid(sfx.Solid())
            if tool.volume < 1e-6:
                raise ValueError(f"{f['name']}: loft solid degenerate")
            op = f["operation"]
            if op == "NewBody":
                if not f.get("bodies"):
                    unnamed.append(tool)
                for n in f.get("bodies", []):
                    bodies[n] = tool
            else:
                targets = f.get("participantBodies") or f.get("bodies") or []
                apply(op, targets, tool, f["name"])
            feats[f["name"]] = [{"tool": tool, "op": op,
                                 "targets": list(f.get("bodies", []))}]
            continue
        if ft == "SplitBody":
            # The splitting tool is a face reference we cannot replay directly,
            # but the capture records every fragment's volume+bbox at split
            # time (bodyGeo) and the following Removes delete all but the one
            # keeping the input name. Net effect: trim the input to the KEPT
            # fragment = input ∩ its recorded bbox, volume-gated.
            name = f["inputBody"]
            kept = (f.get("bodyGeo") or {}).get(name)
            if not kept or name not in bodies:
                raise NotImplementedError(f"{f['name']}: no fragment ground truth")
            lo, hi = kept["bbMin"], kept["bbMax"]
            pad = 0.01
            trim = Solid.make_box(hi[0]-lo[0]+2*pad, hi[1]-lo[1]+2*pad,
                                  hi[2]-lo[2]+2*pad).moved(
                Location((lo[0]-pad, lo[1]-pad, lo[2]-pad)))
            frag = bodies[name] & trim
            dv = abs(frag.volume - kept["volume"])
            if dv > max(0.03 * kept["volume"], 0.05):
                raise ValueError(f"{f['name']}: bbox-trim fragment volume "
                                 f"{frag.volume:.2f} != recorded {kept['volume']:.2f}")
            bodies[name] = frag
            continue
        if ft == "Mirror":
            pl = f["mirrorPlane"]
            plane = Plane(origin=Vector(*pl["origin"]), z_dir=Vector(*pl["normal"]))
            out = f.get("bodies") or []
            inputs = f.get("inputBodies", [])
            # FEATURE mirror (sp.mirror_feats): inputs name earlier features,
            # not bodies. Replay: mirror each source feature's tool solid and
            # apply its op to the mirrored-side target — chosen from the
            # affected-bodies list by overlap (current solid for cuts, final
            # bbox for joins).
            # improved captures classify inputs explicitly; otherwise infer:
            # feature-mode only for Cut/Join tool features (a NewBody feature
            # name, which can collide with body naming, means "mirror that
            # feature's output body" -> body mode below)
            if "inputFeatures" in f or "inputBodyNames" in f:
                feat_ins = [n for n in f.get("inputFeatures", []) if n in feats]
                inputs = f.get("inputBodyNames", [])
            else:
                feat_ins = [n for n in inputs
                            if n in feats and n not in bodies
                            and all(e["op"] in ("Cut", "Join") for e in feats[n])]
            if feat_ins:
                feats[f["name"]] = []
                for fn in feat_ins:
                    for src in feats[fn]:
                        tool = src["tool"].mirror(plane)

                        def tgt_score(n, _t=tool, _s=src):
                            if n not in bodies:
                                return -1.0
                            if _s["op"] == "Cut":
                                return _inter_vol(_t, bodies[n])
                            lo, hi = truth.get(n, (0, env_lo, env_hi))[1:]
                            return _bb_overlap(_t.bounding_box(), lo, hi) \
                                - 2 * _inter_vol(_t, bodies[n])
                        tgt = max(out, key=tgt_score)
                        apply(src["op"], [tgt], tool, f["name"])
                        # register so later patterns can replay the mirror
                        feats[f["name"]].append(
                            {"tool": tool, "op": src["op"], "targets": [tgt]})
                continue
            # BODY mirror: f["bodies"] contains BOTH copies and sources
            # (current names); inputBodies may carry stale pre-rename names
            # or NewBody FEATURE names (resolve to their output bodies).
            sources = [n for n in out if n in bodies]
            for n in inputs:
                if n in bodies and n not in sources:
                    sources.append(n)
                elif n in feats and feats[n][0]["op"] == "NewBody":
                    sources += [t for t in feats[n][0]["targets"]
                                if t in bodies and t not in sources]
            news = f.get("newBodies") or [n for n in out if n not in bodies]
            if not sources or not news:
                raise ValueError(f"{f['name']}: cannot split mirror sources/copies")
            mirrored = {s: bodies[s].mirror(plane) for s in sources}
            for n in news:
                # a "new" name is either the mirrored COPY or a RENAME of the
                # source (script renamed after mirroring); final bbox decides
                if n in truth:
                    lo, hi = truth[n][1], truth[n][2]
                    best_m = max(sources, key=lambda s: _bb_overlap(
                        mirrored[s].bounding_box(), lo, hi))
                    best_s = max(sources, key=lambda s: _bb_overlap(
                        bodies[s].bounding_box(), lo, hi))
                    if (_bb_overlap(bodies[best_s].bounding_box(), lo, hi)
                            > _bb_overlap(mirrored[best_m].bounding_box(), lo, hi)):
                        bodies[n] = bodies.pop(best_s)        # rename
                        continue
                    bodies[n] = mirrored[best_m]
                else:
                    bodies[n] = mirrored[sources[news.index(n) % len(sources)]]
            continue
        if ft == "RectangularPattern":
            entries = [e for n in (f.get("inputs") or [])
                       for e in feats.get(n, [])]
            if not entries:
                raise NotImplementedError(f"{f['name']}: pattern of non-extrude input")
            offsets = f.get("elementOffsets")
            if not offsets:
                q1 = int(round(ev(f["quantityOne"]))); d1 = ev(f["distanceOne"])
                q2 = max(1, int(round(ev(f.get("quantityTwo") or "1"))))
                d2 = ev(f.get("distanceTwo") or "0")
                ax1 = AXIS[f["axisOne"]]
                ax2 = AXIS.get(f.get("axisTwo") or "", Vector(0, 0, 0))
            if offsets:
                # improved captures record every element's exact transform in
                # element order (= Fusion copy-naming order): replay verbatim
                for src in entries:
                    k = 0
                    for off in offsets:
                        v = Vector(*off)
                        if v.length < 1e-9:
                            continue                     # the seed element
                        inst = src["tool"].moved(Location(v))
                        if src["op"] == "NewBody":
                            k += 1
                            bodies[f"{src['targets'][0]} ({k})"] = inst
                        else:
                            apply(src["op"], src["targets"], inst, f["name"])
                continue
            for src in entries:
                # resolve the axis sign by first-copy overlap with the
                # target's final bbox (a dovetail row must stay on the board)
                refs = [truth[t] for t in src["targets"] if t in truth]
                best_sign, best = 1, -1.0
                for s in (1, -1):
                    c1 = src["tool"].moved(Location(ax1 * (s * d1)))
                    sc = (sum(_bb_overlap(c1.bounding_box(), r[1], r[2]) for r in refs)
                          if refs else _bb_overlap(c1.bounding_box(), env_lo, env_hi))
                    if sc > best:
                        best, best_sign = sc, s
                k = 0
                for j in range(q2):
                    for i in range(q1):
                        if i == 0 and j == 0:
                            continue
                        off = ax1 * (best_sign * d1 * i) + ax2 * (d2 * j)
                        inst = src["tool"].moved(Location(off))
                        if src["op"] == "NewBody":
                            # Fusion names pattern copies "<body> (k)"; later
                            # combines consume them by that name (coincident
                            # copies from a degenerate direction included)
                            k += 1
                            bodies[f"{src['targets'][0]} ({k})"] = inst
                        else:
                            apply(src["op"], src["targets"], inst, f["name"])
            continue
        raise NotImplementedError(f"unhandled feature type {ft} ({f['name']})")

    # ---- parity gate ------------------------------------------------------
    m = Model(cap.get("designName") or "capture", units="in")
    disp = {}
    for up in cap.get("userParameters", []):
        u_, v_ = up.get("unit", ""), up["value"]
        if u_ == "in":
            v_ = v_ / 2.54
        elif u_ == "mm":
            v_ = v_ * 10
        elif u_ == "m":
            v_ = v_ / 100
        elif u_ in ("deg", "rad"):
            v_ = math.degrees(v_)
        disp[up["name"]] = round(v_, 4)
    m.params = disp
    m.editable = False       # captured coordinates are baked; display-only
    palette = ["#c79a6b", "#b07a45", "#9c6b3f", "#a06a3c", "#8a5a30", "#7a4a28"]
    ok = True
    print(f"\n=== parity: rebuilt vs captured ground truth ===")
    for i, (name, (vol, lo, hi)) in enumerate(truth.items()):
        if name not in bodies:
            print(f"  {name:<12} MISSING from rebuild"); ok = False
            continue
        s = bodies[name]
        m.add(name, s, palette[i % len(palette)])
        bb = s.bounding_box()
        dv = abs(s.volume - vol)
        db = max(abs(bb.min.X - lo[0]), abs(bb.min.Y - lo[1]), abs(bb.min.Z - lo[2]),
                 abs(bb.max.X - hi[0]), abs(bb.max.Y - hi[1]), abs(bb.max.Z - hi[2]))
        good = dv <= max(0.01 * vol, 0.01) and db <= 0.05
        ok &= good
        print(f"  {name:<12} vol {s.volume:8.3f} vs {vol:8.3f}  "
              f"(d={dv:.4f})   bbox d={db:.4f}  {'OK' if good else 'MISMATCH'}")
    extra = set(bodies) - set(truth)
    if extra:
        print(f"  leftover intermediate bodies: {sorted(extra)}"); ok = False
    for w in warnings:
        print("  warn:", w)
    print(f"  => {'PARITY PASS' if ok else 'PARITY FAIL'}")
    return m, ok


def build(overrides=None):
    """Server hook: rebuild from the bundled capture (no parametric overrides
    — captured sketch coordinates are baked at capture-time values)."""
    if overrides:
        raise ValueError("capture-converted models are not parametric")
    m, _ = convert(CAPTURE, verbose=False)
    return m


CAPTURE = "captures/pencil_box_capture.json"

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else CAPTURE
    model, ok = convert(path)
    model.validate()
    import os
    os.makedirs("out", exist_ok=True)
    # "_cap" suffix so converted output never clobbers a hand-ported
    # model's manifest (which carries live parameters)
    stem = "out/" + os.path.splitext(os.path.basename(path))[0] \
        .replace("_capture", "") + "_cap"
    model.export_parts(stem)
    model.export(stem)
    print(f"exported {stem}.*")
    sys.exit(0 if ok else 1)
