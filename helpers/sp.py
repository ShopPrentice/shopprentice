"""
ShopPrentice Runtime Helpers

Shared utilities for Fusion 360 scripts executed via execute_script.
Import with: from helpers import sp

All functions accept explicit objects (body, sketch, component) rather than
relying on module-level globals, so they work in both normal and sandbox mode.
"""

import adsk.core
import adsk.fusion
import math

Point3D = adsk.core.Point3D
H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation


# ── Design Context ──────────────────────────────────────────────────

class DesignContext:
    """Replaces the 5-line boilerplate at the top of every script.

    Usage:
        ctx = sp.DesignContext()
        depth = ctx.ev("shelf_depth")
        shelf = ctx.find_body("shelf_top")
    """

    def __init__(self, design=None):
        self.app = adsk.core.Application.get()
        self.design = design or adsk.fusion.Design.cast(self.app.activeProduct)
        self.root = self.design.rootComponent
        self.params = self.design.userParameters
        self.units = self.design.unitsManager

    def ev(self, expr):
        """Evaluate parameter name or expression string to float (cm).

        Also accepts int/float (returned as-is, assumed cm).
        """
        if isinstance(expr, (int, float)):
            return float(expr)
        p = self.params.itemByName(expr)
        return p.value if p else self.units.evaluateExpression(expr, "cm")

    def find_body(self, name, component=None):
        """Find body by exact name. Walks all descendants if component is None."""
        comp = component or self.root
        return _find_body_recursive(comp, name)

    def find_bodies(self, pattern, component=None):
        """Find all bodies matching glob pattern. Walks all descendants."""
        import fnmatch
        comp = component or self.root
        results = []
        _collect_bodies_recursive(comp, pattern, results)
        return results


# ── Face Queries ────────────────────────────────────────────────────

def find_face(body, axis, direction):
    """Outermost planar face along axis. direction: +1=max, -1=min.

    Uses pointOnFace coordinate (not normal sign) to handle both-direction
    normals correctly.
    """
    best = None
    best_val = -1e10 if direction > 0 else 1e10
    for i in range(body.faces.count):
        face = body.faces.item(i)
        geom = face.geometry
        if isinstance(geom, adsk.core.Plane):
            if abs(getattr(geom.normal, axis)) > 0.9:
                fv = getattr(face.pointOnFace, axis)
                if (direction > 0 and fv > best_val) or \
                   (direction < 0 and fv < best_val):
                    best_val = fv
                    best = face
    return best


def find_face_at(body, axis, position, tolerance=0.01):
    """Planar face at specific coordinate along axis."""
    for i in range(body.faces.count):
        face = body.faces.item(i)
        geom = face.geometry
        if isinstance(geom, adsk.core.Plane):
            if abs(getattr(geom.normal, axis)) > 0.9:
                fv = getattr(face.pointOnFace, axis)
                if abs(fv - position) < tolerance:
                    return face
    return None


def _face_extent_along(face, axis_vec):
    """Extent of a face's vertices projected onto a direction vector."""
    vals = []
    for ei in range(face.edges.count):
        e = face.edges.item(ei)
        for v in [e.startVertex.geometry, e.endVertex.geometry]:
            vals.append(v.x * axis_vec.x + v.y * axis_vec.y + v.z * axis_vec.z)
    return (max(vals) - min(vals)) if vals else 0.0


def find_faces_at_offset(body, ref_face, offset, tol=0.01,
                         extent_axis=None, extent_val=None, extent_tol=None):
    """Find all planar faces on body parallel to ref_face at a signed offset.

    Searches ``body`` for planar faces whose outward normal is parallel to
    ``ref_face``'s outward normal AND whose plane is ``offset`` cm from
    ``ref_face`` along that normal direction.

    Optional extent filter: when ``extent_axis`` and ``extent_val`` are
    provided, only return faces whose vertex span along ``extent_axis``
    matches ``extent_val`` within ``extent_tol``. This filters out outlier
    faces that happen to be at the right offset but have the wrong size
    (e.g. a groove shelf vs. a proud dovetail tip).

    Use cases:
      - Find proud dovetail tip faces (parallel to pin board surface,
        offset by proud_offset, extent = board_thick along ext_axis).
      - Find rabbet shelves (parallel to a reference face, offset by
        rabbet depth).

    Args:
        body: BRepBody to search for matching faces.
        ref_face: Reference BRepFace — defines the orientation and base
            plane position. Can be on any body (not necessarily ``body``).
        offset: Signed offset in cm along ref_face's outward normal.
            Positive = in the outward normal direction.
            Negative = opposite to the outward normal.
        tol: Tolerance in cm for position matching and angular check.
        extent_axis: Optional axis name ("x", "y", "z") or Vector3D.
            When set with ``extent_val``, filters faces by their vertex
            span along this direction.
        extent_val: Expected extent in cm along ``extent_axis``.
        extent_tol: Tolerance for extent matching. Defaults to ``tol``.

    Returns:
        list of BRepFace objects on ``body`` that match.
    """
    # Reference face outward normal and position along that normal.
    ok, ref_pt = ref_face.evaluator.getPointAtParameter(
        adsk.core.Point2D.create(0.5, 0.5))
    ok2, ref_n = ref_face.evaluator.getNormalAtPoint(ref_pt)
    ref_pos = ref_pt.x * ref_n.x + ref_pt.y * ref_n.y + ref_pt.z * ref_n.z
    target_pos = ref_pos + offset

    # Resolve extent filter axis to a Vector3D.
    ext_vec = None
    if extent_axis is not None and extent_val is not None:
        if isinstance(extent_axis, str):
            _m = {"x": (1,0,0), "y": (0,1,0), "z": (0,0,1)}
            ext_vec = adsk.core.Vector3D.create(*_m[extent_axis])
        else:
            ext_vec = extent_axis
        if extent_tol is None:
            extent_tol = tol

    result = []
    for fi in range(body.faces.count):
        f = body.faces.item(fi)
        geom = f.geometry
        if not isinstance(geom, adsk.core.Plane):
            continue
        # Parallel check: |dot(face_normal, ref_normal)| ≈ 1
        fn = geom.normal
        dot = fn.x * ref_n.x + fn.y * ref_n.y + fn.z * ref_n.z
        if abs(abs(dot) - 1.0) > 0.01:
            continue
        # Position along reference normal
        fp = f.pointOnFace
        face_pos = fp.x * ref_n.x + fp.y * ref_n.y + fp.z * ref_n.z
        if abs(face_pos - target_pos) >= tol:
            continue
        # Extent filter
        if ext_vec is not None:
            ext = _face_extent_along(f, ext_vec)
            if abs(ext - extent_val) >= extent_tol:
                continue
        result.append(f)
    return result


def edges_from_faces(faces):
    """Collect all unique edges from a list of BRepFaces.

    Args:
        faces: Iterable of BRepFace objects.

    Returns:
        adsk.core.ObjectCollection of unique BRepEdge objects.
    """
    coll = adsk.core.ObjectCollection.create()
    seen = set()
    for f in faces:
        for ei in range(f.edges.count):
            e = f.edges.item(ei)
            if e.tempId not in seen:
                coll.add(e)
                seen.add(e.tempId)
    return coll


# ── Edge Queries ────────────────────────────────────────────────────

def find_edges(body, axis):
    """All linear edges aligned with axis."""
    result = []
    for i in range(body.edges.count):
        edge = body.edges.item(i)
        geom = edge.geometry
        if isinstance(geom, adsk.core.Line3D):
            sp = geom.startPoint
            ep = geom.endPoint
            dx = ep.x - sp.x
            dy = ep.y - sp.y
            dz = ep.z - sp.z
            length = math.sqrt(dx*dx + dy*dy + dz*dz)
            if length > 1e-10:
                norm = {"x": dx/length, "y": dy/length, "z": dz/length}
                if abs(norm[axis]) > 0.9:
                    result.append(edge)
    return result


# ── Sketch Helpers ──────────────────────────────────────────────────

def probe_sketch_axes(sk):
    """Detect model axis to sketch H/V mapping for non-XY planes.

    Returns (h_axis, v_axis) where h_axis is the model axis ('x','y','z')
    that maps to sketch horizontal, and v_axis maps to sketch vertical.
    """
    o = sk.modelToSketchSpace(Point3D.create(0, 0, 0))
    ux = sk.modelToSketchSpace(Point3D.create(1, 0, 0))
    uy = sk.modelToSketchSpace(Point3D.create(0, 1, 0))
    uz = sk.modelToSketchSpace(Point3D.create(0, 0, 1))
    deltas = {
        "x": (ux.x - o.x, ux.y - o.y),
        "y": (uy.x - o.x, uy.y - o.y),
        "z": (uz.x - o.x, uz.y - o.y),
    }
    h_axis = max(deltas, key=lambda a: abs(deltas[a][0]))
    v_axis = max(deltas, key=lambda a: abs(deltas[a][1]))
    return h_axis, v_axis


def sketch_rect(comp, plane, x0_expr, y0_expr, w_expr, h_expr,
                name="Sk", ev=None):
    """Parametric rectangle on XY-aligned plane.

    Adds explicit H/V geometric constraints (critical for parametric stability)
    and 4 parametric dimensions (width, height, x-offset, y-offset).

    Args:
        comp: Component to create sketch in.
        plane: Construction plane or BRepFace.
        x0_expr, y0_expr: Origin offset expressions (e.g. "0 cm", "shelf_x").
        w_expr, h_expr: Width and height expressions.
        name: Sketch name.
        ev: Evaluator function (expression -> float cm). If None, creates one
            from the active design.

    Returns:
        (sketch, profile)
    """
    if ev is None:
        ev = _make_ev()

    sk = comp.sketches.add(plane)
    sk.name = name
    x0, y0, w, h = ev(x0_expr), ev(y0_expr), ev(w_expr), ev(h_expr)
    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(x0, y0, 0),
        Point3D.create(x0 + w, y0 + h, 0))

    # Explicit H/V constraints — prevents drift under parameter changes
    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0])
    gc.addHorizontal(rect[2])
    gc.addVertical(rect[1])
    gc.addVertical(rect[3])

    # Parametric dimensions
    d = sk.sketchDimensions
    d.addDistanceDimension(
        rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, Point3D.create(x0 + w / 2, y0 - 1, 0)
    ).parameter.expression = w_expr
    d.addDistanceDimension(
        rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, Point3D.create(x0 + w + 1, y0 + h / 2, 0)
    ).parameter.expression = h_expr
    d.addDistanceDimension(
        sk.originPoint, rect[0].startSketchPoint,
        H, Point3D.create(x0 / 2, y0 - 2, 0)
    ).parameter.expression = x0_expr
    d.addDistanceDimension(
        sk.originPoint, rect[0].startSketchPoint,
        V, Point3D.create(x0 - 1, y0 / 2, 0)
    ).parameter.expression = y0_expr

    return sk, sk.profiles.item(0)


