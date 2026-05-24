"""Mirror, Move, Chamfer, Fillet, Sweep, SplitBody, and Remove capture."""

import adsk.core
import adsk.fusion

from ._common import _roll_to_feature
from .body import _capture_edge_vertices


def _capture_mirror(mir, design=None):
    """Capture a MirrorFeature."""
    info = {"type": "Mirror", "name": mir.name}

    try:
        mp = mir.mirrorPlane
        bcp = adsk.fusion.ConstructionPlane.cast(mp)
        if bcp:
            info["mirrorPlane"] = {"type": "ConstructionPlane", "name": bcp.name}
            try:
                geom = bcp.geometry
                info["mirrorPlane"]["normal"] = [round(geom.normal.x, 6), round(geom.normal.y, 6), round(geom.normal.z, 6)]
                info["mirrorPlane"]["origin"] = [round(geom.origin.x, 4), round(geom.origin.y, 4), round(geom.origin.z, 4)]
            except:
                pass
        else:
            bf = adsk.fusion.BRepFace.cast(mp)
            if bf:
                info["mirrorPlane"] = {"type": "BRepFace", "body": bf.body.name}
                try:
                    eva = bf.evaluator
                    ok, pt, norm = eva.getNormalAtPoint(bf.pointOnFace)
                    if ok:
                        info["mirrorPlane"]["normal"] = [round(norm.x, 6), round(norm.y, 6), round(norm.z, 6)]
                        info["mirrorPlane"]["origin"] = [round(bf.pointOnFace.x, 4), round(bf.pointOnFace.y, 4), round(bf.pointOnFace.z, 4)]
                except:
                    pass
    except:
        pass

    # Input entities — need rollTo for BRep-dependent access
    def _try_inputs():
        try:
            inputs = mir.inputEntities
            input_names = []
            for ii in range(inputs.count):
                e = inputs.item(ii)
                if hasattr(e, 'name'):
                    input_names.append(e.name)
            if input_names:
                info["inputBodies"] = input_names
        except:
            pass

    if design:
        try:
            with _roll_to_feature(mir, design):
                _try_inputs()
        except:
            _try_inputs()
    else:
        _try_inputs()

    # Output bodies — try direct access first, rollTo if consumed downstream
    out = [b.name for b in mir.bodies]
    if not out and design:
        try:
            mir.timelineObject.rollTo(False)
            try:
                out = [b.name for b in mir.bodies]
            finally:
                design.timeline.moveToEnd()
        except:
            pass
    info["bodies"] = out

    try:
        if mir.patternComputeOption == adsk.fusion.PatternComputeOptions.IdenticalPatternCompute:
            info["computeOption"] = "Identical"
        elif mir.patternComputeOption == adsk.fusion.PatternComputeOptions.OptimizedPatternCompute:
            info["computeOption"] = "Optimized"
        elif mir.patternComputeOption == adsk.fusion.PatternComputeOptions.AdjustPatternCompute:
            info["computeOption"] = "Adjust"
    except:
        pass

    return info


def _capture_move(mv, design=None):
    """Capture a MoveFeature."""
    info = {"type": "Move", "name": mv.name}

    try:
        transform = mv.transform
        info["matrix"] = [
            [round(transform.getCell(r, c), 12) for c in range(4)]
            for r in range(4)
        ]
        info["translation"] = [
            round(transform.translation.x, 4),
            round(transform.translation.y, 4),
            round(transform.translation.z, 4),
        ]
    except:
        pass

    def _try_inputs():
        try:
            inputs = mv.inputEntities
            input_names = []
            for ii in range(inputs.count):
                e = inputs.item(ii)
                if hasattr(e, 'name'):
                    input_names.append(e.name)
            if input_names:
                info["inputs"] = input_names
        except:
            pass

    if design:
        try:
            with _roll_to_feature(mv, design):
                _try_inputs()
        except:
            _try_inputs()
    else:
        _try_inputs()

    return info


