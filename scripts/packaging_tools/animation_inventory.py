"""Discover and gate locally cached Jianying text entrance animations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .result import result


_SHADER_SUFFIXES = {".frag", ".glsl", ".shader", ".vert", ".xshader"}
_SCRIPT_SUFFIXES = {".js", ".lua", ".script"}


def _field(entry: Any, name: str, default: Any = None) -> Any:
    if isinstance(entry, dict):
        return entry.get(name, default)
    value = getattr(entry, "value", entry)
    return getattr(value, name, default)


def _animation_name(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("name", entry.get("title", "")))
    return str(getattr(getattr(entry, "value", entry), "title", getattr(entry, "name", "")))


def _cache_entry(cache_root: Path, resource_id: str, effect_id: str, md5: str) -> Path | None:
    root = cache_root if cache_root.name.casefold() == "effect" else cache_root / "effect"
    matches = []
    for identifier in (resource_id, effect_id):
        if not identifier:
            continue
        candidate = root / identifier / md5
        if candidate.is_dir():
            matches.append(candidate.resolve())
    matches = list(dict.fromkeys(matches))
    if len(matches) > 1:
        raise ValueError(f"cache path for resource {resource_id!r} is ambiguous")
    return matches[0] if matches else None


def _render_type(path: Path) -> str:
    suffixes = {item.suffix.casefold() for item in path.rglob("*") if item.is_file()}
    has_script = bool(suffixes & _SCRIPT_SUFFIXES)
    has_shader = bool(suffixes & _SHADER_SUFFIXES)
    if has_script and has_shader:
        return "mixed"
    if has_script:
        return "script"
    if has_shader:
        return "shader"
    return "unknown"


def _verification_record(capabilities: Any, resource_id: str, md5: str) -> dict[str, Any] | None:
    if not isinstance(capabilities, dict):
        return None
    records = capabilities.get("verified")
    if not isinstance(records, list):
        return None
    for record in records:
        if (
            isinstance(record, dict)
            and str(record.get("resource_id", "")) == resource_id
            and str(record.get("md5", "")) == md5
            and record.get("target_kind") == "plain_text"
            and record.get("status") == "visually_verified"
        ):
            return record
    return None


def build_animation_inventory(
    cache_root: str | Path,
    enum_entries: Iterable[Any],
    *,
    jianying_version: str,
    capabilities: Any = None,
) -> dict[str, Any]:
    """Intersect TextIntro metadata with exact cache payloads and verified capabilities."""
    enum_entries = list(enum_entries)
    root = Path(cache_root).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if not jianying_version:
        errors.append("current Jianying version is required for animation inventory")
    if not root.is_dir():
        errors.append(f"animation cache root does not exist: {root}")
    capability_version = capabilities.get("jianying_version") if isinstance(capabilities, dict) else None
    version_matches = bool(jianying_version and capability_version == jianying_version)
    if capabilities is not None and not version_matches:
        errors.append(
            f"animation capability version {capability_version!r} does not match current Jianying {jianying_version!r}"
        )

    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for enum_entry in enum_entries:
        resource_id = str(_field(enum_entry, "resource_id", "") or "")
        effect_id = str(_field(enum_entry, "effect_id", "") or "")
        md5 = str(_field(enum_entry, "md5", "") or "")
        duration_us = _field(enum_entry, "duration_us", _field(enum_entry, "duration"))
        if isinstance(duration_us, bool) or not isinstance(duration_us, int) or duration_us <= 0:
            errors.append(f"TextIntro {resource_id or _animation_name(enum_entry)!r} has invalid default duration")
            continue
        if not resource_id or not md5:
            errors.append(f"TextIntro entry {_animation_name(enum_entry)!r} lacks resource_id or md5")
            continue
        try:
            cache_path = _cache_entry(root, resource_id, effect_id, md5)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if cache_path is None:
            missing.append(resource_id)
            continue
        render_type = _render_type(cache_path)
        verified = _verification_record(capabilities, resource_id, md5) if version_matches else None
        inferred_inputs = ["words"] if render_type in {"script", "mixed"} else []
        declared_inputs = verified.get("required_inputs") if isinstance(verified, dict) else None
        required_inputs = (
            [str(item) for item in declared_inputs]
            if isinstance(declared_inputs, list)
            else inferred_inputs
        )
        compatible_plain_text = (
            render_type in {"shader", "script", "mixed"}
            and verified is not None
            and not required_inputs
        )
        entries.append({
            "name": _animation_name(enum_entry),
            "resource_id": resource_id,
            "effect_id": effect_id,
            "md5": md5,
            "default_duration_us": duration_us,
            "cache_path": str(cache_path),
            "render_type": render_type,
            "required_inputs": required_inputs,
            "native_verified": verified is not None,
            "compatible_plain_text": compatible_plain_text,
        })
    if missing:
        warnings.append(f"TextIntro resources absent from the local effect cache: {', '.join(sorted(missing))}")
    if any(entry["render_type"] == "unknown" for entry in entries):
        warnings.append("one or more cached TextIntro resources have an unknown render type and are blocked")
    return result(
        "packaging_animation_inventory",
        data={"cache_root": str(root), "jianying_version": jianying_version, "entries": entries},
        errors=errors,
        warnings=warnings,
        summary={"enum_count": len(enum_entries), "cached_count": len(entries)},
    )


def resolve_text_animation(
    inventory: dict[str, Any],
    resource_id: str,
    *,
    available_inputs: set[str],
) -> dict[str, Any]:
    entries = inventory.get("entries")
    if not isinstance(entries, list):
        data = inventory.get("data")
        entries = data.get("entries") if isinstance(data, dict) else None
    matches = [
        entry for entry in entries or []
        if isinstance(entry, dict) and str(entry.get("resource_id", "")) == str(resource_id)
    ]
    if len(matches) != 1:
        raise ValueError(f"animation resource {resource_id!r} is unknown or ambiguous in the local inventory")
    entry = matches[0]
    required = set(entry.get("required_inputs", []))
    missing = sorted(required - available_inputs)
    if missing:
        raise ValueError(f"animation resource {resource_id!r} requires {' and '.join(missing)} data")
    if entry.get("render_type") not in {"shader", "script", "mixed"}:
        raise ValueError(f"animation resource {resource_id!r} has an unknown render type")
    if entry.get("native_verified") is not True:
        raise ValueError(f"animation resource {resource_id!r} is unknown or not visually verified for plain text")
    if entry.get("compatible_plain_text") is not True:
        raise ValueError(f"animation resource {resource_id!r} is not verified for a plain-text target")
    return dict(entry)
