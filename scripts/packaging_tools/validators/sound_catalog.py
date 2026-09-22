"""Importable sound catalog/pool validator."""

from typing import Any

from .sound_catalog_impl import validate_catalog, validate_pools


def validate_sound_catalog(catalog: Any, pools: Any | None = None) -> dict[str, Any]:
    catalog_result = validate_catalog(catalog)
    if pools is not None:
        pool_result = validate_pools(pools, set(catalog_result.get("preset_ids", [])))
        catalog_result["errors"].extend(pool_result.get("errors", []))
        catalog_result["warnings"].extend(pool_result.get("warnings", []))
        catalog_result["ok"] = not catalog_result["errors"]
        catalog_result["pool_ids"] = pool_result.get("pool_ids", [])
    return catalog_result
