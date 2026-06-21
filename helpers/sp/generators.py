"""Tier 2 — certified library generators.

Generators promoted out of per-model scripts into the shared library, so certifying
their constraint topology once (see ``genreg`` + the certification harness) covers
every project that calls them. Each is registered with :func:`genreg.register`,
feeds the Tier-1 DOF guard as it builds, and stamps its sketch with
``name@source_hash`` so the deps check can trust it at build time.

Currently:

* ``base_arch_cut`` — the canonical hard case: ONE continuous fitted spline
  (leg cyma → apron arch → leg cyma), mirrored about the span centre, closed
  underneath by a 3-line waste rail into a single cut profile. Promoted from the
  local function in ``bookcase-with-drawers/bookcase_with_drawers.py``.
"""
import adsk.core

from .genreg import register, stamp
from .dof import default_tracker
from .sketch import probe_orientations, refs_to_construction, smallest_profile

Point3D = adsk.core.Point3D

# Inch → cm. fitPoint world coords / placement are model units (cm); the sculpted
# half-curve is authored in INCHES. Passing inch coords without this ×2.54 scales
# the whole curve down by 2.54 — the silent "collapsed shape" bug (brief §4).
IN = 2.54


def _mirror(half_cm, ctr):
    """Mirror a half-curve about the span centre into the full, symmetric point
    list. Two topology branches (both must be certified):

      * center-shared — last half point sits ON the centreline (odd total): the
        crest is a single shared point; mirror all but the last.
      * center-pair   — last half point is left of centre (even total): mirror
        all, so the two innermost points straddle the centre as a pair.
    """
    if abs(half_cm[-1][0] - ctr) < 0.05:
        return half_cm + [(2 * ctr - u, z) for (u, z) in reversed(half_cm[:-1])], \
               "center-shared"
    return half_cm + [(2 * ctr - u, z) for (u, z) in reversed(half_cm)], \
           "center-pair"


