"""Test fixture for finger joint (box joint) template.

Tests define_params (derived count via floor) and box() with 6 configs:
  B1: 1-corner finger joint (2 boards: front + left)
  B2: 2-corner finger joints (3 boards: front + left + right)
  B3: 4-corner finger joints, joint along Z (default)
  B4: 4-corner, narrow fingers (finger_w < board_thick)
  B5: 4-corner, joint along X (box "lying flat")
  B6: 4-corner, joint along Y (box "on its side")

Count is derived: floor(joint_h / (2 * finger_w)) keeps all fingers within the board.
The pin board's last finger fills the remaining gap (may be wider than finger_w).

Each box is in its own component. For 2+ corners, right finger board
is created by mirroring left across x_mid.

Total: 2 + 3 + 4 + 4 + 4 + 4 = 21 bodies.
"""
import adsk.core
import adsk.fusion


def build_box(root, prefix, l_expr, w_expr, h_expr, t_expr,
              x_off_expr, fj_prefix, ev, y_off_expr="0 in",
              corners=4, joint_axis="z", thick_axis="y"):
    """Build a box with finger joints.

    Args:
        root: Root component.
        prefix: Name prefix.
        l_expr, w_expr, h_expr, t_expr: Dimension parameter expressions.
        x_off_expr: X offset expression.
        fj_prefix: Finger joint parameter prefix.
        ev: Evaluator function.
        y_off_expr: Y offset expression.
        corners: 4 = all corners, 2 = front corners only, 1 = FL corner only.
        joint_axis: Axis along which fingers repeat.
        thick_axis: Axis along which slot board thickness runs.

    Returns:
        Dict with component, bodies, and body count.
    """
    from helpers import sp
    from woodworking.templates import finger_joint

    occ = sp.make_comp(root, prefix)
    comp = occ.component

    ox = ev(x_off_expr) if x_off_expr != "0 in" else 0.0
    oy = ev(y_off_expr) if y_off_expr != "0 in" else 0.0

    # For non-standard axis orientations, swap board construction
    if joint_axis == "z" and thick_axis == "y":
        # Standard: front/back span X×Z, left/right span Y×Z
        _build_standard(comp, root, prefix, l_expr, w_expr, h_expr, t_expr,
                        x_off_expr, y_off_expr, fj_prefix, ev, corners,
                        joint_axis, thick_axis, ox, oy)
    elif joint_axis == "x" and thick_axis == "z":
        _build_x_joint(comp, root, prefix, l_expr, w_expr, h_expr, t_expr,
                        x_off_expr, y_off_expr, fj_prefix, ev, corners, ox, oy)
    elif joint_axis == "y" and thick_axis == "x":
        _build_y_joint(comp, root, prefix, l_expr, w_expr, h_expr, t_expr,
                        x_off_expr, y_off_expr, fj_prefix, ev, corners, ox, oy)

    n = comp.bRepBodies.count
    names = [comp.bRepBodies.item(i).name for i in range(n)]
    print(f"  {prefix} finger joints done ({corners}-corner): {n} bodies -> {names}")
    return {"comp": comp, "occ": occ, "count": n, "names": names}


