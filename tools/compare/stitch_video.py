"""Stitch side-by-side comparison videos from MATLAB, app, and CLI frame sources."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from video import TARGET_HEIGHT_1080


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _add_label(img: Image.Image, text: str, font) -> Image.Image:
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    x, y = 20, 20
    for dx, dy in (
        (-2, 0), (2, 0), (0, -2), (0, 2),
        (-2, -2), (2, 2), (-2, 2), (2, -2),
    ):
        draw.text((x + dx, y + dy), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill="white")
    return img


def _resize_to_height(img: Image.Image, height: int) -> Image.Image:
    w, h = img.size
    new_w = max(2, int(round(w * height / h)))
    if new_w % 2:
        new_w += 1
    return img.resize((new_w, height), Image.Resampling.LANCZOS)


def _sorted_frame_paths(directory: Path, pattern: str) -> list[Path]:
    paths = list(directory.glob(pattern))
    if not paths:
        return []

    def sort_key(p: Path) -> tuple[int, str]:
        m = re.search(r"(\d+)", p.stem)
        return (int(m.group(1)) if m else 0, p.name)

    return sorted(paths, key=sort_key)


def resolve_frame_sources(run_root: Path, *, steps: int | None) -> dict[str, list[Path]]:
    """Locate PNG frame sequences for matlab, app, and cli under a run root."""
    from paths import LEGACY_STAGE_APP, LEGACY_STAGE_CLI, LEGACY_STAGE_MATLAB, STAGE_APP, STAGE_CLI, STAGE_MATLAB

    sources: dict[str, list[Path]] = {}

    matlab_dirs = [
        run_root / STAGE_MATLAB / "work" / "outs",
        run_root / LEGACY_STAGE_MATLAB / "work" / "outs",
    ]
    for d in matlab_dirs:
        frames = _sorted_frame_paths(d, "*.png")
        if frames:
            sources["matlab"] = frames
            break

    app_dirs = [
        run_root / STAGE_APP / "outputs" / "frames",
        run_root / LEGACY_STAGE_APP / "outputs" / "frames",
    ]
    for d in app_dirs:
        frames = _sorted_frame_paths(d, "*.png")
        if frames:
            sources["app"] = frames
            break

    cli_stage_dirs = sorted((run_root / STAGE_CLI).glob("*")) if (run_root / STAGE_CLI).exists() else []
    cli_stage_dirs += sorted((run_root / LEGACY_STAGE_CLI).glob("*"))
    for d in cli_stage_dirs:
        if not d.is_dir():
            continue
        frames = _sorted_frame_paths(d / "frames", "*.png")
        if frames:
            sources["cli"] = frames
            break

    if steps is not None:
        for key in list(sources):
            sources[key] = sources[key][:steps]
    return sources


def stitch_panel_video(
    panels: dict[str, Iterable[Path]],
    output_path: Path,
    *,
    target_height: int = TARGET_HEIGHT_1080,
    fps: int = 4,
    labels: dict[str, str] | None = None,
) -> Path:
    """Write a horizontal side-by-side MP4 from labeled panel frame lists."""
    order = [name for name in ("matlab", "app", "cli") if name in panels]
    if not order:
        raise FileNotFoundError("No panel frame sources provided for stitching")

    label_map = labels or {"matlab": "MATLAB", "app": "APP", "cli": "CLI"}
    font = _load_font(max(24, target_height // 24))
    frame_lists = {name: list(panels[name]) for name in order}
    n = min(len(frame_lists[name]) for name in order)
    if n == 0:
        raise RuntimeError("No frames to stitch")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(output_path),
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=1,
    )
    try:
        for i in range(n):
            imgs = []
            for name in order:
                img = Image.open(frame_lists[name][i])
                img = _add_label(
                    _resize_to_height(img, target_height),
                    label_map.get(name, name.upper()),
                    font,
                )
                imgs.append(img)
            h = max(im.height for im in imgs)
            resized = []
            for im in imgs:
                if im.height != h:
                    im = im.resize((int(im.width * h / im.height), h), Image.Resampling.LANCZOS)
                resized.append(im)
            total_w = sum(im.width for im in resized)
            canvas = Image.new("RGB", (total_w, h))
            x = 0
            for im in resized:
                canvas.paste(im, (x, 0))
                x += im.width
            writer.append_data(np.asarray(canvas))
    finally:
        writer.close()
    return output_path
