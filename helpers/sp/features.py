import adsk.core
import adsk.fusion


def ext_new(comp, prof, dist, name="Ext"):
    """Extrude a profile as a new body.

    Returns the ExtrudeFeature. Access the body via ``f.bodies.item(0)``.
    """
    inp = comp.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist))
    f = comp.features.extrudeFeatures.add(inp)
    f.name = name
    return f


def ext_new_sym(comp, prof, dist, name="Ext"):
    """Extrude a profile as a new body, symmetric about the sketch plane.

    Returns the ExtrudeFeature.
    """
    inp = comp.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.setDistanceExtent(True, adsk.core.ValueInput.createByString(dist))
    f = comp.features.extrudeFeatures.add(inp)
    f.name = name
    return f


def ext_op(comp, prof, dist_expr, op, body, name="Ext", flip=False):
    """Extrude a profile as CUT or JOIN into an existing body.

    Args:
        comp: Component owning the extrude feature.
        prof: Sketch profile.
        dist_expr: Distance expression string (e.g. "board_thick").
        op: FeatureOperations enum (CutFeatureOperation or JoinFeatureOperation).
        body: Target body, list of bodies, or None (no participantBodies —
              CUT/JOIN affects all intersecting bodies).
        name: Feature name.
        flip: If True, extrude in negative direction (into the body on
              face-based sketches where default direction points outward).
    """
    inp = comp.features.extrudeFeatures.createInput(prof, op)
    if flip:
        inp.setOneSideExtent(
            adsk.fusion.DistanceExtentDefinition.create(
                adsk.core.ValueInput.createByString(dist_expr)),
            adsk.fusion.ExtentDirections.NegativeExtentDirection)
    else:
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByString(dist_expr))
    if body is not None:
        inp.participantBodies = body if isinstance(body, list) else [body]
    f = comp.features.extrudeFeatures.add(inp)
    f.name = name
    return f


def off_plane(comp, base, expr, name="Pl"):
    """Create an offset construction plane.

    Returns the ConstructionPlane.
    """
    inp = comp.constructionPlanes.createInput()
    inp.setByOffset(base, adsk.core.ValueInput.createByString(expr))
    p = comp.constructionPlanes.add(inp)
    p.name = name
    return p


def _combine_in(comp, target, tool_bodies, op, keep_tool, name="Comb"):
    """Low-level combine primitive — creates the feature in ``comp``.

    Internal helper. Joinery templates and example scripts should call
    :func:`combine` (which picks the right component automatically and
    handles cross-component tool proxies). Use this directly only when
    you have a specific reason to place the feature in a component
    other than ``target.parentComponent``.

    Args:
        comp: Component owning the combine feature.
        target: Target BRepBody.
        tool_bodies: Single BRepBody or list of BRepBody.
        op: FeatureOperations enum (CutFeatureOperation or JoinFeatureOperation).
        keep_tool: Whether to keep tool bodies after the operation.
        name: Feature name.
    """
    coll = adsk.core.ObjectCollection.create()
    if isinstance(tool_bodies, list):
        for b in tool_bodies:
            coll.add(b)
    else:
        coll.add(tool_bodies)
    inp = comp.features.combineFeatures.createInput(target, coll)
    inp.operation = op
    inp.isKeepToolBodies = keep_tool
    f = comp.features.combineFeatures.add(inp)
    f.name = name
    return f


def body_for_root(body, root):
    """Return a body usable by a root-level feature.

    If ``body`` is already in ``root``, returns it unchanged. Otherwise
    walks ``root.allOccurrences`` for the occurrence whose component
    matches ``body``'s owning component and returns a proxy via
    ``createForAssemblyContext``.

    Accepts either a native body or an existing assembly-context
    proxy — proxies are unwrapped to their native body first (Fusion
    rejects ``createForAssemblyContext`` on a body that is already a
    proxy).

    Use when placing a feature at root that must reference bodies living
    in sub-components.
    """
    native = (body.nativeObject if body.assemblyContext else body)
    comp = native.parentComponent
    if comp == root:
        return native
    for i in range(root.allOccurrences.count):
        occ = root.allOccurrences.item(i)
        if occ.component == comp:
            return native.createForAssemblyContext(occ)
    raise ValueError(
        f"No occurrence in root for body '{native.name}' "
        f"(component '{comp.name}').")


