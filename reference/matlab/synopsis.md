# Synopsis — `00_SWUIFT-main` (after renumbering)

**Position in lineage:** **0 — Reference baseline** (root of the tree)  
**Predecessor:** None (original SWUIFT distribution)  
**Successor:** `01_SWUIFT_PY_APP` / `01a_PROTOTYPE_APP` (Python desktop GUI port of this model)

## What this folder is

The authoritative **MATLAB** implementation of SWUIFT (Simulating Wildfire-Urban Interface Fire Transmission), plus Eaton scenario input bundles used by all later Python variants.

## Contents

| Asset | Purpose |
|-------|---------|
| `SWUIFT_V4.m` | Main simulation driver |
| `f_spread.m` | Fire-spread physics (brands, radiation, ignition) |
| `f_plots.m` | Plotting helpers |
| `default_values.mat`, `domains_mat.mat`, `eaton_inputs_all.mat`, `fire_prog.mat`, `wind_eaton.mat` | Eaton reference inputs |
| `SWUIFTv2_Py.zip` | Early **2022** Python prototype (`main.py`, Excel-driven workflow) — historical only; superseded by `01_SWUIFT_PY_APP` |

## Performance / implementation notes

- Full-grid MATLAB loops for brand generation and transport (no sparse/Numba optimizations).
- Wind stored in HDF5 v7.3 (`wind_eaton.mat`, ~7 GB).
- All later folders target **numerical parity** with this reference while accelerating hot paths in Python.

## Optimizations in this project

None relative to itself — this is the correctness baseline. Later projects add vectorization, Numba, sparse radiation windows, and parallel I/O.
