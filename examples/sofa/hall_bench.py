"""
Hall Bench
==========
60"L x 18"D x 34"H modern hall bench with back.
Thick slab seat, square legs, back frame with vertical slats.
Domino joinery at all connections. White oak.

Coordinate system:
  X = length (60")  Y = depth (18")  Z = height (34")
"""
import adsk.core
import adsk.fusion

from helpers import af

CUT  = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW  = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    P = adsk.core.Point3D.create

    def ev(e):
        p = params.itemByName(e)
        return p.value if p else design.unitsManager.evaluateExpression(e, "cm")

    # ══════════════════════════════════════════════════════════════
    #  PARAMETERS
    # ══════════════════════════════════════════════════════════════
    for pname, expr, unit, desc in [
        # Envelope
        ("bench_l",     "60 in",    "in", "Overall length"),
        ("bench_d",     "18 in",    "in", "Overall depth"),
        ("seat_h",      "18 in",    "in", "Seat height"),
        ("back_h",      "34 in",    "in", "Total back height"),
        # Parts
        ("seat_thick",  "1.5 in",   "in", "Seat slab thickness"),
        ("leg_size",    "2 in",     "in", "Leg cross-section (square)"),
        ("apron_h",     "4 in",     "in", "Apron height"),
        ("apron_thick", "0.75 in",  "in", "Apron thickness"),
        ("back_rail_h", "2.5 in",   "in", "Back top rail height"),
        ("back_rail_t", "0.75 in",  "in", "Back rail thickness"),
        ("slat_w",      "2 in",     "in", "Slat width"),
        ("slat_thick",  "0.75 in",  "in", "Slat thickness"),
        ("n_slats",     "3",        "",   "Number of back slats"),
        # Domino (8mm Festool)
        ("dm_t",        "8 mm",     "in", "Domino cutter diameter"),
        ("dm_w",        "40 mm",    "in", "Domino width"),
        ("dm_d",        "20 mm",    "in", "Domino depth per side"),
        ("dm_count",    "2",        "",   "Dominos per apron-to-leg joint"),
        # Derived
        ("inner_l",     "bench_l - 2 * leg_size",          "in", "Length between legs"),
        ("inner_d",     "bench_d - 2 * leg_size",          "in", "Depth between legs"),
        ("apron_z",     "seat_h - seat_thick - apron_h",   "in", "Apron bottom Z"),
        ("slat_h",      "back_h - seat_h - back_rail_h",   "in", "Slat height"),
        ("slat_sp",     "inner_l / (n_slats + 1)",         "in", "Slat spacing"),
        ("dm_sp",       "apron_h / (dm_count + 1)",        "in", "Domino spacing in apron"),
    ]:
        params.add(pname, VI(expr), unit, desc)

    # ══════════════════════════════════════════════════════════════
    #  MIDPLANES
    # ══════════════════════════════════════════════════════════════
    XMid = af.off_plane(root, root.yZConstructionPlane, "bench_l / 2", "XMid")
    YMid = af.off_plane(root, root.xZConstructionPlane, "bench_d / 2", "YMid")

    # ══════════════════════════════════════════════════════════════
    #  LEGS (4 bodies — FL, FR short front; BL, BR tall back)
    # ══════════════════════════════════════════════════════════════
    leg_occ = af.make_comp(root, "Legs")
    leg_c = leg_occ.component

    # Front-left leg (short — seat height)
    sk, prof = af.sketch_rect_model(leg_c, root.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"},
        "LegFL_Sk", ev=ev)
    f = af.ext_new(leg_c, prof, "seat_h - seat_thick", "LegFL")
    leg_fl = f.bodies.item(0)
    leg_fl.name = "Leg_FL"

    # Back-left leg (tall — full back height)
    sk2, prof2 = af.sketch_rect_model(leg_c, root.xYConstructionPlane,
        ("0 in", "bench_d - leg_size", "0 in"),
        {"x": "leg_size", "y": "leg_size"},
        "LegBL_Sk", ev=ev)
    f2 = af.ext_new(leg_c, prof2, "back_h", "LegBL")
    leg_bl = f2.bodies.item(0)
    leg_bl.name = "Leg_BL"

    # Mirror FL → FR and BL → BR across XMid
    m1 = af.mirror_bodies(leg_c, [leg_fl, leg_bl], XMid, "LegR_Mirror")
    leg_fr = m1.bodies.item(0)
    leg_br = m1.bodies.item(1)
    leg_fr.name = "Leg_FR"
    leg_br.name = "Leg_BR"

    print(f">>> Legs: {leg_c.bRepBodies.count} bodies")

    # ══════════════════════════════════════════════════════════════
    #  APRONS (4 bodies — Front, Back, Left, Right)
    # ══════════════════════════════════════════════════════════════
    apr_occ = af.make_comp(root, "Aprons")
    apr_c = apr_occ.component

    # Front apron (runs along X between front legs)
    sk3, prof3 = af.sketch_rect_model(apr_c, root.xZConstructionPlane,
        ("leg_size", "0 in", "apron_z"),
        {"x": "inner_l", "z": "apron_h"},
        "AprFront_Sk", ev=ev)
    f3 = af.ext_new(apr_c, prof3, "apron_thick", "AprFront")
    apr_front = f3.bodies.item(0)
    apr_front.name = "Apron_Front"

    # Mirror front → back across YMid
    m2 = af.mirror_body(apr_c, apr_front, YMid, "AprBack_Mirror")
    apr_back = m2.bodies.item(0)
    apr_back.name = "Apron_Back"

    # Left apron (runs along Y between front-left and back-left legs)
    sk4, prof4 = af.sketch_rect_model(apr_c, root.yZConstructionPlane,
        ("0 in", "leg_size", "apron_z"),
        {"y": "inner_d", "z": "apron_h"},
        "AprLeft_Sk", ev=ev)
    f4 = af.ext_new(apr_c, prof4, "apron_thick", "AprLeft")
    apr_left = f4.bodies.item(0)
    apr_left.name = "Apron_Left"

    # Mirror left → right across XMid
    m3 = af.mirror_body(apr_c, apr_left, XMid, "AprRight_Mirror")
    apr_right = m3.bodies.item(0)
    apr_right.name = "Apron_Right"

    print(f">>> Aprons: {apr_c.bRepBodies.count} bodies")

    # ══════════════════════════════════════════════════════════════
    #  SEAT (1 body — slab spanning full length × depth)
    # ══════════════════════════════════════════════════════════════
    seat_occ = af.make_comp(root, "Seat")
    seat_c = seat_occ.component

    sk5, prof5 = af.sketch_rect_model(seat_c, root.xYConstructionPlane,
        ("0 in", "0 in", "seat_h - seat_thick"),
        {"x": "bench_l", "y": "bench_d"},
        "Seat_Sk", ev=ev)
    f5 = af.ext_new(seat_c, prof5, "seat_thick", "SeatSlab")
    seat = f5.bodies.item(0)
    seat.name = "Seat"

    print(f">>> Seat: {seat_c.bRepBodies.count} body")

    # ══════════════════════════════════════════════════════════════
    #  BACK (top rail + 3 slats between back posts above seat)
    # ══════════════════════════════════════════════════════════════
    back_occ = af.make_comp(root, "Back")
    back_c = back_occ.component

    # Top rail — between back posts, at back_h - back_rail_h
    sk6, prof6 = af.sketch_rect_model(back_c, root.xZConstructionPlane,
        ("leg_size", "0 in", "back_h - back_rail_h"),
        {"x": "inner_l", "z": "back_rail_h"},
        "TopRail_Sk", ev=ev)
    # Extrude at Y = bench_d - leg_size (centered on back posts)
    top_rail_pl = af.off_plane(back_c, root.xZConstructionPlane,
        "bench_d - leg_size + (leg_size - back_rail_t) / 2", "TopRailY_Pl")
    sk6b, prof6b = af.sketch_rect_model(back_c, top_rail_pl,
        ("leg_size", "0 in", "back_h - back_rail_h"),
        {"x": "inner_l", "z": "back_rail_h"},
        "TopRail_Sk2", ev=ev)
    f6 = af.ext_new(back_c, prof6b, "back_rail_t", "TopRail")
    top_rail = f6.bodies.item(0)
    top_rail.name = "Top_Rail"

    # Slats — vertical between seat top and top rail bottom
    # First slat at x = leg_size + slat_sp - slat_w/2
    slat_y_pl = af.off_plane(back_c, root.xZConstructionPlane,
        "bench_d - leg_size + (leg_size - slat_thick) / 2", "SlatY_Pl")
    sk7, prof7 = af.sketch_rect_model(back_c, slat_y_pl,
        ("leg_size + slat_sp - slat_w / 2", "0 in", "seat_h"),
        {"x": "slat_w", "z": "slat_h"},
        "Slat_Sk", ev=ev)
    f7 = af.ext_new(back_c, prof7, "slat_thick", "Slat1")
    slat1 = f7.bodies.item(0)
    slat1.name = "Slat_1"

    # Pattern slats along X
    if ev("n_slats") > 1:
        pat = af.body_pattern(back_c, slat1, back_c.xConstructionAxis,
            "n_slats", "slat_sp", "Slat_Pat")
        for i in range(pat.bodies.count):
            pat.bodies.item(i).name = f"Slat_{i+2}"

    print(f">>> Back: {back_c.bRepBodies.count} bodies")

    # ══════════════════════════════════════════════════════════════
    #  CROSS-COMPONENT JOINERY — Dominos
    # ══════════════════════════════════════════════════════════════
    from helpers.templates import domino

    # Apron-to-leg dominos (8 joints: 4 aprons × 2 ends)
    # Front apron → FL leg (left end)
    domino.grid(root, root.yZConstructionPlane,
        start=("leg_size / 2", "apron_thick / 2",
               "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_fl.createForAssemblyContext(leg_occ),
        body_b=apr_front.createForAssemblyContext(apr_occ),
        name="DM_FA_L", ev=ev)

    # Front apron → FR leg (right end)
    domino.grid(root, root.yZConstructionPlane,
        start=("bench_l - leg_size / 2", "apron_thick / 2",
               "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_fr.createForAssemblyContext(leg_occ),
        body_b=apr_front.createForAssemblyContext(apr_occ),
        name="DM_FA_R", ev=ev)

    # Back apron → BL leg (left end)
    domino.grid(root, root.yZConstructionPlane,
        start=("leg_size / 2", "bench_d - apron_thick / 2",
               "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_bl.createForAssemblyContext(leg_occ),
        body_b=apr_back.createForAssemblyContext(apr_occ),
        name="DM_BA_L", ev=ev)

    # Back apron → BR leg (right end)
    domino.grid(root, root.yZConstructionPlane,
        start=("bench_l - leg_size / 2", "bench_d - apron_thick / 2",
               "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_br.createForAssemblyContext(leg_occ),
        body_b=apr_back.createForAssemblyContext(apr_occ),
        name="DM_BA_R", ev=ev)

    # Left apron → FL leg (front end)
    domino.grid(root, root.xZConstructionPlane,
        start=("apron_thick / 2", "leg_size / 2",
               "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_fl.createForAssemblyContext(leg_occ),
        body_b=apr_left.createForAssemblyContext(apr_occ),
        name="DM_LA_F", ev=ev)

    # Left apron → BL leg (back end)
    domino.grid(root, root.xZConstructionPlane,
        start=("apron_thick / 2", "bench_d - leg_size / 2",
               "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_bl.createForAssemblyContext(leg_occ),
        body_b=apr_left.createForAssemblyContext(apr_occ),
        name="DM_LA_B", ev=ev)

    # Right apron → FR leg (front end)
    domino.grid(root, root.xZConstructionPlane,
        start=("bench_l - apron_thick / 2", "leg_size / 2",
               "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_fr.createForAssemblyContext(leg_occ),
        body_b=apr_right.createForAssemblyContext(apr_occ),
        name="DM_RA_F", ev=ev)

    # Right apron → BR leg (back end)
    domino.grid(root, root.xZConstructionPlane,
        start=("bench_l - apron_thick / 2", "bench_d - leg_size / 2",
               "apron_z + dm_sp"),
        step_axis="z", step_expr="dm_sp", count_expr="dm_count",
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_br.createForAssemblyContext(leg_occ),
        body_b=apr_right.createForAssemblyContext(apr_occ),
        name="DM_RA_B", ev=ev)

    # Top rail → BL post domino
    domino.single(root, root.yZConstructionPlane,
        center=("leg_size / 2",
                "bench_d - leg_size / 2",
                "back_h - back_rail_h / 2"),
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_bl.createForAssemblyContext(leg_occ),
        body_b=top_rail.createForAssemblyContext(back_occ),
        name="DM_TR_L", ev=ev)

    # Top rail → BR post domino
    domino.single(root, root.yZConstructionPlane,
        center=("bench_l - leg_size / 2",
                "bench_d - leg_size / 2",
                "back_h - back_rail_h / 2"),
        long_axis="z", long_expr="dm_w", short_expr="dm_t",
        depth_expr="dm_d",
        body_a=leg_br.createForAssemblyContext(leg_occ),
        body_b=top_rail.createForAssemblyContext(back_occ),
        name="DM_TR_R", ev=ev)

    print(f">>> Dominos: {root.bRepBodies.count} voids in root")

    # ══════════════════════════════════════════════════════════════
    #  DETAILS — seat edge fillet, leg bottom chamfer
    # ══════════════════════════════════════════════════════════════
    # Seat top edge fillet (comfort)
    seat_proxy = seat.createForAssemblyContext(seat_occ)
    top_face = af.find_face(seat_proxy, "z", +1)
    if top_face:
        fillet_inp = root.features.filletFeatures.createInput()
        edges = adsk.core.ObjectCollection.create()
        added = set()
        for ei in range(top_face.edges.count):
            e = top_face.edges.item(ei)
            if e.tempId not in added:
                edges.add(e)
                added.add(e.tempId)
        if edges.count > 0:
            fillet_inp.addConstantRadiusEdgeSet(edges,
                VI("0.125 in"), True)
            fil = root.features.filletFeatures.add(fillet_inp)
            fil.name = "Seat_Fil"

    # Leg bottom chamfers
    for leg_body, leg_name in [
        (leg_fl, "Leg_FL"), (leg_fr, "Leg_FR"),
        (leg_bl, "Leg_BL"), (leg_br, "Leg_BR")]:
        proxy = leg_body.createForAssemblyContext(leg_occ)
        bot_face = af.find_face(proxy, "z", -1)
        if bot_face:
            ch_inp = root.features.chamferFeatures.createInput2()
            ch_edges = adsk.core.ObjectCollection.create()
            ch_added = set()
            for ei in range(bot_face.edges.count):
                e = bot_face.edges.item(ei)
                if e.tempId not in ch_added:
                    ch_edges.add(e)
                    ch_added.add(e.tempId)
            if ch_edges.count > 0:
                ch_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                    ch_edges, VI("0.0625 in"), True)
                ch = root.features.chamferFeatures.add(ch_inp)
                ch.name = f"{leg_name}_Ch"

    # ══════════════════════════════════════════════════════════════
    #  EPILOGUE
    # ══════════════════════════════════════════════════════════════
    # Hide construction elements
    comps = [root] + [root.allOccurrences.item(i).component
                      for i in range(root.allOccurrences.count)]
    for c in comps:
        for sk in c.sketches:
            sk.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False
        for ca in c.constructionAxes:
            ca.isLightBulbOn = False

    # Diagnostic body count
    for i in range(root.occurrences.count):
        occ = root.occurrences.item(i)
        cn = occ.component.name
        names = [occ.component.bRepBodies.item(j).name
                 for j in range(occ.component.bRepBodies.count)]
        print(f"{cn}: {len(names)} -> {names}")
    print(f"Root: {root.bRepBodies.count} domino voids")

    # Apply appearance
    af.apply_appearance("white oak")

    # Fit view
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
