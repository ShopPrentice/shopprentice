"""Rectangular pattern capture."""

import adsk.core
import adsk.fusion

from ._common import _roll_to_feature


def _extract_linear_direction(entity):
    """Extract a normalised direction vector from any linear entity.

    Handles BRepEdge (Line3D geometry), SketchLine, BRepFace (plane normal),
    and ConstructionPlane (normal).  Returns [x, y, z] rounded to 6 decimals,
    or None if the entity type is unrecognised.
    """
    # BRepEdge — Line3D has startPoint/endPoint, NOT .direction
    try:
        edge = adsk.fusion.BRepEdge.cast(entity)
        if edge:
            line = adsk.core.Line3D.cast(edge.geometry)
            if line:
                s, e = line.startPoint, line.endPoint
                dx, dy, dz = e.x - s.x, e.y - s.y, e.z - s.z
                ln = (dx**2 + dy**2 + dz**2) ** 0.5
                if ln > 1e-6:
                    return [round(dx/ln, 6), round(dy/ln, 6), round(dz/ln, 6)]
    except:
        pass
    # SketchLine
    try:
        sl = adsk.fusion.SketchLine.cast(entity)
        if sl:
            s = sl.startSketchPoint.worldGeometry
            e = sl.endSketchPoint.worldGeometry
            dx, dy, dz = e.x - s.x, e.y - s.y, e.z - s.z
            ln = (dx**2 + dy**2 + dz**2) ** 0.5
            if ln > 1e-6:
                return [round(dx/ln, 6), round(dy/ln, 6), round(dz/ln, 6)]
    except:
        pass
    # BRepFace — use plane normal as direction
    try:
        face = adsk.fusion.BRepFace.cast(entity)
        if face:
            plane = adsk.core.Plane.cast(face.geometry)
            if plane:
                n = plane.normal
                return [round(n.x, 6), round(n.y, 6), round(n.z, 6)]
    except:
        pass
    # ConstructionPlane — use normal
    try:
        cp = adsk.fusion.ConstructionPlane.cast(entity)
        if cp:
            n = cp.geometry.normal
            return [round(n.x, 6), round(n.y, 6), round(n.z, 6)]
    except:
        pass
    return None


