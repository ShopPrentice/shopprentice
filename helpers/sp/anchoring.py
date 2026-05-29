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


def anchor_pt(child_sk, mx, my, mz,
              include_centers=True, exclude_origin=True, _eps=1e-4):
    """Return the projected-reference construction point nearest a model point.

    After ``project_face`` has demoted the projected parent face to
    construction, this finds the construction point closest to model coordinate
    ``(mx, my, mz)``. Dimension drawn geometry FROM the returned point (never
    from the sketch origin) to anchor the sketch to the parent (deps rule 1).

    Candidate points are each construction curve's ``startSketchPoint`` /
    ``endSketchPoint`` and — when ``include_centers`` is True — its
    ``centerSketchPoint``. The centre is essential for ROUND parents: a
    projected circular/cylindrical face has no start/end vertices, so its only
    usable anchor is the circle/arc centre (e.g. a turned leg's top face).

    When ``exclude_origin`` is True (default) any candidate whose geometry
    coincides with the sketch origin (within ``_eps``) is skipped, so the
    returned anchor never lands on the sketch-origin projection — dimensioning
    to it would re-introduce the very origin reference the validator forbids
    (deps rules 1-2). This removes the manual "don't pick the origin corner"
    burden from callers.

    Returns None if no eligible construction point exists (e.g. nothing
    projected, or every candidate sits on the origin).
    """
    t = child_sk.modelToSketchSpace(Point3D.create(mx, my, mz))
    o = child_sk.originPoint.geometry
    attrs = ("startSketchPoint", "endSketchPoint", "centerSketchPoint") \
        if include_centers else ("startSketchPoint", "endSketchPoint")
    best = None
    bd = 1e18
    for ci in range(child_sk.sketchCurves.count):
        c = child_sk.sketchCurves.item(ci)
        # Projected parent geometry is either demoted to construction
        # (refs_to_construction handles lines) or left as a reference curve
        # (projected circles/arcs are NOT demoted) — both are valid anchors.
        # Drawn geometry is neither, so it is still excluded.
        if not (c.isConstruction or getattr(c, "isReference", False)):
            continue
        for attr in attrs:
            p = getattr(c, attr, None)
            if not p:
                continue
            g = p.geometry
            if exclude_origin and abs(g.x - o.x) < _eps and abs(g.y - o.y) < _eps:
                continue
            d = (g.x - t.x) ** 2 + (g.y - t.y) ** 2
            if d < bd:
                bd = d
                best = p
    return best


def rdim(sk, d, p1, p2, orient, axis, expr):
    """Relative distance dimension between two sketch points along a model axis.

    Tolerant: if the dimension would over-constrain (the points are already
    determined by prior constraints), it is skipped — the geometry is already
    correctly placed via modelToSketchSpace. ``orient`` is a dict from
    ``probe_orientations`` mapping a model axis to a DimensionOrientation.

    A skip is LOGGED (not silent): an over-constrain skip is benign, but a skip
    caused by a real error would otherwise leave the sketch under-constrained
    with no signal — which validate_deps would later flag as a mysterious
    UNDER-CONSTRAINED failure. The log makes the cause traceable.

    Args:
        sk: Sketch (used for the skip log label).
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
    except Exception as e:
        name = getattr(sk, "name", "?")
        print(f"  rdim skip [{name}] axis={axis} expr={expr!r}: {e} "
              f"(geometry placed; dim not added — verify the sketch is fully "
              f"constrained)")


def reanchor(sk, parent_body, parent_occ, face_axis, face_dir, anchor_xyz,
             _eps=1e-3):
    """Retarget every sketch-origin dimension in ``sk`` to a projected parent
    corner — the one-call way to make an ORIGIN-mode sketch pass the validator.

    Build the sketch normally (``sketch_rect_model`` / ``sketch_slot_model`` /
    a joinery template in default/origin mode), then call ``reanchor`` ONCE.
    It removes the whole "anchor derivation" burden: no choosing a non-origin
    corner, no positive-offset arithmetic, no axis bookkeeping. It:

      1. projects ``parent_body``'s ``face_axis``/``face_dir`` face as a
         construction/reference (``project_face``);
      2. finds the projected anchor nearest ``anchor_xyz`` (the sketch origin is
         auto-excluded by ``anchor_pt``);
      3. for every dimension that references the sketch origin, deletes it and
         re-adds an equivalent dimension from the anchor to the SAME vertex with
         offset ``abs(<original expr> - <anchor's expr on that axis>)`` — so the
         sign is handled by Fusion's ``abs()`` and the vertex never moves.

    Because each origin dim is replaced 1-for-1, DOF is preserved: a sketch that
    was fully constrained in origin mode stays fully constrained, now anchored to
    real parent geometry (deps rules 1-3).

    Args:
        sk: The sketch to re-anchor (already built, with origin dims).
        parent_body, parent_occ, face_axis, face_dir: parent reference face
            (as in ``project_face``).
        anchor_xyz: (x, y, z) model expressions (or numbers) of a REAL parent
            corner to anchor to — must not be the sketch-origin projection.

    Returns:
        Number of dimensions retargeted (0 if no anchor point was found).

    Limitation: the anchored vertex itself must not sit on the sketch origin
    (dimensioning it would re-touch the origin). For a part whose own corner is
    at world (0,0), anchor an adjacent corner instead (``sketch_rect_model``'s
    ``anchor=`` with ``size_far``).
    """
    from .sketch import probe_orientations
    from ._util import _make_ev

    ev = _make_ev()
    project_face(sk, parent_body, parent_occ, face_axis, face_dir)
    ax_expr = {"x": anchor_xyz[0], "y": anchor_xyz[1], "z": anchor_xyz[2]}
    av = [ev(c) if isinstance(c, str) else c for c in anchor_xyz]
    anchor = anchor_pt(sk, av[0], av[1], av[2])
    if anchor is None:
        return 0

    op = sk.originPoint
    og = op.geometry

    def _is_origin(e):
        try:
            g = e.geometry
        except Exception:
            return False
        return abs(g.x - og.x) < _eps and abs(g.y - og.y) < _eps

    # Snapshot the origin-referencing dims before mutating the collection.
    targets = []
    for di in range(sk.sketchDimensions.count):
        dim = sk.sketchDimensions.item(di)
        try:
            e1, e2 = dim.entityOne, dim.entityTwo
        except Exception:
            continue
        o1, o2 = _is_origin(e1), _is_origin(e2)
        if o1 == o2:
            continue  # neither, or both (degenerate) — leave alone
        v = e2 if o1 else e1
        try:
            ori = dim.orientation
        except Exception:
            ori = None
        targets.append((dim, v, dim.parameter.expression,
                        dim.parameter.value, ori))

    om = sk.sketchToModelSpace(og)
    n = 0
    for (dim, v, expr, val, ori) in targets:
        vm = sk.sketchToModelSpace(v.geometry)
        orient = probe_orientations(sk, vm.x, vm.y, vm.z)
        axis = None
        if ori is not None:
            axis = next((a for a in ("x", "y", "z") if orient[a] == ori), None)
        if axis is None:  # fallback: match the measured value to an axis delta
            axis = next(
                (a for a in ("x", "y", "z")
                 if abs(abs(getattr(vm, a) - getattr(om, a)) - val) < _eps),
                None)
        if axis is None:
            continue
        dim.deleteMe()
        rdim(sk, sk.sketchDimensions, anchor, v, orient, axis,
             "abs((%s) - (%s))" % (expr, ax_expr[axis]))
        n += 1
    return n
