#!/usr/bin/env python3
"""Unified SWUIFT comparison suite with smoke and full presets."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

import paths
from orchestrator import (
    APP_PROJECT,
    CLI_PROJECT,
    DEFAULTS,
    EXTRACTED_FILES,
    FRAME_STATE_CATEGORIES,
    FRAME_STATE_DTYPE,
    PROJECT_DIR,
    WORKSPACE,
    _build_frame_state,
    _load_csv_matrix,
    _save_normalized_state,
    _state_files,
    _write_state_manifest,
    detect_matlab,
    ensure_matlab_baseline,
    normalize_stage_outputs,
    prepare_matlab_stage,
    write_frame_state_comparison,
)
from paths import (
    DEFAULT_MATLAB_BASELINE_RUN,
    STAGE_APP,
    STAGE_CLI,
    STAGE_MATLAB,
    add_data_path_arguments,
    apply_data_path_arguments,
    data_roots_summary,
    resolve_stage_dir,
    verify_data_paths,
)
from stitch_video import resolve_frame_sources, stitch_panel_video
from video import recommended_frame_dpi


STAGE_CHOICES = ["matlab_baseline", "app", "cli"]
RUNTIME_RE = re.compile(r"Runtime:\s*([\d.]+)\s*minutes", re.IGNORECASE)


@dataclass(frozen=True)
class PresetConfig:
    name: str
    steps: int | None
    default_stages: tuple[str, ...]
    run_root_name: str
    smoke: bool


@dataclass
class StageRunMetrics:
    wall_seconds: float
    return_code: int
    log_runtime_minutes: float | None = None
    source: str | None = None


PRESETS: dict[str, PresetConfig] = {
    "smoke10": PresetConfig(
        name="smoke10",
        steps=10,
        default_stages=("app",),
        run_root_name="smoke_10",
        smoke=True,
    ),
    "smoke15": PresetConfig(
        name="smoke15",
        steps=15,
        default_stages=("app", "cli"),
        run_root_name="smoke_15",
        smoke=True,
    ),
    "full": PresetConfig(
        name="full",
        steps=None,
        default_stages=("matlab_baseline", "app", "cli"),
        run_root_name="full",
        smoke=False,
    ),
}


def smoke_end_time(steps: int) -> str:
    start = dt.datetime.strptime(DEFAULTS["t_start"], "%Y-%m-%d %H:%M")
    end = start + dt.timedelta(minutes=(steps - 1) * 5)
    return end.strftime("%Y-%m-%d %H:%M")


def _parse_runtime_minutes(text: str) -> float | None:
    match = RUNTIME_RE.search(text)
    return float(match.group(1)) if match else None


def _find_log_runtime(stage: str, run_root: Path) -> float | None:
    candidates: list[Path] = []
    if stage == "matlab":
        matlab_stage = resolve_stage_dir(run_root, STAGE_MATLAB)
        candidates.extend(
            [
                matlab_stage / "work" / "outs" / "run_log.txt",
                matlab_stage / "work" / "matlab_console.log",
            ]
        )
    elif stage == "app":
        app_stage = resolve_stage_dir(run_root, STAGE_APP)
        candidates.append(app_stage / "outputs" / "run_log.txt")
    elif stage == "cli":
        cli_stage = resolve_stage_dir(run_root, STAGE_CLI)
        for run_dir in sorted(cli_stage.glob("cli_default_*")):
            candidates.append(run_dir / "run_log.txt")
    for path in candidates:
        if path.exists():
            runtime = _parse_runtime_minutes(path.read_text(encoding="utf-8", errors="replace"))
            if runtime is not None:
                return runtime
    return None


def _run_command(
    label: str,
    cwd: Path,
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
) -> StageRunMetrics:
    print(f"\n[{label}] cwd={cwd}")
    print(f"[{label}] {' '.join(cmd)}")
    start = dt.datetime.now()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    captured: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        elapsed = dt.datetime.now() - start
        print(f"[{label} +{str(elapsed).split('.')[0]}] {line}", end="")
        captured.append(line)
    rc = proc.wait()
    wall_seconds = (dt.datetime.now() - start).total_seconds()
    output = "".join(captured)
    metrics = StageRunMetrics(
        wall_seconds=wall_seconds,
        return_code=rc,
        log_runtime_minutes=_parse_runtime_minutes(output),
    )
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)
    return metrics


def _format_duration(seconds: float) -> str:
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _print_runtime_table(runtime_comparison: dict[str, Any], *, steps: int | None) -> None:
    label = f"Runtime comparison ({steps} steps):" if steps is not None else "Runtime comparison:"
    print(f"\n{label}")
    print(f"{'Stage':<8} {'Wall clock':<14} {'Reported'}")
    print("-" * 44)
    for stage, payload in runtime_comparison.items():
        wall = _format_duration(payload["wall_seconds"])
        reported = payload.get("reported_minutes")
        reported_text = f"{reported:.1f} min" if reported is not None else "n/a"
        print(f"{stage:<8} {wall:<14} {reported_text}")


def _app_runner_script(
    run_root: Path,
    *,
    steps: int | None,
    smoke: bool,
    frame_dpi: int,
    save_frames: bool,
) -> tuple[Path, list[str]]:
    stage_dir = run_root / STAGE_APP
    output_dir = stage_dir / "outputs"
    stage_dir.mkdir(parents=True, exist_ok=True)
    runner_path = stage_dir / ("run_app_smoke.py" if smoke else "run_app_full.py")
    app_workers = max(1, min(8, (os.cpu_count() or 2) - 1))
    maxstep_line = f"        maxstep={steps},\n" if steps is not None else ""
    preload_wind = "False" if smoke else "True"
    make_video = "False" if smoke else "True"
    dump_radiation = "False" if smoke else "True"
    dump_spotting = "False" if smoke else "True"
    io_workers = "1" if smoke else "max(1, min(8, (os.cpu_count() or 2) - 1))"
    script = f"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SWUIFT_APP_RADIATION_WORKERS", {str(app_workers)!r})
sys.path.insert(0, {str(APP_PROJECT)!r})

from swuift.config import build_config
from swuift.data_loader import load_all_extracted
from swuift.simulation import run_simulation

data = load_all_extracted(
    wildland_fire_matrix_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["fire_prog"])!r},
    domain_matrix_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["domains"])!r},
    binary_cover_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["landcover"])!r},
    homes_matrix_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["homes"])!r},
    latitude_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["lat"])!r},
    longitude_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["lon"])!r},
    radiation_matrix_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["harden_rad_map"])!r},
    spotting_matrix_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["harden_spo_map"])!r},
    water_matrix_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["water"])!r},
    wind_file={str(paths.EXTRACTED_DATA / EXTRACTED_FILES["wind"])!r},
    preload_wind={preload_wind},
)
try:
    cfg = build_config(
        None,
        grid_size={DEFAULTS["grid_size"]},
{maxstep_line}        hardening_rad={DEFAULTS["harden_rad"]},
        hardening_spo={DEFAULTS["harden_spo"]},
        rad_energy_ig={DEFAULTS["rad_ig_thresh"]},
        rad_rf={DEFAULTS["rad_decay"]},
        fb_wind_coef={DEFAULTS["brand_wind_coef"]},
        fb_wind_sd={DEFAULTS["brand_wind_sd"]},
        fb_wind_sd_transverse={DEFAULTS["brand_wind_sd_lat"]},
        seed_hardening={DEFAULTS["seed_harden"]},
        seed_spread={DEFAULTS["seed_spread"]},
    )
    run_simulation(
        cfg=cfg,
        data=data,
        output_dir={str(output_dir)!r},
        dpi=150,
        dpi_hires={frame_dpi},
        make_video={make_video},
        dump_interval=1,
        dump_csv=True,
        dump_radiation_csv={dump_radiation},
        dump_spotting_csv={dump_spotting},
        save_frames={save_frames},
        io_workers={io_workers},
    )
finally:
    data.close()
print("APP_OUTPUT_DIR=" + {str(output_dir)!r})
"""
    runner_path.write_text(script.strip() + "\n", encoding="utf-8")
    return stage_dir, [sys.executable, str(runner_path)]