def _capture_rectangular_pattern(pat, design=None):
    """Capture a RectangularPatternFeature."""
    info = {"type": "RectangularPattern", "name": pat.name}

    try:
        info["quantityOne"] = pat.quantityOne.expression
        info["distanceOne"] = pat.distanceOne.expression
    except:
        pass

    try:
        q2 = pat.quantityTwo
        if q2:
            info["quantityTwo"] = q2.expression
    except:
        pass

    try:
        d2 = pat.distanceTwo
        if d2:
            info["distanceTwo"] = d2.expression
    except:
        pass

    try:
        axis = pat.directionOneEntity
        ca = adsk.fusion.ConstructionAxis.cast(axis)
        if ca:
            info["axisOne"] = ca.name
        # Don't set directionOne from entity — its natural direction may not
        # match the pattern's actual direction. Sign comes from body positions.
    except:
        pass

    # Direction two (if present)
    try:
        axis2 = pat.directionTwoEntity
        if axis2:
            ca2 = adsk.fusion.ConstructionAxis.cast(axis2)
            if ca2:
                info["axisTwo"] = ca2.name
                try:
                    line = ca2.geometry
                    info["directionTwo"] = [round(line.direction.x, 6),
                                            round(line.direction.y, 6),
                                            round(line.direction.z, 6)]
                except:
                    pass
            else:
                d2 = _extract_linear_direction(axis2)
                if d2:
                    info["directionTwo"] = d2
    except:
        pass

    try:
        if pat.patternDistanceType == adsk.fusion.PatternDistanceType.SpacingPatternDistanceType:
            info["distanceType"] = "Spacing"
        elif pat.patternDistanceType == adsk.fusion.PatternDistanceType.ExtentPatternDistanceType:
            info["distanceType"] = "Extent"
    except:
        pass

    # Input entities — may need rollTo for BRep-dependent access
    def _try_inputs():
        try:
            inputs = pat.inputEntities
            input_names = []
            for ii in range(inputs.count):
                e = inputs.item(ii)
                if hasattr(e, 'name'):
                    input_names.append(e.name)
            if input_names:
                info["inputs"] = input_names
        except:
            pass

    def _try_bodies_and_direction():
        """Capture bodies and infer direction inside rollTo.

        Must be called inside rollTo so pat.bodies returns ALL copies
        (at end-of-timeline, downstream Combines may consume pattern bodies).
        Also infers direction from body positions inside rollTo where copies
        are guaranteed to exist.
        """
        body_names = [pat.bodies.item(i).name for i in range(pat.bodies.count)]
        if body_names:
            info["bodies"] = body_names

        # Infer direction from the directionOneEntity geometry.
        # pat.bodies only returns 1 body (the input) — copies are invisible
        # both in pat.bodies and comp.bRepBodies during rollTo.
        # The axis entity (edge or construction axis) gives direction.
        if "directionOne" not in info:
            try:
                axis = pat.directionOneEntity
                direction = None
                ca = adsk.fusion.ConstructionAxis.cast(axis)
                if ca:
                    line = ca.geometry
                    direction = [line.direction.x, line.direction.y, line.direction.z]
                else:
                    edge = adsk.fusion.BRepEdge.cast(axis)
                    if edge:
                        sp = edge.startVertex.geometry
                        ep = edge.endVertex.geometry
                        direction = [ep.x - sp.x, ep.y - sp.y, ep.z - sp.z]
                if direction:
                    adx = abs(direction[0])
                    ady = abs(direction[1])
                    adz = abs(direction[2])
                    if adx >= ady and adx >= adz and adx > 0.001:
                        info["directionOne"] = [1.0 if direction[0] > 0 else -1.0, 0.0, 0.0]
                    elif ady >= adx and ady >= adz and ady > 0.001:
                        info["directionOne"] = [0.0, 1.0 if direction[1] > 0 else -1.0, 0.0]
                    elif adz > 0.001:
                        info["directionOne"] = [0.0, 0.0, 1.0 if direction[2] > 0 else -1.0]
            except:
                pass

    def _try_direction_entity():
        """Try to read directionOneEntity inside rollTo.

        Only captures axis NAME (for identification), NOT the direction vector.
        The entity's natural direction may not match the pattern's actual direction
        (e.g., pattern may use -X on the xConstructionAxis). Direction sign is
        always inferred from body positions at end-of-timeline.
        """
        if "axisOne" in info:
            return  # Already captured
        try:
            axis = pat.directionOneEntity
            ca = adsk.fusion.ConstructionAxis.cast(axis)
            if ca:
                info["axisOne"] = ca.name
        except:
            pass

    if design:
        try:
            with _roll_to_feature(pat, design):
                _try_inputs()
                _try_bodies_and_direction()
                _try_direction_entity()
        except:
            _try_inputs()
            _try_bodies_and_direction()
    else:
        _try_inputs()
        _try_bodies_and_direction()

    # Fallback: if bodies weren't captured inside rollTo
    if "bodies" not in info:
        info["bodies"] = [b.name for b in pat.bodies]

    # Transform rollTo direction from component-local to world space
    if "directionOne" in info and design:
        try:
            comp = pat.parentComponent
            root = design.rootComponent
            if comp != root:
                for occ in root.allOccurrences:
                    if occ.component == comp:
                        xf = occ.transform
                        dir_vec = adsk.core.Vector3D.create(
                            info["directionOne"][0],
                            info["directionOne"][1],
                            info["directionOne"][2])
                        dir_vec.transformBy(xf)
                        d = [dir_vec.x, dir_vec.y, dir_vec.z]
                        ad = [abs(d[0]), abs(d[1]), abs(d[2])]
                        if ad[0] >= ad[1] and ad[0] >= ad[2] and ad[0] > 0.001:
                            info["directionOne"] = [1.0 if d[0] > 0 else -1.0, 0.0, 0.0]
                        elif ad[1] >= ad[0] and ad[1] >= ad[2] and ad[1] > 0.001:
                            info["directionOne"] = [0.0, 1.0 if d[1] > 0 else -1.0, 0.0]
                        elif ad[2] > 0.001:
                            info["directionOne"] = [0.0, 0.0, 1.0 if d[2] > 0 else -1.0]
                        break
        except:
            pass

    # Pattern copy detection: scan component bodies at END-OF-TIMELINE.
    # rollTo(True) doesn't make pattern copies visible in comp.bRepBodies
    # (Fusion API quirk), but they ARE visible at end-of-timeline.
    try:
        comp = pat.parentComponent
        # Use body names (from "bodies") for seed identification.
        # "inputs" contains feature names (e.g. "Extrude2") which don't match
        # body names (e.g. "Body1"), so they can't be used for body lookup.
        seed_body_names = info.get("bodies", [])
        # Find seed body: first body matching bodies[0] in the component.
        # Store index because Fusion API proxy objects are new wrappers each
        # call — `is` comparison fails even for the same underlying entity.
        seed_idx = -1
        seed_min = None
        ref_vol = None
        if seed_body_names:
            for bi in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(bi)
                if b.name == seed_body_names[0]:
                    seed_idx = bi
                    ref_vol = b.volume
                    seed_min = [round(b.boundingBox.minPoint.x, 4),
                                round(b.boundingBox.minPoint.y, 4),
                                round(b.boundingBox.minPoint.z, 4)]
                    break
        # Fallback: use first body's volume as reference
        if ref_vol is None:
            for bi in range(comp.bRepBodies.count):
                ref_vol = comp.bRepBodies.item(bi).volume
                break
        # Find copies: same volume as seed (within 5% tolerance), exclude seed
        if ref_vol and ref_vol > 0:
            copies = []
            for bi in range(comp.bRepBodies.count):
                if bi == seed_idx:
                    continue
                b = comp.bRepBodies.item(bi)
                if abs(b.volume - ref_vol) / ref_vol < 0.05:
                    copies.append({
                        "name": b.name,
                        "min": [round(b.boundingBox.minPoint.x, 4),
                                round(b.boundingBox.minPoint.y, 4),
                                round(b.boundingBox.minPoint.z, 4)],
                    })
            if copies:
                # Infer direction from seed body → nearest copy at end-of-timeline.
                # Only used as FALLBACK when directionOneEntity wasn't readable.
                # Body positions are in component-local space, which may differ
                # from world space if the occurrence has rotation.
                if seed_min:
                    nearest = min(copies, key=lambda c:
                        sum(abs(a - b) for a, b in zip(c["min"], seed_min)))
                    dx = nearest["min"][0] - seed_min[0]
                    dy = nearest["min"][1] - seed_min[1]
                    dz = nearest["min"][2] - seed_min[2]
                    adx, ady, adz = abs(dx), abs(dy), abs(dz)
                    if adx >= ady and adx >= adz and adx > 0.001:
                        info["directionOne"] = [1.0 if dx > 0 else -1.0, 0.0, 0.0]
                    elif ady >= adx and ady >= adz and ady > 0.001:
                        info["directionOne"] = [0.0, 1.0 if dy > 0 else -1.0, 0.0]
                    elif adz > 0.001:
                        info["directionOne"] = [0.0, 0.0, 1.0 if dz > 0 else -1.0]

                # Transform direction from component-local to world space.
                # comp.bRepBodies gives positions in the component's local
                # coordinate system. If the occurrence has a rotation, the
                # local direction differs from world direction.
                if "directionOne" in info and design:
                    try:
                        root = design.rootComponent
                        if comp != root:
                            for occ in root.allOccurrences:
                                if occ.component == comp:
                                    xf = occ.transform
                                    dir_vec = adsk.core.Vector3D.create(
                                        info["directionOne"][0],
                                        info["directionOne"][1],
                                        info["directionOne"][2])
                                    dir_vec.transformBy(xf)
                                    d = [dir_vec.x, dir_vec.y, dir_vec.z]
                                    adx2, ady2, adz2 = abs(d[0]), abs(d[1]), abs(d[2])
                                    if adx2 >= ady2 and adx2 >= adz2 and adx2 > 0.001:
                                        info["directionOne"] = [1.0 if d[0] > 0 else -1.0, 0.0, 0.0]
                                    elif ady2 >= adx2 and ady2 >= adz2 and ady2 > 0.001:
                                        info["directionOne"] = [0.0, 1.0 if d[1] > 0 else -1.0, 0.0]
                                    elif adz2 > 0.001:
                                        info["directionOne"] = [0.0, 0.0, 1.0 if d[2] > 0 else -1.0]
                                    break
                    except:
                        pass

                # Sort by position along pattern axis for stable ordering
                d = info.get("directionOne", [1, 0, 0])
                ax = 0 if abs(d[0]) >= abs(d[1]) and abs(d[0]) >= abs(d[2]) else (
                     1 if abs(d[1]) >= abs(d[2]) else 2)
                copies.sort(key=lambda c: c["min"][ax])
                info["patternCopies"] = [c["name"] for c in copies]
    except Exception as e:
        import traceback
        app = adsk.core.Application.get()
        app.log(f"Pattern copy detection error: {e}\n{traceback.format_exc()}")

    return info