def _capture_chamfer(chamfer, design=None):
    """Capture a ChamferFeature with edge vertex positions."""
    info = {"type": "Chamfer", "name": chamfer.name}

    try:
        chamfer_type = chamfer.chamferType
        type_map = {
            adsk.fusion.ChamferTypes.EqualDistanceChamferType: "EqualDistance",
            adsk.fusion.ChamferTypes.TwoDistancesChamferType: "TwoDistances",
            adsk.fusion.ChamferTypes.DistanceAndAngleChamferType: "DistanceAndAngle",
        }
        info["chamferType"] = type_map.get(chamfer_type, str(chamfer_type))
    except:
        pass

    def _capture_edge_sets():
        try:
            edge_sets = chamfer.edgeSets
            sets_info = []
            total_edges = 0
            for si in range(edge_sets.count):
                es = edge_sets.item(si)
                set_entry = {}
                edges = _capture_edge_vertices(es.edges)
                set_entry["edges"] = edges
                total_edges += len(edges)

                # Detect edge set type and capture parameters
                eq = adsk.fusion.EqualDistanceChamferEdgeSet.cast(es)
                if eq:
                    set_entry["chamferType"] = "EqualDistance"
                    set_entry["distance"] = eq.distance.expression
                    info["distance"] = eq.distance.expression
                else:
                    two = adsk.fusion.TwoDistancesChamferEdgeSet.cast(es)
                    if two:
                        set_entry["chamferType"] = "TwoDistances"
                        set_entry["distanceOne"] = two.distanceOne.expression
                        set_entry["distanceTwo"] = two.distanceTwo.expression
                    else:
                        da = adsk.fusion.DistanceAndAngleChamferEdgeSet.cast(es)
                        if da:
                            set_entry["chamferType"] = "DistanceAndAngle"
                            set_entry["distance"] = da.distance.expression
                            set_entry["angle"] = da.angle.expression
                        else:
                            # Fallback: try generic distance property
                            try:
                                set_entry["distance"] = es.distance.expression
                            except:
                                pass

                sets_info.append(set_entry)
            info["edgeSets"] = sets_info
            info["edgeCount"] = total_edges
        except:
            pass

    # Edge sets need rollTo (BRep-dependent)
    if design:
        try:
            with _roll_to_feature(chamfer, design):
                _capture_edge_sets()
        except:
            _capture_edge_sets()
    else:
        _capture_edge_sets()

    info["bodies"] = [b.name for b in chamfer.bodies]

    return info


def _capture_fillet(fillet, design=None):
    """Capture a FilletFeature with edge vertex positions."""
    info = {"type": "Fillet", "name": fillet.name}

    def _capture_edge_sets():
        try:
            edge_sets = fillet.edgeSets
            sets_info = []
            total_edges = 0
            for si in range(edge_sets.count):
                es = edge_sets.item(si)
                set_entry = {
                    "radius": es.radius.expression,
                    "edges": _capture_edge_vertices(es.edges),
                }
                total_edges += len(set_entry["edges"])
                sets_info.append(set_entry)
            info["edgeSets"] = sets_info
            info["radii"] = [s["radius"] for s in sets_info]
            info["edgeCount"] = total_edges
        except:
            pass

    # Edge sets need rollTo (BRep-dependent)
    if design:
        try:
            with _roll_to_feature(fillet, design):
                _capture_edge_sets()
        except:
            _capture_edge_sets()
    else:
        _capture_edge_sets()

    info["bodies"] = [b.name for b in fillet.bodies]

    return info


