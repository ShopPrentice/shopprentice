"""Fixture: Esherick stool seat — edited spline snapshot, with centre + leg anchors.

Captured from the user's in-Fusion edits. The hex-with-bulges formula and
the rail-bulge parameters have been replaced by explicit fit-point lists
(12 per plan section, 5 per rail) so this fixture now reproduces exactly
the shape the user drew by dragging control points.

Two shared reference frames are derived from the captured Es_Mid spline
and exposed as construction-sketch points so legs can attach reliably:

  Es_Center  — single SketchPoint at the centroid of the mid-section
               outline, at z = t / 2 (true 3D seat centre)

  Es_Legs    — three SketchPoints on z = 0 (seat bottom) arranged 120°
               apart around the centroid, aligned with the three corner
               indices of the edited plan (mid-section indices 3, 7, 11).
               Distance from centre = es_leg_spread.

Capture baseline: es_cx=0, es_cy=150. Changing es_cx/es_cy translates all
fit points. The mid-section scale is NOT exposed (baked in); es_t still
drives the construction-plane heights and hence the loft thickness.
"""
import math
import adsk.core, adsk.fusion


# ─── Captured plan sections (12 pts each, baseline es_cx=0 es_cy=150) ──
BOT_PLAN = [
    (9.6705, 156.7913), (6.9535, 154.7876), (3.8395, 153.4837),
    (3.1864, 153.7881), (2.5900, 154.1925), (2.1931, 157.5000),
    (2.5900, 160.8075), (3.1864, 161.2119), (3.8395, 161.5163),
    (6.9535, 160.2124), (9.6705, 158.2087), (9.7272, 157.5000),
]
MID_PLAN = [
    (10.6680, 154.9400), (7.7545, 153.3976), (3.8862, 151.9521),
    (2.2520, 152.1974), (1.4000, 152.7750), (1.2877, 157.3738),
    (1.5257, 162.1657), (2.2520, 162.8026), (3.2460, 163.1417),
    (7.2552, 161.5582), (10.6875, 160.0208), (11.5960, 157.5000),
]
TOP_PLAN = [
    (9.6705, 156.7913), (8.0358, 154.8266), (3.8395, 153.4837),
    (3.1864, 153.7881), (2.5929, 154.3090), (2.1931, 157.5000),
    (2.5900, 160.8075), (3.1864, 161.2119), (3.8395, 161.5163),
    (6.9535, 160.2124), (9.6705, 158.2087), (9.7272, 157.5000),
]

# ─── Captured rails (5 model-space 3D pts each) ───
# Each rail sits on a radial plane through the seat centroid axis and one
# triangle corner. Points [0] and [4] are anchors on the bot / top plan
# splines; points [1]–[3] are the draggable low / mid / high control points.
# Anchor points (indices 0, 2, 4) MUST exactly match the corresponding
# BOT_PLAN / MID_PLAN / TOP_PLAN entry at CORNER_INDICES[i], or the loft
# fails with "rails do not intersect all profiles".
RAIL_0 = [  # near index 3 — back-left corner
    (BOT_PLAN[3][0], BOT_PLAN[3][1], 0.0000),
    (2.2980, 152.2539, 0.2949),
    (MID_PLAN[3][0], MID_PLAN[3][1], 0.6250),
    (2.2948, 152.2485, 0.9625),
    (TOP_PLAN[3][0], TOP_PLAN[3][1], 1.2500),
]
RAIL_1 = [  # near index 7 — back-right corner
    (BOT_PLAN[7][0], BOT_PLAN[7][1], 0.0000),
    (2.4760, 162.4193, 0.2437),
    (MID_PLAN[7][0], MID_PLAN[7][1], 0.6250),
    (2.3200, 162.6845, 0.9751),
    (TOP_PLAN[7][0], TOP_PLAN[7][1], 1.2500),
]
RAIL_2 = [  # near index 11 — front apex
    (BOT_PLAN[11][0], BOT_PLAN[11][1], 0.0000),
    (11.0660, 157.5000, 0.1912),
    (MID_PLAN[11][0], MID_PLAN[11][1], 0.6250),
    (11.3109, 157.5000, 0.9781),
    (TOP_PLAN[11][0], TOP_PLAN[11][1], 1.2500),
]

