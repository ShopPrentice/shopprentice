"""
Capture Design Tool

Full design introspection: parameters, component tree with body geometry,
and timeline features. Replaces running introspect.py via execute_api_script.

Key improvements over introspect.py:
1. Inline body geometry — component tree includes volume + bounding box per body
2. Structured sketch planes — returns typed objects instead of bare strings
3. Combine tool inference — walks timeline backwards when toolBodies is empty
"""

import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()


# ── Body geometry helpers ──

def _capture_body(body):
    """Capture a single body's geometry: name, volume, bounding box."""
    info = {"name": body.name}
    try:
        info["volume"] = round(body.volume, 4)
    except:
        pass
    try:
        bb = body.boundingBox
        info["boundingBox"] = {
            "min": [round(bb.minPoint.x, 4), round(bb.minPoint.y, 4), round(bb.minPoint.z, 4)],
            "max": [round(bb.maxPoint.x, 4), round(bb.maxPoint.y, 4), round(bb.maxPoint.z, 4)],
        }
    except:
        pass
    return info


def _capture_all_bodies(root_comp):
    """Capture component tree with inline body geometry."""
    def walk(comp, occ=None):
        info = {
            "name": comp.name,
            "bodies": [_capture_body(b) for b in comp.bRepBodies],
            "children": [],
        }
        if occ:
            try:
                t = occ.transform
                info["transform"] = [
                    round(t.translation.x, 4),
                    round(t.translation.y, 4),
                    round(t.translation.z, 4),
                ]
            except:
                pass
        for child_occ in comp.occurrences:
            info["children"].append(walk(child_occ.component, child_occ))
        return info
    return walk(root_comp)


# ── Component tree (full detail for capture_design) ──

def _capture_component_tree(root_comp):
    """Recursive component tree with bodies, sketches, construction planes."""
    def walk(comp, occ=None):
        info = {
            "name": comp.name,
            "bodies": [_capture_body(b) for b in comp.bRepBodies],
            "sketches": [s.name for s in comp.sketches],
            "constructionPlanes": [p.name for p in comp.constructionPlanes],
            "children": [],
        }
        if occ:
            try:
                t = occ.transform
                info["transform"] = [
                    round(t.translation.x, 4),
                    round(t.translation.y, 4),
                    round(t.translation.z, 4),
                ]
            except:
                pass
        for child_occ in comp.occurrences:
            info["children"].append(walk(child_occ.component, child_occ))
        return info
    return walk(root_comp)


# ── Sketch plane helper ──

def _capture_sketch_plane(sk):
    """Return structured plane info for a sketch's reference plane."""
    try:
        ref = sk.referencePlane
        cp = adsk.fusion.ConstructionPlane.cast(ref)
        if cp:
            result = {"type": "ConstructionPlane", "name": cp.name}
            try:
                geom = cp.geometry
                result["normal"] = [round(geom.normal.x, 6), round(geom.normal.y, 6), round(geom.normal.z, 6)]
                result["origin"] = [round(geom.origin.x, 4), round(geom.origin.y, 4), round(geom.origin.z, 4)]
            except:
                pass
            return result
        bf = adsk.fusion.BRepFace.cast(ref)
        if bf:
            result = {"type": "BRepFace", "body": bf.body.name}
            try:
                eva = bf.evaluator
                ok, pt, norm = eva.getNormalAtPoint(bf.pointOnFace)
                if ok:
                    result["normal"] = [round(norm.x, 4), round(norm.y, 4), round(norm.z, 4)]
                    result["origin"] = [round(bf.pointOnFace.x, 4), round(bf.pointOnFace.y, 4), round(bf.pointOnFace.z, 4)]
            except:
                pass
            return result
    except:
        pass
    return None


# ── Feature capture functions ──

