# SWUIFT Desktop App — User Manual

SWUIFT (Simulating Wildfire-Urban Interface Fire Transmission) models wildfire spread through vegetation and urban structures. This manual covers the **desktop GUI** application.

- **Project overview:** [README.md](README.md)
- **Command-line version:** [CLI_MANUAL.md](CLI_MANUAL.md)

---

## 1. Introduction

The desktop app provides a graphical interface for configuring simulations, queuing multiple runs, and monitoring progress. The main window title is **SWUIFT – Wildfire Spread Simulation**.

Typical workflow:

1. Select input data files on the **Data Inputs** tab.
2. Set simulation time, physics parameters, and output options on the other tabs.
3. Click **Add to Queue** to snapshot the current settings as a job.
4. Click **Run All** to execute queued jobs sequentially.
5. Open the output folder listed in the Job Queue table when each job finishes.

---

## 2. Installation and Launch

### Development (from source)

```bash
cd doe-wildfire
python3 -m venv .venv && source .venv/bin/activate
pip install -r apps/desktop/requirements_app.txt
cd apps/desktop
python swuift_app.py
```

### Packaged builds

Pre-built installers are produced with PyInstaller:

- **macOS:** `build_macos.sh` → `dist/SWUIFT.app` and `dist/SWUIFT_macOS_arm64.dmg`
- **Windows:** `build_windows.bat` → `dist/SWUIFT/SWUIFT.exe` (optional Inno Setup installer via `swuift_setup.iss`)

Launch the `.app` or `.exe` directly. No terminal is required.

---

## 3. Main Window Layout

The window is divided into three areas:

```
┌─────────────────────────────────────────────────────────┐
│  Configuration Tabs (6 tabs)                            │
│  Data Inputs | Grid & Time | Radiation | ...            │
├─────────────────────────────────────────────────────────┤
│  Simulation Log                          [Clear]        │
│  (read-only console output from the active job)         │
├─────────────────────────────────────────────────────────┤
│  Job Queue (dock, movable)                              │
│  [Add to Queue] [Run All] [Cancel] ...                  │
│  Progress bar + queue table                             │
└─────────────────────────────────────────────────────────┘
```

| Area | Description |
|------|-------------|
| **Configuration tabs** | All simulation parameters. Each tab has a **Reset to Defaults** button. |
| **Simulation Log** | Live stdout/stderr from the running job. Use **Clear** to empty the view. |
| **Job Queue** | List of pending, running, completed, and failed jobs. Dock can be moved or floated. |

Default window size: 1100 × 800 pixels. Layout and last-used settings are restored when you reopen the app.

---

## 4. Configuration Tabs

### 4.1 Data Inputs

All ten inputs are required before a job can be added to the queue. Use **Browse…** to select `.mat` files.

| Label | Typical file | Contents |
|-------|--------------|----------|
| Wildland Fire Matrix | `wildland_fire_matrix.mat` | Known ignition / fire progression (`knownig_mat`) |
| Domain Matrix | `domain_matrix.mat` | Domain classification raster (`domains_mat`) |
| Binary Cover | `binary_cover_landcover.mat` | Vegetation vs structure raster (`binary_cover`) |
| Homes Matrix | `homes_matrix.mat` | Building ID raster (`homes_mat`) |
| Latitude | `latitude.mat` | 1-D latitude vector (length = rows, variable `lati`) |
| Longitude | `longitude.mat` | 1-D longitude vector (length = cols, variable `long`) |
| Radiation Matrix | `radiation_matrix.mat` | Per-cell radiation hardening (`hardening_mat_rad`) |
| Spotting Matrix | `spotting_matrix.mat` | Per-cell spotting hardening (`hardening_mat_spo`) |
| Water Matrix | `water_matrix.mat` | Non-burnable water cells (`water`) |
| Wind File | `wind.mat` | HDF5/v7.3 file with `wind_s` and `wind_d` arrays |

Hover over each label for a short tooltip describing the expected file format.

Pre-extracted files for the Eaton scenario live in `extracted_mat/` at the repo root (see [README.md](README.md) § Data Setup).

### 4.2 Grid & Time

| Control | Default | Notes |
|---------|---------|-------|
| Simulation Start | 2025-01-07 18:20 | Calendar popup; format `yyyy-MM-dd HH:mm` |
| Simulation End | 2025-01-08 14:20 | Must be after start time |

