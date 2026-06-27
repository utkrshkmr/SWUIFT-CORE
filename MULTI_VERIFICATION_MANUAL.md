# Multi-Fire CLI-vs-MATLAB Verification Manual

This manual explains how to verify SWUIFT CLI outputs against MATLAB outputs for one or more fires. 

The verification pipeline:

- Runs only MATLAB and CLI, not the desktop app.

## What You Need

You need:

- A copy of this repository.
- MATLAB installed and available from the terminal, or the path to the MATLAB executable.
- Python 3.11 with the built-in `venv` module.
- One CLI data folder per fire.
- One MATLAB data folder per fire.

## Get The Repository

If this is the first time using the project on a machine, clone the repository and enter the verification branch:

### Linux / macOS

```bash
cd /path/where/you/want/the/project
git clone https://github.com/utkrshkmr/SWUIFT-CORE.git
cd SWUIFT-CORE/doe-wildfire
git checkout multi_verification_wiring
git pull
```

### Windows PowerShell

```powershell
cd C:\path\where\you\want\the\project
git clone https://github.com/utkrshkmr/SWUIFT-CORE.git
cd SWUIFT-CORE\doe-wildfire
git checkout multi_verification_wiring
git pull
```

If the repository already exists on the machine, go to the repo folder and pull the latest changes:

### Linux / macOS

```bash
cd /path/to/SWUIFT-CORE/doe-wildfire
git checkout multi_verification_wiring
git pull
```

### Windows PowerShell

```powershell
cd C:\path\to\SWUIFT-CORE\doe-wildfire
git checkout multi_verification_wiring
git pull
```

After making documentation or code changes, push them back to the branch:

```bash
git status
git add <changed-files>
git commit -m "Describe the change"
git push
```

Do not commit large simulation outputs or local data folders. Verification outputs under `tools/compare/runs/` are ignored by git.

## Folder Layout

Create one folder for CLI data named `data`. Under it, create one folder per fire. MATLAB data should also be organized one folder per fire; this manual uses `matlab_data` for that side.

```text
data/
├── fire_name_1/
│   ├── wildland_fire_matrix.mat
│   ├── domain_matrix.mat
│   ├── binary_cover_landcover.mat
│   ├── homes_matrix.mat
│   ├── latitude.mat
│   ├── longitude.mat
│   ├── radiation_matrix.mat
│   ├── spotting_matrix.mat
│   ├── water_matrix.mat
│   └── wind.mat
└── fire_name_2/
    └── same file names

matlab_data/
├── fire_name_1/
│   ├── default_values.mat
│   ├── wind_eaton.mat
│   ├── eaton_inputs_all.mat
│   ├── fire_prog.mat
│   └── domains_mat.mat
└── fire_name_2/
    └── same file names
```

The CLI and MATLAB inputs are intentionally separate because their file formats are different. The verification pipeline checks that their contents are comparable before running the simulations.

## Create The Case Manifest

Create `verification_cases.yaml` in the repository root:

```yaml
fires:
  - name: eaton
    cli_data: data/eaton
    matlab_data: matlab_data/eaton
    t_start: "2025-01-07 18:20"
    t_end: "2025-01-08 14:20"
    grid_size: 10
    harden_rad: 70.0
    harden_spo: 70.0
    rad_ig_thresh: 14000.0
    rad_decay: 1.0
    brand_wind_coef: 30.0
    brand_wind_sd: 0.3
    brand_wind_sd_lat: 4.85
    seed_harden: 123456
    seed_spread: 10

  # Example only: repeat the block for another fire.
  # Make sure `name`, `cli_data`, and `matlab_data` match the actual input folders.
  # Here `eaton2` uses the same input folders as `eaton` but changes one parameter.
  - name: eaton2
    cli_data: data/eaton
    matlab_data: matlab_data/eaton
    t_start: "2025-01-07 18:20"
    t_end: "2025-01-08 14:20"
    grid_size: 10
    harden_rad: 70.0
    harden_spo: 70.0
    rad_ig_thresh: 14500.0
    rad_decay: 1.0
    brand_wind_coef: 30.0
    brand_wind_sd: 0.3
    brand_wind_sd_lat: 4.85
    seed_harden: 123456
    seed_spread: 10
```

Add one item under `fires:` for each fire.

