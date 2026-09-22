"""Stable result shape shared by packaging commands."""

from __future__ import annotations

from typing import Any, Iterable


def result(
    report_type: str,
    *,
    data: Any = None,
    errors: Iterable[str] = (),
    input_errors: Iterable[str] = (),
    warnings: Iterable[str] = (),
    status: str | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error_list = list(errors)
    input_error_list = list(input_errors)
    warning_list = list(warnings)
    if status is None:
        status = "blocked" if error_list or input_error_list else ("review" if warning_list else "ok")
    return {
        "report_type": report_type,
        "ok": not error_list and not input_error_list,
        "status": status,
        "errors": error_list,
        "input_errors": input_error_list,
        "warnings": warning_list,
        "summary": summary or {},
        "data": data,
    }


def exit_code(report: dict[str, Any]) -> int:
    if report.get("input_errors"):
        return 2
    return 0 if report.get("ok") else 1
