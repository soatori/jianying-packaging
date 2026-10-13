from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from packaging_tools.animation_inventory import build_animation_inventory, resolve_text_animation


class AnimationInventoryTests(unittest.TestCase):
    def test_cache_intersection_classifies_shader_and_word_script_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "Cache"
            shader_path = cache / "effect" / "rid-shader" / "md5-shader"
            shader_path.mkdir(parents=True)
            (shader_path / "effect.xshader").write_text("shader", encoding="utf-8")
            script_path = cache / "effect" / "rid-script" / "md5-script"
            script_path.mkdir(parents=True)
            (script_path / "Printer.lua").write_text("script", encoding="utf-8")
            unknown_path = cache / "effect" / "rid-unknown" / "md5-unknown"
            unknown_path.mkdir(parents=True)
            (unknown_path / "readme.txt").write_text("unknown", encoding="utf-8")

            entries = [
                {"name": "Shader Intro", "resource_id": "rid-shader", "effect_id": "sid-shader", "md5": "md5-shader", "duration_us": 2_000_000},
                {"name": "Word Intro", "resource_id": "rid-script", "effect_id": "sid-script", "md5": "md5-script", "duration_us": 800_000},
                {"name": "Unknown Intro", "resource_id": "rid-unknown", "effect_id": "sid-unknown", "md5": "md5-unknown", "duration_us": 500_000},
                {"name": "Missing Intro", "resource_id": "rid-missing", "effect_id": "sid-missing", "md5": "md5-missing", "duration_us": 500_000},
            ]
            capabilities = {
                "jianying_version": "11.5.0",
                "verified": [{"resource_id": "rid-shader", "md5": "md5-shader", "target_kind": "plain_text", "status": "visually_verified"}],
            }

            report = build_animation_inventory(cache, entries, jianying_version="11.5.0", capabilities=capabilities)

        self.assertTrue(report["ok"], report)
        by_id = {entry["resource_id"]: entry for entry in report["data"]["entries"]}
        self.assertEqual(set(by_id), {"rid-shader", "rid-script", "rid-unknown"})
        self.assertTrue(by_id["rid-shader"]["compatible_plain_text"])
        self.assertEqual(by_id["rid-shader"]["render_type"], "shader")
        self.assertEqual(by_id["rid-script"]["required_inputs"], ["words"])
        self.assertFalse(by_id["rid-script"]["compatible_plain_text"])
        self.assertFalse(by_id["rid-unknown"]["compatible_plain_text"])
        self.assertEqual(Path(by_id["rid-shader"]["cache_path"]).parts[-2:], ("rid-shader", "md5-shader"))

    def test_text_animation_resolution_blocks_unknown_or_unverified_resources(self):
        inventory = {
            "entries": [
                {"resource_id": "shader", "md5": "m1", "default_duration_us": 2_000_000, "render_type": "shader", "required_inputs": [], "cache_path": "cache/shader/m1", "compatible_plain_text": True, "native_verified": True},
                {"resource_id": "script", "md5": "m2", "default_duration_us": 800_000, "render_type": "script", "required_inputs": ["words"], "cache_path": "cache/script/m2", "compatible_plain_text": False, "native_verified": False},
            ]
        }

        shader = resolve_text_animation(inventory, "shader", available_inputs={"text"})
        self.assertEqual(shader["default_duration_us"], 2_000_000)
        self.assertEqual(shader["cache_path"], "cache/shader/m1")
        with self.assertRaisesRegex(ValueError, "requires words"):
            resolve_text_animation(inventory, "script", available_inputs={"text"})
        with self.assertRaisesRegex(ValueError, "unknown or ambiguous"):
            resolve_text_animation(inventory, "missing", available_inputs={"text"})

    def test_inventory_blocks_version_mismatch_and_missing_capability_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "effect" / "rid" / "md5"
            path.mkdir(parents=True)
            (path / "effect.xshader").write_text("shader", encoding="utf-8")
            entry = {"name": "Intro", "resource_id": "rid", "effect_id": "sid", "md5": "md5", "duration_us": 2_000_000}

            mismatch = build_animation_inventory(
                directory, [entry], jianying_version="11.6.0",
                capabilities={"jianying_version": "11.5.0", "verified": []},
            )
            missing = build_animation_inventory(directory, [entry], jianying_version="11.5.0", capabilities=None)

        self.assertFalse(mismatch["ok"])
        self.assertTrue(any("version" in error for error in mismatch["errors"]))
        self.assertFalse(missing["data"]["entries"][0]["native_verified"])
        self.assertFalse(missing["data"]["entries"][0]["compatible_plain_text"])

    def test_script_resource_can_pass_only_with_same_version_plain_text_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "effect" / "rid-script" / "md5-script"
            path.mkdir(parents=True)
            (path / "effect.lua").write_text("script", encoding="utf-8")
            entry = {"name": "Script Intro", "resource_id": "rid-script", "effect_id": "sid-script", "md5": "md5-script", "duration_us": 800_000}
            capabilities = {
                "jianying_version": "11.5.0",
                "verified": [{
                    "resource_id": "rid-script", "md5": "md5-script",
                    "target_kind": "plain_text", "status": "visually_verified",
                    "required_inputs": [],
                }],
            }

            report = build_animation_inventory(directory, [entry], jianying_version="11.5.0", capabilities=capabilities)

        self.assertTrue(report["ok"], report)
        candidate = report["data"]["entries"][0]
        self.assertEqual(candidate["render_type"], "script")
        self.assertEqual(candidate["required_inputs"], [])
        self.assertTrue(candidate["compatible_plain_text"])

    def test_inventory_blocks_ambiguous_resource_and_effect_cache_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "effect"
            for identifier in ("rid", "sid"):
                path = root / identifier / "md5"
                path.mkdir(parents=True)
                (path / "effect.xshader").write_text("shader", encoding="utf-8")
            report = build_animation_inventory(
                directory,
                [{"name": "Intro", "resource_id": "rid", "effect_id": "sid", "md5": "md5", "duration_us": 1000}],
                jianying_version="11.5.0",
            )

        self.assertFalse(report["ok"])
        self.assertTrue(any("ambiguous" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
