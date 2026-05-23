"""
Modern Wall Cabinet
===================
24"W x 12"D x 30"H, 3/4" stock.
2 inset doors, 1 adjustable shelf, plywood back.
Dado joints for top/bottom, rabbet for back.

Coordinate system:
  X = width (24")  Y = depth (12")  Z = height (30")
"""
import adsk.core, adsk.fusion

from helpers import sp

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
    #  BODY LOOKUP (for body-relative references / validate_deps)
    # ==============================================================
    def find_body(name, comp=None):
        c = comp or root
        for i in range(c.bRepBodies.count):
            if c.bRepBodies.item(i).name == name:
                return c.bRepBodies.item(i)
        for j in range(c.occurrences.count):
            r = find_body(name, c.occurrences.item(j).component)
            if r:
                return r
        return None

    # ==============================================================
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        ("case_w",      "24 in",    "in"),
        ("case_d",      "12 in",    "in"),
        ("case_h",      "30 in",    "in"),
        ("board_thick",  "0.75 in", "in"),
        ("back_thick",   "0.25 in", "in"),
        ("shelf_thick",  "0.75 in", "in"),
        ("door_thick",   "0.75 in", "in"),
        ("door_gap",     "0.0625 in","in"),
        ("dado_d",       "0.25 in", "in"),  # dado depth for top/bottom
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("inner_w",     "case_w - 2 * board_thick",                 "in"),
        ("inner_h",     "case_h - 2 * board_thick",                 "in"),
        ("inner_d",     "case_d - back_thick",                      "in"),
        ("mid_x",       "case_w / 2",                                "in"),
        ("mid_z",       "case_h / 2",                                "in"),
        ("door_w",      "(inner_w - 3 * door_gap) / 2",             "in"),
        ("door_h",      "inner_h - 2 * door_gap",                   "in"),
        ("shelf_w",     "inner_w",                                   "in"),
        ("shelf_d",     "case_d - back_thick - board_thick",         "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    case_occ  = sp.make_comp(root, "Case")
    door_occ  = sp.make_comp(root, "Doors")
    shelf_occ = sp.make_comp(root, "Shelf")
    back_occ  = sp.make_comp(root, "Back")

    case_c  = case_occ.component
    door_c  = door_occ.component
    shelf_c = shelf_occ.component
    back_c  = back_occ.component

    # ==============================================================
    #  1. CASE — left, right sides + top, bottom
    # ==============================================================
    # Left side: X=0, Y=0..case_d, Z=0..case_h
    _, pr = sp.sketch_rect_model(case_c, case_c.yZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"y": "case_d", "z": "case_h"}, "LeftSide_Sk", ev)
    ls_ext = sp.ext_new(case_c, pr, "board_thick", "LeftSide")
    left = ls_ext.bodies.item(0); left.name = "Side_Left"

    # Body-relative ref: Side_Right mirrors Side_Left
    ref_side_left = find_body("Side_Left")
    ref_side_left_bb = ref_side_left.boundingBox

    # Right side: mirror
    x_mid = sp.off_plane(case_c, case_c.yZConstructionPlane, "mid_x", "XMid")
    sp.mirror_feats(case_c, [ls_ext], x_mid, "RightMir").bodies.item(0).name = "Side_Right"

    # Top board: X=board_thick..case_w-board_thick (between sides with dado)
    top_pl = sp.off_plane(case_c, case_c.xYConstructionPlane,
                           "case_h - board_thick", "Top_Pl")
    _, pr = sp.sketch_rect_model(case_c, top_pl,
        ("board_thick - dado_d", "0 in", "case_h - board_thick"),
        {"x": "inner_w + 2 * dado_d", "y": "case_d"}, "Top_Sk", ev)
    top_ext = sp.ext_new(case_c, pr, "board_thick", "TopBoard")
    top_body = top_ext.bodies.item(0); top_body.name = "Top"

    # Bottom board: mirror top across ZMid
    z_mid = sp.off_plane(case_c, case_c.xYConstructionPlane, "mid_z", "ZMid")
    bot_mir = sp.mirror_feats(case_c, [top_ext], z_mid, "BotMir")
    bot_body = bot_mir.bodies.item(0); bot_body.name = "Bottom"

    # Dado CUTs — top/bottom extend into sides by dado_d
    # The top/bottom bodies already extend into the sides by dado_d,
    # so CUT them into the sides
    left_proxy = left.createForAssemblyContext(case_occ)
    top_proxy = top_body.createForAssemblyContext(case_occ)
    bot_proxy = bot_body.createForAssemblyContext(case_occ)

    # Get right side body
    right = None
    for i in range(case_c.bRepBodies.count):
        b = case_c.bRepBodies.item(i)
        if b.name == "Side_Right":
            right = b; break
    right_proxy = right.createForAssemblyContext(case_occ)

    sp.combine(left_proxy, [top_proxy, bot_proxy], CUT, True, "DadoLeft")
    sp.combine(right_proxy, [top_proxy, bot_proxy], CUT, True, "DadoRight")

    print(">>> Case: 4 bodies + dados done")

    # ==============================================================
    #  2. DOORS — 2 inset door panels
    # ==============================================================
    # Body-relative ref: Door_Left positioned relative to Top
    ref_top = find_body("Top")
    ref_top_bb = ref_top.boundingBox

    # Left door: inset inside case opening
    door_z_offset = "board_thick + door_gap"
    _, pr = sp.sketch_rect_model(door_c, door_c.xZConstructionPlane,
        ("board_thick + door_gap", "0 in", door_z_offset),
        {"x": "door_w", "z": "door_h"}, "LeftDoor_Sk", ev)
    ld_ext = sp.ext_new(door_c, pr, "door_thick", "LeftDoor")
    ld_ext.bodies.item(0).name = "Door_Left"

    # Body-relative ref: Door_Right mirrors Door_Left
    ref_door_left = find_body("Door_Left")
    ref_door_left_bb = ref_door_left.boundingBox

    # Right door: mirror across XMid
    d_xmid = sp.off_plane(door_c, door_c.yZConstructionPlane, "mid_x", "DXMid")
    sp.mirror_feats(door_c, [ld_ext], d_xmid, "RightDoorMir").bodies.item(0).name = "Door_Right"

    print(">>> Doors: 2 bodies")

    # ==============================================================
    #  3. SHELF — adjustable (just positioned, no dados)
    # ==============================================================
    # Body-relative ref: Shelf positioned above Bottom
    ref_bottom = find_body("Bottom")
    ref_bottom_bb = ref_bottom.boundingBox
    shelf_z_pl = sp.off_plane(shelf_c, shelf_c.xYConstructionPlane, "mid_z", "ShelfZ_Pl")
    _, pr = sp.sketch_rect_model(shelf_c, shelf_z_pl,
        ("board_thick", "0 in", "mid_z"),
        {"x": "shelf_w", "y": "shelf_d"}, "Shelf_Sk", ev)
    sp.ext_new(shelf_c, pr, "shelf_thick", "ShelfBoard").bodies.item(0).name = "Shelf"

    print(">>> Shelf: 1 body")

    # ==============================================================
    #  4. BACK PANEL
    # ==============================================================
    _, pr = sp.sketch_rect_model(back_c, back_c.xZConstructionPlane,
        ("board_thick", "case_d - back_thick", "board_thick"),
        {"x": "inner_w", "z": "inner_h"}, "Back_Sk", ev)
    sp.ext_new(back_c, pr, "back_thick", "BackPanel").bodies.item(0).name = "BackPanel"

    # Rabbet for back panel in sides
    bp = None
    for i in range(back_c.bRepBodies.count):
        bp = back_c.bRepBodies.item(i); break
    bp_proxy = bp.createForAssemblyContext(back_occ)
    sp.combine(left_proxy, [bp_proxy], CUT, True, "RabLeft")
    sp.combine(right_proxy, [bp_proxy], CUT, True, "RabRight")

    print(">>> Back panel + rabbets done")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [case_c, door_c, shelf_c, back_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for cn, c in [("Case", case_c), ("Doors", door_c),
                   ("Shelf", shelf_c), ("Back", back_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} bodies -> {names}")

    sp.apply_appearance("cherry")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
