"""Diff current packaging state against a saved manual reference."""

from __future__ import annotations

from typing import Any

from .result import result


def _id(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in ("id", "track_id", "segment_id", "material_id", "unit_id", "sound_id"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return None


COLLECTION_ALIASES = {
    "tracks": ("tracks",),
    "segments": ("segments",),
    "materials": ("materials",),
    "subtitle_units": ("subtitle_units", "subtitle"),
    "sounds": ("sounds", "sound", "audio"),
    "templates": ("templates",),
}


def _collection_items(snapshot: dict[str, Any], collection: str) -> Any:
    for alias in COLLECTION_ALIASES[collection]:
        if alias in snapshot:
            return snapshot.get(alias)
    return []


def _index(collection: str, items: Any) -> tuple[list[str], dict[str, Any], list[str]]:
    if not isinstance(items, list):
        return [], {}, [f"{collection} must be an array"]
    ids: list[str] = []
    indexed: dict[str, Any] = {}
    errors: list[str] = []
    for index, item in enumerate(items):
        item_id = _id(item)
        if item_id is None:
            errors.append(f"{collection}[{index}] has no stable id")
            continue
        if item_id in indexed:
            errors.append(f"{collection} duplicates id {item_id!r}")
            continue
        ids.append(item_id)
        indexed[item_id] = item
    return ids, indexed, errors


def diff_manual_reference(current: Any, reference: Any) -> dict[str, Any]:
    if not isinstance(current, dict) or not isinstance(reference, dict):
        return result("packaging_reference_diff", errors=["current and reference must be JSON objects"])

    changes: list[dict[str, Any]] = []
    errors: list[str] = []
    for collection in COLLECTION_ALIASES:
        current_ids, left, current_errors = _index(collection, _collection_items(current, collection))
        reference_ids, right, reference_errors = _index(collection, _collection_items(reference, collection))
        errors.extend(f"current: {error}" for error in current_errors)
        errors.extend(f"reference: {error}" for error in reference_errors)
        if current_ids != reference_ids:
            errors.append(f"{collection} order changed; manual reference remap is blocked")
        for item_id in sorted(set(left) | set(right)):
            if item_id not in left:
                changes.append({"kind": "removed_from_current", "collection": collection, "id": item_id})
                continue
            if item_id not in right:
                changes.append({"kind": "added_to_current", "collection": collection, "id": item_id})
                continue
            before = right[item_id] if isinstance(right[item_id], dict) else {}
            after = left[item_id] if isinstance(left[item_id], dict) else {}
            ignored = {"id", "segment_id", "material_id", "track_id"}
            for key in sorted((set(before) | set(after)) - ignored):
                if before.get(key) != after.get(key):
                    changes.append({"kind": "changed", "collection": collection, "id": item_id, "field": key, "reference": before.get(key), "current": after.get(key)})

    return result(
        "packaging_reference_diff",
        data={"changes": changes, "manual_changes_present": bool(changes)},
        errors=errors,
        summary={"change_count": len(changes)},
    )