def sketch_rect_model(comp, plane, model_origin, model_size,
                      name="Sk", ev=None):
    """Parametric rectangle on ANY plane via modelToSketchSpace.

    Adds explicit H/V geometric constraints (dresser.py original omitted
    these — fixed here per MEMORY.md).

    Args:
        comp: Component to create sketch in.
        plane: Construction plane or BRepFace (can be non-XY).
        model_origin: (x_expr, y_expr, z_expr) — model-space corner.
        model_size: {axis: expr, axis: expr} — 2 model-axis sizes.
        name: Sketch name.
        ev: Evaluator function. If None, creates one from active design.

    Returns:
        (sketch, profile)
    """
    if ev is None:
        ev = _make_ev()

    sk = comp.sketches.add(plane)
    sk.name = name
    h_axis, v_axis = probe_sketch_axes(sk)

    ox = ev(model_origin[0])
    oy = ev(model_origin[1])
    oz = ev(model_origin[2])
    corner = {"x": ox, "y": oy, "z": oz}
    for a, expr in model_size.items():
        corner[a] += ev(expr)

    sk_o = sk.modelToSketchSpace(Point3D.create(ox, oy, oz))
    sk_f = sk.modelToSketchSpace(
        Point3D.create(corner["x"], corner["y"], corner["z"]))

    rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
        Point3D.create(sk_o.x, sk_o.y, 0),
        Point3D.create(sk_f.x, sk_f.y, 0))

    # Explicit H/V constraints
    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0])
    gc.addHorizontal(rect[2])
    gc.addVertical(rect[1])
    gc.addVertical(rect[3])

    # Parametric dimensions in model-axis expressions
    def _to_expr(v):
        """Convert value to expression string. Floats become 'N cm'."""
        return f"{v} cm" if isinstance(v, (int, float)) else v

    d = sk.sketchDimensions
    axis_to_origin = {
        "x": model_origin[0], "y": model_origin[1], "z": model_origin[2]}

    mid_x = (sk_o.x + sk_f.x) / 2
    mid_y = (sk_o.y + sk_f.y) / 2
    dy = -1 if sk_f.y >= sk_o.y else 1
    dx = -1 if sk_f.x >= sk_o.x else 1

    d.addDistanceDimension(
        rect[0].startSketchPoint, rect[0].endSketchPoint,
        H, Point3D.create(mid_x, sk_o.y + dy, 0)
    ).parameter.expression = _to_expr(model_size[h_axis])
    d.addDistanceDimension(
        rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, Point3D.create(sk_f.x - dx, mid_y, 0)
    ).parameter.expression = _to_expr(model_size[v_axis])
    d.addDistanceDimension(
        sk.originPoint, rect[0].startSketchPoint,
        H, Point3D.create(sk_o.x / 2, sk_o.y + 2 * dy, 0)
    ).parameter.expression = _to_expr(axis_to_origin[h_axis])
    d.addDistanceDimension(
        sk.originPoint, rect[0].startSketchPoint,
        V, Point3D.create(sk_o.x + dx, sk_o.y / 2, 0)
    ).parameter.expression = _to_expr(axis_to_origin[v_axis])

    return sk, sk.profiles.item(0)


def refs_to_construction(sk):
    """Convert all projected/reference lines to construction geometry.

    Call this after dimensioning but before profile selection.  Projected
    references (from sketch.project() or auto-projected face edges) form
    profile boundaries, splitting the sketch into fragments.  Setting them
    to construction removes them from profile computation so only the
    drawn geometry defines profiles.

    The sketch points from these lines remain valid for dimensions.
    """
    for i in range(sk.sketchCurves.sketchLines.count):
        ln = sk.sketchCurves.sketchLines.item(i)
        if ln.isReference:
            ln.isConstruction = True


def probe_orientations(sk, x=0, y=0, z=0):
    """Detect which sketch H/V orientation corresponds to each model axis.

    On non-XY planes, sketch H and V map to different model axes.
    This function probes the mapping and returns a dict you can index
    by model axis name to get the correct DimensionOrientation.

    Args:
        sk: Sketch object.
        x, y, z: A model-space point near the sketch (for the probe origin).
            Use ev() values. Defaults to origin — works for most planes.

    Returns:
        Dict {'x': H_or_V, 'y': H_or_V, 'z': H_or_V} where values are
        DimensionOrientations.HorizontalDimensionOrientation or
        VerticalDimensionOrientation.

    Usage:
        orient = sp.probe_orientations(sk, ev("cx"), ev("cy"), ev("cz"))
        d.addDistanceDimension(p1, p2, orient['z'], placement_pt
        ).parameter.expression = "ls_z + ls_w / 2"
        d.addDistanceDimension(p1, p2, orient['y'], placement_pt
        ).parameter.expression = "leg_d / 2"
    """
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    P = adsk.core.Point3D

    m = sk.modelToSketchSpace
    o = m(P.create(x, y, z))
    result = {}
    for axis, dx, dy, dz in [('x', 1, 0, 0), ('y', 0, 1, 0), ('z', 0, 0, 1)]:
        t = m(P.create(x + dx, y + dy, z + dz))
        result[axis] = H if abs(t.x - o.x) > abs(t.y - o.y) else V
    return result


def smallest_profile(sk):
    """Smallest-area profile in a sketch.

    On body-face sketches, an arch line+arc divides the face into two
    regions; the arch is the smaller one.
    """
    best = None
    best_area = float('inf')
    for i in range(sk.profiles.count):
        p = sk.profiles.item(i)
        a = p.areaProperties().area
        if a < best_area:
            best_area = a
            best = p
    return best


# ── Sketch Setup Helpers ──────────────────────────────────────────

def sketch_on_plane(comp, plane, project=None, intersect=None, identify=None, name="Sk"):
    """Create a sketch on a plane with projected/intersected references and identified points.

    Args:
        comp: Component to create the sketch in.
        plane: ConstructionPlane or BRepFace for the sketch.
        project: List of entities to project (SketchLine, BRepBody, ConstructionPlane, etc.)
        intersect: List of BRepBody to intersect with the sketch plane.
        identify: Dict of {name: model_Point3D} — model-space points to identify
                  in the sketch after projection. Returns matching SketchPoints.
        name: Sketch name.

    Returns:
        (sketch, identified_points_dict)
        identified_points_dict maps each name from `identify` to the closest
        SketchPoint in the sketch after all projections.

    All projected/intersected curves are converted to construction geometry.
    Point identification uses modelToSketchSpace — no origin-based guessing.
    """
    sk = comp.sketches.add(plane)
    sk.name = name

    # Project requested entities
    for entity in (project or []):
        sk.project(entity)

    # Intersect requested bodies
    if intersect:
        result = sk.intersectWithSketchPlane(intersect)
        if result:
            for c in result:
                if hasattr(c, 'isConstruction'):
                    c.isConstruction = True

    # Convert all references to construction
    refs_to_construction(sk)

    # Identify points by matching model coordinates to sketch points
    found = {}
    if identify:
        m2s = sk.modelToSketchSpace
        # Collect all sketch points
        all_pts = []
        for ci in range(sk.sketchCurves.count):
            c = sk.sketchCurves.item(ci)
            if hasattr(c, 'startSketchPoint'):
                all_pts.append(c.startSketchPoint)
            if hasattr(c, 'endSketchPoint'):
                all_pts.append(c.endSketchPoint)
            if hasattr(c, 'centerSketchPoint') and c.centerSketchPoint:
                all_pts.append(c.centerSketchPoint)

        for label, model_pt in identify.items():
            expected = m2s(model_pt)
            best_pt = None
            best_dist = float('inf')
            for sp in all_pts:
                g = sp.geometry
                d = math.sqrt((g.x - expected.x)**2 + (g.y - expected.y)**2)
                if d < best_dist:
                    best_dist = d
                    best_pt = sp
            found[label] = best_pt

    return sk, found


def drop_to_line(sketch, point, ref_line, approximate_target=None):
    """Drop a perpendicular construction line from a SketchPoint to a reference line.

    Args:
        sketch: The sketch containing both entities.
        point: SketchPoint to drop from.
        ref_line: SketchLine to drop onto (the reference surface line).
        approximate_target: Optional Point3D for approximate endpoint placement.
                           If None, uses the point's X with the ref_line's mid Y.

    Returns:
        The endpoint SketchPoint on the reference line (the projected point).

    Creates a construction line constrained perpendicular to ref_line,
    with its endpoint coincident with ref_line. This projected point
    updates parametrically when the source point or reference moves.
    """
    P = Point3D.create
    pg = point.geometry
    if approximate_target:
        target = approximate_target
    else:
        rl_s = ref_line.startSketchPoint.geometry
        rl_e = ref_line.endSketchPoint.geometry
        mid_y = (rl_s.y + rl_e.y) / 2
        target = P(pg.x, mid_y, 0)

    drop = sketch.sketchCurves.sketchLines.addByTwoPoints(point, target)
    drop.isConstruction = True
    gc = sketch.geometricConstraints
    gc.addPerpendicular(drop, ref_line)
    return drop.endSketchPoint


def construct_ref_line(sketch, model_z, model_x_range=(-50, 50), model_y=0):
    """Create a horizontal construction line at a known model Z level.

    Args:
        sketch: The sketch to add the line to.
        model_z: The model-space Z coordinate for the reference level (e.g., 0 for floor).
        model_x_range: Tuple (min_x, max_x) in model space for the line extent.
        model_y: Model Y coordinate (use mid_y or relevant Y).

    Returns:
        The construction SketchLine at the specified Z level.

    Uses modelToSketchSpace to place the line correctly regardless of
    sketch plane orientation.
    """
    P = Point3D.create
    m2s = sketch.modelToSketchSpace
    p1 = m2s(P(model_x_range[0], model_y, model_z))
    p2 = m2s(P(model_x_range[1], model_y, model_z))
    line = sketch.sketchCurves.sketchLines.addByTwoPoints(
        P(p1.x, p1.y, 0), P(p2.x, p2.y, 0))
    line.isConstruction = True
    return line


def find_nearest_line(sketch, model_point, construction_only=True):
    """Find the sketch line whose midpoint is closest to a model-space reference point.

    Args:
        sketch: The sketch to search.
        model_point: Point3D in model space to match against.
        construction_only: If True, only search construction lines.

    Returns:
        The closest SketchLine, or None.

    Converts the model point to sketch space and compares by distance.
    Use this to find projected seat surface / floor lines after projection.
    """
    m2s = sketch.modelToSketchSpace
    expected = m2s(model_point)
    best_line = None
    best_dist = float('inf')
    for ci in range(sketch.sketchCurves.count):
        c = sketch.sketchCurves.item(ci)
        if construction_only and not c.isConstruction:
            continue
        if not c.objectType.endswith('SketchLine'):
            continue
        sg = c.startSketchPoint.geometry
        eg = c.endSketchPoint.geometry
        mid_x = (sg.x + eg.x) / 2
        mid_y = (sg.y + eg.y) / 2
        d = math.sqrt((mid_x - expected.x)**2 + (mid_y - expected.y)**2)
        if d < best_dist:
            best_dist = d
            best_line = c
    return best_line


# ── Feature Builders ───────────────────────────────────────────────

def ext_new(comp, prof, dist, name="Ext"):
    """Extrude a profile as a new body.

    Returns the ExtrudeFeature. Access the body via ``f.bodies.item(0)``.
    """
    inp = comp.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
    f = comp.features.extrudeFeatures.add(inp)
    f.name = name
    return f


def ext_new_sym(comp, prof, dist, name="Ext"):
    """Extrude a profile as a new body, symmetric about the sketch plane.

    Returns the ExtrudeFeature.
    """
    inp = comp.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setDistanceExtent(True, adsk.core.ValueInput.createByString(dist))
    f = comp.features.extrudeFeatures.add(inp)
    f.name = name
    return f


