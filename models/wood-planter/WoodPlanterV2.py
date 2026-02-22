"""
Wood Planter V2 — Parametric with Components, Mirror & Pattern
===============================================================
60" L × 20" W body, 30" tall, on 10" legs (40" total).
Frame construction with vertical tongue-and-groove slat infill.

V2 improvements over V1:
  • True parametric features (Sketch → Extrude) — updates when params change
  • Component grouping (Legs, LongRails, ShortRails, *Slats, Bottom)
  • Mirror & Pattern features for replication

All 18 dimensions are exposed as Fusion 360 User Parameters —
go to Modify → Change Parameters to adjust, and the model recomputes.

To run: Fusion 360 → Utilities → Add-Ins → My Scripts → (+) → select this folder → Run
"""
import adsk.core, adsk.fusion, adsk.cam, traceback, math


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        rootComp = design.rootComponent

        # ==============================================================
        #  USER PARAMETERS  (created with string expressions for units)
        # ==============================================================
        param_defs = [
            ("planter_length",    "60 in",    "Overall planter length"),
            ("planter_width",     "20 in",    "Overall planter width"),
            ("total_height",      "40 in",    "Total height including legs"),
            ("leg_below_body",    "10 in",    "Leg height below body"),
            ("leg_size",          "3 in",     "Leg cross-section, square"),
            ("rail_thickness",    "2 in",     "Rail thickness"),
            ("rail_height",       "3 in",     "Rail height"),
            ("tenon_depth",       "2 in",     "Tenon depth into mortise"),
            ("tenon_width",       "1.25 in",  "Tenon width"),
            ("tenon_height",      "1.25 in",  "Tenon height"),
            ("groove_width",      "0.375 in", "Frame groove width"),
            ("groove_depth",      "0.375 in", "Frame groove depth"),
            ("frame_tongue_thick","0.34 in",  "Tongue thickness for frame grooves"),
            ("bottom_thickness",  "0.75 in",  "Bottom panel thickness"),
            ("slat_width",        "4 in",     "Slat face width"),
            ("slat_thickness",    "0.5 in",   "Slat body thickness"),
            ("slat_tg_width",     "0.25 in",  "Slat-to-slat T&G width"),
            ("slat_tg_depth",     "0.25 in",  "Slat-to-slat T&G depth"),
        ]

        params = design.userParameters
        for pname, default_expr, comment in param_defs:
            existing = params.itemByName(pname)
            if not existing:
                params.add(pname,
                           adsk.core.ValueInput.createByString(default_expr),
                           "in", comment)

        # ==============================================================
        #  DERIVED EXPRESSION PARAMETERS
        # ==============================================================
        derived_defs = [
            ("long_shoulder",  "planter_length - 2 * leg_size",
             "Long rail shoulder length"),
            ("short_shoulder", "planter_width - 2 * leg_size",
             "Short rail shoulder length"),
            ("lo_z",           "leg_below_body",
             "Lower rail bottom Z"),
            ("hi_z",           "total_height - rail_height",
             "Upper rail bottom Z"),
            ("groove_offset",  "(rail_thickness - groove_width) / 2",
             "Groove inset from rail face"),
            ("tenon_gap",      "(rail_height - 2 * tenon_height) / 3",
             "Gap between tenons in mortise pattern"),
            ("long_t_zoff",    "(rail_height - 2 * tenon_height) / 3",
             "Long tenon Z offset within rail"),
            ("short_t_zoff",   "2 * (rail_height - 2 * tenon_height) / 3 + tenon_height",
             "Short tenon Z offset within rail"),
            ("body_z",         "leg_below_body + rail_height",
             "Slat visible area bottom Z"),
            ("body_h",         "total_height - rail_height - leg_below_body - rail_height",
             "Slat visible height"),
            ("full_slat_h",    "total_height - 2 * rail_height + 2 * groove_depth - leg_below_body",
             "Full slat height with tongues"),
            ("groove_span",    "total_height - leg_below_body",
             "Leg groove height (lo_z to top of leg)"),
            ("mid_x",          "planter_length / 2",
             "X midplane offset"),
            ("mid_y",          "planter_width / 2",
             "Y midplane offset"),
        ]

        for pname, expr, comment in derived_defs:
            existing = params.itemByName(pname)
            if not existing:
                params.add(pname,
                           adsk.core.ValueInput.createByString(expr),
                           "in", comment)

        # Parametric slat counts (dimensionless)
        for pname, expr, comment in [
            ("n_long_slats",  "floor(long_shoulder / slat_width)",
             "Number of slats per long side"),
            ("n_short_slats", "floor(short_shoulder / slat_width)",
             "Number of slats per short side"),
        ]:
            existing = params.itemByName(pname)
            if not existing:
                params.add(pname,
                           adsk.core.ValueInput.createByString(expr),
                           "", comment)

        # ==============================================================
        #  HELPER: read param value (cm) for positioning calculations
        # ==============================================================
        def pval(name):
            return params.itemByName(name).value  # cm

        # ==============================================================
        #  HELPER: Create a component occurrence under root
        # ==============================================================
        def make_component(name):
            occ = rootComp.occurrences.addNewComponent(
                adsk.core.Matrix3D.create())
            occ.component.name = name
            return occ, occ.component

        # ==============================================================
        #  HELPER: Sketch a rectangle on a given plane, return profile
        # ==============================================================
        def sketch_rect(comp, plane, x0_expr, y0_expr, w_expr, h_expr,
                        sketch_name="Sketch"):
            """Create a sketch with a constrained rectangle.
            x0/y0/w/h are parameter expressions (strings).
            'plane' is a construction plane or BRepFace.
            Returns (sketch, profile).
            """
            sk = comp.sketches.add(plane)
            sk.name = sketch_name
            lines = sk.sketchCurves.sketchLines
            # Draw rectangle from two corner points (approximate, then constrain)
            x0v = pval_expr(x0_expr)
            y0v = pval_expr(y0_expr)
            wv = pval_expr(w_expr)
            hv = pval_expr(h_expr)
            rect = lines.addTwoPointRectangle(
                adsk.core.Point3D.create(x0v, y0v, 0),
                adsk.core.Point3D.create(x0v + wv, y0v + hv, 0))
            # Constrain dimensions parametrically
            dims = sk.sketchDimensions
            # Width = horizontal line (rect[0] is bottom)
            d_w = dims.addDistanceDimension(
                rect[0].startSketchPoint, rect[0].endSketchPoint,
                adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                adsk.core.Point3D.create(x0v + wv / 2, y0v - 1, 0))
            d_w.parameter.expression = w_expr
            # Height = vertical line (rect[1] is right)
            d_h = dims.addDistanceDimension(
                rect[1].startSketchPoint, rect[1].endSketchPoint,
                adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                adsk.core.Point3D.create(x0v + wv + 1, y0v + hv / 2, 0))
            d_h.parameter.expression = h_expr
            # Position: distance from origin to corner
            origin = sk.originPoint
            d_x = dims.addDistanceDimension(
                origin, rect[0].startSketchPoint,
                adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                adsk.core.Point3D.create(x0v / 2, y0v - 2, 0))
            d_x.parameter.expression = x0_expr
            d_y = dims.addDistanceDimension(
                origin, rect[0].startSketchPoint,
                adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                adsk.core.Point3D.create(x0v - 1, y0v / 2, 0))
            d_y.parameter.expression = y0_expr
            prof = sk.profiles.item(0)
            return sk, prof

        def pval_expr(expr):
            """Evaluate a parameter expression to cm value."""
            p = params.itemByName(expr)
            if p:
                return p.value
            # It's a literal or complex expression — use unitsManager
            um = design.unitsManager
            try:
                return um.evaluateExpression(expr, "cm")
            except:
                return 0.0

        # ==============================================================
        #  HELPER: Extrude a profile
        # ==============================================================
        def extrude_new(comp, profile, dist_expr, name="Extrude"):
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByString(dist_expr))
            feat = extrudes.add(ext_input)
            feat.name = name
            return feat

        def extrude_cut(comp, profile, dist_expr, name="Cut"):
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation)
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByString(dist_expr))
            feat = extrudes.add(ext_input)
            feat.name = name
            return feat

        def extrude_cut_from(comp, profile, dist_expr, body, name="Cut"):
            """Cut targeting a specific body only (won't affect adjacent bodies)."""
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation)
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByString(dist_expr))
            ext_input.participantBodies = [body]
            feat = extrudes.add(ext_input)
            feat.name = name
            return feat

        def extrude_join_to(comp, profile, dist_expr, body, name="Join"):
            """Join targeting a specific body only (won't merge adjacent bodies)."""
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.JoinFeatureOperation)
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByString(dist_expr))
            ext_input.participantBodies = [body]
            feat = extrudes.add(ext_input)
            feat.name = name
            return feat

        def extrude_join(comp, profile, dist_expr, name="Join"):
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.JoinFeatureOperation)
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByString(dist_expr))
            feat = extrudes.add(ext_input)
            feat.name = name
            return feat

        # ==============================================================
        #  HELPER: Offset construction plane
        # ==============================================================
        def offset_plane(comp, base_plane, offset_expr, name="Plane"):
            planes = comp.constructionPlanes
            plane_input = planes.createInput()
            plane_input.setByOffset(
                base_plane,
                adsk.core.ValueInput.createByString(offset_expr))
            plane = planes.add(plane_input)
            plane.name = name
            return plane

        # ==============================================================
        #  HELPER: Mirror bodies across a construction plane
        # ==============================================================
        def mirror_bodies(comp, bodies, plane, name="Mirror"):
            mirror_feats = comp.features.mirrorFeatures
            body_coll = adsk.core.ObjectCollection.create()
            for b in bodies:
                body_coll.add(b)
            mirror_input = mirror_feats.createInput(body_coll, plane)
            feat = mirror_feats.add(mirror_input)
            feat.name = name
            return feat

        def mirror_features(comp, features, plane, name="Mirror"):
            """Mirror a list of features across a construction plane."""
            mirror_feats = comp.features.mirrorFeatures
            feat_coll = adsk.core.ObjectCollection.create()
            for f in features:
                feat_coll.add(f)
            mirror_input = mirror_feats.createInput(feat_coll, plane)
            feat = mirror_feats.add(mirror_input)
            feat.name = name
            return feat

        # ==============================================================
        #  CONSTRUCTION MIDPLANES (on root for mirror operations)
        # ==============================================================
        # We create midplanes in each component as needed.

        # ==============================================================
        #  BUILD LEGS
        # ==============================================================
        leg_occ, leg_comp = make_component("Legs")

        # XY plane of the leg component for base sketch
        leg_xy = leg_comp.xYConstructionPlane
        leg_xz = leg_comp.xZConstructionPlane
        leg_yz = leg_comp.yZConstructionPlane

        # --- Front-Left leg: post at origin corner ---
        sk_leg, prof_leg = sketch_rect(
            leg_comp, leg_xy,
            "0 in", "0 in", "leg_size", "leg_size",
            "FL_Leg_Section")
        ext_leg = extrude_new(leg_comp, prof_leg, "total_height", "FL_Leg")
        fl_leg_body = ext_leg.bodies.item(0)
        fl_leg_body.name = "Leg_FL"

        # --- Mortise cuts on FL leg ---
        # Each leg gets 4 mortises (long side upper/lower, short side upper/lower)
        # Long-side mortises: on +X face of FL leg
        # Lower long mortise
        mort_plane_lo = offset_plane(leg_comp, leg_xy, "lo_z + long_t_zoff", "Lo_Rail_Plane")

        # Long mortise at lower rail: on +X face, centered in rail_thickness on Y
        sk_m1, pr_m1 = sketch_rect(
            leg_comp, mort_plane_lo,
            "leg_size - tenon_depth", "(rail_thickness - tenon_width) / 2",
            "tenon_depth", "tenon_width",
            "FL_Mort_Long_Lo")
        extrude_cut(leg_comp, pr_m1, "tenon_height", "Cut_Mort_Long_Lo_1")

        # Second long mortise (offset higher in the rail)
        mort_plane_lo2 = offset_plane(leg_comp, leg_xy,
            "lo_z + 2 * (rail_height - 2 * tenon_height) / 3 + tenon_height",
            "Lo_Rail_Plane_2")
        # Short-side mortise at lower rail: on +Y face
        sk_m2, pr_m2 = sketch_rect(
            leg_comp, mort_plane_lo2,
            "(rail_thickness - tenon_width) / 2", "leg_size - tenon_depth",
            "tenon_width", "tenon_depth",
            "FL_Mort_Short_Lo")
        extrude_cut(leg_comp, pr_m2, "tenon_height", "Cut_Mort_Short_Lo_1")

        # Upper rail mortises
        mort_plane_hi = offset_plane(leg_comp, leg_xy, "hi_z + long_t_zoff", "Hi_Rail_Plane")

        sk_m3, pr_m3 = sketch_rect(
            leg_comp, mort_plane_hi,
            "leg_size - tenon_depth", "(rail_thickness - tenon_width) / 2",
            "tenon_depth", "tenon_width",
            "FL_Mort_Long_Hi")
        extrude_cut(leg_comp, pr_m3, "tenon_height", "Cut_Mort_Long_Hi_1")

        mort_plane_hi2 = offset_plane(leg_comp, leg_xy,
            "hi_z + 2 * (rail_height - 2 * tenon_height) / 3 + tenon_height",
            "Hi_Rail_Plane_2")
        sk_m4, pr_m4 = sketch_rect(
            leg_comp, mort_plane_hi2,
            "(rail_thickness - tenon_width) / 2", "leg_size - tenon_depth",
            "tenon_width", "tenon_depth",
            "FL_Mort_Short_Hi")
        extrude_cut(leg_comp, pr_m4, "tenon_height", "Cut_Mort_Short_Hi_1")

        # --- Grooves on FL leg ---
        # X-face groove (for front slats): runs from lo_z to hi_z + rail_height
        grv_plane = offset_plane(leg_comp, leg_xy, "lo_z", "Groove_Plane")
        sk_gx, pr_gx = sketch_rect(
            leg_comp, grv_plane,
            "leg_size - groove_depth", "groove_offset",
            "groove_depth", "groove_width",
            "FL_Groove_X")
        extrude_cut(leg_comp, pr_gx, "groove_span", "Cut_Groove_X")

        # Y-face groove (for left slats)
        sk_gy, pr_gy = sketch_rect(
            leg_comp, grv_plane,
            "groove_offset", "leg_size - groove_depth",
            "groove_width", "groove_depth",
            "FL_Groove_Y")
        extrude_cut(leg_comp, pr_gy, "groove_span", "Cut_Groove_Y")

        # --- Mirror FL leg to create all 4 legs ---
        mid_yz = offset_plane(leg_comp, leg_yz, "mid_x", "MidPlane_YZ")
        mid_xz = offset_plane(leg_comp, leg_xz, "mid_y", "MidPlane_XZ")

        mir_x = mirror_bodies(leg_comp, [fl_leg_body], mid_yz, "Mirror_X_Legs")
        fr_leg_body = mir_x.bodies.item(0)
        fr_leg_body.name = "Leg_FR"

        all_x_legs = [fl_leg_body, fr_leg_body]
        mir_y = mirror_bodies(leg_comp, all_x_legs, mid_xz, "Mirror_Y_Legs")
        mir_y.bodies.item(0).name = "Leg_BL"
        mir_y.bodies.item(1).name = "Leg_BR"

        # ==============================================================
        #  BUILD LONG RAILS (Front & Back)
        # ==============================================================
        lr_occ, lr_comp = make_component("LongRails")

        lr_xy = lr_comp.xYConstructionPlane
        lr_xz = lr_comp.xZConstructionPlane
        lr_yz = lr_comp.yZConstructionPlane

        # Front lower rail
        fl_rail_plane = offset_plane(lr_comp, lr_xy, "lo_z", "FrontLo_Plane")
        sk_flr, pr_flr = sketch_rect(
            lr_comp, fl_rail_plane,
            "leg_size", "0 in",
            "long_shoulder", "rail_thickness",
            "FrontLo_Section")
        ext_flr = extrude_new(lr_comp, pr_flr, "rail_height", "FrontLo_Rail")
        flo_body = ext_flr.bodies.item(0)
        flo_body.name = "LongRail_Front_Lower"

        # Tenons for front lower rail (both ends)
        flo_tenon_plane = offset_plane(lr_comp, lr_xy,
            "lo_z + long_t_zoff", "FrontLo_Tenon_Plane")
        sk_flt1, pr_flt1 = sketch_rect(
            lr_comp, flo_tenon_plane,
            "leg_size - tenon_depth", "(rail_thickness - tenon_width) / 2",
            "tenon_depth", "tenon_width",
            "FrontLo_Tenon_L")
        extrude_join(lr_comp, pr_flt1, "tenon_height", "Join_FrontLo_Tenon_L")

        sk_flt2, pr_flt2 = sketch_rect(
            lr_comp, flo_tenon_plane,
            "leg_size + long_shoulder", "(rail_thickness - tenon_width) / 2",
            "tenon_depth", "tenon_width",
            "FrontLo_Tenon_R")
        extrude_join(lr_comp, pr_flt2, "tenon_height", "Join_FrontLo_Tenon_R")

        # Groove on top of front lower rail (for slats)
        flo_grv_plane = offset_plane(lr_comp, lr_xy,
            "lo_z + rail_height - groove_depth", "FrontLo_Groove_Plane")
        sk_flg, pr_flg = sketch_rect(
            lr_comp, flo_grv_plane,
            "leg_size", "groove_offset",
            "long_shoulder", "groove_width",
            "FrontLo_Groove")
        extrude_cut(lr_comp, pr_flg, "groove_depth", "Cut_FrontLo_Groove")

        # Front upper rail
        fu_rail_plane = offset_plane(lr_comp, lr_xy, "hi_z", "FrontHi_Plane")
        sk_fur, pr_fur = sketch_rect(
            lr_comp, fu_rail_plane,
            "leg_size", "0 in",
            "long_shoulder", "rail_thickness",
            "FrontHi_Section")
        ext_fur = extrude_new(lr_comp, pr_fur, "rail_height", "FrontHi_Rail")
        fhi_body = ext_fur.bodies.item(0)
        fhi_body.name = "LongRail_Front_Upper"

        # Tenons for front upper rail
        fhi_tenon_plane = offset_plane(lr_comp, lr_xy,
            "hi_z + long_t_zoff", "FrontHi_Tenon_Plane")
        sk_fut1, pr_fut1 = sketch_rect(
            lr_comp, fhi_tenon_plane,
            "leg_size - tenon_depth", "(rail_thickness - tenon_width) / 2",
            "tenon_depth", "tenon_width",
            "FrontHi_Tenon_L")
        extrude_join(lr_comp, pr_fut1, "tenon_height", "Join_FrontHi_Tenon_L")

        sk_fut2, pr_fut2 = sketch_rect(
            lr_comp, fhi_tenon_plane,
            "leg_size + long_shoulder", "(rail_thickness - tenon_width) / 2",
            "tenon_depth", "tenon_width",
            "FrontHi_Tenon_R")
        extrude_join(lr_comp, pr_fut2, "tenon_height", "Join_FrontHi_Tenon_R")

        # Groove on bottom of front upper rail
        sk_fug, pr_fug = sketch_rect(
            lr_comp, fu_rail_plane,
            "leg_size", "groove_offset",
            "long_shoulder", "groove_width",
            "FrontHi_Groove")
        extrude_cut(lr_comp, pr_fug, "groove_depth", "Cut_FrontHi_Groove")

        # Mirror front rails → back rails
        lr_mid_xz = offset_plane(lr_comp, lr_xz, "mid_y", "LR_MidPlane_XZ")
        mir_lr = mirror_bodies(lr_comp, [flo_body, fhi_body], lr_mid_xz,
                               "Mirror_LongRails")
        mir_lr.bodies.item(0).name = "LongRail_Back_Lower"
        mir_lr.bodies.item(1).name = "LongRail_Back_Upper"

        # ==============================================================
        #  BUILD SHORT RAILS (Left & Right)
        # ==============================================================
        sr_occ, sr_comp = make_component("ShortRails")

        sr_xy = sr_comp.xYConstructionPlane
        sr_xz = sr_comp.xZConstructionPlane
        sr_yz = sr_comp.yZConstructionPlane

        # Left lower rail
        ll_rail_plane = offset_plane(sr_comp, sr_xy, "lo_z", "LeftLo_Plane")
        sk_llr, pr_llr = sketch_rect(
            sr_comp, ll_rail_plane,
            "0 in", "leg_size",
            "rail_thickness", "short_shoulder",
            "LeftLo_Section")
        ext_llr = extrude_new(sr_comp, pr_llr, "rail_height", "LeftLo_Rail")
        llo_body = ext_llr.bodies.item(0)
        llo_body.name = "ShortRail_Left_Lower"

        # Tenons for left lower rail
        llo_tenon_plane = offset_plane(sr_comp, sr_xy,
            "lo_z + short_t_zoff", "LeftLo_Tenon_Plane")
        sk_llt1, pr_llt1 = sketch_rect(
            sr_comp, llo_tenon_plane,
            "(rail_thickness - tenon_width) / 2", "leg_size - tenon_depth",
            "tenon_width", "tenon_depth",
            "LeftLo_Tenon_F")
        extrude_join(sr_comp, pr_llt1, "tenon_height", "Join_LeftLo_Tenon_F")

        sk_llt2, pr_llt2 = sketch_rect(
            sr_comp, llo_tenon_plane,
            "(rail_thickness - tenon_width) / 2", "leg_size + short_shoulder",
            "tenon_width", "tenon_depth",
            "LeftLo_Tenon_B")
        extrude_join(sr_comp, pr_llt2, "tenon_height", "Join_LeftLo_Tenon_B")

        # Groove on top of left lower rail
        llo_grv_plane = offset_plane(sr_comp, sr_xy,
            "lo_z + rail_height - groove_depth", "LeftLo_Groove_Plane")
        sk_llg, pr_llg = sketch_rect(
            sr_comp, llo_grv_plane,
            "groove_offset", "leg_size",
            "groove_width", "short_shoulder",
            "LeftLo_Groove")
        extrude_cut(sr_comp, pr_llg, "groove_depth", "Cut_LeftLo_Groove")

        # Left upper rail
        lu_rail_plane = offset_plane(sr_comp, sr_xy, "hi_z", "LeftHi_Plane")
        sk_lur, pr_lur = sketch_rect(
            sr_comp, lu_rail_plane,
            "0 in", "leg_size",
            "rail_thickness", "short_shoulder",
            "LeftHi_Section")
        ext_lur = extrude_new(sr_comp, pr_lur, "rail_height", "LeftHi_Rail")
        lhi_body = ext_lur.bodies.item(0)
        lhi_body.name = "ShortRail_Left_Upper"

        # Tenons for left upper rail
        lhi_tenon_plane = offset_plane(sr_comp, sr_xy,
            "hi_z + short_t_zoff", "LeftHi_Tenon_Plane")
        sk_lut1, pr_lut1 = sketch_rect(
            sr_comp, lhi_tenon_plane,
            "(rail_thickness - tenon_width) / 2", "leg_size - tenon_depth",
            "tenon_width", "tenon_depth",
            "LeftHi_Tenon_F")
        extrude_join(sr_comp, pr_lut1, "tenon_height", "Join_LeftHi_Tenon_F")

        sk_lut2, pr_lut2 = sketch_rect(
            sr_comp, lhi_tenon_plane,
            "(rail_thickness - tenon_width) / 2", "leg_size + short_shoulder",
            "tenon_width", "tenon_depth",
            "LeftHi_Tenon_B")
        extrude_join(sr_comp, pr_lut2, "tenon_height", "Join_LeftHi_Tenon_B")

        # Groove on bottom of left upper rail
        sk_lug, pr_lug = sketch_rect(
            sr_comp, lu_rail_plane,
            "groove_offset", "leg_size",
            "groove_width", "short_shoulder",
            "LeftHi_Groove")
        extrude_cut(sr_comp, pr_lug, "groove_depth", "Cut_LeftHi_Groove")

        # Mirror left rails → right rails
        sr_mid_yz = offset_plane(sr_comp, sr_yz, "mid_x", "SR_MidPlane_YZ")
        mir_sr = mirror_bodies(sr_comp, [llo_body, lhi_body], sr_mid_yz,
                               "Mirror_ShortRails")
        mir_sr.bodies.item(0).name = "ShortRail_Right_Lower"
        mir_sr.bodies.item(1).name = "ShortRail_Right_Upper"

        # ==============================================================
        #  BUILD SLATS (mirror template + independent patterns per side)
        # ==============================================================
        sl_occ, sl_comp = make_component("Slats")

        sl_xy = sl_comp.xYConstructionPlane
        sl_xz = sl_comp.xZConstructionPlane
        sl_yz = sl_comp.yZConstructionPlane

        # Shared construction planes
        sl_body_plane = offset_plane(sl_comp, sl_xy, "body_z", "Slat_BodyZ")
        sl_top_plane  = offset_plane(sl_comp, sl_xy, "hi_z", "Slat_TopZ")
        sl_bot_plane  = offset_plane(sl_comp, sl_xy,
            "lo_z + rail_height - groove_depth", "Slat_BotZ")

        # Midplanes for mirror operations
        sl_mid_xz = offset_plane(sl_comp, sl_xz, "mid_y", "Slat_MidXZ")
        sl_mid_yz = offset_plane(sl_comp, sl_yz, "mid_x", "Slat_MidYZ")

        pat_feats = sl_comp.features.rectangularPatternFeatures

        # Y expressions for front slats (centered on front rail groove)
        fy_body = "groove_offset + groove_width / 2 - slat_thickness / 2"
        fy_tng  = "groove_offset + groove_width / 2 - frame_tongue_thick / 2"
        fy_tg   = "groove_offset + groove_width / 2 - slat_tg_width / 2"

        # ---- FRONT SLAT TEMPLATE ----
        front_tmpl_feats = []

        sk_ft, pr_ft = sketch_rect(sl_comp, sl_body_plane,
            "leg_size", fy_body, "slat_width", "slat_thickness",
            "FrontSlat_Body")
        ext_ft = extrude_new(sl_comp, pr_ft, "body_h", "FrontSlat_Body")
        front_tmpl_feats.append(ext_ft)
        front_tmpl = ext_ft.bodies.item(0)
        front_tmpl.name = "Slat_Front_1"

        sk_fg, pr_fg = sketch_rect(sl_comp, sl_body_plane,
            "leg_size", fy_tg, "slat_tg_depth", "slat_tg_width",
            "FrontSlat_LeftGroove")
        front_tmpl_feats.append(
            extrude_cut(sl_comp, pr_fg, "body_h", "Cut_Front_LeftGroove"))

        sk_frt, pr_frt = sketch_rect(sl_comp, sl_body_plane,
            "leg_size + slat_width", fy_tg, "slat_tg_depth", "slat_tg_width",
            "FrontSlat_RightTongue")
        front_tmpl_feats.append(
            extrude_join(sl_comp, pr_frt, "body_h", "Join_Front_RightTG"))

        sk_ftt, pr_ftt = sketch_rect(sl_comp, sl_top_plane,
            "leg_size", fy_tng, "slat_width", "frame_tongue_thick",
            "FrontSlat_TopTongue")
        front_tmpl_feats.append(
            extrude_join(sl_comp, pr_ftt, "groove_depth", "Join_Front_TopTng"))

        sk_fbt, pr_fbt = sketch_rect(sl_comp, sl_bot_plane,
            "leg_size", fy_tng, "slat_width", "frame_tongue_thick",
            "FrontSlat_BotTongue")
        front_tmpl_feats.append(
            extrude_join(sl_comp, pr_fbt, "groove_depth", "Join_Front_BotTng"))

        # ---- MIRROR FRONT TEMPLATE → BACK TEMPLATE ----
        mir_back_tmpl = mirror_features(sl_comp, front_tmpl_feats, sl_mid_xz,
                                        "Mirror_FrontTmpl_to_Back")
        back_tmpl = mir_back_tmpl.bodies.item(0)
        back_tmpl.name = "Slat_Back_1"

        # ---- PATTERN FRONT along X ----
        f_coll = adsk.core.ObjectCollection.create()
        f_coll.add(front_tmpl)
        pat_f_in = pat_feats.createInput(f_coll,
            sl_comp.xConstructionAxis,
            adsk.core.ValueInput.createByString("n_long_slats"),
            adsk.core.ValueInput.createByString("slat_width"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        pat_front = pat_feats.add(pat_f_in)
        pat_front.name = "Pattern_FrontSlats"
        for i in range(pat_front.bodies.count):
            pat_front.bodies.item(i).name = f"Slat_Front_{i + 2}"

        # ---- PATTERN BACK along X (independent, same parametric count) ----
        b_coll = adsk.core.ObjectCollection.create()
        b_coll.add(back_tmpl)
        pat_b_in = pat_feats.createInput(b_coll,
            sl_comp.xConstructionAxis,
            adsk.core.ValueInput.createByString("n_long_slats"),
            adsk.core.ValueInput.createByString("slat_width"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        pat_back = pat_feats.add(pat_b_in)
        pat_back.name = "Pattern_BackSlats"
        for i in range(pat_back.bodies.count):
            pat_back.bodies.item(i).name = f"Slat_Back_{i + 2}"

        # ---- FRONT LEFT-EDGE TONGUE (after pattern, only affects original) ----
        sk_fle, pr_fle = sketch_rect(sl_comp, sl_bot_plane,
            "leg_size - groove_depth", fy_tng,
            "groove_depth", "frame_tongue_thick",
            "FrontSlat_LeftEdge")
        front_edge_feat = extrude_join(sl_comp, pr_fle, "full_slat_h",
                                       "Join_Front_LeftEdge")
        # Mirror front edge tongue → back
        mirror_features(sl_comp, [front_edge_feat], sl_mid_xz,
                        "Mirror_FrontEdge_to_Back")

        # ---- FRONT GAP SLAT ----
        gap_long_cm = pval("long_shoulder") - pval("slat_width") * int(pval("n_long_slats"))
        if gap_long_cm > 0.01:
            n_long_pat = int(pval("n_long_slats"))
            fg_x = "leg_size + slat_width * n_long_slats"
            fg_w = "long_shoulder - slat_width * n_long_slats"
            front_gap_feats = []

            sk_fgb, pr_fgb = sketch_rect(sl_comp, sl_body_plane,
                fg_x, fy_body, fg_w, "slat_thickness",
                "FrontGap_Body")
            ext_fgb = extrude_new(sl_comp, pr_fgb, "body_h", "FrontGap_Body")
            front_gap_feats.append(ext_fgb)
            front_gap_body = ext_fgb.bodies.item(0)
            front_gap_body.name = f"Slat_Front_{n_long_pat + 1}"

            sk_fgg, pr_fgg = sketch_rect(sl_comp, sl_body_plane,
                fg_x, fy_tg, "slat_tg_depth", "slat_tg_width",
                "FrontGap_LeftGroove")
            front_gap_feats.append(extrude_cut_from(sl_comp, pr_fgg, "body_h",
                front_gap_body, "Cut_FrontGap_LeftGroove"))

            sk_fge, pr_fge = sketch_rect(sl_comp, sl_bot_plane,
                "leg_size + long_shoulder", fy_tng,
                "groove_depth", "frame_tongue_thick",
                "FrontGap_RightEdge")
            front_gap_feats.append(extrude_join_to(sl_comp, pr_fge, "full_slat_h",
                front_gap_body, "Join_FrontGap_RightEdge"))

            sk_fgt, pr_fgt = sketch_rect(sl_comp, sl_top_plane,
                fg_x, fy_tng, fg_w, "frame_tongue_thick",
                "FrontGap_TopTongue")
            front_gap_feats.append(extrude_join_to(sl_comp, pr_fgt, "groove_depth",
                front_gap_body, "Join_FrontGap_TopTng"))

            sk_fgbt, pr_fgbt = sketch_rect(sl_comp, sl_bot_plane,
                fg_x, fy_tng, fg_w, "frame_tongue_thick",
                "FrontGap_BotTongue")
            front_gap_feats.append(extrude_join_to(sl_comp, pr_fgbt, "groove_depth",
                front_gap_body, "Join_FrontGap_BotTng"))

            # Mirror front gap features → back gap
            mir_back_gap = mirror_features(sl_comp, front_gap_feats, sl_mid_xz,
                                           "Mirror_FrontGap_to_Back")
            for i in range(mir_back_gap.bodies.count):
                mir_back_gap.bodies.item(i).name = f"Slat_Back_{n_long_pat + 1}"

        # ---- LEFT SLAT TEMPLATE ----
        left_tmpl_feats = []

        lx_body = "groove_offset + groove_width / 2 - slat_thickness / 2"
        lx_tng  = "groove_offset + groove_width / 2 - frame_tongue_thick / 2"
        lx_tg   = "groove_offset + groove_width / 2 - slat_tg_width / 2"

        sk_lt, pr_lt = sketch_rect(sl_comp, sl_body_plane,
            lx_body, "leg_size", "slat_thickness", "slat_width",
            "LeftSlat_Body")
        ext_lt = extrude_new(sl_comp, pr_lt, "body_h", "LeftSlat_Body")
        left_tmpl_feats.append(ext_lt)
        left_tmpl = ext_lt.bodies.item(0)
        left_tmpl.name = "Slat_Left_1"

        sk_lg, pr_lg = sketch_rect(sl_comp, sl_body_plane,
            lx_tg, "leg_size", "slat_tg_width", "slat_tg_depth",
            "LeftSlat_FrontGroove")
        left_tmpl_feats.append(
            extrude_cut(sl_comp, pr_lg, "body_h", "Cut_Left_FrontGroove"))

        sk_lbt, pr_lbt = sketch_rect(sl_comp, sl_body_plane,
            lx_tg, "leg_size + slat_width", "slat_tg_width", "slat_tg_depth",
            "LeftSlat_BackTongue")
        left_tmpl_feats.append(
            extrude_join(sl_comp, pr_lbt, "body_h", "Join_Left_BackTG"))

        sk_ltt, pr_ltt = sketch_rect(sl_comp, sl_top_plane,
            lx_tng, "leg_size", "frame_tongue_thick", "slat_width",
            "LeftSlat_TopTongue")
        left_tmpl_feats.append(
            extrude_join(sl_comp, pr_ltt, "groove_depth", "Join_Left_TopTng"))

        sk_lbt2, pr_lbt2 = sketch_rect(sl_comp, sl_bot_plane,
            lx_tng, "leg_size", "frame_tongue_thick", "slat_width",
            "LeftSlat_BotTongue")
        left_tmpl_feats.append(
            extrude_join(sl_comp, pr_lbt2, "groove_depth", "Join_Left_BotTng"))

        # ---- MIRROR LEFT TEMPLATE → RIGHT TEMPLATE ----
        mir_right_tmpl = mirror_features(sl_comp, left_tmpl_feats, sl_mid_yz,
                                         "Mirror_LeftTmpl_to_Right")
        right_tmpl = mir_right_tmpl.bodies.item(0)
        right_tmpl.name = "Slat_Right_1"

        # ---- PATTERN LEFT along Y ----
        l_coll = adsk.core.ObjectCollection.create()
        l_coll.add(left_tmpl)
        pat_l_in = pat_feats.createInput(l_coll,
            sl_comp.yConstructionAxis,
            adsk.core.ValueInput.createByString("n_short_slats"),
            adsk.core.ValueInput.createByString("slat_width"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        pat_left = pat_feats.add(pat_l_in)
        pat_left.name = "Pattern_LeftSlats"
        for i in range(pat_left.bodies.count):
            pat_left.bodies.item(i).name = f"Slat_Left_{i + 2}"

        # ---- PATTERN RIGHT along Y (independent, same parametric count) ----
        r_coll = adsk.core.ObjectCollection.create()
        r_coll.add(right_tmpl)
        pat_r_in = pat_feats.createInput(r_coll,
            sl_comp.yConstructionAxis,
            adsk.core.ValueInput.createByString("n_short_slats"),
            adsk.core.ValueInput.createByString("slat_width"),
            adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        pat_right = pat_feats.add(pat_r_in)
        pat_right.name = "Pattern_RightSlats"
        for i in range(pat_right.bodies.count):
            pat_right.bodies.item(i).name = f"Slat_Right_{i + 2}"

        # ---- LEFT FRONT-EDGE TONGUE (after pattern, only affects original) ----
        sk_lle, pr_lle = sketch_rect(sl_comp, sl_bot_plane,
            lx_tng, "leg_size - groove_depth",
            "frame_tongue_thick", "groove_depth",
            "LeftSlat_FrontEdge")
        left_edge_feat = extrude_join(sl_comp, pr_lle, "full_slat_h",
                                      "Join_Left_FrontEdge")
        # Mirror left edge tongue → right
        mirror_features(sl_comp, [left_edge_feat], sl_mid_yz,
                        "Mirror_LeftEdge_to_Right")

        # ---- LEFT GAP SLAT ----
        gap_short_cm = pval("short_shoulder") - pval("slat_width") * int(pval("n_short_slats"))
        if gap_short_cm > 0.01:
            n_short_pat = int(pval("n_short_slats"))
            lg_y = "leg_size + slat_width * n_short_slats"
            lg_h = "short_shoulder - slat_width * n_short_slats"
            left_gap_feats = []

            sk_lgb, pr_lgb = sketch_rect(sl_comp, sl_body_plane,
                lx_body, lg_y, "slat_thickness", lg_h,
                "LeftGap_Body")
            ext_lgb = extrude_new(sl_comp, pr_lgb, "body_h", "LeftGap_Body")
            left_gap_feats.append(ext_lgb)
            left_gap_body = ext_lgb.bodies.item(0)
            left_gap_body.name = f"Slat_Left_{n_short_pat + 1}"

            sk_lgg, pr_lgg = sketch_rect(sl_comp, sl_body_plane,
                lx_tg, lg_y, "slat_tg_width", "slat_tg_depth",
                "LeftGap_FrontGroove")
            left_gap_feats.append(extrude_cut_from(sl_comp, pr_lgg, "body_h",
                left_gap_body, "Cut_LeftGap_FrontGroove"))

            sk_lge, pr_lge = sketch_rect(sl_comp, sl_bot_plane,
                lx_tng, "leg_size + short_shoulder",
                "frame_tongue_thick", "groove_depth",
                "LeftGap_BackEdge")
            left_gap_feats.append(extrude_join_to(sl_comp, pr_lge, "full_slat_h",
                left_gap_body, "Join_LeftGap_BackEdge"))

            sk_lgt, pr_lgt = sketch_rect(sl_comp, sl_top_plane,
                lx_tng, lg_y, "frame_tongue_thick", lg_h,
                "LeftGap_TopTongue")
            left_gap_feats.append(extrude_join_to(sl_comp, pr_lgt, "groove_depth",
                left_gap_body, "Join_LeftGap_TopTng"))

            sk_lgbt, pr_lgbt = sketch_rect(sl_comp, sl_bot_plane,
                lx_tng, lg_y, "frame_tongue_thick", lg_h,
                "LeftGap_BotTongue")
            left_gap_feats.append(extrude_join_to(sl_comp, pr_lgbt, "groove_depth",
                left_gap_body, "Join_LeftGap_BotTng"))

            # Mirror left gap features → right gap
            mir_right_gap = mirror_features(sl_comp, left_gap_feats, sl_mid_yz,
                                            "Mirror_LeftGap_to_Right")
            for i in range(mir_right_gap.bodies.count):
                mir_right_gap.bodies.item(i).name = f"Slat_Right_{n_short_pat + 1}"

        # ==============================================================
        #  BOTTOM PANEL
        # ==============================================================
        bt_occ, bt_comp = make_component("Bottom")

        bt_xy = bt_comp.xYConstructionPlane
        bt_plane = offset_plane(bt_comp, bt_xy,
            "lo_z + rail_height", "Bottom_Plane")
        sk_bt, pr_bt = sketch_rect(
            bt_comp, bt_plane,
            "leg_size", "leg_size",
            "long_shoulder", "short_shoulder",
            "Bottom_Section")
        ext_bt = extrude_new(bt_comp, pr_bt, "bottom_thickness", "BottomPanel")
        ext_bt.bodies.item(0).name = "BottomPanel"

        # ==============================================================
        #  FIT VIEW
        # ==============================================================
        cam = app.activeViewport.camera
        cam.isFitView = True
        app.activeViewport.camera = cam

        n_long = int(pval("n_long_slats"))
        n_short = int(pval("n_short_slats"))
        n_long_total = n_long + (1 if gap_long_cm > 0.01 else 0)
        n_short_total = n_short + (1 if gap_short_cm > 0.01 else 0)
        total_slats = 2 * n_long_total + 2 * n_short_total
        ui.messageBox(
            f"Planter V2 created (parametric)!\n\n"
            f"Components: Legs, LongRails, ShortRails, Slats, Bottom\n\n"
            f"Bodies: 4 legs, 8 rails, {total_slats} slats, 1 bottom\n"
            f"Long sides: {n_long_total} slats each | "
            f"Short sides: {n_short_total} slats each\n\n"
            f"Features: Sketch→Extrude, Mirror (legs, rails, slats), "
            f"Rectangular Pattern (slats)\n\n"
            f"Tip: Modify → Change Parameters to adjust dimensions.\n"
            f"Timeline features will recompute automatically."
        )

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
