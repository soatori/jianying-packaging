"""Text-width geometry and review-only HTML preview for packaging candidates."""

from __future__ import annotations

import copy
import html
import math
from pathlib import Path
from typing import Any, Callable

from .layout_resolver import rotated_aabb_size


class VisualPreviewError(ValueError):
    """A candidate cannot be measured or represented faithfully enough to preview."""


def measure_text_lines(
    text: str,
    *,
    font_path: str | Path | None,
    font_size_px: float,
    letter_spacing_px: float = 0.0,
    font_loader: Callable[[str, int], Any] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(text, str):
        raise VisualPreviewError("text must be a string")
    if not font_path or not Path(font_path).is_file():
        raise VisualPreviewError("reliable font metrics are unavailable")
    if isinstance(font_size_px, bool) or not isinstance(font_size_px, (int, float)) or not math.isfinite(float(font_size_px)) or font_size_px < 1:
        raise VisualPreviewError("font size must be a usable finite pixel value")
    if isinstance(letter_spacing_px, bool) or not isinstance(letter_spacing_px, (int, float)) or not math.isfinite(float(letter_spacing_px)):
        raise VisualPreviewError("letter spacing must be a finite pixel value")

    if font_loader is None:
        try:
            from PIL import ImageFont
        except ImportError as exc:
            raise VisualPreviewError("Pillow is required for exact local font metrics") from exc
        font_loader = lambda path, size: ImageFont.truetype(path, size)
    try:
        font = font_loader(str(font_path), max(1, round(font_size_px)))
    except Exception as exc:
        raise VisualPreviewError(f"font metrics could not be loaded: {exc}") from exc

    lines = text.split("\n") or [""]
    measured = []
    for line in lines:
        try:
            width = float(font.getlength(line)) if line else 0.0
            top, bottom = font.getbbox(line or "国Ag")[1::2]
        except Exception as exc:
            raise VisualPreviewError(f"font metrics could not measure a text line and height: {exc}") from exc
        width += max(0, len(line) - 1) * float(letter_spacing_px)
        measured.append({"text": line, "width_px": round(width, 4), "height_px": float(bottom - top)})
    return measured


def _slot_rotation(slot: dict[str, Any]) -> float:
    rotation = slot.get("rotation")
    if rotation is None:
        transform = slot.get("transform")
        rotation = transform.get("rotation", 0.0) if isinstance(transform, dict) else 0.0
    if isinstance(rotation, bool) or not isinstance(rotation, (int, float)) or not math.isfinite(float(rotation)):
        raise VisualPreviewError("slot rotation must be a finite number")
    return float(rotation)


def fit_slots_to_safe_zone(slots: list[dict[str, Any]], safe_zone: dict[str, Any]) -> dict[str, Any]:
    bounds = {key: safe_zone.get(key) for key in ("x_min", "x_max", "y_min", "y_max")} if isinstance(safe_zone, dict) else {}
    if not bounds or not all(
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
        for value in bounds.values()
    ):
        raise VisualPreviewError("numeric safe-zone bounds are required")
    if bounds["x_min"] >= bounds["x_max"] or bounds["y_min"] >= bounds["y_max"]:
        raise VisualPreviewError("safe-zone bounds must be ordered")
    if bounds["x_min"] < -1 or bounds["x_max"] > 1 or bounds["y_min"] < -1 or bounds["y_max"] > 1:
        raise VisualPreviewError("safe-zone bounds must be inside the normalized canvas")
    if not slots:
        raise VisualPreviewError("at least one measured text slot is required")

    result = copy.deepcopy(slots)
    extents = []
    for slot in result:
        if not isinstance(slot, dict) or not isinstance(slot.get("bounds"), dict):
            raise VisualPreviewError("each slot requires measured bounds")
        x, y = slot.get("x"), slot.get("y")
        width, height = slot["bounds"].get("width"), slot["bounds"].get("height")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in (x, y, width, height)):
            raise VisualPreviewError("slot positions and bounds must be finite numbers")
        if width < 0 or height < 0:
            raise VisualPreviewError("slot bounds must be non-negative")
        rotated_width, rotated_height = rotated_aabb_size(width, height, _slot_rotation(slot))
        extents.append((
            x - rotated_width / 2,
            x + rotated_width / 2,
            y - rotated_height / 2,
            y + rotated_height / 2,
        ))

    left = min(item[0] for item in extents)
    right = max(item[1] for item in extents)
    top = min(item[2] for item in extents)
    bottom = max(item[3] for item in extents)
    safe_width = bounds["x_max"] - bounds["x_min"]
    safe_height = bounds["y_max"] - bounds["y_min"]
    if right - left > safe_width or bottom - top > safe_height:
        raise VisualPreviewError("measured text group is wider than the safe zone")

    shift_x = max(0.0, bounds["x_min"] - left) + min(0.0, bounds["x_max"] - right)
    shift_y = max(0.0, bounds["y_min"] - top) + min(0.0, bounds["y_max"] - bottom)
    for slot in result:
        slot["x"] = round(float(slot["x"]) + shift_x, 8)
        slot["y"] = round(float(slot["y"]) + shift_y, 8)
    return {"slots": result, "shift_x": round(shift_x, 8), "shift_y": round(shift_y, 8)}


