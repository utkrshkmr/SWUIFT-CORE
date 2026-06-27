"""Shared checks for CLI-vs-MATLAB multi-fire verification.

The functions in this module are intentionally free of MATLAB process logic so
they can be unit-tested without MATLAB or large fire datasets.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
import scipy.io as sio


CLI_INPUT_FILES = {
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

MATLAB_INPUT_FILES = (
    "default_values.mat",
    "wind_eaton.mat",
    "eaton_inputs_all.mat",
    "fire_prog.mat",
    "domains_mat.mat",
)

CLI_MAT_VARS = {
    "fire_prog": "wildland_fire_matrix",
    "domains": "domains_mat",
    "landcover": "binary_cover",
    "homes": "homes_mat",
    "lat": "lati",
    "lon": "long",
    "harden_rad_map": "hardening_mat_rad",
    "harden_spo_map": "hardening_mat_spo",
    "water": "water",
}

MATLAB_MAT_VARS = {
    "fire_prog": ("fire_prog.mat", "fire_prog"),
    "domains": ("domains_mat.mat", "domains_mat"),
    "landcover": ("eaton_inputs_all.mat", "binary_cover"),
    "homes": ("eaton_inputs_all.mat", "homes_mat"),
    "lat": ("eaton_inputs_all.mat", "lati"),
    "lon": ("eaton_inputs_all.mat", "long"),
    "harden_rad_map": ("eaton_inputs_all.mat", "hardening_mat_rad"),
    "harden_spo_map": ("eaton_inputs_all.mat", "hardening_mat_spo"),
    "water": ("eaton_inputs_all.mat", "water"),
}

DEFAULT_HYPERPARAMETERS = {
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

MATLAB_DEFAULT_MAP = {
    "rad_ig_thresh": "rad_energy_ig",
    "rad_decay": "rad_rf",
    "brand_wind_coef": "fb_wind_coef",
    "brand_wind_sd": "fb_wind_sd",
    "brand_wind_sd_lat": "fb_wind_sd_transverse",
}


@dataclass(frozen=True)
class FireCase:
    """One fire verification case from a manifest."""

    name: str
    cli_data: Path
    matlab_data: Path
    hyperparameters: dict[str, Any] = field(default_factory=dict)

    def resolved_hyperparameters(self) -> dict[str, Any]:
        params = dict(DEFAULT_HYPERPARAMETERS)
        params.update(self.hyperparameters)
        return params


def _parse_scalar(value: str) -> Any:
    text = value.strip().strip("\"'")
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small manifest subset used by the verification manual.

    This avoids adding PyYAML as a dependency. Supported shape:

    fires:
      - name: eaton
        cli_data: path
        matlab_data: path
        t_start: "..."
    """
    fires: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip() or line.strip() == "fires:":
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if current:
                fires.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if stripped:
                key, value = stripped.split(":", 1)
                current[key.strip()] = _parse_scalar(value)
            continue
        if current is None:
            raise ValueError(f"Unsupported manifest line: {raw_line!r}")
        if ":" not in stripped:
            raise ValueError(f"Unsupported manifest line: {raw_line!r}")
        key, value = stripped.split(":", 1)
        current[key.strip()] = _parse_scalar(value)
    if current:
        fires.append(current)
    return {"fires": fires}


