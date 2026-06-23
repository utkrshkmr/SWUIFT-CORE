from __future__ import annotations
import os
import subprocess
from datetime import datetime, timedelta
from typing import List, Optional, Sequence
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
_VALUES = np.array([-5, -4, -2, -1, 0, 1, 2, 3, 4])
_LABELS_CLEAN = ['Water', 'Vegetation Burned', 'Vegetation Ignited', 'Vegetation', 'Non-Combustible', 'Structure', 'Structure Ignited', 'Structure Fully Developed', 'Structure Burned Out']

def _legend_label_two_lines(label: str) -> str:
    words = label.split()
    if len(words) >= 3:
        return ' '.join(words[:2]) + '\n' + ' '.join(words[2:])
    return label
_CMAP_RGB = np.array([[0.67, 0.8, 0.91], [0.0, 0.3, 0.0], [1.0, 1.0, 0.0], [0.54, 0.64, 0.48], [0.7, 0.7, 0.7], [0.44, 0.5, 0.56], [1.0, 0.0, 0.0], [0.55, 0.13, 0.32], [0.0, 0.0, 0.2]])
_VALUE_TO_REMAP = np.zeros(10, dtype=np.float64)
for _ci, _val in enumerate(_VALUES):
    if -5 <= _val <= 4:
        _VALUE_TO_REMAP[_val + 5] = 100.0 * (_ci + 1)
_FRAME_STATE_DTYPE = np.int16

def build_plt_mat(rows: int, cols: int, binary_cover: np.ndarray, ignition: np.ndarray, fire: np.ndarray, fstep: int, lstep: int, water: np.ndarray) -> np.ndarray:
    plt_mat = np.zeros((rows, cols), dtype=np.float64)
    plt_mat[binary_cover < 0] = -1
    plt_mat[binary_cover == 0] = 0
    plt_mat[binary_cover > 0] = 1
    ig_bc = ignition * binary_cover
    plt_mat[ig_bc < 0] = -2
    plt_mat[ig_bc > 0] = 2
    plt_mat[(binary_cover > 0) & (fire >= fstep) & (fire <= lstep)] = 3
    plt_mat[(binary_cover > 0) & (fire > lstep)] = 4
    plt_mat[(binary_cover < 0) & (fire > 1)] = -4
    plt_mat[water > 0] = -5
    return plt_mat

def render_snapshot_hires(plt_mat: np.ndarray, long: np.ndarray, lati: np.ndarray, timestamp_str: str, out_path: str, dpi: int=600) -> None:
    used_values = _VALUES
    used_labels = [_legend_label_two_lines(l) for l in _LABELS_CLEAN]
    used_colors = _CMAP_RGB
    remap = _VALUE_TO_REMAP[(plt_mat.astype(np.int16) + 5).clip(0, 9)]
    cmap = mcolors.ListedColormap(used_colors)
    bounds = [100 * (ci + 1) - 50 for ci in range(len(used_values))] + [100 * len(used_values) + 50]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)
    fig, ax = plt.subplots(figsize=(12, 10))
    fig.patch.set_facecolor('white')
    hs = ax.pcolormesh(long, lati, remap, cmap=cmap, norm=norm, shading='auto')
    ax.set_aspect('auto')
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel('')
    ax.set_ylabel('')
    for spine in ax.spines.values():
        spine.set_visible(False)
    cb = fig.colorbar(hs, ax=ax, ticks=[100 * (ci + 1) for ci in range(len(used_values))], shrink=0.85, pad=0.02)
    cb.ax.set_yticklabels(used_labels, fontsize=11)
    cb.outline.set_visible(False)
    ax.set_title(timestamp_str, fontsize=20, fontweight='bold', pad=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)

def save_snapshot(rows: int, cols: int, binary_cover: np.ndarray, ignition: np.ndarray, fire: np.ndarray, long: np.ndarray, lati: np.ndarray, sim_time: datetime, tstep: int, fstep: int, lstep: int, water: np.ndarray, frames_dir: str, dpi: int=600) -> None:
    plt_mat = build_plt_mat(rows, cols, binary_cover, ignition, fire, fstep, lstep, water)
    ts_str = sim_time.strftime('%H:%M') + ' MST'
    fname = f'{tstep:04d}.png'
    render_snapshot_hires(plt_mat, long, lati, ts_str, os.path.join(frames_dir, fname), dpi=dpi)

def save_frame_csv(rows: int, cols: int, binary_cover: np.ndarray, ignition: np.ndarray, fire: np.ndarray, fstep: int, lstep: int, water: np.ndarray, tstep: int, frame_csvs_dir: str) -> None:
    plt_mat = build_plt_mat(rows, cols, binary_cover, ignition, fire, fstep, lstep, water)
    save_frame_csv_from_plt_mat(plt_mat, tstep, frame_csvs_dir)

def save_snapshot_from_plt_mat(plt_mat: np.ndarray, long: np.ndarray, lati: np.ndarray, sim_time: datetime, tstep: int, frames_dir: str, dpi: int=600) -> None:
    ts_str = sim_time.strftime('%H:%M') + ' MST'
    fname = f'{tstep:04d}.png'
    render_snapshot_hires(plt_mat, long, lati, ts_str, os.path.join(frames_dir, fname), dpi=dpi)

def save_frame_csv_from_plt_mat(plt_mat: np.ndarray, tstep: int, frame_csvs_dir: str) -> None:
    out_path = os.path.join(frame_csvs_dir, f'{tstep:04d}.csv')
    np.savetxt(out_path, plt_mat, delimiter=',', fmt='%.0f')

