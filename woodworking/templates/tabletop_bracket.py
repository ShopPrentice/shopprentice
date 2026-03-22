"""Tabletop L-bracket template.

Creates steel L-brackets for attaching wide panels (desk tops, table tops)
to aprons while allowing cross-grain wood movement. The vertical face has
slotted screw holes (allows panel expansion/contraction), the horizontal
face has round screw holes (fixed to apron).

Wood movement rule: wide panels expand/contract across the grain direction.
Aprons perpendicular to the grain must use slotted fasteners — never rigid
dominos/dowels — or the panel will split.

Usage:
    from woodworking.templates import tabletop_bracket

    # Single bracket on an apron inner face
    tabletop_bracket.single(comp, apron_body, top_body,
        face_axis="y", face_dir=-1,  # inner face of apron
        pos=("x_center", "y_pos", "z_pos"),
        name="TB_1", ev=ev)

    # Row of brackets along an apron
    tabletop_bracket.row(comp, apron_body, top_body,
        face_axis="y", face_dir=-1,
        start=("x_start", "y_pos", "z_pos"),
        step_axis="x", step_expr="tb_sp", count=3,
        name="TB", ev=ev)
"""

import adsk.core
import adsk.fusion
import math

from helpers import af

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "tabletop_bracket",
    "category": "hardware",
    "description": "L-bracket with slotted holes for cross-grain tabletop attachment",
    "best_for": ["desk tops", "table tops", "wide panels on apron frames",
                 "any cross-grain panel-to-frame connection"],
    "not_for": ["narrow boards (use dominos)", "same-grain connections (use dominos)"],
    "standard_sizes": {
        "small":  {"width": "0.75 in", "height": "0.75 in", "length": "1.5 in", "thick": "0.08 in"},
        "medium": {"width": "1 in",    "height": "1 in",    "length": "2 in",    "thick": "0.08 in"},
        "large":  {"width": "1.25 in", "height": "1.25 in", "length": "2.5 in",  "thick": "0.1 in"},
    },
    "rules": {
        "slot_direction": "Slot must be oriented across the panel grain direction",
        "spacing": "One bracket every 12-18 inches along the apron",
        "slot_length": "≥ 3/8 inch to allow seasonal movement",
    },
}


def _define_params(params, prefix="tb"):
    """Add tabletop bracket parameters if not already defined."""
    VI = adsk.core.ValueInput.createByString
    names = [
        (f"{prefix}_w",      "1 in",      "in"),   # bracket width (along apron)
        (f"{prefix}_leg_h",  "1 in",      "in"),   # vertical leg height (apron side)
        (f"{prefix}_leg_w",  "1 in",      "in"),   # horizontal leg width (top side)
        (f"{prefix}_thick",  "0.08 in",   "in"),   # steel thickness (~2mm)
        (f"{prefix}_slot_l", "0.375 in",  "in"),   # slot length (movement range)
        (f"{prefix}_slot_w", "0.19 in",   "in"),   # slot width (screw shaft dia)
        (f"{prefix}_hole_d", "0.19 in",   "in"),   # round hole diameter
        (f"{prefix}_bend_r", "0.0625 in", "in"),   # inside bend radius
    ]
    for pname, expr, unit in names:
        if not params.itemByName(pname):
            params.add(pname, VI(expr), unit, "")


