"""
AutoFusion Runtime Helpers

Shared utilities for Fusion 360 scripts executed via execute_script.
Import with: from helpers import af

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
        ctx = af.DesignContext()
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
        """Evaluate parameter name or expression string to float (cm)."""
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
    ).parameter.expression = model_size[h_axis]
    d.addDistanceDimension(
        rect[1].startSketchPoint, rect[1].endSketchPoint,
        V, Point3D.create(sk_f.x - dx, mid_y, 0)
    ).parameter.expression = model_size[v_axis]
    d.addDistanceDimension(
        sk.originPoint, rect[0].startSketchPoint,
        H, Point3D.create(sk_o.x / 2, sk_o.y + 2 * dy, 0)
    ).parameter.expression = axis_to_origin[h_axis]
    d.addDistanceDimension(
        sk.originPoint, rect[0].startSketchPoint,
        V, Point3D.create(sk_o.x + dx, sk_o.y / 2, 0)
    ).parameter.expression = axis_to_origin[v_axis]

    return sk, sk.profiles.item(0)


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


def _collect_bodies_recursive(comp, pattern, results):
    """Walk component tree to find bodies matching glob pattern."""
    import fnmatch
    for i in range(comp.bRepBodies.count):
        body = comp.bRepBodies.item(i)
        if fnmatch.fnmatch(body.name, pattern):
            results.append(body)
    for occ in comp.occurrences:
        _collect_bodies_recursive(occ.component, pattern, results)
