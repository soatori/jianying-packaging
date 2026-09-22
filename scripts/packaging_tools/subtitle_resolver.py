"""Resolve packaging groups against the current final subtitle manifest."""

from __future__ import annotations

import hashlib
from typing import Any

from .result import result


def _text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _actual_text(operation: dict[str, Any]) -> str | None:
    for key in ("text", "content", "base_content", "recognize_text"):
        value = operation.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            return value["text"]
    return None


def _visual_operations(group: dict[str, Any]) -> tuple[list[Any], list[str]]:
    """Read the schema 1.2 visual field with explicit legacy compatibility."""
    aliases = [key for key in ("visual", "visuals", "visual_operations") if key in group]
    if not aliases:
        return [], []
    errors: list[str] = []
    values: dict[str, list[Any]] = {}
    for key in aliases:
        value = group.get(key)
        if not isinstance(value, list):
            errors.append(f"group {group.get('id')}: {key} must be an array")
            values[key] = []
        else:
            values[key] = value
    canonical = values.get("visual", values.get(aliases[0], []))
    for key in aliases:
        if key != "visual" and values[key] != canonical:
            errors.append(f"group {group.get('id')}: visual aliases disagree ({key})")
    return canonical, errors


def _runtime_anchor(unit: dict[str, Any]) -> tuple[dict[str, float] | None, list[str]]:
    candidates: list[tuple[str, Any]] = []
    for key in ("runtime_anchor", "anchor"):
        if key in unit:
            candidates.append((key, unit.get(key)))
    if "x0" in unit or "y0" in unit:
        candidates.append(("x0_y0", {"x": unit.get("x0"), "y": unit.get("y0")}))
    if not candidates:
        return None, ["runtime X0/Y0 anchor is missing"]
    normalized: list[tuple[str, dict[str, float]]] = []
    errors: list[str] = []
    for name, value in candidates:
        if not isinstance(value, dict):
            errors.append(f"{name} must be an object")
            continue
        x, y = value.get("x", value.get("x0")), value.get("y", value.get("y0"))
        if not isinstance(x, (int, float)) or isinstance(x, bool) or not isinstance(y, (int, float)) or isinstance(y, bool):
            errors.append(f"{name} must contain numeric x/y")
            continue
        normalized.append((name, {"x": float(x), "y": float(y)}))
    if not normalized:
        return None, errors or ["runtime X0/Y0 anchor is unresolved"]
    first = normalized[0][1]
    if any(value != first for _, value in normalized[1:]):
        errors.append("runtime X0/Y0 anchor sources disagree")
    return (first if not errors else None), errors


