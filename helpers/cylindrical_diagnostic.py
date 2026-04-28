"""Deterministic helpers for CylindricalTextureMapProjection on parametric bodies.

Companion to `helpers/box_diagnostic.py`. Same shape: pure-math rule
calculation, marker-image generation (delegated), analytical seam
prediction, and a calibration procedure to re-derive the rule when
Fusion's behavior changes.

Empirical findings (Fusion 360, April 2026):

  Convention (what scale_x/scale_y actually do, contradicting older docs):
    texture_RealWorldScaleX  -> period along the cylinder axis (V direction)
    texture_RealWorldScaleY  -> period around the circumference (U direction)
    image-X (left/right edges) -> axial direction
    image-Y (top/bottom edges) -> circumferential direction
    texture_WAngle            -> *IGNORED* by CylindricalTextureMapProjection
                                  in this Fusion build.

  Implication for wood photos: real wood-veneer bitmaps store grain along
  image-Y. Mapped natively, that grain wraps AROUND the cylinder. To get
  grain ALONG the cylinder axis, the bitmap must be **pre-rotated 90 deg**
  on disk, since WAngle is silently ignored. Use `make_axial_bitmap()`.

  Recipe (validated on round bars 38 cm x radius 1, 1.3, 2, 3 cm; tall
  post 70 cm x 1.7 cm; same recipe across X/Y/Z body axes):

    1. Pre-rotate bitmap 90 deg (image-Y becomes image-X).
    2. scale_x  = body_axial_length x (1 + seam_buffer)   [Box rule]
                  if natural axial >= body_axial_length; else natural axial.
    3. scale_y  = circumference   (N=1 - see "circ multiplier" note below).
    4. offset_x = bbox_min_axial - (period_axial - body_axial)/2
                  (recenters axial seam off-body, as in Box).
    5. offset_y = 0.25 * circumference  (pushes the single azimuthal seam
                  to the back, +Y direction). Empirical mapping:
                    fraction 0.0  -> seam at +X
                    fraction 0.25 -> seam at +Y (back)
                    fraction 0.5  -> seam at -X
                    fraction 0.75 -> seam at -Y (front)
    6. WAngle   = 0 (no effect anyway).
    7. TMC transform: rotate texture-local +Z to body's long-axis vector;
                      no translate baked in.

  Why N=1 (not N>1): increasing N (period_y = N x circumference) means
  the natural bitmap fills only 1/N of one period; the remaining (N-1)/N
  is filled by Fusion's repeat -> MULTIPLE seams visible. With N=1, image
  edges meet at exactly ONE azimuthal angle, choosable via offset_y.

Seam summary (validated visually with red/green marker bitmaps):
  - AXIAL seams (green markers): fully eliminated on bodies shorter than the
    natural texture by the recenter rule (body * 1.05 period + centered
    translate). Bodies longer than natural MUST tile and accept axial seams
    at each period boundary -- same as Box projection.
  - AZIMUTHAL seam (red markers): CANNOT be eliminated, only relocated.
    With N=1, the bitmap wraps exactly once around the cylinder, producing
    one vertical seam line where the left and right edges of the
    (pre-rotated) image meet. Default offset_y = 0.25 * circumference
    pushes this seam to the +Y (back) side. The seam spans ~(2 * stripe_px
    / image_height_px) fraction of the circumference; for teak.jpg that is
    ~2.5% of the circumference (< 9 degrees of arc), so it is invisible
    from front, left, and right views.
  - ENDCAP faces: cylindrical projection produces radial/cross-hatch
    artifacts on flat endcaps. In practice, endcaps receive a separate
    endgrain appearance, so this is not a concern.

Practical recommendation: use Box+grain (with 45-deg rotation for curved
revolved bodies) as the primary projection for round bars. Cylindrical
works only with the pre-rotated-bitmap hack, and even at N=1 leaves one
azimuthal seam that can only be relocated (not eliminated). Box+45 hides
the equivalent direction-transition behind curvature shading and uses the
natural bitmap. This module exists for completeness and for the rare case
where a body is so close to a perfect cylinder that the user wants the
texture to wrap exactly once around it.

All units cm unless suffixed _in.
"""
import math
import os


# ---------------------------------------------------------------------
# Pure-math rules
# ---------------------------------------------------------------------

