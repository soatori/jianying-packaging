#!/usr/bin/env python3
"""Validate the generic relative-layout template registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALIGNMENTS = {"left", "center", "right", "top", "middle", "bottom"}
REF_TYPES = {"subtitle_unit", "auxiliary_mark"}
COLLISION_POLICIES = {"warn", "block", "intentional_overlap", "intentional_attachment"}


def _has_parent_cycle(parents: dict[str, str]) -> bool:
    for start in parents:
        path: set[str] = set()
        current = start
        while current in parents:
            if current in path:
                return True
            path.add(current)
            current = parents[current]
    return False


def _validate_slot_transform(path: str, slot: dict[str, Any], errors: list[str]) -> None:
    scale = slot.get("scale")
    if scale is not None:
        if isinstance(scale, dict):
            for axis in ("x", "y"):
                if not isinstance(scale.get(axis), (int, float)) or isinstance(scale.get(axis), bool) or scale[axis] <= 0:
                    errors.append(f"{path}.scale.{axis} must be positive")
        elif not isinstance(scale, (int, float)) or isinstance(scale, bool) or scale <= 0:
            errors.append(f"{path}.scale must be positive or an x/y object")
    if "rotation" in slot and (not isinstance(slot.get("rotation"), (int, float)) or isinstance(slot.get("rotation"), bool)):
        errors.append(f"{path}.rotation must be numeric")
    if "alignment" in slot and slot.get("alignment") not in ALIGNMENTS:
        errors.append(f"{path}.alignment is invalid")


def _available_slot_ids(
    template_id: str,
    templates_by_id: dict[str, dict[str, Any]],
    seen: set[str] | None = None,
) -> set[str]:
    seen = set() if seen is None else seen
    if template_id in seen:
        return set()
    seen.add(template_id)
    template = templates_by_id.get(template_id, {})
    slots = template.get("slots", [])
    result = {
        slot.get("id") for slot in slots
        if isinstance(slot, dict) and isinstance(slot.get("id"), str)
    }
    parent = template.get("extends")
    if isinstance(parent, str):
        result.update(_available_slot_ids(parent, templates_by_id, seen))
    return result


def _resolved_slots(
    template_id: str,
    templates_by_id: dict[str, dict[str, Any]],
    seen: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Merge parent slots first, then apply same-ID child overrides."""
    seen = set() if seen is None else seen
    if template_id in seen:
        return {}
    seen.add(template_id)
    template = templates_by_id.get(template_id, {})
    result: dict[str, dict[str, Any]] = {}
    parent = template.get("extends")
    if isinstance(parent, str) and parent in templates_by_id:
        result.update(_resolved_slots(parent, templates_by_id, seen))
    for slot in template.get("slots", []):
        if isinstance(slot, dict) and isinstance(slot.get("id"), str):
            result[slot["id"]] = slot
    return result


def _has_slot_cycle(slots: dict[str, dict[str, Any]]) -> bool:
    edges: dict[str, set[str]] = {slot_id: set() for slot_id in slots}
    for slot_id, slot in slots.items():
        for relation in ("relative_to", "inherit_transform_from"):
            reference = slot.get(relation)
            if isinstance(reference, str) and reference in slots:
                edges[slot_id].add(reference)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in edges.get(node, set()):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in edges)


def validate_registry(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["registry must be an object"], "warnings": []}
    templates = data.get("templates")
    if not isinstance(templates, list) or not templates:
        errors.append("templates must be a non-empty array")
        templates = []
    ids: set[str] = set()
    parents: dict[str, str] = {}
    templates_by_id: dict[str, dict[str, Any]] = {
        item.get("template_id"): item
        for item in templates
        if isinstance(item, dict) and isinstance(item.get("template_id"), str)
    }
    for index, template in enumerate(templates):
        path = f"templates[{index}]"
        if not isinstance(template, dict):
            errors.append(f"{path} must be an object")
            continue
        template_id = template.get("template_id")
        if not isinstance(template_id, str) or not template_id.strip():
            errors.append(f"{path}.template_id is required")
            continue
        if template_id in ids:
            errors.append(f"{path}.template_id is duplicated")
        ids.add(template_id)
        if not isinstance(template.get("template_version"), int) or template["template_version"] <= 0:
            errors.append(f"{path}.template_version must be positive")
        if template.get("position_mode") != "relative_template":
            errors.append(f"{path}.position_mode must be relative_template")
        slots = template.get("slots")
        if not isinstance(slots, list) or not slots:
            errors.append(f"{path}.slots must be non-empty")
            slots = []
        slot_ids: set[str] = set()
        available_slot_ids = _available_slot_ids(template_id, templates_by_id)
        for sindex, slot in enumerate(slots):
            spath = f"{path}.slots[{sindex}]"
            if not isinstance(slot, dict):
                errors.append(f"{spath} must be an object")
                continue
            slot_id = slot.get("id")
            if not isinstance(slot_id, str) or not slot_id.strip() or slot_id in slot_ids:
                errors.append(f"{spath}.id must be unique and non-empty")
            slot_ids.add(slot_id)
            if not isinstance(slot.get("text_ref"), str) or not slot["text_ref"].strip():
                errors.append(f"{spath}.text_ref is required")
            if slot.get("ref_type") not in REF_TYPES:
                errors.append(f"{spath}.ref_type must be subtitle_unit or auxiliary_mark")
            offset = slot.get("offset")
            if not isinstance(offset, dict) or not isinstance(offset.get("dx"), (int, float)) or not isinstance(offset.get("dy"), (int, float)):
                errors.append(f"{spath}.offset requires numeric dx and dy")
            for relation in ("relative_to", "inherit_transform_from"):
                if relation in slot and slot.get(relation) not in available_slot_ids:
                    errors.append(f"{spath}.{relation} references an unknown slot")
            _validate_slot_transform(spath, slot, errors)
        constraints = template.get("constraints")
        if not isinstance(constraints, dict):
            errors.append(f"{path}.constraints must be an object")
        else:
            if not isinstance(constraints.get("safe_zone"), str) or not constraints["safe_zone"].strip():
                errors.append(f"{path}.constraints.safe_zone is required")
            if constraints.get("collision") not in COLLISION_POLICIES:
                errors.append(f"{path}.constraints.collision is invalid")
        if template.get("fallback") != "manual_review":
            errors.append(f"{path}.fallback must be manual_review")
        parent = template.get("extends")
        if parent is not None:
            if not isinstance(parent, str) or not parent.strip():
                errors.append(f"{path}.extends must be a non-empty string")
            else:
                parents[template_id] = parent
    for template_id, parent in parents.items():
        if parent not in ids:
            errors.append(f"templates[{template_id}].extends references unknown template {parent!r}")
    if _has_parent_cycle(parents):
        errors.append("templates.extends must not contain inheritance cycles")
    for template_id in ids:
        if _has_slot_cycle(_resolved_slots(template_id, templates_by_id)):
            errors.append(f"templates[{template_id}].slots must not contain relative-reference cycles")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "template_count": len(ids)}

