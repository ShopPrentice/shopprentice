"""Test: agent auto-selects hinge style from furniture context.

Builds 3 scenarios and picks the correct style based on geometry:
  A) A box with a lid → lid_flush (hidden hinge between lid and back)
  B) A cabinet with inset door → door_flush (hidden hinge between door and case)
  C) A box with visible hinges → lid_surface (hinges on back face)

The style is NOT hardcoded — it's derived from the context.
"""
import adsk.core
import adsk.fusion


def pick_hinge_style(joint_type, visible):
    """Pick hinge style from furniture context.

    joint_type: "lid" (horizontal joint, lid flips up) or "door" (vertical joint, door swings)
    visible: True = surface mount (hinge visible), False = flush mount (hinge hidden)
    """
    if joint_type == "lid":
        return "lid_surface" if visible else "lid_flush"
    elif joint_type == "door":
        return "door_surface" if visible else "door_flush"
    else:
        raise ValueError(f"Unknown joint type: {joint_type}")


def detect_joint_type(board_a, board_b):
    """Detect if boards meet at a horizontal (lid) or vertical (door) joint.

    Checks the shared boundary between the two boards' bounding boxes.
    If they share a Z boundary (same Z face), it's a lid joint.
    If they share an X or Y boundary, it's a door joint.
    """
    a_bb = board_a.boundingBox
    b_bb = board_b.boundingBox

    tol = 0.1  # cm tolerance

    # Check Z boundary (horizontal joint → lid)
    if abs(a_bb.maxPoint.z - b_bb.minPoint.z) < tol or abs(b_bb.maxPoint.z - a_bb.minPoint.z) < tol:
        return "lid"

    # Check X boundary (vertical joint → door)
    if abs(a_bb.maxPoint.x - b_bb.minPoint.x) < tol or abs(b_bb.maxPoint.x - a_bb.minPoint.x) < tol:
        return "door"

    # Check Y boundary (vertical joint → door)
    if abs(a_bb.maxPoint.y - b_bb.minPoint.y) < tol or abs(b_bb.maxPoint.y - a_bb.minPoint.y) < tol:
        return "door"

    return "unknown"


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

    # ── Scenario A: Box with lid (hidden hinges) ────────────────────
    print("A: Box with lid — should auto-select lid_flush")
    params.add("a_l", VI("10 in"), "in", "")
    params.add("a_w", VI("6 in"), "in", "")
    params.add("a_h", VI("5 in"), "in", "")
    params.add("a_bt", VI("0.5 in"), "in", "")

    occ_a = sp.make_comp(root, "A"); comp_a = occ_a.component
    bp = sp.off_plane(comp_a, comp_a.xZConstructionPlane, "a_w - a_bt", "A_BackPl")
    sk, pr = sp.sketch_rect_model(comp_a, bp,
        ("0 in", "a_w - a_bt", "0 in"), {"x": "a_l", "z": "a_h"}, "A_Back_Sk", ctx.ev)
    a_back = sp.ext_new(comp_a, pr, "a_bt", "A_Back").bodies.item(0)
    a_back.name = "A_Back"
    lp = sp.off_plane(comp_a, comp_a.xYConstructionPlane, "a_h", "A_LidPl")
    sk, pr = sp.sketch_rect_model(comp_a, lp,
        ("0 in", "0 in", "a_h"), {"x": "a_l", "y": "a_w"}, "A_Lid_Sk", ctx.ev)
    a_lid = sp.ext_new(comp_a, pr, "a_bt", "A_Lid").bodies.item(0)
    a_lid.name = "A_Lid"

    # Auto-detect style
    jt = detect_joint_type(a_back, a_lid)
    visible = False  # design choice: hidden
    style = pick_hinge_style(jt, visible)
    print(f"  Detected: joint_type={jt}, visible={visible} → style={style}")
    assert style == "lid_flush", f"Expected lid_flush, got {style}"

    bv, lv = a_back.volume, a_lid.volume
    part_id = hardware.recommend_hinge(lid_length_cm=ctx.ev("a_l"))["part_id"]
    for frac, sfx in [("a_l / 4", "L"), ("a_l * 3 / 4", "R")]:
        hardware.install_butt_hinge(part_id=part_id, comp=comp_a,
            back_body=a_back, lid_body=a_lid,
            pin_position=(ctx.ev(frac), ctx.ev("a_w"), ctx.ev("a_h")),
            style=style, ev=ctx.ev, name=f"A_H_{sfx}")
    ok_a = a_back.volume < bv and a_lid.volume < lv
    print(f"  Back cut: {a_back.volume < bv}, Lid cut: {a_lid.volume < lv} → {'PASS' if ok_a else 'FAIL'}")
    results["A"] = ok_a

    # ── Scenario B: Cabinet with inset door (hidden hinges) ─────────
    print("\nB: Cabinet with inset door — should auto-select door_flush")
    params.add("b_h", VI("24 in"), "in", "")
    params.add("b_bt", VI("0.75 in"), "in", "")
    params.add("b_door_w", VI("12 in"), "in", "")
    params.add("b_depth", VI("16 in"), "in", "")
    params.add("b_off_x", VI("a_l + 4 in"), "in", "")

    occ_b = sp.make_comp(root, "B"); comp_b = occ_b.component
    # Case side: thin in X, deep in Y
    sk, pr = sp.sketch_rect_model(comp_b, comp_b.xYConstructionPlane,
        ("b_off_x", "0 in", "0 in"), {"x": "b_bt", "y": "b_depth"}, "B_Side_Sk", ctx.ev)
    b_side = sp.ext_new(comp_b, pr, "b_h", "B_Side").bodies.item(0)
    b_side.name = "B_Side"
    # Door: extends in +X from side, thin in Y
    sk, pr = sp.sketch_rect_model(comp_b, comp_b.xYConstructionPlane,
        ("b_off_x + b_bt", "0 in", "0 in"), {"x": "b_door_w", "y": "b_bt"}, "B_Door_Sk", ctx.ev)
    b_door = sp.ext_new(comp_b, pr, "b_h", "B_Door").bodies.item(0)
    b_door.name = "B_Door"

    jt = detect_joint_type(b_side, b_door)
    visible = False  # design choice: hidden
    style = pick_hinge_style(jt, visible)
    print(f"  Detected: joint_type={jt}, visible={visible} → style={style}")
    assert style == "door_flush", f"Expected door_flush, got {style}"

    sv, dv = b_side.volume, b_door.volume
    part_id = hardware.recommend_hinge(lid_length_cm=ctx.ev("b_h"))["part_id"]
    for frac, sfx in [("b_h / 4", "Lo"), ("b_h * 3 / 4", "Hi")]:
        hardware.install_butt_hinge(part_id=part_id, comp=comp_b,
            door_body=b_door, case_body=b_side,
            pin_position=("b_off_x + b_bt", "0 in", frac),
            style=style, ev=ctx.ev, name=f"B_H_{sfx}")
    ok_b = b_side.volume < sv and b_door.volume < dv
    print(f"  Side cut: {b_side.volume < sv}, Door cut: {b_door.volume < dv} → {'PASS' if ok_b else 'FAIL'}")
    results["B"] = ok_b

    # ── Scenario C: Box with visible hinges ─────────────────────────
    print("\nC: Box with visible hinges — should auto-select lid_surface")
    params.add("c_l", VI("6 in"), "in", "")
    params.add("c_w", VI("4 in"), "in", "")
    params.add("c_h", VI("3 in"), "in", "")
    params.add("c_bt", VI("0.375 in"), "in", "")
    params.add("c_off_y", VI("a_w + 4 in"), "in", "")

    occ_c = sp.make_comp(root, "C"); comp_c = occ_c.component
    bp = sp.off_plane(comp_c, comp_c.xZConstructionPlane, "c_w + c_off_y - c_bt", "C_BackPl")
    sk, pr = sp.sketch_rect_model(comp_c, bp,
        ("0 in", "c_w + c_off_y - c_bt", "0 in"), {"x": "c_l", "z": "c_h"}, "C_Back_Sk", ctx.ev)
    c_back = sp.ext_new(comp_c, pr, "c_bt", "C_Back").bodies.item(0)
    c_back.name = "C_Back"
    lp = sp.off_plane(comp_c, comp_c.xYConstructionPlane, "c_h", "C_LidPl")
    sk, pr = sp.sketch_rect_model(comp_c, lp,
        ("0 in", "c_off_y", "c_h"), {"x": "c_l", "y": "c_w"}, "C_Lid_Sk", ctx.ev)
    c_lid = sp.ext_new(comp_c, pr, "c_bt", "C_Lid").bodies.item(0)
    c_lid.name = "C_Lid"

    jt = detect_joint_type(c_back, c_lid)
    visible = True  # design choice: visible
    style = pick_hinge_style(jt, visible)
    print(f"  Detected: joint_type={jt}, visible={visible} → style={style}")
    assert style == "lid_surface", f"Expected lid_surface, got {style}"

    bv, lv = c_back.volume, c_lid.volume
    part_id = hardware.recommend_hinge(lid_length_cm=ctx.ev("c_l"))["part_id"]
    for frac, sfx in [("c_l / 4", "L"), ("c_l * 3 / 4", "R")]:
        hardware.install_butt_hinge(part_id=part_id, comp=comp_c,
            back_body=c_back, lid_body=c_lid,
            pin_position=(ctx.ev(frac), ctx.ev("c_w + c_off_y"), ctx.ev("c_h")),
            style=style, ev=ctx.ev, name=f"C_H_{sfx}")
    ok_c = c_back.volume < bv and c_lid.volume < lv
    print(f"  Back cut: {c_back.volume < bv}, Lid cut: {c_lid.volume < lv} → {'PASS' if ok_c else 'FAIL'}")
    results["C"] = ok_c

    # ── Summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    hardware.cleanup_step_templates()
    status = "PASS" if all(results.values()) else "FAIL"
    detail = " ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in results.items())
    print(f"{status}: {detail}")

    for occ_item in root.occurrences:
        c = occ_item.component
        for s in c.sketches:
            s.isVisible = False
        for cp in c.constructionPlanes:
            cp.isLightBulbOn = False
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
