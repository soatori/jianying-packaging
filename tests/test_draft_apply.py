from __future__ import annotations

import copy
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from packaging_tools import draft_apply
from packaging_tool import main as packaging_main
from tests.test_plan_validator import valid_plan_v12
from tests.test_plan_validator import synthetic_sound_catalog, synthetic_sound_pools


class DraftApplyTests(unittest.TestCase):
    def apply_with_approved_preview(self, plan: dict, **kwargs):
        kwargs.pop("apply", None)
        kwargs.setdefault("temp_root", Path(kwargs["draft_path"]) / "temp")
        preview = draft_apply.apply_packaging_plan(plan, apply=False, **kwargs)
        if not preview.get("ok"):
            return preview
        preview_hash = (preview.get("data") or {}).get("visual_preview_sha256")
        plan["review_report"] = {
            "source_timeline_hash": preview["data"]["source_timeline_hash"],
        }
        if preview_hash:
            plan["review_report"].update(
                visual_preview_status="approved",
                visual_preview_sha256=preview_hash,
            )
        return draft_apply.apply_packaging_plan(plan, apply=True, **kwargs)

    def test_default_temp_root_is_skill_root_temp(self):
        self.assertEqual(draft_apply._default_temp_root(), Path(__file__).resolve().parents[1] / "temp")

    def test_transform_function_is_exposed_for_dry_run_and_fixture_validation(self):
        self.assertTrue(callable(getattr(draft_apply, "transform_packaging_plan", None)))

    def test_adapter_loads_existing_editor_transaction_api_without_editing_it(self):
        editor_root = Path(r"C:\Users\11\.agents\skills\jianying-editor-skill")
        api = draft_apply._load_editor_api(editor_root)

        self.assertTrue(callable(api.JianyingProject.clone_timeline))
        self.assertTrue(callable(api.JianyingProject._write_content))
        self.assertTrue(callable(api.validate_content))

    def test_staging_copy_from_subtitle_drops_material_side_effects_and_preserves_source(self):
        source = draft_value()
        target = copy.deepcopy(source)
        original = copy.deepcopy(source)
        plan = plan_for_visual({
            "operation": "copy_from_subtitle",
            "object_type": "text",
            "source_locator": {"timeline": "manual", "segment_id": "subtitle-q"},
            "target_locator": {"timeline": "target", "track_id": "upper-track"},
            "text": "Synthetic Q",
            "text_ref": "U1",
            "text_hash": text_hash("Synthetic Q"),
        })

        report = draft_apply.transform_packaging_plan(
            target, plan, source_value=source, timeline_values={"manual": source}
        )

        self.assertTrue(report["ok"], report)
        upper = next(track for track in report["data"]["value"]["tracks"] if track["id"] == "upper-track")
        self.assertEqual(len(upper["segments"]), 1)
        copied = upper["segments"][0]
        self.assertEqual(copied["target_timerange"], {"start": 1_000_000, "duration": 500_000})
        self.assertNotEqual(copied["id"], "subtitle-q")
        self.assertNotEqual(copied["material_id"], "text-q")
        self.assertEqual(copied["extra_material_refs"], [])
        self.assertEqual(len(report["data"]["value"]["materials"]["material_animations"]), 2)
        self.assertEqual(read_text(report["data"]["value"], copied), "Synthetic Q")
        self.assertEqual(source, original)
        self.assertEqual(target, original)

    def test_final_copy_from_subtitle_preserves_material_closure(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "copy_from_subtitle",
            "object_type": "text",
            "source_locator": {"timeline": "manual", "segment_id": "subtitle-q"},
            "target_locator": {"timeline": "target", "track_id": "upper-track"},
            "text": "Synthetic Q",
            "text_ref": "U1",
            "text_hash": text_hash("Synthetic Q"),
        })
        plan["execution"]["phase"] = "final"

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source, timeline_values={"manual": source}
        )

        self.assertTrue(report["ok"], report)
        copied = report["data"]["value"]["tracks"][1]["segments"][0]
        self.assertEqual(len(copied["extra_material_refs"]), 1)
        self.assertNotEqual(copied["extra_material_refs"], ["anim-q"])
        self.assertTrue(any(
            item["id"] == copied["extra_material_refs"][0]
            for item in report["data"]["value"]["materials"]["material_animations"]
        ))

    def test_copy_from_subtitle_requires_text_hash_at_apply(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "copy_from_subtitle",
            "object_type": "text",
            "source_locator": {"timeline": "manual", "segment_id": "subtitle-q"},
            "target_locator": {"timeline": "target", "track_id": "upper-track"},
            "text": "Synthetic Q",
            "text_ref": "U1",
        })

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source, timeline_values={"manual": source}
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("text_hash" in error for error in report["errors"]))

    def test_staging_creates_new_track_from_resolved_subtitle_prototype(self):
        source = draft_value()
        target = copy.deepcopy(source)
        target["tracks"] = [track for track in target["tracks"] if track["id"] != "upper-track"]
        plan = plan_for_visual({
            "operation": "copy_from_subtitle",
            "object_type": "text",
            "source_locator": {"timeline": "manual", "segment_id": "subtitle-q"},
            "target_locator": {"timeline": "target", "track_id": "new-upper-track"},
            "text": "Synthetic Q",
            "text_ref": "U1",
            "text_hash": text_hash("Synthetic Q"),
        })

        report = draft_apply.transform_packaging_plan(
            target, plan, source_value=source, timeline_values={"manual": source}
        )

        self.assertTrue(report["ok"], report)
        created = next(track for track in report["data"]["value"]["tracks"] if track["id"] == "new-upper-track")
        self.assertEqual(created["type"], "text")
        self.assertEqual(len(created["segments"]), 1)
        self.assertEqual(len(target["tracks"]), len(source["tracks"]) - 1)

    def test_clone_template_copies_source_segment_using_declared_preset(self):
        source = draft_value()
        template = draft_value()
        template["tracks"][0]["segments"][0]["id"] = "template-q"
        target = copy.deepcopy(source)
        plan = plan_for_visual({
            "operation": "clone_template",
            "object_type": "text",
            "preset_id": "question",
            "target_locator": {"timeline": "target", "track_id": "upper-track"},
            "text": "Synthetic Q",
            "text_ref": "U1",
            "text_hash": text_hash("Synthetic Q"),
        })
        plan["presets"] = [{
            "preset_id": "question",
            "template_source": {"timeline": "template", "segment_ids": ["template-q"]},
        }]

        report = draft_apply.transform_packaging_plan(
            target,
            plan,
            source_value=source,
            timeline_values={"manual": source, "template": template},
        )

        self.assertTrue(report["ok"], report)
        copied = report["data"]["value"]["tracks"][1]["segments"][0]
        self.assertEqual(read_text(report["data"]["value"], copied), "Synthetic Q")
        self.assertNotEqual(copied["material_id"], "text-q")

    def test_disable_original_changes_only_the_target_segment(self):
        source = draft_value()
        target = copy.deepcopy(source)
        plan = plan_for_visual({
            "operation": "disable_original",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
        })

        report = draft_apply.transform_packaging_plan(target, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        changed = report["data"]["value"]["tracks"][0]["segments"][0]
        self.assertIs(changed["visible"], False)
        self.assertIs(source["tracks"][0]["segments"][0]["visible"], True)

    def test_modify_text_updates_nested_style_ranges(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "A longer synthetic question",
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        value = report["data"]["value"]
        segment = value["tracks"][0]["segments"][0]
        material = next(item for item in value["materials"]["texts"] if item["id"] == segment["material_id"])
        content = json.loads(material["content"])
        self.assertEqual(content["text"], "A longer synthetic question")
        self.assertEqual(content["styles"][0]["range"], [0, len(content["text"])])

    def test_modify_text_preserves_proportional_rich_text_ranges(self):
        source = draft_value()
        source["materials"]["texts"][0]["content"] = json.dumps({
            "text": "abcdefghij",
            "styles": [
                {"range": [0, 4], "color": "red"},
                {"range": {"start": 4, "end": 10}, "color": "blue"},
            ],
        })
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "abcdefghijklmnopqrst",
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][0]["segments"][0]
        material = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == segment["material_id"])
        styles = json.loads(material["content"])["styles"]
        self.assertEqual(styles, [
            {"range": [0, 8], "color": "red"},
            {"range": {"start": 8, "end": 20}, "color": "blue"},
        ])

    def test_modify_text_updates_existing_text_mirrors(self):
        source = draft_value()
        material = source["materials"]["texts"][0]
        material["base_content"] = "Synthetic Q"
        material["recognize_text"] = {"text": "Synthetic Q", "confidence": 0.9}
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "Replacement text",
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][0]["segments"][0]
        updated = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == segment["material_id"])
        self.assertEqual(updated["base_content"], "Replacement text")
        self.assertEqual(updated["recognize_text"], {"text": "Replacement text", "confidence": 0.9})

    def test_modify_text_remaps_styles_inside_text_mirrors(self):
        source = draft_value()
        material = source["materials"]["texts"][0]
        material["base_content"] = {
            "text": "Synthetic Q",
            "styles": [{"range": [0, 5], "color": "red"}],
        }
        material["recognize_text"] = json.dumps({
            "text": "Synthetic Q",
            "styles": [{"range": {"start": 5, "end": 11}, "color": "blue"}],
        })
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "Replacement text",
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][0]["segments"][0]
        updated = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == segment["material_id"])
        self.assertEqual(updated["base_content"]["styles"], [{"range": [0, 8], "color": "red"}])
        self.assertEqual(json.loads(updated["recognize_text"])["styles"], [{"range": {"start": 8, "end": 16}, "color": "blue"}])

    def test_modify_text_remaps_every_item_in_list_text_mirror(self):
        source = draft_value()
        material = source["materials"]["texts"][0]
        material["text_content"] = [
            {"text": "Synthetic Q", "styles": [{"range": [0, 5], "color": "red"}]},
            {"text": "Synthetic Q", "styles": [{"range": [5, 11], "color": "blue"}]},
        ]
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "Replacement text",
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][0]["segments"][0]
        updated = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == segment["material_id"])
        self.assertEqual(updated["text_content"], [
            {"text": "Replacement text", "styles": [{"range": [0, 8], "color": "red"}]},
            {"text": "Replacement text", "styles": [{"range": [8, 16], "color": "blue"}]},
        ])

    def test_transform_rejects_legacy_visual_alias_without_canonical_visual(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "Replacement text",
        })
        plan["groups"][0]["visuals"] = plan["groups"][0].pop("visual")

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("canonical group.visual" in error for error in report["errors"]), report)

    def test_transform_rejects_conflicting_legacy_visual_alias_with_canonical_visual(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "Replacement text",
        })
        plan["groups"][0]["visual"] = []
        plan["groups"][0]["visuals"] = [{"operation": "none"}]

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("visual aliases disagree" in error for error in report["errors"]), report)

    def test_modify_text_applies_relative_overrides_once_in_staging(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "A longer synthetic question",
            "overrides": {
                "position_y": {"mode": "relative", "delta": -20.0},
                "scale_x": {"mode": "relative", "delta": 0.1},
            },
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][0]["segments"][0]
        material = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == segment["material_id"])
        self.assertEqual(segment["clip"]["transform"]["y"], -820.0)
        self.assertEqual(material["transform"]["y"], -820.0)
        self.assertEqual(segment["clip"]["scale"]["x"], 1.1)

    def test_modify_text_applies_relative_overrides_once_in_final_without_layout(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "A longer synthetic question",
            "overrides": {"position_y": {"mode": "relative", "delta": -20.0}},
        })
        plan["execution"]["phase"] = "final"
        plan["groups"][0].pop("layout")

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][0]["segments"][0]
        material = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == segment["material_id"])
        self.assertEqual(segment["clip"]["transform"]["y"], -820.0)
        self.assertEqual(material["transform"]["y"], -820.0)
        self.assertEqual(source["tracks"][0]["segments"][0]["clip"]["transform"]["y"], -800.0)
        self.assertEqual(source["materials"]["texts"][0]["transform"]["y"], -800.0)

    def test_relative_scale_override_rejects_non_positive_result(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_segment",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "overrides": {"scale_x": {"mode": "relative", "delta": -2.0}},
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("scale" in error and "positive" in error for error in report["errors"]), report)
        self.assertEqual(source["tracks"][0]["segments"][0]["clip"]["scale"]["x"], 1.0)

    def test_relative_timerange_override_rejects_invalid_result(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_segment",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "overrides": {"start_us": {"mode": "relative", "delta": -2_000_000}},
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("start_us" in error and "non-negative" in error for error in report["errors"]), report)
        self.assertEqual(source["tracks"][0]["segments"][0]["target_timerange"]["start"], 1_000_000)

    def test_relative_override_rejects_non_finite_prototype_value(self):
        source = draft_value()
        source["tracks"][0]["segments"][0]["clip"]["scale"]["x"] = float("inf")
        plan = plan_for_visual({
            "operation": "modify_segment",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "overrides": {"scale_x": {"mode": "relative", "delta": 0.1}},
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("finite" in error for error in report["errors"]), report)

    def test_modify_text_final_layout_applies_deferred_override_once(self):
        source = draft_value()
        base_plan = final_layout_plan()
        base_visual = base_plan["groups"][0]["visual"][0]
        base_visual.update({
            "operation": "modify_text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "Synthetic Q",
        })
        base_plan["groups"][0]["motion"] = "none"
        base_plan["groups"][0].pop("motion_event", None)
        base_report = draft_apply.transform_packaging_plan(source, base_plan, source_value=source)
        self.assertTrue(base_report["ok"], base_report)
        base_y = base_report["data"]["value"]["tracks"][0]["segments"][0]["clip"]["transform"]["y"]

        plan = copy.deepcopy(base_plan)
        visual = plan["groups"][0]["visual"][0]
        visual.update({
            "overrides": {"position_y": {"mode": "relative", "delta": 0.02}},
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][0]["segments"][0]
        material = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == segment["material_id"])
        self.assertAlmostEqual(segment["clip"]["transform"]["y"], base_y + 0.02)
        self.assertAlmostEqual(material["transform"]["y"], base_y + 0.02)

    def test_modify_text_clones_shared_material_before_changing_one_segment(self):
        source = draft_value()
        shared = copy.deepcopy(source["tracks"][0]["segments"][0])
        shared["id"] = "subtitle-q-copy"
        shared["target_timerange"] = {"start": 3_000_000, "duration": 500_000}
        source["tracks"][0]["segments"].append(shared)
        plan = plan_for_visual({
            "operation": "modify_text", "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "Only the first segment changes",
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        value = report["data"]["value"]
        segments = {item["id"]: item for item in value["tracks"][0]["segments"]}
        self.assertNotEqual(segments["subtitle-q"]["material_id"], "text-q")
        self.assertEqual(segments["subtitle-q-copy"]["material_id"], "text-q")
        self.assertEqual(read_text(value, segments["subtitle-q"]), "Only the first segment changes")
        self.assertEqual(read_text(value, segments["subtitle-q-copy"]), "Synthetic Q")

    def test_modify_segment_position_clones_shared_material(self):
        source = draft_value()
        shared = copy.deepcopy(source["tracks"][0]["segments"][0])
        shared["id"] = "subtitle-q-copy"
        shared["target_timerange"] = {"start": 3_000_000, "duration": 500_000}
        source["tracks"][0]["segments"].append(shared)
        plan = plan_for_visual({
            "operation": "modify_segment", "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "overrides": {"position_y": {"mode": "absolute", "value": -640.0}},
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        value = report["data"]["value"]
        segments = {item["id"]: item for item in value["tracks"][0]["segments"]}
        self.assertNotEqual(segments["subtitle-q"]["material_id"], "text-q")
        self.assertEqual(segments["subtitle-q-copy"]["material_id"], "text-q")
        changed_material = next(item for item in value["materials"]["texts"] if item["id"] == segments["subtitle-q"]["material_id"])
        shared_material = next(item for item in value["materials"]["texts"] if item["id"] == "text-q")
        self.assertEqual(changed_material["transform"]["y"], -640.0)
        self.assertEqual(shared_material["transform"]["y"], -800.0)

    def test_modify_text_blocks_malformed_rich_text_material(self):
        source = draft_value()
        source["materials"]["texts"][0]["content"] = "{not-json"
        plan = plan_for_visual({
            "operation": "modify_text",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "text": "Replacement",
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"])
        self.assertTrue(any("invalid JSON" in error for error in report["errors"]))
        self.assertIsNone(report["data"])

    def test_modify_segment_applies_confirmed_relative_position(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_segment",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "overrides": {"position_y": {"mode": "relative", "delta": -20.0}},
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][0]["segments"][0]
        material = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == segment["material_id"])
        self.assertEqual(segment["clip"]["transform"]["y"], -820.0)
        self.assertEqual(material["transform"]["y"], -820.0)

    def test_add_overlay_clones_media_segment_and_material(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "add_overlay",
            "object_type": "video",
            "source_locator": {"timeline": "manual", "segment_id": "video-source"},
            "target_locator": {"timeline": "target", "track_id": "video-track"},
        })

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source, timeline_values={"manual": source}
        )

        self.assertTrue(report["ok"], report)
        value = report["data"]["value"]
        video_track = next(track for track in value["tracks"] if track["id"] == "video-track")
        self.assertEqual(len(video_track["segments"]), 2)
        copied = video_track["segments"][1]
        self.assertNotEqual(copied["id"], "video-source")
        self.assertNotEqual(copied["material_id"], "video-mat")
        self.assertTrue(any(item["id"] == copied["material_id"] for item in value["materials"]["videos"]))

    def test_add_overlay_from_material_locator_uses_same_type_prototype(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "add_overlay",
            "object_type": "video",
            "source_locator": {"timeline": "manual", "asset_id": "video-mat"},
            "target_locator": {"timeline": "target", "track_id": "video-track"},
        })

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source, timeline_values={"manual": source}
        )

        self.assertTrue(report["ok"], report)
        video_track = next(track for track in report["data"]["value"]["tracks"] if track["id"] == "video-track")
        overlay = video_track["segments"][-1]
        self.assertEqual(overlay["material_id"], "video-mat")

    def test_auxiliary_text_requires_existing_topmost_text_track(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "copy_from_subtitle",
            "object_type": "text",
            "source_locator": {"timeline": "manual", "segment_id": "subtitle-q"},
            "target_locator": {"timeline": "target", "track_id": "missing-overlay-track"},
            "text": "Synthetic Q",
            "text_ref": "mark-1",
            "text_hash": text_hash("Synthetic Q"),
        })
        plan["groups"][0]["auxiliary_text_refs"] = ["mark-1"]

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"])
        self.assertTrue(any("existing topmost text track" in error for error in report["errors"]))

    def test_auxiliary_text_blocks_same_track_overlap(self):
        source = draft_value()
        upper = next(track for track in source["tracks"] if track["id"] == "upper-track")
        upper["segments"].append(copy.deepcopy(source["tracks"][0]["segments"][0]))
        upper["segments"][-1]["id"] = "occupied-overlay"
        plan = plan_for_visual({
            "operation": "copy_from_subtitle",
            "object_type": "text",
            "source_locator": {"timeline": "manual", "segment_id": "subtitle-q"},
            "target_locator": {"timeline": "target", "track_id": "upper-track"},
            "text": "Synthetic Q",
            "text_ref": "mark-1",
            "text_hash": text_hash("Synthetic Q"),
        })
        plan["groups"][0]["auxiliary_text_refs"] = ["mark-1"]

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"])
        self.assertTrue(any("overlaps" in error and "upper-track" in error for error in report["errors"]))

    def test_audio_reuse_clone_and_add_actions_map_ranges(self):
        source = draft_value()
        for action in ("reuse_existing", "clone_asset", "add_asset"):
            with self.subTest(action=action):
                target = copy.deepcopy(source)
                audio = {
                    "action": action,
                    "target_locator": {"timeline": "target", "segment_id": "sound-source"} if action == "reuse_existing" else {"timeline": "target", "track_id": "audio-track"},
                    "target_range": {"start_us": 4_000_000, "duration_us": 250_000},
                    "source_range": {"start_us": 100_000, "duration_us": 250_000},
                    "volume": 0.7,
                }
                if action != "reuse_existing":
                    audio["source_locator"] = {"timeline": "manual", "segment_id": "sound-source"}
                plan = {"schema_version": "1.2", "source": {"timeline": "manual"}, "target": {"timeline_name": "packaged"}, "execution": {"mode": "apply", "phase": "staging"}, "groups": [{"id": "g1", "range": {"start_us": 1_000_000, "duration_us": 500_000}, "visual": [], "audio": audio}]}

                report = draft_apply.transform_packaging_plan(
                    target, plan, source_value=source, timeline_values={"manual": source}
                )

                self.assertTrue(report["ok"], report)
                audio_track = next(track for track in report["data"]["value"]["tracks"] if track["id"] == "audio-track")
                segment = audio_track["segments"][0] if action == "reuse_existing" else audio_track["segments"][-1]
                self.assertEqual(segment["target_timerange"], {"start": 4_000_000, "duration": 250_000})
                self.assertEqual(segment["source_timerange"], {"start": 100_000, "duration": 250_000})
                self.assertEqual(segment["volume"], 0.7)
                if action != "reuse_existing":
                    self.assertNotEqual(segment["material_id"], "sound-mat")

    def test_audio_fades_update_a_cloned_verified_fade_material(self):
        source = draft_value()
        source["tracks"][3]["segments"][0]["extra_material_refs"] = ["fade-a"]
        source["materials"]["audio_fades"] = [{
            "id": "fade-a", "fade_in_duration": 0, "fade_out_duration": 0,
            "fade_type": 0, "type": "audio_fade",
        }]
        shared_audio = copy.deepcopy(source["tracks"][3]["segments"][0])
        shared_audio["id"] = "sound-copy"
        shared_audio["target_timerange"] = {"start": 5_000_000, "duration": 300_000}
        source["tracks"][3]["segments"].append(shared_audio)
        audio = {
            "action": "reuse_existing", "asset_id": "sound-mat",
            "target_locator": {"timeline": "target", "segment_id": "sound-source"},
            "fade_in_us": 1_000, "fade_out_us": 2_000,
        }
        plan = {"schema_version": "1.2", "source": {"timeline": "manual"},
                "target": {"timeline_name": "packaged"},
                "execution": {"mode": "apply", "phase": "staging"},
                "groups": [{"id": "g1", "range": {"start_us": 1_000, "duration_us": 3_000}, "visual": [], "audio": audio}]}

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        value = report["data"]["value"]
        segments = {item["id"]: item for item in value["tracks"][3]["segments"]}
        segment = segments["sound-source"]
        self.assertEqual(segments["sound-copy"]["extra_material_refs"], ["fade-a"])
        self.assertNotIn("fade-a", segment["extra_material_refs"])
        self.assertEqual(len(segment["extra_material_refs"]), 1)
        fade_id = segment["extra_material_refs"][0]
        fade = next(item for item in value["materials"]["audio_fades"] if item["id"] == fade_id)
        self.assertEqual((fade["fade_in_duration"], fade["fade_out_duration"]), (1_000, 2_000))
        self.assertEqual(source["materials"]["audio_fades"][0]["fade_in_duration"], 0)

    def test_audio_fade_request_blocks_without_a_verified_fade_prototype(self):
        source = draft_value()
        plan = {"schema_version": "1.2", "source": {"timeline": "manual"},
                "target": {"timeline_name": "packaged"},
                "execution": {"mode": "apply", "phase": "staging"},
                "groups": [{"id": "g1", "range": {"start_us": 1_000, "duration_us": 3_000}, "visual": [],
                            "audio": {"action": "reuse_existing", "asset_id": "sound-mat",
                                      "target_locator": {"timeline": "target", "segment_id": "sound-source"},
                                      "fade_in_us": 1_000}}]}

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"])
        self.assertTrue(any("fade" in error.lower() and "prototype" in error.lower() for error in report["errors"]))
        self.assertIsNone(report["data"])

    def test_add_audio_asset_from_material_locator_uses_audio_prototype(self):
        source = draft_value()
        plan = {
            "schema_version": "1.2",
            "source": {"timeline": "manual"},
            "target": {"timeline_name": "packaged"},
            "execution": {"mode": "apply", "phase": "final"},
            "groups": [{
                "id": "g1", "range": {"start_us": 1_000_000, "duration_us": 500_000},
                "visual": [],
                "audio": {
                    "action": "add_asset",
                    "source_locator": {"timeline": "manual", "asset_id": "sound-mat"},
                    "target_locator": {"timeline": "target", "track_id": "audio-track"},
                    "target_range": {"start_us": 4_000_000, "duration_us": 250_000},
                    "source_range": {"start_us": 100_000, "duration_us": 250_000},
                },
            }],
        }

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source, timeline_values={"manual": source}
        )

        self.assertTrue(report["ok"], report)
        audio_track = next(track for track in report["data"]["value"]["tracks"] if track["id"] == "audio-track")
        audio = audio_track["segments"][-1]
        self.assertEqual(audio["material_id"], "sound-mat")
        self.assertEqual(audio["target_timerange"], {"start": 4_000_000, "duration": 250_000})

    def test_new_visual_operation_blocks_locator_for_a_different_timeline(self):
        source = draft_value()
        other = draft_value()
        plan = plan_for_visual({
            "operation": "copy_from_subtitle", "object_type": "text",
            "source_locator": {"timeline": "manual", "segment_id": "subtitle-q"},
            "target_locator": {"timeline": "wrong-target", "track_id": "upper-track"},
            "text": "Synthetic Q", "text_ref": "U1", "text_hash": text_hash("Synthetic Q"),
        })

        report = draft_apply.transform_packaging_plan(
            source, plan, source_value=source, timeline_values={"manual": source, "wrong-target": other}
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("target timeline" in error for error in report["errors"]))
        self.assertIsNone(report["data"])

    def test_new_audio_operation_blocks_locator_for_a_different_timeline(self):
        source = draft_value()
        other = draft_value()
        plan = {"schema_version": "1.2", "source": {"timeline": "manual"},
                "target": {"timeline_name": "packaged"},
                "execution": {"mode": "apply", "phase": "staging"},
                "groups": [{"id": "g1", "range": {"start_us": 1_000, "duration_us": 3_000}, "visual": [],
                            "audio": {"action": "add_asset", "asset_id": "sound-mat",
                                      "source_locator": {"timeline": "manual", "segment_id": "sound-source"},
                                      "target_locator": {"timeline": "wrong-target", "track_id": "audio-track"},
                                      "target_range": {"start_us": 4_000, "duration_us": 2_000}}}]}

        report = draft_apply.transform_packaging_plan(
            source, plan, source_value=source, timeline_values={"manual": source, "wrong-target": other}
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("target timeline" in error for error in report["errors"]))
        self.assertIsNone(report["data"])

    def test_unknown_visual_override_blocks_before_returning_a_value(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_segment",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "overrides": {"opacity": {"mode": "absolute", "value": 0.5}},
        })

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"])
        self.assertTrue(any("opacity" in error for error in report["errors"]))
        self.assertIsNone(report["data"])

    def test_clone_template_does_not_ignore_unmapped_overrides(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "clone_template",
            "object_type": "text",
            "preset_id": "question",
            "target_locator": {"timeline": "target", "track_id": "upper-track"},
            "text": "Synthetic Q",
            "text_ref": "U1",
            "text_hash": text_hash("Synthetic Q"),
            "overrides": {"opacity": {"mode": "absolute", "value": 0.5}},
        })
        plan["presets"] = [{"preset_id": "question", "template_source": {"timeline": "manual", "segment_ids": ["subtitle-q"]}}]

        report = draft_apply.transform_packaging_plan(
            source, plan, source_value=source, timeline_values={"manual": source}
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("opacity" in error for error in report["errors"]))

    def test_new_audio_asset_requires_resolved_target_range(self):
        source = draft_value()
        plan = {
            "schema_version": "1.2", "source": {"timeline": "manual"},
            "target": {"timeline_name": "packaged"},
            "execution": {"mode": "apply", "phase": "final"},
            "groups": [{
                "id": "g1", "range": {"start_us": 1_000_000, "duration_us": 500_000},
                "visual": [],
                "audio": {
                    "action": "add_asset",
                    "source_locator": {"timeline": "manual", "segment_id": "sound-source"},
                    "target_locator": {"timeline": "target", "track_id": "audio-track"},
                },
            }],
        }

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"])
        self.assertTrue(any("target_range" in error for error in report["errors"]))

    def test_final_layout_uses_runtime_subtitle_anchor(self):
        source = draft_value()
        template = draft_value()
        add_motion_payload(template)
        template["tracks"][0]["segments"][0]["id"] = "template-q"
        plan = final_layout_plan()

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source,
            timeline_values={"manual": source, "template": template},
        )

        self.assertTrue(report["ok"], report)
        copied = report["data"]["value"]["tracks"][1]["segments"][0]
        material = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == copied["material_id"])
        self.assertGreaterEqual(copied["clip"]["transform"]["x"], -0.8)
        self.assertLessEqual(copied["clip"]["transform"]["x"], 0.8)
        self.assertGreaterEqual(copied["clip"]["transform"]["y"], -0.8)
        self.assertLessEqual(copied["clip"]["transform"]["y"], 0.8)
        self.assertEqual(material["transform"]["x"], copied["clip"]["transform"]["x"])
        self.assertFalse(any("safe zone" in warning for warning in report["warnings"]))

    def test_final_layout_fails_closed_when_font_metrics_are_missing(self):
        source = draft_value()
        template = draft_value()
        template["materials"]["texts"][0].pop("font_path")
        add_motion_payload(template)
        template["tracks"][0]["segments"][0]["id"] = "template-q"

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), final_layout_plan(), source_value=source,
            timeline_values={"manual": source, "template": template},
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("reliable font metrics" in error for error in report["errors"]))

    def test_diagonal_layout_keeps_rotation_zero_and_fits_measured_width(self):
        source = draft_value()
        template = draft_value()
        add_motion_payload(template)
        template["tracks"][0]["segments"][0]["id"] = "template-q"
        plan = final_layout_plan()
        plan["groups"][0]["layout"]["pattern"] = "diagonal_stagger"
        plan["groups"][0]["layout"]["slots"][0]["offset"]["dx"] = 600.0

        with patch.object(draft_apply, "measure_text_lines", return_value=[{"text": "Synthetic Q", "width_px": 200.0, "height_px": 20.0}]):
            report = draft_apply.transform_packaging_plan(
                copy.deepcopy(source), plan, source_value=source,
                timeline_values={"manual": source, "template": template},
            )

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][1]["segments"][0]
        self.assertAlmostEqual(segment["clip"]["transform"]["x"], 0.615, places=3)
        self.assertEqual(segment["clip"].get("rotation", 0), 0)

    def test_explicit_final_position_override_takes_precedence_over_layout(self):
        source = draft_value()
        template = draft_value()
        add_motion_payload(template)
        template["tracks"][0]["segments"][0]["id"] = "template-q"
        plan = final_layout_plan()
        plan["groups"][0]["visual"][0]["overrides"] = {
            "position_y": {"mode": "absolute", "value": 0.3}
        }

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source,
            timeline_values={"manual": source, "template": template},
        )

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][1]["segments"][0]
        material = next(item for item in report["data"]["value"]["materials"]["texts"] if item["id"] == segment["material_id"])
        self.assertEqual(segment["clip"]["transform"]["y"], 0.3)
        self.assertEqual(material["transform"]["y"], 0.3)

    def test_final_layout_blocks_stale_subtitle_order_hash(self):
        source = draft_value()
        template = draft_value()
        add_motion_payload(template)
        template["tracks"][0]["segments"][0]["id"] = "template-q"
        plan = final_layout_plan()
        plan["comparison"]["target_order_hash"] = "sha256:stale"

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source,
            timeline_values={"manual": source, "template": template},
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("target_order_hash" in error for error in report["errors"]))

    def test_final_layout_blocks_when_current_subtitle_timing_order_changed(self):
        source = draft_value()
        source["tracks"][0]["segments"][0]["target_timerange"]["start"] = 3_000_000
        source["tracks"][0]["segments"][1]["target_timerange"]["start"] = 1_000_000
        template = draft_value()
        add_motion_payload(template)
        template["tracks"][0]["segments"][0]["id"] = "template-q"
        plan = final_layout_plan()

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source,
            timeline_values={"manual": source, "template": template},
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("target_order_hash" in error for error in report["errors"]))

    def test_final_layout_blocks_disagreeing_subtitle_transform_sources(self):
        source = draft_value()
        source["materials"]["texts"][0]["transform"]["y"] = -700.0
        template = draft_value()
        add_motion_payload(template)
        template["tracks"][0]["segments"][0]["id"] = "template-q"
        plan = final_layout_plan()

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source,
            timeline_values={"manual": source, "template": template},
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("transforms disagree" in error for error in report["errors"]))

    def test_final_motion_request_blocks_template_without_motion_payload(self):
        source = draft_value()
        template = draft_value()
        template["tracks"][0]["segments"][0]["id"] = "template-q"
        plan = final_layout_plan()

        report = draft_apply.transform_packaging_plan(
            copy.deepcopy(source), plan, source_value=source,
            timeline_values={"manual": source, "template": template},
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("motion payload" in error for error in report["errors"]))

    def test_text_intro_uses_verified_cache_path_and_clamps_to_row_duration(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "copy_from_subtitle",
            "object_type": "text",
            "source_locator": {"timeline": "manual", "segment_id": "subtitle-q"},
            "target_locator": {"timeline": "target", "track_id": "upper-track"},
            "text": "Synthetic Q",
            "text_ref": "U1",
            "text_hash": text_hash("Synthetic Q"),
            "duration_us": 1_840_000,
            "animation": {"resource_id": "rid-shader", "duration_us": 1_840_000},
        })
        group = plan["groups"][0]
        group["range"]["duration_us"] = 1_840_000
        group["motion"] = "reveal"
        group["motion_event"] = {"start_us": 1_000_000, "peak_us": 1_920_000, "end_us": 2_840_000}
        group.pop("layout", None)
        plan["execution"]["phase"] = "final"
        plan["project_profile"] = {"canvas_width": 1080, "canvas_height": 1920}
        inventory = {"entries": [{
            "name": "Verified shader",
            "resource_id": "rid-shader",
            "effect_id": "effect-shader",
            "md5": "md5-shader",
            "default_duration_us": 2_000_000,
            "cache_path": r"C:\Jianying\User Data\Cache\effect\rid-shader\md5-shader",
            "render_type": "shader",
            "required_inputs": [],
            "native_verified": True,
            "compatible_plain_text": True,
        }]}

        report = draft_apply.transform_packaging_plan(
            source, plan, source_value=source, animation_inventory=inventory,
        )

        self.assertTrue(report["ok"], report)
        candidate = report["data"]["value"]
        segment = next(track for track in candidate["tracks"] if track["id"] == "upper-track")["segments"][0]
        self.assertEqual(segment["clip"]["transform"], source["tracks"][0]["segments"][0]["clip"]["transform"])
        material = next(item for item in candidate["materials"]["material_animations"] if item["id"] in segment["extra_material_refs"])
        intro = next(item for item in material["animations"] if item["type"] == "in")
        self.assertEqual(intro["duration"], 1_840_000)
        self.assertEqual(intro["path"], inventory["entries"][0]["cache_path"])
        self.assertEqual(report["data"]["changes"][0]["animation_duration_us"], 1_840_000)

    def test_text_intro_blocks_script_effect_without_words_input(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "copy_from_subtitle",
            "object_type": "text",
            "source_locator": {"timeline": "manual", "segment_id": "subtitle-q"},
            "target_locator": {"timeline": "target", "track_id": "upper-track"},
            "text": "Synthetic Q",
            "text_ref": "U1",
            "text_hash": text_hash("Synthetic Q"),
            "duration_us": 500_000,
            "animation": {"resource_id": "rid-script", "duration_us": 500_000},
        })
        plan["execution"]["phase"] = "final"
        inventory = {"entries": [{
            "resource_id": "rid-script", "effect_id": "effect-script", "md5": "md5-script",
            "default_duration_us": 800_000, "cache_path": "cache/script/md5-script",
            "render_type": "script", "required_inputs": ["words"],
            "native_verified": True, "compatible_plain_text": False,
        }]}

        report = draft_apply.transform_packaging_plan(
            source, plan, source_value=source, animation_inventory=inventory,
        )

        self.assertFalse(report["ok"])
        self.assertTrue(any("requires words" in error for error in report["errors"]))

    def test_text_global_alpha_updates_visibility_separately(self):
        source = draft_value()
        plan = plan_for_visual({
            "operation": "modify_segment",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "overrides": {"global_alpha": {"mode": "absolute", "value": 0.5}},
        })
        plan["groups"][0].pop("layout", None)
        plan["project_profile"] = {"canvas_width": 1080, "canvas_height": 1920}

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertTrue(report["ok"], report)
        segment = report["data"]["value"]["tracks"][0]["segments"][0]
        self.assertEqual(segment["global_alpha"], 0.5)
        self.assertIs(segment["visible"], True)
        self.assertEqual(segment["clip"]["transform"], {"x": 0.0, "y": -800.0, "z": 0.0})

    def test_text_global_alpha_requires_confirmed_segment_field(self):
        source = draft_value()
        source["tracks"][0]["segments"][0].pop("global_alpha")
        plan = plan_for_visual({
            "operation": "modify_segment",
            "object_type": "text",
            "target_locator": {"timeline": "target", "segment_id": "subtitle-q"},
            "overrides": {"global_alpha": {"mode": "absolute", "value": 0.5}},
        })
        plan["groups"][0].pop("layout", None)

        report = draft_apply.transform_packaging_plan(source, plan, source_value=source)

        self.assertFalse(report["ok"])
        self.assertTrue(any("segment.global_alpha prototype" in error for error in report["errors"]))

    def test_apply_dry_run_builds_local_animation_inventory_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = FakeProject(root, draft_value())
            cache_root = root / "Cache"
            asset_path = cache_root / "effect" / "rid-shader" / "md5-shader"
            asset_path.mkdir(parents=True)
            (asset_path / "effect.xshader").write_text("shader", encoding="utf-8")
            plan = final_apply_plan(str(root.resolve()))
            visual = plan["groups"][0]["visual"][0]
            visual["duration_us"] = 1_840_000
            visual["animation"] = {"resource_id": "rid-shader", "duration_us": 1_840_000}
            plan["groups"][0]["range"] = {"start_us": 1_000_000, "duration_us": 1_840_000}
            plan["groups"][0]["motion_event"] = {"start_us": 1_000_000, "peak_us": 1_920_000, "end_us": 2_840_000}
            plan["groups"][0]["motion"] = "reveal"
            capabilities = {
                "jianying_version": "11.5.0",
                "verified": [{"resource_id": "rid-shader", "md5": "md5-shader", "target_kind": "plain_text", "status": "visually_verified"}],
            }
            temp_root = root / "temp"
            metadata = {"name": "Verified shader", "resource_id": "rid-shader", "effect_id": "sid-shader", "md5": "md5-shader", "duration_us": 2_000_000}

            with patch.object(draft_apply, "_text_intro_entries", return_value=[metadata]):
                report = draft_apply.apply_packaging_plan(
                    plan,
                    draft_path=directory,
                    timeline="manual",
                    editor_root=Path("unused"),
                    sound_catalog=synthetic_sound_catalog(),
                    sound_pools=synthetic_sound_pools(),
                    animation_cache_root=cache_root,
                    animation_capabilities=capabilities,
                    animation_version="11.5.0",
                    apply=False,
                    project=project,
                    editor_api=FakeEditorApi,
                    temp_root=temp_root,
                )

            self.assertTrue(report["ok"], report)
            inventory_path = Path(report["data"]["animation_inventory_path"])
            self.assertTrue(inventory_path.is_file())
            self.assertTrue(inventory_path.is_relative_to(temp_root))
            preview_path = Path(report["data"]["visual_preview_path"])
            self.assertTrue(preview_path.is_file())
            self.assertEqual(
                report["data"]["visual_preview_sha256"],
                "sha256:" + __import__("hashlib").sha256(preview_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(project.clone_calls, [])
            self.assertEqual(project.write_calls, [])

    def test_apply_requires_approved_matching_preview_before_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = draft_value()
            add_motion_payload(source)
            project = FakeProject(root, source)
            plan = final_apply_plan(str(root.resolve()))
            temp_root = root / "temp"
            with patch.object(draft_apply, "measure_text_lines", return_value=[{"text": "Synthetic Q", "width_px": 120.0, "height_px": 18.0}]), patch.object(
                draft_apply, "_font_for_material", return_value=("synthetic.ttf", 18.0, 0.0)
            ):
                preview = draft_apply.apply_packaging_plan(
                    plan, draft_path=directory, timeline="manual", editor_root=Path("unused"),
                    sound_catalog=synthetic_sound_catalog(), sound_pools=synthetic_sound_pools(),
                    apply=False, project=project, editor_api=FakeEditorApi, temp_root=temp_root,
                )
                self.assertTrue(preview["ok"], preview)
                plan["review_report"] = {
                    "source_timeline_hash": preview["data"]["source_timeline_hash"],
                }
                unapproved = draft_apply.apply_packaging_plan(
                    plan, draft_path=directory, timeline="manual", editor_root=Path("unused"),
                    sound_catalog=synthetic_sound_catalog(), sound_pools=synthetic_sound_pools(),
                    apply=True, project=project, editor_api=FakeEditorApi, temp_root=temp_root,
                )
                self.assertFalse(unapproved["ok"])
                self.assertTrue(any("must be approved" in error for error in unapproved["errors"]))
                self.assertEqual(project.clone_calls, [])
                plan["review_report"] = {
                    "visual_preview_status": "approved",
                    "visual_preview_sha256": preview["data"]["visual_preview_sha256"],
                    "source_timeline_hash": preview["data"]["source_timeline_hash"],
                }
                position = plan["groups"][0]["visual"][0]["overrides"]["position_y"]
                original_y = position["value"]
                position["value"] = original_y + 0.01
                rejected = draft_apply.apply_packaging_plan(
                    plan, draft_path=directory, timeline="manual", editor_root=Path("unused"),
                    sound_catalog=synthetic_sound_catalog(), sound_pools=synthetic_sound_pools(),
                    apply=True, project=project, editor_api=FakeEditorApi, temp_root=temp_root,
                )
                self.assertFalse(rejected["ok"])
                self.assertTrue(any("preview hash" in error for error in rejected["errors"]))
                position["value"] = original_y
                applied = draft_apply.apply_packaging_plan(
                    plan, draft_path=directory, timeline="manual", editor_root=Path("unused"),
                    sound_catalog=synthetic_sound_catalog(), sound_pools=synthetic_sound_pools(),
                    apply=True, project=project, editor_api=FakeEditorApi, temp_root=temp_root,
                )

            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["data"]["visual_preview_sha256"], preview["data"]["visual_preview_sha256"])
            self.assertEqual(len(project.clone_calls), 1)
            self.assertEqual(applied["data"]["human_visual_audio_review"], "pending")

    def test_apply_blocks_when_reviewed_source_hash_is_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = draft_value()
            add_motion_payload(source)
            project = FakeProject(root, source)
            plan = final_apply_plan(str(root.resolve()))
            temp_root = root / "temp"
            kwargs = {
                "draft_path": directory,
                "timeline": "manual",
                "editor_root": Path("unused"),
                "sound_catalog": synthetic_sound_catalog(),
                "sound_pools": synthetic_sound_pools(),
                "project": project,
                "editor_api": FakeEditorApi,
                "temp_root": temp_root,
            }

            with patch.object(draft_apply, "measure_text_lines", return_value=[{"text": "Synthetic Q", "width_px": 120.0, "height_px": 18.0}]), patch.object(
                draft_apply, "_font_for_material", return_value=("synthetic.ttf", 18.0, 0.0)
            ):
                preview = draft_apply.apply_packaging_plan(plan, apply=False, **kwargs)
                self.assertTrue(preview["ok"], preview)
                plan["review_report"] = {
                    "visual_preview_status": "approved",
                    "visual_preview_sha256": preview["data"]["visual_preview_sha256"],
                    "source_timeline_hash": preview["data"]["source_timeline_hash"],
                }
                project.values["T1"]["duration"] += 1
                refreshed_preview = draft_apply.apply_packaging_plan(plan, apply=False, **kwargs)
                self.assertTrue(refreshed_preview["ok"], refreshed_preview)
                self.assertEqual(
                    refreshed_preview["data"]["visual_preview_sha256"],
                    plan["review_report"]["visual_preview_sha256"],
                )
                self.assertNotEqual(
                    refreshed_preview["data"]["source_timeline_hash"],
                    plan["review_report"]["source_timeline_hash"],
                )
                report = draft_apply.apply_packaging_plan(plan, apply=True, **kwargs)

            self.assertFalse(report["ok"], report)
            self.assertTrue(any("source_timeline_hash" in error for error in report["errors"]))
            self.assertEqual(project.clone_calls, [])
            self.assertEqual(project.write_calls, [])

    def test_apply_blocks_when_reviewed_source_hash_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            project = FakeProject(Path(directory), draft_value())
            plan = staging_plan(str(Path(directory).resolve()))

            report = draft_apply.apply_packaging_plan(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
                temp_root=Path(directory) / "temp",
            )

            self.assertFalse(report["ok"], report)
            self.assertTrue(any("source_timeline_hash" in error for error in report["errors"]))
            self.assertEqual(project.clone_calls, [])
            self.assertEqual(project.write_calls, [])

    def test_dry_run_does_not_clone_or_write(self):
        with tempfile.TemporaryDirectory() as directory:
            project = FakeProject(Path(directory), draft_value())
            plan = staging_plan(str(Path(directory).resolve()))

            report = draft_apply.apply_packaging_plan(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=False,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["data"]["dry_run"])
            self.assertEqual(project.clone_calls, [])
            self.assertEqual(project.write_calls, [])

    def test_dry_run_warns_on_associated_backup_drift_and_uses_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = str(Path(directory) / "T1" / "draft_content.json.bak")
            project = FakeProject(
                Path(directory), draft_value(),
                replica_errors_by_timeline={"T1": [f"Replica differs from primary: {backup}"]},
            )
            plan = staging_plan(str(Path(directory).resolve()))

            report = draft_apply.apply_packaging_plan(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=False,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertTrue(report["ok"], report)
            self.assertEqual(report["errors"], [])
            self.assertEqual(report["warnings"], [f"Replica differs from primary: {backup}"])
            self.assertEqual(project.write_calls, [])
            self.assertEqual(project.clone_calls, [])

    def test_apply_writes_only_a_clone_and_reports_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            source = draft_value()
            project = FakeProject(Path(directory), source)
            before = copy.deepcopy(source)
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertTrue(report["ok"], report)
            self.assertEqual(source, before)
            self.assertEqual(len(project.clone_calls), 1)
            self.assertEqual(project.write_calls, ["T2"])
            self.assertTrue(report["data"]["backup"])
            self.assertEqual(report["data"]["target_timeline_id"], "T2")
            self.assertEqual(report["data"]["phase_state"]["packaging_staging"], "reviewing")
            self.assertIn("review", report["data"]["next_step"].lower())

    def test_apply_blocks_before_candidate_write_when_clone_backup_is_unusable(self):
        with tempfile.TemporaryDirectory() as directory:
            source = draft_value()
            missing_backup = str(Path(directory) / "missing-clone-backup")
            project = FakeProject(Path(directory), source, clone_backup=missing_backup)
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"], report)
            self.assertTrue(any("clone backup" in error for error in report["input_errors"]), report)
            self.assertEqual(project.write_calls, [])

    def test_apply_blocks_before_candidate_write_when_clone_backup_manifest_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            source = draft_value()
            project = FakeProject(Path(directory), source)
            (project.clone_backup / "manifest.json").write_text(json.dumps({
                "root": str(Path(directory).resolve()),
                "files": [],
            }), encoding="utf-8")
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"], report)
            self.assertTrue(any("project index" in error or "no files" in error for error in report["input_errors"]), report)
            self.assertEqual(project.write_calls, [])

    def test_apply_blocks_before_candidate_write_when_clone_backup_file_hash_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            source = draft_value()
            project = FakeProject(Path(directory), source)
            (project.clone_backup / "project.json").write_text("tampered", encoding="utf-8")
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"], report)
            self.assertTrue(any("hash" in error for error in report["input_errors"]), report)
            self.assertEqual(project.write_calls, [])

    def test_apply_blocks_when_clone_backup_is_not_the_preclone_project_index(self):
        with tempfile.TemporaryDirectory() as directory:
            source = draft_value()
            project = FakeProject(Path(directory), source)
            backup_index = project.clone_backup / "project.json"
            backup_index.write_text("{\"unrelated\":true}", encoding="utf-8")
            digest = hashlib.sha256(backup_index.read_bytes()).hexdigest()
            (project.clone_backup / "manifest.json").write_text(json.dumps({
                "root": str(Path(directory).resolve()),
                "files": [{"path": "project.json", "sha256": digest}],
            }), encoding="utf-8")
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"], report)
            self.assertTrue(any("pre-clone" in error for error in report["input_errors"]), report)
            self.assertEqual(project.write_calls, [])

    def test_apply_blocks_source_validation_false_without_structured_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            project = FakeProject(Path(directory), draft_value())
            project.validate = lambda selector: {
                "ok": False,
                "errors": [],
                "warnings": [],
                "replica_manifest": project.replica_manifest(selector),
            }
            plan = staging_plan(str(Path(directory).resolve()))

            report = draft_apply.apply_packaging_plan(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=False,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"], report)
            self.assertTrue(any("without structured errors" in error for error in report["errors"]), report)

    def test_apply_blocks_candidate_validation_false_without_structured_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            project = FakeProject(Path(directory), draft_value())
            editor_api = SimpleNamespace(validate_content=lambda *_args, **_kwargs: {"ok": False})
            plan = staging_plan(str(Path(directory).resolve()))

            report = draft_apply.apply_packaging_plan(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=False,
                project=project,
                editor_api=editor_api,
            )

            self.assertFalse(report["ok"], report)
            self.assertTrue(any("candidate content validation" in error for error in report["errors"]), report)

    def test_real_editor_transaction_applies_to_temporary_plaintext_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = draft_value()
            write_editor_draft(root, source)
            api = draft_apply._load_editor_api(Path(r"C:\Users\11\.agents\skills\jianying-editor-skill"))
            project = api.JianyingProject(root)
            project._assert_editor_closed = lambda: None
            plan = staging_plan(str(root.resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=str(root),
                timeline="manual",
                editor_root=Path(r"C:\Users\11\.agents\skills\jianying-editor-skill"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=api,
            )

            self.assertTrue(report["ok"], report)
            target_id = report["data"]["target_timeline_id"]
            self.assertNotEqual(target_id, "T1")
            self.assertTrue(Path(report["data"]["backup"]).is_dir())
            self.assertTrue(project.validate(target_id)["ok"])
            self.assertEqual(project.decode(root / "Timelines" / "T1" / "draft_content.json").value, source)
            target = project.decode(root / "Timelines" / target_id / "draft_content.json").value
            upper = next(track for track in target["tracks"] if track["id"] == "upper-track")
            self.assertEqual(len(upper["segments"]), 1)

    def test_real_editor_transaction_applies_final_layout_to_temporary_plaintext_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = draft_value()
            add_motion_payload(source)
            write_editor_draft(root, source)
            api = draft_apply._load_editor_api(Path(r"C:\Users\11\.agents\skills\jianying-editor-skill"))
            project = api.JianyingProject(root)
            project._assert_editor_closed = lambda: None
            plan = final_apply_plan(str(root.resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=str(root),
                timeline="manual",
                editor_root=Path(r"C:\Users\11\.agents\skills\jianying-editor-skill"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=api,
            )

            self.assertTrue(report["ok"], report)
            target_id = report["data"]["target_timeline_id"]
            self.assertTrue(project.validate(target_id)["ok"])
            self.assertEqual(project.decode(root / "Timelines" / "T1" / "draft_content.json").value, source)
            target = project.decode(root / "Timelines" / target_id / "draft_content.json").value
            overlay = next(track for track in target["tracks"] if track["id"] == "upper-track")["segments"][0]
            overlay_material = next(item for item in target["materials"]["texts"] if item["id"] == overlay["material_id"])
            self.assertGreaterEqual(overlay["clip"]["transform"]["x"], -0.8)
            self.assertLessEqual(overlay["clip"]["transform"]["x"], 0.8)
            self.assertEqual(overlay["clip"]["transform"]["y"], -0.44)
            self.assertEqual(overlay_material["transform"]["y"], -0.44)
            self.assertTrue(report["data"]["readback_matches_plan"])

    def test_final_apply_resolves_layout_and_writes_approved_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            source = draft_value()
            add_motion_payload(source)
            project = FakeProject(Path(directory), source)
            before = copy.deepcopy(source)
            plan = final_apply_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertTrue(report["ok"], report)
            self.assertEqual(source, before)
            self.assertTrue(report["data"]["readback_matches_plan"])
            self.assertTrue(report["data"]["source_preserved"])
            self.assertEqual(len(project.values["T2"]["tracks"][1]["segments"]), 1)
            self.assertEqual(report["data"]["human_visual_audio_review"], "pending")
            self.assertEqual(report["data"]["phase_state"]["packaging_final"], "awaiting_human_visual_audio_review")

    def test_editor_close_warning_is_advisory_and_preserved_on_success(self):
        with tempfile.TemporaryDirectory() as directory:
            warning = "Jianying is running; closing is recommended."
            project = FakeProject(Path(directory), draft_value())
            project._assert_editor_closed = lambda: warning
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertTrue(report["ok"], report)
            self.assertIn(warning, report["warnings"])
            self.assertEqual(project.clone_calls, [("T1", "packaged")])
            self.assertEqual(project.write_calls, ["T2"])

    def test_editor_close_warning_is_preserved_on_clone_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            warning = "Jianying is running; closing is recommended."
            project = FakeProject(Path(directory), draft_value())
            project._assert_editor_closed = lambda: warning
            project.clone_timeline = lambda *_args, **_kwargs: {"ok": False, "error": "injected clone failure"}
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"])
            self.assertIn(warning, report["warnings"])
            self.assertTrue(any("injected clone failure" in error for error in report["errors"]))
            self.assertEqual(project.write_calls, [])

    def test_editor_clone_exception_warning_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            warning = "Jianying is running; closing is recommended."
            project = FakeProject(Path(directory), draft_value())

            def raise_clone(*_args, **_kwargs):
                exc = RuntimeError("injected clone exception")
                exc.warnings = [warning]
                raise exc

            project.clone_timeline = raise_clone
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"])
            self.assertIn(warning, report["warnings"])
            self.assertTrue(any("injected clone exception" in error for error in report["input_errors"]))

    def test_apply_failure_leaves_source_and_new_clone_at_prewrite_state(self):
        with tempfile.TemporaryDirectory() as directory:
            source = draft_value()
            project = FakeProject(Path(directory), source, fail_write=True)
            warning = "Jianying is running; closing is recommended."
            project._assert_editor_closed = lambda: warning
            before = copy.deepcopy(source)
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"])
            self.assertEqual(source, before)
            self.assertEqual(project.values["T2"]["tracks"], source["tracks"])
            self.assertTrue(any("injected write failure" in error for error in report["errors"]))
            self.assertIn(warning, report["warnings"])

    def test_readback_decode_failure_restores_clone_without_decoding_first(self):
        with tempfile.TemporaryDirectory() as directory:
            project = FakeProject(Path(directory), draft_value(), fail_decode_while_target_is_modified=True)
            warning = "Jianying is running; closing is recommended."
            project._assert_editor_closed = lambda: warning
            plan = staging_plan(str(Path(directory).resolve()))

            report = self.apply_with_approved_preview(
                plan, draft_path=directory, timeline="manual", editor_root=Path("unused"),
                sound_catalog={"presets": []}, sound_pools={"pools": []}, apply=True,
                project=project, editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"])
            self.assertEqual(project.values["T2"]["tracks"], draft_value()["tracks"])
            self.assertEqual(project.write_calls, ["T2", "T2"])
            self.assertTrue(report["data"]["target_clone_preserved"])
            self.assertGreaterEqual(project.validate_calls.count("T2"), 1)
            self.assertIn(warning, report["warnings"])

    def test_apply_gate_blocks_before_editor_access(self):
        with tempfile.TemporaryDirectory() as directory:
            project = FakeProject(Path(directory), draft_value())
            plan = staging_plan(str(Path(directory).resolve()))
            plan["source"]["content_pass"] = "stable"

            report = draft_apply.apply_packaging_plan(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertFalse(report["ok"])
            self.assertEqual(project.resolve_calls, [])
            self.assertEqual(project.clone_calls, [])

    def test_missing_editor_api_blocks_without_direct_write_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = staging_plan(str(Path(directory).resolve()))
            report = draft_apply.apply_packaging_plan(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path(directory),
                sound_catalog={"presets": []},
                sound_pools={"pools": []},
                apply=True,
            )

        self.assertFalse(report["ok"])
        self.assertTrue(any("jianying-editor CLI not found" in error for error in report["input_errors"]))

    def test_sound_apply_requires_dialogue_evidence_before_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            source = draft_value()
            add_motion_payload(source)
            project = FakeProject(Path(directory), source)
            plan = final_apply_plan(str(Path(directory).resolve()))
            plan["groups"][0]["audio"] = {"action": "none"}
            temp_root = Path(directory) / "temp"
            with patch.object(draft_apply, "measure_text_lines", return_value=[{"text": "Synthetic Q", "width_px": 120.0, "height_px": 18.0}]), patch.object(
                draft_apply, "_font_for_material", return_value=("synthetic.ttf", 18.0, 0.0)
            ):
                preview = draft_apply.apply_packaging_plan(
                    plan,
                    draft_path=directory,
                    timeline="manual",
                    editor_root=Path("unused"),
                    sound_catalog=synthetic_sound_catalog(),
                    sound_pools=synthetic_sound_pools(),
                    apply=False,
                    project=project,
                    editor_api=FakeEditorApi,
                    temp_root=temp_root,
                )
            self.assertTrue(preview["ok"], preview)
            plan["review_report"] = {"source_timeline_hash": preview["data"]["source_timeline_hash"]}
            audio = copy.deepcopy(valid_plan_v12()["groups"][0]["audio"])
            audio.update({
                "action": "reuse_existing",
                "asset_id": "sound-mat",
                "target_locator": {"timeline": "target", "segment_id": "sound-source"},
                "target_range": {"start_us": 1_000, "duration_us": 3_000},
                "text_range": {"start_us": 1_000, "duration_us": 3_000},
            })
            plan["groups"][0]["audio"] = audio

            report = draft_apply.apply_packaging_plan(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog=synthetic_sound_catalog(),
                sound_pools=synthetic_sound_pools(),
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
                temp_root=temp_root,
            )

            self.assertFalse(report["ok"])
            self.assertEqual(project.clone_calls, [])
            self.assertTrue(any("dialogue evidence" in error for error in report["errors"]))

    def test_sound_apply_accepts_explicit_non_overlapping_dialogue_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source = draft_value()
            add_motion_payload(source)
            project = FakeProject(Path(directory), source)
            plan = final_apply_plan(str(Path(directory).resolve()))
            audio = copy.deepcopy(valid_plan_v12()["groups"][0]["audio"])
            audio.update({
                "action": "reuse_existing",
                "asset_id": "sound-mat",
                "target_locator": {"timeline": "target", "segment_id": "sound-source"},
                "target_range": {"start_us": 1_000, "duration_us": 3_000},
                "text_range": {"start_us": 1_000, "duration_us": 3_000},
            })
            plan["groups"][0]["audio"] = audio

            report = self.apply_with_approved_preview(
                plan,
                draft_path=directory,
                timeline="manual",
                editor_root=Path("unused"),
                sound_catalog=synthetic_sound_catalog(),
                sound_pools=synthetic_sound_pools(),
                existing_audio=[{"id": "voice", "kind": "dialogue", "start_us": 5_000_000, "end_us": 6_000_000}],
                apply=True,
                project=project,
                editor_api=FakeEditorApi,
            )

            self.assertTrue(report["ok"], report)
            self.assertEqual(project.clone_calls, [("T1", "packaged-final")])

    def test_cli_apply_defaults_to_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            project = FakeProject(Path(directory), draft_value())
            plan_path = Path(directory) / "plan.json"
            plan_path.write_text(json.dumps(staging_plan(str(Path(directory).resolve()))), encoding="utf-8")
            editor_api = SimpleNamespace(JianyingProject=lambda _root: project, validate_content=FakeEditorApi.validate_content)
            stdout = io.StringIO()
            with patch.object(draft_apply, "_load_editor_api", return_value=editor_api):
                with contextlib.redirect_stdout(stdout):
                    code = packaging_main([
                        "apply",
                        "--draft", directory,
                        "--timeline", "manual",
                        "--plan", str(plan_path),
                    ])

            report = json.loads(stdout.getvalue())
            self.assertEqual(code, 0, report)
            self.assertTrue(report["data"]["dry_run"])
            self.assertEqual(project.clone_calls, [])
            self.assertEqual(project.write_calls, [])


def text_hash(text: str) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_material(material_id: str, text: str) -> dict:
    windows = Path(os.environ.get("WINDIR", "C:/Windows"))
    return {
        "id": material_id,
        "type": "text",
        "text": text,
        "content": json.dumps({"text": text, "styles": [{"range": [0, len(text)]}]}, ensure_ascii=False),
        "transform": {"x": 0.0, "y": -800.0, "z": 0.0},
        "font_size": 8.0,
        "font_path": str(windows / "Fonts" / "arial.ttf"),
    }


def text_segment(segment_id: str, material_id: str, start: int, duration: int, aux_id: str) -> dict:
    return {
        "id": segment_id,
        "material_id": material_id,
        "target_timerange": {"start": start, "duration": duration},
        "source_timerange": {"start": 0, "duration": duration},
        "extra_material_refs": [aux_id],
        "clip": {"transform": {"x": 0.0, "y": -800.0, "z": 0.0}, "scale": {"x": 1.0, "y": 1.0}},
        "render_index": 10000,
        "track_render_index": 0,
        "visible": True,
        "global_alpha": 1.0,
    }


def draft_value() -> dict:
    return {
        "id": "T1",
        "duration": 10_000_000,
        "tracks": [
            {
                "id": "subtitle-track",
                "name": "Subtitles",
                "type": "text",
                "render_index": 10,
                "segments": [
                    text_segment("subtitle-q", "text-q", 1_000_000, 500_000, "anim-q"),
                    text_segment("subtitle-a", "text-a", 2_000_000, 600_000, "anim-a"),
                ],
            },
            {"id": "upper-track", "name": "Review", "type": "text", "render_index": 11, "segments": []},
            {
                "id": "video-track", "name": "Video", "type": "video", "render_index": 1,
                "segments": [{"id": "video-source", "material_id": "video-mat", "target_timerange": {"start": 0, "duration": 1_000_000}, "source_timerange": {"start": 0, "duration": 1_000_000}, "extra_material_refs": []}],
            },
            {
                "id": "audio-track", "name": "SFX", "type": "audio", "render_index": 12,
                "segments": [{"id": "sound-source", "material_id": "sound-mat", "target_timerange": {"start": 1_000_000, "duration": 300_000}, "source_timerange": {"start": 0, "duration": 300_000}, "extra_material_refs": [], "volume": 1.0}],
            },
        ],
        "materials": {
            "texts": [text_material("text-q", "Synthetic Q"), text_material("text-a", "Synthetic A")],
            "material_animations": [
                {"id": "anim-q", "type": "sticker_animation", "animations": []},
                {"id": "anim-a", "type": "sticker_animation", "animations": []},
            ],
            "videos": [{"id": "video-mat", "path": "synthetic.mp4", "duration": 1_000_000}],
            "audios": [{"id": "sound-mat", "path": "synthetic.wav", "type": "sound", "duration": 300_000}],
        },
    }


def add_motion_payload(value: dict) -> None:
    value["materials"]["material_animations"][0]["animations"] = [
        {"type": "reveal", "duration_us": 300_000, "peak_us": 150_000}
    ]


def plan_for_visual(visual: dict) -> dict:
    return {
        "schema_version": "1.2",
        "source": {"timeline": "manual"},
        "target": {"timeline_name": "packaged", "clone_source": True},
        "execution": {"mode": "apply", "phase": "staging"},
        "project_profile": {"canvas_width": 1080, "canvas_height": 1920},
        "project_profile": {"canvas_width": 1080, "canvas_height": 1920},
        "groups": [{
            "id": "g1",
            "range": {"start_us": 1_000_000, "duration_us": 500_000},
            "layout": {"slots": []},
            "visual": [visual],
            "audio": {"action": "none"},
        }],
        "presets": [],
    }


def order_hash(unit_ids: list[str]) -> str:
    raw = json.dumps(unit_ids, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    import hashlib
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def final_layout_plan() -> dict:
    plan = plan_for_visual({
        "operation": "clone_template",
        "object_type": "text",
        "preset_id": "question",
        "target_locator": {"timeline": "target", "track_id": "upper-track"},
        "text": "Synthetic Q",
        "text_ref": "U1",
        "text_hash": text_hash("Synthetic Q"),
    })
    plan["execution"]["phase"] = "final"
    plan["presets"] = [{
        "preset_id": "question",
        "template_source": {"timeline": "template", "segment_ids": ["template-q"]},
    }]
    plan["source"]["final_subtitle_units"] = [
        {"unit_id": "U1", "text_hash": text_hash("Synthetic Q"), "status": "approved"},
        {"unit_id": "U2", "text_hash": text_hash("Synthetic A"), "status": "approved"},
    ]
    plan["comparison"] = {
        "source_order_hash": order_hash(["U1", "U2"]),
        "target_order_hash": order_hash(["U1", "U2"]),
        "remap_status": "verified",
    }
    plan["groups"][0].update({
        "semantic_unit_refs": ["U1", "U2"],
        "subtitle_anchor": {"unit_id": "U1", "text_hash": text_hash("Synthetic Q"), "text_authority": "final_visible_subtitle"},
        "motion": "reveal",
        "motion_event": {"start_us": 1_000_000, "peak_us": 1_200_000, "end_us": 1_500_000},
    })
    plan["groups"][0]["layout"] = {
        "template_id": "center_stack", "template_version": 1,
        "position_mode": "relative_template", "anchor": {"type": "runtime_reference", "x": "X0", "y": "Y0"},
        "slots": [
            {"id": "main", "ref_type": "subtitle_unit", "text_ref": "U1", "offset": {"dx": 4.0, "dy": 6.0}},
            {"id": "secondary", "ref_type": "subtitle_unit", "text_ref": "U2", "relative_to": "main", "offset": {"dx": 0.0, "dy": 10.0}},
        ],
        "constraints": {"safe_zone": {"x_min": -0.8, "x_max": 0.8, "y_min": -0.8, "y_max": 0.8}, "collision": "warn"},
        "fallback": "manual_review",
    }
    plan["project_profile"] = {"canvas_width": 1080, "canvas_height": 1920}
    return plan


def read_text(value: dict, segment: dict) -> str:
    materials = value.get("materials", {})
    material = next(item for item in materials["texts"] if item["id"] == segment["material_id"])
    nested = json.loads(material["content"])
    return nested["text"]


def staging_plan(draft_path: str) -> dict:
    plan = valid_plan_v12()
    plan["source"]["draft_path"] = draft_path
    plan["execution"].update(mode="apply", phase="staging")
    plan["target"]["timeline_name"] = "packaged"
    plan["project_profile"] = {"canvas_width": 1080, "canvas_height": 1920}
    group = plan["groups"][0]
    group["status"] = "approved"
    group["visual"][0].update(
        operation="copy_from_subtitle",
        source_locator={"timeline": "manual", "segment_id": "subtitle-q"},
        target_locator={"timeline": "target", "track_id": "upper-track"},
        text="Synthetic Q",
        text_ref="U1",
        text_hash=text_hash("Synthetic Q"),
    )
    group["audio"] = {"action": "none"}
    return plan


def final_apply_plan(draft_path: str) -> dict:
    plan = valid_plan_v12()
    plan["source"]["draft_path"] = draft_path
    plan["source"]["timeline"] = "manual"
    plan["execution"].update(mode="apply", phase="final")
    plan["target"]["timeline_name"] = "packaged-final"
    plan["project_profile"] = {"canvas_width": 1080, "canvas_height": 1920}
    plan["comparison"].update(
        source_order_hash=order_hash(["U1", "U2"]),
        target_order_hash=order_hash(["U1", "U2"]),
        remap_status="verified",
    )
    group = plan["groups"][0]
    group["status"] = "approved"
    group["source_order_hash"] = order_hash(["U1", "U2"])
    group["target_order_hash"] = order_hash(["U1", "U2"])
    group["visual"][0].update(
        operation="clone_template",
        text="Synthetic Q",
        text_ref="U1",
        text_hash=text_hash("Synthetic Q"),
        preset_id="question",
        target_locator={"timeline": "target", "track_id": "upper-track"},
    )
    group["layout"]["slots"][0]["offset"] = {"dx": 4.0, "dy": 6.0}
    group["layout"]["constraints"]["safe_zone"] = {
        "x_min": -0.8, "x_max": 0.8, "y_min": -0.8, "y_max": 0.8,
    }
    plan["presets"][0]["template_source"] = {"timeline": "manual", "segment_ids": ["subtitle-q"]}
    group["audio"] = {"action": "none"}
    return plan


def write_editor_draft(root: Path, value: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    timeline_dir = root / "Timelines" / str(value["id"])
    timeline_dir.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    (root / "Timelines" / "project.json").write_text(json.dumps({
        "main_timeline_id": value["id"],
        "timelines": [{"id": value["id"], "name": "manual"}],
    }), encoding="utf-8")
    (root / "timeline_layout.json").write_text(json.dumps({"activeTimeline": value["id"]}), encoding="utf-8")
    (root / "draft_content.json").write_text(content, encoding="utf-8")
    (timeline_dir / "draft_content.json").write_text(content, encoding="utf-8")


class FakeEditorApi:
    @staticmethod
    def validate_content(value: dict, expected_id: str | None = None) -> dict:
        errors = []
        if expected_id and value.get("id") != expected_id:
            errors.append("content id mismatch")
        materials = {
            str(material.get("id"))
            for bucket in (value.get("materials") or {}).values()
            if isinstance(bucket, list)
            for material in bucket
            if isinstance(material, dict)
        }
        for track in value.get("tracks", []):
            for segment in track.get("segments", []):
                if segment.get("material_id") not in materials:
                    errors.append("missing material reference")
        return {"ok": not errors, "errors": errors, "warnings": []}


class FakeProject:
    def __init__(self, root: Path, value: dict, *, fail_write: bool = False, fail_decode_while_target_is_modified: bool = False, replica_errors_by_timeline: dict[str, list[str]] | None = None, clone_backup: str | None = None):
        self.root = root
        self.values = {"T1": copy.deepcopy(value)}
        self.values["T1"]["id"] = "T1"
        self.entries = [{"id": "T1", "name": "manual"}]
        self.clone_calls: list[tuple[str, str]] = []
        self.write_calls: list[str] = []
        self.resolve_calls: list[str] = []
        self.validate_calls: list[str] = []
        self.fail_write = fail_write
        self.fail_decode_while_target_is_modified = fail_decode_while_target_is_modified
        self.replica_errors_by_timeline = replica_errors_by_timeline or {}
        self.clone_snapshots: dict[str, dict] = {}
        self.project_index_path = self.root / "project.json"
        self.project_index_path.write_text(json.dumps({"timelines": [{"id": "T1", "name": "manual"}]}), encoding="utf-8")
        self.clone_backup = Path(clone_backup) if clone_backup is not None else self.root / "synthetic-clone-backup"
        if clone_backup is None:
            self.clone_backup.mkdir(parents=True, exist_ok=True)
            backup_index = self.clone_backup / "project.json"
            backup_index.write_bytes(self.project_index_path.read_bytes())
            (self.clone_backup / "manifest.json").write_text(json.dumps({
                "root": str(self.root.resolve()),
                "files": [{
                    "path": "project.json",
                    "sha256": hashlib.sha256(backup_index.read_bytes()).hexdigest(),
                }],
            }), encoding="utf-8")

    def resolve_timeline(self, selector: str) -> dict:
        self.resolve_calls.append(str(selector))
        matches = [entry for entry in self.entries if selector in {entry["id"], entry["name"]}]
        if len(matches) != 1:
            raise ValueError(f"timeline selector {selector!r} matched {len(matches)} entries")
        return matches[0]

    def timeline_entries(self) -> list[dict]:
        return copy.deepcopy(self.entries)

    def content_path(self, timeline_id: str) -> Path:
        return self.root / timeline_id / "draft_content.json"

    def decode(self, path: Path):
        timeline_id = Path(path).parent.name
        if (
            self.fail_decode_while_target_is_modified
            and timeline_id in self.clone_snapshots
            and self.values[timeline_id] != self.clone_snapshots[timeline_id]
        ):
            raise RuntimeError("injected target read-back decode failure")
        return SimpleNamespace(value=copy.deepcopy(self.values[timeline_id]), encoding="plaintext")

    def validate(self, selector: str) -> dict:
        entry = self.resolve_timeline(selector)
        self.validate_calls.append(entry["id"])
        report = FakeEditorApi.validate_content(self.values[entry["id"]], entry["id"])
        report["errors"].extend(self.replica_errors_by_timeline.get(entry["id"], []))
        report["ok"] = not report["errors"]
        report["replica_manifest"] = self.replica_manifest(entry["id"])
        return report

    def replica_manifest(self, selector: str) -> dict:
        entry = self.resolve_timeline(selector)
        timeline_id = entry["id"]
        primary = str(self.content_path(timeline_id))
        replicas = [{"path": primary, "role": "primary", "primary": True, "associated": True}]
        backup_path = str(self.root / timeline_id / "draft_content.json.bak")
        if self.replica_errors_by_timeline.get(timeline_id):
            replicas.append({"path": backup_path, "role": "writable-backup", "primary": False, "associated": True})
        return {"timeline_id": timeline_id, "primary": primary, "replicas": replicas, "errors": [], "count": len(replicas)}

    def _editor_close_warning(self) -> str | None:
        return None

    def _assert_editor_closed(self) -> str | None:
        return None

    def clone_timeline(self, selector: str, name: str, activate: bool = False) -> dict:
        source = self.resolve_timeline(selector)
        target_id = "T2"
        candidate = copy.deepcopy(self.values[source["id"]])
        candidate["id"] = target_id
        self.values[target_id] = candidate
        self.clone_snapshots[target_id] = copy.deepcopy(candidate)
        self.entries.append({"id": target_id, "name": name})
        self.clone_calls.append((source["id"], name))
        return {"ok": True, "timeline_id": target_id, "name": name, "backup": str(self.clone_backup)}

    def _write_content(self, timeline_id: str, value: dict) -> dict:
        self.write_calls.append(timeline_id)
        if self.fail_write:
            raise RuntimeError("injected write failure")
        self.values[timeline_id] = copy.deepcopy(value)
        if timeline_id in self.clone_snapshots and self.values[timeline_id] == self.clone_snapshots[timeline_id]:
            self.fail_decode_while_target_is_modified = False
        return {"backup": "synthetic-write-backup", "files_written": [f"{timeline_id}/draft_content.json"]}


if __name__ == "__main__":
    unittest.main()
