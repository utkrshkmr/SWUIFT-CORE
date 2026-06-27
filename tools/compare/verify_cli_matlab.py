#!/usr/bin/env python3
"""Run multi-fire CLI-vs-MATLAB verification.

This runner intentionally modifies only generated MATLAB work-directory copies.
The reference MATLAB source and swuift_core package are not changed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
WORKSPACE = PROJECT_DIR.parent.parent
CLI_PROJECT = WORKSPACE / "packages" / "cli"
MATLAB_PROJECT = WORKSPACE / "reference" / "matlab"
DEFAULT_RUNS_DIR = PROJECT_DIR / "runs"

for project in (CLI_PROJECT, WORKSPACE / "packages" / "core" / "src"):
    text = str(project)
    if text not in sys.path:
        sys.path.insert(0, text)

from orchestrator import _build_frame_state, _save_normalized_state, _write_state_manifest, detect_matlab
from verification_checks import (
    CLI_INPUT_FILES,
    MATLAB_INPUT_FILES,
    FireCase,
    append_jsonl,
    compare_arrays,
    fire_case_to_json,
    first_deviations,
    hyperparameter_report,
    input_similarity,
    load_case_manifest,
    load_dump_array,
    required_file_report,
    step_dirs,
    summarize_step_stats,
    write_csv_rows,
    write_json,
)


DEFAULT_VARIABLES = ("fire", "ignition", "radtotal", "out_fire", "zvector")


def _timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _copy_or_link(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        target.symlink_to(source)
    except OSError:
        shutil.copy2(source, target)


def _run_command(label: str, cwd: Path, argv: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"[{label}] cwd={cwd}\n")
        log.write(f"[{label}] argv={' '.join(argv)}\n\n")
        log.flush()
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(f"[{label}] {line}", end="")
            log.write(line)
        return proc.wait()


def _matlab_dump_block() -> str:
    return (
        "    if ~exist([cd '/outs/verification_dumps'],'dir'), mkdir([cd '/outs/verification_dumps']); end\n"
        "    step_dir = [cd '/outs/verification_dumps/t' sprintf('%06d', tstep)];\n"
        "    if ~exist(step_dir,'dir'), mkdir(step_dir); end\n"
        "    writematrix(fire, [step_dir '/fire.csv']);\n"
        "    writematrix(ignition, [step_dir '/ignition.csv']);\n"
        "    writematrix(radtotal, [step_dir '/radtotal.csv']);\n"
        "    writematrix(out_fire, [step_dir '/out_fire.csv']);\n"
        "    writematrix(zvector, [step_dir '/zvector.csv']);\n"
        "    plt_mat_verify = zeros(rows,columns);\n"
        "    plt_mat_verify(binary_cover < 0) = -1;\n"
        "    plt_mat_verify(binary_cover == 0) = 0;\n"
        "    plt_mat_verify(binary_cover > 0) = 1;\n"
        "    plt_mat_verify(ignition.*binary_cover < 0) = -2;\n"
        "    plt_mat_verify(ignition.*binary_cover > 0) = 2;\n"
        "    plt_mat_verify(binary_cover > 0 & fire >= fstep & fire <= lstep) = 3;\n"
        "    plt_mat_verify(binary_cover > 0 & fire > lstep) = 4;\n"
        "    plt_mat_verify(binary_cover < 0 & fire > 1) = -4;\n"
        "    plt_mat_verify(water > 0) = -5;\n"
        "    if ~exist([cd '/outs/frame_state_raw'],'dir'), mkdir([cd '/outs/frame_state_raw']); end\n"
        "    writematrix(int16(plt_mat_verify), [cd '/outs/frame_state_raw/' sprintf('%04d.csv', tstep)]);\n"
        "    clear plt_mat_verify step_dir\n"
    )


def patch_matlab_for_verification(source: str) -> str:
    """Patch a generated MATLAB copy for low-output verification."""
    source = source.replace("\\outs\\", "/outs/")
    source = source.replace("[cd '\\outs\\", "[cd '/outs/")
    source = source.replace("for tstep=1:maxstep", "for tstep=1:maxstep\n    disp(['MATLAB timestep ' num2str(tstep) '/' num2str(maxstep)]);")
    source = source.replace(
        "    im = f_plots.f_snapshots(rows, columns, binary_cover, ignition, fire,...\n"
        "        long, lati, t_num_vec, tstep, fstep, lstep, im, water);\n",
        "    % Verification mode: skip per-step PNG frame generation.\n",
    )
    source = source.replace(
        "    clear wi ji\n"
        "    %%%%%%%%%%%\n"
        "    %%%%%%%%%%%\n\n"
        "end% for time step",
        "    clear wi ji\n"
        "    %%%%%%%%%%%\n"
        "    %%%%%%%%%%%\n\n"
        f"{_matlab_dump_block()}\n"
        "end% for time step",
        1,
    )
    source = source.replace(
        "%% Creating the gif\nf_plots.f_gif(report_name, im, fileID);",
        "%% Verification mode: skip GIF and per-timestep frame output\nfprintf(fileID, [newline 'Verification mode skipped spread GIF.' newline]);",
    )
    source = source.replace(
        "xlswrite([cd '/outs/zvector.xlsx'],zvector);",
        "writematrix(zvector, [cd '/outs/zvector.csv']);",
    )
    return source


def prepare_matlab_case(case: FireCase, run_root: Path, matlab_exe: str | None) -> tuple[Path, list[str]]:
    stage_dir = run_root / "matlab"
    work_dir = stage_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "outs").mkdir(exist_ok=True)

    for name in MATLAB_INPUT_FILES:
        _copy_or_link(case.matlab_data / name, work_dir / name)

    for name in ("f_spread.m", "f_plots.m"):
        text = (MATLAB_PROJECT / name).read_text(encoding="utf-8", errors="replace")
        (work_dir / name).write_text(patch_matlab_for_verification(text), encoding="utf-8")

    main_text = (MATLAB_PROJECT / "SWUIFT_V4.m").read_text(encoding="utf-8", errors="replace")
    (work_dir / "SWUIFT_V4_verification.m").write_text(
        patch_matlab_for_verification(main_text),
        encoding="utf-8",
    )

    exe = matlab_exe or detect_matlab()
    if not exe:
        raise RuntimeError("MATLAB executable not found. Use --matlab-exe or add matlab to PATH.")
    command_expr = (
        "try, diary('matlab_console.log'); SWUIFT_V4_verification; diary off; "
        "catch ME, try, diary off; catch, end; disp(getReport(ME,'extended')); exit(1); "
        "end; exit(0);"
    )
    return work_dir, [exe, "-nodesktop", "-nosplash", "-r", command_expr]


def build_cli_command(
    case: FireCase,
    run_root: Path,
    *,
    dump_csv: bool,
    lazy_wind: bool,
) -> tuple[Path, list[str]]:
    params = case.resolved_hyperparameters()
    output_dir = run_root / "cli"
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "swuift.cli",
        "--job-name",
        f"{case.name}_cli",
        "--fire-prog",
        str(case.cli_data / CLI_INPUT_FILES["fire_prog"]),
        "--domains",
        str(case.cli_data / CLI_INPUT_FILES["domains"]),
        "--landcover",
        str(case.cli_data / CLI_INPUT_FILES["landcover"]),
        "--homes",
        str(case.cli_data / CLI_INPUT_FILES["homes"]),
        "--lat",
        str(case.cli_data / CLI_INPUT_FILES["lat"]),
        "--lon",
        str(case.cli_data / CLI_INPUT_FILES["lon"]),
        "--harden-rad-map",
        str(case.cli_data / CLI_INPUT_FILES["harden_rad_map"]),
        "--harden-spo-map",
        str(case.cli_data / CLI_INPUT_FILES["harden_spo_map"]),
        "--water",
        str(case.cli_data / CLI_INPUT_FILES["water"]),
        "--wind",
        str(case.cli_data / CLI_INPUT_FILES["wind"]),
        "--grid-size",
        str(params["grid_size"]),
        "--t-start",
        str(params["t_start"]),
        "--t-end",
        str(params["t_end"]),
        "--harden-rad",
        str(params["harden_rad"]),
        "--harden-spo",
        str(params["harden_spo"]),
        "--rad-ig-thresh",
        str(params["rad_ig_thresh"]),
        "--rad-decay",
        str(params["rad_decay"]),
        "--brand-wind-coef",
        str(params["brand_wind_coef"]),
        "--brand-wind-sd",
        str(params["brand_wind_sd"]),
        "--brand-wind-sd-lat",
        str(params["brand_wind_sd_lat"]),
        "--seed-harden",
        str(params["seed_harden"]),
        "--seed-spread",
        str(params["seed_spread"]),
        "--lazy-wind" if lazy_wind else "--no-lazy-wind",
        "--output-dir",
        str(output_dir),
        "--frame-dpi",
        "120",
        "--dump-every",
        "1",
        "--dump-csv" if dump_csv else "--no-dump-csv",
        "--no-out-frames",
        "--no-out-video",
        "--no-out-gif",
        "--out-ig-plots",
        "--out-fire-csv",
        "--out-buildings-csv",
        "--no-out-rad-steps",
        "--no-out-spo-steps",
    ]
    return CLI_PROJECT, cmd


def latest_cli_run(case_root: Path) -> Path:
    candidates = sorted((case_root / "cli").glob("*_cli_*"))
    if not candidates:
        raise FileNotFoundError(f"No CLI run directory found under {case_root / 'cli'}")
    return candidates[-1]


def copy_ignition_plots(case_root: Path, cli_run_dir: Path) -> dict[str, Any]:
    out_root = case_root / "ignition_plots"
    matlab_out = out_root / "matlab"
    cli_out = out_root / "cli"
    matlab_out.mkdir(parents=True, exist_ok=True)
    cli_out.mkdir(parents=True, exist_ok=True)

    inventory: dict[str, Any] = {"matlab": [], "cli": []}
    matlab_sources = sorted((case_root / "matlab" / "work" / "outs").glob("*ig_*.png"))
    cli_sources = [
        path for path in (cli_run_dir / "ig_pixel.png", cli_run_dir / "ig_structure.png")
        if path.exists()
    ]
    for source in matlab_sources:
        target = matlab_out / source.name
        shutil.copy2(source, target)
        inventory["matlab"].append(str(target))
    for source in cli_sources:
        target = cli_out / source.name
        shutil.copy2(source, target)
        inventory["cli"].append(str(target))
    write_json(out_root / "inventory.json", inventory)
    write_json(case_root / "comparisons" / "ignition_plot_inventory.json", inventory)
    return inventory


def normalize_matlab_frame_states(case_root: Path) -> Path:
    source_dir = case_root / "matlab" / "work" / "outs" / "frame_state_raw"
    out_dir = case_root / "matlab" / "normalized_frame_state"
    out_dir.mkdir(parents=True, exist_ok=True)
    extras: set[int] = set()
    count = 0
    for csv_path in sorted(source_dir.glob("*.csv")):
        digits = "".join(ch for ch in csv_path.stem if ch.isdigit())
        if not digits:
            continue
        step = int(digits)
        arr = np.loadtxt(csv_path, delimiter=",")
        extras.update(_save_normalized_state(arr, out_dir / f"state_{step:04d}.npy"))
        count += 1
    _write_state_manifest(
        out_dir,
        stage="matlab",
        source=str(source_dir),
        count=count,
        extras={"extra_categories_seen": sorted(extras)},
    )
    return out_dir


def normalize_cli_frame_states(case: FireCase, cli_run_dir: Path, case_root: Path) -> Path:
    from swuift.data_loader import _load_array

    binary_cover = _load_array(str(case.cli_data / CLI_INPUT_FILES["landcover"]), "binary_cover")
    water = _load_array(str(case.cli_data / CLI_INPUT_FILES["water"]), "water")
    params = case.resolved_hyperparameters()
    t_step_min = 5.0
    fstep = int(22 / t_step_min) + 1
    lstep = int(177 / t_step_min) + 1

    out_dir = case_root / "cli" / "normalized_frame_state"
    out_dir.mkdir(parents=True, exist_ok=True)
    extras: set[int] = set()
    count = 0
    for step, step_dir in step_dirs(cli_run_dir / "timesteps").items():
        fire = load_dump_array(step_dir, "fire")
        ignition = load_dump_array(step_dir, "ignition")
        if fire is None or ignition is None:
            continue
        state = _build_frame_state(
            binary_cover=binary_cover,
            ignition=ignition,
            fire=fire,
            fstep=fstep,
            lstep=lstep,
            water=water,
        )
        extras.update(_save_normalized_state(state, out_dir / f"state_{step:04d}.npy"))
        count += 1
    _write_state_manifest(
        out_dir,
        stage="cli",
        source=str(cli_run_dir / "timesteps"),
        count=count,
        extras={
            "extra_categories_seen": sorted(extras),
            "hyperparameters": params,
        },
    )
    return out_dir


def compare_step_dumps(
    case_root: Path,
    cli_run_dir: Path,
    *,
    variables: tuple[str, ...],
    sample_mismatches: int,
) -> list[dict[str, Any]]:
    matlab_steps = step_dirs(case_root / "matlab" / "work" / "outs" / "verification_dumps")
    cli_steps = step_dirs(cli_run_dir / "timesteps")
    rows: list[dict[str, Any]] = []
    common_steps = sorted(set(matlab_steps) & set(cli_steps))
    for step in common_steps:
        for variable in variables:
            matlab_arr = load_dump_array(matlab_steps[step], variable)
            cli_arr = load_dump_array(cli_steps[step], variable)
            if matlab_arr is None or cli_arr is None:
                rows.append(
                    {
                        "step": step,
                        "variable": variable,
                        "match": False,
                        "missing": {
                            "matlab": matlab_arr is None,
                            "cli": cli_arr is None,
                        },
                    }
                )
                continue
            stats = compare_arrays(
                matlab_arr,
                cli_arr,
                sample_mismatches=sample_mismatches,
            )
            stats.update({"step": step, "variable": variable})
            rows.append(stats)
    append_jsonl(case_root / "comparisons" / "per_step_stats.jsonl", rows)
    write_csv_rows(case_root / "comparisons" / "per_variable_summary.csv", summarize_step_stats(rows))
    write_json(case_root / "comparisons" / "first_deviations.json", first_deviations(rows))
    return rows


def compare_frame_states(
    case_root: Path,
    *,
    sample_mismatches: int,
) -> list[dict[str, Any]]:
    matlab_dir = case_root / "matlab" / "normalized_frame_state"
    cli_dir = case_root / "cli" / "normalized_frame_state"
    rows: list[dict[str, Any]] = []
    matlab_files = {int(path.stem.split("_", 1)[1]): path for path in matlab_dir.glob("state_*.npy")}
    cli_files = {int(path.stem.split("_", 1)[1]): path for path in cli_dir.glob("state_*.npy")}
    for step in sorted(set(matlab_files) & set(cli_files)):
        stats = compare_arrays(
            np.load(matlab_files[step]),
            np.load(cli_files[step]),
            sample_mismatches=sample_mismatches,
        )
        stats.update({"step": step, "variable": "frame_state"})
        rows.append(stats)
    append_jsonl(case_root / "comparisons" / "frame_state_stats.jsonl", rows)
    return rows


def run_preflight(case: FireCase, case_root: Path) -> bool:
    problems = required_file_report(case)
    append_jsonl(case_root / "preflight" / "problems.jsonl", problems)
    if any(problem["severity"] == "fatal" for problem in problems):
        return False

    try:
        write_json(case_root / "preflight" / "input_similarity.json", input_similarity(case))
    except Exception as exc:  # noqa: BLE001 - keep diagnostics structured for non-CS users.
        append_jsonl(
            case_root / "preflight" / "problems.jsonl",
            [
                {
                    "severity": "fatal",
                    "check": "input_similarity",
                    "message": str(exc),
                }
            ],
        )
        return False

    try:
        write_json(case_root / "preflight" / "hyperparameters.json", hyperparameter_report(case))
    except Exception as exc:  # noqa: BLE001
        append_jsonl(
            case_root / "preflight" / "problems.jsonl",
            [
                {
                    "severity": "fatal",
                    "check": "hyperparameters",
                    "message": str(exc),
                }
            ],
        )
        return False
    return True


def run_case(
    case: FireCase,
    run_root: Path,
    *,
    matlab_exe: str | None,
    variables: tuple[str, ...],
    sample_mismatches: int,
    dump_csv: bool,
    lazy_wind: bool,
) -> dict[str, Any]:
    case_root = run_root / case.name
    case_root.mkdir(parents=True, exist_ok=True)
    write_json(case_root / "case.json", fire_case_to_json(case))
    status: dict[str, Any] = {
        "case": case.name,
        "root": str(case_root),
        "started_at": dt.datetime.now().isoformat(),
        "preflight_ok": False,
        "matlab_return_code": None,
        "cli_return_code": None,
        "comparison_completed": False,
    }

    if not run_preflight(case, case_root):
        status["ended_at"] = dt.datetime.now().isoformat()
        status["status"] = "preflight_failed"
        return status
    status["preflight_ok"] = True

    try:
        matlab_cwd, matlab_cmd = prepare_matlab_case(case, case_root, matlab_exe)
        cli_cwd, cli_cmd = build_cli_command(case, case_root, dump_csv=dump_csv, lazy_wind=lazy_wind)
        write_json(
            case_root / "commands.json",
            {
                "matlab": {"cwd": str(matlab_cwd), "argv": matlab_cmd},
                "cli": {"cwd": str(cli_cwd), "argv": cli_cmd},
            },
        )
        status["matlab_return_code"] = _run_command(
            f"{case.name}:matlab",
            matlab_cwd,
            matlab_cmd,
            case_root / "logs" / "matlab.log",
        )
        status["cli_return_code"] = _run_command(
            f"{case.name}:cli",
            cli_cwd,
            cli_cmd,
            case_root / "logs" / "cli.log",
        )
    except Exception as exc:  # noqa: BLE001
        append_jsonl(
            case_root / "preflight" / "problems.jsonl",
            [{"severity": "fatal", "check": "run_processes", "message": str(exc)}],
        )
        status["ended_at"] = dt.datetime.now().isoformat()
        status["status"] = "run_failed"
        return status

    if status["matlab_return_code"] != 0 or status["cli_return_code"] != 0:
        status["ended_at"] = dt.datetime.now().isoformat()
        status["status"] = "run_failed"
        return status

    try:
        cli_run_dir = latest_cli_run(case_root)
        copy_ignition_plots(case_root, cli_run_dir)
        normalize_matlab_frame_states(case_root)
        normalize_cli_frame_states(case, cli_run_dir, case_root)
        compare_step_dumps(
            case_root,
            cli_run_dir,
            variables=variables,
            sample_mismatches=sample_mismatches,
        )
        compare_frame_states(case_root, sample_mismatches=sample_mismatches)
        status["comparison_completed"] = True
        status["status"] = "completed"
    except Exception as exc:  # noqa: BLE001
        append_jsonl(
            case_root / "preflight" / "problems.jsonl",
            [{"severity": "fatal", "check": "comparison", "message": str(exc)}],
        )
        status["status"] = "comparison_failed"

    status["ended_at"] = dt.datetime.now().isoformat()
    return status


def selected_cases(cases: list[FireCase], names: list[str]) -> list[FireCase]:
    if names == ["all"]:
        return cases
    wanted = set(names)
    selected = [case for case in cases if case.name in wanted]
    missing = sorted(wanted - {case.name for case in selected})
    if missing:
        raise ValueError(f"Unknown fire case(s): {', '.join(missing)}")
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True, help="JSON or simple YAML fire-case manifest.")
    parser.add_argument("--fires", nargs="+", default=["all"], help="Fire case names to run, or 'all'.")
    parser.add_argument("--run-root", type=Path, help="Output root. Defaults to tools/compare/runs/verification_TIMESTAMP.")
    parser.add_argument("--matlab-exe", help="Explicit MATLAB executable path.")
    parser.add_argument("--variables", default=",".join(DEFAULT_VARIABLES), help="Comma-separated step dump variables to compare.")
    parser.add_argument("--sample-mismatches", type=int, default=5, help="Number of mismatched coordinates to sample per variable/step.")
    parser.add_argument("--dump-csv", action="store_true", help="Ask CLI to dump CSV instead of compact .npy step files.")
    parser.add_argument("--lazy-wind", action="store_true", help="Use lazy wind loading for CLI to reduce RAM.")
    args = parser.parse_args(argv)

    cases = selected_cases(load_case_manifest(args.cases.resolve()), args.fires)
    run_root = args.run_root.resolve() if args.run_root else DEFAULT_RUNS_DIR / f"verification_{_timestamp()}"
    run_root.mkdir(parents=True, exist_ok=True)
    variables = tuple(item.strip() for item in args.variables.split(",") if item.strip())
    write_json(
        run_root / "run_manifest.json",
        {
            "created_at": dt.datetime.now().isoformat(),
            "workspace": str(WORKSPACE),
            "cases_file": str(args.cases.resolve()),
            "fires": [case.name for case in cases],
            "variables": variables,
            "outputs": {
                "frames": False,
                "video": False,
                "gif": False,
                "ignition_plots": True,
                "cli_dump_csv": args.dump_csv,
            },
        },
    )

    statuses = []
    for case in cases:
        print(f"\n=== Verification case: {case.name} ===")
        status = run_case(
            case,
            run_root,
            matlab_exe=args.matlab_exe,
            variables=variables,
            sample_mismatches=args.sample_mismatches,
            dump_csv=args.dump_csv,
            lazy_wind=args.lazy_wind,
        )
        statuses.append(status)
        append_jsonl(run_root / "fires.jsonl", [status])
        write_json(run_root / "latest_status.json", statuses)

    failures = [status for status in statuses if status.get("status") != "completed"]
    print(f"\nVerification outputs: {run_root}")
    if failures:
        print(f"Completed with {len(failures)} failed case(s). See fires.jsonl and per-case problems.jsonl.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
