"""Sketch mixin: sketch + construction plane emission, coordinate transforms."""


class _SketchMixin:
    """Feature emitters for sketches, construction planes, and sketch helpers."""

    def _feat_constructionplane(self, f):
        name = f.get("name", "Plane")
        comp_name = f.get("component", "")
        # Use component-suffixed variable name to prevent collisions
        # when multiple components have planes with the same name
        if comp_name and comp_name != self._root_name:
            var = self._var(f"{name}_{comp_name}")
        else:
            var = self._var(name)

        if f.get("definitionType") == "Offset":
            expr = f.get("offset", "0 cm")
            base = f.get("basePlane", "")
            base_map = {
                "XY": "comp.xYConstructionPlane",
                "XZ": "comp.xZConstructionPlane",
                "YZ": "comp.yZConstructionPlane",
            }
            if base in base_map:
                base_code = base_map[base]
            elif base in self.planes:
                base_code = self.planes[base]
            elif base.startswith("adsk::fusion::BRepFace"):
                # BRepFace base — use the captured origin + normal to determine
                # the plane position and offset from a standard plane.
                origin = f.get("origin", [0, 0, 0])
                normal = f.get("normal", [0, 0, 1])
                ax, ay, az = abs(normal[0]), abs(normal[1]), abs(normal[2])
                if az > 0.9:
                    base_code = "comp.xYConstructionPlane"
                    # Offset = origin Z (the face position minus expr adjusts)
                    expr = f"{round(origin[2], 4)} cm"
                elif ay > 0.9:
                    base_code = "comp.xZConstructionPlane"
                    expr = f"{round(origin[1], 4)} cm"
                elif ax > 0.9:
                    base_code = "comp.yZConstructionPlane"
                    expr = f"{round(origin[0], 4)} cm"
                else:
                    base_code = "comp.xYConstructionPlane"
                    expr = "0 cm"
                self._c(f"BRepFace base → computed offset from origin {origin}")
            else:
                self._c(f'TODO: unknown base plane "{base}", using XY')
                base_code = "root.xYConstructionPlane"
            self._w(f'{var} = off_plane(comp, {base_code}, "{expr}", "{name}")')
        elif f.get("definitionType") == "AtAngle":
            # At-angle plane: rotated from a base plane around an edge/line
            angle_expr = f.get("angle", "0 deg")
            base = f.get("basePlane", "")
            linear = f.get("linearEntity", {})
            base_map = {
                "XY": "comp.xYConstructionPlane",
                "XZ": "comp.xZConstructionPlane",
                "YZ": "comp.yZConstructionPlane",
            }
            if base in base_map:
                base_code = base_map[base]
            elif base in self.planes:
                base_code = self.planes[base]
            elif not base:
                # No base captured — infer from target normal + rotation axis.
                # For setByAngle: base_normal × target_normal ∥ rotation_axis
                # (the rotation axis is perpendicular to both normals).
                normal = f.get("normal", [0, 0, 1])
                # Compute rotation axis direction from linear entity
                lin = f.get("linearEntity", {})
                rot_dir = None
                if lin.get("type") == "SketchLine" and lin.get("parentSketch"):
                    sk_name = lin["parentSketch"]
                    sk_feat = None
                    for tf in self.cap.get("timeline", []):
                        if tf.get("type") == "Sketch" and tf.get("name") == sk_name:
                            sk_feat = tf
                            break
                    if sk_feat and sk_feat.get("sketchOrigin") and sk_feat.get("sketchXDir") and sk_feat.get("sketchYDir"):
                        o = sk_feat["sketchOrigin"]
                        xd = sk_feat["sketchXDir"]
                        yd = sk_feat["sketchYDir"]
                        sv = lin.get("start", [0, 0, 0])
                        ev = lin.get("end", [0, 0, 0])
                        s3 = [o[i] + sv[0]*xd[i] + sv[1]*yd[i] for i in range(3)]
                        e3 = [o[i] + ev[0]*xd[i] + ev[1]*yd[i] for i in range(3)]
                        dx = e3[0]-s3[0]; dy = e3[1]-s3[1]; dz = e3[2]-s3[2]
                        dl = (dx*dx + dy*dy + dz*dz)**0.5
                        if dl > 0.001:
                            rot_dir = [dx/dl, dy/dl, dz/dl]
                if rot_dir:
                    # Score each standard plane: cross(std_normal, target_normal)
                    # should be parallel to rot_dir.
                    std_planes = [
                        ("comp.xYConstructionPlane", [0, 0, 1]),
                        ("comp.xZConstructionPlane", [0, 1, 0]),
                        ("comp.yZConstructionPlane", [1, 0, 0]),
                    ]
                    best_code, best_score = "comp.xYConstructionPlane", -1
                    for code, sn in std_planes:
                        # cross product of std_normal × target_normal
                        cx = sn[1]*normal[2] - sn[2]*normal[1]
                        cy = sn[2]*normal[0] - sn[0]*normal[2]
                        cz = sn[0]*normal[1] - sn[1]*normal[0]
                        cl = (cx*cx + cy*cy + cz*cz)**0.5
                        if cl < 0.001:
                            continue  # parallel normals, 0° rotation
                        # alignment: |dot(cross, rot_dir)| / |cross|
                        dot = abs(cx*rot_dir[0] + cy*rot_dir[1] + cz*rot_dir[2])
                        score = dot / cl
                        if score > best_score:
                            best_score = score
                            best_code = code
                    base_code = best_code
                else:
                    # Fallback: pick by dominant normal component
                    ax, ay, az = abs(normal[0]), abs(normal[1]), abs(normal[2])
                    if az >= ay and az >= ax:
                        base_code = "comp.xYConstructionPlane"
                    elif ay >= ax:
                        base_code = "comp.xZConstructionPlane"
                    else:
                        base_code = "comp.yZConstructionPlane"
                self._c(f"No base plane captured — inferred from normal + axis")
            else:
                base_code = "comp.xYConstructionPlane"
            # Resolve the linear entity (edge to rotate around)
            lin_type = linear.get("type", "")
            if lin_type == "BRepEdge":
                body_name = linear.get("body", "")
                sv = linear.get("start", [0, 0, 0])
                ev = linear.get("end", [0, 0, 0])
                bv = self._body_ref(body_name)
                self._w(f"_angle_edge = None")
                self._w(f"for _ei in range({bv}.edges.count):")
                self.ind += 1
                self._w(f"_e = {bv}.edges.item(_ei)")
                self._w(f"_sv, _ev = _e.startVertex.geometry, _e.endVertex.geometry")
                self._w(f"if ((abs(_sv.x-{sv[0]:.4f})+abs(_sv.y-{sv[1]:.4f})+abs(_sv.z-{sv[2]:.4f}) < 0.1 and")
                self._w(f"    abs(_ev.x-{ev[0]:.4f})+abs(_ev.y-{ev[1]:.4f})+abs(_ev.z-{ev[2]:.4f}) < 0.1) or")
                self._w(f"   (abs(_sv.x-{ev[0]:.4f})+abs(_sv.y-{ev[1]:.4f})+abs(_sv.z-{ev[2]:.4f}) < 0.1 and")
                self._w(f"    abs(_ev.x-{sv[0]:.4f})+abs(_ev.y-{sv[1]:.4f})+abs(_ev.z-{sv[2]:.4f}) < 0.1)):")
                self.ind += 1
                self._w(f"_angle_edge = _e; break")
                self.ind -= 2
                line_code = "_angle_edge"
            elif lin_type == "SketchLine":
                sk_name = linear.get("parentSketch", "")
                sv = linear.get("start", [0, 0, 0])
                ev = linear.get("end", [0, 0, 0])
                sk_var = self.sketches.get(sk_name)
                if sk_var:
                    # Convert captured 2D sketch coords to 3D world coords
                    # using the parent sketch's captured axes/origin
                    sk_feat = None
                    for tf in self.cap.get("timeline", []):
                        if tf.get("type") == "Sketch" and tf.get("name") == sk_name:
                            sk_feat = tf
                            break
                    use_world = False
                    if sk_feat and sk_feat.get("sketchOrigin") and sk_feat.get("sketchXDir") and sk_feat.get("sketchYDir"):
                        o = sk_feat["sketchOrigin"]
                        xd = sk_feat["sketchXDir"]
                        yd = sk_feat["sketchYDir"]
                        s3d = [o[i] + sv[0]*xd[i] + sv[1]*yd[i] for i in range(3)]
                        e3d = [o[i] + ev[0]*xd[i] + ev[1]*yd[i] for i in range(3)]
                        use_world = True
                    self._w(f"_angle_line = None")
                    self._w(f"for _ci in range({sk_var}.sketchCurves.count):")
                    self.ind += 1
                    self._w(f"_c = {sk_var}.sketchCurves.item(_ci)")
                    self._w(f"_sl = adsk.fusion.SketchLine.cast(_c)")
                    self._w(f"if _sl:")
                    self.ind += 1
                    if use_world:
                        self._w(f"_s, _e = _sl.startSketchPoint.worldGeometry, _sl.endSketchPoint.worldGeometry")
                        self._w(f"if (abs(_s.x-{s3d[0]:.4f})+abs(_s.y-{s3d[1]:.4f})+abs(_s.z-{s3d[2]:.4f}) < 0.1 and "
                                f"abs(_e.x-{e3d[0]:.4f})+abs(_e.y-{e3d[1]:.4f})+abs(_e.z-{e3d[2]:.4f}) < 0.1) or "
                                f"(abs(_s.x-{e3d[0]:.4f})+abs(_s.y-{e3d[1]:.4f})+abs(_s.z-{e3d[2]:.4f}) < 0.1 and "
                                f"abs(_e.x-{s3d[0]:.4f})+abs(_e.y-{s3d[1]:.4f})+abs(_e.z-{s3d[2]:.4f}) < 0.1):")
                    else:
                        self._w(f"_s, _e = _sl.startSketchPoint.geometry, _sl.endSketchPoint.geometry")
                        self._w(f"if (abs(_s.x-{sv[0]:.4f})+abs(_s.y-{sv[1]:.4f}) < 0.1 and "
                                f"abs(_e.x-{ev[0]:.4f})+abs(_e.y-{ev[1]:.4f}) < 0.1) or "
                                f"(abs(_s.x-{ev[0]:.4f})+abs(_e.y-{ev[1]:.4f}) < 0.1 and "
                                f"abs(_e.x-{sv[0]:.4f})+abs(_e.y-{sv[1]:.4f}) < 0.1):")
                    self.ind += 1
                    self._w(f"_angle_line = _sl; break")
                    self.ind -= 3
                    line_code = "_angle_line"
                else:
                    line_code = "comp.xConstructionAxis"
                    self._c(f"TODO: sketch '{sk_name}' not found for AtAngle line")
            elif lin_type == "ConstructionAxis":
                axis_name = linear.get("name", "")
                axis_map = {"X": "comp.xConstructionAxis", "Y": "comp.yConstructionAxis", "Z": "comp.zConstructionAxis"}
                line_code = axis_map.get(axis_name, f'comp.constructionAxes.itemByName("{axis_name}")')
            else:
                line_code = "comp.xConstructionAxis"
                self._c(f"TODO: unknown linear entity type '{lin_type}' for AtAngle plane")

            self._w(f"_pl_inp = comp.constructionPlanes.createInput()")
            self._w(f'_pl_inp.setByAngle({line_code}, adsk.core.ValueInput.createByString("{angle_expr}"), {base_code})')
            self._w(f"{var} = comp.constructionPlanes.add(_pl_inp)")
            self._w(f'{var}.name = "{name}"')

        elif f.get("definitionType") == "MidPlane":
            plane_one = f.get("planeOne", {})
            plane_two = f.get("planeTwo", {})
            p1_code = self._resolve_planar_entity(plane_one)
            p2_code = self._resolve_planar_entity(plane_two)
            self._w(f"_pl_inp = comp.constructionPlanes.createInput()")
            self._w(f"_pl_inp.setByTwoPlanes({p1_code}, {p2_code})")
            self._w(f"{var} = comp.constructionPlanes.add(_pl_inp)")
            self._w(f'{var}.name = "{name}"')

        elif f.get("origin") and f.get("normal"):
            # Non-offset, non-angle plane with known origin + normal.
            # Use offset from closest axis-aligned plane as approximation.
            # NOTE: The offset plane's normal direction may differ from the
            # original, but extrude direction is controlled by isDirectionFlipped
            # in the capture — no extra compensation needed here.
            origin = f["origin"]
            normal = f["normal"]
            ax, ay, az = abs(normal[0]), abs(normal[1]), abs(normal[2])
            if ax > 0.9:
                base_code = "comp.yZConstructionPlane"
                offset = origin[0]
            elif ay > 0.9:
                base_code = "comp.xZConstructionPlane"
                offset = origin[1]
            else:
                base_code = "comp.xYConstructionPlane"
                offset = origin[2]
            self._c(f"Approximation: origin={origin} normal={normal}")
            self._w(f'{var} = off_plane(comp, {base_code}, "{round(offset, 4)} cm", "{name}")')
        else:
            self._c(f"TODO: Non-offset plane (type={f.get('definitionType')})")
            self._w(f"{var} = None")
        self.planes[name] = var
        # Also register component-scoped key for disambiguation
        if comp_name:
            self.planes[f"{comp_name}:{name}"] = var
        # Track plane's owning component for cross-component proxy
        self._plane_comps[var] = comp_name or self._root_name

    @staticmethod
    def _sketch_entity_pt(entity_ref, curves):
        """Return (x, y) sketch coordinate for a dimension entity reference."""
        if not entity_ref or entity_ref.get("type") != "SketchPoint":
            return None
        ci = entity_ref.get("curveIndex")
        role = entity_ref.get("role")
        if ci is None or ci >= len(curves):
            return entity_ref.get("position")  # fallback
        c = curves[ci]
        if role == "start":
            return c.get("start")
        elif role == "end":
            return c.get("end")
        elif role == "center":
            return c.get("center")
        return None

    def _resolve_planar_entity(self, info):
        """Resolve a captured planar entity reference to a code expression."""
        if not info:
            return "comp.xYConstructionPlane"
        entity_type = info.get("type", "")
        if entity_type == "ConstructionPlane":
            name = info.get("name", "")
            std_map = {
                "XY": "comp.xYConstructionPlane",
                "XZ": "comp.xZConstructionPlane",
                "YZ": "comp.yZConstructionPlane",
            }
            if name in std_map:
                return std_map[name]
            if name in self.planes:
                return self.planes[name]
            return f'comp.constructionPlanes.itemByName("{name}")'
        elif entity_type == "BRepFace":
            body_name = info.get("body", "")
            pof = info.get("pointOnFace", [0, 0, 0])
            bv = self._body_ref(body_name)
            return f"find_face_near({bv}, {pof[0]}, {pof[1]}, {pof[2]})"
        return "comp.xYConstructionPlane"

    def _feat_sketch(self, f):
        name = f.get("name", "Sketch")
        comp_name = f.get("component", "")
        # Use component-suffixed variable name to prevent collisions
        if comp_name and comp_name != self._root_name:
            var = self._var(f"{name}_{comp_name}")
        else:
            var = self._var(name)
        self.sketches[name] = var
        if comp_name:
            self.sketches[f"{comp_name}:{name}"] = var
        curves = f.get("curves", [])
        dims = f.get("dimensions", [])
        # Tag ALL curves with original index for dimension/constraint resolution
        for ci, c in enumerate(curves):
            c["_origIdx"] = ci
        plane_info = f.get("plane", {})

        # Enrich BRepFace plane_info with computed normal/pointOnFace from sketch axes.
        # Always compute from sketch axes when available — the capture's pointOnFace
        # may be in root coordinates (from the original occurrence transform), but the
        # generator needs component-local coordinates for find_face_near on the
        # component body.  The enriched value from sketchOrigin + profile center
        # is always in the correct component-local space.
        if (plane_info.get("type") == "BRepFace"
                and f.get("sketchXDir") and f.get("sketchYDir") and f.get("sketchOrigin")):
            xd = f["sketchXDir"]
            yd = f["sketchYDir"]
            origin = f["sketchOrigin"]
            # normal = cross(xDir, yDir)
            plane_info["normal"] = [
                round(xd[1]*yd[2] - xd[2]*yd[1], 6),
                round(xd[2]*yd[0] - xd[0]*yd[2], 6),
                round(xd[0]*yd[1] - xd[1]*yd[0], 6),
            ]
            # Compute a point ON the face from the center of all profile bboxes
            # in world coords.  Using the first curve's midpoint is fragile —
            # it can land on a face boundary modified by a prior extrude,
            # causing find_face_near to pick the wrong face.  The profile-
            # region centroid is safely interior to the intended face.
            profiles = f.get("profiles", [])
            non_ref_curves = [c for c in curves if not c.get("isReference")]
            if profiles:
                # Use center of all profile bounding boxes
                # Profile bbox format: {"min": [x,y], "max": [x,y]} or
                # {"boundingBox": {"min": [x,y], "max": [x,y]}}
                def _pbbox(p):
                    bb = p.get("boundingBox", p)
                    return bb.get("min", [0, 0]), bb.get("max", [0, 0])
                all_min_x = min(_pbbox(p)[0][0] for p in profiles)
                all_max_x = max(_pbbox(p)[1][0] for p in profiles)
                all_min_y = min(_pbbox(p)[0][1] for p in profiles)
                all_max_y = max(_pbbox(p)[1][1] for p in profiles)
                mx = (all_min_x + all_max_x) / 2
                my = (all_min_y + all_max_y) / 2
                plane_info["pointOnFace"] = [
                    round(origin[0] + mx*xd[0] + my*yd[0], 4),
                    round(origin[1] + mx*xd[1] + my*yd[1], 4),
                    round(origin[2] + mx*xd[2] + my*yd[2], 4),
                ]
            elif non_ref_curves:
                # Fallback: center of all non-reference curves' endpoints
                all_sx = [c["start"][0] for c in non_ref_curves if c.get("start")]
                all_sy = [c["start"][1] for c in non_ref_curves if c.get("start")]
                all_ex = [c["end"][0] for c in non_ref_curves if c.get("end")]
                all_ey = [c["end"][1] for c in non_ref_curves if c.get("end")]
                all_x = all_sx + all_ex
                all_y = all_sy + all_ey
                if all_x and all_y:
                    mx = (min(all_x) + max(all_x)) / 2
                    my = (min(all_y) + max(all_y)) / 2
                    plane_info["pointOnFace"] = [
                        round(origin[0] + mx*xd[0] + my*yd[0], 4),
                        round(origin[1] + mx*xd[1] + my*yd[1], 4),
                        round(origin[2] + mx*xd[2] + my*yd[2], 4),
                    ]
                else:
                    plane_info["origin"] = origin
            else:
                plane_info["origin"] = origin

        # Determine sketch creation component.
        # BRepFace sketches in root → root (face access straightforward)
        # BRepFace sketches in child component → comp (extrude must be in same comp)
        # ConstructionPlane sketches → comp (plane is in the component;
        #   body projections use native component bodies)
        has_any_body_proj = any(
            c.get("projectedFrom", {}).get("type") == "BRepBody"
            for c in curves if c.get("isReference")
        )
        sketch_comp = "comp"
        if plane_info.get("type") == "BRepFace":
            # Only use root for sketches actually in root component.
            # Child component sketches must stay in comp so extrudes work.
            if not comp_name or comp_name == self._root_name:
                sketch_comp = "root"
        f["_sketch_comp"] = sketch_comp
        self._current_sketch_comp = sketch_comp

        # BRepFace sketches: strategy depends on geometry.
        # - Has auto-projected boundary + no explicit projections → find_face
        #   (avoids cplane CUT boundary issues, works for rect and non-rect)
        # - Has explicit projections (body edges) → cplane
        #   (avoids boundary coincidence, projections need sk.project)
        is_on_face = False
        if (plane_info.get("type") == "BRepFace"
                and "sketchOrigin" in f
                and "sketchXDir" in f
                and "sketchYDir" in f):
            non_ref = [c for c in curves if not c.get("isReference")]
            refs = [c for c in curves if c.get("isReference")]

            # Forward-reference check: if the face body hasn't been created yet
            # (e.g., sketch is the first feature in a new component), the body
            # face doesn't exist in the scratch doc.  Fall back to construction
            # plane at the sketch origin position.
            _fb = plane_info.get("body", "")
            _fc = f.get("component", "")
            _fwd_ref = False
            if _fc and _fb and _fc != self._root_name:
                _fk = f"{_fc}:{_fb}"
                # Only trigger cplane fallback when the body truly doesn't
                # exist yet — not when it's in a different component.
                _body_exists = (_fk in self.bodies
                                or _fb in self.bodies
                                or any(k.endswith(f":{_fb}")
                                       for k in self.bodies))
                if not _body_exists:
                    self._c(f"Forward ref: {_fb} not yet in {_fc} — cplane")
                    plane_code, curves = self._brep_face_to_cplane(f, curves)
                    # Remove face boundary refs — no face body on cplane
                    curves = [c for c in curves if not (
                        c.get("isReference")
                        and c.get("projectedFrom", {}).get("type") == "BRepFace"
                    )]
                    # _brep_face_to_cplane already transformed curve coords
                    # to the cplane's standard axes. Set _coord_transform to
                    # match the cplane axes (not the original face axes).
                    xd = f.get("sketchXDir", [1, 0, 0])
                    yd = f.get("sketchYDir", [0, 1, 0])
                    fn = [xd[1]*yd[2]-xd[2]*yd[1],
                          xd[2]*yd[0]-xd[0]*yd[2],
                          xd[0]*yd[1]-xd[1]*yd[0]]
                    ax, ay, az = abs(fn[0]), abs(fn[1]), abs(fn[2])
                    if az >= ay and az >= ax:
                        cp_xd, cp_yd = [1, 0, 0], [0, 1, 0]
                        cp_off = f.get("sketchOrigin", [0, 0, 0])[2]
                        cp_origin = [0, 0, cp_off]
                    elif ay >= ax:
                        cp_xd, cp_yd = [1, 0, 0], [0, 0, 1]
                        cp_off = f.get("sketchOrigin", [0, 0, 0])[1]
                        cp_origin = [0, cp_off, 0]
                    else:
                        cp_xd, cp_yd = [0, 1, 0], [0, 0, 1]
                        cp_off = f.get("sketchOrigin", [0, 0, 0])[0]
                        cp_origin = [cp_off, 0, 0]
                    f["_coord_transform"] = {
                        "cap_xdir": cp_xd,
                        "cap_ydir": cp_yd,
                        "cap_origin": cp_origin,
                    }
                    # Check if the cplane normal is opposite to the original
                    # face normal — extrudes need their direction flipped.
                    if az >= ay and az >= ax:
                        if fn[2] < 0:
                            f["_cplane_extrude_flip"] = True
                    elif ay >= ax:
                        if fn[1] < 0:
                            f["_cplane_extrude_flip"] = True
                    else:
                        if fn[0] < 0:
                            f["_cplane_extrude_flip"] = True
                    _fwd_ref = True

            self._brep_face_sketches[name] = plane_info
            has_body_proj = any(
                c.get("projectedFrom", {}).get("type") == "BRepBody"
                for c in refs
            )
            has_edge_proj = any(
                c.get("projectedFrom", {}).get("type") == "BRepEdge"
                for c in refs
            )
            if _fwd_ref:
                pass  # already handled via cplane above
            elif has_body_proj:
                # Body projections: use find_face for accurate intersection
                # geometry on beveled/tapered faces.
                plane_code = self._resolve_plane(plane_info)
                # Filter only the auto-boundary refs (BRepFace type), keep body proj refs.
                # Deep-copy dicts so Y-flip doesn't mutate feat["curves"].
                curves = [dict(c) for c in curves if not (
                    c.get("isReference") and
                    c.get("projectedFrom", {}).get("type") == "BRepFace"
                )]
                # Runtime coordinate transform: the reconstructed sketch may
                # have different axes than the original (rotation/reflection).
                # Store the captured axes so _emit_raw_sketch can emit the
                # transform function and wrap all drawn-curve coordinates.
                f["_coord_transform"] = {
                    "cap_xdir": f.get("sketchXDir", [1, 0, 0]),
                    "cap_ydir": f.get("sketchYDir", [0, 1, 0]),
                    "cap_origin": f.get("sketchOrigin"),
                }
                is_on_face = True
            elif refs and not has_edge_proj:
                # Auto-boundary refs from the face body are auto-projected.
                # Cross-body BRepFace refs (e.g., Body4 intersecting scarf1's
                # face) are NOT reliably auto-projected — convert them to
                # explicit intersectWithSketchPlane projections.
                plane_code = self._resolve_plane(plane_info)
                face_body_name = plane_info.get("body", "")
                new_curves = []
                for c_orig in curves:
                    d = dict(c_orig)
                    if d.get("isReference"):
                        pf = d.get("projectedFrom", {})
                        if pf.get("type") == "BRepFace":
                            body = pf.get("body", "")
                            if body == face_body_name or not body:
                                continue  # face body boundary — auto-projected
                            # Cross-body face ref → explicit intersection
                            d["projectedFrom"] = {
                                "type": "BRepBody",
                                "body": body,
                                "method": "intersect",
                            }
                    new_curves.append(d)
                curves = new_curves
                # NOTE: Do NOT set f["curves"] = curves here — dimension/constraint
                # entity indices reference the ORIGINAL curve list in feat["curves"].
                # Coordinate transform for axis differences
                f["_coord_transform"] = {
                    "cap_xdir": f.get("sketchXDir", [1, 0, 0]),
                    "cap_ydir": f.get("sketchYDir", [0, 1, 0]),
                    "cap_origin": f.get("sketchOrigin"),
                }
                is_on_face = True
                # If cross-body refs exist, use native face sketch so the
                # face boundary is auto-projected while we explicitly project
                # the cross-body intersections.
                has_cross_body_refs = any(
                    c.get("isReference")
                    and c.get("projectedFrom", {}).get("type") == "BRepBody"
                    for c in curves
                )
                # Detect un-attributed reference curves: if many reference
                # curves lack projectedFrom, they may be from cross-body
                # intersections whose source wasn't captured.  Emit runtime
                # auto-intersection code to recreate them.
                unattr_ref_count = sum(
                    1 for c in curves
                    if c.get("isReference") and not c.get("projectedFrom")
                )
                total_ref_count = sum(1 for c in curves if c.get("isReference"))
                # A typical face boundary has 4-8 curves.  If there are many
                # un-attributed refs beyond what a face boundary would produce,
                # assume cross-body intersections are needed.
                if not has_cross_body_refs and unattr_ref_count > 8:
                    f["_auto_intersect_bodies"] = True
                    has_cross_body_refs = True
                if has_cross_body_refs:
                    sketch_comp = "comp"
                    f["_use_native_face"] = True
                    self._current_sketch_comp = sketch_comp
                    self._c(f"Native face sketch: {f.get('name')} (cross-body refs)")
                else:
                    # Check if drawn curves lie along face boundary edges.
                    # Edge coincidence (partial overlap) causes Fusion to merge
                    # edges, producing wrong profiles. Corner-touching is fine.
                    # Fall back to construction plane if edge overlap detected.
                    _ref_lines = []
                    for c in f.get("curves", []):
                        if (c.get("isReference") and c.get("type") == "Line"
                                and c.get("start") and c.get("end")):
                            _ref_lines.append((c["start"], c["end"]))
                    _overlap_ref_indices = set()
                    for c in curves:
                        if c.get("isReference") or c.get("type") != "Line":
                            continue
                        ds, de = c.get("start"), c.get("end")
                        if not ds or not de:
                            continue
                        for ri, (rs, re) in enumerate(_ref_lines):
                            dx_r = re[0] - rs[0]
                            dy_r = re[1] - rs[1]
                            rlen = (dx_r**2 + dy_r**2) ** 0.5
                            if rlen < 1e-6:
                                continue
                            # Perpendicular distance of drawn endpoints to ref line
                            on_line = True
                            for dp in [ds, de]:
                                cross = abs((dp[0]-rs[0])*dy_r - (dp[1]-rs[1])*dx_r) / rlen
                                if cross > 0.05:
                                    on_line = False
                                    break
                            if not on_line:
                                continue
                            # Both endpoints on ref line — check overlap
                            t_s = ((ds[0]-rs[0])*dx_r + (ds[1]-rs[1])*dy_r) / (rlen**2)
                            t_e = ((de[0]-rs[0])*dx_r + (de[1]-rs[1])*dy_r) / (rlen**2)
                            t_lo, t_hi = min(t_s, t_e), max(t_s, t_e)
                            if t_lo > -0.01 and t_hi < 1.01 and (t_hi - t_lo) > 0.01:
                                _overlap_ref_indices.add(ri)
                                break  # this drawn line overlaps — count once
                    # Multiple drawn lines on the SAME ref edge are safe.
                    # Only fall back to cplane when ALL boundary edges are
                    # overlapped (full rectangle coincidence), which merges
                    # the entire boundary. Partial overlaps (internal
                    # subdivision lines along 2 edges) work fine on face.
                    if len(_overlap_ref_indices) >= len(_ref_lines) and len(_ref_lines) >= 4:
                        self._c(f"Full boundary overlap detected — using cplane")
                        plane_code, curves = self._brep_face_to_cplane(f, curves)
                        is_on_face = False
                        # Cplane sketch doesn't need root for face proxy access
                        self._current_sketch_comp = "comp"
                    else:
                        f["_use_native_face"] = True
            else:
                # Edge projections or no refs → use cplane
                plane_code, curves = self._brep_face_to_cplane(f, curves)
        else:
            plane_code = self._resolve_plane(plane_info)
            if not has_any_body_proj:
                self._current_sketch_comp = "comp"
            # Coordinate transform for construction plane sketches:
            # axes may differ between original and reconstructed planes.
            if "sketchXDir" in f and "sketchYDir" in f:
                f["_coord_transform"] = {
                    "cap_xdir": f.get("sketchXDir", [1, 0, 0]),
                    "cap_ydir": f.get("sketchYDir", [0, 1, 0]),
                    "cap_origin": f.get("sketchOrigin"),
                }

        # Record which component the sketch was created in for cross-component detection
        self._sketch_owners[name] = self._current_sketch_comp
        if comp_name:
            self._sketch_owners[f"{comp_name}:{name}"] = self._current_sketch_comp

        if self._is_rect(curves):
            self._emit_rect_sketch(var, name, plane_code, curves, dims, f, on_face=is_on_face)
        else:
            self._emit_raw_sketch(var, name, plane_code, curves, dims, f, on_face=is_on_face)

    # ── Sketch helpers ──

    def _is_rect(self, curves):
        """Check if curves are exactly 4 axis-aligned non-construction drawn lines.

        Returns False if the sketch has any reference curves (projections/
        intersections), because those carry important relationship info
        (e.g. dimensions to projected edges) that rect emission would lose.
        """
        has_ref = any(c.get("isReference") for c in curves)
        if has_ref:
            return False
        lines = [c for c in curves if c.get("type") == "Line"
                 and not c.get("isConstruction")]
        if len(lines) != 4:
            return False
        for ln in lines:
            sx, sy = ln["start"]
            ex, ey = ln["end"]
            if abs(ex - sx) > 0.001 and abs(ey - sy) > 0.001:
                return False
        return True

    def _emit_rect_sketch(self, var, name, plane_code, curves, dims, feat=None, on_face=False):
        """Emit a rectangle sketch with parametric dimensions."""
        lines = [c for c in curves if c.get("type") == "Line" and not c.get("isConstruction")]
        xs = [c["start"][0] for c in lines] + [c["end"][0] for c in lines]
        ys = [c["start"][1] for c in lines] + [c["end"][1] for c in lines]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        w, h = x1 - x0, y1 - y0

        # Match dimensions to geometry
        w_expr = f"{w} cm"
        h_expr = f"{h} cm"
        x0_expr = "0 cm" if abs(x0) < 0.001 else f"{x0} cm"
        y0_expr = "0 cm" if abs(y0) < 0.001 else f"{y0} cm"
        used = set()
        for i, d in enumerate(dims):
            val = d.get("value", 0)
            expr = d.get("expression", "")
            if i not in used and abs(val - w) < 0.01:
                w_expr = expr; used.add(i)
            elif i not in used and abs(val - h) < 0.01:
                h_expr = expr; used.add(i)
            elif i not in used and abs(val - abs(x0)) < 0.01 and abs(x0) > 0.001:
                x0_expr = expr; used.add(i)
            elif i not in used and abs(val - abs(y0)) < 0.01 and abs(y0) > 0.001:
                y0_expr = expr; used.add(i)

        # Check for coordinate transform (BRepFace sketches may have different axes)
        coord_xf = feat.get("_coord_transform") if feat else None

        self._w(f"{var} = {getattr(self, '_current_sketch_comp', 'comp')}.sketches.add({plane_code})")
        self._w(f'{var}.name = "{name}"')

        if coord_xf:
            # Emit runtime transform from capture axes to actual axes.
            # BRepFace sketches can have different axis orientations in the
            # rebuild vs the original (e.g., [-1,0,0] vs [1,0,0]).
            cap_xd = coord_xf["cap_xdir"]
            cap_yd = coord_xf["cap_ydir"]
            self._w(f"_cap_xd = ({cap_xd[0]}, {cap_xd[1]}, {cap_xd[2]})")
            self._w(f"_cap_yd = ({cap_yd[0]}, {cap_yd[1]}, {cap_yd[2]})")
            self._w(f"_act_xd = {var}.xDirection")
            self._w(f"_act_yd = {var}.yDirection")
            self._w(f"_m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z")
            self._w(f"_m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z")
            self._w(f"_m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z")
            self._w(f"_m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z")
            # Origin delta: face-based sketches may have different origins
            # when the face geometry differs between capture and rebuild.
            cap_origin = coord_xf.get("cap_origin")
            if cap_origin:
                self._w(f"_cap_o = ({cap_origin[0]}, {cap_origin[1]}, {cap_origin[2]})")
                self._w(f"_act_o = {var}.origin")
                self._w(f"_do = (_cap_o[0]-_act_o.x, _cap_o[1]-_act_o.y, _cap_o[2]-_act_o.z)")
                self._w(f"_dox = _do[0]*_act_xd.x + _do[1]*_act_xd.y + _do[2]*_act_xd.z")
                self._w(f"_doy = _do[0]*_act_yd.x + _do[1]*_act_yd.y + _do[2]*_act_yd.z")
            else:
                self._w(f"_dox, _doy = 0, 0")
            # Transform corners from capture space to actual space.
            # Compute w/h from parametric expressions, then transform the
            # capture-space rectangle to actual-space coordinates.
            self._w(f'_w0, _h0 = ev("{w_expr}"), ev("{h_expr}")')
            self._w(f'_x0c, _y0c = ev("{x0_expr}"), ev("{y0_expr}")')
            self._w(f"_c1x, _c1y = _x0c*_m00 + _y0c*_m01 + _dox, _x0c*_m10 + _y0c*_m11 + _doy")
            self._w(f"_c2x, _c2y = (_x0c+_w0)*_m00 + (_y0c+_h0)*_m01 + _dox, (_x0c+_w0)*_m10 + (_y0c+_h0)*_m11 + _doy")
            self._w(f"x0, y0 = min(_c1x, _c2x), min(_c1y, _c2y)")
            self._w(f"w, h = abs(_c2x - _c1x), abs(_c2y - _c1y)")
        else:
            self._w(f'x0, y0, w, h = ev("{x0_expr}"), ev("{y0_expr}"), ev("{w_expr}"), ev("{h_expr}")')

        self._w(f"rect = {var}.sketchCurves.sketchLines.addTwoPointRectangle(")
        self.ind += 1
        self._w("P(x0, y0, 0), P(x0 + w, y0 + h, 0))")
        self.ind -= 1
        self._w(f"gc = {var}.geometricConstraints")
        self._w("gc.addHorizontal(rect[0]); gc.addHorizontal(rect[2])")
        self._w("gc.addVertical(rect[1]); gc.addVertical(rect[3])")
        self._w(f"d = {var}.sketchDimensions")
        if coord_xf:
            # When coordinate transform swaps axes, w and h may be exchanged.
            # Match dimension expressions to actual w/h at runtime.
            self._w(f'_wex, _hex = "{w_expr}", "{h_expr}"')
            self._w(f"if abs(w - _h0) < abs(w - _w0): _wex, _hex = _hex, _wex")
        self._w("d.addDistanceDimension(rect[0].startSketchPoint, rect[0].endSketchPoint,")
        self.ind += 1
        if coord_xf:
            self._w(f'H, P(x0 + w/2, y0 - 1, 0)).parameter.expression = _wex')
        else:
            self._w(f'H, P(x0 + w/2, y0 - 1, 0)).parameter.expression = "{w_expr}"')
        self.ind -= 1
        self._w("d.addDistanceDimension(rect[1].startSketchPoint, rect[1].endSketchPoint,")
        self.ind += 1
        if coord_xf:
            self._w(f'V, P(x0 + w + 1, y0 + h/2, 0)).parameter.expression = _hex')
        else:
            self._w(f'V, P(x0 + w + 1, y0 + h/2, 0)).parameter.expression = "{h_expr}"')
        self.ind -= 1
        if coord_xf:
            # When coordinate transform is active, the position in actual
            # sketch space may differ from the capture value. Dimension the
            # actual runtime distance from origin instead of using the
            # capture-time expression.
            self._w(f"_hd = abs(x0)")
            self._w(f"if _hd > 0.01:")
            self.ind += 1
            self._w(f"d.addDistanceDimension({var}.originPoint, rect[0].startSketchPoint,")
            self.ind += 1
            self._w(f'H, P(x0/2, y0 - 2, 0)).parameter.expression = f"{{round(_hd, 4)}} cm"')
            self.ind -= 2
            self._w(f"_vd = abs(y0)")
            self._w(f"if _vd > 0.01:")
            self.ind += 1
            self._w(f"d.addDistanceDimension({var}.originPoint, rect[0].startSketchPoint,")
            self.ind += 1
            self._w(f'V, P(x0 - 1, y0/2, 0)).parameter.expression = f"{{round(_vd, 4)}} cm"')
            self.ind -= 2
        else:
            if x0_expr != "0 cm":
                # Use absolute expression — distance dims are always positive.
                abs_x0 = x0_expr.lstrip("-") if x0_expr.startswith("-") else x0_expr
                self._w("d.addDistanceDimension({0}.originPoint, rect[0].startSketchPoint,".format(var))
                self.ind += 1
                self._w(f'H, P(x0/2, y0 - 2, 0)).parameter.expression = "{abs_x0}"')
                self.ind -= 1
            if y0_expr != "0 cm":
                abs_y0 = y0_expr.lstrip("-") if y0_expr.startswith("-") else y0_expr
                self._w("d.addDistanceDimension({0}.originPoint, rect[0].startSketchPoint,".format(var))
                self.ind += 1
                self._w(f'V, P(x0 - 1, y0/2, 0)).parameter.expression = "{abs_y0}"')
                self.ind -= 1
        prof = f"{var}_prof"
        prof_count = feat.get("profileCount", 1)
        if prof_count > 0:
            if on_face:
                # BRepFace auto-projects boundary → multiple profiles. Select smallest.
                self._w(f"_best_pi, _best_a = 0, float('inf')")
                self._w(f"for _pi in range({var}.profiles.count):")
                self.ind += 1
                self._w(f"_bb = {var}.profiles.item(_pi).boundingBox")
                self._w(f"_a = abs(_bb.maxPoint.x-_bb.minPoint.x)*abs(_bb.maxPoint.y-_bb.minPoint.y)")
                self._w(f"if _a < _best_a: _best_a, _best_pi = _a, _pi")
                self.ind -= 1
                self._w(f"{prof} = {var}.profiles.item(_best_pi) if {var}.profiles.count > 0 else None")
            else:
                self._w(f"{prof} = {var}.profiles.item(0) if {var}.profiles.count > 0 else None")
            self.profiles[name] = prof

    def _emit_sketch_coord_transform(self, var, cap_xdir, cap_ydir, plane_info,
                                      cap_origin=None):
        """Emit runtime code to compute the transform from captured sketch space
        to the actual reconstructed sketch space.

        The captured sketch has axes (cap_xdir, cap_ydir) and origin cap_origin.
        The reconstructed sketch may have different axes AND a different origin
        (face-based sketches place the origin at the projection of the model
        origin onto the face plane, which can shift when face geometry differs).

        The transform handles both axis rotation/reflection and origin translation:
            act_coord = M * cap_coord + origin_delta
        """
        # Emit the captured axes as constants
        self._w(f"# Coordinate transform: captured sketch axes -> actual sketch axes")
        self._w(f"_cap_xd = ({cap_xdir[0]}, {cap_xdir[1]}, {cap_xdir[2]})")
        self._w(f"_cap_yd = ({cap_ydir[0]}, {cap_ydir[1]}, {cap_ydir[2]})")
        self._w(f"_act_xd = {var}.xDirection")
        self._w(f"_act_yd = {var}.yDirection")
        # 2x2 transform matrix: M = [[a,b],[c,d]]
        # where a = dot(cap_xdir, act_xdir), b = dot(cap_ydir, act_xdir), etc.
        self._w(f"_m00 = _cap_xd[0]*_act_xd.x + _cap_xd[1]*_act_xd.y + _cap_xd[2]*_act_xd.z")
        self._w(f"_m01 = _cap_yd[0]*_act_xd.x + _cap_yd[1]*_act_xd.y + _cap_yd[2]*_act_xd.z")
        self._w(f"_m10 = _cap_xd[0]*_act_yd.x + _cap_xd[1]*_act_yd.y + _cap_xd[2]*_act_yd.z")
        self._w(f"_m11 = _cap_yd[0]*_act_yd.x + _cap_yd[1]*_act_yd.y + _cap_yd[2]*_act_yd.z")
        # Origin delta: project (cap_origin - act_origin) into actual sketch axes
        if cap_origin:
            self._w(f"_cap_o = ({cap_origin[0]}, {cap_origin[1]}, {cap_origin[2]})")
            self._w(f"_act_o = {var}.origin")
            self._w(f"_do = (_cap_o[0]-_act_o.x, _cap_o[1]-_act_o.y, _cap_o[2]-_act_o.z)")
            self._w(f"_dox = _do[0]*_act_xd.x + _do[1]*_act_xd.y + _do[2]*_act_xd.z")
            self._w(f"_doy = _do[0]*_act_yd.x + _do[1]*_act_yd.y + _do[2]*_act_yd.z")
        else:
            self._w(f"_dox, _doy = 0, 0")
        self._w(f"def _xf(sx, sy):")
        self.ind += 1
        self._w(f"return (sx * _m00 + sy * _m01 + _dox, sx * _m10 + sy * _m11 + _doy)")
        self.ind -= 1

    def _emit_raw_sketch(self, var, name, plane_code, curves, dims, feat, on_face=False):
        """Emit raw sketch geometry with parametric dimensions and constraints."""
        sketch_comp = getattr(self, '_current_sketch_comp', 'comp')
        if feat.get("_use_native_face"):
            # Use find_face_in_comp to get a native face in the component.
            # This allows Fusion to auto-project all intersecting bodies
            # in the component, matching the original sketch's references.
            # Falls back to find_face_near when the face body is in a
            # different component (e.g., sketch in braces on beam's face).
            plane_info = feat.get("plane", {})
            pof = plane_info.get("pointOnFace", [0, 0, 0])
            normal = plane_info.get("normal", [0, 0, 0])
            body_name = plane_info.get("body", "")
            # Search the specific body's face first to avoid picking a face
            # on a different body in the same component (e.g., post1 vs scarf1).
            # Always use find_body for face lookup — body variables can become
            # stale after RectangularPattern consumes the original body.
            bv = f'find_body("{body_name}")' if body_name else "None"
            self._w(f"_native_face = find_face_near("
                    f"{bv}, {pof[0]}, {pof[1]}, {pof[2]}, "
                    f"{normal[0]}, {normal[1]}, {normal[2]})")
            self._w(f"if not _native_face: _native_face = find_face_in_comp({sketch_comp}, "
                    f"{pof[0]}, {pof[1]}, {pof[2]}, "
                    f"{normal[0]}, {normal[1]}, {normal[2]})")
            self._w(f"{var} = {sketch_comp}.sketches.add(_native_face)")
        else:
            self._w(f"{var} = {sketch_comp}.sketches.add({plane_code})")
        self._w(f'{var}.name = "{name}"')
        self._w(f"lns = {var}.sketchCurves.sketchLines")

        # Emit coordinate transform if the sketch was on a BRepFace with
        # body projections (axes may differ from captured sketch)
        _has_coord_xf = False
        coord_xf = feat.get("_coord_transform")
        if coord_xf:
            _has_coord_xf = True
            self._emit_sketch_coord_transform(var, coord_xf["cap_xdir"], coord_xf["cap_ydir"], feat.get("plane", {}),
                                                  cap_origin=coord_xf.get("cap_origin"))
        else:
            # Identity transform — _xf passthrough for dimension references
            self._w(f"def _xf(sx, sy): return (sx, sy)")

        has_arcs = any(c.get("type") == "Arc" for c in curves)
        has_circles = any(c.get("type") == "Circle" for c in curves)
        has_splines = any(c.get("type") in ("FittedSpline", "SketchFixedSpline") for c in curves)
        if has_arcs:
            self._w(f"arcs = {var}.sketchCurves.sketchArcs")

        # Track sketch points by position to share coincident endpoints.
        # Without sharing, Fusion creates duplicate points and extra profiles.
        pt_map = {}  # (round_x, round_y) → "ln{i}.startSketchPoint" etc.

        def _pt_ref(x, y):
            """Return sketch point ref if one exists at this position, else Point3D."""
            key = (round(x, 3), round(y, 3))
            return pt_map.get(key), key

        def _register_pt(key, ref):
            if key not in pt_map:
                pt_map[key] = ref

        # curve index → variable name mapping for dimension/constraint targets
        curve_vars = {}
        arc_vars = {}
        circle_vars = {}

        # Pre-scan: collect BRepBody projections and detect which drawn line
        # endpoints coincide with projected curve endpoints (in original capture space).
        _body_proj_done = set()
        _has_body_projs = False
        _proj_endpoints = set()  # (round_x, round_y) of projected curve endpoints
        _proj_connected = set()  # (curve_idx, "start"/"end") pairs that should snap to projections
        _on_edge_pts = set()    # (curve_idx, "end") pairs placed exactly on projected edge

        # Pass 1: collect all projected curve endpoint positions (pre-flip coordinates)
        for i, c in enumerate(feat.get("curves", [])):
            if c.get("isReference") and c.get("projectedFrom", {}).get("type") == "BRepBody":
                sx, sy = c["start"]
                ex, ey = c["end"]
                _proj_endpoints.add((round(sx, 3), round(sy, 3)))
                _proj_endpoints.add((round(ex, 3), round(ey, 3)))

        # Pass 2: check which drawn line endpoints match projected endpoints
        for i, c in enumerate(feat.get("curves", [])):
            if not c.get("isReference"):
                sx, sy = c.get("start", [0, 0])
                ex, ey = c.get("end", [0, 0])
                if (round(sx, 3), round(sy, 3)) in _proj_endpoints:
                    _proj_connected.add((i, "start"))
                if (round(ex, 3), round(ey, 3)) in _proj_endpoints:
                    _proj_connected.add((i, "end"))

        # Pass 3: emit sk.project(body) or sk.intersectWithSketchPlane([body])
        for i, c in enumerate(curves):
            if c.get("isReference"):
                pf = c.get("projectedFrom", {})
                if pf.get("type") == "BRepBody" and pf.get("body"):
                    bname = pf["body"]
                    if bname not in _body_proj_done:
                        _body_proj_done.add(bname)
                        _has_body_projs = True
                        pvar = f"_proj_body_{self._var(bname)}"
                        method = pf.get("method", "project")
                        if method == "intersect":
                            self._c(f"Intersect body '{bname}' with sketch plane")
                            bodies_var = f"_bodies_{self._var(bname)}"
                            self._w(f"{bodies_var} = []")
                            if self._current_sketch_comp == "root":
                                # Sketch in root: check root's own bodies first
                                self._w(f"for _bi in range(root.bRepBodies.count):")
                                self.ind += 1
                                self._w(f'if root.bRepBodies.item(_bi).name == "{bname}":')
                                self.ind += 1
                                self._w(f"{bodies_var}.append(root.bRepBodies.item(_bi))")
                                self.ind -= 2
                                # Fallback: proxied bodies via occurrences (multi-component)
                                self._w(f"if not {bodies_var}:")
                                self.ind += 1
                                self._w(f"for _occ in root.allOccurrences:")
                                self.ind += 1
                                self._w(f"for _bi in range(_occ.bRepBodies.count):")
                                self.ind += 1
                                self._w(f'if _occ.bRepBodies.item(_bi).name == "{bname}":')
                                self.ind += 1
                                self._w(f"{bodies_var}.append(_occ.bRepBodies.item(_bi))")
                                self.ind -= 4
                            else:
                                # Sketch in comp: use native or cross-component bodies
                                body_comp = pf.get("bodyComponent")
                                sketch_comp = feat.get("component", "")
                                if body_comp and body_comp != sketch_comp:
                                    # Body is in a different component — search there directly
                                    # (don't search local comp first, since it may have
                                    # a same-named body that's the wrong one)
                                    self._w(f"for _occ in root.allOccurrences:")
                                    self.ind += 1
                                    self._w(f'if _occ.component.name == "{body_comp}":')
                                    self.ind += 1
                                    self._w(f"for _bi in range(_occ.bRepBodies.count):")
                                    self.ind += 1
                                    self._w(f'if _occ.bRepBodies.item(_bi).name == "{bname}":')
                                    self.ind += 1
                                    self._w(f"{bodies_var}.append(_occ.bRepBodies.item(_bi))")
                                    self.ind -= 2
                                    self._w(f"break")
                                    self.ind -= 2
                                else:
                                    # Same component — search locally first
                                    self._w(f"for _bi in range(comp.bRepBodies.count):")
                                    self.ind += 1
                                    self._w(f'if comp.bRepBodies.item(_bi).name == "{bname}":')
                                    self.ind += 1
                                    self._w(f"{bodies_var}.append(comp.bRepBodies.item(_bi))")
                                    self.ind -= 2
                                    # Fallback: cross-component search if local found nothing
                                    self._w(f"if not {bodies_var}:")
                                    self.ind += 1
                                    self._w(f"for _occ in root.allOccurrences:")
                                    self.ind += 1
                                    self._w(f"for _bi in range(_occ.bRepBodies.count):")
                                    self.ind += 1
                                    self._w(f'if _occ.bRepBodies.item(_bi).name == "{bname}":')
                                    self.ind += 1
                                    self._w(f"{bodies_var}.append(_occ.bRepBodies.item(_bi))")
                                    self.ind -= 4
                            self._w(f"if {bodies_var}: {pvar} = {var}.intersectWithSketchPlane({bodies_var})")
                        else:
                            # For project, use find_body
                            if self._current_sketch_comp == "root":
                                bv = f'find_body("{bname}")'
                            else:
                                bv = f'find_body("{bname}", comp)'
                            self._c(f"Project body '{bname}'")
                            self._w(f"{pvar} = {var}.project({bv})")

        # Auto-detect cross-body intersections when reference curves lack
        # projectedFrom attribution (capture couldn't identify the source body).
        if feat.get("_auto_intersect_bodies"):
            face_body_name = feat.get("plane", {}).get("body", "")
            expected_ref_count = sum(
                1 for c in feat.get("curves", []) if c.get("isReference"))
            self._c(f"Auto-detect cross-body intersections ({expected_ref_count} expected refs)")
            self._w(f"_pre_ref = sum(1 for _i in range({var}.sketchCurves.count) if {var}.sketchCurves.item(_i).isReference)")
            self._w(f"if _pre_ref < {expected_ref_count}:")
            self.ind += 1
            self._w(f"_xb = []")
            self._w(f"for _occ in root.allOccurrences:")
            self.ind += 1
            self._w(f"for _bi in range(_occ.bRepBodies.count):")
            self.ind += 1
            self._w(f"_b = _occ.bRepBodies.item(_bi)")
            if face_body_name:
                self._w(f'if _b.name != "{face_body_name}": _xb.append(_b)')
            else:
                self._w(f"_xb.append(_b)")
            self.ind -= 2
            self._w(f"if _xb: {var}.intersectWithSketchPlane(_xb)")
            self.ind -= 1
            _has_body_projs = True

        # Project ConstructionPlane references explicitly.
        # Native face sketches auto-project face boundary but NOT construction
        # planes.  Without explicit projection, _nearest_proj_curve creates a
        # drawn fallback line that changes profile topology.
        _cp_proj_done = set()
        for c in feat.get("curves", []):
            if not (c.get("isReference")
                    and c.get("projectedFrom", {}).get("type") == "ConstructionPlane"):
                continue
            cp_name = c["projectedFrom"].get("name", "")
            if not cp_name or cp_name in _cp_proj_done:
                continue
            _cp_proj_done.add(cp_name)
            comp_name = feat.get("component", "")
            cp_var = None
            if comp_name:
                scoped = f"{comp_name}:{cp_name}"
                if scoped in self.planes:
                    cp_var = self.planes[scoped]
            if not cp_var and cp_name in self.planes:
                cp_var = self.planes[cp_name]
            if cp_var:
                self._c(f"Project construction plane '{cp_name}'")
                self._w(f"{var}.project({cp_var})")
                _has_body_projs = True

        # Pre-compute which reference curves need runtime resolution.
        # This is checked early so we know whether to emit _nearest_proj.
        _proj_curve_pts = {}  # (origIdx, role) → (x, y) in capture space
        for c in feat.get("curves", []):
            oi = c.get("_origIdx")
            if (oi is not None and c.get("isReference")
                    and c.get("start") and c.get("end")):
                sx, sy = c["start"]
                ex, ey = c["end"]
                _proj_curve_pts[(oi, "start")] = (sx, sy)
                _proj_curve_pts[(oi, "end")] = (ex, ey)


        if _has_body_projs or _proj_curve_pts:
            # Build runtime lookup of all projected sketch points AND curves
            self._w(f"_proj_pts = []  # [(x, y, sketchPoint), ...]")
            self._w(f"_proj_curves = []  # [(sx, sy, ex, ey, curve), ...]")
            # NOTE: Anonymous reference curves (isReference with no
            # projectedFrom) are handled by _nearest_proj_curve fallback.
            # Construction plane projection was tested but CP intersections
            # don't match the anonymous ref coordinates — the anonymous refs
            # likely come from native Fusion auto-projection of body silhouettes
            # or other geometry that can't be replicated via the API.
            # The fallback line approach works; profile mismatches are handled
            # by multi-profile bbox matching in the extrude generator.
            self._w(f"for _ci in range({var}.sketchCurves.count):")
            self.ind += 1
            self._w(f"_c = {var}.sketchCurves.item(_ci)")
            self._w(f"if _c.isReference:")
            self.ind += 1
            self._w(f"for _sp in [_c.startSketchPoint, _c.endSketchPoint]:")
            self.ind += 1
            self._w(f"_g = _sp.geometry")
            self._w(f"_proj_pts.append((_g.x, _g.y, _sp))")
            self.ind -= 1
            self._w(f"_s, _e = _c.startSketchPoint.geometry, _c.endSketchPoint.geometry")
            self._w(f"_proj_curves.append((_s.x, _s.y, _e.x, _e.y, _c))")
            self.ind -= 2
            self._w()
            self._w(f"_fallback_pts = {{}}")
            self._w(f"def _nearest_proj(x, y):")
            self.ind += 1
            self._w(f"best, best_d = None, 1e10")
            self._w(f"for _px, _py, _sp in _proj_pts:")
            self.ind += 1
            self._w(f"_d = abs(_px - x) + abs(_py - y)")
            self._w(f"if _d < best_d: best, best_d = _sp, _d")
            self.ind -= 1
            # Reject matches with large distance
            self._w(f"if best_d > 5.0: best = None")
            self._w(f"if best is None:")
            self.ind += 1
            # Check fallback line endpoints first
            self._w(f"_fk = (round(x,2), round(y,2))")
            self._w(f"best = _fallback_pts.get(_fk)")
            self.ind -= 1
            self._w(f"if best is None:")
            self.ind += 1
            self._w(f"best = {var}.sketchPoints.add(P(x, y, 0))")
            self.ind -= 1
            self._w(f"return best")
            self.ind -= 1
            self._w()
            self._w(f"def _nearest_proj_curve(sx, sy, ex, ey):")
            self.ind += 1
            self._w(f"best, best_d = None, 1e10")
            self._w(f"for _sx, _sy, _ex, _ey, _c in _proj_curves:")
            self.ind += 1
            self._w(f"_d = min(abs(_sx-sx)+abs(_sy-sy)+abs(_ex-ex)+abs(_ey-ey),")
            self._w(f"        abs(_sx-ex)+abs(_sy-ey)+abs(_ex-sx)+abs(_ey-sy))")
            self._w(f"if _d < best_d: best, best_d = _c, _d")
            self.ind -= 1
            # Reject matches with large distance — prevents matching wrong curve
            self._w(f"if best_d > 10.0:")
            self.ind += 1
            # Secondary match: same infinite line (parallel direction,
            # small point-to-line distance).  Construction plane projections
            # may have different extent/endpoints than the capture.
            self._w(f"best, best_d = None, 1e10")
            self._w(f"_dx, _dy = ex - sx, ey - sy")
            self._w(f"_len = (_dx*_dx + _dy*_dy)**0.5")
            self._w(f"if _len > 0.001:")
            self.ind += 1
            self._w(f"_ux, _uy = _dx/_len, _dy/_len")
            self._w(f"for _sx, _sy, _ex, _ey, _c in _proj_curves:")
            self.ind += 1
            self._w(f"_rdx, _rdy = _ex - _sx, _ey - _sy")
            self._w(f"_rlen = (_rdx*_rdx + _rdy*_rdy)**0.5")
            self._w(f"if _rlen < 0.001: continue")
            # Check if directions are parallel (cross product ≈ 0)
            self._w(f"_cross = abs(_ux*_rdy/_rlen - _uy*_rdx/_rlen)")
            self._w(f"if _cross > 0.05: continue")
            # Point-to-line distance from query start to reference line
            self._w(f"_ptd = abs((sx-_sx)*(-_rdy/_rlen) + (sy-_sy)*(_rdx/_rlen))")
            self._w(f"if _ptd < best_d: best, best_d = _c, _ptd")
            self.ind -= 2
            self._w(f"if best_d > 1.0: best = None")
            self.ind -= 1
            self._w(f"if best is None:")
            self.ind += 1
            # Share endpoints between fallback lines to form closed loops
            self._w(f"_sk = (round(sx,2), round(sy,2))")
            self._w(f"_ek = (round(ex,2), round(ey,2))")
            self._w(f"_sp = _fallback_pts.get(_sk)")
            self._w(f"_ep = _fallback_pts.get(_ek)")
            self._w(f"if _sp and _ep:")
            self.ind += 1
            self._w(f"best = {var}.sketchCurves.sketchLines.addByTwoPoints(_sp, _ep)")
            self.ind -= 1
            self._w(f"elif _sp:")
            self.ind += 1
            self._w(f"best = {var}.sketchCurves.sketchLines.addByTwoPoints(_sp, P(ex, ey, 0))")
            self._w(f"_fallback_pts[_ek] = best.endSketchPoint")
            self.ind -= 1
            self._w(f"elif _ep:")
            self.ind += 1
            self._w(f"best = {var}.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), _ep)")
            self._w(f"_fallback_pts[_sk] = best.startSketchPoint")
            self.ind -= 1
            self._w(f"else:")
            self.ind += 1
            self._w(f"best = {var}.sketchCurves.sketchLines.addByTwoPoints(P(sx, sy, 0), P(ex, ey, 0))")
            self._w(f"_fallback_pts[_sk] = best.startSketchPoint")
            self._w(f"_fallback_pts[_ek] = best.endSketchPoint")
            self.ind -= 1
            # Pin fallback lines so constraints don't move them to wrong positions.
            self._w(f"try: {var}.geometricConstraints.addFix(best)")
            self._w(f"except: pass")
            self.ind -= 1
            self._w(f"return best")
            self.ind -= 1

            # Register ALL reference curves in curve_vars for
            # constraint/dimension references (match by endpoint proximity).
            # This includes BRepBody projections, BRepFace projections
            # (auto-boundary), and generic reference curves.
            # NOTE: iterate feat["curves"] (unfiltered) because the local
            # `curves` may have been stripped of refs (line 287: curves = non_ref).
            for i, c in enumerate(feat.get("curves", [])):
                if not c.get("isReference"):
                    continue
                _oi = c.get("_origIdx", i)
                if _oi in curve_vars:
                    continue  # already registered (e.g., BRepEdge projection)
                if not (c.get("start") and c.get("end")):
                    continue
                sx, sy = c["start"]
                ex, ey = c["end"]
                cv = f"_pcurve_{_oi}"
                if _has_coord_xf:
                    self._w(f"{cv} = _nearest_proj_curve(*_xf({sx}, {sy}), *_xf({ex}, {ey}))")
                else:
                    self._w(f"{cv} = _nearest_proj_curve({sx}, {sy}, {ex}, {ey})")
                curve_vars[_oi] = cv
                # Don't register endpoints in pt_map — sharing SketchPoints
                # with face boundary vertices creates coincident geometry that
                # changes profile topology in Fusion.

        for i, c in enumerate(curves):
            ctype = c.get("type", "")
            # Projected/reference curves: emit sk.project(edge/body) to recreate
            if c.get("isReference"):
                pf = c.get("projectedFrom", {})
                if pf.get("type") == "BRepBody":
                    # Body projection emitted above. Skip individual curve.
                    continue
                elif pf.get("type") == "BRepFace":
                    # Auto-boundary — skip (handled by find_face)
                    continue
                elif pf.get("type") == "BRepEdge" and "startVertex" in pf and "endVertex" in pf:
                    body_name = pf["body"]
                    sv = pf["startVertex"]
                    ev_pt = pf["endVertex"]
                    bv = self._body_ref(body_name)
                    self._c(f"Project edge from '{body_name}'")
                    self._w(f"_proj_edge_{i} = None")
                    self._w(f"for _ei in range({bv}.edges.count):")
                    self.ind += 1
                    self._w(f"_e = {bv}.edges.item(_ei)")
                    self._w(f"_sv, _ev = _e.startVertex.geometry, _e.endVertex.geometry")
                    self._w(f"if ((abs(_sv.x-{sv[0]:.4f})+abs(_sv.y-{sv[1]:.4f})+abs(_sv.z-{sv[2]:.4f}) < 0.05 and")
                    self._w(f"     abs(_ev.x-{ev_pt[0]:.4f})+abs(_ev.y-{ev_pt[1]:.4f})+abs(_ev.z-{ev_pt[2]:.4f}) < 0.05) or")
                    self._w(f"    (abs(_sv.x-{ev_pt[0]:.4f})+abs(_sv.y-{ev_pt[1]:.4f})+abs(_sv.z-{ev_pt[2]:.4f}) < 0.05 and")
                    self._w(f"     abs(_ev.x-{sv[0]:.4f})+abs(_ev.y-{sv[1]:.4f})+abs(_ev.z-{sv[2]:.4f}) < 0.05)):")
                    self.ind += 1
                    self._w(f"_proj_edge_{i} = _e")
                    self._w("break")
                    self.ind -= 2
                    self._w(f"_proj_curves_{i} = {var}.project(_proj_edge_{i})")
                    # The projected result is a collection; find the matching curve
                    self._w(f"proj{i} = _proj_curves_{i}.item(0)")
                    _oi = c.get("_origIdx", i)
                    curve_vars[_oi] = f"proj{i}"
                    sx, sy = c["start"]
                    ex, ey = c["end"]
                    _register_pt((round(sx, 3), round(sy, 3)), f"proj{i}.startSketchPoint")
                    _register_pt((round(ex, 3), round(ey, 3)), f"proj{i}.endSketchPoint")
                elif pf.get("type") == "ConstructionPlane":
                    # Projected above in the ConstructionPlane pass.
                    # _nearest_proj_curve will find it among reference curves.
                    pass
                else:
                    self._c(f"curve[{i}] is a projected reference (source not captured)")
                continue
            if ctype == "Line":
                sx, sy = c["start"]
                ex, ey = c["end"]
                # When coordinate transform is active, transform captured
                # coords to actual sketch space for _nearest_proj queries
                # and for computing deltas.
                if _has_coord_xf and not c.get("isReference"):
                    self._w(f"_cs_{i} = _xf({sx}, {sy})")
                    self._w(f"_ce_{i} = _xf({ex}, {ey})")
                    tsx, tsy = f"_cs_{i}[0]", f"_cs_{i}[1]"
                    tex, tey = f"_ce_{i}[0]", f"_ce_{i}[1]"
                else:
                    tsx, tsy = str(sx), str(sy)
                    tex, tey = str(ex), str(ey)
                s_ref, s_key = _pt_ref(sx, sy)
                e_ref, e_key = _pt_ref(ex, ey)
                if _has_body_projs:
                    oi = c.get("_origIdx", i)
                    # Force proj even if s_ref exists — the coincident constraint
                    # needs the projected sketch point, not a shared drawn point
                    s_is_proj = (oi, "start") in _proj_connected
                    e_is_proj = (oi, "end") in _proj_connected

                    if s_is_proj:
                        self._w(f"_pp_{i}s = _nearest_proj({tsx}, {tsy})")
                        self._w(f"_pg_{i}s = _pp_{i}s.geometry")
                        s_code = f"P(_pg_{i}s.x, _pg_{i}s.y, 0)"
                    elif s_ref:
                        s_code = s_ref
                    elif _has_coord_xf:
                        s_code = f"P({tsx}, {tsy}, 0)"
                    else:
                        s_code = f"P({sx}, {sy}, 0)"

                    if e_is_proj:
                        self._w(f"_pp_{i}e = _nearest_proj({tex}, {tey})")
                        self._w(f"_pg_{i}e = _pp_{i}e.geometry")
                        e_code = f"P(_pg_{i}e.x, _pg_{i}e.y, 0)"
                    elif e_ref:
                        e_code = e_ref
                    elif s_is_proj:
                        # Non-projected end: place ON the projected edge.
                        # Find which projected curve this endpoint should lie on
                        # (from coincident constraints in the capture), and compute
                        # the endpoint along the actual curve direction.
                        on_curve = self._find_online_constraint(feat, c.get("_origIdx", i), "end")
                        if on_curve is not None and on_curve in curve_vars:
                            cv_on = curve_vars[on_curve]
                            # Compute endpoint along the projected curve from start
                            # at approximate distance (will be set exactly by dimension)
                            cap_dist = ((ex - sx)**2 + (ey - sy)**2)**0.5
                            self._w(f"_es_{i} = {cv_on}.startSketchPoint.geometry")
                            self._w(f"_ee_{i} = {cv_on}.endSketchPoint.geometry")
                            self._w(f"_el_{i} = ((_ee_{i}.x-_es_{i}.x)**2+(_ee_{i}.y-_es_{i}.y)**2)**0.5")
                            self._w(f"_ed_{i} = {round(cap_dist, 6)} / _el_{i} if _el_{i} > 0.001 else 0")
                            # Pick direction: toward start or end of the curve?
                            # Compare distance from the projected start point to both curve endpoints
                            self._w(f"_ds_{i} = abs(_pg_{i}s.x-_es_{i}.x)+abs(_pg_{i}s.y-_es_{i}.y)")
                            self._w(f"_de_{i} = abs(_pg_{i}s.x-_ee_{i}.x)+abs(_pg_{i}s.y-_ee_{i}.y)")
                            self._w(f"if _ds_{i} < _de_{i}:")
                            self.ind += 1
                            self._w(f"_ex_{i} = _es_{i}.x + (_ee_{i}.x-_es_{i}.x)*_ed_{i}")
                            self._w(f"_ey_{i} = _es_{i}.y + (_ee_{i}.y-_es_{i}.y)*_ed_{i}")
                            self.ind -= 1
                            self._w(f"else:")
                            self.ind += 1
                            self._w(f"_ex_{i} = _ee_{i}.x + (_es_{i}.x-_ee_{i}.x)*_ed_{i}")
                            self._w(f"_ey_{i} = _ee_{i}.y + (_es_{i}.y-_ee_{i}.y)*_ed_{i}")
                            self.ind -= 1
                            e_code = f"P(_ex_{i}, _ey_{i}, 0)"
                            _on_edge_pts.add((c.get("_origIdx", i), "end"))
                        else:
                            # Fallback: use transformed delta
                            self._w(f"_dx_{i} = {tex} - {tsx}")
                            self._w(f"_dy_{i} = {tey} - {tsy}")
                            e_code = f"P(_pg_{i}s.x + _dx_{i}, _pg_{i}s.y + _dy_{i}, 0)"
                    elif _has_coord_xf:
                        e_code = f"P({tex}, {tey}, 0)"
                    else:
                        e_code = f"P({ex}, {ey}, 0)"

                    # Same for non-projected start with projected end
                    if not s_is_proj and not s_ref and e_is_proj:
                        if _has_coord_xf:
                            self._w(f"_dx_{i} = {tsx} - {tex}")
                            self._w(f"_dy_{i} = {tsy} - {tey}")
                            s_code = f"P(_pg_{i}e.x + _dx_{i}, _pg_{i}e.y + _dy_{i}, 0)"
                        else:
                            dx = round(sx - ex, 6)
                            dy = round(sy - ey, 6)
                            s_code = f"P(_pg_{i}e.x + {dx}, _pg_{i}e.y + {dy}, 0)"
                else:
                    if _has_coord_xf:
                        s_code = s_ref if s_ref else f"P({tsx}, {tsy}, 0)"
                        e_code = e_ref if e_ref else f"P({tex}, {tey}, 0)"
                    else:
                        s_code = s_ref if s_ref else f"P({sx}, {sy}, 0)"
                        e_code = e_ref if e_ref else f"P({ex}, {ey}, 0)"
                self._w(f"ln{i} = lns.addByTwoPoints({s_code}, {e_code})")
                # Add coincident constraints to merge drawn endpoints
                # with projected sketch points (shares the point, zero-gap)
                if _has_body_projs:
                    oi2 = c.get("_origIdx", i)
                    if (oi2, "start") in _proj_connected:
                        self._w(f"{var}.geometricConstraints.addCoincident(ln{i}.startSketchPoint, _pp_{i}s)")
                    if (oi2, "end") in _proj_connected:
                        self._w(f"{var}.geometricConstraints.addCoincident(ln{i}.endSketchPoint, _pp_{i}e)")
                _register_pt(s_key, f"ln{i}.startSketchPoint")
                _register_pt(e_key, f"ln{i}.endSketchPoint")
                _oi = c.get("_origIdx", i)
                curve_vars[_oi] = f"ln{i}"
                if c.get("isConstruction"):
                    self._w(f"ln{i}.isConstruction = True")
            elif ctype == "Arc":
                cx, cy = c.get("center", [0, 0])
                sx, sy = c.get("start", [0, 0])
                sweep = c.get("sweepAngle", 3.14159)
                if _has_coord_xf and not c.get("isReference"):
                    self._w(f"_ac_{i} = _xf({cx}, {cy})")
                    self._w(f"_as_{i} = _xf({sx}, {sy})")
                    self._w(f"arc{i} = arcs.addByCenterStartSweep(P(_ac_{i}[0], _ac_{i}[1], 0), P(_as_{i}[0], _as_{i}[1], 0), {sweep})")
                else:
                    self._w(f"arc{i} = arcs.addByCenterStartSweep(P({cx}, {cy}, 0), P({sx}, {sy}, 0), {sweep})")
                _oi = c.get("_origIdx", i)
                curve_vars[_oi] = f"arc{i}"
                arc_vars[i] = f"arc{i}"
                _register_pt((round(sx, 3), round(sy, 3)), f"arc{i}.startSketchPoint")
                ex, ey = c.get("end", [sx, sy])
                _register_pt((round(ex, 3), round(ey, 3)), f"arc{i}.endSketchPoint")
            elif ctype == "Circle":
                cx, cy = c.get("center", [0, 0])
                r = c.get("radius", 1)
                if _has_coord_xf and not c.get("isReference"):
                    self._w(f"_cc_{i} = _xf({cx}, {cy})")
                    self._w(f"circ{i} = {var}.sketchCurves.sketchCircles.addByCenterRadius(P(_cc_{i}[0], _cc_{i}[1], 0), {r})")
                else:
                    self._w(f"circ{i} = {var}.sketchCurves.sketchCircles.addByCenterRadius(P({cx}, {cy}, 0), {r})")
                _oi = c.get("_origIdx", i)
                curve_vars[_oi] = f"circ{i}"
                circle_vars[i] = f"circ{i}"
            elif ctype == "FittedSpline":
                pts = c.get("fitPoints", [])
                self._w(f"_spl_pts{i} = adsk.core.ObjectCollection.create()")
                if _has_coord_xf and not c.get("isReference"):
                    for fi, fp in enumerate(pts):
                        self._w(f"_sfp_{i}_{fi} = _xf({fp[0]}, {fp[1]})")
                        self._w(f"_spl_pts{i}.add(P(_sfp_{i}_{fi}[0], _sfp_{i}_{fi}[1], 0))")
                else:
                    for fp in pts:
                        self._w(f"_spl_pts{i}.add(P({fp[0]}, {fp[1]}, 0))")
                self._w(f"spl{i} = {var}.sketchCurves.sketchFittedSplines.add(_spl_pts{i})")
                _oi = c.get("_origIdx", i)
                curve_vars[_oi] = f"spl{i}"
                if pts:
                    _register_pt((round(pts[0][0], 3), round(pts[0][1], 3)), f"spl{i}.startSketchPoint")
                    _register_pt((round(pts[-1][0], 3), round(pts[-1][1], 3)), f"spl{i}.endSketchPoint")
                if c.get("isConstruction"):
                    self._w(f"spl{i}.isConstruction = True")
            elif ctype == "SketchFixedSpline":
                pts = c.get("controlPoints", [])
                if pts:
                    self._w(f"_fsp_pts{i} = adsk.core.ObjectCollection.create()")
                    if _has_coord_xf:
                        for fi, fp in enumerate(pts):
                            self._w(f"_fsp_{i}_{fi} = _xf({fp[0]}, {fp[1]})")
                            self._w(f"_fsp_pts{i}.add(P(_fsp_{i}_{fi}[0], _fsp_{i}_{fi}[1], 0))")
                    else:
                        for fp in pts:
                            self._w(f"_fsp_pts{i}.add(P({fp[0]}, {fp[1]}, 0))")
                    self._w(f"fsp{i} = {var}.sketchCurves.sketchFixedSplines.add(_fsp_pts{i})")
                    _oi = c.get("_origIdx", i)
                    curve_vars[_oi] = f"fsp{i}"
                    start = c.get("start")
                    end = c.get("end")
                    if start:
                        _register_pt((round(start[0], 3), round(start[1], 3)), f"fsp{i}.startSketchPoint")
                    if end:
                        _register_pt((round(end[0], 3), round(end[1], 3)), f"fsp{i}.endSketchPoint")
                    if c.get("isConstruction"):
                        self._w(f"fsp{i}.isConstruction = True")
                else:
                    self._c(f"TODO: SketchFixedSpline[{i}] has no control points")

        # ── Face boundary T-junction fix ──
        # In face-based sketches, drawn curve endpoints that lie on a face
        # boundary edge (mid-edge, not at a vertex) need a coincident
        # constraint to create a proper T-junction.  Without this, Fusion
        # treats the endpoint as free-floating near the edge, so the profile
        # region doesn't split — causing downstream CUT extrudes to select
        # the wrong (merged) profile.
        if feat.get("_use_native_face"):
            _fb_edges = []
            for _fbi, _fbc in enumerate(feat.get("curves", [])):
                if (_fbc.get("isReference")
                        and _fbc.get("projectedFrom", {}).get("type") == "BRepFace"):
                    _fb_oi = _fbc.get("_origIdx", _fbi)
                    if _fb_oi in curve_vars and _fbc.get("start") and _fbc.get("end"):
                        _fb_edges.append((_fbc["start"], _fbc["end"], _fb_oi))
            if _fb_edges:
                for _di, _dc in enumerate(curves):
                    if _dc.get("isReference") or _dc.get("type") != "Line":
                        continue
                    _d_oi = _dc.get("_origIdx", _di)
                    if _d_oi not in curve_vars:
                        continue
                    _dcv = curve_vars[_d_oi]
                    for _pt_side, _ppx, _ppy in [
                        ("start", _dc.get("start", [0, 0])[0], _dc.get("start", [0, 0])[1]),
                        ("end", _dc.get("end", [0, 0])[0], _dc.get("end", [0, 0])[1]),
                    ]:
                        for (_es, _ee, _e_oi) in _fb_edges:
                            _edx = _ee[0] - _es[0]
                            _edy = _ee[1] - _es[1]
                            _elen2 = _edx * _edx + _edy * _edy
                            if _elen2 < 0.001:
                                continue
                            _cross = abs((_ppx - _es[0]) * _edy
                                         - (_ppy - _es[1]) * _edx)
                            if _cross / (_elen2 ** 0.5) > 0.01:
                                continue
                            _dot = ((_ppx - _es[0]) * _edx
                                    + (_ppy - _es[1]) * _edy)
                            _t = _dot / _elen2
                            if _t < 0.01 or _t > 0.99:
                                continue  # at vertex, not mid-edge
                            _sp_code = (f"{_dcv}.startSketchPoint"
                                        if _pt_side == "start"
                                        else f"{_dcv}.endSketchPoint")
                            _ecv = curve_vars[_e_oi]
                            self._w(f"try: {var}.geometricConstraints"
                                    f".addCoincident({_sp_code}, {_ecv})")
                            self._w(f"except: pass")
                            break

        constraints = feat.get("constraints", [])
        _early_ci = set()

        # Pin construction lines referenced by angular dims with an
        # explicit H distance dimension.  Without this, the construction
        # line collapses (endpoint drifts to near the shared start point)
        # before its H/V constraint is applied in the constraint phase.
        # addFix() fails on shared-endpoint lines and on SketchPoints,
        # so we use a distance dimension to lock the horizontal extent.
        _pinned_const = set()   # curve indices with explicit pin dim
        if dims:
            _const_curves = {}  # curveIndex → curve dict
            for _ci2, _c2 in enumerate(feat.get("curves", [])):
                if _c2.get("isConstruction") and _c2.get("type") == "Line":
                    _const_curves[_ci2] = _c2
            if _const_curves:
                _to_pin = set()
                for _d2 in dims:
                    if _d2.get("type") == "SketchAngularDimension":
                        for _key in ("lineOne", "lineTwo"):
                            _ref = _d2.get(_key, {})
                            if isinstance(_ref, dict):
                                _ci3 = _ref.get("curveIndex")
                                if _ci3 is not None and _ci3 in _const_curves:
                                    _to_pin.add(_ci3)
                if _to_pin:
                    self._w(f"_pd = {var}.sketchDimensions")
                    for _ci3 in sorted(_to_pin):
                        if _ci3 not in curve_vars:
                            continue
                        _cv = curve_vars[_ci3]
                        _cc = _const_curves[_ci3]
                        _s = _cc.get("start", [0, 0])
                        _e = _cc.get("end", [0, 0])
                        _hdist = abs(_e[0] - _s[0])
                        if _hdist < 0.001:
                            continue  # vertical — skip
                        self._w(f"try: _pd.addDistanceDimension("
                                f"{_cv}.startSketchPoint, {_cv}.endSketchPoint, "
                                f"H, P(0, 0, 0)).parameter.value = {round(_hdist, 6)}")
                        self._w(f"except: pass")
                        _pinned_const.add(_ci3)

        # Emit dimensions FIRST, then geometric constraints.
        # Dimension + on-line coincident together determine point position.
        # Dimension first: sets distance along axis. Coincident second:
        # snaps to the projected edge (compatible, not over-constraining).
        if dims:
            self._w(f"d = {var}.sketchDimensions")
            for di, d in enumerate(dims):
                dtype = d.get("type", "")
                expr = d.get("expression")
                if not expr:
                    continue

                if dtype == "SketchLinearDimension":
                    e1 = d.get("entityOne")
                    e2 = d.get("entityTwo")
                    orient = d.get("orientation", "Horizontal")
                    # Downgrade Aligned → H/V when endpoints are axis-aligned
                    # (minor component < 0.01). Aligned produces less stable
                    # constraint solving than H/V for such pairs.
                    if orient == "Aligned" and e1 and e2:
                        # Use original curves (before BRepFace filtering) for index lookup
                        _orig = feat.get("curves", [])
                        p1 = self._sketch_entity_pt(e1, _orig)
                        p2 = self._sketch_entity_pt(e2, _orig)
                        if p1 and p2:
                            dx = abs(p1[0] - p2[0])
                            dy = abs(p1[1] - p2[1])
                            if dy < 0.01 and dx > 0.01:
                                orient = "Horizontal"
                            elif dx < 0.01 and dy > 0.01:
                                orient = "Vertical"
                    orient_map = {
                        "Horizontal": "H",
                        "Vertical": "V",
                        "Aligned": "adsk.fusion.DimensionOrientations.AlignedDimensionOrientation",
                    }
                    orient_code = orient_map.get(orient, "H")
                    if _has_coord_xf and orient in ("Horizontal", "Vertical"):
                        # Swap H/V when transform rotates axes
                        if orient == "Horizontal":
                            orient_code = "H if abs(_m10) < 0.5 else V"
                        else:
                            orient_code = "V if abs(_m01) < 0.5 else H"

                    e1_code = self._resolve_sketch_entity_ref(e1, curve_vars, var, _proj_curve_pts)
                    e2_code = self._resolve_sketch_entity_ref(e2, curve_vars, var, _proj_curve_pts)
                    if (_has_body_projs and e1_code and e2_code
                            and "_nearest_proj" in str(e1_code)
                            and "_nearest_proj" in str(e2_code)):
                        self._c(f"dim[{di}]: {expr} (both endpoints from intersection)")
                        continue
                    # Keep dims for on-edge endpoints — makes them parametric.
                    # (on-line coincident constraints are skipped separately)
                    if e1_code and e2_code:
                        self._w(f"try:")
                        self.ind += 1
                        self._w(f"d.addDistanceDimension({e1_code}, {e2_code},")
                        self.ind += 1
                        self._w(f'{orient_code}, P(0, 0, 0)).parameter.expression = "{expr}"')
                        self.ind -= 2
                        self._w(f"except: pass  # skip if already constrained")
                    else:
                        self._c(f"TODO: dim[{di}] {dtype}: {expr} (targets not resolved)")

                elif dtype == "SketchDiameterDimension":
                    entity = d.get("entity")
                    entity_code = self._resolve_sketch_curve_ref(entity, curve_vars)
                    if entity_code:
                        val = d.get("value", 1)
                        self._w(f'd.addDiameterDimension({entity_code}, P({val + 1}, 0, 0)).parameter.expression = "{expr}"')
                    else:
                        self._c(f"TODO: dim[{di}] {dtype}: {expr}")

                elif dtype == "SketchRadialDimension":
                    entity = d.get("entity")
                    entity_code = self._resolve_sketch_curve_ref(entity, curve_vars)
                    if entity_code:
                        val = d.get("value", 1)
                        self._w(f'd.addRadialDimension({entity_code}, P({val + 1}, 0, 0)).parameter.expression = "{expr}"')
                    else:
                        self._c(f"TODO: dim[{di}] {dtype}: {expr}")

                elif dtype == "SketchAngularDimension":
                    l1 = d.get("lineOne")
                    l2 = d.get("lineTwo")
                    l1_code = self._resolve_sketch_entity_ref(l1, curve_vars, var, _proj_curve_pts)
                    l2_code = self._resolve_sketch_entity_ref(l2, curve_vars, var, _proj_curve_pts)
                    if l1_code and l2_code:
                        # Compute text point in the correct angular quadrant.
                        # The midpoint of the two "far" endpoints (not the
                        # shared intersection) lies between the two lines.
                        _txt = "P(0, 0, 0)"
                        _orig = feat.get("curves", [])
                        _l1i = l1.get("curveIndex") if isinstance(l1, dict) else None
                        _l2i = l2.get("curveIndex") if isinstance(l2, dict) else None
                        if (_l1i is not None and _l2i is not None
                                and _l1i < len(_orig) and _l2i < len(_orig)):
                            _c1 = _orig[_l1i]
                            _c2 = _orig[_l2i]
                            s1, e1 = _c1.get("start"), _c1.get("end")
                            s2, e2 = _c2.get("start"), _c2.get("end")
                            if s1 and e1 and s2 and e2:
                                # Find the shared point (start/start)
                                # and use midpoint of the far ends
                                _mx = (e1[0] + e2[0]) / 2
                                _my = (e1[1] + e2[1]) / 2
                                if _has_coord_xf:
                                    _txt = f"P(*_xf({round(_mx, 4)}, {round(_my, 4)}), 0)"
                                else:
                                    _txt = f"P({round(_mx, 4)}, {round(_my, 4)}, 0)"
                        self._w(f"try:")
                        self.ind += 1
                        self._w(f'd.addAngularDimension({l1_code}, {l2_code}, {_txt}).parameter.expression = "{expr}"')
                        self.ind -= 1
                        self._w(f"except: pass  # skip if already constrained")
                    else:
                        self._c(f"TODO: dim[{di}] {dtype}: {expr} = {d.get('value', 0)}")

                else:
                    self._c(f"TODO: dim[{di}] {dtype}: {expr} = {d.get('value', 0)}")

        if constraints and any(isinstance(c, dict) for c in constraints):
            self._w(f"gc = {var}.geometricConstraints")
            for ci, c in enumerate(constraints):
                if ci in _early_ci:
                    continue  # Already emitted before dimensions
                if isinstance(c, str):
                    # Legacy format (just type name, no targets)
                    continue
                ctype = c.get("type", "")

                # Wrap each constraint in try/except — constraints can fail
                # if geometry is already constrained (e.g., shared points,
                # collinear lines, or implicit constraints from line creation)
                call = None
                if ctype == "HorizontalConstraint":
                    line_ref = c.get("line")
                    line_code = self._resolve_sketch_curve_ref(line_ref, curve_vars)
                    if line_code:
                        if _has_coord_xf:
                            # Swap H/V when transform rotates axes
                            call = f"(gc.addHorizontal if abs(_m10) < 0.5 else gc.addVertical)({line_code})"
                        else:
                            call = f"gc.addHorizontal({line_code})"

                elif ctype == "VerticalConstraint":
                    line_ref = c.get("line")
                    line_code = self._resolve_sketch_curve_ref(line_ref, curve_vars)
                    if line_code:
                        if _has_coord_xf:
                            call = f"(gc.addVertical if abs(_m01) < 0.5 else gc.addHorizontal)({line_code})"
                        else:
                            call = f"gc.addVertical({line_code})"

                elif ctype == "CoincidentConstraint":
                    pt_ref = c.get("point")
                    ent_ref = c.get("entity")
                    pt_ci = pt_ref.get("curveIndex") if pt_ref else None
                    pt_role = pt_ref.get("role", "") if pt_ref else ""
                    if pt_ci is not None and (pt_ci, pt_role) in _on_edge_pts:
                        continue
                    pt_code = self._resolve_sketch_entity_ref(
                        pt_ref, curve_vars, var, _proj_curve_pts)
                    ent_code = self._resolve_sketch_entity_ref(
                        ent_ref, curve_vars, var, _proj_curve_pts)
                    if pt_code and ent_code and pt_code != ent_code:
                        call = f"gc.addCoincident({pt_code}, {ent_code})"

                elif ctype == "ParallelConstraint":
                    l1 = self._resolve_sketch_curve_ref(c.get("lineOne"), curve_vars)
                    l2 = self._resolve_sketch_curve_ref(c.get("lineTwo"), curve_vars)
                    if l1 and l2:
                        call = f"gc.addParallel({l1}, {l2})"

                elif ctype == "PerpendicularConstraint":
                    l1 = self._resolve_sketch_curve_ref(c.get("lineOne"), curve_vars)
                    l2 = self._resolve_sketch_curve_ref(c.get("lineTwo"), curve_vars)
                    if l1 and l2:
                        call = f"gc.addPerpendicular({l1}, {l2})"

                elif ctype == "TangentConstraint":
                    c1 = self._resolve_sketch_curve_ref(c.get("curveOne"), curve_vars)
                    c2 = self._resolve_sketch_curve_ref(c.get("curveTwo"), curve_vars)
                    if c1 and c2:
                        call = f"gc.addTangent({c1}, {c2})"

                elif ctype == "EqualConstraint":
                    c1 = self._resolve_sketch_curve_ref(c.get("curveOne"), curve_vars)
                    c2 = self._resolve_sketch_curve_ref(c.get("curveTwo"), curve_vars)
                    if c1 and c2:
                        call = f"gc.addEqual({c1}, {c2})"

                elif ctype == "MidPointConstraint":
                    pt_code = self._resolve_sketch_entity_ref(
                        c.get("point"), curve_vars, var, _proj_curve_pts)
                    crv_code = self._resolve_sketch_curve_ref(
                        c.get("midPointCurve"), curve_vars)
                    if pt_code and crv_code:
                        call = f"gc.addMidPoint({pt_code}, {crv_code})"

                elif ctype == "SymmetryConstraint":
                    e1 = self._resolve_sketch_entity_ref(
                        c.get("entityOne"), curve_vars, var, _proj_curve_pts)
                    e2 = self._resolve_sketch_entity_ref(
                        c.get("entityTwo"), curve_vars, var, _proj_curve_pts)
                    sym_line = self._resolve_sketch_curve_ref(
                        c.get("symmetryLine"), curve_vars)
                    if e1 and e2 and sym_line:
                        call = f"gc.addSymmetry({e1}, {e2}, {sym_line})"

                if call:
                    self._w(f"try: {call}")
                    self._w(f"except: pass")

        # Profile — use item(0) by default; the extrude/sweep emitter
        # uses the captured profileIndex to select the correct profile.
        prof = f"{var}_prof"
        prof_count = feat.get("profileCount", 1)
        if prof_count > 0:
            self._w(f"{prof} = {var}.profiles.item(0) if {var}.profiles.count > 0 else None  # {prof_count} profile(s)")
            self.profiles[name] = prof

    def _find_online_constraint(self, feat, curve_idx, role):
        """Find if a curve endpoint has a coincident-on-line constraint.

        Searches the captured constraints for a CoincidentConstraint where
        point=(curveIndex=curve_idx, role=role) and entity is a SketchLine.
        Returns the curveIndex of the line, or None.
        """
        for c in feat.get("constraints", []):
            if not isinstance(c, dict):
                continue
            if c.get("type") != "CoincidentConstraint":
                continue
            pt = c.get("point", {})
            ent = c.get("entity", {})
            if (pt.get("curveIndex") == curve_idx and pt.get("role") == role
                    and ent.get("type") == "SketchLine"):
                return ent.get("curveIndex")
        return None

    def _resolve_sketch_entity_ref(self, ref, curve_vars, sk_var, proj_curve_pts=None):
        """Resolve a captured sketch entity reference to a code string."""
        if not ref:
            return None
        rtype = ref.get("type", "")
        ci = ref.get("curveIndex")
        role = ref.get("role", "")

        if rtype == "SketchPoint":
            if role == "origin":
                return f"{sk_var}.originPoint"
            # For projected body curves, use _nearest_proj (curve direction
            # may be reversed, so startSketchPoint/endSketchPoint are unreliable).
            # Use _xf to transform captured coords if coord transform is active.
            if ci is not None and proj_curve_pts and (ci, role) in proj_curve_pts:
                x, y = proj_curve_pts[(ci, role)]
                return f"_nearest_proj(*_xf({x}, {y}))"
            if ci is not None and ci in curve_vars:
                cv = curve_vars[ci]
                if role == "start":
                    return f"{cv}.startSketchPoint"
                elif role == "end":
                    return f"{cv}.endSketchPoint"
                elif role == "center":
                    return f"{cv}.centerSketchPoint"
                elif role == "fitPoint":
                    fi = ref.get("fitIndex", 0)
                    return f"{cv}.fitPoints.item({fi})"
            # Fallback: unresolvable sketch point — return None to skip constraint
            return None

        if rtype in ("SketchLine", "SketchArc", "SketchCircle", "SketchFittedSpline"):
            return self._resolve_sketch_curve_ref(ref, curve_vars)

        return None

    def _resolve_sketch_curve_ref(self, ref, curve_vars):
        """Resolve a captured sketch curve reference to a code string."""
        if not ref:
            return None
        ci = ref.get("curveIndex")
        if ci is not None and ci in curve_vars:
            return curve_vars[ci]
        return None
