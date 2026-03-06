"""
Script Generator — template-based code generation from capture_design output.

Reads the structured JSON from capture_design and emits a standalone Fusion 360
Python script that recreates the model. The generated script is self-contained
(no af.py dependency) and uses parametric expressions from the captured dimensions.

Usage:
    from ._script_generator import generate_script
    script_text = generate_script(capture_data)

    # For search-based building:
    info = get_ambiguous_features(capture_data)
    script = generate_with_choices(capture_data, {0: 2, 3: 1})
"""

from ._base import _BaseMixin
from ._core import _CoreMixin
from ._variants import _VariantsMixin
from ._feat_sketch import _SketchMixin
from ._feat_extrude import _ExtrudeMixin
from ._feat_modifiers import _ModifiersMixin
from ._feat_pattern import _PatternMixin
from ._geometry import _GeometryMixin


class _Generator(_CoreMixin, _VariantsMixin, _SketchMixin, _ExtrudeMixin,
                 _ModifiersMixin, _PatternMixin, _GeometryMixin, _BaseMixin):
    """Walks capture_design output and emits a Fusion 360 Python script.

    Composed from mixins — each handles a disjoint set of feature types.
    _BaseMixin is listed last so its __init__ is reached via MRO.
    """
    pass


def generate_script(capture):
    """Generate a standalone Fusion 360 script from capture_design JSON."""
    return _Generator(capture).generate()


def get_ambiguous_features(capture):
    """Return list of {index, name, type, variants} for ambiguous features."""
    g = _Generator(capture)
    g._scan_needs()
    result = []
    for fi, feat in enumerate(g.cap.get("timeline", [])):
        if feat.get("isRolledBack"):
            continue
        variants = g._feature_variants(feat)
        if len(variants) > 1:
            result.append({
                "index": fi,
                "name": feat.get("name", ""),
                "type": feat.get("type", ""),
                "variantCount": len(variants),
                "descriptions": [v[1] for v in variants],
            })
    return result


def generate_with_choices(capture, choices):
    """Generate full script with specific variant choices for ambiguous features.

    Args:
        capture: capture_design JSON data
        choices: dict mapping feature index → variant index
                 (0-based; only ambiguous features need entries)

    Returns:
        Complete Fusion 360 Python script text.
    """
    return _Generator(capture).generate_with_choices(choices)


def generate_prefix_script(capture):
    """Generate a script that sets up design type + user parameters only.

    Used as the first step in incremental building. Execute with clean=true
    to start from a blank document with all parameters defined.

    Returns:
        Standalone Fusion 360 Python script text.
    """
    return _Generator(capture).generate_prefix_script()


def generate_feature_script(capture, feature_index, choices=None):
    """Generate a standalone script for ONE feature at feature_index.

    Includes helpers + entity lookups for everything created by features 0..N-1,
    then emits the single feature's code.

    Args:
        capture: capture_design JSON data
        feature_index: index into the timeline array (0-based)
        choices: optional dict mapping feature index → variant index

    Returns:
        Standalone Fusion 360 Python script text.
    """
    return _Generator(capture).generate_feature_script(feature_index, choices)
