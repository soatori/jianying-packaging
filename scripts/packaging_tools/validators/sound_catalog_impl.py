#!/usr/bin/env python3
"""Validate generic Jianying sound metadata and motion candidate pools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SOUND_FORMS = {"single_hit", "decay", "multi_hit", "loop", "ambience", "unknown"}
TRIM_POLICIES = {"text_span", "motion_span", "natural", "manual_review"}
SOUND_STATUSES = {"verified", "candidate", "needs_listen", "blocked"}
LEADING_POLICIES = {"skip", "preserve", "manual_review"}
FORBIDDEN_KEYS = {
    "draft_path", "timeline", "track_id", "segment_id", "material_id", "asset_id",
    "start_us", "end_us", "timecode", "caption", "subtitle", "project_id",
}


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def find_forbidden(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                errors.append(f"{path}.{key}: project-specific field is not allowed")
            find_forbidden(item, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            find_forbidden(item, f"{path}[{index}]", errors)


def validate_catalog(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["catalog must be an object"], "warnings": []}
    find_forbidden(data, "catalog", errors)
    presets = data.get("presets")
    if not isinstance(presets, list):
        errors.append("presets must be an array")
        presets = []
    ids: set[str] = set()
    for index, preset in enumerate(presets):
        path = f"presets[{index}]"
        if not isinstance(preset, dict):
            errors.append(f"{path} must be an object")
            continue
        preset_id = preset.get("preset_id")
        if not nonempty(preset_id):
            errors.append(f"{path}.preset_id is required")
            continue
        if preset_id in ids:
            errors.append(f"{path}.preset_id is duplicated")
        ids.add(preset_id)
        if not nonempty(preset.get("display_name")):
            errors.append(f"{path}.display_name is required")
        sound_form = preset.get("sound_form")
        if sound_form not in SOUND_FORMS:
            errors.append(f"{path}.sound_form is invalid")
        for field in ("duration_us", "leading_silence_us", "tail_duration_us"):
            value = preset.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"{path}.{field} must be a non-negative integer")
        if isinstance(preset.get("duration_us"), int) and isinstance(preset.get("leading_silence_us"), int):
            if preset["leading_silence_us"] > preset["duration_us"]:
                errors.append(f"{path}.leading_silence_us cannot exceed duration_us")
        if isinstance(preset.get("duration_us"), int) and isinstance(preset.get("tail_duration_us"), int):
            if preset["tail_duration_us"] > preset["duration_us"]:
                errors.append(f"{path}.tail_duration_us cannot exceed duration_us")
        trim = preset.get("default_trim_policy")
        if trim not in TRIM_POLICIES:
            errors.append(f"{path}.default_trim_policy is invalid")
        if sound_form in {"single_hit", "decay"} and trim == "motion_span":
            warnings.append(f"{path}: single/decay sound defaults to text_span")
        if sound_form == "multi_hit" and trim == "text_span":
            warnings.append(f"{path}: multi_hit sound normally uses motion_span")
        if preset.get("leading_silence_policy") not in LEADING_POLICIES:
            errors.append(f"{path}.leading_silence_policy is invalid")
        if preset.get("status") not in SOUND_STATUSES:
            errors.append(f"{path}.status is invalid")
        evidence = preset.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(not nonempty(item) for item in evidence):
            errors.append(f"{path}.evidence must contain at least one non-empty item")
        if preset.get("status") == "verified" and not nonempty(preset.get("last_verified")):
            errors.append(f"{path}.last_verified is required for verified presets")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "preset_ids": sorted(ids)}


def validate_pools(data: Any, catalog_ids: set[str] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["pools must be an object"], "warnings": []}
    find_forbidden(data, "pools", errors)
    pools = data.get("pools")
    if not isinstance(pools, list):
        errors.append("pools must be an array")
        pools = []
    pool_ids: set[str] = set()
    for index, pool in enumerate(pools):
        path = f"pools[{index}]"
        if not isinstance(pool, dict):
            errors.append(f"{path} must be an object")
            continue
        pool_id = pool.get("pool_id")
        if not nonempty(pool_id):
            errors.append(f"{path}.pool_id is required")
        elif pool_id in pool_ids:
            errors.append(f"{path}.pool_id is duplicated")
        else:
            pool_ids.add(pool_id)
        minimum = pool.get("min_candidates")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
            errors.append(f"{path}.min_candidates must be a non-negative integer")
            minimum = 3
        candidates = pool.get("candidates")
        if not isinstance(candidates, list):
            errors.append(f"{path}.candidates must be an array")
            candidates = []
        candidate_ids: set[str] = set()
        candidate_ranks: set[int] = set()
        for cindex, candidate in enumerate(candidates):
            cpath = f"{path}.candidates[{cindex}]"
            if not isinstance(candidate, dict) or not nonempty(candidate.get("preset_id")):
                errors.append(f"{cpath}.preset_id is required")
                continue
            preset_id = candidate["preset_id"]
            if preset_id in candidate_ids:
                errors.append(f"{cpath}.preset_id is duplicated")
            candidate_ids.add(preset_id)
            if candidate.get("status") not in SOUND_STATUSES:
                errors.append(f"{cpath}.status is invalid")
            rank = candidate.get("rank")
            if not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0:
                errors.append(f"{cpath}.rank must be a positive integer")
            elif rank in candidate_ranks:
                errors.append(f"{cpath}.rank is duplicated")
            else:
                candidate_ranks.add(rank)
            if candidate.get("sound_form") not in SOUND_FORMS:
                errors.append(f"{cpath}.sound_form is invalid")
            if catalog_ids is not None and preset_id not in catalog_ids:
                errors.append(f"{cpath}.preset_id is absent from the catalog")
        if len(candidate_ids) < minimum:
            if pool.get("status") != "candidate_pool_incomplete":
                errors.append(f"{path}: incomplete pool must be marked candidate_pool_incomplete")
            warnings.append(f"{path}: candidate_pool_incomplete ({len(candidate_ids)}/{minimum})")
        if pool.get("status") not in {"verified", "candidate_pool_incomplete", "not_applicable"}:
            errors.append(f"{path}.status is invalid")
        if minimum == 0 and pool.get("status") != "not_applicable":
            errors.append(f"{path}: zero-candidate pool must be not_applicable")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "pool_ids": sorted(pool_ids)}

