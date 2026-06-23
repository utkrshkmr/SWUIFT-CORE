# SWUIFT CLI — User Manual

SWUIFT (Simulating Wildfire-Urban Interface Fire Transmission) models wildfire spread through vegetation and urban structures. This manual covers the **command-line interface** (`swuift`).

- **Project overview:** [README.md](README.md)
- **Desktop GUI version:** [MANUAL.md](MANUAL.md)

---

## 1. Introduction

The CLI runs SWUIFT from a terminal. It supports:

- **Single-run mode** — all parameters passed as command-line flags
- **Batch mode** — multiple jobs defined in a JSON file, executed sequentially

Entry points:

```bash
swuift --help
python -m swuift --help
```

The CLI and desktop app share the same physics via `packages/core` (`swuift-core`). They differ only in workflow: terminal/batch vs graphical job queue.

---

## 2. Installation

From the monorepo root:

```bash
cd doe-wildfire
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This installs editable `packages/core` and `packages/cli`. Verify:

```bash
swuift --help
```

**Requirements:** Python 3.10 or newer.

---

## 3. Prerequisites

Before running a simulation you need:

1. **Input files** — ten spatial/temporal inputs in `.mat` and/or `.csv` format (see §4). Pre-extracted Eaton scenario files are in `extracted_mat/` after running `python data/extract_inputs_to_mat.py`.
2. **Writable output directory outside the repository** — the CLI refuses to write inside `packages/cli/`. Use e.g. `/mnt/swuift_runs` or `~/swuift_outputs`.

---

## 4. Input Files

All ten inputs are **required** for every job (single-run or batch).

| CLI flag | Typical filename | MATLAB variable | Format |
|----------|------------------|-----------------|--------|
| `--fire-prog` | `wildland_fire_matrix.mat` | `knownig_mat` | `.mat` or `.csv` |
| `--domains` | `domain_matrix.mat` | `domains_mat` | `.mat` or `.csv` |
| `--landcover` | `binary_cover_landcover.mat` | `binary_cover` | `.mat` or `.csv` |
| `--homes` | `homes_matrix.mat` | `homes_mat` | `.mat` or `.csv` |
| `--lat` | `latitude.mat` | `lati` | `.mat` or `.csv` (1-D, length = rows) |
| `--lon` | `longitude.mat` | `long` | `.mat` or `.csv` (1-D, length = cols) |
| `--harden-rad-map` | `radiation_matrix.mat` | `hardening_mat_rad` | `.mat` or `.csv` |
| `--harden-spo-map` | `spotting_matrix.mat` | `hardening_mat_spo` | `.mat` or `.csv` |
| `--water` | `water_matrix.mat` | `water` | `.mat` or `.csv` |
| `--wind` | `wind.mat` | `wind_s`, `wind_d` | HDF5/v7.3 `.mat` or `.csv` pair |

### Wind file notes

- **`.mat` (HDF5/v7.3):** Large time-series file (~7 GB for Eaton). Use `--no-lazy-wind` to preload into RAM (faster) or `--lazy-wind` to read on demand (lower RAM).
- **`.csv`:** Pass a marker path; companion files `wind_s.csv` + `wind_d.csv` must sit in the same directory. CSV wind is single-timestep only.

All rasters must share the same `(rows, cols)` shape from `binary_cover`.

---

## 5. Single-Run Mode

Every required flag must be provided explicitly. If any are missing, the CLI reports:

```
Job 'myjob' missing required CLI parameters: --flag1, --flag2, ...
```

### Full example (Eaton defaults)

Replace `/path/to/doe-wildfire` and `/mnt/swuift_runs` with your paths:

```bash
swuift \
  --job-name baseline \
  --fire-prog /path/to/doe-wildfire/extracted_mat/wildland_fire_matrix.mat \
  --domains /path/to/doe-wildfire/extracted_mat/domain_matrix.mat \
  --landcover /path/to/doe-wildfire/extracted_mat/binary_cover_landcover.mat \
  --homes /path/to/doe-wildfire/extracted_mat/homes_matrix.mat \
  --lat /path/to/doe-wildfire/extracted_mat/latitude.mat \
  --lon /path/to/doe-wildfire/extracted_mat/longitude.mat \
  --harden-rad-map /path/to/doe-wildfire/extracted_mat/radiation_matrix.mat \
  --harden-spo-map /path/to/doe-wildfire/extracted_mat/spotting_matrix.mat \
  --water /path/to/doe-wildfire/extracted_mat/water_matrix.mat \
  --wind /path/to/doe-wildfire/extracted_mat/wind.mat \
  --grid-size 10 \
  --t-start "2025-01-07 18:20" \
  --t-end "2025-01-08 14:20" \
  --harden-rad 70 \
  --harden-spo 70 \
  --rad-ig-thresh 14000.0 \
  --rad-decay 1.0 \
  --brand-wind-coef 30.0 \
  --brand-wind-sd 0.3 \
  --brand-wind-sd-lat 4.85 \
  --seed-harden 123456 \
  --seed-spread 10 \
  --no-lazy-wind \
  --output-dir /mnt/swuift_runs \
  --frame-dpi 300 \
  --dump-every 0 \
  --no-dump-csv
