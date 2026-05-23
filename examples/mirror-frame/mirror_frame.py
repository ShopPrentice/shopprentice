"""
Modern Mirror Frame
===================
24"W x 36"H mirror opening, 3" wide frame, 3/4" thick.
Butt-joint corners with rabbet on inner back edge to hold glass.

Coordinate system:
  X = width   Y = depth (thickness)   Z = height

Components:
  Frame — Top, Bottom, Left, Right boards with rabbeted inner edge
  Glass — Placeholder body representing the mirror glass
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
    #  PARAMETERS
    # ==============================================================
    for pname, expr, unit in [
        ("mirror_w",     "24 in",    "in"),
        ("mirror_h",     "36 in",    "in"),
        ("frame_w",      "3 in",     "in"),
        ("frame_thick",  "0.75 in",  "in"),
        ("rabbet_d",     "0.375 in", "in"),  # rabbet depth into frame
        ("rabbet_w",     "0.375 in", "in"),  # rabbet width (glass + backing)
        ("glass_thick",  "0.125 in", "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("outer_w",  "mirror_w + 2 * frame_w",  "in"),
        ("outer_h",  "mirror_h + 2 * frame_w",  "in"),
        ("inner_w",  "mirror_w",                 "in"),
        ("inner_h",  "mirror_h",                 "in"),
        ("mid_x",    "outer_w / 2",              "in"),
        ("mid_z",    "outer_h / 2",              "in"),
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
    frame_occ = sp.make_comp(root, "Frame")
    glass_occ = sp.make_comp(root, "Glass")
    frame_c = frame_occ.component
    glass_c = glass_occ.component

    # ==============================================================
    #  1. FRAME — 4 boards with rabbet
    # ==============================================================
    # Bottom rail: X=0..outer_w, Z=0..frame_w, extrude frame_thick in Y
    _, pr = sp.sketch_rect_model(frame_c, frame_c.xZConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "outer_w", "z": "frame_w"},
        "Bottom_Sk", ev)
    bot_ext = sp.ext_new(frame_c, pr, "frame_thick", "BottomRail")
    bottom = bot_ext.bodies.item(0)
    bottom.name = "Bottom"

    # Body-relative ref: Top depends on Bottom
    ref_body = find_body("Bottom")
    ref_bb = ref_body.boundingBox

    # Top rail: mirror across ZMid
    z_mid = sp.off_plane(frame_c, frame_c.xYConstructionPlane, "mid_z", "ZMid")
    top_mir = sp.mirror_feats(frame_c, [bot_ext], z_mid, "TopMir")
    top_body = top_mir.bodies.item(0)
    top_body.name = "Top"

    # Body-relative ref: Left depends on Bottom
    ref_body = find_body("Bottom")
    ref_bb = ref_body.boundingBox

    # Left stile: X=0..frame_w, Z=frame_w..outer_h-frame_w (between rails)
    _, pr = sp.sketch_rect_model(frame_c, frame_c.xZConstructionPlane,
        ("0 in", "0 in", "frame_w"),
        {"x": "frame_w", "z": "inner_h"},
        "Left_Sk", ev)
    left_ext = sp.ext_new(frame_c, pr, "frame_thick", "LeftStile")
    left = left_ext.bodies.item(0)
    left.name = "Left"

    # Body-relative ref: Right depends on Bottom (via Left mirror)
    ref_body = find_body("Left")
    ref_bb = ref_body.boundingBox

    # Right stile: mirror across XMid
    x_mid = sp.off_plane(frame_c, frame_c.yZConstructionPlane, "mid_x", "XMid")
    right_mir = sp.mirror_feats(frame_c, [left_ext], x_mid, "RightMir")
    right = right_mir.bodies.item(0)
    right.name = "Right"

    print(">>> Frame: 4 bodies done")

    # ==============================================================
    #  2. RABBET — cut inner back edge of all frame pieces
    #     Rabbet tool body: spans the entire inner opening area
    #     at the back face, removing rabbet_d deep × rabbet_w wide
    # ==============================================================
    # Rabbet tool: inner rectangle at back face
    rab_pl = sp.off_plane(frame_c, frame_c.xZConstructionPlane,
                           "frame_thick - rabbet_w", "Rabbet_Pl")
    _, pr = sp.sketch_rect_model(frame_c, rab_pl,
        ("frame_w - rabbet_d", "frame_thick - rabbet_w", "frame_w - rabbet_d"),
        {"x": "inner_w + 2 * rabbet_d", "z": "inner_h + 2 * rabbet_d"},
        "Rabbet_Sk", ev)
    rab_ext = sp.ext_new(frame_c, pr, "rabbet_w", "RabbetTool")
    rab_body = rab_ext.bodies.item(0)

    # CUT rabbet into all 4 frame pieces
    sp.combine(bottom, [rab_body], CUT, True, "Rab_Bot")
    sp.combine(top_body, [rab_body], CUT, True, "Rab_Top")
    sp.combine(left, [rab_body], CUT, True, "Rab_Left")
    sp.combine(right, [rab_body], CUT, False, "Rab_Right")  # consumes tool

    print(">>> Rabbets cut into all 4 frame pieces")

    # ==============================================================
    #  3. GLASS — placeholder body in the rabbet
    # ==============================================================
    # Body-relative ref: Glass depends on Bottom
    ref_body = find_body("Bottom")
    ref_bb = ref_body.boundingBox
    glass_pl = sp.off_plane(glass_c, glass_c.xZConstructionPlane,
                             "frame_thick - rabbet_w", "Glass_Pl")
    _, pr = sp.sketch_rect_model(glass_c, glass_pl,
        ("frame_w", "frame_thick - rabbet_w", "frame_w"),
        {"x": "mirror_w", "z": "mirror_h"},
        "Glass_Sk", ev)
    glass_ext = sp.ext_new(glass_c, pr, "glass_thick", "GlassPanel")
    glass_body = glass_ext.bodies.item(0)
    glass_body.name = "Glass"

    print(">>> Glass placeholder done")

    # ==============================================================
    #  EPILOGUE
    # ==============================================================
    for comp in [frame_c, glass_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False

    for comp_name, c in [("Frame", frame_c), ("Glass", glass_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{comp_name}: {len(names)} bodies -> {names}")

    sp.apply_appearance("walnut")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
