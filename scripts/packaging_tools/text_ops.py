"""Check text mirror and style-range consistency before packaging apply."""

from __future__ import annotations

from typing import Any

from .result import result


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "content", "base_content", "recognize_text"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
            nested = _text(candidate)
            if nested:
                return nested
        for candidate in value.values():
            nested = _text(candidate)
            if nested:
                return nested
    if isinstance(value, list):
        for candidate in value:
            nested = _text(candidate)
            if nested:
                return nested
    return ""


def _field_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        for key in ("content", "base_content", "recognize_text"):
            nested = _field_text(value.get(key))
            if nested is not None:
                return nested
    return None


def _field_shape(value: Any) -> str:
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _ranges(value: Any) -> tuple[list[tuple[int, int]], list[str]]:
    if not isinstance(value, list):
        return [], ["style ranges must be an array"]
    ranges: list[tuple[int, int]] = []
    errors: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"styles[{index}] must be an object")
            continue
        start = item.get("start", 0)
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            errors.append(f"styles[{index}].start must be a non-negative integer")
            continue
        if "end" in item:
            end = item.get("end")
        elif "length" in item and isinstance(item.get("length"), int):
            end = start + item["length"]
        else:
            errors.append(f"styles[{index}] requires end or length")
            continue
        if not isinstance(end, int) or isinstance(end, bool) or end <= start:
            errors.append(f"styles[{index}] must have a positive range")
            continue
        ranges.append((start, end))
    return ranges, errors


def _mirror_fields(value: Any, path: str = "") -> list[tuple[str, Any]]:
    fields: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in {"text", "content", "base_content", "recognize_text"}:
                fields.append((child_path, item))
            fields.extend(_mirror_fields(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            fields.extend(_mirror_fields(item, f"{path}[{index}]"))
    return fields


def _get_path(value: Any, path: str) -> tuple[bool, Any]:
    current = value
    for part in path.replace("]", "").replace("[", ".").split("."):
        if not part:
            continue
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _style_fields(value: Any, path: str = "") -> list[tuple[str, Any]]:
    fields: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            if key == "styles":
                fields.append((child_path, item))
            fields.extend(_style_fields(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            fields.extend(_style_fields(item, f"{path}[{index}]"))
    return fields


def check_text_replacement(prototype: Any, replacement: Any) -> dict[str, Any]:
    if not isinstance(prototype, dict) or not isinstance(replacement, dict):
        return result("packaging_text_operation", errors=["prototype and replacement must be JSON objects"])
    text = _text(replacement)
    errors: list[str] = []
    warnings: list[str] = []
    mirror_fields = _mirror_fields(prototype)
    for path, prototype_value in mirror_fields:
        present, replacement_value = _get_path(replacement, path)
        if not present:
            errors.append(f"replacement.{path} is required because prototype contains it")
            continue
        prototype_text = _field_text(prototype_value)
        replacement_text = _field_text(replacement_value)
        if replacement_text is None:
            errors.append(f"replacement.{path} must contain visible text")
            continue
        if prototype_text is None:
            errors.append(f"prototype.{path} has unsupported text shape")
        if _field_shape(prototype_value) != _field_shape(replacement_value):
            errors.append(f"replacement.{path} must preserve the prototype field shape")
        if replacement_text != text:
            errors.append(f"replacement.{path} is not synchronized with the visible replacement text")
    if not text:
        errors.append("replacement contains no visible text")
    prototype_style_fields = _style_fields(prototype)
    replacement_style_fields = dict(_style_fields(replacement))
    if prototype_style_fields and not replacement_style_fields:
        errors.append("replacement styles are required because prototype contains style ranges")
    for path, _ in prototype_style_fields:
        if path not in replacement_style_fields:
            errors.append(f"replacement.{path} is required because prototype contains style ranges")
    style_values = list(replacement_style_fields.items())
    if not style_values and not prototype_style_fields:
        style_values = []
    for path, style_ranges in style_values:
        parsed, range_errors = _ranges(style_ranges)
        errors.extend(range_errors)
        cursor = 0
        for start, end in sorted(parsed):
            if end > len(text):
                errors.append(f"{path}: style range exceeds replacement text")
            if start > cursor:
                errors.append(f"{path}: style ranges do not cover the complete replacement text")
            if start < cursor:
                errors.append(f"{path}: style ranges overlap and cannot be confirmed safe")
            cursor = max(cursor, end)
        if not parsed and text:
            errors.append(f"{path}: style ranges do not cover the complete replacement text")
        elif parsed and cursor < len(text):
            errors.append(f"{path}: style ranges do not cover the complete replacement text")
    if len(text) > 13:
        warnings.append("replacement exceeds the default 13-character Chinese line guideline; perform visual width review")
    return result("packaging_text_operation", data={"text": text, "text_length": len(text)}, errors=errors, warnings=warnings)
