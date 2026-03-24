"""All 5 hinge fixtures with screws installed via install_screws=True.

S1 lid_surface (1603A2), S2 lid_flush (1603A3), S3 door_surface (1603A7),
S4 door_flush (1603A3), S5 door_flush+gap (1603A3).

STEP files are imported once per part_id and copied for additional uses.
Screws are installed as part of install_butt_hinge (not a separate call).
"""
import adsk.core
import adsk.fusion


def run(context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import sp, hardware

    # Clear STEP cache to start fresh
    hardware.clear_step_cache()

    ctx = sp.DesignContext(design)
    results = {}

    # ── S1: lid_surface — 1603A2 (small) ─────────────────────────────
    print("S1: lid_surface — 1603A2")
    params.add("s1_l", VI("8 in"), "in", ""); params.add("s1_w", VI("5 in"), "in", "")
    params.add("s1_h", VI("4 in"), "in", ""); params.add("s1_bt", VI("0.375 in"), "in", "")

    occ1 = sp.make_comp(root, "S1"); comp1 = occ1.component
    back_pl = sp.off_plane(comp1, comp1.xZConstructionPlane, "s1_w - s1_bt", "S1_BackPl")
    sk, pr = sp.sketch_rect_model(comp1, back_pl,
        ("0 in", "s1_w - s1_bt", "0 in"), {"x": "s1_l", "z": "s1_h"}, "S1_Back_Sk", ctx.ev)
    s1_back = sp.ext_new(comp1, pr, "s1_bt", "S1_Back").bodies.item(0); s1_back.name = "S1_Back"
    lid_pl = sp.off_plane(comp1, comp1.xYConstructionPlane, "s1_h", "S1_LidPl")
    sk, pr = sp.sketch_rect_model(comp1, lid_pl,
        ("0 in", "0 in", "s1_h"), {"x": "s1_l", "y": "s1_w"}, "S1_Lid_Sk", ctx.ev)
    s1_lid = sp.ext_new(comp1, pr, "s1_bt", "S1_Lid").bodies.item(0); s1_lid.name = "S1_Lid"

    bv, lv = s1_back.volume, s1_lid.volume
    for i, (frac, sfx) in enumerate([("s1_l / 4", "L"), ("s1_l * 3 / 4", "R")]):
        r = hardware.install_butt_hinge(part_id="1603a2", comp=comp1,
            back_body=s1_back, lid_body=s1_lid,
            pin_position=(ctx.ev(frac), ctx.ev("s1_w"), ctx.ev("s1_h")),
            style="lid_surface",
            ev=ctx.ev, name=f"S1_H_{sfx}")
    ok = s1_back.volume < bv and s1_lid.volume < lv
    print(f"  Back cut: {s1_back.volume < bv}, Lid cut: {s1_lid.volume < lv} -> {'PASS' if ok else 'FAIL'}")
    results["S1"] = ok

    # ── S2: lid_flush — 1603A3 (medium) ──────────────────────────────
    print("S2: lid_flush — 1603A3")
    params.add("s2_l", VI("10 in"), "in", ""); params.add("s2_w", VI("6 in"), "in", "")
    params.add("s2_h", VI("5 in"), "in", ""); params.add("s2_bt", VI("0.5 in"), "in", "")
    params.add("s2_off_x", VI("s1_l + 4 in"), "in", "")

    occ2 = sp.make_comp(root, "S2"); comp2 = occ2.component
    bp2 = sp.off_plane(comp2, comp2.xZConstructionPlane, "s2_w - s2_bt", "S2_BackPl")
    sk, pr = sp.sketch_rect_model(comp2, bp2,
        ("s2_off_x", "s2_w - s2_bt", "0 in"), {"x": "s2_l", "z": "s2_h"}, "S2_Back_Sk", ctx.ev)
    s2_back = sp.ext_new(comp2, pr, "s2_bt", "S2_Back").bodies.item(0); s2_back.name = "S2_Back"
    lp2 = sp.off_plane(comp2, comp2.xYConstructionPlane, "s2_h", "S2_LidPl")
    sk, pr = sp.sketch_rect_model(comp2, lp2,
        ("s2_off_x", "0 in", "s2_h"), {"x": "s2_l", "y": "s2_w"}, "S2_Lid_Sk", ctx.ev)
    s2_lid = sp.ext_new(comp2, pr, "s2_bt", "S2_Lid").bodies.item(0); s2_lid.name = "S2_Lid"

    bv, lv = s2_back.volume, s2_lid.volume
    for i, (frac, sfx) in enumerate([("s2_off_x + s2_l / 4", "L"), ("s2_off_x + s2_l * 3 / 4", "R")]):
        r = hardware.install_butt_hinge(part_id="1603a3", comp=comp2,
            back_body=s2_back, lid_body=s2_lid,
            pin_position=(ctx.ev(frac), ctx.ev("s2_w"), ctx.ev("s2_h")),
            style="lid_flush",
            ev=ctx.ev, name=f"S2_H_{sfx}")
    ok = s2_back.volume < bv and s2_lid.volume < lv
    print(f"  Back cut: {s2_back.volume < bv}, Lid cut: {s2_lid.volume < lv} -> {'PASS' if ok else 'FAIL'}")
    results["S2"] = ok

    # ── S3: door_surface — 1603A7 (large) ────────────────────────────
    print("S3: door_surface — 1603A7")
    params.add("s3_h", VI("14 in"), "in", ""); params.add("s3_bt", VI("0.75 in"), "in", "")
    params.add("s3_door_w", VI("10 in"), "in", ""); params.add("s3_depth", VI("14 in"), "in", "")
    params.add("s3_off_y", VI("s2_w + 4 in"), "in", "")

    occ3 = sp.make_comp(root, "S3"); comp3 = occ3.component
    sk, pr = sp.sketch_rect_model(comp3, comp3.xYConstructionPlane,
        ("0 in", "s3_off_y", "0 in"), {"x": "s3_bt", "y": "s3_depth"}, "S3_Side_Sk", ctx.ev)
    s3_side = sp.ext_new(comp3, pr, "s3_h", "S3_Side").bodies.item(0); s3_side.name = "S3_Side"
    sk, pr = sp.sketch_rect_model(comp3, comp3.xYConstructionPlane,
        ("0 in", "s3_off_y - s3_bt", "0 in"), {"x": "s3_door_w", "y": "s3_bt"}, "S3_Door_Sk", ctx.ev)
    s3_door = sp.ext_new(comp3, pr, "s3_h", "S3_Door").bodies.item(0); s3_door.name = "S3_Door"

    sv, dv = s3_side.volume, s3_door.volume
    for frac, sfx in [("s3_h / 4", "Lo"), ("s3_h * 3 / 4", "Hi")]:
        r = hardware.install_butt_hinge(part_id="1603a7", comp=comp3,
            door_body=s3_door, case_body=s3_side,
            pin_position=("0 in", "s3_off_y", frac),
            style="door_surface",
            ev=ctx.ev, name=f"S3_H_{sfx}")
    ok = s3_side.volume < sv and s3_door.volume < dv
    print(f"  Side cut: {s3_side.volume < sv}, Door cut: {s3_door.volume < dv} -> {'PASS' if ok else 'FAIL'}")
    results["S3"] = ok

    # ── S4: door_flush — 1603A3, no gap ──────────────────────────────
    print("S4: door_flush — 1603A3, no gap")
    params.add("s4_h", VI("12 in"), "in", ""); params.add("s4_bt", VI("0.5 in"), "in", "")
    params.add("s4_door_w", VI("8 in"), "in", ""); params.add("s4_depth", VI("12 in"), "in", "")
    params.add("s4_off_x", VI("s3_bt + s3_door_w + 4 in"), "in", "")

    occ4 = sp.make_comp(root, "S4"); comp4 = occ4.component
    sk, pr = sp.sketch_rect_model(comp4, comp4.xYConstructionPlane,
        ("s4_off_x", "s3_off_y", "0 in"), {"x": "s4_bt", "y": "s4_depth"}, "S4_Side_Sk", ctx.ev)
    s4_side = sp.ext_new(comp4, pr, "s4_h", "S4_Side").bodies.item(0); s4_side.name = "S4_Side"
    sk, pr = sp.sketch_rect_model(comp4, comp4.xYConstructionPlane,
        ("s4_off_x + s4_bt", "s3_off_y", "0 in"), {"x": "s4_door_w", "y": "s4_bt"}, "S4_Door_Sk", ctx.ev)
    s4_door = sp.ext_new(comp4, pr, "s4_h", "S4_Door").bodies.item(0); s4_door.name = "S4_Door"

    sv, dv = s4_side.volume, s4_door.volume
    for frac, sfx in [("s4_h / 4", "Lo"), ("s4_h * 3 / 4", "Hi")]:
        r = hardware.install_butt_hinge(part_id="1603a3", comp=comp4,
            door_body=s4_door, case_body=s4_side,
            pin_position=("s4_off_x + s4_bt", "s3_off_y", frac),
            style="door_flush",
            ev=ctx.ev, name=f"S4_H_{sfx}")
    ok = s4_side.volume < sv and s4_door.volume < dv
    print(f"  Side cut: {s4_side.volume < sv}, Door cut: {s4_door.volume < dv} -> {'PASS' if ok else 'FAIL'}")
    results["S4"] = ok

    # ── S5: door_flush — 1603A3, 1/16" gap ───────────────────────────
    print("S5: door_flush — 1603A3, 1/16\" gap")
    params.add("s5_h", VI("12 in"), "in", ""); params.add("s5_bt", VI("0.5 in"), "in", "")
    params.add("s5_door_w", VI("8 in"), "in", ""); params.add("s5_depth", VI("12 in"), "in", "")
    params.add("s5_gap", VI("0.0625 in"), "in", "")
    params.add("s5_off_x", VI("s4_off_x + s4_bt + s4_door_w + 4 in"), "in", "")

    occ5 = sp.make_comp(root, "S5"); comp5 = occ5.component
    sk, pr = sp.sketch_rect_model(comp5, comp5.xYConstructionPlane,
        ("s5_off_x", "s3_off_y", "0 in"), {"x": "s5_bt", "y": "s5_depth"}, "S5_Side_Sk", ctx.ev)
    s5_side = sp.ext_new(comp5, pr, "s5_h", "S5_Side").bodies.item(0); s5_side.name = "S5_Side"
    sk, pr = sp.sketch_rect_model(comp5, comp5.xYConstructionPlane,
        ("s5_off_x + s5_bt + s5_gap", "s3_off_y", "0 in"), {"x": "s5_door_w", "y": "s5_bt"}, "S5_Door_Sk", ctx.ev)
    s5_door = sp.ext_new(comp5, pr, "s5_h", "S5_Door").bodies.item(0); s5_door.name = "S5_Door"

    sv, dv = s5_side.volume, s5_door.volume
    gap_cm = ctx.ev("s5_gap")
    for frac, sfx in [("s5_h / 4", "Lo"), ("s5_h * 3 / 4", "Hi")]:
        r = hardware.install_butt_hinge(part_id="1603a3", comp=comp5,
            door_body=s5_door, case_body=s5_side,
            pin_position=("s5_off_x + s5_bt", "s3_off_y", frac),
            style="door_flush", gap=gap_cm,
            ev=ctx.ev, name=f"S5_H_{sfx}")
    ok = s5_side.volume < sv and s5_door.volume < dv
    print(f"  Gap={gap_cm/2.54:.4f}in  Side cut: {s5_side.volume < sv}, Door cut: {s5_door.volume < dv} -> {'PASS' if ok else 'FAIL'}")
    results["S5"] = ok

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    for occ_item in root.occurrences:
        c = occ_item.component
        print(f"  {c.name}: {c.bRepBodies.count} bodies")
    status = "PASS" if all(results.values()) else "FAIL"
    detail = " ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in results.items())
    print(f"\n{status}: {detail}")

    # Clean up hidden STEP template occurrences
    hardware.cleanup_step_templates()

    for occ_item in root.occurrences:
        c = occ_item.component
        for s in c.sketches:
            s.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
