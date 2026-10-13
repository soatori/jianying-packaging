"""Fields with verified direct visual-override adapters."""

from __future__ import annotations


DIRECT_OVERRIDE_FIELDS = frozenset({
    "position_x",
    "position_y",
    "scale_x",
    "scale_y",
    "uniform_scale",
    "start_us",
    "duration_us",
    "visible",
    "global_alpha",
})

__all__ = ["DIRECT_OVERRIDE_FIELDS"]
