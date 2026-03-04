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
            if input_name in self.bodies:
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
        tool_type = tool_info.get("type")
        if tool_type == "ConstructionPlane":
            pname = tool_info.get("name", "")
            builtin = {"XY": "root.xYConstructionPlane",
                       "XZ": "root.xZConstructionPlane",
                       "YZ": "root.yZConstructionPlane"}
            tool_code = self.planes.get(pname, builtin.get(pname, f'root.constructionPlanes.itemByName("{pname}")'))
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
        # end-of-timeline names. Snapshot before/after, then force-rename
        # ALL bodies in the component to match expected names by volume order.
        self.ind = 1  # Reset: we're inside def run()
        expected_names = [repr(bn) for bn in bodies]
        self._w(f"_expected = [{', '.join(expected_names)}]")
        self._w(f"_all_comp_bodies = [comp.bRepBodies.item(_i) for _i in range(comp.bRepBodies.count)]")
        self._w(f"_all_comp_bodies.sort(key=lambda b: -b.volume)")
        self._c(f"Rename all {len(bodies)} bodies in component to match captured names (by volume)")
        self._w(f"for _i, _nm in enumerate(_expected):")
        self.ind += 1
        self._w(f"if _i < len(_all_comp_bodies): _all_comp_bodies[_i].name = _nm")
        self.ind -= 1
        # Now resolve body variables by name
        for bn in bodies:
            bv = self._var(bn)
            self.bodies[bn] = bv
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

    def _feat_mirror(self, f):
        name = f.get("name", "Mirror")
        var = self._var(name)
        plane_info = f.get("mirrorPlane", {})
        bodies = f.get("bodies", [])
        input_bodies = f.get("inputBodies", [])

        # Resolve plane
        pname = plane_info.get("name", "")
        if pname in self.planes:
            plane_code = self.planes[pname]
        else:
            self._c(f'TODO: mirror plane "{pname}" not tracked')
            plane_code = "None"

        # Resolve inputs
        if input_bodies:
            input_code = self._body_list(input_bodies)
        else:
            # Fallback: bodies that already exist in self.bodies are the inputs
            known = [bn for bn in bodies if bn in self.bodies]
            if known:
                input_code = self._body_list(known)
            else:
                self._c("TODO: mirror inputs unknown")
                input_code = "[]"

        self._w(f"{var} = mirror_bodies(root, {input_code}, {plane_code}, \"{name}\")")

        self.feats[name] = var
        for i, bn in enumerate(bodies):
            bv = self._var(bn)
            self.bodies[bn] = bv
            self._w(f'{bv} = {var}.bodies.item({i})')
            self._w(f'{bv}.name = "{bn}"')

    def _feat_combine(self, f):
        name = f.get("name", "Combine")
        op = f.get("operation", "Join")
        target = f.get("targetBody")
        tools = f.get("toolBodies", [])
        keep = f.get("isKeepToolBodies", False)

        op_map = {"Join": "JOIN", "Cut": "CUT"}
        op_code = op_map.get(op, "JOIN")

        if target:
            tc = self._body_ref(target)
        else:
            err = f.get("targetBodyError", "not captured")
            self._c(f"TODO: target body not captured ({err})")
            tc = "None"

        if tools:
            tools_code = self._body_list(tools)
        else:
            err = f.get("toolBodiesError", "not captured")
            self._c(f"TODO: tool bodies not captured ({err})")
            tools_code = "[]"

        self._w(f'combine(comp, {tc}, {tools_code}, {op_code}, {keep}, "{name}")')

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