def recommend_cyl_periods_cm(body_axial_cm, body_radius_cm,
                              natural_axial_cm, ppi_per_cm,
                              ppi_threshold=20.0, seam_buffer=0.05,
                              circ_multiplier=1):
    """Return (period_axial_cm, period_circ_cm, rule_used) for a cylindrical body.

    period_axial follows the same Box rule as Box+grain:
      - sharp source (ppi >= threshold)  -> natural axial
      - body >= natural                  -> natural axial (force tile)
      - body < natural                   -> body x (1 + seam_buffer)

    period_circ = circ_multiplier x (2 pi r). Default 1 (single wrap).
    Higher multipliers are NOT recommended for low-resolution wood photos -
    they replicate the photo's edge stripes around the cylinder.
    """
    if natural_axial_cm <= 0 or body_axial_cm <= 0 or body_radius_cm <= 0:
        return 0.0, 0.0, "invalid input"
    circumference = 2.0 * math.pi * body_radius_cm
    if ppi_per_cm >= ppi_threshold:
        period_axial = natural_axial_cm
        rule = "natural axial (sharp source)"
    elif body_axial_cm >= natural_axial_cm:
        period_axial = natural_axial_cm
        rule = "natural axial (body >= natural; tiling)"
    else:
        period_axial = body_axial_cm * (1.0 + seam_buffer)
        rule = "body x %.3f" % (1 + seam_buffer)
    period_circ = circ_multiplier * circumference
    return period_axial, period_circ, rule


def recenter_axial_offset_cm(bbox_min_axial_cm, period_axial_cm,
                              body_axial_cm):
    """Same as Box's recenter_translate_grain_cm but renamed for clarity.

    Returns:
        offset_x = bbox_min_axial - (period - body) / 2

    Both axial-period boundaries land off-body when period > body, each
    at distance (period - body)/2 from the nearer body endcap.
    """
    return bbox_min_axial_cm - (period_axial_cm - body_axial_cm) / 2.0


def analytical_axial_seams(bbox_min_axial_cm, bbox_max_axial_cm,
                            period_axial_cm, offset_axial_cm,
                            tolerance_cm=0.001):
    """Predict axial-seam positions inside the body extent. Empty list = no
    axial seam. (Circumferential seam at offset_y mod period_y is always
    present at one azimuth when period_circ = circumference.)
    """
    seams = []
    if period_axial_cm <= 0:
        return seams
    n_lo = math.ceil((bbox_min_axial_cm - tolerance_cm - offset_axial_cm) / period_axial_cm)
    n_hi = math.floor((bbox_max_axial_cm + tolerance_cm - offset_axial_cm) / period_axial_cm)
    for n in range(n_lo, n_hi + 1):
        pos = offset_axial_cm + n * period_axial_cm
        if bbox_min_axial_cm - tolerance_cm < pos < bbox_max_axial_cm + tolerance_cm:
            seams.append(pos)
    return seams


# ---------------------------------------------------------------------
# Pre-rotated bitmap generation (works around WAngle being ignored)
# ---------------------------------------------------------------------

