# Monorepo structure

```
doe-wildfire/
├── packages/
│   ├── core/              # swuift-core: shared physics (src/swuift_core/)
│   └── cli/               # swuift CLI package
├── apps/
│   └── desktop/           # PySide6 GUI + PyInstaller spec
├── reference/
│   └── matlab/            # MATLAB reference (SWUIFT_V4.m)
├── tools/
│   └── compare/           # compare_suite, orchestrator, video stitching
├── tests/
│   ├── unit/core/         # physics unit tests
│   ├── unit/cli/          # CLI unit tests
│   └── fixtures/          # baseline outputs (manifests tracked; large dumps gitignored)
├── docs/                  # lineage and implementation notes
├── data/                  # raw .mat inputs (gitignored)
└── extracted_mat/         # extracted simulation inputs (gitignored)
```

## Dependencies

- Root `requirements.txt` installs editable `packages/core` and `packages/cli`.
- Desktop app adds `apps/desktop/requirements_app.txt` for GUI and packaging deps.

## Comparison tooling

`tools/compare/compare_suite.py` orchestrates smoke and full presets:

- **smoke10** — short parity check against copied MATLAB baseline
- **full** — fresh MATLAB (if installed), app, and CLI runs with runtime comparison and 1080p video stitching

Stage output directories under each run use role-based names: `matlab/`, `app/`, `cli/`.

Legacy numbered folders (`01_matlab_basic`, `02_app_core`, `03_cli_advanced`) are still resolved when reading older runs.
