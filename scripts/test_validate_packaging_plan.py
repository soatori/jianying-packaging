#!/usr/bin/env python3
"""Regression tests for validate_packaging_plan.py."""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).with_name("validate_packaging_plan.py")
SPEC = importlib.util.spec_from_file_location("validate_packaging_plan", SCRIPT)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - environment failure
    raise RuntimeError(f"cannot load {SCRIPT}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def valid_plan() -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "source": {
            "draft_path": "D:/draft",
            "timeline": "manual",
            "content_pass": "approved",
            "subtitle_alignment": {
                "id": "alignment-v1",
                "hash": "sha256:alignment",
                "status": "approved",
            },
        },
        "target": {"timeline_name": "packaged", "clone_source": True},
        "execution": {
            "mode": "review",
            "phase": "final",
            "preserve_source": True,
            "preserve_manual_edits": True,
            "allow_in_place": False,
            "allow_manual_overwrite": False,
            "covered_subtitle_policy": "preserve",
        },
        "staging": {
            "required": True,
            "mode": "copy_to_upper_review_track",
            "source_timeline": "manual",
            "target_timeline": "packaged",
            "review_status": "approved",
            "original_subtitles": "preserve",
        },
        "duplicate_policy": {
            "start_tolerance_us": 40_000,
            "text_must_match": False,
            "cross_track": "cover_or_delete_target",
            "same_track": "preserve_continuation",
        },
        "template_health": [{
            "preset_id": "question",
            "status": "verified",
            "font_source": "fonts[0].path",
            "visual_verification": True,
        }],
        "sound_selection": {
            "reuse_cap": 3,
            "selection_order": ["motion_family", "sound_family", "reuse_cap", "semantic_special_slot"],
        },
        "light_content_ops": [],
        "visual_capability_requirements": [{
            "capability": "composite_text",
            "evidence_status": "demonstrated",
            "visual_verification": True,
        }],
        "presets": [
            {
                "preset_id": "question",
                "preset_type": "composite_text",
                "template_source": {
                    "timeline": "template",
                    "segment_ids": ["template-segment"],
                },
                "allowed_overrides": ["position_y"],
            }
        ],
        "groups": [
            {
                "id": "g1",
                "status": "review",
                "range": {"start_us": 1000, "duration_us": 5000},
                "context": "A question needs emphasis.",
                "category": "question",
                "level": 2,
                "motion": "reveal",
                "motion_event": {
                    "start_us": 1000,
                    "peak_us": 2000,
                    "end_us": 3000,
                },
                "visual": [
                    {
                        "operation": "clone_template",
                        "object_type": "text",
                        "preset_id": "question",
                        "target_locator": {
                            "timeline": "target",
                            "track_id": "text-track",
                        },
                        "text": "这是一个问题",
                        "overrides": {
                            "position_y": {
                                "mode": "absolute",
                                "value": -0.44,
                            }
                        },
                    }
                ],
                "audio": {"action": "none"},
            }
        ],
    }