def _capture_extrude(ext, idx, tl):
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

    # Sketch — multi-strategy capture
    sk_found = _find_sketch_for_extrude(ext, idx, tl, info)
    if sk_found:
        info["sketch"] = sk_found.name
        try:
            info["sketchComponent"] = sk_found.parentComponent.name
        except:
            pass
        # Profile index matching
        _match_profile_index(ext, sk_found, info)
    elif "sketchError" not in info:
        info["sketchError"] = "no sketch found (all strategies failed)"

    info["bodies"] = [b.name for b in ext.bodies]

    try:
        if ext.participantBodies:
            info["participantBodies"] = [b.name for b in ext.participantBodies]
    except:
        pass

    try:
        if ext.startFaces and ext.startFaces.count > 0:
            info["startFace"] = True
    except:
        pass

    return info


def _find_sketch_for_extrude(ext, idx, tl, info):
    """Multi-strategy sketch finding for an extrude feature."""
    sk_found = None

    # Strategy 1-3: from profile
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
    except Exception as e:
        info["sketchError"] = f"profile access: {e}"

    # Strategy 4: walk timeline backwards
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


def _match_profile_index(ext, sk_found, info):
    """Match extrude profile bounding box to sketch profiles."""
    try:
        profile = ext.profile
        profiles_coll = adsk.core.ObjectCollection.cast(profile)
        ext_prof = profiles_coll.item(0) if profiles_coll else adsk.fusion.Profile.cast(profile)
        if ext_prof:
            ext_bb = ext_prof.boundingBox
            ext_min = (round(ext_bb.minPoint.x, 3), round(ext_bb.minPoint.y, 3))
            ext_max = (round(ext_bb.maxPoint.x, 3), round(ext_bb.maxPoint.y, 3))
            info["profileCount"] = sk_found.profiles.count
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
            info["profileIndex"] = best_idx
    except:
        pass


def _capture_sketch(sk):
    """Capture a Sketch feature."""
    info = {"type": "Sketch", "name": sk.name}

    # Structured sketch plane
    plane = _capture_sketch_plane(sk)
    if plane:
        info["plane"] = plane

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

    info["curves"] = curves_info
    info["profileCount"] = sk.profiles.count

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
        info["profiles"] = profiles_info

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
    info["dimensions"] = dims_info

    # Constraints
    constraints_info = []
    for ci in range(sk.geometricConstraints.count):
        c = sk.geometricConstraints.item(ci)
        constraints_info.append(type(c).__name__)
    info["constraints"] = constraints_info

    return info


def _capture_construction_plane(cp):
    """Capture a ConstructionPlane feature."""
    info = {"type": "ConstructionPlane", "name": cp.name}

    try:
        defn = cp.definition
        offset_def = adsk.fusion.ConstructionPlaneOffsetDefinition.cast(defn)
        if offset_def:
            info["definitionType"] = "Offset"
            info["offset"] = offset_def.offset.expression
            base = offset_def.planarEntity
            bcp = adsk.fusion.ConstructionPlane.cast(base)
            if bcp:
                info["basePlane"] = bcp.name
            else:
                info["basePlane"] = str(base.objectType)
    except Exception as e:
        info["definitionError"] = str(e)

    try:
        geom = cp.geometry
        info["normal"] = [round(geom.normal.x, 6), round(geom.normal.y, 6), round(geom.normal.z, 6)]
        info["origin"] = [round(geom.origin.x, 4), round(geom.origin.y, 4), round(geom.origin.z, 4)]
    except Exception as e:
        info["geometryError"] = str(e)

    return info


def _capture_mirror(mir):
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

    try:
        inputs = mir.inputEntities
        input_names = []
        for ii in range(inputs.count):
            e = inputs.item(ii)
            if hasattr(e, 'name'):
                input_names.append(e.name)
        info["inputs"] = input_names
    except:
        pass

    info["bodies"] = [b.name for b in mir.bodies]

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


