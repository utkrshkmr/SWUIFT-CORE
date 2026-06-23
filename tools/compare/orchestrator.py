#!/usr/bin/env python3
"""Run the three SWUIFT reference implementations in sequence.

This project intentionally only orchestrates runs and records enough metadata
for later comparison. Numerical comparison is planned in COMPARISON_PLAN.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np


import paths
from paths import (
    APP_PROJECT,
    CLI_PROJECT,
    DEFAULT_MATLAB_BASELINE_RUN,
    LEGACY_STAGE_APP,
    LEGACY_STAGE_CLI,
    LEGACY_STAGE_MATLAB,
    MATLAB_PROJECT,
    PROJECT_DIR,
    STAGE_APP,
    STAGE_CLI,
    STAGE_MATLAB,
    WORKSPACE,
    add_data_path_arguments,
    apply_data_path_arguments,
    resolve_stage_dir,
    verify_data_paths,
)

DEFAULT_RUN_ROOT = PROJECT_DIR / "runs"
FRAME_STATE_DTYPE = np.int16
FRAME_STATE_CATEGORIES = [-5, -4, -2, -1, 0, 1, 2, 3, 4]
FRAME_STATE_LABELS = [
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
FRAME_STATE_COLORS = np.array(
    [
        [0.67, 0.80, 0.91],
        [0.00, 0.30, 0.00],
        [1.00, 1.00, 0.00],
        [0.54, 0.64, 0.48],
        [0.70, 0.70, 0.70],
        [0.44, 0.50, 0.56],
        [1.00, 0.00, 0.00],
        [0.55, 0.13, 0.32],
        [0.00, 0.00, 0.20],
    ]
)


DEFAULTS = {
    "grid_size": 10,
    "t_start": "2025-01-07 18:20",
    "t_end": "2025-01-08 14:20",
    "harden_rad": 70.0,
    "harden_spo": 70.0,
    "rad_ig_thresh": 14000.0,
    "rad_decay": 1.0,
    "brand_wind_coef": 30.0,
    "brand_wind_sd": 0.3,
    "brand_wind_sd_lat": 4.85,
    "seed_harden": 123456,
    "seed_spread": 10,
}

EXTRACTED_FILES = {
    "fire_prog": "wildland_fire_matrix.mat",
    "domains": "domain_matrix.mat",
    "landcover": "binary_cover_landcover.mat",
    "homes": "homes_matrix.mat",
    "lat": "latitude.mat",
    "lon": "longitude.mat",
    "harden_rad_map": "radiation_matrix.mat",
    "harden_spo_map": "spotting_matrix.mat",
    "water": "water_matrix.mat",
    "wind": "wind.mat",
}

MATLAB_DATA_FILES = [
    "default_values.mat",
    "domains_mat.mat",
    "eaton_inputs_all.mat",
    "fire_prog.mat",
    "wind_eaton.mat",
]


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _matlab_vec_to_date(value: Iterable[Any]) -> str:
    parts = [int(float(x)) for x in value]
    return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d} {parts[3]:02d}:{parts[4]:02d}"


def _require_paths() -> None:
    verify_data_paths()
    required = [
        MATLAB_PROJECT / "SWUIFT_V4.m",
        MATLAB_PROJECT / "f_spread.m",
        MATLAB_PROJECT / "f_plots.m",
        paths.MATLAB_DATA,
        paths.EXTRACTED_DATA,
        APP_PROJECT / "swuift",
        CLI_PROJECT / "swuift",
    ]
    missing = [str(path) for path in required if not path.exists()]
    missing += [
        str(paths.MATLAB_DATA / name)
        for name in MATLAB_DATA_FILES
        if not (paths.MATLAB_DATA / name).exists()
    ]
    missing += [
        str(paths.EXTRACTED_DATA / name)
        for name in EXTRACTED_FILES.values()
        if not (paths.EXTRACTED_DATA / name).exists()
    ]
    if missing:
        raise FileNotFoundError("Missing required paths:\n" + "\n".join(missing))


def detect_matlab() -> str | None:
    """Return a usable MATLAB executable path if one can be found."""
    from_path = shutil.which("matlab")
    if from_path:
        return from_path

    candidates = sorted(glob.glob("/Applications/MATLAB_R*.app/bin/matlab"), reverse=True)
    return candidates[0] if candidates else None


def run_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    label: str,
    env: dict[str, str] | None = None,
) -> int:
    """Run a command and stream stdout/stderr with a stage prefix."""
    print(f"\n[{label}] cwd: {cwd}")
    print(f"[{label}] command: {' '.join(cmd)}")
    start = time.time()
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        elapsed = dt.timedelta(seconds=int(time.time() - start))
        print(f"[{label} +{elapsed}] {line}", end="")
    rc = proc.wait()
    elapsed = dt.timedelta(seconds=int(time.time() - start))
    print(f"[{label}] finished rc={rc} elapsed={elapsed}")
    return rc


def check_matlab(matlab_exe: str | None = None) -> bool:
    exe = matlab_exe or detect_matlab()
    if not exe:
        print("MATLAB executable not found on PATH or /Applications/MATLAB_R*.app/bin/matlab")
        return False
    # On this machine -batch may return a silent non-zero status. The older
    # non-desktop invocation prints diagnostics reliably and preserves exit codes.
    cmd = [
        exe,
        "-nodesktop",
        "-nosplash",
        "-r",
        "try, disp('MATLAB_OK'); catch ME, disp(getReport(ME,'extended')); exit(1); end; exit(0);",
    ]
    return run_subprocess(cmd, cwd=WORKSPACE, label="check:matlab") == 0


def collect_default_summary() -> dict[str, dict[str, Any]]:
    """Collect comparable defaults from MATLAB data/script and Python configs."""
    try:
        import scipy.io
    except ImportError as exc:
        raise RuntimeError("Install requirements first: python -m pip install -r requirements.txt") from exc

    mat = scipy.io.loadmat(paths.MATLAB_DATA / "default_values.mat", squeeze_me=True)
    script = (MATLAB_PROJECT / "SWUIFT_V4.m").read_text(encoding="utf-8", errors="replace")

    def scalar(name: str) -> float:
        value = mat[name]
        return float(value.item() if hasattr(value, "item") else value)

    def regex_float(pattern: str, fallback: float | None = None) -> float:
        match = re.search(pattern, script)
        if match:
            return float(match.group(1))
        if fallback is None:
            raise ValueError(f"Could not parse {pattern!r} from SWUIFT_V4.m")
        return fallback

    seeds = re.findall(r"rng\((\d+)\)", script)
    matlab = {
        "grid_size": regex_float(r"grid_size\s*=\s*([0-9.]+)", scalar("grid_size")),
        "t_start": _matlab_vec_to_date(re.search(r"t_start_vec\s*=\s*\[([^\]]+)\]", script).group(1).split(",")),
        "t_end": _matlab_vec_to_date(re.search(r"t_end_vec\s*=\s*\[([^\]]+)\]", script).group(1).split(",")),
        "t_step_min": scalar("t_step_min"),
        "harden_rad": regex_float(r"hardening_level_rad\s*=\s*([0-9.]+)"),
        "harden_spo": regex_float(r"hardening_level_spo\s*=\s*([0-9.]+)"),
        "rad_ig_thresh": scalar("rad_energy_ig"),
        "rad_decay": scalar("rad_rf"),
        "brand_wind_coef": scalar("fb_wind_coef"),
        "brand_wind_sd": scalar("fb_wind_sd"),
        "brand_wind_sd_lat": scalar("fb_wind_sd_transverse"),
        "seed_harden": int(seeds[0]) if seeds else None,
        "seed_spread": int(seeds[1]) if len(seeds) > 1 else None,
    }

    app_cfg = _load_module("swuift_app_config", APP_PROJECT / "swuift" / "config.py")
    cli_cfg = _load_module("swuift_cli_config", CLI_PROJECT / "swuift" / "config.py")

    app = {
        "grid_size": app_cfg.GRID_SIZE,
        "t_start": app_cfg.T_START_DEFAULT.strftime("%Y-%m-%d %H:%M"),
        "t_end": app_cfg.T_END_DEFAULT.strftime("%Y-%m-%d %H:%M"),
        "t_step_min": app_cfg.T_STEP_MIN,
        "harden_rad": app_cfg.HARDENING_RAD_DEFAULT,
        "harden_spo": app_cfg.HARDENING_SPO_DEFAULT,
        "rad_ig_thresh": app_cfg.RAD_ENERGY_IG_DEFAULT,
        "rad_decay": app_cfg.RAD_RF_DEFAULT,
        "brand_wind_coef": app_cfg.FB_WIND_COEF_DEFAULT,
        "brand_wind_sd": app_cfg.FB_WIND_SD_DEFAULT,
        "brand_wind_sd_lat": app_cfg.FB_WIND_SD_TRANSVERSE_DEFAULT,
        "seed_harden": app_cfg.SEED_HARDENING_DEFAULT,
        "seed_spread": app_cfg.SEED_SPREAD_DEFAULT,
    }

    cli = {
        "grid_size": cli_cfg.GRID_SIZE,
        "t_start": cli_cfg.T_START_DEFAULT.strftime("%Y-%m-%d %H:%M"),
        "t_end": cli_cfg.T_END_DEFAULT.strftime("%Y-%m-%d %H:%M"),
        "t_step_min": cli_cfg.T_STEP_MIN,
        "harden_rad": cli_cfg.HARDENING_RAD_DEFAULT,
        "harden_spo": cli_cfg.HARDENING_SPO_DEFAULT,
        "rad_ig_thresh": cli_cfg.RAD_IG_THRESH_DEFAULT,
        "rad_decay": cli_cfg.RAD_DECAY_DEFAULT,
        "brand_wind_coef": cli_cfg.BRAND_WIND_COEF_DEFAULT,
        "brand_wind_sd": cli_cfg.BRAND_WIND_SD_DEFAULT,
        "brand_wind_sd_lat": cli_cfg.BRAND_WIND_SD_LAT_DEFAULT,
        "seed_harden": cli_cfg.SEED_HARDEN_DEFAULT,
        "seed_spread": cli_cfg.SEED_SPREAD_DEFAULT,
    }
    return {"matlab": matlab, "app": app, "cli": cli}


def check_defaults(write_to: Path | None = None) -> bool:
    summary = collect_default_summary()
    keys = list(summary["matlab"].keys())
    print("\nDefault hyperparameter check")
    print("-" * 96)
    print(f"{'key':24} {'matlab':22} {'app':22} {'cli':22} status")
    print("-" * 96)
    ok = True
    for key in keys:
        values = [summary[name].get(key) for name in ("matlab", "app", "cli")]
        if all(isinstance(v, (int, float)) for v in values):
            status = "OK" if max(float(v) for v in values) - min(float(v) for v in values) < 1e-12 else "DIFF"
        else:
            comparable = [str(v) for v in values]
            status = "OK" if len(set(comparable)) == 1 else "DIFF"
        if status != "OK":
            ok = False
        print(f"{key:24} {str(values[0]):22} {str(values[1]):22} {str(values[2]):22} {status}")
    if write_to:
        write_to.parent.mkdir(parents=True, exist_ok=True)
        write_to.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return ok


def patch_matlab_source(source: str) -> str:
    """Make the MATLAB script runnable from a generated work directory on macOS."""
    source = source.replace("\\outs\\", "/outs/")
    source = source.replace(
        "[status ,idx] = intersect(values, unique(plt_mat));",
        "if ~exist([cd '/outs/frame_state_raw'],'dir'), mkdir([cd '/outs/frame_state_raw']); end\n"
        "            writematrix(int16(plt_mat), [cd '/outs/frame_state_raw/' sprintf('%04d.csv', tstep)]);\n"
        "            [status ,idx] = intersect(values, unique(plt_mat));",
    )
    source = source.replace(
        "for tstep=1:maxstep",
        "for tstep=1:maxstep\n    disp(['MATLAB timestep ' num2str(tstep) '/' num2str(maxstep)]);",
    )
    source = source.replace(
        "xlswrite([cd '/outs/zvector.xlsx'],zvector);",
        "writematrix(zvector, [cd '/outs/zvector.csv']);",
    )
    return source


def prepare_matlab_stage(run_root: Path) -> tuple[Path, list[str]]:
    stage_dir = run_root / STAGE_MATLAB
    work_dir = stage_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    for name in paths.MATLAB_DATA_FILES:
        target = work_dir / name
        if target.exists() or target.is_symlink():
            target.unlink()
        target.symlink_to(paths.MATLAB_DATA / name)

    for name in ("f_spread.m", "f_plots.m"):
        text = (MATLAB_PROJECT / name).read_text(encoding="utf-8", errors="replace")
        (work_dir / name).write_text(patch_matlab_source(text), encoding="utf-8")

    main_text = (MATLAB_PROJECT / "SWUIFT_V4.m").read_text(encoding="utf-8", errors="replace")
    (work_dir / "SWUIFT_V4_orchestrated.m").write_text(
        patch_matlab_source(main_text),
        encoding="utf-8",
    )
    command_expr = (
        "try, diary('matlab_console.log'); SWUIFT_V4_orchestrated; diary off; "
        "catch ME, try, diary off; catch, end; disp(getReport(ME,'extended')); exit(1); "
        "end; exit(0);"
    )
    exe = detect_matlab()
    if not exe:
        raise RuntimeError("MATLAB executable not found. Install MATLAB or add matlab to PATH.")
    return work_dir, [exe, "-nodesktop", "-nosplash", "-r", command_expr]


def write_app_runner(run_root: Path) -> tuple[Path, list[str]]:
    stage_dir = run_root / STAGE_APP
    stage_dir.mkdir(parents=True, exist_ok=True)
    runner_path = stage_dir / "run_app_core.py"
    output_dir = stage_dir / "outputs"
    app_workers = max(1, min(8, (os.cpu_count() or 2) - 1))
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
    preload_wind=True,
)
cfg = build_config(
    None,
    grid_size={DEFAULTS["grid_size"]},
    hardening_rad={DEFAULTS["harden_rad"]},
    hardening_spo={DEFAULTS["harden_spo"]},
    rad_energy_ig={DEFAULTS["rad_ig_thresh"]},
    rad_rf={DEFAULTS["rad_decay"]},
    fb_wind_coef={DEFAULTS["brand_wind_coef"]},
    fb_wind_sd={DEFAULTS["brand_wind_sd"]},
    fb_wind_sd_transverse={DEFAULTS["brand_wind_sd_lat"]},
    seed_hardening={DEFAULTS["seed_harden"]},
    seed_spread={DEFAULTS["seed_spread"]},
)
try:
    run_simulation(
        cfg=cfg,
        data=data,
        output_dir={str(output_dir)!r},
        dpi=150,
        dpi_hires=600,
        make_video=True,
        dump_interval=1,
        dump_csv=True,
        dump_radiation_csv=True,
        dump_spotting_csv=True,
    )
finally:
    data.close()
print("APP_CORE_OUTPUT_DIR=" + {str(output_dir)!r})
"""
    runner_path.write_text(textwrap.dedent(script).strip() + "\n", encoding="utf-8")
    return stage_dir, [sys.executable, str(runner_path)]


