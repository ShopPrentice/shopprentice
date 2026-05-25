# Optimizing Fusion 360 Models

Read this file when the user asks to optimize an existing model, reduce timeline features, or build a polished reusable template. Do NOT load for regular builds — these rules add overhead that isn't worth it for one-off models.

## Combine Batching

When multiple tool bodies all CUT (or JOIN) the same target body, use a single combine with all tools — never loop with one tool per combine.

```python
# WRONG — N combines for N tools:
for tool in tools:
    sp.combine(target, tool, CUT, True, f"{target.name}_{tool.name}_Cut")

# RIGHT — 1 combine with all tools:
sp.combine(target, tools, CUT, True, f"{target.name}_Cut")
```

**When to batch:** Any time you find yourself in a loop calling `sp.combine` on the same target body. Collect all tool bodies first, then do one combine.

**When NOT to batch:** When the tools don't exist yet (e.g., they're built in the same loop). Build all tools first, then batch the combine.

## Construction Plane Reuse

Create each midplane ONCE at the assembly level. Every mirror operation at the same center reuses it — never create a duplicate plane at the same offset.

**Recognition:** Before calling `sp.off_plane` for a mirror, ask: "Is there already a plane at this position?" Common duplicates:
- Stile S-midplane = frame S-midplane (both at `origin_s + stile_len / 2`)
- Panel S-midplane = frame S-midplane (for single-panel layouts)
- Panel R-midplane = frame R-midplane (for single-panel layouts)

**Pattern:** Create frame-level midplanes early, pass them to sub-routines:
```python
r_mid = sp.off_plane(comp, perp_base[R], f"({o_r}) + ({rail_len}) / 2", f"{prefix}_RMid")
s_mid = sp.off_plane(comp, perp_base[S], f"({o_s}) + ({stile_len}) / 2", f"{prefix}_SMid")
# Reuse r_mid and s_mid for ALL mirrors at these centers
```

**Per-entity planes are OK** when each entity has a genuinely different center (e.g., per-divider R-midplanes where each divider is at a unique R position).

## Conditional Plane Creation

Only create construction planes that will actually be used. If a plane is only needed for a specific configuration (e.g., h-dividers), gate it:

```python
groove_plane = None
if n_h > 0:
    groove_plane = sp.off_plane(comp, base_plane, groove_e, f"{prefix}_GPl")
```

## Deferred CUTs

When building a multi-part assembly where bodies CUT into each other, defer ALL CUTs to the end and batch per target:

```python
# Build all bodies first (rails, stiles, dividers, panels)
# Then one consolidated CUT pass:
for rail in rails:
    sp.combine(rail, stiles + dividers + panels, CUT, True, f"{prefix}_{rail.name}_Cut")
for stile in stiles:
    sp.combine(stile, dividers_h + panels, CUT, True, f"{prefix}_{stile.name}_Cut")
```

This minimizes total combine features and keeps the timeline clean.

## Mirror Feature Batching

When mirroring multiple bodies across the same plane, use `sp.mirror_feats` with all source features in one call rather than separate `sp.mirror_body` calls:

```python
# WRONG — 3 mirror features:
sp.mirror_body(comp, body_a, mid_plane, "A_Mir")
sp.mirror_body(comp, body_b, mid_plane, "B_Mir")
sp.mirror_body(comp, body_c, mid_plane, "C_Mir")

# RIGHT — 1 mirror feature:
sp.mirror_feats(comp, [ext_a, ext_b, ext_c], mid_plane, "ABC_Mir")
```

Note: `mirror_feats` takes timeline features (extrudes, mirrors), not bodies. Collect the extrude features when building, then mirror them together.
