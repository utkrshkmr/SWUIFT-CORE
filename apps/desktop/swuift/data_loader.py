from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Tuple
import h5py
import numpy as np
import scipy.io as sio

def _load_v5(path: str, squeeze: bool=True) -> dict:
    return sio.loadmat(path, squeeze_me=squeeze)

def _load_single_v5(path: str, var_name: str) -> np.ndarray:
    d = _load_v5(path, squeeze=True)
    if var_name not in d:
        raise KeyError(f'Variable {var_name!r} not found in {path!r}')
    arr = np.asarray(d[var_name], dtype=np.float64)
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr.ravel()
    return arr

def load_default_values(data_dir: str) -> dict:
    path = os.path.join(data_dir, 'default_values.mat')
    return _load_v5(path)

def load_domains(data_dir: str) -> np.ndarray:
    path = os.path.join(data_dir, 'domains_mat.mat')
    d = _load_v5(path)
    return np.asarray(d['domains_mat'], dtype=np.float64)

def load_eaton_inputs(data_dir: str) -> dict:
    path = os.path.join(data_dir, 'eaton_inputs_all.mat')
    d = _load_v5(path)
    out = {}
    for key in ('binary_cover', 'hardening_mat_rad', 'hardening_mat_spo', 'homes_mat', 'water'):
        out[key] = np.asarray(d[key], dtype=np.float64)
    out['lati'] = np.asarray(d['lati'], dtype=np.float64).ravel()
    out['long'] = np.asarray(d['long'], dtype=np.float64).ravel()
    return out

def load_fire_prog(data_dir: str) -> np.ndarray:
    path = os.path.join(data_dir, 'fire_prog.mat')
    d = _load_v5(path)
    return np.asarray(d['fire_prog'], dtype=np.float64)

class WindData:

    def __init__(self, path: str, preload: bool=True):
        if os.path.isdir(path):
            path = os.path.join(path, 'wind_eaton.mat')
        self._h5 = h5py.File(path, 'r')
        self._ws = self._h5['wind_s']
        self._wd = self._h5['wind_d']
        self.n_timesteps = self._ws.shape[0]
        self._preloaded = False
        self.wind_s_all: np.ndarray | None = None
        self.wind_d_all: np.ndarray | None = None
        self._cache: dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        if preload:
            self._preload()
        else:
            import warnings
            warnings.warn('Lazy wind mode enabled: wind slices are read from HDF5 on demand. This saves RAM but is much slower per timestep than preloaded wind.', RuntimeWarning, stacklevel=3)

    def _preload(self):
        raw_s = self._ws[()]
        raw_d = self._wd[()]
        self.wind_s_all = np.ascontiguousarray(np.transpose(raw_s, (2, 1, 0)))
        self.wind_d_all = np.ascontiguousarray(np.transpose(raw_d, (2, 1, 0)))
        self._preloaded = True

    def get_slice(self, tstep_0based: int) -> Tuple[np.ndarray, np.ndarray]:
        if self._preloaded:
            return (self.wind_s_all[:, :, tstep_0based], self.wind_d_all[:, :, tstep_0based])
        if tstep_0based in self._cache:
            return self._cache[tstep_0based]
        ws = np.ascontiguousarray(self._ws[tstep_0based, :, :].T)
        wd = np.ascontiguousarray(self._wd[tstep_0based, :, :].T)
        self._cache[tstep_0based] = (ws, wd)
        return (ws, wd)

    def close(self):
        self._h5.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

@dataclass
class SWUIFTData:
    binary_cover: np.ndarray = field(repr=False)
    hardening_mat_rad: np.ndarray = field(repr=False)
    hardening_mat_spo: np.ndarray = field(repr=False)
    homes_mat: np.ndarray = field(repr=False)
    water: np.ndarray = field(repr=False)
    lati: np.ndarray = field(repr=False)
    long: np.ndarray = field(repr=False)
    domains_mat: np.ndarray = field(repr=False)
    knownig_mat: np.ndarray = field(repr=False)
    wind: WindData = field(repr=False)
    rows: int = 0
    cols: int = 0

    def close(self):
        self.wind.close()

def load_all(data_dir: str, preload_wind: bool=True) -> Tuple[dict, SWUIFTData]:
    defaults = load_default_values(data_dir)
    domains = load_domains(data_dir)
    eaton = load_eaton_inputs(data_dir)
    fire_prog = load_fire_prog(data_dir)
    wind = WindData(data_dir, preload=preload_wind)
    rows, cols = eaton['binary_cover'].shape
    data = SWUIFTData(binary_cover=eaton['binary_cover'], hardening_mat_rad=eaton['hardening_mat_rad'], hardening_mat_spo=eaton['hardening_mat_spo'], homes_mat=eaton['homes_mat'], water=eaton['water'], lati=eaton['lati'], long=eaton['long'], domains_mat=domains, knownig_mat=fire_prog.copy(), wind=wind, rows=rows, cols=cols)
    _validate_raster_shapes(data)
    return (defaults, data)

def _validate_raster_shapes(data: SWUIFTData) -> None:
    rows, cols = (data.rows, data.cols)
    expected = (rows, cols)
    grids = {'binary_cover': data.binary_cover, 'hardening_mat_rad': data.hardening_mat_rad, 'hardening_mat_spo': data.hardening_mat_spo, 'homes_mat': data.homes_mat, 'water': data.water, 'domains_mat': data.domains_mat, 'knownig_mat': data.knownig_mat}
    for name, arr in grids.items():
        if arr.shape != expected:
            raise ValueError(f'Incompatible shape for {name}: expected {expected}, got {arr.shape}')
    lati = np.asarray(data.lati).ravel()
    long = np.asarray(data.long).ravel()
    if lati.size != rows:
        raise ValueError(f'Incompatible latitude length: expected {rows}, got {lati.size}')
    if long.size != cols:
        raise ValueError(f'Incompatible longitude length: expected {cols}, got {long.size}')

def load_all_extracted(*, wildland_fire_matrix_file: str, domain_matrix_file: str, binary_cover_file: str, homes_matrix_file: str, latitude_file: str, longitude_file: str, radiation_matrix_file: str, spotting_matrix_file: str, water_matrix_file: str, wind_file: str, preload_wind: bool=True) -> SWUIFTData:
    knownig_mat = _load_single_v5(wildland_fire_matrix_file, 'wildland_fire_matrix')
    domains_mat = _load_single_v5(domain_matrix_file, 'domains_mat')
    binary_cover = _load_single_v5(binary_cover_file, 'binary_cover')
    homes_mat = _load_single_v5(homes_matrix_file, 'homes_mat')
    water = _load_single_v5(water_matrix_file, 'water')
    lati = _load_single_v5(latitude_file, 'lati').ravel()
    long = _load_single_v5(longitude_file, 'long').ravel()
    hardening_mat_rad = _load_single_v5(radiation_matrix_file, 'hardening_mat_rad')
    hardening_mat_spo = _load_single_v5(spotting_matrix_file, 'hardening_mat_spo')
    wind = WindData(wind_file, preload=preload_wind)
    rows, cols = binary_cover.shape
    data = SWUIFTData(binary_cover=binary_cover, hardening_mat_rad=hardening_mat_rad, hardening_mat_spo=hardening_mat_spo, homes_mat=homes_mat, water=water, lati=lati, long=long, domains_mat=domains_mat, knownig_mat=knownig_mat, wind=wind, rows=rows, cols=cols)
    _validate_raster_shapes(data)
    return data