def _cli_command(
    project: Path,
    output_dir: Path,
    job_name: str,
    *,
    t_end: str,
    smoke: bool,
    frame_dpi: int,
    save_frames: bool,
) -> tuple[Path, list[str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "swuift.cli",
        "--job-name",
        job_name,
        "--fire-prog",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["fire_prog"]),
        "--domains",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["domains"]),
        "--landcover",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["landcover"]),
        "--homes",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["homes"]),
        "--lat",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["lat"]),
        "--lon",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["lon"]),
        "--harden-rad-map",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["harden_rad_map"]),
        "--harden-spo-map",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["harden_spo_map"]),
        "--water",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["water"]),
        "--wind",
        str(paths.EXTRACTED_DATA / EXTRACTED_FILES["wind"]),
        "--grid-size",
        str(DEFAULTS["grid_size"]),
        "--t-start",
        DEFAULTS["t_start"],
        "--t-end",
        t_end,
        "--harden-rad",
        str(DEFAULTS["harden_rad"]),
        "--harden-spo",
        str(DEFAULTS["harden_spo"]),
        "--rad-ig-thresh",
        str(DEFAULTS["rad_ig_thresh"]),
        "--rad-decay",
        str(DEFAULTS["rad_decay"]),
        "--brand-wind-coef",
        str(DEFAULTS["brand_wind_coef"]),
        "--brand-wind-sd",
        str(DEFAULTS["brand_wind_sd"]),
        "--brand-wind-sd-lat",
        str(DEFAULTS["brand_wind_sd_lat"]),
        "--seed-harden",
        str(DEFAULTS["seed_harden"]),
        "--seed-spread",
        str(DEFAULTS["seed_spread"]),
        "--output-dir",
        str(output_dir),
        "--frame-dpi",
        str(frame_dpi),
        "--dump-every",
        "1",
        "--dump-csv",
    ]
    if smoke:
        cmd.extend(
            [
                "--lazy-wind",
                "--no-out-frames",
                "--no-out-video",
                "--no-out-gif",
                "--no-out-ig-plots",
                "--out-fire-csv",
                "--out-buildings-csv",
                "--no-out-rad-steps",
                "--no-out-spo-steps",
            ]
        )
    else:
        cmd.extend(
            [
                "--no-lazy-wind",
                "--out-frames" if save_frames else "--no-out-frames",
                "--out-video",
                "--out-gif",
                "--out-ig-plots",
                "--out-fire-csv",
                "--out-buildings-csv",
                "--out-rad-steps",
                "--out-spo-steps",
            ]
        )
    return project, cmd


