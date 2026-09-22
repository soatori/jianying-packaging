"""Normalize an editor observation for packaging-only comparisons."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .result import result


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "content", "base_content", "recognize_text"):
            nested = _text(value.get(key))
            if nested:
                return nested
        for nested_value in value.values():
            nested = _text(nested_value)
            if nested:
                return nested
    if isinstance(value, list):
        for nested_value in value:
            nested = _text(nested_value)
            if nested:
                return nested
    return ""


def build_packaging_snapshot(observation: Any) -> dict[str, Any]:
    if not isinstance(observation, dict):
        return result("packaging_snapshot", errors=["observation must be a JSON object"])

    snapshot = copy.deepcopy(observation)
    for key in ("tracks", "segments", "materials", "subtitle_units", "sounds", "templates", "fonts"):
        value = snapshot.get(key)
        if value is None:
            snapshot[key] = []
        elif not isinstance(value, list):
            return result("packaging_snapshot", errors=[f"{key} must be a list"])

    for item in snapshot["subtitle_units"]:
        if isinstance(item, dict):
            text = _text(item)
            if text and "text_hash" not in item:
                item["text_hash"] = _hash(text)

    orders: dict[str, str] = {}
    for track in snapshot["tracks"]:
        if not isinstance(track, dict):
            continue
        track_id = str(track.get("id", track.get("track_id", "unknown")))
        segments = track.get("segments", [])
        order = [str(item.get("id", item.get("segment_id", ""))) for item in segments if isinstance(item, dict)]
        orders[track_id] = _hash(order)
    snapshot["order_hashes"] = orders
    snapshot["snapshot_hash"] = _hash(snapshot)
    return result("packaging_snapshot", data=snapshot, summary={"track_count": len(snapshot["tracks"]), "segment_count": len(snapshot["segments"])})
