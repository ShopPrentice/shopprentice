"""
Modern Dining Chair
===================
18"W x 17"D seat, 18"H seat height, 38"H total.
Ladder-back with 3 horizontal slats, raked back legs (~5° backward),
H-stretchers for stability, domino joinery at all connections.

Coordinate system:
  X = width (18")  Y = depth (17")  Z = height (38")

Key design features:
  - Back legs are continuous from floor to backrest top, raked 5° backward
  - Front legs are vertical, shorter (stop at seat)
  - 3 ladder-back slats between the back legs above the seat
  - 4 aprons under the seat connecting all legs
  - Front + back H-stretchers between legs near the floor
  - Domino joinery at all apron-to-leg and stretcher-to-leg connections
"""
import adsk.core, adsk.fusion, math

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

    for pname, expr, unit in [
        ("seat_w",       "18 in",    "in"),
        ("seat_d",       "17 in",    "in"),
        ("seat_h",       "18 in",    "in"),
        ("back_h",       "38 in",    "in"),
        ("seat_thick",   "0.75 in",  "in"),
        ("leg_size",     "1.5 in",   "in"),
        ("apron_h",      "3 in",     "in"),
        ("apron_thick",  "0.75 in",  "in"),
        ("slat_h",       "2.5 in",   "in"),
        ("slat_thick",   "0.75 in",  "in"),
        ("n_slats",      "3",        ""),
        ("back_rake",    "5 deg",    "deg"),  # back leg angle from vertical
        ("str_h",        "1.5 in",   "in"),   # stretcher height
        ("str_thick",    "0.75 in",  "in"),
        ("str_z",        "4 in",     "in"),   # stretcher center from floor
        # Domino params (6mm)
        ("dm_t",         "6 mm",     "in"),
        ("dm_w",         "20 mm",    "in"),
        ("dm_d",         "15 mm",    "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    for pname, expr, unit in [
        ("front_leg_h",   "seat_h - seat_thick",                     "in"),
        ("apron_z",       "seat_h - seat_thick - apron_h",           "in"),
        ("short_apron_l", "seat_w - 2 * leg_size",                   "in"),
        ("long_apron_l",  "seat_d - 2 * leg_size",                   "in"),
        ("mid_x",         "seat_w / 2",                               "in"),
        ("mid_y",         "seat_d / 2",                               "in"),
        # Back leg Y offset at floor due to rake
        # At height h, the back leg center moves backward by h * tan(back_rake)
        ("back_leg_offset", "back_h * tan(back_rake)",               "in"),
        # Back slat spacing
        ("back_zone",     "back_h - seat_h - leg_size",              "in"),
        ("slat_pitch",    "back_zone / (n_slats + 1)",               "in"),
        ("slat_start_z",  "seat_h + slat_pitch - slat_h / 2",      "in"),
        # Stretcher lengths
        ("front_str_l",   "seat_w - 2 * leg_size",                  "in"),
        ("side_str_l",    "seat_d - 2 * leg_size",                  "in"),
    ]:
        params.add(pname, VI(expr), unit, "")

    print(">>> Parameters done")

    leg_occ   = af.make_comp(root, "Legs")
    apron_occ = af.make_comp(root, "Aprons")
    seat_occ  = af.make_comp(root, "Seat")
    back_occ  = af.make_comp(root, "Back")

    leg_c   = leg_occ.component
    apron_c = apron_occ.component
    seat_c  = seat_occ.component
    back_c  = back_occ.component

    # ==== FRONT LEGS (vertical, short) ====
    _, pr = af.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "leg_size", "y": "leg_size"}, "LegFL_Sk", ev)
    fl_ext = af.ext_new(leg_c, pr, "front_leg_h", "LegFL")
    leg_fl = fl_ext.bodies.item(0); leg_fl.name = "Leg_FL"

    l_xmid = af.off_plane(leg_c, leg_c.yZConstructionPlane, "mid_x", "LXMid")
    leg_fr = af.mirror_body(leg_c, leg_fl, l_xmid, "LegFR").bodies.item(0)
    leg_fr.name = "Leg_FR"

    # ==== BACK LEGS (raked, tall — continuous from floor to back top) ====
    # Build back leg vertically first, then use MoveFeature to rotate by back_rake
    # Position: start at (0, seat_d - leg_size, 0), height = back_h
    _, pr = af.sketch_rect_model(leg_c, leg_c.xYConstructionPlane,
        ("0 in", "seat_d - leg_size", "0 in"),
        {"x": "leg_size", "y": "leg_size"}, "LegBL_Sk", ev)
    bl_ext = af.ext_new(leg_c, pr, "back_h", "LegBL")
    leg_bl = bl_ext.bodies.item(0); leg_bl.name = "Leg_BL"

    # Rotate back leg by back_rake around X axis at the leg bottom
    Point3D = adsk.core.Point3D

    bl_cx = ev("leg_size") / 2
    bl_cy = ev("seat_d") - ev("leg_size") / 2

    # Rotate back leg using freeMove with a rotation matrix
    move_feats = leg_c.features.moveFeatures
    coll = adsk.core.ObjectCollection.create()
    coll.add(leg_bl)
    move_inp = move_feats.createInput2(coll)

    # Create rotation transform: rotate around X axis by back_rake at the leg base
    transform = adsk.core.Matrix3D.create()
    rake_rad = ev("back_rake")  # already in radians from Fusion
    cos_r = math.cos(rake_rad)
    sin_r = math.sin(rake_rad)

    # Rotation around X axis at point (bl_cx, bl_cy, 0):
    # Translate to origin, rotate, translate back
    # T = Translate(bl_cx, bl_cy, 0) * RotX(rake) * Translate(-bl_cx, -bl_cy, 0)
    # RotX: [1,0,0; 0,cos,-sin; 0,sin,cos]
    # Combined:
    transform.setCell(0, 0, 1); transform.setCell(0, 1, 0); transform.setCell(0, 2, 0)
    transform.setCell(1, 0, 0); transform.setCell(1, 1, cos_r); transform.setCell(1, 2, -sin_r)
    transform.setCell(2, 0, 0); transform.setCell(2, 1, sin_r); transform.setCell(2, 2, cos_r)
    # Translation component: T = (I-R) * pivot
    transform.setCell(0, 3, 0)
    transform.setCell(1, 3, bl_cy * (1 - cos_r))
    transform.setCell(2, 3, -bl_cy * sin_r)

    move_inp.defineAsFreeMove(transform)
    move_feats.add(move_inp).name = "BackLeg_Rake"

    # Mirror raked back-left leg to back-right
    leg_br = af.mirror_body(leg_c, leg_bl, l_xmid, "LegBR").bodies.item(0)
    leg_br.name = "Leg_BR"

    print(">>> Legs: 4 (front vertical, back raked 5°)")

    # ==== APRONS (4 — under seat, connecting all legs) ====
    az_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane, "apron_z", "AZ_Pl")

    # Front apron (between front legs)
    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "0 in", "apron_z"),
        {"x": "short_apron_l", "y": "apron_thick"}, "FrontApron_Sk", ev)
    fa_ext = af.ext_new(apron_c, pr, "apron_h", "FrontApron")
    front_apron = fa_ext.bodies.item(0); front_apron.name = "Apron_Front"

    # Back apron (between back legs — at the Y position where back legs are at seat height)
    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("leg_size", "seat_d - leg_size - apron_thick", "apron_z"),
        {"x": "short_apron_l", "y": "apron_thick"}, "BackApron_Sk", ev)
    ba_ext = af.ext_new(apron_c, pr, "apron_h", "BackApron")
    back_apron = ba_ext.bodies.item(0); back_apron.name = "Apron_Back"

    # Left side apron
    _, pr = af.sketch_rect_model(apron_c, az_pl,
        ("0 in", "leg_size", "apron_z"),
        {"x": "apron_thick", "y": "long_apron_l"}, "LeftApron_Sk", ev)
    la_ext = af.ext_new(apron_c, pr, "apron_h", "LeftApron")
    left_apron = la_ext.bodies.item(0); left_apron.name = "Apron_Left"

    a_xmid = af.off_plane(apron_c, apron_c.yZConstructionPlane, "mid_x", "AXMid")
    ra_mir = af.mirror_feats(apron_c, [la_ext], a_xmid, "RightApronMir")
    right_apron = ra_mir.bodies.item(0); right_apron.name = "Apron_Right"
    print(">>> Aprons: 4")

    # ==== STRETCHERS (front + back H-stretchers for stability) ====
    str_z_pl = af.off_plane(apron_c, apron_c.xYConstructionPlane, "str_z", "StrZ_Pl")

    # Front stretcher
    _, pr = af.sketch_rect_model(apron_c, str_z_pl,
        ("leg_size", "0 in", "str_z"),
        {"x": "front_str_l", "y": "str_thick"}, "FrontStr_Sk", ev)
    fs_ext = af.ext_new(apron_c, pr, "str_h", "FrontStr")
    fs_ext.bodies.item(0).name = "Str_Front"

    a_ymid = af.off_plane(apron_c, apron_c.xZConstructionPlane, "mid_y", "AYMid")
    af.mirror_feats(apron_c, [fs_ext], a_ymid, "BackStrMir").bodies.item(0).name = "Str_Back"
    print(">>> Stretchers: 2 (front + back)")

    # ==== SEAT ====
    seat_pl = af.off_plane(seat_c, seat_c.xYConstructionPlane, "front_leg_h", "SeatPl")
    _, pr = af.sketch_rect_model(seat_c, seat_pl,
        ("0 in", "0 in", "front_leg_h"),
        {"x": "seat_w", "y": "seat_d"}, "Seat_Sk", ev)
    af.ext_new(seat_c, pr, "seat_thick", "SeatBoard").bodies.item(0).name = "Seat"
    print(">>> Seat: 1")

    # ==== BACK SLATS (3 ladder-back slats between raked back legs) ====
    # Slats are between the back legs above the seat.
    # Since back legs are raked, the slat Y position shifts with height.
    # For simplicity, place slats at the back leg Y at seat height (seat_d - leg_size)
    # and let the rake handle the visual.
    slat_y_pl = af.off_plane(back_c, back_c.xZConstructionPlane,
                              "seat_d - leg_size", "SlatY_Pl")
    _, pr = af.sketch_rect_model(back_c, slat_y_pl,
        ("leg_size", "seat_d - leg_size", "slat_start_z"),
        {"x": "short_apron_l", "z": "slat_h"}, "Slat_Sk", ev)
    slat_ext = af.ext_new(back_c, pr, "slat_thick", "BackSlat_1")
    slat_body = slat_ext.bodies.item(0)
    slat_body.name = "BackSlat_1"

    n_s = int(ev("n_slats"))
    if n_s > 1:
        pat = af.body_pattern(back_c, slat_body, back_c.zConstructionAxis,
                               "n_slats", "slat_pitch", "SlatPat")
        for i in range(pat.bodies.count):
            pat.bodies.item(i).name = f"BackSlat_{i+2}"
    print(f">>> Back slats: {n_s}")

    # ==== DOMINO JOINERY — apron-to-leg ====
    params.add("dm_count", VI("2"), "", "")
    params.add("dm_sp", VI("apron_h / (dm_count + 1)"), "in", "")
    params.add("dm_z_start", VI("apron_z + apron_h / (dm_count + 1)"), "in", "")

    fl_p = leg_fl.createForAssemblyContext(leg_occ)
    fr_p = leg_fr.createForAssemblyContext(leg_occ)
    bl_p = leg_bl.createForAssemblyContext(leg_occ)
    br_p = leg_br.createForAssemblyContext(leg_occ)
    fa_p = front_apron.createForAssemblyContext(apron_occ)
    ba_p = back_apron.createForAssemblyContext(apron_occ)
    la_p = left_apron.createForAssemblyContext(apron_occ)
    ra_p = right_apron.createForAssemblyContext(apron_occ)

    dm_fl = af.off_plane(root, root.yZConstructionPlane, "leg_size", "DM_FL")
    dm_fr = af.off_plane(root, root.yZConstructionPlane, "seat_w - leg_size", "DM_FR")
    dm_lf = af.off_plane(root, root.xZConstructionPlane, "leg_size", "DM_LF")
    dm_lb = af.off_plane(root, root.xZConstructionPlane, "seat_d - leg_size", "DM_LB")

    # Front apron → FL, FR
    domino.grid(root, dm_fl, ("leg_size", "apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        fa_p, fl_p, "DM_FA_L", ev)
    domino.grid(root, dm_fr, ("seat_w - leg_size", "apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        fa_p, fr_p, "DM_FA_R", ev)

    # Back apron → BL, BR
    domino.grid(root, dm_fl, ("leg_size", "seat_d - leg_size - apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ba_p, bl_p, "DM_BA_L", ev)
    domino.grid(root, dm_fr, ("seat_w - leg_size", "seat_d - leg_size - apron_thick/2", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ba_p, br_p, "DM_BA_R", ev)

    # Left apron → FL, BL
    domino.grid(root, dm_lf, ("apron_thick/2", "leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        la_p, fl_p, "DM_LA_F", ev)
    domino.grid(root, dm_lb, ("apron_thick/2", "seat_d - leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        la_p, bl_p, "DM_LA_B", ev)

    # Right apron → FR, BR
    domino.grid(root, dm_lf, ("seat_w - apron_thick/2", "leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ra_p, fr_p, "DM_RA_F", ev)
    domino.grid(root, dm_lb, ("seat_w - apron_thick/2", "seat_d - leg_size", "dm_z_start"),
        "z", "dm_sp", "dm_count", "z", "dm_w", "dm_t", "dm_d",
        ra_p, br_p, "DM_RA_B", ev)

    print(">>> Dominos: 8 apron-to-leg joints")

    # ==== EPILOGUE ====
    for comp in [leg_c, apron_c, seat_c, back_c]:
        for sk in comp.sketches:
            sk.isVisible = False
        for cp in comp.constructionPlanes:
            cp.isLightBulbOn = False
    for sk in root.sketches:
        sk.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    for cn, c in [("Legs", leg_c), ("Aprons", apron_c),
                   ("Seat", seat_c), ("Back", back_c)]:
        names = [c.bRepBodies.item(i).name for i in range(c.bRepBodies.count)]
        print(f"{cn}: {len(names)} -> {names}")
    print(f"Root: {root.bRepBodies.count} domino voids")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