def ext_op(comp, prof, dist_expr, op, body, name="Ext", flip=False):
    """Extrude a profile as CUT or JOIN into an existing body.

    Args:
        comp: Component owning the extrude feature.
        prof: Sketch profile.
        dist_expr: Distance expression string (e.g. "board_thick").
        op: FeatureOperations enum (CutFeatureOperation or JoinFeatureOperation).
        body: Target body, list of bodies, or None (no participantBodies —
              CUT/JOIN affects all intersecting bodies).
        name: Feature name.
        flip: If True, extrude in negative direction (into the body on
              face-based sketches where default direction points outward).
    """
    inp = comp.features.extrudeFeatures.createInput(prof, op)
    if flip:
        inp.setOneSideExtent(
            adsk.fusion.DistanceExtentDefinition.create(
                adsk.core.ValueInput.createByString(dist_expr)),
            adsk.fusion.ExtentDirections.NegativeExtentDirection)
    else:
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist_expr))
    if body is not None:
        inp.participantBodies = body if isinstance(body, list) else [body]
    f = comp.features.extrudeFeatures.add(inp)
    f.name = name
    return f


def off_plane(comp, base, expr, name="Pl"):
    """Create an offset construction plane.

    Returns the ConstructionPlane.
    """
    inp = comp.constructionPlanes.createInput()
    inp.setByOffset(base, adsk.core.ValueInput.createByString(expr))
    p = comp.constructionPlanes.add(inp)
    p.name = name
    return p


def _combine_in(comp, target, tool_bodies, op, keep_tool, name="Comb"):
    """Low-level combine primitive — creates the feature in ``comp``.

    Internal helper. Joinery templates and example scripts should call
    :func:`combine` (which picks the right component automatically and
    handles cross-component tool proxies). Use this directly only when
    you have a specific reason to place the feature in a component
    other than ``target.parentComponent``.

    Args:
        comp: Component owning the combine feature.
        target: Target BRepBody.
        tool_bodies: Single BRepBody or list of BRepBody.
        op: FeatureOperations enum (CutFeatureOperation or JoinFeatureOperation).
        keep_tool: Whether to keep tool bodies after the operation.
        name: Feature name.
    """
    coll = adsk.core.ObjectCollection.create()
    if isinstance(tool_bodies, list):
        for b in tool_bodies:
            coll.add(b)
    else:
        coll.add(tool_bodies)
    inp = comp.features.combineFeatures.createInput(target, coll)
    inp.operation = op
    inp.isKeepToolBodies = keep_tool
    f = comp.features.combineFeatures.add(inp)
    f.name = name
    return f


def body_for_root(body, root):
    """Return a body usable by a root-level feature.

    If ``body`` is already in ``root``, returns it unchanged. Otherwise
    walks ``root.allOccurrences`` for the occurrence whose component
    matches ``body``'s owning component and returns a proxy via
    ``createForAssemblyContext``.

    Accepts either a native body or an existing assembly-context
    proxy — proxies are unwrapped to their native body first (Fusion
    rejects ``createForAssemblyContext`` on a body that is already a
    proxy).

    Use when placing a feature at root that must reference bodies living
    in sub-components.
    """
    # Unwrap proxy → native so createForAssemblyContext works.
    native = (body.nativeObject if body.assemblyContext else body)
    comp = native.parentComponent
    if comp == root:
        return native
    for i in range(root.allOccurrences.count):
        occ = root.allOccurrences.item(i)
        if occ.component == comp:
            return native.createForAssemblyContext(occ)
    raise ValueError(
        f"No occurrence in root for body '{native.name}' "
        f"(component '{comp.name}').")


def combine(target, tool_bodies, op, keep_tool, name="Comb"):
    """Combine (CUT / JOIN / Intersect) tool bodies into a target body.

    The combine feature lives in ``target.parentComponent`` — the
    natural home for a feature that modifies the target. Tool bodies
    from other components are wrapped via ``createForAssemblyContext``
    proxies automatically, so the same call works whether the tools
    are native, already proxied, or in sibling components.

    Args:
        target: Target BRepBody. Must be a native body (not a proxy) —
            the combine feature is created in its parent component.
        tool_bodies: Single BRepBody or list of BRepBody. Native bodies
            in other components are proxied automatically.
        op: FeatureOperations enum
            (CutFeatureOperation / JoinFeatureOperation / IntersectFeatureOperation).
        keep_tool: Whether to keep tool bodies after the operation.
        name: Feature name.
    """
    tools = tool_bodies if isinstance(tool_bodies, list) else [tool_bodies]
    # Unwrap the target proxy → native. The feature is created in
    # the native's parent component regardless of what assembly
    # context the caller happened to pass in.
    tgt = target.nativeObject if target.assemblyContext else target
    tgt_comp = tgt.parentComponent
    root = tgt_comp.parentDesign.rootComponent

    # For tool bodies: if they live in tgt_comp (same component as
    # target), use their native directly. Otherwise wrap in a
    # root-occurrence proxy via body_for_root (which handles the
    # unwrap-then-rewrap step for already-proxied tools).
    tool_refs = []
    for b in tools:
        native_b = b.nativeObject if b.assemblyContext else b
        if native_b.parentComponent == tgt_comp:
            tool_refs.append(native_b)
        else:
            tool_refs.append(body_for_root(b, root))

    return _combine_in(tgt_comp, tgt, tool_refs, op, keep_tool, name)


def mirror_body(comp, body, plane, name="Mirror"):
    """Mirror a single body across a plane.

    Returns the MirrorFeature. Access the mirrored body via
    ``m.bodies.item(0)``.
    """
    coll = adsk.core.ObjectCollection.create()
    coll.add(body)
    inp = comp.features.mirrorFeatures.createInput(coll, plane)
    m = comp.features.mirrorFeatures.add(inp)
    m.name = name
    return m


def mirror_bodies(comp, bodies, plane, name="Mirror"):
    """Mirror multiple bodies across a plane.

    Returns the MirrorFeature.
    """
    coll = adsk.core.ObjectCollection.create()
    for b in bodies:
        coll.add(b)
    inp = comp.features.mirrorFeatures.createInput(coll, plane)
    m = comp.features.mirrorFeatures.add(inp)
    m.name = name
    return m


def mirror_feats(comp, features, plane, name="Mirror"):
    """Mirror features (extrudes, combines, etc.) across a plane.

    Use this instead of ``mirror_body`` when the mirrored side needs to
    replay the feature operations (e.g., extrude + JOIN into a target that
    spans both sides).
    """
    coll = adsk.core.ObjectCollection.create()
    for f in features:
        coll.add(f)
    inp = comp.features.mirrorFeatures.createInput(coll, plane)
    m = comp.features.mirrorFeatures.add(inp)
    m.name = name
    return m


def make_comp(root_comp, name, transform=None):
    """Create a new component under root_comp.

    Args:
        root_comp: Parent component (typically design root).
        name: New component name.
        transform: Optional ``Matrix3D`` placing the occurrence in the
            parent's space. If ``None``, creates at identity. Baking the
            transform in at creation time is the reliable way to place
            a rotated/translated occurrence — setting ``occurrence.
            transform2`` AFTER bodies are built is silently rejected by
            Fusion in many cases.

    Returns:
        The Occurrence (access component via ``occ.component``).
    """
    xf = transform if transform is not None else adsk.core.Matrix3D.create()
    occ = root_comp.occurrences.addNewComponent(xf)
    occ.component.name = name
    return occ


def feat_pattern(comp, feat, axis, count_expr, spacing_expr, name="Pat"):
    """Rectangular pattern of a single feature along an axis.

    Returns the RectangularPatternFeature.
    """
    VI = adsk.core.ValueInput.createByString
    coll = adsk.core.ObjectCollection.create()
    coll.add(feat)
    inp = comp.features.rectangularPatternFeatures.createInput(
        coll, axis, VI(count_expr), VI(spacing_expr),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    p = comp.features.rectangularPatternFeatures.add(inp)
    p.name = name
    return p


def body_pattern(comp, body, axis, count_expr, spacing_expr, name="Pat"):
    """Rectangular pattern of a body along an axis.

    WARNING: body_pattern replays the full feature tree of the template body.
    If the body has CUT/JOIN operations in its timeline history (including
    CUTs added AFTER the pattern), each pattern instance creates ghost
    duplicate bodies. Use a Python ``for`` loop instead for bodies with
    CUT/JOIN history. Safe for simple bodies (NewBody extrude + Mirror only).

    Returns the RectangularPatternFeature.
    """
    VI = adsk.core.ValueInput.createByString
    coll = adsk.core.ObjectCollection.create()
    coll.add(body)
    inp = comp.features.rectangularPatternFeatures.createInput(
        coll, axis, VI(count_expr), VI(spacing_expr),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    p = comp.features.rectangularPatternFeatures.add(inp)
    p.name = name
    return p


# ── Sketch Slot (Stadium Shape) ────────────────────────────────────

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
                      long_expr, short_expr, name="Sk", ev=None):
    """Stadium-shaped sketch positioned in model coordinates.

    Handles axis flips on non-XY planes automatically via sign detection.
    Use this instead of sketch_slot when working in model-space coordinates.

    Args:
        comp: Component to create sketch in.
        plane: Construction plane or BRepFace (can be non-XY).
        model_center: (x_expr, y_expr, z_expr) — center in model-space expressions.
        long_model_axis: 'x', 'y', or 'z' — which model axis the long dim runs along.
        long_expr: Long dimension expression.
        short_expr: Short dimension expression.
        name: Sketch name.
        ev: Evaluator function. If None, creates one from active design.

    Returns:
        (sketch, profile)
    """
    if ev is None:
        ev = _make_ev()

    sk = comp.sketches.add(plane)
    sk.name = name
    h_axis, v_axis = probe_sketch_axes(sk)

    # Convert model center to sketch space
    mcx = ev(model_center[0])
    mcy = ev(model_center[1])
    mcz = ev(model_center[2])
    sc = sk.modelToSketchSpace(Point3D.create(mcx, mcy, mcz))
    cx, cy = sc.x, sc.y

    # Is the long axis along sketch V (vertical) or sketch H?
    vertical = (long_model_axis == v_axis)

    # Model axis expressions → sketch H/V
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

    # Detect axis sign
    delta_pt = {
        "x": Point3D.create(mcx + 1, mcy, mcz),
        "y": Point3D.create(mcx, mcy + 1, mcz),
        "z": Point3D.create(mcx, mcy, mcz + 1),
    }
    sd_h = sk.modelToSketchSpace(delta_pt[h_axis])
    sd_v = sk.modelToSketchSpace(delta_pt[v_axis])
    h_sign = 1 if (sd_h.x - sc.x) > 0 else -1
    v_sign = 1 if (sd_v.y - sc.y) > 0 else -1

    # Offset expressions for arc center positioning (sign-aware)
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
        ).parameter.expression = h_expr + h_left_op + half_str
        d.addDistanceDimension(
            sk.originPoint, a_l.centerSketchPoint,
            V, Point3D.create(cx - hl - 2, cy / 2, 0)
        ).parameter.expression = v_expr
    return sk, sk.profiles.item(0)


# ── Spatial Queries ────────────────────────────────────────────────

def body_side(body, reference, direction):
    """Test if a body is on a given side of a reference body.

    Uses center-of-mass for the test point and pointContainment for
    inside/outside classification.  The direction vector defines
    which "outside" region counts as the target side.

    Args:
        body: BRepBody to test
        reference: BRepBody defining the boundary
        direction: (x, y, z) tuple — the side to test for

    Returns:
        'inside'   — body's COM is inside the reference body
        'outside'  — body's COM is outside, on the direction side
        'opposite' — body's COM is outside, on the other side

    Example — is a fragment above the seat?::

        result = sp.body_side(fragment, seat_body, (0, 0, 1))
        if result == 'outside':
            remove(fragment)  # above the seat → excess
    """
    INSIDE = adsk.fusion.PointContainment.PointInsidePointContainment
    com = body.physicalProperties.centerOfMass
    if reference.pointContainment(com) == INSIDE:
        return 'inside'
    ref_com = reference.physicalProperties.centerOfMass
    dx = com.x - ref_com.x
    dy = com.y - ref_com.y
    dz = com.z - ref_com.z
    dot = dx * direction[0] + dy * direction[1] + dz * direction[2]
    return 'outside' if dot > 0 else 'opposite'


