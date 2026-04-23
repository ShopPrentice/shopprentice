"""Test fixture for domino joint template.

Tests 4 real-world use cases:
  F1 M&T_Replacement: Seat + 4 posts using four_corners. 9 bodies in 1 comp.
  F2 Edge_Joint: Two boards edge-joined with grid dominos,
                 wide face parallel to board surface. 5 bodies in 1 comp.
  F3 Case_Joint: Box side-to-back connection (like bookshelf). 4 bodies in 1 comp.
  F4 Cross_Edge_Joint: Same as F2 but Left and Right live in separate
                       root components. Exercises grid()'s cross-component
                       routing via combine. 5 bodies across 3 comps.

Total: 9 + 5 + 4 + 5 = 23 bodies.
"""
import adsk.core
import adsk.fusion


def make_comp_at(root, name, x_cm=0.0):
    """Create a component at the given X world position."""
    xf = adsk.core.Matrix3D.create()
    if x_cm != 0.0:
        xf.setCell(0, 3, x_cm)
    occ = root.occurrences.addNewComponent(xf)
    occ.component.name = name
    return occ


def run(context):
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import sp
    from woodworking.templates import domino

    ctx = sp.DesignContext(design)

    # ═══════════════════════════════════════════════════════════════════
    # F1: M&T Replacement — seat + 4 posts, four_corners domino
    # ═══════════════════════════════════════════════════════════════════
    params.add("seat_w", VI("12 in"), "in", "Seat width")
    params.add("seat_d", VI("10 in"), "in", "Seat depth")
    params.add("seat_t", VI("1 in"), "in", "Seat thickness")
    params.add("post_w", VI("1.5 in"), "in", "Post width")
    params.add("post_h", VI("4 in"), "in", "Post height")
    params.add("post_inset", VI("2 in"), "in", "Post inset from edge")
    # Standard 8mm domino: 8×40mm, 20mm depth
    params.add("dm1_w", VI("40 mm"), "in", "F1 domino width (long)")
    params.add("dm1_t", VI("8 mm"), "in", "F1 domino thickness (short)")
    params.add("dm1_d", VI("20 mm"), "in", "F1 domino depth per side")

    f1 = make_comp_at(root, "MT_Replacement").component

    # Seat — sits on top of legs at Z = post_h
    seat_pl = sp.off_plane(f1, f1.xYConstructionPlane, "post_h", "f1_Seat_Pl")
    _, pr = sp.sketch_rect_model(f1, seat_pl,
        ("0 in", "0 in", "post_h"),
        {"x": "seat_w", "y": "seat_d"}, "f1_Seat_Sk", ctx.ev)
    seat = sp.ext_new(f1, pr, "seat_t", "f1_Seat").bodies.item(0)
    seat.name = "f1_Seat"

    # 4 posts
    def make_post(comp, x_expr, y_expr, name):
        _, pr = sp.sketch_rect_model(comp, comp.xYConstructionPlane,
            (x_expr, y_expr, "0 in"),
            {"x": "post_w", "y": "post_w"}, f"{name}_Sk", ctx.ev)
        b = sp.ext_new(comp, pr, "post_h", name).bodies.item(0)
        b.name = name
        return b

    post_nl = make_post(f1, "post_inset - post_w / 2",
                        "post_inset - post_w / 2", "f1_Post_NL")
    post_nr = make_post(f1, "seat_w - post_inset - post_w / 2",
                        "post_inset - post_w / 2", "f1_Post_NR")
    post_fl = make_post(f1, "post_inset - post_w / 2",
                        "seat_d - post_inset - post_w / 2", "f1_Post_FL")
    post_fr = make_post(f1, "seat_w - post_inset - post_w / 2",
                        "seat_d - post_inset - post_w / 2", "f1_Post_FR")

    XMid = sp.off_plane(f1, f1.yZConstructionPlane, "seat_w / 2", "f1_XMid")
    YMid = sp.off_plane(f1, f1.xZConstructionPlane, "seat_d / 2", "f1_YMid")

    domino.four_corners(f1, seat_pl,
        center=("post_inset", "post_inset", "post_h"),
        long_axis="x", long_expr="dm1_w", short_expr="dm1_t",
        depth_expr="dm1_d", top_body=seat,
        leg_bodies=[post_nl, post_nr, post_fl, post_fr],
        x_mid=XMid, y_mid=YMid,
        name="f1_DM", ev=ctx.ev)

    assert f1.bRepBodies.count == 9
    print("MT_Replacement: 9 bodies — PASS")

    # ═══════════════════════════════════════════════════════════════════
    # F2: Edge Joint — two boards edge-joined, dominos align them.
    #     Wide face of domino parallel to board surface.
    #     Boards are flat panels on XY plane (thickness along Z).
    #     Joint at Y boundary. Domino long axis = X (parallel to surface).
    # ═══════════════════════════════════════════════════════════════════
    params.add("ej_board_w", VI("18 in"), "in", "Edge joint board width (X)")
    params.add("ej_board_d", VI("6 in"), "in", "Edge joint board depth (Y)")
    params.add("ej_board_t", VI("0.75 in"), "in", "Edge joint board thick (Z)")
    # Standard 8mm domino: 8×40mm, depth limited by 0.75" board
    params.add("dm2_w", VI("40 mm"), "in", "F2 domino width (long)")
    params.add("dm2_t", VI("8 mm"), "in", "F2 domino thickness (short)")
    params.add("dm2_d", VI("15 mm"), "in", "F2 domino depth per side")
    params.add("dm2_count", VI("3"), "", "F2 domino count")
    params.add("dm2_sp", VI("6 in"), "in", "F2 domino spacing")
    params.add("f2_x", VI("seat_w + 3 in"), "in", "F2 X offset")

    f2 = make_comp_at(root, "Edge_Joint", ctx.ev("f2_x")).component

    # Left board
    _, pr = sp.sketch_rect_model(f2, f2.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "ej_board_w", "y": "ej_board_d"}, "f2_Left_Sk", ctx.ev)
    left = sp.ext_new(f2, pr, "ej_board_t", "f2_Left").bodies.item(0)
    left.name = "f2_Left"

    # Right board (adjacent along Y)
    _, pr = sp.sketch_rect_model(f2, f2.xYConstructionPlane,
        ("0 in", "ej_board_d", "0 in"),
        {"x": "ej_board_w", "y": "ej_board_d"}, "f2_Right_Sk", ctx.ev)
    right = sp.ext_new(f2, pr, "ej_board_t", "f2_Right").bodies.item(0)
    right.name = "f2_Right"

    # Joint plane at Y = ej_board_d
    joint_pl = sp.off_plane(f2, f2.xZConstructionPlane,
                             "ej_board_d", "f2_Joint_Pl")

    # Grid of dominos — long_axis="x" so wide face is parallel to
    # the board surface (XY plane). Dominos step along X.
    # Start at center of board thickness, offset from board left edge.
    grid_bodies = domino.grid(f2, joint_pl,
        start=("3 in", "ej_board_d", "ej_board_t / 2"),
        step_axis="x", step_expr="dm2_sp",
        count_expr="dm2_count",
        long_axis="x", long_expr="dm2_w",
        short_expr="dm2_t", depth_expr="dm2_d",
        body_a=left, body_b=right,
        name="f2_DM", ev=ctx.ev)

    assert f2.bRepBodies.count == 5
    print("Edge_Joint: 5 bodies — PASS")

    # ═══════════════════════════════════════════════════════════════════
    # F3: Case Joint — box side-to-back (like bookshelf).
    #     Side board (XZ plane) meets back board (YZ plane) at right angle.
    #     Dominos connect side's back edge to back board's inner face.
    # ═══════════════════════════════════════════════════════════════════
    params.add("case_w", VI("12 in"), "in", "Case width (X)")
    params.add("case_h", VI("10 in"), "in", "Case height (Z)")
    params.add("case_d", VI("8 in"), "in", "Case depth (Y)")
    params.add("side_t", VI("0.75 in"), "in", "Side board thickness")
    params.add("back_t", VI("0.5 in"), "in", "Back board thickness")
    # Standard 6mm domino: 6×40mm, depth limited by 0.5" back
    params.add("dm3_w", VI("40 mm"), "in", "F3 domino width (long)")
    params.add("dm3_t", VI("6 mm"), "in", "F3 domino thickness (short)")
    params.add("dm3_d", VI("10 mm"), "in", "F3 domino depth per side")
    params.add("dm3_count", VI("2"), "", "F3 domino count")
    params.add("dm3_sp", VI("4 in"), "in", "F3 domino spacing")
    params.add("f3_x", VI("f2_x + ej_board_w + 3 in"), "in", "F3 X offset")

    f3 = make_comp_at(root, "Case_Joint", ctx.ev("f3_x")).component

    # Left side board (XZ face, extruded along Y for full depth)
    _, pr = sp.sketch_rect_model(f3, f3.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "side_t", "z": "case_h"}, "f3_Side_Sk", ctx.ev)
    side = sp.ext_new(f3, pr, "case_d", "f3_Side").bodies.item(0)
    side.name = "f3_Side"

    # Back board — sits between the sides, touching at X = side_t.
    # No overlap: back starts at X = side_t, side ends at X = side_t.
    back_pl = sp.off_plane(f3, f3.yZConstructionPlane, "side_t", "f3_Back_Pl")
    _, pr = sp.sketch_rect_model(f3, back_pl,
        ("side_t", "case_d - back_t", "0 in"),
        {"y": "back_t", "z": "case_h"}, "f3_Back_Sk", ctx.ev)
    back = sp.ext_new(f3, pr, "case_w - 2 * side_t", "f3_Back").bodies.item(0)
    back.name = "f3_Back"

    # Joint plane at X = side_t (mating surface between side and back).
    # Dominos bridge side (penetrate toward -X) and back (toward +X).
    # Long axis = Z (parallel to both board surfaces at the joint).
    case_joint_pl = sp.off_plane(f3, f3.yZConstructionPlane,
                                  "side_t", "f3_CaseJoint_Pl")

    # Domino center at Y = case_d - back_t / 2 (centered in back thickness).
    # Start near bottom, step upward along Z.
    grid_bodies = domino.grid(f3, case_joint_pl,
        start=("side_t", "case_d - back_t / 2", "3 in"),
        step_axis="z", step_expr="dm3_sp",
        count_expr="dm3_count",
        long_axis="z", long_expr="dm3_w",
        short_expr="dm3_t", depth_expr="dm3_d",
        body_a=side, body_b=back,
        name="f3_DM", ev=ctx.ev)

    assert f3.bRepBodies.count == 4
    print("Case_Joint: 4 bodies — PASS")

    # ═══════════════════════════════════════════════════════════════════
    # F4: Cross-component Edge Joint — like F2 but Left board, Right
    #     board, and the grid voids live in SEPARATE root components.
    #     Exercises grid()'s cross-component CUTs via combine.
    # ═══════════════════════════════════════════════════════════════════
    params.add("f4_x", VI("f3_x + case_w + 3 in"), "in", "F4 X offset")
    f4_x = ctx.ev("f4_x")

    # Three sibling components under root, each at the same world X so
    # the boards abut along Y at a common interface (ej_board_d).
    f4_L = make_comp_at(root, "F4_Left", f4_x).component
    f4_R = make_comp_at(root, "F4_Right", f4_x).component
    f4_V = make_comp_at(root, "F4_Voids", f4_x).component

    # Left board in F4_Left
    _, pr = sp.sketch_rect_model(f4_L, f4_L.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "ej_board_w", "y": "ej_board_d"}, "f4_Left_Sk", ctx.ev)
    f4_left = sp.ext_new(f4_L, pr, "ej_board_t", "f4_Left").bodies.item(0)
    f4_left.name = "f4_Left"

    # Right board in F4_Right (adjacent along Y)
    _, pr = sp.sketch_rect_model(f4_R, f4_R.xYConstructionPlane,
        ("0 in", "ej_board_d", "0 in"),
        {"x": "ej_board_w", "y": "ej_board_d"}, "f4_Right_Sk", ctx.ev)
    f4_right = sp.ext_new(f4_R, pr, "ej_board_t", "f4_Right").bodies.item(0)
    f4_right.name = "f4_Right"

    # Voids live in F4_Voids — a third sibling component. The grid()
    # call uses comp=f4_V for sketch+extrude+pattern. CUTs into
    # f4_left (F4_Left comp) and f4_right (F4_Right comp) must route
    # to root via combine.
    f4_joint_pl = sp.off_plane(f4_V, f4_V.xZConstructionPlane,
                                "ej_board_d", "f4_Joint_Pl")
    domino.grid(f4_V, f4_joint_pl,
        start=("3 in", "ej_board_d", "ej_board_t / 2"),
        step_axis="x", step_expr="dm2_sp",
        count_expr="dm2_count",
        long_axis="x", long_expr="dm2_w",
        short_expr="dm2_t", depth_expr="dm2_d",
        body_a=f4_left, body_b=f4_right,
        name="f4_DM", ev=ctx.ev)

    assert f4_L.bRepBodies.count == 1, \
        f"F4_Left expected 1 body, got {f4_L.bRepBodies.count}"
    assert f4_R.bRepBodies.count == 1, \
        f"F4_Right expected 1 body, got {f4_R.bRepBodies.count}"
    assert f4_V.bRepBodies.count == 3, \
        f"F4_Voids expected 3 bodies, got {f4_V.bRepBodies.count}"
    print("Cross_Edge_Joint: 5 bodies across 3 comps — PASS")

    # ── Summary ──
    total = 0
    for occ in root.occurrences:
        c = occ.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {names}")
        total += n
    print(f"\n{'PASS' if total == 23 else 'FAIL'}: {total}/23 bodies")

    for occ in root.occurrences:
        c = occ.component
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
