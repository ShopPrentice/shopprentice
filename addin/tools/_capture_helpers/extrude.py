"""Extrude feature capture and inference helpers."""

import adsk.core
import adsk.fusion

from ._common import _roll_to_feature


def _capture_extrude(ext, idx, tl, design=None):
    """Capture an ExtrudeFeature."""
    info = {"type": "Extrude", "name": ext.name}

    op_map = {
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation: "NewBody",
        adsk.fusion.FeatureOperations.CutFeatureOperation: "Cut",
        adsk.fusion.FeatureOperations.JoinFeatureOperation: "Join",
        adsk.fusion.FeatureOperations.IntersectFeatureOperation: "Intersect",
    }
    info["operation"] = op_map.get(ext.operation, str(ext.operation))

    # Extent type and distance
    try:
        extent = ext.extentOne
        if isinstance(extent, adsk.fusion.DistanceExtentDefinition):
            info["extentType"] = "Distance"
            info["distance"] = extent.distance.expression
        elif isinstance(extent, adsk.fusion.SymmetricExtentDefinition):
            info["extentType"] = "Symmetric"
            info["distance"] = extent.distance.expression
        else:
            info["extentType"] = type(extent).__name__
    except:
        pass

    # Check for symmetric
    try:
        if ext.extentType == adsk.fusion.FeatureExtentTypes.SymmetricFeatureExtentType:
            info["extentType"] = "Symmetric"
            sym_ext = adsk.fusion.SymmetricExtentDefinition.cast(ext.extentOne)
            if sym_ext:
                info["distance"] = sym_ext.distance.expression
    except:
        pass

    # Taper angle
    try:
        ta = ext.taperAngleOne
        if ta:
            info["taperAngle"] = ta.expression
    except:
        pass

    # Two-sided extent
    try:
        if ext.extentType == adsk.fusion.FeatureExtentTypes.TwoSidesFeatureExtentType:
            info["hasTwoExtents"] = True
            ext2 = ext.extentTwo
            if isinstance(ext2, adsk.fusion.DistanceExtentDefinition):
                info["extentTwoType"] = "Distance"
                info["distanceTwo"] = ext2.distance.expression
            else:
                info["extentTwoType"] = type(ext2).__name__
            try:
                ta2 = ext.taperAngleTwo
                if ta2:
                    info["taperAngleTwo"] = ta2.expression
            except:
                pass
    except:
        pass

    # Direction flipped
    try:
        info["isDirectionFlipped"] = ext.isDirectionFlipped
    except:
        pass

    # Sketch — multi-strategy capture (only when timeline context is available)
    if idx is not None and tl is not None:
        sk_found = _find_sketch_for_extrude(ext, idx, tl, info)
    else:
        sk_found = _find_sketch_for_extrude_no_timeline(ext, info)

    if sk_found:
        info["sketch"] = sk_found.name
        try:
            info["sketchComponent"] = sk_found.parentComponent.name
        except:
            pass
        # Profile index matching
        _match_profile_index(ext, sk_found, info)
    elif "sketchError" not in info and info.get("profileType") not in ("BRepFace", "Inaccessible"):
        info["sketchError"] = "no sketch found (all strategies failed)"

    body_names = [b.name for b in ext.bodies]

    # Try rollTo(False) to capture user-renamed body names.  At end-of-
    # timeline a consumed body's ext.bodies may be empty or stale; rolling
    # to just AFTER the feature shows the body alive with its current name.
    # NOTE: _roll_to_feature uses rollTo(True) (before), we need (False) (after).
    if design and ext.operation == adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
        try:
            tl = design.timeline
            ext.timelineObject.rollTo(False)  # roll to just after this feature
            try:
                rolled = [b.name for b in ext.bodies]
                if rolled:
                    body_names = rolled
            finally:
                tl.moveToEnd()
        except:
            pass

    # If bodies list is still empty (consumed by downstream combine/join),
    # infer the body name by scanning downstream Combine features.
    if not body_names and design and ext.operation == adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
        if idx is not None and tl is not None:
            body_names = _infer_extrude_body_name(ext, idx, tl, design)

    info["bodies"] = body_names

    def _try_participants():
        try:
            pb = ext.participantBodies
            if pb and pb.count > 0:
                info["participantBodies"] = [pb.item(i).name for i in range(pb.count)]
        except:
            pass

    _try_participants()
    if "participantBodies" not in info and design:
        try:
            with _roll_to_feature(ext, design):
                _try_participants()
        except:
            pass

    # Fallback: infer participantBodies by comparing body volumes before/after
    # the extrude. The body whose volume changed is the actual JOIN/CUT target.
    if "participantBodies" not in info and info.get("operation") in ("Join", "Cut") and design:
        try:
            tl = design.timeline
            tlo = ext.timelineObject
            idx = tlo.index
            comp = ext.parentComponent

            # Volumes BEFORE the extrude
            tl.markerPosition = idx
            before = {}
            for i in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(i)
                before[b.name] = round(b.volume, 4)

            # Volumes AFTER the extrude
            tl.markerPosition = idx + 1
            after = {}
            for i in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(i)
                after[b.name] = round(b.volume, 4)

            tl.moveToEnd()

            # Bodies whose volume changed = participants
            changed = [n for n in before if n in after and before[n] != after[n]]
            if changed:
                info["participantBodies"] = changed
        except:
            try:
                design.timeline.moveToEnd()
            except:
                pass

    try:
        if ext.startFaces and ext.startFaces.count > 0:
            info["startFace"] = True
    except:
        pass

    return info


