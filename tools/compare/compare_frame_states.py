#!/usr/bin/env python3
"""Compare normalized SWUIFT frame-state arrays across implementations."""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

from paths import STAGE_APP, STAGE_CLI, STAGE_MATLAB, resolve_stage_dir


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads((path / "manifest.json").read_text(encoding="utf-8"))


def _state_files(path: Path) -> dict[int, Path]:
    files: dict[int, Path] = {}
    for candidate in sorted(path.glob("state_*.npy")):
        step = int(candidate.stem.split("_", 1)[1])
        files[step] = candidate
    return files


def compare_pair(
    stage_dirs: dict[str, Path],
    left: str,
    right: str,
) -> dict[str, Any]:
    left_dir = stage_dirs[left]
    right_dir = stage_dirs[right]
    left_manifest = _load_manifest(left_dir)
    right_manifest = _load_manifest(right_dir)

    if left_manifest["dtype"] != "int16" or right_manifest["dtype"] != "int16":
        raise ValueError(f"{left} vs {right}: normalized states must be int16")

    common_categories = sorted(
        set(int(v) for v in left_manifest["categories"])
        & set(int(v) for v in right_manifest["categories"])
    )

    left_files = _state_files(left_dir)
    right_files = _state_files(right_dir)
    common_steps = sorted(set(left_files) & set(right_files))

    per_step = []
    first_difference = None
    for step in common_steps:
        a = np.load(left_files[step])
        b = np.load(right_files[step])
        if a.dtype != np.int16 or b.dtype != np.int16:
            raise ValueError(f"{left} vs {right} step {step}: dtype must be int16")
        if a.shape != b.shape:
            raise ValueError(f"{left} vs {right} step {step}: shape mismatch {a.shape} != {b.shape}")

        mask = np.isin(a, common_categories) & np.isin(b, common_categories)
        comparable_cells = int(mask.sum())
        diff_cells = int(((a != b) & mask).sum())
        if diff_cells and first_difference is None:
            first_difference = step
        per_step.append(
            {
                "step": step,
                "comparable_cells": comparable_cells,
                "different_cells": diff_cells,
                "different_fraction": (diff_cells / comparable_cells) if comparable_cells else None,
            }
        )

    return {
        "pair": [left, right],
        "common_categories": common_categories,
        "common_step_count": len(common_steps),
        "first_difference_step": first_difference,
        "per_step": per_step,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--out", type=Path, help="Optional JSON output path.")
    parser.add_argument(
        "--matlab-run-root",
        type=Path,
        help="Optional existing run root that supplies matlab/normalized_frame_state.",
    )
    args = parser.parse_args()

    run_root = args.run_root.resolve()
    matlab_run_root = args.matlab_run_root.resolve() if args.matlab_run_root else run_root
    stage_names = ("matlab", "app", "cli")
    stage_dirs = {
        "matlab": resolve_stage_dir(matlab_run_root, STAGE_MATLAB) / "normalized_frame_state",
        "app": resolve_stage_dir(run_root, STAGE_APP) / "normalized_frame_state",
        "cli": resolve_stage_dir(run_root, STAGE_CLI) / "normalized_frame_state",
    }
    summary = {
        "run_root": str(run_root),
        "matlab_run_root": str(matlab_run_root),
        "pairs": [
            compare_pair(stage_dirs, left, right)
            for left, right in combinations(stage_names, 2)
            if stage_dirs[left].exists()
            and stage_dirs[right].exists()
        ],
    }

    text = json.dumps(summary, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