def _build_standard(comp, root, prefix, l_expr, w_expr, h_expr, t_expr,
                    x_off_expr, y_off_expr, fj_prefix, ev, corners,
                    joint_axis, thick_axis, ox, oy):
    """Standard box: joint along Z, thick along Y."""
    from helpers import sp
    from woodworking.templates import finger_joint

    front_y_expr = y_off_expr
    back_y_expr = (f"{y_off_expr} + {w_expr} - {t_expr}"
                   if oy != 0.0 else f"{w_expr} - {t_expr}")
    tail_y_expr = f"{y_off_expr} + {t_expr}" if oy != 0.0 else t_expr
    tail_w_expr = f"{w_expr} - 2 * {t_expr}"

    # Front (slot board)
    if oy == 0.0:
        front_sk_pl = comp.xZConstructionPlane
    else:
        front_sk_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                                    y_off_expr, f"{prefix}_FrontYPl")

    sk, pr = sp.sketch_rect_model(comp, front_sk_pl,
        (x_off_expr, front_y_expr, "0 in"),
        {"x": l_expr, "z": h_expr}, f"{prefix}_Front_Sk", ev)
    front = sp.ext_new(comp, pr, t_expr, f"{prefix}_Front").bodies.item(0)
    front.name = f"{prefix}_Front"

    # Back (slot board, only for 4-corner)
    back = None
    if corners == 4:
        back_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                               back_y_expr, f"{prefix}_Back_Pl")
        sk, pr = sp.sketch_rect_model(comp, back_pl,
            (x_off_expr, back_y_expr, "0 in"),
            {"x": l_expr, "z": h_expr}, f"{prefix}_Back_Sk", ev)
        back = sp.ext_new(comp, pr, t_expr, f"{prefix}_Back").bodies.item(0)
        back.name = f"{prefix}_Back"

    # Midplanes
    x_mid_expr = (f"{x_off_expr} + {l_expr} / 2"
                  if ox != 0.0 else f"{l_expr} / 2")
    y_mid_expr = (f"{y_off_expr} + {w_expr} / 2"
                  if oy != 0.0 else f"{w_expr} / 2")

    x_mid = sp.off_plane(comp, comp.yZConstructionPlane,
                          x_mid_expr, f"{prefix}_XMid")
    y_mid = sp.off_plane(comp, comp.xZConstructionPlane,
                          y_mid_expr, f"{prefix}_YMid")

    # Left (finger board, narrower)
    if ox == 0.0:
        left_pl = comp.yZConstructionPlane
    else:
        left_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                               x_off_expr, f"{prefix}_Left_Pl")

    sk, pr = sp.sketch_rect_model(comp, left_pl,
        (x_off_expr, tail_y_expr, "0 in"),
        {"y": tail_w_expr, "z": h_expr}, f"{prefix}_Left_Sk", ev)
    left = sp.ext_new(comp, pr, t_expr, f"{prefix}_Left").bodies.item(0)
    left.name = f"{prefix}_Left"

    # Right (finger board via mirror, only for 2+ corners)
    right = None
    if corners >= 2:
        right_mir = sp.mirror_body(comp, left, x_mid, f"{prefix}_RightMir")
        right = right_mir.bodies.item(0)
        right.name = f"{prefix}_Right"

    # Finger joints
    finger_joint.box(comp, front, left,
                     x_mid, y_mid, thick_expr=t_expr,
                     right=right, back=back,
                     prefix=fj_prefix, name=prefix, ev=ev,
                     fl_plane=left_pl,
                     front_expr=front_y_expr,
                     joint_axis=joint_axis, thick_axis=thick_axis)