def face_side(body, face):
    """Test which side of a face a body's center of mass is on.

    Uses the face's outward normal to define the two sides.
    Useful after SplitBody to classify fragments by which side
    of the splitting face they ended up on.

    Args:
        body: BRepBody to test
        face: BRepFace defining the boundary surface

    Returns:
        'normal' — COM is on the face-normal side (outside/above)
        'anti'   — COM is on the opposite side (inside/below)
        'on'     — COM is within 0.01 cm of the face surface

    Example — classify split fragments::

        for frag in fragments:
            side = sp.face_side(frag, seat_top_face)
            if side == 'normal':
                remove(frag)   # above the surface
            else:
                keep(frag)     # below the surface
    """
    com = body.physicalProperties.centerOfMass
    ok, normal = face.evaluator.getNormalAtPoint(face.pointOnFace)
    if not ok:
        return 'on'
    ref = face.pointOnFace
    dx = com.x - ref.x
    dy = com.y - ref.y
    dz = com.z - ref.z
    dot = dx * normal.x + dy * normal.y + dz * normal.z
    if abs(dot) < 0.01:
        return 'on'
    return 'normal' if dot > 0 else 'anti'


def classify_bodies(bodies, reference, direction=None):
    """Batch-classify bodies relative to a reference body.

    Convenience wrapper around body_side.  Groups a list of bodies
    into inside / outside / opposite buckets.

    Args:
        bodies: list of BRepBody to classify
        reference: BRepBody defining the boundary
        direction: optional (x, y, z) — if given, uses body_side
                   with this direction.  If None, all outside bodies
                   go into 'outside' (no direction filtering).

    Returns:
        dict with keys 'inside', 'outside', 'opposite' → lists of bodies

    Example — after splitting stretchers at a leg surface::

        groups = sp.classify_bodies(fragments, leg_body)
        for b in groups['inside']:
            sp.combine(stretcher, b, JOIN, False)  # tenon interior
        for b in groups['outside']:
            comp.features.removeFeatures.add(b)  # excess tip
    """
    INSIDE = adsk.fusion.PointContainment.PointInsidePointContainment
    result = {'inside': [], 'outside': [], 'opposite': []}
    ref_com = reference.physicalProperties.centerOfMass
    for body in bodies:
        com = body.physicalProperties.centerOfMass
        if reference.pointContainment(com) == INSIDE:
            result['inside'].append(body)
        elif direction is None:
            result['outside'].append(body)
        else:
            dx = com.x - ref_com.x
            dy = com.y - ref_com.y
            dz = com.z - ref_com.z
            dot = dx * direction[0] + dy * direction[1] + dz * direction[2]
            if dot > 0:
                result['outside'].append(body)
            else:
                result['opposite'].append(body)
    return result


# ── Mating Surface ─────────────────────────────────────────────────

def mating_bounds(body_a, body_b, normal_axis, tol=0.1):
    """Compute the contact area between two bodies at their shared interface.

    Validates that the bodies are in surface contact (touching, not gapped,
    not overlapping) before computing bounds. Raises ValueError with
    diagnostic messages if preconditions aren't met — giving the agent
    feedback during the build, not just at final validation.

    Args:
        body_a, body_b: The two mating bodies.
        normal_axis: 'x', 'y', or 'z' — axis perpendicular to the interface.
            For a rail meeting a post at a YZ plane, normal_axis='x'.
        tol: Contact tolerance in cm (default 0.1 = 1mm). Bodies must be
            within this distance along the normal axis to count as touching.

    Returns:
        dict with overlap bounds in model coordinates (cm), keyed by axis:
            '<ax>_min', '<ax>_max', '<ax>_center', '<ax>_size'
        for each of the two axes parallel to the interface.

    Raises:
        ValueError: If bodies are gapped along normal axis (not in contact),
            overlapping along normal axis (penetrating — CUT first), or
            have no shared area in a parallel axis (side-by-side, not
            face-to-face).

    Example:
        mb = sp.mating_bounds(rung, ladder_side, 'x')
        # returns {'y_min': ..., 'y_max': ..., 'y_center': ..., 'y_size': ...,
        #          'z_min': ..., 'z_max': ..., 'z_center': ..., 'z_size': ...}
        dm_y = mb['y_center']   # center domino in Y overlap
        dm_z = mb['z_center']   # center domino in Z overlap
        # Verify domino fits: dm_h < mb['z_size'] with margin
    """
    bb_a = body_a.boundingBox
    bb_b = body_b.boundingBox

    # ── Precondition 1: Normal axis — bodies must be touching ──
    n_a_lo = getattr(bb_a.minPoint, normal_axis)
    n_a_hi = getattr(bb_a.maxPoint, normal_axis)
    n_b_lo = getattr(bb_b.minPoint, normal_axis)
    n_b_hi = getattr(bb_b.maxPoint, normal_axis)

    normal_overlap = min(n_a_hi, n_b_hi) - max(n_a_lo, n_b_lo)

    if normal_overlap < -tol:
        gap = -normal_overlap
        raise ValueError(
            f"mating_bounds: {body_a.name} and {body_b.name} have a "
            f"{gap:.2f} cm gap along {normal_axis} axis — bodies are not "
            f"in contact. "
            f"{body_a.name} {normal_axis}=[{n_a_lo:.2f}, {n_a_hi:.2f}], "
            f"{body_b.name} {normal_axis}=[{n_b_lo:.2f}, {n_b_hi:.2f}]. "
            f"Check body positioning — they must touch at the interface.")

    if normal_overlap > tol:
        raise ValueError(
            f"mating_bounds: {body_a.name} and {body_b.name} overlap by "
            f"{normal_overlap:.2f} cm along {normal_axis} axis — bodies "
            f"are penetrating. "
            f"{body_a.name} {normal_axis}=[{n_a_lo:.2f}, {n_a_hi:.2f}], "
            f"{body_b.name} {normal_axis}=[{n_b_lo:.2f}, {n_b_hi:.2f}]. "
            f"CUT one from the other first, then call mating_bounds on "
            f"the result.")

    # ── Precondition 2: Parallel axes — bodies must share a mating area ──
    para_axes = [ax for ax in ('x', 'y', 'z') if ax != normal_axis]

    result = {}
    for ax in para_axes:
        a_lo = getattr(bb_a.minPoint, ax)
        a_hi = getattr(bb_a.maxPoint, ax)
        b_lo = getattr(bb_b.minPoint, ax)
        b_hi = getattr(bb_b.maxPoint, ax)

        lo = max(a_lo, b_lo)
        hi = min(a_hi, b_hi)

        if lo >= hi:
            raise ValueError(
                f"mating_bounds: {body_a.name} and {body_b.name} have no "
                f"overlap in {ax} axis — no shared mating surface. "
                f"{body_a.name} {ax}=[{a_lo:.2f}, {a_hi:.2f}], "
                f"{body_b.name} {ax}=[{b_lo:.2f}, {b_hi:.2f}]. "
                f"The bodies don't face each other at this interface.")

        result[f'{ax}_min'] = lo
        result[f'{ax}_max'] = hi
        result[f'{ax}_center'] = (lo + hi) / 2
        result[f'{ax}_size'] = hi - lo

    return result


def check_domino_exposure(void, body_a, body_b, normal_axis, tol=0.05):
    """Check that a domino void creates blind pockets in both mating pieces.

    On axes perpendicular to the interface normal, the void must be fully
    contained within each body's bounding box. If it extends beyond a body's
    boundary, the mortise pocket opens to a surface — the domino is "exposed."

    Call this AFTER creating the void body but BEFORE CUTting it from
    the mating pieces. Raises ValueError with diagnostic info if exposure
    is detected, so the agent can fix placement during the build.

    Args:
        void: The domino void body (un-CUT).
        body_a: Primary mating piece.
        body_b: Secondary mating piece.
        normal_axis: 'x', 'y', or 'z' — axis perpendicular to the
            interface (the extrude direction of the domino).
        tol: Tolerance in cm (default 0.05 ≈ 0.5mm).

    Raises:
        ValueError: If the void extends beyond either body on any
            perpendicular axis, with axis ranges for both the void
            and the offending body so the agent can diagnose and fix.

    Example:
        void = ext.bodies.item(0)
        sp.check_domino_exposure(void, rail, post, 'x')
        # If rail Y=[42, 43] and void Y=[42.77, 43.23] and post Y=[43, 46]:
        #   → ValueError: void extends beyond rail in Y (void max=43.23, rail max=43.00)
        #   → ValueError: void extends beyond post in Y (void min=42.77, post min=43.00)
        # Fix: center the rail on the post so the domino sits inside both pieces.
    """
    perp_axes = [ax for ax in ('x', 'y', 'z') if ax != normal_axis]
    vbb = void.boundingBox
    errors = []

    for body, label in [(body_a, body_a.name), (body_b, body_b.name)]:
        bbb = body.boundingBox
        for ax in perp_axes:
            v_lo = getattr(vbb.minPoint, ax)
            v_hi = getattr(vbb.maxPoint, ax)
            b_lo = getattr(bbb.minPoint, ax)
            b_hi = getattr(bbb.maxPoint, ax)

            if v_lo < b_lo - tol:
                overshoot = b_lo - v_lo
                errors.append(
                    f"  {void.name} exposed in {label} on -{ax.upper()} side: "
                    f"void {ax}={v_lo:.2f} extends {overshoot:.2f} cm "
                    f"beyond {label} {ax}_min={b_lo:.2f}")
            if v_hi > b_hi + tol:
                overshoot = v_hi - b_hi
                errors.append(
                    f"  {void.name} exposed in {label} on +{ax.upper()} side: "
                    f"void {ax}={v_hi:.2f} extends {overshoot:.2f} cm "
                    f"beyond {label} {ax}_max={b_hi:.2f}")

    if errors:
        detail = "\n".join(errors)
        raise ValueError(
            f"check_domino_exposure: domino '{void.name}' mortise is exposed "
            f"(opens to surface) — the mortise pocket won't be blind.\n"
            f"{detail}\n"
            f"Fix: reposition the mating body so the domino center is well "
            f"inside both pieces, or move the domino center to the mating "
            f"surface overlap region.")


# ── Joint Validation ───────────────────────────────────────────────

