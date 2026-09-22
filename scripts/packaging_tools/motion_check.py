"""Check semantic motion reuse without forcing every text layer to animate."""

from __future__ import annotations

from typing import Any

from .result import result


STATIC_MOTIONS = {None, "", "none", "static", "continuation", "static_continuation"}


def _declared_region(item: dict[str, Any]) -> str | None:
    for key in ("content_region_id", "semantic_region", "section_id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _assign_content_regions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign playback-local content regions without comparing the whole film."""
    normalized: list[dict[str, Any]] = []
    inferred_index = 0
    current_region: str | None = None
    current_source = "inferred"
    for item in events:
        event = dict(item)
        declared = _declared_region(event)
        breaks_before = bool(
            event.get("region_break_before")
            or event.get("section_break_before")
            or event.get("content_boundary_before")
        )
        if declared is not None:
            current_region = declared
            current_source = "declared"
        elif current_region is None or breaks_before:
            inferred_index += 1
            current_region = f"inferred-{inferred_index}"
            current_source = "boundary" if breaks_before else "inferred"
        event["content_region_id"] = current_region
        event["content_region_source"] = current_source
        normalized.append(event)
    return normalized


def check_motion_reuse(observation: Any, adjacent_window: int = 1) -> dict[str, Any]:
    if not isinstance(observation, dict):
        return result("packaging_motion_check", errors=["observation must be an object"])
    events = observation.get("motion_events", observation.get("groups", []))
    if not isinstance(events, list):
        return result("packaging_motion_check", errors=["motion_events or groups must be an array"])
    if not isinstance(adjacent_window, int) or adjacent_window < 1:
        return result("packaging_motion_check", input_errors=["adjacent_window must be a positive integer"])
    normalized: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, item in enumerate(events):
        if not isinstance(item, dict):
            errors.append(f"motion_events[{index}] must be an object")
            continue
        event = dict(item)
        event["id"] = str(event.get("id", f"motion-{index + 1}"))
        event["motion_family"] = event.get("motion_family", event.get("motion", event.get("animation")))
        normalized.append(event)
    normalized.sort(key=lambda item: ((item.get("start_us") if isinstance(item.get("start_us"), int) else 0), item["id"]))
    normalized = _assign_content_regions(normalized)
    repeated: list[dict[str, Any]] = []
    for index, current in enumerate(normalized):
        motion = current.get("motion_family")
        if motion in STATIC_MOTIONS:
            continue
        for previous in normalized[max(0, index - adjacent_window):index]:
            if previous.get("content_region_id") != current.get("content_region_id"):
                continue
            if previous.get("motion_family") != motion or previous.get("motion_family") in STATIC_MOTIONS:
                continue
            same_motif = (
                isinstance(current.get("motif_id"), str)
                and bool(current.get("motif_id"))
                and current.get("motif_id") == previous.get("motif_id")
            )
            both_intentional = bool(current.get("intentional_motif")) and bool(previous.get("intentional_motif"))
            intentional = same_motif or both_intentional
            if not intentional:
                repeated.append({
                    "previous_id": previous["id"],
                    "current_id": current["id"],
                    "motion_family": motion,
                    "content_region_id": current["content_region_id"],
                    "scope": "adjacent_region",
                    "same_region": True,
                })
    warnings = [
        f"adjacent-region motion reuse: {item['previous_id']} -> {item['current_id']} uses {item['motion_family']!r} in {item['content_region_id']!r}; declare a shared motif when deliberate"
        for item in repeated
    ]
    region_ids = [item["content_region_id"] for item in normalized]
    return result(
        "packaging_motion_check",
        data={
            "events": normalized,
            "repeated": repeated,
            "static_events": [item["id"] for item in normalized if item.get("motion_family") in STATIC_MOTIONS],
            "scope": "adjacent_region",
        },
        errors=errors,
        warnings=warnings,
        summary={
            "event_count": len(normalized),
            "region_count": len(set(region_ids)),
            "repeated_count": len(repeated),
            "static_count": sum(item.get("motion_family") in STATIC_MOTIONS for item in normalized),
        },
    )
