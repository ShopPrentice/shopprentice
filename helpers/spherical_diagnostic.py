"""Reliable helpers for SphericalTextureMapProjection on parametric bodies.

Companion to `helpers/box_diagnostic.py` and `cylindrical_diagnostic.py`.

Empirical finding (Fusion 360, April 2026 — refined twice): Spherical
projection works ONLY for bodies whose shape is close to a sphere
(aspect ≈ 1) or has a geometric pinch point that hides the projection's
polar singularity (e.g. a cone tapering to a tip). For other curved
revolved bodies (cylinders, ellipsoids, hemispheres, bullets, squat
disks), the polar pinching surface artifact persists at every value
of `pole_clearance_factor` because Fusion's spherical projection maps
image-Y to LATITUDE ANGLE, not meridian arc length — so increasing
scale_y just relocates pinch stripes, never eliminates them.

Recipe (for sphere-like bodies only):

    scale_x  = body_circumference                       # one azimuthal wrap
    scale_y  = body_axial_extent × N    where N >= 3    # default 3
    offset_x = scale_x / 2                              # azimuthal seam to back
    offset_y = scale_y / 2                              # body centered on equator
    TMC translate = body bbox center
    Projection axis = body's long axis

Body shape → recommended projection:

  | Shape                                | Projection      |
  |--------------------------------------|-----------------|
  | Sphere (aspect ≈ 1)                  | Spherical, N=3 |
  | Cone (tapers to a tip)               | Spherical, N=5 |
  | Cylinder (any aspect)                | Cylindrical     |
  | Hemisphere / bullet / ellipsoid      | Box+grain       |
  | Squat disk (radius > axial)          | Box+grain       |

`is_body_sphere_like(axial, radius)` returns True iff the body's aspect
ratio (axial / 2·radius) is within ±15% of 1 — the empirical heuristic
for Spherical reliability.

`apply_spherical_recipe()` accepts a `warn_if_not_sphere_like` flag
(default True) which prints a warning when the heuristic fails.

This module mirrors the shape of `box_diagnostic.py` and
`cylindrical_diagnostic.py`:

  - Pure-math recipe calculation (`recommend_spherical_periods_cm`).
  - Sphere-shape heuristic (`is_body_sphere_like`).
  - Marker-image generation (delegates to box_diagnostic).
  - High-level applier (`apply_spherical_recipe`).
  - Calibration sweep (`calibrate_pole_clearance`) for re-deriving the
    minimum N if Fusion changes behavior.
"""
import math
import os


# ─────────────────────────────────────────────────────────────────────
# Pure-math rules
# ─────────────────────────────────────────────────────────────────────

def recommend_spherical_periods_cm(body_axial_cm, body_radius_cm,
                                     pole_clearance_factor=3.0,
                                     azimuthal_seam_offset_fraction=0.5):
    """Return (scale_x_cm, scale_y_cm, offset_x_cm, offset_y_cm, rule_used).

    `pole_clearance_factor` (N) controls how far each pole sits from
    the body. N >= 5 is reliably seam-free across body shapes tested;
    smaller N leaves polar pinching visible at the body's axial ends.

    `azimuthal_seam_offset_fraction` controls where the one inevitable
    image-X wrap-around lands around the body. 0.5 puts it at the back
    (180° from the texture origin). Set to 0.0 if you want the seam at
    the front (e.g. for testing).
    """
    if body_axial_cm <= 0 or body_radius_cm <= 0:
        return 0.0, 0.0, 0.0, 0.0, "invalid input"
    circumference = 2.0 * math.pi * body_radius_cm
    scale_x_cm = circumference                                  # one wrap around
    scale_y_cm = body_axial_cm * pole_clearance_factor
    offset_x_cm = scale_x_cm * azimuthal_seam_offset_fraction
    offset_y_cm = scale_y_cm / 2.0                               # center on equator
    return (scale_x_cm, scale_y_cm, offset_x_cm, offset_y_cm,
            f"equatorial band, N={pole_clearance_factor}")


def is_body_sphere_like(body_axial_cm, body_radius_cm, aspect_tolerance=0.15):
    """Heuristic: True if the body's aspect ratio (axial / 2·radius) is
    within ±aspect_tolerance of 1.0. Spherical projection is reliable for
    sphere-like bodies and unreliable for everything else (use Cylindrical
    or Box+grain instead — see module docstring)."""
    if body_radius_cm <= 0 or body_axial_cm <= 0:
        return False
    aspect = body_axial_cm / (2.0 * body_radius_cm)
    return abs(aspect - 1.0) <= aspect_tolerance