def _build_x_joint(comp, root, prefix, l_expr, w_expr, h_expr, t_expr,
                   x_off_expr, y_off_expr, fj_prefix, ev, corners, ox, oy):
    """Box with joint along X, thick along Z (lying flat)."""
    from helpers import sp
    from woodworking.templates import finger_joint

    # Front/back: span X×Y, thin in Z
    sk, pr = sp.sketch_rect_model(comp, comp.xYConstructionPlane,
        (x_off_expr, y_off_expr, "0 in"),
        {"x": l_expr, "y": w_expr}, f"{prefix}_Front_Sk", ev)
    front = sp.ext_new(comp, pr, t_expr, f"{prefix}_Front").bodies.item(0)
    front.name = f"{prefix}_Front"

    back_pl = sp.off_plane(comp, comp.xYConstructionPlane,
                            f"{h_expr} - {t_expr}", f"{prefix}_Back_Pl")
    sk, pr = sp.sketch_rect_model(comp, back_pl,
        (x_off_expr, y_off_expr, f"{h_expr} - {t_expr}"),
        {"x": l_expr, "y": w_expr}, f"{prefix}_Back_Sk", ev)
    back = sp.ext_new(comp, pr, t_expr, f"{prefix}_Back").bodies.item(0)
    back.name = f"{prefix}_Back"

    # Left/right: span X×Z, thin in Y, narrower in Z
    ext_mid = sp.off_plane(comp, comp.xZConstructionPlane,
                            f"{y_off_expr} + {w_expr} / 2"
                            if oy != 0.0 else f"{w_expr} / 2",
                            f"{prefix}_ExtMid")
    thick_mid = sp.off_plane(comp, comp.xYConstructionPlane,
                              f"{h_expr} / 2", f"{prefix}_ThickMid")

    left_pl = sp.off_plane(comp, comp.xZConstructionPlane,
                            y_off_expr if oy != 0.0 else "0 in",
                            f"{prefix}_Left_Pl")
    sk, pr = sp.sketch_rect_model(comp, left_pl,
        (x_off_expr, y_off_expr, t_expr),
        {"x": l_expr, "z": f"{h_expr} - 2 * {t_expr}"},
        f"{prefix}_Left_Sk", ev)
    left = sp.ext_new(comp, pr, t_expr, f"{prefix}_Left").bodies.item(0)
    left.name = f"{prefix}_Left"

    right_mir = sp.mirror_body(comp, left, ext_mid, f"{prefix}_RightMir")
    right = right_mir.bodies.item(0)
    right.name = f"{prefix}_Right"

    finger_joint.box(comp, front, left,
                     ext_mid, thick_mid, thick_expr=t_expr,
                     right=right, back=back,
                     prefix=fj_prefix, name=prefix, ev=ev,
                     fl_plane=left_pl,
                     front_expr="0 in",
                     joint_axis="x", thick_axis="z")


def _build_y_joint(comp, root, prefix, l_expr, w_expr, h_expr, t_expr,
                   x_off_expr, y_off_expr, fj_prefix, ev, corners, ox, oy):
    """Box with joint along Y, thick along X (on its side)."""
    from helpers import sp
    from woodworking.templates import finger_joint

    # Front/back: span Y×Z, thin in X
    front_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                             x_off_expr, f"{prefix}_Front_Pl")
    sk, pr = sp.sketch_rect_model(comp, front_pl,
        (x_off_expr, y_off_expr, "0 in"),
        {"y": w_expr, "z": h_expr}, f"{prefix}_Front_Sk", ev)
    front = sp.ext_new(comp, pr, t_expr, f"{prefix}_Front").bodies.item(0)
    front.name = f"{prefix}_Front"

    back_pl = sp.off_plane(comp, comp.yZConstructionPlane,
                            f"{x_off_expr} + {l_expr} - {t_expr}"
                            if ox != 0.0 else f"{l_expr} - {t_expr}",
                            f"{prefix}_Back_Pl")
    sk, pr = sp.sketch_rect_model(comp, back_pl,
        (f"{x_off_expr} + {l_expr} - {t_expr}" if ox != 0.0
         else f"{l_expr} - {t_expr}",
         y_off_expr, "0 in"),
        {"y": w_expr, "z": h_expr}, f"{prefix}_Back_Sk", ev)
    back = sp.ext_new(comp, pr, t_expr, f"{prefix}_Back").bodies.item(0)
    back.name = f"{prefix}_Back"

    # Left/right: span X×Y, thin in Z, narrower in X
    z_mid = sp.off_plane(comp, comp.xYConstructionPlane,
                          f"{h_expr} / 2", f"{prefix}_ZMid")
    x_mid = sp.off_plane(comp, comp.yZConstructionPlane,
                          f"{x_off_expr} + {l_expr} / 2"
                          if ox != 0.0 else f"{l_expr} / 2",
                          f"{prefix}_XMid")

    sk, pr = sp.sketch_rect_model(comp, comp.xYConstructionPlane,
        (f"{x_off_expr} + {t_expr}" if ox != 0.0 else t_expr,
         y_off_expr, "0 in"),
        {"x": f"{l_expr} - 2 * {t_expr}", "y": w_expr},
        f"{prefix}_Left_Sk", ev)
    left = sp.ext_new(comp, pr, t_expr, f"{prefix}_Left").bodies.item(0)
    left.name = f"{prefix}_Left"

    right_mir = sp.mirror_body(comp, left, z_mid, f"{prefix}_RightMir")
    right = right_mir.bodies.item(0)
    right.name = f"{prefix}_Right"

    finger_joint.box(comp, front, left,
                     z_mid, x_mid, thick_expr=t_expr,
                     right=right, back=back,
                     prefix=fj_prefix, name=prefix, ev=ev,
                     fl_plane=comp.xYConstructionPlane,
                     front_expr=x_off_expr,
                     joint_axis="y", thick_axis="x",
                     joint_base_expr=y_off_expr
                     if y_off_expr != "0 in" else None)


