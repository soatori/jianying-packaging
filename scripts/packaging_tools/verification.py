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
TEXT_FIELDS = {"text", "content", "base_content", "recognize_text", "styles", "style"}
NEW_VISUAL_OPERATIONS = {"clone_template", "copy_from_subtitle", "add_overlay"}
NEW_AUDIO_ACTIONS = {"clone_asset", "add_asset"}


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


def _layout_paths(group: dict[str, Any], descriptor: dict[str, Any]) -> set[str]:
    layout = group.get("layout")
    if not isinstance(layout, dict) or not layout or not descriptor.get("text_ref"):
        return set()
    paths = {"clip.transform.x", "clip.transform.y"}
    slots = layout.get("slots")
    for slot in slots if isinstance(slots, list) else []:
        if not isinstance(slot, dict) or slot.get("text_ref") != descriptor.get("text_ref"):
            continue
        transform = slot.get("transform") if isinstance(slot.get("transform"), dict) else {}
        if slot.get("scale") is not None or transform.get("scale") is not None:
            paths.update({"clip.scale.x", "clip.scale.y"})
        if slot.get("rotation") is not None or transform.get("rotation") is not None:
            paths.add("clip.rotation")
    if layout.get("pattern") == "diagonal_stagger":
        paths.add("clip.rotation")
    return paths


def _operation_fields(operation: str, descriptor: dict[str, Any], group: dict[str, Any]) -> dict[str, set[str]]:
    if operation == "disable_original":
        return {"segments": {"visible"}}
    if operation == "modify_text":
        fields = set(TEXT_FIELDS)
        overrides = descriptor.get("overrides")
        overrides = overrides if isinstance(overrides, dict) else {}
        if "position_x" in overrides:
            fields.add("clip.transform.x")
        if "position_y" in overrides:
            fields.add("clip.transform.y")
        if "scale_x" in overrides or "uniform_scale" in overrides:
            fields.add("clip.scale.x")
        if "scale_y" in overrides or "uniform_scale" in overrides:
            fields.add("clip.scale.y")
        if "start_us" in overrides:
            fields.add("target_timerange.start")
        if "duration_us" in overrides:
            fields.add("target_timerange.duration")
        fields.update(set(overrides) & {"visible", "global_alpha"})
        layout_fields = _layout_paths(group, descriptor)
        fields.update(layout_fields)
        return {"segments": fields}
    if operation == "modify_segment":
        fields: set[str] = set()
        overrides = descriptor.get("overrides")
        overrides = overrides if isinstance(overrides, dict) else {}
        if "position_x" in overrides:
            fields.add("clip.transform.x")
        if "position_y" in overrides:
            fields.add("clip.transform.y")
        if "scale_x" in overrides or "uniform_scale" in overrides:
            fields.add("clip.scale.x")
        if "scale_y" in overrides or "uniform_scale" in overrides:
            fields.add("clip.scale.y")
        if "start_us" in overrides:
            fields.add("target_timerange.start")
        if "duration_us" in overrides:
            fields.add("target_timerange.duration")
        fields.update(set(overrides) & {"visible", "global_alpha"})
        fields.update(_layout_paths(group, descriptor))
        material_fields = {"animations"} if descriptor.get("animation") is not None else set()
        return {"segments": fields, "materials": material_fields}
    if operation in NEW_VISUAL_OPERATIONS:
        return {"tracks": {"segments"}}
    if operation == "audio":
        action = descriptor.get("action")
        if action == "reuse_existing":
            fields: set[str] = set()
            if "volume" in descriptor:
                fields.update({"volume", "last_nonzero_volume"})
            if "source_range" in descriptor:
                fields.update({"source_timerange.start", "source_timerange.duration"})
            if "target_range" in descriptor:
                fields.update({"target_timerange.start", "target_timerange.duration"})
            fade_fields = set()
            if "fade_in_us" in descriptor:
                fade_fields.add("fade_in_duration")
            if "fade_out_us" in descriptor:
                fade_fields.add("fade_out_duration")
            return {"segments": fields, "materials": fade_fields}
        if action in NEW_AUDIO_ACTIONS:
            return {"tracks": {"segments"}}
    return {}