def _latest_cli_run(stage_dir: Path, job_prefix: str) -> Path:
    run_dirs = sorted(stage_dir.glob(f"{job_prefix}_*"))
    if not run_dirs:
        raise FileNotFoundError(f"No {job_prefix!r} run directory found under {stage_dir}")
    return run_dirs[-1]


def _normalize_timestep_dir(stage: str, timesteps_dir: Path, out_dir: Path, *, steps: int | None) -> Path:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import scipy.io
    except ImportError as exc:
        raise RuntimeError("scipy is required to normalize timestep frame states") from exc

    binary_cover = scipy.io.loadmat(paths.EXTRACTED_DATA / EXTRACTED_FILES["landcover"], squeeze_me=True)["binary_cover"]
    water = scipy.io.loadmat(paths.EXTRACTED_DATA / EXTRACTED_FILES["water"], squeeze_me=True)["water"]
    fstep = int(22 / 5.0) + 1
    lstep = int(177 / 5.0) + 1

    extras: set[int] = set()
    count = 0
    for step_dir in sorted(timesteps_dir.glob("t*")):
        step_match = re.search(r"(\d+)", step_dir.name)
        if not step_match:
            continue
        step = int(step_match.group(1))
        if steps is not None and step > steps:
            continue
        fire_path = step_dir / "fire.csv"
        ignition_path = step_dir / "ignition.csv"
        if not fire_path.exists() or not ignition_path.exists():
            continue
        state = _build_frame_state(
            binary_cover=binary_cover,
            ignition=_load_csv_matrix(ignition_path),
            fire=_load_csv_matrix(fire_path),
            fstep=fstep,
            lstep=lstep,
            water=water,
        )
        extras.update(_save_normalized_state(state, out_dir / f"state_{step:04d}.npy"))
        count += 1
    manifest_extras: dict[str, Any] = {"extra_categories_seen": sorted(extras)}
    if steps is not None:
        manifest_extras["smoke_steps"] = steps
    _write_state_manifest(
        out_dir,
        stage=stage,
        source=str(timesteps_dir),
        count=count,
        extras=manifest_extras,
    )
    return out_dir


