"""
Tests for the wood-appearance library scan (issue: apply_appearance found
zero appearances after Autodesk renamed the stock library to "Fusion
Appearance Library" and dropped most wood species).

Runs outside Fusion 360 using shared mock fixtures. The mock library
contents mirror a live 2026-07 session: 185-appearance "Fusion Appearance
Library" whose woods are Bamboo / Cherry / Mahogany / Oak / Pine / Walnut
plus "3D " procedural variants — no Teak, Ash, Beech, Hickory, etc. A slim
variant (Oak / Walnut / Bamboo only) covers further library shrinkage.
"""

import importlib.util
import os
import sys
import unittest

from tests.fixtures.mock_adsk import setup as _setup_mocks
_m = _setup_mocks()
mock_app = _m["app"]

import adsk.core
import adsk.fusion

# helpers/sp/appearance.py aliases this at import time; the shared fixture
# doesn't define it.
if not hasattr(adsk.core, "Point3D"):
    from unittest.mock import MagicMock
    adsk.core.Point3D = MagicMock()

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ADDIN_DIR = os.path.join(_REPO_ROOT, "addin")
if _ADDIN_DIR not in sys.path:
    sys.path.insert(0, _ADDIN_DIR)


def _load_module(dotted_name, rel_path):
    if dotted_name in sys.modules:
        return sys.modules[dotted_name]
    spec = importlib.util.spec_from_file_location(
        dotted_name, os.path.join(_REPO_ROOT, rel_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotted_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Fake material-library object model ──

class FakeAppearance:
    def __init__(self, name):
        self.name = name


class FakeCollection:
    def __init__(self, items):
        self._items = list(items)

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class FakeLibrary:
    def __init__(self, name, appearance_names, raises=False):
        self.name = name
        self._raises = raises
        self._appearances = FakeCollection(
            [FakeAppearance(n) for n in appearance_names])

    @property
    def appearances(self):
        if self._raises:
            raise RuntimeError("library has no appearances")
        return self._appearances


# Wood entries observed live in the current stock library (2026-07,
# enumerated in-session via _list_wood_appearances), plus a sample of the
# non-wood majority.
_LIVE_WOODS = [
    "3D Cherry - Figured -Semigloss", "3D Cherry - Painted",
    "3D Cherry - Stained dark semigloss", "3D Cherry - Stained light semigloss",
    "3D Mahogany - Glossy", "3D Maple - Stained light semigloss",
    "3D Maple - Unfinished", "3D Oak - Semigloss",
    "3D Walnut - Figured - Semigloss", "Bamboo Light - Semigloss",
    "Cherry", "Mahogany", "Oak", "Oak - Semigloss", "Pine", "Walnut",
]
# A hypothetical further-slimmed library — the scan must stay resilient to
# Autodesk dropping more species, as happened between library versions.
_SLIM_WOODS = [
    "Oak", "Oak - Semigloss", "Walnut", "Bamboo Light - Semigloss",
    "3D Oak - Semigloss", "3D Walnut - Figured - Semigloss",
]
_LIVE_OTHERS = [
    "Aluminum - Anodized Glossy (Blue)", "Brass - Satin", "Glass - Basic",
    "Paint - Enamel Glossy (Black)", "Steel - Satin",
]


def _install_libraries(libraries):
    mock_app.materialLibraries = FakeCollection(libraries)


def _stock_libs(lib_name="Fusion Appearance Library", woods=_LIVE_WOODS):
    return [
        # A material-only library that raises on .appearances — the scan
        # must survive it.
        FakeLibrary("Fusion Material Library", [], raises=True),
        FakeLibrary(lib_name, woods + _LIVE_OTHERS),
    ]


class _EmptyDesign:
    """Design with no local appearances."""
    def __init__(self):
        self.appearances = FakeCollection([])


class TestToolFindAppearance(unittest.TestCase):
    """addin/tools/apply_appearance.py scan against the live library."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module(
            "tools.apply_appearance", "addin/tools/apply_appearance.py")

    def setUp(self):
        _install_libraries(_stock_libs())
        adsk.fusion.Design.cast = lambda _p: _EmptyDesign()

    def test_oak_prefers_exact_plain_match(self):
        a, source, term = self.mod._find_appearance("oak")
        self.assertEqual(a.name, "Oak")
        self.assertEqual(term, "Oak")
        self.assertIn("Fusion Appearance Library", source)

    def test_walnut_found(self):
        a, _source, term = self.mod._find_appearance("walnut")
        self.assertEqual(a.name, "Walnut")
        self.assertEqual(term, "Walnut")

    def test_bamboo_found(self):
        a, _source, _term = self.mod._find_appearance("bamboo")
        self.assertEqual(a.name, "Bamboo Light - Semigloss")

    def test_teak_falls_back_to_stand_in(self):
        a, _source, term = self.mod._find_appearance("teak")
        self.assertEqual(a.name, "Mahogany")
        # matched a fallback term, not the primary — handler emits a note
        self.assertNotEqual(term, self.mod.SPECIES_MAP["teak"][0])

    def test_every_mapped_species_resolves(self):
        for species in self.mod.SPECIES_MAP:
            a, source, _term = self.mod._find_appearance(species)
            self.assertIsNotNone(a, f"{species!r} unresolved: {source}")

    def test_every_mapped_species_resolves_in_slim_library(self):
        _install_libraries(_stock_libs(woods=_SLIM_WOODS))
        for species in self.mod.SPECIES_MAP:
            a, source, _term = self.mod._find_appearance(species)
            self.assertIsNotNone(a, f"{species!r} unresolved: {source}")
            self.assertIn(a.name, _SLIM_WOODS)

    def test_unknown_species_reports_error(self):
        a, err, term = self.mod._find_appearance("purpleheart")
        self.assertIsNone(a)
        self.assertIsNone(term)
        self.assertIn("purpleheart", err)

    def test_old_library_name_still_preferred(self):
        _install_libraries(_stock_libs("Fusion 360 Appearance Library"))
        a, source, _term = self.mod._find_appearance("oak")
        self.assertEqual(a.name, "Oak")
        self.assertIn("Fusion 360 Appearance Library", source)

    def test_wood_listing_not_empty(self):
        names = self.mod._list_wood_appearances()
        for expected in ("Oak", "Walnut", "Bamboo Light - Semigloss"):
            self.assertIn(expected, names)
        for other in _LIVE_OTHERS:
            self.assertNotIn(other, names)

    def test_design_local_appearance_wins(self):
        class _Design:
            appearances = FakeCollection([FakeAppearance("My Teak Custom")])
        adsk.fusion.Design.cast = lambda _p: _Design()
        a, source, term = self.mod._find_appearance("teak")
        self.assertEqual(a.name, "My Teak Custom")
        self.assertTrue(source.startswith("design:"))
        self.assertEqual(term, "Teak")


class TestHelpersBaseFallback(unittest.TestCase):
    """helpers/sp/appearance.py base lookup for custom-texture species."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module(
            "helpers_sp_appearance_standalone", "helpers/sp/appearance.py")

    def setUp(self):
        _install_libraries(_stock_libs())

    def test_present_mahogany_base_used_directly(self):
        a = self.mod._find_base_appearance("Mahogany")
        self.assertEqual(a.name, "Mahogany")

    def test_missing_mahogany_base_falls_back_to_walnut(self):
        _install_libraries(_stock_libs(woods=_SLIM_WOODS))
        a = self.mod._find_base_appearance("Mahogany")
        self.assertIsNotNone(a)
        self.assertEqual(a.name, "Walnut")

    def test_existing_base_used_directly(self):
        a = self.mod._find_base_appearance("Walnut")
        self.assertEqual(a.name, "Walnut")

    def test_no_woods_at_all_returns_none(self):
        _install_libraries([FakeLibrary("Fusion Appearance Library",
                                        _LIVE_OTHERS)])
        self.assertIsNone(self.mod._find_base_appearance("Mahogany"))

    def test_all_texture_bases_resolve(self):
        for key, cfg in self.mod._SPECIES_TEXTURE.items():
            a = self.mod._find_base_appearance(cfg.get("base", "Mahogany"))
            self.assertIsNotNone(a, f"no base for {key!r}")


if __name__ == "__main__":
    unittest.main()
