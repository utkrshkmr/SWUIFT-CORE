#!/usr/bin/env bash
# Full validation: unit tests + full comparison (MATLAB/app/CLI, runtime metrics, 1080p video).
#
# Expected data layout (NOT in git — place on the target machine):
#
#   parent/
#   ├── data/              MATLAB bundles (default_values.mat, wind_eaton.mat, …)
#   ├── extracted_mat/     per-variable .mat files for Python
#   └── doe-wildfire/      this repository
#
# Override with env vars or flags:
#   SWUIFT_MATLAB_DATA=/path/to/data SWUIFT_EXTRACTED_DATA=/path/to/extracted_mat ./run_full_test.sh
#   ./run_full_test.sh --matlab-data /path/to/data --extracted-data /path/to/extracted_mat
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV="$ROOT/.venv"

if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment at $VENV"
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "=== Installing dependencies ==="
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "=== Verifying data paths ==="
python - "$@" <<'PY'
import sys
from pathlib import Path
import argparse

sys.path.insert(0, str(Path("tools/compare")))
import paths

parser = argparse.ArgumentParser()
paths.add_data_path_arguments(parser)
args, _ = parser.parse_known_args(sys.argv[1:])
paths.apply_data_path_arguments(args)
roots = paths.verify_data_paths()
print("matlab_data:  ", roots["matlab_data"])
print("extracted_mat:", roots["extracted_data"])
print("layout:       ", paths.data_roots_summary()["layout"])
PY

echo "=== Unit tests ==="
pytest tests/unit/ -q

echo "=== Full comparison (241 steps, runtime + 1080p stitch) ==="
cd tools/compare

COMPARE_ARGS=("$@")
if [[ ${#COMPARE_ARGS[@]} -eq 0 ]]; then
  COMPARE_ARGS=(--preset full --stitch-1080p)
fi

python compare_suite.py "${COMPARE_ARGS[@]}"

echo ""
echo "=== Full test complete ==="
echo "Results under: tools/compare/runs/full_*"
echo "  - full_comparison.json       (parity + runtime_comparison)"
echo "  - comparison_1080p.mp4       (MATLAB | APP | CLI)"
echo "  - frame_state_comparison.json"