Below the pickers, an info line shows the calculated step count, duration in hours, **5-minute timestep**, and **10 m grid** (fixed internally).

End time must be after start time. If invalid, a red warning is shown.

### 4.3 Radiation

| Control | Default | Range |
|---------|---------|-------|
| Ignition Threshold (W/m²) | 14000.0 | 0 – 100000 (step 100) |
| Radiation Reduction Factor (0–1) | 1.0 | 0 – 1 (step 0.01) |

Lower ignition threshold makes structures easier to ignite by radiation. Reduction factor scales radiant flux before the ignition test (1.0 = no reduction).

### 4.4 Firebrands

| Control | Default | Range |
|---------|---------|-------|
| Wind Coefficient | 30.0 | 0 – 1000 |
| Wind Std Dev (longitudinal) | 0.3 | 0 – 100 |
| Wind Std Dev (transverse) | 4.85 | 0 – 100 |

These control wind-driven firebrand transport distance and stochastic scatter in the along-wind and cross-wind directions.

### 4.5 Hardening & Seeds

| Control | Default | Range |
|---------|---------|-------|
| Radiation Hardening Level (%) | 70.0 | 0 – 100 |
| Spotting Hardening Level (%) | 70.0 | 0 – 100 |
| Seed — Hardening RNG | 123456 | 0 – 2147483647 |
| Seed — Spread RNG | 10 | 0 – 2147483647 |

Hardening levels set the percentage of structures that resist radiation or spotting ignition. Use the same seeds to reproduce stochastic results.

### 4.6 Output Settings

| Control | Default | Notes |
|---------|---------|-------|
| Output Folder | `{app_dir}/outputs` | Folder picker; all runs go into timestamped subfolders |
| Generate Video / GIF | On | Creates `simulation.mp4` and `simulation.gif` after the run |
| Frame DPI | 600 | 72 – 1200 (step 50); resolution of PNG frames and video |
| Dump Interval (0 = off) | 0 | Save full per-step state every N timesteps |
| Dump as CSV | Off | When dumps enabled, use CSV instead of binary `.npy` (slower) |
| Lazy Wind (low RAM mode) | Off | Read wind from disk on demand (~7 GB RAM saved, slower) |
| Export radiation flux CSV per frame | Off | `radiation_csv/{step}.csv` per timestep |
| Export spotting (brands) CSV per frame | Off | `spotting_csv/{step}.csv` per timestep |

---

## 5. Job Queue

### Buttons

| Button | Action |
|--------|--------|
| **Add to Queue** | Validates data inputs, warns about RAM if Lazy Wind is off, snapshots current tab settings as a new **Pending** job |
| **Run All** | Runs all Pending jobs one after another |
| **Cancel** | Cancels the selected Running job, or stops all jobs if none is selected |
| **Remove Selected** | Removes the selected **Pending** job only |
| **Duplicate Selected** | Copies the selected job as a new Pending entry at the end of the queue |
| **Clear Queue** | Removes all jobs (blocked while a simulation is running) |

### Queue table columns

| Column | Description |
|--------|-------------|
| # | Job ID |
| Status | `Pending`, `Running`, `Done`, or `Failed` |
| Phase | Current stage: Loading data, Building config, Simulating, Generating video, Done |
| Elapsed / ETA | Time elapsed and estimated time remaining |
| Output Dir | Path to the run output folder (hover for full path) |

### Context menu (right-click on a job)

- **Pending jobs:** Duplicate Job, Remove Job, Move Up, Move Down
- **Failed jobs:** Show Error…

Double-click a failed job to open the error dialog.

### Typical workflow

1. Configure all tabs.
2. **Add to Queue**.
3. Optionally change parameters and **Add to Queue** again for parameter sweeps, or use **Duplicate Selected** on an existing job and edit settings before running.
4. **Run All**.
5. Watch the Simulation Log and progress bar.
6. When status is **Done**, open the Output Dir shown in the table.

---

## 6. File Menu and Keyboard Shortcuts

| Menu item | Shortcut | Action |
|-----------|----------|--------|
| Save Settings as JSON… | Ctrl+S | Save all tab settings to a JSON file |
| Load Settings from JSON… | Ctrl+O | Restore settings from a saved JSON file |
| Quit | Ctrl+Q | Exit the application |

