"""Test fixtures for butt hinge installation styles with screws.

6 fixtures testing different hinge sizes, styles, screws, and gaps:
  S1 lid_surface  — 1603A2 (small), 2 hinges + screws
  S2 lid_flush    — 1603A3 (medium), 2 hinges + screws
  S3 door_surface — 1603A7 (large), 2 hinges + screws
  S4 door_flush   — 1603A3 (medium), 2 hinges + screws
  S5 door_flush   — 1603A3, 2 hinges + screws, 1/16" gap between boards

Each install_butt_hinge() call handles everything: import, position,
fold, rebate CUTs. install_hinge_screws() places matching screws.
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

    ctx = sp.DesignContext(design)
    all_pass = True
    results = {}

    # ================================================================
    # S1: lid_surface — 1603A2 (small), surface mount
    # ================================================================
    print("=" * 50)
    print("S1: lid_surface — 1603A2 small, 2 hinges + screws")
    print("=" * 50)

    PART1 = "1603a2"
    params.add("s1_l", VI("8 in"), "in", "S1 box length")
    params.add("s1_w", VI("5 in"), "in", "S1 box width")
    params.add("s1_h", VI("4 in"), "in", "S1 box height")
    params.add("s1_bt", VI("0.375 in"), "in", "S1 board thick")

    occ1 = sp.make_comp(root, "S1")
    comp1 = occ1.component

    back_pl = sp.off_plane(comp1, comp1.xZConstructionPlane,
                            "s1_w - s1_bt", "S1_BackPl")
    sk, pr = sp.sketch_rect_model(comp1, back_pl,
        ("0 in", "s1_w - s1_bt", "0 in"),
        {"x": "s1_l", "z": "s1_h"}, "S1_Back_Sk", ctx.ev)
    s1_back = sp.ext_new(comp1, pr, "s1_bt", "S1_Back").bodies.item(0)
    s1_back.name = "S1_Back"

    lid_pl = sp.off_plane(comp1, comp1.xYConstructionPlane,
                           "s1_h", "S1_LidPl")
    sk, pr = sp.sketch_rect_model(comp1, lid_pl,
        ("0 in", "0 in", "s1_h"),
        {"x": "s1_l", "y": "s1_w"}, "S1_Lid_Sk", ctx.ev)
    s1_lid = sp.ext_new(comp1, pr, "s1_bt", "S1_Lid").bodies.item(0)
    s1_lid.name = "S1_Lid"

    s1_back_vol = s1_back.volume
    s1_lid_vol = s1_lid.volume

    s1_hinges = []
    s1_screws = []
    for frac, sfx in [("s1_l / 4", "L"), ("s1_l * 3 / 4", "R")]:
        result = hardware.install_butt_hinge(
            part_id=PART1, comp=comp1,
            back_body=s1_back, lid_body=s1_lid,
            pin_position=(ctx.ev(frac), ctx.ev("s1_w"), ctx.ev("s1_h")),
            pin_axis="x", style="lid_surface",
            ev=ctx.ev, name=f"S1_Hinge_{sfx}")
        s1_hinges.append(result)
        screws = hardware.install_hinge_screws(result, comp1,
                                                ev=ctx.ev, name=f"S1_Screw_{sfx}")
        s1_screws.extend(screws)

    n1 = comp1.bRepBodies.count
    s1_ok = (n1 == 2
             and len(s1_hinges) == 2
             and all(h["occurrence"].component.bRepBodies.count == 3
                     for h in s1_hinges)
             and s1_back.volume < s1_back_vol
             and s1_lid.volume < s1_lid_vol)
    print(f"  Comp bodies: {n1}, Hinges: {len(s1_hinges)}, Screws: {len(s1_screws)}")
    print(f"  Back rebate: {s1_back.volume < s1_back_vol}, "
          f"Lid rebate: {s1_lid.volume < s1_lid_vol}")
    print(f"  S1: {'PASS' if s1_ok else 'FAIL'}\n")
    if not s1_ok:
        all_pass = False
    results["S1"] = s1_ok

    # ================================================================
    # S2: lid_flush — 1603A3 (medium), closed between boards
    # ================================================================
    print("=" * 50)
    print("S2: lid_flush — 1603A3 medium, 2 hinges + screws")
    print("=" * 50)

    PART2 = "1603a3"
    params.add("s2_l", VI("10 in"), "in", "S2 box length")
    params.add("s2_w", VI("6 in"), "in", "S2 box width")
    params.add("s2_h", VI("5 in"), "in", "S2 box height")
    params.add("s2_bt", VI("0.5 in"), "in", "S2 board thick")
    params.add("s2_off_x", VI("s1_l + 4 in"), "in", "S2 X offset")

    occ2 = sp.make_comp(root, "S2")
    comp2 = occ2.component

    back_pl2 = sp.off_plane(comp2, comp2.xZConstructionPlane,
                             "s2_w - s2_bt", "S2_BackPl")
    sk, pr = sp.sketch_rect_model(comp2, back_pl2,
        ("s2_off_x", "s2_w - s2_bt", "0 in"),
        {"x": "s2_l", "z": "s2_h"}, "S2_Back_Sk", ctx.ev)
    s2_back = sp.ext_new(comp2, pr, "s2_bt", "S2_Back").bodies.item(0)
    s2_back.name = "S2_Back"

    lid_pl2 = sp.off_plane(comp2, comp2.xYConstructionPlane,
                            "s2_h", "S2_LidPl")
    sk, pr = sp.sketch_rect_model(comp2, lid_pl2,
        ("s2_off_x", "0 in", "s2_h"),
        {"x": "s2_l", "y": "s2_w"}, "S2_Lid_Sk", ctx.ev)
    s2_lid = sp.ext_new(comp2, pr, "s2_bt", "S2_Lid").bodies.item(0)
    s2_lid.name = "S2_Lid"

    s2_back_vol = s2_back.volume
    s2_lid_vol = s2_lid.volume

    s2_hinges = []
    s2_screws = []
    for frac, sfx in [("s2_off_x + s2_l / 4", "L"),
                      ("s2_off_x + s2_l * 3 / 4", "R")]:
        result = hardware.install_butt_hinge(
            part_id=PART2, comp=comp2,
            back_body=s2_back, lid_body=s2_lid,
            pin_position=(ctx.ev(frac), ctx.ev("s2_w"), ctx.ev("s2_h")),
            pin_axis="x", style="lid_flush",
            ev=ctx.ev, name=f"S2_Hinge_{sfx}")
        s2_hinges.append(result)
        screws = hardware.install_hinge_screws(result, comp2,
                                                ev=ctx.ev, name=f"S2_Screw_{sfx}")
        s2_screws.extend(screws)

    n2 = comp2.bRepBodies.count
    s2_ok = (n2 == 2
             and len(s2_hinges) == 2
             and all(h["occurrence"].component.bRepBodies.count == 3
                     for h in s2_hinges)
             and s2_back.volume < s2_back_vol
             and s2_lid.volume < s2_lid_vol)
    print(f"  Comp bodies: {n2}, Hinges: {len(s2_hinges)}, Screws: {len(s2_screws)}")
    print(f"  Back rebate: {s2_back.volume < s2_back_vol}, "
          f"Lid rebate: {s2_lid.volume < s2_lid_vol}")
    print(f"  S2: {'PASS' if s2_ok else 'FAIL'}\n")
    if not s2_ok:
        all_pass = False
    results["S2"] = s2_ok

    # ================================================================
    # S3: door_surface — 1603A7 (large), overlay door
    # ================================================================
    print("=" * 50)
    print("S3: door_surface — 1603A7 large, 2 hinges + screws")
    print("=" * 50)

    PART3 = "1603a7"
    params.add("s3_h", VI("14 in"), "in", "S3 cabinet height")
    params.add("s3_bt", VI("0.75 in"), "in", "S3 board thick")
    params.add("s3_door_w", VI("10 in"), "in", "S3 door width")
    params.add("s3_depth", VI("14 in"), "in", "S3 cabinet depth")
    params.add("s3_off_y", VI("s2_w + 4 in"), "in", "S3 Y offset")

    occ3 = sp.make_comp(root, "S3")
    comp3 = occ3.component

    sk, pr = sp.sketch_rect_model(comp3, comp3.xYConstructionPlane,
        ("0 in", "s3_off_y", "0 in"),
        {"x": "s3_bt", "y": "s3_depth"}, "S3_Side_Sk", ctx.ev)
    s3_side = sp.ext_new(comp3, pr, "s3_h", "S3_Side").bodies.item(0)
    s3_side.name = "S3_Side"

    sk, pr = sp.sketch_rect_model(comp3, comp3.xYConstructionPlane,
        ("0 in", "s3_off_y - s3_bt", "0 in"),
        {"x": "s3_door_w", "y": "s3_bt"}, "S3_Door_Sk", ctx.ev)
    s3_door = sp.ext_new(comp3, pr, "s3_h", "S3_Door").bodies.item(0)
    s3_door.name = "S3_Door"

    s3_side_vol = s3_side.volume
    s3_door_vol = s3_door.volume

    s3_hinges = []
    s3_screws = []
    for frac, sfx in [("s3_h / 4", "Lo"), ("s3_h * 3 / 4", "Hi")]:
        result = hardware.install_butt_hinge(
            part_id=PART3, comp=comp3,
            door_body=s3_door, case_body=s3_side,
            pin_position=("0 in", "s3_off_y", frac),
            pin_axis="z", style="door_surface",
            ev=ctx.ev, name=f"S3_Hinge_{sfx}")
        s3_hinges.append(result)
        screws = hardware.install_hinge_screws(result, comp3,
                                                ev=ctx.ev, name=f"S3_Screw_{sfx}")
        s3_screws.extend(screws)

    n3 = comp3.bRepBodies.count
    s3_ok = (n3 == 2
             and len(s3_hinges) == 2
             and all(h["occurrence"].component.bRepBodies.count == 3
                     for h in s3_hinges)
             and s3_side.volume < s3_side_vol
             and s3_door.volume < s3_door_vol)
    print(f"  Comp bodies: {n3}, Hinges: {len(s3_hinges)}, Screws: {len(s3_screws)}")
    print(f"  Side rebate: {s3_side.volume < s3_side_vol}, "
          f"Door rebate: {s3_door.volume < s3_door_vol}")
    print(f"  S3: {'PASS' if s3_ok else 'FAIL'}\n")
    if not s3_ok:
        all_pass = False
    results["S3"] = s3_ok

    # ================================================================
    # S4: door_flush — 1603A3, inset door, no gap
    # ================================================================
    print("=" * 50)
    print("S4: door_flush — 1603A3, 2 hinges + screws, no gap")
    print("=" * 50)

    PART4 = "1603a3"
    params.add("s4_h", VI("12 in"), "in", "S4 cabinet height")
    params.add("s4_bt", VI("0.5 in"), "in", "S4 board thick")
    params.add("s4_door_w", VI("8 in"), "in", "S4 door width")
    params.add("s4_depth", VI("12 in"), "in", "S4 cabinet depth")
    params.add("s4_off_x", VI("s3_bt + s3_door_w + 4 in"), "in",
               "S4 X offset")

    occ4 = sp.make_comp(root, "S4")
    comp4 = occ4.component

    sk, pr = sp.sketch_rect_model(comp4, comp4.xYConstructionPlane,
        ("s4_off_x", "s3_off_y", "0 in"),
        {"x": "s4_bt", "y": "s4_depth"}, "S4_Side_Sk", ctx.ev)
    s4_side = sp.ext_new(comp4, pr, "s4_h", "S4_Side").bodies.item(0)
    s4_side.name = "S4_Side"

    sk, pr = sp.sketch_rect_model(comp4, comp4.xYConstructionPlane,
        ("s4_off_x + s4_bt", "s3_off_y", "0 in"),
        {"x": "s4_door_w", "y": "s4_bt"}, "S4_Door_Sk", ctx.ev)
    s4_door = sp.ext_new(comp4, pr, "s4_h", "S4_Door").bodies.item(0)
    s4_door.name = "S4_Door"

    s4_side_vol = s4_side.volume
    s4_door_vol = s4_door.volume

    s4_hinges = []
    s4_screws = []
    for frac, sfx in [("s4_h / 4", "Lo"), ("s4_h * 3 / 4", "Hi")]:
        result = hardware.install_butt_hinge(
            part_id=PART4, comp=comp4,
            door_body=s4_door, case_body=s4_side,
            pin_position=("s4_off_x + s4_bt", "s3_off_y", frac),
            pin_axis="z", style="door_flush",
            ev=ctx.ev, name=f"S4_Hinge_{sfx}")
        s4_hinges.append(result)
        screws = hardware.install_hinge_screws(result, comp4,
                                                ev=ctx.ev, name=f"S4_Screw_{sfx}")
        s4_screws.extend(screws)

    n4 = comp4.bRepBodies.count
    s4_ok = (n4 == 2
             and len(s4_hinges) == 2
             and all(h["occurrence"].component.bRepBodies.count == 3
                     for h in s4_hinges)
             and s4_side.volume < s4_side_vol
             and s4_door.volume < s4_door_vol)
    print(f"  Comp bodies: {n4}, Hinges: {len(s4_hinges)}, Screws: {len(s4_screws)}")
    print(f"  Side rebate: {s4_side.volume < s4_side_vol}, "
          f"Door rebate: {s4_door.volume < s4_door_vol}")
    print(f"  S4: {'PASS' if s4_ok else 'FAIL'}\n")
    if not s4_ok:
        all_pass = False
    results["S4"] = s4_ok

    # ================================================================
    # S5: door_flush — 1603A3, with 1/16" gap
    # ================================================================
    print("=" * 50)
    print("S5: door_flush — 1603A3, 2 hinges + screws, 1/16\" gap")
    print("=" * 50)

    PART5 = "1603a3"
    params.add("s5_h", VI("12 in"), "in", "S5 cabinet height")
    params.add("s5_bt", VI("0.5 in"), "in", "S5 board thick")
    params.add("s5_door_w", VI("8 in"), "in", "S5 door width")
    params.add("s5_depth", VI("12 in"), "in", "S5 cabinet depth")
    params.add("s5_gap", VI("0.0625 in"), "in", "S5 door gap")
    params.add("s5_off_x", VI("s4_off_x + s4_bt + s4_door_w + 4 in"),
               "in", "S5 X offset")

    occ5 = sp.make_comp(root, "S5")
    comp5 = occ5.component

    # Case side
    sk, pr = sp.sketch_rect_model(comp5, comp5.xYConstructionPlane,
        ("s5_off_x", "s3_off_y", "0 in"),
        {"x": "s5_bt", "y": "s5_depth"}, "S5_Side_Sk", ctx.ev)
    s5_side = sp.ext_new(comp5, pr, "s5_h", "S5_Side").bodies.item(0)
    s5_side.name = "S5_Side"

    # Door with gap: starts at seam + gap
    sk, pr = sp.sketch_rect_model(comp5, comp5.xYConstructionPlane,
        ("s5_off_x + s5_bt + s5_gap", "s3_off_y", "0 in"),
        {"x": "s5_door_w", "y": "s5_bt"}, "S5_Door_Sk", ctx.ev)
    s5_door = sp.ext_new(comp5, pr, "s5_h", "S5_Door").bodies.item(0)
    s5_door.name = "S5_Door"

    s5_side_vol = s5_side.volume
    s5_door_vol = s5_door.volume

    gap_cm = ctx.ev("s5_gap")
    print(f"  Gap: {gap_cm:.4f} cm = {gap_cm/2.54:.4f} in")

    s5_hinges = []
    s5_screws = []
    for frac, sfx in [("s5_h / 4", "Lo"), ("s5_h * 3 / 4", "Hi")]:
        result = hardware.install_butt_hinge(
            part_id=PART5, comp=comp5,
            door_body=s5_door, case_body=s5_side,
            pin_position=("s5_off_x + s5_bt", "s3_off_y", frac),
            pin_axis="z", style="door_flush",
            gap=gap_cm,
            ev=ctx.ev, name=f"S5_Hinge_{sfx}")
        s5_hinges.append(result)
        screws = hardware.install_hinge_screws(result, comp5,
                                                ev=ctx.ev, name=f"S5_Screw_{sfx}")
        s5_screws.extend(screws)

    n5 = comp5.bRepBodies.count
    s5_ok = (n5 == 2
             and len(s5_hinges) == 2
             and all(h["occurrence"].component.bRepBodies.count == 3
                     for h in s5_hinges)
             and s5_side.volume < s5_side_vol
             and s5_door.volume < s5_door_vol)
    print(f"  Comp bodies: {n5}, Hinges: {len(s5_hinges)}, Screws: {len(s5_screws)}")
    print(f"  Side rebate: {s5_side.volume < s5_side_vol}, "
          f"Door rebate: {s5_door.volume < s5_door_vol}")
    print(f"  S5: {'PASS' if s5_ok else 'FAIL'}\n")
    if not s5_ok:
        all_pass = False
    results["S5"] = s5_ok

    # ================================================================
    # Summary
    # ================================================================
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)

    for occ_item in root.occurrences:
        c = occ_item.component
        n = c.bRepBodies.count
        body_names = [c.bRepBodies.item(i).name for i in range(n)]
        print(f"  {c.name}: {n} bodies -> {body_names}")

    total_screws = len(s1_screws) + len(s2_screws) + len(s3_screws) + \
                   len(s4_screws) + len(s5_screws)
    print(f"\n  Total screws installed: {total_screws}")

    status = "PASS" if all_pass else "FAIL"
    detail = " ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in results.items())
    print(f"\n{status}: {detail}")

    # Hide construction
    for occ_item in root.occurrences:
        c = occ_item.component
        for sk_item in c.sketches:
            sk_item.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
