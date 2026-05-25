"""Deterministic helpers for BoxTextureMapProjection on parametric bodies.

The functions in this module replace the prose "red marker iterate" recipe
in `docs/appearance.md` with code: pure-math rule calculation,
marker-image generation, analytical seam detection, and a structured
calibration procedure that captures evidence and reports the smallest
seam-free buffer.

If a future Fusion update changes Box-projection behavior, run
`calibrate(...)` against a scratch document to re-establish the new
baseline parameters; the analytical and visual results will diverge,
making the regression visible.

Convention:
    "grain axis"        the body's long axis (= image-Y direction in
                        teak veneer photos when grain is configured to
                        run along image-Y)
    "cross axis"        the body's short axis (image-X direction)
    period_along_grain  = the texture period in cm in the grain direction
                          (corresponds to scale_y in inches × 2.54)
    period_cross_grain  = the texture period in cm cross-grain
                          (corresponds to scale_x in inches × 2.54)

All units cm unless suffixed _in.
"""
import math
import os


# ─────────────────────────────────────────────────────────────────────
# Pure-math rules
# ─────────────────────────────────────────────────────────────────────

def recommend_period_cm(body_grain_cm, natural_grain_cm, ppi_per_cm,
                         ppi_threshold=20.0, seam_buffer=0.05,
                         min_natural_fraction=0.5):
    """Return (period_cm, rule_used) for a flat body using Box+grain.

    Three branches — first match wins:
      1. Sharp source (ppi >= ppi_threshold): period = natural.
      2. body >= natural: must tile; period = natural; caller accepts seam.
      3. body < natural (low-res):
           period = max(body × (1 + seam_buffer),
                        natural × min_natural_fraction).
         The seam_buffer term avoids the period boundary landing on the
         body; the natural-fraction floor is an aesthetic limit (no
         excessive image compression).

    Default seam_buffer is 0.05. Empirically 5% body extent margin is the
    smallest reliably seam-free value across body sizes 5–100 cm; under
    that, float-precision drift in Fusion's TMC can re-introduce a seam.
    """
    if natural_grain_cm <= 0 or body_grain_cm <= 0:
        return natural_grain_cm or 0.0, "invalid input"
    if ppi_per_cm >= ppi_threshold:
        return natural_grain_cm, "natural (sharp source)"
    if body_grain_cm >= natural_grain_cm:
        return natural_grain_cm, "natural (body >= natural; tiling)"
    target = body_grain_cm * (1.0 + seam_buffer)
    floor = natural_grain_cm * min_natural_fraction
    if target >= floor:
        return target, f"body × {1 + seam_buffer:.3f}"
    return floor, f"natural × {min_natural_fraction:.2f} (aesthetic floor)"


def recenter_translate_grain_cm(bbox_min_grain_cm, period_grain_cm,
                                 body_grain_cm):
    """Translate value along the grain axis that puts both period boundaries
    off-body. Returns:

        translate_grain = bbox_min_grain - (period - body) / 2

    For period > body this places one boundary at
    `bbox_min - (period - body)/2` (off-body, below) and the other at
    `bbox_max + (period - body)/2` (off-body, above), each at distance
    `(period - body)/2` from the nearer body edge.
    """
    return bbox_min_grain_cm - (period_grain_cm - body_grain_cm) / 2.0


def analytical_seams(bbox_min_cm, bbox_max_cm, period_cm, translate_cm,
                      tolerance_cm=0.001):
    """Pure-math seam-location predictor.

    Given a body's bbox along one axis, the period in that axis, and the
    TMC translate value, returns the list of period-boundary positions
    that land within the body extent (within ±tolerance_cm). Empty list
    means no seam in this axis.

    Period boundaries are at `translate + n * period` for any integer n.

    Useful as a regression check: an in-body seam from this function
    means the configured period/translate are wrong (caller's bug).
    A no-seam result here followed by a visible seam in a screenshot
    means Fusion's actual behavior diverges from the math (= rule
    update needed).
    """
    seams = []
    if period_cm <= 0:
        return seams
    n_lo = math.ceil((bbox_min_cm - tolerance_cm - translate_cm) / period_cm)
    n_hi = math.floor((bbox_max_cm + tolerance_cm - translate_cm) / period_cm)
    for n in range(n_lo, n_hi + 1):
        pos = translate_cm + n * period_cm
        if bbox_min_cm - tolerance_cm < pos < bbox_max_cm + tolerance_cm:
            seams.append(pos)
    return seams


