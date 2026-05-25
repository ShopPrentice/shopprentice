import adsk.core
import adsk.fusion
import math
import os as _os

Point3D = adsk.core.Point3D

_SPECIES_MAP = {
    "cherry":      ["Cherry"],
    "walnut":      ["Walnut"],
    "oak":         ["Oak"],
    "white oak":   ["Oak"],
    "red oak":     ["Oak"],
    "maple":       ["Maple", "Oak"],
    "ash":         ["Ash", "Oak"],
    "birch":       ["Birch", "Oak"],
    "pine":        ["Pine"],
    "cedar":       ["Cedar", "Pine"],
    "mahogany":    ["Mahogany"],
    "teak":        ["Teak", "Mahogany"],
    "beech":       ["Beech", "Oak"],
    "poplar":      ["Poplar", "Oak"],
    "hickory":     ["Hickory", "Oak"],
    "ebony":       ["Ebony", "Walnut"],
    "rosewood":    ["Rosewood", "Walnut"],
    "sapele":      ["Sapele", "Mahogany"],
    "bamboo":      ["Bamboo"],
    "douglas fir": ["Douglas Fir", "Pine"],
}

_SPECIES_TEXTURE = {
    "teak":              {"base": "Mahogany", "texture": "teak.jpg",
                          "scale_x": 9.9, "scale_y": 20.1, "natural_unit": "in",
                          "px_w": 3120, "px_h": 6320,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in",
                          "eg_px_w": 2080, "eg_px_h": 620},
    "teak a":            {"base": "Mahogany", "texture": "teak_a.jpg",
                          "scale_x": 15.8, "scale_y": 60.3, "natural_unit": "in",
                          "px_w": 800, "px_h": 2902,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "teak b":            {"base": "Mahogany", "texture": "teak_b.jpg",
                          "scale_x": 13.9, "scale_y": 89.2, "natural_unit": "in",
                          "px_w": 544, "px_h": 3260,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "teak c":            {"base": "Mahogany", "texture": "teak_c.jpg",
                          "scale_x": 11.5, "scale_y": 77.0, "natural_unit": "in",
                          "px_w": 526, "px_h": 3310,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "teak d":            {"base": "Mahogany", "texture": "teak_d.jpg",
                          "scale_x": 10.1, "scale_y": 62.9, "natural_unit": "in",
                          "px_w": 508, "px_h": 3070,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "teak e":            {"base": "Mahogany", "texture": "teak_e.jpg",
                          "scale_x": 11.8701, "scale_y": 67.6785, "natural_unit": "in",
                          "px_w": 1856, "px_h": 10362,
                          "reflectance": 0.035,
                          "endgrain": "teak_endgrain.jpg",
                          "eg_scale_x": 5.9, "eg_scale_y": 1.8,
                          "eg_natural_unit": "in"},
    "brazilian rosewood": {"base": "Walnut",  "texture": "brazilian_rosewood.jpg",
                          "scale_x": 8.1, "scale_y": 19.8, "reflectance": 0.06,
                          "endgrain": "brazilian_rosewood_endgrain.jpg",
                          "eg_scale_x": 6.0, "eg_scale_y": 1.9},
    "cocobolo":          {"base": "Walnut",   "texture": "cocobolo.jpg",
                          "scale_x": 9.8, "scale_y": 20.8, "reflectance": 0.07,
                          "endgrain": "cocobolo_endgrain.jpg",
                          "eg_scale_x": 6.0, "eg_scale_y": 1.3},
    "ziricote":          {"base": "Walnut",   "texture": "ziricote.jpg",
                          "scale_x": 9.0, "scale_y": 23.9, "reflectance": 0.05,
                          "endgrain": "ziricote_endgrain.jpg",
                          "eg_scale_x": 6.0, "eg_scale_y": 2.1},
    "spalted maple":     {"base": "Pine",     "texture": "spalted_maple.jpg",
                          "scale_x": 9.1, "scale_y": 17.8, "reflectance": 0.025,
                          "endgrain": "spalted_maple_endgrain.jpg",
                          "eg_scale_x": 6.7, "eg_scale_y": 5.2},
}

# helpers/sp/appearance.py → repo root is 3 levels up
_TEXTURE_DIR = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
    "textures", "wood"
)

_CM_TO_TEX_IN = 1.0 / 2.54


def _jpeg_dimensions(path):
    """Read pixel dimensions from a JPEG file header (no PIL dependency).
    Returns (width, height) or (None, None) if unreadable."""
    import struct as _struct
    try:
        with open(path, "rb") as f:
            f.read(2)  # SOI marker
            while True:
                marker = f.read(2)
                if len(marker) < 2:
                    return None, None
                if marker[0] != 0xFF:
                    return None, None
                if marker[1] in (0xC0, 0xC1, 0xC2):  # SOF markers
                    f.read(3)  # length + precision
                    h = _struct.unpack(">H", f.read(2))[0]
                    w = _struct.unpack(">H", f.read(2))[0]
                    return w, h
                else:
                    length = _struct.unpack(">H", f.read(2))[0]
                    f.read(length - 2)
    except Exception:
        return None, None


def _get_px_dims(cfg):
    """Return (px_w, px_h) for a species config. Uses cfg["px_w"]/["px_h"]
    if present, otherwise auto-detects from the JPEG file on disk."""
    px_w = cfg.get("px_w")
    px_h = cfg.get("px_h")
    if px_w and px_h:
        return px_w, px_h
    tex_path = _os.path.join(_TEXTURE_DIR, cfg.get("texture", ""))
    if _os.path.isfile(tex_path):
        w, h = _jpeg_dimensions(tex_path)
        if w and h:
            return w, h
    return None, None


def _natural_size_cm(cfg, axis, eg=False):
    """Return cfg["scale_<axis>"] (or eg_scale_<axis>) converted to cm
    based on cfg["natural_unit"] (or eg_natural_unit). Default unit cm."""
    if eg:
        val = cfg.get(f"eg_scale_{axis}", 0)
        unit = cfg.get("eg_natural_unit", cfg.get("natural_unit", "cm"))
    else:
        val = cfg.get(f"scale_{axis}", 0)
        unit = cfg.get("natural_unit", "cm")
    if unit == "in":
        return val * 2.54
    return val


def fit_scale_y_cm(body, species_key,
                    ppi_threshold_per_cm=20.0, seam_buffer=0.05):
    """Per-body compress-fit rule for the grain-direction (scale_y) period.

    Thin wrapper that reads body bbox + species cfg and delegates to
    `box_diagnostic.recommend_period_cm()` for the actual rule.

    Args:
        body: Fusion BRepBody — bbox is read for grain extent.
        species_key: key into _SPECIES_TEXTURE (must have px_h field).
        ppi_threshold_per_cm: pixel-per-cm density above which the image
            is considered sharp enough at natural size. Default 20 px/cm.
        seam_buffer: extra fraction added to body length when compressing.

    Returns:
        Recommended scale_y in cm (or natural cm if rule doesn't apply).
    """
    cfg = _SPECIES_TEXTURE.get(species_key)
    if not cfg:
        return None
    natural_cm = _natural_size_cm(cfg, "y")
    if natural_cm <= 0:
        return natural_cm
    _, px_h = _get_px_dims(cfg)
    if not px_h:
        return natural_cm
    bb = body.boundingBox
    body_grain_cm = max(bb.maxPoint.x - bb.minPoint.x,
                         bb.maxPoint.y - bb.minPoint.y,
                         bb.maxPoint.z - bb.minPoint.z)
    ppi = px_h / natural_cm
    from helpers import box_diagnostic
    period_cm, _rule = box_diagnostic.recommend_period_cm(
        body_grain_cm, natural_cm, ppi,
        ppi_threshold=ppi_threshold_per_cm,
        seam_buffer=seam_buffer)
    return period_cm


def _apply_custom_texture(local_appearance, species_key, body=None, _force=False):
    """Swap texture bitmap and tune properties for a custom species.

    Args:
        local_appearance: Design-local copy of a Fusion appearance.
        species_key: Key into _SPECIES_TEXTURE.
        body: Optional BRepBody. When provided, the per-body fit rule
            (fit_scale_y_cm) is applied to scale_y instead of the natural
            value.

    Returns:
        True if texture was applied, False if texture file not found.

    Safety: refuses to modify an appearance that is currently assigned to
    more than one body in the active design.
    """
    if _force:
        pass
    else:
      try:
        _guard_app = adsk.core.Application.get()
        _guard_design = adsk.fusion.Design.cast(_guard_app.activeProduct)
        if _guard_design:
            ref_count = 0
            def _count_refs(comp):
                nonlocal ref_count
                for i in range(comp.bRepBodies.count):
                    b = comp.bRepBodies.item(i)
                    try:
                        if b.appearance and b.appearance.name == local_appearance.name:
                            ref_count += 1
                            if ref_count > 1:
                                return
                    except Exception:
                        pass
                for i in range(comp.occurrences.count):
                    _count_refs(comp.occurrences.item(i).component)
                    if ref_count > 1:
                        return
            _count_refs(_guard_design.rootComponent)
            if ref_count > 1:
                raise ValueError(
                    f"Refusing to modify '{local_appearance.name}' — "
                    f"it is referenced by {ref_count} bodies. "
                    f"Use sp.per_body_appearance(body, species_key) to get "
                    f"a safe per-body copy first.")
      except ValueError:
          raise
      except Exception:
          pass

    cfg = _SPECIES_TEXTURE[species_key]
    tex_path = _os.path.join(_TEXTURE_DIR, cfg["texture"])
    if not _os.path.isfile(tex_path):
        return False

    props = local_appearance.appearanceProperties
    cp = adsk.core.ColorProperty.cast(props.itemById("opaque_albedo"))
    if not cp or not cp.hasConnectedTexture:
        return False

    tex = cp.connectedTexture

    bmp = tex.properties.itemById("unifiedbitmap_Bitmap")
    if bmp:
        fp = adsk.core.FilenameProperty.cast(bmp)
        if fp and not fp.isReadOnly:
            fp.value = tex_path

    sx_cm = _natural_size_cm(cfg, "x")
    if body is not None:
        sy_cm = fit_scale_y_cm(body, species_key)
    else:
        sy_cm = _natural_size_cm(cfg, "y")
    sx_prop = tex.properties.itemById("texture_RealWorldScaleX")
    sy_prop = tex.properties.itemById("texture_RealWorldScaleY")
    if sx_prop and sx_cm:
        adsk.core.FloatProperty.cast(sx_prop).value = sx_cm * _CM_TO_TEX_IN
    if sy_prop and sy_cm:
        adsk.core.FloatProperty.cast(sy_prop).value = sy_cm * _CM_TO_TEX_IN

    if cfg.get("reflectance"):
        f0 = props.itemById("opaque_f0")
        if f0:
            adsk.core.FloatProperty.cast(f0).value = cfg["reflectance"]

    return True


def per_body_appearance(body, species_key):
    """Get (or create) a per-body appearance for this specific body.

    Copies from the Fusion material library base directly -- no shared
    SP_<species> intermediate is created or modified.

    Naming convention: SP_<species>_<comp>_<body.name>

    Args:
        body: adsk.fusion.BRepBody
        species_key: key into _SPECIES_TEXTURE (e.g. "teak b")

    Returns:
        The per-body appearance (adsk.core.Appearance), already assigned
        to body.appearance and with the species texture applied.
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    cfg = _SPECIES_TEXTURE.get(species_key)
    if not cfg:
        raise ValueError(f"Unknown species: {species_key!r}")

    comp_name = body.parentComponent.name if body.parentComponent else "root"
    local_name = f"SP_{species_key}_{comp_name}_{body.name}"
    local = design.appearances.itemByName(local_name)
    if not local:
        base_name = cfg.get("base", "Mahogany")
        base_app = None
        libs = app.materialLibraries
        for li in range(libs.count):
            lib = libs.item(li)
            for ai in range(lib.appearances.count):
                a = lib.appearances.item(ai)
                if a.name == base_name and not a.name.startswith("3D "):
                    if "appearance" in lib.name.lower():
                        base_app = a
                        break
                    if base_app is None:
                        base_app = a
            if base_app and "appearance" in lib.name.lower():
                break
        if base_app is None:
            raise RuntimeError(
                f"Cannot create appearance for '{species_key}': "
                f"base '{base_name}' not found in material libraries")
        local = design.appearances.addByCopy(base_app, local_name)

    _apply_custom_texture(local, species_key)
    body.appearance = local
    return local


def _apply_endgrain_texture(local_appearance, species_key):
    """Swap texture bitmap for an end grain appearance."""
    cfg = _SPECIES_TEXTURE[species_key]
    eg_file = cfg.get("endgrain")
    if not eg_file:
        return False
    tex_path = _os.path.join(_TEXTURE_DIR, eg_file)
    if not _os.path.isfile(tex_path):
        return False

    props = local_appearance.appearanceProperties
    cp = adsk.core.ColorProperty.cast(props.itemById("opaque_albedo"))
    if not cp or not cp.hasConnectedTexture:
        return False

    tex = cp.connectedTexture

    bmp = tex.properties.itemById("unifiedbitmap_Bitmap")
    if bmp:
        fp = adsk.core.FilenameProperty.cast(bmp)
        if fp and not fp.isReadOnly:
            fp.value = tex_path

    sx_cm = _natural_size_cm(cfg, "x", eg=True)
    sy_cm = _natural_size_cm(cfg, "y", eg=True)
    sx_prop = tex.properties.itemById("texture_RealWorldScaleX")
    sy_prop = tex.properties.itemById("texture_RealWorldScaleY")
    if sx_prop and sx_cm:
        adsk.core.FloatProperty.cast(sx_prop).value = sx_cm * _CM_TO_TEX_IN
    if sy_prop and sy_cm:
        adsk.core.FloatProperty.cast(sy_prop).value = sy_cm * _CM_TO_TEX_IN

    if cfg.get("reflectance"):
        f0 = props.itemById("opaque_f0")
        if f0:
            adsk.core.FloatProperty.cast(f0).value = cfg["reflectance"]

    return True


def _grain_axis(body):
    """Grain direction = longest bounding box axis (name string)."""
    bb = body.boundingBox
    dims = {
        "x": abs(bb.maxPoint.x - bb.minPoint.x),
        "y": abs(bb.maxPoint.y - bb.minPoint.y),
        "z": abs(bb.maxPoint.z - bb.minPoint.z),
    }
    return max(dims, key=dims.get)


def _grain_vector(body):
    """Compute grain direction as a unit vector using principal axes of inertia.

    The axis with the smallest moment of inertia is the elongation axis
    (grain direction).  Works for any orientation.

    Falls back to bounding-box longest axis if the API call fails.
    """
    try:
        pp = body.physicalProperties
        ok_ax, ax_x, ax_y, ax_z = pp.getPrincipalAxes()
        ok_mo, mx, my, mz = pp.getPrincipalMomentsOfInertia()
        if ok_ax and ok_mo:
            axes = [(mx, ax_x), (my, ax_y), (mz, ax_z)]
            axes.sort(key=lambda a: a[0])
            g = axes[0][1]
            vx, vy, vz = g.x, g.y, g.z
            comps = [("x", abs(vx)), ("y", abs(vy)), ("z", abs(vz))]
            dominant = max(comps, key=lambda c: c[1])[0]
            if (dominant == "x" and vx < 0) or \
               (dominant == "y" and vy < 0) or \
               (dominant == "z" and vz < 0):
                vx, vy, vz = -vx, -vy, -vz
            return adsk.core.Vector3D.create(vx, vy, vz)
    except Exception:
        pass

    axis = _grain_axis(body)
    v = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[axis]
    return adsk.core.Vector3D.create(*v)


def _find_endgrain_faces(body, grain_vec):
    """Find faces whose normals are parallel to the grain direction (end grain).

    grain_vec: Vector3D or axis name string (backward compat).
    """
    if isinstance(grain_vec, str):
        gv = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[grain_vec]
        grain_vec = adsk.core.Vector3D.create(*gv)
    endgrain_faces = []
    for i in range(body.faces.count):
        face = body.faces.item(i)
        geom = face.geometry
        if isinstance(geom, adsk.core.Plane):
            n = geom.normal
            dot = abs(n.x * grain_vec.x + n.y * grain_vec.y + n.z * grain_vec.z)
            if dot > 0.85:
                endgrain_faces.append(face)
    return endgrain_faces


def _grain_transform(grain_dir):
    """Rotate texture so grain (texture Y) aligns with grain direction.

    grain_dir: axis name string ("x"/"y"/"z") or Vector3D for arbitrary angles.
    """
    m = adsk.core.Matrix3D.create()
    if isinstance(grain_dir, str):
        if grain_dir == "x":
            m.setToRotation(math.pi / 2, adsk.core.Vector3D.create(0, 1, 0),
                            Point3D.create(0, 0, 0))
        elif grain_dir == "y":
            m.setToRotation(-math.pi / 2, adsk.core.Vector3D.create(1, 0, 0),
                            Point3D.create(0, 0, 0))
    else:
        z_axis = adsk.core.Vector3D.create(0, 0, 1)
        angle = z_axis.angleTo(grain_dir)
        if angle > 0.001 and angle < math.pi - 0.001:
            cross = z_axis.crossProduct(grain_dir)
            if cross.length > 0.001:
                cross.normalize()
                m.setToRotation(angle, cross, Point3D.create(0, 0, 0))
        elif angle >= math.pi - 0.001:
            m.setToRotation(math.pi, adsk.core.Vector3D.create(0, 1, 0),
                            Point3D.create(0, 0, 0))
    return m


def apply_appearance(species="white oak", bodies=None):
    """Apply wood appearance to bodies with grain-aligned texture.

    Call at the end of a script, after all geometry is built.

    Args:
        species: Wood species name (e.g. "cherry", "walnut", "white oak").
                 Falls back to a similar species if exact match unavailable.
        bodies: Optional list of body name strings. If None, applies to ALL
                bodies. Use for multi-species designs.

    Usage:
        sp.apply_appearance("walnut")
        sp.apply_appearance("white oak", bodies=["Seat"])
        sp.apply_appearance("teak", bodies=["Leg_FL","Leg_FR"])
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    species_lower = species.lower().strip()

    custom_tex = species_lower in _SPECIES_TEXTURE
    if custom_tex:
        cfg = _SPECIES_TEXTURE[species_lower]
        base_name = cfg["base"]
        local_name = f"SP_{species_lower}"
        local = design.appearances.itemByName(local_name)
        if not local:
            base_app = None
            libs = app.materialLibraries
            for li in range(libs.count):
                lib = libs.item(li)
                for ai in range(lib.appearances.count):
                    a = lib.appearances.item(ai)
                    if a.name == base_name and not a.name.startswith("3D "):
                        if "appearance" in lib.name.lower():
                            base_app = a
                            break
                        if base_app is None:
                            base_app = a
                if base_app and "appearance" in lib.name.lower():
                    break
            if base_app is None:
                print(f"WARNING: Base appearance '{base_name}' not found "
                      f"for custom species '{species}'")
                return
            local = design.appearances.addByCopy(base_app, local_name)
        if not _apply_custom_texture(local, species_lower, _force=True):
            print(f"WARNING: Texture file not found for '{species}' "
                  f"— using base {base_name}. "
                  f"Place {cfg['texture']} in textures/wood/")
    else:
        search_terms = _SPECIES_MAP.get(species_lower, [species])
        appearance = None
        for term in search_terms:
            for i in range(design.appearances.count):
                a = design.appearances.item(i)
                if term.lower() in a.name.lower() and not a.name.startswith("3D "):
                    appearance = a
                    break
            if appearance:
                break
            libs = app.materialLibraries
            for li in range(libs.count):
                lib = libs.item(li)
                for ai in range(lib.appearances.count):
                    a = lib.appearances.item(ai)
                    if term.lower() in a.name.lower():
                        if a.name.startswith("3D "):
                            continue
                        if "appearance" in lib.name.lower():
                            appearance = a
                            break
                        if appearance is None:
                            appearance = a
                if appearance and "appearance" in lib.name.lower():
                    break
            if appearance:
                break

        if appearance is None:
            print(f"WARNING: No appearance found for '{species}'")
            return

        local = design.appearances.itemByName(appearance.name)
        if not local:
            local = design.appearances.addByCopy(appearance, appearance.name)

    def all_bodies_recursive(comp):
        result = []
        for i in range(comp.bRepBodies.count):
            result.append(comp.bRepBodies.item(i))
        for i in range(comp.occurrences.count):
            result.extend(all_bodies_recursive(comp.occurrences.item(i).component))
        return result

    target_bodies = all_bodies_recursive(root)
    if bodies is not None:
        name_set = set(bodies)
        target_bodies = [b for b in target_bodies if b.name in name_set]

    eg_local = None
    if custom_tex and _SPECIES_TEXTURE[species_lower].get("endgrain"):
        eg_name = f"SP_{species_lower}_endgrain"
        eg_local = design.appearances.itemByName(eg_name)
        if not eg_local:
            base_app = None
            libs = app.materialLibraries
            cfg = _SPECIES_TEXTURE[species_lower]
            for li in range(libs.count):
                lib = libs.item(li)
                for ai in range(lib.appearances.count):
                    a = lib.appearances.item(ai)
                    if a.name == cfg["base"] and not a.name.startswith("3D "):
                        if "appearance" in lib.name.lower():
                            base_app = a
                            break
                        if base_app is None:
                            base_app = a
                if base_app and "appearance" in lib.name.lower():
                    break
            if base_app:
                eg_local = design.appearances.addByCopy(base_app, eg_name)
        if eg_local:
            _apply_endgrain_texture(eg_local, species_lower)

    count = 0
    eg_count = 0
    for body in target_bodies:
        try:
            body.appearance = local
            grain_vec = _grain_vector(body)
            adsk.doEvents()
            tmc = body.textureMapControl
            if tmc:
                ptmc = adsk.core.ProjectedTextureMapControl.cast(tmc)
                if ptmc:
                    ptmc.projectedTextureMapType = (
                        adsk.core.ProjectedTextureMapTypes
                        .BoxTextureMapProjection)
                    ptmc.transform = _grain_transform(grain_vec)
            count += 1

            if eg_local:
                for face in _find_endgrain_faces(body, grain_vec):
                    face.appearance = eg_local
                    eg_count += 1
        except Exception:
            pass

    msg = f"Applied {local.name} to {count} bodies"
    if eg_count:
        msg += f" ({eg_count} end grain faces)"
    print(msg)