def validate_joint_contact(body_a, body_b, joint_axis=None, tol_cm=0.1):
    """Validate that two bodies have touching/overlapping faces.

    Checks that body_a and body_b are adjacent (gap < tol) or overlapping
    along the joint axis, and that they overlap in the perpendicular plane.

    If joint_axis is None, auto-detects by finding the axis with the
    smallest gap between the two bounding boxes.

    Args:
        body_a: First body (e.g. rail/stretcher).
        body_b: Second body (e.g. leg/post).
        joint_axis: 'x', 'y', or 'z' — axis along which bodies should meet.
            If None, auto-detected.
        tol_cm: Maximum allowed gap in cm (default 0.1 = 1mm).

    Raises:
        ValueError with diagnostic message if bodies don't contact.

    Returns:
        Dict with 'axis', 'gap_cm', 'perp_overlaps'.
    """
    bb_a = body_a.boundingBox
    bb_b = body_b.boundingBox
    all_axes = ['x', 'y', 'z']

    def _bb_range(bb, ax):
        return (getattr(bb.minPoint, ax), getattr(bb.maxPoint, ax))

    if joint_axis is None:
        # Auto-detect: find axis with smallest gap
        best_axis = None
        best_gap = 1e10
        for ax in all_axes:
            a_min, a_max = _bb_range(bb_a, ax)
            b_min, b_max = _bb_range(bb_b, ax)
            overlap = min(a_max, b_max) - max(a_min, b_min)
            if overlap >= -tol_cm:
                # Bodies overlap or touch on this axis — not the gap axis
                continue
            gap = -overlap
            if gap < best_gap:
                best_gap = gap
                best_axis = ax
        if best_axis is None:
            # Bodies overlap on all axes (they intersect) — contact is fine
            return {"axis": None, "gap_cm": 0.0, "perp_overlaps": {}}
        joint_axis = best_axis

    a_min, a_max = _bb_range(bb_a, joint_axis)
    b_min, b_max = _bb_range(bb_b, joint_axis)

    # Check adjacency or overlap along joint axis
    overlap_along = min(a_max, b_max) - max(a_min, b_min)
    if overlap_along < -tol_cm:
        gap = -overlap_along
        raise ValueError(
            f"Joint contact failed: {body_a.name} and {body_b.name} "
            f"have a {gap:.2f} cm gap along {joint_axis} axis. "
            f"{body_a.name} {joint_axis}=[{a_min:.2f}, {a_max:.2f}], "
            f"{body_b.name} {joint_axis}=[{b_min:.2f}, {b_max:.2f}]")

    # Check perpendicular overlap (bodies must share area in the other 2 axes)
    perp_axes = [ax for ax in all_axes if ax != joint_axis]
    perp_overlaps = {}
    for pax in perp_axes:
        pa_min, pa_max = _bb_range(bb_a, pax)
        pb_min, pb_max = _bb_range(bb_b, pax)
        p_overlap = min(pa_max, pb_max) - max(pa_min, pb_min)
        perp_overlaps[pax] = p_overlap
        if p_overlap < -tol_cm:
            raise ValueError(
                f"Joint contact failed: {body_a.name} and {body_b.name} "
                f"don't overlap in {pax} axis — no shared mating area. "
                f"{body_a.name} {pax}=[{pa_min:.2f}, {pa_max:.2f}], "
                f"{body_b.name} {pax}=[{pb_min:.2f}, {pb_max:.2f}]")

    return {
        "axis": joint_axis,
        "gap_cm": max(0, -overlap_along),
        "perp_overlaps": perp_overlaps,
    }


# ── Internal Helpers ────────────────────────────────────────────────

def _make_ev():
    """Create an ev() function from the active design."""
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    params = design.userParameters
    units = design.unitsManager

    def ev(expr):
        p = params.itemByName(expr)
        return p.value if p else units.evaluateExpression(expr, "cm")
    return ev


def _find_body_recursive(comp, name):
    """Walk component tree to find body by exact name."""
    for i in range(comp.bRepBodies.count):
        body = comp.bRepBodies.item(i)
        if body.name == name:
            return body
    for occ in comp.occurrences:
        result = _find_body_recursive(occ.component, name)
        if result:
            return result
    return None


def apply_appearance(body, appearance_name="Brass - Polished",
                     library_name="Fusion Appearance Library"):
    """Apply a named appearance from a material library to a body.

    Copies the appearance into the active design (if not already present)
    and assigns it to the body. Common appearance names:
      "Brass - Polished", "Brass - Matte", "Bronze - Polished",
      "Steel - Satin", "Aluminum - Satin", "Oak", "Walnut"

    Args:
        body: BRepBody to apply appearance to.
        appearance_name: Name in the library (e.g. "Brass - Polished").
        library_name: Material library name (default: Fusion Appearance Library).

    Returns:
        The applied Appearance, or None if not found.
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)

    # Check if already copied into design
    safe_name = appearance_name.replace(" ", "_").replace("-", "_")
    for i in range(design.appearances.count):
        a = design.appearances.item(i)
        if a.name == safe_name:
            body.appearance = a
            return a

    # Find in library
    lib = None
    for i in range(app.materialLibraries.count):
        if app.materialLibraries.item(i).name == library_name:
            lib = app.materialLibraries.item(i)
            break
    if lib is None:
        return None

    source = None
    for i in range(lib.appearances.count):
        a = lib.appearances.item(i)
        if a.name == appearance_name:
            source = a
            break
    if source is None:
        return None

    local = design.appearances.addByCopy(source, safe_name)
    body.appearance = local
    return local


def _collect_bodies_recursive(comp, pattern, results):
    """Walk component tree to find bodies matching glob pattern."""
    import fnmatch
    for i in range(comp.bRepBodies.count):
        body = comp.bRepBodies.item(i)
        if fnmatch.fnmatch(body.name, pattern):
            results.append(body)
    for occ in comp.occurrences:
        _collect_bodies_recursive(occ.component, pattern, results)


# ── Screenshot / Camera Helpers ───────────────────────────────────

def _visible_bodies_bbox(root):
    """Compute bounding box of all visible bodies (root + occurrences).

    Returns (min_x, min_y, min_z, max_x, max_y, max_z) in cm.
    """
    min_x = min_y = min_z = 1e10
    max_x = max_y = max_z = -1e10

    for i in range(root.bRepBodies.count):
        b = root.bRepBodies.item(i)
        if not b.isVisible:
            continue
        bb = b.boundingBox
        min_x, min_y, min_z = min(min_x, bb.minPoint.x), min(min_y, bb.minPoint.y), min(min_z, bb.minPoint.z)
        max_x, max_y, max_z = max(max_x, bb.maxPoint.x), max(max_y, bb.maxPoint.y), max(max_z, bb.maxPoint.z)

    for i in range(root.allOccurrences.count):
        occ = root.allOccurrences.item(i)
        if not occ.isLightBulbOn:
            continue
        for j in range(occ.component.bRepBodies.count):
            body = occ.component.bRepBodies.item(j)
            if not body.isVisible:
                continue
            proxy = body.createForAssemblyContext(occ)
            bb = proxy.boundingBox
            min_x, min_y, min_z = min(min_x, bb.minPoint.x), min(min_y, bb.minPoint.y), min(min_z, bb.minPoint.z)
            max_x, max_y, max_z = max(max_x, bb.maxPoint.x), max(max_y, bb.maxPoint.y), max(max_z, bb.maxPoint.z)

    return min_x, min_y, min_z, max_x, max_y, max_z


def _bodies_bbox(bodies):
    """Compute bounding box of a list of BRepBody objects.

    Returns (min_x, min_y, min_z, max_x, max_y, max_z) in cm.
    """
    min_x = min_y = min_z = 1e10
    max_x = max_y = max_z = -1e10
    for b in bodies:
        bb = b.boundingBox
        min_x, min_y, min_z = min(min_x, bb.minPoint.x), min(min_y, bb.minPoint.y), min(min_z, bb.minPoint.z)
        max_x, max_y, max_z = max(max_x, bb.maxPoint.x), max(max_y, bb.maxPoint.y), max(max_z, bb.maxPoint.z)
    return min_x, min_y, min_z, max_x, max_y, max_z


def screenshot_cam(eye_dir, bodies=None, fill=0.80):
    """Position camera for a screenshot with dynamic zoom.

    Computes the bounding box of the target bodies, projects all 8 corners
    onto the camera's view plane, and sets the camera distance so the subject
    fills `fill` fraction of the frame. Uses perspective projection with
    the actual Fusion FOV.

    Args:
        eye_dir: (x, y, z) tuple — camera direction from target.
            Standard shots: iso-top-left (-1,-1,0.7), iso-top-right (1,-1,0.7),
            front (0,-1,0), right (1,0,0).
        bodies: List of BRepBody objects to frame. If None, frames all
            visible bodies. For detail views, pass only the bodies
            involved in the joint or feature being documented — the
            camera will zoom to their bounding box.
        fill: Fraction of frame the subject should fill (0.0-1.0).
            Default 0.80 (80%). Use ~0.90 for tight detail shots,
            ~0.70 for overview shots with more breathing room.

    Returns:
        dict with 'dist', 'center', 'bbox' for diagnostics.
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    vp = app.activeViewport

    # Ensure perspective mode (clears any leftover orthographic extents)
    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.isFitView = True
    vp.camera = cam
    adsk.doEvents()

    actual_fov = vp.camera.perspectiveAngle

    # Compute bounding box
    if bodies is not None:
        min_x, min_y, min_z, max_x, max_y, max_z = _bodies_bbox(bodies)
    else:
        min_x, min_y, min_z, max_x, max_y, max_z = _visible_bodies_bbox(root)

    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    cz = (min_z + max_z) / 2

    # Normalize eye direction
    ex, ey, ez = eye_dir
    emag = math.sqrt(ex * ex + ey * ey + ez * ez)
    ex, ey, ez = ex / emag, ey / emag, ez / emag

    # Build view-plane coordinate system
    # right = eye x up(0,0,1)
    rx, ry, rz = ey * 1 - ez * 0, ez * 0 - ex * 1, ex * 0 - ey * 0
    rmag = math.sqrt(rx * rx + ry * ry + rz * rz)
    rx, ry, rz = rx / rmag, ry / rmag, rz / rmag
    # up = right x eye
    ux = ry * ez - rz * ey
    uy = rz * ex - rx * ez
    uz = rx * ey - ry * ex

    # Project all 8 bbox corners onto view plane
    max_r = max_u = 0
    for x in [min_x - cx, max_x - cx]:
        for y in [min_y - cy, max_y - cy]:
            for z in [min_z - cz, max_z - cz]:
                max_r = max(max_r, abs(x * rx + y * ry + z * rz))
                max_u = max(max_u, abs(x * ux + y * uy + z * uz))

    # Distance from projected extent.
    # fill=0.80 means the subject fills 80% of the frame width/height.
    # tan(half_fov) * dist = full frame half-extent at target distance.
    # We want max_extent = fill * full_half_extent, so:
    #   dist = max_extent / (tan(half_fov) * fill)
    half_fov = actual_fov / 2
    dist = max(max_r, max_u) / (math.tan(half_fov) * fill)

    # For elevation views, enforce minimum distance based on 3D diagonal
    # so we don't zoom absurdly close to a flat face
    diag = math.sqrt((max_x - min_x) ** 2 + (max_y - min_y) ** 2
                     + (max_z - min_z) ** 2)
    min_dist = (diag / 2) / (math.tan(half_fov) * fill) * 0.75
    dist = max(dist, min_dist)

    # Set camera
    cam = vp.camera
    cam.isFitView = False
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.target = Point3D.create(cx, cy, cz)
    cam.eye = Point3D.create(cx + ex * dist, cy + ey * dist, cz + ez * dist)
    cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
    vp.camera = cam

    return {
        "dist": dist,
        "center": (cx, cy, cz),
        "bbox": (min_x, min_y, min_z, max_x, max_y, max_z),
    }


# ── Appearance ───────────────────────────────────────────────────────

# Species name → Fusion Appearance Library search terms (with fallbacks)
_SPECIES_MAP = {
    "cherry":      ["Cherry"],
    "walnut":      ["Walnut"],
    "oak":         ["Oak"],
    "white oak":   ["Oak"],
    "red oak":     ["Oak"],
    "maple":       ["Maple", "Oak"],
    "ash":         ["Ash", "Oak"],
    "birch":       ["Birch", "Oak"],
    "pine":        ["Pine"],
    "cedar":       ["Cedar", "Pine"],
    "mahogany":    ["Mahogany"],
    "teak":        ["Teak", "Mahogany"],
    "beech":       ["Beech", "Oak"],
    "poplar":      ["Poplar", "Oak"],
    "hickory":     ["Hickory", "Oak"],
    "ebony":       ["Ebony", "Walnut"],
    "rosewood":    ["Rosewood", "Walnut"],
    "sapele":      ["Sapele", "Mahogany"],
    "bamboo":      ["Bamboo"],
    "douglas fir": ["Douglas Fir", "Pine"],
}

