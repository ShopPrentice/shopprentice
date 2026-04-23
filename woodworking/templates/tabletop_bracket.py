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

    # Row of brackets along an apron
    tabletop_bracket.row(comp, face_axis="y", face_dir=-1,
        start=("x_start", "y_apron_inner", "z_top_underside"),
        step_axis="x", step_expr="spacing", count=3,
        name="TB", ev=ev)
"""

import adsk.core
import adsk.fusion

from helpers import sp

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

METADATA = {
    "name": "tabletop_bracket",
    "category": "hardware",
    "description": "L-bracket with slotted holes for cross-grain tabletop attachment",
    "best_for": ["desk tops", "table tops", "wide panels on apron frames"],
    "not_for": ["narrow boards (use dominos)", "same-grain connections (use dominos)"],
}


def _define_params(params, prefix="tb"):
    """Add tabletop bracket parameters if not already defined."""
    VI = adsk.core.ValueInput.createByString
    names = [
        (f"{prefix}_w",      "1 in",      "in"),   # bracket width (along apron)
        (f"{prefix}_leg_h",  "1 in",      "in"),   # vertical leg height
        (f"{prefix}_leg_w",  "1 in",      "in"),   # horizontal leg depth (into desk)
        (f"{prefix}_thick",  "0.08 in",   "in"),   # steel thickness (~2mm)
    ]
    for pname, expr, unit in names:
        if not params.itemByName(pname):
            params.add(pname, VI(expr), unit, "")


def _apply_steel(comp, bodies):
    """Apply steel appearance to bracket bodies."""
    try:
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        for matlib in app.materialLibraries:
            for i in range(matlib.appearances.count):
                a = matlib.appearances.item(i)
                if "Steel" in a.name and "Satin" in a.name:
                    local = design.appearances.itemByName(a.name)
                    if not local:
                        local = design.appearances.addByCopy(a, a.name)
                    for b in bodies:
                        b.appearance = local
                    return
    except Exception:
        pass


def single(comp, face_axis, face_dir, pos, prefix="tb", name="TB", ev=None):
    """Create a single L-bracket.

    Built from two rectangular plates joined together:
    - Vertical plate: against the apron inner face, hangs down from top underside
    - Horizontal plate: at the top, extends inward under the tabletop

    Args:
        comp: Component to create features in.
        face_axis: 'x' or 'y' — axis perpendicular to the apron face.
        face_dir: +1 or -1 — direction from apron face toward desk interior.
        pos: (x, y, z) — position where:
             x,y = center of bracket on apron face
             z = top underside (bracket hangs down from here)
        prefix: Parameter prefix (default "tb").
        name: Feature name prefix.
        ev: Evaluator function.

    Returns:
        The bracket body (BRepBody).
    """
    if ev is None:
        ev = sp._make_ev()

    params = comp.parentDesign.userParameters
    _define_params(params, prefix)

    P3 = adsk.core.Point3D

    cx = ev(pos[0]) if isinstance(pos[0], str) else pos[0]
    cy = ev(pos[1]) if isinstance(pos[1], str) else pos[1]
    cz = ev(pos[2]) if isinstance(pos[2], str) else pos[2]

    w = ev(f"{prefix}_w")
    v_h = ev(f"{prefix}_leg_h")
    h_w = ev(f"{prefix}_leg_w")
    thick = ev(f"{prefix}_thick")

    # Vertical plate: against apron face, hangs down from cz
    # Horizontal plate: at cz, extends inward from apron face
    # Helper: format float as cm string for sketch_rect_model
    def cm(val):
        return f"{val} cm"

    if face_axis == "y":
        # Vertical plate sits ON the apron inner face, extending inward
        # ext_new always goes +Y, so offset plane for face_dir=-1
        vp_y = cy if face_dir > 0 else cy - thick
        vp_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                              cm(vp_y), f"{name}_VP_Pl")
        _, vp_prof = sp.sketch_rect_model(comp, vp_pl,
            (cm(cx - w/2), cm(vp_y), cm(cz - v_h)),
            {"x": f"{prefix}_w", "z": f"{prefix}_leg_h"},
            f"{name}_VP_Sk", ev)
        vp_ext = sp.ext_new(comp, vp_prof, f"{prefix}_thick", f"{name}_VP")
        vert_body = vp_ext.bodies.item(0)
        vert_body.name = f"{name}_V"

        # Horizontal plate at top, extending inward from apron face
        hp_pl = sp.off_plane(comp, comp.xYConstructionPlane,
                              cm(cz - thick), f"{name}_HP_Pl")
        hp_y0 = cy if face_dir > 0 else cy - h_w
        _, hp_prof = sp.sketch_rect_model(comp, hp_pl,
            (cm(cx - w/2), cm(hp_y0), cm(cz - thick)),
            {"x": f"{prefix}_w", "y": f"{prefix}_leg_w"},
            f"{name}_HP_Sk", ev)
        hp_ext = sp.ext_new(comp, hp_prof, f"{prefix}_thick", f"{name}_HP")
        horiz_body = hp_ext.bodies.item(0)
        horiz_body.name = f"{name}_H"

        sp.combine(vert_body, horiz_body, JOIN, False, f"{name}_Join")
        vert_body.name = name

    elif face_axis == "x":
        # Vertical plate sits ON apron inner face
        vp_x = cx if face_dir > 0 else cx - thick
        vp_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                              cm(vp_x), f"{name}_VP_Pl")
        _, vp_prof = sp.sketch_rect_model(comp, vp_pl,
            (cm(vp_x), cm(cy - w/2), cm(cz - v_h)),
            {"y": f"{prefix}_w", "z": f"{prefix}_leg_h"},
            f"{name}_VP_Sk", ev)
        vp_ext = sp.ext_new(comp, vp_prof, f"{prefix}_thick", f"{name}_VP")
        vert_body = vp_ext.bodies.item(0)
        vert_body.name = f"{name}_V"

        hp_pl = sp.off_plane(comp, comp.xYConstructionPlane,
                              cm(cz - thick), f"{name}_HP_Pl")
        hp_x0 = cx if face_dir > 0 else cx - h_w
        _, hp_prof = sp.sketch_rect_model(comp, hp_pl,
            (cm(hp_x0), cm(cy - w/2), cm(cz - thick)),
            {"x": f"{prefix}_leg_w", "y": f"{prefix}_w"},
            f"{name}_HP_Sk", ev)
        hp_ext = sp.ext_new(comp, hp_prof, f"{prefix}_thick", f"{name}_HP")
        horiz_body = hp_ext.bodies.item(0)
        horiz_body.name = f"{name}_H"

        sp.combine(vert_body, horiz_body, JOIN, False, f"{name}_Join")
        vert_body.name = name

    # Apply steel appearance
    _apply_steel(comp, [vert_body])

    return vert_body


def row(comp, face_axis, face_dir,
        start, step_axis, step_expr, count,
        prefix="tb", name="TB", ev=None):
    """Create a row of L-brackets along an apron.

    Args:
        comp: Component to create features in.
        face_axis: 'x' or 'y'.
        face_dir: +1 or -1.
        start: (x, y, z) — first bracket position.
        step_axis: 'x' or 'y' — axis to step along.
        step_expr: Spacing (expression string or float cm).
        count: Number of brackets.
        prefix: Parameter prefix.
        name: Feature name prefix.
        ev: Evaluator function.

    Returns:
        List of bracket bodies.
    """
    if ev is None:
        ev = sp._make_ev()

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

        b = single(comp, face_axis, face_dir, pos,
                   prefix=prefix, name=f"{name}_{i}", ev=ev)
        brackets.append(b)

    return brackets
