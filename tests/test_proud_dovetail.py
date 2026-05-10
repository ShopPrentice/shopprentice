"""Focused test for Krenov-style proud dovetails.

Tests:
  B1: 1-corner flush (baseline, verifies no regression)
  B16: 1-corner proud (proud_offset = 0.04 in ≈ 1mm)
  B17: 4-corner proud (proud_offset = 0.03 in)
"""
import adsk.core
import adsk.fusion
import sys


def build_box(root, prefix, l_expr, w_expr, h_expr, t_expr,
              x_off_expr, dt_prefix, ev, y_off_expr="0 in",
              corners=4, proud_offset_expr=None):
    """Build a box with through dovetails, optionally proud."""
    from helpers import sp
    from woodworking.templates import dovetail

    has_proud = proud_offset_expr is not None

    occ = sp.make_comp(root, prefix)
    comp = occ.component

    ox = ev(x_off_expr) if x_off_expr != "0 in" else 0.0
    oy = ev(y_off_expr) if y_off_expr != "0 in" else 0.0

    # Y expressions for board positions
    front_y_expr = y_off_expr
    back_y_expr = (f"{y_off_expr} + {w_expr} - {t_expr}"
                   if oy != 0.0 else f"{w_expr} - {t_expr}")
    tail_y_expr = f"{y_off_expr} + {t_expr}" if oy != 0.0 else t_expr
    tail_w_expr = f"{w_expr} - 2 * {t_expr}"

    # ── Pin and tail board dimensions are built at normal positions.
    # After construction, proud boards are extended via JOIN extrudes. ──
    pin_l_expr = l_expr
    pin_x_expr = x_off_expr
    tail_t_expr = t_expr
    tail_x_expr = x_off_expr

    # ── Front (pin board) ──
    if oy == 0.0:
        front_sk_pl = comp.xZConstructionPlane
    else:
        front_sk_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                                    y_off_expr, f"{prefix}_FrontYPl")

    sk, pr = sp.sketch_rect_model(comp, front_sk_pl,
        (pin_x_expr, front_y_expr, "0 in"),
        {"x": pin_l_expr, "z": h_expr}, f"{prefix}_Front_Sk", ev)
    front = sp.ext_new(comp, pr, t_expr, f"{prefix}_Front").bodies.item(0)
    front.name = f"{prefix}_Front"

    # ── Back (pin board, only for 4-corner) ──
    back = None
    if corners == 4:
        back_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                               back_y_expr, f"{prefix}_Back_Pl")
        sk, pr = sp.sketch_rect_model(comp, back_pl,
            (pin_x_expr, back_y_expr, "0 in"),
            {"x": pin_l_expr, "z": h_expr}, f"{prefix}_Back_Sk", ev)
        back = sp.ext_new(comp, pr, t_expr, f"{prefix}_Back").bodies.item(0)
        back.name = f"{prefix}_Back"

    # ── Midplanes ──
    x_mid_expr = (f"{x_off_expr} + {l_expr} / 2"
                  if ox != 0.0 else f"{l_expr} / 2")
    y_mid_expr = (f"{y_off_expr} + {w_expr} / 2"
                  if oy != 0.0 else f"{w_expr} / 2")

    x_mid = sp.off_plane(comp, comp.yZConstructionPlane,
                          x_mid_expr, f"{prefix}_XMid")
    y_mid = sp.off_plane(comp, comp.xZConstructionPlane,
                          y_mid_expr, f"{prefix}_YMid")

    # ── Left (tail board, narrower) ──
    if ox == 0.0:
        left_pl = comp.yZConstructionPlane
    else:
        left_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                               x_off_expr, f"{prefix}_Left_Pl")

    sk, pr = sp.sketch_rect_model(comp, left_pl,
        (tail_x_expr, tail_y_expr, "0 in"),
        {"y": tail_w_expr, "z": h_expr}, f"{prefix}_Left_Sk", ev)
    left = sp.ext_new(comp, pr, tail_t_expr, f"{prefix}_Left").bodies.item(0)
    left.name = f"{prefix}_Left"

    # ── Right (tail board via mirror of left, only for 2+ corners) ──
    right = None
    if corners >= 2:
        right_mir = sp.mirror_body(comp, left, x_mid, f"{prefix}_RightMir")
        right = right_mir.bodies.item(0)
        right.name = f"{prefix}_Right"

    board_count = 1 + (1 if back else 0) + 1 + (1 if right else 0)
    print(f"  {prefix} boards built: {board_count} boards")

    # ── Proud extensions: widen pin boards + thicken tail boards ──
    if has_proud:
        VI_p = adsk.core.ValueInput.createByString
        JOIN_op = adsk.fusion.FeatureOperations.JoinFeatureOperation

        # Extend pin boards by proud_offset on each end (ext_axis = x)
        for pb, pb_name in [(front, "Front")] + ([(back, "Back")] if back else []):
            for direction in [-1, +1]:
                face = sp.find_face(pb, "x", direction)
                inp = comp.features.extrudeFeatures.createInput(face, JOIN_op)
                inp.setDistanceExtent(False, VI_p(proud_offset_expr))
                inp.participantBodies = [pb]
                ext = comp.features.extrudeFeatures.add(inp)
                ext.name = f"{prefix}_{pb_name}_Ext{'L' if direction < 0 else 'R'}"

        # Extend tail boards by proud_offset toward pin boards (ext_axis = x)
        # Left: extend in -X direction
        face_l = sp.find_face(left, "x", -1)
        inp = comp.features.extrudeFeatures.createInput(face_l, JOIN_op)
        inp.setDistanceExtent(False, VI_p(proud_offset_expr))
        inp.participantBodies = [left]
        ext = comp.features.extrudeFeatures.add(inp)
        ext.name = f"{prefix}_Left_Ext"

        if right is not None:
            face_r = sp.find_face(right, "x", +1)
            inp = comp.features.extrudeFeatures.createInput(face_r, JOIN_op)
            inp.setDistanceExtent(False, VI_p(proud_offset_expr))
            inp.participantBodies = [right]
            ext = comp.features.extrudeFeatures.add(inp)
            ext.name = f"{prefix}_Right_Ext"

        print(f"  {prefix} proud extensions applied")

    # ── Dovetails ──
    # When proud, the dovetail sketch plane must be at the extended tail
    # board position (original - proud_offset in ext_axis).
    dt_plane = left_pl
    if has_proud:
        dt_plane = sp.off_plane(comp, comp.yZConstructionPlane,
                                f"{x_off_expr} - {proud_offset_expr}",
                                f"{prefix}_DT_Pl")

    result = dovetail.box(comp, front, left,
                          x_mid, y_mid, thick_expr=t_expr,
                          right=right,
                          back=back,
                          prefix=dt_prefix, name=prefix, ev=ev,
                          fl_plane=dt_plane,
                          front_expr=front_y_expr,
                          proud_offset_expr=proud_offset_expr)

    # Restore body names by position
    x_mid_val = ev(x_mid_expr)
    y_mid_val = ev(y_mid_expr)
    for i in range(comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        bb = b.boundingBox
        cx = (bb.minPoint.x + bb.maxPoint.x) / 2
        cy = (bb.minPoint.y + bb.maxPoint.y) / 2
        dx = bb.maxPoint.x - bb.minPoint.x
        dy = bb.maxPoint.y - bb.minPoint.y
        if dx > dy:
            if cy < y_mid_val:
                b.name = f"{prefix}_Front"
            else:
                b.name = f"{prefix}_Back"
        else:
            if cx < x_mid_val:
                b.name = f"{prefix}_Left"
            else:
                b.name = f"{prefix}_Right"

    n = comp.bRepBodies.count
    names = [comp.bRepBodies.item(i).name for i in range(n)]
    print(f"  {prefix} dovetails done ({corners}-corner): {n} bodies -> {names}")
    return {"comp": comp, "occ": occ, "count": n, "names": names,
            "front": front, "back": back, "left": left, "right": right}


def run(context):
    for _mod in list(sys.modules):
        if _mod.startswith("woodworking") or _mod.startswith("helpers"):
            del sys.modules[_mod]

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import sp
    from woodworking.templates import dovetail

    ctx = sp.DesignContext(design)

    for i in range(params.count - 1, -1, -1):
        try:
            params.item(i).deleteMe()
        except Exception:
            pass

    def _add_param(name, expr, unit, comment):
        p = params.itemByName(name)
        if p is not None:
            try:
                p.expression = expr
            except Exception:
                pass
        else:
            params.add(name, VI(expr), unit, comment)

    _add_param("grid_x", "14 in", "in", "Grid X spacing")
    _add_param("grid_y", "12 in", "in", "Grid Y spacing")

    def slot(col, row):
        x_expr = "0 in" if col == 0 else f"{col} * grid_x"
        y_expr = "0 in" if row == 0 else f"{row} * grid_y"
        return x_expr, y_expr

    # ================================================================
    # B1 @ (0,0): 1-corner FLUSH (baseline regression test)
    # ================================================================
    print("=" * 50 + "\nB1: 1-corner flush 8x6x4\n" + "=" * 50)
    b1_x, b1_y = slot(0, 0)
    _add_param("b1_l", "8 in", "in", "B1 length")
    _add_param("b1_w", "6 in", "in", "B1 width")
    _add_param("b1_h", "4 in", "in", "B1 height")
    _add_param("b1_t", "0.5 in", "in", "B1 thickness")
    dovetail.define_params(params, prefix="dt1",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b1_h", thick_expr="b1_t")
    r1 = build_box(root, "B1", "b1_l", "b1_w", "b1_h", "b1_t",
                   b1_x, "dt1", ctx.ev, y_off_expr=b1_y, corners=1)
    assert r1["count"] == 2, f"B1: expected 2, got {r1['count']}"
    print("B1 FLUSH: PASS\n")

    # ================================================================
    # B16 @ (1,0): 1-corner PROUD 8x6x4, proud_offset = 0.04 in
    # ================================================================
    print("=" * 50 + "\nB16: 1-corner PROUD 8x6x4\n" + "=" * 50)
    b16_x, b16_y = slot(1, 0)
    _add_param("b16_l", "8 in", "in", "B16 length")
    _add_param("b16_w", "6 in", "in", "B16 width")
    _add_param("b16_h", "4 in", "in", "B16 height")
    _add_param("b16_t", "0.5 in", "in", "B16 thickness")
    _add_param("b16_proud", "0.04 in", "in", "B16 proud offset")
    dovetail.define_params(params, prefix="dt16",
        angle="8 deg", tail_w="0.75 in", tail_count="3",
        joint_h_expr="b16_h", thick_expr="b16_t",
        proud_offset="b16_proud")
    r16 = build_box(root, "B16", "b16_l", "b16_w", "b16_h", "b16_t",
                    b16_x, "dt16", ctx.ev, y_off_expr=b16_y, corners=1,
                    proud_offset_expr="b16_proud")
    assert r16["count"] == 2, f"B16: expected 2, got {r16['count']}"
    print("B16 PROUD 1-corner: PASS\n")

    # ================================================================
    # B17 @ (0,1): 4-corner PROUD 6x4x5, proud_offset = 0.03 in
    # ================================================================
    print("=" * 50 + "\nB17: 4-corner PROUD 6x4x5\n" + "=" * 50)
    b17_x, b17_y = slot(0, 1)
    _add_param("b17_l", "6 in", "in", "B17 length")
    _add_param("b17_w", "4 in", "in", "B17 width")
    _add_param("b17_h", "5 in", "in", "B17 height")
    _add_param("b17_t", "0.5 in", "in", "B17 thickness")
    _add_param("b17_proud", "0.03 in", "in", "B17 proud offset")
    dovetail.define_params(params, prefix="dv17",
        angle="8 deg", tail_w="0.625 in", tail_count="3",
        joint_h_expr="b17_h", thick_expr="b17_t",
        proud_offset="b17_proud")
    r17 = build_box(root, "B17", "b17_l", "b17_w", "b17_h", "b17_t",
                    b17_x, "dv17", ctx.ev, y_off_expr=b17_y, corners=4,
                    proud_offset_expr="b17_proud")
    assert r17["count"] == 4, f"B17: expected 4, got {r17['count']}"
    print("B17 PROUD 4-corner: PASS\n")

    # ── Fit view ──
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam

    print("=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)