```

---

## 6. CLI Reference

### Mode

| Flag | Description |
|------|-------------|
| `--batch PATH` | Run jobs from a JSON file (mutually exclusive with single-run flags) |
| `--job-name NAME` | Unique job name for single-run mode (**required** in single mode) |

### Input files

`--fire-prog`, `--domains`, `--landcover`, `--homes`, `--lat`, `--lon`, `--harden-rad-map`, `--harden-spo-map`, `--water`, `--wind`

### Hyperparameters (required in single mode)

| Flag | Description | Reference default |
|------|-------------|-------------------|
| `--grid-size` | Cell size in meters | `10` |
| `--t-start` | Simulation start datetime | `2025-01-07 18:20` |
| `--t-end` | Simulation end datetime | `2025-01-08 14:20` |
| `--harden-rad` | Radiation hardening level (%) | `70` |
| `--harden-spo` | Spotting hardening level (%) | `70` |
| `--rad-ig-thresh` | Radiation ignition threshold (W/m²) | `14000.0` |
| `--rad-decay` | Radiation decay / reduction factor | `1.0` |
| `--brand-wind-coef` | Firebrand wind coefficient | `30.0` |
| `--brand-wind-sd` | Firebrand wind std dev (longitudinal) | `0.3` |
| `--brand-wind-sd-lat` | Firebrand wind std dev (transverse) | `4.85` |
| `--seed-harden` | Hardening RNG seed | `123456` |
| `--seed-spread` | Spread RNG seed | `10` |
| `--lazy-wind` / `--no-lazy-wind` | Lazy HDF5 wind loading (**required** in single mode) | — |

**Time formats:** `YYYY-MM-DD HH:MM`, `YYYY-MM-DDTHH:MM`, or `YYYY-MM-DD HH:MM:SS`. Start and end must align to **5-minute** boundaries; the total window must be divisible by 5 minutes.

### Run controls (required in single mode)

| Flag | Description |
|------|-------------|
| `--output-dir PATH` | Base output directory (must be outside `packages/cli/`) |
| `--frame-dpi N` | DPI for simulation frame PNGs |
| `--dump-every N` | Save per-step state every N steps; `0` = disabled |
| `--dump-csv` / `--no-dump-csv` | Dump format: CSV vs binary `.npy` (**required** in single mode) |

### Output toggles (optional in single mode; defaults shown)

| Flag | Default | Output |
|------|---------|--------|
| `--out-frames` / `--no-out-frames` | On | `frames/%04d.png` |
| `--out-video` / `--no-out-video` | On | `simulation.mp4` (requires frames) |
| `--out-gif` / `--no-out-gif` | On | `simulation.gif` (requires frames) |
| `--out-ig-plots` / `--no-out-ig-plots` | On | `ig_pixel.png`, `ig_structure.png` |
| `--out-fire-csv` / `--no-out-fire-csv` | On | `fire_prog.csv` |
| `--out-buildings-csv` / `--no-out-buildings-csv` | On | `zvector.csv` |
| `--out-rad-steps` / `--no-out-rad-steps` | Off | `timesteps/rad_XXXXXX.csv` per step |
| `--out-spo-steps` / `--no-out-spo-steps` | Off | `timesteps/spo_XXXXXX.csv` per step |

---

## 7. Batch Mode

Define multiple jobs in a JSON file and run them sequentially:

```bash
swuift --batch packages/cli/jobs_example.json
```

### JSON schema

Top-level object with a `jobs` array. Each job object uses the same field names as CLI flags (snake_case):

```json
{
  "jobs": [
    {
      "name": "baseline",
      "fire_prog": "/path/to/extracted_mat/wildland_fire_matrix.mat",
      "domains": "...",
      "landcover": "...",
      "homes": "...",
      "lat": "...",
      "lon": "...",
      "harden_rad_map": "...",
      "harden_spo_map": "...",
      "water": "...",
      "wind": "...",
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
      "lazy_wind": false,
      "output_dir": "/mnt/swuift_runs",
      "frame_dpi": 300,
      "dump_every": 0,
      "dump_csv": false,
      "out_frames": true,
      "out_video": true,
      "out_gif": true,
      "out_ig_plots": true,
      "out_fire_csv": true,
      "out_buildings_csv": true,
      "out_rad_steps": false,
      "out_spo_steps": false
    }
  ]
}
```

Required per job: `name`, all ten input paths, all hyperparameters, `lazy_wind`, `output_dir`, `frame_dpi`, `dump_every`, `dump_csv`. Output toggles are optional (defaults apply).

See `packages/cli/jobs_example.json` for a two-job example (baseline + high hardening).

---

## 8. Output Directory Layout

Each job creates a timestamped run folder:

```
<output_dir>/<job_name>_<YYYYMMDD_HHMMSS>/
```

### Always written

| File | Contents |
|------|----------|
| `run_log.txt` | Full console log and command line |
| `run_params.json` | Inputs, config, outputs, timing, grid shape, full job spec |

### Optional outputs

| Flag(s) | Path |
|---------|------|
| `out_frames` | `frames/0001.png`, `frames/0002.png`, … |
| `out_video` | `simulation.mp4` |
| `out_gif` | `simulation.gif` |
| `out_ig_plots` | `ig_pixel.png`, `ig_structure.png` |
| `out_fire_csv` | `fire_prog.csv` |
| `out_buildings_csv` | `zvector.csv` |
| `out_rad_steps` | `timesteps/rad_000001.csv`, … |
| `out_spo_steps` | `timesteps/spo_000001.csv`, … |
| `dump_every > 0` | `timesteps/t000001/` per dumped step |

### Per-step dump contents (`dump_every`)

When `dump_csv=true`: `fire.csv`, `ignition.csv`, `radtotal.csv`, `out_fire.csv`, `zvector.csv`  
When `dump_csv=false`: corresponding `.npy` files

**Constraint:** `out_frames` must be `true` if `out_video` or `out_gif` is enabled.

---

## 9. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SWUIFT_APP_KERNEL_BACKEND` | `numba` | Set to `python` for pure-Python kernels (debugging, ARM64 builds without Numba) |
| `SWUIFT_APP_RADIATION_WORKERS` | `1` | Process count for parallel radiation chunking on multi-core hosts |