def make_axial_bitmap(src_path, dst_path=None, marker=False):
    """Return a path to a 90-degree-rotated copy of `src_path`.

    Original wood photos store grain on image-Y. Cylindrical projection
    in this Fusion build maps image-X -> axial, image-Y -> circumferential.
    Rotating the bitmap 90 deg puts the grain on image-X -> axial -> grain
    runs along the cylinder axis as the user expects.

    If `marker=True`, also adds the box_diagnostic colored edge stripes
    AFTER rotation, so red/green still mark image-Y/-X edges of the
    rotated image (= circ/axial edges respectively).
    """
    from PIL import Image, ImageDraw
    src = Image.open(src_path).convert("RGB")
    rot = src.transpose(Image.ROTATE_90)
    if marker:
        W, H = rot.size
        px = max(8, H // 80)
        d = ImageDraw.Draw(rot)
        # Red on image-Y top/bottom (= circumferential edges of cylinder mapping)
        d.rectangle([0, 0, W, px], fill=(255, 0, 0))
        d.rectangle([0, H - px, W, H], fill=(255, 0, 0))
        # Green on image-X left/right (= axial edges of cylinder mapping)
        d.rectangle([0, 0, px, H], fill=(0, 255, 0))
        d.rectangle([W - px, 0, W, H], fill=(0, 255, 0))
    if dst_path is None:
        base, ext = os.path.splitext(os.path.basename(src_path))
        suffix = "_cyl90_marker" if marker else "_cyl90"
        dst_path = "/tmp/%s%s%s" % (base, suffix, ext)
    rot.save(dst_path, quality=92)
    return dst_path


# ---------------------------------------------------------------------
# Convenience: applier using the rules
# ---------------------------------------------------------------------

def apply_cylindrical_recipe(body, species_key, sp_module,
                              circ_multiplier=1, seam_buffer=0.05,
                              ppi_threshold=20.0,
                              azimuth_offset_fraction=0.25):
    """Apply the deterministic Cylindrical+grain recipe to a round body.

    body: BRepBody. Its body axis is taken from `sp._grain_vector(body)`
          (principal-axis-of-inertia rule from sp.py - works on bars).
    species_key: key into sp_module._SPECIES_TEXTURE.
    circ_multiplier: N. Use 1 unless you know what you're doing.
    seam_buffer: as in Box rule. 0.05 is the validated default.
    ppi_threshold: pixels-per-cm threshold for "sharp source" branch.
    azimuth_offset_fraction: Fraction of circumference to rotate the
        azimuthal seam away from TMC theta=0 (+X direction).
        Empirical mapping (identity TMC transform, Z-axis body):
          0.0  -> seam at +X  (visible from front and right)
          0.25 -> seam at +Y  (back, hidden from default front camera)
          0.5  -> seam at -X  (visible from front and left)
          0.75 -> seam at -Y  (front, worst position)
        Default 0.25 pushes the single azimuthal seam behind the body.

    The bitmap is pre-rotated 90 deg and saved to /tmp before being
    assigned to the body's appearance. Returns a dict with the analytical
    state (period_axial, period_circ, offset_axial, etc.) for logging.
    """
    import adsk.core, adsk.fusion
    CM_TO_IN = 1.0 / 2.54
    cfg = sp_module._SPECIES_TEXTURE.get(species_key)
    if not cfg:
        raise ValueError("Unknown species: %s" % species_key)
    natural_axial_cm = sp_module._natural_size_cm(cfg, "y")
    _, px_h = sp_module._get_px_dims(cfg)
    if not px_h or natural_axial_cm <= 0:
        ppi = float("inf")   # no pixel data → natural-scale
    else:
        ppi = px_h / natural_axial_cm
    bb = body.boundingBox
    grain_vec = sp_module._grain_vector(body)
    comps = [abs(grain_vec.x), abs(grain_vec.y), abs(grain_vec.z)]
    gi = comps.index(max(comps))
    extents = (bb.maxPoint.x - bb.minPoint.x,
               bb.maxPoint.y - bb.minPoint.y,
               bb.maxPoint.z - bb.minPoint.z)
    body_axial_cm = extents[gi]
    cross_indices = [i for i in (0, 1, 2) if i != gi]
    body_radius_cm = max(extents[cross_indices[0]], extents[cross_indices[1]]) / 2.0
    period_axial, period_circ, rule = recommend_cyl_periods_cm(
        body_axial_cm, body_radius_cm, natural_axial_cm, ppi,
        ppi_threshold=ppi_threshold, seam_buffer=seam_buffer,
        circ_multiplier=circ_multiplier)
    bbox_min_axial = (bb.minPoint.x, bb.minPoint.y, bb.minPoint.z)[gi]
    offset_axial = recenter_axial_offset_cm(bbox_min_axial, period_axial,
                                             body_axial_cm)
    offset_circ = period_circ * azimuth_offset_fraction

    src_path = os.path.join(sp_module._TEXTURE_DIR, cfg["texture"])
    rotated_bitmap = make_axial_bitmap(src_path)

    # Per-body appearance via sp.per_body_appearance -- safe, never touches
    # a shared SP_<species> appearance.
    local = sp_module.per_body_appearance(body, species_key)
    cp = adsk.core.ColorProperty.cast(
        local.appearanceProperties.itemById("opaque_albedo"))
    if cp and cp.hasConnectedTexture:
        tex = cp.connectedTexture
        bp = tex.properties.itemById("unifiedbitmap_Bitmap")
        fp = adsk.core.FilenameProperty.cast(bp)
        if fp and not fp.isReadOnly:
            fp.value = rotated_bitmap
        def setf(name, val):
            p = tex.properties.itemById(name)
            if p:
                adsk.core.FloatProperty.cast(p).value = val
        def setb(name, val):
            p = tex.properties.itemById(name)
            if p:
                adsk.core.BooleanProperty.cast(p).value = val
        setb("texture_ScaleLock", False)
        setf("texture_RealWorldScaleX", period_axial * CM_TO_IN)
        setf("texture_RealWorldScaleY", period_circ * CM_TO_IN)
        setf("texture_RealWorldOffsetX", offset_axial * CM_TO_IN)
        setf("texture_RealWorldOffsetY", offset_circ * CM_TO_IN)
        setf("texture_WAngle", 0.0)
        setf("texture_UOffset", 0.0)
        setf("texture_VOffset", 0.0)

    m = adsk.core.Matrix3D.create()
    z_axis = adsk.core.Vector3D.create(0, 0, 1)
    target = adsk.core.Vector3D.create(grain_vec.x, grain_vec.y, grain_vec.z)
    angle = z_axis.angleTo(target)
    if angle > 0.001 and angle < math.pi - 0.001:
        cross = z_axis.crossProduct(target)
        if cross.length > 0.001:
            cross.normalize()
            m.setToRotation(angle, cross, adsk.core.Point3D.create(0, 0, 0))
    elif angle >= math.pi - 0.001:
        m.setToRotation(math.pi, adsk.core.Vector3D.create(1, 0, 0),
                        adsk.core.Point3D.create(0, 0, 0))
    ptmc = adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl)
    if ptmc:
        ptmc.projectedTextureMapType = (
            adsk.core.ProjectedTextureMapTypes.CylindricalTextureMapProjection)
        ptmc.transform = m

    seams = analytical_axial_seams(bbox_min_axial,
                                    bbox_min_axial + body_axial_cm,
                                    period_axial, offset_axial)
    return {
        "species": species_key,
        "natural_axial_cm": natural_axial_cm,
        "ppi_per_cm": ppi,
        "body_axial_cm": body_axial_cm,
        "body_radius_cm": body_radius_cm,
        "circumference_cm": 2.0 * math.pi * body_radius_cm,
        "period_axial_cm": period_axial,
        "period_circ_cm": period_circ,
        "circ_multiplier": circ_multiplier,
        "rule_used": rule,
        "offset_axial_cm": offset_axial,
        "offset_circ_cm": offset_circ,
        "rotated_bitmap": rotated_bitmap,
        "analytical_axial_seams_in_body": seams,
        "appearance": local.name if local else None,
    }


