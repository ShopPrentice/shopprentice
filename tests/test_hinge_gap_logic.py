"""Test gap-aware rebate logic for door_flush hinge installation.

Uses 1603A3 (medium hinge):
  barrel_d = 0.116 in (barrel diameter, total folded thickness)
  plate_t  ≈ 0.025 in (flat leaf plate, measured from STEP)

5 scenarios covering every gap-to-hinge ratio:

  G1: gap = 0            → two-side rebate (both boards cut equally)
  G2: gap = 0.04 in      → two-side rebate (gap < barrel_d - plate_t)
  G3: gap = 0.1 in       → one-side rebate (barrel_d - plate_t ≤ gap < barrel_d)
  G4: gap = 0.116 in     → no rebate (gap ≈ barrel_d, surface mount)
  G5: gap = 0.2 in       → ValueError (gap > barrel_d)
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
    hardware.clear_step_cache()
    ctx = sp.DesignContext(design)
    results = {}

    # Shared board dimensions
    params.add("g_h", VI("6 in"), "in", "")
    params.add("g_bt", VI("0.5 in"), "in", "")
    params.add("g_door_w", VI("4 in"), "in", "")
    params.add("g_depth", VI("6 in"), "in", "")
    # Spacing between fixtures along Y
    params.add("g_pitch", VI("g_depth + 4 in"), "in", "")

    def make_door_case(tag, row):
        """Build a case side + door pair at Y = row * pitch."""
        params.add(f"{tag}_gap", VI(f"{tag}_gap_val"), "in", "")
        occ = sp.make_comp(root, tag)
        comp = occ.component
        off_y = f"{row} * g_pitch"
        # Case side
        sk, pr = sp.sketch_rect_model(comp, comp.xYConstructionPlane,
            ("0 in", off_y, "0 in"),
            {"x": "g_bt", "y": "g_depth"},
            f"{tag}_Side_Sk", ctx.ev)
        side = sp.ext_new(comp, pr, "g_h", f"{tag}_Side").bodies.item(0)
        side.name = f"{tag}_Side"
        # Door (offset by board_thick + gap)
        sk, pr = sp.sketch_rect_model(comp, comp.xYConstructionPlane,
            (f"g_bt + {tag}_gap", off_y, "0 in"),
            {"x": "g_door_w", "y": "g_bt"},
            f"{tag}_Door_Sk", ctx.ev)
        door = sp.ext_new(comp, pr, "g_h", f"{tag}_Door").bodies.item(0)
        door.name = f"{tag}_Door"
        return comp, side, door

    # ── G1: gap = 0 → two-side rebate ────────────────────────────────
    print("G1: gap = 0 → two-side rebate (both boards cut)")
    params.add("G1_gap_val", VI("0 in"), "in", "")
    comp1, side1, door1 = make_door_case("G1", 0)
    sv1, dv1 = side1.volume, door1.volume
    gap1 = 0.0
    r1 = hardware.install_butt_hinge(
        part_id="1603a3", comp=comp1,
        door_body=door1, case_body=side1,
        pin_position=("g_bt", "0 in", "g_h / 2"),
        style="door_flush", gap=gap1, ev=ctx.ev, name="G1_H")
    ok1 = side1.volume < sv1 and door1.volume < dv1
    print(f"  Side cut: {side1.volume < sv1}, Door cut: {door1.volume < dv1}"
          f" → {'PASS' if ok1 else 'FAIL'}")
    results["G1_two_side_zero"] = ok1

    # ── G2: gap = 0.04 in → two-side rebate ──────────────────────────
    print("\nG2: gap = 0.04 in → two-side rebate")
    params.add("G2_gap_val", VI("0.04 in"), "in", "")
    comp2, side2, door2 = make_door_case("G2", 1)
    sv2, dv2 = side2.volume, door2.volume
    gap2 = ctx.ev("G2_gap")
    r2 = hardware.install_butt_hinge(
        part_id="1603a3", comp=comp2,
        door_body=door2, case_body=side2,
        pin_position=("g_bt", "1 * g_pitch", "g_h / 2"),
        style="door_flush", gap=gap2, ev=ctx.ev, name="G2_H")
    ok2 = side2.volume < sv2 and door2.volume < dv2
    print(f"  Side cut: {side2.volume < sv2}, Door cut: {door2.volume < dv2}"
          f" → {'PASS' if ok2 else 'FAIL'}")
    results["G2_two_side_small_gap"] = ok2

    # ── G3: gap = 0.1 in → one-side rebate (case side only) ──────────
    print("\nG3: gap = 0.1 in → one-side rebate (case only)")
    params.add("G3_gap_val", VI("0.1 in"), "in", "")
    comp3, side3, door3 = make_door_case("G3", 2)
    sv3, dv3 = side3.volume, door3.volume
    gap3 = ctx.ev("G3_gap")
    r3 = hardware.install_butt_hinge(
        part_id="1603a3", comp=comp3,
        door_body=door3, case_body=side3,
        pin_position=("g_bt", "2 * g_pitch", "g_h / 2"),
        style="door_flush", gap=gap3, ev=ctx.ev, name="G3_H")
    ok3_side = side3.volume < sv3
    # Door gets screw holes (small cut) but no rebate pocket.
    # Side rebate >> door screw holes.
    side_cut3 = sv3 - side3.volume
    door_cut3 = dv3 - door3.volume
    ok3_bigger = side_cut3 > door_cut3 * 2  # side rebate much larger
    ok3 = ok3_side and ok3_bigger
    print(f"  Side cut: {side_cut3:.4f}, Door cut: {door_cut3:.4f}"
          f" (side >> door) → {'PASS' if ok3 else 'FAIL'}")
    results["G3_one_side"] = ok3

    # ── G4: gap = 0.116 in → no rebate (gap ≈ barrel_d) ──────────────
    print("\nG4: gap = 0.116 in → no rebate (surface mount)")
    params.add("G4_gap_val", VI("0.116 in"), "in", "")
    comp4, side4, door4 = make_door_case("G4", 3)
    sv4, dv4 = side4.volume, door4.volume
    gap4 = ctx.ev("G4_gap")
    r4 = hardware.install_butt_hinge(
        part_id="1603a3", comp=comp4,
        door_body=door4, case_body=side4,
        pin_position=("g_bt", "3 * g_pitch", "g_h / 2"),
        style="door_flush", gap=gap4, ev=ctx.ev, name="G4_H")
    # No rebate pocket — only screw holes (small volume change).
    side_cut4 = sv4 - side4.volume
    door_cut4 = dv4 - door4.volume
    ok4 = side_cut4 < 0.1 and door_cut4 < 0.1  # tiny screw holes only
    print(f"  Side cut: {side_cut4:.4f}, Door cut: {door_cut4:.4f}"
          f" (screw holes only) → {'PASS' if ok4 else 'FAIL'}")
    results["G4_no_rebate"] = ok4

    # ── G5: gap = 0.2 in → ValueError (gap > barrel_d) ───────────────
    print("\nG5: gap = 0.2 in → should raise ValueError")
    params.add("G5_gap_val", VI("0.2 in"), "in", "")
    comp5, side5, door5 = make_door_case("G5", 4)
    gap5 = ctx.ev("G5_gap")
    try:
        hardware.install_butt_hinge(
            part_id="1603a3", comp=comp5,
            door_body=door5, case_body=side5,
            pin_position=("g_bt", "4 * g_pitch", "g_h / 2"),
            style="door_flush", gap=gap5, ev=ctx.ev, name="G5_H")
        ok5 = False
        print("  ERROR: No exception raised!")
    except ValueError as e:
        ok5 = True
        print(f"  ValueError raised: {e} → PASS")
    except Exception as e:
        ok5 = False
        print(f"  Wrong exception: {type(e).__name__}: {e} → FAIL")
    results["G5_error"] = ok5

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    hardware.cleanup_step_templates()

    status = "PASS" if all(results.values()) else "FAIL"
    detail = "\n".join(f"  {k}: {'PASS' if v else 'FAIL'}"
                       for k, v in results.items())
    print(f"\n{status}:\n{detail}")

    for occ_item in root.occurrences:
        c = occ_item.component
        for s in c.sketches:
            s.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
