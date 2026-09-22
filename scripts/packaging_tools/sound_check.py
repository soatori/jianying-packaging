"""Validate packaging sound choices without selecting semantic sounds."""

from __future__ import annotations

from typing import Any

from .result import result


def _interval(item: dict[str, Any]) -> tuple[int, int] | None:
    start = item.get("start_us", item.get("target_start_us"))
    end = item.get("end_us", item.get("target_end_us"))
    if end is None and isinstance(start, int) and isinstance(item.get("duration_us"), int):
        end = start + item["duration_us"]
    if isinstance(start, int) and not isinstance(start, bool) and isinstance(end, int) and not isinstance(end, bool) and start >= 0 and end > start:
        return start, end
    return None


def _audio_evidence(value: Any) -> tuple[list[dict[str, Any]], bool]:
    """Normalize explicit dialogue/audio evidence without inventing intervals."""
    if value is None:
        return [], False
    if isinstance(value, list):
        rows = [item for item in value if isinstance(item, dict)]
        dialogue = any(str(item.get("kind", item.get("type", item.get("track_type", item.get("role", ""))))).lower() in {"dialogue", "voice", "speech", "spoken"} for item in rows)
        return rows, dialogue
    if not isinstance(value, dict):
        return [], False
    rows: list[dict[str, Any]] = []
    dialogue_evidence = False
    for key in ("sounds", "audio", "events", "dialogue", "dialogue_intervals", "voice_intervals", "speech_intervals"):
        if key not in value:
            continue
        raw = value.get(key)
        if isinstance(raw, list):
            if key in {"dialogue", "dialogue_intervals", "voice_intervals", "speech_intervals"}:
                dialogue_evidence = True
            for item in raw:
                if isinstance(item, dict):
                    row = dict(item)
                    if key in {"dialogue", "dialogue_intervals", "voice_intervals", "speech_intervals"}:
                        row.setdefault("kind", "dialogue")
                        dialogue_evidence = True
                    elif str(row.get("kind", row.get("type", row.get("track_type", row.get("role", ""))))).lower() in {"dialogue", "voice", "speech", "spoken"}:
                        dialogue_evidence = True
                    rows.append(row)
    return rows, dialogue_evidence


