from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from packaging_tools.visual_preview import (
    VisualPreviewError,
    build_html_preview,
    fit_slots_to_safe_zone,
    measure_text_lines,
)


class _MeasuredFont:
    def getlength(self, text: str) -> float:
        return sum(10.0 if char.isascii() else 20.0 for char in text)

    def getbbox(self, _text: str):
        return (0, 0, 20, 20)


class VisualPreviewTests(unittest.TestCase):
    def test_measures_each_line_with_actual_font_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            font_path = Path(directory) / "font.ttf"
            font_path.write_bytes(b"fixture-font-placeholder")
            lines = measure_text_lines(
                "AB\n中",
                font_path=font_path,
                font_size_px=20,
                font_loader=lambda _path, _size: _MeasuredFont(),
            )

        self.assertEqual(lines, [
            {"text": "AB", "width_px": 20.0, "height_px": 20.0},
            {"text": "中", "width_px": 20.0, "height_px": 20.0},
        ])

    def test_missing_font_metrics_fail_closed(self):
        with self.assertRaisesRegex(VisualPreviewError, "font metrics"):
            measure_text_lines("text", font_path=None, font_size_px=20)

    def test_group_fit_preserves_diagonal_offsets_and_clamps_edges(self):
        slots = [
            {"id": "line-1", "x": -0.95, "y": 0.4, "bounds": {"width": 0.2, "height": 0.1}},
            {"id": "line-2", "x": -0.55, "y": 0.0, "bounds": {"width": 0.3, "height": 0.1}},
        ]

        fitted = fit_slots_to_safe_zone(
            slots,
            {"x_min": -0.8, "x_max": 0.8, "y_min": -0.8, "y_max": 0.8},
        )

        self.assertEqual(fitted["shift_x"], 0.25)
        self.assertEqual(fitted["slots"][0]["x"], -0.7)
        self.assertEqual(fitted["slots"][1]["x"], -0.3)
        self.assertEqual(fitted["slots"][1]["y"] - fitted["slots"][0]["y"], -0.4)

    def test_group_too_wide_for_safe_zone_is_rejected(self):
        slots = [{"id": "wide", "x": 0.0, "y": 0.0, "bounds": {"width": 2.0, "height": 0.2}}]
        with self.assertRaisesRegex(VisualPreviewError, "wider than the safe zone"):
            fit_slots_to_safe_zone(slots, {"x_min": -0.8, "x_max": 0.8, "y_min": -0.8, "y_max": 0.8})

    def test_group_fit_accounts_for_rotated_axis_aligned_bounds(self):
        fitted = fit_slots_to_safe_zone(
            [{"id": "rotated", "x": 0.7, "y": 0.0, "rotation": 45.0, "bounds": {"width": 0.2, "height": 0.2}}],
            {"x_min": -0.8, "x_max": 0.8, "y_min": -0.8, "y_max": 0.8},
        )

        self.assertAlmostEqual(fitted["shift_x"], 0.8 - (0.7 + 0.2 * 2 ** 0.5 / 2), places=8)
        self.assertAlmostEqual(fitted["slots"][0]["x"], 0.8 - 0.2 * 2 ** 0.5 / 2, places=8)

    def test_group_fit_reads_nested_rotation_and_swaps_rectangle_extents(self):
        fitted = fit_slots_to_safe_zone(
            [{
                "id": "vertical",
                "x": 0.0,
                "y": 0.75,
                "transform": {"rotation": 90.0},
                "bounds": {"width": 0.4, "height": 0.1},
            }],
            {"x_min": -0.8, "x_max": 0.8, "y_min": -0.8, "y_max": 0.8},
        )

        self.assertAlmostEqual(fitted["shift_x"], 0.0, places=8)
        self.assertAlmostEqual(fitted["shift_y"], -0.15, places=8)
        self.assertAlmostEqual(fitted["slots"][0]["y"], 0.6, places=8)

    def test_html_preview_escapes_text_and_marks_native_animation_as_unverified(self):
        html = build_html_preview({
            "canvas_width": 1080,
            "canvas_height": 1920,
            "safe_zone": {"x_min": -0.8, "x_max": 0.8, "y_min": -0.8, "y_max": 0.8},
            "slots": [{
                "id": "mark",
                "text": "<mark>",
                "x": 0,
                "y": 0,
                "width_px": 120,
                "height_px": 48,
                "global_alpha": 0.5,
                "rotation": 0,
                "scale_x": 0.8,
                "scale_y": 1.2,
                "start_us": 1_000_000,
                "duration_us": 1_840_000,
                "line_widths_px": [60.0],
                "animation_resource_id": "rid-1",
                "animation_duration_us": 1_840_000,
                "native_verified": False,
            }],
        })

        self.assertIn("&lt;mark&gt;", html)
        self.assertIn("0.5", html)
        self.assertIn("1,840,000", html)
        self.assertIn("60.0px", html)
        self.assertIn("1,000,000–2,840,000 µs", html)
        self.assertIn("scale 0.8000×1.2000", html)
        self.assertIn("native Jianying verification pending", html)

    def test_html_preview_uses_nested_rotation(self):
        html = build_html_preview({
            "canvas_width": 1080,
            "canvas_height": 1920,
            "safe_zone": {"x_min": -0.8, "x_max": 0.8, "y_min": -0.8, "y_max": 0.8},
            "slots": [{
                "id": "nested-rotation",
                "text": "rotated",
                "x": 0,
                "y": 0,
                "width_px": 120,
                "height_px": 48,
                "transform": {"rotation": 45},
            }],
        })

        self.assertIn("rotate(45.0000deg)", html)


if __name__ == "__main__":
    unittest.main()