def _capture_rectangular_pattern(pat):
    """Capture a RectangularPatternFeature."""
    info = {"type": "RectangularPattern", "name": pat.name}

    try:
        info["quantityOne"] = pat.quantityOne.expression
        info["distanceOne"] = pat.distanceOne.expression
    except:
        pass

    try:
        axis = pat.directionOneEntity
        ca = adsk.fusion.ConstructionAxis.cast(axis)
        if ca:
            info["axisOne"] = ca.name
            try:
                line = ca.geometry
                info["directionOne"] = [round(line.direction.x, 6), round(line.direction.y, 6), round(line.direction.z, 6)]
            except:
                pass
        else:
            try:
                edge = adsk.fusion.BRepEdge.cast(axis)
                if edge:
                    geom = edge.geometry
                    line = adsk.core.Line3D.cast(geom)
                    if line:
                        info["directionOne"] = [round(line.direction.x, 6), round(line.direction.y, 6), round(line.direction.z, 6)]
            except:
                pass
    except:
        pass

    try:
        if pat.patternDistanceType == adsk.fusion.PatternDistanceType.SpacingPatternDistanceType:
            info["distanceType"] = "Spacing"
        elif pat.patternDistanceType == adsk.fusion.PatternDistanceType.ExtentPatternDistanceType:
            info["distanceType"] = "Extent"
    except:
        pass

    try:
        inputs = pat.inputEntities
        input_names = []
        for ii in range(inputs.count):
            e = inputs.item(ii)
            if hasattr(e, 'name'):
                input_names.append(e.name)
        info["inputs"] = input_names
    except:
        pass

    info["bodies"] = [b.name for b in pat.bodies]

    return info


def _capture_combine(comb, idx, tl):
    """Capture a CombineFeature with tool body inference."""
    info = {"type": "Combine", "name": comb.name}

    op_map = {
        adsk.fusion.FeatureOperations.JoinFeatureOperation: "Join",
        adsk.fusion.FeatureOperations.CutFeatureOperation: "Cut",
        adsk.fusion.FeatureOperations.IntersectFeatureOperation: "Intersect",
    }
    info["operation"] = op_map.get(comb.operation, str(comb.operation))

    # Target body
    try:
        tb = comb.targetBody
        info["targetBody"] = tb.name
        try:
            info["targetComponent"] = tb.parentComponent.name
        except:
            pass
    except Exception as e:
        info["targetBodyError"] = str(e)

    # Tool bodies — with inference when consumed
    tool_names = []
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
        tool_names = [t["name"] for t in tool_info]
        info["toolBodies"] = tool_names
        if any("component" in t for t in tool_info):
            info["toolComponents"] = [t.get("component", "") for t in tool_info]
    except Exception as e:
        info["toolBodiesError"] = str(e)

    # Inference: if toolBodies is empty, walk timeline backwards to find
    # bodies that existed before this combine but don't exist after
    if not tool_names:
        inferred = _infer_combine_tool_bodies(comb, idx, tl)
        if inferred:
            info["toolBodiesInferred"] = inferred

    try:
        info["isKeepToolBodies"] = comb.isKeepToolBodies
    except:
        pass

    return info


def _infer_combine_tool_bodies(comb, idx, tl):
    """Walk timeline backwards to infer which bodies were consumed as tools."""
    inferred = []
    try:
        target_name = comb.targetBody.name
    except:
        return inferred

    # Look at the features just before this combine for NewBody extrudes
    # whose bodies no longer exist (consumed by the combine)
    try:
        target_comp = comb.targetBody.parentComponent
    except:
        return inferred

    for back_idx in range(idx - 1, max(idx - 10, -1), -1):
        try:
            back_item = tl.item(back_idx)
            back_entity = back_item.entity
        except:
            continue
        if back_entity is None:
            continue

        # Check extrudes that created new bodies
        back_ext = adsk.fusion.ExtrudeFeature.cast(back_entity)
        if back_ext and back_ext.operation == adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
            try:
                if back_ext.parentComponent == target_comp:
                    for b in back_ext.bodies:
                        if b.name != target_name:
                            # Check if this body is no longer valid (consumed)
                            try:
                                _ = b.volume
                            except:
                                inferred.append(b.name)
            except:
                pass

    return inferred


def _capture_move(mv):
    """Capture a MoveFeature."""
    info = {"type": "Move", "name": mv.name}

    try:
        transform = mv.transform
        info["matrix"] = [
            [round(transform.getCell(r, c), 6) for c in range(4)]
            for r in range(4)
        ]
        info["translation"] = [
            round(transform.translation.x, 4),
            round(transform.translation.y, 4),
            round(transform.translation.z, 4),
        ]
    except:
        pass

    try:
        inputs = mv.inputEntities
        input_names = []
        for ii in range(inputs.count):
            e = inputs.item(ii)
            if hasattr(e, 'name'):
                input_names.append(e.name)
        info["inputs"] = input_names
    except:
        pass

    return info


