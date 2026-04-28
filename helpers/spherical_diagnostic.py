"""Diagnostic / non-recommendation module for SphericalTextureMapProjection.

Companion to `helpers/box_diagnostic.py` and `cylindrical_diagnostic.py`.

Empirical finding (Fusion 360, April 2026): SphericalTextureMapProjection
is **not useful** for any wood-furniture body shape we tested. The
projection has two intrinsic problems that no parameter sweep can fix
when the source is a real wood photograph:

  1. Polar pinching. The projection collapses an entire image-Y row to
     a single point at each pole (top and bottom of the texture sphere).
     A wood photo shows a triangular wedge of color radiating from each
     pole. Visible on every sphere as a "hub" with radial streaks,
     however the sphere is oriented.

  2. Equatorial seam. The image-Y top/bottom edges (the longest rows of
     the photo) wrap around the equator of the texture sphere. On a real
     wood photo these edges are unrelated -> a strong horizontal band of
     color discontinuity.

  3. Grain direction is not constant. On a flat wood photo, grain runs
     along image-Y. The spherical mapping turns each "image-Y line" into
     a meridian (pole-to-pole arc), so grain points to the poles - a
     visual signal woodworkers parse as "this object isn't real wood".

Test bodies we ran the projection on:
  - Sphere R=5 cm: pole pinch + equatorial seam visible at every angle.
  - Hemisphere R=5 cm (flat-bottom): pole pinch on top, equatorial seam
    cut at the flat-bottom edge.
  - Bullet (cyl + half-sphere top): cylindrical body gets one wrap of
    the photo (badly distorted), spherical cap pinches at apex.
  - Lathe-turned leg (revolved profile, ~70 cm): user has previously
    rejected this configuration ("looks really bad").

Recommendation: do not use SphericalTextureMapProjection for wood. For
spheres / hemispheres / bullets, prefer Box+grain (period_y = bbox
along grain, period_x = natural cross). The Box projection picks one
of six box-side projections at every surface point - on a sphere this
gives six visible "patches" with a direction transition between them,
but each patch shows correctly-oriented grain and no polar singularity.
For specifically rounded shapes (knobs, finials, drawer pulls), the user
might instead select the rendered shot's camera angle to hide a Box
patch transition along a silhouette edge.

This module exists for two reasons:

  - To provide a diagnostic `apply_spherical_marker()` so a future Fusion
    release with a fixed spherical projection can be re-evaluated using
    the same red/green-stripe oracle as Box.
  - To give a single canonical place to record the rejection reasoning,
    so later runs of this skill don't try Spherical again from scratch.

All units cm unless suffixed _in.
"""
import math
import os


# ---------------------------------------------------------------------
# Pure-math (such as it is)
# ---------------------------------------------------------------------

def recommend_sphere_periods_cm(body_radius_cm, natural_axial_cm,
                                 natural_cross_cm):
    """Return (period_x_cm, period_y_cm) for a spherical body.

    Naive and not validated. Sets period to natural-image dimensions.
    Even the "best" parameter choice produces an unacceptable result -
    see module docstring. Provided so calibrate_sphere() can still set
    SOMETHING for visual inspection.

    period_x = natural axial   (image-X row wraps the sphere meridian)
    period_y = natural cross   (image-Y col wraps the sphere parallel)
    """
    return (natural_cross_cm or 1.0,
            natural_axial_cm or 1.0)


# ---------------------------------------------------------------------
# Diagnostic applier (NOT RECOMMENDED FOR PRODUCTION USE)
# ---------------------------------------------------------------------