def _capture_sweep(sweep, design):
    """Capture a SweepFeature with profile, path, and extent details."""
    info = {"type": "Sweep", "name": sweep.name}

    op_map = {
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation: "NewBody",
        adsk.fusion.FeatureOperations.CutFeatureOperation: "Cut",
        adsk.fusion.FeatureOperations.JoinFeatureOperation: "Join",
        adsk.fusion.FeatureOperations.IntersectFeatureOperation: "Intersect",
    }
    info["operation"] = op_map.get(sweep.operation, str(sweep.operation))

    # Orientation
    orient_map = {
        adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType: "Perpendicular",
        adsk.fusion.SweepOrientationTypes.ParallelOrientationType: "Parallel",
    }
    try:
        info["orientation"] = orient_map.get(sweep.orientation, str(sweep.orientation))
    except:
        pass

    # Taper / twist / direction (accessible without rollTo)
    try:
        if sweep.taperAngle:
            info["taperAngle"] = sweep.taperAngle.expression
    except:
        pass

    try:
        if sweep.twistAngle:
            info["twistAngle"] = sweep.twistAngle.expression
    except:
        pass

    try:
        info["isDirectionFlipped"] = sweep.isDirectionFlipped
    except:
        pass

    # BRep-dependent properties need rollTo (including distances)
    try:
        with _roll_to_feature(sweep, design):
            # Profile → sketch name + profile index
            # profile can be a single Profile or an ObjectCollection of Profiles
            try:
                profile = sweep.profile
                p = adsk.fusion.Profile.cast(profile)
                if not p:
                    coll = adsk.core.ObjectCollection.cast(profile)
                    if coll and coll.count > 0:
                        info["profileCollectionCount"] = coll.count
                        # Capture all profile indices
                        first_p = adsk.fusion.Profile.cast(coll.item(0))
                        if first_p:
                            sk = first_p.parentSketch
                            info["sketch"] = sk.name
                            indices = []
                            for pi in range(coll.count):
                                cp = adsk.fusion.Profile.cast(coll.item(pi))
                                if cp:
                                    idx = _match_profile_index_from_profile(cp, sk, info)
                                    if idx is not None:
                                        indices.append(idx)
                            if indices:
                                info["profileIndices"] = indices
                                # Store profile bounding box dims for runtime matching
                                pdims = []
                                for pi2 in range(coll.count):
                                    cp2 = adsk.fusion.Profile.cast(coll.item(pi2))
                                    if cp2:
                                        try:
                                            bb = cp2.boundingBox
                                            pdims.append([
                                                round(bb.maxPoint.x - bb.minPoint.x, 4),
                                                round(bb.maxPoint.y - bb.minPoint.y, 4),
                                            ])
                                        except:
                                            pass
                                if pdims:
                                    info["profileDims"] = pdims
                        p = None  # already handled
                if p:
                    sk = p.parentSketch
                    info["sketch"] = sk.name
                    _match_profile_index_from_profile(p, sk, info)
                    try:
                        bb = p.boundingBox
                        info["profileDims"] = [[
                            round(bb.maxPoint.x - bb.minPoint.x, 4),
                            round(bb.maxPoint.y - bb.minPoint.y, 4),
                        ]]
                    except:
                        pass
            except Exception as e:
                info["profileError"] = str(e)

            # Path
            try:
                path = sweep.path
                path_entities = []
                for pi in range(path.count):
                    pe = path.item(pi)
                    pe_info = {"isOpposedToEntity": pe.isOpposedToEntity}
                    curve = pe.entity
                    sk_curve = adsk.fusion.SketchCurve.cast(curve)
                    if sk_curve:
                        pe_info["source"] = "SketchCurve"
                        pe_info["parentSketch"] = sk_curve.parentSketch.name
                        pe_info["curveType"] = type(sk_curve).__name__
                        # Capture geometry for lines/arcs
                        line = adsk.fusion.SketchLine.cast(sk_curve)
                        if line:
                            pe_info["start"] = [round(line.startSketchPoint.geometry.x, 4),
                                                round(line.startSketchPoint.geometry.y, 4)]
                            pe_info["end"] = [round(line.endSketchPoint.geometry.x, 4),
                                              round(line.endSketchPoint.geometry.y, 4)]
                        arc = adsk.fusion.SketchArc.cast(sk_curve)
                        if arc:
                            pe_info["center"] = [round(arc.centerSketchPoint.geometry.x, 4),
                                                 round(arc.centerSketchPoint.geometry.y, 4)]
                            pe_info["radius"] = round(arc.radius, 4)
                    else:
                        edge = adsk.fusion.BRepEdge.cast(curve)
                        if edge:
                            pe_info["source"] = "BRepEdge"
                            try:
                                pe_info["body"] = edge.body.name
                            except:
                                pass
                            try:
                                sv = edge.startVertex.geometry
                                ev = edge.endVertex.geometry
                                pe_info["startVertex"] = [round(sv.x, 4), round(sv.y, 4), round(sv.z, 4)]
                                pe_info["endVertex"] = [round(ev.x, 4), round(ev.y, 4), round(ev.z, 4)]
                            except:
                                pass
                            pe_info["curveType"] = type(edge.geometry).__name__
                        else:
                            pe_info["source"] = "Unknown"
                            pe_info["objectType"] = curve.objectType if hasattr(curve, 'objectType') else str(type(curve))
                    path_entities.append(pe_info)
                info["path"] = path_entities
            except Exception as e:
                info["pathError"] = str(e)

            # Participant bodies
            try:
                if sweep.participantBodies:
                    info["participantBodies"] = [b.name for b in sweep.participantBodies]
            except:
                pass

            # Distances (0-1 fractions of path length)
            for attr, key in [("distanceOne", "distanceOne"), ("distanceTwo", "distanceTwo")]:
                try:
                    val = getattr(sweep, attr)
                    if val:
                        info[key] = val.expression
                except Exception as e:
                    info[key + "Error"] = str(e)

            # Guide rail
            try:
                gr = sweep.guideRail
                if gr:
                    info["hasGuideRail"] = True
                else:
                    info["hasGuideRail"] = False
            except:
                pass
    except Exception as e:
        info["rollToError"] = str(e)

    # Bodies (accessible without rollTo)
    info["bodies"] = [b.name for b in sweep.bodies]

    return info