def calibrate_circ_multiplier(body, species_key, sp_module,
                               n_candidates=(1, 2, 4, 8),
                               screenshot_fn=None, oracle_fn=None,
                               marker_dir="/tmp"):
    """Sweep circ_multiplier candidates with a marker bitmap, returning the
    smallest N for which the body has no visible green or red seam stripe
    on the front-camera-facing side.

    Mirrors box_diagnostic.calibrate_seam_buffer signature/usage. In this
    Fusion build N=1 is the only sensible value; this function exists so
    a future Fusion update that fixes WAngle can be detected (a higher
    N suddenly becoming better than 1 would indicate behavior changed).

    screenshot_fn: returns image path (e.g. mcp.get_screenshot wrapper).
    oracle_fn: (image_path, n) -> bool (True = no seam visible).
    """
    import adsk.core, adsk.fusion
    cfg = sp_module._SPECIES_TEXTURE.get(species_key) or {}
    src_path = os.path.join(sp_module._TEXTURE_DIR, cfg.get("texture", ""))
    if not os.path.isfile(src_path):
        raise FileNotFoundError("Texture not found: %s" % src_path)
    marker_rot = make_axial_bitmap(
        src_path,
        os.path.join(marker_dir,
                     "%s_cyl90_marker.jpg" % species_key.replace(' ', '_')),
        marker=True)
    results = {"min_seam_free_n": None, "screenshots": {},
               "analytical_results": {}, "scratch_appearances": []}
    orig_appearance = body.appearance
    scratch_state = []   # list of (appearance, original_bitmap_path)
    try:
        for N in n_candidates:
            applied = apply_cylindrical_recipe(body, species_key, sp_module,
                                                circ_multiplier=N)
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
                    fp.value = marker_rot
            if not any(s[0] is ap for s in scratch_state):
                scratch_state.append((ap, orig_bitmap))
                results["scratch_appearances"].append(ap.name)
            if screenshot_fn is not None:
                shot = screenshot_fn()
                results["screenshots"][N] = shot
                if oracle_fn is not None and oracle_fn(shot, N):
                    results["min_seam_free_n"] = N
                    break
    finally:
        for ap, orig_bmp in scratch_state:
            if orig_bmp:
                try:
                    cp = adsk.core.ColorProperty.cast(
                        ap.appearanceProperties.itemById("opaque_albedo"))
                    if cp and cp.hasConnectedTexture:
                        tex = cp.connectedTexture
                        bp = tex.properties.itemById("unifiedbitmap_Bitmap")
                        fp = adsk.core.FilenameProperty.cast(bp)
                        if fp and not fp.isReadOnly:
                            fp.value = orig_bmp
                except Exception:
                    pass
        try:
            body.appearance = orig_appearance
        except Exception:
            pass
    return results