def check_sound_operations(plan: Any, catalog: Any, pools: Any, existing_audio: Any = None) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return result("packaging_sound_check", errors=["plan must be a JSON object"])
    catalog_records = {
        str(item.get("preset_id")): item
        for item in (catalog or {}).get("presets", [])
        if isinstance(item, dict) and item.get("preset_id")
    } if isinstance(catalog, dict) else {}
    catalog_ids = set(catalog_records)
    pool_map = {str(item.get("pool_id")): item for item in (pools or {}).get("pools", []) if isinstance(item, dict)} if isinstance(pools, dict) else {}
    errors: list[str] = []
    warnings: list[str] = []
    execution = plan.get("execution", {}) if isinstance(plan.get("execution"), dict) else {}
    final_or_apply = execution.get("phase") == "final" or execution.get("mode") == "apply"
    checks: list[dict[str, Any]] = []
    selected_counts: dict[str, int] = {}
    sound_selection = plan.get("sound_selection", {}) if isinstance(plan.get("sound_selection"), dict) else {}
    reuse_cap = sound_selection.get("reuse_cap", 3)
    if not isinstance(reuse_cap, int) or reuse_cap <= 0:
        reuse_cap = 3
    groups = plan.get("groups")
    if not isinstance(groups, list):
        return result("packaging_sound_check", errors=["plan.groups must be an array"])

    def report_gate(message: str, *, final_only: bool = False) -> None:
        if final_or_apply or not final_only:
            errors.append(message)
        else:
            warnings.append(message)

    for group in groups:
        if not isinstance(group, dict):
            continue
        audio = group.get("audio") or group.get("sound") or {}
        if not isinstance(audio, dict) or audio.get("action") in (None, "none"):
            continue
        pool_id = str(audio.get("candidate_pool_ref", ""))
        pool = pool_map.get(pool_id)
        selected = str(audio.get("selected_preset_id", ""))
        if not selected:
            report_gate(f"group {group.get('id')}: selected_preset_id is required for a sound operation", final_only=True)
        if pool is None:
            errors.append(f"group {group.get('id')}: unknown candidate pool {pool_id!r}")
        else:
            candidates = pool.get("candidates", []) or []
            if not isinstance(candidates, list):
                errors.append(f"group {group.get('id')}: candidate pool candidates must be an array")
                candidates = []
            for index, candidate_item in enumerate(candidates):
                if not isinstance(candidate_item, dict) or not candidate_item.get("preset_id"):
                    errors.append(f"group {group.get('id')}: candidate pool candidate[{index}] must contain preset_id")
            candidate_ids = {str(item.get("preset_id")) for item in candidates if isinstance(item, dict) and item.get("preset_id")}
            if len(candidate_ids) != len([item for item in candidates if isinstance(item, dict) and item.get("preset_id")]):
                errors.append(f"group {group.get('id')}: candidate pool contains duplicate preset IDs")
            minimum = pool.get("min_candidates", 3)
            if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
                errors.append(f"group {group.get('id')}: candidate pool min_candidates is invalid")
                minimum = 0
            if len(candidate_ids) < minimum or not candidate_ids:
                message = f"group {group.get('id')}: candidate_pool_incomplete"
                (errors if final_or_apply else warnings).append(message)
            if pool.get("status") not in {None, "verified"}:
                report_gate(f"group {group.get('id')}: candidate pool is not verified", final_only=True)
            if selected and selected not in candidate_ids:
                errors.append(f"group {group.get('id')}: selected preset {selected!r} is absent from candidate pool")
            if selected:
                candidate = next((item for item in candidates if isinstance(item, dict) and str(item.get("preset_id")) == selected), None)
                if candidate is not None and candidate.get("status") != "verified":
                    report_gate(f"group {group.get('id')}: selected candidate {selected!r} is not verified", final_only=True)
                pool_family = pool.get("motion_family")
                audio_family = audio.get("motion_family")
                candidate_family = candidate.get("motion_family") if isinstance(candidate, dict) else None
                if pool_family and audio_family and pool_family != audio_family:
                    errors.append(f"group {group.get('id')}: audio motion_family does not match candidate pool")
                if candidate_family and audio_family and candidate_family != audio_family:
                    errors.append(f"group {group.get('id')}: selected candidate motion_family does not match audio")
                candidate_form = candidate.get("sound_form") if isinstance(candidate, dict) else None
                if candidate_form and audio.get("sound_form") and candidate_form != audio.get("sound_form"):
                    errors.append(f"group {group.get('id')}: selected candidate sound_form does not match audio")
        if selected and selected not in catalog_ids:
            errors.append(f"group {group.get('id')}: selected preset {selected!r} is absent from catalog")
        if selected:
            selected_counts[selected] = selected_counts.get(selected, 0) + 1
            catalog_record = catalog_records.get(selected)
            if catalog_record is not None:
                if catalog_record.get("status") != "verified":
                    report_gate(f"group {group.get('id')}: selected catalog preset is not verified", final_only=True)
                if catalog_record.get("sound_form") and audio.get("sound_form") and catalog_record["sound_form"] != audio["sound_form"]:
                    errors.append(f"group {group.get('id')}: sound_form does not match catalog")
                if catalog_record.get("motion_family") and audio.get("motion_family") and catalog_record["motion_family"] != audio["motion_family"]:
                    errors.append(f"group {group.get('id')}: motion_family does not match catalog")
        sound_form = audio.get("sound_form")
        trim_policy = audio.get("trim_policy")
        expected_trim = None
        if sound_form in {"single_hit", "decay"}:
            expected_trim = "text_span"
        elif sound_form in {"multi_hit", "typing"}:
            expected_trim = "motion_span"
        if expected_trim and trim_policy is None:
            report_gate(f"group {group.get('id')}: {sound_form} requires an explicit {expected_trim} trim policy", final_only=True)
        elif expected_trim and trim_policy != expected_trim:
            errors.append(f"group {group.get('id')}: {sound_form} must use {expected_trim} trim")
        leading_policy = audio.get("leading_silence_policy")
        catalog_leading = catalog_records.get(selected, {}).get("leading_silence_us", 0) if selected else 0
        leading_silence = audio.get("leading_silence_us", catalog_leading or 0)
        source_range = _interval(audio.get("source_range", {})) if isinstance(audio.get("source_range"), dict) else None
        if "source_range" in audio and source_range is None:
            errors.append(f"group {group.get('id')}: source_range is invalid")
        if not isinstance(leading_silence, int) or isinstance(leading_silence, bool) or leading_silence < 0:
            errors.append(f"group {group.get('id')}: leading_silence_us must be a non-negative integer")
            leading_silence = 0
        catalog_duration = catalog_records.get(selected, {}).get("duration_us") if selected else None
        if source_range is not None and isinstance(catalog_duration, int) and source_range[1] > catalog_duration:
            errors.append(f"group {group.get('id')}: source_range exceeds catalog duration")
        if leading_silence and leading_policy not in {"skip", "preserve", "manual_review"}:
            report_gate(f"group {group.get('id')}: known leading silence requires an explicit policy", final_only=True)
        if leading_silence and leading_policy == "manual_review":
            report_gate(f"group {group.get('id')}: leading silence policy remains manual_review", final_only=True)
        if leading_policy in {"skip", "preserve"} and leading_silence:
            if source_range is None:
                report_gate(f"group {group.get('id')}: known leading silence requires an explicit source_range", final_only=True)
            elif leading_policy == "skip" and source_range[0] < leading_silence:
                errors.append(f"group {group.get('id')}: source_range starts before skipped leading silence")
            elif leading_policy == "preserve" and not audio.get("override_reason"):
                report_gate(f"group {group.get('id')}: preserving leading silence requires override_reason", final_only=True)
        text_span = _interval(audio.get("text_range", {})) if isinstance(audio.get("text_range"), dict) else None
        if "text_range" in audio and text_span is None:
            errors.append(f"group {group.get('id')}: text_range is invalid")
        motion_event = group.get("motion_event") if isinstance(group.get("motion_event"), dict) else {}
        motion_span = _interval(motion_event)
        if group.get("motion_event") is not None and motion_span is None:
            errors.append(f"group {group.get('id')}: motion_event range is invalid")
        target_span = _interval(audio.get("target_range", {})) if isinstance(audio.get("target_range"), dict) else None
        if "target_range" in audio and target_span is None:
            errors.append(f"group {group.get('id')}: target_range is invalid")
        expected_span = text_span if trim_policy == "text_span" else motion_span if trim_policy == "motion_span" else None
        if trim_policy in {"text_span", "motion_span"}:
            if expected_span is None or target_span is None:
                report_gate(f"group {group.get('id')}: {trim_policy} requires complete source and target ranges")
            elif target_span != expected_span:
                errors.append(f"group {group.get('id')}: target_range does not match {trim_policy}")
        checks.append({"group_id": group.get("id"), "pool_id": pool_id, "selected_preset_id": selected})

    for preset_id, count in selected_counts.items():
        if count > reuse_cap:
            errors.append(f"preset {preset_id!r} is selected {count} times; reuse cap is {reuse_cap}")

    audio_rows, dialogue_evidence_present = _audio_evidence(existing_audio)
    intervals = []
    for item in audio_rows:
        span = _interval(item)
        if span:
            intervals.append((item, span))
    active_audio_groups: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        audio = group.get("audio") or group.get("sound") or {}
        if not isinstance(audio, dict) or audio.get("action") in (None, "none"):
            continue
        active_audio_groups.append(group)
        event = group.get("motion_event") or {}
        event_span = _interval(event) if isinstance(event, dict) else None
        sound_span = _interval(audio.get("target_range", {})) if isinstance(audio.get("target_range"), dict) else event_span
        if sound_span is None:
            report_gate(f"group {group.get('id')}: sound interval is unresolved", final_only=True)
            continue
        start, end = sound_span
        for item, span in intervals:
            kind = str(item.get("kind", item.get("type", item.get("track_type", item.get("role", ""))))).lower()
            if kind in {"dialogue", "voice", "speech", "spoken"}:
                dialogue_evidence_present = True
                if span[0] < end and start < span[1]:
                    report_gate(f"group {group.get('id')}: sound overlaps dialogue interval ({item.get('id')})", final_only=True)
            elif abs(span[0] - start) <= 40000 and span[1] > start:
                warnings.append(f"group {group.get('id')}: existing audio event is within 40ms of the motion start ({item.get('id')})")
    if final_or_apply and active_audio_groups and not dialogue_evidence_present:
        errors.append("dialogue evidence is required for final/apply sound collision checks")
    return result("packaging_sound_check", data={"checks": checks}, errors=errors, warnings=warnings, summary={"checked_groups": len(checks)})
