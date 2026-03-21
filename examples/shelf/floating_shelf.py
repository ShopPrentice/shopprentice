"""
Modern Floating Shelf
=====================
36"L x 8"D x 1.5" thick, hidden cleat mounting system.
Hollow shell (top, bottom, end caps) slides over wall-mounted cleat.

Coordinate system:
  X = length (36")  Y = depth (8")  Z = height (1.5")

Components:
  Shelf — hollow shell (top, bottom, left cap, right cap)
  Cleat — wall-mount strip fitting inside the shelf cavity
"""
import adsk.core, adsk.fusion

from helpers import af

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        ("shelf_l",     "36 in",   "in"),
        ("shelf_d",     "8 in",    "in"),
        ("shelf_thick", "1.5 in",  "in"),
        ("board_thick", "0.25 in", "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("cleat_h",  "shelf_thick - 2 * board_thick",  "in"),
        ("cleat_d",  "shelf_d - board_thick",           "in"),
        ("cleat_l",  "shelf_l - 2 * board_thick",       "in"),
        ("mid_x",    "shelf_l / 2",                     "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    shelf_occ = af.make_comp(root, "Shelf")
    cleat_occ = af.make_comp(root, "Cleat")
    shelf_c = shelf_occ.component
    cleat_c = cleat_occ.component

    # ==============================================================
    #  1. SHELF — hollow shell
    # ==============================================================
    # Bottom board: Z=0, full length × full depth
    _, pr = af.sketch_rect_model(shelf_c, shelf_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "shelf_l", "y": "shelf_d"},
        "Bottom_Sk", ev)
    bot_ext = af.ext_new(shelf_c, pr, "board_thick", "BottomBoard")
    bottom = bot_ext.bodies.item(0)
    bottom.name = "Bottom"

    # Top board: Z = shelf_thick - board_thick
    top_pl = af.off_plane(shelf_c, shelf_c.xYConstructionPlane,
                           "shelf_thick - board_thick", "Top_Pl")
    _, pr = af.sketch_rect_model(shelf_c, top_pl,
        ("0 in", "0 in", "shelf_thick - board_thick"),
        {"x": "shelf_l", "y": "shelf_d"},
        "Top_Sk", ev)
    top_ext = af.ext_new(shelf_c, pr, "board_thick", "TopBoard")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    # Left end cap: X=0, full depth × full height
    _, pr = af.sketch_rect_model(shelf_c, shelf_c.yZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"y": "shelf_d", "z": "shelf_thick"},
        "LeftCap_Sk", ev)
    left_ext = af.ext_new(shelf_c, pr, "board_thick", "LeftCap")
    left_cap = left_ext.bodies.item(0)
    left_cap.name = "Cap_Left"

    # Right end cap: mirror across XMid
    x_mid = af.off_plane(shelf_c, shelf_c.yZConstructionPlane, "mid_x", "XMid")
    right_mir = af.mirror_feats(shelf_c, [left_ext], x_mid, "RightCapMir")
    right_cap = right_mir.bodies.item(0)
    right_cap.name = "Cap_Right"

    print(">>> Shelf: 4 bodies done (top, bottom, left cap, right cap)")

    # ==============================================================
    #  2. CLEAT — wall-mount strip
    # ==============================================================
    # Cleat sits inside the shelf cavity, against the back wall (max Y)
    # Position: X = board_thick, Y = board_thick, Z = board_thick
    cleat_pl = af.off_plane(cleat_c, cleat_c.xYConstructionPlane,
                             "board_thick", "Cleat_Pl")
    _, pr = af.sketch_rect_model(cleat_c, cleat_pl,
        ("board_thick", "board_thick", "board_thick"),
        {"x": "cleat_l", "y": "cleat_d"},
        "Cleat_Sk", ev)
    cleat_ext = af.ext_new(cleat_c, pr, "cleat_h", "CleatBoard")
    cleat_body = cleat_ext.bodies.item(0)
    cleat_body.name = "Cleat"

    print(">>> Cleat: 1 body done")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [shelf_c, cleat_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
        for ca in comp.constructionAxes:
            ca.isLightBulbOn = False

    for comp_name, c in [("Shelf", shelf_c), ("Cleat", cleat_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    root_names = [root.bRepBodies.item(i).name
                  for i in range(root.bRepBodies.count)]
    print(f"Root: {len(root_names)} bodies -> {root_names}")

    af.apply_appearance("walnut")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