### Settings JSON structure

```json
{
  "data": { "wildland_fire_matrix": "...", ... },
  "grid": { "t_start": "2025-01-07T18:20:00", "t_end": "...", "maxstep": null },
  "radiation": { "rad_energy_ig": 14000.0, "rad_rf": 1.0 },
  "firebrands": { "fb_wind_coef": 30.0, "fb_wind_sd": 0.3, "fb_wind_sd_transverse": 4.85 },
  "hardening": { "hardening_rad": 70.0, "hardening_spo": 70.0, "seed_hardening": 123456, "seed_spread": 10 },
  "output": { "output_dir": "...", "make_video": true, "dpi_hires": 600, ... }
}
```

Save settings JSON files to reuse configurations across sessions or share them with colleagues.

---

## 7. Output Files

Each run creates a timestamped folder under your chosen output directory:

```
{output_folder}/run_YYYYMMDD_HHMMSS/
```

If a name collision occurs, suffixes `-2`, `-3`, etc. are appended.

### Always produced

| File / folder | Description |
|---------------|-------------|
| `run_log.txt` | Full simulation log with per-step messages and runtime |
| `frame_state/state_XXXX.npy` | Normalized frame-state array per timestep |
| `frame_csvs/XXXX.csv` | Frame-state CSV per timestep |
| `fire_prog.csv` | Fire progression matrix |
| `zvector.csv` | Structure ignition summary |
| `ig_pixel.png` | Pixel ignition plot |
| `ig_structure.png` | Structure ignition plot |

### Optional (controlled by Output Settings)

| Option enabled | Output |
|----------------|--------|
| Generate Video / GIF | `frames/0001.png`, … → `simulation.mp4`, `simulation.gif` |
| Dump Interval > 0 | `timesteps/tXXXXXX/` with per-step arrays (`.npy` or `.csv`) |
| Export radiation flux CSV | `radiation_csv/XXXX.csv` |
| Export spotting CSV | `spotting_csv/XXXX.csv` |

### Simulation phases

While running, the Phase column shows:

`Loading data` → `Building config` → `Simulating` → (`Generating video` if enabled) → `Done`

---

## 8. Warnings and Dialogs

| Dialog | When |
|--------|------|
| **Invalid Data Inputs** | Missing or invalid `.mat` files when adding to queue |
| **RAM Usage Warning** | Lazy Wind is unchecked; wind preload uses ~7 GB RAM |
| **Nothing to Run** | Run All with an empty pending queue |
| **Cancel Job / Cancel All Jobs** | Confirmation before stopping |
| **Job Cancelled** | Ask whether to continue remaining queued jobs |
| **All Jobs Complete** | Shown when the entire queue finishes |
| **Cannot Remove / Cannot Clear** | Attempt to modify queue while a job is running |
| **Error – Job #N** | Failed job details with expandable traceback |
| **Simulation Running** | Quit while a job is still running |

---

## 9. Tips

- **Parameter sweeps:** Add a job, change one parameter (e.g. hardening level), add again, then Run All.
- **Reuse settings:** File → Save Settings as JSON… after configuring; load next session with Ctrl+O.
- **Session persistence:** Window layout and last settings are saved automatically on quit.
- **Low RAM machines:** Enable **Lazy Wind** on the Output Settings tab (slower but avoids ~7 GB preload).
- **Debugging:** Set Dump Interval to 1 and enable Dump as CSV for per-step state inspection.

---

## 10. Troubleshooting

| Problem | Solution |
|---------|----------|
| "Missing or invalid files" on Add to Queue | Ensure all ten `.mat` paths exist and are readable |
| Out of memory during data load | Enable **Lazy Wind**; close other applications |
| Video not generated | Check **Generate Video / GIF** is enabled; ffmpeg must be available (bundled in PyInstaller builds) |
| Job failed with traceback | Right-click job → Show Error…; check Simulation Log |
| Slow simulation | Expected for full 241-step Eaton runs; use shorter time window for tests |
| Cannot find output | Check Output Dir column in queue table; default is `apps/desktop/outputs/` |

For batch or scripted runs, see [CLI_MANUAL.md](CLI_MANUAL.md).
