"""
Create Demo Video Tool

Generates a demo video of the current model by capturing frame sequences:
1. Orbit — camera rotates around the model
2. Explode — components move outward from center
3. Reassemble — components move back
4. Stitch frames into MP4 via FFmpeg
"""

import math
import os
import subprocess
import tempfile
import time
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

    def _walk(comp, transform=None):
        nonlocal min_x, min_y, min_z, max_x, max_y, max_z
        for i in range(comp.bRepBodies.count):
            b = comp.bRepBodies.item(i)
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

    _walk(root)
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

    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    cz = (min_z + max_z) / 2
    radius = math.sqrt((max_x - min_x) ** 2 + (max_y - min_y) ** 2
                        + (max_z - min_z) ** 2) / 2
    return cx, cy, cz, radius


def _set_camera(vp, eye_x, eye_y, eye_z, cx, cy, cz):
    """Set camera position looking at center."""
    cam = vp.camera
    cam.isFitView = False
    cam.cameraType = adsk.core.CameraTypes.PerspectiveCameraType
    cam.eye = P3.create(eye_x, eye_y, eye_z)
    cam.target = P3.create(cx, cy, cz)
    cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
    vp.camera = cam


def _capture_frame(vp, frame_dir, frame_num, width, height):
    """Save one frame."""
    path = os.path.join(frame_dir, f"frame_{frame_num:04d}.png")
    vp.saveAsImageFile(path, width, height)
    return path


def _get_component_centers(root):
    """Get each top-level occurrence's bounding box center (for explode).

    Returns list of (occurrence, (cx, cy, cz)) tuples.
    Uses list instead of dict — Fusion Occurrence objects aren't hashable.
    """
    results = []
    for i in range(root.occurrences.count):
        occ = root.occurrences.item(i)
        if not occ.isLightBulbOn:
            continue
        min_x = min_y = min_z = 1e10
        max_x = max_y = max_z = -1e10
        has_bodies = False
        for j in range(occ.component.bRepBodies.count):
            b = occ.component.bRepBodies.item(j)
            proxy = b.createForAssemblyContext(occ)
            bb = proxy.boundingBox
            if bb:
                has_bodies = True
                min_x = min(min_x, bb.minPoint.x)
                min_y = min(min_y, bb.minPoint.y)
                min_z = min(min_z, bb.minPoint.z)
                max_x = max(max_x, bb.maxPoint.x)
                max_y = max(max_y, bb.maxPoint.y)
                max_z = max(max_z, bb.maxPoint.z)
        if has_bodies:
            results.append((occ, (
                (min_x + max_x) / 2,
                (min_y + max_y) / 2,
                (min_z + max_z) / 2,
            )))
    return results


def _ease_in_out(t):
    """Smooth ease-in-out curve (0→1)."""
    return t * t * (3 - 2 * t)


