#!/usr/bin/env python3
"""Validate a Jianying semantic packaging plan without touching a draft."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


CATEGORIES = {
    "question", "core_point", "number_parameter", "product_brand",
    "technical_term", "risk_warning", "conclusion", "contrast_turn",
    "emotion", "cta", "transition", "ordinary_explanation",
}
STATUSES = {"approved", "review", "skip"}
VISUAL_OPERATIONS = {
    "clone_template", "copy_from_subtitle", "modify_text", "modify_segment",
    "add_overlay", "disable_original", "none",
}
OBJECT_TYPES = {"text", "video", "image", "png", "sticker"}
AUDIO_ACTIONS = {"none", "reuse_existing", "clone_asset", "add_asset"}
SYNC_ANCHORS = {
    "group_start", "phrase_start", "animation_start", "animation_peak",
    "transition_peak", "custom",
}
MOTIONS = {
    "pop", "reveal", "typing", "sweep", "impact", "mechanical_open",
    "warning_pulse", "confirmation", "none", "custom",
}
SUPPORTED_SCHEMA_VERSIONS = {"1.0", "1.1"}
PACKAGING_PHASES = {"staging", "final"}
STAGING_REVIEW_STATUSES = {"pending", "reviewing", "approved"}
COVERED_SUBTITLE_POLICIES = {
    "preserve", "disable_after_readback", "delete_on_clone_after_approval", "review",
    # Legacy values remain readable so old plans can be migrated safely.
    "disable", "keep", "delete",
}
LIGHT_CONTENT_OPERATIONS = {
    "display_shorten", "line_break", "punctuation", "emphasis_range", "cover_relation",
}
TEMPLATE_HEALTH_STATUSES = {"verified", "fallback", "blocked"}
CAPABILITY_EVIDENCE_STATUS = {"demonstrated", "experimental", "unsupported"}

NEW_OBJECT_VISUAL_OPERATIONS = {
    "clone_template", "copy_from_subtitle", "add_overlay",
}
EXISTING_SEGMENT_VISUAL_OPERATIONS = {
    "modify_text", "modify_segment", "disable_original",
}
SOURCE_SEGMENT_VISUAL_OPERATIONS = {"copy_from_subtitle"}
SOURCE_ASSET_VISUAL_OPERATIONS = {"add_overlay"}
ANIMATION_ANCHORS = {"animation_start", "animation_peak", "animation_end"}
TIME_FIELDS = {
    "phrase_start_us", "start_us", "duration_us", "end_us",
    "animation_start_us", "animation_peak_us", "animation_end_us",
}
LOCATOR_IDENTIFIER_FIELDS = (
    "track_id", "track_type", "segment_id", "material_id", "asset_id",
)


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_string_list(
    path: str,
    value: Any,
    errors: list[str],
    *,
    require_nonempty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{path}: must be an array of non-empty strings")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not is_nonempty_string(item):
            errors.append(f"{path}[{index}]: must be a non-empty string")
        else:
            result.append(item)
    if require_nonempty and not result:
        errors.append(f"{path}: must contain at least one non-empty string")
    return result


def validate_override(path: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: override must be an object with explicit mode")
        return
    mode = value.get("mode")
    if mode == "absolute":
        if "value" not in value or value.get("value") is None or "delta" in value:
            errors.append(f"{path}: absolute override requires a non-null value and forbids delta")
    elif mode == "relative":
        if "delta" not in value or "value" in value:
            errors.append(f"{path}: relative override requires delta and forbids value")
        elif not is_number(value.get("delta")):
            errors.append(f"{path}.delta: relative delta must be numeric")
    else:
        errors.append(f"{path}: mode must be absolute or relative")


def validate_timerange(
    path: str,
    value: Any,
    errors: list[str],
) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: required object")
        return None
    start = value.get("start_us")
    duration = value.get("duration_us")
    valid = True
    if not is_int(start) or start < 0:
        errors.append(f"{path}.start_us: must be a non-negative integer")
        valid = False
    if not is_int(duration) or duration <= 0:
        errors.append(f"{path}.duration_us: must be a positive integer")
        valid = False
    if not valid:
        return None
    end = start + duration
    if "end_us" in value:
        end_value = value.get("end_us")
        if not is_int(end_value):
            errors.append(f"{path}.end_us: must be an integer")
        elif end_value != end:
            errors.append(f"{path}.end_us: must equal start_us + duration_us")
    return start, end


def validate_motion_event(
    path: str,
    value: Any,
    errors: list[str],
) -> dict[str, int] | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: required object")
        return None
    event: dict[str, int] = {}
    valid = True
    for field in ("start_us", "peak_us", "end_us"):
        field_value = value.get(field)
        if not is_int(field_value) or field_value < 0:
            errors.append(f"{path}.{field}: must be a non-negative integer")
            valid = False
        else:
            event[field] = field_value
    if valid and not (event["start_us"] <= event["peak_us"] <= event["end_us"]):
        errors.append(f"{path}: start_us, peak_us, and end_us must be ordered")
        valid = False
    return event if valid else None


def validate_locator(
    path: str,
    value: Any,
    errors: list[str],
    *,
    require_segment: bool = False,
    require_track: bool = False,
    require_asset: bool = False,
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{path}: required locator object")
        return False

    valid = True
    if not is_nonempty_string(value.get("timeline")):
        errors.append(f"{path}.timeline: required non-empty string")
        valid = False

    for field in LOCATOR_IDENTIFIER_FIELDS + ("draft_path",):
        if field in value and not is_nonempty_string(value.get(field)):
            errors.append(f"{path}.{field}: must be a non-empty string")
            valid = False

    if not any(is_nonempty_string(value.get(field)) for field in LOCATOR_IDENTIFIER_FIELDS):
        errors.append(
            f"{path}: must identify a track, segment, material, or asset"
        )
        valid = False
    if require_segment and not is_nonempty_string(value.get("segment_id")):
        errors.append(f"{path}.segment_id: required for an existing segment target")
        valid = False
    if require_track and not (
        is_nonempty_string(value.get("track_id"))
        or is_nonempty_string(value.get("track_type"))
    ):
        errors.append(f"{path}: requires track_id or explicit track_type")
        valid = False
    if require_asset and not any(
        is_nonempty_string(value.get(field))
        for field in ("segment_id", "material_id", "asset_id")
    ):
        errors.append(f"{path}: requires segment_id, material_id, or asset_id")
        valid = False
    return valid


def locator_key(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for field in ("asset_id", "material_id", "segment_id", "track_id"):
        field_value = value.get(field)
        if is_nonempty_string(field_value):
            return f"{field}:{field_value}"
    return None


def validate_optional_nonnegative_int(
    path: str,
    container: dict[str, Any],
    field: str,
    errors: list[str],
) -> None:
    if field not in container:
        return
    value = container.get(field)
    if not is_int(value) or value < 0:
        errors.append(f"{path}.{field}: must be a non-negative integer")


def register_track_interval(
    path: str,
    locator: Any,
    start_end: tuple[int, int] | None,
    intervals: dict[str, list[tuple[int, int, str]]],
    warnings: list[str],
) -> None:
    if start_end is None or not isinstance(locator, dict):
        return
    track_id = locator.get("track_id")
    if not is_nonempty_string(track_id):
        return
    start, end = start_end
    for old_start, old_end, old_path in intervals.get(track_id, []):
        if start < old_end and old_start < end:
            warnings.append(
                f"{path}: overlaps {old_path} on target track {track_id!r}; verify track/layer intent"
            )
    intervals.setdefault(track_id, []).append((start, end, path))


def validate_reference_status(path: str, value: Any, errors: list[str], *, required: bool) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, dict):
        errors.append(f"{path}: required object")
        return None
    for field in ("id", "hash"):
        if not is_nonempty_string(value.get(field)):
            errors.append(f"{path}.{field}: required non-empty string")
    status = value.get("status")
    if status not in {"stable", "approved"}:
        errors.append(f"{path}.status: must be stable or approved")
    return status if isinstance(status, str) else None


def validate_v11_contract(data: dict[str, Any], errors: list[str], warnings: list[str]) -> tuple[str | None, int]:
    source = data.get("source")
    content_status: str | None = None
    alignment_status: str | None = None
    if not isinstance(source, dict):
        return None, 3
    content_status = source.get("content_pass")
    if content_status not in {"stable", "approved"}:
        errors.append("source.content_pass: must be stable or approved")
    alignment_status = validate_reference_status(
        "source.subtitle_alignment", source.get("subtitle_alignment"), errors, required=True
    )

    staging = data.get("staging")
    if not isinstance(staging, dict):
        errors.append("staging: required object for schema 1.1")
    else:
        if staging.get("required") is not True:
            errors.append("staging.required: must be true for schema 1.1")
        if staging.get("mode") != "copy_to_upper_review_track":
            errors.append("staging.mode: must be copy_to_upper_review_track")
        for field in ("source_timeline", "target_timeline"):
            if not is_nonempty_string(staging.get(field)):
                errors.append(f"staging.{field}: required non-empty string")
        if staging.get("review_status") not in STAGING_REVIEW_STATUSES:
            errors.append("staging.review_status: invalid")
        if staging.get("original_subtitles") != "preserve":
            errors.append("staging.original_subtitles: must be preserve")

    duplicate = data.get("duplicate_policy")
    if not isinstance(duplicate, dict):
        errors.append("duplicate_policy: required object for schema 1.1")
    else:
        tolerance = duplicate.get("start_tolerance_us")
        if not is_int(tolerance) or tolerance <= 0:
            errors.append("duplicate_policy.start_tolerance_us: must be positive integer")
        # default is 40000us; any positive integer override is allowed
        if duplicate.get("text_must_match") is not False:
            errors.append("duplicate_policy.text_must_match: must be false")
        if duplicate.get("cross_track") not in {"cover_or_delete_target", "preserve", "review"}:
            errors.append("duplicate_policy.cross_track: invalid")
        if duplicate.get("same_track") != "preserve_continuation":
            errors.append("duplicate_policy.same_track: must be preserve_continuation")

    template_health = data.get("template_health")
    if not isinstance(template_health, list):
        errors.append("template_health: required array for schema 1.1")
    else:
        for index, item in enumerate(template_health):
            path = f"template_health[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{path}: must be an object")
                continue
            if not is_nonempty_string(item.get("preset_id")):
                errors.append(f"{path}.preset_id: required")
            status = item.get("status")
            if status not in TEMPLATE_HEALTH_STATUSES:
                errors.append(f"{path}.status: invalid")
            if status in {"verified", "fallback"} and not is_nonempty_string(item.get("font_source")):
                errors.append(f"{path}.font_source: required for a usable template")
            if status == "blocked" and item.get("visual_verification") is not False:
                warnings.append(f"{path}: blocked template must not be applied")

    sound_selection = data.get("sound_selection")
    reuse_cap = 3
    if not isinstance(sound_selection, dict):
        errors.append("sound_selection: required object for schema 1.1")
    else:
        reuse_cap = sound_selection.get("reuse_cap", 3)
        if not is_int(reuse_cap) or reuse_cap <= 0:
            errors.append("sound_selection.reuse_cap: must be a positive integer")
            reuse_cap = 3
        order = sound_selection.get("selection_order")
        if not isinstance(order, list) or not order:
            errors.append("sound_selection.selection_order: must be a non-empty array")
        else:
            allowed = {"motion_family", "sound_family", "reuse_cap", "semantic_special_slot"}
            if any((not isinstance(key, str)) or key not in allowed for key in order):
                errors.append("sound_selection.selection_order: unknown selection key")

    light_ops = data.get("light_content_ops")
    if not isinstance(light_ops, list):
        errors.append("light_content_ops: required array for schema 1.1")
    else:
        for index, item in enumerate(light_ops):
            path = f"light_content_ops[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{path}: must be an object")
                continue
            if item.get("operation") not in LIGHT_CONTENT_OPERATIONS:
                errors.append(f"{path}.operation: unsupported light-content operation")
            if not isinstance(item.get("semantic_preserved"), bool) or item.get("semantic_preserved") is not True:
                errors.append(f"{path}.semantic_preserved: must be true")
            if not is_nonempty_string(item.get("review_status")) or item.get("review_status") not in {"pending", "approved"}:
                errors.append(f"{path}.review_status: must be pending or approved")
            validate_locator(path + ".target_locator", item.get("target_locator"), errors, require_segment=True)

    capabilities = data.get("visual_capability_requirements")
    if not isinstance(capabilities, list):
        errors.append("visual_capability_requirements: required array for schema 1.1")
    else:
        for index, item in enumerate(capabilities):
            path = f"visual_capability_requirements[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{path}: must be an object")
                continue
            if not is_nonempty_string(item.get("capability")):
                errors.append(f"{path}.capability: required")
            evidence_status = item.get("evidence_status")
            if evidence_status not in CAPABILITY_EVIDENCE_STATUS:
                errors.append(f"{path}.evidence_status: invalid")
            if evidence_status in {"experimental", "unsupported"} and item.get("visual_verification") is not True:
                errors.append(f"{path}.visual_verification: required for experimental/unsupported capability")

    return alignment_status, reuse_cap


def validate_plan(data: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["root: plan must be a JSON object"], warnings

    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append("schema_version: expected '1.0' or '1.1'")
    is_v11 = schema_version == "1.1"
    if schema_version == "1.0":
        warnings.append("schema_version 1.0 is legacy; migrate to 1.1 before apply")

    alignment_status: str | None = None
    reuse_cap = 3
    if is_v11:
        alignment_status, reuse_cap = validate_v11_contract(data, errors, warnings)

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source: required object")
    else:
        for field in ("draft_path", "timeline"):
            if not is_nonempty_string(source.get(field)):
                errors.append(f"source.{field}: required non-empty string")

    target = data.get("target")
    target_clone_source: Any = None
    if not isinstance(target, dict):
        errors.append("target: required object")
    else:
        if not is_nonempty_string(target.get("timeline_name")):
            errors.append("target.timeline_name: required non-empty string")
        target_clone_source = target.get("clone_source")
        if "clone_source" in target and not isinstance(target_clone_source, bool):
            errors.append("target.clone_source: must be boolean")
        elif target_clone_source is not True:
            warnings.append(
                "target.clone_source: false or missing; in-place mutation needs explicit user intent"
            )

    execution = data.get("execution")
    mode: str | None = None
    phase: str | None = None
    allow_in_place = False
    allow_manual_overwrite = False
    preserve_source: Any = None
    preserve_manual_edits: Any = None
    if not isinstance(execution, dict):
        errors.append("execution: required object")
    else:
        mode_value = execution.get("mode")
        if not isinstance(mode_value, str) or mode_value not in {"review", "apply"}:
            errors.append("execution.mode: must be review or apply")
        else:
            mode = mode_value

        for field in (
            "preserve_source", "preserve_manual_edits", "allow_in_place",
            "allow_manual_overwrite",
        ):
            if field in execution and not isinstance(execution.get(field), bool):
                errors.append(f"execution.{field}: must be boolean")

        preserve_source = execution.get("preserve_source")
        preserve_manual_edits = execution.get("preserve_manual_edits")
        allow_in_place = execution.get("allow_in_place") is True
        allow_manual_overwrite = execution.get("allow_manual_overwrite") is True
        authorization_note = execution.get("authorization_note")
        if (allow_in_place or allow_manual_overwrite) and not is_nonempty_string(authorization_note):
            errors.append(
                "execution.authorization_note: required when an apply safety exception is enabled"
            )
        if "authorization_note" in execution and authorization_note is not None and not is_nonempty_string(authorization_note):
            errors.append("execution.authorization_note: must be a non-empty string")

        if not isinstance(preserve_source, bool) or preserve_source is not True:
            warnings.append("execution.preserve_source: false or missing")
        if not isinstance(preserve_manual_edits, bool) or preserve_manual_edits is not True:
            warnings.append("execution.preserve_manual_edits: false or missing")

        covered_policy = execution.get("covered_subtitle_policy")
        if not isinstance(covered_policy, str) or covered_policy not in COVERED_SUBTITLE_POLICIES:
            errors.append(
                "execution.covered_subtitle_policy: unsupported policy"
            )
        elif covered_policy in {"disable", "delete"}:
            warnings.append("execution.covered_subtitle_policy: legacy policy; prefer preserve or clone-only policy")
        if is_v11 and covered_policy in {"disable", "keep", "delete"}:
            errors.append("execution.covered_subtitle_policy: legacy value is not allowed in schema 1.1")

        phase = execution.get("phase", "final" if not is_v11 else None)
        if is_v11 and phase not in PACKAGING_PHASES:
            errors.append("execution.phase: must be staging or final")
        if is_v11 and phase == "final":
            staging = data.get("staging")
            if isinstance(staging, dict) and staging.get("review_status") != "approved":
                errors.append("execution.phase=final requires staging.review_status=approved")
            if alignment_status != "approved":
                errors.append("execution.phase=final requires approved subtitle alignment")
        if is_v11 and phase == "staging" and covered_policy not in {"preserve", "review"}:
            errors.append("staging phase may only preserve or review covered subtitles")
        if is_v11 and covered_policy == "delete_on_clone_after_approval":
            staging = data.get("staging")
            if not isinstance(staging, dict) or staging.get("review_status") != "approved":
                errors.append("delete_on_clone_after_approval requires approved staging review")
        if is_v11 and covered_policy == "disable_after_readback" and mode == "apply":
            warnings.append("disable_after_readback requires visual read-back; it is not a success condition by itself")

        if mode == "apply":
            if schema_version == "1.0":
                errors.append("schema_version 1.0 must be migrated before apply")
            if target_clone_source is not True and not allow_in_place:
                errors.append(
                    "apply requires target.clone_source=true unless allow_in_place is explicitly authorized"
                )
            if preserve_source is not True and not allow_in_place:
                errors.append(
                    "apply requires execution.preserve_source=true unless allow_in_place is explicitly authorized"
                )
            if preserve_manual_edits is not True and not allow_manual_overwrite:
                errors.append(
                    "apply requires execution.preserve_manual_edits=true unless manual overwrite is explicitly authorized"
                )

    profile = data.get("project_profile", {})
    if not isinstance(profile, dict):
        errors.append("project_profile: must be an object")
        profile = {}
    for field in ("canvas_width", "canvas_height"):
        if field in profile and (not is_int(profile.get(field)) or profile[field] <= 0):
            errors.append(f"project_profile.{field}: must be a positive integer")
    max_chars = profile.get("max_chars_per_line", 13)
    if not is_int(max_chars) or max_chars <= 0:
        errors.append("project_profile.max_chars_per_line: must be a positive integer")
        max_chars = 13

    presets = data.get("presets", [])
    if not isinstance(presets, list):
        errors.append("presets: must be an array")
        presets = []
    preset_ids: set[str] = set()
    preset_allowed_overrides: dict[str, set[str]] = {}
    for index, preset in enumerate(presets):
        path = f"presets[{index}]"
        if not isinstance(preset, dict):
            errors.append(f"{path}: must be an object")
            continue
        preset_id = preset.get("preset_id")
        if not is_nonempty_string(preset_id):
            errors.append(f"{path}.preset_id: required non-empty string")
            preset_id = None
        elif preset_id in preset_ids:
            errors.append(f"{path}.preset_id: duplicate {preset_id!r}")
        else:
            preset_ids.add(preset_id)

        if not is_nonempty_string(preset.get("preset_type")):
            errors.append(f"{path}.preset_type: required non-empty string")

        template_source = preset.get("template_source")
        if not isinstance(template_source, dict):
            errors.append(f"{path}.template_source: required object")
        else:
            if not is_nonempty_string(template_source.get("timeline")):
                errors.append(f"{path}.template_source.timeline: required non-empty string")
            validate_string_list(
                f"{path}.template_source.segment_ids",
                template_source.get("segment_ids"),
                errors,
                require_nonempty=True,
            )
            if "material_ids" in template_source:
                validate_string_list(
                    f"{path}.template_source.material_ids",
                    template_source.get("material_ids"),
                )

        allowed = validate_string_list(
            f"{path}.allowed_overrides",
            preset.get("allowed_overrides"),
            errors,
        )
        if preset_id is not None:
            preset_allowed_overrides[preset_id] = set(allowed)

    if is_v11 and isinstance(data.get("template_health"), list):
        health_ids = {
            item.get("preset_id") for item in data["template_health"]
            if isinstance(item, dict) and is_nonempty_string(item.get("preset_id"))
        }
        for preset_id in preset_ids - health_ids:
            errors.append(f"template_health: missing health record for preset {preset_id!r}")

    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        errors.append("groups: required non-empty array")
        groups = []

    group_ids: set[str] = set()
    previous_sound: str | None = None
    sound_counts: dict[str, int] = {}
    track_intervals: dict[str, list[tuple[int, int, str]]] = {}

    for index, group in enumerate(groups):
        path = f"groups[{index}]"
        if not isinstance(group, dict):
            errors.append(f"{path}: must be an object")
            continue

        group_id = group.get("id")
        if not is_nonempty_string(group_id):
            errors.append(f"{path}.id: required non-empty string")
        elif group_id in group_ids:
            errors.append(f"{path}.id: duplicate {group_id!r}")
        else:
            group_ids.add(group_id)

        status = group.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            errors.append(f"{path}.status: must be one of {sorted(STATUSES)}")
        elif mode == "apply" and status == "review":
            errors.append(f"{path}.status: review group cannot be applied")

        if not is_nonempty_string(group.get("context")):
            errors.append(f"{path}.context: required non-empty string")

        group_range = validate_timerange(path + ".range", group.get("range"), errors)

        category = group.get("category")
        if not isinstance(category, str) or category not in CATEGORIES:
            errors.append(f"{path}.category: unsupported category")

        level = group.get("level")
        if not is_int(level) or level not in {1, 2, 3}:
            errors.append(f"{path}.level: must be 1, 2, or 3")

        motion = group.get("motion")
        motion_valid = isinstance(motion, str) and motion in MOTIONS
        if not motion_valid:
            errors.append(f"{path}.motion: unsupported motion")

        motion_event: dict[str, int] | None = None
        if "motion_event" in group:
            motion_event = validate_motion_event(
                path + ".motion_event", group.get("motion_event"), errors
            )
        elif motion_valid and motion != "none":
            errors.append(f"{path}.motion_event: required when motion is not none")
        if motion == "custom" and not is_nonempty_string(group.get("motion_note")):
            errors.append(f"{path}.motion_note: required for custom motion")
        if "motion_note" in group and group.get("motion_note") is not None and not is_nonempty_string(group.get("motion_note")):
            errors.append(f"{path}.motion_note: must be a non-empty string")

        if group_range and motion_event:
            group_start, group_end = group_range
            if motion_event["start_us"] < group_start or motion_event["end_us"] > group_end:
                warnings.append(
                    f"{path}.motion_event: falls outside the group range; verify intentional staging"
                )

        if "risk_note" in group and not is_nonempty_string(group.get("risk_note")):
            errors.append(f"{path}.risk_note: must be a non-empty string")

        visuals = group.get("visual", [])
        if not isinstance(visuals, list):
            errors.append(f"{path}.visual: must be an array")
            visuals = []
        phrase_start_present = False

        for vindex, visual in enumerate(visuals):
            vpath = f"{path}.visual[{vindex}]"
            if not isinstance(visual, dict):
                errors.append(f"{vpath}: must be an object")
                continue

            operation = visual.get("operation")
            operation_valid = isinstance(operation, str) and operation in VISUAL_OPERATIONS
            if not operation_valid:
                errors.append(f"{vpath}.operation: unsupported operation")
            if is_v11 and phase == "staging" and operation_valid and operation not in {"copy_from_subtitle", "modify_text", "none"}:
                errors.append(f"{vpath}.operation: staging phase only permits subtitle-copy/display review operations")

            object_type = visual.get("object_type")
            object_type_valid = isinstance(object_type, str) and object_type in OBJECT_TYPES
            if not object_type_valid:
                errors.append(f"{vpath}.object_type: unsupported object type")
            elif operation == "modify_text" and object_type != "text":
                errors.append(f"{vpath}.object_type: modify_text requires text")

            preset_id = visual.get("preset_id")
            preset_id_valid = False
            if preset_id is not None:
                if not is_nonempty_string(preset_id):
                    errors.append(f"{vpath}.preset_id: must be a non-empty string")
                else:
                    preset_id_valid = True
                    if preset_id not in preset_ids:
                        errors.append(f"{vpath}.preset_id: unknown preset {preset_id!r}")
            if operation == "clone_template" and not preset_id_valid:
                errors.append(f"{vpath}.preset_id: required for clone_template")

            if operation_valid and operation in EXISTING_SEGMENT_VISUAL_OPERATIONS:
                validate_locator(
                    f"{vpath}.target_locator",
                    visual.get("target_locator"),
                    errors,
                    require_segment=True,
                )
            elif operation_valid and operation in NEW_OBJECT_VISUAL_OPERATIONS:
                validate_locator(
                    f"{vpath}.target_locator",
                    visual.get("target_locator"),
                    errors,
                    require_track=True,
                )

            if operation_valid and operation in SOURCE_SEGMENT_VISUAL_OPERATIONS:
                validate_locator(
                    f"{vpath}.source_locator",
                    visual.get("source_locator"),
                    errors,
                    require_segment=True,
                )
            elif operation_valid and operation in SOURCE_ASSET_VISUAL_OPERATIONS:
                validate_locator(
                    f"{vpath}.source_locator",
                    visual.get("source_locator"),
                    errors,
                    require_asset=True,
                )

            if "text" in visual and not isinstance(visual.get("text"), str):
                errors.append(f"{vpath}.text: must be a string")
            if operation_valid and operation in {"clone_template", "modify_text"} and object_type == "text" and not is_nonempty_string(visual.get("text")):
                errors.append(f"{vpath}.text: required for {operation}")

            overrides = visual.get("overrides", {})
            if not isinstance(overrides, dict):
                errors.append(f"{vpath}.overrides: must be an object")
            else:
                allowed_for_preset = (
                    preset_allowed_overrides.get(preset_id, set())
                    if preset_id_valid
                    else set()
                )
                for name, value in overrides.items():
                    validate_override(f"{vpath}.overrides.{name}", value, errors)
                    if preset_id_valid and preset_id in preset_allowed_overrides and name not in allowed_for_preset:
                        errors.append(
                            f"{vpath}.overrides.{name}: not listed in preset {preset_id!r}.allowed_overrides"
                        )

            for field in TIME_FIELDS:
                if field not in visual:
                    continue
                field_value = visual.get(field)
                if not is_int(field_value):
                    errors.append(f"{vpath}.{field}: must be an integer")
                elif field == "duration_us" and field_value <= 0:
                    errors.append(f"{vpath}.{field}: must be positive")
                elif field != "duration_us" and field_value < 0:
                    errors.append(f"{vpath}.{field}: must be non-negative")
                if field == "phrase_start_us" and is_int(field_value):
                    phrase_start_present = True

            visual_start = visual.get("start_us")
            visual_duration = visual.get("duration_us")
            visual_end = visual.get("end_us")
            if is_int(visual_start) and is_int(visual_duration) and visual_duration > 0:
                calculated_end = visual_start + visual_duration
                if "end_us" in visual and is_int(visual_end) and visual_end != calculated_end:
                    errors.append(f"{vpath}.end_us: must equal start_us + duration_us")
                if group_range and (visual_start < group_range[0] or calculated_end > group_range[1]):
                    warnings.append(
                        f"{vpath}: timing falls outside the group range; verify intentional staging"
                    )
            elif group_range:
                for field in ("phrase_start_us", "start_us", "animation_start_us", "animation_peak_us", "animation_end_us"):
                    field_value = visual.get(field)
                    if is_int(field_value) and not (group_range[0] <= field_value <= group_range[1]):
                        warnings.append(
                            f"{vpath}.{field}: falls outside the group range; verify intentional staging"
                        )

            if operation_valid and operation in NEW_OBJECT_VISUAL_OPERATIONS:
                register_track_interval(
                    vpath,
                    visual.get("target_locator"),
                    group_range,
                    track_intervals,
                    warnings,
                )

            text = visual.get("text")
            if isinstance(text, str):
                long_lines = [line for line in text.splitlines() if len(line) > max_chars]
                if long_lines and not is_nonempty_string(group.get("risk_note")):
                    warnings.append(
                        f"{vpath}.text: line exceeds max_chars_per_line={max_chars}; split it or add risk_note"
                    )

        audio = group.get("audio", {"action": "none"})
        if not isinstance(audio, dict):
            errors.append(f"{path}.audio: must be an object")
            continue

        action = audio.get("action", "none")
        action_valid = isinstance(action, str) and action in AUDIO_ACTIONS
        if not action_valid:
            errors.append(f"{path}.audio.action: unsupported action")
            continue

        if action != "none":
            if not is_nonempty_string(audio.get("reason")):
                errors.append(f"{path}.audio.reason: required for a sound action")
            if not is_nonempty_string(audio.get("sound_family")):
                errors.append(f"{path}.audio.sound_family: required for a sound action")
            if is_v11:
                if not is_nonempty_string(audio.get("motion_family")):
                    errors.append(f"{path}.audio.motion_family: required for schema 1.1")
                if not is_nonempty_string(audio.get("selection_basis")):
                    errors.append(f"{path}.audio.selection_basis: required for schema 1.1")
                reuse_count = audio.get("reuse_count")
                if not is_int(reuse_count) or reuse_count <= 0:
                    errors.append(f"{path}.audio.reuse_count: must be a positive integer")
                elif reuse_count > reuse_cap:
                    errors.append(f"{path}.audio.reuse_count: exceeds configured reuse cap {reuse_cap}")
            if is_v11 and phase == "staging":
                errors.append(f"{path}.audio: staging phase must not add sound effects")

            target_locator = audio.get("target_locator")
            target_locator_valid = validate_locator(
                f"{path}.audio.target_locator",
                target_locator,
                errors,
                require_segment=action == "reuse_existing",
                require_track=action != "reuse_existing",
            )

            asset_id = audio.get("asset_id")
            asset_id_valid = is_nonempty_string(asset_id)
            if "asset_id" in audio and not asset_id_valid:
                errors.append(f"{path}.audio.asset_id: must be a non-empty string")

            source_locator_valid = False
            if "source_locator" in audio:
                source_locator_valid = validate_locator(
                    f"{path}.audio.source_locator",
                    audio.get("source_locator"),
                    errors,
                    require_asset=True,
                )
            if action in {"clone_asset", "add_asset"} and not source_locator_valid:
                errors.append(f"{path}.audio.source_locator: required for {action}")
            elif action == "reuse_existing" and not (asset_id_valid or source_locator_valid):
                errors.append(
                    f"{path}.audio: identify asset_id or source_locator; asset_name alone is ambiguous"
                )

            asset_name = audio.get("asset_name")
            if "asset_name" in audio and not is_nonempty_string(asset_name):
                errors.append(f"{path}.audio.asset_name: must be a non-empty string")

            sync = audio.get("sync")
            anchor: str | None = None
            if not isinstance(sync, dict):
                errors.append(f"{path}.audio.sync: required object")
            else:
                anchor_value = sync.get("anchor")
                if not isinstance(anchor_value, str) or anchor_value not in SYNC_ANCHORS:
                    errors.append(f"{path}.audio.sync.anchor: unsupported or missing")
                else:
                    anchor = anchor_value
                for field in ("offset_us", "time_us"):
                    if field in sync and not is_int(sync.get(field)):
                        errors.append(f"{path}.audio.sync.{field}: must be an integer")
                if "time_us" in sync and is_int(sync.get("time_us")) and sync["time_us"] < 0:
                    errors.append(f"{path}.audio.sync.time_us: must be non-negative")

                if anchor in ANIMATION_ANCHORS and motion_event is None:
                    errors.append(
                        f"{path}.audio.sync: {anchor} requires a valid motion_event"
                    )
                if anchor == "phrase_start" and not phrase_start_present:
                    errors.append(
                        f"{path}.audio.sync: phrase_start requires visual phrase_start_us"
                    )
                if anchor in {"transition_peak", "custom"} and not is_int(sync.get("time_us")):
                    errors.append(
                        f"{path}.audio.sync.time_us: required for {anchor}"
                    )
                if anchor in {"transition_peak", "custom"} and is_int(sync.get("time_us")) and group_range:
                    if not (group_range[0] <= sync["time_us"] <= group_range[1]):
                        warnings.append(
                            f"{path}.audio.sync.time_us: falls outside the group range; verify intentional staging"
                        )

            if "volume" in audio:
                volume = audio.get("volume")
                if not is_number(volume) or not 0 <= volume <= 1:
                    errors.append(f"{path}.audio.volume: must be numeric between 0 and 1")
            for field in ("fade_in_us", "fade_out_us", "dedupe_tolerance_us"):
                validate_optional_nonnegative_int(path + ".audio", audio, field, errors)

            source_range = None
            target_range = None
            if "source_range" in audio:
                source_range = validate_timerange(
                    f"{path}.audio.source_range", audio.get("source_range"), errors
                )
            if "target_range" in audio:
                target_range = validate_timerange(
                    f"{path}.audio.target_range", audio.get("target_range"), errors
                )

            sound_key = None
            if asset_id_valid:
                sound_key = f"asset_id:{asset_id}"
            elif source_locator_valid:
                sound_key = locator_key(audio.get("source_locator"))
            if previous_sound and sound_key and sound_key == previous_sound:
                warnings.append(
                    f"{path}.audio: same sound asset as previous audible group; verify intentional repetition"
                )
            if sound_key:
                previous_sound = sound_key
                sound_counts[sound_key] = sound_counts.get(sound_key, 0) + 1
                if is_v11 and sound_counts[sound_key] > reuse_cap:
                    errors.append(f"{path}.audio: sound asset {sound_key!r} exceeds reuse cap {reuse_cap}")
                if is_v11 and is_int(audio.get("reuse_count")) and audio["reuse_count"] != sound_counts[sound_key]:
                    errors.append(
                        f"{path}.audio.reuse_count: expected occurrence {sound_counts[sound_key]} for {sound_key!r}"
                    )

            if action != "reuse_existing" and target_locator_valid:
                register_track_interval(
                    path + ".audio",
                    target_locator,
                    target_range or group_range,
                    track_intervals,
                    warnings,
                )

        elif not visuals and status == "approved":
            warnings.append(f"{path}: approved group has no visual operation or audible action")

    return errors, warnings


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_packaging_plan.py <plan.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        errors, warnings = validate_plan(data)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": [f"validation failed safely: {type(exc).__name__}: {exc}"],
                    "warnings": [],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(
        json.dumps(
            {"ok": not errors, "errors": errors, "warnings": warnings},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
