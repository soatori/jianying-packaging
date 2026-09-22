"""Classify audio events so music/ambience are not counted as SFX."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .result import result


def _audio_role(item: dict[str, Any]) -> str:
    for key in ("role", "event_type", "kind", "track_role"):
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip().lower()
        if value in {"music", "bgm", "background_music"}:
            return "music"
        if value in {"ambience", "atmosphere", "bed"}:
            return "ambience"
        if value in {"dialogue", "voice", "speech", "spoken"}:
            return "dialogue"
        if value in {"sfx", "sound_effect", "effect"}:
            return "sfx"
    return "unknown"


def classify_audio_events(observation: Any) -> dict[str, Any]:
    if not isinstance(observation, dict):
        return result("packaging_audio_inventory", errors=["observation must be an object"])
    events = observation.get("audio_events", observation.get("sounds", observation.get("audio", [])))
    if not isinstance(events, list):
        return result("packaging_audio_inventory", errors=["audio_events/sounds/audio must be an array"])
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    warnings: list[str] = []
    for index, item in enumerate(events):
        if not isinstance(item, dict):
            warnings.append(f"audio_events[{index}] is not an object")
            continue
        row = dict(item)
        row["id"] = str(row.get("id", row.get("sound_id", f"audio-{index + 1}")))
        row["audio_role"] = _audio_role(row)
        if row["audio_role"] == "unknown":
            warnings.append(f"audio_events[{index}] has no supported audio role; review before counting or applying")
        counts[row["audio_role"]] += 1
        rows.append(row)
    return result(
        "packaging_audio_inventory",
        data={"events": rows, "counts": dict(counts)},
        warnings=warnings,
        summary={"event_count": len(rows), **{f"{key}_count": value for key, value in counts.items()}},
    )
