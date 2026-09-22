import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "packaging_tools" / "validators" / "sound_catalog_impl.py"
SPEC = importlib.util.spec_from_file_location("validate_sound_preset_catalog", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def catalog():
    return {
        "catalog_version": "1.0",
        "presets": [{
            "preset_id": "synthetic-a",
            "display_name": "Synthetic hit",
            "duration_us": 1000,
            "leading_silence_us": 100,
            "tail_duration_us": 200,
            "sound_form": "single_hit",
            "default_trim_policy": "text_span",
            "leading_silence_policy": "skip",
            "status": "verified",
            "evidence": ["waveform", "manual_listen"],
            "last_verified": "2026-01-01",
        }],
    }


def pools():
    return {
        "pool_version": "1.0",
        "pools": [{
            "pool_id": "synthetic-pool",
            "motion_family": "reveal",
            "min_candidates": 3,
            "candidates": [
                {"preset_id": "synthetic-a", "rank": 1, "sound_form": "single_hit", "status": "verified"},
                {"preset_id": "synthetic-b", "rank": 2, "sound_form": "single_hit", "status": "candidate"},
                {"preset_id": "synthetic-c", "rank": 3, "sound_form": "single_hit", "status": "needs_listen"},
            ],
            "status": "verified",
        }],
    }


class SoundCatalogTests(unittest.TestCase):
    def test_valid_catalog_and_pool(self):
        result = MODULE.validate_catalog(catalog())
        self.assertTrue(result["ok"], result)
        pool_result = MODULE.validate_pools(pools(), set(result["preset_ids"]) | {"synthetic-b", "synthetic-c"})
        self.assertTrue(pool_result["ok"], pool_result)

    def test_leading_silence_cannot_exceed_duration(self):
        data = catalog()
        data["presets"][0]["leading_silence_us"] = 2000
        self.assertFalse(MODULE.validate_catalog(data)["ok"])

    def test_duplicate_candidate_is_rejected(self):
        data = pools()
        data["pools"][0]["candidates"].append({"preset_id": "synthetic-a", "rank": 4, "sound_form": "single_hit", "status": "verified"})
        self.assertFalse(MODULE.validate_pools(data)["ok"])

    def test_incomplete_pool_is_explicitly_marked(self):
        data = pools()
        data["pools"][0]["candidates"] = [{"preset_id": "synthetic-a", "rank": 1, "sound_form": "single_hit", "status": "verified"}]
        data["pools"][0]["status"] = "candidate_pool_incomplete"
        result = MODULE.validate_pools(data)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["warnings"])

    def test_project_fields_are_rejected(self):
        data = catalog()
        data["presets"][0]["draft_path"] = "<project>"
        self.assertFalse(MODULE.validate_catalog(data)["ok"])

    def test_validation_does_not_mutate_input(self):
        data = catalog()
        before = copy.deepcopy(data)
        MODULE.validate_catalog(data)
        self.assertEqual(data, before)


if __name__ == "__main__":
    unittest.main()
