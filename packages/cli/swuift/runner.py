"""Single-job execution runner and run metadata writer."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any

from .config import SWUIFTConfig, build_config
from .data_loader import SWUIFTData, load_all_extracted
from .job import JobSpec, validate_output_dir
from .logger import tee_run_output
from .simulation import run_simulation


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_job_name(name: str) -> str:
    keep = []
    for ch in name.strip():
        keep.append(ch if ch.isalnum() or ch in ("-", "_") else "_")
    return "".join(keep) or "job"


def _prepare_run_dir(base_output_dir: str, job_name: str) -> str:
    run_id = f"{_safe_job_name(job_name)}_{_timestamp()}"
    run_dir = os.path.join(base_output_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _jsonable(value: Any) -> Any:
    """Recursively convert values to JSON-serializable representations."""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _write_run_params(
    *,
    output_dir: str,
    job: JobSpec,
    cfg: SWUIFTConfig,
    command_line: str,
    start_ts: datetime,
    end_ts: datetime,
    elapsed_s: float,
    data: SWUIFTData,
) -> None:
    payload = {
        "job_name": job.name,
        "command_line": command_line,
        "started_at": start_ts.isoformat(),
        "ended_at": end_ts.isoformat(),
        "elapsed_seconds": elapsed_s,
        "input_files": {
            "fire_prog": job.fire_prog,
            "domains": job.domains,
            "landcover": job.landcover,
            "homes": job.homes,
            "lat": job.lat,
            "lon": job.lon,
            "harden_rad_map": job.harden_rad_map,
            "harden_spo_map": job.harden_spo_map,
            "water": job.water,
            "wind": job.wind,
        },
        "config": {
            "grid_size": cfg.grid_size,
            "t_start": cfg.t_start.isoformat(sep=" "),
            "t_end": cfg.t_end.isoformat(sep=" "),
            "max_steps": cfg.maxstep,
            "harden_rad": cfg.harden_rad,
            "harden_spo": cfg.harden_spo,
            "rad_ig_thresh": cfg.rad_ig_thresh,
            "rad_decay": cfg.rad_decay,
            "brand_wind_coef": cfg.brand_wind_coef,
            "brand_wind_sd": cfg.brand_wind_sd,
            "brand_wind_sd_lat": cfg.brand_wind_sd_lat,
            "seed_harden": cfg.seed_harden,
            "seed_spread": cfg.seed_spread,
            "t_step_min": cfg.t_step_min,
            "fstep": cfg.fstep,
            "lstep": cfg.lstep,
        },
        "outputs": {
            "frame_dpi": job.frame_dpi,
            "dump_every": job.dump_every,
            "dump_csv": job.dump_csv,
            "out_frames": job.out_frames,
            "out_video": job.out_video,
            "out_gif": job.out_gif,
            "out_ig_plots": job.out_ig_plots,
            "out_fire_csv": job.out_fire_csv,
            "out_buildings_csv": job.out_buildings_csv,
            "out_rad_steps": job.out_rad_steps,
            "out_spo_steps": job.out_spo_steps,
        },
        "grid_shape": {"rows": data.rows, "cols": data.cols},
        "job_spec": _jsonable(asdict(job)),
    }
    out_path = os.path.join(output_dir, "run_params.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def run_single(job: JobSpec, *, command_line: str) -> str:
    """Run one job and return the run directory path."""
    if (job.out_video or job.out_gif) and not job.out_frames:
        raise ValueError(
            f"Job {job.name!r}: out_frames must be true when out_video/out_gif is enabled."
        )

    safe_output_dir = validate_output_dir(job.output_dir, job.name)
    run_dir = _prepare_run_dir(safe_output_dir, job.name)
    with tee_run_output(run_dir, command_line):
        print(f"Starting job: {job.name}")
        print(f"Run directory: {run_dir}")
        start_dt = datetime.now()
        t0 = time.time()

        data = load_all_extracted(
            wildland_fire_matrix_file=job.fire_prog,
            domain_matrix_file=job.domains,
            binary_cover_file=job.landcover,
            homes_matrix_file=job.homes,
            latitude_file=job.lat,
            longitude_file=job.lon,
            radiation_matrix_file=job.harden_rad_map,
            spotting_matrix_file=job.harden_spo_map,
            water_matrix_file=job.water,
            wind_file=job.wind,
            preload_wind=not job.lazy_wind,
        )
        cfg = build_config(
            grid_size=job.grid_size,
            t_start=job.t_start,
            t_end=job.t_end,
            harden_rad=job.harden_rad,
            harden_spo=job.harden_spo,
            rad_ig_thresh=job.rad_ig_thresh,
            rad_decay=job.rad_decay,
            brand_wind_coef=job.brand_wind_coef,
            brand_wind_sd=job.brand_wind_sd,
            brand_wind_sd_lat=job.brand_wind_sd_lat,
            seed_harden=job.seed_harden,
            seed_spread=job.seed_spread,
        )

        try:
            run_simulation(
                cfg=cfg,
                data=data,
                output_dir=run_dir,
                frame_dpi=job.frame_dpi,
                dump_every=job.dump_every,
                dump_csv=job.dump_csv,
                out_frames=job.out_frames,
                out_video=job.out_video,
                out_gif=job.out_gif,
                out_ig_plots=job.out_ig_plots,
                out_fire_csv=job.out_fire_csv,
                out_buildings_csv=job.out_buildings_csv,
                out_rad_steps=job.out_rad_steps,
                out_spo_steps=job.out_spo_steps,
            )
        finally:
            data.close()

        elapsed_s = time.time() - t0
        end_dt = datetime.now()
        _write_run_params(
            output_dir=run_dir,
            job=job,
            cfg=cfg,
            command_line=command_line,
            start_ts=start_dt,
            end_ts=end_dt,
            elapsed_s=elapsed_s,
            data=data,
        )
        print(f"Completed job: {job.name} in {elapsed_s:.2f}s")
    return run_dir

