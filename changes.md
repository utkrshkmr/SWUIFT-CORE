# Monorepo Restructure — Changes Summary

This document records all changes made during the monorepo restructure, 1080p video stitching, runtime comparison, and gitignore/CI work for `doe-wildfire/`.

---

## Overview

The repository was reorganized from a numbered `SWUIFT_FINAL/` layout into a standard Python monorepo. Shared physics live in `packages/core`, consumers are `apps/desktop` and `packages/cli`, and comparison tooling lives under `tools/compare/`. The comparison suite now supports 1080p tri-panel video stitching and runtime metrics on the `full` preset.

---

## 1. Directory restructure

The `SWUIFT_FINAL/` wrapper folder was removed. Folders were renamed/moved to role-based paths:

| Old path | New path |
|----------|----------|
| `swuift_core/` | `packages/core/` |
| `SWUIFT_FINAL/01_SWUIFT_PY_APP/` | `apps/desktop/` |
| `SWUIFT_FINAL/05_SWUIFT_CLI_V1.1/doe-fire/` | `packages/cli/` |
| `SWUIFT_FINAL/00_SWUIFT-main/` | `reference/matlab/` |
| `swuift_compare_orchestrator/` | `tools/compare/` |
| `SWUIFT_FINAL/99_test-op/` | `tests/fixtures/baseline-outputs/` |
| `SWUIFT_FINAL/LINEAGE.md` | `docs/lineage.md` |
| `stitch_matlab_app.py` (root) | Migrated to `tools/compare/stitch_video.py` (then deleted at root) |

**Removed folders** (from earlier consolidation, pre-monorepo):

- `02_PROTOTYPE_FAST_APP`, `03_PROTOTYPE_FAST_ALL_EMBERS_STREAMLINED`, `04_SWUIFT_CLI_v1`, `01a_PROTOTYPE_APP`
- `swuift-py-app`, `swuift-py-app-push`, `doe-wildfire/0`
- Empty `SWUIFT_FINAL/` wrapper after moves

### Target layout