def _linked_material_fields(operation: str, descriptor: dict[str, Any], group: dict[str, Any]) -> dict[str, set[str]]:
    if operation == "modify_text":
        fields = set(TEXT_FIELDS)
        overrides = descriptor.get("overrides")
        overrides = overrides if isinstance(overrides, dict) else {}
        if "position_x" in overrides:
            fields.add("transform.x")
        if "position_y" in overrides:
            fields.add("transform.y")
        if "clip.transform.x" in _layout_paths(group, descriptor):
            fields.update({"transform.x", "transform.y"})
        rules = {"text": fields}
        if descriptor.get("animation") is not None:
            rules["sticker_animation"] = {"animations"}
        return rules
    if operation == "modify_segment":
        rules: dict[str, set[str]] = {}
        if descriptor.get("object_type") == "text":
            fields: set[str] = set()
            overrides = descriptor.get("overrides")
            overrides = overrides if isinstance(overrides, dict) else {}
            if "position_x" in overrides:
                fields.add("transform.x")
            if "position_y" in overrides:
                fields.add("transform.y")
            if "clip.transform.x" in _layout_paths(group, descriptor):
                fields.update({"transform.x", "transform.y"})
            rules["text"] = fields
        if descriptor.get("animation") is not None:
            rules["sticker_animation"] = {"animations"}
        return rules
    if operation == "audio" and descriptor.get("action") == "reuse_existing":
        fields = _operation_fields(operation, descriptor, {}).get("materials", set())
        return {"audio_fade": fields} if fields else {}
    return {}


def _changed_paths(before: Any, after: Any, path: str) -> list[str]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        paths: list[str] = []
        for key in sorted(set(before) | set(after)):
            child_path = f"{path}.{key}" if path else str(key)
            if key not in before or key not in after:
                paths.append(child_path)
            else:
                paths.extend(_changed_paths(before[key], after[key], child_path))
        return paths
    return [path]


def _field_allowed(path: str, allowed_fields: set[str]) -> bool:
    if path in allowed_fields:
        return True
    prefixes = TEXT_FIELDS | {"clip.transform", "clip.scale", "transform"}
    return any(path.startswith(field + ".") for field in allowed_fields & prefixes)


def _added_collections(operation: str, descriptor: dict[str, Any]) -> set[str]:
    if operation in NEW_VISUAL_OPERATIONS:
        return {"segments"}
    if operation == "audio" and descriptor.get("action") in NEW_AUDIO_ACTIONS:
        return {"segments"}
    return set()


def _target_specs(plan: dict[str, Any]) -> tuple[dict[str, set[str]], set[str], dict[tuple[str, str], set[str]], dict[str, set[str]], dict[str, dict[str, set[str]]], list[str]]:
    allowed: dict[str, set[str]] = {collection: set() for collection in COLLECTION_ALIASES}
    generic_ids: set[str] = set()
    fields: dict[tuple[str, str], set[str]] = {}
    group_additions: dict[str, set[str]] = {collection: set() for collection in COLLECTION_ALIASES}
    linked_material_fields: dict[str, dict[str, set[str]]] = {}
    errors: list[str] = []
    groups = plan.get("groups", [])
    if not isinstance(groups, list):
        return allowed, generic_ids, fields, group_additions, linked_material_fields, ["plan.groups must be an array"]

    def add_locator(locator: Any, group_id: str, operation: str, descriptor: dict[str, Any], group: dict[str, Any]) -> None:
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
        operation_fields = _operation_fields(operation, descriptor, group)
        for collection, item_id in pairs:
            if collection in {"segments", "*"} and group_id and "segments" in _added_collections(operation, descriptor):
                group_additions.setdefault("direct_segments", set()).add(item_id)
            if collection == "segments":
                for material_type, material_fields in _linked_material_fields(operation, descriptor, group).items():
                    linked_material_fields.setdefault(item_id, {}).setdefault(material_type, set()).update(material_fields)
            if collection == "tracks" and group_id and "segments" in operation_fields.get("tracks", set()):
                group_additions.setdefault(f"track:{item_id}", set()).add(group_id)
            if collection == "*":
                generic_ids.add(item_id)
                for known_collection in COLLECTION_ALIASES:
                    fields.setdefault((known_collection, item_id), set()).update(operation_fields.get(known_collection, set()))
            else:
                allowed[collection].add(item_id)
                fields.setdefault((collection, item_id), set()).update(operation_fields.get(collection, set()))
        if group_id:
            for collection in _added_collections(operation, descriptor):
                group_additions[collection].add(group_id)

    for group in groups:
        if not isinstance(group, dict):
            errors.append("plan.groups entries must be objects")
            continue
        group_id = str(group.get("id", ""))
        if not group_id:
            errors.append("packaging group has no stable id")
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
                    add_locator(visual.get("target_locator"), group_id, str(visual.get("operation", "")), visual, group)
        elif visual_keys:
            errors.append(f"group {group_id}: visual must be an array")
        audio = group.get("audio", group.get("sound"))
        if isinstance(audio, dict) and audio.get("action") not in (None, "none"):
            add_locator(audio.get("target_locator"), group_id, "audio", audio, group)
    return allowed, generic_ids, fields, group_additions, linked_material_fields, errors


