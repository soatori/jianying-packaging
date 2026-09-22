import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "packaging_tools" / "validators" / "layout_impl.py"
SPEC = importlib.util.spec_from_file_location("validate_layout_templates", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


REGISTRY = Path(__file__).resolve().parents[1] / "references" / "layout-template-registry.json"


class LayoutRegistryTests(unittest.TestCase):
    def test_bundled_registry_is_valid(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        result = MODULE.validate_registry(data)
        self.assertTrue(result["ok"], result)

    def test_duplicate_template_ids_are_rejected(self):
        data = {"templates": [
            {"template_id": "same", "template_version": 1, "position_mode": "relative_template", "slots": [{"id": "main", "text_ref": "x", "offset": {"dx": 0, "dy": 0}}], "fallback": "manual_review"},
            {"template_id": "same", "template_version": 1, "position_mode": "relative_template", "slots": [{"id": "main", "text_ref": "x", "offset": {"dx": 0, "dy": 0}}], "fallback": "manual_review"},
        ]}
        self.assertFalse(MODULE.validate_registry(data)["ok"])

    def test_extension_requires_existing_parent(self):
        data = {"templates": [{
            "template_id": "extension",
            "extends": "missing",
            "template_version": 1,
            "position_mode": "relative_template",
            "slots": [{"id": "main", "text_ref": "x", "offset": {"dx": 0, "dy": 0}}],
            "fallback": "manual_review",
        }]}
        self.assertFalse(MODULE.validate_registry(data)["ok"])

    def test_extension_cycle_is_rejected(self):
        data = {"templates": [
            {
                "template_id": "a",
                "extends": "b",
                "template_version": 1,
                "position_mode": "relative_template",
                "slots": [{"id": "main", "ref_type": "subtitle_unit", "text_ref": "x", "offset": {"dx": 0, "dy": 0}}],
                "constraints": {"safe_zone": "safe", "collision": "block"},
                "fallback": "manual_review",
            },
            {
                "template_id": "b",
                "extends": "a",
                "template_version": 1,
                "position_mode": "relative_template",
                "slots": [{"id": "main", "ref_type": "subtitle_unit", "text_ref": "x", "offset": {"dx": 0, "dy": 0}}],
                "constraints": {"safe_zone": "safe", "collision": "block"},
                "fallback": "manual_review",
            },
        ]}
        result = MODULE.validate_registry(data)
        self.assertFalse(result["ok"])
        self.assertTrue(any("inheritance cycles" in error for error in result["errors"]))

    def test_slot_reference_cycle_is_rejected(self):
        data = {"templates": [{
            "template_id": "slot-cycle",
            "template_version": 1,
            "position_mode": "relative_template",
            "slots": [
                {"id": "a", "ref_type": "subtitle_unit", "text_ref": "x", "relative_to": "b", "offset": {"dx": 0, "dy": 0}},
                {"id": "b", "ref_type": "subtitle_unit", "text_ref": "y", "relative_to": "a", "offset": {"dx": 0, "dy": 0}},
            ],
            "constraints": {"safe_zone": "safe", "collision": "block"},
            "fallback": "manual_review",
        }]}
        result = MODULE.validate_registry(data)
        self.assertFalse(result["ok"])
        self.assertTrue(any("relative-reference cycles" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
