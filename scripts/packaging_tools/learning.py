"""Application-independent learning reports for human-reviewed outcomes."""

from __future__ import annotations

from typing import Any

from .result import result


AREAS = {"rough_cut", "subtitle_alignment", "packaging", "motion", "audio", "handoff"}
EVIDENCE_LEVELS = {"plan_consistency", "visual_frame", "human_listening"}
GENERALIZABILITY = {"generic", "user_preference", "project_case", "pending"}
PROMOTION_STATUS = {"external_case", "pending", "approved_generic", "rejected"}
REPORT_FIELDS = {"schema_version", "report_type", "source", "entries"}
SOURCE_FIELDS = {"kind", "case_ref"}
ENTRY_FIELDS = {
    "id", "area", "pattern", "evidence_level", "generalizability",
    "anti_pattern", "promotion_status", "case_ref",
}


def _reject_unknown_fields(value: dict[str, Any], allowed: set[str], path: str, errors: list[str]) -> None:
    for key in sorted(set(value) - allowed):
        errors.append(f"{path}.{key}: unknown learning-report field")


def validate_learning_report(report: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return result("learning_report_validation", errors=["report must be an object"])
    _reject_unknown_fields(report, REPORT_FIELDS, "report", errors)
    if report.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if report.get("report_type") != "learning_report":
        errors.append("report_type must be learning_report")
    source = report.get("source", {})
    if not isinstance(source, dict):
        errors.append("source must be an object")
        source = {}
    else:
        _reject_unknown_fields(source, SOURCE_FIELDS, "source", errors)
        if source.get("kind") not in {"project_case", "synthetic_fixture", "manual_review"}:
            errors.append("source.kind must be project_case, synthetic_fixture, or manual_review")
        if "case_ref" in source and (not isinstance(source.get("case_ref"), str) or not source["case_ref"].strip()):
            errors.append("source.case_ref must be a non-empty string when present")
        if source.get("kind") == "project_case" and not isinstance(source.get("case_ref"), str):
            errors.append("source.case_ref is required for project_case")
    entries = report.get("entries")
    if not isinstance(entries, list):
        errors.append("entries must be an array")
        entries = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{path} must be an object")
            continue
        _reject_unknown_fields(entry, ENTRY_FIELDS, path, errors)
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            errors.append(f"{path}.id must be a non-empty string")
        elif entry_id in seen:
            errors.append(f"{path}.id duplicates {entry_id!r}")
        else:
            seen.add(entry_id)
        if entry.get("area") not in AREAS:
            errors.append(f"{path}.area is invalid")
        if not isinstance(entry.get("pattern"), str) or not entry["pattern"].strip():
            errors.append(f"{path}.pattern must be a non-empty string")
        if entry.get("evidence_level") not in EVIDENCE_LEVELS:
            errors.append(f"{path}.evidence_level is invalid")
        if entry.get("generalizability") not in GENERALIZABILITY:
            errors.append(f"{path}.generalizability is invalid")
        if entry.get("promotion_status") not in PROMOTION_STATUS:
            errors.append(f"{path}.promotion_status is invalid")
        if "anti_pattern" in entry and not isinstance(entry.get("anti_pattern"), str):
            errors.append(f"{path}.anti_pattern must be a string when present")
        if "case_ref" in entry and (not isinstance(entry.get("case_ref"), str) or not entry["case_ref"].strip()):
            errors.append(f"{path}.case_ref must be a non-empty string when present")
    areas = sorted({entry.get("area") for entry in entries if isinstance(entry, dict) and isinstance(entry.get("area"), str)})
    return result(
        "learning_report_validation",
        data={"entry_count": len(entries), "areas": areas},
        errors=errors,
        summary={"entry_count": len(entries)},
    )


def build_learning_report(
    entries: Any,
    *,
    source_kind: str = "project_case",
    case_ref: str | None = None,
) -> dict[str, Any]:
    if isinstance(entries, dict) and isinstance(entries.get("entries"), list):
        rows = entries["entries"]
    elif isinstance(entries, list):
        rows = entries
    else:
        return result("learning_report", input_errors=["entries must be an array or an object containing entries"])
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_type": "learning_report",
        "source": {"kind": source_kind},
        "entries": rows,
    }
    if case_ref is not None:
        report["source"]["case_ref"] = case_ref
    validation = validate_learning_report(report)
    return result(
        "learning_report",
        data=report,
        errors=validation.get("errors", []),
        input_errors=validation.get("input_errors", []),
        warnings=validation.get("warnings", []),
        summary=validation.get("summary", {}),
    )