def _add_linked_material_permissions(
    before: dict[str, Any],
    after: dict[str, Any],
    linked_material_fields: dict[str, dict[str, set[str]]],
    group_additions: dict[str, set[str]],
    allowed: dict[str, set[str]],
    fields: dict[tuple[str, str], set[str]],
    clone_sources: dict[str, dict[str, Any]],
) -> None:
    snapshots = (before, after)
    segment_indexes: list[dict[str, Any]] = []
    material_indexes: list[dict[str, Any]] = []
    for snapshot in snapshots:
        segment_items, _ = _collection_items(snapshot, "segments")
        material_items, _ = _collection_items(snapshot, "materials")
        segment_indexes.append({(_stable_id(item) or ""): item for item in segment_items if isinstance(item, dict)})
        material_indexes.append({(_stable_id(item) or ""): item for item in material_items if isinstance(item, dict)})

    after_segment_index = segment_indexes[1]
    before_segment_index = segment_indexes[0]
    before_material_index = material_indexes[0]
    after_material_index = material_indexes[1]
    for segment_id, type_fields in linked_material_fields.items():
        segment = after_segment_index.get(segment_id)
        if not isinstance(segment, dict):
            continue
        before_segment = before_segment_index.get(segment_id)
        before_references = []
        if isinstance(before_segment, dict):
            before_references = [before_segment.get("material_id")]
            before_extra = before_segment.get("extra_material_refs")
            if isinstance(before_extra, list):
                before_references.extend(before_extra)
        before_referenced_materials = [
            before_material_index[str(raw_id)]
            for raw_id in before_references
            if raw_id is not None and str(raw_id) in before_material_index
        ]
        references = [segment.get("material_id")]
        extra = segment.get("extra_material_refs")
        if isinstance(extra, list):
            references.extend(extra)
        for raw_id in references:
            if raw_id is None:
                continue
            material_id = str(raw_id)
            material = after_material_index.get(material_id)
            if not isinstance(material, dict):
                continue
            material_fields = type_fields.get(str(material.get("type", "")))
            if material_fields is None:
                continue
            allowed["materials"].add(material_id)
            fields.setdefault(("materials", material_id), set()).update(material_fields)
            if material_id not in before_material_index:
                sources = [
                    source for source in before_referenced_materials
                    if source.get("type") == material.get("type")
                ]
                clone_sources.setdefault(segment_id, {})[material_id] = sources[0] if len(sources) == 1 else None

    before_segments, _ = _collection_items(before, "segments")
    after_segments, _ = _collection_items(after, "segments")
    before_segment_ids = {_stable_id(item) for item in before_segments if isinstance(item, dict)}
    before_material_ids = set(material_indexes[0])

    def string_values(value: Any):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from string_values(child)
        elif isinstance(value, list):
            for child in value:
                yield from string_values(child)

    for segment in after_segments if isinstance(after_segments, list) else []:
        segment_id = _stable_id(segment)
        if segment_id in before_segment_ids or not _item_has_group(segment, group_additions.get("segments", set())):
            continue
        roots = [segment.get("material_id")]
        extra = segment.get("extra_material_refs")
        if isinstance(extra, list):
            roots.extend(extra)
        pending = [str(item) for item in roots if item not in (None, "")]
        seen: set[str] = set()
        while pending:
            material_id = pending.pop()
            if material_id in seen or material_id not in after_material_index:
                continue
            seen.add(material_id)
            if material_id not in before_material_ids:
                allowed["materials"].add(material_id)
                group_additions.setdefault("material_closure", set()).add(material_id)
            pending.extend(
                child for child in string_values(after_material_index[material_id])
                if child in after_material_index and child not in seen
            )