def _normalize_app(run_root: Path, *, steps: int | None) -> Path:
    app_stage = resolve_stage_dir(run_root, STAGE_APP)
    frame_state_dir = app_stage / "outputs" / "frame_state"
    timesteps_dir = app_stage / "outputs" / "timesteps"
    out_dir = app_stage / "normalized_frame_state"
    if _state_files(frame_state_dir):
        if out_dir.exists():
            shutil.rmtree(out_dir)
        shutil.copytree(frame_state_dir, out_dir)
        manifest_extras: dict[str, Any] = {"source_kind": "frame_state"}
        if steps is not None:
            manifest_extras["smoke_steps"] = steps
        _write_state_manifest(
            out_dir,
            stage="app",
            source=str(frame_state_dir),
            count=len(_state_files(out_dir)),
            extras=manifest_extras,
        )
        return out_dir
    return _normalize_timestep_dir("app", timesteps_dir, out_dir, steps=steps)


def _normalize_cli(run_root: Path, job_prefix: str, *, steps: int | None) -> Path:
    stage_dir = resolve_stage_dir(run_root, STAGE_CLI)
    cli_run_dir = _latest_cli_run(stage_dir, job_prefix)
    return _normalize_timestep_dir(
        STAGE_CLI,
        cli_run_dir / "timesteps",
        stage_dir / "normalized_frame_state",
        steps=steps,
    )


def _matlab_baseline_state_dir(matlab_run_root: Path) -> Path:
    return resolve_stage_dir(matlab_run_root, STAGE_MATLAB) / "normalized_frame_state"


def _copy_matlab_baseline(run_root: Path, matlab_run_root: Path, *, steps: int | None) -> Path:
    source = _matlab_baseline_state_dir(matlab_run_root)
    if not _state_files(source):
        raise FileNotFoundError(f"Missing MATLAB normalized states: {source}")
    out_dir = resolve_stage_dir(run_root, STAGE_MATLAB) / "normalized_frame_state"
    out_dir.mkdir(parents=True, exist_ok=True)
    source_files = _state_files(source)
    selected = sorted(source_files) if steps is None else list(range(1, steps + 1))
    for step in selected:
        shutil.copy2(source / f"state_{step:04d}.npy", out_dir / f"state_{step:04d}.npy")
    manifest_extras: dict[str, Any] = {"matlab_run_root": str(matlab_run_root), "source": "baseline_copy"}
    if steps is not None:
        manifest_extras["smoke_steps"] = steps
    _write_state_manifest(
        out_dir,
        stage="matlab",
        source=str(source),
        count=len(selected),
        extras=manifest_extras,
    )
    return out_dir


