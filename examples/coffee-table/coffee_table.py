"""
Modern Coffee Table
===================
48"L x 20"W x 16"H, 1" thick top, tapered legs.
No aprons — legs connect to top via dominos. Lower shelf.

Coordinate system:
  X = length (48")  Y = width (20")  Z = height (16")
"""
import adsk.core, adsk.fusion

from helpers import af
from helpers.templates import domino

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
        ("table_l",     "48 in",   "in"),
        ("table_w",     "20 in",   "in"),
        ("table_h",     "16 in",   "in"),
        ("top_thick",   "1 in",    "in"),
        ("leg_top",     "1.5 in",  "in"),   # leg size at top (where it meets the table)
        ("leg_bot",     "1 in",    "in"),   # leg size at bottom (tapered)
        ("leg_inset",   "2 in",    "in"),   # leg center inset from edge
        ("shelf_thick", "0.75 in", "in"),
        ("shelf_z",     "3 in",    "in"),
        # Domino params (8mm)
        ("dm_t",        "8 mm",    "in"),
        ("dm_w",        "22 mm",   "in"),
        ("dm_d",        "20 mm",   "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("leg_h",      "table_h - top_thick",                     "in"),
        ("shelf_l",    "table_l - 2 * leg_inset",                 "in"),
        ("shelf_w",    "table_w - 2 * leg_inset",                 "in"),
        ("mid_x",      "table_l / 2",                              "in"),
        ("mid_y",      "table_w / 2",                              "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    # ==============================================================
    #  COMPONENTS
    # ==============================================================
    leg_occ   = af.make_comp(root, "Legs")
    top_occ   = af.make_comp(root, "Top")
    shelf_occ = af.make_comp(root, "Shelf")

    leg_c   = leg_occ.component
    top_c   = top_occ.component
    shelf_c = shelf_occ.component

    # ==============================================================
    #  1. LEGS — 4 tapered legs, no aprons
    #     Legs are tapered: leg_top at the top, leg_bot at the bottom.
    #     For simplicity, model as rectangular (leg_top size) and note
    #     taper as a future detail. The domino connection is what matters.
    # ==============================================================
    # Front-left leg at (leg_inset - leg_top/2, leg_inset - leg_top/2, 0)
    _, pr = af.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("leg_inset - leg_top / 2", "leg_inset - leg_top / 2", "0 in"),
        {"x": "leg_top", "y": "leg_top"},
        "LegFL_Sk", ev)
    fl_ext = af.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = fl_ext.bodies.item(0)
    leg_fl.name = "Leg_FL"

    l_xmid = af.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = af.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")

    leg_fr = af.mirror_body(leg_c, leg_fl, l_xmid, "LegFR_Mir").bodies.item(0)
    leg_fr.name = "Leg_FR"
    leg_bl = af.mirror_body(leg_c, leg_fl, l_ymid, "LegBL_Mir").bodies.item(0)
    leg_bl.name = "Leg_BL"
    leg_br = af.mirror_body(leg_c, leg_fr, l_ymid, "LegBR_Mir").bodies.item(0)
    leg_br.name = "Leg_BR"

    print(">>> Legs: 4 bodies")

    # ==============================================================
    #  2. TOP — solid panel
    # ==============================================================
    top_pl = af.off_plane(top_c, top_c.xYConstructionPlane, "leg_h", "Top_Pl")
    _, pr = af.sketch_rect_model(top_c, top_pl,
        ("0 in", "0 in", "leg_h"),
        {"x": "table_l", "y": "table_w"},
        "Top_Sk", ev)
    top_ext = af.ext_new(top_c, pr, "top_thick", "TopBoard")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    print(">>> Top: 1 body")

    # ==============================================================
    #  3. SHELF — lower shelf between legs
    # ==============================================================
    shelf_z_pl = af.off_plane(shelf_c, shelf_c.xYConstructionPlane,
                               "shelf_z", "Shelf_Pl")
    _, pr = af.sketch_rect_model(shelf_c, shelf_z_pl,
        ("leg_inset", "leg_inset", "shelf_z"),
        {"x": "shelf_l", "y": "shelf_w"},
        "Shelf_Sk", ev)
    shelf_ext = af.ext_new(shelf_c, pr, "shelf_thick", "ShelfBoard")
    shelf_body = shelf_ext.bodies.item(0)
    shelf_body.name = "Shelf"

    print(">>> Shelf: 1 body")

    # ==============================================================
    #  4. DOMINO JOINERY — legs directly to top underside
    #     One domino per leg, centered on the leg, at the top interface
    # ==============================================================
    fl_proxy = leg_fl.createForAssemblyContext(leg_occ)
    fr_proxy = leg_fr.createForAssemblyContext(leg_occ)
    bl_proxy = leg_bl.createForAssemblyContext(leg_occ)
    br_proxy = leg_br.createForAssemblyContext(leg_occ)
    top_proxy = top_body.createForAssemblyContext(top_occ)

    # Interface plane at leg top (Z = leg_h)
    dm_pl = af.off_plane(root, root.xYConstructionPlane, "leg_h", "DM_Pl")

    # FL leg domino
    domino.single(root, dm_pl,
        ("leg_inset", "leg_inset", "leg_h"),
        "x", "dm_w", "dm_t", "dm_d",
        fl_proxy, top_proxy, "DM_FL", ev)

    # FR leg domino
    domino.single(root, dm_pl,
        ("table_l - leg_inset", "leg_inset", "leg_h"),
        "x", "dm_w", "dm_t", "dm_d",
        fr_proxy, top_proxy, "DM_FR", ev)

    # BL leg domino
    domino.single(root, dm_pl,
        ("leg_inset", "table_w - leg_inset", "leg_h"),
        "x", "dm_w", "dm_t", "dm_d",
        bl_proxy, top_proxy, "DM_BL", ev)

    # BR leg domino
    domino.single(root, dm_pl,
        ("table_l - leg_inset", "table_w - leg_inset", "leg_h"),
        "x", "dm_w", "dm_t", "dm_d",
        br_proxy, top_proxy, "DM_BR", ev)

    print(">>> Dominos: 4 leg-to-top joints")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [leg_c, top_c, shelf_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for cn, c in [("Legs", leg_c), ("Top", top_c), ("Shelf", shelf_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} -> {names}")
    print(f"Root: {root.bRepBodies.count} domino voids")

    af.apply_appearance("walnut")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