class ValidatePackagingPlanTests(unittest.TestCase):
    def assert_error_contains(self, plan: dict[str, Any], fragment: str) -> None:
        errors, _ = VALIDATOR.validate_plan(plan)
        self.assertTrue(
            any(fragment in error for error in errors),
            f"expected {fragment!r} in errors: {errors}",
        )

    def test_valid_plan(self) -> None:
        errors, warnings = VALIDATOR.validate_plan(valid_plan())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_malformed_enum_types_are_rejected_without_crashing(self) -> None:
        for field, value in (
            ("category", []),
            ("level", {}),
            ("status", []),
        ):
            plan = valid_plan()
            plan["groups"][0][field] = value
            errors, _ = VALIDATOR.validate_plan(plan)
            self.assertTrue(errors, field)

        plan = valid_plan()
        plan["groups"][0]["visual"][0]["operation"] = []
        errors, _ = VALIDATOR.validate_plan(plan)
        self.assertTrue(errors)

        plan = valid_plan()
        plan["groups"][0]["audio"] = {"action": {}}
        errors, _ = VALIDATOR.validate_plan(plan)
        self.assertTrue(errors)

    def test_clone_template_requires_preset_and_target_locator(self) -> None:
        plan = valid_plan()
        visual = plan["groups"][0]["visual"][0]
        del visual["preset_id"]
        del visual["target_locator"]
        errors, _ = VALIDATOR.validate_plan(plan)
        self.assertTrue(any("preset_id: required" in error for error in errors))
        self.assertTrue(any("target_locator" in error for error in errors))

    def test_apply_fails_closed_for_unsafe_defaults(self) -> None:
        plan = valid_plan()
        plan["execution"]["mode"] = "apply"
        plan["groups"][0]["status"] = "approved"
        plan["target"]["clone_source"] = False
        plan["execution"]["preserve_source"] = False
        plan["execution"]["preserve_manual_edits"] = False
        self.assert_error_contains(plan, "allow_in_place")
        self.assert_error_contains(plan, "preserve_manual_edits")

    def test_explicit_safety_exception_requires_authorization_note(self) -> None:
        plan = valid_plan()
        plan["execution"]["mode"] = "apply"
        plan["groups"][0]["status"] = "approved"
        plan["target"]["clone_source"] = False
        plan["execution"]["preserve_source"] = False
        plan["execution"]["allow_in_place"] = True
        errors, _ = VALIDATOR.validate_plan(plan)
        self.assertTrue(any("authorization_note" in error for error in errors))

        plan["execution"]["authorization_note"] = "User explicitly requested in-place packaging."
        errors, _ = VALIDATOR.validate_plan(plan)
        self.assertEqual(errors, [])

    def test_animation_audio_anchor_requires_motion_event(self) -> None:
        plan = valid_plan()
        group = plan["groups"][0]
        group["motion_event"] = None
        group["audio"] = {
            "action": "reuse_existing",
            "asset_id": "prompt-asset",
            "sound_family": "prompt",
            "motion_family": "reveal",
            "selection_basis": "motion family plus spoken question",
            "reuse_count": 1,
            "target_locator": {"timeline": "target", "segment_id": "sound"},
            "sync": {"anchor": "animation_peak"},
            "reason": "The prompt lands with the reveal.",
        }
        self.assert_error_contains(plan, "requires a valid motion_event")

    def test_override_must_be_allowed_by_preset(self) -> None:
        plan = valid_plan()
        plan["groups"][0]["visual"][0]["overrides"]["rotation"] = {
            "mode": "absolute",
            "value": 10,
        }
        self.assert_error_contains(plan, "not listed in preset")

    def test_copy_is_not_mutated_by_validation(self) -> None:
        plan = valid_plan()
        before = copy.deepcopy(plan)
        VALIDATOR.validate_plan(plan)
        self.assertEqual(plan, before)

    def test_final_plan_requires_approved_staging(self) -> None:
        plan = valid_plan()
        plan["staging"]["review_status"] = "reviewing"
        self.assert_error_contains(plan, "staging.review_status=approved")

    def test_staging_phase_rejects_sound_and_template_application(self) -> None:
        plan = valid_plan()
        plan["execution"]["phase"] = "staging"
        plan["staging"]["review_status"] = "reviewing"
        errors, _ = VALIDATOR.validate_plan(plan)
        self.assertTrue(any("staging phase only permits" in error for error in errors))

        plan = valid_plan()
        plan["execution"]["phase"] = "staging"
        plan["staging"]["review_status"] = "reviewing"
        plan["groups"][0]["visual"][0]["operation"] = "copy_from_subtitle"
        plan["groups"][0]["visual"][0]["source_locator"] = {
            "timeline": "source", "segment_id": "subtitle-segment"
        }
        plan["groups"][0]["audio"] = {
            "action": "reuse_existing",
            "asset_id": "sound",
            "sound_family": "prompt",
            "motion_family": "reveal",
            "selection_basis": "question emphasis",
            "reuse_count": 1,
            "target_locator": {"timeline": "target", "segment_id": "sound"},
            "sync": {"anchor": "animation_peak"},
            "reason": "staging must not add audio",
        }
        errors, _ = VALIDATOR.validate_plan(plan)
        self.assertTrue(any("staging phase must not add sound" in error for error in errors))

    def test_light_content_operation_requires_semantic_preservation(self) -> None:
        plan = valid_plan()
        plan["light_content_ops"] = [{
            "operation": "display_shorten",
            "semantic_preserved": False,
            "review_status": "approved",
            "target_locator": {"timeline": "target", "segment_id": "subtitle"},
        }]
        self.assert_error_contains(plan, "semantic_preserved")

    def test_sound_reuse_cap_is_enforced(self) -> None:
        plan = valid_plan()
        plan["sound_selection"]["reuse_cap"] = 1
        plan["groups"][0]["audio"] = {
            "action": "reuse_existing",
            "asset_id": "same-sound",
            "sound_family": "prompt",
            "motion_family": "reveal",
            "selection_basis": "question emphasis",
            "reuse_count": 2,
            "target_locator": {"timeline": "target", "segment_id": "sound"},
            "sync": {"anchor": "animation_peak"},
            "reason": "test",
        }
        self.assert_error_contains(plan, "exceeds configured reuse cap")

    def test_legacy_schema_is_review_only(self) -> None:
        plan = valid_plan()
        plan["schema_version"] = "1.0"
        plan["execution"]["phase"] = None
        errors, warnings = VALIDATOR.validate_plan(plan)
        self.assertEqual(errors, [])
        self.assertTrue(any("legacy" in warning for warning in warnings))
        plan["execution"]["mode"] = "apply"
        plan["groups"][0]["status"] = "approved"
        self.assert_error_contains(plan, "must be migrated before apply")


if __name__ == "__main__":
    unittest.main()
