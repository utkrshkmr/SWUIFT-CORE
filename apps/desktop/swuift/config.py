"""App configuration — re-exports core config plus GUI build helper."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np

from swuift_core.config import (
    AES,
    EE,
    ER,
    FB_DIST_MU,
    FB_DIST_SD,
    FB_MASS,
    FB_WIND_COEF_DEFAULT,
    FB_WIND_SD_DEFAULT,
    FB_WIND_SD_TRANSVERSE_DEFAULT,
    GRID_SIZE,
    HARDENING_RAD_DEFAULT,
    HARDENING_SPO_DEFAULT,
    RAD_ENERGY_IG_DEFAULT,
    RAD_RF_DEFAULT,
    SEED_HARDENING_DEFAULT,
    SEED_SPREAD_DEFAULT,
    SCONST,
    SWUIFTConfig,
    T_END_DEFAULT,
    T_START_DEFAULT,
    T_STEP_MIN,
    TMPR_DEFAULT,
)

__all__ = [
    "AES",
    "EE",
    "ER",
    "FB_DIST_MU",
    "FB_DIST_SD",
    "FB_MASS",
    "FB_WIND_COEF_DEFAULT",
    "FB_WIND_SD_DEFAULT",
    "FB_WIND_SD_TRANSVERSE_DEFAULT",
    "GRID_SIZE",
    "HARDENING_RAD_DEFAULT",
    "HARDENING_SPO_DEFAULT",
    "RAD_ENERGY_IG_DEFAULT",
    "RAD_RF_DEFAULT",
    "SEED_HARDENING_DEFAULT",
    "SEED_SPREAD_DEFAULT",
    "SCONST",
    "SWUIFTConfig",
    "T_END_DEFAULT",
    "T_START_DEFAULT",
    "T_STEP_MIN",
    "TMPR_DEFAULT",
    "build_config",
]


def build_config(
    defaults: Optional[dict],
    *,
    grid_size: Optional[int] = None,
    t_start: Optional[datetime] = None,
    t_end: Optional[datetime] = None,
    maxstep: Optional[int] = None,
    hardening_rad: Optional[float] = None,
    hardening_spo: Optional[float] = None,
    rad_energy_ig: Optional[float] = None,
    rad_rf: Optional[float] = None,
    fb_wind_coef: Optional[float] = None,
    fb_wind_sd: Optional[float] = None,
    fb_wind_sd_transverse: Optional[float] = None,
    seed_hardening: Optional[int] = None,
    seed_spread: Optional[int] = None,
) -> SWUIFTConfig:
    def _scalar_from_defaults(key: str, fallback: float) -> float:
        if defaults is not None and key in defaults:
            v = defaults[key]
            if hasattr(v, "item"):
                return float(v.item())
            return float(v)
        return float(fallback)

    def _vec_from_defaults(key: str, fallback: np.ndarray) -> np.ndarray:
        if defaults is not None and key in defaults:
            v = defaults[key]
            return np.asarray(v, dtype=np.float64).ravel()
        return np.asarray(fallback, dtype=np.float64).ravel()

    t_step_min = _scalar_from_defaults("t_step_min", T_STEP_MIN)
    if t_start is None:
        t_start = T_START_DEFAULT
    if t_end is None:
        t_end = T_END_DEFAULT
    aes = _scalar_from_defaults("aes", AES)
    ee = _scalar_from_defaults("ee", EE)
    er = _scalar_from_defaults("er", ER)
    sconst = _scalar_from_defaults("sconst", SCONST)
    rad_energy_ig_val = (
        float(rad_energy_ig)
        if rad_energy_ig is not None
        else _scalar_from_defaults("rad_energy_ig", RAD_ENERGY_IG_DEFAULT)
    )
    rad_rf_val = (
        float(rad_rf) if rad_rf is not None else _scalar_from_defaults("rad_rf", RAD_RF_DEFAULT)
    )
    fb_mass = _scalar_from_defaults("fb_mass", FB_MASS)
    fb_wind_coef_val = (
        float(fb_wind_coef)
        if fb_wind_coef is not None
        else _scalar_from_defaults("fb_wind_coef", FB_WIND_COEF_DEFAULT)
    )
    fb_wind_sd_val = (
        float(fb_wind_sd)
        if fb_wind_sd is not None
        else _scalar_from_defaults("fb_wind_sd", FB_WIND_SD_DEFAULT)
    )
    fb_wind_sd_transverse_val = (
        float(fb_wind_sd_transverse)
        if fb_wind_sd_transverse is not None
        else _scalar_from_defaults("fb_wind_sd_transverse", FB_WIND_SD_TRANSVERSE_DEFAULT)
    )
    fb_dist_mu = _scalar_from_defaults("fb_dist_mu", FB_DIST_MU)
    fb_dist_sd = _scalar_from_defaults("fb_dist_sd", FB_DIST_SD)
    veg_included = True
    if defaults is not None and "veg_included" in defaults:
        veg_included = bool(_scalar_from_defaults("veg_included", 1.0))
    tmpr_vec = _vec_from_defaults("tmpr", TMPR_DEFAULT)
    hardening_level_rad = (
        float(hardening_rad)
        if hardening_rad is not None
        else _scalar_from_defaults("hardening_level_rad", HARDENING_RAD_DEFAULT)
    )
    hardening_level_spo = (
        float(hardening_spo)
        if hardening_spo is not None
        else _scalar_from_defaults("hardening_level_spo", HARDENING_SPO_DEFAULT)
    )
    seed_h = int(seed_hardening) if seed_hardening is not None else int(SEED_HARDENING_DEFAULT)
    seed_s = int(seed_spread) if seed_spread is not None else int(SEED_SPREAD_DEFAULT)
    return SWUIFTConfig(
        grid_size=grid_size if grid_size is not None else GRID_SIZE,
        t_start=t_start,
        t_end=t_end,
        t_step_min=t_step_min,
        maxstep=maxstep,
        aes=aes,
        ee=ee,
        er=er,
        sconst=sconst,
        rad_energy_ig=rad_energy_ig_val,
        rad_rf=rad_rf_val,
        fb_mass=fb_mass,
        fb_wind_coef=fb_wind_coef_val,
        fb_wind_sd=fb_wind_sd_val,
        fb_wind_sd_transverse=fb_wind_sd_transverse_val,
        fb_dist_mu=fb_dist_mu,
        fb_dist_sd=fb_dist_sd,
        veg_included=veg_included,
        tmpr=tmpr_vec,
        hardening_level_rad=hardening_level_rad,
        hardening_level_spo=hardening_level_spo,
        seed_hardening=seed_h,
        seed_spread=seed_s,
    )
