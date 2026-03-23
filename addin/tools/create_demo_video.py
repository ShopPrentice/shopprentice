"""
Create Demo Video Tool

Generates a demo video by capturing frame sequences:
1. Orbit — camera rotates around the model
2. Pull drawers out (if present)
3. Transition to transparent mode
4. Orbit — transparent flyaround showing internals
5. Transition back to opaque
6. Push drawers back in
7. Final orbit
Stitches frames into MP4 via FFmpeg.
"""

import math
import os
import subprocess
import tempfile
import traceback
from primitives.tool import Tool
from primitives.item import Item
from primitives.registry import register
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()
P3 = adsk.core.Point3D


def _model_center_and_radius(root):
    """Compute center and radius of all visible bodies."""
    min_x = min_y = min_z = 1e10
    max_x = max_y = max_z = -1e10
    for occ in root.allOccurrences:
        for i in range(occ.component.bRepBodies.count):
            b = occ.component.bRepBodies.item(i)
            if not b.isVisible:
                continue
            proxy = b.createForAssemblyContext(occ)
            bb = proxy.boundingBox
            if bb:
                min_x = min(min_x, bb.minPoint.x)
                min_y = min(min_y, bb.minPoint.y)
                min_z = min(min_z, bb.minPoint.z)
                max_x = max(max_x, bb.maxPoint.x)
                max_y = max(max_y, bb.maxPoint.y)
                max_z = max(max_z, bb.maxPoint.z)
    for i in range(root.bRepBodies.count):
        b = root.bRepBodies.item(i)
        if not b.isVisible:
            continue
        bb = b.boundingBox
        if bb:
            min_x = min(min_x, bb.minPoint.x)
            min_y = min(min_y, bb.minPoint.y)
            min_z = min(min_z, bb.minPoint.z)
            max_x = max(max_x, bb.maxPoint.x)
            max_y = max(max_y, bb.maxPoint.y)
            max_z = max(max_z, bb.maxPoint.z)
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    cz = (min_z + max_z) / 2
    radius = math.sqrt((max_x - min_x) ** 2 + (max_y - min_y) ** 2
                        + (max_z - min_z) ** 2) / 2
    return cx, cy, cz, radius


def _set_camera(vp, root, angle, elevation, fill=0.70):
    """Position camera at orbit angle, auto-framing the current model state."""
    cx, cy, cz, radius = _model_center_and_radius(root)

    cam = vp.camera
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.isFitView = True
    vp.camera = cam
    adsk.doEvents()
    fov = vp.camera.perspectiveAngle
    dist = radius / (math.tan(fov / 2) * fill)

    ex = cx + dist * math.cos(angle)
    ey = cy + dist * math.sin(angle)
    ez = cz + dist * elevation

    cam = vp.camera
    cam.isFitView = False
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.eye = P3.create(ex, ey, ez)
    cam.target = P3.create(cx, cy, cz)
    cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
    vp.camera = cam


def _ease_in_out(t):
    """Smooth ease-in-out (0→1)."""
    return t * t * (3 - 2 * t)


def _capture(vp, frame_dir, num, w, h):
    """Save one frame."""
    path = os.path.join(frame_dir, f"frame_{num:04d}.png")
    vp.saveAsImageFile(path, w, h)