# ─────────────────────────────────────────────────────────────────────
# Marker image generation
# ─────────────────────────────────────────────────────────────────────

def make_marker_image(src_path, dst_path=None, stripe_px=None,
                       long_edge_color=(255, 0, 0),
                       short_edge_color=(0, 255, 0)):
    """Create a copy of a wood texture with bright stripes on its four edges.

    Stripes:
      - long_edge_color (default red) on image-Y top/bottom rows: marks
        the period-along-grain boundary.
      - short_edge_color (default green) on image-X left/right columns:
        marks the period-cross-grain boundary.

    Use the marker image in place of the natural bitmap when calibrating
    Box projection: any red horizontal line visible on the body's surface
    means a period-along-grain boundary lies on the body (= seam to fix).

    Returns dst_path (defaults to /tmp/<src>_marker.<ext>).
    """
    from PIL import Image, ImageDraw  # imported lazily; only needed at calibration time
    src = Image.open(src_path).convert("RGB")
    out = src.copy()
    W, H = out.size
    px = stripe_px if stripe_px else max(8, H // 80)
    d = ImageDraw.Draw(out)
    d.rectangle([0, 0, W, px], fill=long_edge_color)
    d.rectangle([0, H - px, W, H], fill=long_edge_color)
    d.rectangle([0, 0, px, H], fill=short_edge_color)
    d.rectangle([W - px, 0, W, H], fill=short_edge_color)
    if dst_path is None:
        base, ext = os.path.splitext(os.path.basename(src_path))
        dst_path = f"/tmp/{base}_marker{ext}"
    out.save(dst_path, quality=92)
    return dst_path


# ─────────────────────────────────────────────────────────────────────
# Convenience: applier using the rules + calibration procedure
# ─────────────────────────────────────────────────────────────────────

def apply_box_grain_recipe(body, species_key, sp_module,
                            seam_buffer=0.05, ppi_threshold=20.0):
    """Apply the deterministic Box+grain recipe to a flat body.

    Wraps the math: looks up the species in `sp_module._SPECIES_TEXTURE`,
    computes the period via `recommend_period_cm()`, applies a per-body
    appearance copy with the period set on `texture_RealWorldScaleY`,
    and configures the body's TMC with Box+grain rotation + the
    grain-axis-recentered translate. Other (cross-grain) translate axes
    sit at bbox-min.

    Caller must pass `sp_module` (the helpers.sp module) so this file
    avoids a circular import.

    For curved revolved bodies (legs/posts/round bars) use
    `apply_box_grain_45rot()` instead.
    """
    import adsk.core, adsk.fusion
    cfg = sp_module._SPECIES_TEXTURE.get(species_key)
    if not cfg:
        raise ValueError(f"Unknown species: {species_key}")
    natural_grain_cm = sp_module._natural_size_cm(cfg, "y")
    _, px_h = sp_module._get_px_dims(cfg)
    if not px_h or natural_grain_cm <= 0:
        ppi = float("inf")   # no pixel data → natural-scale
    else:
        ppi = px_h / natural_grain_cm
    bb = body.boundingBox
    grain_vec = sp_module._grain_vector(body)
    comps = [abs(grain_vec.x), abs(grain_vec.y), abs(grain_vec.z)]
    gi = comps.index(max(comps))
    body_extents = (bb.maxPoint.x - bb.minPoint.x,
                    bb.maxPoint.y - bb.minPoint.y,
                    bb.maxPoint.z - bb.minPoint.z)
    body_min = (bb.minPoint.x, bb.minPoint.y, bb.minPoint.z)
    body_grain_cm = body_extents[gi]
    period_cm, rule = recommend_period_cm(
        body_grain_cm, natural_grain_cm, ppi,
        ppi_threshold=ppi_threshold, seam_buffer=seam_buffer)
    translate_grain = recenter_translate_grain_cm(
        body_min[gi], period_cm, body_grain_cm)
    # Build TMC transform: rotation aligned to grain, translates per axis
    m = sp_module._grain_transform(grain_vec)
    translate_xyz = list(body_min)
    translate_xyz[gi] = translate_grain
    for axis_idx, val in enumerate(translate_xyz):
        m.setCell(axis_idx, 3, val)
    # Per-body appearance via sp.per_body_appearance — safe, never touches
    # a shared SP_<species> appearance.
    local = sp_module.per_body_appearance(body, species_key)
    cp = adsk.core.ColorProperty.cast(
        local.appearanceProperties.itemById("opaque_albedo"))
    if cp and cp.hasConnectedTexture:
        tex = cp.connectedTexture
        sy_prop = tex.properties.itemById("texture_RealWorldScaleY")
        if sy_prop:
            adsk.core.FloatProperty.cast(sy_prop).value = period_cm / 2.54
    body.appearance = local
    ptmc = adsk.core.ProjectedTextureMapControl.cast(body.textureMapControl)
    if ptmc:
        ptmc.projectedTextureMapType = (
            adsk.core.ProjectedTextureMapTypes.BoxTextureMapProjection)
        ptmc.transform = m
    # Diagnostic: confirm no analytical seam
    seams = analytical_seams(body_min[gi], body_min[gi] + body_grain_cm,
                              period_cm, translate_grain)
    return {
        "species": species_key,
        "natural_grain_cm": natural_grain_cm,
        "ppi_per_cm": ppi,
        "body_grain_cm": body_grain_cm,
        "period_cm": period_cm,
        "rule_used": rule,
        "translate_grain": translate_grain,
        "analytical_seams_in_body": seams,
        "appearance": local.name if local else None,
    }


def calibrate_seam_buffer(body, species_key, sp_module,
                          buffer_candidates=(0.005, 0.01, 0.025, 0.05, 0.10),
                          screenshot_fn=None, oracle_fn=None,
                          marker_dir="/tmp"):
    """Sweep buffer candidates with marker bitmaps, returning the smallest
    seam-free buffer.

    Args:
        body: BRepBody to calibrate against.
        species_key: key into _SPECIES_TEXTURE.
        sp_module: imported helpers.sp.
        buffer_candidates: ascending buffer values to try.
        screenshot_fn: callable taking no args, returns an image file path.
            Pass `lambda: mcp.get_screenshot(view='current', width=1600,
            height=1600)['path']` (or equivalent).
        oracle_fn: callable taking `(image_path, buffer)` and returning
            `True` if the body is seam-free in that image. If None, the
            function returns ALL screenshot paths and lets the caller
            inspect (e.g. an interactive subagent loop).
        marker_dir: where to write the marker bitmap.

    Returns:
        dict with `min_seam_free_buffer` (or None if all failed),
        `screenshots` (per-buffer file paths), and `analytical_results`.
    """
    import adsk.core, adsk.fusion
    cfg = sp_module._SPECIES_TEXTURE.get(species_key) or {}
    src_path = os.path.join(sp_module._TEXTURE_DIR, cfg.get("texture", ""))
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"Texture not found: {src_path}")
    marker_path = make_marker_image(
        src_path,
        os.path.join(marker_dir, f"{species_key.replace(' ','_')}_marker.jpg"))
    results = {"min_seam_free_buffer": None, "screenshots": {},
               "analytical_results": {}, "scratch_appearances": []}
    orig_appearance = body.appearance
    # Track scratch per-body appearances so we can restore each one's
    # bitmap (and optionally remove them) in the finally block.
    scratch_state = []   # list of (appearance, original_bitmap_path)
    try:
        for buf in buffer_candidates:
            applied = apply_box_grain_recipe(body, species_key, sp_module,
                                              seam_buffer=buf)
            results["analytical_results"][buf] = applied
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
                results["screenshots"][buf] = shot
                if oracle_fn is not None and oracle_fn(shot, buf):
                    results["min_seam_free_buffer"] = buf
                    break
    finally:
        # Restore each scratch appearance's bitmap to its pre-calibration
        # source, and restore body.appearance to whatever it was before.
        # We do NOT delete the per-body appearance copies — that's an
        # explicit caller responsibility, since they may want to keep the
        # converged result. They can `design.appearances.itemByName(...).deleteMe()`
        # afterwards using the names in `results["scratch_appearances"]`.
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