# ── Main handler ──

def handler() -> dict:
    """Capture full design: parameters, component tree, timeline features."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

        out = {
            "designName": design.rootComponent.name,
            "designType": "Parametric" if design.designType == adsk.fusion.DesignTypes.ParametricDesignType else "Direct",
            "userParameters": [],
            "components": None,
            "timeline": [],
        }

        # 1. User Parameters
        for i in range(design.userParameters.count):
            p = design.userParameters.item(i)
            out["userParameters"].append({
                "name": p.name,
                "expression": p.expression,
                "unit": p.unit,
                "value": p.value,
                "comment": p.comment,
            })

        # 2. Component Tree (with inline body geometry)
        out["components"] = _capture_component_tree(design.rootComponent)

        # 3. Timeline Features
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

            # Component
            try:
                if hasattr(entity, 'parentComponent') and entity.parentComponent:
                    feat_info["component"] = entity.parentComponent.name
            except:
                pass

            # Extrude
            ext = adsk.fusion.ExtrudeFeature.cast(entity)
            if ext:
                feat_info.update(_capture_extrude(ext, idx, tl))
                out["timeline"].append(feat_info)
                continue

            # Sketch
            sk = adsk.fusion.Sketch.cast(entity)
            if sk:
                feat_info.update(_capture_sketch(sk))
                out["timeline"].append(feat_info)
                continue

            # ConstructionPlane
            cp = adsk.fusion.ConstructionPlane.cast(entity)
            if cp:
                feat_info.update(_capture_construction_plane(cp))
                out["timeline"].append(feat_info)
                continue

            # Mirror
            mir = adsk.fusion.MirrorFeature.cast(entity)
            if mir:
                feat_info.update(_capture_mirror(mir))
                out["timeline"].append(feat_info)
                continue

            # RectangularPattern
            pat = adsk.fusion.RectangularPatternFeature.cast(entity)
            if pat:
                feat_info.update(_capture_rectangular_pattern(pat))
                out["timeline"].append(feat_info)
                continue

            # Combine
            comb = adsk.fusion.CombineFeature.cast(entity)
            if comb:
                feat_info.update(_capture_combine(comb, idx, tl))
                out["timeline"].append(feat_info)
                continue

            # ConstructionAxis
            ca = adsk.fusion.ConstructionAxis.cast(entity)
            if ca:
                feat_info["type"] = "ConstructionAxis"
                feat_info["name"] = ca.name
                out["timeline"].append(feat_info)
                continue

            # Move
            mv = adsk.fusion.MoveFeature.cast(entity)
            if mv:
                feat_info.update(_capture_move(mv))
                out["timeline"].append(feat_info)
                continue

            # Occurrence
            occ = adsk.fusion.Occurrence.cast(entity)
            if occ:
                feat_info["type"] = "ComponentCreation"
                feat_info["name"] = occ.component.name
                out["timeline"].append(feat_info)
                continue

            # Snapshot
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

            # Unknown
            feat_info["type"] = "Unknown"
            feat_info["objectType"] = entity.objectType
            try:
                feat_info["name"] = entity.name
            except:
                pass
            out["timeline"].append(feat_info)

        return {
            "content": [{"type": "text", "text": __import__('json').dumps(out, indent=2)}],
            "isError": False,
            "message": f"Captured design: {out['designName']}"
        }

    except Exception as e:
        app.log(f"capture_design error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "capture_design failed"
        }


# Tool definition

TOOL_DESCRIPTION = \
"""Capture the full active design: user parameters, component tree with body geometry (volume + bounding box), and all timeline features.

Returns structured JSON with:
- userParameters: all parametric dimensions
- components: recursive tree with inline body volumes and bounding boxes
- timeline: every feature (Extrude, Sketch, Mirror, Pattern, Combine, Move, etc.) with full detail

Use this instead of running introspect.py via execute_script."""

tool = Tool.create_simple(
    name="capture_design",
    description=TOOL_DESCRIPTION
).strict_schema()

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
