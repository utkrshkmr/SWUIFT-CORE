"""Visualisation: per-timestep frames, GIF, video, and summary plots."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from typing import List, Optional, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

# ── colour map ────────────────────────────────────────────────────────────────

_VALUES = np.array([-5, -4, -2, -1, 0, 1, 2, 3, 4])

_LABELS_MATLAB = [
    "water", "veg burned", "veg ignited", "veg", "not-combustible",
    "str", "str ignited", "str developed", "str burned",
]

_LABELS_CLEAN = [
    "Water",
    "Vegetation Burned",
    "Vegetation Ignited",
    "Vegetation",
    "Non-Combustible",
    "Structure",
    "Structure Ignited",
    "Structure Fully Developed",
    "Structure Burned Out",
]


def _legend_label_two_lines(label: str) -> str:
    """Put the third word (and rest) of a label on the next line."""
    words = label.split()
    if len(words) >= 3:
        return " ".join(words[:2]) + "\n" + " ".join(words[2:])
    return label

_CMAP_RGB = np.array([
    [0.67, 0.80, 0.91],  # water
    [0.00, 0.30, 0.00],  # veg burned
    [1.00, 1.00, 0.00],  # veg ignited
    [0.54, 0.64, 0.48],  # veg
    [0.70, 0.70, 0.70],  # not-combustible
    [0.44, 0.50, 0.56],  # str
    [1.00, 0.00, 0.00],  # str ignited
    [0.55, 0.13, 0.32],  # str developed
    [0.00, 0.00, 0.20],  # str burned
])


# ── build the classification matrix ─────────────────────────────────────────

def build_plt_mat(
    rows: int,
    cols: int,
    binary_cover: np.ndarray,
    ignition: np.ndarray,
    fire: np.ndarray,
    fstep: int,
    lstep: int,
    water: np.ndarray,
) -> np.ndarray:
    """Build the integer classification matrix exactly as MATLAB does."""
    plt_mat = np.zeros((rows, cols), dtype=np.float64)
    plt_mat[binary_cover < 0] = -1   # veg
    plt_mat[binary_cover == 0] = 0   # not-combustible
    plt_mat[binary_cover > 0] = 1    # str

    ig_bc = ignition * binary_cover
    plt_mat[ig_bc < 0] = -2          # veg ignited
    plt_mat[ig_bc > 0] = 2           # str ignited
    plt_mat[(binary_cover > 0) & (fire >= fstep) & (fire <= lstep)] = 3  # str developed
    plt_mat[(binary_cover > 0) & (fire > lstep)] = 4                     # str burned
    plt_mat[(binary_cover < 0) & (fire > 1)] = -4                        # veg burned
    plt_mat[water > 0] = -5          # water
    return plt_mat


# ── MATLAB-style snapshot (matches legacy output) ───────────────────────────

def render_snapshot_matlab(
    plt_mat: np.ndarray,
    long: np.ndarray,
    lati: np.ndarray,
    timestamp_str: str,
    out_path: str,
    dpi: int = 150,
) -> None:
    """Render one frame matching the MATLAB f_plots style."""
    present = np.unique(plt_mat)
    idx = np.isin(_VALUES, present.astype(int))
    used_values = _VALUES[idx]
    used_labels = [_LABELS_MATLAB[k] for k in np.where(idx)[0]]
    used_colors = _CMAP_RGB[idx]

    remap = plt_mat.copy()
    for ci, val in enumerate(used_values):
        remap[plt_mat == val] = 100 * (ci + 1)

    cmap = mcolors.ListedColormap(used_colors)
    bounds = [100 * (ci + 1) - 50 for ci in range(len(used_values))] + [
        100 * len(used_values) + 50
    ]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, ax = plt.subplots(figsize=(8, 8))
    fig.patch.set_facecolor("white")

    hs = ax.pcolormesh(long, lati, remap, cmap=cmap, norm=norm, shading="auto")
    ax.set_aspect("auto")

    cb = fig.colorbar(hs, ax=ax, ticks=[100 * (ci + 1) for ci in range(len(used_values))])
    cb.ax.set_yticklabels(used_labels)

    ax.set_title(f"{timestamp_str}", fontsize=18)
    ax.tick_params(labelsize=14)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.2f}"))
    fig.autofmt_xdate(rotation=0, ha="center")

    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


# ── high-res clean snapshot ─────────────────────────────────────────────────

def render_snapshot_hires(
    plt_mat: np.ndarray,
    long: np.ndarray,
    lati: np.ndarray,
    timestamp_str: str,
    out_path: str,
    dpi: int = 600,
) -> None:
    """Render a high-resolution frame with clean legend and no axis labels.
    Legend shows all categories always; label text wraps at third word."""
    used_values = _VALUES
    used_labels = [_legend_label_two_lines(l) for l in _LABELS_CLEAN]
    used_colors = _CMAP_RGB

    remap = plt_mat.copy()
    for ci, val in enumerate(used_values):
        remap[plt_mat == val] = 100 * (ci + 1)

    cmap = mcolors.ListedColormap(used_colors)
    bounds = [100 * (ci + 1) - 50 for ci in range(len(used_values))] + [
        100 * len(used_values) + 50
    ]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, ax = plt.subplots(figsize=(12, 10))
    fig.patch.set_facecolor("white")

    hs = ax.pcolormesh(long, lati, remap, cmap=cmap, norm=norm, shading="auto")
    ax.set_aspect("auto")

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    for spine in ax.spines.values():
        spine.set_visible(False)

    cb = fig.colorbar(
        hs, ax=ax,
        ticks=[100 * (ci + 1) for ci in range(len(used_values))],
        shrink=0.85,
        pad=0.02,
    )
    cb.ax.set_yticklabels(used_labels, fontsize=11)
    cb.outline.set_visible(False)

    ax.set_title(timestamp_str, fontsize=20, fontweight="bold", pad=12)

    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)


# ── snapshot helpers used by simulation loop ────────────────────────────────

def save_snapshot(
    rows: int,
    cols: int,
    binary_cover: np.ndarray,
    ignition: np.ndarray,
    fire: np.ndarray,
    long: np.ndarray,
    lati: np.ndarray,
    sim_time: datetime,
    tstep: int,
    fstep: int,
    lstep: int,
    water: np.ndarray,
    frames_dir: str,
    dpi: int = 600,
) -> None:
    """Save a single high-res frame for one timestep (MATLAB-style output retired)."""
    plt_mat = build_plt_mat(rows, cols, binary_cover, ignition, fire, fstep, lstep, water)
    ts_str = sim_time.strftime("%H:%M") + " MST"
    fname = f"{tstep:04d}.png"
    render_snapshot_hires(plt_mat, long, lati, ts_str,
                          os.path.join(frames_dir, fname), dpi=dpi)


def save_frame_csv(
    rows: int,
    cols: int,
    binary_cover: np.ndarray,
    ignition: np.ndarray,
    fire: np.ndarray,
    fstep: int,
    lstep: int,
    water: np.ndarray,
    tstep: int,
    frame_csvs_dir: str,
) -> None:
    """Export the classification matrix as CSV for one timestep."""
    plt_mat = build_plt_mat(rows, cols, binary_cover, ignition, fire, fstep, lstep, water)
    out_path = os.path.join(frame_csvs_dir, f"{tstep:04d}.csv")
    np.savetxt(out_path, plt_mat, delimiter=",", fmt="%.0f")


# ── assemble video ──────────────────────────────────────────────────────────

def assemble_video(
    frames_dir: str,
    output_dir: str,
    fps: int = 4,
    tag: str = "",
    make_mp4: bool = True,
    make_gif: bool = True,
) -> None:
    """Stitch PNGs into MP4 and GIF using ffmpeg (subprocess)."""
    pattern = os.path.join(frames_dir, "%04d.png")

    suffix = f"_{tag}" if tag else ""
    mp4_path = os.path.join(output_dir, f"simulation{suffix}.mp4")
    gif_path = os.path.join(output_dir, f"simulation{suffix}.gif")

    if make_mp4:
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-i", pattern,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    mp4_path,
                ],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError:
            _assemble_video_imageio(frames_dir, mp4_path, fps)

    if make_gif:
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-i", pattern,
                    gif_path,
                ],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError:
            _assemble_gif_imageio(frames_dir, gif_path, fps)


def _assemble_video_imageio(frames_dir: str, out_path: str, fps: int):
    import imageio.v3 as iio
    frames = sorted(
        f for f in os.listdir(frames_dir) if f.endswith(".png")
    )
    writer = iio.imopen(out_path, "w", plugin="pyav")
    for fn in frames:
        img = iio.imread(os.path.join(frames_dir, fn))
        writer.write(img)
    writer.close()


def _assemble_gif_imageio(frames_dir: str, out_path: str, fps: int):
    import imageio.v2 as iio
    frames = sorted(
        f for f in os.listdir(frames_dir) if f.endswith(".png")
    )
    images = [iio.imread(os.path.join(frames_dir, fn)) for fn in frames]
    iio.mimsave(out_path, images, duration=1.0 / fps, loop=0)


# ── summary plots ───────────────────────────────────────────────────────────

def plot_pixel_ignitions(
    output_dir: str,
    maxstep: int,
    time_labels: List[str],
    tick_positions: List[int],
    ig_known: np.ndarray,
    ig_dev: np.ndarray,
    ig_rad: np.ndarray,
    ig_brand: np.ndarray,
    ig_total: np.ndarray,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))
    x = np.arange(1, maxstep + 1)
    ax.plot(x, np.cumsum(ig_known), lw=2, color=(1, 0.7, 0), label="Known")
    ax.plot(x, np.cumsum(ig_dev), lw=2, color="g", label="Developed")
    ax.plot(x, np.cumsum(ig_rad), lw=2, color="r", label="Radiation")
    ax.plot(x, np.cumsum(ig_brand), lw=2, color="k", label="Branding")
    ax.plot(x, ig_total, lw=2, color="b", label="Total")
    ax.legend(loc="upper left")
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(time_labels, fontsize=12)
    ax.set_xlabel("Time", fontsize=18)
    ax.set_ylabel("Number of ignited pixels", fontsize=18)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "ig_pixel.png"), dpi=150)
    plt.close(fig)


def plot_structure_ignitions(
    output_dir: str,
    maxstep: int,
    time_labels: List[str],
    tick_positions: List[int],
    house_ig_known: np.ndarray,
    house_ig_rad: np.ndarray,
    house_ig_brand: np.ndarray,
    house_ig_total: np.ndarray,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))
    x = np.arange(1, maxstep + 1)
    ax.plot(x, np.cumsum(house_ig_known), lw=2, color=(1, 0.7, 0), label="Known")
    ax.plot(x, np.cumsum(house_ig_rad), lw=2, color="r", label="Radiation")
    ax.plot(x, np.cumsum(house_ig_brand), lw=2, color="k", label="Branding")
    ax.plot(x, house_ig_total, lw=2, color="b", label="Total")
    ax.legend(loc="upper left")
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(time_labels, fontsize=12)
    ax.set_xlabel("Time", fontsize=18)
    ax.set_ylabel("Number of ignited structures", fontsize=18)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "ig_structure.png"), dpi=150)
    plt.close(fig)
