"""Read-only field tools added after the 2026-10 packaging review.

The five commands here close gaps that the 2026-10 vertical interview case
exposed. None of them writes a draft: writes still go through
``prepare``/``commit``, so the skill keeps its "prepare never writes" invariant.

* ``build_animation_inventory_report`` – P2/P14/P15  bounded animation discovery
* ``validate_capabilities``            – P14/P15     exact capability tokens
* ``harvest_catalog``                  – P1          bounded asset harvesting
* ``expand_plan``                      – P3/P5       batch animation / music expansion
* ``build_layer_audit``                – P5–P8/P10/P16/P17  layer + mix audit
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from packaging_tools.result import result

#: ``--animation-capabilities`` 里唯一被接受的状态字面值。
VERIFIED_STATUS = "visually_verified"
#: 只有纯文本对象可以复用已验证的入场动画。
VERIFIED_TARGET_KIND = "plain_text"
#: 三层混音默认带宽（人声 / 音效 / 音乐）。
MIX_BANDS = {
    "dialogue": (0.90, 1.00),
    "sfx": (0.45, 0.55),
    "music": (0.35, 0.45),
}
MUSIC_FADE_IN_US = 1_000_000
MUSIC_FADE_OUT_US = 3_000_000
TRANSITION_MAX_US = 600_000
LINE_LIMIT_DEFAULT = 13
STRIP_PUNCTUATION = "。，、；：…—～·"


def _compact(value: Any, limit: int = 60) -> str:
    text = str(value if value is not None else "")
    return text[:limit]


def _materials(observation: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(observation, dict):
        return []
    materials = observation.get("materials")
    if not isinstance(materials, dict):
        return []
    value = materials.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _tracks(observation: Any) -> list[dict[str, Any]]:
    if not isinstance(observation, dict):
        return []
    value = observation.get("tracks")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _timerange(segment: dict[str, Any], prefix: str = "target") -> tuple[int, int]:
    block = segment.get(f"{prefix}_timerange")
    if isinstance(block, dict):
        start = int(block.get("start", 0) or 0)
        duration = int(block.get("duration", 0) or 0)
        return start, start + duration
    start = segment.get(f"{prefix}_start_us")
    if isinstance(start, int):
        duration = segment.get(f"{prefix}_duration_us")
        if isinstance(duration, int):
            return start, start + duration
    return 0, 0


def _text_len(value: str) -> int:
    return len(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", value or ""))


# --------------------------------------------------------------------------
# P2/P14/P15 — animation inventory
# --------------------------------------------------------------------------
def build_animation_inventory_report(
    cache_root: str | None,
    enum_entries: list[dict[str, Any]] | None,
    *,
    jianying_version: str | None,
    capabilities: Any = None,
    observations: list[Any] | None = None,
    keywords: str = "",
) -> dict[str, Any]:
    """列出本机可用的文字入场动画，并把候选标成 ``unverified``。

    与 ``prepare`` 不同，这里**不会**把任何条目升格成 ``visually_verified``：
    候选必须由人复开确认后才写进 capabilities 文件。
    """
    tokens = [item.strip() for item in keywords.split(",") if item.strip()]
    observed: dict[str, dict[str, Any]] = {}
    scanned: list[str] = []
    for observation in observations or []:
        if not isinstance(observation, dict):
            continue
        timeline = observation.get("timeline_id") or observation.get("name")
        if timeline:
            scanned.append(str(timeline))
        for block in _materials(observation, "material_animations"):
            for item in block.get("animations") or []:
                if not isinstance(item, dict):
                    continue
                resource_id = str(item.get("resource_id") or "")
                if not resource_id:
                    continue
                record = observed.setdefault(
                    resource_id,
                    {
                        "resource_id": resource_id,
                        "effect_id": item.get("id"),
                        "name": item.get("name"),
                        "md5": item.get("md5"),
                        "default_duration_us": item.get("duration"),
                        "cache_path": item.get("path"),
                        "material_type": item.get("material_type"),
                        "type": item.get("type"),
                        "observed_in": [],
                    },
                )
                record["observed_in"].append(str(timeline))
    entries: list[dict[str, Any]] = []
    for entry in enum_entries or []:
        if not isinstance(entry, dict):
            continue
        resource_id = str(entry.get("resource_id") or "")
        if not resource_id:
            continue
        entries.append(
            {
                "resource_id": resource_id,
                "effect_id": entry.get("effect_id") or entry.get("id"),
                "name": entry.get("name"),
                "md5": entry.get("md5"),
                "default_duration_us": entry.get("duration_us") or entry.get("duration"),
                "cache_path": entry.get("cache_path") or entry.get("path"),
                "render_type": entry.get("render_type"),
                "required_inputs": entry.get("required_inputs"),
                "native_verified": None,
                "compatible_plain_text": None,
                "observed_in": sorted(set(observed.pop(resource_id, {}).get("observed_in", []))),
            }
        )
    for record in observed.values():
        record["observed_in"] = sorted(set(record["observed_in"]))
        record["render_type"] = None
        record["required_inputs"] = None
        record["native_verified"] = None
        record["compatible_plain_text"] = None
        entries.append(record)
    if tokens:
        entries = [
            entry
            for entry in entries
            if any(token.lower() in str(entry.get("name") or "").lower() for token in tokens)
        ]
    warnings: list[str] = []
    if not jianying_version:
        warnings.append("current Jianying version was not supplied; capability matching cannot be checked")
    if cache_root and not os.path.isdir(str(cache_root)):
        warnings.append(f"animation cache root does not exist: {cache_root}")
    if capabilities is not None:
        cap_version = capabilities.get("jianying_version") if isinstance(capabilities, dict) else None
        if jianying_version and cap_version != jianying_version:
            warnings.append(
                f"capability version {cap_version!r} does not match current Jianying {jianying_version!r}"
            )
    verified = {
        str(item.get("resource_id"))
        for item in (capabilities or {}).get("verified", [])
        if isinstance(item, dict) and item.get("status") == VERIFIED_STATUS
    } if isinstance(capabilities, dict) else set()
    for entry in entries:
        entry["native_verified"] = entry["resource_id"] in verified
        entry["compatible_plain_text"] = entry["native_verified"]
    candidates = [
        {
            "resource_id": entry["resource_id"],
            "md5": entry.get("md5"),
            "target_kind": VERIFIED_TARGET_KIND,
            "status": "unverified",
            "suggested_verification": "reopen_and_review",
        }
        for entry in entries
        if not entry["native_verified"]
    ]
    if not entries:
        warnings.append("no animation entries matched; supply --enum or a reference-draft observation")
    return result(
        "packaging_animation_inventory",
        data={
            "entries": entries,
            "candidates_for_capabilities": candidates,
            "provenance": {"reference_timelines": scanned, "keyword_filter": tokens},
        },
        warnings=warnings,
        summary={"entry_count": len(entries), "candidate_count": len(candidates)},
    )


# --------------------------------------------------------------------------
# P14/P15 — capability file validation
# --------------------------------------------------------------------------
def validate_capabilities(payload: Any, *, current_version: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return result("packaging_capability_validation", errors=["capabilities file must be a JSON object"])
    version = payload.get("jianying_version")
    if not isinstance(version, str) or not version.strip():
        errors.append("jianying_version: required string")
    elif current_version and version != current_version:
        errors.append(f"jianying_version: must equal current Jianying version {current_version!r}, got {version!r}")
    verified = payload.get("verified")
    if not isinstance(verified, list):
        errors.append("verified: required array")
        verified = []
    for index, item in enumerate(verified):
        path = f"verified[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{path}: must be an object")
            continue
        resource_id = item.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id:
            errors.append(f"{path}.resource_id: required string")
        md5 = item.get("md5")
        if not isinstance(md5, str) or not md5:
            errors.append(f"{path}.md5: required string")
        target_kind = item.get("target_kind")
        if target_kind != VERIFIED_TARGET_KIND:
            errors.append(
                f"{path}.target_kind: expected {VERIFIED_TARGET_KIND!r}, got {_compact(target_kind)!r}"
            )
        status = item.get("status")
        if status != VERIFIED_STATUS:
            errors.append(
                f"{path}.status: expected {VERIFIED_STATUS!r}, got {_compact(status)!r}"
            )
        required = item.get("required_inputs")
        if required is not None and not isinstance(required, list):
            errors.append(f"{path}.required_inputs: must be an array when present")
        elif isinstance(required, list) and required:
            warnings.append(
                f"{path}.required_inputs is not empty; the entry cannot be used for plain text"
            )
    return result(
        "packaging_capability_validation",
        data={
            "jianying_version": version,
            "verified_count": len(verified),
            "errors": errors,
            "warnings": warnings,
            "expected_status_token": VERIFIED_STATUS,
            "expected_target_kind": VERIFIED_TARGET_KIND,
        },
        summary={"verified_count": len(verified)},
    )


# --------------------------------------------------------------------------
# P1 — bounded catalog harvesting
# --------------------------------------------------------------------------
def harvest_catalog(
    observations: list[Any] | None,
    *,
    kinds: str = "both",
    max_items: int = 200,
    note: str | None = None,
    cache_root: str | None = None,
) -> dict[str, Any]:
    if not observations:
        return result(
            "packaging_catalog_harvest",
            errors=["at least one explicit reference observation is required"],
        )
    if len(observations) > 5:
        return result(
            "packaging_catalog_harvest",
            errors=["at most 5 reference observations may be supplied"],
        )
    want_sound = kinds in {"sound", "both"}
    want_animation = kinds in {"animation", "both"}
    items: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    scanned: list[str] = []
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        timeline = str(observation.get("timeline_id") or observation.get("name") or "")
        scanned.append(timeline)
        if want_sound:
            for audio in _materials(observation, "audios"):
                if audio.get("type") not in {"sound", None}:
                    continue
                items.append(
                    {
                        "kind": "sound",
                        "preset_id": audio.get("effect_id") or audio.get("id"),
                        "name": audio.get("name"),
                        "duration_us": audio.get("duration"),
                        "path": audio.get("path"),
                        "source": "timeline",
                        "observed_in": timeline,
                        "leading_silence_us": None,
                        "status": "unverified",
                    }
                )
        if want_animation:
            for block in _materials(observation, "material_animations"):
                for item in block.get("animations") or []:
                    if not isinstance(item, dict):
                        continue
                    items.append(
                        {
                            "kind": "animation",
                            "resource_id": item.get("resource_id"),
                            "name": item.get("name"),
                            "duration_us": item.get("duration"),
                            "path": item.get("path"),
                            "source": "timeline",
                            "observed_in": timeline,
                            "leading_silence_us": None,
                            "status": "unverified",
                        }
                    )
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = (item["kind"], str(item.get("preset_id") or item.get("resource_id")))
        if key in seen:
            continue
        seen.add(key)
        if len(unique) >= max_items:
            dropped.append({"reason": "over_max_items", "key": key[1]})
            continue
        unique.append(item)
    warnings = [
        "Leading silence is reported as null; measure it with ffmpeg before placing any sound.",
        "Every harvested item stays unverified until it is reviewed on a reopened project.",
    ]
    if not cache_root:
        warnings.append("no cache root was supplied; harvested paths were not checked against the local cache")
    return result(
        "packaging_catalog_harvest",
        data={
            "items": unique,
            "dropped": dropped,
            "provenance": {
                "timelines_scanned": scanned,
                "max_items": max_items,
                "note": note,
                "bounded": True,
            },
        },
        warnings=warnings,
        summary={"item_count": len(unique), "dropped_count": len(dropped)},
    )


# --------------------------------------------------------------------------
# P3/P5 — plan expansion (batch animation, music injection)
# --------------------------------------------------------------------------
def expand_plan(
    plan: Any,
    *,
    animation_resource_id: str | None = None,
    duration_mode: str = "head_follow",
    head_us: int = 400_000,
    follow_us: int = 240_000,
    explicit_us: int | None = None,
    clamp_to_row: bool = True,
    motion_role: str = "uniform_entry",
) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return result("packaging_plan_expansion", errors=["plan must be an object"])
    groups = plan.get("groups")
    if not isinstance(groups, list):
        return result("packaging_plan_expansion", errors=["plan.groups must be an array"])
    expanded = json.loads(json.dumps(plan))
    added: list[dict[str, Any]] = []
    clamped: list[dict[str, Any]] = []
    unexpanded: list[dict[str, Any]] = []
    for group_index, group in enumerate(expanded.get("groups") or []):
        if not isinstance(group, dict):
            continue
        visuals = group.get("visual") or group.get("visuals") or []
        if not isinstance(visuals, list):
            continue
        for visual_index, visual in enumerate(visuals):
            if not isinstance(visual, dict):
                continue
            animation = visual.get("animation")
            resource_id = animation_resource_id
            requested = None
            if isinstance(animation, dict):
                resource_id = animation.get("resource_id") or resource_id
                requested = animation.get("duration_us")
            if not resource_id:
                continue
            if isinstance(animation, dict) and isinstance(requested, int) and requested > 0:
                continue
            if explicit_us:
                target_duration = explicit_us
            else:
                target_duration = head_us if visual_index == 0 else follow_us
            row_window = visual.get("duration_us")
            if not isinstance(row_window, int) or row_window <= 0:
                row_window = group.get("row_duration_us")
            note = None
            if clamp_to_row and isinstance(row_window, int) and row_window > 0:
                applied = min(target_duration, row_window)
                if applied != target_duration:
                    note = "clamped_to_row"
            else:
                applied = target_duration
            if applied <= 0:
                unexpanded.append(
                    {
                        "group_index": group_index,
                        "visual_index": visual_index,
                        "reason": "row window unknown",
                    }
                )
                continue
            visual["animation"] = {"resource_id": resource_id, "duration_us": applied}
            if motion_role:
                visual["motion_role"] = motion_role
            added.append(
                {
                    "group_index": group_index,
                    "visual_index": visual_index,
                    "resource_id": resource_id,
                    "applied_us": applied,
                    "requested_us": target_duration,
                }
            )
            if note:
                clamped.append(
                    {
                        "group_index": group_index,
                        "visual_index": visual_index,
                        "requested_us": target_duration,
                        "applied_us": applied,
                        "reason": note,
                    }
                )
    warnings = []
    if not added:
        warnings.append("no visual carried an animation reference; nothing to expand")
    if clamped:
        warnings.append(f"{len(clamped)} animation durations were clamped to the visible row window")
    return result(
        "packaging_plan_expansion",
        data={
            "expanded_plan": expanded,
            "report": {
                "visuals_added": len(added),
                "added": added,
                "clamped": clamped,
                "unexpanded": unexpanded,
                "duration_mode": duration_mode,
                "clamp_to_row": clamp_to_row,
            },
        },
        warnings=warnings,
        summary={"visuals_added": len(added), "clamped": len(clamped)},
    )


# --------------------------------------------------------------------------
# P5–P8/P10/P16/P17 — layer and mix audit
# --------------------------------------------------------------------------
def build_layer_audit(
    observation: Any,
    *,
    kinds: str = "music,transition,overlay,effect,text_animation",
    music_vol: tuple[float, float] = MIX_BANDS["music"],
    sfx_vol: tuple[float, float] = MIX_BANDS["sfx"],
    dialogue_vol: tuple[float, float] = MIX_BANDS["dialogue"],
    transition_max_us: int = TRANSITION_MAX_US,
    max_chars_per_line: int = LINE_LIMIT_DEFAULT,
) -> dict[str, Any]:
    if not isinstance(observation, dict):
        return result("packaging_layer_audit", errors=["observation must be an object"])
    wanted = {item.strip() for item in kinds.split(",") if item.strip()}
    audios = {str(item.get("id")): item for item in _materials(observation, "audios")}
    texts = {str(item.get("id")): item for item in _materials(observation, "texts")}
    animations = {str(item.get("id")): item for item in _materials(observation, "material_animations")}
    fades = {str(item.get("id")): item for item in _materials(observation, "audio_fades")}
    violations: list[dict[str, Any]] = []
    music: list[dict[str, Any]] = []
    sfx: list[dict[str, Any]] = []
    overlays: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    text_rows: list[dict[str, Any]] = []
    animated_rows = 0
    dialogue_us = 0
    music_us = 0
    sfx_us = 0
    for track_index, track in enumerate(_tracks(observation)):
        kind = track.get("type")
        segments = track.get("segments") or []
        # 只有主视频轨自带人声；第二视频轨是画中画，不重复计入对白
        if kind == "video" and track_index == 0:
            for segment in segments:
                if isinstance(segment, dict):
                    start, end = _timerange(segment)
                    dialogue_us += max(0, end - start)
        if kind == "video" and track_index > 0:
            overlays.append(
                {
                    "track_id": track.get("id"),
                    "track_index": track_index,
                    "segment_count": len(segments),
                    "duration_us": sum(_timerange(seg)[1] - _timerange(seg)[0] for seg in segments),
                }
            )
        if kind == "audio":
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                start, end = _timerange(segment)
                duration = end - start
                material = audios.get(str(segment.get("material_id")), {})
                volume = segment.get("volume")
                if not isinstance(volume, (int, float)):
                    volume = material.get("volume")
                if not isinstance(volume, (int, float)):
                    volume = 1.0
                fade_ids = [ref for ref in segment.get("extra_material_refs") or [] if ref in fades]
                fade = fades.get(fade_ids[0], {}) if fade_ids else {}
                fade_in = int(fade.get("fade_in_duration") or 0)
                fade_out = int(fade.get("fade_out_duration") or 0)
                material_type = material.get("type")
                record = {
                    "track_id": track.get("id"),
                    "material_type": material_type,
                    "name": material.get("name"),
                    "start_us": start,
                    "end_us": end,
                    "volume": volume,
                    "fade_in_us": fade_in,
                    "fade_out_us": fade_out,
                }
                if material_type == "music":
                    music.append(record)
                    music_us += duration
                    low, high = music_vol
                    if not isinstance(volume, (int, float)) or not (low <= volume <= high):
                        violations.append(
                            {
                                "rule": "music_volume_band",
                                "observed": volume,
                                "expected": f"{low}-{high}",
                                "severity": "block",
                            }
                        )
                    if fade_in <= 0 or fade_out <= 0:
                        violations.append(
                            {
                                "rule": "music_requires_fade",
                                "observed": {"fade_in_us": fade_in, "fade_out_us": fade_out},
                                "expected": {"fade_in_us": MUSIC_FADE_IN_US, "fade_out_us": MUSIC_FADE_OUT_US},
                                "severity": "block",
                            }
                        )
                elif material_type == "sound":
                    sfx.append(record)
                    sfx_us += duration
                    low, high = sfx_vol
                    if not isinstance(volume, (int, float)) or not (low <= volume <= high):
                        violations.append(
                            {
                                "rule": "sfx_volume_band",
                                "observed": volume,
                                "expected": f"{low}-{high}",
                                "severity": "warning",
                            }
                        )
                else:
                    dialogue_us += duration
                    low, high = dialogue_vol
                    if isinstance(volume, (int, float)) and volume < low:
                        violations.append(
                            {
                                "rule": "dialogue_volume_band",
                                "observed": volume,
                                "expected": f"{low}-{high}",
                                "severity": "warning",
                            }
                        )
        if kind == "text":
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                if segment.get("visible") is False:
                    continue
                start, end = _timerange(segment)
                content = texts.get(str(segment.get("material_id")), {})
                raw = content.get("content") or ""
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    parsed = {}
                text = parsed.get("text") if isinstance(parsed, dict) else ""
                text = text or content.get("recognize_text") or ""
                has_animation = any(
                    (animations.get(ref) or {}).get("animations")
                    for ref in segment.get("extra_material_refs") or []
                )
                if has_animation:
                    animated_rows += 1
                lengths = [_text_len(line) for line in str(text).split("\n") if line.strip()]
                over = [length for length in lengths if length > max_chars_per_line]
                punctuation = [ch for ch in str(text) if ch in STRIP_PUNCTUATION]
                if over:
                    violations.append(
                        {
                            "rule": "line_width_limit",
                            "observed": {"text": str(text)[:40], "lengths": lengths},
                            "expected": f"<= {max_chars_per_line}",
                            "severity": "block",
                        }
                    )
                if punctuation:
                    violations.append(
                        {
                            "rule": "punctuation_stripped",
                            "observed": "".join(punctuation),
                            "expected": "none",
                            "severity": "warning",
                        }
                    )
                text_rows.append(
                    {
                        "start_us": start,
                        "end_us": end,
                        "text": str(text)[:40],
                        "line_lengths": lengths,
                        "animated": bool(has_animation),
                    }
                )
    if "transition" in wanted:
        for item in _materials(observation, "transitions"):
            duration = int(item.get("duration") or 0)
            transitions.append(
                {
                    "name": item.get("name"),
                    "duration_us": duration,
                    "is_overlap": item.get("is_overlap"),
                }
            )
            if duration > transition_max_us:
                violations.append(
                    {
                        "rule": "transition_duration_cap",
                        "observed": duration,
                        "expected": f"<= {transition_max_us}",
                        "severity": "warning",
                    }
                )
    effects = _materials(observation, "effects")
    timeline_duration = observation.get("duration_us") or 0
    coverage = {
        "dialogue_us": dialogue_us,
        "music_us": music_us,
        "sfx_us": sfx_us,
        "dialogue_ratio": round(min(1.0, dialogue_us / timeline_duration), 4) if timeline_duration else None,
    }
    # 同类违规聚合成一条，避免 48 段音效刷出 48 条告警
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in violations:
        key = (str(item.get("rule")), str(item.get("severity")))
        bucket = grouped.setdefault(
            key,
            {
                "rule": item.get("rule"),
                "severity": item.get("severity"),
                "count": 0,
                "expected": item.get("expected"),
                "samples": [],
            },
        )
        bucket["count"] += 1
        if len(bucket["samples"]) < 3:
            bucket["samples"].append(item.get("observed"))
    aggregated = list(grouped.values())
    blocking = [item for item in aggregated if item.get("severity") == "block"]
    if blocking:
        warnings_note = f"{len(blocking)} blocking mix/layout violations"
    else:
        warnings_note = None
    return result(
        "packaging_layer_audit",
        data={
            "music": music if "music" in wanted else [],
            "sfx": {"count": len(sfx), "duration_us": sfx_us},
            "transitions": transitions,
            "overlays": overlays if "overlay" in wanted else [],
            "effects": {"count": len(effects)},
            "text": {
                "rows": len(text_rows),
                "animated_rows": animated_rows,
                "sample": text_rows[:20],
            },
            "coverage": coverage,
            "mix_violations": aggregated,
            "violation_total": len(violations),
            "bands": {
                "dialogue": list(dialogue_vol),
                "sfx": list(sfx_vol),
                "music": list(music_vol),
            },
            "limits": {
                "transition_max_us": transition_max_us,
                "max_chars_per_line": max_chars_per_line,
            },
        },
        warnings=[warnings_note] if warnings_note else [],
        summary={
            "music_count": len(music),
            "transition_count": len(transitions),
            "overlay_count": len(overlays),
            "effect_count": len(effects),
            "text_rows": len(text_rows),
            "violation_count": len(violations),
        },
    )