# Which MID_PLAN indices the 3 rails anchor near (for deriving corner directions)
CORNER_INDICES = [3, 7, 11]


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters

    P = adsk.core.Point3D.create
    VI = adsk.core.ValueInput.createByString
    NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    params.add("es_cx", VI("0 cm"), "cm", "Anchor X (seat SW corner baseline 0)")
    params.add("es_cy", VI("150 cm"), "cm", "Anchor Y (seat SW corner baseline 150)")
    params.add("es_t",  VI("1.25 cm"), "cm", "Seat thickness")
    params.add("es_blend_weight", VI("3.0"), "",
               "Direction end-condition weight — higher = longer flat top before slope builds")
    params.add("es_leg_spread", VI("3 cm"), "cm",
               "Leg connection distance from seat centroid (at z=0)")

    ev = lambda e: (params.itemByName(e).value if params.itemByName(e)
                    else design.unitsManager.evaluateExpression(e, "cm"))

    ax, ay = ev("es_cx"), ev("es_cy")
    t = ev("es_t")
    leg_spread = ev("es_leg_spread")

    # Translation from captured baseline (0, 150) to current anchor
    dx, dy = ax - 0.0, ay - 150.0

    def shift_xy(pts):
        return [(x + dx, y + dy) for x, y in pts]

    def shift_xyz(pts):
        return [(x + dx, y + dy, z) for x, y, z in pts]

    def add_spline_plan(plane, z_val, pts_xy, name):
        sk = root.sketches.add(plane); sk.name = name
        coll = adsk.core.ObjectCollection.create()
        for mx, my in pts_xy:
            p = sk.modelToSketchSpace(P(mx, my, z_val))
            coll.add(P(p.x, p.y, 0))
        sp = sk.sketchCurves.sketchFittedSplines.add(coll)
        sp.isClosed = True
        return sk

    # Section 0 — bottom
    sk_bot = add_spline_plan(root.xYConstructionPlane, 0,
                             shift_xy(BOT_PLAN), "Es_Bot")

    # Section 1 — mid
    cpi_mid = root.constructionPlanes.createInput()
    cpi_mid.setByOffset(root.xYConstructionPlane, VI("es_t / 2"))
    cp_mid = root.constructionPlanes.add(cpi_mid); cp_mid.name = "Es_MidPl"
    sk_mid = add_spline_plan(cp_mid, t / 2, shift_xy(MID_PLAN), "Es_Mid")

    # Section 2 — top
    cpi_top = root.constructionPlanes.createInput()
    cpi_top.setByOffset(root.xYConstructionPlane, VI("es_t"))
    cp_top = root.constructionPlanes.add(cpi_top); cp_top.name = "Es_TopPl"
    sk_top = add_spline_plan(cp_top, t, shift_xy(TOP_PLAN), "Es_Top")

    # Centroid anchor sketch points (for setByThreePoints on rail planes)
    mid_translated = shift_xy(MID_PLAN)
    cent_x = sum(p[0] for p in mid_translated) / len(mid_translated)
    cent_y = sum(p[1] for p in mid_translated) / len(mid_translated)

    cb = sk_bot.modelToSketchSpace(P(cent_x, cent_y, 0))
    centroid_bot_pt = sk_bot.sketchPoints.add(P(cb.x, cb.y, 0))
    ct = sk_top.modelToSketchSpace(P(cent_x, cent_y, t))
    centroid_top_pt = sk_top.sketchPoints.add(P(ct.x, ct.y, 0))

    # Rails — hardcoded model-space fit points, translated by anchor offset
    def build_rail(rail_i, pts_3d, corner_model_mid):
        cx_m, cy_m = corner_model_mid
        ms = sk_mid.modelToSketchSpace(P(cx_m, cy_m, t / 2))
        corner_mid_pt = sk_mid.sketchPoints.add(P(ms.x, ms.y, 0))

        cpi_r = root.constructionPlanes.createInput()
        cpi_r.setByThreePoints(centroid_bot_pt, centroid_top_pt, corner_mid_pt)
        rail_pl = root.constructionPlanes.add(cpi_r)
        rail_pl.name = f"Es_RailPl{rail_i}"

        sk_rail = root.sketches.add(rail_pl); sk_rail.name = f"Es_Rail{rail_i}"
        fit_pts = adsk.core.ObjectCollection.create()
        for x, y, z in pts_3d:
            m = sk_rail.modelToSketchSpace(P(x, y, z))
            fit_pts.add(P(m.x, m.y, 0))
        return sk_rail.sketchCurves.sketchFittedSplines.add(fit_pts)

    corners_mid = [mid_translated[i] for i in CORNER_INDICES]
    rail_defs = [(0, shift_xyz(RAIL_0), corners_mid[0]),
                 (1, shift_xyz(RAIL_1), corners_mid[1]),
                 (2, shift_xyz(RAIL_2), corners_mid[2])]
    rail_splines = [build_rail(i, pts, corner) for i, pts, corner in rail_defs]

    # Loft: sections + tangent end conditions + 3 rails
    loft_inp = root.features.loftFeatures.createInput(NEWBODY)
    sec_bot = loft_inp.loftSections.add(sk_bot.profiles.item(0))
    loft_inp.loftSections.add(sk_mid.profiles.item(0))
    sec_top = loft_inp.loftSections.add(sk_top.profiles.item(0))
    sec_bot.setDirectionEndCondition(VI("0 deg"), VI("es_blend_weight"))
    sec_top.setDirectionEndCondition(VI("0 deg"), VI("es_blend_weight"))
    for rs in rail_splines:
        loft_inp.centerLineOrRails.addRail(rs)
    loft_inp.isSolid = True
    loft_inp.isTangentEdgesMerged = True
    loft = root.features.loftFeatures.add(loft_inp)
    loft.name = "EsherickSeatLoft"
    loft.bodies.item(0).name = "EsherickSeat"

    # ── Center + leg anchor sketch points ────────────────────────────
    # One sketch for the seat centre (z = t/2), another for the 3 leg
    # connection points (z = 0). Visible in the browser; usable as inputs
    # to subsequent features (leg tenon positioning, mortise cuts, etc.)
    sk_center = root.sketches.add(cp_mid)
    sk_center.name = "Es_Center"
    cs = sk_center.modelToSketchSpace(P(cent_x, cent_y, t / 2))
    sk_center.sketchPoints.add(P(cs.x, cs.y, 0))

    sk_legs = root.sketches.add(root.xYConstructionPlane)
    sk_legs.name = "Es_Legs"
    leg_positions = []
    for corner_xy in corners_mid:
        vx = corner_xy[0] - cent_x
        vy = corner_xy[1] - cent_y
        length = math.hypot(vx, vy)
        ux, uy = vx / length, vy / length
        leg_x = cent_x + ux * leg_spread
        leg_y = cent_y + uy * leg_spread
        leg_positions.append((leg_x, leg_y))
        ls = sk_legs.modelToSketchSpace(P(leg_x, leg_y, 0))
        sk_legs.sketchPoints.add(P(ls.x, ls.y, 0))

    print(f"Seat centre  (z=t/2): ({cent_x:.3f}, {cent_y:.3f}, {t/2:.3f})")
    for i, (lx, ly) in enumerate(leg_positions):
        print(f"Leg {i} anchor (z=0)  : ({lx:.3f}, {ly:.3f}, 0.000)")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
