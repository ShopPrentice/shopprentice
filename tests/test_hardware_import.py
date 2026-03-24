"""Test hardware STEP import workflow.

End-to-end test:
  1. Create a simple hinge-shaped body in Fusion
  2. Export it as STEP
  3. Register it in the hardware catalog
  4. Import it back into a fresh design using hardware.install()
  5. Verify the imported body exists and is positioned correctly
  6. CUT mortise into a test board
  7. Verify body count

This test is self-contained — no manual McMaster-Carr download needed.

Expected bodies:
  T1: 1 board + 1 imported hinge (inside child component) = 1 root body
      + 1 child occurrence with 1 body. Mortise CUT into board.
  T2: 1 board + catalog install with position offset = same structure.
"""
import adsk.core
import adsk.fusion
import os
import tempfile


def run(context):
    app = adsk.core.Application.get()

    # ================================================================
    # Phase 1: Create a dummy hinge body and export as STEP
    # ================================================================
    print("=" * 50)
    print("Phase 1: Create dummy hinge + export STEP")
    print("=" * 50)

    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root = design.rootComponent

    from helpers import sp

    # Create a simple hinge leaf: thin rectangle + cylinder knuckle
    # Leaf plate: 3.175cm x 1.27cm x 0.127cm (1.25" x 0.5" x 0.050")
    params = design.userParameters
    VI = adsk.core.ValueInput.createByString
    params.add("th_l", VI("1.25 in"), "in", "Hinge length")
    params.add("th_w", VI("0.5 in"), "in", "Leaf width")
    params.add("th_t", VI("0.050 in"), "in", "Leaf thickness")
    params.add("th_bd", VI("0.1875 in"), "in", "Barrel diameter")

    ctx = sp.DesignContext(design)

    # Leaf plate on XY plane at origin
    sk, pr = sp.sketch_rect_model(root, root.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "th_l", "y": "th_w"}, "Leaf_Sk", ctx.ev)
    leaf_ext = sp.ext_new(root, pr, "th_t", "LeafPlate")
    leaf_body = leaf_ext.bodies.item(0)
    leaf_body.name = "LeafPlate"

    # Knuckle cylinder at Y=0 edge, centered on X
    knuckle_pl = sp.off_plane(root, root.yZConstructionPlane,
                               "th_l / 2", "KnucklePl")
    sk2 = root.sketches.add(knuckle_pl)
    sk2.name = "Knuckle_Sk"
    P = adsk.core.Point3D
    m = sk2.modelToSketchSpace
    bc = m(P.create(ctx.ev("th_l / 2"), 0, ctx.ev("th_t / 2")))
    r = ctx.ev("th_bd") / 2
    circle = sk2.sketchCurves.sketchCircles.addByCenterRadius(
        P.create(bc.x, bc.y, 0), r)
    sk2.sketchDimensions.addDiameterDimension(
        circle, P.create(bc.x + r + 0.5, bc.y, 0)
    ).parameter.expression = "th_bd"

    prof = sk2.profiles.item(0)
    knuckle_ext = sp.ext_new_sym(root, prof, "th_l", "Knuckle")
    knuckle_body = knuckle_ext.bodies.item(0)
    knuckle_body.name = "Knuckle"

    n = root.bRepBodies.count
    print(f"  Created dummy hinge: {n} bodies")
    assert n == 2, f"Expected 2 bodies, got {n}"

    # Export as STEP
    # Use repo hardware directory
    step_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "hardware", "hinges")
    os.makedirs(step_dir, exist_ok=True)
    step_path = os.path.join(step_dir, "test_hinge.step")

    export_mgr = design.exportManager
    step_opts = export_mgr.createSTEPExportOptions(step_path, root)
    export_mgr.execute(step_opts)
    assert os.path.isfile(step_path), f"STEP export failed: {step_path}"
    print(f"  Exported STEP: {step_path}")
    print(f"  File size: {os.path.getsize(step_path)} bytes")

    # Close the dummy design
    app.activeDocument.close(False)
    print("  Phase 1: PASS\n")

    # ================================================================
    # Phase 2: Register in catalog and import into fresh design
    # ================================================================
    print("=" * 50)
    print("Phase 2: Register + import via hardware.install()")
    print("=" * 50)

    from helpers import hardware

    # Register the test hinge
    hardware.register_part(
        part_id="test_hinge",
        name="Test Hinge (dummy)",
        category="hinge",
        step_file="hinges/test_hinge.step",
        dimensions={
            "length": "1.25 in",
            "leaf_width": "0.5 in",
            "leaf_thickness": "0.050 in",
            "barrel_diameter": "0.1875 in",
        },
        anchor={
            "origin": [0, 0, 0],
            "axes": {"pin": "x"},
        },
        notes="Auto-generated test hinge for import workflow validation",
    )

    # Verify catalog
    parts = hardware.list_parts(category="hinge")
    print(f"  Catalog has {len(parts)} hinge(s): {[p['part_id'] for p in parts]}")
    assert len(parts) >= 1

    found = hardware.search("test hinge")
    assert len(found) >= 1, "Search didn't find test_hinge"
    print(f"  Search 'test hinge': found {len(found)} result(s)")

    # Create fresh design with a test board
    design2 = adsk.fusion.Design.cast(app.activeProduct)
    design2.designType = adsk.fusion.DesignTypes.ParametricDesignType
    root2 = design2.rootComponent
    params2 = design2.userParameters

    params2.add("board_l", VI("8 in"), "in", "Board length")
    params2.add("board_w", VI("4 in"), "in", "Board width")
    params2.add("board_t", VI("0.5 in"), "in", "Board thickness")

    ctx2 = sp.DesignContext(design2)

    # Board on XY plane
    sk, pr = sp.sketch_rect_model(root2, root2.xYConstructionPlane,
        ("0 in", "0 in", "0 in"),
        {"x": "board_l", "y": "board_w"}, "Board_Sk", ctx2.ev)
    board_ext = sp.ext_new(root2, pr, "board_t", "Board")
    board_body = board_ext.bodies.item(0)
    board_body.name = "Board"

    print(f"  Board created: 1 body")

    # Install the test hinge at an offset position
    # Position: 2" from left edge, at Y=0 (front edge), on top of board
    pos_x = ctx2.ev("2 in")
    pos_y = 0.0
    pos_z = ctx2.ev("board_t")  # on top of board

    result = hardware.install(
        part_id="test_hinge",
        comp=root2,
        position=(pos_x, pos_y, pos_z),
        board=board_body,
        mortise=True,
        keep_tool=True,
        name="TestHinge",
    )

    print(f"  Installed: occurrence={result['occurrence'].component.name}")
    print(f"  Bodies in import: {len(result['bodies'])}")
    print(f"  CUT result: {result['cut']}")

    # Count bodies
    # Root should have 1 board body (with mortise CUT)
    root_bodies = root2.bRepBodies.count
    root_names = [root2.bRepBodies.item(i).name for i in range(root_bodies)]
    print(f"  Root bodies: {root_bodies} -> {root_names}")

    # Child component should have the imported hinge bodies
    child_comp = result['occurrence'].component
    child_bodies = child_comp.bRepBodies.count
    child_names = [child_comp.bRepBodies.item(i).name
                   for i in range(child_bodies)]
    print(f"  Import bodies: {child_bodies} -> {child_names}")

    # Verify at least 1 root body (board) and 1+ imported bodies
    assert root_bodies >= 1, f"Expected board body, got {root_bodies}"
    assert child_bodies >= 1, f"Expected imported bodies, got {child_bodies}"
    print("  Phase 2: PASS\n")

    # ================================================================
    # Phase 3: Verify positioning via body bounding box
    # ================================================================
    print("=" * 50)
    print("Phase 3: Verify position")
    print("=" * 50)

    # Check that imported bodies moved to the expected position
    # The hinge was created at origin (0,0,0) with length along X.
    # After move, min X of the bounding box should be near pos_x.
    occ = result['occurrence']
    child_comp = occ.component
    body0 = child_comp.bRepBodies.item(0)
    # Get bounding box in assembly context
    proxy = body0.createForAssemblyContext(occ)
    bb = proxy.boundingBox
    min_x = bb.minPoint.x
    min_z = bb.minPoint.z
    print(f"  Body bounding box min: ({min_x:.3f}, {bb.minPoint.y:.3f}, {min_z:.3f}) cm")
    print(f"  Expected X offset: {pos_x:.3f} cm, Z offset: {pos_z:.3f} cm")

    tol = 0.1  # 1mm tolerance (STEP import can have slight offsets)
    assert abs(min_x - pos_x) < tol, f"X position off: {min_x} vs {pos_x}"
    assert abs(min_z - pos_z) < tol, f"Z position off: {min_z} vs {pos_z}"
    print("  Phase 3: PASS\n")

    # ================================================================
    # Summary
    # ================================================================
    print("=" * 50)
    print("ALL PHASES PASS")
    print("=" * 50)

    # Hide construction
    for sk_item in root2.sketches:
        sk_item.isVisible = False
    for cp in root2.constructionPlanes:
        cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
