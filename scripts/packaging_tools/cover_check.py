"""Cover check: detect subtitle originals left visible under upper-track copies.

Staging copies that sit on the same time position as a still-visible original
produce doubled text; the covered originals must be disabled on the clone
(jianying-packaging staging reference, step 6b). This module provides the
mechanical guard so the omission fails an automated check instead of being
noticed by eye.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .result import result

DEFAULT_TOLERANCE_US = 40_000


def _segment_view(value: dict[str, Any], segment: dict[str, Any]) -> dict[str, Any]:
    material_id = segment.get("material_id")
    text = ""
    for mat in (value.get("materials", {}) or {}).get("texts") or []:
        if isinstance(mat, dict) and mat.get("id") == material_id:
            try:
                text = str(json.loads(mat.get("content") or "{}").get("text", ""))
            except (TypeError, ValueError):
                text = ""
            break
    tt = segment.get("target_timerange") or {}
    start = int(tt.get("start") or 0)
    duration = int(tt.get("duration") or 0)
    return {
        "segment_id": segment.get("id"),
        "material_id": material_id,
        "text": text,
        "start_us": start,
        "end_us": start + duration,
        "visible": segment.get("visible", True) is not False,
    }


def find_visible_covered_duplicates(value: dict[str, Any], tolerance_us: int = DEFAULT_TOLERANCE_US) -> list[dict[str, Any]]:
    """Cross-track duplicates: a visible upper copy whose visible original is still rendered below."""
    text_tracks = [
        (track, [_segment_view(value, s) for s in track.get("segments") or [] if isinstance(s, dict)])
        for track in value.get("tracks") or []
        if isinstance(track, dict) and track.get("type") == "text"
    ]
    duplicates: list[dict[str, Any]] = []
    for upper_index in range(len(text_tracks)):
        for lower_index in range(upper_index):  # later array index renders on top
            upper_track, upper_segments = text_tracks[upper_index]
            lower_track, lower_segments = text_tracks[lower_index]
            for up in upper_segments:
                if not up["visible"]:
                    continue
                for low in lower_segments:
                    if not low["visible"]:
                        continue
                    delta = abs(up["start_us"] - low["start_us"])
                    overlap = min(up["end_us"], low["end_us"]) - max(up["start_us"], low["start_us"])
                    if delta <= tolerance_us and overlap > tolerance_us:
                        duplicates.append({
                            "lower_track_id": lower_track.get("id"),
                            "upper_track_id": upper_track.get("id"),
                            "original": low,
                            "copy": up,
                            "delta_start_us": delta,
                            "overlap_us": overlap,
                            "same_text": low["text"] == up["text"],
                        })
    return duplicates


def check_covered_originals(
    draft_path: str,
    timeline: str = "active",
    *,
    editor_api: Any = None,
    project: Any = None,
    editor_root: str | None = None,
    dll_path: str | None = None,
    tolerance_us: int = DEFAULT_TOLERANCE_US,
    content_value: dict[str, Any] | None = None,
    timeline_id: str | None = None,
) -> dict[str, Any]:
    """Decode the timeline (or accept content_value) and report visible covered originals."""
    value = content_value
    try:
        if value is None:
            if editor_api is None:
                from .draft_apply import _load_editor_api
                root = editor_root or str(Path(__file__).resolve().parents[2] / "jianying-editor-skill")
                editor_api = _load_editor_api(Path(root))
            if project is None:
                project = editor_api.JianyingProject(str(draft_path), dll_path) if dll_path else editor_api.JianyingProject(str(draft_path))
            if timeline_id is None:
                timeline_id = str(project.resolve_timeline(timeline)["id"])
            value = project.decode(project.content_path(timeline_id)).value
    except Exception as exc:  # noqa: BLE001 - report decode failures as input errors
        return result("cover_check", errors=[f"cannot decode timeline {timeline!r}: {exc}"],
                      input_errors=[f"cannot decode timeline {timeline!r}: {exc}"])

    duplicates = find_visible_covered_duplicates(value or {}, tolerance_us=tolerance_us)
    exact = [d for d in duplicates if d["same_text"]]
    warnings = [
        "covered original still visible: lower %s segment %s under upper %s segment %s (start Δ%dµs, overlap %dms)%s"
        % (d["lower_track_id"], (d["original"] or {}).get("segment_id"), d["upper_track_id"],
           (d["copy"] or {}).get("segment_id"), d["delta_start_us"], d["overlap_us"] // 1000,
           " — 按 staging 参考 6b 立即在克隆禁用或明确挂起待批" if d["same_text"] else "")
        for d in duplicates
    ]
    return result(
        "cover_check",
        data={
            "timeline_id": timeline_id,
            "tolerance_us": tolerance_us,
            "visible_covered_duplicates": len(duplicates),
            "exact_text_duplicates": len(exact),
            "duplicates": duplicates,
        },
        warnings=warnings,
        summary={
            "duplicates": len(duplicates),
            "exact_text_duplicates": len(exact),
            "clean": not duplicates,
        },
    )