def _infer_extrude_body_name(ext, idx, tl, design):
    """Infer body name for an extrude whose body was consumed by a downstream combine.

    Walks forward in the timeline looking for CombineFeatures that reference
    a toolBody created by this extrude. Uses rollTo on the combine to access
    its toolBodies (which preserves the original body name).
    """
    try:
        ext_comp = ext.parentComponent
    except:
        return []

    for fwd in range(idx + 1, min(idx + 15, tl.count)):
        try:
            fwd_entity = tl.item(fwd).entity
        except:
            continue
        if fwd_entity is None:
            continue
        comb = adsk.fusion.CombineFeature.cast(fwd_entity)
        if not comb:
            continue
        try:
            if comb.parentComponent != ext_comp:
                continue
        except:
            continue
        # Try to get toolBodies via rollTo
        try:
            with _roll_to_feature(comb, design):
                tools = comb.toolBodies
                for ti in range(tools.count):
                    t = tools.item(ti)
                    # The tool body name is the one we're looking for
                    return [t.name]
        except:
            # Direct access fallback
            try:
                tools = comb.toolBodies
                for ti in range(tools.count):
                    return [tools.item(ti).name]
            except:
                pass
    return []


def _find_sketch_for_extrude(ext, idx, tl, info):
    """Multi-strategy sketch finding for an extrude feature (with timeline)."""
    sk_found = _find_sketch_from_profile(ext, info)

    # Strategy: walk timeline backwards (skip for face-based profiles only).
    # Inaccessible profiles still need sketch name — the variant search
    # system will try all profile indices at build time.
    if not sk_found and info.get("profileType") != "BRepFace":
        try:
            for back_idx in range(idx - 1, -1, -1):
                back_item = tl.item(back_idx)
                try:
                    back_entity = back_item.entity
                except RuntimeError:
                    continue
                if back_entity is None:
                    continue
                back_sk = adsk.fusion.Sketch.cast(back_entity)
                if back_sk:
                    try:
                        sk_comp = back_sk.parentComponent
                        ext_comp = ext.parentComponent
                        if sk_comp == ext_comp or sk_comp == ext_comp.parentDesign.rootComponent:
                            sk_found = back_sk
                            break
                    except:
                        sk_found = back_sk
                        break
        except Exception as e:
            if "sketchError" not in info:
                info["sketchError"] = f"timeline walk: {e}"

    return sk_found