def build_html_preview(model: dict[str, Any]) -> str:
    width, height = model.get("canvas_width"), model.get("canvas_height")
    safe_zones = model.get("safe_zones")
    if not isinstance(safe_zones, list):
        safe_zone = model.get("safe_zone")
        safe_zones = [{"id": "canvas", "bounds": safe_zone}] if isinstance(safe_zone, dict) else []
    slots = model.get("slots")
    if isinstance(width, bool) or not isinstance(width, int) or width <= 0 or isinstance(height, bool) or not isinstance(height, int) or height <= 0:
        raise VisualPreviewError("preview canvas dimensions are required")
    if not safe_zones or not isinstance(slots, list):
        raise VisualPreviewError("preview safe_zones and slots are required")

    safe_layers = []
    for zone in safe_zones:
        bounds = zone.get("bounds") if isinstance(zone, dict) else None
        values = [bounds.get(key) for key in ("x_min", "x_max", "y_min", "y_max")] if isinstance(bounds, dict) else []
        if len(values) != 4 or not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) for value in values):
            raise VisualPreviewError("preview safe-zone bounds must be numeric")
        x_min, x_max, y_min, y_max = values
        if x_min >= x_max or y_min >= y_max or x_min < -1 or x_max > 1 or y_min < -1 or y_max > 1:
            raise VisualPreviewError("preview safe-zone bounds must be ordered inside the normalized canvas")
        safe_layers.append(
            f'<div class="safe" data-zone="{html.escape(str(zone.get("id", "safe")))}" '
            f'style="left:{(0.5 + x_min / 2) * width:.2f}px;top:{(0.5 - y_max / 2) * height:.2f}px;'
            f'width:{(x_max - x_min) * width / 2:.2f}px;height:{(y_max - y_min) * height / 2:.2f}px"></div>'
        )

    layers = []
    for slot in slots:
        if not isinstance(slot, dict):
            raise VisualPreviewError("preview slots must be objects")
        x, y = slot.get("x"), slot.get("y")
        if not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(float(x)) or not isinstance(y, (int, float)) or isinstance(y, bool) or not math.isfinite(float(y)):
            raise VisualPreviewError("preview slot coordinates must be numeric")
        cx, cy = width / 2 + x * width / 2, height / 2 - y * height / 2
        box = slot.get("bounds", {}) if isinstance(slot.get("bounds"), dict) else {}
        box_width = float(box.get("width_px", box.get("width", 0)))
        box_height = float(box.get("height_px", box.get("height", 0)))
        alpha = float(slot.get("global_alpha", 1.0))
        rotation = _slot_rotation(slot)
        if any(not math.isfinite(value) for value in (box_width, box_height, alpha, rotation)) or box_width < 0 or box_height < 0 or not 0 <= alpha <= 1:
            raise VisualPreviewError("preview bounds, alpha, and rotation must be finite and valid")
        text = html.escape(str(slot.get("text", "")))
        label = html.escape(str(slot.get("id", "text")))
        animation = slot.get("animation_duration_us")
        animation_label = (
            f"animation {html.escape(str(slot.get('animation_resource_id', '')))} · {int(animation):,} µs"
            if isinstance(animation, int) and not isinstance(animation, bool)
            else "no planned entrance animation"
        )
        verification = "native Jianying animation verified" if slot.get("native_verified") else "native Jianying verification pending"
        line_widths = ", ".join(f"{float(value):.1f}px" for value in slot.get("line_widths_px", []))
        visibility = "visible" if slot.get("visible", True) else "hidden"
        z_index = int(slot.get("track_render_index", 0))
        scale_x = float(slot.get("scale_x", 1.0))
        scale_y = float(slot.get("scale_y", 1.0))
        start_us = int(slot.get("start_us", 0))
        duration_us = int(slot.get("duration_us", 0))
        if not math.isfinite(scale_x) or not math.isfinite(scale_y) or start_us < 0 or duration_us < 0:
            raise VisualPreviewError("preview scale and row timing must be finite and non-negative")
        layers.append(
            f'<div class="layer" style="left:{cx - box_width / 2:.2f}px;top:{cy - box_height / 2:.2f}px;'
            f'width:{box_width:.2f}px;height:{box_height:.2f}px;opacity:{alpha:.4f};visibility:{visibility};'
            f'z-index:{z_index};transform:rotate({rotation:.4f}deg) scale({scale_x:.5f},{scale_y:.5f})">'
            f'<strong>{label}</strong><div>{text}</div><small>{html.escape(str(slot.get("track_name", "text")))} '
            f'(track {z_index}); lines {line_widths}; '
            f'row {start_us:,}–{start_us + duration_us:,} µs; scale {scale_x:.4f}×{scale_y:.4f}; '
            f'{animation_label}; {verification}</small></div>'
        )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Packaging visual preview</title>"
        "<style>body{font:14px sans-serif;background:#333;color:#eee}.stage{position:relative;"
        f"width:{width}px;height:{height}px;background:#181818;overflow:hidden;margin:24px auto}}"
        ".safe{position:absolute;"
        "border:1px dashed #7fd4a2;box-sizing:border-box}.layer{position:absolute;box-sizing:border-box;"
        "border:1px solid #f0c75e;color:#fff;display:flex;flex-direction:column;justify-content:center;"
        "text-align:center;white-space:pre-wrap;overflow:hidden}.layer small{font-size:10px;color:#f4d58a}</style></head><body>"
        "<p>Layout and timing intent preview; native effect persistence must be checked after reopening Jianying.</p>"
        f'<div class="stage">{"".join(safe_layers)}{"".join(layers)}</div></body></html>'
    )