def handler(output_path: str = "/tmp/demo.mp4",
            width: int = 1920, height: int = 1080,
            fps: int = 30,
            orbit_seconds: float = 3.0,
            explode_seconds: float = 1.5,
            hold_seconds: float = 1.0,
            explode_factor: float = 0.5,
            elevation: float = 0.4) -> dict:
    """Create a demo video: orbit → explode → hold → reassemble → orbit."""

    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return {
                "content": [{"type": "text", "text": "No active design"}],
                "isError": True,
                "message": "No active design"
            }

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

        # Model center and camera distance
        cx, cy, cz, radius = _model_center_and_radius(root)
        cam_dist = radius * 3.0  # camera distance from center

        # Frame counts
        orbit_frames = int(orbit_seconds * fps)
        explode_frames = int(explode_seconds * fps)
        hold_frames = int(hold_seconds * fps)

        # Component centers for explode — list of (occ, (cx, cy, cz))
        comp_centers = _get_component_centers(root)
        orig_transforms = []  # list of (occ, orig_transform)
        for occ, _ in comp_centers:
            orig_transforms.append((occ, occ.transform.copy()))

        # Temp directory for frames
        frame_dir = tempfile.mkdtemp(prefix="autofusion_video_")
        frame_num = 0
        total_frames = orbit_frames + explode_frames + hold_frames + explode_frames + orbit_frames

        app.log(f"Creating demo video: {total_frames} frames at {fps}fps")

        # === Phase 1: Initial orbit (half rotation) ===
        for i in range(orbit_frames):
            angle = (i / orbit_frames) * math.pi  # 0 to π
            ex = cx + cam_dist * math.cos(angle)
            ey = cy + cam_dist * math.sin(angle)
            ez = cz + cam_dist * elevation
            _set_camera(vp, ex, ey, ez, cx, cy, cz)
            adsk.doEvents()
            _capture_frame(vp, frame_dir, frame_num, width, height)
            frame_num += 1

        # === Phase 2: Explode ===
        for i in range(explode_frames):
            t = _ease_in_out(i / max(explode_frames - 1, 1))
            # Move each component outward from model center
            for occ, (ocx, ocy, ocz) in comp_centers:
                dx = (ocx - cx) * explode_factor * t
                dy = (ocy - cy) * explode_factor * t
                dz = (ocz - cz) * explode_factor * t
                # Find original transform for this occurrence
                orig_t = None
                for o, ot in orig_transforms:
                    if o.name == occ.name:
                        orig_t = ot
                        break
                if orig_t is None:
                    continue
                new_t = orig_t.copy()
                trans = adsk.core.Matrix3D.create()
                trans.translation = adsk.core.Vector3D.create(dx, dy, dz)
                new_t.transformBy(trans)
                occ.transform = new_t
            adsk.doEvents()
            # Keep camera at last orbit position
            _capture_frame(vp, frame_dir, frame_num, width, height)
            frame_num += 1

        # === Phase 3: Hold exploded view ===
        for i in range(hold_frames):
            _capture_frame(vp, frame_dir, frame_num, width, height)
            frame_num += 1

        # === Phase 4: Reassemble ===
        for i in range(explode_frames):
            t = _ease_in_out(1.0 - i / max(explode_frames - 1, 1))
            for occ, (ocx, ocy, ocz) in comp_centers:
                dx = (ocx - cx) * explode_factor * t
                dy = (ocy - cy) * explode_factor * t
                dz = (ocz - cz) * explode_factor * t
                # Find original transform for this occurrence
                orig_t = None
                for o, ot in orig_transforms:
                    if o.name == occ.name:
                        orig_t = ot
                        break
                if orig_t is None:
                    continue
                new_t = orig_t.copy()
                trans = adsk.core.Matrix3D.create()
                trans.translation = adsk.core.Vector3D.create(dx, dy, dz)
                new_t.transformBy(trans)
                occ.transform = new_t
            adsk.doEvents()
            _capture_frame(vp, frame_dir, frame_num, width, height)
            frame_num += 1

        # === Phase 5: Final orbit (second half rotation) ===
        for i in range(orbit_frames):
            angle = math.pi + (i / orbit_frames) * math.pi  # π to 2π
            ex = cx + cam_dist * math.cos(angle)
            ey = cy + cam_dist * math.sin(angle)
            ez = cz + cam_dist * elevation
            _set_camera(vp, ex, ey, ez, cx, cy, cz)
            adsk.doEvents()
            _capture_frame(vp, frame_dir, frame_num, width, height)
            frame_num += 1

        # Restore original transforms
        for occ, orig_t in orig_transforms:
            occ.transform = orig_t
        adsk.doEvents()

        # Restore camera
        cam = vp.camera
        cam.isFitView = True
        vp.camera = cam

        app.log(f"Captured {frame_num} frames to {frame_dir}")

        # === Stitch with FFmpeg ===
        # Try common FFmpeg paths (Fusion's Python env may not have it in PATH)
        ffmpeg_bin = "ffmpeg"
        for p in ["/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg",
                   "/usr/bin/ffmpeg"]:
            if os.path.exists(p):
                ffmpeg_bin = p
                break

        ffmpeg_cmd = [
            ffmpeg_bin, "-y",
            "-framerate", str(fps),
            "-i", os.path.join(frame_dir, "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",  # high quality
            output_path
        ]

        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True,
                                     timeout=60)
            if result.returncode != 0:
                return {
                    "content": [{"type": "text", "text":
                        f"FFmpeg failed: {result.stderr[:500]}"}],
                    "isError": True,
                    "message": "FFmpeg encoding failed"
                }
        except FileNotFoundError:
            # FFmpeg not installed — return frame directory instead
            return {
                "content": [{"type": "text", "text":
                    f"FFmpeg not found. {frame_num} frames saved to: {frame_dir}\n"
                    f"Run manually: ffmpeg -framerate {fps} -i {frame_dir}/frame_%04d.png "
                    f"-c:v libx264 -pix_fmt yuv420p {output_path}"}],
                "isError": False,
                "message": f"{frame_num} frames captured (FFmpeg not found)"
            }

        # Cleanup frames
        for f in os.listdir(frame_dir):
            os.unlink(os.path.join(frame_dir, f))
        os.rmdir(frame_dir)

        file_size = os.path.getsize(output_path)
        return {
            "content": [{"type": "text", "text":
                f"Video saved: {output_path} ({file_size // 1024}KB, "
                f"{frame_num} frames, {frame_num / fps:.1f}s at {fps}fps)\n"
                f"Sequence: orbit({orbit_seconds}s) → explode({explode_seconds}s) → "
                f"hold({hold_seconds}s) → reassemble({explode_seconds}s) → "
                f"orbit({orbit_seconds}s)"}],
            "isError": False,
            "message": f"Demo video created: {output_path}"
        }

    except Exception as e:
        # Restore transforms on error
        try:
            for occ, orig_t in orig_transforms:
                occ.transform = orig_t
            adsk.doEvents()
        except Exception:
            pass
        app.log(f"create_demo_video error: {e}\n{traceback.format_exc()}")
        return {
            "content": [{"type": "text", "text": f"Error: {e}\n{traceback.format_exc()}"}],
            "isError": True,
            "message": "create_demo_video failed"
        }


