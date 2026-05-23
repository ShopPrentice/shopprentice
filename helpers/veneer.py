"""
apply_veneer — Seam-free photo texture mapping for Fusion 360 bodies.

Maps a photo texture (e.g. spalted maple veneer) onto one or more bodies
with no visible tile seams, continuous grain across all bodies, and correct
handling of the Box projection -Z face offset.

Scale-to-Period Relationship (empirically determined):
    Fusion 360's texture_RealWorldScaleX/Y properties are stored in INCHES.
    The visible texture period (tile repeat distance) is exactly HALF the
    scale property value:

        period_inches = texture_RealWorldScale_inches / 2

    Therefore, to make one full copy of the texture image cover a span of
    W inches, set:

        texture_RealWorldScaleX = W * 2

    This was verified by disabling tiling (URepeat=False) and observing
    the texture/black boundary at known distances using ruler bodies with
    tick marks. The 0.5x factor is exact across tested scales 5-50 inches.

Usage:
    from veneer import apply_veneer, apply_veneer_autofit, apply_veneer_realsize

    # Best default: apply at the image's real physical size (no stretching)
    apply_veneer_realsize(
        bodies=[panel_l, panel_r],
        image_path="/path/to/spalted_maple_landscape.jpg",
        real_width_inches=17.8,   # physical width of the image
        real_height_inches=9.1,   # physical height of the image
    )

    # Auto-fit: stretches texture to cover the combined bounding box
    apply_veneer_autofit(
        bodies=[panel_l, panel_r],
        image_path="/path/to/spalted_maple_landscape.jpg",
    )

    # Explicit: specify desired image dimensions on surface (cm)
    apply_veneer(
        bodies=[panel_l, panel_r],
        image_path="/path/to/spalted_maple_landscape.jpg",
        real_width_cm=27.0,   # desired image width on surface
        real_height_cm=19.7,  # desired image height on surface
    )

Utility:
    from veneer import period_to_scale, scale_to_period

    scale_inches = period_to_scale(desired_period_inches=12.0)  # -> 24.0
    period_inches = scale_to_period(scale_inches=24.0)          # -> 12.0
"""