def handler(output_path: str = "/tmp/demo.mp4",
            width: int = 2560, height: int = 1440,
            fps: int = 30,
            orbit_seconds: float = 3.0,
            drawer_seconds: float = 2.0,
            transparent_orbit_seconds: float = 8.0,
            drawer_pull: float = -1.0,
            elevation: float = 0.4) -> dict:
    """Create demo: orbit → drawer pull → transparent orbit → drawer push → orbit."""

    orig_transforms = []

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {"content": [{"type": "text", "text": "No active design"}],
                    "isError": True, "message": "No active design"}

        root = design.rootComponent
        vp = app.activeViewport

        # Hide construction artifacts
        for occ in root.allOccurrences:
            comp = occ.component
            for sk in comp.sketches:
                sk.isVisible = False
            for cp in comp.constructionPlanes:
                cp.isLightBulbOn = False
            for ca in comp.constructionAxes:
                ca.isLightBulbOn = False
        for sk in root.sketches:
            sk.isVisible = False
        for cp in root.constructionPlanes:
            cp.isLightBulbOn = False

        # Ensure opaque visual style
        vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle

        # Identify drawer components — store index for reliable re-access
        drawer_indices = []
        for i in range(root.occurrences.count):
            occ = root.occurrences.item(i)
            comp_name = occ.component.name.lower()
            if "drawer" in comp_name and occ.isLightBulbOn:
                drawer_indices.append(i)
                orig_transforms.append((i, occ.transform.copy()))
                app.log(f"  Drawer found: {occ.component.name} (index {i})")

        # Auto-calculate drawer pull distance from world-space bounding box
        if drawer_pull < 0 and drawer_indices:
            occ0 = root.occurrences.item(drawer_indices[0])
            d_min_y = 1e10
            d_max_y = -1e10
            for j in range(occ0.component.bRepBodies.count):
                b = occ0.component.bRepBodies.item(j)
                proxy = b.createForAssemblyContext(occ0)
                bb = proxy.boundingBox
                if bb:
                    d_min_y = min(d_min_y, bb.minPoint.y)
                    d_max_y = max(d_max_y, bb.maxPoint.y)
            if d_max_y > d_min_y:
                drawer_pull = (d_max_y - d_min_y) * 0.95
            app.log(f"  Drawer pull distance: {drawer_pull:.2f} cm")

        has_drawers = drawer_pull > 0 and len(drawer_indices) > 0
        app.log(f"  has_drawers={has_drawers}, count={len(drawer_indices)}, pull={drawer_pull:.2f}")

        # Frame counts
        orbit1 = int(orbit_seconds * fps)
        drawer_out = int(drawer_seconds * fps) if has_drawers else 0
        trans_orbit = int(transparent_orbit_seconds * fps)
        drawer_in = int(drawer_seconds * fps) if has_drawers else 0
        orbit2 = int(orbit_seconds * fps)
        total = orbit1 + drawer_out + trans_orbit + drawer_in + orbit2

        frame_dir = tempfile.mkdtemp(prefix="shopprentice_video_")
        n = 0
        angle = 0.0

        app.log(f"Demo video: {total} frames, {total/fps:.1f}s")

        # === Phase 1: Opening orbit (opaque) ===
        for i in range(orbit1):
            angle = (i / orbit1) * math.pi * 0.8  # ~144° rotation
            _set_camera(vp, root, angle, elevation)
            adsk.doEvents()
            _capture(vp, frame_dir, n, width, height)
            n += 1
        last_angle = angle

        # === Phase 2: Pull drawers out ===
        if has_drawers:
            for i in range(drawer_out):
                t = _ease_in_out(i / max(drawer_out - 1, 1))
                for idx in drawer_indices:
                    occ = root.occurrences.item(idx)
                    # Find original transform by index
                    orig_t = None
                    for stored_idx, ot in orig_transforms:
                        if stored_idx == idx:
                            orig_t = ot
                            break
                    if orig_t is None:
                        continue
                    new_t = orig_t.copy()
                    tr = adsk.core.Matrix3D.create()
                    tr.translation = adsk.core.Vector3D.create(0, -drawer_pull * t, 0)
                    new_t.transformBy(tr)
                    occ.transform = new_t
                # Slow orbit during drawer pull
                last_angle += 0.3 / drawer_out
                _set_camera(vp, root, last_angle, elevation)
                adsk.doEvents()
                _capture(vp, frame_dir, n, width, height)
                n += 1

        # === Phase 3: Transition to transparent + orbit ===
        vp.visualStyle = adsk.core.VisualStyles.ShadedWithHiddenEdgesVisualStyle
        adsk.doEvents()

        for i in range(trans_orbit):
            last_angle += (math.pi * 1.5) / trans_orbit  # 270° rotation (slower)
            _set_camera(vp, root, last_angle, elevation)
            adsk.doEvents()
            _capture(vp, frame_dir, n, width, height)
            n += 1

        # === Phase 4: Back to opaque + push drawers in ===
        vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
        adsk.doEvents()

        if has_drawers:
            for i in range(drawer_in):
                t = _ease_in_out(1.0 - i / max(drawer_in - 1, 1))
                for idx in drawer_indices:
                    occ = root.occurrences.item(idx)
                    orig_t = None
                    for stored_idx, ot in orig_transforms:
                        if stored_idx == idx:
                            orig_t = ot
                            break
                    if orig_t is None:
                        continue
                    new_t = orig_t.copy()
                    tr = adsk.core.Matrix3D.create()
                    tr.translation = adsk.core.Vector3D.create(0, -drawer_pull * t, 0)
                    new_t.transformBy(tr)
                    occ.transform = new_t
                last_angle += 0.3 / drawer_in
                _set_camera(vp, root, last_angle, elevation)
                adsk.doEvents()
                _capture(vp, frame_dir, n, width, height)
                n += 1

        # === Phase 5: Closing orbit ===
        for i in range(orbit2):
            last_angle += (math.pi * 0.5) / orbit2  # ~90° more
            _set_camera(vp, root, last_angle, elevation)
            adsk.doEvents()
            _capture(vp, frame_dir, n, width, height)
            n += 1

        # Restore
        for idx, orig_t in orig_transforms:
            root.occurrences.item(idx).transform = orig_t
        adsk.doEvents()
        vp.visualStyle = adsk.core.VisualStyles.ShadedWithVisibleEdgesOnlyVisualStyle
        cam = vp.camera
        cam.isFitView = True
        vp.camera = cam

        app.log(f"Captured {n} frames")

        # === FFmpeg ===
        ffmpeg_bin = "ffmpeg"
        for p in ["/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/bin/ffmpeg"]:
            if os.path.exists(p):
                ffmpeg_bin = p
                break

        ffmpeg_cmd = [
            ffmpeg_bin, "-y",
            "-framerate", str(fps),
            "-i", os.path.join(frame_dir, "frame_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            output_path
        ]
        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return {"content": [{"type": "text", "text": f"FFmpeg failed: {result.stderr[:500]}"}],
                        "isError": True, "message": "FFmpeg failed"}
        except FileNotFoundError:
            return {"content": [{"type": "text", "text":
                f"{n} frames saved to: {frame_dir}\n"
                f"ffmpeg -framerate {fps} -i {frame_dir}/frame_%04d.png "
                f"-c:v libx264 -pix_fmt yuv420p {output_path}"}],
                "isError": False, "message": f"{n} frames (FFmpeg not found)"}

        # Cleanup frames
        for f in os.listdir(frame_dir):
            os.unlink(os.path.join(frame_dir, f))
        os.rmdir(frame_dir)

        sz = os.path.getsize(output_path)
        return {"content": [{"type": "text", "text":
            f"Video: {output_path} ({sz // 1024}KB, {n} frames, {n / fps:.1f}s)\n"
            f"Sequence: orbit → drawer pull → transparent orbit → drawer push → orbit"}],
            "isError": False, "message": f"Demo video: {output_path}"}

    except Exception as e:
        try:
            for occ, orig_t in orig_transforms:
                occ.transform = orig_t
            adsk.doEvents()
            app.activeViewport.visualStyle = adsk.core.VisualStyles.ShadedVisualStyle
        except Exception:
            pass
        app.log(f"create_demo_video error: {e}\n{traceback.format_exc()}")
        return {"content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
                "isError": True, "message": "create_demo_video failed"}


TOOL_DESCRIPTION = \
"""Create a demo video of the current model.

Sequence: orbit → pull drawers out → transparent flyaround → push drawers back → orbit.

Drawer components (names containing 'Drawer') are automatically detected and
slid out. Set drawer_pull=-1 to auto-calculate distance from drawer depth.

Default: 2560x1440, 30fps, ~15 seconds."""

tool = Tool.create_simple(
    name="create_demo_video",
    description=TOOL_DESCRIPTION
).add_input_property(
    "output_path", {"type": "string", "default": "/tmp/demo.mp4",
        "description": "Output video file path."}
).add_input_property(
    "width", {"type": "integer", "default": 2560,
        "description": "Frame width in pixels."}
).add_input_property(
    "height", {"type": "integer", "default": 1440,
        "description": "Frame height in pixels."}
).add_input_property(
    "fps", {"type": "integer", "default": 30,
        "description": "Frames per second."}
).add_input_property(
    "orbit_seconds", {"type": "number", "default": 3.0,
        "description": "Duration of each orbit phase."}
).add_input_property(
    "drawer_seconds", {"type": "number", "default": 2.0,
        "description": "Duration of drawer pull/push."}
).add_input_property(
    "transparent_orbit_seconds", {"type": "number", "default": 8.0,
        "description": "Duration of transparent flyaround."}
).add_input_property(
    "drawer_pull", {"type": "number", "default": -1.0,
        "description": "Drawer slide distance in cm. -1=auto, 0=skip."}
).add_input_property(
    "elevation", {"type": "number", "default": 0.4,
        "description": "Camera elevation (0=level, 1=high)."}
)

item = Item.create_tool_item(tool=tool, handler=handler)
register(item)
