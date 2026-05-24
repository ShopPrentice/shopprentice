import adsk.core
import adsk.fusion
import math

Point3D = adsk.core.Point3D


def _visible_bodies_bbox(root):
    """Compute bounding box of all visible bodies (root + occurrences).

    Returns (min_x, min_y, min_z, max_x, max_y, max_z) in cm.
    """
    min_x = min_y = min_z = 1e10
    max_x = max_y = max_z = -1e10

    for i in range(root.bRepBodies.count):
        b = root.bRepBodies.item(i)
        if not b.isVisible:
            continue
        bb = b.boundingBox
        min_x, min_y, min_z = min(min_x, bb.minPoint.x), min(min_y, bb.minPoint.y), min(min_z, bb.minPoint.z)
        max_x, max_y, max_z = max(max_x, bb.maxPoint.x), max(max_y, bb.maxPoint.y), max(max_z, bb.maxPoint.z)

    for i in range(root.allOccurrences.count):
        occ = root.allOccurrences.item(i)
        if not occ.isLightBulbOn:
            continue
        for j in range(occ.component.bRepBodies.count):
            body = occ.component.bRepBodies.item(j)
            if not body.isVisible:
                continue
            proxy = body.createForAssemblyContext(occ)
            bb = proxy.boundingBox
            min_x, min_y, min_z = min(min_x, bb.minPoint.x), min(min_y, bb.minPoint.y), min(min_z, bb.minPoint.z)
            max_x, max_y, max_z = max(max_x, bb.maxPoint.x), max(max_y, bb.maxPoint.y), max(max_z, bb.maxPoint.z)

    return min_x, min_y, min_z, max_x, max_y, max_z


def _bodies_bbox(bodies):
    """Compute bounding box of a list of BRepBody objects.

    Returns (min_x, min_y, min_z, max_x, max_y, max_z) in cm.
    """
    min_x = min_y = min_z = 1e10
    max_x = max_y = max_z = -1e10
    for b in bodies:
        bb = b.boundingBox
        min_x, min_y, min_z = min(min_x, bb.minPoint.x), min(min_y, bb.minPoint.y), min(min_z, bb.minPoint.z)
        max_x, max_y, max_z = max(max_x, bb.maxPoint.x), max(max_y, bb.maxPoint.y), max(max_z, bb.maxPoint.z)
    return min_x, min_y, min_z, max_x, max_y, max_z


def screenshot_cam(eye_dir, bodies=None, fill=0.80):
    """Position camera for a screenshot with dynamic zoom.

    Computes the bounding box of the target bodies, projects all 8 corners
    onto the camera's view plane, and sets the camera distance so the subject
    fills `fill` fraction of the frame. Uses perspective projection with
    the actual Fusion FOV.

    Args:
        eye_dir: (x, y, z) tuple — camera direction from target.
            Standard shots: iso-top-left (-1,-1,0.7), iso-top-right (1,-1,0.7),
            front (0,-1,0), right (1,0,0).
        bodies: List of BRepBody objects to frame. If None, frames all
            visible bodies. For detail views, pass only the bodies
            involved in the joint or feature being documented — the
            camera will zoom to their bounding box.
        fill: Fraction of frame the subject should fill (0.0-1.0).
            Default 0.80 (80%). Use ~0.90 for tight detail shots,
            ~0.70 for overview shots with more breathing room.

    Returns:
        dict with 'dist', 'center', 'bbox' for diagnostics.
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    vp = app.activeViewport

    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.isFitView = True
    vp.camera = cam
    adsk.doEvents()

    actual_fov = vp.camera.perspectiveAngle

    if bodies is not None:
        min_x, min_y, min_z, max_x, max_y, max_z = _bodies_bbox(bodies)
    else:
        min_x, min_y, min_z, max_x, max_y, max_z = _visible_bodies_bbox(root)

    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    cz = (min_z + max_z) / 2

    ex, ey, ez = eye_dir
    emag = math.sqrt(ex * ex + ey * ey + ez * ez)
    ex, ey, ez = ex / emag, ey / emag, ez / emag

    rx, ry, rz = ey * 1 - ez * 0, ez * 0 - ex * 1, ex * 0 - ey * 0
    rmag = math.sqrt(rx * rx + ry * ry + rz * rz)
    rx, ry, rz = rx / rmag, ry / rmag, rz / rmag
    ux = ry * ez - rz * ey
    uy = rz * ex - rx * ez
    uz = rx * ey - ry * ex

    max_r = max_u = 0
    for x in [min_x - cx, max_x - cx]:
        for y in [min_y - cy, max_y - cy]:
            for z in [min_z - cz, max_z - cz]:
                max_r = max(max_r, abs(x * rx + y * ry + z * rz))
                max_u = max(max_u, abs(x * ux + y * uy + z * uz))

    half_fov = actual_fov / 2
    dist = max(max_r, max_u) / (math.tan(half_fov) * fill)

    diag = math.sqrt((max_x - min_x) ** 2 + (max_y - min_y) ** 2
                     + (max_z - min_z) ** 2)
    min_dist = (diag / 2) / (math.tan(half_fov) * fill) * 0.75
    dist = max(dist, min_dist)

    cam = vp.camera
    cam.isFitView = False
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.target = Point3D.create(cx, cy, cz)
    cam.eye = Point3D.create(cx + ex * dist, cy + ey * dist, cz + ez * dist)
    cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
    vp.camera = cam

    return {
        "dist": dist,
        "center": (cx, cy, cz),
        "bbox": (min_x, min_y, min_z, max_x, max_y, max_z),
    }