def _match_profile_index_from_profile(profile, sk, info):
    """Match a single Profile's bounding box to its sketch profiles. Returns matched index or None."""
    try:
        ext_bb = profile.boundingBox
        ext_min = (round(ext_bb.minPoint.x, 3), round(ext_bb.minPoint.y, 3))
        ext_max = (round(ext_bb.maxPoint.x, 3), round(ext_bb.maxPoint.y, 3))
        info["profileCount"] = sk.profiles.count
        best_idx = 0
        best_dist = float('inf')
        for pi in range(sk.profiles.count):
            sp = sk.profiles.item(pi)
            sp_bb = sp.boundingBox
            sp_min = (round(sp_bb.minPoint.x, 3), round(sp_bb.minPoint.y, 3))
            sp_max = (round(sp_bb.maxPoint.x, 3), round(sp_bb.maxPoint.y, 3))
            dist = (abs(sp_min[0] - ext_min[0]) + abs(sp_min[1] - ext_min[1])
                    + abs(sp_max[0] - ext_max[0]) + abs(sp_max[1] - ext_max[1]))
            if dist < best_dist:
                best_dist = dist
                best_idx = pi
        info["profileIndex"] = best_idx
        return best_idx
    except:
        return None


def _capture_split_body(split, design):
    """Capture a SplitBodyFeature."""
    info = {"type": "SplitBody", "name": split.name}

    try:
        info["isSplittingToolExtended"] = split.isSplittingToolExtended
    except:
        pass

    # splittingTool needs rollTo (BRep-dependent)
    try:
        with _roll_to_feature(split, design):
            try:
                tool = split.splittingTool
                cp = adsk.fusion.ConstructionPlane.cast(tool)
                if cp:
                    info["splitTool"] = {"type": "ConstructionPlane", "name": cp.name}
                else:
                    face = adsk.fusion.BRepFace.cast(tool)
                    if face:
                        info["splitTool"] = {"type": "BRepFace", "body": face.body.name}
                        try:
                            eva = face.evaluator
                            ok, pt, norm = eva.getNormalAtPoint(face.pointOnFace)
                            if ok:
                                info["splitTool"]["normal"] = [round(norm.x, 4), round(norm.y, 4), round(norm.z, 4)]
                        except:
                            pass
                    else:
                        body = adsk.fusion.BRepBody.cast(tool)
                        if body:
                            info["splitTool"] = {"type": "BRepBody", "name": body.name}
                        else:
                            info["splitTool"] = {"type": "Unknown", "objectType": tool.objectType if hasattr(tool, 'objectType') else str(type(tool))}
            except Exception as e:
                info["splitToolError"] = str(e)

            # Input bodies being split (can be multiple)
            try:
                sb = split.splitBodies
                if sb.count == 1:
                    info["inputBody"] = sb.item(0).name
                else:
                    info["inputBodies"] = [sb.item(i).name for i in range(sb.count)]
                    info["inputBody"] = sb.item(0).name  # backwards compat
            except:
                pass
            # Output bodies read below after exiting edit mode
            pass
    except Exception as e:
        info["rollToError"] = str(e)

    # Read output bodies with marker AFTER the split (not in edit mode).
    # rollTo(True) is edit mode — split not yet applied. Set markerPosition
    # to just after the feature to see the result.
    if "bodies" not in info:
        try:
            tl = design.timeline
            tlo = split.timelineObject
            tl.markerPosition = tlo.index + 1
            comp = split.parentComponent
            # Sort by (-volume, bbox.min) for deterministic order among
            # equal-volume mirror copies — emitter uses the same sort key.
            body_keys = []
            for i in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(i)
                try:
                    bb = b.boundingBox
                    key = (-b.volume,
                           round(bb.minPoint.x, 4),
                           round(bb.minPoint.y, 4),
                           round(bb.minPoint.z, 4))
                except:
                    key = (-b.volume, 0, 0, 0)
                body_keys.append((b.name, key))
            body_keys.sort(key=lambda x: x[1])
            info["bodies"] = [name for name, key in body_keys]
            # Store volume+bbox for each body so the generator can use
            # distance-based matching instead of relying on sort order.
            body_geo = {}
            for i in range(comp.bRepBodies.count):
                b = comp.bRepBodies.item(i)
                try:
                    bb = b.boundingBox
                    body_geo[b.name] = {
                        "volume": round(b.volume, 4),
                        "bbMin": [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4), round(bb.minPoint.z, 4)],
                        "bbMax": [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4), round(bb.maxPoint.z, 4)],
                    }
                except:
                    body_geo[b.name] = {"volume": round(b.volume, 4), "bbMin": [0,0,0], "bbMax": [0,0,0]}
            info["bodyGeo"] = body_geo
            tl.moveToEnd()
        except:
            info["bodies"] = []

    return info


# ── Remove ──

def _capture_remove(remove):
    """Capture a RemoveFeature. Body name is parsed from the feature name."""
    info = {"type": "Remove", "name": remove.name}

    # Fusion names RemoveFeatures as "RemoveBody-<BodyName>"
    # The removed body is no longer accessible, but the feature name encodes it
    try:
        name = remove.name
        if "RemoveBody-" in name:
            info["removedBody"] = name.split("RemoveBody-", 1)[1]
        elif name.startswith("Remove"):
            info["removedBody"] = name[len("Remove"):].strip()
    except:
        pass

    return info
