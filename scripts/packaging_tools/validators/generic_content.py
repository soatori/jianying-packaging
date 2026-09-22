"""Importable generic-content checker."""

from pathlib import Path
from typing import Any

from .generic_content_impl import scan


def check_generic_content(paths: list[str | Path], forbidden_literals: list[str] | None = None) -> dict[str, object]:
    if not isinstance(paths, list) or not paths:
        return {
            "ok": False,
            "errors": [],
            "input_errors": ["generic-content roots must be a non-empty array"],
            "warnings": [],
        }
    roots = [Path(path) for path in paths]
    missing = [str(path) for path in roots if not path.exists() or not (path.is_file() or path.is_dir())]
    if missing:
        return {
            "ok": False,
            "errors": [],
            "input_errors": [f"generic-content root does not exist: {path}" for path in missing],
            "warnings": [],
        }
    try:
        errors = scan(roots, forbidden_literals=forbidden_literals)
    except OSError as exc:
        return {"ok": False, "errors": [], "input_errors": [f"generic-content root is not readable: {exc}"], "warnings": []}
    return {"ok": not errors, "errors": errors, "input_errors": [], "warnings": []}