def cli_command(run_root: Path) -> tuple[Path, list[str]]:
    output_dir = run_root / STAGE_CLI
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "swuift.cli",
        "--job-name",
        "advanced_cli_default",
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
        DEFAULTS["t_end"],
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
        "--no-lazy-wind",
        "--output-dir",
        str(output_dir),
        "--frame-dpi",
        "600",
        "--dump-every",
        "1",
        "--dump-csv",
        "--out-frames",
        "--out-video",
        "--out-gif",
        "--out-ig-plots",
        "--out-fire-csv",
        "--out-buildings-csv",
        "--out-rad-steps",
        "--out-spo-steps",
    ]
    return CLI_PROJECT, cmd


def build_commands(run_root: Path, stages: Iterable[str]) -> dict[str, tuple[Path, list[str]]]:
    commands: dict[str, tuple[Path, list[str]]] = {}
    for stage in stages:
        if stage == "matlab":
            commands[stage] = prepare_matlab_stage(run_root)
        elif stage == "app":
            commands[stage] = write_app_runner(run_root)
        elif stage == "cli":
            commands[stage] = cli_command(run_root)
        else:
            raise ValueError(f"Unknown stage: {stage}")
    return commands


def write_run_manifest(
    run_root: Path,
    commands: dict[str, tuple[Path, list[str]]],
    *,
    matlab_baseline_run_root: Path | None = None,
) -> None:
    manifest = {
        "created_at": dt.datetime.now().isoformat(),
        "workspace": str(WORKSPACE),
        "projects": {
            "matlab": str(MATLAB_PROJECT),
            "app": str(APP_PROJECT),
            "cli": str(CLI_PROJECT),
        },
        "data": {
            "matlab": str(paths.MATLAB_DATA),
            "python": str(paths.EXTRACTED_DATA),
        },
        "defaults": DEFAULTS,
        "normalized_frame_state": {
            "dtype": np.dtype(FRAME_STATE_DTYPE).name,
            "categories": FRAME_STATE_CATEGORIES,
            "meaning": {
                "-5": "water",
                "-4": "vegetation burned",
                "-2": "vegetation ignited",
                "-1": "vegetation",
                "0": "not-combustible",
                "1": "structure",
                "2": "structure ignited",
                "3": "structure developed",
                "4": "structure burned",
            },
            "comparison_note": "Future comparisons should ignore categories outside the common category set.",
        },
        "matlab_baseline_run_root": str(matlab_baseline_run_root) if matlab_baseline_run_root else None,
        "commands": {
            stage: {"cwd": str(cwd), "argv": argv}
            for stage, (cwd, argv) in commands.items()
        },
    }
    (run_root / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _write_state_manifest(out_dir: Path, *, stage: str, source: str, count: int, extras: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {
        "stage": stage,
        "source": source,
        "dtype": np.dtype(FRAME_STATE_DTYPE).name,
        "categories": FRAME_STATE_CATEGORIES,
        "count": count,
        "file_pattern": "state_XXXX.npy",
        "comparison_note": "Compare only shared categories; ignore extra categories present in one implementation.",
    }
    if extras:
        payload.update(extras)
    (out_dir / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _save_normalized_state(arr: np.ndarray, out_path: Path) -> list[int]:
    state = np.rint(arr).astype(FRAME_STATE_DTYPE, copy=False)
    np.save(out_path, state)
    return sorted(int(v) for v in np.unique(state) if int(v) not in FRAME_STATE_CATEGORIES)


def _load_csv_matrix(path: Path) -> np.ndarray:
    return np.loadtxt(path, delimiter=",")


def _build_frame_state(
    *,
    binary_cover: np.ndarray,
    ignition: np.ndarray,
    fire: np.ndarray,
    fstep: int,
    lstep: int,
    water: np.ndarray,
) -> np.ndarray:
    plt_mat = np.zeros(binary_cover.shape, dtype=np.float64)
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


def _normalize_csv_frame_dir(stage: str, source_dir: Path, out_dir: Path) -> None:
    if not source_dir.exists():
        raise FileNotFoundError(f"Missing frame-state source directory: {source_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    extras: set[int] = set()
    count = 0
    for csv_path in sorted(source_dir.glob("*.csv")):
        step_match = re.search(r"(\d+)", csv_path.stem)
        if not step_match:
            continue
        step = int(step_match.group(1))
        arr = _load_csv_matrix(csv_path)
        extras.update(_save_normalized_state(arr, out_dir / f"state_{step:04d}.npy"))
        count += 1
    _write_state_manifest(
        out_dir,
        stage=stage,
        source=str(source_dir),
        count=count,
        extras={"extra_categories_seen": sorted(extras)},
    )


def _normalize_timestep_frame_state(
    *,
    stage: str,
    timesteps_dir: Path,
    out_dir: Path,
    manifest_extras: dict[str, Any] | None = None,
) -> None:
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
    _write_state_manifest(
        out_dir,
        stage=stage,
        source=str(timesteps_dir),
        count=count,
        extras={
            **(manifest_extras or {}),
            "extra_categories_seen": sorted(extras),
        },
    )


def _normalize_cli_frame_state(run_root: Path) -> None:
    stage_root = resolve_stage_dir(run_root, STAGE_CLI)
    run_dirs = sorted(stage_root.glob("advanced_cli_default_*"))
    if not run_dirs:
        raise FileNotFoundError(f"No CLI run directory found under {stage_root}")
    cli_run_dir = run_dirs[-1]
    _normalize_timestep_frame_state(
        stage="cli",
        timesteps_dir=cli_run_dir / "timesteps",
        out_dir=stage_root / "normalized_frame_state",
        manifest_extras={"cli_run_dir": str(cli_run_dir)},
    )


def _state_files(path: Path) -> dict[int, Path]:
    return {
        int(candidate.stem.split("_", 1)[1]): candidate
        for candidate in sorted(path.glob("state_*.npy"))
    }


def _legend_label_two_lines(label: str) -> str:
    words = label.split()
    if len(words) >= 3:
        return " ".join(words[:2]) + "\n" + " ".join(words[2:])
    return label


def _load_lat_lon() -> tuple[np.ndarray, np.ndarray]:
    try:
        import scipy.io
    except ImportError as exc:
        raise RuntimeError("scipy is required to render state videos") from exc
    lat = scipy.io.loadmat(paths.EXTRACTED_DATA / EXTRACTED_FILES["lat"], squeeze_me=True)["lati"]
    lon = scipy.io.loadmat(paths.EXTRACTED_DATA / EXTRACTED_FILES["lon"], squeeze_me=True)["long"]
    return np.asarray(lat).squeeze(), np.asarray(lon).squeeze()


def _render_state_frame(
    state: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
    timestamp: str,
    out_path: Path,
    *,
    dpi: int,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt

    value_to_remap = np.zeros(10, dtype=np.float64)
    for idx, value in enumerate(FRAME_STATE_CATEGORIES):
        value_to_remap[value + 5] = 100.0 * (idx + 1)
    remap = value_to_remap[(state.astype(np.int16) + 5).clip(0, 9)]
    cmap = mcolors.ListedColormap(FRAME_STATE_COLORS)
    bounds = [100 * (idx + 1) - 50 for idx in range(len(FRAME_STATE_CATEGORIES))]
    bounds.append(100 * len(FRAME_STATE_CATEGORIES) + 50)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, ax = plt.subplots(figsize=(12, 10))
    fig.patch.set_facecolor("white")
    mesh = ax.pcolormesh(lon, lat, remap, cmap=cmap, norm=norm, shading="auto")
    ax.set_aspect("auto")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    for spine in ax.spines.values():
        spine.set_visible(False)

    ticks = [100 * (idx + 1) for idx in range(len(FRAME_STATE_CATEGORIES))]
    labels = [_legend_label_two_lines(label) for label in FRAME_STATE_LABELS]
    cb = fig.colorbar(mesh, ax=ax, ticks=ticks, shrink=0.85, pad=0.02)
    cb.ax.set_yticklabels(labels, fontsize=11)
    cb.outline.set_visible(False)
    ax.set_title(timestamp, fontsize=20, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _assemble_state_video(frames_dir: Path, output_dir: Path, *, fps: int, tag: str) -> None:
    ffmpeg = _ffmpeg_exe()
    pattern = str(frames_dir / "%04d.png")
    suffix = f"_{tag}" if tag else ""
    mp4_path = output_dir / f"simulation{suffix}.mp4"
    gif_path = output_dir / f"simulation{suffix}.gif"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            str(fps),
            "-i",
            pattern,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            str(mp4_path),
        ],
        check=True,
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            str(fps),
            "-i",
            pattern,
            "-vf",
            "scale=640:-1:flags=lanczos",
            str(gif_path),
        ],
        check=True,
    )


def render_state_video(
    *,
    state_dir: Path,
    output_dir: Path,
    frames_dir: Path | None = None,
    tag: str = "",
    dpi: int = 150,
    fps: int = 4,
    overwrite_frames: bool = False,
) -> None:
    state_files = _state_files(state_dir)
    if not state_files:
        raise FileNotFoundError(f"No normalized state_*.npy files found in {state_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = frames_dir or (output_dir / "frames")
    if overwrite_frames and frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    lat, lon = _load_lat_lon()
    start = dt.datetime.strptime(DEFAULTS["t_start"], "%Y-%m-%d %H:%M")
    for step, state_path in sorted(state_files.items()):
        frame_path = frames_dir / f"{step:04d}.png"
        if frame_path.exists() and not overwrite_frames:
            continue
        sim_time = start + dt.timedelta(minutes=(step - 1) * 5)
        timestamp = sim_time.strftime("%H:%M") + " MST"
        _render_state_frame(np.load(state_path), lon, lat, timestamp, frame_path, dpi=dpi)

    _assemble_state_video(frames_dir, output_dir, fps=fps, tag=tag)


def ensure_matlab_baseline(run_root: Path, baseline_run_root: Path) -> Path:
    baseline_stage = resolve_stage_dir(baseline_run_root, STAGE_MATLAB)
    baseline_state = baseline_stage / "normalized_frame_state"
    if not _state_files(baseline_state):
        normalize_stage_outputs("matlab", baseline_run_root)
        baseline_state = resolve_stage_dir(baseline_run_root, STAGE_MATLAB) / "normalized_frame_state"
    if not _state_files(baseline_state):
        raise FileNotFoundError(f"No MATLAB baseline state files found in {baseline_state}")

    target = resolve_stage_dir(run_root, STAGE_MATLAB) / "normalized_frame_state"
    if target.resolve() == baseline_state.resolve():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            target.unlink()
        elif not any(target.iterdir()):
            target.rmdir()
        else:
            return target
    target.symlink_to(baseline_state, target_is_directory=True)
    return target


def write_frame_state_comparison(run_root: Path, baseline_run_root: Path | None) -> None:
    script = PROJECT_DIR / "compare_frame_states.py"
    out_path = run_root / "frame_state_comparison.json"
    cmd = [sys.executable, str(script), str(run_root), "--out", str(out_path)]
    if baseline_run_root is not None:
        cmd.extend(["--matlab-run-root", str(baseline_run_root)])
    subprocess.run(cmd, cwd=str(PROJECT_DIR), check=True)


def normalize_stage_outputs(stage: str, run_root: Path) -> None:
    if stage == "matlab":
        matlab_stage = resolve_stage_dir(run_root, STAGE_MATLAB)
        _normalize_csv_frame_dir(
            "matlab",
            matlab_stage / "work" / "outs" / "frame_state_raw",
            matlab_stage / "normalized_frame_state",
        )
        return
    if stage == "app":
        app_stage = resolve_stage_dir(run_root, STAGE_APP)
        _normalize_timestep_frame_state(
            stage="app",
            timesteps_dir=app_stage / "outputs" / "timesteps",
            out_dir=app_stage / "normalized_frame_state",
            manifest_extras={"app_output_dir": str(app_stage / "outputs")},
        )
        return
    if stage == "cli":
        _normalize_cli_frame_state(run_root)
        return
    raise ValueError(f"Unknown stage: {stage}")


def run_sequence(args: argparse.Namespace) -> int:
    _require_paths()
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = Path(args.run_root or DEFAULT_RUN_ROOT / timestamp).resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    matlab_baseline_run_root = (
        Path(args.matlab_baseline_run_root).resolve()
        if args.matlab_baseline_run_root and "matlab" not in args.stages
        else None
    )

    defaults_ok = check_defaults(write_to=run_root / "default_check.json")
    if not defaults_ok and not args.allow_default_diffs:
        print("\nDefault mismatch detected. Re-run with --allow-default-diffs to continue.")
        return 2

    commands = build_commands(run_root, args.stages)
    if matlab_baseline_run_root is not None:
        ensure_matlab_baseline(run_root, matlab_baseline_run_root)
    write_run_manifest(run_root, commands, matlab_baseline_run_root=matlab_baseline_run_root)
    print(f"\nRun root: {run_root}")
    if matlab_baseline_run_root is not None:
        print(f"MATLAB baseline: {matlab_baseline_run_root}")

    if args.dry_run:
        for stage in args.stages:
            cwd, cmd = commands[stage]
            print(f"\n[{stage}] cwd={cwd}\n{' '.join(cmd)}")
        return 0

    for stage in args.stages:
        cwd, cmd = commands[stage]
        rc = run_subprocess(cmd, cwd=cwd, label=stage)
        if rc != 0:
            print(f"Stopping sequence because {stage} failed.")
            return rc
        print(f"[{stage}] normalizing per-timestep frame state")
        normalize_stage_outputs(stage, run_root)
    if not args.skip_compare:
        write_frame_state_comparison(run_root, matlab_baseline_run_root)
    print(f"\nAll requested stages completed. Outputs: {run_root}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_data_path_arguments(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-matlab", help="Verify MATLAB can be invoked.")
    sub.add_parser("check-defaults", help="Compare MATLAB/app/CLI defaults.")

    run = sub.add_parser("run", help="Run implementations in sequence.")
    run.add_argument("--run-root", help="Output directory for this orchestration run.")
    run.add_argument(
        "--stages",
        nargs="+",
        choices=["matlab", "app", "cli"],
        default=["matlab", "app", "cli"],
        help="Stages to run in order.",
    )
    run.add_argument("--dry-run", action="store_true", help="Write scripts and print commands only.")
    run.add_argument(
        "--allow-default-diffs",
        action="store_true",
        help="Continue even if default hyperparameter checks find mismatches.",
    )
    run.add_argument(
        "--matlab-baseline-run-root",
        default=str(DEFAULT_MATLAB_BASELINE_RUN),
        help="Existing MATLAB run to compare against when the matlab stage is not requested.",
    )
    run.add_argument(
        "--skip-compare",
        action="store_true",
        help="Do not write frame_state_comparison.json after the requested stages finish.",
    )

    render = sub.add_parser("render-state-video", help="Render PNG frames, MP4, and GIF from normalized state files.")
    render.add_argument("state_dir", type=Path, help="Directory containing normalized state_*.npy files.")
    render.add_argument("output_dir", type=Path, help="Directory where frames/video/GIF should be written.")
    render.add_argument("--frames-dir", type=Path, help="Optional frame output directory.")
    render.add_argument("--tag", default="", help="Optional output suffix, e.g. matlab -> simulation_matlab.mp4.")
    render.add_argument("--dpi", type=int, default=150, help="PNG render DPI.")
    render.add_argument("--fps", type=int, default=4, help="Video/GIF frame rate.")
    render.add_argument("--overwrite-frames", action="store_true", help="Regenerate PNG frames even if they exist.")

    args = parser.parse_args(argv)
    apply_data_path_arguments(args)
    if args.command == "check-matlab":
        return 0 if check_matlab() else 1
    if args.command == "check-defaults":
        _require_paths()
        return 0 if check_defaults() else 2
    if args.command == "run":
        return run_sequence(args)
    if args.command == "render-state-video":
        _require_paths()
        render_state_video(
            state_dir=args.state_dir.resolve(),
            output_dir=args.output_dir.resolve(),
            frames_dir=args.frames_dir.resolve() if args.frames_dir else None,
            tag=args.tag,
            dpi=args.dpi,
            fps=args.fps,
            overwrite_frames=args.overwrite_frames,
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
