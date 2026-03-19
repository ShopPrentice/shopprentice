"""Test fixture for hardware templates: butt_hinge, pull, chest_lock.

Tests butt_hinge with 3 orientations + full pair(), pull, and lock.

Fixtures:
  H1: Hinge pair on XZ joint (box back-lid), barrel along X — pair()
  H2: Hinge pair on YZ joint (cabinet side-door), barrel along Z — pair()
  H3: Hinge pair on XY joint (drop-front), barrel along X — pair()
  P1: Bar pull on XZ face
  L1: Chest lock on front + keyhole + strike on lid

Expected bodies per component:
  H1: 2 boards + 2 plates + 5 knuckles + 1 pin = 10  (medium, 5-knuckle)
  H2: 2 boards + 2 plates + 5 knuckles + 1 pin = 10  (large, 5-knuckle)
  H3: 2 boards + 2 plates + 5 knuckles + 1 pin = 10  (medium, 5-knuckle)
  P1: 1 board + 1 pull handle = 2
  L1: 2 boards + 1 lock body + 1 strike plate = 4
  Total: 10 + 10 + 10 + 2 + 4 = 36
"""
import adsk.core
import adsk.fusion


def run(context):
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import af
    from helpers.templates import butt_hinge, pull, chest_lock

    ctx = af.DesignContext(design)

    # ================================================================
    # H1: Hinge pair — box back-lid joint (barrel along X)
    # Back board: XZ face at Y=5", lid: XY face at Z=4"
    # ================================================================
    print("=" * 50)
    print("H1: Back-lid hinge pair, barrel along X")
    print("=" * 50)

    params.add("h1_l", VI("8 in"), "in", "H1 box length")
    params.add("h1_w", VI("6 in"), "in", "H1 box width")
    params.add("h1_h", VI("4 in"), "in", "H1 box height")
    params.add("h1_bt", VI("0.5 in"), "in", "H1 board thick")
    params.add("h1_inset", VI("1.5 in"), "in", "H1 hinge inset")

    butt_hinge.define_params(params, prefix="bh1", size="medium")

    occ = af.make_comp(root, "H1")
    comp = occ.component

    # Back board (XZ at Y = h1_w - h1_bt)
    back_pl = af.off_plane(comp, comp.xZConstructionPlane,
                            "h1_w - h1_bt", "H1_BackPl")
    sk, pr = af.sketch_rect_model(comp, back_pl,
        ("0 in", "h1_w - h1_bt", "0 in"),
        {"x": "h1_l", "z": "h1_h"}, "H1_Back_Sk", ctx.ev)
    back = af.ext_new(comp, pr, "h1_bt", "H1_Back").bodies.item(0)
    back.name = "H1_Back"

    # Lid (XY at Z = h1_h)
    lid_pl = af.off_plane(comp, comp.xYConstructionPlane,
                           "h1_h", "H1_LidPl")
    sk, pr = af.sketch_rect_model(comp, lid_pl,
        ("0 in", "0 in", "h1_h"),
        {"x": "h1_l", "y": "h1_w"}, "H1_Lid_Sk", ctx.ev)
    lid = af.ext_new(comp, pr, "h1_bt", "H1_Lid").bodies.item(0)
    lid.name = "H1_Lid"

    result = butt_hinge.pair(comp,
        board_a=back, plane_a=back_pl,
        origin_a=("h1_inset", "h1_w - h1_bt", "h1_h - bh1_leaf_w"),
        size_a={"x": "bh1_l", "z": "bh1_leaf_w"},
        board_b=lid, plane_b=lid_pl,
        origin_b=("h1_inset", "h1_w - h1_bt - bh1_leaf_w", "h1_h"),
        size_b={"x": "bh1_l", "y": "bh1_leaf_w"},
        barrel_center=("h1_inset + bh1_l / 2", "h1_w", "h1_h + bh1_barrel_d / 2"),
        barrel_axis="x",
        prefix="bh1", name="H1", ev=ctx.ev,
        flip_a=True, flip_b=True)

    n = comp.bRepBodies.count
    names = [comp.bRepBodies.item(i).name for i in range(n)]
    print(f"  H1: {n} bodies -> {names}")
    assert n == 10, f"H1: expected 10, got {n}"
    print("  H1: PASS\n")

    # ================================================================
    # H2: Hinge pair — cabinet side-door joint (barrel along Z)
    # Side board: YZ face at X=10", door: YZ face at X=10"+bt
    # ================================================================
    print("=" * 50)
    print("H2: Side-door hinge pair, barrel along Z")
    print("=" * 50)

    params.add("h2_h", VI("12 in"), "in", "H2 cabinet height")
    params.add("h2_bt", VI("0.5 in"), "in", "H2 board thick")
    params.add("h2_door_w", VI("8 in"), "in", "H2 door width")
    params.add("h2_off_x", VI("h1_l + 2 in"), "in", "H2 X offset")
    params.add("h2_inset", VI("2 in"), "in", "H2 hinge inset from top/bottom")

    butt_hinge.define_params(params, prefix="bh2", size="large")

    occ2 = af.make_comp(root, "H2")
    comp2 = occ2.component

    # Side board (YZ at X = h2_off_x)
    side_pl = af.off_plane(comp2, comp2.yZConstructionPlane,
                            "h2_off_x", "H2_SidePl")
    sk, pr = af.sketch_rect_model(comp2, side_pl,
        ("h2_off_x", "0 in", "0 in"),
        {"y": "h2_bt", "z": "h2_h"}, "H2_Side_Sk", ctx.ev)
    side = af.ext_new(comp2, pr, "h2_bt", "H2_Side").bodies.item(0)
    side.name = "H2_Side"

    # Door (YZ at X = h2_off_x + h2_bt)
    door_pl = af.off_plane(comp2, comp2.yZConstructionPlane,
                            "h2_off_x + h2_bt", "H2_DoorPl")
    sk, pr = af.sketch_rect_model(comp2, door_pl,
        ("h2_off_x + h2_bt", "0 in", "0 in"),
        {"y": "h2_door_w", "z": "h2_h"}, "H2_Door_Sk", ctx.ev)
    door = af.ext_new(comp2, pr, "h2_bt", "H2_Door").bodies.item(0)
    door.name = "H2_Door"

    result2 = butt_hinge.pair(comp2,
        board_a=side, plane_a=side_pl,
        origin_a=("h2_off_x", "0 in", "h2_inset"),
        size_a={"y": "bh2_leaf_w", "z": "bh2_l"},
        board_b=door, plane_b=door_pl,
        origin_b=("h2_off_x + h2_bt", "0 in", "h2_inset"),
        size_b={"y": "bh2_leaf_w", "z": "bh2_l"},
        barrel_center=("h2_off_x + h2_bt / 2",
                       "0 in - bh2_barrel_d / 2",
                       "h2_inset + bh2_l / 2"),
        barrel_axis="z",
        prefix="bh2", name="H2", ev=ctx.ev,
        flip_a=False, flip_b=False)

    n = comp2.bRepBodies.count
    names = [comp2.bRepBodies.item(i).name for i in range(n)]
    print(f"  H2: {n} bodies -> {names}")
    assert n == 10, f"H2: expected 10, got {n}"
    print("  H2: PASS\n")

    # ================================================================
    # H3: Hinge pair — drop-front/desk lid (barrel along X, XY joint)
    # Fixed panel: XY at Z=0 (tabletop), Drop front: XZ at Y=0
    # ================================================================
    print("=" * 50)
    print("H3: Drop-front hinge pair, barrel along X, XY joint")
    print("=" * 50)

    params.add("h3_l", VI("10 in"), "in", "H3 panel length")
    params.add("h3_bt", VI("0.5 in"), "in", "H3 board thick")
    params.add("h3_off_y", VI("h1_w + 2 in"), "in", "H3 Y offset")
    params.add("h3_inset", VI("2 in"), "in", "H3 hinge inset")

    butt_hinge.define_params(params, prefix="bh3", size="medium")

    occ3 = af.make_comp(root, "H3")
    comp3 = occ3.component

    # Top panel (XY at Z=0)
    sk, pr = af.sketch_rect_model(comp3, comp3.xYConstructionPlane,
        ("0 in", "h3_off_y", "0 in"),
        {"x": "h3_l", "y": "6 in"}, "H3_Top_Sk", ctx.ev)
    top = af.ext_new(comp3, pr, "h3_bt", "H3_Top").bodies.item(0)
    top.name = "H3_Top"

    # Drop front (XZ at Y = h3_off_y, extending downward)
    front_pl3 = af.off_plane(comp3, comp3.xZConstructionPlane,
                              "h3_off_y", "H3_FrontPl")
    sk, pr = af.sketch_rect_model(comp3, front_pl3,
        ("0 in", "h3_off_y", "-8 in"),
        {"x": "h3_l", "z": "8 in"}, "H3_Front_Sk", ctx.ev)
    drop = af.ext_new(comp3, pr, "h3_bt", "H3_Drop").bodies.item(0)
    drop.name = "H3_Drop"

    result3 = butt_hinge.pair(comp3,
        board_a=top, plane_a=comp3.xYConstructionPlane,
        origin_a=("h3_inset", "h3_off_y", "0 in"),
        size_a={"x": "bh3_l", "y": "bh3_leaf_w"},
        board_b=drop, plane_b=front_pl3,
        origin_b=("h3_inset", "h3_off_y", "-bh3_leaf_w"),
        size_b={"x": "bh3_l", "z": "bh3_leaf_w"},
        barrel_center=("h3_inset + bh3_l / 2",
                       "h3_off_y - bh3_barrel_d / 2", "0 in"),
        barrel_axis="x",
        prefix="bh3", name="H3", ev=ctx.ev,
        flip_a=True, flip_b=True)

    n = comp3.bRepBodies.count
    names = [comp3.bRepBodies.item(i).name for i in range(n)]
    print(f"  H3: {n} bodies -> {names}")
    assert n == 10, f"H3: expected 10, got {n}"
    print("  H3: PASS\n")

    # ================================================================
    # P1: Bar pull on a drawer front
    # ================================================================
    print("=" * 50)
    print("P1: Bar pull on drawer front")
    print("=" * 50)

    params.add("p1_off_y", VI("h3_off_y + 10 in"), "in", "P1 Y offset")
    pull.define_params(params, prefix="pl", style="bar_3in")

    occ4 = af.make_comp(root, "P1")
    comp4 = occ4.component

    sk, pr = af.sketch_rect_model(comp4, comp4.xZConstructionPlane,
        ("0 in", "p1_off_y", "0 in"),
        {"x": "8 in", "z": "6 in"}, "P1_Front_Sk", ctx.ev)
    drawer_front = af.ext_new(comp4, pr, "0.75 in", "P1_Front").bodies.item(0)
    drawer_front.name = "P1_Front"

    p1_pl = af.off_plane(comp4, comp4.xZConstructionPlane,
                          "p1_off_y", "P1_Pl")
    pull.install(comp4, drawer_front, p1_pl,
        center=("4 in", "p1_off_y", "3 in"),
        pull_axis="x", depth_axis="y",
        prefix="pl", name="P1_Pull", ev=ctx.ev, flip=True,
        board_thick_expr="0.75 in")

    n = comp4.bRepBodies.count
    names = [comp4.bRepBodies.item(i).name for i in range(n)]
    print(f"  P1: {n} bodies -> {names}")
    assert n == 2, f"P1: expected 2, got {n}"
    print("  P1: PASS\n")

    # ================================================================
    # L1: Chest lock + keyhole + strike plate
    # ================================================================
    print("=" * 50)
    print("L1: Chest lock on front + keyhole + strike on lid")
    print("=" * 50)

    params.add("l1_off_x", VI("h2_off_x + 4 in"), "in", "L1 X offset")
    chest_lock.define_params(params, prefix="lk", size="small")

    occ5 = af.make_comp(root, "L1")
    comp5 = occ5.component

    # Front board
    front_pl5 = af.off_plane(comp5, comp5.xZConstructionPlane,
                              "p1_off_y", "L1_FrontPl")
    sk, pr = af.sketch_rect_model(comp5, front_pl5,
        ("l1_off_x", "p1_off_y", "0 in"),
        {"x": "6 in", "z": "4 in"}, "L1_Front_Sk", ctx.ev)
    l1_front = af.ext_new(comp5, pr, "0.5 in", "L1_Front").bodies.item(0)
    l1_front.name = "L1_Front"

    # Lid
    lid_pl5 = af.off_plane(comp5, comp5.xYConstructionPlane,
                             "4 in", "L1_LidPl")
    sk, pr = af.sketch_rect_model(comp5, lid_pl5,
        ("l1_off_x", "p1_off_y", "4 in"),
        {"x": "6 in", "y": "6 in"}, "L1_Lid_Sk", ctx.ev)
    l1_lid = af.ext_new(comp5, pr, "0.5 in", "L1_Lid").bodies.item(0)
    l1_lid.name = "L1_Lid"

    # Lock mortise on front inner face
    inner_pl5 = af.off_plane(comp5, comp5.xZConstructionPlane,
                              "p1_off_y + 0.5 in", "L1_InnerPl")
    chest_lock.lock_mortise(comp5, l1_front, inner_pl5,
        origin=("l1_off_x + 3 in - lk_w / 2", "p1_off_y + 0.5 in",
                "3 in"),
        size_map={"x": "lk_w", "z": "lk_h"},
        prefix="lk", name="L1_Lock", ev=ctx.ev, flip=True)

    # Keyhole through front
    chest_lock.keyhole(comp5, l1_front, front_pl5,
        center=("l1_off_x + 3 in", "p1_off_y", "3 in + lk_h / 2"),
        prefix="lk", name="L1_Lock", ev=ctx.ev, flip=True,
        board_thick_expr="0.5 in")

    # Strike plate on lid
    chest_lock.strike(comp5, l1_lid, lid_pl5,
        origin=("l1_off_x + 3 in - lk_strike_w / 2",
                "p1_off_y + 0.5 in", "4 in"),
        size_map={"x": "lk_strike_w", "y": "lk_strike_l"},
        prefix="lk", name="L1_Strike", ev=ctx.ev, flip=True)

    n = comp5.bRepBodies.count
    names = [comp5.bRepBodies.item(i).name for i in range(n)]
    print(f"  L1: {n} bodies -> {names}")
    assert n == 4, f"L1: expected 4, got {n}"
    print("  L1: PASS\n")

    # ================================================================
    # Summary
    # ================================================================
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)

    total = 0
    for occ_item in root.occurrences:
        c = occ_item.component
        n = c.bRepBodies.count
        body_names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {body_names}")
        total += n

    expected = 10 + 10 + 10 + 2 + 4  # 36
    status = "PASS" if total == expected else "FAIL"
    print(f"\n{status}: expected {expected}, got {total}")

    # Hide construction
    for occ_item in root.occurrences:
        c = occ_item.component
        for sk_item in c.sketches:
            sk_item.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
