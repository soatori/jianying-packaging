"""Importable packaging-plan validator with the common report shape."""

from __future__ import annotations

from typing import Any

from .plan_impl import validate_plan as _validate_plan


def validate_plan(data: Any, **kwargs: Any) -> dict[str, Any]:
    errors, warnings = _validate_plan(data, **kwargs)
    return {"ok": not errors, "errors": errors, "warnings": warnings}

__all__ = ["validate_plan"]
