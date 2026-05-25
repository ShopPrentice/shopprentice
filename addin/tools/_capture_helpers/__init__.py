"""
Shared capture helpers for design introspection.

Used by capture_design.py, get_selection.py, sync_script.py, and get_changes.py.
Extracts structured info from Fusion 360 entities (sketches, extrudes,
combines, mirrors, patterns, moves, chamfers, fillets, sweeps,
split-body, remove, etc.).
"""

# Re-export everything so `from ._capture_helpers import X` keeps working.
from .body import _capture_body, _capture_edge_vertices
from .plane import _capture_sketch_plane, _capture_construction_plane
from .sketch import _identify_sketch_entity, _capture_sketch, _capture_sketch_summary
from .extrude import (
    _capture_extrude, _infer_extrude_body_name,
    _find_sketch_for_extrude, _find_sketch_for_extrude_no_timeline,
    _find_sketch_from_profile, _match_profile_index,
)
from .pattern import _extract_linear_direction, _capture_rectangular_pattern
from .combine import _capture_combine, _infer_combine_tool_bodies
from .modifiers import (
    _capture_mirror, _capture_move, _capture_chamfer, _capture_fillet,
    _capture_sweep, _match_profile_index_from_profile,
    _capture_split_body, _capture_remove,
)
