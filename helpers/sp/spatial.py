import adsk.core
import adsk.fusion


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