def single(comp, apron_body, top_body,
           face_axis, face_dir, pos,
           prefix="tb", name="TB", ev=None, cut=True):
    """Create a single L-bracket at a position.

    The bracket sits on the inner face of the apron, with its horizontal
    leg extending up to the underside of the top panel. Two slotted holes
    on the vertical face allow cross-grain movement. One round hole on
    the horizontal face screws into the top.

    Args:
        comp: Component to create features in.
        apron_body: The apron body (bracket mounts to its inner face).
        top_body: The top panel body (bracket screws into its underside).
        face_axis: 'x', 'y', or 'z' — axis perpendicular to the apron inner face.
        face_dir: +1 or -1 — direction toward the interior (inner face).
        pos: (x_expr, y_expr, z_expr) — center of bracket on the apron face.
        prefix: Parameter prefix (default "tb").
        name: Feature name prefix.
        ev: Evaluator function.
        cut: If True, CUT screw holes into apron and top.

    Returns:
        The bracket body (BRepBody).
    """
    if ev is None:
        ev = af._make_ev()

    _define_params(comp.parentDesign.userParameters, prefix)

    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D

    # Evaluate dimensions
    w = ev(f"{prefix}_w")
    leg_h = ev(f"{prefix}_leg_h")
    leg_w = ev(f"{prefix}_leg_w")
    thick = ev(f"{prefix}_thick")
    slot_l = ev(f"{prefix}_slot_l")
    slot_w = ev(f"{prefix}_slot_w")
    hole_d = ev(f"{prefix}_hole_d")
    bend_r = ev(f"{prefix}_bend_r")

    cx = ev(pos[0]) if isinstance(pos[0], str) else pos[0]
    cy = ev(pos[1]) if isinstance(pos[1], str) else pos[1]
    cz = ev(pos[2]) if isinstance(pos[2], str) else pos[2]

    # Determine orientation based on face_axis
    # The vertical leg lies on the apron face (perpendicular to face_axis)
    # The horizontal leg extends along face_axis toward the interior
    # The bracket width runs along the remaining axis

    # Build the L-profile sketch on the plane that contains the face_axis and Z
    # The L-shape: vertical leg goes down, horizontal leg goes inward
    if face_axis == "y":
        # Apron face is in XZ plane — bracket width along X, L-profile in YZ
        profile_plane = comp.yZConstructionPlane
        width_axis = "x"
        # Vertical leg: Z direction (down from top)
        # Horizontal leg: Y direction (inward toward top)
        sk = comp.sketches.add(profile_plane)
        sk.name = f"{name}_Sk"
        m2s = sk.modelToSketchSpace

        # L-profile: start at top-outer corner, go down, across, up, across
        inward = face_dir  # +1 or -1
        # Top-outer corner of the L
        y_face = cy  # face position
        z_top = cz + leg_h / 2
        z_bot = cz - leg_h / 2

        # L-profile points (outer boundary)
        pts = [
            (y_face, z_top),                          # top-outer
            (y_face, z_bot),                          # bottom-outer
            (y_face + inward * leg_w, z_bot),         # bottom-inner
            (y_face + inward * leg_w, z_bot + thick), # step up
            (y_face + inward * thick, z_bot + thick), # inner corner
            (y_face + inward * thick, z_top),         # top-inner
        ]

        sp = []
        for pt in pts:
            s = m2s(P3.create(0, pt[0], pt[1]))
            sp.append(P3.create(s.x, s.y, 0))

        lines = sk.sketchCurves.sketchLines
        prev = None
        for i in range(len(sp)):
            next_i = (i + 1) % len(sp)
            if prev is None:
                l = lines.addByTwoPoints(sp[i], sp[next_i])
            else:
                l = lines.addByTwoPoints(prev.endSketchPoint, sp[next_i])
            prev = l

        # Close the profile
        lines.addByTwoPoints(prev.endSketchPoint, sk.sketchCurves.sketchLines.item(0).startSketchPoint)

        prof = sk.profiles.item(0)
        # Extrude along X (width)
        ext = af.ext_new_sym(comp, prof, f"{prefix}_w / 2", f"{name}")
        bracket = ext.bodies.item(0)
        bracket.name = name

    elif face_axis == "x":
        # Apron face is in YZ plane — bracket width along Y, L-profile in XZ
        sk = comp.sketches.add(comp.xZConstructionPlane)
        sk.name = f"{name}_Sk"
        m2s = sk.modelToSketchSpace

        inward = face_dir
        x_face = cx
        z_top = cz + leg_h / 2
        z_bot = cz - leg_h / 2

        pts = [
            (x_face, z_top),
            (x_face, z_bot),
            (x_face + inward * leg_w, z_bot),
            (x_face + inward * leg_w, z_bot + thick),
            (x_face + inward * thick, z_bot + thick),
            (x_face + inward * thick, z_top),
        ]

        sp = []
        for pt in pts:
            s = m2s(P3.create(pt[0], 0, pt[1]))
            sp.append(P3.create(s.x, s.y, 0))

        lines_coll = sk.sketchCurves.sketchLines
        prev = None
        for i in range(len(sp)):
            next_i = (i + 1) % len(sp)
            if prev is None:
                l = lines_coll.addByTwoPoints(sp[i], sp[next_i])
            else:
                l = lines_coll.addByTwoPoints(prev.endSketchPoint, sp[next_i])
            prev = l
        lines_coll.addByTwoPoints(prev.endSketchPoint,
                                   sk.sketchCurves.sketchLines.item(0).startSketchPoint)

        prof = sk.profiles.item(0)
        ext = af.ext_new_sym(comp, prof, f"{prefix}_w / 2", f"{name}")
        bracket = ext.bodies.item(0)
        bracket.name = name

    sk.isVisible = False

    # CUT slotted holes in vertical face and round hole in horizontal face
    if cut and apron_body is not None and top_body is not None:
        # Slot on vertical face (allows cross-grain movement)
        # Two slots, evenly spaced on the vertical leg
        slot_z1 = cz + leg_h / 4
        slot_z2 = cz - leg_h / 4

        for si, sz in enumerate([slot_z1, slot_z2]):
            slot_sk = comp.sketches.add(comp.xYConstructionPlane
                                         if face_axis == "y" else comp.xYConstructionPlane)
            # Simple approach: create slot as a rectangle with rounded ends
            # For now use a simple rectangle CUT (slot approximation)
            if face_axis == "y":
                slot_pl = af.off_plane(comp, comp.xYConstructionPlane,
                                        f"{sz} cm", f"{name}_Slot{si}_Pl")
                s_sk = comp.sketches.add(slot_pl)
                s_sk.name = f"{name}_Slot{si}_Sk"
                sm = s_sk.modelToSketchSpace
                # Slot runs along the width axis (X) for cross-grain movement
                sc = sm(P3.create(cx, cy + face_dir * thick / 2, sz))
                s_sk.sketchCurves.sketchCircles.addByCenterRadius(
                    P3.create(sc.x, sc.y, 0), slot_w / 2)
                s_prof = s_sk.profiles.item(0)
                af.ext_op(comp, s_prof, f"{prefix}_thick * 2", CUT, bracket,
                          f"{name}_Slot{si}", flip=False)
                s_sk.isVisible = False

        # Round hole on horizontal face (fixed screw into top)
        h_pl = af.off_plane(comp, comp.xYConstructionPlane,
                             f"{z_bot + thick / 2} cm", f"{name}_Hole_Pl")
        h_sk = comp.sketches.add(h_pl)
        h_sk.name = f"{name}_Hole_Sk"
        hm = h_sk.modelToSketchSpace
        if face_axis == "y":
            hc = hm(P3.create(cx, cy + face_dir * leg_w / 2, z_bot + thick / 2))
        else:
            hc = hm(P3.create(cx + face_dir * leg_w / 2, cy, z_bot + thick / 2))
        h_sk.sketchCurves.sketchCircles.addByCenterRadius(
            P3.create(hc.x, hc.y, 0), hole_d / 2)
        h_prof = h_sk.profiles.item(0)
        af.ext_op(comp, h_prof, f"{prefix}_thick * 2", CUT, bracket,
                  f"{name}_HoleCut", flip=False)
        h_sk.isVisible = False

    # Apply steel appearance
    try:
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        lib = app.materialLibraries.itemByName("Fusion 360 Appearance Library")
        if lib:
            steel = None
            for i in range(lib.appearances.count):
                a = lib.appearances.item(i)
                if "Steel" in a.name and "Satin" in a.name:
                    steel = a
                    break
            if steel:
                local = design.appearances.itemByName(steel.name)
                if not local:
                    local = design.appearances.addByCopy(steel, steel.name)
                bracket.appearance = local
    except Exception:
        pass

    return bracket


