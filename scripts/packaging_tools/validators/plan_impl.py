#!/usr/bin/env python3
"""Validate a Jianying semantic packaging plan without touching a draft."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


CATEGORIES = {
    "question", "core_point", "number_parameter", "product_brand",
    "technical_term", "risk_warning", "conclusion", "contrast_turn",
    "emotion", "cta", "transition", "ordinary_explanation", "hook",
    "background", "reaction", "answer", "evidence", "technical_detail",
    "contrast", "benefit", "summary",
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
SUPPORTED_SCHEMA_VERSIONS = {"1.0", "1.1", "1.2"}
PACKAGING_PHASES = {"staging", "final"}
REMAP_STATUSES = {"not_required", "pending", "verified", "blocked"}
LAYOUT_POSITION_MODES = {"relative_template", "legacy_absolute"}
LAYOUT_ANCHOR_TYPES = {"runtime_reference", "group_origin", "manual_reference"}
LAYOUT_COLLISION_POLICIES = {"warn", "block", "intentional_overlap", "intentional_attachment"}
LAYOUT_REF_TYPES = {"subtitle_unit", "auxiliary_mark"}
LAYOUT_ALIGNMENTS = {"left", "center", "right", "top", "middle", "bottom"}
TRIM_POLICIES = {"text_span", "motion_span", "natural", "manual_review"}
LEADING_SILENCE_POLICIES = {"skip", "preserve", "manual_review"}
SOUND_FORMS = {"single_hit", "decay", "multi_hit", "loop", "ambience", "unknown"}
SOUND_STATUSES = {"verified", "candidate", "needs_listen", "blocked"}
MOTION_SOUND_FAMILIES = {
    "pop", "reveal", "typing", "sweep", "impact", "mechanical_open",
    "warning_pulse", "confirmation", "none",
}
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
CONTEXT_STOP_CONDITIONS = {
    "pending_remap",
    "text_mismatch",
    "layout_collision",
    "unverified_sound",
    "leading_silence_unresolved",
    "missing_backup",
}

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
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def sha256_text(value: str) -> str:
    """Return the canonical UTF-8 hash used for final subtitle text bindings."""
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def _detect_cycle(edges: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in edges.get(node, set()):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in edges)


def _load_reference_json(filename: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[3] / "references" / filename
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _validate_slot_transform(path: str, slot: dict[str, Any], errors: list[str]) -> None:
    scale = slot.get("scale")
    if scale is not None:
        if isinstance(scale, dict):
            for axis in ("x", "y"):
                if not is_number(scale.get(axis)) or scale[axis] <= 0:
                    errors.append(f"{path}.scale.{axis}: must be a positive number")
        elif not is_number(scale) or scale <= 0:
            errors.append(f"{path}.scale: must be a positive number or x/y object")
    if "rotation" in slot and not is_number(slot.get("rotation")):
        errors.append(f"{path}.rotation: must be numeric")
    if "alignment" in slot and slot.get("alignment") not in LAYOUT_ALIGNMENTS:
        errors.append(f"{path}.alignment: invalid")


def validate_layout(
    path: str,
    value: Any,
    errors: list[str],
    warnings: list[str],
    *,
    final_phase: bool,
    schema_v12: bool,
    semantic_refs: set[str],
    auxiliary_refs: set[str],
    layout_registry: dict[str, Any],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: required layout object")
        return
    if not is_nonempty_string(value.get("template_id")):
        errors.append(f"{path}.template_id: required non-empty string")
    version = value.get("template_version")
    if not is_int(version) or version <= 0:
        errors.append(f"{path}.template_version: must be a positive integer")
    position_mode = value.get("position_mode", "relative_template")
    if position_mode not in LAYOUT_POSITION_MODES:
        errors.append(f"{path}.position_mode: invalid")

    templates = layout_registry.get("templates") if isinstance(layout_registry, dict) else None
    template_record = None
    if isinstance(templates, list):
        template_record = next(
            (
                item for item in templates
                if isinstance(item, dict) and item.get("template_id") == value.get("template_id")
            ),
            None,
        )
    if template_record is None:
        errors.append(f"{path}.template_id: not found in layout registry")
    elif is_int(version) and template_record.get("template_version") != version:
        errors.append(f"{path}.template_version: does not match layout registry")

    anchor = value.get("anchor")
    if not isinstance(anchor, dict):
        errors.append(f"{path}.anchor: required object")
    else:
        anchor_type = anchor.get("type")
        if anchor_type not in LAYOUT_ANCHOR_TYPES:
            errors.append(f"{path}.anchor.type: invalid")
        if position_mode == "relative_template":
            if anchor_type == "runtime_reference":
                if anchor.get("x") != "X0" or anchor.get("y") != "Y0":
                    errors.append(f"{path}.anchor: runtime_reference must use X0 and Y0")
            elif anchor_type == "manual_reference" and final_phase:
                warnings.append(f"{path}.anchor: manual reference requires visual verification")

    slots = value.get("slots")
    if not isinstance(slots, list) or not slots:
        errors.append(f"{path}.slots: must be a non-empty array")
        slots = []
    slot_ids: set[str] = set()
    references: list[tuple[str, str]] = []
    edges: dict[str, set[str]] = {}
    for index, slot in enumerate(slots):
        slot_path = f"{path}.slots[{index}]"
        if not isinstance(slot, dict):
            errors.append(f"{slot_path}: must be an object")
            continue
        slot_id = slot.get("id")
        if not is_nonempty_string(slot_id):
            errors.append(f"{slot_path}.id: required non-empty string")
            continue
        if slot_id in slot_ids:
            errors.append(f"{slot_path}.id: duplicate {slot_id!r}")
        slot_ids.add(slot_id)
        if not is_nonempty_string(slot.get("text_ref")):
            errors.append(f"{slot_path}.text_ref: required non-empty string")
        ref_type = slot.get("ref_type")
        if schema_v12 and ref_type not in LAYOUT_REF_TYPES:
            errors.append(f"{slot_path}.ref_type: must be subtitle_unit or auxiliary_mark")
        elif ref_type is None:
            ref_type = "subtitle_unit"
        text_ref = slot.get("text_ref")
        if is_nonempty_string(text_ref):
            if ref_type == "subtitle_unit" and text_ref not in semantic_refs:
                errors.append(f"{slot_path}.text_ref: must reference a declared semantic_unit_ref")
            elif ref_type == "auxiliary_mark" and text_ref not in auxiliary_refs:
                errors.append(f"{slot_path}.text_ref: must reference a declared auxiliary_text_ref")
        offset = slot.get("offset")
        if not isinstance(offset, dict):
            errors.append(f"{slot_path}.offset: required object")
        else:
            for field in ("dx", "dy"):
                if not is_number(offset.get(field)):
                    errors.append(f"{slot_path}.offset.{field}: must be numeric")
        for field in ("relative_to", "inherit_transform_from"):
            reference = slot.get(field)
            if reference is not None:
                if not is_nonempty_string(reference):
                    errors.append(f"{slot_path}.{field}: must be a non-empty string")
                else:
                    references.append((slot_path, reference))
                    edges.setdefault(slot_id, set()).add(reference)
        if "relation_labels" in slot:
            validate_string_list(f"{slot_path}.relation_labels", slot.get("relation_labels"), errors)
        _validate_slot_transform(slot_path, slot, errors)
    for slot_path, reference in references:
        if reference not in slot_ids:
            errors.append(f"{slot_path}: references unknown slot {reference!r}")
    if _detect_cycle(edges):
        errors.append(f"{path}.slots: relative references must not contain cycles")

    if value.get("fallback") != "manual_review":
        errors.append(f"{path}.fallback: must be manual_review")
    constraints = value.get("constraints", {})
    if not isinstance(constraints, dict):
        errors.append(f"{path}.constraints: must be an object")
    else:
        if final_phase and not is_nonempty_string(constraints.get("safe_zone")):
            errors.append(f"{path}.constraints.safe_zone: required for final layout validation")
        collision = constraints.get("collision")
        if collision is not None and collision not in LAYOUT_COLLISION_POLICIES:
            errors.append(f"{path}.constraints.collision: invalid")
        if final_phase and collision is None:
            errors.append(f"{path}.constraints.collision: required for final layout validation")
    if position_mode == "legacy_absolute":
        if value.get("visual_verification") is not True:
            errors.append(f"{path}: legacy_absolute requires visual_verification=true")
        if final_phase:
            warnings.append(f"{path}: legacy absolute layout is allowed only after visual review")


def _validate_sound_pool(
    path: str,
    audio: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    *,
    mode: str | None,
    phase: str | None,
    sound_pools: dict[str, Any],
    sound_catalog: dict[str, Any],
) -> tuple[dict[str, Any] | None, set[str]]:
    pool_ref = audio.get("candidate_pool_ref")
    if not is_nonempty_string(pool_ref):
        errors.append(f"{path}.candidate_pool_ref: required for schema 1.2 audio")
        return None, set()
    pool_data: dict[str, Any] | None = None
    inline_used = False
    inline = audio.get("candidate_pool")
    if isinstance(inline, list):
        inline_used = True
        pool_data = {"pool_id": pool_ref, "min_candidates": 3, "candidates": inline}
    else:
        for item in sound_pools.get("pools", []) if isinstance(sound_pools.get("pools"), list) else []:
            if isinstance(item, dict) and item.get("pool_id") == pool_ref:
                pool_data = item
                break
    if pool_data is None:
        errors.append(f"{path}.candidate_pool_ref: unknown candidate pool {pool_ref!r}")
        return None, set()
    candidates = pool_data.get("candidates")
    if not isinstance(candidates, list):
        errors.append(f"{path}.candidate_pool: candidates must be an array")
        return pool_data, set()
    candidate_ids: set[str] = set()
    candidate_statuses: dict[str, str] = {}
    for index, candidate in enumerate(candidates):
        candidate_path = f"{path}.candidate_pool[{index}]"
        if not isinstance(candidate, dict) or not is_nonempty_string(candidate.get("preset_id")):
            errors.append(f"{candidate_path}.preset_id: required")
            continue
        preset_id = candidate["preset_id"]
        if preset_id in candidate_ids:
            errors.append(f"{candidate_path}.preset_id: duplicate")
        candidate_ids.add(preset_id)
        status = candidate.get("status")
        if status not in SOUND_STATUSES:
            errors.append(f"{candidate_path}.status: invalid")
        elif preset_id not in candidate_statuses:
            candidate_statuses[preset_id] = status
        if "rank" in candidate and (not is_int(candidate.get("rank")) or candidate["rank"] <= 0):
            errors.append(f"{candidate_path}.rank: must be a positive integer")
        if "sound_form" in candidate and candidate.get("sound_form") not in SOUND_FORMS:
            errors.append(f"{candidate_path}.sound_form: invalid")

    final_or_apply = mode == "apply" or phase == "final"
    if inline_used and final_or_apply:
        errors.append(f"{path}.candidate_pool: inline candidate pools are review-only")

    expected_motion = audio.get("motion_family")
    pool_motion = pool_data.get("motion_family")
    if pool_motion is not None and expected_motion != pool_motion:
        errors.append(
            f"{path}.candidate_pool_ref: motion family {pool_motion!r} does not match {expected_motion!r}"
        )
    minimum = pool_data.get("min_candidates", 3)
    if not is_int(minimum) or minimum < 0:
        errors.append(f"{path}.candidate_pool.min_candidates: must be a non-negative integer")
        minimum = 3
    if len(candidate_ids) < minimum:
        message = f"{path}.candidate_pool: candidate_pool_incomplete ({len(candidate_ids)}/{minimum})"
        if final_or_apply:
            errors.append(message)
        else:
            warnings.append(message)
    selected = audio.get("selected_preset_id")
    if not is_nonempty_string(selected):
        errors.append(f"{path}.selected_preset_id: required")
    elif selected not in candidate_ids:
        errors.append(f"{path}.selected_preset_id: must belong to candidate pool")

    catalog_records = {
        item.get("preset_id"): item
        for item in sound_catalog.get("presets", [])
        if isinstance(item, dict) and is_nonempty_string(item.get("preset_id"))
    }
    catalog_ref = audio.get("catalog_ref")
    if catalog_ref != selected:
        errors.append(f"{path}.catalog_ref: must equal selected_preset_id")
    if catalog_ref not in catalog_records:
        message = f"{path}.catalog_ref: preset is absent from the sound catalog"
        if final_or_apply:
            errors.append(message)
        else:
            warnings.append(message)
    elif catalog_records[catalog_ref].get("status") != "verified" and final_or_apply:
        errors.append(f"{path}.catalog_ref: final/apply requires a verified catalog record")

    return pool_data, candidate_ids


def _validate_common_source_status(
    data: dict[str, Any],
    errors: list[str],
) -> str | None:
    source = data.get("source")
    if not isinstance(source, dict):
        return None
    content_status = source.get("content_pass")
    if content_status not in {"stable", "approved"}:
        errors.append("source.content_pass: must be stable or approved")
    return validate_reference_status(
        "source.subtitle_alignment", source.get("subtitle_alignment"), errors, required=True
    )


def _validate_final_subtitle_units(
    source: dict[str, Any],
    errors: list[str],
) -> dict[str, str]:
    units = source.get("final_subtitle_units")
    if not isinstance(units, list) or not units:
        errors.append("source.final_subtitle_units: required non-empty array for schema 1.2")
        return {}

    result: dict[str, str] = {}
    for index, unit in enumerate(units):
        path = f"source.final_subtitle_units[{index}]"
        if not isinstance(unit, dict):
            errors.append(f"{path}: must be an object")
            continue
        unit_id = unit.get("unit_id")
        text_hash = unit.get("text_hash")
        if not is_nonempty_string(unit_id):
            errors.append(f"{path}.unit_id: required non-empty string")
            continue
        if unit_id in result:
            errors.append(f"{path}.unit_id: duplicate {unit_id!r}")
        if not is_nonempty_string(text_hash):
            errors.append(f"{path}.text_hash: required non-empty string")
        if unit.get("status") != "approved":
            errors.append(f"{path}.status: must be approved")
        result[unit_id] = text_hash if is_nonempty_string(text_hash) else ""
    return result


def validate_v12_contract(
    data: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> dict[str, str]:
    source = data.get("source")
    if not isinstance(source, dict):
        return {}
    final_subtitle_hashes = _validate_final_subtitle_units(source, errors)
    final_reference = source.get("final_subtitle_reference")
    if not isinstance(final_reference, dict):
        errors.append("source.final_subtitle_reference: required object for schema 1.2")
    else:
        for field in ("id", "hash"):
            if not is_nonempty_string(final_reference.get(field)):
                errors.append(f"source.final_subtitle_reference.{field}: required non-empty string")
        if final_reference.get("status") != "approved":
            errors.append("source.final_subtitle_reference.status: must be approved")

    comparison = data.get("comparison")
    if not isinstance(comparison, dict):
        errors.append("comparison: required object for schema 1.2")
    else:
        for field in ("source_order_hash", "target_order_hash"):
            if not is_nonempty_string(comparison.get(field)):
                errors.append(f"comparison.{field}: required non-empty string")
        if comparison.get("remap_status") not in REMAP_STATUSES:
            errors.append("comparison.remap_status: invalid")
        if (
            is_nonempty_string(comparison.get("source_order_hash"))
            and is_nonempty_string(comparison.get("target_order_hash"))
            and comparison.get("source_order_hash") != comparison.get("target_order_hash")
            and comparison.get("remap_status") == "not_required"
        ):
            errors.append("comparison.remap_status: order hashes differ, remap cannot be not_required")

    execution = data.get("execution")
    if not isinstance(execution, dict):
        return final_subtitle_hashes
    authorization_note = execution.get("authorization_note")
    allow_in_place = execution.get("allow_in_place") is True and is_nonempty_string(authorization_note)
    allow_manual_overwrite = execution.get("allow_manual_overwrite") is True and is_nonempty_string(authorization_note)
    if execution.get("clone_source") is not True and not allow_in_place:
        errors.append("execution.clone_source: must be true for schema 1.2")
    if execution.get("pre_write_backup") != "required":
        errors.append("execution.pre_write_backup: must be required for schema 1.2")
    if execution.get("preserve_source") is not True and not allow_in_place:
        errors.append("execution.preserve_source: must be true for schema 1.2")
    if execution.get("preserve_manual_edits") is not True and not allow_manual_overwrite:
        errors.append("execution.preserve_manual_edits: must be true for schema 1.2")

    context = execution.get("context_contract")
    if not isinstance(context, dict):
        errors.append("execution.context_contract: required for schema 1.2")
    else:
        expected_context = {
            "anchor_policy": "runtime_final_subtitle_x0_y0",
            "layout_policy": "group_atomic_relative",
            "sound_policy": "catalog_candidate_single",
        }
        for field, expected in expected_context.items():
            if context.get(field) != expected:
                errors.append(f"execution.context_contract.{field}: must be {expected}")
        if context.get("readback_required") is not True:
            errors.append("execution.context_contract.readback_required: must be true")
        stop_conditions = context.get("stop_conditions")
        if not isinstance(stop_conditions, list) or any(not is_nonempty_string(item) for item in stop_conditions):
            errors.append("execution.context_contract.stop_conditions: must be an array of strings")
        elif not CONTEXT_STOP_CONDITIONS.issubset(set(stop_conditions)):
            errors.append("execution.context_contract.stop_conditions: missing required stop condition")
    return final_subtitle_hashes


def validate_v11_contract(data: dict[str, Any], errors: list[str], warnings: list[str]) -> tuple[str | None, int]:
    source = data.get("source")
    if not isinstance(source, dict):
        return None, 3
    alignment_status = _validate_common_source_status(data, errors)

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


def _visual_values(group: dict[str, Any], path: str, errors: list[str]) -> list[Any]:
    """Return canonical group.visual while checking legacy aliases."""
    aliases = [key for key in ("visual", "visuals", "visual_operations") if key in group]
    if not aliases:
        return []
    canonical_key = "visual" if "visual" in group else aliases[0]
    canonical = group.get(canonical_key)
    if not isinstance(canonical, list):
        errors.append(f"{path}.visual: must be an array")
        canonical = []
    for alias in aliases:
        if alias == canonical_key:
            continue
        value = group.get(alias)
        if not isinstance(value, list):
            errors.append(f"{path}.{alias}: must be an array")
        elif value != canonical:
            errors.append(f"{path}: visual aliases disagree ({alias})")
    return canonical


def validate_plan(
    data: Any,
    *,
    sound_catalog: dict[str, Any] | None = None,
    sound_pools: dict[str, Any] | None = None,
    layout_registry: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["root: plan must be a JSON object"], warnings

    if sound_catalog is None:
        sound_catalog = _load_reference_json("sound-preset-catalog.json")
    if sound_pools is None:
        sound_pools = _load_reference_json("motion-sound-pools.json")
    if layout_registry is None:
        layout_registry = _load_reference_json("layout-template-registry.json")

    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append("schema_version: expected '1.0', '1.1', or '1.2'")
    is_v11 = schema_version == "1.1"
    is_v12 = schema_version == "1.2"
    if schema_version == "1.0":
        warnings.append("schema_version 1.0 is legacy; migrate to 1.2 before apply")

    alignment_status: str | None = None
    final_subtitle_hashes: dict[str, str] = {}
    reuse_cap = 3
    if is_v11:
        alignment_status, reuse_cap = validate_v11_contract(data, errors, warnings)
    if is_v12:
        alignment_status = _validate_common_source_status(data, errors)
        final_subtitle_hashes = validate_v12_contract(data, errors, warnings)

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
        if is_v12 and phase not in PACKAGING_PHASES:
            errors.append("execution.phase: must be staging or final")
        if is_v12 and phase == "final":
            staging = data.get("staging")
            if not isinstance(staging, dict) or staging.get("review_status") != "approved":
                errors.append("execution.phase=final requires staging.review_status=approved")
            if alignment_status != "approved":
                errors.append("execution.phase=final requires approved subtitle alignment")
            comparison = data.get("comparison")
            if isinstance(comparison, dict) and comparison.get("remap_status") not in {"not_required", "verified"}:
                errors.append("execution.phase=final requires comparison.remap_status=not_required or verified")
        if is_v11 and phase == "staging" and covered_policy not in {"preserve", "review"}:
            errors.append("staging phase may only preserve or review covered subtitles")
        if is_v11 and covered_policy == "delete_on_clone_after_approval":
            staging = data.get("staging")
            if not isinstance(staging, dict) or staging.get("review_status") != "approved":
                errors.append("delete_on_clone_after_approval requires approved staging review")
        if is_v11 and covered_policy == "disable_after_readback" and mode == "apply":
            warnings.append("disable_after_readback requires visual read-back; it is not a success condition by itself")

        if mode == "apply":
            if schema_version in {"1.0", "1.1"}:
                errors.append(f"schema_version {schema_version} must be migrated before apply (to 1.2)")
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
                    errors,
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

        semantic_refs: set[str] = set()
        auxiliary_refs: set[str] = set()
        if is_v12:
            semantic_refs = set(validate_string_list(
                f"{path}.semantic_unit_refs",
                group.get("semantic_unit_refs"),
                errors,
                require_nonempty=True,
            ))
            auxiliary_refs = set(validate_string_list(
                f"{path}.auxiliary_text_refs",
                group.get("auxiliary_text_refs", []),
                errors,
            ))
            for unit_id in sorted(semantic_refs):
                if unit_id not in final_subtitle_hashes:
                    errors.append(
                        f"{path}.semantic_unit_refs: {unit_id!r} is missing from source.final_subtitle_units"
                    )
            subtitle_anchor = group.get("subtitle_anchor")
            if not isinstance(subtitle_anchor, dict):
                errors.append(f"{path}.subtitle_anchor: required object for schema 1.2")
            else:
                if not is_nonempty_string(subtitle_anchor.get("unit_id")):
                    errors.append(f"{path}.subtitle_anchor.unit_id: required")
                if not is_nonempty_string(subtitle_anchor.get("text_hash")):
                    errors.append(f"{path}.subtitle_anchor.text_hash: required")
                if subtitle_anchor.get("text_authority") != "final_visible_subtitle":
                    errors.append(f"{path}.subtitle_anchor.text_authority: must be final_visible_subtitle")
                if semantic_refs and subtitle_anchor.get("unit_id") not in semantic_refs:
                    errors.append(f"{path}.subtitle_anchor.unit_id: must be listed in semantic_unit_refs")
                anchor_id = subtitle_anchor.get("unit_id")
                expected_anchor_hash = final_subtitle_hashes.get(anchor_id)
                if expected_anchor_hash and subtitle_anchor.get("text_hash") != expected_anchor_hash:
                    errors.append(f"{path}.subtitle_anchor: text_mismatch with final subtitle unit {anchor_id!r}")
            group_remap = group.get("remap_status")
            if group_remap not in REMAP_STATUSES:
                errors.append(f"{path}.remap_status: invalid")
            elif phase == "final" and group_remap not in {"not_required", "verified"}:
                errors.append(f"{path}.remap_status: final groups require not_required or verified")
            for field in ("source_order_hash", "target_order_hash"):
                if not is_nonempty_string(group.get(field)):
                    errors.append(f"{path}.{field}: required for schema 1.2")
            if (
                is_nonempty_string(group.get("source_order_hash"))
                and is_nonempty_string(group.get("target_order_hash"))
                and group.get("source_order_hash") != group.get("target_order_hash")
                and group_remap == "not_required"
            ):
                errors.append(f"{path}.remap_status: group order hashes differ, remap cannot be not_required")
            if "sound_selection_basis" in group and not is_nonempty_string(group.get("sound_selection_basis")):
                errors.append(f"{path}.sound_selection_basis: must be a non-empty string")

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

        visuals = _visual_values(group, path, errors)
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
            if phase == "staging" and operation_valid and operation not in {"copy_from_subtitle", "modify_text", "none"}:
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

            if is_v12 and object_type == "text" and is_nonempty_string(visual.get("text")):
                text_ref = visual.get("text_ref")
                if not is_nonempty_string(text_ref):
                    errors.append(f"{vpath}.text_ref: required for schema 1.2 text operations")
                elif text_ref in semantic_refs:
                    expected_hash = final_subtitle_hashes.get(text_ref)
                    text_hash = visual.get("text_hash")
                    if not is_nonempty_string(text_hash):
                        errors.append(f"{vpath}.text_hash: required for final subtitle text")
                    elif expected_hash and text_hash != expected_hash:
                        errors.append(f"{vpath}: text_mismatch with final subtitle unit {text_ref!r}")
                    if expected_hash and sha256_text(visual["text"]) != expected_hash:
                        errors.append(f"{vpath}: text_mismatch with final subtitle unit {text_ref!r}")
                elif text_ref not in auxiliary_refs:
                    errors.append(
                        f"{vpath}.text_ref: must reference a declared semantic_unit_ref or auxiliary_text_ref"
                    )

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

        if is_v12:
            has_visual_operation = any(
                isinstance(visual, dict) and visual.get("operation") not in {None, "none"}
                for visual in visuals
            )
            if has_visual_operation:
                if "layout" not in group:
                    if phase == "final":
                        errors.append(f"{path}.layout: required for schema 1.2 final visual groups")
                else:
                    validate_layout(
                        path + ".layout",
                        group.get("layout"),
                        errors,
                        warnings,
                        final_phase=phase == "final",
                        schema_v12=True,
                        semantic_refs=semantic_refs,
                        auxiliary_refs=auxiliary_refs,
                        layout_registry=layout_registry,
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
            if is_v12 and not is_nonempty_string(group.get("sound_selection_basis")):
                errors.append(f"{path}.sound_selection_basis: required when a sound is selected")
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
            sound_pool: dict[str, Any] | None = None
            sound_pool_ids: set[str] = set()
            if is_v12:
                motion_family = audio.get("motion_family")
                if motion_family not in MOTION_SOUND_FAMILIES or motion_family == "none":
                    errors.append(f"{path}.audio.motion_family: must be a supported audible motion family")
                if not is_nonempty_string(audio.get("catalog_ref")):
                    errors.append(f"{path}.audio.catalog_ref: required for schema 1.2")
                sound_form = audio.get("sound_form")
                if sound_form not in SOUND_FORMS:
                    errors.append(f"{path}.audio.sound_form: invalid")
                trim_policy = audio.get("trim_policy")
                if trim_policy not in TRIM_POLICIES:
                    errors.append(f"{path}.audio.trim_policy: invalid")
                leading_policy = audio.get("leading_silence_policy")
                if leading_policy not in LEADING_SILENCE_POLICIES:
                    errors.append(f"{path}.audio.leading_silence_policy: invalid")
                leading_silence = audio.get("leading_silence_us")
                if not is_int(leading_silence) or leading_silence < 0:
                    errors.append(f"{path}.audio.leading_silence_us: must be a non-negative integer")
                sound_pool, sound_pool_ids = _validate_sound_pool(
                    f"{path}.audio",
                    audio,
                    errors,
                    warnings,
                    mode=mode,
                    phase=phase,
                    sound_pools=sound_pools,
                    sound_catalog=sound_catalog,
                )
                final_or_apply = mode == "apply" or phase == "final"
                if sound_form == "unknown" and final_or_apply:
                    errors.append(f"{path}.audio.sound_form: unknown form cannot be applied")
                elif sound_form == "unknown":
                    warnings.append(f"{path}.audio.sound_form: unknown form requires human review")
                if sound_form in {"single_hit", "decay"} and trim_policy == "motion_span" and not is_nonempty_string(audio.get("override_reason")):
                    errors.append(f"{path}.audio.override_reason: required when single/decay uses motion_span")
                if sound_form == "multi_hit" and trim_policy == "text_span" and not is_nonempty_string(audio.get("override_reason")):
                    errors.append(f"{path}.audio.override_reason: required when multi_hit uses text_span")
                if leading_policy == "preserve" and not is_nonempty_string(audio.get("override_reason")):
                    errors.append(f"{path}.audio.override_reason: required when preserving leading silence")
                if leading_policy == "manual_review" and final_or_apply:
                    errors.append(f"{path}.audio.leading_silence_policy: manual review is unresolved")
                selected = audio.get("selected_preset_id")
                selected_status = None
                if sound_pool and isinstance(sound_pool.get("candidates"), list):
                    for candidate in sound_pool["candidates"]:
                        if isinstance(candidate, dict) and candidate.get("preset_id") == selected:
                            selected_status = candidate.get("status")
                            break
                if selected_status != "verified":
                    if final_or_apply:
                        errors.append(f"{path}.audio.selected_preset_id: final/apply requires a verified candidate")
                    else:
                        warnings.append(f"{path}.audio.selected_preset_id: candidate is not verified")
            if phase == "staging":
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

            if is_v12:
                trim_policy = audio.get("trim_policy")
                text_range = None
                if "text_range" in audio:
                    text_range = validate_timerange(
                        f"{path}.audio.text_range", audio.get("text_range"), errors
                    )
                if trim_policy == "text_span" and text_range is None:
                    errors.append(f"{path}.audio.text_range: required for text_span")
                if trim_policy == "text_span" and text_range is not None:
                    if target_range is None:
                        errors.append(f"{path}.audio.target_range: required for text_span")
                    elif target_range != text_range:
                        errors.append(f"{path}.audio.target_range: must equal text_range for text_span")
                if trim_policy == "motion_span" and motion_event is None:
                    errors.append(f"{path}.audio: motion_span requires a valid group motion_event")
                if trim_policy == "motion_span" and motion_event is not None:
                    expected_motion_range = (
                        motion_event["start_us"],
                        motion_event["end_us"],
                    )
                    if target_range is None:
                        errors.append(f"{path}.audio.target_range: required for motion_span")
                    elif target_range != expected_motion_range:
                        errors.append(f"{path}.audio.target_range: must equal motion_event for motion_span")
                if trim_policy == "manual_review" and (mode == "apply" or phase == "final"):
                    errors.append(f"{path}.audio.trim_policy: manual review is unresolved")
                leading_policy = audio.get("leading_silence_policy")
                leading_silence = audio.get("leading_silence_us")
                if is_int(leading_silence) and leading_silence > 0 and source_range is None:
                    errors.append(f"{path}.audio.source_range: required when leading silence is known")
                if (
                    leading_policy == "skip"
                    and is_int(leading_silence)
                    and leading_silence > 0
                    and source_range is not None
                    and source_range[0] < leading_silence
                ):
                    errors.append(f"{path}.audio.source_range: must start after known leading silence")

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


