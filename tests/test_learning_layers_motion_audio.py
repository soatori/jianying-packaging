import unittest
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from packaging_tools.audio_inventory import classify_audio_events
from packaging_tools.layer_discovery import discover_packaging_layers
from packaging_tools.learning import build_learning_report
from packaging_tools.motion_check import check_motion_reuse


class LearningLayerMotionAudioTests(unittest.TestCase):
    def test_layers_are_discovered_without_fixed_track_count(self):
        report = discover_packaging_layers({
            "tracks": [
                {"id": "base", "type": "text", "role": "subtitle", "segments": [{}]},
                {"id": "emphasis", "type": "text", "segments": [{"track_render_index": 2}]},
                {"id": "aux", "type": "text", "role": "auxiliary", "segments": [{}]},
            ]
        })
        self.assertTrue(report["ok"])
        self.assertEqual(report["data"]["baseline_track_ids"], ["base"])
        self.assertIn("emphasis", report["data"]["emphasis_track_ids"])
        self.assertIn("aux", report["data"]["auxiliary_track_ids"])

    def test_explicit_auxiliary_or_continuation_is_not_promoted_to_baseline(self):
        report = discover_packaging_layers({
            "tracks": [
                {"id": "aux-first", "type": "text", "role": "auxiliary", "segments": [{}]},
                {"id": "continuation", "type": "text", "role": "continuation", "segments": [{}]},
                {"id": "unresolved", "type": "text", "segments": [{"track_render_index": 4}]},
            ]
        })
        self.assertEqual(report["data"]["baseline_track_ids"], ["unresolved"])
        self.assertEqual(report["data"]["auxiliary_track_ids"], ["aux-first"])
        self.assertEqual(report["data"]["continuation_track_ids"], ["continuation"])

    def test_no_unresolved_track_keeps_explicit_roles_and_warns_on_missing_baseline(self):
        report = discover_packaging_layers({
            "tracks": [
                {"id": "aux", "type": "text", "role": "auxiliary", "segments": [{}]},
                {"id": "static", "type": "text", "role": "continuation", "segments": [{}]},
            ]
        })
        self.assertEqual(report["data"]["baseline_track_ids"], [])
        self.assertTrue(any("baseline text tracks" in warning for warning in report["warnings"]))

    def test_adjacent_motion_reuse_warns_but_intentional_motif_is_allowed(self):
        report = check_motion_reuse({"motion_events": [
            {"id": "a", "start_us": 0, "motion": "reveal", "content_region_id": "r1"},
            {"id": "b", "start_us": 10, "motion": "reveal", "content_region_id": "r1"},
            {"id": "c", "start_us": 20, "motion": "reveal", "content_region_id": "r2", "motif_id": "labels"},
            {"id": "d", "start_us": 30, "motion": "reveal", "content_region_id": "r2", "motif_id": "labels"},
        ]})
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["data"]["repeated"]), 1)

    def test_motion_reuse_is_limited_to_adjacent_events_in_one_content_region(self):
        report = check_motion_reuse({"motion_events": [
            {"id": "r1-a", "start_us": 0, "motion": "reveal", "content_region_id": "r1"},
            {"id": "r2-a", "start_us": 10, "motion": "reveal", "content_region_id": "r2"},
            {"id": "r1-b", "start_us": 20, "motion": "reveal", "content_region_id": "r1"},
        ]})
        self.assertEqual(report["data"]["scope"], "adjacent_region")
        self.assertEqual(report["data"]["repeated"], [])

        same_region = check_motion_reuse({"motion_events": [
            {"id": "a", "start_us": 0, "motion": "reveal", "content_region_id": "r1"},
            {"id": "b", "start_us": 10, "motion": "reveal", "content_region_id": "r1"},
        ]})
        self.assertEqual(len(same_region["data"]["repeated"]), 1)
        self.assertEqual(same_region["data"]["repeated"][0]["scope"], "adjacent_region")

    def test_motif_requires_same_id_or_both_intentional_in_same_region(self):
        shared = check_motion_reuse({"motion_events": [
            {"id": "a", "start_us": 0, "motion": "reveal", "content_region_id": "r1", "motif_id": "m1"},
            {"id": "b", "start_us": 10, "motion": "reveal", "content_region_id": "r1", "motif_id": "m1"},
        ]})
        self.assertEqual(shared["data"]["repeated"], [])
        both = check_motion_reuse({"motion_events": [
            {"id": "a", "start_us": 0, "motion": "reveal", "content_region_id": "r1", "intentional_motif": True},
            {"id": "b", "start_us": 10, "motion": "reveal", "content_region_id": "r1", "intentional_motif": True},
        ]})
        self.assertEqual(both["data"]["repeated"], [])

    def test_static_continuation_is_not_a_missing_animation(self):
        report = check_motion_reuse({"motion_events": [{"id": "static", "motion": "static_continuation"}]})
        self.assertEqual(report["data"]["static_events"], ["static"])
        self.assertEqual(report["warnings"], [])

    def test_audio_inventory_separates_music_and_sfx(self):
        report = classify_audio_events({"audio_events": [
            {"id": "s1", "role": "sfx"},
            {"id": "m1", "role": "music"},
            {"id": "a1", "role": "ambience"},
        ]})
        self.assertEqual(report["data"]["counts"], {"sfx": 1, "music": 1, "ambience": 1})

    def test_unknown_audio_role_is_not_counted_as_sfx(self):
        report = classify_audio_events({"audio_events": [{"id": "u1", "name": "unclassified"}]})
        self.assertEqual(report["data"]["counts"], {"unknown": 1})
        self.assertTrue(any("no supported audio role" in warning for warning in report["warnings"]))

    def test_learning_report_is_shared_by_packaging(self):
        report = build_learning_report([
            {
                "id": "p1",
                "area": "motion",
                "pattern": "static continuation layers remain optional",
                "evidence_level": "plan_consistency",
                "generalizability": "generic",
                "promotion_status": "pending",
            }
        ], source_kind="synthetic_fixture")
        self.assertTrue(report["ok"])

    def test_learning_report_rejects_unknown_fields_and_missing_project_case_ref(self):
        unknown = build_learning_report([{
            "id": "p1",
            "area": "motion",
            "pattern": "generic",
            "evidence_level": "plan_consistency",
            "generalizability": "generic",
            "promotion_status": "pending",
            "text": "project-specific copy",
        }], source_kind="synthetic_fixture")
        self.assertFalse(unknown["ok"])
        self.assertTrue(any("text" in error for error in unknown["errors"]))

        missing_ref = build_learning_report([], source_kind="project_case")
        self.assertFalse(missing_ref["ok"])
        self.assertTrue(any("source.case_ref" in error for error in missing_ref["errors"]))


if __name__ == "__main__":
    unittest.main()
