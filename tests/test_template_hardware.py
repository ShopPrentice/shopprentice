"""Test fixture for remaining inline hardware templates: pull and chest_lock.

Fixtures:
  P1: Bar pull on XZ face
  L1: Chest lock on front + keyhole + strike on lid

Expected bodies per component:
  P1: 1 board + 1 pull handle = 2
  L1: 2 boards + 1 lock body + 1 strike plate = 4
  Total: 6
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

    from helpers import sp
    from woodworking.templates import pull, chest_lock

    ctx = sp.DesignContext(design)

    # ================================================================
    # P1: Bar pull on a drawer front
    # ================================================================
    print("=" * 50)
    print("P1: Bar pull on drawer front")
    print("=" * 50)

    params.add("p1_off_y", VI("10 in"), "in", "P1 Y offset")
    pull.define_params(params, prefix="pl", style="bar_3in")

    occ1 = sp.make_comp(root, "P1")
    comp1 = occ1.component

    sk, pr = sp.sketch_rect_model(comp1, comp1.xZConstructionPlane,
        ("0 in", "p1_off_y", "0 in"),
        {"x": "8 in", "z": "6 in"}, "P1_Front_Sk", ctx.ev)
    drawer_front = sp.ext_new(comp1, pr, "0.75 in", "P1_Front").bodies.item(0)
    drawer_front.name = "P1_Front"

    p1_pl = sp.off_plane(comp1, comp1.xZConstructionPlane,
                          "p1_off_y", "P1_Pl")
    pull.install(comp1, drawer_front, p1_pl,
        center=("4 in", "p1_off_y", "3 in"),
        pull_axis="x", depth_axis="y",
        prefix="pl", name="P1_Pull", ev=ctx.ev, flip=True,
        board_thick_expr="0.75 in")

    n = comp1.bRepBodies.count
    names = [comp1.bRepBodies.item(i).name for i in range(n)]
    print(f"  P1: {n} bodies -> {names}")
    assert n == 2, f"P1: expected 2, got {n}"
    print("  P1: PASS\n")

    # ================================================================
    # L1: Chest lock + keyhole + strike plate
    # ================================================================
    print("=" * 50)
    print("L1: Chest lock on front + keyhole + strike on lid")
    print("=" * 50)

    params.add("l1_off_x", VI("12 in"), "in", "L1 X offset")
    chest_lock.define_params(params, prefix="lk", size="small")

    occ2 = sp.make_comp(root, "L1")
    comp2 = occ2.component

    front_pl = sp.off_plane(comp2, comp2.xZConstructionPlane,
                             "p1_off_y", "L1_FrontPl")
    sk, pr = sp.sketch_rect_model(comp2, front_pl,
        ("l1_off_x", "p1_off_y", "0 in"),
        {"x": "6 in", "z": "4 in"}, "L1_Front_Sk", ctx.ev)
    l1_front = sp.ext_new(comp2, pr, "0.5 in", "L1_Front").bodies.item(0)
    l1_front.name = "L1_Front"

    lid_pl = sp.off_plane(comp2, comp2.xYConstructionPlane,
                           "4 in", "L1_LidPl")
    sk, pr = sp.sketch_rect_model(comp2, lid_pl,
        ("l1_off_x", "p1_off_y", "4 in"),
        {"x": "6 in", "y": "6 in"}, "L1_Lid_Sk", ctx.ev)
    l1_lid = sp.ext_new(comp2, pr, "0.5 in", "L1_Lid").bodies.item(0)
    l1_lid.name = "L1_Lid"

    inner_pl = sp.off_plane(comp2, comp2.xZConstructionPlane,
                             "p1_off_y + 0.5 in", "L1_InnerPl")
    chest_lock.lock_mortise(comp2, l1_front, inner_pl,
        origin=("l1_off_x + 3 in - lk_w / 2", "p1_off_y + 0.5 in", "3 in"),
        size_map={"x": "lk_w", "z": "lk_h"},
        prefix="lk", name="L1_Lock", ev=ctx.ev, flip=True)

    chest_lock.keyhole(comp2, l1_front, front_pl,
        center=("l1_off_x + 3 in", "p1_off_y", "3 in + lk_h / 2"),
        prefix="lk", name="L1_Lock", ev=ctx.ev, flip=True,
        board_thick_expr="0.5 in")

    chest_lock.strike(comp2, l1_lid, lid_pl,
        origin=("l1_off_x + 3 in - lk_strike_w / 2",
                "p1_off_y + 0.5 in", "4 in"),
        size_map={"x": "lk_strike_w", "y": "lk_strike_l"},
        prefix="lk", name="L1_Strike", ev=ctx.ev, flip=True)

    n = comp2.bRepBodies.count
    names = [comp2.bRepBodies.item(i).name for i in range(n)]
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

    expected = 2 + 4
    status = "PASS" if total == expected else "FAIL"
    print(f"\n{status}: expected {expected}, got {total}")

    for occ_item in root.occurrences:
        c = occ_item.component
        for sk_item in c.sketches:
            sk_item.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
