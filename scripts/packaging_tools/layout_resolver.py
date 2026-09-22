"""Resolve relative packaging layout slots without writing Jianying fields."""

from __future__ import annotations

from typing import Any

from .result import result


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and value not in {float("inf"), float("-inf")}


def _templates(registry: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(registry, dict) or not isinstance(registry.get("templates"), list):
        return {}
    templates: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(registry["templates"]):
        if not isinstance(item, dict) or not item.get("template_id"):
            raise ValueError(f"layout registry templates[{index}] must contain template_id")
        template_id = str(item["template_id"])
        if template_id in templates:
            raise ValueError(f"layout registry duplicates template_id {template_id!r}")
        templates[template_id] = item
    return templates


def _resolve_template(template_id: str, templates: dict[str, dict[str, Any]], stack: tuple[str, ...] = ()) -> dict[str, dict[str, Any]]:
    if template_id in stack:
        raise ValueError("template inheritance cycle: " + " -> ".join(stack + (template_id,)))
    template = templates.get(template_id)
    if template is None:
        raise KeyError(f"unknown layout template: {template_id}")
    slots: dict[str, dict[str, Any]] = {}
    parent = template.get("extends")
    if parent:
        slots.update(_resolve_template(str(parent), templates, stack + (template_id,)))
    local_ids: set[str] = set()
    raw_slots = template.get("slots", [])
    if not isinstance(raw_slots, list):
        raise TypeError(f"template {template_id}: slots must be an array")
    for index, slot in enumerate(raw_slots):
        if not isinstance(slot, dict) or not slot.get("id"):
            raise ValueError(f"template {template_id}: slots[{index}] must contain id")
        slot_id = str(slot["id"])
        if slot_id in local_ids:
            raise ValueError(f"template {template_id}: duplicate slot {slot_id!r}")
        local_ids.add(slot_id)
        slots[slot_id] = dict(slot)
    return slots


def resolve_relative_layout(group: Any, registry: Any, anchor: Any) -> dict[str, Any]:
    if not isinstance(group, dict) or not isinstance(anchor, dict):
        return result("packaging_layout_resolution", errors=["group and anchor must be JSON objects"])
    layout = group.get("layout")
    if not isinstance(layout, dict):
        return result("packaging_layout_resolution", errors=[f"group {group.get('id')}: layout must be an object"])
    template_id = layout.get("template_id")
    if not template_id:
        return result("packaging_layout_resolution", errors=[f"group {group.get('id')}: layout.template_id is required"])
    try:
        slots = _resolve_template(str(template_id), _templates(registry))
    except (KeyError, ValueError) as exc:
        return result("packaging_layout_resolution", errors=[str(exc)])
    inline_slots = layout.get("slots", []) or []
    if not isinstance(inline_slots, list):
        return result("packaging_layout_resolution", errors=["layout.slots must be an array"])
    inline_ids: set[str] = set()
    for index, slot in enumerate(inline_slots):
        if not isinstance(slot, dict) or not slot.get("id"):
            return result("packaging_layout_resolution", errors=[f"layout.slots[{index}] must contain id"])
        slot_id = str(slot["id"])
        if slot_id in inline_ids:
            return result("packaging_layout_resolution", errors=[f"layout.slots duplicates id {slot_id!r}"])
        inline_ids.add(slot_id)
        slots[slot_id] = dict(slot)
    x0 = anchor.get("x", anchor.get("x0"))
    y0 = anchor.get("y", anchor.get("y0"))
    if (
        not _number(x0)
        or isinstance(x0, bool)
        or not _number(y0)
        or isinstance(y0, bool)
    ):
        return result("packaging_layout_resolution", errors=["runtime X0/Y0 anchor is unresolved"])
    resolved: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    def visit_transform(slot_id: str, stack: tuple[str, ...] = ()) -> dict[str, Any]:
        if slot_id in stack:
            raise ValueError("slot transform cycle: " + " -> ".join(stack + (slot_id,)))
        slot = slots.get(slot_id)
        if slot is None:
            raise KeyError(f"unknown slot: {slot_id}")
        inherited: dict[str, Any] = {}
        parent_id = slot.get("inherit_transform_from")
        if parent_id:
            inherited.update(visit_transform(str(parent_id), stack + (slot_id,)))
        own = slot.get("transform", {})
        if own is None:
            own = {}
        if not isinstance(own, dict):
            raise TypeError(f"slot {slot_id}: transform must be an object")
        own = dict(own)
        for key in ("scale", "rotation", "alignment", "opacity", "skew"):
            if key in slot:
                if key in own and own[key] != slot[key]:
                    raise ValueError(f"slot {slot_id}: direct and nested transform values conflict for {key}")
                own[key] = slot[key]
        for key, value in own.items():
            if key in inherited and inherited[key] != value:
                raise ValueError(f"slot {slot_id}: inherited transform conflicts for {key}")
            if key in {"scale", "opacity"} and not _number(value) and not isinstance(value, dict):
                raise TypeError(f"slot {slot_id}: transform {key} must be numeric or an object")
            if key == "scale" and isinstance(value, dict) and any(not _number(value.get(axis)) or value.get(axis) <= 0 for axis in ("x", "y")):
                raise TypeError(f"slot {slot_id}: transform scale must be positive")
            if key == "rotation" and not _number(value):
                raise TypeError(f"slot {slot_id}: transform rotation must be numeric")
        inherited.update(own)
        return inherited

    def visit(slot_id: str, stack: tuple[str, ...] = ()) -> dict[str, Any]:
        if slot_id in resolved:
            return resolved[slot_id]
        if slot_id in stack:
            raise ValueError("slot relation cycle: " + " -> ".join(stack + (slot_id,)))
        slot = slots.get(slot_id)
        if slot is None:
            raise KeyError(f"unknown slot: {slot_id}")
        parent_id = slot.get("relative_to")
        parent = visit(str(parent_id), stack + (slot_id,)) if parent_id else {"x": x0, "y": y0}
        offset = slot.get("offset", {}) or {}
        if not isinstance(offset, dict):
            raise TypeError(f"slot {slot_id}: offset must be an object")
        dx, dy = offset.get("dx", 0), offset.get("dy", 0)
        if not _number(dx) or not _number(dy):
            raise TypeError(f"slot {slot_id}: offset must be numeric")
        if isinstance(dx, bool) or isinstance(dy, bool):
            raise TypeError(f"slot {slot_id}: offset must be numeric")
        ref_type = slot.get("ref_type")
        if ref_type not in {"subtitle_unit", "auxiliary_mark"}:
            raise ValueError(f"slot {slot_id}: invalid ref_type")
        value = {
            "x": parent["x"] + dx,
            "y": parent["y"] + dy,
            "transform": visit_transform(slot_id),
            "inherit_transform_from": slot.get("inherit_transform_from"),
            "ref_type": ref_type,
            "text_ref": slot.get("text_ref"),
        }
        resolved[slot_id] = value
        return value

    try:
        for slot_id in slots:
            visit(slot_id)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))
    constraints = layout.get("constraints", {})
    if constraints is None:
        constraints = {}
    if not isinstance(constraints, dict):
        errors.append("layout.constraints must be an object")
        constraints = {}
    if isinstance(constraints, dict):
        safe_zone = constraints.get("safe_zone")
        if isinstance(safe_zone, dict):
            bounds = {key: safe_zone.get(key) for key in ("x_min", "x_max", "y_min", "y_max")}
            if all(_number(value) for value in bounds.values()):
                for slot_id, item in resolved.items():
                    if not (bounds["x_min"] <= item["x"] <= bounds["x_max"] and bounds["y_min"] <= item["y"] <= bounds["y_max"]):
                        errors.append(f"slot {slot_id}: resolved position is outside safe-zone bounds")
        if "collision" in constraints and constraints.get("collision") not in {"warn", "block", "intentional_overlap", "intentional_attachment"}:
            errors.append("layout constraints.collision is invalid")
        if "safe_zone" in constraints and not isinstance(safe_zone, dict):
            errors.append("layout constraints.safe_zone must be an object")
        if isinstance(safe_zone, dict):
            bounds = {key: safe_zone.get(key) for key in ("x_min", "x_max", "y_min", "y_max")}
            if not all(_number(value) for value in bounds.values()):
                errors.append("layout safe-zone bounds must be numeric")
            elif bounds["x_min"] > bounds["x_max"] or bounds["y_min"] > bounds["y_max"]:
                errors.append("layout safe-zone bounds must be ordered")
        if constraints.get("collision") == "block":
            coordinates: dict[tuple[float, float], str] = {}
            for slot_id, item in resolved.items():
                point = (item["x"], item["y"])
                if point in coordinates:
                    errors.append(f"layout collision: slots {coordinates[point]!r} and {slot_id!r} share a position")
                else:
                    coordinates[point] = slot_id
    for slot_id, item in resolved.items():
        slot = slots.get(slot_id, {})
        bounds = slot.get("bounds", slot.get("size")) if isinstance(slot, dict) else None
        if bounds is not None:
            if not isinstance(bounds, dict) or not all(_number(bounds.get(key)) and bounds.get(key) >= 0 for key in ("width", "height")):
                errors.append(f"slot {slot_id}: bounds must contain non-negative numeric width/height")
                continue
            half_width = bounds["width"] / 2
            half_height = bounds["height"] / 2
            if not (-1 <= item["x"] - half_width and item["x"] + half_width <= 1 and -1 <= item["y"] - half_height and item["y"] + half_height <= 1):
                errors.append(f"slot {slot_id}: resolved bounds exceed normalized canvas")
            if isinstance(constraints, dict) and constraints.get("collision") == "block":
                for other_id, other in resolved.items():
                    if other_id == slot_id:
                        continue
                    other_slot = slots.get(other_id, {})
                    other_bounds = other_slot.get("bounds", other_slot.get("size")) if isinstance(other_slot, dict) else None
                    if not isinstance(other_bounds, dict) or not all(_number(other_bounds.get(key)) and other_bounds.get(key) >= 0 for key in ("width", "height")):
                        continue
                    if slot_id >= other_id:
                        continue
                    if (
                        abs(item["x"] - other["x"]) < (bounds["width"] + other_bounds["width"]) / 2
                        and abs(item["y"] - other["y"]) < (bounds["height"] + other_bounds["height"]) / 2
                    ):
                        errors.append(f"layout collision: slot bounds for {slot_id!r} and {other_id!r} overlap")
    return result("packaging_layout_resolution", data={"template_id": template_id, "slots": resolved}, errors=errors, summary={"slot_count": len(resolved)})
