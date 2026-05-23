"""Test find_faces_at_offset and edges_from_faces helpers.

Uses sp.sketch_rect_model for reliable geometry placement.

  T1: Simple protrusion — find tip face
  T2: Multiple protrusions at same offset
  T3: Different offsets — only correct one matches
  T4: Decoy faces — perpendicular, not selected
  T5: Negative offset — find face behind reference
  T6: No matching faces
  T7: Cross-body reference
  T8: edges_from_faces count
"""
import adsk.core
import adsk.fusion
import sys


def run(context):
    for _mod in list(sys.modules):
        if _mod.startswith("woodworking") or _mod.startswith("helpers"):
            del sys.modules[_mod]

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString

    from helpers import sp

    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation

    passed = 0
    failed = 0

    def assert_eq(name, actual, expected, msg=""):
        nonlocal passed, failed
        if actual == expected:
            print(f"  PASS: {name}" + (f" — {msg}" if msg else ""))
            passed += 1
        else:
            print(f"  FAIL: {name}: expected {expected}, got {actual}"
                  + (f" — {msg}" if msg else ""))
            failed += 1

    ev = sp._make_ev()

    def box_at(comp, x, y, z, wx, wy, wz, name):
        """Create an axis-aligned box using sketch_rect_model."""
        # Sketch on XZ plane at y, extrude in +Y
        pl = sp.off_plane(comp, comp.xZConstructionPlane,
                          f"{y} cm", f"{name}_pl")
        _, pr = sp.sketch_rect_model(comp, pl,
            (f"{x} cm", f"{y} cm", f"{z} cm"),
            {"x": f"{wx} cm", "z": f"{wz} cm"},
            f"{name}_sk", ev)
        b = sp.ext_new(comp, pr, f"{wy} cm", f"{name}_ext").bodies.item(0)
        b.name = name
        return b

    S = 10.0  # spacing

    # ================================================================
    # T1: Box 4×3×2 at origin. Protrusion 1×1×0.5 on +Y face.
    # Ref = separate thin plate at y=3 (+Y face, normal +Y).
    # offset = +0.5 → tip at y=3.5.
    # ================================================================
    print("\n=== T1: Simple protrusion ===")
    test1 = box_at(root, 0, 0, 0, 4, 3, 2, "T1")
    # Protrusion on +Y face
    top1 = sp.find_face(test1, "y", +1)
    _, pr = sp.sketch_rect_model(root, top1,
        ("1.5 cm", "3 cm", "0.5 cm"),
        {"x": "1 cm", "z": "1 cm"}, "T1_bump_sk", ev)
    sp.refs_to_construction(root.sketches.itemByName("T1_bump_sk"))
    pr = sp.smallest_profile(root.sketches.itemByName("T1_bump_sk"))
    sp.ext_op(root, pr, "0.5 cm", JOIN, [test1], "T1_bump")

    # Ref body at y=[3, 3.01]
    ref1 = box_at(root, 0, 3, 0, 4, 0.01, 2, "T1_ref")
    ref_face1 = sp.find_face(ref1, "y", +1)  # y≈3.01, normal +Y

    faces1 = sp.find_faces_at_offset(test1, ref_face1, 0.49, tol=0.02)
    assert_eq("T1 count", len(faces1), 1, "tip at y=3.5")

    # Verify position
    if faces1:
        y_val = faces1[0].pointOnFace.y
        assert_eq("T1 y pos", abs(y_val - 3.5) < 0.02, True,
                  f"y={y_val:.3f}")

    # ================================================================
    # T2: Three protrusions at same offset
    # ================================================================
    print("\n=== T2: Multiple protrusions ===")
    test2 = box_at(root, S, 0, 0, 4, 3, 6, "T2")
    base_pl2 = sp.off_plane(root, root.xZConstructionPlane, "3 cm", "T2_base_pl")
    for i, z in enumerate([0.5, 2.5, 4.5]):
        _, pr = sp.sketch_rect_model(root, base_pl2,
            (f"{S+1.5} cm", "3 cm", f"{z} cm"),
            {"x": "1 cm", "z": "1 cm"}, f"T2_b{i}_sk", ev)
        sp.ext_op(root, pr, "0.5 cm", JOIN, [test2], f"T2_b{i}")

    ref2 = box_at(root, S, 3, 0, 4, 0.01, 6, "T2_ref")
    faces2 = sp.find_faces_at_offset(
        test2, sp.find_face(ref2, "y", +1), 0.49, tol=0.02)
    assert_eq("T2 count", len(faces2), 3, "3 tips")

    # ================================================================
    # T3: Different offsets
    # ================================================================
    print("\n=== T3: Different offsets ===")
    test3 = box_at(root, 2*S, 0, 0, 4, 3, 4, "T3")
    base_pl3 = sp.off_plane(root, root.xZConstructionPlane, "3 cm", "T3_base_pl")
    _, pr = sp.sketch_rect_model(root, base_pl3,
        (f"{2*S+0.5} cm", "3 cm", "0.5 cm"),
        {"x": "1 cm", "z": "1 cm"}, "T3_short_sk", ev)
    sp.ext_op(root, pr, "0.5 cm", JOIN, [test3], "T3_short")

    _, pr = sp.sketch_rect_model(root, base_pl3,
        (f"{2*S+2.5} cm", "3 cm", "2.5 cm"),
        {"x": "1 cm", "z": "1 cm"}, "T3_tall_sk", ev)
    sp.ext_op(root, pr, "1.0 cm", JOIN, [test3], "T3_tall")

    ref3 = box_at(root, 2*S, 3, 0, 4, 0.01, 4, "T3_ref")
    rf3 = sp.find_face(ref3, "y", +1)
    assert_eq("T3 at 0.5", len(sp.find_faces_at_offset(test3, rf3, 0.49, tol=0.02)),
              1, "short only")
    assert_eq("T3 at 1.0", len(sp.find_faces_at_offset(test3, rf3, 0.99, tol=0.02)),
              1, "tall only")
    assert_eq("T3 wrong", len(sp.find_faces_at_offset(test3, rf3, 2.0)),
              0, "nothing")

    # ================================================================
    # T4: Decoy — +X protrusion at same Y, wrong orientation
    # ================================================================
    print("\n=== T4: Decoy faces ===")
    test4 = box_at(root, 3*S, 0, 0, 4, 3, 3, "T4")
    top4 = sp.find_face(test4, "y", +1)
    _, pr = sp.sketch_rect_model(root, top4,
        (f"{3*S+1.5} cm", "3 cm", "1 cm"),
        {"x": "1 cm", "z": "1 cm"}, "T4_y_sk", ev)
    sp.refs_to_construction(root.sketches.itemByName("T4_y_sk"))
    pr = sp.smallest_profile(root.sketches.itemByName("T4_y_sk"))
    sp.ext_op(root, pr, "0.5 cm", JOIN, [test4], "T4_y")

    # +X protrusion (perpendicular — should not match Y search)
    xf4 = sp.find_face(test4, "x", +1)
    _, pr = sp.sketch_rect_model(root, xf4,
        (f"{3*S+4} cm", "1 cm", "1 cm"),
        {"y": "1 cm", "z": "1 cm"}, "T4_x_sk", ev)
    sp.refs_to_construction(root.sketches.itemByName("T4_x_sk"))
    pr = sp.smallest_profile(root.sketches.itemByName("T4_x_sk"))
    sp.ext_op(root, pr, "0.5 cm", JOIN, [test4], "T4_x")

    ref4 = box_at(root, 3*S, 3, 0, 4, 0.01, 3, "T4_ref")
    faces4 = sp.find_faces_at_offset(
        test4, sp.find_face(ref4, "y", +1), 0.49, tol=0.02)
    assert_eq("T4 count", len(faces4), 1, "only +Y, not +X")

    # ================================================================
    # T5: Negative offset — use +Y face to find -Y face
    # ================================================================
    print("\n=== T5: Negative offset ===")
    test5 = box_at(root, 4*S, 0, 0, 3, 3, 3, "T5")
    ref5 = sp.find_face(test5, "y", +1)  # y=3, normal +Y
    faces5 = sp.find_faces_at_offset(test5, ref5, -3.0)
    assert_eq("T5 neg offset", len(faces5), 1, "-Y face at y=0")

    # ================================================================
    # T6: No match
    # ================================================================
    print("\n=== T6: No match ===")
    assert_eq("T6", len(sp.find_faces_at_offset(test5, ref5, 10.0)), 0, "empty")

    # ================================================================
    # T7: Cross-body — ref on A, search B
    # ================================================================
    print("\n=== T7: Cross-body ===")
    body_a = box_at(root, 5*S, 0, 0, 3, 2, 3, "T7_A")
    body_b = box_at(root, 5*S, 2, 0, 3, 2, 3, "T7_B")
    top_b = sp.find_face(body_b, "y", +1)
    _, pr = sp.sketch_rect_model(root, top_b,
        (f"{5*S+1} cm", "4 cm", "1 cm"),
        {"x": "1 cm", "z": "1 cm"}, "T7_bump_sk", ev)
    sp.refs_to_construction(root.sketches.itemByName("T7_bump_sk"))
    pr = sp.smallest_profile(root.sketches.itemByName("T7_bump_sk"))
    sp.ext_op(root, pr, "0.5 cm", JOIN, [body_b], "T7_bump")

    ref7 = sp.find_face(body_a, "y", +1)  # y=2, normal +Y
    faces7 = sp.find_faces_at_offset(body_b, ref7, 2.5)
    assert_eq("T7 cross-body", len(faces7), 1, "B's tip via A's ref")

    # ================================================================
    # T8: edges_from_faces
    # ================================================================
    print("\n=== T8: edges_from_faces ===")
    if faces7:
        edges7 = sp.edges_from_faces(faces7)
        assert_eq("T8 edges", edges7.count, 4, "rect = 4 edges")

    # ── Summary ──
    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam

    print(f"\n{'=' * 50}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'=' * 50}")
