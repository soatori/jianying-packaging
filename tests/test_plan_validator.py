#!/usr/bin/env python3
"""Regression tests for the packaging plan validator module."""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "packaging_tools" / "validators" / "plan_impl.py"
SPEC = importlib.util.spec_from_file_location("validate_packaging_plan", SCRIPT)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - environment failure
    raise RuntimeError(f"cannot load {SCRIPT}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def valid_plan() -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "source": {
            "draft_path": "<synthetic-draft>",
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


def valid_plan_v12() -> dict[str, Any]:
    plan = valid_plan()
    plan["schema_version"] = "1.2"
    for key in (
        "staging",
        "duplicate_policy",
        "template_health",
        "sound_selection",
        "light_content_ops",
        "visual_capability_requirements",
    ):
        plan.pop(key, None)
    plan["staging"] = {
        "required": True,
        "mode": "copy_to_upper_review_track",
        "source_timeline": "manual",
        "target_timeline": "packaged",
        "review_status": "approved",
        "original_subtitles": "preserve",
    }
    plan["source"]["final_subtitle_reference"] = {
        "id": "subtitle-ref",
        "hash": "sha256:subtitle",
        "status": "approved",
    }
    plan["source"]["final_subtitle_units"] = [
        {
            "unit_id": "U1",
            "text_hash": VALIDATOR.sha256_text("Synthetic Q"),
            "status": "approved",
        },
        {
            "unit_id": "U2",
            "text_hash": VALIDATOR.sha256_text("Synthetic A"),
            "status": "approved",
        },
    ]
    plan["comparison"] = {
        "source_order_hash": "sha256:source",
        "target_order_hash": "sha256:target",
        "remap_status": "verified",
    }
    plan["execution"].update({
        "clone_source": True,
        "pre_write_backup": "required",
        "context_contract": {
            "anchor_policy": "runtime_final_subtitle_x0_y0",
            "layout_policy": "group_atomic_relative",
            "sound_policy": "catalog_candidate_single",
            "readback_required": True,
            "stop_conditions": [
                "pending_remap",
                "text_mismatch",
                "layout_collision",
                "unverified_sound",
                "leading_silence_unresolved",
                "missing_backup",
            ],
        },
    })
    group = plan["groups"][0]
    group.update({
        "status": "review",
        "semantic_unit_refs": ["U1", "U2"],
        "auxiliary_text_refs": [],
        "subtitle_anchor": {
            "unit_id": "U1",
            "text_hash": VALIDATOR.sha256_text("Synthetic Q"),
            "text_authority": "final_visible_subtitle",
        },
        "remap_status": "verified",
        "source_order_hash": "sha256:source",
        "target_order_hash": "sha256:target",
        "layout": {
            "template_id": "center_stack",
            "template_version": 1,
            "position_mode": "relative_template",
            "anchor": {"type": "runtime_reference", "x": "X0", "y": "Y0"},
            "slots": [
                {"id": "main", "ref_type": "subtitle_unit", "text_ref": "U1", "offset": {"dx": 0.0, "dy": 0.0}},
                {"id": "secondary", "ref_type": "subtitle_unit", "text_ref": "U2", "relative_to": "main", "offset": {"dx": 0.0, "dy": 0.1}, "inherit_transform_from": "main"},
            ],
            "constraints": {"safe_zone": "project_safe_zone", "collision": "block"},
            "fallback": "manual_review",
        },
        "sound_selection_basis": "generic motion and spoken function",
    })
    group["visual"][0].update({
        "text": "Synthetic Q",
        "text_ref": "U1",
        "text_hash": VALIDATOR.sha256_text("Synthetic Q"),
    })
    group["audio"] = {
        "action": "reuse_existing",
        "asset_id": "synthetic-sound",
        "catalog_ref": "synthetic-preset",
        "candidate_pool_ref": "synthetic-pool",
        "selected_preset_id": "synthetic-preset",
        "sound_form": "single_hit",
        "trim_policy": "text_span",
        "leading_silence_policy": "skip",
        "leading_silence_us": 0,
        "text_range": {"start_us": 1000, "duration_us": 3000},
        "motion_family": "reveal",
        "sound_family": "prompt",
        "selection_basis": "generic motion and spoken function",
        "reuse_count": 1,
        "target_locator": {"timeline": "target", "segment_id": "sound"},
        "target_range": {"start_us": 1000, "duration_us": 3000},
        "sync": {"anchor": "animation_peak"},
        "reason": "One restrained sound supports the visual landing.",
    }
    return plan


def synthetic_sound_catalog() -> dict[str, Any]:
    return {
        "presets": [
            {
                "preset_id": f"synthetic-preset{suffix}",
                "display_name": "Synthetic sound",
                "duration_us": 500000,
                "leading_silence_us": 0,
                "tail_duration_us": 100000,
                "sound_form": "single_hit",
                "default_trim_policy": "text_span",
                "leading_silence_policy": "skip",
                "status": "verified",
                "evidence": ["synthetic-test"],
                "last_verified": "synthetic",
            }
            for suffix in ("", "-2", "-3")
        ]
    }


def synthetic_sound_pools() -> dict[str, Any]:
    return {
        "pools": [{
            "pool_id": "synthetic-pool",
            "motion_family": "reveal",
            "min_candidates": 3,
            "status": "verified",
            "candidates": [
                {"preset_id": "synthetic-preset", "rank": 1, "sound_form": "single_hit", "status": "verified"},
                {"preset_id": "synthetic-preset-2", "rank": 2, "sound_form": "single_hit", "status": "verified"},
                {"preset_id": "synthetic-preset-3", "rank": 3, "sound_form": "single_hit", "status": "verified"},
            ],
        }]
    }


def validate_for_test(plan: dict[str, Any]) -> tuple[list[str], list[str]]:
    if plan.get("schema_version") == "1.2":
        return VALIDATOR.validate_plan(
            plan,
            sound_catalog=synthetic_sound_catalog(),
            sound_pools=synthetic_sound_pools(),
        )
    return VALIDATOR.validate_plan(plan)


class ValidatePackagingPlanTests(unittest.TestCase):
    def assert_error_contains(self, plan: dict[str, Any], fragment: str) -> None:
        errors, _ = validate_for_test(plan)
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
        errors, _ = validate_for_test(plan)
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
        plan = valid_plan_v12()
        plan["execution"]["mode"] = "apply"
        plan["groups"][0]["status"] = "approved"
        plan["target"]["clone_source"] = False
        plan["execution"]["preserve_source"] = False
        plan["execution"]["allow_in_place"] = True
        errors, _ = validate_for_test(plan)
        self.assertTrue(any("authorization_note" in error for error in errors))

        plan["execution"]["authorization_note"] = "User explicitly requested in-place packaging."
        errors, _ = validate_for_test(plan)
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

    def test_schema_11_apply_is_migration_only(self) -> None:
        plan = valid_plan()
        plan["execution"]["mode"] = "apply"
        plan["groups"][0]["status"] = "approved"
        self.assert_error_contains(plan, "schema_version 1.1")

    def test_tolerance_may_override_default(self) -> None:
        plan = valid_plan()
        plan["duplicate_policy"]["start_tolerance_us"] = 25_000
        errors, _ = VALIDATOR.validate_plan(plan)
        self.assertEqual(errors, [])

    def test_selection_order_accepts_nonempty_known_keys(self) -> None:
        plan = valid_plan()
        plan["sound_selection"]["selection_order"] = ["sound_family", "motion_family"]
        errors, _ = validate_for_test(plan)
        self.assertEqual(errors, [])

    def test_valid_schema_12_plan(self) -> None:
        errors, warnings = validate_for_test(valid_plan_v12())
        self.assertEqual(errors, [], warnings)

    def test_schema_12_reads_legacy_visual_alias_but_blocks_conflict(self) -> None:
        plan = valid_plan_v12()
        plan["groups"][0]["visuals"] = plan["groups"][0].pop("visual")
        errors, _ = validate_for_test(plan)
        self.assertEqual(errors, [])
        plan = valid_plan_v12()
        plan["groups"][0]["visuals"] = [{"operation": "none"}]
        errors, _ = validate_for_test(plan)
        self.assertTrue(any("visual aliases disagree" in error for error in errors))

    def test_schema_12_is_independent_of_legacy_contract(self) -> None:
        plan = valid_plan_v12()
        self.assertNotIn("duplicate_policy", plan)
        errors, _ = validate_for_test(plan)
        self.assertEqual(errors, [])

    def test_schema_12_requires_context_contract(self) -> None:
        plan = valid_plan_v12()
        del plan["execution"]["context_contract"]
        self.assert_error_contains(plan, "context_contract")

    def test_slot_reference_must_belong_to_group(self) -> None:
        plan = valid_plan_v12()
        plan["groups"][0]["layout"]["slots"][1]["text_ref"] = "undeclared-unit"
        self.assert_error_contains(plan, "declared semantic_unit_ref")

    def test_auxiliary_mark_reference_is_allowed_when_declared(self) -> None:
        plan = valid_plan_v12()
        group = plan["groups"][0]
        group["auxiliary_text_refs"] = ["mark-1"]
        group["layout"]["slots"][1] = {
            "id": "mark",
            "ref_type": "auxiliary_mark",
            "text_ref": "mark-1",
            "relative_to": "main",
            "offset": {"dx": 0.2, "dy": 0.0},
            "inherit_transform_from": "main",
        }
        group["layout"]["slots"] = [group["layout"]["slots"][0], group["layout"]["slots"][1]]
        errors, _ = validate_for_test(plan)
        self.assertEqual(errors, [])

    def test_layout_registry_version_is_required(self) -> None:
        plan = valid_plan_v12()
        plan["groups"][0]["layout"]["template_id"] = "missing-template"
        self.assert_error_contains(plan, "not found in layout registry")

    def test_text_span_target_range_must_match_text_range(self) -> None:
        plan = valid_plan_v12()
        plan["groups"][0]["audio"]["target_range"]["duration_us"] = 1000
        self.assert_error_contains(plan, "must equal text_range")

    def test_motion_span_target_range_must_match_motion_event(self) -> None:
        plan = valid_plan_v12()
        audio = plan["groups"][0]["audio"]
        audio["sound_form"] = "multi_hit"
        audio["trim_policy"] = "motion_span"
        audio["text_range"] = {"start_us": 1000, "duration_us": 3000}
        audio["target_range"] = {"start_us": 1000, "duration_us": 500}
        self.assert_error_contains(plan, "must equal motion_event")

    def test_known_leading_silence_requires_source_range(self) -> None:
        plan = valid_plan_v12()
        audio = plan["groups"][0]["audio"]
        audio["leading_silence_us"] = 200
        audio.pop("source_range", None)
        self.assert_error_contains(plan, "source_range: required when leading silence is known")

    def test_apply_requires_formal_sound_pool_not_inline_pool(self) -> None:
        plan = valid_plan_v12()
        plan["execution"]["mode"] = "apply"
        plan["groups"][0]["status"] = "approved"
        plan["groups"][0]["audio"]["candidate_pool"] = [
            {"preset_id": "synthetic-preset", "status": "verified"},
            {"preset_id": "synthetic-preset-2", "status": "verified"},
            {"preset_id": "synthetic-preset-3", "status": "verified"},
        ]
        self.assert_error_contains(plan, "inline candidate pools are review-only")

    def test_final_review_requires_formal_sound_pool_not_inline_pool(self) -> None:
        plan = valid_plan_v12()
        plan["execution"]["phase"] = "final"
        plan["groups"][0]["audio"]["candidate_pool"] = [
            {"preset_id": "synthetic-preset", "status": "verified"},
            {"preset_id": "synthetic-preset-2", "status": "verified"},
            {"preset_id": "synthetic-preset-3", "status": "verified"},
        ]
        self.assert_error_contains(plan, "inline candidate pools are review-only")

    def test_apply_requires_catalog_membership(self) -> None:
        plan = valid_plan_v12()
        plan["execution"]["mode"] = "apply"
        plan["groups"][0]["status"] = "approved"
        plan["groups"][0]["audio"]["selected_preset_id"] = "missing-preset"
        plan["groups"][0]["audio"]["catalog_ref"] = "missing-preset"
        self.assert_error_contains(plan, "absent from the sound catalog")

    def test_apply_rejects_unresolved_sound_policies(self) -> None:
        plan = valid_plan_v12()
        plan["execution"]["mode"] = "apply"
        plan["groups"][0]["status"] = "approved"
        plan["groups"][0]["audio"]["trim_policy"] = "manual_review"
        self.assert_error_contains(plan, "manual review is unresolved")

    def test_schema_12_requires_final_subtitle_reference(self) -> None:
        plan = valid_plan_v12()
        del plan["source"]["final_subtitle_reference"]
        self.assert_error_contains(plan, "final_subtitle_reference")

    def test_schema_12_requires_final_subtitle_units(self) -> None:
        plan = valid_plan_v12()
        del plan["source"]["final_subtitle_units"]
        self.assert_error_contains(plan, "final_subtitle_units")

    def test_schema_12_rejects_stale_visual_text(self) -> None:
        plan = valid_plan_v12()
        plan["groups"][0]["visual"][0]["text"] = "stale flower text"
        self.assert_error_contains(plan, "text_mismatch")

    def test_schema_12_rejects_mismatched_subtitle_anchor_hash(self) -> None:
        plan = valid_plan_v12()
        plan["groups"][0]["subtitle_anchor"]["text_hash"] = "sha256:stale"
        self.assert_error_contains(plan, "subtitle_anchor: text_mismatch")

    def test_schema_12_final_requires_verified_remap(self) -> None:
        plan = valid_plan_v12()
        plan["comparison"]["remap_status"] = "pending"
        self.assert_error_contains(plan, "remap_status")

    def test_schema_12_groups_require_order_fingerprints(self) -> None:
        plan = valid_plan_v12()
        del plan["groups"][0]["source_order_hash"]
        self.assert_error_contains(plan, "groups[0].source_order_hash")

    def test_layout_unknown_reference_is_rejected(self) -> None:
        plan = valid_plan_v12()
        plan["groups"][0]["layout"]["slots"][1]["relative_to"] = "missing-slot"
        self.assert_error_contains(plan, "unknown slot")

    def test_layout_cycle_is_rejected(self) -> None:
        plan = valid_plan_v12()
        plan["groups"][0]["layout"]["slots"][0]["relative_to"] = "secondary"
        self.assert_error_contains(plan, "cycles")

    def test_incomplete_sound_pool_blocks_apply(self) -> None:
        plan = valid_plan_v12()
        plan["execution"]["mode"] = "apply"
        plan["groups"][0]["status"] = "approved"
        plan["groups"][0]["audio"]["candidate_pool"] = [
            {"preset_id": "synthetic-preset", "status": "verified"},
        ]
        self.assert_error_contains(plan, "candidate_pool_incomplete")

    def test_leading_silence_must_be_skipped(self) -> None:
        plan = valid_plan_v12()
        plan["groups"][0]["audio"]["leading_silence_us"] = 200
        plan["groups"][0]["audio"]["source_range"] = {"start_us": 0, "duration_us": 500}
        self.assert_error_contains(plan, "leading silence")

    def test_sound_form_trim_mismatch_requires_reason(self) -> None:
        plan = valid_plan_v12()
        audio = plan["groups"][0]["audio"]
        audio["sound_form"] = "single_hit"
        audio["trim_policy"] = "motion_span"
        audio.pop("override_reason", None)
        self.assert_error_contains(plan, "override_reason")


if __name__ == "__main__":
    unittest.main()
