"""Run the read-only packaging audits over one saved timeline observation."""

from __future__ import annotations

from typing import Any

from .audio_inventory import classify_audio_events
from .inventory import inventory_templates_and_materials
from .layer_discovery import discover_packaging_layers
from .motion_check import check_motion_reuse
from .result import result
from .snapshot import build_packaging_snapshot


CHECK_TYPES = {
    "snapshot": "packaging_snapshot",
    "inventory": "packaging_inventory",
    "layers": "packaging_layer_discovery",
    "motion_check": "packaging_motion_check",
    "audio_audit": "packaging_audio_inventory",
}
OBSERVATION_SCHEMA = "jianying_timeline_observation@1"
AVAILABLE_EVIDENCE = {"available", "observed_empty"}
REQUIRED_ARRAYS = (
    "tracks", "segments", "subtitle_units", "materials",
    "templates", "fonts", "motion_events", "audio_events",
)


def _blocked(report_type: str, evidence: str) -> dict[str, Any]:
    return result(
        report_type,
        input_errors=[f"{evidence} evidence is unavailable in the saved observation"],
        status="blocked",
    )


def build_audit_bundle(observation: Any, adjacent_window: int = 1) -> dict[str, Any]:
    if not isinstance(observation, dict) or observation.get("schema_version") != OBSERVATION_SCHEMA:
        return result(
            "packaging_audit_bundle",
            input_errors=[f"observation must use schema {OBSERVATION_SCHEMA}"],
            status="blocked",
        )
    source = observation.get("source")
    fingerprint = source.get("primary_sha256") if isinstance(source, dict) else None
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        return result("packaging_audit_bundle", input_errors=["observation source.primary_sha256 is required"], status="blocked")
    evidence = observation.get("evidence_status")
    if not isinstance(evidence, dict):
        return result("packaging_audit_bundle", input_errors=["observation evidence_status must be an object"], status="blocked")
    invalid_arrays = [
        f"observation field {field!r} must be an array"
        for field in REQUIRED_ARRAYS
        if not isinstance(observation.get(field), list)
    ]
    if invalid_arrays:
        return result("packaging_audit_bundle", input_errors=invalid_arrays, status="blocked")

    checks: dict[str, dict[str, Any]] = {}
    checks["snapshot"] = (
        build_packaging_snapshot(observation)
        if evidence.get("segments") in AVAILABLE_EVIDENCE
        else _blocked(CHECK_TYPES["snapshot"], "segments")
    )
    checks["inventory"] = (
        inventory_templates_and_materials(observation)
        if evidence.get("materials") in AVAILABLE_EVIDENCE
        else _blocked(CHECK_TYPES["inventory"], "materials")
    )
    checks["layers"] = (
        discover_packaging_layers(observation)
        if evidence.get("segments") in AVAILABLE_EVIDENCE
        else _blocked(CHECK_TYPES["layers"], "tracks/segments")
    )
    checks["motion_check"] = (
        check_motion_reuse(observation, adjacent_window)
        if evidence.get("motion_events") in AVAILABLE_EVIDENCE
        else _blocked(CHECK_TYPES["motion_check"], "motion_events")
    )
    checks["audio_audit"] = (
        classify_audio_events(observation)
        if evidence.get("audio_events") in AVAILABLE_EVIDENCE
        else _blocked(CHECK_TYPES["audio_audit"], "audio_events")
    )

    warnings: list[str] = []
    if evidence.get("templates") == "unavailable":
        warnings.append("template inventory is unavailable; zero templates are not inferred")
    if evidence.get("fonts") == "unavailable":
        warnings.append("font inventory is unavailable; zero fonts are not inferred")
    errors: list[str] = []
    input_errors: list[str] = []
    for name, check in checks.items():
        errors.extend(f"{name}: {item}" for item in check.get("errors", []))
        input_errors.extend(f"{name}: {item}" for item in check.get("input_errors", []))
        warnings.extend(f"{name}: {item}" for item in check.get("warnings", []))

    blocked = [name for name, check in checks.items() if not check.get("ok")]
    return result(
        "packaging_audit_bundle",
        data={
            "schema_version": "packaging_audit_bundle@1",
            "source_fingerprint": fingerprint,
            "source_timeline_id": source.get("timeline_id"),
            "checks": checks,
        },
        errors=errors,
        input_errors=input_errors,
        warnings=warnings,
        summary={"check_count": len(checks), "blocked_checks": blocked},
    )
