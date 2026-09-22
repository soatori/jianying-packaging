"""JSON and presentation helpers for packaging tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class BlockedReportError(ValueError):
    """A previous tool report is valid input but carries a safety block."""


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def unwrap_report(value: Any, expected_report_type: str | None = None) -> Any:
    """Accept either a CLI report envelope or its raw data payload."""
    if not isinstance(value, dict) or "data" not in value or "report_type" not in value:
        return value
    if expected_report_type and value.get("report_type") != expected_report_type:
        raise ValueError(
            f"expected report_type {expected_report_type!r}, got {value.get('report_type')!r}"
        )
    if value.get("ok") is False:
        raise BlockedReportError(
            f"cannot consume blocked report {value.get('report_type')!r}: "
            + "; ".join(str(item) for item in value.get("errors", []))
        )
    return value.get("data")


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def write_json(path: str | Path, value: Any) -> None:
    Path(path).write_text(dump_json(value) + "\n", encoding="utf-8")


def text_result(report: dict[str, Any]) -> str:
    lines = [
        f"{report.get('report_type', 'report')}: {report.get('status', 'unknown')}",
        f"ok: {report.get('ok', False)}",
    ]
    for key in ("errors", "warnings"):
        values = report.get(key) or []
        if values:
            lines.append(f"{key}:")
            lines.extend(f"- {value}" for value in values)
    values = report.get("input_errors") or []
    if values:
        lines.append("input_errors:")
        lines.extend(f"- {value}" for value in values)
    summary = report.get("summary") or {}
    if summary:
        lines.append("summary:")
        lines.extend(f"- {key}: {value}" for key, value in summary.items())
    return "\n".join(lines)
