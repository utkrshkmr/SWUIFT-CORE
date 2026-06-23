# SWUIFT Comparison Tooling

Cross-implementation comparison for MATLAB, desktop app, and CLI against a saved MATLAB baseline.

Canonical data roots (auto-detected; **not in git**):

| Root | Resolution order |
|------|------------------|
| `data/` (MATLAB bundles) | `SWUIFT_MATLAB_DATA` → `--matlab-data` → `../data` (sibling) → `./data` (in repo) |
| `extracted_mat/` (Python inputs) | `SWUIFT_EXTRACTED_DATA` → `--extracted-data` → `../extracted_mat` → `./extracted_mat` |

**Recommended layout after git clone:**

```
parent/
├── data/
├── extracted_mat/
└── doe-wildfire/    ← this repo
```

- Shared physics core: `../../packages/core`
- Saved MATLAB baseline run: `runs/20260602_162114` (optional for `full` when MATLAB is installed)

Project versions:

| Stage name | Folder |
|---|---|
| `matlab_baseline` | saved run in `runs/20260602_162114` (or fresh `matlab/` on full preset) |
| `app` | `../../apps/desktop` |
| `cli` | `../../packages/cli` |

## Setup

```bash
cd doe-wildfire
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

MATLAB is detected from `PATH` first, then from `/Applications/MATLAB_R*.app/bin/matlab`.

## Checks

```bash
cd tools/compare
python3 orchestrator.py check-matlab
python3 orchestrator.py check-defaults
```

## Comparison Suite

```bash
# Fast 10-step app parity check
python3 compare_suite.py --preset smoke10

# 15-step app + CLI check
python3 compare_suite.py --preset smoke15

# Run both smoke presets in sequence
python3 compare_suite.py --preset all

# Full 241-step comparison with runtime metrics and 1080p tri-panel video
python3 compare_suite.py --preset full
python3 compare_suite.py --preset full --no-stitch   # skip video stitching
python3 compare_suite.py --preset full --stitch-1080p --video-height 1080
```

The `full` preset runs fresh MATLAB (when installed), app, and CLI. It always writes `runtime_comparison` to the JSON summary and prints a wall-clock vs reported-runtime table.

Run only selected stages:

```bash
python3 compare_suite.py --preset smoke15 --stages app cli
python3 compare_suite.py --preset smoke10 --stages matlab_baseline app
```

1080p stitching uses auto-calculated frame DPI (`108` for 12×10 inch figures at 1080px height) and writes `comparison_1080p.mp4` under the run root.

### Full validation script (from repo root)

```bash
./run_full_test.sh
./run_full_test.sh --matlab-data /path/to/data --extracted-data /path/to/extracted_mat
```

Runs `pytest tests/unit/` then `compare_suite.py --preset full --stitch-1080p` (runtime comparison + 1080p video).

## Kernel environment variables

Both app and CLI honor these variables (defined in `swuift_core`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SWUIFT_APP_KERNEL_BACKEND` | `numba` | Set to `python` to force pure-Python kernels |
| `SWUIFT_APP_RADIATION_WORKERS` | `1` | Process count for parallel radiation chunking |

The orchestrator-generated app runner sets `SWUIFT_APP_RADIATION_WORKERS` to a bounded multi-process value.

## Full Orchestrator Run

```bash
python3 orchestrator.py run --stages app cli --matlab-baseline-run-root runs/20260602_162114
```

Compare any run root against the saved MATLAB baseline:

```bash
python3 compare_frame_states.py runs/smoke_15 --matlab-run-root runs/20260602_162114
```