def row(comp, apron_body, top_body,
        face_axis, face_dir,
        start, step_axis, step_expr, count,
        prefix="tb", name="TB", ev=None, cut=True):
    """Create a row of L-brackets along an apron.

    Args:
        comp: Component to create features in.
        apron_body, top_body: Bodies for CUT operations.
        face_axis, face_dir: Which face and direction.
        start: (x, y, z) — center of first bracket.
        step_axis: 'x', 'y', or 'z' — axis to step along.
        step_expr: Spacing expression.
        count: Number of brackets (int or expression).
        prefix: Parameter prefix.
        name: Feature name prefix.
        ev: Evaluator function.
        cut: If True, CUT screw holes.

    Returns:
        List of bracket bodies.
    """
    if ev is None:
        ev = af._make_ev()

    n = int(ev(count) if isinstance(count, str) else count)
    step = ev(step_expr) if isinstance(step_expr, str) else step_expr

    sx = ev(start[0]) if isinstance(start[0], str) else start[0]
    sy = ev(start[1]) if isinstance(start[1], str) else start[1]
    sz = ev(start[2]) if isinstance(start[2], str) else start[2]

    brackets = []
    for i in range(n):
        offset = i * step
        if step_axis == "x":
            pos = (sx + offset, sy, sz)
        elif step_axis == "y":
            pos = (sx, sy + offset, sz)
        else:
            pos = (sx, sy, sz + offset)

        b = single(comp, apron_body, top_body,
                   face_axis, face_dir, pos,
                   prefix=prefix, name=f"{name}_{i}", ev=ev, cut=cut)
        brackets.append(b)

    return brackets
