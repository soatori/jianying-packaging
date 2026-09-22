"""Inventory packaging templates, materials and font evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .result import result


def inventory_templates_and_materials(observation: Any) -> dict[str, Any]:
    if not isinstance(observation, dict):
        return result("packaging_inventory", errors=["observation must be a JSON object"])
    templates = observation.get("templates", [])
    materials = observation.get("materials", [])
    fonts = observation.get("fonts", [])
    errors: list[str] = []
    for name, value in (("templates", templates), ("materials", materials), ("fonts", fonts)):
        if not isinstance(value, list):
            errors.append(f"{name} must be an array")
    if errors:
        return result("packaging_inventory", errors=errors)
    missing_fonts = []
    for font in fonts if isinstance(fonts, list) else []:
        if isinstance(font, dict) and font.get("path") and not Path(str(font["path"])).exists():
            missing_fonts.append(font.get("path"))
    unresolved = []
    material_ids = {str(item.get("id", item.get("material_id"))) for item in materials if isinstance(item, dict)}
    for template in templates if isinstance(templates, list) else []:
        if not isinstance(template, dict):
            continue
        refs = template.get("material_refs", template.get("extra_material_refs", [])) or []
        for ref in refs:
            if str(ref) not in material_ids:
                unresolved.append({"template": template.get("id"), "material": ref})
    errors = ["template material closure contains unresolved references"] if unresolved else []
    warnings = [f"font path does not exist: {path}" for path in missing_fonts]
    return result(
        "packaging_inventory",
        data={"templates": templates, "materials": materials, "fonts": fonts, "missing_fonts": missing_fonts, "unresolved_refs": unresolved},
        errors=errors,
        warnings=warnings,
        summary={"template_count": len(templates) if isinstance(templates, list) else 0, "material_count": len(materials) if isinstance(materials, list) else 0},
    )