import adsk.core
import adsk.fusion


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_veneer(
    bodies,
    image_path,
    real_width_cm,
    real_height_cm,
    origin_body=None,
    margin=1.05,
    base_appearance_name="Pine",
    appearance_name="SP_veneer",
    fix_bottom_face=True,
):
    """Apply a photo texture to bodies with no visible seams.

    Creates (or reuses) a custom appearance with the given image, computes
    the correct texture scale so one full image tile covers the bounding
    extent of all bodies, sets a shared TMC (TextureMapControl) origin for
    continuous grain, and optionally applies a half-period Y-offset fix to
    bottom (-Z) faces.

    Args:
        bodies: list of adsk.fusion.BRepBody objects to texture.
        image_path: absolute path to the texture image file (JPEG/PNG).
        real_width_cm: desired physical width of the image on the surface,
            in centimeters. This is the X-axis coverage (grain direction for
            landscape images).
        real_height_cm: desired physical height of the image, in cm.
            This is the Y-axis coverage.
        origin_body: body whose bounding-box min point is used as the TMC
            origin. If None, uses the first body in the list. All bodies
            share this origin for seamless grain continuity.
        margin: multiplicative safety margin on the scale (default 1.05 =
            5%). Ensures the texture period slightly exceeds the body span,
            pushing tile seams outside the visible surface.
        base_appearance_name: Fusion library appearance to copy from when
            creating the custom appearance. "Pine" works well for wood
            veneers (neutral base color).
        appearance_name: name for the custom appearance in the design.
        fix_bottom_face: if True, creates a second appearance using a
            horizontally flipped copy of the image and applies it to
            downward-facing (-Z) faces. This produces a mirror-image
            of the top — matching what you'd see looking through a thin
            veneer from the back. The flipped image is auto-generated
            (via macOS sips) as <image_path>_flipped.<ext> if it doesn't
            already exist.

    Returns:
        dict with keys:
            "appearance": the main adsk.core.Appearance
            "bottom_appearance": the bottom-face Appearance (or None)
            "scale_x_in": the X scale value written (inches)
            "scale_y_in": the Y scale value written (inches)
            "period_x_in": the visible X period (inches)
            "period_y_in": the visible Y period (inches)
            "tmc_origin_cm": (x, y, z) tuple of TMC origin in cm

    Scale Calculation:
        The function converts the desired real-world coverage from cm to
        inches, then computes:

            scale_x = (real_width_cm / 2.54) * 2 * margin
            scale_y = (real_height_cm / 2.54) * 2 * margin

        The factor of 2 accounts for Fusion's period = scale/2 behavior.
        The margin factor ensures the seam falls outside the body.

        Alternatively, if you want the texture to auto-fit the combined
        bounding box of all bodies, use apply_veneer_autofit() instead.
    """
    if not bodies:
        raise ValueError("bodies list is empty")

    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)

    # --- Create or reuse appearance ---
    main_app = _get_or_create_appearance(design, app, appearance_name,
                                         base_appearance_name)

    # --- Set texture properties ---
    tex = _get_texture(main_app)
    if tex is None:
        raise RuntimeError(
            f"Appearance '{appearance_name}' has no connected texture on "
            f"opaque_albedo. Cannot apply veneer.")

    # Set bitmap
    _set_tex(tex, "unifiedbitmap_Bitmap", image_path, is_filename=True)

    # Compute scale: period = scale/2, so scale = desired_size_inches * 2
    CM_TO_IN = 1.0 / 2.54
    scale_x = real_width_cm * CM_TO_IN * 2 * margin
    scale_y = real_height_cm * CM_TO_IN * 2 * margin

    _set_tex(tex, "texture_RealWorldScaleX", scale_x)
    _set_tex(tex, "texture_RealWorldScaleY", scale_y)
    _set_tex(tex, "texture_RealWorldOffsetX", 0.0)
    _set_tex(tex, "texture_RealWorldOffsetY", 0.0)
    _set_tex(tex, "texture_WAngle", 0.0)
    _set_tex_bool(tex, "texture_URepeat", True)
    _set_tex_bool(tex, "texture_VRepeat", True)

    # --- Apply appearance to all bodies + face overrides ---
    for body in bodies:
        body.appearance = main_app
        for fi in range(body.faces.count):
            body.faces.item(fi).appearance = main_app

    # --- Set shared TMC origin ---
    ref_body = origin_body or bodies[0]
    origin = ref_body.boundingBox.minPoint
    m = adsk.core.Matrix3D.create()
    m.setCell(0, 3, origin.x)
    m.setCell(1, 3, origin.y)
    m.setCell(2, 3, origin.z)

    for body in bodies:
        adsk.doEvents()
        tmc = body.textureMapControl
        ptmc = adsk.core.ProjectedTextureMapControl.cast(tmc)
        if ptmc:
            ptmc.projectedTextureMapType = (
                adsk.core.ProjectedTextureMapTypes.BoxTextureMapProjection)
            ptmc.transform = m

    # --- Fix bottom (-Z) faces ---
    # For thin veneers, the bottom should show a horizontally flipped
    # version of the top — as if looking through the wood from behind.
    # We use a pre-flipped image file (same scale/offset, different bitmap).
    bot_app = None
    if fix_bottom_face:
        import os
        base, ext = os.path.splitext(image_path)
        flipped_path = base + "_flipped" + ext
        if not os.path.exists(flipped_path):
            import subprocess
            subprocess.run(["sips", "--flip", "horizontal",
                            image_path, "--out", flipped_path],
                           capture_output=True)

        bot_name = appearance_name + "_bottom"
        bot_app = design.appearances.itemByName(bot_name)
        if not bot_app:
            bot_app = design.appearances.addByCopy(main_app, bot_name)

        bot_tex = _get_texture(bot_app)
        if bot_tex:
            _set_tex(bot_tex, "unifiedbitmap_Bitmap", flipped_path,
                     is_filename=True)
            # Negate scales to undo Box projection's -Z UV inversion,
            # Y offset cancels the built-in half-period shift.
            # Combined with the flipped image this gives a true mirror.
            _set_tex(bot_tex, "texture_RealWorldScaleX", -scale_x)
            _set_tex(bot_tex, "texture_RealWorldScaleY", -scale_y)
            _set_tex(bot_tex, "texture_RealWorldOffsetX", 0.0)
            _set_tex(bot_tex, "texture_RealWorldOffsetY", scale_y / 2.0)
            _set_tex(bot_tex, "texture_WAngle", 0.0)
            _set_tex_bool(bot_tex, "texture_URepeat", True)
            _set_tex_bool(bot_tex, "texture_VRepeat", True)

            for body in bodies:
                for fi in range(body.faces.count):
                    f = body.faces.item(fi)
                    ok, pt = f.evaluator.getPointAtParameter(
                        adsk.core.Point2D.create(0.5, 0.5))
                    if ok:
                        ok2, n = f.evaluator.getNormalAtPoint(pt)
                        if ok2 and n.z < -0.9:
                            f.appearance = bot_app

    period_x = scale_x / 2.0
    period_y = scale_y / 2.0

    return {
        "appearance": main_app,
        "bottom_appearance": bot_app,
        "scale_x_in": scale_x,
        "scale_y_in": scale_y,
        "period_x_in": period_x,
        "period_y_in": period_y,
        "tmc_origin_cm": (origin.x, origin.y, origin.z),
    }


