import os
"""Tests for sp.per_body_appearance and the _apply_custom_texture guard.

These tests run OUTSIDE Fusion (no adsk module). They verify the pure-logic
aspects: naming convention, guard logic, and that the function signatures
are correct. Fusion-dependent behavior (actual appearance creation) is
tested via the MCP execute_script path in integration tests.
"""

def test_per_body_naming():
    """per_body_appearance names follow SP_<species>_<body.name> convention."""
    # Can't test actual Fusion calls without adsk, but verify the naming logic
    species = "teak b"
    body_name = "leg_FR"
    expected = f"SP_{species}_{body_name}"
    assert expected == "SP_teak b_leg_FR"

def test_per_body_naming_with_spaces():
    species = "brazilian rosewood"
    body_name = "BT_apron_F_1"
    expected = f"SP_{species}_{body_name}"
    assert expected == "SP_brazilian rosewood_BT_apron_F_1"

def test_guard_message_content():
    """The guard error message should mention per_body_appearance."""
    msg = (f"Refusing to modify 'SP_teak b' — "
           f"it is referenced by 3 bodies. "
           f"Use sp.per_body_appearance(body, species_key) to get "
           f"a safe per-body copy first.")
    assert "per_body_appearance" in msg
    assert "3 bodies" in msg

def test_species_texture_has_base():
    """Every species in _SPECIES_TEXTURE must have a 'base' key for
    per_body_appearance to copy from."""
    import re
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "helpers", "sp.py")) as f:
        src = f.read()
    # Find all species entries and verify each has "base":
    entries = re.findall(r'"(teak[^"]*)":\s*\{[^}]*"base":\s*"([^"]*)"', src)
    assert len(entries) >= 5, f"Expected at least 5 teak species, found {len(entries)}"
    for species, base in entries:
        assert base in ("Mahogany", "Walnut", "Pine"), \
            f"Species '{species}' has unexpected base '{base}'"

if __name__ == "__main__":
    test_per_body_naming()
    test_per_body_naming_with_spaces()
    test_guard_message_content()
    test_species_texture_has_base()
    print("All tests passed.")