def save_frame_state_npy(plt_mat: np.ndarray, tstep: int, frame_state_dir: str) -> None:
    os.makedirs(frame_state_dir, exist_ok=True)
    state = np.rint(plt_mat).astype(_FRAME_STATE_DTYPE, copy=False)
    np.save(os.path.join(frame_state_dir, f'state_{tstep:04d}.npy'), state)

def _get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return 'ffmpeg'

def assemble_video(frames_dir: str, output_dir: str, fps: int=4, tag: str='') -> None:
    ffmpeg = _get_ffmpeg_exe()
    pattern = os.path.join(frames_dir, '%04d.png')
    suffix = f'_{tag}' if tag else ''
    mp4_path = os.path.join(output_dir, f'simulation{suffix}.mp4')
    gif_path = os.path.join(output_dir, f'simulation{suffix}.gif')
    try:
        subprocess.run([ffmpeg, '-y', '-framerate', str(fps), '-i', pattern, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', mp4_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=3600)
        print(f'MP4 written to {mp4_path}')
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        _log_ffmpeg_error('MP4', exc)
        _assemble_video_imageio(frames_dir, mp4_path, fps)
    try:
        subprocess.run([ffmpeg, '-y', '-framerate', str(fps), '-i', pattern, '-vf', 'scale=640:-1:flags=lanczos', gif_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=3600)
        print(f'GIF written to {gif_path}')
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        _log_ffmpeg_error('GIF', exc)
        _assemble_gif_imageio(frames_dir, gif_path, fps)

def _log_ffmpeg_error(label: str, exc: Exception) -> None:
    stderr_text = getattr(exc, 'stderr', b'') or b''
    if isinstance(stderr_text, bytes):
        stderr_text = stderr_text.decode(errors='replace')
    print(f'ffmpeg {label} failed ({type(exc).__name__}): {stderr_text[-400:].strip()}')
    print(f'Trying imageio fallback for {label} …')

def _assemble_video_imageio(frames_dir: str, out_path: str, fps: int) -> None:
    try:
        import imageio.v3 as iio
        frames = sorted((f for f in os.listdir(frames_dir) if f.endswith('.png')))
        if not frames:
            print('No frames found — skipping MP4.')
            return
        writer = iio.imopen(out_path, 'w', plugin='pyav', fps=fps)
        for fn in frames:
            img = iio.imread(os.path.join(frames_dir, fn))
            writer.write(img)
        writer.close()
        print(f'MP4 (imageio) written to {out_path}')
    except Exception as exc:
        print(f'imageio MP4 fallback also failed: {exc}')

def _assemble_gif_imageio(frames_dir: str, out_path: str, fps: int) -> None:
    try:
        import imageio.v2 as iio
        frames = sorted((f for f in os.listdir(frames_dir) if f.endswith('.png')))
        if not frames:
            print('No frames found — skipping GIF.')
            return
        duration_ms = int(1000.0 / fps)
        writer = iio.get_writer(out_path, format='GIF', mode='I', duration=duration_ms, loop=0)
        for fn in frames:
            img = iio.imread(os.path.join(frames_dir, fn))
            writer.append_data(img)
        writer.close()
        print(f'GIF (imageio) written to {out_path}')
    except Exception as exc:
        print(f'imageio GIF fallback also failed: {exc}')

def plot_pixel_ignitions(output_dir: str, maxstep: int, time_labels: List[str], tick_positions: List[int], ig_known: np.ndarray, ig_dev: np.ndarray, ig_rad: np.ndarray, ig_brand: np.ndarray, ig_total: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))
    x = np.arange(1, maxstep + 1)
    ax.plot(x, np.cumsum(ig_known), lw=2, color=(1, 0.7, 0), label='Known')
    ax.plot(x, np.cumsum(ig_dev), lw=2, color='g', label='Developed')
    ax.plot(x, np.cumsum(ig_rad), lw=2, color='r', label='Radiation')
    ax.plot(x, np.cumsum(ig_brand), lw=2, color='k', label='Branding')
    ax.plot(x, ig_total, lw=2, color='b', label='Total')
    ax.legend(loc='upper left')
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(time_labels, fontsize=12)
    ax.set_xlabel('Time', fontsize=18)
    ax.set_ylabel('Number of ignited pixels', fontsize=18)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'ig_pixel.png'), dpi=150)
    plt.close(fig)

def plot_structure_ignitions(output_dir: str, maxstep: int, time_labels: List[str], tick_positions: List[int], house_ig_known: np.ndarray, house_ig_rad: np.ndarray, house_ig_brand: np.ndarray, house_ig_total: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))
    x = np.arange(1, maxstep + 1)
    ax.plot(x, np.cumsum(house_ig_known), lw=2, color=(1, 0.7, 0), label='Known')
    ax.plot(x, np.cumsum(house_ig_rad), lw=2, color='r', label='Radiation')
    ax.plot(x, np.cumsum(house_ig_brand), lw=2, color='k', label='Branding')
    ax.plot(x, house_ig_total, lw=2, color='b', label='Total')
    ax.legend(loc='upper left')
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(time_labels, fontsize=12)
    ax.set_xlabel('Time', fontsize=18)
    ax.set_ylabel('Number of ignited structures', fontsize=18)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'ig_structure.png'), dpi=150)
    plt.close(fig)