def apply_veneer_autofit(
    bodies,
    image_path,
    origin_body=None,
    margin=1.05,
    base_appearance_name="Pine",
    appearance_name="SP_veneer",
    fix_bottom_face=True,
):
    """Apply a photo texture sized to exactly cover the combined bounding box.

    Computes the required real_width_cm and real_height_cm from the union of
    all body bounding boxes (in the XY plane, which is the top face for
    typical panels), then delegates to apply_veneer().

    This is the simplest API: just pass bodies and an image path, and the
    function figures out the right scale.

    Args:
        bodies: list of BRepBody objects.
        image_path: path to image file.
        origin_body: reference body for TMC origin (default: first).
        margin: safety margin (default 1.05 = 5%).
        base_appearance_name: Fusion library base appearance.
        appearance_name: name for the custom appearance.
        fix_bottom_face: apply -Z face fix (default True).

    Returns:
        Same dict as apply_veneer().
    """
    if not bodies:
        raise ValueError("bodies list is empty")

    # Compute combined bounding box
    ref = (origin_body or bodies[0]).boundingBox.minPoint
    min_x = ref.x
    min_y = ref.y
    max_x = ref.x
    max_y = ref.y

    for body in bodies:
        bb = body.boundingBox
        min_x = min(min_x, bb.minPoint.x)
        min_y = min(min_y, bb.minPoint.y)
        max_x = max(max_x, bb.maxPoint.x)
        max_y = max(max_y, bb.maxPoint.y)

    span_x_cm = max_x - min_x  # Fusion internal units = cm
    span_y_cm = max_y - min_y

    return apply_veneer(
        bodies=bodies,
        image_path=image_path,
        real_width_cm=span_x_cm,
        real_height_cm=span_y_cm,
        origin_body=origin_body,
        margin=margin,
        base_appearance_name=base_appearance_name,
        appearance_name=appearance_name,
        fix_bottom_face=fix_bottom_face,
    )


