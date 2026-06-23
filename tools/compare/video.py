"""Video frame DPI helpers for 1080p comparison stitching."""

from __future__ import annotations

import math

TARGET_HEIGHT_1080 = 1080
HIRES_FIGSIZE = (12.0, 10.0)


def frame_dpi_for_height(
    figsize_inches: tuple[float, float] = HIRES_FIGSIZE,
    target_height: int = TARGET_HEIGHT_1080,
) -> int:
    """Compute matplotlib DPI so saved PNG height is approximately target_height."""
    return max(72, math.ceil(target_height / figsize_inches[1]))


def recommended_frame_dpi(target_height: int = TARGET_HEIGHT_1080) -> int:
    """Recommended DPI for app/CLI frame exports used in comparison videos."""
    return frame_dpi_for_height(HIRES_FIGSIZE, target_height)
