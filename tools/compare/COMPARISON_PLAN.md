# SWUIFT Three-Way Comparison Plan

This orchestrator currently runs the implementations and collects their native outputs. The next phase should compare only artifacts that exist for at least two implementations.

## 1. Normalize Run Metadata

Create one normalized metadata JSON per stage:

- implementation name/version
- source project path
- data source path
- hyperparameters
- grid shape
- timestep count
- wall-clock runtime
- output files discovered

Use `run_manifest.json`, CLI `run_params.json`, app runner settings, and MATLAB logs/workspace files.

## 2. Canonical Output Discovery

Discover these artifacts when present:

- normalized per-timestep frame state
  - every stage: `normalized_frame_state/state_XXXX.npy`
  - dtype: `int16`
  - category set: `[-5, -4, -2, -1, 0, 1, 2, 3, 4]`
  - this is the primary comparison target because it is the classified matrix used to draw PNGs
- final fire progression raster
  - MATLAB: `outs/fire_prog.txt`
  - app: `outputs/fire_prog.csv`
  - CLI: stage run folder `fire_prog.csv`
- building ignition table
  - MATLAB: patched runner writes `outs/zvector.csv`
  - app: `outputs/zvector.csv`
  - CLI: stage run folder `zvector.csv`
- timestep state dumps
  - app/CLI: `timesteps/`
  - MATLAB: full workspace in `*_vars.mat`, if saved successfully
- frames and animations
  - MATLAB: `outs/*.png`, `*.gif`
  - app/CLI: `frames/`, `simulation.mp4`, `simulation.gif`
- aggregate ignition plots
  - pixel ignition plot
  - structure ignition plot
- logs
  - MATLAB text report + diary
  - app stdout/logs
  - CLI `run_log.txt`

## 3. Numeric Comparisons

Start with normalized frame state:

- load `state_XXXX.npy` from each implementation
- assert shape equality
- assert dtype is `int16`
- compare only common categories from each stage manifest
- ignore cells/categories that exist only in one implementation
- report per-step differing-cell counts and percentages
- identify the first timestep where category states diverge

Then compare final outputs:

- matrix shape equality
- NaN count equality
- exact integer equality where data are integer arrival/ignition states
- absolute and relative error stats for floating matrices
- count of differing cells
- largest differences with cell coordinates

Then compare `zvector`:

- number of homes
- ignition flag counts
- radiation vs branding cause counts
- timestep deltas per home
- first N mismatching homes

## 4. Time-Series Comparisons

Where timestep dumps are available:

- compare `fire`, `ignition`, `out_fire`, `radtotal`, `zvector`
- record per-step max/mean absolute difference
- identify first timestep where implementations diverge
- generate compact CSV/JSON summaries rather than huge tables

## 5. Visual Summaries

Generate comparison images:

- final fire progression diff heatmap
- zvector ignition timestep histogram
- per-step divergence line plot
- side-by-side selected frames

Do not rely on pixel equality for rendered PNGs unless matplotlib/MATLAB rendering settings are locked down.

## 6. Report Format

Create:

- `comparison_summary.md` for humans
- `comparison_summary.json` for automation
- `diffs/` with optional CSVs and PNGs

Keep full raw run outputs untouched; write comparisons into a separate `comparison/` folder under the run root.
