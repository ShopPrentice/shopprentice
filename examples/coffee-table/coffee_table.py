"""
Modern Coffee Table
===================
48"L x 20"W x 16"H, 1" thick top, tapered legs.
No aprons — legs connect to top via dominos. Lower shelf.

Coordinate system:
  X = length (48")  Y = width (20")  Z = height (16")
"""
import adsk.core, adsk.fusion

from helpers import sp
from woodworking.templates import domino

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
    #  BODY LOOKUP
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
    #  COMPONENTS
    # ==============================================================
    leg_occ   = sp.make_comp(root, "Legs")
    top_occ   = sp.make_comp(root, "Top")
    shelf_occ = sp.make_comp(root, "Shelf")

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
    _, pr = sp.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("leg_inset - leg_top / 2", "leg_inset - leg_top / 2", "0 in"),
        {"x": "leg_top", "y": "leg_top"},
        "LegFL_Sk", ev)
    fl_ext = sp.ext_new(leg_c, pr, "leg_h", "LegFL")
    leg_fl = fl_ext.bodies.item(0)
    leg_fl.name = "Leg_FL"

    l_xmid = sp.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    l_ymid = sp.off_plane(leg_c, leg_c.xZConstructionPlane, "mid_y", "LYMid")

    ref_fl = find_body("Leg_FL")
    ref_fl_bb = ref_fl.boundingBox
    leg_fr = sp.mirror_body(leg_c, leg_fl, l_xmid, "LegFR_Mir").bodies.item(0)
    leg_fr.name = "Leg_FR"
    leg_bl = sp.mirror_body(leg_c, leg_fl, l_ymid, "LegBL_Mir").bodies.item(0)
    leg_bl.name = "Leg_BL"
    ref_fr = find_body("Leg_FR")
    ref_fr_bb = ref_fr.boundingBox
    leg_br = sp.mirror_body(leg_c, leg_fr, l_ymid, "LegBR_Mir").bodies.item(0)
    leg_br.name = "Leg_BR"

    print(">>> Legs: 4 bodies")

    # ==============================================================
    #  2. TOP — solid panel
    # ==============================================================
    # Body-relative ref: Top depends on Leg_FL
    ref_body = find_body("Leg_FL")
    ref_bb = ref_body.boundingBox
    top_pl = sp.off_plane(top_c, top_c.xYConstructionPlane, "leg_h", "Top_Pl")
    _, pr = sp.sketch_rect_model(top_c, top_pl,
        ("0 in", "0 in", "leg_h"),
        {"x": "table_l", "y": "table_w"},
        "Top_Sk", ev)
    top_ext = sp.ext_new(top_c, pr, "top_thick", "TopBoard")
    top_body = top_ext.bodies.item(0)
    top_body.name = "Top"

    print(">>> Top: 1 body")

    # ==============================================================
    #  3. SHELF — lower shelf between legs
    # ==============================================================
    # Body-relative ref: Shelf depends on Leg_FL
    ref_body = find_body("Leg_FL")
    ref_bb = ref_body.boundingBox
    shelf_z_pl = sp.off_plane(shelf_c, shelf_c.xYConstructionPlane,
                               "shelf_z", "Shelf_Pl")
    _, pr = sp.sketch_rect_model(shelf_c, shelf_z_pl,
        ("leg_inset", "leg_inset", "shelf_z"),
        {"x": "shelf_l", "y": "shelf_w"},
        "Shelf_Sk", ev)
    shelf_ext = sp.ext_new(shelf_c, pr, "shelf_thick", "ShelfBoard")
    shelf_body = shelf_ext.bodies.item(0)
    shelf_body.name = "Shelf"

    print(">>> Shelf: 1 body")

    # ==============================================================
    #  4. DOMINO JOINERY — legs directly to top underside
    #     One domino per leg, centered on the leg, at the top interface
    #     Voids live in the Top component; legs are cross-component proxies.
    # ==============================================================
    fl_proxy = leg_fl.createForAssemblyContext(leg_occ)
    fr_proxy = leg_fr.createForAssemblyContext(leg_occ)
    bl_proxy = leg_bl.createForAssemblyContext(leg_occ)
    br_proxy = leg_br.createForAssemblyContext(leg_occ)

    # Interface plane at leg top (Z = leg_h) — in Top component
    dm_pl = sp.off_plane(top_c, top_c.xYConstructionPlane, "leg_h", "DM_Pl")

    # Body-relative ref: DM_FL depends on Leg_FL
    ref_body = find_body("Leg_FL")
    ref_bb = ref_body.boundingBox

    # FL leg domino
    domino.single(top_c, dm_pl,
        ("leg_inset", "leg_inset", "leg_h"),
        "x", "dm_w", "dm_t", "dm_d",
        top_body, fl_proxy, "DM_FL", ev)

    # Body-relative ref: DM_FR depends on Leg_FR
    ref_body = find_body("Leg_FR")
    ref_bb = ref_body.boundingBox

    # FR leg domino
    domino.single(top_c, dm_pl,
        ("table_l - leg_inset", "leg_inset", "leg_h"),
        "x", "dm_w", "dm_t", "dm_d",
        top_body, fr_proxy, "DM_FR", ev)

    # Body-relative ref: DM_BL depends on Leg_BL
    ref_body = find_body("Leg_BL")
    ref_bb = ref_body.boundingBox

    # BL leg domino
    domino.single(top_c, dm_pl,
        ("leg_inset", "table_w - leg_inset", "leg_h"),
        "x", "dm_w", "dm_t", "dm_d",
        top_body, bl_proxy, "DM_BL", ev)

    # Body-relative ref: DM_BR depends on Leg_BR
    ref_body = find_body("Leg_BR")
    ref_bb = ref_body.boundingBox

    # BR leg domino
    domino.single(top_c, dm_pl,
        ("table_l - leg_inset", "table_w - leg_inset", "leg_h"),
        "x", "dm_w", "dm_t", "dm_d",
        top_body, br_proxy, "DM_BR", ev)

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
    print(f"Root: {root.bRepBodies.count} bodies")

    sp.apply_appearance("walnut")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
