"""Unit tests for multi-fire CLI-vs-MATLAB verification helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
COMPARE = ROOT / "tools" / "compare"
for path in (COMPARE, ROOT / "packages" / "cli", ROOT / "packages" / "core" / "src"):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from verification_checks import (  # noqa: E402
    FireCase,
    compare_arrays,
    first_deviations,
    load_case_manifest,
    required_file_report,
    summarize_step_stats,
)
from verify_cli_matlab import build_cli_command, compare_step_dumps  # noqa: E402


def test_load_case_manifest_simple_yaml(tmp_path):
    manifest = tmp_path / "cases.yaml"
    manifest.write_text(
        """
fires:
  - name: alpha
    cli_data: data/cli/alpha
    matlab_data: data/matlab/alpha
    t_start: "2025-01-07 18:20"
    t_end: "2025-01-07 18:30"
    rad_decay: 0.9
""",
        encoding="utf-8",
    )

    cases = load_case_manifest(manifest)

    assert len(cases) == 1
    assert cases[0].name == "alpha"
    assert cases[0].cli_data == (tmp_path / "data/cli/alpha").resolve()
    assert cases[0].resolved_hyperparameters()["rad_decay"] == 0.9


def test_required_file_report_marks_missing_files(tmp_path):
    case = FireCase(
        name="missing",
        cli_data=tmp_path / "cli",
        matlab_data=tmp_path / "matlab",
    )

    problems = required_file_report(case)

    assert problems
    assert all(problem["severity"] == "fatal" for problem in problems)
    assert any("wildland_fire_matrix.mat" in problem["path"] for problem in problems)


def test_compare_arrays_reports_mismatch_stats_and_samples():
    matlab = np.array([[1.0, 2.0], [3.0, 4.0]])
    cli = np.array([[1.0, 2.5], [3.0, 10.0]])

    stats = compare_arrays(matlab, cli, sample_mismatches=1)

    assert stats["match"] is False
    assert stats["shape_match"] is True
    assert stats["mismatched_count"] == 2
    assert stats["exact_match_count"] == 2
    assert stats["max_abs_diff"] == 6.0
    assert len(stats["mismatch_samples"]) == 1


def test_summary_and_first_deviation_continue_after_mismatch():
    rows = [
        {"step": 1, "variable": "fire", "match": True, "mismatched_count": 0, "max_abs_diff": 0.0},
        {"step": 2, "variable": "fire", "match": False, "mismatched_count": 3, "max_abs_diff": 2.0},
        {"step": 3, "variable": "fire", "match": False, "mismatched_count": 1, "max_abs_diff": 5.0},
    ]

    summary = summarize_step_stats(rows)
    first = first_deviations(rows)

    assert summary[0]["step_count"] == 3
    assert summary[0]["mismatch_step_count"] == 2
    assert summary[0]["first_deviation_step"] == 2
    assert summary[0]["max_abs_diff"] == 5.0
    assert first["fire"]["step"] == 2


def test_compare_step_dumps_logs_all_common_steps(tmp_path):
    case_root = tmp_path / "case"
    matlab_root = case_root / "matlab/work/outs/verification_dumps"
    cli_root = case_root / "cli/alpha_cli_20260101/timesteps"
    for root in (matlab_root, cli_root):
        for step in (1, 2):
            step_dir = root / f"t{step:06d}"
            step_dir.mkdir(parents=True)
            np.save(step_dir / "fire.npy", np.array([[step, 0.0]]))

    np.save(cli_root / "t000002/fire.npy", np.array([[99.0, 0.0]]))

    rows = compare_step_dumps(
        case_root,
        case_root / "cli/alpha_cli_20260101",
        variables=("fire",),
        sample_mismatches=0,
    )

    assert [row["step"] for row in rows] == [1, 2]
    assert rows[0]["match"] is True
    assert rows[1]["match"] is False
    assert (case_root / "comparisons/per_step_stats.jsonl").exists()
    assert (case_root / "comparisons/per_variable_summary.csv").exists()
    assert (case_root / "comparisons/first_deviations.json").exists()


def test_build_cli_command_uses_low_output_defaults(tmp_path):
    case = FireCase(
        name="alpha",
        cli_data=tmp_path / "cli",
        matlab_data=tmp_path / "matlab",
        hyperparameters={"t_end": "2025-01-07 18:30"},
    )

    _, cmd = build_cli_command(case, tmp_path / "run", dump_csv=False, lazy_wind=True)

    assert "--no-out-frames" in cmd
    assert "--no-out-video" in cmd
    assert "--no-out-gif" in cmd
    assert "--out-ig-plots" in cmd
    assert "--no-dump-csv" in cmd
    assert "--lazy-wind" in cmd
