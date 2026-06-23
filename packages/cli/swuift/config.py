"""CLI configuration — maps CLI/JSON field names to swuift_core canonical config."""

from __future__ import annotations

from datetime import datetime

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
    SWUIFTConfig as _CoreSWUIFTConfig,
    T_END_DEFAULT,
    T_START_DEFAULT,
    T_STEP_MIN,
    TMPR_DEFAULT,
)

# CLI-facing alias names for defaults (backward compatible with JSON jobs)
RAD_IG_THRESH_DEFAULT = RAD_ENERGY_IG_DEFAULT
RAD_DECAY_DEFAULT = RAD_RF_DEFAULT
SEED_HARDEN_DEFAULT = SEED_HARDENING_DEFAULT
BRAND_WIND_COEF_DEFAULT = FB_WIND_COEF_DEFAULT
BRAND_WIND_SD_DEFAULT = FB_WIND_SD_DEFAULT
BRAND_WIND_SD_LAT_DEFAULT = FB_WIND_SD_TRANSVERSE_DEFAULT


class SWUIFTConfig(_CoreSWUIFTConfig):
    """Core config with CLI property aliases for logging and legacy callers."""

    @property
    def rad_ig_thresh(self) -> float:
        return self.rad_energy_ig

    @property
    def rad_decay(self) -> float:
        return self.rad_rf

    @property
    def brand_wind_coef(self) -> float:
        return self.fb_wind_coef

    @property
    def brand_wind_sd(self) -> float:
        return self.fb_wind_sd

    @property
    def brand_wind_sd_lat(self) -> float:
        return self.fb_wind_sd_transverse

    @property
    def harden_rad(self) -> float:
        return self.hardening_level_rad

    @property
    def harden_spo(self) -> float:
        return self.hardening_level_spo

    @property
    def seed_harden(self) -> int:
        return self.seed_hardening


def build_config(
    *,
    grid_size: int,
    t_start: datetime,
    t_end: datetime,
    harden_rad: float,
    harden_spo: float,
    rad_ig_thresh: float,
    rad_decay: float,
    brand_wind_coef: float,
    brand_wind_sd: float,
    brand_wind_sd_lat: float,
    seed_harden: int,
    seed_spread: int,
) -> SWUIFTConfig:
    """Construct config from explicit CLI/JSON values."""
    if t_end < t_start:
        raise ValueError("t_end must be greater than or equal to t_start.")

    step_seconds = int(T_STEP_MIN * 60)
    start_seconds = t_start.minute * 60 + t_start.second
    end_seconds = t_end.minute * 60 + t_end.second
    if t_start.microsecond != 0 or t_end.microsecond != 0:
        raise ValueError(
            "not possible to calculate integer time steps: "
            "timestamps must not include fractional seconds."
        )
    if start_seconds % step_seconds != 0 or end_seconds % step_seconds != 0:
        raise ValueError(
            "not possible to calculate integer time steps: "
            "t_start and t_end must be quantized to 5-minute intervals."
        )

    total_seconds = int((t_end - t_start).total_seconds())
    if total_seconds % step_seconds != 0:
        raise ValueError(
            "not possible to calculate integer time steps: "
            "time window must be divisible by 5-minute intervals."
        )
    derived_max_steps = total_seconds // step_seconds + 1

    return SWUIFTConfig(
        grid_size=int(grid_size),
        t_start=t_start,
        t_end=t_end,
        t_step_min=T_STEP_MIN,
        maxstep=int(derived_max_steps),
        aes=AES,
        ee=EE,
        er=ER,
        sconst=SCONST,
        rad_energy_ig=float(rad_ig_thresh),
        rad_rf=float(rad_decay),
        fb_mass=FB_MASS,
        fb_wind_coef=float(brand_wind_coef),
        fb_wind_sd=float(brand_wind_sd),
        fb_wind_sd_transverse=float(brand_wind_sd_lat),
        fb_dist_mu=FB_DIST_MU,
        fb_dist_sd=FB_DIST_SD,
        veg_included=True,
        tmpr=TMPR_DEFAULT.copy(),
        hardening_level_rad=float(harden_rad),
        hardening_level_spo=float(harden_spo),
        seed_hardening=int(seed_harden),
        seed_spread=int(seed_spread),
    )