def combine(target, tool_bodies, op, keep_tool, name="Comb"):
    """Combine (CUT / JOIN / Intersect) tool bodies into a target body.

    The combine feature lives in ``target.parentComponent`` — the
    natural home for a feature that modifies the target. Tool bodies
    from other components are wrapped via ``createForAssemblyContext``
    proxies automatically, so the same call works whether the tools
    are native, already proxied, or in sibling components.

    Args:
        target: Target BRepBody. Must be a native body (not a proxy) —
            the combine feature is created in its parent component.
        tool_bodies: Single BRepBody or list of BRepBody. Native bodies
            in other components are proxied automatically.
        op: FeatureOperations enum
            (CutFeatureOperation / JoinFeatureOperation / IntersectFeatureOperation).
        keep_tool: Whether to keep tool bodies after the operation.
        name: Feature name.
    """
    tools = tool_bodies if isinstance(tool_bodies, list) else [tool_bodies]
    tgt = target.nativeObject if target.assemblyContext else target
    tgt_comp = tgt.parentComponent
    root = tgt_comp.parentDesign.rootComponent

    tool_refs = []
    for b in tools:
        native_b = b.nativeObject if b.assemblyContext else b
        if native_b.parentComponent == tgt_comp:
            tool_refs.append(native_b)
        else:
            tool_refs.append(body_for_root(b, root))

    return _combine_in(tgt_comp, tgt, tool_refs, op, keep_tool, name)


def mirror_body(comp, body, plane, name="Mirror"):
    """Mirror a single body across a plane.

    Returns the MirrorFeature. Access the mirrored body via
    ``m.bodies.item(0)``.
    """
    coll = adsk.core.ObjectCollection.create()
    coll.add(body)
    inp = comp.features.mirrorFeatures.createInput(coll, plane)
    m = comp.features.mirrorFeatures.add(inp)
    m.name = name
    return m


def mirror_bodies(comp, bodies, plane, name="Mirror"):
    """Mirror multiple bodies across a plane.

    Returns the MirrorFeature.
    """
    coll = adsk.core.ObjectCollection.create()
    for b in bodies:
        coll.add(b)
    inp = comp.features.mirrorFeatures.createInput(coll, plane)
    m = comp.features.mirrorFeatures.add(inp)
    m.name = name
    return m


def mirror_feats(comp, features, plane, name="Mirror"):
    """Mirror features (extrudes, combines, etc.) across a plane.

    Use this instead of ``mirror_body`` when the mirrored side needs to
    replay the feature operations (e.g., extrude + JOIN into a target that
    spans both sides).
    """
    coll = adsk.core.ObjectCollection.create()
    for f in features:
        coll.add(f)
    inp = comp.features.mirrorFeatures.createInput(coll, plane)
    m = comp.features.mirrorFeatures.add(inp)
    m.name = name
    return m


def make_comp(root_comp, name, transform=None):
    """Create a new component under root_comp.

    Args:
        root_comp: Parent component (typically design root).
        name: New component name.
        transform: Optional ``Matrix3D`` placing the occurrence in the
            parent's space. If ``None``, creates at identity. Baking the
            transform in at creation time is the reliable way to place
            a rotated/translated occurrence — setting ``occurrence.
            transform2`` AFTER bodies are built is silently rejected by
            Fusion in many cases.

    Returns:
        The Occurrence (access component via ``occ.component``).
    """
    xf = transform if transform is not None else adsk.core.Matrix3D.create()
    occ = root_comp.occurrences.addNewComponent(xf)
    occ.component.name = name
    return occ


def feat_pattern(comp, feat, axis, count_expr, spacing_expr, name="Pat"):
    """Rectangular pattern of a single feature along an axis.

    Returns the RectangularPatternFeature.
    """
    VI = adsk.core.ValueInput.createByString
    coll = adsk.core.ObjectCollection.create()
    coll.add(feat)
    inp = comp.features.rectangularPatternFeatures.createInput(
        coll, axis, VI(count_expr), VI(spacing_expr),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    p = comp.features.rectangularPatternFeatures.add(inp)
    p.name = name
    return p


def body_pattern(comp, body, axis, count_expr, spacing_expr, name="Pat"):
    """Rectangular pattern of a body along an axis.

    WARNING: body_pattern replays the full feature tree of the template body.
    If the body has CUT/JOIN operations in its timeline history (including
    CUTs added AFTER the pattern), each pattern instance creates ghost
    duplicate bodies. Use a Python ``for`` loop instead for bodies with
    CUT/JOIN history. Safe for simple bodies (NewBody extrude + Mirror only).

    Returns the RectangularPatternFeature.
    """
    VI = adsk.core.ValueInput.createByString
    coll = adsk.core.ObjectCollection.create()
    coll.add(body)
    inp = comp.features.rectangularPatternFeatures.createInput(
        coll, axis, VI(count_expr), VI(spacing_expr),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    inp.quantityTwo = VI("1")
    p = comp.features.rectangularPatternFeatures.add(inp)
    p.name = name
    return p