def _compare_to_matlab(
    matlab_dir: Path,
    candidate_dirs: dict[str, Path],
    *,
    expected_steps: int | None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "expected_steps": expected_steps,
        "matlab": str(matlab_dir),
        "candidates": {},
    }
    matlab_files = _state_files(matlab_dir)
    for name, candidate_dir in candidate_dirs.items():
        candidate_files = _state_files(candidate_dir)
        common_steps = sorted(set(matlab_files) & set(candidate_files))
        per_step = []
        first_difference = None
        max_different_cells = 0
        for step in common_steps:
            a = np.load(matlab_files[step])
            b = np.load(candidate_files[step])
            if a.dtype != np.dtype(FRAME_STATE_DTYPE) or b.dtype != np.dtype(FRAME_STATE_DTYPE):
                raise ValueError(f"{name} step {step}: expected {FRAME_STATE_DTYPE} normalized dtype")
            if a.shape != b.shape:
                raise ValueError(f"{name} step {step}: shape mismatch {a.shape} != {b.shape}")
            mask = np.isin(a, FRAME_STATE_CATEGORIES) & np.isin(b, FRAME_STATE_CATEGORIES)
            diff = (a != b) & mask
            diff_cells = int(diff.sum())
            comparable_cells = int(mask.sum())
            if diff_cells and first_difference is None:
                first_difference = step
            max_different_cells = max(max_different_cells, diff_cells)
            per_step.append(
                {
                    "step": step,
                    "different_cells": diff_cells,
                    "comparable_cells": comparable_cells,
                    "different_fraction": diff_cells / comparable_cells if comparable_cells else None,
                }
            )
        matches = first_difference is None and (
            expected_steps is None or len(common_steps) == expected_steps
        )
        summary["candidates"][name] = {
            "path": str(candidate_dir),
            "common_step_count": len(common_steps),
            "first_difference_step": first_difference,
            "max_different_cells": max_different_cells,
            "matches_all_common_steps": matches,
            "per_step": per_step,
        }
    return summary


def _print_summary(summary: dict[str, Any], *, title: str) -> None:
    print(f"\n{title}")
    print("-" * 80)
    for name, payload in summary["candidates"].items():
        status = "MATCH" if payload["matches_all_common_steps"] else "DIFF"
        first = payload["first_difference_step"]
        max_diff = payload["max_different_cells"]
        print(
            f"{name:12s} {status:5s} common={payload['common_step_count']:3d} "
            f"first_diff={first} max_diff_cells={max_diff}"
        )


def _stage_specs(stages: list[str]) -> dict[str, tuple[Path, Path, str]]:
    mapping = {
        "app": (APP_PROJECT, Path(STAGE_APP), "app_default"),
        "cli": (CLI_PROJECT, Path(STAGE_CLI), "cli_default"),
    }
    return {stage: mapping[stage] for stage in stages if stage in mapping}


def _metrics_to_json(metrics: StageRunMetrics) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "wall_seconds": metrics.wall_seconds,
        "return_code": metrics.return_code,
    }
    if metrics.log_runtime_minutes is not None:
        payload["reported_minutes"] = metrics.log_runtime_minutes
    if metrics.source is not None:
        payload["source"] = metrics.source
    return payload