def analytical_pole_distance_cm(body_axial_cm, scale_y_cm):
    """How far past the body's axial end does each pole sit (cm)?

    Returns the polar clearance — the distance from the body's axial
    boundary to the nearest pole on the projection sphere. Negative
    means the pole is on or inside the body (= polar pinching visible).
    Positive >= 0 means clean.

    With scale_y_cm = body_axial_cm × N: clearance = body_axial × (N-1) / 2.
    """
    return (scale_y_cm - body_axial_cm) / 2.0


# ─────────────────────────────────────────────────────────────────────
# Marker generation (delegates to box_diagnostic)
# ─────────────────────────────────────────────────────────────────────

def make_marker_image(*args, **kwargs):
    """Re-export of box_diagnostic.make_marker_image for convenience."""
    from helpers import box_diagnostic
    return box_diagnostic.make_marker_image(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────
# Applier — equatorial-band recipe
# ─────────────────────────────────────────────────────────────────────

def apply_spherical_recipe(body, species_key, sp_module,
                            pole_clearance_factor=3.0,
                            projection_axis_idx=None,
                            warn_if_not_sphere_like=True):
    """Apply the equatorial-band Spherical recipe to a body.

    Args:
        body: BRepBody. Should be a sphere, cylinder, hemisphere, or
            similar revolved body. The "axial extent" is the body's
            extent along its long axis; the "radius" is half the
            largest cross-section.
        species_key: key into sp_module._SPECIES_TEXTURE.
        sp_module: imported helpers.sp.
        pole_clearance_factor: N. scale_y = body_axial × N. Default 5.
        projection_axis_idx: 0=X, 1=Y, 2=Z. If None, picks the body's
            longest bbox axis.

    Returns dict with applied state (scale_x_cm, scale_y_cm,
    offset_x/y_cm, projection_axis, pole_distance_cm).
    """
    import adsk.core, adsk.fusion
    bb = body.boundingBox
    spans = (bb.maxPoint.x - bb.minPoint.x,
             bb.maxPoint.y - bb.minPoint.y,
             bb.maxPoint.z - bb.minPoint.z)
    if projection_axis_idx is None:
        projection_axis_idx = spans.index(max(spans))
    body_axial_cm = spans[projection_axis_idx]
    body_radius_cm = max(s for i, s in enumerate(spans)
                          if i != projection_axis_idx) / 2.0
    sphere_like = is_body_sphere_like(body_axial_cm, body_radius_cm)
    if warn_if_not_sphere_like and not sphere_like:
        aspect = body_axial_cm / (2.0 * body_radius_cm)
        print(f"WARN apply_spherical_recipe: '{body.name}' aspect "
              f"{aspect:.2f} is not sphere-like (≈1.00 ±0.15); "
              f"expect polar pinching. Use Cylindrical or Box+grain.")
    sx, sy, ox, oy, rule = recommend_spherical_periods_cm(
        body_axial_cm, body_radius_cm, pole_clearance_factor)
    cm_to_in = 1.0 / 2.54
    cx = (bb.minPoint.x + bb.maxPoint.x) / 2.0
    cy = (bb.minPoint.y + bb.maxPoint.y) / 2.0
    cz = (bb.minPoint.z + bb.maxPoint.z) / 2.0
    # Per-body appearance via sp.per_body_appearance -- safe, never touches
    # a shared SP_<species> appearance. Spherical uses a _sph suffix by
    # convention, but per_body_appearance uses body.name directly; we call
    # it and then rename the convention note here for reference.
    local = sp_module.per_body_appearance(body, species_key)
    cp = adsk.core.ColorProperty.cast(
        local.appearanceProperties.itemById("opaque_albedo"))
    if cp and cp.hasConnectedTexture:
        tex = cp.connectedTexture
        for prop, val in (
            ("texture_RealWorldScaleX", sx * cm_to_in),
            ("texture_RealWorldScaleY", sy * cm_to_in),
            ("texture_RealWorldOffsetX", ox * cm_to_in),
            ("texture_RealWorldOffsetY", oy * cm_to_in),
            ("texture_WAngle", 0.0),
        ):
            p = tex.properties.itemById(prop)
            v = adsk.core.FloatProperty.cast(p) if p else None
            if v: v.value = val
    body.appearance = local
    # TMC: rotation aligning texture-local +Z to projection axis, translate
    # to body center.
    m = adsk.core.Matrix3D.create()
    if projection_axis_idx == 0:    # +X
        m.setToRotation(math.pi / 2,
                         adsk.core.Vector3D.create(0, 1, 0),
                         adsk.core.Point3D.create(0, 0, 0))
    elif projection_axis_idx == 1:  # +Y
        m.setToRotation(-math.pi / 2,
                         adsk.core.Vector3D.create(1, 0, 0),
                         adsk.core.Point3D.create(0, 0, 0))
    # axis 2 (Z): identity
    m.setCell(0, 3, cx)
    m.setCell(1, 3, cy)
    m.setCell(2, 3, cz)
    ptmc = adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl)
    if ptmc:
        ptmc.projectedTextureMapType = (
            adsk.core.ProjectedTextureMapTypes.SphericalTextureMapProjection)
        ptmc.transform = m
    return {
        "species": species_key,
        "appearance": local.name,
        "projection_axis": "xyz"[projection_axis_idx],
        "body_axial_cm": body_axial_cm,
        "body_radius_cm": body_radius_cm,
        "sphere_like": sphere_like,
        "scale_x_cm": sx,
        "scale_y_cm": sy,
        "offset_x_cm": ox,
        "offset_y_cm": oy,
        "pole_distance_cm": analytical_pole_distance_cm(body_axial_cm, sy),
        "rule_used": rule,
    }


