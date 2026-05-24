import adsk.core
import adsk.fusion


def mating_bounds(body_a, body_b, normal_axis, tol=0.1):
    """Compute the contact area between two bodies at their shared interface.

    Raises ValueError if bodies are gapped, overlapping, or have no shared
    area — this is a computation, not a validation. The caller needs the
    result to position geometry, so failing early is correct.

    Args:
        body_a, body_b: The two mating bodies.
        normal_axis: 'x', 'y', or 'z' — axis perpendicular to the interface.
        tol: Contact tolerance in cm (default 0.1 = 1mm).

    Returns:
        dict with overlap bounds in model coordinates (cm).
    """
    bb_a = body_a.boundingBox
    bb_b = body_b.boundingBox

    n_a_lo = getattr(bb_a.minPoint, normal_axis)
    n_a_hi = getattr(bb_a.maxPoint, normal_axis)
    n_b_lo = getattr(bb_b.minPoint, normal_axis)
    n_b_hi = getattr(bb_b.maxPoint, normal_axis)

    normal_overlap = min(n_a_hi, n_b_hi) - max(n_a_lo, n_b_lo)

    if normal_overlap < -tol:
        gap = -normal_overlap
        raise ValueError(
            f"mating_bounds: {body_a.name} and {body_b.name} have a "
            f"{gap:.2f} cm gap along {normal_axis} axis — not in contact. "
            f"{body_a.name} {normal_axis}=[{n_a_lo:.2f}, {n_a_hi:.2f}], "
            f"{body_b.name} {normal_axis}=[{n_b_lo:.2f}, {n_b_hi:.2f}].")

    if normal_overlap > tol:
        raise ValueError(
            f"mating_bounds: {body_a.name} and {body_b.name} overlap "
            f"by {normal_overlap:.2f} cm along {normal_axis} axis — "
            f"penetrating. "
            f"{body_a.name} {normal_axis}=[{n_a_lo:.2f}, {n_a_hi:.2f}], "
            f"{body_b.name} {normal_axis}=[{n_b_lo:.2f}, {n_b_hi:.2f}].")

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
                f"{body_b.name} {ax}=[{b_lo:.2f}, {b_hi:.2f}].")

        result[f'{ax}_min'] = lo
        result[f'{ax}_max'] = hi
        result[f'{ax}_center'] = (lo + hi) / 2
        result[f'{ax}_size'] = hi - lo

    return result


def check_domino_exposure(void, body_a, body_b, normal_axis, tol=0.05):
    """Check that a domino void creates blind pockets in both mating pieces.

    Prints warnings if the void extends beyond a body's boundary (exposed
    mortise). Returns a dict with 'ok' bool and any 'warnings' list.
    """
    perp_axes = [ax for ax in ('x', 'y', 'z') if ax != normal_axis]
    vbb = void.boundingBox
    warnings = []

    for body, label in [(body_a, body_a.name), (body_b, body_b.name)]:
        bbb = body.boundingBox
        for ax in perp_axes:
            v_lo = getattr(vbb.minPoint, ax)
            v_hi = getattr(vbb.maxPoint, ax)
            b_lo = getattr(bbb.minPoint, ax)
            b_hi = getattr(bbb.maxPoint, ax)

            if v_lo < b_lo - tol:
                overshoot = b_lo - v_lo
                warnings.append(
                    f"{void.name} exposed in {label} on -{ax.upper()} side: "
                    f"void {ax}={v_lo:.2f} extends {overshoot:.2f} cm "
                    f"beyond {label} {ax}_min={b_lo:.2f}")
            if v_hi > b_hi + tol:
                overshoot = v_hi - b_hi
                warnings.append(
                    f"{void.name} exposed in {label} on +{ax.upper()} side: "
                    f"void {ax}={v_hi:.2f} extends {overshoot:.2f} cm "
                    f"beyond {label} {ax}_max={b_hi:.2f}")

    if warnings:
        for w in warnings:
            print(f"WARNING check_domino_exposure: {w}")

    return {"ok": len(warnings) == 0, "warnings": warnings}


def validate_joint_contact(body_a, body_b, joint_axis=None, tol_cm=0.1):
    """Validate that two bodies have touching/overlapping faces.

    Prints warnings if bodies don't contact. Never raises — the script
    continues and issues are caught by post-phase validate_design.

    Returns:
        Dict with 'ok', 'axis', 'gap_cm', 'perp_overlaps'.
    """
    bb_a = body_a.boundingBox
    bb_b = body_b.boundingBox
    all_axes = ['x', 'y', 'z']

    def _bb_range(bb, ax):
        return (getattr(bb.minPoint, ax), getattr(bb.maxPoint, ax))

    if joint_axis is None:
        best_axis = None
        best_gap = 1e10
        for ax in all_axes:
            a_min, a_max = _bb_range(bb_a, ax)
            b_min, b_max = _bb_range(bb_b, ax)
            overlap = min(a_max, b_max) - max(a_min, b_min)
            if overlap >= -tol_cm:
                continue
            gap = -overlap
            if gap < best_gap:
                best_gap = gap
                best_axis = ax
        if best_axis is None:
            return {"ok": True, "axis": None, "gap_cm": 0.0, "perp_overlaps": {}}
        joint_axis = best_axis

    ok = True
    a_min, a_max = _bb_range(bb_a, joint_axis)
    b_min, b_max = _bb_range(bb_b, joint_axis)

    overlap_along = min(a_max, b_max) - max(a_min, b_min)
    if overlap_along < -tol_cm:
        gap = -overlap_along
        print(
            f"WARNING validate_joint_contact: {body_a.name} and "
            f"{body_b.name} have a {gap:.2f} cm gap along {joint_axis}. "
            f"{body_a.name} {joint_axis}=[{a_min:.2f}, {a_max:.2f}], "
            f"{body_b.name} {joint_axis}=[{b_min:.2f}, {b_max:.2f}].")
        ok = False

    perp_axes = [ax for ax in all_axes if ax != joint_axis]
    perp_overlaps = {}
    for pax in perp_axes:
        pa_min, pa_max = _bb_range(bb_a, pax)
        pb_min, pb_max = _bb_range(bb_b, pax)
        p_overlap = min(pa_max, pb_max) - max(pa_min, pb_min)
        perp_overlaps[pax] = p_overlap
        if p_overlap < -tol_cm:
            print(
                f"WARNING validate_joint_contact: {body_a.name} and "
                f"{body_b.name} don't overlap in {pax} — no shared "
                f"mating area. "
                f"{body_a.name} {pax}=[{pa_min:.2f}, {pa_max:.2f}], "
                f"{body_b.name} {pax}=[{pb_min:.2f}, {pb_max:.2f}].")
            ok = False

    return {
        "ok": ok,
        "axis": joint_axis,
        "gap_cm": max(0, -overlap_along),
        "perp_overlaps": perp_overlaps,
    }