def _find_sketch_for_extrude_no_timeline(ext, info):
    """Sketch finding for an extrude feature without timeline context."""
    return _find_sketch_from_profile(ext, info)


def _find_sketch_from_profile(ext, info):
    """Extract sketch from extrude's profile (shared by both timeline and no-timeline paths)."""
    sk_found = None
    try:
        profile = ext.profile
        profiles_coll = adsk.core.ObjectCollection.cast(profile)
        if profiles_coll:
            for pi in range(profiles_coll.count):
                p = profiles_coll.item(pi)
                try:
                    sk_found = adsk.fusion.Profile.cast(p).parentSketch
                except:
                    pass
                if not sk_found:
                    try:
                        sk_found = p.parentSketch
                    except:
                        pass
                if sk_found:
                    break
            # If no sketch found, check if profile items are BRepFaces
            if not sk_found:
                try:
                    f0 = adsk.fusion.BRepFace.cast(profiles_coll.item(0))
                    if f0:
                        info["profileType"] = "BRepFace"
                        return None
                except:
                    pass
        else:
            try:
                p = adsk.fusion.Profile.cast(profile)
                if p:
                    sk_found = p.parentSketch
            except:
                pass
            if not sk_found:
                try:
                    sk_found = profile.parentSketch
                except:
                    pass
            # Check BRepFace
            if not sk_found:
                try:
                    face = adsk.fusion.BRepFace.cast(profile)
                    if face:
                        info["profileType"] = "BRepFace"
                        return None
                except:
                    pass
    except Exception as e:
        # InternalValidationError at end-of-timeline often means a face-based
        # extrude whose profile can't be read.  Mark it so timeline walk-back
        # doesn't incorrectly assign a sketch.
        if "InternalValidationError" in str(e):
            info["profileType"] = "Inaccessible"
        info["sketchError"] = f"profile access: {e}"

    return sk_found


def _match_profile_index(ext, sk_found, info):
    """Match extrude profile bounding box to sketch profiles."""
    try:
        profile = ext.profile
        profiles_coll = adsk.core.ObjectCollection.cast(profile)
        # Collect ALL profiles the extrude uses
        ext_profs = []
        if profiles_coll:
            for i in range(profiles_coll.count):
                p = adsk.fusion.Profile.cast(profiles_coll.item(i))
                if p:
                    ext_profs.append(p)
        else:
            p = adsk.fusion.Profile.cast(profile)
            if p:
                ext_profs.append(p)

        if ext_profs:
            info["profileCount"] = sk_found.profiles.count
            matched_indices = []
            for ext_prof in ext_profs:
                ext_bb = ext_prof.boundingBox
                ext_min = (round(ext_bb.minPoint.x, 3), round(ext_bb.minPoint.y, 3))
                ext_max = (round(ext_bb.maxPoint.x, 3), round(ext_bb.maxPoint.y, 3))
                best_idx = 0
                best_dist = float('inf')
                for pi in range(sk_found.profiles.count):
                    sp = sk_found.profiles.item(pi)
                    sp_bb = sp.boundingBox
                    sp_min = (round(sp_bb.minPoint.x, 3), round(sp_bb.minPoint.y, 3))
                    sp_max = (round(sp_bb.maxPoint.x, 3), round(sp_bb.maxPoint.y, 3))
                    dist = (abs(sp_min[0] - ext_min[0]) + abs(sp_min[1] - ext_min[1])
                            + abs(sp_max[0] - ext_max[0]) + abs(sp_max[1] - ext_max[1]))
                    if dist < best_dist:
                        best_dist = dist
                        best_idx = pi
                matched_indices.append(best_idx)
            # Single profile → profileIndex (int), multi → profileIndices (list)
            if len(matched_indices) == 1:
                info["profileIndex"] = matched_indices[0]
            else:
                info["profileIndices"] = matched_indices
                info["profileIndex"] = matched_indices[0]  # backward compat
    except:
        pass