def _item_has_group(item: Any, group_ids: set[str]) -> bool:
    return isinstance(item, dict) and any(str(item.get(key)) in group_ids for key in ("group_id", "packaging_group_id", "target_group_id"))


def _material_clone_source(material_clone_sources: dict[str, dict[str, Any]], segment_id: str, material_id: Any) -> Any:
    return material_clone_sources.get(segment_id, {}).get(str(material_id))


def _fresh_animation_material(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and set(item) == {"id", "type", "multi_language_current", "animations"}
        and item.get("type") == "sticker_animation"
        and item.get("multi_language_current") == "none"
        and isinstance(item.get("animations"), list)
    )


def _material_refs_change_is_planned(
    before_segment: dict[str, Any],
    after_segment: dict[str, Any],
    segment_id: str,
    linked_material_fields: dict[str, dict[str, set[str]]],
    material_clone_sources: dict[str, dict[str, Any]],
    after_material_index: dict[str, Any],
) -> bool:
    before = before_segment.get("extra_material_refs", [])
    after = after_segment.get("extra_material_refs", [])
    if not isinstance(before, list) or not isinstance(after, list):
        return False
    allowed_types = set(linked_material_fields.get(segment_id, {}))
    source_by_clone = material_clone_sources.get(segment_id, {})

    def replaceable(old_ref: Any, new_ref: Any) -> bool:
        source = source_by_clone.get(str(new_ref))
        new_material = after_material_index.get(str(new_ref))
        return (
            isinstance(source, dict)
            and _stable_id(source) == str(old_ref)
            and source.get("type") in allowed_types
            and isinstance(new_material, dict)
            and new_material.get("type") == source.get("type")
        )

    for old_ref, new_ref in zip(before, after):
        if str(old_ref) != str(new_ref) and not replaceable(old_ref, new_ref):
            return False
    if len(after) == len(before):
        return True
    return (
        len(after) == len(before) + 1
        and after[:-1] == before
        and "sticker_animation" in allowed_types
        and str(after[-1]) in source_by_clone
        and source_by_clone[str(after[-1])] is None
        and _fresh_animation_material(after_material_index.get(str(after[-1])))
    )


def _track_segment_additions_are_planned(
    before: Any,
    after: Any,
    group_ids: set[str],
    before_segment_ids: set[str],
    after_segment_index: dict[str, Any],
    fields: dict[tuple[str, str], set[str]],
    linked_material_fields: dict[str, dict[str, set[str]]],
    material_clone_sources: dict[str, dict[str, Any]],
    after_material_index: dict[str, Any],
) -> bool:
    if not isinstance(before, list) or not isinstance(after, list):
        return False

    def ref_id(value: Any) -> str | None:
        if isinstance(value, dict):
            return _stable_id(value)
        return str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) else None

    before_ids = [ref_id(value) for value in before]
    after_ids = [ref_id(value) for value in after]
    if any(item is None for item in before_ids + after_ids):
        return False

    before_by_id = dict(zip(before_ids, before))
    after_by_id = dict(zip(after_ids, after))
    for item_id in set(before_by_id) & set(after_by_id):
        before_item, after_item = before_by_id[item_id], after_by_id[item_id]
        if not isinstance(before_item, dict) or not isinstance(after_item, dict):
            if before_item != after_item:
                return False
            continue
        allowed_fields = fields.get(("segments", item_id), set())
        for field in sorted(set(before_item) | set(after_item)):
            if field in IDENTIFIER_KEYS and str(before_item.get(field, "")) == item_id and after_item.get(field) == before_item.get(field):
                continue
            if field not in before_item or field not in after_item:
                paths = [field]
            else:
                paths = _changed_paths(before_item[field], after_item[field], field)
            if any(
                not (
                    field == "material_id"
                    and path == "material_id"
                    and isinstance(_material_clone_source(material_clone_sources, item_id, after_item.get("material_id")), dict)
                )
                and not (
                    field == "extra_material_refs"
                    and path == "extra_material_refs"
                    and _material_refs_change_is_planned(
                        before_item, after_item, item_id, linked_material_fields,
                        material_clone_sources, after_material_index,
                    )
                )
                and not _field_allowed(path, allowed_fields)
                for path in paths
            ):
                return False

    cursor = 0
    additions: list[str] = []
    for item_id in after_ids:
        if cursor < len(before_ids) and item_id == before_ids[cursor]:
            cursor += 1
        else:
            additions.append(item_id)
    return cursor == len(before_ids) and all(
        item_id not in before_segment_ids
        and _item_has_group(after_segment_index.get(item_id), group_ids)
        for item_id in additions
    )