def apply_veneer_realsize(
    bodies,
    image_path,
    real_width_inches,
    real_height_inches,
    origin_body=None,
    offset_x_inches=0.0,
    offset_y_inches=0.0,
    base_appearance_name="Pine",
    appearance_name="SP_veneer",
    fix_bottom_face=True,
):
    """Apply a photo texture at its real physical size (no stretching).

    The simplest "do the right thing" API for photo-based veneers. Maps the
    texture at exactly the image's real-world dimensions with margin=1.0
    (no safety overshoot), so the grain scale is physically accurate on
    every body regardless of body size.

    Pieces smaller than the image show a cropped portion (no seams).
    Pieces larger than the image tile naturally (seams at image boundaries).
    All bodies share the same texture origin, so grain is continuous across
    adjacent panels.

    Args:
        bodies: list of BRepBody objects to texture.
        image_path: absolute path to the texture image file (JPEG/PNG).
        real_width_inches: physical width of the image in inches (X-axis /
            grain direction for landscape images).
        real_height_inches: physical height of the image in inches (Y-axis).
        origin_body: body whose bounding-box min point is used as the TMC
            origin. If None, uses the first body in the list.
        offset_x_inches: horizontal texture offset in inches (default 0).
            Shifts where the image lands on the surface.
        offset_y_inches: vertical texture offset in inches (default 0).
        base_appearance_name: Fusion library base appearance (default "Pine").
        appearance_name: name for the custom appearance in the design.
        fix_bottom_face: apply -Z face fix (default True).

    Returns:
        Same dict as apply_veneer(), plus:
            "offset_x_in": the X offset written (inches)
            "offset_y_in": the Y offset written (inches)
    """
    result = apply_veneer(
        bodies=bodies,
        image_path=image_path,
        real_width_cm=real_width_inches * 2.54,
        real_height_cm=real_height_inches * 2.54,
        origin_body=origin_body,
        margin=1.0,
        base_appearance_name=base_appearance_name,
        appearance_name=appearance_name,
        fix_bottom_face=fix_bottom_face,
    )

    # Apply offsets if nonzero
    if offset_x_inches != 0.0 or offset_y_inches != 0.0:
        tex = _get_texture(result["appearance"])
        if tex:
            _set_tex(tex, "texture_RealWorldOffsetX", offset_x_inches)
            _set_tex(tex, "texture_RealWorldOffsetY", offset_y_inches)

    result["offset_x_in"] = offset_x_inches
    result["offset_y_in"] = offset_y_inches
    return result


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def period_to_scale(desired_period_inches):
    """Convert desired visible period (inches) to texture_RealWorldScale value.

    Fusion 360's texture period = scale / 2, so scale = period * 2.

    Args:
        desired_period_inches: how many inches one tile of the texture
            should cover in real space.

    Returns:
        The value to write to texture_RealWorldScaleX or Y (in inches).
    """
    return desired_period_inches * 2.0


def scale_to_period(scale_inches):
    """Convert a texture_RealWorldScale value to visible period (inches).

    Args:
        scale_inches: the value of texture_RealWorldScaleX or Y.

    Returns:
        The visible texture period in inches.
    """
    return scale_inches / 2.0


def span_to_scale(span_cm, margin=1.05):
    """Compute the texture scale needed to cover a span with no seams.

    Args:
        span_cm: the physical span to cover, in cm (Fusion internal units).
        margin: safety factor (default 1.05 = 5% overshoot).

    Returns:
        The texture_RealWorldScale value (inches) that makes one full
        texture tile cover the span plus margin.
    """
    span_inches = span_cm / 2.54
    return span_inches * 2.0 * margin


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _get_or_create_appearance(design, app, name, base_name):
    """Get existing or create new appearance by copying from library."""
    existing = design.appearances.itemByName(name)
    if existing:
        return existing

    base_app = None
    libs = app.materialLibraries
    for li in range(libs.count):
        lib = libs.item(li)
        for ai in range(lib.appearances.count):
            a = lib.appearances.item(ai)
            if a.name == base_name and not a.name.startswith("3D "):
                if "appearance" in lib.name.lower():
                    return design.appearances.addByCopy(a, name)
                if base_app is None:
                    base_app = a
        if base_app and "appearance" in lib.name.lower():
            break

    if base_app is None:
        raise RuntimeError(
            f"Base appearance '{base_name}' not found in material libraries")

    return design.appearances.addByCopy(base_app, name)


def _get_texture(appearance):
    """Get the connected texture from the opaque_albedo color property."""
    props = appearance.appearanceProperties
    cp = adsk.core.ColorProperty.cast(props.itemById("opaque_albedo"))
    if cp and cp.hasConnectedTexture:
        return cp.connectedTexture
    return None


def _set_tex(tex, prop_id, value, is_filename=False):
    """Set a texture property by ID."""
    prop = tex.properties.itemById(prop_id)
    if prop is None:
        return False
    if is_filename:
        fp = adsk.core.FilenameProperty.cast(prop)
        if fp and not fp.isReadOnly:
            fp.value = value
            return True
        return False
    fp = adsk.core.FloatProperty.cast(prop)
    if fp:
        fp.value = value
        return True
    return False


def _set_tex_bool(tex, prop_id, value):
    """Set a boolean texture property by ID."""
    prop = tex.properties.itemById(prop_id)
    if prop is None:
        return False
    bp = adsk.core.BooleanProperty.cast(prop)
    if bp:
        bp.value = value
        return True
    return False
