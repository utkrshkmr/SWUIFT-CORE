"""Tests for mixed .mat/.csv input loading and compatibility checks."""

from __future__ import annotations

import numpy as np
import pytest
import scipy.io as sio

from swuift.data_loader import load_all_extracted


def _write_csv(path, arr: np.ndarray) -> None:
    np.savetxt(path, arr, delimiter=",")


def test_load_all_extracted_accepts_mixed_mat_and_csv(tmp_path):
    rows, cols = 2, 3
    raster = np.arange(rows * cols, dtype=np.float64).reshape(rows, cols)
    lat = np.array([34.10, 34.11], dtype=np.float64)
    lon = np.array([-118.30, -118.29, -118.28], dtype=np.float64)

    fire_prog_mat = tmp_path / "wildland_fire_matrix.mat"
    domains_csv = tmp_path / "domains.csv"
    landcover_mat = tmp_path / "binary_cover_landcover.mat"
    homes_csv = tmp_path / "homes.csv"
    lat_mat = tmp_path / "latitude.mat"
    lon_csv = tmp_path / "longitude.csv"
    harden_rad_mat = tmp_path / "radiation_matrix.mat"
    harden_spo_csv = tmp_path / "spotting_matrix.csv"
    water_mat = tmp_path / "water_matrix.mat"

    sio.savemat(fire_prog_mat, {"wildland_fire_matrix": raster})
    _write_csv(domains_csv, raster)
    sio.savemat(landcover_mat, {"binary_cover": raster})
    _write_csv(homes_csv, raster)
    sio.savemat(lat_mat, {"lati": lat})
    _write_csv(lon_csv, lon)
    sio.savemat(harden_rad_mat, {"hardening_mat_rad": raster})
    _write_csv(harden_spo_csv, raster)
    sio.savemat(water_mat, {"water": raster})

    # Wind CSV mode: marker + companion speed/direction files.
    wind_marker = tmp_path / "wind.csv"
    wind_s_csv = tmp_path / "wind_s.csv"
    wind_d_csv = tmp_path / "wind_d.csv"
    wind_marker.write_text("wind csv marker", encoding="utf-8")
    _write_csv(wind_s_csv, np.ones((rows, cols), dtype=np.float64))
    _write_csv(wind_d_csv, np.zeros((rows, cols), dtype=np.float64))

    data = load_all_extracted(
        wildland_fire_matrix_file=str(fire_prog_mat),
        domain_matrix_file=str(domains_csv),
        binary_cover_file=str(landcover_mat),
        homes_matrix_file=str(homes_csv),
        latitude_file=str(lat_mat),
        longitude_file=str(lon_csv),
        radiation_matrix_file=str(harden_rad_mat),
        spotting_matrix_file=str(harden_spo_csv),
        water_matrix_file=str(water_mat),
        wind_file=str(wind_marker),
        preload_wind=True,
    )
    try:
        assert data.rows == rows
        assert data.cols == cols
        ws, wd = data.wind.get_slice(0)
        assert ws.shape == (rows, cols)
        assert wd.shape == (rows, cols)
    finally:
        data.close()


def test_load_all_extracted_rejects_dimension_mismatch(tmp_path):
    rows, cols = 2, 3
    raster = np.arange(rows * cols, dtype=np.float64).reshape(rows, cols)
    bad_raster = np.arange(rows * 4, dtype=np.float64).reshape(rows, 4)
    lat = np.array([34.10, 34.11], dtype=np.float64)
    lon = np.array([-118.30, -118.29, -118.28], dtype=np.float64)

    sio.savemat(tmp_path / "wildland_fire_matrix.mat", {"wildland_fire_matrix": raster})
    sio.savemat(tmp_path / "domains.mat", {"domains_mat": raster})
    sio.savemat(tmp_path / "binary_cover.mat", {"binary_cover": raster})
    sio.savemat(tmp_path / "homes.mat", {"homes_mat": bad_raster})
    sio.savemat(tmp_path / "latitude.mat", {"lati": lat})
    sio.savemat(tmp_path / "longitude.mat", {"long": lon})
    sio.savemat(tmp_path / "rad.mat", {"hardening_mat_rad": raster})
    sio.savemat(tmp_path / "spo.mat", {"hardening_mat_spo": raster})
    sio.savemat(tmp_path / "water.mat", {"water": raster})

    wind_marker = tmp_path / "wind.csv"
    wind_marker.write_text("wind csv marker", encoding="utf-8")
    _write_csv(tmp_path / "wind_s.csv", np.ones((rows, cols), dtype=np.float64))
    _write_csv(tmp_path / "wind_d.csv", np.zeros((rows, cols), dtype=np.float64))

    with pytest.raises(ValueError, match="Incompatible shape"):
        load_all_extracted(
            wildland_fire_matrix_file=str(tmp_path / "wildland_fire_matrix.mat"),
            domain_matrix_file=str(tmp_path / "domains.mat"),
            binary_cover_file=str(tmp_path / "binary_cover.mat"),
            homes_matrix_file=str(tmp_path / "homes.mat"),
            latitude_file=str(tmp_path / "latitude.mat"),
            longitude_file=str(tmp_path / "longitude.mat"),
            radiation_matrix_file=str(tmp_path / "rad.mat"),
            spotting_matrix_file=str(tmp_path / "spo.mat"),
            water_matrix_file=str(tmp_path / "water.mat"),
            wind_file=str(wind_marker),
            preload_wind=True,
        )
