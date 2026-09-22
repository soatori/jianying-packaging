"""Discover packaging layers from observed relationships, not fixed track counts."""

from __future__ import annotations

from typing import Any

from .result import result


BASELINE_ROLES = {"baseline", "subtitle", "caption", "source_subtitle"}
AUXILIARY_ROLES = {"auxiliary", "mark", "question_mark", "slash", "label"}
CONTINUATION_ROLES = {"continuation", "static_continuation"}


def _role(track: dict[str, Any]) -> str | None:
    for key in ("role", "layer_role", "semantic_role"):
        value = track.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def discover_packaging_layers(observation: Any) -> dict[str, Any]:
    if not isinstance(observation, dict):
        return result("packaging_layer_discovery", errors=["observation must be an object"])
    tracks = observation.get("tracks", [])
    if not isinstance(tracks, list):
        return result("packaging_layer_discovery", errors=["tracks must be an array"])
    text_tracks = [track for track in tracks if isinstance(track, dict) and track.get("type") == "text"]
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for order, track in enumerate(text_tracks):
        segments = track.get("segments", []) if isinstance(track.get("segments", []), list) else []
        render_indices = [segment.get("track_render_index") for segment in segments if isinstance(segment, dict) and isinstance(segment.get("track_render_index"), int)]
        explicit = _role(track)
        if explicit in BASELINE_ROLES:
            relation = "baseline"
        elif explicit in AUXILIARY_ROLES:
            relation = "auxiliary"
        elif explicit in CONTINUATION_ROLES:
            relation = "continuation"
        elif explicit in {"emphasis", "upper", "highlight", "secondary"}:
            relation = "emphasis"
        else:
            relation = "unresolved"
        rows.append({
            "track_id": track.get("id", track.get("track_id")),
            "track_order": order,
            "track_render_indices": sorted(set(render_indices)),
            "segment_count": len(segments),
            "explicit_role": explicit,
            "relation": relation,
        })

    unresolved = [row for row in rows if row["relation"] == "unresolved"]
    if unresolved:
        explicit_baseline = any(row["relation"] == "baseline" for row in rows)
        if explicit_baseline:
            for row in unresolved:
                row["relation"] = "emphasis"
        else:
            # Infer only from unresolved tracks. Explicit auxiliary and
            # continuation relations are observations, not candidates for
            # replacement by a guessed baseline.
            ordered_unresolved = sorted(
                unresolved,
                key=lambda row: (row["track_render_indices"] or [10**9], row["track_order"]),
            )
            ordered_unresolved[0]["relation"] = "baseline"
            for row in ordered_unresolved[1:]:
                row["relation"] = "emphasis"
        warnings.append("some text layer roles were inferred from relative render order")
    baseline = [row["track_id"] for row in rows if row["relation"] == "baseline"]
    if len(baseline) != 1:
        warnings.append(f"layer discovery found {len(baseline)} baseline text tracks; review the source relationship")
    return result(
        "packaging_layer_discovery",
        data={
            "layers": rows,
            "baseline_track_ids": baseline,
            "emphasis_track_ids": [row["track_id"] for row in rows if row["relation"] == "emphasis"],
            "auxiliary_track_ids": [row["track_id"] for row in rows if row["relation"] == "auxiliary"],
            "continuation_track_ids": [row["track_id"] for row in rows if row["relation"] == "continuation"],
        },
        warnings=warnings,
        summary={"text_track_count": len(rows), "baseline_count": len(baseline)},
    )