Example:

```bash
export SWUIFT_APP_RADIATION_WORKERS=4
swuift --job-name baseline ...
```

---

## 10. Common Recipes

### Fast smoke run (no video)

```bash
swuift --job-name smoke ... \
  --t-end "2025-01-07 19:35" \
  --lazy-wind \
  --no-out-frames --no-out-video --no-out-gif \
  --dump-every 1 --dump-csv \
  --frame-dpi 100
```

### Full run with all outputs

Use the full example in §5 with `--out-frames --out-video --out-gif` (defaults).

### Background batch (Linux)

```bash
nohup swuift --batch ./jobs.json > /mnt/swuift_runs/batch.log 2>&1 &
```

### Disable GIF only

```bash
swuift --job-name baseline ... --no-out-gif
```

---

## 11. Troubleshooting

| Problem | Solution |
|---------|----------|
| Missing required CLI parameters | Provide all 29 required flags in single mode (see §6) |
| Output directory inside project | Use a path outside `packages/cli/` |
| Time alignment error | Start/end must be on 5-minute boundaries; window divisible by 5 min |
| Out of memory loading wind | Use `--lazy-wind` |
| Slow per-step performance | `--no-lazy-wind` preloads wind (~7 GB) but is faster per step |
| `out_video` requires frames | Enable `--out-frames` or disable `--out-video` |
| Command not found | Activate venv; run `pip install -r requirements.txt` |

For a graphical interface, see [MANUAL.md](MANUAL.md).

---

## License

See the [SWUIFT Research and Academic Use License](../../LICENSE) at the repository root. Commercial licensing inquiries: Prof. Negar Elhami-Khorasani, `negarkho@buffalo.edu`.
