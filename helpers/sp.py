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


def combine(comp, target, tool_bodies, op, keep_tool, name="Comb"):
    """Combine (CUT/JOIN) tool bodies into a target body.

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


def make_comp(root_comp, name):
    """Create a new component under root_comp.

    Returns the Occurrence (access component via ``occ.component``).
    """
    occ = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
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
_SPECIES_TEXTURE = {
    "teak":              {"base": "Mahogany", "texture": "teak.jpg",
                          "scale_x": 9.9, "scale_y": 20.1, "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8},
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


def _apply_custom_texture(local_appearance, species_key):
    """Swap texture bitmap and tune properties for a custom species.

    Args:
        local_appearance: Design-local copy of a Fusion appearance.
        species_key: Key into _SPECIES_TEXTURE.

    Returns:
        True if texture was applied, False if texture file not found.
    """
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

    # Set texture scale
    sx_prop = tex.properties.itemById("texture_RealWorldScaleX")
    sy_prop = tex.properties.itemById("texture_RealWorldScaleY")
    if sx_prop and cfg.get("scale_x"):
        adsk.core.FloatProperty.cast(sx_prop).value = cfg["scale_x"]
    if sy_prop and cfg.get("scale_y"):
        adsk.core.FloatProperty.cast(sy_prop).value = cfg["scale_y"]

    # Set reflectance
    if cfg.get("reflectance"):
        f0 = props.itemById("opaque_f0")
        if f0:
            adsk.core.FloatProperty.cast(f0).value = cfg["reflectance"]

    return True


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

    sx_prop = tex.properties.itemById("texture_RealWorldScaleX")
    sy_prop = tex.properties.itemById("texture_RealWorldScaleY")
    if sx_prop and cfg.get("eg_scale_x"):
        adsk.core.FloatProperty.cast(sx_prop).value = cfg["eg_scale_x"]
    if sy_prop and cfg.get("eg_scale_y"):
        adsk.core.FloatProperty.cast(sy_prop).value = cfg["eg_scale_y"]

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
        if not _apply_custom_texture(local, species_lower):
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
