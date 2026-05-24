import adsk.core
import adsk.fusion
import math


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
    ok, ref_pt = ref_face.evaluator.getPointAtParameter(
        adsk.core.Point2D.create(0.5, 0.5))
    ok2, ref_n = ref_face.evaluator.getNormalAtPoint(ref_pt)
    ref_pos = ref_pt.x * ref_n.x + ref_pt.y * ref_n.y + ref_pt.z * ref_n.z
    target_pos = ref_pos + offset

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
        fn = geom.normal
        dot = fn.x * ref_n.x + fn.y * ref_n.y + fn.z * ref_n.z
        if abs(abs(dot) - 1.0) > 0.01:
            continue
        fp = f.pointOnFace
        face_pos = fp.x * ref_n.x + fp.y * ref_n.y + fp.z * ref_n.z
        if abs(face_pos - target_pos) >= tol:
            continue
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