def apply_spherical_marker(body, species_key, sp_module,
                            scale_x_cm=None, scale_y_cm=None):
    """Apply SphericalTextureMapProjection with a marker bitmap, for the
    sole purpose of confirming the polar-pinching + equatorial-seam
    failure modes are still present in the current Fusion build.

    On success returns a dict with the configuration; the caller is
    expected to take a screenshot, observe the seam/pinch, and not ship
    this projection mode to users.

    To dispute this diagnosis, run the function on a sphere body, take
    screenshots from top and side, and verify both failure modes are
    visible. If a future Fusion update has fixed them, this module
    should be expanded into a real recipe - and box_diagnostic + the
    Cylindrical module updated to recognize spherical as an option for
    sphere/hemisphere bodies.
    """
    import adsk.core, adsk.fusion
    CM_TO_IN = 1.0 / 2.54
    cfg = sp_module._SPECIES_TEXTURE.get(species_key)
    if not cfg:
        raise ValueError("Unknown species: %s" % species_key)
    natural_axial_cm = sp_module._natural_size_cm(cfg, "y")
    natural_cross_cm = sp_module._natural_size_cm(cfg, "x")
    if scale_x_cm is None or scale_y_cm is None:
        sx, sy = recommend_sphere_periods_cm(
            (body.boundingBox.maxPoint.x - body.boundingBox.minPoint.x) / 2.0,
            natural_axial_cm, natural_cross_cm)
        if scale_x_cm is None:
            scale_x_cm = sx
        if scale_y_cm is None:
            scale_y_cm = sy

    # Marker bitmap (re-uses box_diagnostic - red/green edge stripes).
    try:
        from helpers import box_diagnostic
    except ImportError:
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__))))
        from helpers import box_diagnostic
    src_path = os.path.join(sp_module._TEXTURE_DIR, cfg["texture"])
    marker_path = box_diagnostic.make_marker_image(
        src_path,
        "/tmp/%s_marker.jpg" % species_key.replace(' ', '_'))

    # Per-body local appearance
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    src_app = design.appearances.itemByName("SP_%s" % species_key)
    if src_app is None:
        sp_module.apply_appearance(species_key)
        src_app = design.appearances.itemByName("SP_%s" % species_key)
    local_name = "SP_%s_%s" % (species_key, body.name)
    local = design.appearances.itemByName(local_name)
    if not local and src_app:
        local = design.appearances.addByCopy(src_app, local_name)
    body.appearance = local

    cp = adsk.core.ColorProperty.cast(
        local.appearanceProperties.itemById("opaque_albedo"))
    if cp and cp.hasConnectedTexture:
        tex = cp.connectedTexture
        bp = tex.properties.itemById("unifiedbitmap_Bitmap")
        fp = adsk.core.FilenameProperty.cast(bp)
        if fp and not fp.isReadOnly:
            fp.value = marker_path
        def setf(name, val):
            p = tex.properties.itemById(name)
            if p:
                adsk.core.FloatProperty.cast(p).value = val
        def setb(name, val):
            p = tex.properties.itemById(name)
            if p:
                adsk.core.BooleanProperty.cast(p).value = val
        setb("texture_ScaleLock", False)
        setf("texture_RealWorldScaleX", scale_x_cm * CM_TO_IN)
        setf("texture_RealWorldScaleY", scale_y_cm * CM_TO_IN)
        setf("texture_RealWorldOffsetX", 0.0)
        setf("texture_RealWorldOffsetY", 0.0)
        setf("texture_WAngle", 0.0)

    m = adsk.core.Matrix3D.create()  # identity TMC
    ptmc = adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl)
    if ptmc:
        ptmc.projectedTextureMapType = (
            adsk.core.ProjectedTextureMapTypes.SphericalTextureMapProjection)
        ptmc.transform = m

    return {
        "species": species_key,
        "scale_x_cm": scale_x_cm,
        "scale_y_cm": scale_y_cm,
        "marker_bitmap": marker_path,
        "appearance": local.name if local else None,
        "expected_failures": [
            "polar_pinch_top",
            "polar_pinch_bottom",
            "equatorial_seam",
            "non_uniform_grain_direction",
        ],
    }


def calibrate_sphere(body, species_key, sp_module,
                      screenshot_fn=None, oracle_fn=None):
    """Detect whether spherical projection has stopped being a failure.

    Applies the marker spherical projection and asks `oracle_fn` if any
    of the four expected failures (polar_pinch_top/bottom, equatorial_
    seam, non_uniform_grain) are visible. Returns a dict listing which
    failures persist. If all four come back False, the Fusion behavior
    has changed and this module needs to be promoted from "diagnostic
    only" to a real recipe.
    """
    applied = apply_spherical_marker(body, species_key, sp_module)
    if screenshot_fn is None:
        return {"applied": applied, "failures_observed": None}
    shot = screenshot_fn()
    failures = {}
    if oracle_fn is None:
        return {"applied": applied, "screenshot": shot,
                "failures_observed": "no oracle"}
    for failure in applied["expected_failures"]:
        failures[failure] = bool(oracle_fn(shot, failure))
    applied["screenshot"] = shot
    applied["failures_observed"] = failures
    applied["all_failures_resolved"] = not any(failures.values())
    return applied