def run_preset(
    preset: PresetConfig,
    *,
    run_root: Path,
    matlab_run_root: Path,
    stages: list[str],
    reuse: bool,
    stitch_1080p: bool,
    video_height: int,
    video_fps: int,
) -> dict[str, Any]:
    steps = preset.steps
    t_end = smoke_end_time(steps) if steps is not None else DEFAULTS["t_end"]
    run_stages = [stage for stage in stages if stage != "matlab_baseline"]
    commands: dict[str, dict[str, Any]] = {}
    runtime_metrics: dict[str, StageRunMetrics] = {}

    frame_dpi = recommended_frame_dpi(video_height) if stitch_1080p else (100 if preset.smoke else 600)
    save_frames = stitch_1080p and not preset.smoke

    if not reuse and run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    run_fresh_matlab = (
        not preset.smoke
        and "matlab_baseline" in stages
        and not reuse
        and detect_matlab() is not None
    )

    if run_fresh_matlab:
        cwd, cmd = prepare_matlab_stage(run_root)
        commands["matlab"] = {"cwd": str(cwd), "argv": cmd}
        runtime_metrics["matlab"] = _run_command("matlab", cwd, cmd)
        runtime_metrics["matlab"].source = "fresh_run"
        normalize_stage_outputs("matlab", run_root)
        matlab_dir = resolve_stage_dir(run_root, STAGE_MATLAB) / "normalized_frame_state"
        log_runtime = _find_log_runtime("matlab", run_root)
        if log_runtime is not None:
            runtime_metrics["matlab"].log_runtime_minutes = log_runtime
    elif "matlab_baseline" in stages or run_stages:
        if preset.smoke:
            matlab_dir = _copy_matlab_baseline(run_root, matlab_run_root, steps=steps)
        else:
            try:
                matlab_dir = ensure_matlab_baseline(run_root, matlab_run_root)
                runtime_metrics["matlab"] = StageRunMetrics(
                    wall_seconds=0.0,
                    return_code=0,
                    log_runtime_minutes=_find_log_runtime("matlab", matlab_run_root),
                    source="baseline_copy",
                )
            except FileNotFoundError:
                print("Warning: MATLAB baseline unavailable; attempting fresh MATLAB run.")
                if detect_matlab() is None:
                    raise
                cwd, cmd = prepare_matlab_stage(run_root)
                commands["matlab"] = {"cwd": str(cwd), "argv": cmd}
                runtime_metrics["matlab"] = _run_command("matlab", cwd, cmd)
                runtime_metrics["matlab"].source = "fresh_run"
                normalize_stage_outputs("matlab", run_root)
                matlab_dir = resolve_stage_dir(run_root, STAGE_MATLAB) / "normalized_frame_state"
                log_runtime = _find_log_runtime("matlab", run_root)
                if log_runtime is not None:
                    runtime_metrics["matlab"].log_runtime_minutes = log_runtime

    if "app" in run_stages and not reuse:
        cwd, cmd = _app_runner_script(
            run_root,
            steps=steps,
            smoke=preset.smoke,
            frame_dpi=frame_dpi,
            save_frames=save_frames,
        )
        commands["app"] = {"cwd": str(cwd), "argv": cmd}
        runtime_metrics["app"] = _run_command("app", cwd, cmd)
        log_runtime = _find_log_runtime("app", run_root)
        if log_runtime is not None:
            runtime_metrics["app"].log_runtime_minutes = log_runtime

    for stage, (project, rel_dir, job_name) in _stage_specs(run_stages).items():
        if stage == "app" or reuse:
            continue
        output_dir = run_root / rel_dir
        cwd, cmd = _cli_command(
            project,
            output_dir,
            job_name,
            t_end=t_end,
            smoke=preset.smoke,
            frame_dpi=frame_dpi,
            save_frames=save_frames,
        )
        commands[stage] = {"cwd": str(cwd), "argv": cmd}
        runtime_metrics[stage] = _run_command(stage, cwd, cmd)
        log_runtime = _find_log_runtime(stage, run_root)
        if log_runtime is not None:
            runtime_metrics[stage].log_runtime_minutes = log_runtime

    candidate_dirs: dict[str, Path] = {}
    if "app" in run_stages:
        candidate_dirs["app"] = _normalize_app(run_root, steps=steps)
    if "cli" in run_stages:
        candidate_dirs["cli"] = _normalize_cli(run_root, "cli_default", steps=steps)

    summary = _compare_to_matlab(matlab_dir, candidate_dirs, expected_steps=steps)
    summary.update(
        {
            "preset": preset.name,
            "run_root": str(run_root),
            "matlab_run_root": str(matlab_run_root),
            "commands": commands,
            "stages": stages,
            "time_window": {"start": DEFAULTS["t_start"], "end": t_end},
            "data_roots": data_roots_summary(),
        }
    )

    if runtime_metrics:
        summary["runtime_comparison"] = {
            stage: _metrics_to_json(metrics) for stage, metrics in runtime_metrics.items()
        }

    if stitch_1080p and not preset.smoke:
        summary["video"] = {"target_height": video_height, "frame_dpi": frame_dpi}
        try:
            panels = resolve_frame_sources(run_root, steps=steps)
            video_path = run_root / "comparison_1080p.mp4"
            stitch_panel_video(panels, video_path, target_height=video_height, fps=video_fps)
            summary["video"]["path"] = str(video_path)
            print(f"\nWrote {video_path}")
        except (FileNotFoundError, RuntimeError) as exc:
            summary["video"]["error"] = str(exc)
            print(f"\nWarning: could not stitch 1080p video: {exc}")

    out_name = f"{preset.name}_comparison.json"
    out_path = run_root / out_name
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _print_summary(summary, title=f"{preset.name} MATLAB baseline comparison")
    print(f"\nWrote {out_path}")

    if summary.get("runtime_comparison"):
        _print_runtime_table(summary["runtime_comparison"], steps=steps)

    if not preset.smoke and candidate_dirs:
        write_frame_state_comparison(run_root, matlab_run_root)
        print(f"Wrote {run_root / 'frame_state_comparison.json'}")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run standardized SWUIFT comparison presets.")
    add_data_path_arguments(parser)
    parser.add_argument(
        "--preset",
        choices=[*PRESETS.keys(), "all"],
        required=True,
        help="Comparison preset: smoke10, smoke15, full, or all (smoke10 then smoke15).",
    )
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=STAGE_CHOICES,
        help="Stages to run. Defaults depend on the selected preset.",
    )
    parser.add_argument("--run-root", type=Path, help="Output directory for this comparison run.")
    parser.add_argument(
        "--matlab-baseline-run-root",
        type=Path,
        default=DEFAULT_MATLAB_BASELINE_RUN,
        help="Existing MATLAB baseline run to compare against.",
    )
    parser.add_argument("--reuse", action="store_true", help="Reuse existing outputs under --run-root.")
    parser.add_argument(
        "--stitch-1080p",
        action="store_true",
        help="Build side-by-side MATLAB|APP|CLI MP4 at 1080p panel height after the run.",
    )
    parser.add_argument(
        "--no-stitch",
        action="store_true",
        help="Disable automatic 1080p stitching for the full preset.",
    )
    parser.add_argument(
        "--video-height",
        type=int,
        default=1080,
        help="Target panel height for stitched comparison video (default: 1080).",
    )
    parser.add_argument(
        "--video-fps",
        type=int,
        default=4,
        help="FPS for stitched comparison video (default: 4).",
    )
    args = parser.parse_args(argv)
    apply_data_path_arguments(args)
    verify_data_paths()
    print("Data roots:", json.dumps(data_roots_summary(), indent=2))

    matlab_run_root = args.matlab_baseline_run_root.resolve()
    preset_names = ["smoke10", "smoke15"] if args.preset == "all" else [args.preset]
    exit_code = 0

    for preset_name in preset_names:
        preset = PRESETS[preset_name]
        stages = args.stages or list(preset.default_stages)
        if "matlab_baseline" not in stages:
            stages = ["matlab_baseline", *stages]
        stitch_1080p = args.stitch_1080p or (preset.name == "full" and not args.no_stitch)
        if args.run_root and len(preset_names) > 1:
            run_root = args.run_root.resolve() / preset.run_root_name
        elif args.run_root:
            run_root = args.run_root.resolve()
        else:
            if preset.smoke:
                run_root = PROJECT_DIR / "runs" / preset.run_root_name
            else:
                timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                run_root = PROJECT_DIR / "runs" / f"{preset.run_root_name}_{timestamp}"

        summary = run_preset(
            preset,
            run_root=run_root,
            matlab_run_root=matlab_run_root,
            stages=stages,
            reuse=args.reuse,
            stitch_1080p=stitch_1080p and not preset.smoke,
            video_height=args.video_height,
            video_fps=args.video_fps,
        )
        if any(not payload["matches_all_common_steps"] for payload in summary["candidates"].values()):
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
