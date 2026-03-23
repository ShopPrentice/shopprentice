"""
Bed Rail Fastener (Mortise Bedlock) — Hardware Model + STEP Export
==================================================================
Three sizes: 80mm (1 hook), 100mm (2 hooks), 120mm (2 hooks).
Exports each size as a STEP file with 2 bodies: male (hook plate) + female (strike plate).
Screw heads have Phillips cross on the OUTSIDE face (Z=plate_t = top).
"""
import adsk.core, adsk.fusion, math, os

CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def stadium_profile(sk, x0, y0, length, width):
    P3 = adsk.core.Point3D
    r = width / 2
    lines = sk.sketchCurves.sketchLines
    arcs = sk.sketchCurves.sketchArcs
    l_top = lines.addByTwoPoints(
        P3.create(x0 + r, y0 + width/2, 0),
        P3.create(x0 + length - r, y0 + width/2, 0))
    l_bot = lines.addByTwoPoints(
        P3.create(x0 + length - r, y0 - width/2, 0),
        P3.create(x0 + r, y0 - width/2, 0))
    arcs.addByThreePoints(
        l_top.endSketchPoint, P3.create(x0 + length, y0, 0), l_bot.startSketchPoint)
    arcs.addByThreePoints(
        l_bot.endSketchPoint, P3.create(x0, y0, 0), l_top.startSketchPoint)
    return sk.profiles.item(0)


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    VI = adsk.core.ValueInput.createByString
    P3 = adsk.core.Point3D

    # Dimensions (cm)
    plate_w = 1.5
    plate_t = 0.25
    hook_arm_h = 0.9
    hook_catch_l = 0.45
    hook_arm_t = 0.15
    hook_w = 0.6
    slot_len = 1.4
    slot_w = 0.5
    screw_d = 0.45
    # Phillips cross
    phillips_w = 0.08
    phillips_l_frac = 0.7  # fraction of screw diameter
    phillips_d = plate_t * 0.5

    sizes = {
        "80mm":  {"length": 8.0,  "n_hooks": 1},
        "100mm": {"length": 10.0, "n_hooks": 2},
        "120mm": {"length": 12.0, "n_hooks": 2},
    }

    gap_y = 5.0
    gap_x = 16.0
    export_dir = os.path.expanduser("~/.shopprentice/hardware/bed_rail_fastener")
    os.makedirs(export_dir, exist_ok=True)

    for idx, (size_name, dims) in enumerate(sizes.items()):
        length = dims["length"]
        n_hooks = dims["n_hooks"]
        x0 = idx * gap_x
        y_hook = 0
        y_strike = gap_y
        phillips_l = screw_d * phillips_l_frac

        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = f"Bedlock_{size_name}"
        comp = occ.component

        # Offset plane at top face for Phillips sketches
        top_pl_inp = comp.constructionPlanes.createInput()
        top_pl_inp.setByOffset(comp.xYConstructionPlane, VI(f"{plate_t} cm"))
        top_plane = comp.constructionPlanes.add(top_pl_inp)
        top_plane.name = "TopFace_Pl"
        top_plane.isLightBulbOn = False

        # ==== HOOK PLATE ====
        sk_h = comp.sketches.add(comp.xYConstructionPlane)
        sk_h.name = f"HP_Sk"
        hp_prof = stadium_profile(sk_h, x0, y_hook, length, plate_w)
        hp_ext = comp.features.extrudeFeatures.createInput(hp_prof, NEW)
        hp_ext.setDistanceExtent(False, VI(f"{plate_t} cm"))
        hp_feat = comp.features.extrudeFeatures.add(hp_ext)
        hp_feat.name = "HookPlate"
        hook_plate = hp_feat.bodies.item(0)
        hook_plate.name = f"HookPlate_{size_name}"

        # L-shaped hooks
        if n_hooks == 1:
            hook_xs = [length * 0.4]
        else:
            hook_xs = [length * 0.28, length * 0.58]

        for hi, hx in enumerate(hook_xs):
            hook_y_pl = comp.constructionPlanes.createInput()
            hook_y_pl.setByOffset(comp.xZConstructionPlane, VI(f"{y_hook} cm"))
            hook_plane = comp.constructionPlanes.add(hook_y_pl)
            hook_plane.name = f"HookPl_{hi}"

            sk_hook = comp.sketches.add(hook_plane)
            sk_hook.name = f"Hook_{hi}_Sk"
            m2s = sk_hook.modelToSketchSpace

            ax0 = x0 + hx - hook_w/2
            ax1 = x0 + hx + hook_w/2
            z0 = plate_t
            z1 = plate_t + hook_arm_h
            cx1 = ax1 + hook_catch_l
            cz0 = z1 - hook_w * 0.5

            pts_model = [
                (ax0, z0), (ax0, z1), (ax1, z1),
                (cx1, z1), (cx1, cz0), (ax1, cz0), (ax1, z0),
            ]
            sp = [m2s(P3.create(px, y_hook, pz)) for px, pz in pts_model]
            lines = sk_hook.sketchCurves.sketchLines
            prev = lines.addByTwoPoints(sp[0], sp[1])
            for j in range(2, len(sp)):
                prev = lines.addByTwoPoints(prev.endSketchPoint, sp[j])
            lines.addByTwoPoints(prev.endSketchPoint,
                sk_hook.sketchCurves.sketchLines.item(0).startSketchPoint)

            hook_prof = sk_hook.profiles.item(0)
            hook_ext_inp = comp.features.extrudeFeatures.createInput(hook_prof, NEW)
            hook_ext_inp.setSymmetricExtent(VI(f"{hook_arm_t / 2} cm"), False)
            hook_ext = comp.features.extrudeFeatures.add(hook_ext_inp)
            hook_ext.name = f"Hook_{hi}"
            hook_body = hook_ext.bodies.item(0)

            coll = adsk.core.ObjectCollection.create()
            coll.add(hook_body)
            ci = comp.features.combineFeatures.createInput(hook_plate, coll)
            ci.operation = JOIN; ci.isKeepToolBodies = False
            comp.features.combineFeatures.add(ci).name = f"HookJoin_{hi}"
            sk_hook.isVisible = False
            hook_plane.isLightBulbOn = False

        # Screw holes + fake screw heads with Phillips on TOP face
        if n_hooks == 1:
            screw_xs = [length * 0.12, length * 0.78]
        else:
            screw_xs = [length * 0.1, length * 0.45, length * 0.9]

        hp_screw_bodies = []
        for si, sx in enumerate(screw_xs):
            # Hole through plate
            sk_sc = comp.sketches.add(comp.xYConstructionPlane)
            sk_sc.name = f"ScrHP_{si}_Sk"
            sk_sc.sketchCurves.sketchCircles.addByCenterRadius(
                P3.create(x0 + sx, y_hook, 0), screw_d/2)
            sc_ext = comp.features.extrudeFeatures.createInput(sk_sc.profiles.item(0), CUT)
            sc_ext.setDistanceExtent(False, VI(f"{plate_t * 1.5} cm"))
            sc_ext.participantBodies = [hook_plate]
            comp.features.extrudeFeatures.add(sc_ext).name = f"ScrHP_{si}"
            sk_sc.isVisible = False

            # Screw body (fills hole)
            sk_fh = comp.sketches.add(comp.xYConstructionPlane)
            sk_fh.name = f"FakeScr_HP_{si}_Sk"
            sk_fh.sketchCurves.sketchCircles.addByCenterRadius(
                P3.create(x0 + sx, y_hook, 0), screw_d/2)
            fh_ext = comp.features.extrudeFeatures.createInput(sk_fh.profiles.item(0), NEW)
            fh_ext.setDistanceExtent(False, VI(f"{plate_t} cm"))
            fh_feat = comp.features.extrudeFeatures.add(fh_ext)
            fh_feat.name = f"FakeScr_HP_{si}"
            screw_body = fh_feat.bodies.item(0)
            screw_body.name = f"Screw_HP_{si}"
            sk_fh.isVisible = False

            # Phillips cross on TOP face (outside) — sketch at Z=0, offset start
            for slot_dir in ["h", "v"]:
                sk_ph = comp.sketches.add(comp.xYConstructionPlane)
                sk_ph.name = f"Ph_HP_{si}_{slot_dir}_Sk"
                cx_s = x0 + sx; cy_s = y_hook
                if slot_dir == "h":
                    sk_ph.sketchCurves.sketchLines.addTwoPointRectangle(
                        P3.create(cx_s - phillips_l/2, cy_s - phillips_w/2, 0),
                        P3.create(cx_s + phillips_l/2, cy_s + phillips_w/2, 0))
                else:
                    sk_ph.sketchCurves.sketchLines.addTwoPointRectangle(
                        P3.create(cx_s - phillips_w/2, cy_s - phillips_l/2, 0),
                        P3.create(cx_s + phillips_w/2, cy_s + phillips_l/2, 0))
                ph_prof = sk_ph.profiles.item(0)
                ph_ext = comp.features.extrudeFeatures.createInput(ph_prof, CUT)
                ph_start = adsk.fusion.OffsetStartDefinition.create(
                    VI(f"{plate_t - phillips_d} cm"))
                ph_ext.startExtent = ph_start
                ph_ext.setDistanceExtent(False, VI(f"{phillips_d} cm"))
                ph_ext.participantBodies = [screw_body]
                comp.features.extrudeFeatures.add(ph_ext).name = f"Ph_HP_{si}_{slot_dir}"
                sk_ph.isVisible = False

            hp_screw_bodies.append(screw_body)

        # Screws stay as separate bodies (visible circle boundary on plate surface)

        # ==== STRIKE PLATE ====
        sk_s = comp.sketches.add(comp.xYConstructionPlane)
        sk_s.name = f"SP_Sk"
        sp_prof = stadium_profile(sk_s, x0, y_strike, length, plate_w)
        sp_ext = comp.features.extrudeFeatures.createInput(sp_prof, NEW)
        sp_ext.setDistanceExtent(False, VI(f"{plate_t} cm"))
        sp_feat = comp.features.extrudeFeatures.add(sp_ext)
        sp_feat.name = "StrikePlate"
        strike_plate = sp_feat.bodies.item(0)
        strike_plate.name = f"StrikePlate_{size_name}"

        # Slots
        for si, sx in enumerate(hook_xs):
            sk_sl = comp.sketches.add(comp.xYConstructionPlane)
            sk_sl.name = f"Slot_{si}_Sk"
            rect = sk_sl.sketchCurves.sketchLines.addTwoPointRectangle(
                P3.create(x0 + sx - slot_len/2, y_strike - slot_w/2, 0),
                P3.create(x0 + sx + slot_len/2, y_strike + slot_w/2, 0))
            gc = sk_sl.geometricConstraints
            gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])
            gc.addVertical(rect[1]); gc.addVertical(rect[3])
            sl_ext = comp.features.extrudeFeatures.createInput(sk_sl.profiles.item(0), CUT)
            sl_ext.setDistanceExtent(False, VI(f"{plate_t * 2} cm"))
            sl_ext.participantBodies = [strike_plate]
            comp.features.extrudeFeatures.add(sl_ext).name = f"Slot_{si}"
            sk_sl.isVisible = False

        # Strike plate screws
        if n_hooks == 1:
            strike_scr = [length * 0.12, length * 0.85]
        else:
            strike_scr = [length * 0.1, length * 0.45, length * 0.9]

        sp_screw_bodies = []
        for si, sx in enumerate(strike_scr):
            sk_ss = comp.sketches.add(comp.xYConstructionPlane)
            sk_ss.name = f"ScrSP_{si}_Sk"
            sk_ss.sketchCurves.sketchCircles.addByCenterRadius(
                P3.create(x0 + sx, y_strike, 0), screw_d/2)
            ss_ext = comp.features.extrudeFeatures.createInput(sk_ss.profiles.item(0), CUT)
            ss_ext.setDistanceExtent(False, VI(f"{plate_t * 1.5} cm"))
            ss_ext.participantBodies = [strike_plate]
            comp.features.extrudeFeatures.add(ss_ext).name = f"ScrSP_{si}"
            sk_ss.isVisible = False

            sk_fs = comp.sketches.add(comp.xYConstructionPlane)
            sk_fs.name = f"FakeScr_SP_{si}_Sk"
            sk_fs.sketchCurves.sketchCircles.addByCenterRadius(
                P3.create(x0 + sx, y_strike, 0), screw_d/2)
            fs_ext = comp.features.extrudeFeatures.createInput(sk_fs.profiles.item(0), NEW)
            fs_ext.setDistanceExtent(False, VI(f"{plate_t} cm"))
            fs_feat = comp.features.extrudeFeatures.add(fs_ext)
            fs_feat.name = f"FakeScr_SP_{si}"
            screw_body_sp = fs_feat.bodies.item(0)
            screw_body_sp.name = f"Screw_SP_{si}"
            sk_fs.isVisible = False

            # Phillips on top face — sketch at Z=0, offset start to cut top portion
            for slot_dir in ["h", "v"]:
                sk_ps = comp.sketches.add(comp.xYConstructionPlane)
                sk_ps.name = f"Ph_SP_{si}_{slot_dir}_Sk"
                cx_s = x0 + sx; cy_s = y_strike
                if slot_dir == "h":
                    sk_ps.sketchCurves.sketchLines.addTwoPointRectangle(
                        P3.create(cx_s - phillips_l/2, cy_s - phillips_w/2, 0),
                        P3.create(cx_s + phillips_l/2, cy_s + phillips_w/2, 0))
                else:
                    sk_ps.sketchCurves.sketchLines.addTwoPointRectangle(
                        P3.create(cx_s - phillips_w/2, cy_s - phillips_l/2, 0),
                        P3.create(cx_s + phillips_w/2, cy_s + phillips_l/2, 0))
                ps_ext = comp.features.extrudeFeatures.createInput(sk_ps.profiles.item(0), CUT)
                ps_start = adsk.fusion.OffsetStartDefinition.create(
                    VI(f"{plate_t - phillips_d} cm"))
                ps_ext.startExtent = ps_start
                ps_ext.setDistanceExtent(False, VI(f"{phillips_d} cm"))
                ps_ext.participantBodies = [screw_body_sp]
                comp.features.extrudeFeatures.add(ps_ext).name = f"Ph_SP_{si}_{slot_dir}"
                sk_ps.isVisible = False

            sp_screw_bodies.append(screw_body_sp)

        # Screws stay as separate bodies (visible circle boundary on plate surface)

        sk_h.isVisible = False
        sk_s.isVisible = False

        # Export SEPARATE STEP files per plate (hook and strike independently)
        export_mgr = design.exportManager

        # Move hook plate + its screws into a sub-component for export
        hook_sub = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        hook_sub.component.name = f"HookPlate_{size_name}"
        hook_coll = adsk.core.ObjectCollection.create()
        hook_coll.add(hook_plate)
        for sb in hp_screw_bodies:
            hook_coll.add(sb)
        hook_sub.component.features.copyPasteBodies.add(hook_coll)

        hook_path = os.path.join(export_dir, f"hook_plate_{size_name}.step")
        step_opts = export_mgr.createSTEPExportOptions(hook_path, hook_sub.component)
        export_mgr.execute(step_opts)

        # Move strike plate + its screws into a sub-component for export
        strike_sub = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        strike_sub.component.name = f"StrikePlate_{size_name}"
        strike_coll = adsk.core.ObjectCollection.create()
        strike_coll.add(strike_plate)
        for sb in sp_screw_bodies:
            strike_coll.add(sb)
        strike_sub.component.features.copyPasteBodies.add(strike_coll)

        strike_path = os.path.join(export_dir, f"strike_plate_{size_name}.step")
        step_opts = export_mgr.createSTEPExportOptions(strike_path, strike_sub.component)
        export_mgr.execute(step_opts)

        # Also export combined (backward compat)
        combined_path = os.path.join(export_dir, f"bedlock_{size_name}.step")
        step_opts = export_mgr.createSTEPExportOptions(combined_path, comp)
        export_mgr.execute(step_opts)

        print(f">>> {size_name}: exported hook_plate + strike_plate + combined STEP")

    # ================================================================
    # TEST FIXTURES — one for each size (80mm, 100mm, 120mm)
    # ================================================================
    from woodworking.templates import bed_rail_fastener as brf

    fix_ev = lambda e: design.unitsManager.evaluateExpression(e, "cm")
    post_w_cm = fix_ev("3 in")
    fixture_spacing = fix_ev("30 in")  # space between fixtures

    for fi, fix_size in enumerate(["80mm", "100mm", "120mm"]):
        y_offset = fi * fixture_spacing

        fix_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        fix_occ.component.name = f"Fixture_{fix_size}"
        fix_c = fix_occ.component

        # Post: 3" x 3" x 14" tall
        _, pr = af.sketch_rect_model(fix_c, fix_c.xYConstructionPlane,
            ("0 in", f"{y_offset} cm", "0 in"),
            {"x": "3 in", "y": "3 in"}, "Post_Sk", fix_ev)
        post_ext = af.ext_new(fix_c, pr, "14 in", "Post")
        post_body = post_ext.bodies.item(0)
        post_body.name = f"Post_{fix_size}"

        # Rail: 1.5" x 10" x 20" long, butted against post
        _, pr = af.sketch_rect_model(fix_c, fix_c.xYConstructionPlane,
            ("3 in", f"{y_offset + fix_ev('0.75 in')} cm", "2.5 in"),
            {"x": "20 in", "y": "1.5 in"}, "Rail_Sk", fix_ev)
        rail_ext = af.ext_new(fix_c, pr, "10 in", "Rail")
        rail_body = rail_ext.bodies.item(0)
        rail_body.name = f"Rail_{fix_size}"

        # Hide sketches
        for sk in fix_c.sketches:
            sk.isVisible = False

        # Install bedlock
        post_p = post_body.createForAssemblyContext(fix_occ)
        rail_p = rail_body.createForAssemblyContext(fix_occ)
        rail_center_z = fix_ev("2.5 in") + fix_ev("10 in") / 2

        brf.install(root, post_p, rail_p,
                    interface_axis="x",
                    interface_coord=post_w_cm,
                    center_z=rail_center_z,
                    size=fix_size, name=f"Fix_{fix_size}",
                    ev=fix_ev)

        print(f">>> Fixture {fix_size}: post + rail with bedlock installed")

    # Hide sketches
    for sk in fix_c.sketches:
        sk.isVisible = False

    print(">>> Test fixture: post + rail with 100mm bedlock installed")

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
    print(">>> All 3 sizes generated, exported, and test fixture built")
