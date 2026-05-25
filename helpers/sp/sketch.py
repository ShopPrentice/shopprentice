import adsk.core
import adsk.fusion
import math

from ._util import _make_ev

Point3D = adsk.core.Point3D
H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation


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

    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0])
    gc.addHorizontal(rect[2])
    gc.addVertical(rect[1])
    gc.addVertical(rect[3])

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

    gc = sk.geometricConstraints
    gc.addHorizontal(rect[0])
    gc.addHorizontal(rect[2])
    gc.addVertical(rect[1])
    gc.addVertical(rect[3])

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

    for entity in (project or []):
        sk.project(entity)

    if intersect:
        result = sk.intersectWithSketchPlane(intersect)
        if result:
            for c in result:
                if hasattr(c, 'isConstruction'):
                    c.isConstruction = True

    refs_to_construction(sk)

    found = {}
    if identify:
        m2s = sk.modelToSketchSpace
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
