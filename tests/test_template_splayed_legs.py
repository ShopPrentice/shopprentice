"""Test fixture for splayed legs template.

Tests define_params, build (4 legs with compound splay), splay_offset,
and define_stretcher_params. Creates a simple stool with splayed legs
and validates 5 bodies (seat + 4 legs).
"""
import adsk.core
import adsk.fusion
import math

def run(context):
    app = adsk.core.Application.get()

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    Point3D = adsk.core.Point3D

    from helpers import sp
    from woodworking.templates import splayed_legs

    ctx = sp.DesignContext(design)

    # ── Parameters ──
    params.add("seat_l", VI("14 in"), "in", "Seat length")
    params.add("seat_w", VI("12 in"), "in", "Seat width")
    params.add("seat_t", VI("1 in"), "in", "Seat thickness")
    params.add("seat_h", VI("18 in"), "in", "Seat height")

    # Splayed leg params via template
    splayed_legs.define_params(params,
        splay_x="6 deg", splay_y="4 deg",
        leg_w="1.5 in", leg_d="1.5 in",
        leg_h_expr="seat_h - seat_t",
        inset_x="3 in", inset_y="2.5 in")

    # ── Build seat ──
    seat_pl = sp.off_plane(root, root.xYConstructionPlane,
                           "seat_h - seat_t", "Seat_Pl")
    sk, pr = sp.sketch_rect(root, seat_pl,
                             "0 in", "0 in", "seat_l", "seat_w",
                             "Seat_Sk", ctx.ev)
    seat_ext = sp.ext_new(root, pr, "seat_t", "Seat")
    seat = seat_ext.bodies.item(0)
    seat.name = "Seat"

    print(f"Seat built at Z={ctx.ev('seat_h - seat_t'):.2f} cm")

    # ── Midplanes ──
    XMid = sp.off_plane(root, root.yZConstructionPlane,
                        "seat_l / 2", "XMid")
    YMid = sp.off_plane(root, root.xZConstructionPlane,
                        "seat_w / 2", "YMid")

    # ── Build 4 splayed legs via template ──
    legs = splayed_legs.build(root,
        inset_x_expr="leg_inset_x",
        inset_y_expr="leg_inset_y",
        seat_body=seat, x_mid=XMid, y_mid=YMid,
        ev=ctx.ev)

    print(f"Legs built: {list(legs.keys())[:4]}")
    for k in ["NL", "NR", "FL", "FR"]:
        b = legs[k]
        bb = b.boundingBox
        print(f"  {k}: min=({bb.minPoint.x:.1f}, {bb.minPoint.y:.1f}, {bb.minPoint.z:.1f}) "
              f"max=({bb.maxPoint.x:.1f}, {bb.maxPoint.y:.1f}, {bb.maxPoint.z:.1f})")

    # ── Test splay_offset ──
    str_h = ctx.ev("seat_h - seat_t") * 0.4  # 40% up the leg
    sx, sy = splayed_legs.splay_offset(str_h, ev=ctx.ev)
    print(f"\nSplay offset at h={str_h:.1f}cm: sx={sx:.3f}cm, sy={sy:.3f}cm")

    # Verify: at h=0, offset should be full splay_shift
    sx0, sy0 = splayed_legs.splay_offset(0, ev=ctx.ev)
    full_sx = ctx.ev("splay_shift")
    full_sy = ctx.ev("splay_shift_w")
    print(f"Splay at floor: sx={sx0:.3f} (expected {full_sx:.3f}), "
          f"sy={sy0:.3f} (expected {full_sy:.3f})")
    assert abs(sx0 - full_sx) < 0.001, "Floor splay X mismatch"
    assert abs(sy0 - full_sy) < 0.001, "Floor splay Y mismatch"

    # At h=leg_top_z, offset should be 0
    sx_top, sy_top = splayed_legs.splay_offset(ctx.ev("leg_top_z"), ev=ctx.ev)
    assert abs(sx_top) < 0.001, "Top splay X should be 0"
    assert abs(sy_top) < 0.001, "Top splay Y should be 0"
    print("Splay interpolation: PASS")

    # ── Test define_stretcher_params ──
    params.add("str_h", VI("8 in"), "in", "Stretcher height")
    params.add("st_l", VI("0.875 in"), "in", "Tenon length")
    sp = splayed_legs.define_stretcher_params(params, "bstr",
        height_expr="str_h",
        top_l_expr="seat_l", top_w_expr="seat_w",
        tenon_l_expr="st_l")
    bstr_len = ctx.ev(sp["len_x"])
    print(f"Stretcher length (X): {bstr_len:.3f} cm = {bstr_len/2.54:.2f} in")

    # ── Summary ──
    names = [root.bRepBodies.item(i).name
             for i in range(root.bRepBodies.count)]
    print(f"\nTotal: {len(names)} bodies -> {names}")

    expected = 5  # Seat + 4 legs
    actual = len(names)
    status = "PASS" if actual == expected else "FAIL"
    print(f"\n{status}: expected {expected} bodies, got {actual}")

    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
