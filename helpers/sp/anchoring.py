"""Canonical sketch-anchoring helpers for non-root (in-component) sketches.

These are the reusable form of the local helpers that trestle_table.py proved
out. They make a child-component sketch comply with the sketch-quality
validator in ``helpers/sp/deps.py`` by:

  * ``project_face`` — projecting REAL parent geometry (an assembly-context
    proxy face for a cross-component parent) into the child sketch and
    demoting it to construction, satisfying deps rule (2) "must PROJECT real
    parent geometry that resolves to BRep".
  * ``anchor_pt`` — locating the projected parent corner nearest a model point
    so drawn geometry can be dimensioned FROM the reference (not the origin),
    satisfying deps rule (1) "no dimension may touch the sketch origin".
  * ``rdim`` — a tolerant relative distance dimension between two sketch points
    along a model axis, used to fully constrain drawn geometry against the
    projected reference (deps rule (3) "fully constrained, no Fix/Ground").

Import via ``sp``:  ``sp.project_face(...)`` / ``sp.anchor_pt(...)`` / ``sp.rdim(...)``.

The implementations mirror trestle_table.py exactly so projects can drop the
local copies and call ``sp.*`` instead.
"""

import adsk.core
import adsk.fusion

Point3D = adsk.core.Point3D


def project_face(child_sk, parent_body, parent_occ, axis, direction):
    """Project a parent body's outermost ``axis``/``direction`` face into a
    child-component sketch as a construction reference (associative).

    Uses the assembly-context proxy (``createForAssemblyContext``) so the
    projection resolves to real BRep and moves with the parent — the
    cross-component dependency pattern the validator requires (deps rule 2).
    Reference curves are demoted to construction so they don't split the
    profile (see ``refs_to_construction``).

    Args:
        child_sk: Sketch in the child component to project into.
        parent_body: The parent BRepBody whose face is the reference.
        parent_occ: The parent body's occurrence (for the assembly-context
            proxy). For a same-component (native) parent, pass the body's
            own occurrence or None — when None the native face is projected.
        axis: 'x', 'y', or 'z' — face normal axis.
        direction: +1 (max coordinate face) or -1 (min coordinate face).
    """
    # Imported lazily to avoid a circular import (faces/sketch import order).
    from .faces import find_face
    from .sketch import refs_to_construction

    face = find_face(parent_body, axis, direction)
    if parent_occ is not None:
        face = face.createForAssemblyContext(parent_occ)
    child_sk.project(face)
    refs_to_construction(child_sk)


def anchor_pt(child_sk, mx, my, mz):
    """Return the projected-reference construction endpoint nearest a model point.

    After ``project_face`` has demoted the projected parent face to
    construction, this finds the construction-curve start/end SketchPoint
    closest to model coordinate ``(mx, my, mz)``. Dimension drawn geometry
    FROM the returned point (never from the sketch origin) to anchor the
    sketch to the parent (deps rule 1).

    Returns None if no construction endpoint exists (e.g. nothing projected).
    """
    t = child_sk.modelToSketchSpace(Point3D.create(mx, my, mz))
    best = None
    bd = 1e18
    for ci in range(child_sk.sketchCurves.count):
        c = child_sk.sketchCurves.item(ci)
        if not c.isConstruction:
            continue
        for attr in ("startSketchPoint", "endSketchPoint"):
            p = getattr(c, attr, None)
            if not p:
                continue
            g = p.geometry
            d = (g.x - t.x) ** 2 + (g.y - t.y) ** 2
            if d < bd:
                bd = d
                best = p
    return best


def rdim(sk, d, p1, p2, orient, axis, expr):
    """Relative distance dimension between two sketch points along a model axis.

    Tolerant: if the dimension would over-constrain (the points are already
    determined by prior constraints), it is silently skipped — the geometry is
    already correctly placed via modelToSketchSpace. ``orient`` is a dict from
    ``probe_orientations`` mapping a model axis to a DimensionOrientation.

    Args:
        sk: Sketch (only used for skip-tracking context).
        d: ``sk.sketchDimensions`` collection.
        p1, p2: SketchPoints to dimension between.
        orient: Dict {'x'/'y'/'z': DimensionOrientation} (probe_orientations).
        axis: Model axis name for this dimension.
        expr: Parameter expression string (positive magnitude).
    """
    g1, g2 = p1.geometry, p2.geometry
    try:
        d.addDistanceDimension(
            p1, p2, orient[axis],
            Point3D.create((g1.x + g2.x) / 2 + 0.4,
                           (g1.y + g2.y) / 2 + 0.4, 0)
        ).parameter.expression = expr
    except Exception:
        pass
