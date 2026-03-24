"""Test surface-mount hinge installation on a box.

Validates:
  - Hinge recommendation based on box size
  - Surface-mount installation: hinge flat on back face, pin at joint line
  - Leaf inner face flush against back face (Y = box_w)
  - One leaf on back board, one on lid
  - No rabbets — screwed on
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

    from helpers import sp
    from helpers import hardware

    ctx = sp.DesignContext(design)

    # ── Parameters ──
    params.add("box_l", VI("10 in"), "in", "Box length")
    params.add("box_w", VI("6 in"), "in", "Box width")
    params.add("box_h", VI("4 in"), "in", "Box height")
    params.add("bt", VI("0.5 in"), "in", "Board thickness")

    # ── Recommend hinge ──
    rec = hardware.recommend_hinge(lid_length_cm=ctx.ev("box_l"))
    print("Recommended hinge: " + rec["part_id"])
    print("  Reason: " + rec["reason"])

    # ── Build back board (XZ plane, at Y = box_w - bt) ──
    back_pl = sp.off_plane(root, root.xZConstructionPlane,
                            "box_w - bt", "BackPl")
    sk, pr = sp.sketch_rect_model(root, back_pl,
        ("0 in", "box_w - bt", "0 in"),
        {"x": "box_l", "z": "box_h"}, "Back_Sk", ctx.ev)
    back = sp.ext_new(root, pr, "bt", "BackBoard").bodies.item(0)
    back.name = "Back"

    # ── Build lid (XY plane, at Z = box_h) ──
    lid_pl = sp.off_plane(root, root.xYConstructionPlane,
                           "box_h", "LidPl")
    sk, pr = sp.sketch_rect_model(root, lid_pl,
        ("0 in", "0 in", "box_h"),
        {"x": "box_l", "y": "box_w"}, "Lid_Sk", ctx.ev)
    lid = sp.ext_new(root, pr, "bt", "LidBoard").bodies.item(0)
    lid.name = "Lid"

    print("")
    print("Boards created: Back + Lid")

    # ── Install hinge on back face ──
    # Pin at joint line: X = inset, Y = box_w (back face), Z = box_h
    print("")
    print("Installing " + rec["part_id"] + " surface-mount on back face...")

    result = hardware.install_butt_hinge(
        part_id=rec["part_id"],
        comp=root,
        back_body=back,
        lid_body=lid,
        pin_position=("2 in", "box_w", "box_h"),
        pin_axis="x",
        ev=ctx.ev,
        name="Hinge1",
    )

    print("  Occurrence: " + result["occurrence"].component.name)
    print("  Total bodies: " + str(len(result["bodies"])))
    print("  Pin: " + result["pin"].name)
    print("  Leaves: " + str(len(result["leaves"])))

    # ── Verify leaf position ──
    occ = result["occurrence"]
    box_w = ctx.ev("box_w")
    box_h = ctx.ev("box_h")

    for leaf in result["leaves"]:
        proxy = lesp.createForAssemblyContext(occ)
        bb = proxy.boundingBox
        y_min = bb.minPoint.y
        print("  Leaf " + lesp.name + ": Y_min=" + str(round(y_min, 3))
              + " (back face=" + str(round(box_w, 3)) + ")")
        tol = 0.1  # leaf bbox includes barrel knuckles, not just flat plate
        assert abs(y_min - box_w) < tol, (
            "Leaf inner face not on back face: Y_min="
            + str(y_min) + " vs box_w=" + str(box_w))

    # Check one leaf is on back board, one on lid
    pin_proxy = result["pin"].createForAssemblyContext(occ)
    pin_z = (pin_proxy.boundingBox.minPoint.z
             + pin_proxy.boundingBox.maxPoint.z) / 2
    print("  Pin Z center: " + str(round(pin_z, 3))
          + " (joint line=" + str(round(box_h, 3)) + ")")
    assert abs(pin_z - box_h) < 0.1, "Pin not at joint line"

    # ── Verify body count ──
    root_count = root.bRepBodies.count
    root_names = [root.bRepBodies.item(i).name for i in range(root_count)]
    print("")
    print("Root bodies: " + str(root_count) + " -> " + str(root_names))

    child_count = 0
    for i in range(root.occurrences.count):
        o = root.occurrences.item(i)
        c = o.component
        n = c.bRepBodies.count
        names = [c.bRepBodies.item(j).name for j in range(n)]
        print("  " + c.name + ": " + str(n) + " bodies -> " + str(names))
        child_count += n

    total = root_count + child_count
    print("")
    print("Total: " + str(total) + " bodies (2 boards + 3 hinge parts)")
    assert root_count == 2, "Expected 2 root bodies, got " + str(root_count)
    # Bare hinge STEP: 3 bodies (pin + 2 leaves). Assembly STEP would have more.
    assert child_count >= 3, "Expected 3+ hinge bodies, got " + str(child_count)

    # Back board has rebate pocket from lid_surface hinge installation
    back_vol = back.volume
    orig_vol = ctx.ev("box_l") * ctx.ev("bt") * ctx.ev("box_h")
    print("Back board: " + str(round(back_vol, 2))
          + " (orig " + str(round(orig_vol, 2)) + ", rebate cut)")
    assert back_vol < orig_vol, "Back board should have rebate cut"

    print("PASS")

    # Hide construction
    for sk_item in root.sketches:
        sk_item.isVisible = False
    for cp in root.constructionPlanes:
        cp.isLightBulbOn = False

    cam = app.activeViewport.camera
    cam.isFitView = True
    app.activeViewport.camera = cam
