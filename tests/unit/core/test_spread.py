"""Tests for swuift_core physics functions on small synthetic grids."""

import numpy as np
import pytest

from swuift_core.config import SWUIFTConfig
from swuift_core.hardening import apply_hardening
from swuift_core.kernels import kernel_backend, radiation_kernel
from swuift_core.spread import radiation_ig


def _small_cfg(**overrides):
    defaults = dict(
        grid_size=10,
        t_step_min=5.0,
        fb_mass=0.5,
        aes=9.0,
        ee=0.9,
        er=0.9,
        sconst=5.67e-8,
        rad_energy_ig=12500.0,
        rad_rf=0.9,
        fb_wind_coef=6.0,
        fb_wind_sd=0.8,
        fb_wind_sd_transverse=5.0,
        fb_dist_mu=0.0,
        fb_dist_sd=1.0,
        veg_included=True,
        tmpr=np.linspace(20, 1100, 37),
    )
    defaults.update(overrides)
    return SWUIFTConfig(**defaults)


class TestRadiationIg:
    def test_basic_ignition(self):
        n = 5
        ignition = np.zeros((n, n))
        binary_cover = np.ones((n, n))
        radtotal = np.zeros((n, n))
        criteria_rad = np.zeros((n, n))
        radtotal[2, 3] = 20000.0
        criteria_rad[2, 3] = 0.1
        result = radiation_ig(ignition, binary_cover, radtotal, 12500.0, criteria_rad, 0.3)
        assert result[2, 3] == 1
        assert result.sum() == 1

    def test_no_ignition_below_threshold(self):
        n = 5
        ignition = np.zeros((n, n))
        binary_cover = np.ones((n, n))
        radtotal = np.full((n, n), 5000.0)
        criteria_rad = np.full((n, n), 0.1)
        result = radiation_ig(ignition, binary_cover, radtotal, 12500.0, criteria_rad, 0.3)
        assert result.sum() == 0


class TestRadiationKernel:
    def test_single_burning_cell(self):
        rows, cols = 5, 5
        grid_size = 10.0
        binary_cover = np.ones((rows, cols))
        fire = np.zeros((rows, cols))
        fire[2, 2] = 5.0
        tmpr = np.linspace(20, 1100, 37)
        radtotal = np.zeros((rows, cols))
        fstep, lstep = 5, 36
        rad_rf = 0.9
        wind_d_2d = np.full((rows, cols), 0.0)
        aes, ee, er = 9.0, 0.9, 0.9
        sconst = 5.67e-8
        emissivity = 1.0 / (1.0 / ee + 1.0 / er - 1.0)
        source_mask = (binary_cover > 0) & (fire >= fstep) & (fire <= lstep)
        src = np.argwhere(source_mask)
        source_rows = src[:, 0].astype(np.int64)
        source_cols = src[:, 1].astype(np.int64)
        fire_vals = fire[source_mask].copy()
        wind_dirs = wind_d_2d[source_mask].copy()
        result = radiation_kernel(
            source_rows, source_cols, fire_vals, wind_dirs,
            rows, cols, grid_size,
            radtotal, tmpr, rad_rf,
            aes, emissivity, sconst,
        )
        assert result[2, 2] == 0.0
        assert result[2, 3] > 0 or result[2, 4] > 0

    def test_python_fallback(self, monkeypatch):
        monkeypatch.setenv("SWUIFT_APP_KERNEL_BACKEND", "python")
        import importlib
        import swuift_core.kernels as kernels_mod
        importlib.reload(kernels_mod)
        assert kernels_mod.kernel_backend() == "python"
        importlib.reload(kernels_mod)


class TestHardening:
    def test_hardening_basic(self):
        cfg = _small_cfg()
        rows, cols = 10, 10
        binary_cover = np.zeros((rows, cols))
        binary_cover[2:5, 2:5] = 1
        homes_mat = np.zeros((rows, cols))
        homes_mat[2:5, 2:5] = 1
        hardening_mat_rad = np.zeros((rows, cols))
        hardening_mat_rad[2:5, 2:5] = 2
        hardening_mat_spo = np.zeros((rows, cols))
        hardening_mat_spo[2:5, 2:5] = 2
        knownig_mat = np.zeros((rows, cols))
        lati = np.arange(rows, dtype=np.float64)
        long = np.arange(cols, dtype=np.float64)
        result = apply_hardening(
            cfg, binary_cover, homes_mat,
            hardening_mat_rad, hardening_mat_spo,
            knownig_mat, lati, long,
        )
        assert np.any(result.criteria_rad[2:5, 2:5] > 0)
        assert result.criteria_rad.shape == (rows, cols)
