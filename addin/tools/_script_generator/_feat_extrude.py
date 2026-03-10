"""Extrude mixin: extrude, sweep, move features."""


def _fmt_pt(pt):
    """Format a 3D point list for comments."""
    return f"({pt[0]:.2f}, {pt[1]:.2f}, {pt[2]:.2f})"


class _ExtrudeMixin:
    """Feature emitters for extrude, sweep, and move operations."""

    def _emit_extrude_extent(self, f, dist, taper, flipped):
        """Emit extent, taper settings on the 'inp' variable."""
        extent = f.get("extentType", "Distance")
        if f.get("hasTwoExtents"):
            d2 = f.get("distanceTwo", "1 cm")
            t2 = f.get("taperAngleTwo")
            taper_args = ""
            if taper and taper not in ("0.0 deg", "0 deg"):
                taper_args += f',\n{"    " * (self.ind+1)}adsk.core.ValueInput.createByString("{taper}")'
                if t2 and t2 not in ("0.0 deg", "0 deg"):
                    taper_args += f',\n{"    " * (self.ind+1)}adsk.core.ValueInput.createByString("{t2}")'
            self._w("inp.setTwoSidesExtent(")
            self.ind += 1
            self._w(f'adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString("{dist}")),')
            self._w(f'adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString("{d2}")){taper_args})')
            self.ind -= 1
        elif extent == "Symmetric":
            self._w(f'inp.setSymmetricExtent(adsk.core.ValueInput.createByString("{dist}"), True)')
        elif flipped:
            self._w("inp.setOneSideExtent(")
            self.ind += 1
            self._w(f'adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString("{dist}")),')
            self._w("adsk.fusion.ExtentDirections.NegativeExtentDirection)")
            self.ind -= 1
        else:
            self._w(f'inp.setDistanceExtent(False, adsk.core.ValueInput.createByString("{dist}"))')

        if not f.get("hasTwoExtents") and taper and taper not in ("0.0 deg", "0 deg"):
            self._w(f'inp.taperAngle = adsk.core.ValueInput.createByString("{taper}")')

    def _emit_extrude_participants(self, f, op, bodies, participants, dist, sketch):
        """Emit participantBodies on the 'inp' variable."""
        if participants and op in ("Cut", "Join"):
            self._w(f"inp.participantBodies = {self._body_list(participants)}")
        elif not participants and op in ("Cut", "Join") and bodies:
            self._w(f"inp.participantBodies = {self._body_list(bodies)}")
        elif not participants and op == "Join" and not bodies:
            sketch_feat = None
            for tf in self.cap.get("timeline", []):
                if tf.get("type") == "Sketch" and tf.get("name") == sketch:
                    sketch_feat = tf
            if sketch_feat:
                sk_plane = sketch_feat.get("plane", {})
                if sk_plane.get("type") == "BRepFace" and sk_plane.get("body"):
                    plane_body = sk_plane["body"]
                    pb_ref = self._body_ref(plane_body)
                    is_negative = dist.lstrip().startswith("-")
                    if is_negative:
                        self._w(f'_pb = [comp.bRepBodies.item(_i) for _i in range(comp.bRepBodies.count) if comp.bRepBodies.item(_i).name != "{plane_body}"]')
                        self._w(f"if _pb: inp.participantBodies = _pb")
                    else:
                        self._w(f"if {pb_ref}: inp.participantBodies = [{pb_ref}]")

    def _feat_extrude(self, f):
        name = f.get("name", "Extrude")
        fvar = self._var(name)

        # Face-based extrude with inaccessible profile — can't reconstruct
        if f.get("profileType") in ("BRepFace", "Inaccessible"):
            self._c(f"TODO: face-based or inaccessible profile extrude '{name}'")
            self.feats[name] = "None"
            for bn in f.get("bodies", []):
                self._register_body(bn, "None")
            return

        op = f.get("operation", "NewBody")
        dist = f.get("distance", "1 cm")
        sketch = f.get("sketch", "")
        pidx = f.get("profileIndex", 0)
        taper = f.get("taperAngle")
        bodies = f.get("bodies", [])
        participants = f.get("participantBodies", [])
        flipped = f.get("isDirectionFlipped", False)

        # Detect negative-wrapped expressions: "-( expr )" means the extrude went
        # opposite to the sketch plane normal. Unwrap and set flip.
        if dist.startswith("-(") and dist.endswith(")"):
            dist = dist[2:-1].strip()
            flipped = True

        op_map = {"NewBody": "NEWBODY", "Cut": "CUT", "Join": "JOIN",
                  "Intersect": "adsk.fusion.FeatureOperations.IntersectFeatureOperation"}
        op_code = op_map.get(op, "NEWBODY")

        # Profile reference — match by bounding box from capture when available
        prof = None
        # Find the sketch feature that matches by name AND component
        sketch_feat = None
        sketch_comp = f.get("sketchComponent", f.get("component", ""))
        feat_idx = f.get("index", len(self.cap.get("timeline", [])))
        for ti, tf in enumerate(self.cap.get("timeline", [])):
            if ti >= feat_idx:
                break
            if (tf.get("type") == "Sketch" and tf.get("name") == sketch
                    and tf.get("component", "") == sketch_comp):
                sketch_feat = tf
        if sketch_feat is None:
            # Fallback: match by name only (last one before this extrude)
            for ti, tf in enumerate(self.cap.get("timeline", [])):
                if ti >= feat_idx:
                    break
                if tf.get("type") == "Sketch" and tf.get("name") == sketch:
                    sketch_feat = tf
        # Cross-component cplane direction fix: when the sketch is on a
        # BRepFace from another component, the generator creates a construction
        # plane instead.  The cplane normal (XDir × YDir) may be opposite to
        # the face normal, requiring an extrude direction flip.
        # Forward-reference detection: if the face body doesn't exist yet,
        # the sketch also lacks face boundary profiles → reduce multi-profile.
        _fwd_ref_cplane = False
        if sketch_feat:
            _sk_plane = sketch_feat.get("plane", {})
            if _sk_plane.get("type") == "BRepFace":
                _sk_comp = sketch_feat.get("component", "")
                _sk_body = _sk_plane.get("body", "")
                if _sk_comp and _sk_body and _sk_comp != self._root_name:
                    _sk_fk = f"{_sk_comp}:{_sk_body}"
                    # Check if body exists in same component, any component,
                    # or not at all.
                    _in_same_comp = _sk_fk in self.bodies
                    _in_any_comp = (_in_same_comp
                                    or _sk_body in self.bodies
                                    or any(k.endswith(f":{_sk_body}")
                                           for k in self.bodies))
                    # Direction flip needed only when generator used a cplane
                    # instead of the native face.  Determine this from sketch
                    # characteristics (can't rely on _use_native_face flag due
                    # to deep-copy of timeline in Generator.__init__).
                    # Native face is used when: body exists in some component,
                    # no body/edge projections, and not full boundary overlap.
                    _sk_refs = [c for c in sketch_feat.get("curves", [])
                                if c.get("isReference")]
                    _has_bproj = any(
                        c.get("projectedFrom", {}).get("type") == "BRepBody"
                        for c in _sk_refs)
                    _has_eproj = any(
                        c.get("projectedFrom", {}).get("type") == "BRepEdge"
                        for c in _sk_refs)
                    # Body projections → cplane used; edge projections → cplane;
                    # forward-ref (body not in any comp) → cplane.
                    # Otherwise native face → no direction flip needed.
                    _used_cplane = (not _in_any_comp
                                    or _has_bproj or _has_eproj)
                    if _used_cplane:
                        _xd = sketch_feat.get("sketchXDir", [1, 0, 0])
                        _yd = sketch_feat.get("sketchYDir", [0, 1, 0])
                        _fn = [_xd[1]*_yd[2]-_xd[2]*_yd[1],
                               _xd[2]*_yd[0]-_xd[0]*_yd[2],
                               _xd[0]*_yd[1]-_xd[1]*_yd[0]]
                        _ax, _ay, _az = abs(_fn[0]), abs(_fn[1]), abs(_fn[2])
                        if _az >= _ay and _az >= _ax:
                            if _fn[2] < 0: flipped = not flipped
                        elif _ay >= _ax:
                            if _fn[1] < 0: flipped = not flipped
                        else:
                            if _fn[0] < 0: flipped = not flipped
                    if not _in_any_comp:
                        _fwd_ref_cplane = True
            # Fallback: flag set during full script generation
            if sketch_feat.get("_cplane_extrude_flip"):
                flipped = not flipped
        cap_profiles = sketch_feat.get("profiles", []) if sketch_feat else []
        profile_indices = f.get("profileIndices", [pidx])
        # Forward-reference cplane: face boundary profiles don't exist on the
        # cplane sketch, so reduce multi-profile to single profile.
        if _fwd_ref_cplane and len(profile_indices) > 1:
            profile_indices = [profile_indices[0]]
        target_profs = [
            next((p for p in cap_profiles if p.get("index") == idx), None)
            for idx in profile_indices
        ]
        target_profs = [t for t in target_profs if t is not None]

        # When sketchError prevents profile access, captured bboxes may be from
        # sketch creation time — not the extrude's timeline position.  Face sketch
        # boundaries auto-update when JOINs/CUTs modify the body, so bbox matching
        # against stale data picks the wrong profile.  Fall through to direct
        # profile-index selection from the rebuilt sketch's actual profiles.
        if f.get("sketchError"):
            target_profs = []

        # Look up sketch variable by component-scoped key first
        sk_key = f"{sketch_comp}:{sketch}" if sketch_comp else sketch
        sk_var = self.sketches.get(sk_key, self.sketches.get(sketch))

        # Determine coordinate transform availability
        cap_xd = sketch_feat.get("sketchXDir") if sketch_feat else None
        cap_yd = sketch_feat.get("sketchYDir") if sketch_feat else None
        has_xf = bool(cap_xd and cap_yd)

        if target_profs and sk_var:
            is_multi = len(target_profs) > 1

            # Detect cross-component multi-profile: ObjectCollection of profiles
            # from a root-level sketch can't be used in a child component's
            # createInput — Fusion doesn't auto-proxy ObjectCollection contents.
            # Use sequential single-profile extrudes instead.
            # Triggers when: _sketch_owners says "root" (set by _feat_sketch
            # during full script generation), OR _force_sequential flag is set
            # (set by _extrude_variants for search builder per-feature scripts).
            sk_owner_key = f"{sketch_comp}:{sketch}" if sketch_comp else sketch
            sk_owner = self._sketch_owners.get(sk_owner_key,
                           self._sketch_owners.get(sketch, ""))
            cross_comp_multi = (is_multi
                and (sk_owner == "root" or f.get("_force_sequential"))
                and self._comp_ref(f) != "root")

            # Emit coordinate transform (once, reused for all profiles)
            if has_xf:
                self._w(f"_cx = ({cap_xd[0]}, {cap_xd[1]}, {cap_xd[2]})")
                self._w(f"_cy = ({cap_yd[0]}, {cap_yd[1]}, {cap_yd[2]})")
                self._w(f"_ax = {sk_var}.xDirection")
                self._w(f"_ay = {sk_var}.yDirection")
                self._w(f"_m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z")
                self._w(f"_m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z")
                self._w(f"_m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z")
                self._w(f"_m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z")
                # Origin delta for profile BB matching
                cap_origin = sketch_feat.get("sketchOrigin") if sketch_feat else None
                if cap_origin:
                    self._w(f"_co = ({cap_origin[0]}, {cap_origin[1]}, {cap_origin[2]})")
                    self._w(f"_ao = {sk_var}.origin")
                    self._w(f"_od = (_co[0]-_ao.x, _co[1]-_ao.y, _co[2]-_ao.z)")
                    self._w(f"_odx = _od[0]*_ax.x + _od[1]*_ax.y + _od[2]*_ax.z")
                    self._w(f"_ody = _od[0]*_ay.x + _od[1]*_ay.y + _od[2]*_ay.z")
                else:
                    self._w(f"_odx, _ody = 0, 0")

            if is_multi:
                if cross_comp_multi:
                    self._c(f"Cross-component multi-profile: {len(target_profs)} sequential extrudes")
                    self._w(f"_matched_pis = []")
                else:
                    self._c(f"Multi-profile extrude: {len(target_profs)} profiles")
                    self._w(f"_prof_coll = adsk.core.ObjectCollection.create()")
                self._w(f"_used = set()")

            for ti, tp in enumerate(target_profs):
                mn = tp["min"]
                mx = tp["max"]
                t_mnx, t_mny = round(mn[0], 4), round(mn[1], 4)
                t_mxx, t_mxy = round(mx[0], 4), round(mx[1], 4)
                if has_xf:
                    self._c(f"Match profile by bbox (transformed): ({t_mnx}, {t_mny}) to ({t_mxx}, {t_mxy})")
                    self._w(f"_t1 = ({t_mnx}*_m00 + {t_mny}*_m01 + _odx, {t_mnx}*_m10 + {t_mny}*_m11 + _ody)")
                    self._w(f"_t2 = ({t_mxx}*_m00 + {t_mxy}*_m01 + _odx, {t_mxx}*_m10 + {t_mxy}*_m11 + _ody)")
                    self._w(f"_t_mnx, _t_mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])")
                    self._w(f"_t_mxx, _t_mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])")
                    t_ref = ("_t_mnx", "_t_mny", "_t_mxx", "_t_mxy")
                else:
                    self._c(f"Match profile by bbox: ({t_mnx}, {t_mny}) to ({t_mxx}, {t_mxy})")
                    t_ref = (f"({t_mnx})", f"({t_mny})", f"({t_mxx})", f"({t_mxy})")
                self._w(f"_best_pi, _best_d = 0, 1e10")
                self._w(f"for _pi in range({sk_var}.profiles.count):")
                self.ind += 1
                if is_multi:
                    self._w(f"if _pi in _used: continue")
                self._w(f"_bb = {sk_var}.profiles.item(_pi).boundingBox")
                self._w(f"_d = abs(_bb.minPoint.x - {t_ref[0]}) + abs(_bb.minPoint.y - {t_ref[1]}) + abs(_bb.maxPoint.x - {t_ref[2]}) + abs(_bb.maxPoint.y - {t_ref[3]})")
                self._w(f"if _d < _best_d: _best_pi, _best_d = _pi, _d")
                self.ind -= 1
                if is_multi:
                    if cross_comp_multi:
                        self._w(f"_matched_pis.append(_best_pi)")
                    else:
                        self._w(f"_prof_coll.add({sk_var}.profiles.item(_best_pi))")
                    self._w(f"_used.add(_best_pi)")

            # Cross-component multi-profile: sequential single-profile extrudes.
            # For NewBody: first profile creates the body, subsequent profiles
            # JOIN into it to produce a single merged body (matching the
            # ObjectCollection behavior that creates one body from N profiles).
            if cross_comp_multi:
                # Track face-based sketch usage for offset computation
                _sk_off_key = f"{sketch_comp}:{sketch}" if sketch_comp else sketch
                _is_face_sk = (_sk_off_key in self._brep_face_sketches
                               or sketch in self._brep_face_sketches)
                if _is_face_sk:
                    dists = self._face_sketch_extrude_dists.get(_sk_off_key, [])
                    dists.append(f.get("distance", dist))
                    self._face_sketch_extrude_dists[_sk_off_key] = dists
                self._w(f"_ext_results = []")
                self._w(f"for _idx, _mi in enumerate(_matched_pis):")
                self.ind += 1
                if op == "NewBody":
                    self._w(f"_op = NEWBODY if _idx == 0 else JOIN")
                    self._w(f"inp = comp.features.extrudeFeatures.createInput({sk_var}.profiles.item(_mi), _op)")
                else:
                    self._w(f"inp = comp.features.extrudeFeatures.createInput({sk_var}.profiles.item(_mi), {op_code})")
                self._emit_extrude_extent(f, dist, taper, flipped)
                self._emit_extrude_participants(f, op, bodies, participants, dist, sketch)
                if op == "NewBody":
                    self._w(f"if _idx > 0: inp.participantBodies = [_ext_results[0].bodies.item(0)]")
                self._w(f"_ext_results.append(comp.features.extrudeFeatures.add(inp))")
                self.ind -= 1
                self._w(f'_ext_results[0].name = "{name}"')
                self.feats[name] = "_ext_results[0]"
                if bodies:
                    for i, bn in enumerate(bodies):
                        bv = self._body_var(bn)
                        if bv == fvar:
                            bv = bv + "_b"
                        self._register_body(bn, bv)
                        self._w(f"{bv} = _ext_results[{i}].bodies.item(0)")
                        self._w(f'{bv}.name = "{bn}"')
                elif op == "NewBody":
                    bv = self._body_var(name)
                    if bv == fvar:
                        bv = bv + "_b"
                    self._register_body(name, bv)
                    self._w(f"{bv} = _ext_results[0].bodies.item(0)")
                    self._w(f'{bv}.name = "{name}"')
                return

            if is_multi:
                prof = "_prof_coll"
            else:
                prof = f"{sk_var}.profiles.item(_best_pi) if {sk_var}.profiles.count > 0 else None"
        elif sketch in self.profiles:
            prof = self.profiles[sketch]
        elif sk_var:
            prof = f"{sk_var}.profiles.item({pidx}) if {sk_var} and {sk_var}.profiles.count > {pidx} else None"
        else:
            self._c(f"TODO: sketch '{sketch}' not tracked")
            prof = "None"

        self._w(f"inp = comp.features.extrudeFeatures.createInput({prof}, {op_code})")
        self._emit_extrude_extent(f, dist, taper, flipped)

        # Face-following sketch offset: when a face-based sketch is reused
        # by multiple extrudes, Fusion's parametric model moves the sketch
        # with the face. Whether offset is needed depends on profile overlap
        # (handled as a variant in _extrude_variants).
        # Here we just track the distance for variant computation and apply
        # the offset if _offset_expr was set by the variant system.
        sk_offset_key = f"{sketch_comp}:{sketch}" if sketch_comp else sketch
        is_face_sketch = (sk_offset_key in self._brep_face_sketches
                          or sketch in self._brep_face_sketches)
        offset_expr = f.get("_offset_expr")
        if offset_expr:
            self._w(f"inp.startExtent = adsk.fusion.OffsetStartDefinition.create(")
            self._w(f'    adsk.core.ValueInput.createByString("{offset_expr}"))')
        if is_face_sketch:
            dists = self._face_sketch_extrude_dists.get(sk_offset_key, [])
            dists.append(f.get("distance", dist))
            self._face_sketch_extrude_dists[sk_offset_key] = dists

        self._emit_extrude_participants(f, op, bodies, participants, dist, sketch)

        self._w(f"{fvar} = comp.features.extrudeFeatures.add(inp)")
        self._w(f'{fvar}.name = "{name}"')
        self.feats[name] = fvar

        if bodies:
            for i, bn in enumerate(bodies):
                bv = self._body_var(bn)
                # Avoid collision with feature variable
                if bv == fvar:
                    bv = bv + "_b"
                self._register_body(bn, bv)
                self._w(f"{bv} = {fvar}.bodies.item({i})")
                self._w(f'{bv}.name = "{bn}"')
        elif op == "NewBody":
            bv = self._body_var(name)
            if bv == fvar:
                bv = bv + "_b"
            self._register_body(name, bv)
            self._w(f"{bv} = {fvar}.bodies.item(0)")
            self._w(f'{bv}.name = "{name}"')

    def _feat_move(self, f):
        name = f.get("name", "Move")
        matrix = f.get("matrix")
        inputs = f.get("inputs", [])

        if not matrix:
            self._c("TODO: Move with no matrix data")
            return

        self._w("xform = adsk.core.Matrix3D.create()")
        vals = [matrix[r][c] for r in range(4) for c in range(4)]
        self._w(f"xform.setWithArray({vals})")

        self._w("move_coll = adsk.core.ObjectCollection.create()")
        if inputs:
            for inp_name in inputs:
                bv = self._body_ref(inp_name)
                self._w(f"move_coll.add({bv})")
        else:
            self._c("TODO: No input entities captured — add the body to move")
            self._w("# move_coll.add(body)")

        self._w("move_inp = comp.features.moveFeatures.createInput2(move_coll)")
        self._w("move_inp.defineAsFreeMove(xform)")
        self._w(f'move_feat = comp.features.moveFeatures.add(move_inp)')
        self._w(f'move_feat.name = "{name}"')
        self.feats[name] = "move_feat"

    def _feat_sweep(self, f):
        name = f.get("name", "Sweep")
        op = f.get("operation", "NewBody")
        sketch_name = f.get("sketch", "")
        pidx = f.get("profileIndex", 0)
        pcoll_count = f.get("profileCollectionCount", 1)
        path_ents = f.get("path", [])
        participants = f.get("participantBodies", [])
        bodies = f.get("bodies", [])
        orientation = f.get("orientation", "Perpendicular")

        op_map = {"NewBody": "NEWBODY", "Cut": "CUT", "Join": "JOIN"}
        op_code = op_map.get(op, "NEWBODY")

        # Profile
        indices = f.get("profileIndices", [])
        if not indices:
            indices = [pidx]

        sweep_comp = f.get("sketchComponent", f.get("component", ""))
        sweep_sk_key = f"{sweep_comp}:{sketch_name}" if sweep_comp else sketch_name
        sk_var = self.sketches.get(sweep_sk_key, self.sketches.get(sketch_name))
        if not sk_var:
            self._c(f"TODO: sketch '{sketch_name}' not tracked")
            prof_code = "None"
        elif pcoll_count > 1:
            # Multi-profile sweep: match profiles by bounding box
            # from the capture data. This handles profile count/ordering changes
            # from BRepFace→find_face conversion.
            pdims = f.get("profileDims", [])
            # Look up sketch's captured profiles for full bounding box data
            sketch_feat = None
            feat_idx = f.get("index", len(self.cap.get("timeline", [])))
            for ti, tf in enumerate(self.cap.get("timeline", [])):
                if ti >= feat_idx:
                    break
                if tf.get("type") == "Sketch" and tf.get("name") == sketch_name:
                    sketch_feat = tf
            cap_profiles = sketch_feat.get("profiles", []) if sketch_feat else []
            # Try to resolve full bounding boxes for each profileDims entry
            pd_bboxes = []
            if pdims and cap_profiles:
                used_cp = set()
                for pd in pdims:
                    tw, th = pd[0], pd[1]
                    best_cp, best_d = None, 1e10
                    for ci, cp in enumerate(cap_profiles):
                        if ci in used_cp:
                            continue
                        cpw = abs(cp["max"][0] - cp["min"][0])
                        cph = abs(cp["max"][1] - cp["min"][1])
                        d = abs(cpw - tw) + abs(cph - th)
                        if d < best_d:
                            best_d = d
                            best_cp = (ci, cp)
                    if best_cp and best_d < 0.01:
                        used_cp.add(best_cp[0])
                        pd_bboxes.append(best_cp[1])
                    else:
                        pd_bboxes.append(None)
            use_bbox = pd_bboxes and all(b is not None for b in pd_bboxes)
            # Get sketch axes for coordinate transform
            cap_xd = sketch_feat.get("sketchXDir") if sketch_feat else None
            cap_yd = sketch_feat.get("sketchYDir") if sketch_feat else None
            self._w("sweep_profs = adsk.core.ObjectCollection.create()")
            if use_bbox:
                # Full bounding box matching — distinguishes profiles by position
                if cap_xd and cap_yd:
                    # Transform captured bbox to actual sketch coordinate space
                    self._w(f"_cx = ({cap_xd[0]}, {cap_xd[1]}, {cap_xd[2]})")
                    self._w(f"_cy = ({cap_yd[0]}, {cap_yd[1]}, {cap_yd[2]})")
                    self._w(f"_ax = {sk_var}.xDirection")
                    self._w(f"_ay = {sk_var}.yDirection")
                    self._w(f"_m00 = _cx[0]*_ax.x + _cx[1]*_ax.y + _cx[2]*_ax.z")
                    self._w(f"_m01 = _cy[0]*_ax.x + _cy[1]*_ax.y + _cy[2]*_ax.z")
                    self._w(f"_m10 = _cx[0]*_ay.x + _cx[1]*_ay.y + _cx[2]*_ay.z")
                    self._w(f"_m11 = _cy[0]*_ay.x + _cy[1]*_ay.y + _cy[2]*_ay.z")
                self._w("_target_bboxes = [")
                self.ind += 1
                for bb in pd_bboxes:
                    mn, mx = bb["min"], bb["max"]
                    self._w(f"({round(mn[0], 4)}, {round(mn[1], 4)}, {round(mx[0], 4)}, {round(mx[1], 4)}),")
                self.ind -= 1
                self._w("]")
                self._w("_used = set()")
                self._w("for _c_mnx, _c_mny, _c_mxx, _c_mxy in _target_bboxes:")
                self.ind += 1
                if cap_xd and cap_yd:
                    self._w("_t1 = (_c_mnx*_m00 + _c_mny*_m01, _c_mnx*_m10 + _c_mny*_m11)")
                    self._w("_t2 = (_c_mxx*_m00 + _c_mxy*_m01, _c_mxx*_m10 + _c_mxy*_m11)")
                    self._w("_mnx, _mny = min(_t1[0], _t2[0]), min(_t1[1], _t2[1])")
                    self._w("_mxx, _mxy = max(_t1[0], _t2[0]), max(_t1[1], _t2[1])")
                else:
                    self._w("_mnx, _mny, _mxx, _mxy = _c_mnx, _c_mny, _c_mxx, _c_mxy")
                self._w("_best_pi, _best_d = -1, 1e10")
                self._w(f"for _pi in range({sk_var}.profiles.count):")
                self.ind += 1
                self._w("if _pi not in _used:")
                self.ind += 1
                self._w(f"_bb = {sk_var}.profiles.item(_pi).boundingBox")
                self._w(f"_d = abs(_bb.minPoint.x - _mnx) + abs(_bb.minPoint.y - _mny) + abs(_bb.maxPoint.x - _mxx) + abs(_bb.maxPoint.y - _mxy)")
                self._w(f"if _d < _best_d: _best_pi, _best_d = _pi, _d")
                self.ind -= 2
                self._w(f"if _best_pi >= 0:")
                self.ind += 1
                self._w(f"sweep_profs.add({sk_var}.profiles.item(_best_pi))")
                self._w(f"_used.add(_best_pi)")
                self.ind -= 2
            elif pdims:
                # Fallback: match by dimensions only (when sketch profiles lack bounding box data)
                self._w("_target_dims = [")
                self.ind += 1
                for pd in pdims:
                    self._w(f"({pd[0]}, {pd[1]}),")
                self.ind -= 1
                self._w("]")
                self._w("_used = set()")
                self._w("for _tw, _th in _target_dims:")
                self.ind += 1
                self._w("_best_pi, _best_d = -1, 1e10")
                self._w(f"for _pi in range({sk_var}.profiles.count):")
                self.ind += 1
                self._w("if _pi not in _used:")
                self.ind += 1
                self._w(f"_bb = {sk_var}.profiles.item(_pi).boundingBox")
                self._w(f"_w = abs(_bb.maxPoint.x - _bb.minPoint.x)")
                self._w(f"_h = abs(_bb.maxPoint.y - _bb.minPoint.y)")
                self._w(f"_d = abs(_w - _tw) + abs(_h - _th)")
                self._w(f"if _d < _best_d: _best_pi, _best_d = _pi, _d")
                self.ind -= 2
                self._w(f"if _best_pi >= 0:")
                self.ind += 1
                self._w(f"sweep_profs.add({sk_var}.profiles.item(_best_pi))")
                self._w(f"_used.add(_best_pi)")
                self.ind -= 2
            else:
                # Fallback: N smallest non-trivial profiles
                self._w("_areas = []")
                self._w(f"for _pi in range({sk_var}.profiles.count):")
                self.ind += 1
                self._w(f"_bb = {sk_var}.profiles.item(_pi).boundingBox")
                self._w(f"_a = abs(_bb.maxPoint.x - _bb.minPoint.x) * abs(_bb.maxPoint.y - _bb.minPoint.y)")
                self._w(f"_areas.append((_a, _pi))")
                self.ind -= 1
                self._w("_max_a = max(a for a, _ in _areas) if _areas else 1")
                self._w("_cands = sorted((a, i) for a, i in _areas if a > _max_a * 0.001)")
                self._w(f"for _a, _pi in _cands[:{pcoll_count}]:")
                self.ind += 1
                self._w(f"sweep_profs.add({sk_var}.profiles.item(_pi))")
                self.ind -= 1
            prof_code = "sweep_profs"
        else:
            prof_code = f"{sk_var}.profiles.item({indices[0]})"

        # Path
        if path_ents:
            pe = path_ents[0]
            if pe.get("source") == "BRepEdge":
                body_name = pe.get("body", "")
                sv = pe.get("startVertex", [0, 0, 0])
                ev = pe.get("endVertex", [0, 0, 0])
                bv = self._body_ref(body_name)
                self._c(f"Path: edge on '{body_name}' from ~{_fmt_pt(sv)} to ~{_fmt_pt(ev)}")
                self._w(f"sweep_edge = None")
                self._w(f"for i in range({bv}.edges.count):")
                self.ind += 1
                self._w(f"e = {bv}.edges.item(i)")
                self._w(f"sp, ep = e.startVertex.geometry, e.endVertex.geometry")
                # Match by approximate vertex positions
                self._w(f"if (abs(sp.x - {sv[0]:.4f}) + abs(sp.y - {sv[1]:.4f}) + abs(sp.z - {sv[2]:.4f}) < 0.1 and")
                self._w(f"    abs(ep.x - {ev[0]:.4f}) + abs(ep.y - {ev[1]:.4f}) + abs(ep.z - {ev[2]:.4f}) < 0.1):")
                self.ind += 1
                self._w(f"sweep_edge = e")
                self._w(f"break")
                self.ind -= 2
                self._w(f"sweep_path = comp.features.createPath(sweep_edge)")
                # Detect path direction: check which end is closer to the
                # captured startVertex. If reversed, swap distance1/distance2.
                # createPath may reverse direction from edge vertex order.
                # Check isOpposedToEntity AND vertex proximity to determine
                # the actual path direction.
                self._w(f"_psv = sweep_edge.startVertex.geometry")
                self._w(f"_vtx_match = (abs(_psv.x - {sv[0]:.4f}) + abs(_psv.y - {sv[1]:.4f}) + abs(_psv.z - {sv[2]:.4f}) < 0.1)")
                self._w(f"_opposed = sweep_path.item(0).isOpposedToEntity")
                self._w(f"_path_fwd = not (_vtx_match != _opposed)")
                self._c("_path_fwd: True if path direction matches captured direction")
            elif pe.get("source") == "SketchCurve":
                sk_name = pe.get("parentSketch", "")
                self._c(f"Path: SketchCurve from '{sk_name}'")
                _path_sk = self.sketches.get(f"{sweep_comp}:{sk_name}", self.sketches.get(sk_name))
                if _path_sk:
                    self._w(f"sweep_path = comp.features.createPath({_path_sk}.sketchCurves.item(0))  # TODO: correct curve")
                else:
                    self._w(f"sweep_path = None  # TODO: sketch '{sk_name}'")
            else:
                self._w("sweep_path = None  # TODO: unknown path source")
        else:
            self._w("sweep_path = None  # TODO: no path captured")

        self._w(f"sweep_inp = comp.features.sweepFeatures.createInput({prof_code}, sweep_path, {op_code})")

        orient_map = {
            "Perpendicular": "adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType",
            "Parallel": "adsk.fusion.SweepOrientationTypes.ParallelOrientationType",
        }
        if orientation in orient_map:
            self._w(f"sweep_inp.orientation = {orient_map[orientation]}")

        # Distance extent (default is full path; distanceOne/Two are 0-1 fractions)
        # If path direction is reversed, swap distanceOne and distanceTwo
        dist1 = f.get("distanceOne")
        dist2 = f.get("distanceTwo")
        if dist1 and dist2:
            if path_ents and path_ents[0].get("source") == "BRepEdge":
                self._w(f"if _path_fwd:")
                self.ind += 1
                self._w(f'sweep_inp.distanceTwo = adsk.core.ValueInput.createByString("{dist2}")')
                self._w(f'sweep_inp.distanceOne = adsk.core.ValueInput.createByString("{dist1}")')
                self.ind -= 1
                self._w(f"else:")
                self.ind += 1
                self._w(f'sweep_inp.distanceTwo = adsk.core.ValueInput.createByString("{dist1}")')
                self._w(f'sweep_inp.distanceOne = adsk.core.ValueInput.createByString("{dist2}")')
                self.ind -= 1
            else:
                self._w(f'sweep_inp.distanceTwo = adsk.core.ValueInput.createByString("{dist2}")')
                self._w(f'sweep_inp.distanceOne = adsk.core.ValueInput.createByString("{dist1}")')
        elif dist1:
            self._w(f'sweep_inp.distanceOne = adsk.core.ValueInput.createByString("{dist1}")')

        # Taper and twist angles
        taper = f.get("taperAngle")
        if taper and taper != "0.0 deg" and taper != "0 deg":
            self._w(f'sweep_inp.taperAngle = adsk.core.ValueInput.createByString("{taper}")')
        twist = f.get("twistAngle")
        if twist and twist != "0.0 deg" and twist != "0 deg":
            self._w(f'sweep_inp.twistAngle = adsk.core.ValueInput.createByString("{twist}")')

        # Direction flip
        if f.get("isDirectionFlipped"):
            self._w(f"sweep_inp.isDirectionFlipped = True")

        if participants and op in ("Cut", "Join"):
            self._w(f"sweep_inp.participantBodies = {self._body_list(participants)}")

        self._w(f"sweep_feat = comp.features.sweepFeatures.add(sweep_inp)")
        self._w(f'sweep_feat.name = "{name}"')
        self.feats[name] = "sweep_feat"

        for i, bn in enumerate(bodies):
            bv = self._body_var(bn)
            self._register_body(bn, bv)
            self._w(f'{bv} = sweep_feat.bodies.item({i})')
            self._w(f'{bv}.name = "{bn}"')