# ─────────────────────────────────────────────────────────────────────
# Calibration — re-derive min pole-clearance factor after Fusion changes
# ─────────────────────────────────────────────────────────────────────

def calibrate_pole_clearance(body, species_key, sp_module,
                              n_candidates=(2.0, 3.0, 4.0, 5.0, 7.0, 10.0),
                              screenshot_fn=None, oracle_fn=None,
                              marker_dir="/tmp"):
    """Sweep `pole_clearance_factor` (N) ascending and return the smallest
    value that's seam-free per `oracle_fn(image, N)`.

    Mirrors box_diagnostic.calibrate_seam_buffer's contract: applies marker
    bitmap, screenshots at each N, restores original bitmap on cleanup.
    """
    import adsk.core, adsk.fusion
    cfg = sp_module._SPECIES_TEXTURE.get(species_key) or {}
    src_path = os.path.join(sp_module._TEXTURE_DIR, cfg.get("texture", ""))
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"Texture not found: {src_path}")
    marker_path = make_marker_image(
        src_path,
        os.path.join(marker_dir, f"{species_key.replace(' ','_')}_sph_marker.jpg"))
    results = {"min_seam_free_N": None, "screenshots": {},
               "analytical_results": {}, "scratch_appearances": []}
    orig_appearance = body.appearance
    scratch_state = []
    try:
        for N in n_candidates:
            applied = apply_spherical_recipe(body, species_key, sp_module,
                                              pole_clearance_factor=N)
            results["analytical_results"][N] = applied
            ap = body.appearance
            cp = adsk.core.ColorProperty.cast(
                ap.appearanceProperties.itemById("opaque_albedo"))
            orig_bitmap = None
            if cp and cp.hasConnectedTexture:
                tex = cp.connectedTexture
                bp = tex.properties.itemById("unifiedbitmap_Bitmap")
                fp = adsk.core.FilenameProperty.cast(bp)
                if fp and not fp.isReadOnly:
                    orig_bitmap = fp.value
                    fp.value = marker_path
            if not any(s[0] is ap for s in scratch_state):
                scratch_state.append((ap, orig_bitmap))
                results["scratch_appearances"].append(ap.name)
            if screenshot_fn is not None:
                shot = screenshot_fn()
                results["screenshots"][N] = shot
                if oracle_fn is not None and oracle_fn(shot, N):
                    results["min_seam_free_N"] = N
                    break
    finally:
        for ap, orig_bitmap in scratch_state:
            if orig_bitmap:
                cp = adsk.core.ColorProperty.cast(
                    ap.appearanceProperties.itemById("opaque_albedo"))
                if cp and cp.hasConnectedTexture:
                    tex = cp.connectedTexture
                    bp = tex.properties.itemById("unifiedbitmap_Bitmap")
                    fp = adsk.core.FilenameProperty.cast(bp)
                    if fp and not fp.isReadOnly:
                        fp.value = orig_bitmap
        try:
            body.appearance = orig_appearance
        except Exception:
            pass
    return results