def resolve_text_hashes(plan: Any, subtitle_manifest: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or not isinstance(subtitle_manifest, list):
        return result("packaging_text_resolution", errors=["plan and subtitle_manifest have invalid types"])
    manifest: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for index, item in enumerate(subtitle_manifest):
        if not isinstance(item, dict) or not item.get("unit_id"):
            errors.append(f"subtitle_manifest[{index}] must contain unit_id")
            continue
        unit_id = str(item["unit_id"])
        if unit_id in manifest:
            errors.append(f"subtitle manifest duplicates unit_id {unit_id!r}")
        else:
            manifest[unit_id] = item
    resolved: list[dict[str, Any]] = []
    groups = plan.get("groups")
    if not isinstance(groups, list):
        errors.append("plan.groups must be an array")
        groups = []
    for group in groups:
        if not isinstance(group, dict):
            errors.append("plan.groups entries must be objects")
            continue
        visuals, alias_errors = _visual_operations(group)
        errors.extend(alias_errors)
        for operation in visuals:
            if not isinstance(operation, dict):
                errors.append(f"group {group.get('id')}: visual operation must be an object")
                continue
            is_text_visual = (
                operation.get("object_type") == "text"
                or "text_ref" in operation
                or "text_hash" in operation
                or any(key in operation for key in ("text", "content", "base_content", "recognize_text"))
            )
            if not is_text_visual:
                continue
            ref = operation.get("text_ref")
            declared = operation.get("text_hash")
            if not ref:
                errors.append(f"group {group.get('id')}: text_ref is required for text visual")
                continue
            if not declared:
                errors.append(f"group {group.get('id')}: text_hash is required for text visual {ref!r}")
            unit = manifest.get(str(ref))
            if unit is None:
                errors.append(f"group {group.get('id')}: text_ref {ref!r} is absent from subtitle manifest")
                continue
            actual_text = _actual_text(operation)
            if not isinstance(actual_text, str):
                errors.append(f"group {group.get('id')}: text visual {ref!r} must contain string text")
                continue
            expected = unit.get("text_hash")
            manifest_text = unit.get("text")
            if not isinstance(expected, str) or not expected:
                errors.append(f"group {group.get('id')}: subtitle manifest {ref!r} has no text_hash")
                expected = _text_hash(manifest_text) if isinstance(manifest_text, str) else None
            if expected is None:
                continue
            if isinstance(manifest_text, str) and _text_hash(manifest_text) != expected:
                errors.append(f"group {group.get('id')}: subtitle manifest text_hash is not the UTF-8 hash of its text")
            if declared != expected:
                errors.append(f"group {group.get('id')}: declared text_hash differs from subtitle manifest")
            actual = _text_hash(actual_text)
            if actual != expected:
                errors.append(f"group {group.get('id')}: text_mismatch for {ref}")
            resolved.append({"group_id": group.get("id"), "text_ref": ref, "text_hash": actual, "ok": actual == expected})
    return result("packaging_text_resolution", data={"resolved": resolved}, errors=errors, summary={"checked": len(resolved)})


def resolve_subtitle_anchor(plan: Any, observation: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or not isinstance(observation, dict):
        return result("packaging_subtitle_resolution", errors=["plan and observation must be JSON objects"])
    units = [unit for unit in observation.get("subtitle_units", []) if isinstance(unit, dict)]
    comparison = plan.get("comparison", {}) if isinstance(plan.get("comparison"), dict) else {}
    source_order = comparison.get("source_order_hash")
    target_order = comparison.get("target_order_hash")
    remap_status = comparison.get("remap_status")
    if source_order and target_order and source_order != target_order and remap_status not in {"not_required", "verified"}:
        return result("packaging_subtitle_resolution", errors=[f"order remap is {remap_status or 'missing'}; final packaging requires verified remap"])
    errors: list[str] = []
    by_id: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        unit_id = str(unit.get("unit_id", unit.get("id", "")))
        if not unit_id:
            errors.append("observation subtitle unit has no unit_id/id")
            continue
        by_id.setdefault(unit_id, []).append(unit)
    resolved: list[dict[str, Any]] = []
    by_group: dict[str, dict[str, Any]] = {}
    for group in plan.get("groups", []) or []:
        if not isinstance(group, dict):
            continue
        subtitle_anchor = group.get("subtitle_anchor") if isinstance(group.get("subtitle_anchor"), dict) else {}
        primary_ref = subtitle_anchor.get("unit_id") or ((group.get("semantic_unit_refs") or [None])[0])
        refs = group.get("semantic_unit_refs", []) or []
        if primary_ref and primary_ref not in refs:
            refs = [primary_ref, *refs]
        if not isinstance(refs, list) or not refs:
            errors.append(f"group {group.get('id')}: semantic_unit_refs/subtitle_anchor.unit_id is required")
            continue
        for ref in refs:
            matches = by_id.get(str(ref), [])
            if len(matches) != 1:
                errors.append(f"group {group.get('id')}: subtitle anchor {ref!r} matched {len(matches)} units")
                continue
            anchor, anchor_errors = _runtime_anchor(matches[0])
            errors.extend(f"group {group.get('id')}: {error}" for error in anchor_errors)
            entry = {"group_id": group.get("id"), "unit_id": ref, "unit": matches[0], "runtime_anchor": anchor}
            resolved.append(entry)
            if str(ref) == str(primary_ref) and anchor is not None:
                by_group[str(group.get("id"))] = entry
    return result(
        "packaging_subtitle_resolution",
        data={"resolved": resolved, "by_group": by_group},
        errors=errors,
        summary={"resolved_count": len(resolved), "group_count": len(by_group)},
    )
