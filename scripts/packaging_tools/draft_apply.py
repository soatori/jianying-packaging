"""Schema 1.2 packaging-plan adapter for existing Jianying drafts."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from .animation_inventory import resolve_text_animation
from .animation_inventory import build_animation_inventory
from .layout_resolver import resolve_relative_layout
from .override_contract import DIRECT_OVERRIDE_FIELDS
from .replica_audit import classify_replica_errors
from .result import result
from .sound_check import check_sound_operations
from .subtitle_resolver import resolve_subtitle_anchor, resolve_text_hashes
from .validators.plan import validate_plan
from .visual_preview import VisualPreviewError, build_html_preview, fit_slots_to_safe_zone, measure_text_lines


_NEW_VISUAL = {"clone_template", "copy_from_subtitle", "add_overlay"}
_EXISTING_VISUAL = {"modify_text", "modify_segment", "disable_original"}
_VISUAL_OPS = _NEW_VISUAL | _EXISTING_VISUAL | {"none"}
_AUDIO_ACTIONS = {"none", "reuse_existing", "clone_asset", "add_asset"}


class DraftApplyError(ValueError):
    """A packaging operation cannot be translated safely to this draft."""


def _append_warnings(target: list[str], source: Any) -> None:
    values = [source] if isinstance(source, str) else source if isinstance(source, list) else []
    for value in values:
        warning = str(value)
        if warning and warning not in target:
            target.append(warning)


def _text_intro_entries() -> list[Any]:
    try:
        from pyJianYingDraft import TextIntro
    except ImportError as exc:
        raise DraftApplyError("pyJianYingDraft.TextIntro is unavailable; animation apply is blocked") from exc
    return list(TextIntro)


def _animation_cache_root(draft_root: Path, explicit: str | Path | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if root.name.casefold() == "effect":
            root = root.parent
        if not (root / "effect").is_dir():
            raise DraftApplyError(f"animation cache root has no effect directory: {root}")
        return root

    candidates: set[Path] = set()
    for ancestor in (draft_root, *draft_root.parents):
        for candidate in (ancestor / "User Data" / "Cache", ancestor / "Cache"):
            if (candidate / "effect").is_dir():
                candidates.add(candidate.resolve())
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "JianyingPro" / "User Data" / "Cache"
        if (candidate / "effect").is_dir():
            candidates.add(candidate.resolve())
    if len(candidates) != 1:
        detail = "no" if not candidates else "multiple"
        raise DraftApplyError(f"{detail} Jianying animation cache roots resolved; pass --animation-cache-root")
    return next(iter(candidates))


def _animation_version(project: Any, explicit: str | None) -> str:
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    try:
        crypto = getattr(project, "crypto")
        version = getattr(crypto, "jianying_version", None)
    except (AttributeError, RuntimeError, OSError):
        version = None
    if isinstance(version, str) and version.strip():
        return version.strip()
    raise DraftApplyError("current Jianying version is unresolved; pass --animation-version")


def _write_temp_json(root: Path, category: str, value: dict[str, Any]) -> str:
    run_dir = root / category / uuid.uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=False)
    path = run_dir / "inventory.json"
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _write_temp_html(root: Path, category: str, value: str) -> str:
    run_dir = root / category / uuid.uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=False)
    path = run_dir / "preview.html"
    path.write_text(value, encoding="utf-8")
    return str(path)


def _default_temp_root() -> Path:
    return Path(__file__).resolve().parents[2] / "temp"


def _requires_visual_preview(plan: dict[str, Any]) -> bool:
    geometry_fields = {"position_x", "position_y", "uniform_scale", "scale_x", "scale_y", "rotation", "global_alpha"}
    phase = plan.get("execution", {}).get("phase") if isinstance(plan.get("execution"), dict) else None
    for group in plan.get("groups", []) if isinstance(plan.get("groups"), list) else []:
        if not isinstance(group, dict):
            continue
        layout = group.get("layout")
        if phase == "final" and isinstance(layout, dict) and isinstance(layout.get("slots"), list) and layout["slots"]:
            return True
        for visual in group.get("visual", []) if isinstance(group.get("visual"), list) else []:
            if not isinstance(visual, dict):
                continue
            if isinstance(visual.get("animation"), dict):
                return True
            overrides = visual.get("overrides")
            if isinstance(overrides, dict) and geometry_fields.intersection(overrides):
                return True
    return False


def _visual_preview_model(
    value: dict[str, Any],
    plan: dict[str, Any],
    operations: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]],
) -> dict[str, Any]:
    profile = plan.get("project_profile") if isinstance(plan.get("project_profile"), dict) else {}
    width, height = profile.get("canvas_width"), profile.get("canvas_height")
    if isinstance(width, bool) or not isinstance(width, int) or width <= 0 or isinstance(height, bool) or not isinstance(height, int) or height <= 0:
        raise DraftApplyError("visual preview requires project_profile canvas_width and canvas_height")
    safe_zones: list[dict[str, Any]] = []
    slots: list[dict[str, Any]] = []
    groups = {str(group.get("id", "")): group for group in plan.get("groups", []) if isinstance(group, dict)}
    tracks = {str(track.get("id", "")): track for track in value.get("tracks", []) if isinstance(track, dict)}
    zones_by_group: dict[str, dict[str, Any]] = {}
    final_phase = isinstance(plan.get("execution"), dict) and plan["execution"].get("phase") == "final"
    for group_id, group in groups.items():
        layout = group.get("layout") if isinstance(group.get("layout"), dict) else {}
        constraints = layout.get("constraints") if isinstance(layout.get("constraints"), dict) else {}
        safe_zone = constraints.get("safe_zone")
        if final_phase and isinstance(layout.get("slots"), list) and layout["slots"]:
            if not isinstance(safe_zone, dict):
                raise DraftApplyError(f"group {group_id}: numeric safe-zone bounds are required for visual preview")
        else:
            safe_zone = {"x_min": -1.0, "x_max": 1.0, "y_min": -1.0, "y_max": 1.0}
        zone_id = group_id or f"group-{len(zones_by_group) + 1}"
        zones_by_group[group_id] = {"id": zone_id, "bounds": safe_zone}
        safe_zones.append(zones_by_group[group_id])

    layout_check: dict[str, list[dict[str, Any]]] = {}
    for index, (group, visual, segment, material) in enumerate(operations):
        if visual.get("object_type") != "text" or not isinstance(material, dict):
            continue
        text = _material_text(material)
        if not isinstance(text, str) or not text:
            raise DraftApplyError(f"group {group.get('id')}: preview text has no current material text")
        lines, box_width, box_height = _measure_material_text(material, text)
        clip = segment.get("clip") if isinstance(segment.get("clip"), dict) else {}
        clip_transform = clip.get("transform") if isinstance(clip.get("transform"), dict) else {}
        material_transform = material.get("transform") if isinstance(material.get("transform"), dict) else {}
        x, y = clip_transform.get("x"), clip_transform.get("y")
        if not _finite_number(x) or not _finite_number(y):
            raise DraftApplyError(f"group {group.get('id')}: preview position is unresolved")
        if material_transform and (material_transform.get("x") != x or material_transform.get("y") != y):
            raise DraftApplyError(f"group {group.get('id')}: segment and material preview positions disagree")
        track_id = str(segment.get("_preview_track_id", ""))
        track = tracks.get(track_id)
        if track is None:
            track = next((candidate for candidate in tracks.values() if segment in candidate.get("segments", [])), None)
        if track is None:
            raise DraftApplyError(f"group {group.get('id')}: preview track is unresolved")
        track_order = track.get("render_index", 0)
        if isinstance(track_order, bool) or not isinstance(track_order, int):
            raise DraftApplyError(f"group {group.get('id')}: preview track render order is unresolved")
        alpha = segment.get("global_alpha", material.get("global_alpha", 1.0))
        if not _finite_number(alpha) or not 0 <= float(alpha) <= 1:
            raise DraftApplyError(f"group {group.get('id')}: preview global_alpha must be from 0 through 1")
        clip_rotation = clip.get("rotation", 0.0)
        if not _finite_number(clip_rotation):
            raise DraftApplyError(f"group {group.get('id')}: preview rotation is unresolved")
        scale_x, scale_y = _scale_factors(segment)
        timerange = segment.get("target_timerange") if isinstance(segment.get("target_timerange"), dict) else {}
        start_us, duration_us = timerange.get("start"), timerange.get("duration")
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in (start_us, duration_us)) or duration_us == 0:
            raise DraftApplyError(f"group {group.get('id')}: preview row timing is unresolved")
        slot = {
            "id": f"{group.get('id', 'group')}-{visual.get('text_ref', 'text')}-{index + 1}",
            "group_id": str(group.get("id", "")),
            "text": text,
            "x": float(x),
            "y": float(y),
            "bounds": {"width_px": box_width, "height_px": box_height},
            "line_widths_px": [line["width_px"] for line in lines],
            "global_alpha": float(alpha),
            "visible": segment.get("visible", True) is not False,
            "rotation": float(clip_rotation),
            "scale_x": scale_x,
            "scale_y": scale_y,
            "start_us": start_us,
            "duration_us": duration_us,
            "track_render_index": track_order,
            "track_name": str(track.get("name", track.get("id", ""))),
            "native_verified": False,
            "safe_zone_id": zones_by_group[str(group.get("id", ""))]["id"],
        }
        animation = visual.get("animation")
        if isinstance(animation, dict):
            slot["animation_resource_id"] = str(animation.get("resource_id", ""))
            slot["animation_duration_us"] = animation.get("duration_us")
        if final_phase and isinstance(group.get("layout"), dict) and group["layout"].get("slots"):
            slot["bounds"]["width"] = 2 * box_width * abs(scale_x) / width
            slot["bounds"]["height"] = 2 * box_height * abs(scale_y) / height
            layout_check.setdefault(str(group.get("id", "")), []).append(slot)
        slots.append(slot)

    for group_id, group_slots in layout_check.items():
        fitted = fit_slots_to_safe_zone(group_slots, zones_by_group[group_id]["bounds"])
        if fitted["shift_x"] or fitted["shift_y"]:
            raise DraftApplyError(f"group {group_id}: final overrides place text outside the numeric safe zone")
    return {"canvas_width": width, "canvas_height": height, "safe_zones": safe_zones, "slots": slots}


def _new_id() -> str:
    return str(uuid.uuid4()).upper()


def _text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _replace_ids(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_ids(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_ids(item, replacements) for item in value]
    if isinstance(value, str):
        return replacements.get(value, value)
    return value


def _material_index(value: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    materials = value.get("materials")
    if not isinstance(materials, dict):
        raise DraftApplyError("draft materials must be an object")
    index: dict[str, tuple[str, dict[str, Any]]] = {}
    for bucket, items in materials.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                if item["id"] in index:
                    raise DraftApplyError(f"duplicate material id {item['id']!r}")
                index[item["id"]] = (bucket, item)
    return index


def _material_for_segment(value: dict[str, Any], segment: dict[str, Any], *, required: bool = False) -> dict[str, Any] | None:
    material_id = segment.get("material_id")
    index = _material_index(value)
    entry = index.get(str(material_id)) if material_id is not None else None
    if entry is None:
        if required:
            raise DraftApplyError("text operation target has no resolvable material_id")
        return None
    bucket, material = entry
    if required and bucket != "texts":
        raise DraftApplyError(f"text operation target resolves to materials.{bucket}, not materials.texts")
    return material


def _material_segment_reference_count(value: dict[str, Any], material_id: str) -> int:
    count = 0
    for track in value.get("tracks", []) if isinstance(value.get("tracks"), list) else []:
        if not isinstance(track, dict):
            continue
        for segment in track.get("segments", []) if isinstance(track.get("segments"), list) else []:
            if not isinstance(segment, dict):
                continue
            if str(segment.get("material_id", "")) == material_id:
                count += 1
            refs = segment.get("extra_material_refs")
            if isinstance(refs, list):
                count += sum(str(ref) == material_id for ref in refs)
    return count


def _ensure_private_text_material(value: dict[str, Any], segment: dict[str, Any], material: dict[str, Any]) -> dict[str, Any]:
    material_id = str(material.get("id", ""))
    if not material_id or _material_segment_reference_count(value, material_id) <= 1:
        return material
    index = _material_index(value)
    entry = index.get(material_id)
    if entry is None or entry[0] != "texts":
        raise DraftApplyError("shared text material cannot be cloned from the current draft")
    materials = value.get("materials")
    if not isinstance(materials, dict) or not isinstance(materials.get("texts"), list):
        raise DraftApplyError("shared text material has no materials.texts target bucket")
    cloned = copy.deepcopy(material)
    cloned["id"] = _new_id()
    materials["texts"].append(cloned)
    segment["material_id"] = cloned["id"]
    return cloned


def _apply_audio_fades(value: dict[str, Any], segment: dict[str, Any], audio: dict[str, Any]) -> None:
    fields = {"fade_in_us": "fade_in_duration", "fade_out_us": "fade_out_duration"}
    requested = [name for name in fields if name in audio]
    if not requested:
        return
    for name in requested:
        duration = audio.get(name)
        if isinstance(duration, bool) or not isinstance(duration, int) or duration < 0:
            raise DraftApplyError(f"audio.{name} must be a non-negative integer")
    refs = segment.get("extra_material_refs")
    if not isinstance(refs, list):
        raise DraftApplyError("audio fade request has no extra_material_refs prototype")
    index = _material_index(value)
    fade_refs = [
        str(ref) for ref in refs
        if str(ref) in index and index[str(ref)][0] == "audio_fades"
        and index[str(ref)][1].get("type") == "audio_fade"
    ]
    if len(set(fade_refs)) != 1:
        raise DraftApplyError(f"audio fade request requires one verified audio_fade prototype; found {len(set(fade_refs))}")
    fade_id = fade_refs[0]
    fade = index[fade_id][1]
    if any(not isinstance(fade.get(field), int) or isinstance(fade.get(field), bool) for field in ("fade_in_duration", "fade_out_duration")):
        raise DraftApplyError("audio_fade prototype has no verified integer duration fields")
    if _material_segment_reference_count(value, fade_id) > 1:
        materials = value.get("materials")
        if not isinstance(materials, dict) or not isinstance(materials.get("audio_fades"), list):
            raise DraftApplyError("audio_fade material has no materials.audio_fades target bucket")
        cloned = copy.deepcopy(fade)
        cloned["id"] = _new_id()
        materials["audio_fades"].append(cloned)
        segment["extra_material_refs"] = [cloned["id"] if str(ref) == fade_id else ref for ref in refs]
        fade = cloned
    for requested_name in requested:
        fade[fields[requested_name]] = audio[requested_name]


def _verify_asset_identity(material: dict[str, Any] | None, asset_id: Any, label: str) -> None:
    if asset_id is None:
        return
    if not isinstance(asset_id, str) or not asset_id:
        raise DraftApplyError(f"{label}.asset_id must be a non-empty string")
    if material is None:
        raise DraftApplyError(f"{label}.asset_id cannot be verified without a resolved material")
    identities = {str(material.get(field)) for field in ("id", "resource_id", "music_id", "effect_id") if material.get(field)}
    if asset_id not in identities:
        raise DraftApplyError(f"{label}.asset_id does not match the resolved current-draft material")


def _material_text(material: dict[str, Any]) -> str | None:
    content = material.get("content")
    if isinstance(content, str):
        if content.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(content)
            except (json.JSONDecodeError, TypeError) as exc:
                raise DraftApplyError("text material content looks structured but is invalid JSON") from exc
            if not isinstance(parsed, dict) or not isinstance(parsed.get("text"), str):
                raise DraftApplyError("text material content JSON has no string text field")
            return parsed["text"]
        if content:
            return content
    elif isinstance(content, dict) and isinstance(content.get("text"), str):
        return content["text"]
    text = material.get("text")
    return text if isinstance(text, str) else None


def _set_style_ranges(container: dict[str, Any], old_length: int, new_length: int) -> None:
    styles = container.get("styles")
    if not isinstance(styles, list):
        return
    mapped_styles = []
    for style in styles:
        if not isinstance(style, dict):
            mapped_styles.append(style)
            continue
        value = style.get("range")
        if isinstance(value, list) and len(value) == 2:
            start, end = value
            range_kind = "list"
        elif isinstance(value, dict):
            start, end = value.get("start"), value.get("end")
            range_kind = "dict"
        else:
            mapped_styles.append(style)
            continue
        if (
            old_length <= 0
            or new_length <= 0
            or any(
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not math.isfinite(float(item))
                for item in (start, end)
            )
        ):
            continue
        start = max(0.0, min(float(old_length), float(start)))
        end = max(0.0, min(float(old_length), float(end)))
        if end <= start:
            continue
        mapped_start = min(new_length, max(0, math.ceil(start / old_length * new_length)))
        mapped_end = min(new_length, max(0, math.ceil(end / old_length * new_length)))
        if mapped_end <= mapped_start:
            continue
        updated = copy.deepcopy(style)
        if range_kind == "list":
            updated["range"] = [mapped_start, mapped_end]
        else:
            updated["range"] = {**value, "start": mapped_start, "end": mapped_end}
        mapped_styles.append(updated)
    container["styles"] = mapped_styles


def _replace_text_mirror(value: Any, text: str, old_length: int, new_length: int) -> Any:
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return text
            updated = _replace_text_mirror(parsed, text, old_length, new_length)
            return json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
        return text
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            value["text"] = text
            _set_style_ranges(value, old_length, new_length)
            return value
        for key in ("content", "base_content", "recognize_text", "text_content"):
            if key in value:
                value[key] = _replace_text_mirror(value[key], text, old_length, new_length)
                return value
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, (dict, list, str)):
                value[index] = _replace_text_mirror(item, text, old_length, new_length)
    return value


def _set_material_text(material: dict[str, Any], text: str) -> None:
    old_text = _material_text(material) or ""
    content = material.get("content")
    if isinstance(content, str):
        if content.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                raise DraftApplyError("text material content looks structured but is invalid JSON") from exc
            if not isinstance(parsed, dict):
                raise DraftApplyError("text material content JSON is not an object")
            parsed["text"] = text
            _set_style_ranges(parsed, len(old_text), len(text))
            material["content"] = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
        else:
            material["content"] = text
    elif isinstance(content, dict):
        content["text"] = text
        _set_style_ranges(content, len(old_text), len(text))
    else:
        material["content"] = text
    material["text"] = text
    for mirror in ("base_content", "recognize_text", "text_content"):
        if mirror in material:
            material[mirror] = _replace_text_mirror(material[mirror], text, len(old_text), len(text))
    _set_style_ranges(material, len(old_text), len(text))


def _find_segments(value: dict[str, Any], locator: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    tracks = value.get("tracks")
    if not isinstance(tracks, list):
        return matches
    for track in tracks:
        if not isinstance(track, dict):
            continue
        if locator.get("track_id") and str(track.get("id")) != str(locator["track_id"]):
            continue
        if locator.get("track_type") and track.get("type") != locator["track_type"]:
            continue
        segments = track.get("segments")
        if not isinstance(segments, list):
            continue
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            if locator.get("segment_id") and str(segment.get("id")) != str(locator["segment_id"]):
                continue
            if locator.get("material_id") and str(segment.get("material_id")) != str(locator["material_id"]):
                continue
            matches.append((track, segment))
    return matches


def _find_one_segment(value: dict[str, Any], locator: dict[str, Any], label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = _find_segments(value, locator)
    if len(matches) != 1:
        raise DraftApplyError(f"{label} locator matched {len(matches)} segments; exactly one is required")
    return matches[0]


def _select_timeline_value(
    locator: dict[str, Any],
    *,
    target_value: dict[str, Any],
    source_value: dict[str, Any],
    plan: dict[str, Any],
    timeline_values: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    name = str(locator.get("timeline", ""))
    source = plan.get("source", {}) if isinstance(plan.get("source"), dict) else {}
    target = plan.get("target", {}) if isinstance(plan.get("target"), dict) else {}
    aliases = {"target", str(target.get("timeline_name", "")), str(target_value.get("id", ""))}
    if name in aliases:
        return target_value
    if name in {"source", str(source.get("timeline", "")), str(source_value.get("id", ""))}:
        return source_value
    if name in timeline_values:
        return timeline_values[name]
    raise DraftApplyError(f"locator timeline {name!r} is not available in the current draft")


def _target_track(
    value: dict[str, Any],
    locator: dict[str, Any],
    object_type: str,
    *,
    prototype_track: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tracks = value.get("tracks")
    if not isinstance(tracks, list):
        raise DraftApplyError("draft tracks must be an array")
    track_id = locator.get("track_id")
    track_type = locator.get("track_type")
    inferred_type = track_type or ("text" if object_type == "text" else "audio" if object_type == "audio" else "video")
    matches = [
        track for track in tracks
        if isinstance(track, dict)
        and (str(track.get("id")) == str(track_id) if track_id else track.get("type") == inferred_type)
    ]
    if len(matches) > 1:
        raise DraftApplyError(f"target track locator matched {len(matches)} tracks; use an explicit track_id")
    if matches:
        track = matches[0]
        if track.get("type") != inferred_type:
            raise DraftApplyError("target track type does not match the requested object type")
        if not isinstance(track.get("segments"), list):
            raise DraftApplyError("target track segments must be an array")
        return track

    templates = [track for track in tracks if isinstance(track, dict) and track.get("type") == inferred_type]
    if not templates:
        raise DraftApplyError(f"cannot create a {inferred_type!r} target track without a same-type prototype")
    if prototype_track is not None:
        if prototype_track.get("type") != inferred_type:
            raise DraftApplyError("target track prototype type does not match the requested object type")
        track_template = prototype_track
    elif len(templates) == 1:
        track_template = templates[0]
    else:
        raise DraftApplyError(f"cannot choose among {len(templates)} same-type target track prototypes")
    new_id = str(track_id) if track_id else _new_id()
    if any(isinstance(track, dict) and str(track.get("id")) == new_id for track in tracks):
        raise DraftApplyError(f"target track id {new_id!r} is ambiguous")
    track = copy.deepcopy(track_template)
    track.update({"id": new_id, "name": str(locator.get("name", "Packaging review")), "segments": []})
    track["render_index"] = max(
        (int(item.get("render_index", 0) or 0) for item in templates if _finite_number(item.get("render_index", 0) or 0)),
        default=0,
    ) + 1
    tracks.append(track)
    return track


def _is_auxiliary_text(group: dict[str, Any], visual: dict[str, Any]) -> bool:
    text_ref = visual.get("text_ref")
    if not isinstance(text_ref, str):
        return False
    if text_ref in group.get("auxiliary_text_refs", []):
        return True
    layout = group.get("layout")
    return isinstance(layout, dict) and any(
        isinstance(slot, dict) and slot.get("ref_type") == "auxiliary_mark" and slot.get("text_ref") == text_ref
        for slot in layout.get("slots", []) if isinstance(layout.get("slots"), list)
    )


def _existing_topmost_text_track(value: dict[str, Any], locator: dict[str, Any]) -> dict[str, Any]:
    track_id = locator.get("track_id")
    if not isinstance(track_id, str) or not track_id:
        raise DraftApplyError("auxiliary text requires an explicit existing topmost text track")
    tracks = [track for track in value.get("tracks", []) if isinstance(track, dict) and track.get("type") == "text"]
    matches = [track for track in tracks if str(track.get("id")) == track_id]
    if len(matches) != 1:
        raise DraftApplyError("auxiliary text requires an explicit existing topmost text track")
    orders = [track.get("render_index") for track in tracks]
    if not orders or any(isinstance(order, bool) or not isinstance(order, int) for order in orders):
        raise DraftApplyError("auxiliary text track render order is unresolved")
    highest = max(orders)
    if orders.count(highest) != 1 or matches[0].get("render_index") != highest:
        raise DraftApplyError("auxiliary text target must be the unique topmost text track")
    return matches[0]


def _assert_no_track_overlap(track: dict[str, Any], start: int, duration: int) -> None:
    end = start + duration
    for segment in track.get("segments", []):
        timerange = segment.get("target_timerange") if isinstance(segment, dict) else None
        old_start = timerange.get("start") if isinstance(timerange, dict) else None
        old_duration = timerange.get("duration") if isinstance(timerange, dict) else None
        if any(isinstance(item, bool) or not isinstance(item, int) for item in (old_start, old_duration)) or old_start < 0 or old_duration <= 0:
            raise DraftApplyError(f"cannot prove overlay track {track.get('id')!r} is free of overlap")
        if start < old_start + old_duration and old_start < end:
            raise DraftApplyError(f"auxiliary text overlaps an existing segment on track {track.get('id')!r}")


def _clone_material_closure(source_value: dict[str, Any], target_value: dict[str, Any], root_ids: list[str]) -> dict[str, str]:
    source_index = _material_index(source_value)
    target_materials = target_value.setdefault("materials", {})
    if not isinstance(target_materials, dict):
        raise DraftApplyError("target materials must be an object")
    closure: set[str] = set()
    pending = [value for value in root_ids if isinstance(value, str)]
    while pending:
        material_id = pending.pop()
        if material_id in closure:
            continue
        if material_id not in source_index:
            raise DraftApplyError(f"segment material closure has unresolved reference {material_id!r}")
        closure.add(material_id)
        for child in _all_strings(source_index[material_id][1]):
            if child in source_index and child not in closure:
                pending.append(child)
    replacements = {old_id: _new_id() for old_id in closure}
    for old_id in closure:
        bucket, material = source_index[old_id]
        target_materials.setdefault(bucket, []).append(_replace_ids(copy.deepcopy(material), replacements))
    return replacements


def _clone_segment_closure(
    source_value: dict[str, Any],
    target_value: dict[str, Any],
    segment: dict[str, Any],
    *,
    required_material_ids: set[str] | None = None,
    preserve_extra_material_refs: bool = True,
) -> dict[str, Any]:
    extra_material_refs = segment.get("extra_material_refs") if isinstance(segment.get("extra_material_refs"), list) else []
    root_ids = [segment.get("material_id")]
    if preserve_extra_material_refs:
        root_ids.extend(extra_material_refs)
    root_ids = [value for value in root_ids if isinstance(value, str)]
    replacements = _clone_material_closure(source_value, target_value, root_ids)
    missing = set(required_material_ids or ()) - set(replacements)
    if missing:
        raise DraftApplyError(f"template material closure omits declared material_ids: {sorted(missing)}")
    cloned = _replace_ids(copy.deepcopy(segment), replacements)
    cloned["id"] = _new_id()
    if not preserve_extra_material_refs:
        cloned["extra_material_refs"] = []
    return cloned


def _clone_segment_from_asset_material(
    source_value: dict[str, Any],
    target_value: dict[str, Any],
    prototype: dict[str, Any],
    asset_id: str,
    *,
    clone_asset: bool,
) -> dict[str, Any]:
    source_index = _material_index(source_value)
    asset_entry = source_index.get(asset_id)
    if asset_entry is None:
        raise DraftApplyError(f"asset material {asset_id!r} is not present in the source timeline")
    extras = [str(item) for item in prototype.get("extra_material_refs", []) if isinstance(item, str)]
    extra_replacements = _clone_material_closure(source_value, target_value, extras) if extras else {}
    cloned = _replace_ids(copy.deepcopy(prototype), extra_replacements)
    target_index = _material_index(target_value)
    if clone_asset or asset_id not in target_index:
        asset_replacements = _clone_material_closure(source_value, target_value, [asset_id])
        target_asset_id = asset_replacements[asset_id]
    else:
        target_asset_id = asset_id
    cloned["id"] = _new_id()
    cloned["material_id"] = target_asset_id
    cloned["extra_material_refs"] = [extra_replacements.get(item, item) for item in extras]
    return cloned


def _prototype_for_asset(source_value: dict[str, Any], asset_id: str, object_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    source_index = _material_index(source_value)
    asset_entry = source_index.get(asset_id)
    if asset_entry is None:
        raise DraftApplyError(f"asset material {asset_id!r} is not present in the source timeline")
    bucket, asset = asset_entry
    expected = {"text": ("text", "texts"), "video": ("video", "videos"), "audio": ("audio", "audios")}.get(object_type)
    if expected is None or bucket != expected[1]:
        raise DraftApplyError(f"material-only asset {asset_id!r} has no verified {object_type!r} segment mapping")
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for track in source_value.get("tracks", []) if isinstance(source_value.get("tracks"), list) else []:
        if not isinstance(track, dict) or track.get("type") != expected[0]:
            continue
        for segment in track.get("segments", []) if isinstance(track.get("segments"), list) else []:
            if not isinstance(segment, dict):
                continue
            existing = source_index.get(str(segment.get("material_id")))
            if existing is not None and existing[0] == bucket and existing[1].get("type") == asset.get("type"):
                candidates.append((track, segment))
    if len(candidates) != 1:
        raise DraftApplyError(f"asset material {asset_id!r} requires one unambiguous same-type segment prototype; found {len(candidates)}")
    return candidates[0]


def _all_strings(value: Any):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _all_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_strings(nested)
    elif isinstance(value, str):
        yield value


def _segment_has_motion(value: dict[str, Any], segment: dict[str, Any]) -> bool:
    clip = segment.get("clip") if isinstance(segment.get("clip"), dict) else {}
    if isinstance(segment.get("keyframes"), list) and segment["keyframes"]:
        return True
    if isinstance(clip.get("keyframes"), list) and clip["keyframes"]:
        return True
    materials = _material_index(value)
    pending = [item for item in segment.get("extra_material_refs", []) if isinstance(item, str)]
    seen: set[str] = set()
    while pending:
        material_id = pending.pop()
        if material_id in seen or material_id not in materials:
            continue
        seen.add(material_id)
        bucket, material = materials[material_id]
        if "animation" in bucket.lower() or "effect" in bucket.lower():
            if material.get("is_animating") is True:
                return True
            if any(isinstance(material.get(field), list) and material[field] for field in ("animations", "keyframes")):
                return True
            if isinstance(material.get("animation"), dict) and material["animation"]:
                return True
        pending.extend(item for item in _all_strings(material) if item in materials and item not in seen)
    return False


def _visual_range(group: dict[str, Any], visual: dict[str, Any]) -> tuple[int, int]:
    group_range = group.get("range") if isinstance(group.get("range"), dict) else {}
    start = visual.get("start_us", group_range.get("start_us"))
    duration = visual.get("duration_us", group_range.get("duration_us"))
    end = visual.get("end_us")
    if duration is None and isinstance(end, int) and isinstance(start, int):
        duration = end - start
    if isinstance(start, bool) or not isinstance(start, int) or isinstance(duration, bool) or not isinstance(duration, int) or start < 0 or duration <= 0:
        raise DraftApplyError(f"group {group.get('id')}: visual operation requires a valid start_us/duration_us range")
    return start, duration


def _audio_range(audio: dict[str, Any], field: str) -> dict[str, int] | None:
    value = audio.get(field)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DraftApplyError(f"audio.{field} must be a timerange object")
    start, duration = value.get("start_us"), value.get("duration_us")
    if isinstance(start, bool) or not isinstance(start, int) or isinstance(duration, bool) or not isinstance(duration, int) or start < 0 or duration <= 0:
        raise DraftApplyError(f"audio.{field} must contain non-negative start_us and positive duration_us")
    return {"start": start, "duration": duration}


def _apply_numeric_override(current: Any, descriptor: Any, field: str) -> float | int:
    if not isinstance(descriptor, dict) or descriptor.get("mode") not in {"absolute", "relative"}:
        raise DraftApplyError(f"override {field!r} must use absolute or relative mode")
    value = descriptor.get("value") if descriptor["mode"] == "absolute" else descriptor.get("delta")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise DraftApplyError(f"override {field!r} must contain a finite numeric value")
    if descriptor["mode"] == "absolute":
        return value
    if isinstance(current, bool) or not isinstance(current, (int, float)) or not math.isfinite(float(current)):
        raise DraftApplyError(f"relative override {field!r} has no finite numeric prototype value")
    result = current + value
    if not math.isfinite(float(result)):
        raise DraftApplyError(f"override {field!r} result must be finite")
    return result


def _set_position(segment: dict[str, Any], material: dict[str, Any], x: float, y: float) -> None:
    clip = segment.get("clip")
    clip_transform = clip.get("transform") if isinstance(clip, dict) else None
    material_transform = material.get("transform")
    if not isinstance(clip_transform, dict) or not isinstance(material_transform, dict):
        raise DraftApplyError("text position needs both segment clip.transform and material transform prototypes")
    clip_transform["x"], clip_transform["y"] = x, y
    material_transform["x"], material_transform["y"] = x, y


def _scale_factors(segment: dict[str, Any], transform: Any = None) -> tuple[float, float]:
    override = transform.get("scale") if isinstance(transform, dict) else None
    clip = segment.get("clip") if isinstance(segment.get("clip"), dict) else {}
    current = clip.get("scale") if isinstance(clip.get("scale"), dict) else {}
    if override is None:
        x, y = current.get("x", 1.0), current.get("y", 1.0)
    elif isinstance(override, dict):
        x, y = override.get("x"), override.get("y")
    else:
        x = y = override
    if not _finite_number(x) or not _finite_number(y):
        raise DraftApplyError("text scale has no confirmed numeric x/y mapping")
    return float(x), float(y)


def _font_for_material(material: dict[str, Any]) -> tuple[str, float, float]:
    content = material.get("content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            content = None
    style = next(iter(content.get("styles", [])), {}) if isinstance(content, dict) and isinstance(content.get("styles"), list) else {}
    font_path = material.get("font_path") or (content.get("font_path") if isinstance(content, dict) else None)
    font_size = material.get("font_size", style.get("size") if isinstance(style, dict) else None)
    letter_spacing = material.get("letter_spacing", style.get("letter_spacing", 0.0) if isinstance(style, dict) else 0.0)
    if not isinstance(font_path, str) or not font_path.strip():
        raise DraftApplyError("reliable font metrics are unavailable: text material has no font file path")
    if not _finite_number(font_size) or float(font_size) < 1:
        raise DraftApplyError("reliable font metrics are unavailable: text material has no usable pixel font size")
    if not _finite_number(letter_spacing):
        raise DraftApplyError("reliable font metrics are unavailable: letter spacing is not numeric")
    return font_path, float(font_size), float(letter_spacing)


def _measure_material_text(material: dict[str, Any], text: str) -> tuple[list[dict[str, Any]], float, float]:
    font_path, font_size, letter_spacing = _font_for_material(material)
    try:
        lines = measure_text_lines(
            text,
            font_path=font_path,
            font_size_px=font_size,
            letter_spacing_px=letter_spacing,
        )
    except VisualPreviewError as exc:
        raise DraftApplyError(str(exc)) from exc
    width = max((float(line["width_px"]) for line in lines), default=0.0)
    height = sum(float(line["height_px"]) for line in lines)
    if width <= 0 or height <= 0:
        raise DraftApplyError("reliable font metrics are unavailable: text measured to an empty box")
    return lines, width, height


def _contains_words_payload(value: Any) -> bool:
    if isinstance(value, dict):
        if "words" in value and isinstance(value["words"], (list, dict)) and value["words"]:
            return True
        return any(_contains_words_payload(nested) for nested in value.values())
    if isinstance(value, list):
        return any(_contains_words_payload(nested) for nested in value)
    return False


def _available_text_inputs(material: dict[str, Any] | None) -> set[str]:
    if not isinstance(material, dict):
        return set()
    inputs = {"text"} if _material_text(material) is not None else set()
    content = material.get("content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            content = None
    if _contains_words_payload(content) or _contains_words_payload(material):
        inputs.add("words")
    return inputs


def _animation_materials(value: dict[str, Any]) -> list[dict[str, Any]]:
    materials = value.get("materials")
    if not isinstance(materials, dict):
        raise DraftApplyError("target draft has no materials object")
    animations = materials.setdefault("material_animations", [])
    if not isinstance(animations, list):
        raise DraftApplyError("materials.material_animations must be an array")
    return animations


def _segment_has_intro_animation(value: dict[str, Any], segment: dict[str, Any]) -> bool:
    refs = segment.get("extra_material_refs")
    if not isinstance(refs, list):
        return False
    ref_ids = {str(ref) for ref in refs}
    materials = value.get("materials", {})
    animations = materials.get("material_animations", []) if isinstance(materials, dict) else []
    return isinstance(animations, list) and any(
        isinstance(material, dict)
        and str(material.get("id", "")) in ref_ids
        and isinstance(material.get("animations"), list)
        and any(isinstance(animation, dict) and animation.get("type") == "in" for animation in material["animations"])
        for material in animations
    )


def _ensure_private_animation_container(
    value: dict[str, Any],
    segment: dict[str, Any],
    container: dict[str, Any] | None,
) -> dict[str, Any]:
    materials = _animation_materials(value)
    refs = segment.setdefault("extra_material_refs", [])
    if not isinstance(refs, list):
        raise DraftApplyError("text segment extra_material_refs must be an array")
    if container is None:
        container = {
            "id": _new_id(),
            "type": "sticker_animation",
            "multi_language_current": "none",
            "animations": [],
        }
        materials.append(container)
        refs.append(container["id"])
        return container

    original_id = str(container.get("id", ""))
    uses = sum(
        1
        for track in value.get("tracks", []) if isinstance(track, dict)
        for item in track.get("segments", []) if isinstance(item, dict)
        if original_id and original_id in item.get("extra_material_refs", [])
    )
    if uses > 1:
        clone = copy.deepcopy(container)
        clone["id"] = _new_id()
        materials.append(clone)
        segment["extra_material_refs"] = [clone["id"] if str(ref) == original_id else ref for ref in refs]
        return clone
    return container


def _apply_text_animation(
    value: dict[str, Any],
    segment: dict[str, Any],
    material: dict[str, Any] | None,
    animation: Any,
    inventory: dict[str, Any] | None,
) -> int:
    if not isinstance(animation, dict):
        raise DraftApplyError("visual.animation must be an object")
    if not isinstance(inventory, dict):
        raise DraftApplyError("visual.animation requires a current local animation inventory")
    if not isinstance(material, dict) or material.get("type") != "text":
        raise DraftApplyError("TextIntro animations require a text material prototype")
    resource_id = str(animation.get("resource_id", ""))
    try:
        entry = resolve_text_animation(inventory, resource_id, available_inputs=_available_text_inputs(material))
    except ValueError as exc:
        raise DraftApplyError(str(exc)) from exc

    timerange = segment.get("target_timerange")
    visible_duration = timerange.get("duration") if isinstance(timerange, dict) else None
    requested_duration = animation.get("duration_us")
    if isinstance(visible_duration, bool) or not isinstance(visible_duration, int) or visible_duration <= 0:
        raise DraftApplyError("animated text segment has no positive visible duration")
    effective_duration = min(int(entry["default_duration_us"]), visible_duration)
    if isinstance(requested_duration, bool) or requested_duration != effective_duration:
        raise DraftApplyError(
            f"visual.animation.duration_us must equal min(preset {entry['default_duration_us']}, row {visible_duration}) = {effective_duration}"
        )

    refs = segment.get("extra_material_refs")
    if not isinstance(refs, list):
        raise DraftApplyError("text segment extra_material_refs must be an array")
    animation_materials = _animation_materials(value)
    referenced = [
        item for item in animation_materials
        if isinstance(item, dict) and str(item.get("id", "")) in {str(ref) for ref in refs}
        and item.get("type") == "sticker_animation"
    ]
    if len(referenced) > 1:
        raise DraftApplyError("text segment has multiple animation containers; select a verified template")
    container = _ensure_private_animation_container(value, segment, referenced[0] if referenced else None)
    animations = container.get("animations")
    if not isinstance(animations, list):
        raise DraftApplyError("animation material animations must be an array")
    intro_indices = [index for index, item in enumerate(animations) if isinstance(item, dict) and item.get("type") == "in"]
    if len(intro_indices) > 1:
        raise DraftApplyError("text animation prototype contains multiple entrance animations")
    payload = {
        "anim_adjust_params": None,
        "platform": "all",
        "panel": "",
        "material_type": "sticker",
        "name": entry["name"],
        "id": entry["effect_id"],
        "resource_id": entry["resource_id"],
        "type": "in",
        "start": 0,
        "duration": effective_duration,
        "path": entry["cache_path"],
    }
    if intro_indices:
        preserved = dict(animations[intro_indices[0]])
        preserved.update(payload)
        animations[intro_indices[0]] = preserved
    else:
        animations.append(payload)
    return effective_duration


def _apply_planned_animation(
    value: dict[str, Any],
    segment: dict[str, Any],
    material: dict[str, Any] | None,
    visual: dict[str, Any],
    inventory: dict[str, Any] | None,
) -> int | None:
    animation = visual.get("animation")
    if animation is None:
        if _segment_has_intro_animation(value, segment):
            raise DraftApplyError("copied entrance animation requires an explicit visual.animation duration declaration")
        return None
    return _apply_text_animation(value, segment, material, animation, inventory)


def _apply_override(segment: dict[str, Any], material: dict[str, Any] | None, field: str, descriptor: Any) -> None:
    if field not in DIRECT_OVERRIDE_FIELDS:
        raise DraftApplyError(f"override {field!r} has no verified adapter mapping")
    if field == "global_alpha":
        if not isinstance(material, dict) or material.get("type") != "text":
            raise DraftApplyError("global_alpha requires a confirmed text material prototype")
        if "global_alpha" not in segment:
            raise DraftApplyError("global_alpha requires a confirmed segment.global_alpha prototype")
        if not isinstance(descriptor, dict) or descriptor.get("mode") != "absolute":
            raise DraftApplyError("global_alpha requires an absolute value")
        value = descriptor.get("value")
        if not _finite_number(value) or not 0 <= value <= 1:
            raise DraftApplyError("global_alpha must be between 0 and 1")
        segment["global_alpha"] = value
        return
    if field in {"position_x", "position_y"}:
        clip = segment.get("clip")
        clip_transform = clip.get("transform") if isinstance(clip, dict) else None
        material_transform = material.get("transform") if isinstance(material, dict) else None
        if not isinstance(clip_transform, dict):
            raise DraftApplyError(f"override {field!r} requires a confirmed clip transform prototype")
        if material is not None and not isinstance(material_transform, dict):
            raise DraftApplyError(f"override {field!r} requires a confirmed material transform prototype")
        if isinstance(material_transform, dict):
            for axis in ("x", "y"):
                if not _finite_number(clip_transform.get(axis)) or not _finite_number(material_transform.get(axis)) or clip_transform[axis] != material_transform[axis]:
                    raise DraftApplyError(f"override {field!r} requires matching numeric clip/material transforms")
        axis = "x" if field.endswith("x") else "y"
        value = _apply_numeric_override(clip_transform.get(axis), descriptor, field)
        clip_transform[axis] = value
        if material_transform is not None:
            material_transform[axis] = value
        return
    if field in {"scale_x", "scale_y", "uniform_scale"}:
        clip = segment.get("clip")
        scale = clip.get("scale") if isinstance(clip, dict) else None
        if not isinstance(scale, dict):
            raise DraftApplyError(f"override {field!r} requires a confirmed clip.scale prototype")
        axes = ("x", "y") if field == "uniform_scale" else (("x",) if field == "scale_x" else ("y",))
        for axis in axes:
            value = _apply_numeric_override(scale.get(axis), descriptor, field)
            if value <= 0:
                raise DraftApplyError(f"override {field!r} result must be positive")
            scale[axis] = value
        return
    if field in {"start_us", "duration_us"}:
        timerange = segment.get("target_timerange")
        if not isinstance(timerange, dict):
            raise DraftApplyError(f"override {field!r} requires target_timerange")
        key = "start" if field == "start_us" else "duration"
        value = _apply_numeric_override(timerange.get(key), descriptor, field)
        if field == "start_us" and value < 0:
            raise DraftApplyError("override 'start_us' result must be non-negative")
        if field == "duration_us" and value <= 0:
            raise DraftApplyError("override 'duration_us' result must be positive")
        timerange[key] = value
        return
    if field == "visible":
        if not isinstance(descriptor, dict) or descriptor.get("mode") != "absolute" or not isinstance(descriptor.get("value"), bool):
            raise DraftApplyError("override 'visible' requires an absolute boolean value")
        segment["visible"] = descriptor["value"]
        return
    raise DraftApplyError(f"override {field!r} has no verified draft-field mapping")


def _subtitle_manifest(source_value: dict[str, Any], plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    source = plan.get("source", {}) if isinstance(plan.get("source"), dict) else {}
    units = source.get("final_subtitle_units")
    if not isinstance(units, list) or not units:
        return [], ["source.final_subtitle_units is required to resolve runtime layout anchors"]
    material_index = _material_index(source_value)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for track in source_value.get("tracks", []) if isinstance(source_value.get("tracks"), list) else []:
        if not isinstance(track, dict) or track.get("type") != "text":
            continue
        for segment in track.get("segments", []) if isinstance(track.get("segments"), list) else []:
            if not isinstance(segment, dict) or segment.get("visible") is False:
                continue
            timerange = segment.get("target_timerange")
            playback_start = timerange.get("start") if isinstance(timerange, dict) else None
            if isinstance(playback_start, bool) or not isinstance(playback_start, int) or playback_start < 0:
                errors.append(f"visible subtitle {segment.get('id')!r}: target_timerange.start is not a non-negative integer")
                continue
            entry = material_index.get(str(segment.get("material_id")))
            if entry is None or entry[0] != "texts":
                continue
            text = _material_text(entry[1])
            if not isinstance(text, str) or not text:
                continue
            clip = segment.get("clip") if isinstance(segment.get("clip"), dict) else {}
            clip_transform = clip.get("transform") if isinstance(clip.get("transform"), dict) else None
            material_transform = entry[1].get("transform") if isinstance(entry[1].get("transform"), dict) else None
            anchors: list[dict[str, float]] = []
            for label, transform in (("segment", clip_transform), ("material", material_transform)):
                if transform is None:
                    continue
                x, y = transform.get("x"), transform.get("y")
                if not _finite_number(x) or not _finite_number(y):
                    errors.append(f"visible subtitle {segment.get('id')!r}: {label} transform has no numeric x/y")
                    continue
                anchors.append({"x": float(x), "y": float(y)})
            if len(anchors) > 1 and any(item != anchors[0] for item in anchors[1:]):
                errors.append(f"visible subtitle {segment.get('id')!r}: segment and material transforms disagree")
            anchor = anchors[0] if anchors and all(item == anchors[0] for item in anchors) else None
            rows.append({
                "segment_id": str(segment.get("id", "")),
                "text": text,
                "text_hash": _text_hash(text),
                "runtime_anchor": anchor,
                "playback_start_us": playback_start,
                "track_id": str(track.get("id", "")),
                "track_render_index": track.get("render_index", 0),
                "segment": segment,
                "material": entry[1],
            })

    rows.sort(key=lambda row: row["playback_start_us"])

    manifest: list[dict[str, Any]] = []
    used: set[int] = set()
    cursor = 0
    for index, unit in enumerate(units):
        path = f"source.final_subtitle_units[{index}]"
        if not isinstance(unit, dict) or not isinstance(unit.get("unit_id"), str) or not isinstance(unit.get("text_hash"), str):
            errors.append(f"{path} must contain unit_id and text_hash")
            continue
        direct = [i for i, row in enumerate(rows) if row["segment_id"] == unit["unit_id"] and row["text_hash"] == unit["text_hash"]]
        candidates = direct or [i for i, row in enumerate(rows) if i >= cursor and row["text_hash"] == unit["text_hash"]]
        if not direct and not candidates:
            candidates = [i for i, row in enumerate(rows) if row["text_hash"] == unit["text_hash"]]
        candidates = [i for i in candidates if i not in used]
        if len(candidates) != 1:
            errors.append(f"{path}: current visible subtitle text matched {len(candidates)} timeline rows")
            continue
        row_index = candidates[0]
        used.add(row_index)
        cursor = row_index + 1
        row = rows[row_index]
        if row["runtime_anchor"] is None:
            errors.append(f"{path}: current subtitle segment has no numeric runtime transform")
            continue
        manifest.append({
            "unit_id": unit["unit_id"],
            "text": row["text"],
            "text_hash": row["text_hash"],
            "runtime_anchor": row["runtime_anchor"],
            "segment_id": row["segment_id"],
            "playback_start_us": row["playback_start_us"],
            "track_id": row["track_id"],
            "track_render_index": row["track_render_index"],
            "segment": row["segment"],
            "material": row["material"],
        })
    manifest.sort(key=lambda row: row["playback_start_us"])
    for row in manifest:
        row.pop("playback_start_us", None)
    return manifest, errors


def _finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))


def _audio_evidence_from_value(value: dict[str, Any]) -> list[dict[str, Any]]:
    materials = _material_index(value)
    rows: list[dict[str, Any]] = []
    for track in value.get("tracks", []) if isinstance(value.get("tracks"), list) else []:
        if not isinstance(track, dict) or track.get("type") != "audio":
            continue
        track_name = " ".join(
            str(track.get(field, "")) for field in ("name", "role", "track_role")
        ).strip().lower()
        for segment in track.get("segments", []) if isinstance(track.get("segments"), list) else []:
            if not isinstance(segment, dict):
                continue
            timerange = segment.get("target_timerange") if isinstance(segment.get("target_timerange"), dict) else {}
            start = timerange.get("start")
            duration = timerange.get("duration")
            if isinstance(start, bool) or not isinstance(start, int) or isinstance(duration, bool) or not isinstance(duration, int) or start < 0 or duration <= 0:
                continue
            entry = materials.get(str(segment.get("material_id")))
            material_type = str(entry[1].get("type", "")).lower() if entry else ""
            if material_type in {"video_original_sound", "text_to_audio", "voice", "dialogue"} or any(word in track_name for word in ("dialogue", "voice", "speech", "narration", "人声", "旁白", "原声")):
                kind = "dialogue"
            elif material_type in {"music", "extract_music"} or any(word in track_name for word in ("music", "bgm", "配乐")):
                kind = "music"
            elif material_type in {"sound", "extract_sound"} or any(word in track_name for word in ("sfx", "sound effect", "音效")):
                kind = "sfx"
            else:
                kind = "unknown"
            rows.append({
                "id": str(segment.get("id", segment.get("material_id", "audio"))),
                "kind": kind,
                "start_us": start,
                "end_us": start + duration,
            })
    return rows


def _normalize_audio_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        data = value.get("data") if isinstance(value.get("data"), dict) else value
        for key in ("events", "sounds", "audio"):
            rows = data.get(key) if isinstance(data, dict) else None
            if isinstance(rows, list):
                normalized = []
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    row = dict(item)
                    if not row.get("kind") and isinstance(row.get("audio_role"), str):
                        row["kind"] = row["audio_role"]
                    normalized.append(row)
                return normalized
    return value


def _apply_final_layouts(
    target_value: dict[str, Any],
    source_value: dict[str, Any],
    plan: dict[str, Any],
    operations: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]],
    layout_registry: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    groups = [
        group for group in plan.get("groups", [])
        if isinstance(group, dict)
        and isinstance(group.get("layout"), dict)
        and isinstance(group["layout"].get("slots"), list)
        and group["layout"]["slots"]
    ]
    if not groups:
        return [], []
    if layout_registry is None:
        registry_path = Path(__file__).resolve().parents[2] / "references" / "layout-template-registry.json"
        try:
            layout_registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [], [f"layout template registry could not be loaded: {exc}"]

    manifest, errors = _subtitle_manifest(source_value, plan)
    if errors:
        return [], errors
    comparison = plan.get("comparison") if isinstance(plan.get("comparison"), dict) else {}
    target_order_hash = comparison.get("target_order_hash")
    current_order_hash = _hash_value([item["unit_id"] for item in manifest])
    if target_order_hash != current_order_hash:
        return [], ["comparison.target_order_hash does not match the current visible subtitle order"]
    text_report = resolve_text_hashes(plan, manifest)
    errors.extend(text_report.get("errors", []))
    anchor_report = resolve_subtitle_anchor(plan, {"subtitle_units": manifest})
    errors.extend(anchor_report.get("errors", []))
    if errors:
        return [], errors

    by_group = anchor_report.get("data", {}).get("by_group", {})
    source_by_unit = {str(row["unit_id"]): row for row in manifest}
    warnings: list[str] = []
    for group in groups:
        group_id = str(group.get("id", ""))
        entry = by_group.get(group_id)
        if not isinstance(entry, dict) or not isinstance(entry.get("runtime_anchor"), dict):
            errors.append(f"group {group_id}: current final subtitle runtime anchor is unresolved")
            continue
        layout = group.get("layout", {})
        if layout.get("position_mode", "relative_template") != "relative_template":
            errors.append(f"group {group_id}: legacy_absolute layout has no verified raw-coordinate adapter")
            continue
        constraints = layout.get("constraints") if isinstance(layout.get("constraints"), dict) else {}
        safe_zone = constraints.get("safe_zone")
        if not isinstance(safe_zone, dict):
            errors.append(f"group {group_id}: numeric safe-zone bounds are required for layout writes")
            continue
        profile = plan.get("project_profile") if isinstance(plan.get("project_profile"), dict) else {}
        canvas_width, canvas_height = profile.get("canvas_width"), profile.get("canvas_height")
        if isinstance(canvas_width, bool) or not isinstance(canvas_width, int) or canvas_width <= 0 or isinstance(canvas_height, bool) or not isinstance(canvas_height, int) or canvas_height <= 0:
            errors.append(f"group {group_id}: project_profile canvas dimensions are required for measured layout")
            continue
        group_for_resolution = copy.deepcopy(group)
        group_for_resolution["layout"].get("constraints", {}).pop("safe_zone", None)
        resolved = resolve_relative_layout(group_for_resolution, layout_registry, entry["runtime_anchor"])
        errors.extend(resolved.get("errors", []))
        if not resolved.get("ok"):
            continue
        slots = resolved.get("data", {}).get("slots", {})
        layout_items: list[dict[str, Any]] = []
        item_operations: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]] = []
        for operation_group, visual, segment, material in operations:
            if str(operation_group.get("id", "")) != group_id or not visual.get("text_ref"):
                continue
            matches = [slot for slot in slots.values() if isinstance(slot, dict) and slot.get("text_ref") == visual["text_ref"]]
            if len(matches) != 1:
                errors.append(f"group {group_id}: text_ref {visual['text_ref']!r} matched {len(matches)} layout slots")
                continue
            slot = copy.deepcopy(matches[0])
            text = _material_text(material) if isinstance(material, dict) else None
            try:
                if not isinstance(text, str) or not text:
                    source_row = source_by_unit.get(str(visual["text_ref"]))
                    text = source_row.get("text") if isinstance(source_row, dict) else None
                    metric_material = source_row.get("material") if isinstance(source_row, dict) else None
                else:
                    metric_material = material
                if not isinstance(text, str) or not isinstance(metric_material, dict):
                    raise DraftApplyError("layout text has no resolvable text material")
                lines, width, height = _measure_material_text(metric_material, text)
                scale_x, scale_y = _scale_factors(segment, slot.get("transform"))
                slot["bounds"] = {
                    "width": 2 * width * abs(scale_x) / canvas_width,
                    "height": 2 * height * abs(scale_y) / canvas_height,
                }
                slot["text"] = text
                slot["line_widths_px"] = [line["width_px"] for line in lines]
                layout_items.append(slot)
                item_operations.append((operation_group, visual, segment, material))
            except (DraftApplyError, KeyError, TypeError, ValueError) as exc:
                errors.append(f"group {group_id}: {exc}")
        if errors:
            continue
        if not layout_items:
            continue
        try:
            fitted = fit_slots_to_safe_zone(layout_items, safe_zone)["slots"]
        except VisualPreviewError as exc:
            errors.append(f"group {group_id}: {exc}")
            continue
        by_text_ref = {str(slot.get("text_ref")): slot for slot in fitted}
        for operation_group, visual, segment, material in item_operations:
            slot = by_text_ref[str(visual["text_ref"])]
            try:
                _set_position(segment, material or {}, float(slot["x"]), float(slot["y"]))
                transform = slot.get("transform", {})
                unsupported = set(transform) - {"scale", "rotation"}
                if unsupported:
                    raise DraftApplyError(f"layout transform fields lack a verified mapping: {sorted(unsupported)}")
                if layout.get("pattern") == "diagonal_stagger" and transform.get("rotation", 0) != 0:
                    raise DraftApplyError("diagonal_stagger layouts require zero text rotation")
                if "scale" in transform:
                    scale = transform["scale"]
                    clip = segment.get("clip")
                    clip_scale = clip.get("scale") if isinstance(clip, dict) else None
                    if isinstance(scale, dict):
                        if not isinstance(clip_scale, dict):
                            raise DraftApplyError("layout scale requires a confirmed clip.scale prototype")
                        clip_scale.update({"x": scale["x"], "y": scale["y"]})
                    elif _finite_number(scale):
                        if not isinstance(clip_scale, dict):
                            raise DraftApplyError("layout scale requires a confirmed clip.scale prototype")
                        clip_scale.update({"x": scale, "y": scale})
                    else:
                        raise DraftApplyError("layout scale is not numeric")
                if "rotation" in transform:
                    clip = segment.get("clip")
                    if not isinstance(clip, dict) or "rotation" not in clip:
                        raise DraftApplyError("layout rotation requires a confirmed clip.rotation prototype")
                    clip["rotation"] = transform["rotation"]
                elif layout.get("pattern") == "diagonal_stagger":
                    clip = segment.get("clip")
                    if isinstance(clip, dict) and "rotation" in clip:
                        clip["rotation"] = 0
            except (DraftApplyError, KeyError, TypeError, ValueError) as exc:
                errors.append(f"group {group_id}: {exc}")
    return warnings, errors


def transform_packaging_plan(
    target_value: dict[str, Any],
    plan: dict[str, Any],
    *,
    source_value: dict[str, Any] | None = None,
    timeline_values: dict[str, dict[str, Any]] | None = None,
    layout_registry: dict[str, Any] | None = None,
    animation_inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an in-memory packaging change set without writing a draft."""

    if not isinstance(target_value, dict) or not isinstance(plan, dict):
        return result("packaging_draft_transform", input_errors=["target_value and plan must be JSON objects"])
    if plan.get("schema_version") != "1.2":
        return result("packaging_draft_transform", errors=["only schema_version 1.2 can be applied"])
    execution = plan.get("execution") if isinstance(plan.get("execution"), dict) else {}
    phase = execution.get("phase")
    if execution.get("mode") != "apply" or phase not in {"staging", "final"}:
        return result("packaging_draft_transform", errors=["an apply-mode staging or final plan is required"])

    source_value = source_value if isinstance(source_value, dict) else target_value
    timeline_values = timeline_values if isinstance(timeline_values, dict) else {}
    candidate = copy.deepcopy(target_value)
    changes: list[dict[str, Any]] = []
    warnings: list[str] = []
    operations: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]] = []
    errors: list[str] = []

    groups = plan.get("groups")
    if not isinstance(groups, list):
        return result("packaging_draft_transform", errors=["plan.groups must be an array"])

    for group in groups:
        if not isinstance(group, dict):
            errors.append("plan.groups entries must be objects")
            continue
        group_id = str(group.get("id", ""))
        legacy_visual_aliases = [key for key in ("visuals", "visual_operations") if key in group]
        if "visual" not in group and legacy_visual_aliases:
            errors.append(f"group {group_id}: apply requires canonical group.visual; legacy aliases are review-only")
            visuals = []
        else:
            visuals = group.get("visual", [])
            for alias in legacy_visual_aliases:
                alias_value = group.get(alias)
                if not isinstance(visuals, list) or not isinstance(alias_value, list) or alias_value != visuals:
                    errors.append(f"group {group_id}: visual aliases disagree ({alias})")
        if not isinstance(visuals, list):
            errors.append(f"group {group_id}: visual must be an array")
            visuals = []
        for visual_index, visual in enumerate(visuals):
            path = f"group {group_id}.visual[{visual_index}]"
            if not isinstance(visual, dict):
                errors.append(f"{path}: must be an object")
                continue
            operation = visual.get("operation")
            if operation not in _VISUAL_OPS:
                errors.append(f"{path}: unsupported visual operation {operation!r}")
                continue
            if operation == "none":
                continue
            try:
                target_locator = visual.get("target_locator")
                if not isinstance(target_locator, dict):
                    raise DraftApplyError("target_locator is required")
                if operation in _NEW_VISUAL:
                    target_value_for_locator = _select_timeline_value(
                        target_locator,
                        target_value=candidate,
                        source_value=source_value,
                        plan=plan,
                        timeline_values=timeline_values,
                    )
                    if target_value_for_locator is not candidate:
                        raise DraftApplyError("visual mutation target must be the requested target timeline")
                    if operation == "clone_template":
                        preset_id = visual.get("preset_id")
                        presets = plan.get("presets", [])
                        preset = next((p for p in presets if isinstance(p, dict) and p.get("preset_id") == preset_id), None)
                        if not isinstance(preset, dict):
                            raise DraftApplyError(f"preset {preset_id!r} is missing")
                        template_source = preset.get("template_source")
                        if not isinstance(template_source, dict):
                            raise DraftApplyError(f"preset {preset_id!r} has no template_source")
                        template_timeline = str(template_source.get("timeline", ""))
                        plan_source = plan.get("source", {}) if isinstance(plan.get("source"), dict) else {}
                        plan_target = plan.get("target", {}) if isinstance(plan.get("target"), dict) else {}
                        if template_timeline in {"target", str(plan_target.get("timeline_name", ""))} and template_timeline not in {str(plan_source.get("timeline", "")), str(source_value.get("id", ""))}:
                            raise DraftApplyError("template_source cannot refer to a target timeline that does not exist yet")
                        template_value = _select_timeline_value(
                            {"timeline": template_timeline},
                            target_value=candidate,
                            source_value=source_value,
                            plan=plan,
                            timeline_values=timeline_values,
                        )
                        segment_ids = template_source.get("segment_ids")
                        if not isinstance(segment_ids, list) or not segment_ids:
                            raise DraftApplyError(f"preset {preset_id!r} must identify template segment_ids")
                        requested_template_id = visual.get("template_segment_id")
                        if requested_template_id:
                            segment_ids = [item for item in segment_ids if str(item) == str(requested_template_id)]
                        if len(segment_ids) != 1:
                            raise DraftApplyError(
                                f"preset {preset_id!r} has {len(segment_ids)} template segments; identify one template_segment_id per operation"
                            )
                        template_matches = _find_segments(template_value, {"segment_id": str(segment_ids[0])})
                        if len(template_matches) != 1:
                            raise DraftApplyError(f"template segment {segment_ids[0]!r} did not resolve uniquely")
                        material_source = template_value
                        source_track, source_segment = template_matches[0]
                        declared_material_ids = {
                            str(item) for item in template_source.get("material_ids", [])
                            if isinstance(item, str)
                        }
                    else:
                        source_locator = visual.get("source_locator")
                        if not isinstance(source_locator, dict):
                            raise DraftApplyError("source_locator is required")
                        material_source = _select_timeline_value(
                            source_locator,
                            target_value=candidate,
                            source_value=source_value,
                            plan=plan,
                            timeline_values=timeline_values,
                        )
                        if source_locator.get("segment_id"):
                            source_track, source_segment = _find_one_segment(material_source, source_locator, "source")
                            source_asset_id = None
                            declared_material_ids = set()
                        elif operation == "add_overlay" and (source_locator.get("material_id") or source_locator.get("asset_id")):
                            source_asset_id = str(source_locator.get("material_id") or source_locator.get("asset_id"))
                            source_track, source_segment = _prototype_for_asset(
                                material_source, source_asset_id, str(visual.get("object_type", ""))
                            )
                            declared_material_ids = set()
                        else:
                            raise DraftApplyError("source asset locator has no segment prototype; a material-only asset cannot be synthesized safely")

                    if operation == "copy_from_subtitle" and source_track.get("type") != "text":
                        raise DraftApplyError("copy_from_subtitle source must be a text-track segment")
                    auxiliary_text = visual.get("object_type") == "text" and _is_auxiliary_text(group, visual)
                    target_track = (
                        _existing_topmost_text_track(candidate, target_locator)
                        if auxiliary_text
                        else _target_track(
                            candidate, target_locator, str(visual.get("object_type", "text")),
                            prototype_track=source_track,
                        )
                    )
                    if operation == "add_overlay" and source_asset_id:
                        cloned = _clone_segment_from_asset_material(
                            material_source, candidate, source_segment, source_asset_id, clone_asset=False
                        )
                    else:
                        cloned = _clone_segment_closure(
                            material_source, candidate, source_segment,
                            required_material_ids=declared_material_ids,
                            preserve_extra_material_refs=not (
                                phase == "staging" and operation == "copy_from_subtitle"
                            ),
                        )
                    start, duration = _visual_range(group, visual)
                    cloned["target_timerange"] = {"start": start, "duration": duration}
                    if auxiliary_text:
                        _assert_no_track_overlap(target_track, start, duration)
                    if isinstance(cloned.get("source_timerange"), dict):
                        cloned["source_timerange"] = {
                            "start": int(cloned["source_timerange"].get("start", 0) or 0),
                            "duration": duration,
                        }
                    cloned["track_render_index"] = target_track.get("render_index", cloned.get("track_render_index", 0))
                    material = _material_for_segment(candidate, cloned, required=visual.get("object_type") == "text")
                    requested_text = visual.get("text")
                    if operation == "copy_from_subtitle" and visual.get("object_type") == "text":
                        if not isinstance(requested_text, str) or not requested_text:
                            raise DraftApplyError("copy_from_subtitle requires non-empty visual.text")
                        if not isinstance(visual.get("text_ref"), str) or not visual["text_ref"]:
                            raise DraftApplyError("copy_from_subtitle requires visual.text_ref")
                        if not isinstance(visual.get("text_hash"), str) or not visual["text_hash"]:
                            raise DraftApplyError("copy_from_subtitle requires visual.text_hash")
                        if visual["text_hash"] != _text_hash(requested_text):
                            raise DraftApplyError("copy_from_subtitle text_hash does not match visual.text")
                    if requested_text is not None:
                        if visual.get("object_type") != "text":
                            raise DraftApplyError("visual.text is supported only for text objects")
                        if not isinstance(requested_text, str) or not requested_text:
                            raise DraftApplyError("visual.text must be a non-empty string")
                        source_text = _material_text(material) if material else None
                        if operation == "copy_from_subtitle" and source_text != requested_text:
                            raise DraftApplyError("copy_from_subtitle text differs from the current approved subtitle")
                        if material is not None:
                            _set_material_text(material, requested_text)
                    animation_duration = _apply_planned_animation(
                        candidate, cloned, material, visual, animation_inventory
                    )
                    overrides = visual.get("overrides", {})
                    if not isinstance(overrides, dict):
                        raise DraftApplyError("visual.overrides must be an object")
                    defer_overrides = phase == "final" and isinstance(group.get("layout"), dict)
                    if not defer_overrides:
                        for field, descriptor in overrides.items():
                            _apply_override(cloned, material, field, descriptor)
                    target_track["segments"].append(cloned)
                    change = {"group_id": group_id, "operation": operation, "segment_id": cloned["id"], "track_id": target_track.get("id")}
                    if animation_duration is not None:
                        change.update({"animation_resource_id": visual["animation"]["resource_id"], "animation_duration_us": animation_duration})
                    changes.append(change)
                    operations.append((group, visual, cloned, material))
                else:
                    target_value_for_locator = _select_timeline_value(
                        target_locator,
                        target_value=candidate,
                        source_value=source_value,
                        plan=plan,
                        timeline_values=timeline_values,
                    )
                    track, segment = _find_one_segment(target_value_for_locator, target_locator, "target")
                    if target_value_for_locator is not candidate:
                        raise DraftApplyError("visual mutation target must be the requested target timeline")
                    animation_duration: int | None = None
                    if operation == "disable_original":
                        segment["visible"] = False
                        if visual.get("overrides"):
                            raise DraftApplyError("disable_original does not accept overrides")
                    else:
                        material = _material_for_segment(candidate, segment, required=visual.get("object_type") == "text")
                        if operation == "modify_text":
                            text = visual.get("text")
                            if not isinstance(text, str) or not text:
                                raise DraftApplyError("modify_text requires non-empty visual.text")
                            if material is None:
                                raise DraftApplyError("modify_text target has no text material")
                            material = _ensure_private_text_material(candidate, segment, material)
                            _set_material_text(material, text)
                            overrides = visual.get("overrides", {})
                            if not isinstance(overrides, dict):
                                raise DraftApplyError("visual.overrides must be an object")
                        elif operation == "modify_segment":
                            overrides = visual.get("overrides", {})
                            if not isinstance(overrides, dict):
                                raise DraftApplyError("modify_segment overrides must be an object")
                            if visual.get("object_type") == "text" and material is not None:
                                material = _ensure_private_text_material(candidate, segment, material)
                        animation_duration = _apply_planned_animation(
                            candidate, segment, material, visual, animation_inventory
                        )
                        if operation == "modify_text":
                            defer_overrides = phase == "final" and isinstance(group.get("layout"), dict)
                            if not defer_overrides:
                                for field, descriptor in overrides.items():
                                    _apply_override(segment, material, field, descriptor)
                        elif operation == "modify_segment":
                            defer_overrides = phase == "final" and isinstance(group.get("layout"), dict)
                            if not defer_overrides:
                                for field, descriptor in overrides.items():
                                    _apply_override(segment, material, field, descriptor)
                        operations.append((group, visual, segment, material))
                    change = {"group_id": group_id, "operation": operation, "segment_id": segment.get("id"), "track_id": track.get("id")}
                    if animation_duration is not None:
                        change.update({"animation_resource_id": visual["animation"]["resource_id"], "animation_duration_us": animation_duration})
                    changes.append(change)
            except (DraftApplyError, KeyError, TypeError, ValueError) as exc:
                errors.append(f"{path}: {exc}")

        audio = group.get("audio", {"action": "none"})
        if not isinstance(audio, dict):
            errors.append(f"group {group_id}.audio: must be an object")
            continue
        action = audio.get("action", "none")
        if action not in _AUDIO_ACTIONS:
            errors.append(f"group {group_id}.audio: unsupported action {action!r}")
            continue
        if action == "none":
            continue
        try:
            target_locator = audio.get("target_locator")
            if not isinstance(target_locator, dict):
                raise DraftApplyError("target_locator is required")
            target_value_for_locator = _select_timeline_value(
                target_locator,
                target_value=candidate,
                source_value=source_value,
                plan=plan,
                timeline_values=timeline_values,
            )
            if target_value_for_locator is not candidate:
                raise DraftApplyError("audio mutation target must be the requested target timeline")
            if action == "reuse_existing":
                track, segment = _find_one_segment(target_value_for_locator, target_locator, "audio target")
                _verify_asset_identity(_material_for_segment(candidate, segment), audio.get("asset_id"), "audio")
            else:
                source_locator = audio.get("source_locator")
                if not isinstance(source_locator, dict):
                    raise DraftApplyError("audio add/clone requires a source locator")
                audio_source = _select_timeline_value(
                    source_locator,
                    target_value=candidate,
                    source_value=source_value,
                    plan=plan,
                    timeline_values=timeline_values,
                )
                source_asset_id = None
                if source_locator.get("segment_id"):
                    source_track, source_segment = _find_one_segment(audio_source, source_locator, "audio source")
                elif source_locator.get("material_id") or source_locator.get("asset_id"):
                    source_asset_id = str(source_locator.get("material_id") or source_locator.get("asset_id"))
                    source_track, source_segment = _prototype_for_asset(audio_source, source_asset_id, "audio")
                else:
                    raise DraftApplyError("audio add/clone requires a source segment or material locator")
                if source_track.get("type") != "audio":
                    raise DraftApplyError("audio source prototype must be on an audio track")
                _verify_asset_identity(_material_for_segment(audio_source, source_segment), audio.get("asset_id"), "audio")
                track = _target_track(candidate, target_locator, "audio", prototype_track=source_track)
                if source_asset_id:
                    segment = _clone_segment_from_asset_material(
                        audio_source, candidate, source_segment, source_asset_id,
                        clone_asset=action == "clone_asset",
                    )
                else:
                    segment = _clone_segment_closure(audio_source, candidate, source_segment)
                track["segments"].append(segment)

            if track.get("type") != "audio":
                raise DraftApplyError("audio target locator must resolve to an audio track")
            target_range = _audio_range(audio, "target_range")
            source_range = _audio_range(audio, "source_range")
            if action in {"clone_asset", "add_asset"} and target_range is None:
                raise DraftApplyError("new audio operations require a resolved target_range")
            if target_range is not None:
                segment["target_timerange"] = target_range
            if source_range is not None:
                segment["source_timerange"] = source_range
            elif target_range is not None:
                current_source = segment.get("source_timerange")
                if not isinstance(current_source, dict):
                    raise DraftApplyError("audio source_range is unresolved and the source segment has no prototype range")
                segment["source_timerange"] = {"start": int(current_source.get("start", 0)), "duration": target_range["duration"]}
            if "volume" in audio:
                volume = audio["volume"]
                if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not 0 <= volume <= 1:
                    raise DraftApplyError("audio.volume must be numeric from 0 through 1")
                segment["volume"] = volume
                if "last_nonzero_volume" in segment:
                    segment["last_nonzero_volume"] = volume
            _apply_audio_fades(candidate, segment, audio)
            changes.append({"group_id": group_id, "operation": action, "segment_id": segment.get("id"), "track_id": track.get("id")})
        except (DraftApplyError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"group {group_id}.audio: {exc}")

    if phase == "final" and not errors:
        for group in groups:
            if not isinstance(group, dict):
                continue
            motion = group.get("motion", "none")
            group_segments = [segment for group_ref, _visual, segment, _material in operations if str(group_ref.get("id", "")) == str(group.get("id", ""))]
            has_motion_payload = any(_segment_has_motion(candidate, segment) for segment in group_segments)
            if motion not in (None, "none") and not has_motion_payload:
                errors.append(f"group {group.get('id')}: requested motion {motion!r} has no motion payload in the cloned prototype")
            elif motion in (None, "none") and has_motion_payload:
                errors.append(f"group {group.get('id')}: template contains motion but plan declares motion=none")
            elif motion not in (None, "none"):
                warnings.append(f"group {group.get('id')}: motion payload was cloned; visual timing still requires reopened Jianying review")
        if errors:
            return result("packaging_draft_transform", errors=errors, warnings=warnings)
        try:
            layout_warnings, layout_errors = _apply_final_layouts(candidate, source_value, plan, operations, layout_registry)
            warnings.extend(layout_warnings)
            errors.extend(layout_errors)
            if not layout_errors:
                for operation_group, visual, segment, material in operations:
                    if not isinstance(operation_group.get("layout"), dict):
                        continue
                    overrides = visual.get("overrides", {})
                    if not isinstance(overrides, dict):
                        errors.append(f"group {operation_group.get('id')}.visual.overrides must be an object")
                        continue
                    for field, descriptor in overrides.items():
                        try:
                            _apply_override(segment, material, field, descriptor)
                        except (DraftApplyError, KeyError, TypeError, ValueError) as exc:
                            errors.append(f"group {operation_group.get('id')} override {field!r}: {exc}")
        except (DraftApplyError, KeyError, TypeError, ValueError) as exc:
            errors.append(str(exc))

    if errors:
        return result("packaging_draft_transform", errors=errors, warnings=warnings)
    preview_model = None
    if _requires_visual_preview(plan):
        try:
            preview_model = _visual_preview_model(candidate, plan, operations)
        except (DraftApplyError, KeyError, TypeError, ValueError) as exc:
            return result("packaging_draft_transform", errors=[str(exc)], warnings=warnings)
    return result(
        "packaging_draft_transform",
        data={"value": candidate, "changes": changes, "visual_preview_model": preview_model},
        warnings=warnings,
        summary={"change_count": len(changes)},
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validation_errors(report: Any, label: str) -> list[str]:
    if not isinstance(report, dict):
        return [f"{label} returned an invalid report"]
    raw_errors = report.get("errors")
    if isinstance(raw_errors, list):
        errors = [str(error) for error in raw_errors]
    elif raw_errors in (None, ""):
        errors = []
    else:
        errors = [str(raw_errors)]
    if report.get("ok") is False and not errors:
        errors.append(f"{label} reported failure without structured errors")
    return errors


def _validate_clone_backup(
    project: Any,
    backup: Any,
    target_id: str,
    *,
    expected_project_index_sha256: str | None = None,
) -> str:
    if not isinstance(backup, (str, Path)) or not str(backup).strip():
        raise DraftApplyError("editor clone did not return a usable clone backup")
    backup_path = Path(backup).expanduser()
    project_root = getattr(project, "root", None)
    if not backup_path.is_absolute() and project_root is not None:
        backup_path = Path(project_root) / backup_path
    backup_path = backup_path.resolve()
    if not backup_path.is_dir():
        raise DraftApplyError(f"clone backup does not exist: {backup_path}")
    if project_root is not None:
        root_path = Path(project_root).resolve()
        try:
            backup_path.relative_to(root_path)
        except ValueError as exc:
            raise DraftApplyError("clone backup is outside the current draft root") from exc
    manifest_path = backup_path / "manifest.json"
    if not manifest_path.is_file():
        raise DraftApplyError(f"clone backup manifest does not exist: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DraftApplyError(f"clone backup manifest is unreadable: {manifest_path}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise DraftApplyError("clone backup manifest is invalid")
    if project_root is None:
        raise DraftApplyError("clone backup cannot be associated with a draft root")
    root_path = Path(project_root).resolve()
    if Path(str(manifest.get("root", ""))).resolve() != root_path:
        raise DraftApplyError("clone backup belongs to a different draft root")
    if not manifest["files"]:
        raise DraftApplyError("clone backup manifest contains no files")
    manifest_files: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(manifest["files"]):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"].strip():
            raise DraftApplyError(f"clone backup manifest file entry {index} is invalid")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise DraftApplyError(f"clone backup manifest file entry {index} escapes the backup root")
        snapshot_path = (backup_path / relative).resolve()
        try:
            snapshot_path.relative_to(backup_path)
        except ValueError as exc:
            raise DraftApplyError(f"clone backup manifest file entry {index} escapes the backup root") from exc
        if not snapshot_path.is_file():
            raise DraftApplyError(f"clone backup file does not exist: {snapshot_path}")
        expected_hash = item.get("sha256")
        if not isinstance(expected_hash, str) or not expected_hash.strip():
            raise DraftApplyError(f"clone backup manifest file entry {index} has no sha256")
        actual_hash = _file_sha256(snapshot_path)
        if actual_hash != expected_hash:
            raise DraftApplyError(f"clone backup file hash mismatch: {snapshot_path}")
        relative_key = relative.as_posix()
        if relative_key in manifest_files:
            raise DraftApplyError(f"clone backup manifest duplicates file: {relative_key}")
        manifest_files[relative_key] = item
    project_index = getattr(project, "project_index_path", None)
    if not isinstance(project_index, (str, Path)) or not str(project_index).strip():
        raise DraftApplyError("clone backup cannot identify the current project index")
    project_index_path = Path(project_index).resolve()
    try:
        index_relative = project_index_path.relative_to(root_path)
    except ValueError as exc:
        raise DraftApplyError("current project index is outside the draft root") from exc
    index_entry = manifest_files.get(index_relative.as_posix())
    if index_entry is None:
        raise DraftApplyError("clone backup does not contain the current project index")
    if expected_project_index_sha256 is not None and index_entry["sha256"] != expected_project_index_sha256:
        raise DraftApplyError("clone backup project index does not match the pre-clone snapshot")
    try:
        project.decode(project.content_path(target_id))
    except (OSError, RuntimeError, KeyError, TypeError, ValueError) as exc:
        raise DraftApplyError(f"clone backup does not match target timeline {target_id!r}") from exc
    return str(backup_path)


def apply_packaging_plan(
    plan: Any,
    *,
    draft_path: str,
    timeline: str,
    editor_root: Any,
    sound_catalog: dict[str, Any] | None = None,
    sound_pools: dict[str, Any] | None = None,
    animation_cache_root: str | Path | None = None,
    animation_capabilities: dict[str, Any] | None = None,
    animation_version: str | None = None,
    existing_audio: Any = None,
    apply: bool = False,
    project: Any = None,
    editor_api: Any = None,
    temp_root: str | Path | None = None,
) -> dict[str, Any]:
    """Dry-run or apply a validated schema 1.2 packaging plan."""

    if not isinstance(plan, dict):
        return result("packaging_apply", input_errors=["plan must be a JSON object"])
    if plan.get("schema_version") != "1.2":
        return result("packaging_apply", errors=["only schema_version 1.2 can be applied"])
    execution = plan.get("execution") if isinstance(plan.get("execution"), dict) else {}
    if execution.get("mode") != "apply":
        return result("packaging_apply", errors=["execution.mode must be apply for the packaging apply command"])

    validation = validate_plan(plan, sound_catalog=sound_catalog, sound_pools=sound_pools)
    if not validation.get("ok"):
        return result("packaging_apply", data={"validation": validation}, errors=validation.get("errors", []), warnings=validation.get("warnings", []))

    apply_warnings: list[str] = []
    try:
        draft_root = Path(draft_path).resolve()
        if not draft_root.exists():
            return result("packaging_apply", input_errors=[f"draft path does not exist: {draft_root}"])
        plan_source = plan.get("source", {})
        plan_draft = Path(str(plan_source.get("draft_path", ""))).resolve()
        if plan_draft != draft_root:
            return result("packaging_apply", errors=["source.draft_path does not match --draft"])
        if project is None or editor_api is None:
            editor_api = editor_api or _load_editor_api(Path(editor_root))
            project = project or editor_api.JianyingProject(str(draft_root))

        source_selector = str(plan_source.get("timeline", ""))
        selected_entry = project.resolve_timeline(timeline)
        plan_entry = project.resolve_timeline(source_selector)
        source_id = str(selected_entry.get("id", ""))
        if not source_id or source_id != str(plan_entry.get("id", "")):
            return result("packaging_apply", errors=["--timeline does not resolve to source.timeline"])
        replica_warnings: list[str] = []
        if hasattr(project, "validate"):
            source_validation = project.validate(source_id)
            source_errors, replica_warnings = classify_replica_errors(
                _validation_errors(source_validation, "source validation"),
                source_validation.get("replica_manifest"),
            )
            source_validation = {
                **source_validation,
                "ok": not source_errors,
                "errors": source_errors,
                "warnings": [
                    *[str(warning) for warning in source_validation.get("warnings", [])],
                    *replica_warnings,
                ],
            }
            if source_errors:
                return result("packaging_apply", data={"source_validation": source_validation}, errors=source_errors, warnings=replica_warnings)

        source_value = project.decode(project.content_path(source_id)).value
        source_hash = _hash_value(source_value)
        animation_specs = [
            visual.get("animation")
            for group in plan.get("groups", []) if isinstance(group, dict)
            for visual in group.get("visual", []) if isinstance(group.get("visual"), list) and isinstance(visual, dict)
            if visual.get("animation") is not None
        ]
        animation_inventory: dict[str, Any] | None = None
        animation_inventory_path: str | None = None
        if animation_specs:
            cache_root = _animation_cache_root(draft_root, animation_cache_root)
            current_version = _animation_version(project, animation_version)
            inventory_report = build_animation_inventory(
                cache_root,
                _text_intro_entries(),
                jianying_version=current_version,
                capabilities=animation_capabilities,
            )
            if not inventory_report.get("ok"):
                return result(
                    "packaging_apply",
                    data={"source_hash": source_hash, "animation_inventory": inventory_report},
                    errors=inventory_report.get("errors", []),
                    warnings=inventory_report.get("warnings", []),
                )
            temp_base = Path(temp_root) if temp_root is not None else _default_temp_root()
            animation_inventory_path = _write_temp_json(temp_base, "animation-inventories", inventory_report)
            animation_inventory = inventory_report
        timeline_values: dict[str, dict[str, Any]] = {source_selector: source_value, source_id: source_value, "source": source_value}
        required_preset_ids = {
            str(visual.get("preset_id"))
            for group in plan.get("groups", []) if isinstance(group, dict)
            for visual in group.get("visual", []) if isinstance(group.get("visual"), list) and isinstance(visual, dict)
            if visual.get("operation") == "clone_template" and visual.get("preset_id")
        }
        for preset in plan.get("presets", []) if isinstance(plan.get("presets"), list) else []:
            if not isinstance(preset, dict) or str(preset.get("preset_id", "")) not in required_preset_ids:
                continue
            template = preset.get("template_source") if isinstance(preset, dict) else None
            selector = str(template.get("timeline", "")) if isinstance(template, dict) else ""
            if not selector or selector in timeline_values or selector in {"target", str(plan.get("target", {}).get("timeline_name", ""))}:
                continue
            entry = project.resolve_timeline(selector)
            timeline_values[selector] = project.decode(project.content_path(str(entry["id"]))).value

        plan_groups = plan.get("groups", [])
        has_sound_operations = any(
            isinstance(group, dict)
            and isinstance(group.get("audio"), dict)
            and group["audio"].get("action") not in (None, "none")
            for group in plan_groups if isinstance(plan_groups, list)
        )
        sound_warnings: list[str] = list(replica_warnings)
        if has_sound_operations:
            audio_evidence = _normalize_audio_evidence(existing_audio) if existing_audio is not None else _audio_evidence_from_value(source_value)
            sound_report = check_sound_operations(
                plan,
                sound_catalog or {"presets": []},
                sound_pools or {"pools": []},
                audio_evidence,
            )
            sound_warnings.extend(sound_report.get("warnings", []))
            if not sound_report.get("ok"):
                return result("packaging_apply", data={"source_hash": source_hash, "sound_check": sound_report}, errors=sound_report.get("errors", []), warnings=sound_warnings)

        transformed = transform_packaging_plan(
            source_value,
            plan,
            source_value=source_value,
            timeline_values=timeline_values,
            animation_inventory=animation_inventory,
        )
        if not transformed.get("ok"):
            return result("packaging_apply", data={"source_hash": source_hash}, errors=transformed.get("errors", []), warnings=[*sound_warnings, *transformed.get("warnings", [])])
        candidate = transformed["data"]["value"]
        content_validation = editor_api.validate_content(candidate, expected_id=source_id)
        content_errors = _validation_errors(content_validation, "candidate content validation")
        if content_errors:
            return result("packaging_apply", data={"source_hash": source_hash, "candidate_validation": content_validation}, errors=content_errors)

        visual_preview_path: str | None = None
        visual_preview_sha256: str | None = None
        if _requires_visual_preview(plan):
            try:
                preview_html = build_html_preview(transformed["data"]["visual_preview_model"])
                preview_bytes = preview_html.encode("utf-8")
                visual_preview_sha256 = "sha256:" + hashlib.sha256(preview_bytes).hexdigest()
                temp_base = Path(temp_root).resolve() if temp_root is not None else _default_temp_root().resolve()
                visual_preview_path = _write_temp_html(temp_base, "visual-previews", preview_html)
            except (DraftApplyError, VisualPreviewError, OSError, KeyError, TypeError, ValueError) as exc:
                return result("packaging_apply", data={"source_hash": source_hash}, errors=[f"visual preview could not be generated: {exc}"])

        target = plan.get("target", {}) if isinstance(plan.get("target"), dict) else {}
        clone_source = target.get("clone_source") is True
        target_name = str(target.get("timeline_name", ""))
        if clone_source:
            collisions = [entry for entry in project.timeline_entries() if str(entry.get("name", "")).casefold() == target_name.casefold() and str(entry.get("id")) != source_id]
            if collisions:
                return result("packaging_apply", errors=[f"target timeline name {target_name!r} already exists"])

        preview_data = {
            "dry_run": not apply,
            "phase": execution.get("phase"),
            "would_change": bool(transformed["data"].get("changes")),
            "source_timeline_id": source_id,
            "source_timeline_hash": source_hash,
            "target_timeline_name": target_name if clone_source else selected_entry.get("name"),
            "changes": transformed["data"].get("changes", []),
            "draft_writes": 0,
            "clone_created": False,
            "next_step": "Review the dry-run change list; an authorized --apply run is still required for writes.",
            "validation": validation,
            "source_replica_warnings": replica_warnings,
            "animation_inventory_path": animation_inventory_path,
            "visual_preview_path": visual_preview_path,
            "visual_preview_sha256": visual_preview_sha256,
            "native_visual_verification": "pending after reopening Jianying",
        }
        apply_warnings = [*sound_warnings, *transformed.get("warnings", [])]
        if not apply:
            return result("packaging_apply", data=preview_data, warnings=apply_warnings)

        if visual_preview_sha256 is not None:
            review = plan.get("review_report") if isinstance(plan.get("review_report"), dict) else {}
            if review.get("visual_preview_status") != "approved":
                return result("packaging_apply", data=preview_data, errors=["visual preview must be approved before apply"])
            if review.get("visual_preview_sha256") != visual_preview_sha256:
                return result("packaging_apply", data=preview_data, errors=["approved visual preview hash does not match the current candidate preview hash"])

        close_warning = project._assert_editor_closed() if hasattr(project, "_assert_editor_closed") else None
        if close_warning:
            apply_warnings.append(str(close_warning))

        target_id = source_id
        clone_backup = None
        pre_clone_project_index_sha256 = None
        if clone_source:
            project_index = getattr(project, "project_index_path", None)
            if not isinstance(project_index, (str, Path)) or not str(project_index).strip():
                raise DraftApplyError("clone source has no readable project index for backup verification")
            pre_clone_project_index_sha256 = _file_sha256(Path(project_index).resolve())
            try:
                clone_result = project.clone_timeline(source_id, target_name, activate=False)
            except Exception as exc:
                _append_warnings(apply_warnings, getattr(exc, "warnings", None))
                raise
            _append_warnings(apply_warnings, clone_result.get("warnings"))
            if not clone_result.get("ok"):
                return result("packaging_apply", data=preview_data, errors=[str(clone_result.get("error", clone_result))], warnings=apply_warnings)
            target_id = str(clone_result.get("timeline_id", ""))
            clone_backup = clone_result.get("backup")
            if not target_id:
                return result("packaging_apply", data=preview_data, errors=["editor clone did not return a timeline_id"], warnings=apply_warnings)
            clone_backup = _validate_clone_backup(
                project,
                clone_backup,
                target_id,
                expected_project_index_sha256=pre_clone_project_index_sha256,
            )
            clone_base = project.decode(project.content_path(target_id)).value
            expected_clone = _replace_ids(copy.deepcopy(source_value), {source_id: target_id})
            if _canonical_json(clone_base) != _canonical_json(expected_clone):
                return result("packaging_apply", data={**preview_data, "target_timeline_id": target_id, "draft_writes": 1, "clone_created": True}, errors=["new clone does not match the preflight source snapshot; clone was left untouched"], warnings=apply_warnings)
            if hasattr(project, "replica_paths"):
                source_replicas = {Path(path).resolve() for path in project.replica_paths(source_id)}
                target_replicas = {Path(path).resolve() for path in project.replica_paths(target_id)}
                overlap = sorted(str(path) for path in source_replicas & target_replicas)
                if overlap:
                    return result("packaging_apply", data={**preview_data, "target_timeline_id": target_id, "draft_writes": 1, "clone_created": True}, errors=[f"clone replicas overlap source replicas: {overlap}"], warnings=apply_warnings)
            if _hash_value(project.decode(project.content_path(source_id)).value) != source_hash:
                return result("packaging_apply", data={**preview_data, "target_timeline_id": target_id, "draft_writes": 1, "clone_created": True}, errors=["source timeline changed between preflight and clone; clone was left untouched"], warnings=apply_warnings)
        else:
            if not execution.get("allow_in_place") or not execution.get("authorization_note"):
                return result("packaging_apply", data=preview_data, errors=["in-place apply requires the plan's explicit authorized exception"], warnings=apply_warnings)
            clone_base = copy.deepcopy(source_value)

        write_value = _replace_ids(copy.deepcopy(candidate), {source_id: target_id})
        write_value["id"] = target_id
        target_validation = editor_api.validate_content(write_value, expected_id=target_id)
        target_errors = _validation_errors(target_validation, "target content validation")
        if target_errors:
            if clone_source:
                return result("packaging_apply", data={**preview_data, "target_timeline_id": target_id, "draft_writes": 1, "clone_created": True}, errors=target_errors, warnings=apply_warnings)
            return result("packaging_apply", data=preview_data, errors=target_errors, warnings=apply_warnings)

        try:
            write_result = project._write_content(target_id, write_value)
            readback = project.decode(project.content_path(target_id)).value
            if _canonical_json(readback) != _canonical_json(write_value):
                raise DraftApplyError("editor read-back differs from the planned packaging value")
            readback_validation = project.validate(target_id)
            readback_errors = _validation_errors(readback_validation, "editor replica validation")
            if readback_errors:
                raise DraftApplyError("editor replica validation failed: " + "; ".join(readback_errors))
            if clone_source and _hash_value(project.decode(project.content_path(source_id)).value) != source_hash:
                raise DraftApplyError("source timeline fingerprint changed during clone write")
        except Exception as exc:
            rollback_error = None
            target_restored = False
            try:
                project._write_content(target_id, clone_base)
                current_after_failure = project.decode(project.content_path(target_id)).value
                primary_restored = _canonical_json(current_after_failure) == _canonical_json(clone_base)
                rollback_validation = project.validate(target_id)
                target_restored = primary_restored and bool(rollback_validation.get("ok"))
                if not target_restored:
                    validation_errors = rollback_validation.get("errors", [])
                    rollback_error = "rollback validation failed: " + "; ".join(validation_errors) if validation_errors else "read-back after rollback differs from the pre-write clone"
            except Exception as rollback_exc:  # report both the failed operation and failed rollback
                rollback_error = str(rollback_exc)
            errors = [f"packaging write failed: {exc}"]
            if rollback_error:
                errors.append(f"target rollback also failed: {rollback_error}")
            return result("packaging_apply", data={**preview_data, "target_timeline_id": target_id, "draft_writes": 1 if clone_source else 0, "clone_created": clone_source, "target_clone_preserved": target_restored}, errors=errors, warnings=apply_warnings)

        data = {
            **preview_data,
            "dry_run": False,
            "draft_writes": 2 if clone_source else 1,
            "clone_created": clone_source,
            "target_timeline_id": target_id,
            "target_timeline_name": target_name if clone_source else selected_entry.get("name"),
            "backup": write_result.get("backup") or clone_backup,
            "replicas_checked": readback_validation.get("replicas_checked"),
            "readback_matches_plan": True,
            "source_preserved": clone_source and _hash_value(project.decode(project.content_path(source_id)).value) == source_hash,
            "human_visual_audio_review": "pending",
            "phase_state": {
                "packaging_staging": "reviewing" if execution.get("phase") == "staging" else "approved",
                "packaging_final": "not_started" if execution.get("phase") == "staging" else "awaiting_human_visual_audio_review",
            },
            "next_step": (
                "Open the cloned staging timeline in Jianying and review selection, wording, timing, overlap, and obstruction."
                if execution.get("phase") == "staging"
                else "Reopen Jianying and complete visual/audio review; do not report the package as verified yet."
            ),
        }
        return result("packaging_apply", data=data, warnings=apply_warnings)
    except (OSError, RuntimeError, ImportError, AttributeError, DraftApplyError, ValueError, KeyError, TypeError) as exc:
        return result("packaging_apply", input_errors=[f"apply preflight failed: {type(exc).__name__}: {exc}"], warnings=apply_warnings)


def _load_editor_api(editor_root: Path) -> Any:
    scripts = editor_root / "scripts"
    script = scripts / "jianying_project.py"
    if not script.is_file():
        raise FileNotFoundError(f"jianying-editor CLI not found: {script}")
    scripts_text = str(scripts)
    if scripts_text not in sys.path:
        sys.path.insert(0, scripts_text)
    module = importlib.import_module("jianying_project")
    if Path(module.__file__).resolve() != script.resolve():
        raise DraftApplyError("imported jianying_project does not match --editor-root")
    return module


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
