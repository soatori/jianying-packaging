"""Compare packaging snapshots after a read-back performed by editor.

This module is deliberately conservative. It does not infer that an object
belongs to a packaging group merely because it has a similar shape; a target
locator in the approved plan (or an explicit group association) is required.
"""

from __future__ import annotations

from typing import Any

from .result import result


COLLECTION_ALIASES = {
    "tracks": ("tracks",),
    "segments": ("segments",),
    "materials": ("materials",),
    "subtitle_units": ("subtitle_units", "subtitle"),
    "sounds": ("sounds", "sound", "audio"),
    "templates": ("templates",),
}
IDENTIFIER_KEYS = ("id", "segment_id", "material_id", "unit_id", "sound_id", "track_id")
MUTABLE_FIELDS = {
    "text", "content", "base_content", "recognize_text", "styles", "style",
    "start_us", "end_us", "duration_us", "visible", "enable", "layer",
    "track_id", "track_order", "render_index", "media", "material_id", "sound",
    "volume", "position", "transform", "scale", "animation", "transition",
    "overlay", "source_range", "target_range", "source_timerange", "target_timerange",
    "group_id", "packaging_group_id", "target_group_id", "text_ref", "text_hash",
}


def _stable_id(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in IDENTIFIER_KEYS:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _index(collection: str, items: Any) -> tuple[list[str], dict[str, Any], list[str]]:
    if not isinstance(items, list):
        return [], {}, [f"{collection} must be an array"]
    order: list[str] = []
    indexed: dict[str, Any] = {}
    errors: list[str] = []
    for index, item in enumerate(items):
        item_id = _stable_id(item)
        if item_id is None:
            errors.append(f"{collection}[{index}] has no stable id")
            continue
        if item_id in indexed:
            errors.append(f"{collection} duplicates id {item_id!r}")
            continue
        order.append(item_id)
        indexed[item_id] = item
    return order, indexed, errors


def _collection_items(snapshot: dict[str, Any], collection: str) -> tuple[Any, str | None]:
    for alias in COLLECTION_ALIASES[collection]:
        if alias in snapshot:
            return snapshot.get(alias), alias
    return [], None


def _view(snapshot: dict[str, Any], name: str) -> dict[str, Any]:
    value = snapshot.get(name)
    return value if isinstance(value, dict) else snapshot


def _locator_ids(locator: Any) -> list[tuple[str, str]]:
    if not isinstance(locator, dict):
        return []
    pairs: list[tuple[str, str]] = []
    explicit = locator.get("collection")
    if isinstance(explicit, str) and explicit in COLLECTION_ALIASES:
        for key in IDENTIFIER_KEYS:
            if locator.get(key) not in (None, ""):
                return [(explicit, str(locator[key]))]
        if locator.get("id") not in (None, ""):
            return [(explicit, str(locator["id"]))]
        return []
    mapping = (
        ("track_id", "tracks"),
        ("segment_id", "segments"),
        ("material_id", "materials"),
        ("unit_id", "subtitle_units"),
        ("sound_id", "sounds"),
    )
    for key, collection in mapping:
        if locator.get(key) not in (None, ""):
            pairs.append((collection, str(locator[key])))
    if pairs:
        return pairs
    if locator.get("id") not in (None, ""):
        return [("*", str(locator["id"]))]
    return []


def _target_specs(plan: dict[str, Any]) -> tuple[dict[str, set[str]], set[str], set[str], dict[tuple[str, str], set[str]], list[str]]:
    allowed: dict[str, set[str]] = {collection: set() for collection in COLLECTION_ALIASES}
    generic_ids: set[str] = set()
    group_ids: set[str] = set()
    fields: dict[tuple[str, str], set[str]] = {}
    errors: list[str] = []
    groups = plan.get("groups", [])
    if not isinstance(groups, list):
        return allowed, generic_ids, group_ids, fields, ["plan.groups must be an array"]

    def add_locator(locator: Any, group_id: str, operation: Any) -> None:
        if locator is None:
            return
        if not isinstance(locator, dict):
            errors.append(f"group {group_id}: target_locator must be an object")
            return
        if locator.get("timeline") == "source":
            errors.append(f"group {group_id}: target_locator cannot point to the source timeline")
        pairs = _locator_ids(locator)
        if not pairs:
            errors.append(f"group {group_id}: target_locator has no stable identifier")
            return
        operation_fields = set(MUTABLE_FIELDS)
        if operation in {"modify_text", "modify_segment"}:
            operation_fields = {"text", "content", "base_content", "recognize_text", "styles", "style", "text_ref", "text_hash"}
        for collection, item_id in pairs:
            if collection == "*":
                generic_ids.add(item_id)
                for known_collection in COLLECTION_ALIASES:
                    fields.setdefault((known_collection, item_id), set()).update(operation_fields)
            else:
                allowed[collection].add(item_id)
                fields.setdefault((collection, item_id), set()).update(operation_fields)

    for group in groups:
        if not isinstance(group, dict):
            errors.append("plan.groups entries must be objects")
            continue
        group_id = str(group.get("id", ""))
        if not group_id:
            errors.append("packaging group has no stable id")
        group_has_locator = False
        visual_keys = [key for key in ("visual", "visuals", "visual_operations") if key in group]
        visual_values = group.get(visual_keys[0], []) if visual_keys else []
        if "visual" in group:
            visual_values = group.get("visual")
        if visual_keys:
            if not isinstance(visual_values, list):
                errors.append(f"group {group_id}: visual must be an array")
                visual_values = []
            for alias in visual_keys:
                if alias != "visual" and group.get(alias) != visual_values:
                    errors.append(f"group {group_id}: visual aliases disagree ({alias})")
        if isinstance(visual_values, list):
            for visual in visual_values:
                if isinstance(visual, dict):
                    group_has_locator = group_has_locator or isinstance(visual.get("target_locator"), dict)
                    add_locator(visual.get("target_locator"), group_id, visual.get("operation"))
        elif visual_keys:
            errors.append(f"group {group_id}: visual must be an array")
        audio = group.get("audio", group.get("sound"))
        if isinstance(audio, dict) and audio.get("action") not in (None, "none"):
            group_has_locator = group_has_locator or isinstance(audio.get("target_locator"), dict)
            add_locator(audio.get("target_locator"), group_id, "audio")
        if group_has_locator:
            group_ids.add(group_id)
    return allowed, generic_ids, group_ids, fields, errors


def _matches_planned(collection: str, item_id: str, item: Any, allowed: dict[str, set[str]], generic_ids: set[str], group_ids: set[str]) -> bool:
    if item_id in allowed[collection] or item_id in generic_ids:
        return True
    if isinstance(item, dict):
        return any(str(item.get(key)) in group_ids for key in ("group_id", "packaging_group_id", "target_group_id"))
    return False


def _diff_view(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    view_name: str,
    allowed: dict[str, set[str]],
    generic_ids: set[str],
    group_ids: set[str],
    fields: dict[tuple[str, str], set[str]],
    errors: list[str],
    changed: list[str],
    unplanned: list[dict[str, Any]],
) -> None:
    for collection in COLLECTION_ALIASES:
        before_items, _ = _collection_items(before, collection)
        after_items, _ = _collection_items(after, collection)
        before_order, before_index, before_errors = _index(collection, before_items)
        after_order, after_index, after_errors = _index(collection, after_items)
        errors.extend(f"{view_name} before: {error}" for error in before_errors)
        errors.extend(f"{view_name} after: {error}" for error in after_errors)
        if before_order != after_order:
            allowed_ids = allowed[collection] | generic_ids
            # Planned additions/removals may change the collection shape, but
            # an existing item's relative order is never implicitly authorized
            # by merely targeting that item.
            shape_only_ids = {
                item_id
                for item_id in allowed_ids
                if (item_id in before_index) != (item_id in after_index)
            }
            before_remaining = [item_id for item_id in before_order if item_id not in shape_only_ids]
            after_remaining = [item_id for item_id in after_order if item_id not in shape_only_ids]
            if before_remaining != after_remaining:
                unplanned.append({"view": view_name, "collection": collection, "kind": "order_changed", "before": before_order, "after": after_order})
            else:
                changed.append(f"{view_name}:{collection}:order")
        for item_id in sorted(set(before_index) | set(after_index)):
            before_item = before_index.get(item_id)
            after_item = after_index.get(item_id)
            if before_item == after_item:
                continue
            changed.append(f"{view_name}:{collection}:{item_id}")
            candidate = after_item if after_item is not None else before_item
            planned = _matches_planned(collection, item_id, candidate, allowed, generic_ids, group_ids)
            kind = "added" if before_item is None else "removed" if after_item is None else "changed"
            if not planned:
                unplanned.append({"view": view_name, "collection": collection, "id": item_id, "kind": kind})
                continue
            if kind == "changed" and isinstance(before_item, dict) and isinstance(after_item, dict):
                allowed_fields = fields.get((collection, item_id), set(MUTABLE_FIELDS))
                for field in sorted(set(before_item) | set(after_item)):
                    if field in {"id", "segment_id", "material_id", "unit_id", "sound_id", "track_id"}:
                        continue
                    if before_item.get(field) != after_item.get(field) and field not in allowed_fields:
                        unplanned.append({"view": view_name, "collection": collection, "id": item_id, "kind": "changed", "field": field})


def _find_locator(collection: str, item_id: str, snapshot: dict[str, Any]) -> bool:
    items, _ = _collection_items(snapshot, collection)
    _, indexed, _ = _index(collection, items)
    return item_id in indexed


def verify_packaging_result(before: Any, after: Any, plan: Any) -> dict[str, Any]:
    if not isinstance(before, dict) or not isinstance(after, dict) or not isinstance(plan, dict):
        return result("packaging_verification", input_errors=["before, after and plan must be JSON objects"])
    errors: list[str] = []
    changed: list[str] = []
    unplanned: list[dict[str, Any]] = []
    before_hash = before.get("source_timeline_hash")
    after_hash = after.get("source_timeline_hash")
    if not isinstance(before_hash, str) or not before_hash.strip():
        errors.append("before.source_timeline_hash is required")
    if not isinstance(after_hash, str) or not after_hash.strip():
        errors.append("after.source_timeline_hash is required")
    source_preserved = bool(isinstance(before_hash, str) and before_hash.strip() and isinstance(after_hash, str) and after_hash.strip() and before_hash == after_hash)
    if isinstance(before_hash, str) and before_hash.strip() and isinstance(after_hash, str) and after_hash.strip() and before_hash != after_hash:
        errors.append("source timeline fingerprint changed")

    allowed, generic_ids, group_ids, fields, plan_errors = _target_specs(plan)
    errors.extend(plan_errors)
    before_source = before.get("source") if isinstance(before.get("source"), dict) else None
    after_source = after.get("source") if isinstance(after.get("source"), dict) else None
    if (before_source is None) != (after_source is None):
        errors.append("before and after must expose the same source snapshot shape")
    source_error_count = len(errors)
    if before_source is not None and after_source is not None:
        _diff_view(before_source, after_source, view_name="source", allowed={key: set() for key in COLLECTION_ALIASES}, generic_ids=set(), group_ids=set(), fields={}, errors=errors, changed=changed, unplanned=unplanned)
    elif before_source is not None or after_source is not None:
        source_preserved = False
    if len(errors) > source_error_count or any(item.get("view") == "source" for item in unplanned):
        source_preserved = False

    before_target = _view(before, "target") if isinstance(before.get("target"), dict) else before
    after_target = _view(after, "target") if isinstance(after.get("target"), dict) else after
    _diff_view(before_target, after_target, view_name="target", allowed=allowed, generic_ids=generic_ids, group_ids=group_ids, fields=fields, errors=errors, changed=changed, unplanned=unplanned)

    missing_plan_items: list[dict[str, Any]] = []
    groups = plan.get("groups", []) if isinstance(plan.get("groups"), list) else []
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("id", ""))
        locators: list[tuple[str, Any, str]] = []
        visual_keys = [key for key in ("visual", "visuals", "visual_operations") if key in group]
        visual_values = group.get("visual", group.get(visual_keys[0], [])) if visual_keys else []
        for visual in visual_values if isinstance(visual_values, list) else []:
            if isinstance(visual, dict) and isinstance(visual.get("target_locator"), dict):
                locators.append(("visual", visual.get("target_locator"), str(visual.get("operation", ""))))
        audio = group.get("audio", group.get("sound"))
        if isinstance(audio, dict) and audio.get("action") not in (None, "none") and isinstance(audio.get("target_locator"), dict):
            locators.append(("audio", audio.get("target_locator"), str(audio.get("action", ""))))
        for kind, locator, operation in locators:
            pairs = _locator_ids(locator)
            for collection, item_id in pairs:
                if collection == "*":
                    found = any(_find_locator(candidate, item_id, after_target) for candidate in COLLECTION_ALIASES)
                else:
                    found = _find_locator(collection, item_id, after_target)
                if not found and operation not in {"disable_original", "none"}:
                    missing_plan_items.append({"group_id": group_id, "kind": kind, "operation": operation, "collection": collection, "id": item_id})
    if missing_plan_items:
        errors.append("planned packaging targets are missing from read-back")
    if unplanned:
        errors.append("unplanned packaging changes detected")
    source_preserved = source_preserved and not any(item.get("view") == "source" for item in unplanned)
    return result(
        "packaging_verification",
        data={
            "changed_ids": changed,
            "unplanned_changes": unplanned,
            "missing_plan_items": missing_plan_items,
            "source_preserved": source_preserved,
            "allowed_target_ids": {collection: sorted(values) for collection, values in allowed.items() if values},
        },
        errors=errors,
        summary={"changed_count": len(changed), "unplanned_change_count": len(unplanned), "missing_plan_item_count": len(missing_plan_items)},
    )