def run(context):
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import sp
    from woodworking.templates import finger_joint

    ctx = sp.DesignContext(design)

    # ================================================================
    # FIXTURE 1: 1-corner — 8x6x4, 0.5" thick, 0.375" fingers
    # ================================================================
    print("=" * 50)
    print("FIXTURE 1: 1-corner box 8x6x4, 0.375\" fingers")
    print("=" * 50)

    params.add("b1_l", VI("8 in"), "in", "Box 1 length")
    params.add("b1_w", VI("6 in"), "in", "Box 1 width")
    params.add("b1_h", VI("4 in"), "in", "Box 1 height")
    params.add("b1_t", VI("0.5 in"), "in", "Box 1 thickness")

    finger_joint.define_params(params, prefix="fj1",
        finger_w="0.375 in",
        joint_h_expr="b1_h", thick_expr="b1_t")

    r1 = build_box(root, "B1", "b1_l", "b1_w", "b1_h", "b1_t",
                   "0 in", "fj1", ctx.ev, corners=1)
    assert r1["count"] == 2, f"Box 1: expected 2, got {r1['count']}"
    print("Box 1: PASS\n")

    # ================================================================
    # FIXTURE 2: 2-corner — 8x5x6, 0.5" thick, 0.375" fingers
    # ================================================================
    print("=" * 50)
    print("FIXTURE 2: 2-corner box 8x5x6, 0.375\" fingers")
    print("=" * 50)

    params.add("b2_l", VI("8 in"), "in", "Box 2 length")
    params.add("b2_w", VI("5 in"), "in", "Box 2 width")
    params.add("b2_h", VI("6 in"), "in", "Box 2 height")
    params.add("b2_t", VI("0.5 in"), "in", "Box 2 thickness")
    params.add("b2_y", VI("b1_w + 2 in"), "in", "Box 2 Y offset")

    finger_joint.define_params(params, prefix="fj2",
        finger_w="0.375 in",
        joint_h_expr="b2_h", thick_expr="b2_t")

    r2 = build_box(root, "B2", "b2_l", "b2_w", "b2_h", "b2_t",
                   "0 in", "fj2", ctx.ev, y_off_expr="b2_y",
                   corners=2)
    assert r2["count"] == 3, f"Box 2: expected 3, got {r2['count']}"
    print("Box 2: PASS\n")

    # ================================================================
    # FIXTURE 3: 4-corner — 10x8x6, 0.5" thick, 0.5" fingers
    # ================================================================
    print("=" * 50)
    print("FIXTURE 3: 4-corner box 10x8x6, 0.5\" fingers")
    print("=" * 50)

    params.add("b3_l", VI("10 in"), "in", "Box 3 length")
    params.add("b3_w", VI("8 in"), "in", "Box 3 width")
    params.add("b3_h", VI("6 in"), "in", "Box 3 height")
    params.add("b3_t", VI("0.5 in"), "in", "Box 3 thickness")
    params.add("b3_y", VI("b2_y + b2_w + 2 in"), "in", "Box 3 Y offset")

    finger_joint.define_params(params, prefix="fj3",
        finger_w="0.5 in",
        joint_h_expr="b3_h", thick_expr="b3_t")

    r3 = build_box(root, "B3", "b3_l", "b3_w", "b3_h", "b3_t",
                   "0 in", "fj3", ctx.ev, y_off_expr="b3_y")
    assert r3["count"] == 4, f"Box 3: expected 4, got {r3['count']}"
    print("Box 3: PASS\n")

    # ================================================================
    # FIXTURE 4: 4-corner — narrow fingers (0.25" wide, 0.75" thick)
    # ================================================================
    print("=" * 50)
    print("FIXTURE 4: 4-corner, narrow fingers 0.25\" wide")
    print("=" * 50)

    params.add("b4_l", VI("6 in"), "in", "Box 4 length")
    params.add("b4_w", VI("4 in"), "in", "Box 4 width")
    params.add("b4_h", VI("5 in"), "in", "Box 4 height")
    params.add("b4_t", VI("0.75 in"), "in", "Box 4 thickness")
    params.add("b4_x", VI("b3_l + 2 in"), "in", "Box 4 X offset")

    finger_joint.define_params(params, prefix="fj4",
        finger_w="0.25 in",
        joint_h_expr="b4_h", thick_expr="b4_t")

    r4 = build_box(root, "B4", "b4_l", "b4_w", "b4_h", "b4_t",
                   "b4_x", "fj4", ctx.ev, y_off_expr="b3_y")
    assert r4["count"] == 4, f"Box 4: expected 4, got {r4['count']}"
    print("Box 4: PASS\n")

    # ================================================================
    # FIXTURE 5: 4-corner — joint along X, thick along Z (lying flat)
    # ================================================================
    print("=" * 50)
    print("FIXTURE 5: 4-corner, joint along X, 7x5x3")
    print("=" * 50)

    params.add("b5_l", VI("7 in"), "in", "Box 5 length (X)")
    params.add("b5_w", VI("5 in"), "in", "Box 5 width (Y)")
    params.add("b5_h", VI("3 in"), "in", "Box 5 height (Z)")
    params.add("b5_t", VI("0.5 in"), "in", "Box 5 thickness")
    params.add("b5_y", VI("b3_y + b3_w + 2 in"), "in", "Box 5 Y offset")

    finger_joint.define_params(params, prefix="fj5",
        finger_w="0.375 in",
        joint_h_expr="b5_l", thick_expr="b5_t")

    r5 = build_box(root, "B5", "b5_l", "b5_w", "b5_h", "b5_t",
                   "0 in", "fj5", ctx.ev, y_off_expr="b5_y",
                   joint_axis="x", thick_axis="z")
    assert r5["count"] == 4, f"Box 5: expected 4, got {r5['count']}"
    print("Box 5: PASS\n")

    # ================================================================
    # FIXTURE 6: 4-corner — joint along Y, thick along X (on its side)
    # ================================================================
    print("=" * 50)
    print("FIXTURE 6: 4-corner, joint along Y, 6x8x5")
    print("=" * 50)

    params.add("b6_l", VI("6 in"), "in", "Box 6 length (X)")
    params.add("b6_w", VI("8 in"), "in", "Box 6 width (Y)")
    params.add("b6_h", VI("5 in"), "in", "Box 6 height (Z)")
    params.add("b6_t", VI("0.5 in"), "in", "Box 6 thickness")
    params.add("b6_x", VI("b5_l + 2 in"), "in", "Box 6 X offset")
    params.add("b6_y", VI("b5_y"), "in", "Box 6 Y offset")

    finger_joint.define_params(params, prefix="fj6",
        finger_w="0.375 in",
        joint_h_expr="b6_w", thick_expr="b6_t")

    r6 = build_box(root, "B6", "b6_l", "b6_w", "b6_h", "b6_t",
                   "b6_x", "fj6", ctx.ev, y_off_expr="b6_y",
                   joint_axis="y", thick_axis="x")
    assert r6["count"] == 4, f"Box 6: expected 4, got {r6['count']}"
    print("Box 6: PASS\n")

    # ================================================================
    # Summary
    # ================================================================
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)

    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n

    expected = 2 + 3 + 4 + 4 + 4 + 4  # 21
    status = "PASS" if total == expected else "FAIL"
    print(f"\n{status}: expected {expected} bodies, got {total}")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