# Custom texture overrides — species with their own grain photo.
# "texture" is a filename in textures/wood/ (resolved relative to repo root).
# "base" is the Fusion appearance to copy (provides bump map, reflectance model).
# "scale_x/y" in cm controls texture repeat size.
# "reflectance" overrides opaque_f0 (higher = shinier).
#
# To add a new species: drop a .jpg in textures/wood/ and add an entry here.
# scale_x / scale_y are the natural sample size (per filename / EXIF) in
# `natural_unit`. px_w / px_h are the JPEG pixel dimensions — with the natural
# size they let us compute pixel density and decide whether to apply the
# per-body compress-fit rule (see `fit_scale_y_cm` below).
_SPECIES_TEXTURE = {
    "teak":              {"base": "Mahogany", "texture": "teak.jpg",
                          "scale_x": 9.9, "scale_y": 20.1, "natural_unit": "in",
                          "px_w": 3120, "px_h": 6320,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in",
                          "eg_px_w": 2080, "eg_px_h": 620},
    "teak a":            {"base": "Mahogany", "texture": "teak_a.jpg",
                          "scale_x": 15.8, "scale_y": 60.3, "natural_unit": "in",
                          "px_w": 800, "px_h": 2902,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "teak b":            {"base": "Mahogany", "texture": "teak_b.jpg",
                          "scale_x": 13.9, "scale_y": 89.2, "natural_unit": "in",
                          "px_w": 544, "px_h": 3260,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "teak c":            {"base": "Mahogany", "texture": "teak_c.jpg",
                          "scale_x": 11.5, "scale_y": 77.0, "natural_unit": "in",
                          "px_w": 526, "px_h": 3310,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "teak d":            {"base": "Mahogany", "texture": "teak_d.jpg",
                          "scale_x": 10.1, "scale_y": 62.9, "natural_unit": "in",
                          "px_w": 508, "px_h": 3070,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "teak e":            {"base": "Mahogany", "texture": "teak_e.jpg",
                          "scale_x": 11.8701, "scale_y": 67.6785, "natural_unit": "in",
                          "px_w": 1856, "px_h": 10362,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "brazilian rosewood": {"base": "Walnut",  "texture": "brazilian_rosewood.jpg",
                          "scale_x": 8.1, "scale_y": 19.8, "reflectance": 0.06,
                          "endgrain": "brazilian_rosewood_endgrain.jpg",
                          "eg_scale_x": 6.0, "eg_scale_y": 1.9},
    "cocobolo":          {"base": "Walnut",   "texture": "cocobolo.jpg",
                          "scale_x": 9.8, "scale_y": 20.8, "reflectance": 0.07,
                          "endgrain": "cocobolo_endgrain.jpg",
                          "eg_scale_x": 6.0, "eg_scale_y": 1.3},
    "ziricote":          {"base": "Walnut",   "texture": "ziricote.jpg",
                          "scale_x": 9.0, "scale_y": 23.9, "reflectance": 0.05,
                          "endgrain": "ziricote_endgrain.jpg",
                          "eg_scale_x": 6.0, "eg_scale_y": 2.1},
    "spalted maple":     {"base": "Pine",     "texture": "spalted_maple.jpg",
                          "scale_x": 9.1, "scale_y": 17.8, "reflectance": 0.025,
                          "endgrain": "spalted_maple_endgrain.jpg",
                          "eg_scale_x": 6.7, "eg_scale_y": 5.2},
}

# Resolve textures/wood/ directory path
import os as _os
_TEXTURE_DIR = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "textures", "wood"
)

# Fusion's `texture_RealWorldScaleX/Y` and `texture_RealWorldOffsetX/Y`
# properties are stored in INCHES, regardless of the design's units (which
# are cm in this skill). The scale_x / scale_y / eg_scale_x / eg_scale_y
# values in `_SPECIES_TEXTURE` above are stored in CM (the physical sample
# size of the wood photograph at the source image's pixel density — e.g.
# teak_15.8x60.3.jpg is 400×1451 px representing a 15.8×60.3 cm board sample
# at ~25 px/cm). The wrappers multiply by `_CM_TO_TEX_IN` before writing so
# the world-space period matches the configured cm value 1:1.
#
# Note: `teak.jpg` (the base species, 1560×3160 px) is a higher-resolution
# scan with sample size 9.9×20.1 in (= 25×51 cm at 158 dpi). Despite the
# inch-natural source, its config scale_x=9.9, scale_y=20.1 is stored as cm
# for consistency — the wrapper converts uniformly. So teak.jpg renders at
# ~9.9-cm period, much smaller than its true 25-cm physical size; the trade-
# off keeps the wrapper convention simple.
_CM_TO_TEX_IN = 1.0 / 2.54


def _jpeg_dimensions(path):
    """Read pixel dimensions from a JPEG file header (no PIL dependency).
    Returns (width, height) or (None, None) if unreadable."""
    import struct as _struct
    try:
        with open(path, "rb") as f:
            f.read(2)  # SOI marker
            while True:
                marker = f.read(2)
                if len(marker) < 2:
                    return None, None
                if marker[0] != 0xFF:
                    return None, None
                if marker[1] in (0xC0, 0xC1, 0xC2):  # SOF markers
                    f.read(3)  # length + precision
                    h = _struct.unpack(">H", f.read(2))[0]
                    w = _struct.unpack(">H", f.read(2))[0]
                    return w, h
                else:
                    length = _struct.unpack(">H", f.read(2))[0]
                    f.read(length - 2)
    except Exception:
        return None, None


def _get_px_dims(cfg):
    """Return (px_w, px_h) for a species config. Uses cfg["px_w"]/["px_h"]
    if present, otherwise auto-detects from the JPEG file on disk. This
    means new species only need a texture file — no manual pixel entries."""
    px_w = cfg.get("px_w")
    px_h = cfg.get("px_h")
    if px_w and px_h:
        return px_w, px_h
    tex_path = _os.path.join(_TEXTURE_DIR, cfg.get("texture", ""))
    if _os.path.isfile(tex_path):
        w, h = _jpeg_dimensions(tex_path)
        if w and h:
            return w, h
    return None, None


def _natural_size_cm(cfg, axis, eg=False):
    """Return cfg["scale_<axis>"] (or eg_scale_<axis>) converted to cm
    based on cfg["natural_unit"] (or eg_natural_unit). Default unit cm."""
    if eg:
        val = cfg.get(f"eg_scale_{axis}", 0)
        unit = cfg.get("eg_natural_unit", cfg.get("natural_unit", "cm"))
    else:
        val = cfg.get(f"scale_{axis}", 0)
        unit = cfg.get("natural_unit", "cm")
    if unit == "in":
        return val * 2.54
    return val


def fit_scale_y_cm(body, species_key,
                    ppi_threshold_per_cm=20.0, seam_buffer=0.05):
    """Per-body compress-fit rule for the grain-direction (scale_y) period.

    Thin wrapper that reads body bbox + species cfg and delegates to
    `box_diagnostic.recommend_period_cm()` for the actual rule. Kept
    here for backwards compatibility; the rule itself lives in the
    diagnostic module so it can be exercised + recalibrated separately.

    Args:
        body: Fusion BRepBody — bbox is read for grain extent.
        species_key: key into _SPECIES_TEXTURE (must have px_h field).
        ppi_threshold_per_cm: pixel-per-cm density above which the image
            is considered sharp enough at natural size. Default 20 px/cm.
        seam_buffer: extra fraction added to body length when compressing.
            Default 5% — empirically smallest reliably seam-free margin
            across body sizes 5–100 cm. See box_diagnostic.calibrate_seam_buffer
            to re-derive after Fusion updates.

    Returns:
        Recommended scale_y in cm (or natural cm if rule doesn't apply).
    """
    cfg = _SPECIES_TEXTURE.get(species_key)
    if not cfg:
        return None
    natural_cm = _natural_size_cm(cfg, "y")
    if natural_cm <= 0:
        return natural_cm
    _, px_h = _get_px_dims(cfg)
    # If pixel dimensions can't be determined (no px_h in config AND JPEG
    # file unreadable), treat as natural-scale — safe no-op.
    if not px_h:
        return natural_cm
    bb = body.boundingBox
    body_grain_cm = max(bb.maxPoint.x - bb.minPoint.x,
                         bb.maxPoint.y - bb.minPoint.y,
                         bb.maxPoint.z - bb.minPoint.z)
    ppi = px_h / natural_cm
    # Lazy import to avoid load-time cycle.
    from helpers import box_diagnostic
    period_cm, _rule = box_diagnostic.recommend_period_cm(
        body_grain_cm, natural_cm, ppi,
        ppi_threshold=ppi_threshold_per_cm,
        seam_buffer=seam_buffer)
    return period_cm


def _apply_custom_texture(local_appearance, species_key, body=None, _force=False):
    """Swap texture bitmap and tune properties for a custom species.

    Args:
        local_appearance: Design-local copy of a Fusion appearance.
        species_key: Key into _SPECIES_TEXTURE.
        body: Optional BRepBody. When provided, the per-body fit rule
            (fit_scale_y_cm) is applied to scale_y instead of the natural
            value.

    Returns:
        True if texture was applied, False if texture file not found.

    Safety: refuses to modify an appearance that is currently assigned to
    more than one body in the active design. This prevents accidental
    cross-body texture resets when a shared SP_<species> appearance is
    modified. Use sp.per_body_appearance(body, species) to get a safe
    per-body copy instead.
    """
    # Guard: refuse to modify if multiple bodies reference this appearance.
    # _force=True bypasses — used by sp.apply_appearance() which intentionally
    # refreshes shared species appearances in the bulk assignment flow.
    if _force:
        pass  # skip guard
    else:
      try:
        _guard_app = adsk.core.Application.get()
        _guard_design = adsk.fusion.Design.cast(_guard_app.activeProduct)
        if _guard_design:
            ref_count = 0
            def _count_refs(comp):
                nonlocal ref_count
                for i in range(comp.bRepBodies.count):
                    b = comp.bRepBodies.item(i)
                    try:
                        if b.appearance and b.appearance.name == local_appearance.name:
                            ref_count += 1
                            if ref_count > 1:
                                return  # early exit
                    except Exception:
                        pass
                for i in range(comp.occurrences.count):
                    _count_refs(comp.occurrences.item(i).component)
                    if ref_count > 1:
                        return
            _count_refs(_guard_design.rootComponent)
            if ref_count > 1:
                raise ValueError(
                    f"Refusing to modify '{local_appearance.name}' — "
                    f"it is referenced by {ref_count} bodies. "
                    f"Use sp.per_body_appearance(body, species_key) to get "
                    f"a safe per-body copy first.")
      except ValueError:
          raise  # re-raise the guard error
      except Exception:
          pass  # if design isn't available (e.g. during tests), skip the guard

    cfg = _SPECIES_TEXTURE[species_key]
    tex_path = _os.path.join(_TEXTURE_DIR, cfg["texture"])
    if not _os.path.isfile(tex_path):
        return False

    props = local_appearance.appearanceProperties
    cp = adsk.core.ColorProperty.cast(props.itemById("opaque_albedo"))
    if not cp or not cp.hasConnectedTexture:
        return False

    tex = cp.connectedTexture

    # Swap the bitmap
    bmp = tex.properties.itemById("unifiedbitmap_Bitmap")
    if bmp:
        fp = adsk.core.FilenameProperty.cast(bmp)
        if fp and not fp.isReadOnly:
            fp.value = tex_path

    # Compute scales in cm — natural for X (cross-grain), fit-rule for Y when
    # a body is supplied. Fusion stores RealWorldScale* in inches: multiply
    # by _CM_TO_TEX_IN before writing.
    sx_cm = _natural_size_cm(cfg, "x")
    if body is not None:
        sy_cm = fit_scale_y_cm(body, species_key)
    else:
        sy_cm = _natural_size_cm(cfg, "y")
    sx_prop = tex.properties.itemById("texture_RealWorldScaleX")
    sy_prop = tex.properties.itemById("texture_RealWorldScaleY")
    if sx_prop and sx_cm:
        adsk.core.FloatProperty.cast(sx_prop).value = sx_cm * _CM_TO_TEX_IN
    if sy_prop and sy_cm:
        adsk.core.FloatProperty.cast(sy_prop).value = sy_cm * _CM_TO_TEX_IN

    # Set reflectance
    if cfg.get("reflectance"):
        f0 = props.itemById("opaque_f0")
        if f0:
            adsk.core.FloatProperty.cast(f0).value = cfg["reflectance"]

    return True


def per_body_appearance(body, species_key):
    """Get (or create) a per-body appearance for this specific body.

    Copies from the Fusion material library base directly -- no shared
    SP_<species> intermediate is created or modified. _apply_custom_texture
    is only called on the per-body copy, so modifying scale/bitmap can
    never affect another body.

    Naming convention: SP_<species>_<body.name>

    Args:
        body: adsk.fusion.BRepBody
        species_key: key into _SPECIES_TEXTURE (e.g. "teak b")

    Returns:
        The per-body appearance (adsk.core.Appearance), already assigned
        to body.appearance and with the species texture applied.
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    cfg = _SPECIES_TEXTURE.get(species_key)
    if not cfg:
        raise ValueError(f"Unknown species: {species_key!r}")

    # Include component name to avoid collisions when bodies in different
    # components share the same name (e.g. "Body1" in legs vs stretcher).
    comp_name = body.parentComponent.name if body.parentComponent else "root"
    local_name = f"SP_{species_key}_{comp_name}_{body.name}"
    local = design.appearances.itemByName(local_name)
    if not local:
        # Copy from library base directly -- skip shared SP_<species>
        base_name = cfg.get("base", "Mahogany")
        base_app = None
        libs = app.materialLibraries
        for li in range(libs.count):
            lib = libs.item(li)
            for ai in range(lib.appearances.count):
                a = lib.appearances.item(ai)
                if a.name == base_name and not a.name.startswith("3D "):
                    if "appearance" in lib.name.lower():
                        base_app = a
                        break
                    if base_app is None:
                        base_app = a
            if base_app and "appearance" in lib.name.lower():
                break
        if base_app is None:
            raise RuntimeError(
                f"Cannot create appearance for '{species_key}': "
                f"base '{base_name}' not found in material libraries")
        local = design.appearances.addByCopy(base_app, local_name)

    # Apply species texture to the per-body copy only
    _apply_custom_texture(local, species_key)
    body.appearance = local
    return local


def _apply_endgrain_texture(local_appearance, species_key):
    """Swap texture bitmap for an end grain appearance.

    Same as _apply_custom_texture but uses endgrain file + eg_scale.
    """
    cfg = _SPECIES_TEXTURE[species_key]
    eg_file = cfg.get("endgrain")
    if not eg_file:
        return False
    tex_path = _os.path.join(_TEXTURE_DIR, eg_file)
    if not _os.path.isfile(tex_path):
        return False

    props = local_appearance.appearanceProperties
    cp = adsk.core.ColorProperty.cast(props.itemById("opaque_albedo"))
    if not cp or not cp.hasConnectedTexture:
        return False

    tex = cp.connectedTexture

    bmp = tex.properties.itemById("unifiedbitmap_Bitmap")
    if bmp:
        fp = adsk.core.FilenameProperty.cast(bmp)
        if fp and not fp.isReadOnly:
            fp.value = tex_path

    # End grain scale — uses eg_scale_* + eg_natural_unit (or natural_unit).
    sx_cm = _natural_size_cm(cfg, "x", eg=True)
    sy_cm = _natural_size_cm(cfg, "y", eg=True)
    sx_prop = tex.properties.itemById("texture_RealWorldScaleX")
    sy_prop = tex.properties.itemById("texture_RealWorldScaleY")
    if sx_prop and sx_cm:
        adsk.core.FloatProperty.cast(sx_prop).value = sx_cm * _CM_TO_TEX_IN
    if sy_prop and sy_cm:
        adsk.core.FloatProperty.cast(sy_prop).value = sy_cm * _CM_TO_TEX_IN

    if cfg.get("reflectance"):
        f0 = props.itemById("opaque_f0")
        if f0:
            adsk.core.FloatProperty.cast(f0).value = cfg["reflectance"]

    return True


def _grain_axis(body):
    """Grain direction = longest bounding box axis (name string)."""
    bb = body.boundingBox
    dims = {
        "x": abs(bb.maxPoint.x - bb.minPoint.x),
        "y": abs(bb.maxPoint.y - bb.minPoint.y),
        "z": abs(bb.maxPoint.z - bb.minPoint.z),
    }
    return max(dims, key=dims.get)


def _grain_vector(body):
    """Compute grain direction as a unit vector using principal axes of inertia.

    The axis with the smallest moment of inertia is the elongation axis
    (grain direction).  Works for any orientation: axis-aligned boards,
    compound-angle splayed legs, angled stretchers, turned spindles.

    Falls back to bounding-box longest axis if the API call fails.
    """
    import adsk.core

    # Primary: principal axes of inertia
    try:
        pp = body.physicalProperties
        ok_ax, ax_x, ax_y, ax_z = pp.getPrincipalAxes()
        ok_mo, mx, my, mz = pp.getPrincipalMomentsOfInertia()
        if ok_ax and ok_mo:
            axes = [(mx, ax_x), (my, ax_y), (mz, ax_z)]
            axes.sort(key=lambda a: a[0])
            g = axes[0][1]  # smallest moment = elongation axis
            vx, vy, vz = g.x, g.y, g.z
            # Ensure dominant component is positive for consistent rotation
            comps = [("x", abs(vx)), ("y", abs(vy)), ("z", abs(vz))]
            dominant = max(comps, key=lambda c: c[1])[0]
            if (dominant == "x" and vx < 0) or \
               (dominant == "y" and vy < 0) or \
               (dominant == "z" and vz < 0):
                vx, vy, vz = -vx, -vy, -vz
            return adsk.core.Vector3D.create(vx, vy, vz)
    except Exception:
        pass

    # Fallback: bounding box longest axis
    axis = _grain_axis(body)
    v = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[axis]
    return adsk.core.Vector3D.create(*v)


def _find_endgrain_faces(body, grain_vec):
    """Find faces whose normals are parallel to the grain direction (end grain).

    grain_vec: Vector3D or axis name string (backward compat).
    """
    import adsk.core
    if isinstance(grain_vec, str):
        # Legacy axis name
        gv = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[grain_vec]
        grain_vec = adsk.core.Vector3D.create(*gv)
    endgrain_faces = []
    for i in range(body.faces.count):
        face = body.faces.item(i)
        geom = face.geometry
        if isinstance(geom, adsk.core.Plane):
            n = geom.normal
            dot = abs(n.x * grain_vec.x + n.y * grain_vec.y + n.z * grain_vec.z)
            if dot > 0.85:  # ~30° tolerance for splayed faces
                endgrain_faces.append(face)
    return endgrain_faces


def _grain_transform(grain_dir):
    """Rotate texture so grain (texture Y) aligns with grain direction.

    grain_dir: axis name string ("x"/"y"/"z") or Vector3D for arbitrary angles.
    """
    import adsk.core
    m = adsk.core.Matrix3D.create()
    if isinstance(grain_dir, str):
        if grain_dir == "x":
            m.setToRotation(math.pi / 2, adsk.core.Vector3D.create(0, 1, 0),
                            Point3D.create(0, 0, 0))
        elif grain_dir == "y":
            m.setToRotation(-math.pi / 2, adsk.core.Vector3D.create(1, 0, 0),
                            Point3D.create(0, 0, 0))
        # "z" = identity (default texture direction)
    else:
        # Arbitrary vector — rotate texture Z to align with grain_dir
        z_axis = adsk.core.Vector3D.create(0, 0, 1)
        angle = z_axis.angleTo(grain_dir)
        if angle > 0.001 and angle < math.pi - 0.001:
            cross = z_axis.crossProduct(grain_dir)
            if cross.length > 0.001:
                cross.normalize()
                m.setToRotation(angle, cross, Point3D.create(0, 0, 0))
        elif angle >= math.pi - 0.001:
            # ~180° — rotate around any perpendicular axis
            m.setToRotation(math.pi, adsk.core.Vector3D.create(0, 1, 0),
                            Point3D.create(0, 0, 0))
    return m


def apply_appearance(species="white oak", bodies=None):
    """Apply wood appearance to bodies with grain-aligned texture.

    Call at the end of a script, after all geometry is built.

    Args:
        species: Wood species name (e.g. "cherry", "walnut", "white oak").
                 Falls back to a similar species if exact match unavailable.
        bodies: Optional list of body name strings. If None, applies to ALL
                bodies. Use for multi-species designs.

    Usage:
        sp.apply_appearance("walnut")                          # all bodies
        sp.apply_appearance("white oak", bodies=["Seat"])      # specific bodies
        sp.apply_appearance("teak", bodies=["Leg_FL","Leg_FR"]) # accent species
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    species_lower = species.lower().strip()

    # ── Custom texture path: copy base appearance + swap bitmap ──
    custom_tex = species_lower in _SPECIES_TEXTURE
    if custom_tex:
        cfg = _SPECIES_TEXTURE[species_lower]
        base_name = cfg["base"]
        local_name = f"SP_{species_lower}"
        # Re-use existing or create new, always refresh texture from disk
        local = design.appearances.itemByName(local_name)
        if not local:
            # Find base appearance in libraries
            base_app = None
            libs = app.materialLibraries
            for li in range(libs.count):
                lib = libs.item(li)
                for ai in range(lib.appearances.count):
                    a = lib.appearances.item(ai)
                    if a.name == base_name and not a.name.startswith("3D "):
                        if "appearance" in lib.name.lower():
                            base_app = a
                            break
                        if base_app is None:
                            base_app = a
                if base_app and "appearance" in lib.name.lower():
                    break
            if base_app is None:
                print(f"WARNING: Base appearance '{base_name}' not found "
                      f"for custom species '{species}'")
                return
            local = design.appearances.addByCopy(base_app, local_name)
        # Always re-apply texture (picks up file changes on disk)
        if not _apply_custom_texture(local, species_lower, _force=True):
            print(f"WARNING: Texture file not found for '{species}' "
                  f"— using base {base_name}. "
                  f"Place {cfg['texture']} in textures/wood/")
    else:
        # ── Standard path: find appearance by species map ──
        search_terms = _SPECIES_MAP.get(species_lower, [species])
        appearance = None
        for term in search_terms:
            for i in range(design.appearances.count):
                a = design.appearances.item(i)
                if term.lower() in a.name.lower() and not a.name.startswith("3D "):
                    appearance = a
                    break
            if appearance:
                break
            libs = app.materialLibraries
            for li in range(libs.count):
                lib = libs.item(li)
                for ai in range(lib.appearances.count):
                    a = lib.appearances.item(ai)
                    if term.lower() in a.name.lower():
                        if a.name.startswith("3D "):
                            continue
                        if "appearance" in lib.name.lower():
                            appearance = a
                            break
                        if appearance is None:
                            appearance = a
                if appearance and "appearance" in lib.name.lower():
                    break
            if appearance:
                break

        if appearance is None:
            print(f"WARNING: No appearance found for '{species}'")
            return

        local = design.appearances.itemByName(appearance.name)
        if not local:
            local = design.appearances.addByCopy(appearance, appearance.name)

    # Collect target bodies
    def all_bodies_recursive(comp):
        result = []
        for i in range(comp.bRepBodies.count):
            result.append(comp.bRepBodies.item(i))
        for i in range(comp.occurrences.count):
            result.extend(all_bodies_recursive(comp.occurrences.item(i).component))
        return result

    target_bodies = all_bodies_recursive(root)
    if bodies is not None:
        name_set = set(bodies)
        target_bodies = [b for b in target_bodies if b.name in name_set]

    # Create end grain appearance if available
    eg_local = None
    if custom_tex and _SPECIES_TEXTURE[species_lower].get("endgrain"):
        eg_name = f"SP_{species_lower}_endgrain"
        eg_local = design.appearances.itemByName(eg_name)
        if not eg_local:
            base_app = None
            libs = app.materialLibraries
            cfg = _SPECIES_TEXTURE[species_lower]
            for li in range(libs.count):
                lib = libs.item(li)
                for ai in range(lib.appearances.count):
                    a = lib.appearances.item(ai)
                    if a.name == cfg["base"] and not a.name.startswith("3D "):
                        if "appearance" in lib.name.lower():
                            base_app = a
                            break
                        if base_app is None:
                            base_app = a
                if base_app and "appearance" in lib.name.lower():
                    break
            if base_app:
                eg_local = design.appearances.addByCopy(base_app, eg_name)
        # Always refresh texture from disk
        if eg_local:
            _apply_endgrain_texture(eg_local, species_lower)

    # Apply to each body with grain orientation
    count = 0
    eg_count = 0
    for body in target_bodies:
        try:
            body.appearance = local
            grain_vec = _grain_vector(body)
            adsk.doEvents()
            tmc = body.textureMapControl
            if tmc:
                ptmc = adsk.core.ProjectedTextureMapControl.cast(tmc)
                if ptmc:
                    ptmc.projectedTextureMapType = (
                        adsk.core.ProjectedTextureMapTypes
                        .BoxTextureMapProjection)
                    ptmc.transform = _grain_transform(grain_vec)
            count += 1

            # Apply end grain to faces perpendicular to grain axis
            if eg_local:
                for face in _find_endgrain_faces(body, grain_vec):
                    face.appearance = eg_local
                    eg_count += 1
        except Exception:
            pass

    msg = f"Applied {local.name} to {count} bodies"
    if eg_count:
        msg += f" ({eg_count} end grain faces)"
    print(msg)


# ── Dependency Tree Validation ─────────────────────────────────────

def validate_deps(ctx, metadata_path=None):
    """Validate spatial relationships from a model.json metadata file.

    Reads the dependency tree and checks:
    1. Side — is each body on the expected side of its reference body?
       Uses center-of-mass via body_side(). Handles joints correctly
       (tenon is small vs. main body, COM stays on the correct side).
    2. Contact — do bounding boxes overlap? (connected pieces must touch)

    Args:
        ctx: DesignContext instance
        metadata_path: path to model.json. If None, tries to find it
            next to the calling script via the design's script path.

    Returns:
        True if all checks pass, False if any fail.
        Returns None if no metadata file found (not an error — just
        means this project predates metadata).
    """
    import json
    import os
    import re

    # Resolve metadata path
    if metadata_path is None:
        # Try to find model.json next to the script via DocumentTracker
        script_path = None
        try:
            from server.document_tracker import DocumentTracker
            script_path = DocumentTracker._script_path
        except Exception:
            pass
        if script_path:
            script_dir = os.path.dirname(script_path)
            stem = os.path.splitext(os.path.basename(script_path))[0]
            per_script = os.path.join(script_dir, f"{stem}_model.json")
            if os.path.exists(per_script):
                metadata_path = per_script
            else:
                metadata_path = os.path.join(script_dir, "model.json")
        else:
            print("validate_deps: no metadata path and no script path found")
            return None

    if not os.path.exists(metadata_path):
        print(f"validate_deps: {metadata_path} not found — skipping "
              f"(create model.json to enable dependency validation)")
        return None

    with open(metadata_path, "r") as f:
        meta = json.load(f)

    deps = meta.get("deps", [])
    if not deps:
        print("validate_deps: no deps entries in metadata")
        return True

    print(f"\n=== Dependency tree ({len(deps)} relationships) ===")
    all_ok = True

    for entry in deps:
        body_name = entry["body"]
        ref_name = entry["ref"]
        expected = entry["side"]
        direction = tuple(entry["direction"])
        contact = entry.get("contact", True)
        note = entry.get("note", "")

        body = ctx.find_body(body_name)
        if not body:
            print(f"  SKIP  {body_name} → {ref_name}: "
                  f"body '{body_name}' not found")
            continue

        # ── Origin/floor as reference ──
        # "origin" means the XY ground plane (Z=0). The body should be
        # above the floor (COM z > 0) and touching it (bbox minZ ≈ 0).
        if ref_name == "origin":
            com = body.physicalProperties.centerOfMass
            dot = (com.x * direction[0] +
                   com.y * direction[1] +
                   com.z * direction[2])
            actual = "outside" if dot > 0 else "opposite"
            side_ok = (actual == expected)
            tag = " OK " if side_ok else "FAIL"
            print(f"  {tag}  {body_name} is {actual} of origin "
                  f"(expected {expected})"
                  + (f"  — {note}" if note and not side_ok else ""))
            if not side_ok:
                all_ok = False
            if contact:
                bb = body.boundingBox
                # Check that body touches the origin plane along direction
                # For direction (0,0,1): minZ should be near 0
                # For direction (0,1,0): minY should be near 0, etc.
                axis_vals = [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z]
                axis_idx = direction.index(max(direction, key=abs))
                near_origin = abs(axis_vals[axis_idx]) < 0.1  # within 1mm
                if not near_origin:
                    print(f"  FAIL  {body_name} not touching origin "
                          f"(min along axis = {axis_vals[axis_idx]:.3f})")
                    all_ok = False
            continue

        # ── Normal body-to-body reference ──
        ref = ctx.find_body(ref_name)
        if not ref:
            print(f"  SKIP  {body_name} → {ref_name}: "
                  f"ref '{ref_name}' not found")
            continue

        # Side check
        actual = body_side(body, ref, direction)
        side_ok = (actual == expected)
        tag = " OK " if side_ok else "FAIL"
        print(f"  {tag}  {body_name} is {actual} of {ref_name} "
              f"(expected {expected})"
              + (f"  — {note}" if note and not side_ok else ""))
        if not side_ok:
            all_ok = False

        # Contact check
        if contact:
            bb = body.boundingBox
            rb = ref.boundingBox
            touch = (bb.minPoint.x <= rb.maxPoint.x + 0.01 and
                     bb.maxPoint.x >= rb.minPoint.x - 0.01 and
                     bb.minPoint.y <= rb.maxPoint.y + 0.01 and
                     bb.maxPoint.y >= rb.minPoint.y - 0.01 and
                     bb.minPoint.z <= rb.maxPoint.z + 0.01 and
                     bb.maxPoint.z >= rb.minPoint.z - 0.01)
            if not touch:
                print(f"  FAIL  {body_name} has NO CONTACT with {ref_name}")
                all_ok = False

    # ── Source check: did the code actually reference each dep's body? ──
    script_source = None
    try:
        from server.document_tracker import DocumentTracker
        src_path = DocumentTracker._script_path
        if src_path and os.path.isfile(src_path):
            with open(src_path, "r") as f:
                script_source = f.read()
    except Exception:
        pass

    if script_source and deps:
        print("--- Reference usage check ---")
        for entry in deps:
            body_name = entry["body"]
            ref_name = entry["ref"]

            # Origin ref = root body using construction planes — correct by design
            if ref_name == "origin":
                print(f"   OK   {body_name}: root body (ref=origin)")
                continue

            # Check 1: was find_body("ref_name") called?
            # Match patterns: find_body("ref_name"), find_body('ref_name')
            lookup_pat = re.compile(
                r'find_body\(\s*["\']' + re.escape(ref_name) + r'["\']'
            )
            found_lookup = bool(lookup_pat.search(script_source))

            # Check 2: was .boundingBox accessed on that body?
            # Look for boundingBox near the find_body call (within same section)
            found_bb = False
            if found_lookup:
                # Find all positions of the lookup
                for m in lookup_pat.finditer(script_source):
                    # Check ~40 lines after the lookup for .boundingBox
                    start = m.start()
                    # Count forward ~40 lines
                    end = start
                    newlines = 0
                    while end < len(script_source) and newlines < 40:
                        if script_source[end] == '\n':
                            newlines += 1
                        end += 1
                    snippet = script_source[start:end]
                    if '.boundingBox' in snippet or 'find_face' in snippet:
                        found_bb = True
                        break

            if not found_lookup:
                print(f"  WARN  {body_name}: ref body '{ref_name}' never "
                      f"looked up — likely using origin-based positioning")
                all_ok = False
            elif not found_bb:
                print(f"  WARN  {body_name}: ref body '{ref_name}' found "
                      f"but .boundingBox/find_face never used — "
                      f"ceremonial lookup?")
                # Don't fail on this — the body might be used as a
                # sketch plane or CUT tool without needing bounding box
            else:
                print(f"   OK   {body_name}: ref '{ref_name}' looked up "
                      f"+ geometry read")

    # ── Completeness check: are all design bodies tracked? ──
    import fnmatch as _fnmatch
    print("--- Completeness check ---")
    tracked = set(entry["body"] for entry in deps)
    replica_patterns = []
    for entry in deps:
        if "replicas" in entry:
            replica_patterns.append(entry["replicas"])

    # Collect ALL bodies — root AND components. No exclusions.
    root_bodies = []
    comp_bodies = []
    for i in range(ctx.root.bRepBodies.count):
        root_bodies.append(ctx.root.bRepBodies.item(i).name)

    def _collect_comp_bodies(comp):
        for i in range(comp.bRepBodies.count):
            comp_bodies.append(comp.bRepBodies.item(i).name)

    for j in range(ctx.root.occurrences.count):
        _collect_comp_bodies(ctx.root.occurrences.item(j).component)

    # Flag root-level bodies — ALL bodies should be inside components.
    if root_bodies:
        print(f"  FAIL  {len(root_bodies)} bodies in root component "
              f"(should be inside a component):")
        for rb in root_bodies[:10]:
            print(f"         - {rb}")
        if len(root_bodies) > 10:
            print(f"         ... and {len(root_bodies) - 10} more")
        all_ok = False

    all_bodies = root_bodies + comp_bodies
    orphans = []
    for name in all_bodies:
        # Exact match
        if name in tracked:
            continue
        # Pattern copy: "Slat (3)" → base "Slat"
        base = re.sub(r'\s*\(\d+\)$', '', name)
        if base in tracked:
            continue
        # Replica glob: e.g. "Rung_*" covers Rung_2, Rung_3, etc.
        if any(_fnmatch.fnmatch(name, pat) for pat in replica_patterns):
            continue
        orphans.append(name)

    if orphans:
        for o in orphans:
            print(f"  MISS  {o}: exists in design but not in model.json")
        all_ok = False
    else:
        print(f"   OK   All {len(all_bodies)} bodies are tracked")

    status = "PASS" if all_ok else "FAIL"
    print(f"=== Dependency validation: {status} ===\n")
    return all_ok