def load_case_manifest(path: Path) -> list[FireCase]:
    """Load a JSON or simple YAML fire case manifest."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
    else:
        payload = _parse_simple_yaml(text)

    base = path.parent
    cases: list[FireCase] = []
    for item in payload.get("fires", []):
        known = {"name", "cli_data", "matlab_data"}
        missing = sorted(known - set(item))
        if missing:
            raise ValueError(f"Fire case is missing required fields: {', '.join(missing)}")
        hyper = {k: v for k, v in item.items() if k not in known}
        cli_data = Path(item["cli_data"])
        matlab_data = Path(item["matlab_data"])
        cases.append(
            FireCase(
                name=str(item["name"]),
                cli_data=(base / cli_data).resolve() if not cli_data.is_absolute() else cli_data,
                matlab_data=(base / matlab_data).resolve() if not matlab_data.is_absolute() else matlab_data,
                hyperparameters=hyper,
            )
        )
    return cases


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payloads: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for payload in payloads:
            f.write(json.dumps(payload, default=str) + "\n")


def write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def required_file_report(case: FireCase) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for label, folder, names in (
        ("cli", case.cli_data, CLI_INPUT_FILES.values()),
        ("matlab", case.matlab_data, MATLAB_INPUT_FILES),
    ):
        for name in names:
            path = folder / name
            if not path.exists():
                problems.append(
                    {
                        "severity": "fatal",
                        "check": "required_file_exists",
                        "stage": label,
                        "path": str(path),
                        "message": f"Missing required {label} input file: {path}",
                    }
                )
    return problems


def _load_mat_array(path: Path, var_name: str) -> np.ndarray:
    data = sio.loadmat(path, squeeze_me=True)
    if var_name not in data:
        raise KeyError(f"Variable {var_name!r} not found in {path}")
    arr = np.asarray(data[var_name])
    if arr.ndim == 2 and 1 in arr.shape:
        arr = arr.ravel()
    return arr.astype(np.float64, copy=False)


def _array_summary(arr: np.ndarray) -> dict[str, Any]:
    finite = np.asarray(arr)[np.isfinite(arr)]
    summary: dict[str, Any] = {
        "shape": list(arr.shape),
        "size": int(arr.size),
        "nan_count": int(np.isnan(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
    }
    if finite.size:
        summary.update(
            {
                "min": float(finite.min()),
                "max": float(finite.max()),
                "mean": float(finite.mean()),
                "nonzero_count": int(np.count_nonzero(arr)),
            }
        )
    return summary


def compare_arrays(
    left: np.ndarray,
    right: np.ndarray,
    *,
    left_name: str = "matlab",
    right_name: str = "cli",
    sample_mismatches: int = 0,
    atol: float = 0.0,
) -> dict[str, Any]:
    """Return structured stats for two arrays; never raises on mismatch."""
    left_arr = np.asarray(left)
    right_arr = np.asarray(right)
    payload: dict[str, Any] = {
        "shape_match": tuple(left_arr.shape) == tuple(right_arr.shape),
        f"{left_name}_shape": list(left_arr.shape),
        f"{right_name}_shape": list(right_arr.shape),
        f"{left_name}_dtype": str(left_arr.dtype),
        f"{right_name}_dtype": str(right_arr.dtype),
    }
    if not payload["shape_match"]:
        payload["match"] = False
        return payload

    diff = np.abs(left_arr.astype(np.float64) - right_arr.astype(np.float64))
    if atol:
        mismatch_mask = diff > atol
    else:
        mismatch_mask = left_arr != right_arr
    total = int(left_arr.size)
    mismatched = int(np.count_nonzero(mismatch_mask))
    exact = total - mismatched
    finite_diff = diff[np.isfinite(diff)]
    payload.update(
        {
            "match": mismatched == 0,
            "total_elements": total,
            "exact_match_count": exact,
            "exact_match_fraction": exact / total if total else None,
            "mismatched_count": mismatched,
            "mismatched_fraction": mismatched / total if total else None,
            "max_abs_diff": float(finite_diff.max()) if finite_diff.size else None,
            "mean_abs_diff": float(finite_diff.mean()) if finite_diff.size else None,
            "p50_abs_diff": float(np.percentile(finite_diff, 50)) if finite_diff.size else None,
            "p95_abs_diff": float(np.percentile(finite_diff, 95)) if finite_diff.size else None,
            "p99_abs_diff": float(np.percentile(finite_diff, 99)) if finite_diff.size else None,
            f"{left_name}_min": float(np.nanmin(left_arr)) if left_arr.size else None,
            f"{left_name}_max": float(np.nanmax(left_arr)) if left_arr.size else None,
            f"{right_name}_min": float(np.nanmin(right_arr)) if right_arr.size else None,
            f"{right_name}_max": float(np.nanmax(right_arr)) if right_arr.size else None,
        }
    )
    if diff.size:
        max_index = np.unravel_index(int(np.nanargmax(diff)), diff.shape)
        payload["max_diff_index"] = [int(v) for v in max_index]
    if sample_mismatches and mismatched:
        coords = np.argwhere(mismatch_mask)
        samples = []
        for coord in coords[:sample_mismatches]:
            index = tuple(int(v) for v in coord)
            samples.append(
                {
                    "index": list(index),
                    left_name: float(left_arr[index]),
                    right_name: float(right_arr[index]),
                    "abs_diff": float(diff[index]),
                }
            )
        payload["mismatch_samples"] = samples
    return payload


def input_similarity(case: FireCase) -> dict[str, Any]:
    """Compare CLI extracted inputs against MATLAB bundle inputs."""
    report: dict[str, Any] = {"case": case.name, "arrays": {}, "wind": {}}
    for key, cli_file in CLI_INPUT_FILES.items():
        if key == "wind":
            continue
        matlab_file, matlab_var = MATLAB_MAT_VARS[key]
        cli_arr = _load_mat_array(case.cli_data / cli_file, CLI_MAT_VARS[key])
        matlab_arr = _load_mat_array(case.matlab_data / matlab_file, matlab_var)
        stats = compare_arrays(matlab_arr, cli_arr, sample_mismatches=0)
        stats["matlab_summary"] = _array_summary(matlab_arr)
        stats["cli_summary"] = _array_summary(cli_arr)
        report["arrays"][key] = stats

    report["wind"] = wind_similarity(case)
    return report


def wind_similarity(case: FireCase) -> dict[str, Any]:
    """Compare wind dataset shapes and the first slice when both are HDF5 MAT files."""
    cli_path = case.cli_data / CLI_INPUT_FILES["wind"]
    matlab_path = case.matlab_data / "wind_eaton.mat"
    payload: dict[str, Any] = {
        "cli_path": str(cli_path),
        "matlab_path": str(matlab_path),
    }
    with h5py.File(cli_path, "r") as cli_h5, h5py.File(matlab_path, "r") as matlab_h5:
        for var_name in ("wind_s", "wind_d"):
            if var_name not in cli_h5 or var_name not in matlab_h5:
                payload[var_name] = {"available": False}
                continue
            cli_ds = cli_h5[var_name]
            matlab_ds = matlab_h5[var_name]
            entry: dict[str, Any] = {
                "cli_shape": list(cli_ds.shape),
                "matlab_shape": list(matlab_ds.shape),
                "shape_match": tuple(cli_ds.shape) == tuple(matlab_ds.shape),
            }
            if cli_ds.shape and matlab_ds.shape and tuple(cli_ds.shape) == tuple(matlab_ds.shape):
                entry.update(compare_arrays(matlab_ds[0], cli_ds[0], sample_mismatches=0))
            payload[var_name] = entry
    return payload


def _mat_scalar(path: Path, var_name: str) -> Any:
    data = sio.loadmat(path, squeeze_me=True)
    if var_name not in data:
        return None
    value = np.asarray(data[var_name]).squeeze()
    if value.shape == ():
        return value.item()
    return value.tolist()


def _parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d %H:%M")


def hyperparameter_report(case: FireCase) -> dict[str, Any]:
    """Compare manifest parameters, MATLAB defaults, and derived CLI config."""
    params = case.resolved_hyperparameters()

    from swuift.config import build_config

    cfg = build_config(
        grid_size=int(params["grid_size"]),
        t_start=_parse_dt(params["t_start"]),
        t_end=_parse_dt(params["t_end"]),
        harden_rad=float(params["harden_rad"]),
        harden_spo=float(params["harden_spo"]),
        rad_ig_thresh=float(params["rad_ig_thresh"]),
        rad_decay=float(params["rad_decay"]),
        brand_wind_coef=float(params["brand_wind_coef"]),
        brand_wind_sd=float(params["brand_wind_sd"]),
        brand_wind_sd_lat=float(params["brand_wind_sd_lat"]),
        seed_harden=int(params["seed_harden"]),
        seed_spread=int(params["seed_spread"]),
    )

    matlab_defaults = {
        key: _mat_scalar(case.matlab_data / "default_values.mat", matlab_name)
        for key, matlab_name in MATLAB_DEFAULT_MAP.items()
    }
    manifest = dict(params)
    derived = {
        "maxstep": cfg.maxstep,
        "fstep": cfg.fstep,
        "lstep": cfg.lstep,
        "fb_str_ig": cfg.fb_str_ig,
        "fb_veg_gen": cfg.fb_veg_gen,
        "fb_veg_ig": cfg.fb_veg_ig,
        "limrad": cfg.limrad,
        "limspo": cfg.limspo,
        "t_step_min": cfg.t_step_min,
    }

    comparisons = {}
    for key, matlab_value in matlab_defaults.items():
        manifest_value = manifest.get(key)
        if matlab_value is None:
            status = "missing_in_matlab"
        elif isinstance(matlab_value, (int, float)) and isinstance(manifest_value, (int, float)):
            status = "match" if abs(float(matlab_value) - float(manifest_value)) < 1e-12 else "diff"
        else:
            status = "match" if str(matlab_value) == str(manifest_value) else "diff"
        comparisons[key] = {
            "manifest": manifest_value,
            "matlab_default_values_mat": matlab_value,
            "status": status,
        }

    return {
        "case": case.name,
        "manifest": manifest,
        "matlab_defaults": matlab_defaults,
        "derived_cli_config": derived,
        "comparisons": comparisons,
    }


def load_dump_array(step_dir: Path, variable: str) -> np.ndarray | None:
    npy_path = step_dir / f"{variable}.npy"
    csv_path = step_dir / f"{variable}.csv"
    if npy_path.exists():
        return np.load(npy_path)
    if csv_path.exists():
        return np.loadtxt(csv_path, delimiter=",")
    return None


def step_dirs(root: Path) -> dict[int, Path]:
    dirs: dict[int, Path] = {}
    for candidate in sorted(root.glob("t*")):
        if not candidate.is_dir():
            continue
        digits = "".join(ch for ch in candidate.name if ch.isdigit())
        if digits:
            dirs[int(digits)] = candidate
    return dirs


def summarize_step_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        variable = row["variable"]
        current = summary.setdefault(
            variable,
            {
                "variable": variable,
                "step_count": 0,
                "mismatch_step_count": 0,
                "max_mismatched_count": 0,
                "max_abs_diff": 0.0,
                "first_deviation_step": None,
            },
        )
        current["step_count"] += 1
        mismatch_count = int(row.get("mismatched_count") or 0)
        if mismatch_count:
            current["mismatch_step_count"] += 1
            if current["first_deviation_step"] is None:
                current["first_deviation_step"] = row["step"]
        current["max_mismatched_count"] = max(current["max_mismatched_count"], mismatch_count)
        max_abs = row.get("max_abs_diff")
        if max_abs is not None:
            current["max_abs_diff"] = max(float(current["max_abs_diff"]), float(max_abs))
    return list(summary.values())


def first_deviations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in rows:
        if row.get("match") is False and row.get("mismatched_count", 0):
            result.setdefault(row["variable"], row)
    return result


def fire_case_to_json(case: FireCase) -> dict[str, Any]:
    payload = asdict(case)
    payload["cli_data"] = str(case.cli_data)
    payload["matlab_data"] = str(case.matlab_data)
    payload["hyperparameters"] = case.resolved_hyperparameters()
    return payload
