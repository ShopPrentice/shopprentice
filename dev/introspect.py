"""
Fusion 360 Design Introspection Script

Walks the active design's timeline and dumps a structured representation
of every feature: parameters, sketches, extrudes, mirrors, patterns,
combines, and construction planes.

Output is printed as JSON so it can be parsed programmatically.
"""
import adsk.core, adsk.fusion
import json
import traceback


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)

    out = {
        "designName": design.rootComponent.name,
        "designType": "Parametric" if design.designType == adsk.fusion.DesignTypes.ParametricDesignType else "Direct",
        "userParameters": [],
        "components": [],
        "timeline": [],
    }

    # ── 1. User Parameters ──
    for i in range(design.userParameters.count):
        p = design.userParameters.item(i)
        out["userParameters"].append({
            "name": p.name,
            "expression": p.expression,
            "unit": p.unit,
            "value": p.value,
            "comment": p.comment,
        })

    # ── 2. Component Tree ──
    def dump_comp(comp, occ=None, depth=0):
        info = {
            "name": comp.name,
            "bodies": [b.name for b in comp.bRepBodies],
            "sketches": [s.name for s in comp.sketches],
            "constructionPlanes": [p.name for p in comp.constructionPlanes],
            "children": [],
        }
        # Occurrence transform (world position of this component)
        if occ:
            try:
                t = occ.transform
                info["transform"] = {
                    "translation": [
                        round(t.translation.x, 4),
                        round(t.translation.y, 4),
                        round(t.translation.z, 4),
                    ],
                }
            except:
                pass
        for child_occ in comp.occurrences:
            info["children"].append(
                dump_comp(child_occ.component, child_occ, depth + 1))
        return info

    out["components"] = dump_comp(design.rootComponent)

    # ── 3. Timeline Features ──
    tl = design.timeline
    for idx in range(tl.count):
        item = tl.item(idx)
        try:
            entity = item.entity
        except RuntimeError:
            continue
        if entity is None:
            continue

        feat_info = {
            "index": idx,
            "isGroup": item.isGroup,
            "isRolledBack": item.isRolledBack,
        }

        # Identify the component this feature belongs to
        try:
            if hasattr(entity, 'parentComponent') and entity.parentComponent:
                feat_info["component"] = entity.parentComponent.name
        except:
            pass

        # ── ExtrudeFeature ──
        ext = adsk.fusion.ExtrudeFeature.cast(entity)
        if ext:
            feat_info["type"] = "Extrude"
            feat_info["name"] = ext.name

            # Operation
            op_map = {
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation: "NewBody",
                adsk.fusion.FeatureOperations.CutFeatureOperation: "Cut",
                adsk.fusion.FeatureOperations.JoinFeatureOperation: "Join",
                adsk.fusion.FeatureOperations.IntersectFeatureOperation: "Intersect",
            }
            feat_info["operation"] = op_map.get(ext.operation, str(ext.operation))

            # Extent type and distance
            try:
                extent = ext.extentOne
                if isinstance(extent, adsk.fusion.DistanceExtentDefinition):
                    feat_info["extentType"] = "Distance"
                    feat_info["distance"] = extent.distance.expression
                elif isinstance(extent, adsk.fusion.SymmetricExtentDefinition):
                    feat_info["extentType"] = "Symmetric"
                    feat_info["distance"] = extent.distance.expression
                else:
                    feat_info["extentType"] = type(extent).__name__
            except:
                pass

            # Check for symmetric
            try:
                if ext.extentType == adsk.fusion.FeatureExtentTypes.SymmetricFeatureExtentType:
                    feat_info["extentType"] = "Symmetric"
                    sym_ext = adsk.fusion.SymmetricExtentDefinition.cast(ext.extentOne)
                    if sym_ext:
                        feat_info["distance"] = sym_ext.distance.expression
            except:
                pass

            # Sketch info — multi-strategy capture
            sk_found = None
            try:
                profile = ext.profile
                # Strategy 1: ObjectCollection of profiles
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
                else:
                    # Strategy 2: single Profile.cast
                    try:
                        p = adsk.fusion.Profile.cast(profile)
                        if p:
                            sk_found = p.parentSketch
                    except:
                        pass
                    # Strategy 3: direct .parentSketch without cast
                    if not sk_found:
                        try:
                            sk_found = profile.parentSketch
                        except:
                            pass
            except Exception as e:
                feat_info["sketchError"] = f"profile access: {e}"

            # Strategy 4: walk timeline backwards to find nearest preceding sketch
            if not sk_found:
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
                            # Check same or parent component
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
                    if "sketchError" not in feat_info:
                        feat_info["sketchError"] = f"timeline walk: {e}"

            if sk_found:
                feat_info["sketch"] = sk_found.name
                try:
                    feat_info["sketchComponent"] = sk_found.parentComponent.name
                except:
                    pass

                # Profile index: match extrude profile bbox to sketch profiles
                try:
                    profile = ext.profile
                    profiles_coll = adsk.core.ObjectCollection.cast(profile)
                    ext_prof = profiles_coll.item(0) if profiles_coll else adsk.fusion.Profile.cast(profile)
                    if ext_prof:
                        ext_bb = ext_prof.boundingBox
                        ext_min = (round(ext_bb.minPoint.x, 3), round(ext_bb.minPoint.y, 3))
                        ext_max = (round(ext_bb.maxPoint.x, 3), round(ext_bb.maxPoint.y, 3))
                        feat_info["profileCount"] = sk_found.profiles.count
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
                        feat_info["profileIndex"] = best_idx
                except:
                    pass
            elif "sketchError" not in feat_info:
                feat_info["sketchError"] = "no sketch found (all strategies failed)"

            # Bodies created
            feat_info["bodies"] = [b.name for b in ext.bodies]

            # Participant bodies
            try:
                if ext.participantBodies:
                    feat_info["participantBodies"] = [b.name for b in ext.participantBodies]
            except:
                pass

            # Start face (if sketched on a face)
            try:
                if ext.startFaces and ext.startFaces.count > 0:
                    feat_info["startFace"] = True
            except:
                pass

            out["timeline"].append(feat_info)
            continue

        # ── Sketch ──
        sk = adsk.fusion.Sketch.cast(entity)
        if sk:
            feat_info["type"] = "Sketch"
            feat_info["name"] = sk.name

            # Sketch plane info
            try:
                ref = sk.referencePlane
                cp = adsk.fusion.ConstructionPlane.cast(ref)
                if cp:
                    feat_info["plane"] = cp.name
                else:
                    bf = adsk.fusion.BRepFace.cast(ref)
                    if bf:
                        feat_info["plane"] = f"BRepFace(body={bf.body.name})"
                        # Get face normal and position
                        try:
                            eva = bf.evaluator
                            ok, pt, norm = eva.getNormalAtPoint(bf.pointOnFace)
                            if ok:
                                feat_info["faceNormal"] = [round(norm.x, 4), round(norm.y, 4), round(norm.z, 4)]
                                feat_info["facePoint"] = [round(bf.pointOnFace.x, 4), round(bf.pointOnFace.y, 4), round(bf.pointOnFace.z, 4)]
                        except:
                            pass
            except:
                pass

            # Curves
            curves_info = []
            for ci in range(sk.sketchCurves.count):
                c = sk.sketchCurves.item(ci)
                line = adsk.fusion.SketchLine.cast(c)
                if line:
                    curves_info.append({
                        "type": "Line",
                        "start": [round(line.startSketchPoint.geometry.x, 4),
                                  round(line.startSketchPoint.geometry.y, 4)],
                        "end": [round(line.endSketchPoint.geometry.x, 4),
                                round(line.endSketchPoint.geometry.y, 4)],
                        "isConstruction": line.isConstruction,
                    })
                    continue
                arc = adsk.fusion.SketchArc.cast(c)
                if arc:
                    arc_info = {
                        "type": "Arc",
                        "center": [round(arc.centerSketchPoint.geometry.x, 4),
                                   round(arc.centerSketchPoint.geometry.y, 4)],
                        "radius": round(arc.radius, 4),
                        "start": [round(arc.startSketchPoint.geometry.x, 4),
                                  round(arc.startSketchPoint.geometry.y, 4)],
                        "end": [round(arc.endSketchPoint.geometry.x, 4),
                                round(arc.endSketchPoint.geometry.y, 4)],
                    }
                    # Get sweep angle from the underlying Arc3D geometry
                    try:
                        _, _, _, _, sweep = arc.geometry.getData()
                        arc_info["sweepAngle"] = round(sweep, 4)
                    except:
                        pass
                    curves_info.append(arc_info)
                    continue
                circle = adsk.fusion.SketchCircle.cast(c)
                if circle:
                    curves_info.append({
                        "type": "Circle",
                        "center": [round(circle.centerSketchPoint.geometry.x, 4),
                                   round(circle.centerSketchPoint.geometry.y, 4)],
                        "radius": round(circle.radius, 4),
                    })
                    continue

            feat_info["curves"] = curves_info
            feat_info["profileCount"] = sk.profiles.count

            # Profile bounding boxes
            profiles_info = []
            for pi in range(sk.profiles.count):
                try:
                    p = sk.profiles.item(pi)
                    bb = p.boundingBox
                    profiles_info.append({
                        "index": pi,
                        "min": [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4)],
                        "max": [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4)],
                    })
                except:
                    profiles_info.append({"index": pi})
            if profiles_info:
                feat_info["profiles"] = profiles_info

            # Dimensions
            dims_info = []
            for di in range(sk.sketchDimensions.count):
                d = sk.sketchDimensions.item(di)
                dim_entry = {
                    "type": type(d).__name__,
                    "expression": d.parameter.expression if d.parameter else None,
                    "value": round(d.parameter.value, 6) if d.parameter else None,
                }
                dims_info.append(dim_entry)
            feat_info["dimensions"] = dims_info

            # Constraints
            constraints_info = []
            for ci in range(sk.geometricConstraints.count):
                c = sk.geometricConstraints.item(ci)
                constraints_info.append(type(c).__name__)
            feat_info["constraints"] = constraints_info

            out["timeline"].append(feat_info)
            continue

        # ── ConstructionPlane ──
        cp = adsk.fusion.ConstructionPlane.cast(entity)
        if cp:
            feat_info["type"] = "ConstructionPlane"
            feat_info["name"] = cp.name

            # Try offset definition
            try:
                defn = cp.definition
                offset_def = adsk.fusion.ConstructionPlaneOffsetDefinition.cast(defn)
                if offset_def:
                    feat_info["definitionType"] = "Offset"
                    feat_info["offset"] = offset_def.offset.expression
                    base = offset_def.planarEntity
                    bcp = adsk.fusion.ConstructionPlane.cast(base)
                    if bcp:
                        feat_info["basePlane"] = bcp.name
                    else:
                        feat_info["basePlane"] = str(base.objectType)
            except Exception as e:
                feat_info["definitionError"] = str(e)

            # Always try to get the plane geometry (normal + origin)
            try:
                geom = cp.geometry
                feat_info["normal"] = [
                    round(geom.normal.x, 6),
                    round(geom.normal.y, 6),
                    round(geom.normal.z, 6),
                ]
                feat_info["origin"] = [
                    round(geom.origin.x, 4),
                    round(geom.origin.y, 4),
                    round(geom.origin.z, 4),
                ]
            except Exception as e:
                feat_info["geometryError"] = str(e)

            out["timeline"].append(feat_info)
            continue

        # ── MirrorFeature ──
        mir = adsk.fusion.MirrorFeature.cast(entity)
        if mir:
            feat_info["type"] = "Mirror"
            feat_info["name"] = mir.name

            try:
                mp = mir.mirrorPlane
                bcp = adsk.fusion.ConstructionPlane.cast(mp)
                if bcp:
                    feat_info["mirrorPlane"] = bcp.name
                    # Get mirror plane geometry
                    try:
                        geom = bcp.geometry
                        feat_info["planeNormal"] = [
                            round(geom.normal.x, 6),
                            round(geom.normal.y, 6),
                            round(geom.normal.z, 6),
                        ]
                        feat_info["planeOrigin"] = [
                            round(geom.origin.x, 4),
                            round(geom.origin.y, 4),
                            round(geom.origin.z, 4),
                        ]
                    except:
                        pass
                else:
                    # Try BRepFace as mirror plane
                    bf = adsk.fusion.BRepFace.cast(mp)
                    if bf:
                        feat_info["mirrorPlane"] = f"BRepFace(body={bf.body.name})"
                        try:
                            eva = bf.evaluator
                            ok, pt, norm = eva.getNormalAtPoint(bf.pointOnFace)
                            if ok:
                                feat_info["planeNormal"] = [
                                    round(norm.x, 6),
                                    round(norm.y, 6),
                                    round(norm.z, 6),
                                ]
                                feat_info["planeOrigin"] = [
                                    round(bf.pointOnFace.x, 4),
                                    round(bf.pointOnFace.y, 4),
                                    round(bf.pointOnFace.z, 4),
                                ]
                        except:
                            pass
            except:
                pass

            # Input entities
            try:
                inputs = mir.inputEntities
                input_names = []
                for ii in range(inputs.count):
                    e = inputs.item(ii)
                    if hasattr(e, 'name'):
                        input_names.append(e.name)
                feat_info["inputs"] = input_names
            except:
                pass

            # Output bodies
            feat_info["bodies"] = [b.name for b in mir.bodies]

            # Pattern compute option (bodies vs features)
            try:
                if mir.patternComputeOption == adsk.fusion.PatternComputeOptions.IdenticalPatternCompute:
                    feat_info["computeOption"] = "Identical"
                elif mir.patternComputeOption == adsk.fusion.PatternComputeOptions.OptimizedPatternCompute:
                    feat_info["computeOption"] = "Optimized"
                elif mir.patternComputeOption == adsk.fusion.PatternComputeOptions.AdjustPatternCompute:
                    feat_info["computeOption"] = "Adjust"
            except:
                pass

            out["timeline"].append(feat_info)
            continue

        # ── RectangularPatternFeature ──
        pat = adsk.fusion.RectangularPatternFeature.cast(entity)
        if pat:
            feat_info["type"] = "RectangularPattern"
            feat_info["name"] = pat.name

            # Direction and count/spacing
            try:
                feat_info["quantityOne"] = pat.quantityOne.expression
                feat_info["distanceOne"] = pat.distanceOne.expression
            except:
                pass

            try:
                axis = pat.directionOneEntity
                ca = adsk.fusion.ConstructionAxis.cast(axis)
                if ca:
                    feat_info["axisOne"] = ca.name
                    # Try to get axis direction vector
                    try:
                        line = ca.geometry
                        feat_info["directionOne"] = [
                            round(line.direction.x, 6),
                            round(line.direction.y, 6),
                            round(line.direction.z, 6),
                        ]
                    except:
                        pass
                else:
                    # Could be a BRepEdge or other linear entity
                    try:
                        edge = adsk.fusion.BRepEdge.cast(axis)
                        if edge:
                            geom = edge.geometry
                            line = adsk.core.Line3D.cast(geom)
                            if line:
                                feat_info["directionOne"] = [
                                    round(line.direction.x, 6),
                                    round(line.direction.y, 6),
                                    round(line.direction.z, 6),
                                ]
                    except:
                        pass
            except:
                pass

            # Distance type
            try:
                if pat.patternDistanceType == adsk.fusion.PatternDistanceType.SpacingPatternDistanceType:
                    feat_info["distanceType"] = "Spacing"
                elif pat.patternDistanceType == adsk.fusion.PatternDistanceType.ExtentPatternDistanceType:
                    feat_info["distanceType"] = "Extent"
            except:
                pass

            # Input entities
            try:
                inputs = pat.inputEntities
                input_names = []
                for ii in range(inputs.count):
                    e = inputs.item(ii)
                    if hasattr(e, 'name'):
                        input_names.append(e.name)
                feat_info["inputs"] = input_names
            except:
                pass

            feat_info["bodies"] = [b.name for b in pat.bodies]

            out["timeline"].append(feat_info)
            continue

        # ── CombineFeature ──
        comb = adsk.fusion.CombineFeature.cast(entity)
        if comb:
            feat_info["type"] = "Combine"
            feat_info["name"] = comb.name

            op_map = {
                adsk.fusion.FeatureOperations.JoinFeatureOperation: "Join",
                adsk.fusion.FeatureOperations.CutFeatureOperation: "Cut",
                adsk.fusion.FeatureOperations.IntersectFeatureOperation: "Intersect",
            }
            feat_info["operation"] = op_map.get(comb.operation, str(comb.operation))

            # Target body — may be a proxy in assembly context
            try:
                tb = comb.targetBody
                feat_info["targetBody"] = tb.name
                try:
                    feat_info["targetComponent"] = tb.parentComponent.name
                except:
                    pass
            except Exception as e:
                feat_info["targetBodyError"] = str(e)

            # Tool bodies — may be proxies in assembly context
            try:
                tools = comb.toolBodies
                tool_info = []
                for i in range(tools.count):
                    t = tools.item(i)
                    entry = {"name": t.name}
                    try:
                        entry["component"] = t.parentComponent.name
                    except:
                        pass
                    tool_info.append(entry)
                feat_info["toolBodies"] = [t["name"] for t in tool_info]
                if any("component" in t for t in tool_info):
                    feat_info["toolComponents"] = [
                        t.get("component", "") for t in tool_info]
            except Exception as e:
                feat_info["toolBodiesError"] = str(e)

            try:
                feat_info["isKeepToolBodies"] = comb.isKeepToolBodies
            except:
                pass

            out["timeline"].append(feat_info)
            continue

        # ── ConstructionAxis ──
        ca = adsk.fusion.ConstructionAxis.cast(entity)
        if ca:
            feat_info["type"] = "ConstructionAxis"
            feat_info["name"] = ca.name
            out["timeline"].append(feat_info)
            continue

        # ── MoveFeature ──
        mv = adsk.fusion.MoveFeature.cast(entity)
        if mv:
            feat_info["type"] = "Move"
            feat_info["name"] = mv.name

            # Translation / full transform matrix
            try:
                transform = mv.transform
                feat_info["matrix"] = [
                    [round(transform.getCell(r, c), 6) for c in range(4)]
                    for r in range(4)
                ]
                feat_info["translation"] = [
                    round(transform.translation.x, 4),
                    round(transform.translation.y, 4),
                    round(transform.translation.z, 4),
                ]
            except:
                pass

            # Input bodies
            try:
                inputs = mv.inputEntities
                input_names = []
                for ii in range(inputs.count):
                    e = inputs.item(ii)
                    if hasattr(e, 'name'):
                        input_names.append(e.name)
                feat_info["inputs"] = input_names
            except:
                pass

            out["timeline"].append(feat_info)
            continue

        # ── Occurrence (component creation) ──
        occ = adsk.fusion.Occurrence.cast(entity)
        if occ:
            feat_info["type"] = "ComponentCreation"
            feat_info["name"] = occ.component.name
            out["timeline"].append(feat_info)
            continue

        # ── Snapshot (position capture — no geometry) ──
        try:
            if entity.objectType == "adsk::fusion::Snapshot":
                feat_info["type"] = "Snapshot"
                try:
                    feat_info["name"] = entity.name
                except:
                    pass
                out["timeline"].append(feat_info)
                continue
        except:
            pass

        # ── Unknown feature type ──
        feat_info["type"] = "Unknown"
        feat_info["objectType"] = entity.objectType
        try:
            feat_info["name"] = entity.name
        except:
            pass
        out["timeline"].append(feat_info)

    # ── Output ──
    print(json.dumps(out, indent=2))
