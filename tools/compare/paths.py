"""Canonical workspace paths for SWUIFT comparison tooling."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
WORKSPACE = PROJECT_DIR.parent.parent

CORE_PROJECT = WORKSPACE / "packages" / "core"
APP_PROJECT = WORKSPACE / "apps" / "desktop"
CLI_PROJECT = WORKSPACE / "packages" / "cli"
MATLAB_PROJECT = WORKSPACE / "reference" / "matlab"
FIXTURES_DIR = WORKSPACE / "tests" / "fixtures"

STAGE_MATLAB = "matlab"
STAGE_APP = "app"
STAGE_CLI = "cli"

LEGACY_STAGE_MATLAB = "01_matlab_basic"
LEGACY_STAGE_APP = "02_app_core"
LEGACY_STAGE_CLI = "03_cli_advanced"

DEFAULT_MATLAB_BASELINE_RUN = PROJECT_DIR / "runs" / "20260602_162114"

MATLAB_DATA_MARKER_FILES = (
    "default_values.mat",
    "eaton_inputs_all.mat",
    "fire_prog.mat",
    "wind_eaton.mat",
)

EXTRACTED_DATA_MARKER_FILES = (
    "wildland_fire_matrix.mat",
    "domain_matrix.mat",
    "binary_cover_landcover.mat",
    "wind.mat",
)

_MATLAB_DATA_OVERRIDE: Path | None = None
_EXTRACTED_DATA_OVERRIDE: Path | None = None


def _candidate_data_dirs(folder: str) -> list[Path]:
    """Search sibling-outside-repo first, then inside the monorepo."""
    return [WORKSPACE.parent / folder, WORKSPACE / folder]


def _dir_has_markers(path: Path, markers: tuple[str, ...]) -> bool:
    return path.is_dir() and all((path / name).exists() for name in markers)


def _resolve_data_dir(
    folder: str,
    *,
    env_var: str,
    markers: tuple[str, ...],
    override: Path | None,
) -> Path:
    if override is not None:
        return override.resolve()

    env_value = os.environ.get(env_var)
    if env_value:
        return Path(env_value).resolve()

    for candidate in _candidate_data_dirs(folder):
        if _dir_has_markers(candidate, markers):
            return candidate.resolve()

    # Prefer data/extracted_mat as siblings of doe-wildfire/ (git clone without large files).
    return _candidate_data_dirs(folder)[0].resolve()


def configure_data_roots(
    *,
    matlab_data: Path | str | None = None,
    extracted_data: Path | str | None = None,
) -> None:
    """Override MATLAB and extracted input directories (CLI/env resolution)."""
    global MATLAB_DATA, EXTRACTED_DATA, _MATLAB_DATA_OVERRIDE, _EXTRACTED_DATA_OVERRIDE

    _MATLAB_DATA_OVERRIDE = Path(matlab_data).resolve() if matlab_data else None
    _EXTRACTED_DATA_OVERRIDE = Path(extracted_data).resolve() if extracted_data else None

    MATLAB_DATA = _resolve_data_dir(
        "data",
        env_var="SWUIFT_MATLAB_DATA",
        markers=MATLAB_DATA_MARKER_FILES[:1],
        override=_MATLAB_DATA_OVERRIDE,
    )
    EXTRACTED_DATA = _resolve_data_dir(
        "extracted_mat",
        env_var="SWUIFT_EXTRACTED_DATA",
        markers=EXTRACTED_DATA_MARKER_FILES[:2],
        override=_EXTRACTED_DATA_OVERRIDE,
    )


def data_roots_summary() -> dict[str, str]:
    return {
        "workspace": str(WORKSPACE),
        "matlab_data": str(MATLAB_DATA),
        "extracted_mat": str(EXTRACTED_DATA),
        "layout": (
            "external"
            if MATLAB_DATA.parent == WORKSPACE.parent or EXTRACTED_DATA.parent == WORKSPACE.parent
            else "in-repo"
        ),
    }


def verify_data_paths() -> dict[str, Path]:
    """Ensure required input bundles exist; raise FileNotFoundError with layout hints."""
    missing: list[str] = []

    for name in MATLAB_DATA_MARKER_FILES:
        path = MATLAB_DATA / name
        if not path.exists():
            missing.append(f"  {path}")

    for name in EXTRACTED_DATA_MARKER_FILES:
        path = EXTRACTED_DATA / name
        if not path.exists():
            missing.append(f"  {path}")

    if missing:
        raise FileNotFoundError(
            "Missing SWUIFT input data.\n\n"
            "Expected layout (data NOT in git — place locally):\n\n"
            f"  {WORKSPACE.parent}/\n"
            f"  ├── data/              ← MATLAB bundles (default_values.mat, wind_eaton.mat, …)\n"
            f"  ├── extracted_mat/     ← per-variable .mat files for Python\n"
            f"  └── {WORKSPACE.name}/    ← this repository\n\n"
            "Alternative: keep data/ and extracted_mat/ inside the repo root.\n\n"
            "Override paths with:\n"
            "  --matlab-data PATH --extracted-data PATH\n"
            "  SWUIFT_MATLAB_DATA=... SWUIFT_EXTRACTED_DATA=...\n\n"
            "Resolved roots:\n"
            f"  matlab_data:    {MATLAB_DATA}\n"
            f"  extracted_mat:  {EXTRACTED_DATA}\n\n"
            "Missing files:\n" + "\n".join(missing)
        )

    return {"matlab_data": MATLAB_DATA, "extracted_data": EXTRACTED_DATA}


def add_data_path_arguments(parser) -> None:
    parser.add_argument(
        "--matlab-data",
        type=Path,
        help=f"MATLAB data bundle directory (default: auto-detect; prefers {WORKSPACE.parent}/data)",
    )
    parser.add_argument(
        "--extracted-data",
        type=Path,
        help=f"Extracted per-variable .mat directory (default: auto-detect; prefers {WORKSPACE.parent}/extracted_mat)",
    )


def apply_data_path_arguments(args) -> None:
    configure_data_roots(
        matlab_data=getattr(args, "matlab_data", None),
        extracted_data=getattr(args, "extracted_data", None),
    )


def resolve_stage_dir(run_root: Path, stage: str) -> Path:
    """Return stage directory, supporting legacy numbered folder names."""
    modern = run_root / stage
    if modern.exists():
        return modern
    legacy_map = {
        STAGE_MATLAB: LEGACY_STAGE_MATLAB,
        STAGE_APP: LEGACY_STAGE_APP,
        STAGE_CLI: LEGACY_STAGE_CLI,
    }
    legacy = run_root / legacy_map.get(stage, stage)
    if legacy.exists():
        return legacy
    return modern


configure_data_roots()