```
doe-wildfire/
├── packages/
│   ├── core/              # swuift-core (src/swuift_core/)
│   └── cli/               # swuift CLI
├── apps/
│   └── desktop/           # PySide6 GUI + PyInstaller
├── reference/
│   └── matlab/            # MATLAB reference (SWUIFT_V4.m)
├── tools/
│   └── compare/           # compare_suite, orchestrator, video tools
├── tests/
│   ├── unit/core/
│   ├── unit/cli/
│   └── fixtures/baseline-outputs/
├── docs/
├── .github/workflows/
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

---

## 2. Shared physics core (`packages/core`)

Physics were previously duplicated across app/CLI prototypes. They were extracted into `packages/core` with a `src/swuift_core/` layout:

| Module | Purpose |
|--------|---------|
| `kernels.py` | Numba + Python fallback kernels |
| `spread.py` | Full-grid radiation, brand ignition (01-style physics) |
| `hardening.py` | Loop-based hardening |
| `config.py` | Canonical `SWUIFTConfig` |

**Consumers rewired:**

- `apps/desktop/swuift/simulation.py`, `config.py`, `__init__.py` — import from `swuift_core`
- `packages/cli/swuift/simulation.py`, `config.py`, `profiler.py` — import from `swuift_core`
- Local duplicate modules (`kernels.py`, `spread.py`, `hardening.py`, `numba_kernels.py`) removed from app and CLI

**Environment variables** (honored by app and CLI via core):

- `SWUIFT_APP_KERNEL_BACKEND` — `numba` (default) or `python`
- `SWUIFT_APP_RADIATION_WORKERS` — parallel radiation worker count

---

## 3. Path constants (`tools/compare/paths.py`)

New canonical path module. `WORKSPACE` is `PROJECT_DIR.parent.parent` (repo root), fixing the bug where `tools/compare/` nesting made `PROJECT_DIR.parent` resolve to `tools/` instead of `doe-wildfire/`.

```python
WORKSPACE = PROJECT_DIR.parent.parent
CORE_PROJECT = WORKSPACE / "packages" / "core"
APP_PROJECT = WORKSPACE / "apps" / "desktop"
CLI_PROJECT = WORKSPACE / "packages" / "cli"
MATLAB_PROJECT = WORKSPACE / "reference" / "matlab"
FIXTURES_DIR = WORKSPACE / "tests" / "fixtures"
```

**Stage directory names** updated from numbered folders to role-based names:

| Old | New |
|-----|-----|
| `01_matlab_basic` | `matlab` |
| `02_app_core` | `app` |
| `03_cli_advanced` | `cli` |

Legacy numbered folders are still resolved via `resolve_stage_dir()` when reading older runs under `tools/compare/runs/`.

---

## 4. Updated path references

| File | Change |
|------|--------|
| `requirements.txt` | `-e packages/core`, `-e packages/cli` |
| `apps/desktop/requirements_app.txt` | `-e ../../packages/core` |
| `apps/desktop/swuift_app.spec` | PyInstaller datas: `../../packages/core/src/swuift_core` |
| `tools/compare/orchestrator.py` | Imports from `paths.py`; stage dirs use `matlab`/`app`/`cli` |
| `tools/compare/compare_suite.py` | Full rewrite: new paths, video, runtime metrics |
| `tools/compare/compare_frame_states.py` | Uses `resolve_stage_dir()` and new stage names |
| `packages/core/README.md` | Install path updated |
| `docs/lineage.md` | Monorepo layout |
| `SWUIFT_IMPLEMENTATION_DIFFERENCES_00_01_05.md` | Updated folder references |

---

## 5. Test consolidation

| Old location | New location |
|--------------|--------------|
| `packages/core/tests/test_spread.py` | `tests/unit/core/test_spread.py` |
| `packages/cli/tests/*` | `tests/unit/cli/` |

**Added:** root `pytest.ini`:

```ini
[pytest]
testpaths = tests/unit
pythonpath = packages/cli packages/core/src apps/desktop
```

Old `packages/*/tests/` directories removed after move.

---

## 6. 1080p video stitching

### New files

- **`tools/compare/video.py`** — DPI helpers:
  - `frame_dpi_for_height(figsize=(12, 10), target_height=1080)` → **108 DPI**
  - `recommended_frame_dpi()` wrapper
- **`tools/compare/stitch_video.py`** — Tri-panel side-by-side MP4 stitcher:
  - `resolve_frame_sources()` — locates MATLAB/app/CLI PNG sequences (modern + legacy paths)
  - `stitch_panel_video()` — resize to 1080px height, label panels, H.264/yuv420p output

### Compare suite integration

New CLI flags in `compare_suite.py`:

| Flag | Behavior |
|------|----------|
| `--stitch-1080p` | Build MATLAB \| APP \| CLI MP4 after run |
| `--no-stitch` | Disable auto-stitch on `full` preset |
| `--video-height` | Panel height (default 1080) |
| `--video-fps` | Output FPS (default 4) |

When stitching is enabled on `full`:

1. Frame DPI auto-set to 108 (1080px height for 12×10 inch figures)
2. App runner: `dpi_hires=108`, `save_frames=True`
3. CLI: `--frame-dpi 108`, `--out-frames`
4. Output: `runs/<run_root>/comparison_1080p.mp4`

**Deleted:** root `stitch_matlab_app.py` (hardcoded Mac paths, MATLAB|APP only).

---

## 7. Runtime comparison (full preset)

### Preset change

```python
"full": PresetConfig(
    default_stages=("matlab_baseline", "app", "cli"),  # was ("app", "cli")
    smoke=False,
)
```

### New behavior

- **`StageRunMetrics` dataclass** — `wall_seconds`, `return_code`, `log_runtime_minutes`, optional `source`
- **`_run_command()`** — returns metrics; parses `Runtime: X minutes` from stdout
- **`_find_log_runtime()`** — reads run logs from matlab/app/cli output dirs
- **Fresh MATLAB on full** — runs via `prepare_matlab_stage()` when MATLAB is installed; falls back to baseline copy with `source: baseline_copy` and a warning
- **JSON output** — `runtime_comparison` block always included when stages ran
- **Console table** — wall clock vs reported runtime printed at end of full runs

Example JSON shape:

```json
"runtime_comparison": {
  "matlab": {"wall_seconds": 1234.5, "reported_minutes": 18.2, "source": "fresh_run"},
  "app":    {"wall_seconds": 890.1, "reported_minutes": 14.1},
  "cli":    {"wall_seconds": 635.3, "reported_minutes": 9.7}
}
```

Smoke presets (`smoke10`, `smoke15`) remain lightweight: no stitch, no fresh MATLAB unless explicitly requested.

---

## 8. Root `.gitignore`

Created `doe-wildfire/.gitignore` as single source of truth. Key rules:

**Ignored:** `.venv/`, `__pycache__/`, `.pytest_cache/`, `build/`, `dist/`, `tools/compare/runs/`, `**/outputs/`, `**/outs/`, `extracted_mat/`, `data/*.mat`, `*.mp4`, `*.gif`, IDE/OS dotfiles

**Tracked (not ignored):** source code, `*.spec`, icons, Inno Setup scripts, `.github/workflows/`, docs, small fixture manifests

---

## 9. CI relocation

| Old | New |
|-----|-----|
| `apps/desktop/.github/workflows/build.yml` | `.github/workflows/build-desktop.yml` |

Workflow updates:

- `working-directory: apps/desktop` for build steps
- `pip install -r ../../requirements.txt` then `pip install -r requirements_app.txt`
- Artifact paths prefixed with `apps/desktop/dist/`

---

## 10. Documentation

| File | Description |
|------|-------------|
| `README.md` | Root setup, layout summary, comparison and build commands |
| `docs/structure.md` | Full monorepo map and comparison tooling notes |
| `docs/lineage.md` | Updated lineage for monorepo layout |
| `tools/compare/README.md` | New paths, `--stitch-1080p`, runtime comparison on full preset |

---

## 11. Deleted / migrated files

- `stitch_matlab_app.py` — logic moved to `tools/compare/stitch_video.py`
- `apps/desktop/.github/workflows/build.yml` — moved to repo root
- Redundant prototype folders (see section 1)
- `SWUIFT_FINAL/` wrapper after all contents moved

---

## 12. Validation status

| Check | Status |
|-------|--------|
| `pytest tests/unit/` | **Passed** (22/22) after reinstall |
| `pip install -e packages/core && pip install -e packages/cli` | **Done** |
| App import (`from swuift.simulation import run_simulation`) | **OK** with venv Python |
| `compare_suite.py --preset smoke15` | **Blocked** — default baseline run `runs/20260602_162114` missing on this machine; legacy baseline exists at `runs/20260608_150939` |
| `compare_suite.py --preset full --stitch-1080p` | **Not run** (requires MATLAB + long runtime) |
| PyInstaller dry-run / CI build | **Not run yet** |

### Known issues

1. **Default MATLAB baseline path** (`tools/compare/runs/20260602_162114`) does not exist on this machine. Use `--matlab-baseline-run-root runs/20260608_150939` or regenerate baseline.
2. **Legacy run artifacts** under `tools/compare/runs/` still reference old folder names (`02_app_core`, `03_cli_advanced`); new runs use `app/`, `cli/`, `matlab/`.
3. **Reinstall required** after path moves: `pip install -e packages/core -e packages/cli` in `.venv`.

---

## 13. Quick reference — commands after restructure

```bash
# Setup
cd doe-wildfire
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/unit/

# Smoke comparison (use available baseline if default missing)
cd tools/compare
python compare_suite.py --preset smoke15 --stages app cli \
  --matlab-baseline-run-root runs/20260608_150939

# Full comparison with runtime + 1080p video
python compare_suite.py --preset full

# Desktop app build
cd apps/desktop
pip install -r requirements_app.txt
pyinstaller swuift_app.spec --noconfirm
```