Before running, double-check that each fire `name` corresponds to the intended CLI and MATLAB input folders. For example, if `name: marshall`, the paths should point to the Marshall input folders, not to Eaton inputs.

If a hyperparameter is omitted, the verification runner uses the current SWUIFT defaults. For clarity, keep all values explicit when you are preparing an official verification package.

## Set Up Python

### Linux

```bash
cd /home/csgrad/utkarshk/doe_fire_prediction/SWUIFT-CORE/doe-wildfire-multi_verification_wiring
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS

```bash
cd /path/to/doe-wildfire-multi_verification_wiring
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
cd C:\path\to\doe-wildfire-multi_verification_wiring
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Install And Check MATLAB

Download MATLAB from the MathWorks website:

1. Go to [https://www.mathworks.com/downloads/](https://www.mathworks.com/downloads/).
2. Sign in with the MathWorks account connected to your University at Buffalo identity.
3. If prompted for institutional login, use your `buffalo.edu` ID.
4. Download and install MATLAB for your operating system.
5. Open MATLAB once after installation and activate it using your `buffalo.edu` ID / University at Buffalo license.

After installation and activation, check that MATLAB can be accessed from the terminal.

### Linux

```bash
matlab -nodesktop -nosplash -r "disp('MATLAB_OK'); exit(0);"
```

If `matlab` is not found, use the full executable path when running verification:

```bash
python tools/compare/verify_cli_matlab.py --cases verification_cases.yaml --matlab-exe /path/to/matlab --fires all
```

### macOS

Common MATLAB path:

```bash
/Applications/MATLAB_R2024b.app/bin/matlab -nodesktop -nosplash -r "disp('MATLAB_OK'); exit(0);"
```

Run verification with:

```bash
python tools/compare/verify_cli_matlab.py --cases verification_cases.yaml --matlab-exe /Applications/MATLAB_R2024b.app/bin/matlab --fires all
```

Change `R2024b` to the version installed on the machine.

### Windows PowerShell

Common MATLAB path:

```powershell
& "C:\Program Files\MATLAB\R2024b\bin\matlab.exe" -nodesktop -nosplash -r "disp('MATLAB_OK'); exit(0);"
```

Run verification with:

```powershell
python tools\compare\verify_cli_matlab.py --cases verification_cases.yaml --matlab-exe "C:\Program Files\MATLAB\R2024b\bin\matlab.exe" --fires all
```

Change `R2024b` to the version installed on the machine.

## Run Verification

Run all fires:

```bash
python tools/compare/verify_cli_matlab.py --cases verification_cases.yaml --fires all
```

Run only one fire:

```bash
python tools/compare/verify_cli_matlab.py --cases verification_cases.yaml --fires eaton
```

Run multiple named fires:

```bash
python tools/compare/verify_cli_matlab.py --cases verification_cases.yaml --fires eaton marshall
```

Use compact binary CLI timestep dumps, which is the default:

```bash
python tools/compare/verify_cli_matlab.py --cases verification_cases.yaml --fires all
```

Use CSV CLI timestep dumps if the reviewer needs to open the files directly:

```bash
python tools/compare/verify_cli_matlab.py --cases verification_cases.yaml --fires all --dump-csv
```

Use lazy wind loading if memory is limited:

```bash
python tools/compare/verify_cli_matlab.py --cases verification_cases.yaml --fires all --lazy-wind
```

## What The Runner Produces

Outputs are written under:

```text
tools/compare/runs/verification_YYYYMMDD_HHMMSS/
```

Each fire gets its own folder:

```text
fire_name/
├── case.json
├── commands.json
├── logs/
│   ├── matlab.log
│   └── cli.log
├── preflight/
│   ├── input_similarity.json
│   ├── hyperparameters.json
│   └── problems.jsonl
├── matlab/
│   ├── work/
│   └── normalized_frame_state/
├── cli/
│   ├── fire_name_cli_YYYYMMDD_HHMMSS/
│   └── normalized_frame_state/
├── ignition_plots/
│   ├── matlab/
│   ├── cli/
│   └── inventory.json
└── comparisons/
    ├── per_step_stats.jsonl
    ├── frame_state_stats.jsonl
    ├── per_variable_summary.csv
    ├── ignition_plot_inventory.json
    └── first_deviations.json
```

## How To Read The Checks

### `preflight/input_similarity.json`

This compares input data before the simulations run.

It checks:

- Raster shapes match.
- Latitude and longitude vectors match.
- Fire ignition matrices have compatible values.
- Domain, landcover, homes, water, and hardening maps are comparable.
- Wind dataset shapes match, and the first wind slice matches when possible.

Important fields:

- `shape_match`: `true` means both sides have the same dimensions.
- `mismatched_count`: number of cells that are different.
- `max_abs_diff`: largest numeric difference found.
- `mean_abs_diff`: average numeric difference.

### `preflight/hyperparameters.json`

This compares requested hyperparameters with MATLAB defaults and CLI derived values.

It logs:

- `grid_size`
- `t_start`
- `t_end`
- hardening levels
- radiation ignition threshold
- radiation decay
- firebrand wind parameters
- random seeds
- derived values such as `maxstep`, `fstep`, `lstep`, `fb_str_ig`, `fb_veg_gen`, `fb_veg_ig`, `limrad`, and `limspo`

If this file shows a hyperparameter difference, simulation output differences may be caused by setup rather than the algorithm.

### `preflight/problems.jsonl`

This is a line-by-line problem log.

Each line is one JSON record. Fatal problems stop that fire case. Mismatches during comparison are not fatal and are logged elsewhere.

### `comparisons/per_step_stats.jsonl`

This is the main computational comparison file.

It compares these variables at every common timestep:

- `fire`
- `ignition`
- `radtotal`
- `out_fire`
- `zvector`

For each variable and timestep, it logs:

- Whether the shape matched.
- Whether the values matched.
- Number and fraction of mismatched cells.
- Maximum absolute difference.
- Mean absolute difference.
- p50, p95, and p99 absolute differences.
- Minimum and maximum values from MATLAB and CLI.
- A small sample of mismatched coordinates.

The algorithm does not stop at the first mismatch. It continues until the run ends.

### `comparisons/frame_state_stats.jsonl`

This compares normalized classified frame states. These are compact category matrices used to understand visible state differences:

- water
- vegetation
- vegetation ignited
- vegetation burned
- structure
- structure ignited
- structure fully developed
- structure burned out
- non-combustible

This file is useful when the raw computational arrays differ but the visible fire state appears similar, or vice versa.

### `comparisons/per_variable_summary.csv`

This is a compact table for spreadsheet review.

For each variable, it shows:

- Number of compared steps.
- Number of steps with mismatches.
- First deviation step.
- Worst mismatch count.
- Worst absolute difference.

### `comparisons/first_deviations.json`

This records the first timestep where each variable deviated.

Use this when you want to quickly locate where differences begin.

### `ignition_plots/`

This folder stores ignition plots from both implementations:

- MATLAB ignition plots
- CLI ignition plots

Video, GIF, and per-timestep frames are intentionally not generated. Ignition plots are kept because they are compact and useful for visual review.

## Troubleshooting

### MATLAB is not found

Use `--matlab-exe` with the full MATLAB executable path.

### A fire stops at preflight

Open:

```text
fire_name/preflight/problems.jsonl
```

Most failures are missing files, incompatible shapes, or unreadable `.mat` files.

### CLI fails but MATLAB runs

Open:

```text
fire_name/logs/cli.log
```

Also check:

```text
fire_name/commands.json
```

This shows the exact command that was run.

### MATLAB fails but CLI runs

Open:

```text
fire_name/logs/matlab.log
fire_name/matlab/work/matlab_console.log
```

### Outputs differ immediately

Check these first:

1. `preflight/hyperparameters.json`
2. `preflight/input_similarity.json`
3. `comparisons/first_deviations.json`

If inputs or hyperparameters differ, fix those before analyzing algorithm differences.

### Outputs differ later

Use:

```text
comparisons/per_step_stats.jsonl
comparisons/per_variable_summary.csv
```

Look for the first variable that deviates, then inspect later steps to see if the difference grows or remains small.

## What Is Safe To Delete

After reviewing a run, you can delete the whole run folder:

```text
tools/compare/runs/verification_YYYYMMDD_HHMMSS/
```

Do not delete the original `verification_data/` folders unless the fire input package is backed up elsewhere.