@register(
    "base_arch_cut",
    contract=("closed free-spline top edge mirrored about the span centre + a "
              "3-line waste-rail frame; spline endpoints anchored to the floor "
              "line, interiors free; closes into one cut profile"),
    when_to_use=("one continuous sculpted curve must flow across multiple members "
                 "(leg→apron→leg) and be cut in a single feature. ROOT/origin "
                 "component only: endpoints anchor to the sketch origin, which deps "
                 "permits only in the origin-root component. Floor is model z=0."),
    branches=["center-shared", "center-pair"],
    range_guards=["span > 2*end_inset", "half_uz strictly increasing in u",
                  "half_uz[0] z == 0 (endpoint on the floor line)"],
)
def base_arch_cut(comp, plane, axis, span_expr, half_uz, end_inset_expr,
                  off_axis_cm, name, floor_z_expr="0 in", rail_depth_expr="0.5 in",
                  ev=None, dof=None):
    """Build the constrained arch-cut profile sketch and return ``(sketch, profile)``.

    The caller supplies the (already-offset) sketch ``plane`` and later extrudes the
    returned profile as a CUT across the target members. This function owns only the
    certifiable artifact: the fully-constrained-modulo-interiors closed profile.

    Args:
        comp: ROOT/origin component (endpoints anchor to the sketch origin).
        plane: sketch plane (caller builds the offset plane).
        axis: 'x' or 'y' — model axis the span runs along; the in-plane vertical
            axis is model z.
        span_expr: span dimension expression (along ``axis``).
        half_uz: half-curve fit points as (u_inch, z_inch), floor→centre. The first
            point is the floor endpoint (z must be 0); the last is the crest (on the
            centreline for center-shared, or left of it for center-pair).
        end_inset_expr: distance along ``axis`` from each end to the spline endpoint
            (the foot inner edge at the floor).
        off_axis_cm: model coordinate of the sketch plane on the OFF axis (the value
            used to build ``plane``), in cm.
        name: base name; the sketch is ``name + "_Sk"``.
        floor_z_expr: model-z expression of the endpoints (default "0 in").
        rail_depth_expr: waste-rail depth below the floor (default "0.5 in").
        ev: evaluator (expr → float cm). Required.
        dof: optional DOF tracker (defaults to the global-switch tracker).

    CONSTRAINT ORDER (brief §4, do not reorder): dimension the spline ENDPOINTS
    first, while the spline is the only geometry; THEN add the closing rail lines +
    H/V; THEN the single rail-depth dim. If the rail lines go first, the closed loop
    already determines the endpoints and the endpoint dims read as redundant →
    VCS_SKETCH_OVER_CONSTRAINTS. The fit points are NOT auto-fixed; interiors stay
    free (drag-to-shape).
    """
    if ev is None:
        raise ValueError("base_arch_cut requires an evaluator ev")
    dof = dof or default_tracker(name + "_Sk")

    sk = comp.sketches.add(plane)
    sk.name = name + "_Sk"
    m = sk.modelToSketchSpace

    def mp(u, z):
        p = Point3D.create(u, off_axis_cm, z) if axis == "x" \
            else Point3D.create(off_axis_cm, u, z)
        return m(p)

    span = ev(span_expr)
    ctr = span / 2.0
    half_cm = [(u * IN, z * IN) for (u, z) in half_uz]
    pts, branch = _mirror(half_cm, ctr)

    # ── fitted spline (data = exempt interiors; endpoints anchored below) ──
    coll = adsk.core.ObjectCollection.create()
    for u, z in pts:
        q = mp(u, z)
        coll.add(Point3D.create(q.x, q.y, 0))
    spline = sk.sketchCurves.sketchFittedSplines.add(coll)
    dof.add_spline(len(pts))                      # +2 endpoints, len-2 interiors exempt

    # ── endpoint dims FIRST (order matters) ──
    sh = ev(floor_z_expr)
    ori = probe_orientations(sk, (ctr if axis == "x" else off_axis_cm),
                             (off_axis_cm if axis == "x" else ctr), sh)
    au, az = ori[axis], ori["z"]
    d = sk.sketchDimensions
    d.addDistanceDimension(sk.originPoint, spline.startSketchPoint, au,
                           Point3D.create(pts[0][0] - 2, 1, 0)
                           ).parameter.expression = end_inset_expr
    d.addDistanceDimension(sk.originPoint, spline.startSketchPoint, az,
                           Point3D.create(pts[0][0] - 3, 1, 0)
                           ).parameter.expression = floor_z_expr
    d.addDistanceDimension(sk.originPoint, spline.endSketchPoint, au,
                           Point3D.create(pts[-1][0] + 2, 1, 0)
                           ).parameter.expression = f"({span_expr}) - ({end_inset_expr})"
    d.addDistanceDimension(sk.originPoint, spline.endSketchPoint, az,
                           Point3D.create(pts[-1][0] + 3, 1, 0)
                           ).parameter.expression = floor_z_expr
    dof.add_dim(4)

    # ── closing waste rail (3 lines), THEN H/V, THEN one depth dim ──
    gL = ev(end_inset_expr)                       # foot inner edge = endpoint u
    rail_z = sh - ev(rail_depth_expr)             # rail base sits below the floor
    L = sk.sketchCurves.sketchLines
    pR = mp(span - gL, rail_z)
    pL2 = mp(gL, rail_z)
    l1 = L.addByTwoPoints(spline.endSketchPoint, Point3D.create(pR.x, pR.y, 0))
    l2 = L.addByTwoPoints(l1.endSketchPoint, Point3D.create(pL2.x, pL2.y, 0))
    l3 = L.addByTwoPoints(l2.endSketchPoint, spline.startSketchPoint)
    dof.add_point(2)                              # pR, pL2 (l3 closes on the spline start)

    gc = sk.geometricConstraints
    for ln in (l1, l2, l3):
        s_ = ln.startSketchPoint.geometry
        e_ = ln.endSketchPoint.geometry
        if abs(e_.x - s_.x) >= abs(e_.y - s_.y):
            gc.addHorizontal(ln)
        else:
            gc.addVertical(ln)
    dof.add_hv(3)

    d.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint, az,
                           Point3D.create(pR.x + 1, pR.y, 0)
                           ).parameter.expression = rail_depth_expr
    dof.add_dim(1)

    dof.assert_balanced()
    refs_to_construction(sk)
    stamp(sk, "base_arch_cut")
    return sk, smallest_profile(sk)
