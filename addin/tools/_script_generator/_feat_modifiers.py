"""Modifiers mixin: split, remove, mirror, combine, fillet, chamfer."""

import re


class _ModifiersMixin:
    """Feature emitters for body-modifying operations and entity finders."""

    def _feat_splitbody(self, f):
        name = f.get("name", "Split")
        bodies = f.get("bodies", [])
        tool_info = f.get("splitTool", {})
        extend = f.get("isSplittingToolExtended", True)

        # Resolve input body: try tracked name, then runtime search with rename
        input_name = f.get("inputBody")
        body_code = None
        if input_name:
            # Try component-scoped key first
            split_comp_name = f.get("component", "")
            scoped_key = f"{split_comp_name}:{input_name}" if split_comp_name else ""
            if scoped_key and scoped_key in self.bodies:
                body_code = self.bodies[scoped_key]
            elif input_name in self.bodies:
                body_code = self.bodies[input_name]
            else:
                # Body may have been renamed between creation and split.
                # Emit runtime code that searches by name then renames to match.
                self._w(f'_split_body = find_body("{input_name}", comp)')
                self._w(f"if not _split_body:")
                self.ind += 1
                self._c(f'Body "{input_name}" not found — try largest body in comp')
                self._w(f"_biggest = None")
                self._w(f"for _bi in range(comp.bRepBodies.count):")
                self.ind += 1
                self._w(f"_b = comp.bRepBodies.item(_bi)")
                self._w(f"if _biggest is None or _b.volume > _biggest.volume: _biggest = _b")
                self.ind -= 1
                self._w(f"if _biggest:")
                self.ind += 1
                self._w(f"_split_body = _biggest")
                self._w(f'_split_body.name = "{input_name}"')
                self.ind -= 2
                body_code = "_split_body"
        if body_code is None:
            for bn in bodies:
                base = re.sub(r'\s*\(\d+\)\s*$', '', bn)
                if base in self.bodies:
                    body_code = self.bodies[base]
                    break
        if body_code is None:
            for bn in bodies:
                if bn in self.bodies:
                    body_code = self.bodies[bn]
                    break
        if body_code is None:
            for bn in bodies:
                base = re.sub(r'\s*\(\d+\)\s*$', '', bn)
                ref = self._body_ref(base)
                if not ref.startswith('find_body('):
                    body_code = ref
                    break
        if body_code is None:
            body_code = 'find_body("?")  # TODO: split input body not resolved'

        # Resolve splitting tool
        split_comp = f.get("component", "")
        tool_type = tool_info.get("type")
        if tool_type == "ConstructionPlane":
            tool_code = self._resolve_plane_proxied(tool_info, split_comp)
        elif tool_type == "BRepFace":
            body_name = tool_info.get("body", "")
            normal = tool_info.get("normal")
            bv = self._body_ref(body_name)
            if normal:
                axis, direction = self._normal_to_axis(normal)
            else:
                axis, direction = "z", 1
            tool_code = f'find_face({bv}, "{axis}", {direction})'
        elif tool_type == "BRepBody":
            tool_code = self._body_ref(tool_info.get("name", ""))
        else:
            tool_code = "None  # TODO: unknown split tool type"

        # Determine expected split-related body count (bodies derived from inputBody)
        input_base = re.sub(r'\s*\(\d+\)\s*$', '', input_name) if input_name else ""
        expected_split_bodies = [bn for bn in bodies
                                 if re.sub(r'\s*\(\d+\)\s*$', '', bn) == input_base
                                 ] if input_base else []
        needs_supplementary = len(expected_split_bodies) > 2  # >2 pieces = multi-tool

        self._w(f"split_inp = comp.features.splitBodyFeatures.createInput("
                f"{body_code}, {tool_code}, {extend})")
        self._w(f"split_feat = comp.features.splitBodyFeatures.add(split_inp)")
        self._w(f'split_feat.name = "{name}"')
        self.feats[name] = "split_feat"

        # Multi-body split: UI allows selecting multiple bodies to split with
        # one tool, but API createInput only accepts one. Emit sequential splits.
        extra_bodies = f.get("inputBodies", [])
        if extra_bodies:
            for eb in extra_bodies[1:]:  # skip first (already split above)
                eb_code = self._body_ref(eb)
                self._w(f"split_inp = comp.features.splitBodyFeatures.createInput("
                        f"{eb_code}, {tool_code}, {extend})")
                self._w(f"comp.features.splitBodyFeatures.add(split_inp)")

        # API limitation: SplitBodyFeature only accepts 1 splitting tool,
        # but the UI allows multiple. When the expected output has more
        # pieces than a single tool produces, try supplementary splits
        # with each available construction plane.
        if needs_supplementary:
            n_expected = len(expected_split_bodies)
            self._w()
            self._c(f"Multi-tool split workaround: expected {n_expected} pieces from 1 body")
            self._c(f"API only supports 1 tool per split — try additional planes")
            self._w(f"_pre_count = comp.bRepBodies.count")
            self._w(f"_need = {n_expected} - (comp.bRepBodies.count - _pre_count + 2)")
            self._c(f"2 = minimum pieces from first split")
            # Count actual pieces from input body
            self._w(f"_got = 0")
            self._w(f"for _bi in range(comp.bRepBodies.count):")
            self.ind += 1
            self._w(f"_bn = comp.bRepBodies.item(_bi).name")
            base_esc = input_base.replace('"', '\\"')
            self._w(f'import re as _re')
            self._w(f'if _re.sub(r"(\\s*\\(\\d+\\))+\\s*$", "", _bn) == "{base_esc}": _got += 1')
            self.ind -= 1
            self._w(f"if _got < {n_expected}:")
            self.ind += 1
            self._c(f"Try each construction plane as supplementary split tool")
            self._w(f"_biggest = None")
            self._w(f"for _bi in range(comp.bRepBodies.count):")
            self.ind += 1
            self._w(f"_b = comp.bRepBodies.item(_bi)")
            self._w(f'if _re.sub(r"(\\s*\\(\\d+\\))+\\s*$", "", _b.name) == "{base_esc}":')
            self.ind += 1
            self._w(f"if _biggest is None or _b.volume > _biggest.volume: _biggest = _b")
            self.ind -= 2  # back to if _got level
            exp_vols = []  # filled at runtime

            self._w(f"if _biggest:")
            self.ind += 1
            self._c(f"Try every candidate tool, score by volume match, pick best")
            self._w(f"_tools = []")
            self._w(f"for _pi in range(comp.constructionPlanes.count):")
            self.ind += 1
            self._w(f"_tools.append(comp.constructionPlanes.item(_pi))")
            self.ind -= 1
            self._w(f"for _bi3 in range(comp.bRepBodies.count):")
            self.ind += 1
            self._w(f"_bod = comp.bRepBodies.item(_bi3)")
            self._w(f"if _bod != _biggest:")
            self.ind += 1
            self._w(f"for _fi in range(_bod.faces.count):")
            self.ind += 1
            self._w(f"_tools.append(_bod.faces.item(_fi))")
            self.ind -= 3
            self._c(f"Record pre-supplementary volumes to detect new pieces")
            self._w(f"_pre_vols = set()")
            self._w(f"for _bi4 in range(comp.bRepBodies.count):")
            self.ind += 1
            self._w(f"_pre_vols.add(round(comp.bRepBodies.item(_bi4).volume, 4))")
            self.ind -= 1
            self._w(f"_best_tool = None")
            self._w(f"_best_new_vol = 1e10")
            self._w(f"for _pl in _tools:")
            self.ind += 1
            self._w(f"try:")
            self.ind += 1
            self._w(f"_si = comp.features.splitBodyFeatures.createInput(_biggest, _pl, True)")
            self._w(f"_sf = comp.features.splitBodyFeatures.add(_si)")
            self._c(f"Find the smallest NEW piece (not in pre-split volumes)")
            self._w(f"_new_min = 1e10")
            self._w(f"for _bi2 in range(comp.bRepBodies.count):")
            self.ind += 1
            self._w(f"_bx = comp.bRepBodies.item(_bi2)")
            self._w(f"_bv = round(_bx.volume, 4)")
            self._w(f"if _bv not in _pre_vols and _bv < _new_min: _new_min = _bv")
            self.ind -= 1
            self._w(f"if _new_min < _best_new_vol:")
            self.ind += 1
            self._w(f"_best_new_vol = _new_min")
            self._w(f"_best_tool = _pl")
            self.ind -= 1
            self._w(f"_sf.deleteMe()")
            self.ind -= 1  # end try
            self._w(f"except:")
            self.ind += 1
            self._w(f"pass")
            self.ind -= 1  # end except
            self.ind -= 1  # end for _pl
            self._c(f"Apply the best tool (smallest new piece = closest to trim waste)")
            self._w(f"if _best_tool is not None:")
            self.ind += 1
            self._w(f"_si = comp.features.splitBodyFeatures.createInput(_biggest, _best_tool, True)")
            self._w(f"_sf = comp.features.splitBodyFeatures.add(_si)")
            self._w(f'_sf.name = "{name}_sup"')
            self.ind -= 1
            self.ind -= 1  # end if _biggest
            self.ind -= 1  # end if _got

        # Track ALL output bodies by name.
        # After split, Fusion auto-names pieces which differ from captured
        # end-of-timeline names. Rename to match captured names using
        # distance-based matching (volume + bounding box position).
        # ind is already at entry level (balanced by needs_supplementary block)
        body_geo = f.get("bodyGeo", {})
        if body_geo:
            # Distance-based matching: pair each expected body to the closest
            # actual body by volume + bbox position. Avoids sort-order issues
            # when multiple bodies have similar volumes.
            self._c(f"Rename {len(bodies)} bodies by volume+position matching")
            self._w(f"_all_comp_bodies = [comp.bRepBodies.item(_i) for _i in range(comp.bRepBodies.count)]")
            # First rename all to temp names to avoid conflicts
            self._w(f"for _ti, _tb in enumerate(_all_comp_bodies): _tb.name = f'__tmp_{{_ti}}'")
            # Build expected geo list
            geo_items = []
            for bn in bodies:
                geo = body_geo.get(bn, {})
                vol = geo.get("volume", 0)
                bbmin = geo.get("bbMin", [0, 0, 0])
                geo_items.append(f'("{bn}", {vol}, {bbmin})')
            self._w(f"_expected_geo = [")
            self.ind += 1
            for gi in geo_items:
                self._w(f"{gi},")
            self.ind -= 1
            self._w(f"]")
            self._w(f"_used = set()")
            self._w(f"for _nm, _ev, _emin in _expected_geo:")
            self.ind += 1
            self._w(f"_best_i, _best_d = -1, 1e10")
            self._w(f"for _bi, _b in enumerate(_all_comp_bodies):")
            self.ind += 1
            self._w(f"if _bi in _used: continue")
            self._w(f"_d = abs(_b.volume - _ev)")
            self._w(f"try:")
            self.ind += 1
            self._w(f"_bb = _b.boundingBox")
            self._w(f"_d += abs(_bb.minPoint.x - _emin[0]) + abs(_bb.minPoint.y - _emin[1]) + abs(_bb.minPoint.z - _emin[2])")
            self.ind -= 1
            self._w(f"except: pass")
            self._w(f"if _d < _best_d: _best_i, _best_d = _bi, _d")
            self.ind -= 1
            self._w(f"if _best_i >= 0:")
            self.ind += 1
            self._w(f"_all_comp_bodies[_best_i].name = _nm")
            self._w(f"_used.add(_best_i)")
            self.ind -= 2
        else:
            # Fallback: sort-based matching (legacy captures without bodyGeo)
            expected_names = [repr(bn) for bn in bodies]
            self._w(f"_expected = [{', '.join(expected_names)}]")
            self._w(f"_all_comp_bodies = [comp.bRepBodies.item(_i) for _i in range(comp.bRepBodies.count)]")
            self._w(f"def _sort_key(b):")
            self.ind += 1
            self._w(f"bb = b.boundingBox")
            self._w(f"return (-b.volume, round(bb.minPoint.x, 4), round(bb.minPoint.y, 4), round(bb.minPoint.z, 4))")
            self.ind -= 1
            self._w(f"_all_comp_bodies.sort(key=_sort_key)")
            self._c(f"Rename all {len(bodies)} bodies in component to match captured names (by volume+position)")
            self._w(f"for _i, _nm in enumerate(_expected):")
            self.ind += 1
            self._w(f"if _i < len(_all_comp_bodies): _all_comp_bodies[_i].name = _nm")
            self.ind -= 1
        # Diagnostic: check body count matches
        self._w(f"if comp.bRepBodies.count != {len(bodies)}:")
        self.ind += 1
        self._w(f"app.log(f'WARNING: Split body count mismatch: expected {len(bodies)}, got {{comp.bRepBodies.count}}')")
        self._w(f"for _bi in range(comp.bRepBodies.count):")
        self.ind += 1
        self._w(f"app.log(f'  body[{{_bi}}]: {{comp.bRepBodies.item(_bi).name}} vol={{round(comp.bRepBodies.item(_bi).volume, 2)}}')")
        self.ind -= 2
        # Now resolve body variables by name
        for bn in bodies:
            bv = self._body_var(bn)
            self._register_body(bn, bv)
            self._w(f'{bv} = find_body("{bn}", comp)')

    def _feat_remove(self, f):
        removed = f.get("removedBody", "")
        if not removed:
            self._c("TODO: Remove — no body name captured")
            return
        body_code = self._body_ref(removed)
        # Guard: body may not exist if upstream split produced fewer pieces
        self._w(f"_rm = {body_code}")
        self._w(f"if _rm: comp.features.removeFeatures.add(_rm)")
        if removed in self.bodies:
            del self.bodies[removed]

    def _feat_copypastebody(self, f):
        """Emit CopyPasteBody: duplicates a body within the same component."""
        name = f.get("name", "CopyPasteBodies1")
        source_names = f.get("sourceBody", [])
        output_names = f.get("bodies", [])
        comp_name = f.get("component", "")
        for i, src_name in enumerate(source_names):
            src_ref = self._body_ref(src_name, component=comp_name)
            self._w(f"_cpb = comp.features.copyPasteBodies.add({src_ref})")
            # Rename the copy to match the original output name
            if i < len(output_names):
                out_name = output_names[i]
                self._w(f"_cpb_body = _cpb.bodies.item(0)")
                self._w(f'_cpb_body.name = "{out_name}"')
        # Register output bodies
        for bn in output_names:
            bv = self._body_var(bn)
            if comp_name and comp_name != self._root_name:
                c_ref = self.components.get(comp_name, "root")
                self._w(f'{bv} = find_body("{bn}", {c_ref})')
            else:
                self._w(f'{bv} = find_body("{bn}")')
            self._register_body(bn, bv)

    def _feat_mirror(self, f):
        name = f.get("name", "Mirror")
        var = self._var(name)
        plane_info = f.get("mirrorPlane", {})
        bodies = f.get("bodies", [])
        input_bodies = f.get("inputBodies", [])
        compute = f.get("computeOption", "NewBody")

        # Resolve plane (handles component scoping + cross-component proxy)
        mirror_comp = f.get("component", "")
        plane_code = self._resolve_plane_proxied(plane_info, mirror_comp)

        if compute == "Adjust":
            # Adjust mirror: inputs can be features or bodies.
            # Try features first (feature names from self.feats), fall back to bodies.
            feat_refs = []
            body_refs = []
            for inp_name in input_bodies:
                if inp_name in self.feats:
                    feat_refs.append(self.feats[inp_name])
                else:
                    body_refs.append(self._body_ref(inp_name))
            if feat_refs and not body_refs:
                input_code = f"[{', '.join(feat_refs)}]"
                self._w(f"{var} = mirror_feats(comp, {input_code}, {plane_code}, \"{name}\")")
            elif body_refs and not feat_refs:
                # Body-only inputs: use mirror_bodies (Identical compute) for
                # predictable body ordering. Adjust vs Identical produces the
                # same geometry for body mirrors but different body item order.
                input_code = f"[{', '.join(body_refs)}]"
                self._w(f"{var} = mirror_bodies(comp, {input_code}, {plane_code}, \"{name}\")")
            else:
                # Mixed — use mirror_feats (Adjust compute needed for features)
                all_refs = feat_refs + body_refs
                input_code = f"[{', '.join(all_refs)}]"
                self._w(f"{var} = mirror_feats(comp, {input_code}, {plane_code}, \"{name}\")")
        else:
            # Body-level mirror (NewBody)
            if input_bodies:
                input_code = self._body_list(input_bodies)
            else:
                known = [bn for bn in bodies if bn in self.bodies]
                if known:
                    input_code = self._body_list(known)
                else:
                    self._c("TODO: mirror inputs unknown")
                    input_code = "[]"
            self._w(f"{var} = mirror_bodies(comp, {input_code}, {plane_code}, \"{name}\")")

        self.feats[name] = var

        # Determine new body names (mirror copies, not inputs)
        input_set = set(input_bodies)
        new_names = [bn for bn in bodies if bn not in input_set]

        if len(new_names) > 1 and len(input_bodies) > 1:
            # Multi-body mirror: body order in feat.bodies is non-deterministic
            # and Python id() doesn't work for Fusion COM wrappers.
            # Match ALL output bodies by centroid to expected positions from capture.
            # Scope lookup to the feature's component to avoid cross-component
            # name collisions (e.g., Body3 in beam vs Body3 in braces).
            cap_centroids = {}
            feat_comp = mirror_comp or ""
            comp_data = self.cap.get("components", {})
            def _find_comp(c, target):
                if c.get("name") == target:
                    return c
                for ch in c.get("children", []):
                    r = _find_comp(ch, target)
                    if r:
                        return r
                return None
            target_comp = _find_comp(comp_data, feat_comp) if feat_comp else comp_data
            if target_comp:
                for b in target_comp.get("bodies", []):
                    bb = b.get("boundingBox")
                    if bb:
                        mn, mx = bb["min"], bb["max"]
                        cap_centroids[b["name"]] = (
                            round((mn[0]+mx[0])/2, 4),
                            round((mn[1]+mx[1])/2, 4),
                            round((mn[2]+mx[2])/2, 4))

            # Check if we found centroids for the output bodies
            found = sum(1 for bn in bodies if bn in cap_centroids)
            if found >= len(bodies):
                # Emit runtime: match each expected body to the closest in feat.bodies
                self._c("Match mirror output bodies by centroid position")
                self._w(f"_mir_expected = [")
                self.ind += 1
                for bn in bodies:
                    c = cap_centroids.get(bn)
                    if c:
                        self._w(f'("{bn}", {c[0]}, {c[1]}, {c[2]}),')
                self.ind -= 1
                self._w(f"]")
                self._w(f"_mir_used = set()")
                self._w(f"_mir_bodies = {{}}")
                self._w(f"for _name, _ex, _ey, _ez in _mir_expected:")
                self.ind += 1
                self._w(f"_best_bi, _best_d = -1, 1e10")
                self._w(f"for _bi in range({var}.bodies.count):")
                self.ind += 1
                self._w(f"if _bi in _mir_used: continue")
                self._w(f"_b = {var}.bodies.item(_bi)")
                self._w(f"_mn, _mx = _b.boundingBox.minPoint, _b.boundingBox.maxPoint")
                self._w(f"_d = abs((_mn.x+_mx.x)/2-_ex)+abs((_mn.y+_mx.y)/2-_ey)+abs((_mn.z+_mx.z)/2-_ez)")
                self._w(f"if _d < _best_d: _best_bi, _best_d = _bi, _d")
                self.ind -= 1
                self._w(f"if _best_bi >= 0:")
                self.ind += 1
                self._w(f"_mir_bodies[_name] = {var}.bodies.item(_best_bi)")
                self._w(f"{var}.bodies.item(_best_bi).name = _name")
                self._w(f"_mir_used.add(_best_bi)")
                self.ind -= 2

                for bn in bodies:
                    bv = self._body_var(bn)
                    self._register_body(bn, bv)
                    self._w(f'{bv} = _mir_bodies.get("{bn}")')
            else:
                # Bodies not in component tree (consumed by downstream features).
                # Use runtime centroid matching: compute expected positions from
                # input body centroids + mirror plane reflection.
                self._c("Bodies consumed downstream — match by runtime centroid")
                inp_refs = [self._body_ref(bn) for bn in input_bodies]
                self._w(f"_mir_inp_centroids = {{}}")
                for i, bn in enumerate(input_bodies):
                    self._w(f"_bb = {inp_refs[i]}.boundingBox")
                    self._w(f'_mir_inp_centroids["{bn}"] = ('
                            f"(_bb.minPoint.x+_bb.maxPoint.x)/2, "
                            f"(_bb.minPoint.y+_bb.maxPoint.y)/2, "
                            f"(_bb.minPoint.z+_bb.maxPoint.z)/2)")
                # Match output bodies: inputs stay close to original pos,
                # new copies are at mirrored pos. Use index-based fallback.
                for i, bn in enumerate(bodies):
                    bv = self._body_var(bn)
                    self._register_body(bn, bv)
                    self._w(f'{bv} = {var}.bodies.item({i})')
                    self._w(f'{bv}.name = "{bn}"')
        else:
            # Single-body mirror or simple case: index-based naming is reliable
            for i, bn in enumerate(bodies):
                bv = self._body_var(bn)
                self._register_body(bn, bv)
                self._w(f'{bv} = {var}.bodies.item({i})')
                self._w(f'{bv}.name = "{bn}"')

    def _feat_combine(self, f):
        name = f.get("name", "Combine")
        op = f.get("operation", "Join")
        target = f.get("targetBody")
        tools = f.get("toolBodies", [])
        keep = f.get("isKeepToolBodies", False)
        target_comp = f.get("targetComponent")
        tool_comps = f.get("toolComponents", [])

        op_map = {"Join": "JOIN", "Cut": "CUT"}
        op_code = op_map.get(op, "JOIN")

        if target:
            tc = self._body_ref(target, component=target_comp)
        else:
            err = f.get("targetBodyError", "not captured")
            self._c(f"TODO: target body not captured ({err})")
            tc = "None"

        if tools:
            # Filter out the target body from tools (can't cut/join a body with itself)
            # Only filter when tool is in the SAME component as target (same-named
            # bodies in different components are distinct bodies)
            filtered = []
            for i, t in enumerate(tools):
                tc_i = tool_comps[i] if i < len(tool_comps) else None
                same_body = (t == target and
                             (not tc_i or not target_comp or tc_i == target_comp))
                if not same_body:
                    filtered.append((t, tc_i))
            if filtered:
                refs = [self._body_ref(t, component=c) for t, c in filtered]
                tools_code = f"[{', '.join(refs)}]"
            else:
                tools_code = "[]"
        else:
            err = f.get("toolBodiesError", "not captured")
            self._c(f"TODO: tool bodies not captured ({err})")
            tools_code = "[]"

        var = self._var(name)

        # For CUT that expects a split, save tool BB BEFORE the combine
        # (the tool body is consumed by isKeepToolBodies=False).
        output_bodies = f.get("outputBodies", [])
        known = {target} | set(tools)
        new_bodies = [bn for bn in output_bodies if bn not in known]
        if new_bodies and op_code == "CUT" and tools:
            first_tool = tools[0]
            first_tc = tool_comps[0] if tool_comps else None
            tool_ref = self._body_ref(first_tool, component=first_tc)
            self._w(f"_pre_cut_tool_bb = {tool_ref}.boundingBox")
            # Snapshot body names before the combine
            self._w(f"_pre_cut_names = set()")
            self._w(f"for _bi in range(comp.bRepBodies.count): _pre_cut_names.add(comp.bRepBodies.item(_bi).name)")

        self._w(f'{var} = combine(comp, {tc}, {tools_code}, {op_code}, {keep}, "{name}")')

        if new_bodies and op_code == "CUT":
            n_expected = len(new_bodies)
            # Check if the CUT produced the expected split
            self._w(f"if {var} is not None and {var}.bodies.count > {n_expected}:")
            self.ind += 1
            for bn in new_bodies:
                idx = output_bodies.index(bn)
                bv = self._body_var(bn)
                self._register_body(bn, bv)
                self._w(f'{bv} = {var}.bodies.item({idx})')
                self._w(f'{bv}.name = "{bn}"')
            self.ind -= 1
            self._w(f"else:")
            self.ind += 1
            self._c("CUT did not split (coincident face issue) — 2-plane SplitBody fallback")
            self._w(f"_tbb = _pre_cut_tool_bb")
            self._w(f"_dx = _tbb.maxPoint.x - _tbb.minPoint.x")
            self._w(f"_dy = _tbb.maxPoint.y - _tbb.minPoint.y")
            self._w(f"_dz = _tbb.maxPoint.z - _tbb.minPoint.z")
            # Determine thin axis + split offsets at runtime
            self._w(f"if _dy <= _dx and _dy <= _dz:")
            self.ind += 1
            self._w(f'_off_min, _off_max, _base_pl, _ax = _tbb.minPoint.y, _tbb.maxPoint.y, comp.xZConstructionPlane, "y"')
            self.ind -= 1
            self._w(f"elif _dx <= _dy and _dx <= _dz:")
            self.ind += 1
            self._w(f'_off_min, _off_max, _base_pl, _ax = _tbb.minPoint.x, _tbb.maxPoint.x, comp.yZConstructionPlane, "x"')
            self.ind -= 1
            self._w(f"else:")
            self.ind += 1
            self._w(f'_off_min, _off_max, _base_pl, _ax = _tbb.minPoint.z, _tbb.maxPoint.z, comp.xYConstructionPlane, "z"')
            self.ind -= 1
            # Create two construction planes at tool min/max faces
            self._w(f"_pl_inp1 = comp.constructionPlanes.createInput()")
            self._w(f"_pl_inp1.setByOffset(_base_pl, adsk.core.ValueInput.createByReal(_off_min))")
            self._w(f"_pln1 = comp.constructionPlanes.add(_pl_inp1)")
            self._w(f"_pl_inp2 = comp.constructionPlanes.createInput()")
            self._w(f"_pl_inp2.setByOffset(_base_pl, adsk.core.ValueInput.createByReal(_off_max))")
            self._w(f"_pln2 = comp.constructionPlanes.add(_pl_inp2)")
            # First split at min face
            self._w(f"try:")
            self.ind += 1
            self._w(f"_spi = comp.features.splitBodyFeatures.createInput({tc}, _pln1, False)")
            self._w(f"comp.features.splitBodyFeatures.add(_spi)")
            self.ind -= 1
            self._w(f"except: pass")
            # Second split at max face — try target first, then auto-named pieces only
            self._w(f"try:")
            self.ind += 1
            self._w(f"_spi2 = comp.features.splitBodyFeatures.createInput({tc}, _pln2, False)")
            self._w(f"comp.features.splitBodyFeatures.add(_spi2)")
            self.ind -= 1
            self._w(f"except:")
            self.ind += 1
            self._c("Target didn't span max plane — try auto-named pieces from first split")
            self._w(f"for _bi in range(comp.bRepBodies.count):")
            self.ind += 1
            self._w(f"_b = comp.bRepBodies.item(_bi)")
            self._w(f"if _b.name not in _pre_cut_names:")
            self.ind += 1
            self._w(f"try:")
            self.ind += 1
            self._w(f"_spi2 = comp.features.splitBodyFeatures.createInput(_b, _pln2, False)")
            self._w(f"comp.features.splitBodyFeatures.add(_spi2)")
            self._w(f"break")
            self.ind -= 1
            self._w(f"except: pass")
            self.ind -= 3
            # Do NOT delete planes — SplitBody features depend on them
            # Delete pocket pieces (near-zero volume, not in pre-CUT snapshot)
            self._w(f"for _bi in range(comp.bRepBodies.count - 1, -1, -1):")
            self.ind += 1
            self._w(f"_b = comp.bRepBodies.item(_bi)")
            self._w(f"if _b.name not in _pre_cut_names and _b.volume < 1.0:")
            self.ind += 1
            self._w(f"try: comp.features.removeFeatures.add(_b)")
            self._w(f"except: pass")
            self.ind -= 2
            # Collect remaining new bodies, sort by position on thin axis
            self._w(f"_new_bodies = []")
            self._w(f"for _bi in range(comp.bRepBodies.count):")
            self.ind += 1
            self._w(f"_b = comp.bRepBodies.item(_bi)")
            self._w(f"if _b.name not in _pre_cut_names:")
            self.ind += 1
            self._w(f"_new_bodies.append(_b)")
            self.ind -= 2
            self._w(f"_new_bodies.sort(key=lambda _b: getattr(_b.boundingBox.minPoint, _ax))")
            for bn in new_bodies:
                bv = self._body_var(bn)
                self._register_body(bn, bv)
                self._w(f'if _new_bodies:')
                self.ind += 1
                self._w(f'{bv} = _new_bodies.pop(0)')
                self._w(f'{bv}.name = "{bn}"')
                self.ind -= 1
                self._w(f'else:')
                self.ind += 1
                self._w(f'{bv} = find_body("{bn}", comp)')
                self.ind -= 1
            self.ind -= 1
        elif new_bodies:
            for bn in new_bodies:
                idx = output_bodies.index(bn)
                bv = self._body_var(bn)
                self._register_body(bn, bv)
                self._w(f'{bv} = {var}.bodies.item({idx})')
                self._w(f'{bv}.name = "{bn}"')

    def _feat_fillet(self, f):
        name = f.get("name", "Fillet")
        edge_sets = f.get("edgeSets", [])

        if not edge_sets:
            self._c(f"TODO: Fillet '{name}' — no edge data captured")
            return

        self._w("fillet_inp = comp.features.filletFeatures.createInput()")
        any_items = False
        for si, es in enumerate(edge_sets):
            radius = es.get("radius", "0.1 cm")
            edges = es.get("edges", [])
            if not edges:
                self._c(f"TODO: edge set {si} has no captured data")
                continue

            # Check if items are BRepFace or BRepEdge
            has_faces = any(e.get("type") == "BRepFace" for e in edges)
            has_edges = any(e.get("type") == "BRepEdge" or "start" in e for e in edges)

            if has_faces:
                any_items = True
                self._emit_face_finder(f"fillet_items_{si}", edges, f.get("bodies", []))
                self._w(f"if fillet_items_{si}.count > 0:")
                self.ind += 1
                self._w(f"fillet_inp.addConstantRadiusEdgeSet(fillet_items_{si}, "
                        f'adsk.core.ValueInput.createByString("{radius}"), True)')
                self.ind -= 1
            elif has_edges:
                any_items = True
                self._emit_edge_finder(f"fillet_edges_{si}", edges, f.get("bodies", []))
                self._w(f"if fillet_edges_{si}.count > 0:")
                self.ind += 1
                self._w(f"fillet_inp.addConstantRadiusEdgeSet(fillet_edges_{si}, "
                        f'adsk.core.ValueInput.createByString("{radius}"), True)')
                self.ind -= 1
        if any_items:
            self._w(f'fillet_feat = comp.features.filletFeatures.add(fillet_inp)')
            self._w(f'fillet_feat.name = "{name}"')
        else:
            self._c(f"TODO: Fillet '{name}' skipped — no edges/faces captured")

    def _feat_chamfer(self, f):
        name = f.get("name", "Chamfer")
        edge_sets = f.get("edgeSets", [])

        if not edge_sets:
            self._c(f"TODO: Chamfer '{name}' — no edge data captured")
            return

        self._w("chamfer_inp = comp.features.chamferFeatures.createInput2()")
        any_edges = False
        for si, es in enumerate(edge_sets):
            edges = es.get("edges", [])
            if not edges:
                self._c(f"TODO: edge set {si} has no captured vertices")
                continue
            any_edges = True
            ctype = es.get("chamferType", "EqualDistance")
            self._emit_edge_finder(f"chamfer_edges_{si}", edges, f.get("bodies", []))

            if ctype == "EqualDistance":
                dist = es.get("distance", f.get("distance", "0.1 cm"))
                self._w(f"chamfer_inp.chamferEdgeSets.addEqualDistanceChamferEdgeSet("
                        f'chamfer_edges_{si}, adsk.core.ValueInput.createByString("{dist}"), True)')
            elif ctype == "TwoDistances":
                d1 = es.get("distanceOne", f.get("distanceOne", "0.1 cm"))
                d2 = es.get("distanceTwo", f.get("distanceTwo", "0.1 cm"))
                self._w(f"chamfer_inp.chamferEdgeSets.addTwoDistanceChamferEdgeSet("
                        f'chamfer_edges_{si}, adsk.core.ValueInput.createByString("{d1}"), '
                        f'adsk.core.ValueInput.createByString("{d2}"), True)')
            elif ctype == "DistanceAndAngle":
                dist = es.get("distance", f.get("distance", "0.1 cm"))
                angle = es.get("angle", f.get("angle", "45 deg"))
                self._w(f"chamfer_inp.chamferEdgeSets.addDistanceAndAngleChamferEdgeSet("
                        f'chamfer_edges_{si}, adsk.core.ValueInput.createByString("{dist}"), '
                        f'adsk.core.ValueInput.createByString("{angle}"), True)')

        if any_edges:
            self._w(f'chamfer_feat = comp.features.chamferFeatures.add(chamfer_inp)')
            self._w(f'chamfer_feat.name = "{name}"')
        else:
            self._c(f"TODO: Chamfer '{name}' skipped — no edges captured")

    def _emit_face_finder(self, var, faces, body_names):
        """Emit code that finds BRepFaces and adds their EDGES for fillet.

        Fillet API requires BRepEdge objects, not BRepFaces. When the user
        selected faces in the UI, we find the matching faces and add all
        their edges to the collection.
        """
        self._w(f"{var} = adsk.core.ObjectCollection.create()")
        if not faces:
            return
        self._w("_face_targets = [")
        self.ind += 1
        for f in faces:
            if f.get("type") != "BRepFace":
                continue
            pof = f.get("pointOnFace", [0, 0, 0])
            body = f.get("body", "")
            self._w(f'("{body}", {pof[0]}, {pof[1]}, {pof[2]}),')
        self.ind -= 1
        self._w("]")
        saved_ind = self.ind
        self._w("_added = set()")
        self._w("for _fb, _fx, _fy, _fz in _face_targets:")
        self.ind += 1
        self._c(f"Search ALL bodies (names may be swapped from mirror)")
        self._w(f"_best_face, _best_d = None, 1e10")
        self._w(f"for _bsi in range(root.bRepBodies.count):")
        self.ind += 1
        self._w(f"_body = root.bRepBodies.item(_bsi)")
        self._w(f"for _fi in range(_body.faces.count):")
        self.ind += 1
        self._w(f"_f = _body.faces.item(_fi)")
        self._w(f"_p = _f.pointOnFace")
        self._w(f"_d = abs(_p.x-_fx)+abs(_p.y-_fy)+abs(_p.z-_fz)")
        self._w(f"if _d < _best_d: _best_face, _best_d = _f, _d")
        self.ind -= 2  # back to for _fb level
        self._w(f"if _best_face and _best_d < 0.5:")
        self.ind += 1
        self._c(f"Add all edges of the matched face (fillet API needs edges)")
        self._w(f"for _ei in range(_best_face.edges.count):")
        self.ind += 1
        self._w(f"_edge = _best_face.edges.item(_ei)")
        self._w(f"_eid = _edge.tempId")
        self._w(f"if _eid not in _added:")
        self.ind += 1
        self._w(f"{var}.add(_edge)")
        self._w(f"_added.add(_eid)")
        self.ind -= 3  # back to for _fb level
        self.ind -= 1  # back to base
        self.ind = saved_ind

    def _emit_edge_finder(self, var, edges, body_names):
        """Emit code that finds edges by matching vertex positions."""
        self._w(f"{var} = adsk.core.ObjectCollection.create()")
        if not edges:
            self._c("TODO: no edge vertices captured")
            return

        # Build list of target vertex pairs
        self._w("_targets = [")
        self.ind += 1
        for e in edges:
            s = e["start"]
            ev = e["end"]
            self._w(f"(({s[0]}, {s[1]}, {s[2]}), ({ev[0]}, {ev[1]}, {ev[2]})),")
        self.ind -= 1
        self._w("]")

        # Search bodies for matching edges
        if body_names:
            body_code = self._body_ref(body_names[0])
        else:
            body_code = "None"
        self._w(f"_body = {body_code}")
        self._w("if _body:")
        self.ind += 1
        self._w("for _ei in range(_body.edges.count):")
        self.ind += 1
        self._w("_e = _body.edges.item(_ei)")
        self._w("_sv, _ev = _e.startVertex.geometry, _e.endVertex.geometry")
        self._w("for _ts, _te in _targets:")
        self.ind += 1
        self._w("if ((abs(_sv.x-_ts[0])+abs(_sv.y-_ts[1])+abs(_sv.z-_ts[2]) < 0.05 and")
        self._w("     abs(_ev.x-_te[0])+abs(_ev.y-_te[1])+abs(_ev.z-_te[2]) < 0.05) or")
        self._w("    (abs(_sv.x-_te[0])+abs(_sv.y-_te[1])+abs(_sv.z-_te[2]) < 0.05 and")
        self._w("     abs(_ev.x-_ts[0])+abs(_ev.y-_ts[1])+abs(_ev.z-_ts[2]) < 0.05)):")
        self.ind += 1
        self._w(f"{var}.add(_e)")
        self._w("break")
        self.ind -= 4