TOOL_DESCRIPTION = \
"""Create a demo video of the current model.

Captures frame sequences with camera orbit and exploded view animation:
1. Orbit — camera rotates around the model (first half)
2. Explode — components move outward from center (ease-in-out)
3. Hold — pause on exploded view
4. Reassemble — components return to position
5. Orbit — camera completes rotation (second half)

Frames are stitched into MP4 via FFmpeg. If FFmpeg is not installed,
raw frames are saved and the FFmpeg command is provided.

Default: 1920x1080, 30fps, ~10 seconds total."""

tool = Tool.create_simple(
    name="create_demo_video",
    description=TOOL_DESCRIPTION
).add_input_property(
    "output_path",
    {
        "description": "Output video file path. Default: /tmp/demo.mp4",
        "type": "string",
        "default": "/tmp/demo.mp4"
    }
).add_input_property(
    "width",
    {
        "description": "Frame width in pixels.",
        "type": "integer",
        "default": 1920
    }
).add_input_property(
    "height",
    {
        "description": "Frame height in pixels.",
        "type": "integer",
        "default": 1080
    }
).add_input_property(
    "fps",
    {
        "description": "Frames per second.",
        "type": "integer",
        "default": 30
    }
).add_input_property(
    "orbit_seconds",
    {
        "description": "Duration of each orbit phase in seconds.",
        "type": "number",
        "default": 3.0
    }
).add_input_property(
    "explode_seconds",
    {
        "description": "Duration of explode/reassemble animation.",
        "type": "number",
        "default": 1.5
    }
).add_input_property(
    "hold_seconds",
    {
        "description": "Duration to hold the exploded view.",
        "type": "number",
        "default": 1.0
    }
).add_input_property(
    "explode_factor",
    {
        "description": "How far to explode (fraction of component offset from center). Default 0.5.",
        "type": "number",
        "default": 0.5
    }
).add_input_property(
    "elevation",
    {
        "description": "Camera elevation factor (0=level, 1=high). Default 0.4.",
        "type": "number",
        "default": 0.4
    }
)

item = Item.create_tool_item(
    tool=tool,
    handler=handler
)

register(item)
