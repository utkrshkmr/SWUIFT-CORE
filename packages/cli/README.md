> **Canonical CLI manual:** see [CLI_MANUAL.md](../../CLI_MANUAL.md) at the repo root.

![SWUIFT Banner](./SWUIFT%20LOGO.png)

SWUIFT CLI v1 is jointly created by X-Lab, CSE and Khorasani Research Group, CSEE

The usage is strictly limited to the two groups.
To share externally request permission from Prof. Khorasani and/or Prof. Xiong

# SWUIFT User Manual

This guide is written for users who want to run SWUIFT experiments from a terminal, including users with limited programming background.

The workflow supports:
- Single-run execution from CLI
- Multi-run sequential experiments from JSON
- Full run metadata logging for reproducibility

## 1) What You Need

- A Linux machine, macOS machine, or Windows machine with terminal access
- Python 3.10 or newer
- Access to SWUIFT input files in `.mat` and/or `.csv` format
- A writable external output location **outside this project folder**

## 2) Verify Python and Pip

Run:

```bash
python3 --version
python3 -m pip --version
```

Expected:
- Python version is `3.10+`
- Pip is available

If `python3` is not found, install Python first and then re-run the commands.

## 3) Go to Project Folder

```bash
cd /path/to/SWUIFT_CLI_v1
pwd
```

Confirm that `pwd` prints the project directory.

## 4) Create and Activate Virtual Environment

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

After activation, your shell prompt usually shows `(.venv)`.

## 5) Install SWUIFT and Dependencies

```bash
python -m pip install --upgrade pip
pip install -e .
```

## 6) Verify Installation

Check CLI help:

```bash
swuift --help
```

Check key packages:

```bash
python -c "import numpy, scipy, h5py, numba, matplotlib, tqdm, imageio, av; print('OK')"
```

If you see `OK`, installation is successful.

## 7) Important Rule: Output Directory Must Be Outside Project

`output_dir` is required for every run and must be outside this repository.

Examples:
- Good: `/mnt/swuift_runs`
- Good: `/home/user/experiments/swuift_out`
- Bad: `./outputs` (inside project)

If you use an inside-project path, SWUIFT now throws an explicit error.

## 8) Run a Single Experiment from CLI

Use full explicit arguments:

```bash
swuift \
  --job-name baseline \
  --fire-prog /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/wildland_fire_matrix.mat \
  --domains /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/domain_matrix.mat \
  --landcover /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/binary_cover_landcover.mat \
  --homes /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/homes_matrix.mat \
  --lat /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/latitude.mat \
  --lon /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/longitude.mat \
  --harden-rad-map /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/radiation_matrix.mat \
  --harden-spo-map /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/spotting_matrix.mat \
  --water /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/water_matrix.mat \
  --wind /Users/utkarsh/Desktop/doe-wildfire/extracted_mat/wind.mat \
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

## 9) Run Multiple Experiments from JSON

A ready example file is included at:

- `jobs_example.json`

Run it:

```bash
swuift --batch ./jobs_example.json
```

## 10) JSON File Format (Sequential Jobs)

Top-level key must be `jobs`, containing an array:

```json
{
  "jobs": [
    {
      "name": "baseline",
      "fire_prog": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/wildland_fire_matrix.mat",
      "domains": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/domain_matrix.mat",
      "landcover": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/binary_cover_landcover.mat",
      "homes": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/homes_matrix.mat",
      "lat": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/latitude.mat",
      "lon": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/longitude.mat",
      "harden_rad_map": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/radiation_matrix.mat",
      "harden_spo_map": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/spotting_matrix.mat",
      "water": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/water_matrix.mat",
      "wind": "/Users/utkarsh/Desktop/doe-wildfire/extracted_mat/wind.mat",
      "grid_size": 10,
      "t_start": "2025-01-07 18:20",
      "t_end": "2025-01-08 14:20",
      "harden_rad": 70.0,
      "harden_spo": 70.0,
      "rad_ig_thresh": 14000.0,
      "rad_decay": 0.9,
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

Notes:
- Time steps are automatically derived from `t_start` and `t_end` using 5-minute intervals.
- If `t_start` or `t_end` is not quantized to a 5-minute boundary, SWUIFT raises:
  `not possible to calculate integer time steps`.
- Any non-wind input can be either `.mat` or `.csv` (mixed formats are allowed).
- For wind CSV mode, pass `--wind /path/to/wind.csv` and place companion files in the same directory:
  `wind_s.csv` + `wind_d.csv` (or `<wind_stem>_s.csv` + `<wind_stem>_d.csv`).

## 11) Output Controls

Defaults:
- `out_frames`, `out_video`, `out_gif`, `out_ig_plots`, `out_fire_csv`, `out_buildings_csv`: `true`
- `out_rad_steps`, `out_spo_steps`: `false`

You can disable outputs per job (JSON) or with CLI flags such as `--no-out-video`.

## 12) What Gets Saved Per Run

Each job creates:

```text
<output_dir>/<job_name>_<YYYYMMDD_HHMMSS>/
```

Always saved:
- `run_log.txt` (full console log + full command line)
- `run_params.json` (all options selected + timing + metadata)

Optional (based on output flags):
- `frames/`
- `simulation.mp4`
- `simulation.gif`
- `ig_pixel.png`
- `ig_structure.png`
- `fire_prog.csv`
- `zvector.csv`
- `timesteps/` (state/rad/spo step files)

## 13) Running in Background (`nohup`) on Linux

### Single-run nohup

```bash
nohup swuift --job-name baseline ... --output-dir /mnt/swuift_runs > /mnt/swuift_runs/nohup_single.log 2>&1 &
```

### Batch-run nohup

```bash
nohup swuift --batch ./jobs_example.json > /mnt/swuift_runs/nohup_batch.log 2>&1 &
```

Monitor progress:

```bash
tail -f /mnt/swuift_runs/nohup_batch.log
```

See background jobs:

```bash
jobs -l
```

Find process:

```bash
ps -ef | grep swuift | grep -v grep
```

## 14) Basic Troubleshooting

- `swuift: command not found`:
  - Activate virtual environment and reinstall with `pip install -e .`
- Missing package error:
  - Re-run `pip install -e .`
- Output directory error:
  - Set `output_dir` to a path outside the project (absolute path recommended)
- JSON validation error:
  - Check job name and missing fields listed in the error

## 15) Recommended Team Workflow

- Keep dataset files outside the repository
- Keep output directory on high-capacity storage
- Use JSON batch files for reproducible experiment sets
- Archive each run folder (`run_log.txt` + `run_params.json`) for auditability

## 16) Kernel Environment Variables

Both the CLI and the shared `swuift_core` physics package honor:

| Variable | Default | Description |
|----------|---------|-------------|
| `SWUIFT_APP_KERNEL_BACKEND` | `numba` | Set to `python` to force pure-Python kernels (useful for debugging or frozen builds) |
| `SWUIFT_APP_RADIATION_WORKERS` | `1` | Number of processes for parallel radiation chunking on multi-core hosts |

Example:

```bash
export SWUIFT_APP_RADIATION_WORKERS=4
export SWUIFT_APP_KERNEL_BACKEND=numba
swuift --job-name baseline ...
```

