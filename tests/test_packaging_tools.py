from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from packaging_tools.layout_resolver import resolve_relative_layout
from packaging_tools.reference_diff import diff_manual_reference
from packaging_tools.snapshot import build_packaging_snapshot
from packaging_tools.sound_check import check_sound_operations
from packaging_tools.subtitle_resolver import resolve_subtitle_anchor, resolve_text_hashes
from packaging_tools.text_ops import check_text_replacement
from packaging_tools.verification import verify_packaging_result
from packaging_tools.validators.generic_content import check_generic_content
from packaging_tool import main as packaging_main


class PackagingToolTests(unittest.TestCase):
    def test_snapshot_adds_hashes_and_order_fingerprint(self):
        report = build_packaging_snapshot({"tracks": [{"id": "t1", "segments": [{"id": "s1"}]}], "subtitle_units": [{"unit_id": "u1", "text": "测试"}]})
        self.assertTrue(report["ok"])
        self.assertIn("snapshot_hash", report["data"])
        self.assertIn("text_hash", report["data"]["subtitle_units"][0])
        self.assertIn("t1", report["data"]["order_hashes"])

    def test_reference_diff_reports_manual_field_changes(self):
        report = diff_manual_reference({"segments": [{"id": "s1", "visible": True}]}, {"segments": [{"id": "s1", "visible": False}]})
        self.assertTrue(report["ok"])
        self.assertEqual(report["summary"]["change_count"], 1)

    def test_layout_resolution_uses_runtime_anchor(self):
        registry = {"templates": [{"template_id": "stack", "slots": [{"id": "main", "ref_type": "subtitle_unit", "offset": {"dx": 0, "dy": 0}}, {"id": "sub", "ref_type": "subtitle_unit", "relative_to": "main", "offset": {"dx": 1, "dy": 2}}]}]}
        group = {"id": "g1", "layout": {"template_id": "stack"}}
        report = resolve_relative_layout(group, registry, {"x": 10, "y": 20})
        self.assertTrue(report["ok"])
        self.assertEqual(report["data"]["slots"]["sub"]["x"], 11)
        self.assertEqual(report["data"]["slots"]["sub"]["y"], 22)

    def test_text_check_blocks_uncovered_styles(self):
        report = check_text_replacement({"content": "旧"}, {"content": "新文本", "styles": [{"start": 0, "end": 1}]})
        self.assertFalse(report["ok"])
        self.assertTrue(any("style ranges" in error for error in report["errors"]))

    def test_empty_sound_pool_is_reviewable_not_fabricated(self):
        plan = {"groups": [{"id": "g1", "audio": {"action": "add", "candidate_pool_ref": "pop-default", "selected_preset_id": ""}}]}
        report = check_sound_operations(plan, {"presets": []}, {"pools": [{"pool_id": "pop-default", "min_candidates": 3, "candidates": []}]})
        self.assertTrue(report["ok"])
        self.assertTrue(any("candidate_pool_incomplete" in warning for warning in report["warnings"]))

    def test_empty_sound_pool_blocks_final_apply(self):
        plan = {"execution": {"phase": "final"}, "groups": [{"id": "g1", "audio": {"action": "add", "candidate_pool_ref": "pop-default"}}]}
        report = check_sound_operations(plan, {"presets": []}, {"pools": [{"pool_id": "pop-default", "min_candidates": 3, "candidates": []}]})
        self.assertFalse(report["ok"])
        self.assertTrue(any("candidate_pool_incomplete" in error for error in report["errors"]))

    def test_text_hash_mismatch_blocks_resolution(self):
        plan = {"groups": [{"id": "g1", "visuals": [{"text": "错误", "text_ref": "u1", "text_hash": "sha256:bad"}]}]}
        report = resolve_text_hashes(plan, [{"unit_id": "u1", "text": "正确", "text_hash": "sha256:correct"}])
        self.assertFalse(report["ok"])

    def test_pending_order_remap_blocks_subtitle_resolution(self):
        plan = {"comparison": {"source_order_hash": "sha256:a", "target_order_hash": "sha256:b", "remap_status": "pending"}, "groups": []}
        report = resolve_subtitle_anchor(plan, {"subtitle_units": []})
        self.assertFalse(report["ok"])

    def test_verification_detects_source_fingerprint_change(self):
        report = verify_packaging_result({"source_timeline_hash": "a", "segments": []}, {"source_timeline_hash": "b", "segments": []}, {"groups": []})
        self.assertFalse(report["ok"])

    def test_cli_uses_json_by_default_and_returns_success(self):
        registry = Path(__file__).resolve().parents[1] / "references" / "layout-template-registry.json"
        self.assertEqual(packaging_main(["validate", "layout", str(registry)]), 0)

    def test_canonical_visual_hash_and_legacy_alias_conflict_are_fail_closed(self):
        text = "规范文本"
        text_hash = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        manifest = [{"unit_id": "u1", "text": text, "text_hash": text_hash}]
        canonical = {"groups": [{"id": "g1", "visual": [{"object_type": "text", "text": text, "text_ref": "u1", "text_hash": text_hash}]}]}
        self.assertTrue(resolve_text_hashes(canonical, manifest)["ok"])
        conflict = {"groups": [{"id": "g1", "visual": canonical["groups"][0]["visual"], "visuals": [{"object_type": "text", "text": "旧文本", "text_ref": "u1", "text_hash": text_hash}]}]}
        report = resolve_text_hashes(conflict, manifest)
        self.assertFalse(report["ok"])
        self.assertTrue(any("aliases disagree" in error for error in report["errors"]))
        duplicate_manifest = manifest + [{"unit_id": "u1", "text": text, "text_hash": text_hash}]
        self.assertFalse(resolve_text_hashes(canonical, duplicate_manifest)["ok"])

    def test_manifest_hash_is_declared_evidence_not_silently_derived(self):
        text = "规范文本"
        plan = {"groups": [{"id": "g1", "visual": [{"object_type": "text", "text": text, "text_ref": "u1", "text_hash": "sha256:any"}]}]}
        report = resolve_text_hashes(plan, [{"unit_id": "u1", "text": text}])
        self.assertFalse(report["ok"])
        self.assertTrue(any("has no text_hash" in error for error in report["errors"]))

    def test_runtime_anchor_is_observation_data_and_conflicts_block(self):
        plan = {"groups": [{"id": "g1", "semantic_unit_refs": ["u1"], "subtitle_anchor": {"unit_id": "u1"}}]}
        observation = {"subtitle_units": [{"unit_id": "u1", "runtime_anchor": {"x": 0.1, "y": -0.2}}]}
        report = resolve_subtitle_anchor(plan, observation)
        self.assertTrue(report["ok"])
        self.assertEqual(report["data"]["by_group"]["g1"]["runtime_anchor"]["x"], 0.1)
        missing = resolve_subtitle_anchor(plan, {"subtitle_units": [{"unit_id": "u1"}]})
        self.assertFalse(missing["ok"])
        conflict = resolve_subtitle_anchor(plan, {"subtitle_units": [{"unit_id": "u1", "runtime_anchor": {"x": 0.1, "y": -0.2}, "anchor": {"x": 0.2, "y": -0.2}}]})
        self.assertFalse(conflict["ok"])

    def test_layout_transform_inheritance_cycles_bounds_and_collisions(self):
        registry = {"templates": [{"template_id": "t", "slots": [
            {"id": "main", "ref_type": "subtitle_unit", "offset": {"dx": 0, "dy": 0}, "transform": {"scale": 1}},
            {"id": "child", "ref_type": "subtitle_unit", "relative_to": "main", "inherit_transform_from": "main", "offset": {"dx": 0.1, "dy": 0.1}},
        ]}]}
        report = resolve_relative_layout({"id": "g", "layout": {"template_id": "t"}}, registry, {"x": 0, "y": 0})
        self.assertTrue(report["ok"])
        self.assertEqual(report["data"]["slots"]["child"]["transform"]["scale"], 1)
        cycle_registry = {"templates": [{"template_id": "t", "slots": [
            {"id": "a", "ref_type": "subtitle_unit", "inherit_transform_from": "b", "offset": {"dx": 0, "dy": 0}},
            {"id": "b", "ref_type": "subtitle_unit", "inherit_transform_from": "a", "offset": {"dx": 0, "dy": 0}},
        ]}]}
        self.assertFalse(resolve_relative_layout({"id": "g", "layout": {"template_id": "t"}}, cycle_registry, {"x": 0, "y": 0})["ok"])
        collision = {"id": "g", "layout": {"template_id": "t", "constraints": {"collision": "block", "safe_zone": {"x_min": -1, "x_max": 1, "y_min": -1, "y_max": 1}}, "slots": [
            {"id": "a", "ref_type": "subtitle_unit", "offset": {"dx": 2, "dy": 0}},
            {"id": "b", "ref_type": "subtitle_unit", "offset": {"dx": 2, "dy": 0}},
        ]}}
        self.assertFalse(resolve_relative_layout(collision, {"templates": [{"template_id": "t", "slots": []}]}, {"x": 0, "y": 0})["ok"])

    def _sound_fixture(self):
        plan = {"execution": {"phase": "review"}, "sound_selection": {"reuse_cap": 1}, "groups": [{
            "id": "g1", "motion_event": {"start_us": 100, "peak_us": 150, "end_us": 200},
            "audio": {"action": "add_asset", "candidate_pool_ref": "p1", "selected_preset_id": "s1", "motion_family": "reveal", "sound_form": "single_hit", "trim_policy": "text_span", "leading_silence_policy": "skip", "leading_silence_us": 0, "text_range": {"start_us": 100, "end_us": 200}, "target_range": {"start_us": 100, "end_us": 200}},
        }]}
        catalog = {"presets": [{"preset_id": "s1", "status": "verified", "sound_form": "single_hit", "motion_family": "reveal", "duration_us": 500}]}
        pools = {"pools": [{"pool_id": "p1", "status": "verified", "motion_family": "reveal", "min_candidates": 1, "candidates": [{"preset_id": "s1", "status": "verified", "sound_form": "single_hit", "motion_family": "reveal"}]}]}
        return plan, catalog, pools

    def test_sound_safety_gates_cover_pool_status_ranges_collision_and_reuse(self):
        plan, catalog, pools = self._sound_fixture()
        self.assertTrue(check_sound_operations(plan, catalog, pools, [{"id": "voice", "kind": "dialogue", "start_us": 0, "end_us": 50}])["ok"])
        absent = json.loads(json.dumps(plan))
        absent["groups"][0]["audio"]["selected_preset_id"] = "other"
        self.assertFalse(check_sound_operations(absent, catalog, pools, [])["ok"])
        candidate = json.loads(json.dumps(pools))
        candidate["pools"][0]["candidates"][0]["status"] = "candidate"
        review = check_sound_operations(plan, catalog, candidate, [{"id": "voice", "kind": "dialogue", "start_us": 0, "end_us": 50}])
        self.assertTrue(review["ok"])
        final = json.loads(json.dumps(plan))
        final["execution"]["phase"] = "final"
        final_report = check_sound_operations(final, catalog, candidate, [{"id": "voice", "kind": "dialogue", "start_us": 100, "end_us": 200}])
        self.assertFalse(final_report["ok"])
        overlap = check_sound_operations(plan, catalog, pools, [{"id": "voice", "kind": "dialogue", "start_us": 120, "end_us": 180}])
        self.assertTrue(overlap["ok"])
        self.assertTrue(any("overlaps dialogue" in warning for warning in overlap["warnings"]))
        final_overlap = json.loads(json.dumps(plan))
        final_overlap["execution"]["phase"] = "final"
        self.assertFalse(check_sound_operations(final_overlap, catalog, pools, [{"id": "voice", "kind": "dialogue", "start_us": 120, "end_us": 180}])["ok"])
        reuse = json.loads(json.dumps(plan))
        reuse["groups"].append(json.loads(json.dumps(reuse["groups"][0])))
        self.assertFalse(check_sound_operations(reuse, catalog, pools, [{"id": "voice", "kind": "dialogue", "start_us": 0, "end_us": 50}])["ok"])
        sound_only = json.loads(json.dumps(plan))
        sound_only["execution"]["phase"] = "final"
        sound_only_report = check_sound_operations(sound_only, catalog, pools, [{"id": "sfx", "kind": "effect", "start_us": 0, "end_us": 50}])
        self.assertFalse(sound_only_report["ok"])
        self.assertTrue(any("dialogue evidence" in error for error in sound_only_report["errors"]))

    def test_text_mirrors_and_style_ranges_must_stay_synchronized(self):
        prototype = {"content": {"text": "旧", "styles": [{"start": 0, "end": 1}]}, "base_content": "旧", "recognize_text": {"text": "旧"}}
        valid = {"content": {"text": "新", "styles": [{"start": 0, "end": 1}]}, "base_content": "新", "recognize_text": {"text": "新"}}
        self.assertTrue(check_text_replacement(prototype, valid)["ok"])
        mismatch = json.loads(json.dumps(valid))
        mismatch["base_content"] = "旧"
        self.assertFalse(check_text_replacement(prototype, mismatch)["ok"])
        gap = json.loads(json.dumps(valid))
        gap["content"]["styles"] = [{"start": 0, "end": 0}]
        self.assertFalse(check_text_replacement(prototype, gap)["ok"])

    def test_reference_diff_and_verification_are_occurrence_and_plan_aware(self):
        duplicate = diff_manual_reference({"segments": [{"id": "s1"}, {"id": "s1"}]}, {"segments": [{"id": "s1"}]})
        self.assertFalse(duplicate["ok"])
        order = diff_manual_reference({"segments": [{"id": "s2"}, {"id": "s1"}]}, {"segments": [{"id": "s1"}, {"id": "s2"}]})
        self.assertFalse(order["ok"])
        before = {"source_timeline_hash": "sha256:source", "segments": [{"id": "s1", "visible": True}]}
        after = {"source_timeline_hash": "sha256:source", "segments": [{"id": "s1", "visible": True}, {"id": "s3"}]}
        plan = {"groups": [{"id": "g1", "visual": [{"operation": "clone_template", "target_locator": {"timeline": "target", "segment_id": "s2"}}]}]}
        blocked = verify_packaging_result(before, after, plan)
        self.assertFalse(blocked["ok"])
        self.assertTrue(blocked["data"]["unplanned_changes"])
        plan["groups"][0]["visual"][0]["target_locator"]["segment_id"] = "s3"
        allowed = verify_packaging_result(before, after, plan)
        self.assertTrue(allowed["ok"])
        self.assertFalse(verify_packaging_result({"segments": []}, {"segments": []}, {"groups": []})["ok"])

    def test_generic_root_and_cli_input_errors_use_code_two(self):
        missing = check_generic_content([Path("does-not-exist-generic-root")])
        self.assertFalse(missing["ok"])
        self.assertTrue(missing["input_errors"])
        registry = Path(__file__).resolve().parents[1] / "references" / "layout-template-registry.json"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = packaging_main(["validate", "layout", str(registry), "--format", "text"])
        self.assertEqual(code, 0)
        self.assertIn("packaging_layout_validation", output.getvalue())
        self.assertEqual(packaging_main(["validate", "layout", "not-a-json-file.json"]), 2)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(packaging_main(["validate", "layout", str(registry), "--out", directory]), 2)


if __name__ == "__main__":
    unittest.main()
