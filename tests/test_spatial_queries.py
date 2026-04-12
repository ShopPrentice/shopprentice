"""Test sp.body_side, sp.face_side, sp.classify_bodies.

Creates simple geometry (boxes) and verifies spatial classification.
Run via execute_script with sandbox=true.
"""
import adsk.core, adsk.fusion
from helpers import sp

P = adsk.core.Point3D.create
VI = adsk.core.ValueInput.createByString
NEWBODY = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def run(context):
    ctx = sp.DesignContext()
    root = ctx.root
    params = ctx.params

    # ── Create test geometry ──────────────────────────────────────
    # Big box at origin: 10x10x10 cm centered at (5,5,5)
    sk1, prof1 = sp.sketch_rect(root, root.xYConstructionPlane,
                                 "0 cm", "0 cm", "10 cm", "10 cm",
                                 name="BigBox_Sk")
    big_ext = sp.ext_new(root, prof1, "10 cm", "BigBox")
    big = big_ext.bodies.item(0)
    big.name = "Big"

    # Small box ABOVE big: 2x2x2 at (4,4,12)
    above_pl = sp.off_plane(root, root.xYConstructionPlane, "12 cm", "AbovePl")
    sk2, prof2 = sp.sketch_rect(root, above_pl,
                                 "4 cm", "4 cm", "2 cm", "2 cm",
                                 name="Above_Sk")
    above_ext = sp.ext_new(root, prof2, "2 cm", "AboveBox")
    above = above_ext.bodies.item(0)
    above.name = "Above"

    # Small box BELOW big: 2x2x2 at (4,4,-4)
    below_pl = sp.off_plane(root, root.xYConstructionPlane, "-4 cm", "BelowPl")
    sk3, prof3 = sp.sketch_rect(root, below_pl,
                                 "4 cm", "4 cm", "2 cm", "2 cm",
                                 name="Below_Sk")
    below_ext = sp.ext_new(root, prof3, "2 cm", "BelowBox")
    below = below_ext.bodies.item(0)
    below.name = "Below"

    # Small box INSIDE big: 2x2x2 at (4,4,4)
    inside_pl = sp.off_plane(root, root.xYConstructionPlane, "4 cm", "InsidePl")
    sk4, prof4 = sp.sketch_rect(root, inside_pl,
                                 "4 cm", "4 cm", "2 cm", "2 cm",
                                 name="Inside_Sk")
    inside_ext = sp.ext_new(root, prof4, "2 cm", "InsideBox")
    inside_body = inside_ext.bodies.item(0)
    inside_body.name = "Inside"

    # Small box to the RIGHT of big: 2x2x2 at (12,4,4)
    right_pl = sp.off_plane(root, root.xYConstructionPlane, "4 cm", "RightPl2")
    sk5, prof5 = sp.sketch_rect(root, right_pl,
                                 "12 cm", "4 cm", "2 cm", "2 cm",
                                 name="Right_Sk")
    right_ext = sp.ext_new(root, prof5, "2 cm", "RightBox")
    right = right_ext.bodies.item(0)
    right.name = "Right"

    passed = 0
    failed = 0

    def check(test_name, actual, expected):
        nonlocal passed, failed
        if actual == expected:
            passed += 1
        else:
            failed += 1
            print(f"FAIL: {test_name}: expected {expected}, got {actual}")

    # ── Test body_side ────────────────────────────────────────────
    # Above box, testing +Z direction → should be 'outside'
    check("above +Z", sp.body_side(above, big, (0, 0, 1)), 'outside')
    # Above box, testing -Z direction → should be 'opposite'
    check("above -Z", sp.body_side(above, big, (0, 0, -1)), 'opposite')

    # Below box, testing -Z direction → should be 'outside'
    check("below -Z", sp.body_side(below, big, (0, 0, -1)), 'outside')
    # Below box, testing +Z direction → should be 'opposite'
    check("below +Z", sp.body_side(below, big, (0, 0, 1)), 'opposite')

    # Inside box → should be 'inside' regardless of direction
    check("inside +Z", sp.body_side(inside_body, big, (0, 0, 1)), 'inside')
    check("inside -Z", sp.body_side(inside_body, big, (0, 0, -1)), 'inside')
    check("inside +X", sp.body_side(inside_body, big, (1, 0, 0)), 'inside')

    # Right box, testing +X direction → should be 'outside'
    check("right +X", sp.body_side(right, big, (1, 0, 0)), 'outside')
    # Right box, testing -X direction → should be 'opposite'
    check("right -X", sp.body_side(right, big, (-1, 0, 0)), 'opposite')
    # Right box, testing +Z → COM is at same Z as big center, so dot≈0
    # This is an edge case — the right box is level with big, not above
    right_z = sp.body_side(right, big, (0, 0, 1))
    check("right +Z", right_z in ('outside', 'opposite'), True)

    # ── Test face_side ────────────────────────────────────────────
    top_face = sp.find_face(big, "z", +1)

    check("above vs top face", sp.face_side(above, top_face), 'normal')
    check("below vs top face", sp.face_side(below, top_face), 'anti')
    # Inside body COM is at Z=5, top face is at Z=10 → anti
    check("inside vs top face", sp.face_side(inside_body, top_face), 'anti')

    bot_face = sp.find_face(big, "z", -1)
    check("below vs bot face", sp.face_side(below, bot_face), 'normal')
    check("above vs bot face", sp.face_side(above, bot_face), 'anti')

    # ── Test classify_bodies ──────────────────────────────────────
    all_small = [above, below, inside_body, right]

    # With direction +Z
    groups = sp.classify_bodies(all_small, big, (0, 0, 1))
    check("classify inside count", len(groups['inside']), 1)
    check("classify outside +Z count", len(groups['outside']), 1)
    check("classify opposite +Z count", len(groups['opposite']), 2)
    check("classify inside is Inside", groups['inside'][0].name, "Inside")
    check("classify outside is Above", groups['outside'][0].name, "Above")

    # Without direction — all outside bodies go to 'outside'
    groups2 = sp.classify_bodies(all_small, big)
    check("classify no-dir inside", len(groups2['inside']), 1)
    check("classify no-dir outside", len(groups2['outside']), 3)
    check("classify no-dir opposite", len(groups2['opposite']), 0)

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"{failed} TESTS FAILED")