def _matches_planned(
    collection: str,
    item_id: str,
    item: Any,
    kind: str,
    allowed: dict[str, set[str]],
    generic_ids: set[str],
    group_additions: dict[str, set[str]],
) -> bool:
    if kind == "removed":
        return False
    if kind == "added":
        if collection == "segments":
            return item_id in group_additions.get("direct_segments", set()) or _item_has_group(item, group_additions.get(collection, set()))
        if collection == "materials":
            return item_id in group_additions.get("material_closure", set())
        return False
    if item_id in allowed[collection] or item_id in generic_ids:
        return True
    return False


def _diff_view(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    view_name: str,
    allowed: dict[str, set[str]],
    generic_ids: set[str],
    fields: dict[tuple[str, str], set[str]],
    group_additions: dict[str, set[str]],
    linked_material_fields: dict[str, dict[str, set[str]]],
    material_clone_sources: dict[str, dict[str, Any]],
    errors: list[str],
    changed: list[str],
    unplanned: list[dict[str, Any]],
) -> None:
    before_segments, _ = _collection_items(before, "segments")
    after_segments, _ = _collection_items(after, "segments")
    before_materials, _ = _collection_items(before, "materials")
    after_materials, _ = _collection_items(after, "materials")
    before_segment_ids = {_stable_id(item) for item in before_segments if isinstance(item, dict)}
    _, after_segment_index, _ = _index("segments", after_segments)
    _, after_material_index, _ = _index("materials", after_materials)
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
            shape_only_ids.update(
                item_id
                for item_id, item in after_index.items()
                if item_id not in before_index and _item_has_group(item, group_additions.get(collection, set()))
            )
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
            kind = "added" if before_item is None else "removed" if after_item is None else "changed"
            clone_origins = [
                sources[item_id]
                for sources in material_clone_sources.values()
                if item_id in sources
            ] if collection == "materials" and kind == "added" else []
            clone_source = None
            fresh_animation = False
            if clone_origins:
                source_ids = {_stable_id(source) for source in clone_origins if isinstance(source, dict)}
                if len(source_ids) == 1 and all(isinstance(source, dict) for source in clone_origins):
                    clone_source = next(source for source in clone_origins if isinstance(source, dict))
                    planned = True
                elif all(source is None for source in clone_origins) and _fresh_animation_material(candidate):
                    fresh_animation = True
                    planned = True
                else:
                    planned = False
            else:
                planned = _matches_planned(collection, item_id, candidate, kind, allowed, generic_ids, group_additions)
            if not planned and collection == "tracks" and kind == "changed" and isinstance(before_item, dict) and isinstance(after_item, dict):
                track_paths = _changed_paths(before_item, after_item, "")
                planned = bool(track_paths) and all(
                    path == "segments" and _track_segment_additions_are_planned(
                        before_item.get("segments"), after_item.get("segments"),
                        group_additions.get(f"track:{item_id}", set()),
                        {str(value) for value in before_segment_ids if value is not None},
                        after_segment_index, fields, linked_material_fields,
                        material_clone_sources, after_material_index,
                    )
                    for path in track_paths
                )
            if not planned:
                unplanned.append({"view": view_name, "collection": collection, "id": item_id, "kind": kind})
                continue
            if collection == "materials" and kind == "added" and clone_origins:
                if fresh_animation:
                    continue
                source_item = clone_source
                allowed_fields = fields.get((collection, item_id), set())
                for field in sorted(set(source_item) | set(after_item)):
                    if field == "id":
                        continue
                    if field not in source_item or field not in after_item:
                        paths = [field]
                    else:
                        paths = _changed_paths(source_item[field], after_item[field], field)
                    for path in paths:
                        if not _field_allowed(path, allowed_fields):
                            unplanned.append({"view": view_name, "collection": collection, "id": item_id, "kind": "changed", "field": path})
                continue
            if kind == "changed" and isinstance(before_item, dict) and isinstance(after_item, dict):
                allowed_fields = fields.get((collection, item_id), set())
                stable_id = _stable_id(before_item)
                for field in sorted(set(before_item) | set(after_item)):
                    if field in IDENTIFIER_KEYS and str(before_item.get(field, "")) == stable_id and after_item.get(field) == before_item.get(field):
                        continue
                    if field not in before_item or field not in after_item:
                        paths = [field]
                    else:
                        paths = _changed_paths(before_item[field], after_item[field], field)
                    for path in paths:
                        if collection == "tracks" and field == "segments":
                            if _track_segment_additions_are_planned(
                                before_item[field] if field in before_item else None,
                                after_item[field] if field in after_item else None,
                                group_additions.get(f"track:{item_id}", set()),
                                {str(value) for value in before_segment_ids if value is not None},
                                after_segment_index,
                                fields,
                                linked_material_fields,
                                material_clone_sources,
                                after_material_index,
                            ):
                                continue
                            unplanned.append({"view": view_name, "collection": collection, "id": item_id, "kind": "changed", "field": path})
                            continue
                        if collection == "segments" and field == "material_id" and path == "material_id":
                            segment_clone_source = _material_clone_source(material_clone_sources, item_id, after_item.get("material_id"))
                            if isinstance(segment_clone_source, dict):
                                continue
                        if collection == "segments" and field == "extra_material_refs" and path == "extra_material_refs":
                            if _material_refs_change_is_planned(
                                before_item, after_item, item_id, linked_material_fields,
                                material_clone_sources, after_material_index,
                            ):
                                continue
                        if not _field_allowed(path, allowed_fields):
                            unplanned.append({"view": view_name, "collection": collection, "id": item_id, "kind": "changed", "field": path})


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

    allowed, generic_ids, fields, group_additions, linked_material_fields, plan_errors = _target_specs(plan)
    material_clone_sources: dict[str, dict[str, Any]] = {}
    errors.extend(plan_errors)
    before_source = before.get("source") if isinstance(before.get("source"), dict) else None
    after_source = after.get("source") if isinstance(after.get("source"), dict) else None
    if (before_source is None) != (after_source is None):
        errors.append("before and after must expose the same source snapshot shape")
    source_error_count = len(errors)
    if before_source is not None and after_source is not None:
        _diff_view(before_source, after_source, view_name="source", allowed={key: set() for key in COLLECTION_ALIASES}, generic_ids=set(), fields={}, group_additions={}, linked_material_fields={}, material_clone_sources={}, errors=errors, changed=changed, unplanned=unplanned)
    elif before_source is not None or after_source is not None:
        source_preserved = False
    if len(errors) > source_error_count or any(item.get("view") == "source" for item in unplanned):
        source_preserved = False

    before_target = _view(before, "target") if isinstance(before.get("target"), dict) else before
    after_target = _view(after, "target") if isinstance(after.get("target"), dict) else after
    _add_linked_material_permissions(before_target, after_target, linked_material_fields, group_additions, allowed, fields, material_clone_sources)
    _diff_view(before_target, after_target, view_name="target", allowed=allowed, generic_ids=generic_ids, fields=fields, group_additions=group_additions, linked_material_fields=linked_material_fields, material_clone_sources=material_clone_sources, errors=errors, changed=changed, unplanned=unplanned)

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
