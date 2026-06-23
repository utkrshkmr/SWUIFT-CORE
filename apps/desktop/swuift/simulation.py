from __future__ import annotations
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Callable, Dict, Set, Tuple
import numpy as np
from tqdm import tqdm
from swuift_core.hardening import apply_hardening
from swuift_core.spread import brand_gen, brand_ig, radiation_gen, radiation_ig

from .config import SWUIFTConfig
from .data_loader import SWUIFTData
from .plotting import assemble_video, build_plt_mat, plot_pixel_ignitions, plot_structure_ignitions, save_frame_csv_from_plt_mat, save_frame_state_npy, save_snapshot_from_plt_mat

def _time_vector(t_start: datetime, t_end: datetime, t_step_min: float):
    dt = timedelta(minutes=t_step_min)
    times = []
    t = t_start
    while t <= t_end:
        times.append(t)
        t += dt
    return times

def _write_log(fh, msg: str, *, flush: bool=False):
    fh.write(msg)
    if flush:
        fh.flush()

def _build_home_pixel_index(homes_mat: np.ndarray) -> Tuple[Dict[int, np.ndarray], Dict[int, np.ndarray]]:
    mask = homes_mat > 0
    flat = homes_mat[mask].astype(np.intp)
    rows_idx, cols_idx = np.where(mask)
    home_id_to_rows: Dict[int, list] = defaultdict(list)
    home_id_to_cols: Dict[int, list] = defaultdict(list)
    for k in range(len(flat)):
        hid = int(flat[k])
        home_id_to_rows[hid].append(rows_idx[k])
        home_id_to_cols[hid].append(cols_idx[k])
    home_rows = {hid: np.array(v, dtype=np.intp) for hid, v in home_id_to_rows.items()}
    home_cols = {hid: np.array(v, dtype=np.intp) for hid, v in home_id_to_cols.items()}
    return (home_rows, home_cols)

def _update_ignited_homes(ignited_homes: Set[int], ignition: np.ndarray, homes_positive: np.ndarray, homes_mat: np.ndarray) -> None:
    mask = (ignition == 1) & homes_positive
    if not np.any(mask):
        return
    for hid in np.unique(homes_mat[mask].astype(int)):
        hid_i = int(hid)
        if hid_i > 0:
            ignited_homes.add(hid_i)

def _dump_step_binary(step_dir: str, fire, ignition, radtotal, out_fire, zvector):
    os.makedirs(step_dir, exist_ok=True)
    np.save(os.path.join(step_dir, 'fire.npy'), fire)
    np.save(os.path.join(step_dir, 'ignition.npy'), ignition)
    np.save(os.path.join(step_dir, 'radtotal.npy'), radtotal)
    np.save(os.path.join(step_dir, 'out_fire.npy'), out_fire)
    np.save(os.path.join(step_dir, 'zvector.npy'), zvector)

def _dump_step_csv(step_dir: str, fire, ignition, radtotal, out_fire, zvector):
    os.makedirs(step_dir, exist_ok=True)
    np.savetxt(os.path.join(step_dir, 'fire.csv'), fire, delimiter=',')
    np.savetxt(os.path.join(step_dir, 'ignition.csv'), ignition, delimiter=',')
    np.savetxt(os.path.join(step_dir, 'radtotal.csv'), radtotal, delimiter=',')
    np.savetxt(os.path.join(step_dir, 'out_fire.csv'), out_fire, delimiter=',')
    np.savetxt(os.path.join(step_dir, 'zvector.csv'), zvector, delimiter=',')

def run_simulation(cfg: SWUIFTConfig, data: SWUIFTData, output_dir: str, dpi: int=150, dpi_hires: int=600, make_video: bool=True, dump_interval: int=1, dump_csv: bool=True, dump_radiation_csv: bool=False, dump_spotting_csv: bool=False, save_frame_csv: bool=False, save_frames: bool=True, io_workers: int=2, phase_callback=None, profile_callback: Callable[[str, float], None] | None=None) -> None:

    def _profile(stage: str, elapsed: float) -> None:
        if profile_callback is not None:
            profile_callback(stage, elapsed)
    t0 = time.perf_counter()
    hard = apply_hardening(cfg, data.binary_cover, data.homes_mat, data.hardening_mat_rad, data.hardening_mat_spo, data.knownig_mat, data.lati, data.long)
    knownig_mat = hard.knownig_mat
    criteria_rad = hard.criteria_rad
    criteria_spo = hard.criteria_spo
    _profile('hardening', time.perf_counter() - t0)
    n_homes = int(data.homes_mat.max())
    zvector = np.zeros((n_homes, 5))
    zvector[:, 0] = np.arange(1, n_homes + 1)
    rng = np.random.RandomState(cfg.seed_spread)
    t_num_vec = _time_vector(cfg.t_start, cfg.t_end, cfg.t_step_min)
    if cfg.maxstep is not None:
        maxstep = min(cfg.maxstep, len(t_num_vec))
        t_num_vec = t_num_vec[:maxstep]
    else:
        maxstep = len(t_num_vec)
    fstep = cfg.fstep
    lstep = cfg.lstep
    rows, cols = (data.rows, data.cols)
    ignition = np.zeros((rows, cols))
    fire = np.zeros((rows, cols))
    radtotal = np.zeros((rows, cols))
    out_fire = np.zeros((rows, cols))
    ig_known = np.zeros(maxstep)
    ig_dev = np.zeros(maxstep)
    ig_rad = np.zeros(maxstep)
    ig_brand = np.zeros(maxstep)
    ig_total = np.zeros(maxstep)
    house_ig_known = np.zeros(maxstep)
    house_ig_rad = np.zeros(maxstep)
    house_ig_brand = np.zeros(maxstep)
    house_ig_total = np.zeros(maxstep)
    brands_on_structures_cumsum = 0
    homes_positive = data.homes_mat > 0
    bc_positive = data.binary_cover > 0
    home_rows, home_cols = _build_home_pixel_index(data.homes_mat)
    ignited_homes: Set[int] = set()
    frames_dir = os.path.join(output_dir, 'frames')
    frame_csvs_dir = os.path.join(output_dir, 'frame_csvs')
    frame_state_dir = os.path.join(output_dir, 'frame_state')
    timesteps_dir = os.path.join(output_dir, 'timesteps')
    radiation_csv_dir = os.path.join(output_dir, 'radiation_csv')
    spotting_csv_dir = os.path.join(output_dir, 'spotting_csv')
    if save_frames:
        os.makedirs(frames_dir, exist_ok=True)
    if save_frame_csv:
        os.makedirs(frame_csvs_dir, exist_ok=True)
    os.makedirs(frame_state_dir, exist_ok=True)
    if dump_interval > 0:
        os.makedirs(timesteps_dir, exist_ok=True)
    if dump_radiation_csv:
        os.makedirs(radiation_csv_dir, exist_ok=True)
    if dump_spotting_csv:
        os.makedirs(spotting_csv_dir, exist_ok=True)
    log_path = os.path.join(output_dir, 'run_log.txt')
    fh = open(log_path, 'w')
    wall_start = time.time()
    _write_log(fh, f'Spread loop begins at: {datetime.now()}\n')
    _write_log(fh, '################################\n')
    _write_log(fh, f'grid cell size = {cfg.grid_size} m\n')
    _write_log(fh, f"start time = {cfg.t_start.strftime('%Y/%m/%d %H:%M')}\n")
    _write_log(fh, f"end time = {cfg.t_end.strftime('%Y/%m/%d %H:%M')}\n")
    _write_log(fh, f'time step = {cfg.t_step_min} minutes\n')
    _write_log(fh, f'Fully developed phase between steps {fstep} and {lstep}\n')
    _write_log(fh, f'threshold for ignition due to radiation = {cfg.rad_energy_ig}\n')
    _write_log(fh, f'emissivity receiving = {cfg.er}\n')
    _write_log(fh, f'emissivity emitting = {cfg.ee}\n')
    _write_log(fh, f'area for radiating surface = {cfg.aes} m2\n')
    _write_log(fh, f'radiation reduction factor = {cfg.rad_rf}\n')
    _write_log(fh, f'mass of each firebrand = {cfg.fb_mass} g\n')
    _write_log(fh, f'brands for Santamaria condition = {cfg.fb_str_ig}\n')
    _write_log(fh, f'brands for igniting vegetation = {cfg.fb_veg_ig}\n')
    _write_log(fh, f'brands generated from vegetation = {cfg.fb_veg_gen}\n')
    _write_log(fh, '################################\n\n')
    io_pool = ThreadPoolExecutor(max_workers=max(1, io_workers))
    io_futures: list = []
    for tstep in tqdm(range(1, maxstep + 1), desc='Time steps', unit='step'):
        step_log: list[str] = []
        sim_time = t_num_vec[tstep - 1]
        step_log.append(f"Step {tstep}: {sim_time.strftime('%Y/%m/%d %H:%M')}\n")
        t_step0 = time.perf_counter()
        fire[fire > 0] += 1
        ignition[(knownig_mat == tstep) & (data.domains_mat >= 8)] = 1
        ig_known_mask = homes_positive & (knownig_mat == tstep) & (data.domains_mat >= 8)
        ig_known[tstep - 1] = ignition[ig_known_mask].sum()
        if np.any(ig_known_mask):
            new_known_ids = {int(h) for h in data.homes_mat[ig_known_mask].astype(int) if h > 0}
            ignited_now = set(ignited_homes)
            _update_ignited_homes(ignited_homes, ignition, homes_positive, data.homes_mat)
            house_ig_known[tstep - 1] = len(new_known_ids - ignited_now)
        str_pixels_ignited = int(ignition[homes_positive].sum())
        _update_ignited_homes(ignited_homes, ignition, homes_positive, data.homes_mat)
        house_ig_tmp = len(ignited_homes)
        step_log.append('- Known ignitions registered.\n')
        step_log.append(f'    Structure pixels ignited so far: {str_pixels_ignited}\n')
        step_log.append(f'    Structures ignited so far: {house_ig_tmp}\n')
        step_log.append('- Propagating full-house ignition.\n')
        ind_mask = (ignition == 1) & bc_positive
        active_hids = np.unique(data.homes_mat[ind_mask].astype(int))
        for hid in active_hids:
            hid_i = int(hid)
            if hid_i <= 0:
                continue
            hr = home_rows.get(hid_i)
            hc = home_cols.get(hid_i)
            if hr is None or hr.size == 0:
                continue
            if np.any(fire[hr, hc] >= fstep):
                ignition[hr, hc] = 1
        new_str_pix = int(ignition[homes_positive].sum())
        ig_dev[tstep - 1] = new_str_pix - str_pixels_ignited
        str_pixels_ignited = new_str_pix
        _update_ignited_homes(ignited_homes, ignition, homes_positive, data.homes_mat)
        step_log.append(f'    Structure pixels ignited so far: {str_pixels_ignited}\n')
        wind_ix = min(tstep - 1, data.wind.n_timesteps - 1)
        wind_s_2d, wind_d_2d = data.wind.get_slice(wind_ix)
        t_brand0 = time.perf_counter()
        brands, brand_gen_mat = brand_gen(cfg, rows, cols, data.binary_cover, fire, fstep, lstep, wind_s_2d, wind_d_2d, cfg.fb_veg_gen, cfg.fb_str_ig, cfg.veg_included, tstep, data.domains_mat, rng)
        _profile('brand_gen', time.perf_counter() - t_brand0)
        step_log.append('- Brands generated and transported.\n')
        if dump_spotting_csv:
            _spo_path = os.path.join(spotting_csv_dir, f'{tstep:04d}.csv')
            _spo_mat = brand_gen_mat.copy()
            io_futures.append(io_pool.submit(np.savetxt, _spo_path, _spo_mat, delimiter=',', fmt='%.6g'))
        step_brands_on_structures = 0
        if brands.shape[1] > 0:
            brand_indices = brands[0, :].astype(np.intp)
            brand_counts = brands[1, :].astype(np.int64)
            total_counts = np.zeros(rows * cols, dtype=np.int64)
            np.add.at(total_counts, brand_indices, brand_counts)
            total_counts_2d = total_counts.reshape(rows, cols)
            step_brands_on_structures = int(total_counts_2d[bc_positive].sum())
        brands_on_structures_cumsum += step_brands_on_structures
        step_log.append(f'    Brands on structures this step: {step_brands_on_structures}\n')
        step_log.append(f'    Brands on structures cumulative: {brands_on_structures_cumsum}\n')
        t_rad0 = time.perf_counter()
        radtotal = radiation_gen(cfg, rows, cols, data.binary_cover, fire, cfg.tmpr, radtotal, fstep, lstep, cfg.rad_rf, wind_d_2d, cfg.aes, cfg.ee, cfg.er, cfg.sconst)
        _profile('radiation', time.perf_counter() - t_rad0)
        step_log.append('- Radiation fluxes evaluated.\n')
        if dump_radiation_csv:
            _rad_path = os.path.join(radiation_csv_dir, f'{tstep:04d}.csv')
            _rad_copy = radtotal.copy()
            io_futures.append(io_pool.submit(np.savetxt, _rad_path, _rad_copy, delimiter=',', fmt='%.6g'))
        ig_before_rad = str_pixels_ignited
        homes_before_rad_set = set(ignited_homes)
        homes_before_rad = len(homes_before_rad_set)
        ignition = radiation_ig(ignition, data.binary_cover, radtotal, cfg.rad_energy_ig, criteria_rad, cfg.limrad)
        _update_zvector(ignition=ignition, homes_mat=data.homes_mat, binary_cover=data.binary_cover, zvector=zvector, tstep=tstep, previously_ignited=homes_before_rad_set, cause_column=2)
        _update_ignited_homes(ignited_homes, ignition, homes_positive, data.homes_mat)
        str_pixels_ignited = int(ignition[homes_positive].sum())
        ig_rad[tstep - 1] = str_pixels_ignited - ig_before_rad
        house_ig_rad[tstep - 1] = len(ignited_homes) - homes_before_rad
        step_log.append('- Radiation ignitions registered.\n')
        step_log.append(f'    Structure pixels ignited so far: {str_pixels_ignited}\n')
        step_log.append(f'    Structures ignited so far: {len(ignited_homes)}\n')
        ig_before_brand = str_pixels_ignited
        homes_before_brand_set = set(ignited_homes)
        homes_before_brand = len(homes_before_brand_set)
        brand_log: list[str] = []
        t_brand_ig0 = time.perf_counter()
        ignition = brand_ig(cfg, rows, cols, data.binary_cover, ignition, brand_log, brands, cfg.fb_str_ig, cfg.fb_veg_ig, cfg.fb_dist_mu, cfg.fb_dist_sd, cfg.veg_included, data.domains_mat, criteria_spo, cfg.limspo, rng)
        _profile('brand_ig', time.perf_counter() - t_brand_ig0)
        step_log.extend((f'    {line}\n' for line in brand_log))
        _update_zvector(ignition=ignition, homes_mat=data.homes_mat, binary_cover=data.binary_cover, zvector=zvector, tstep=tstep, previously_ignited=homes_before_brand_set, cause_column=3)
        _update_ignited_homes(ignited_homes, ignition, homes_positive, data.homes_mat)
        str_pixels_ignited = int(ignition[homes_positive].sum())
        ig_brand[tstep - 1] = str_pixels_ignited - ig_before_brand
        house_ig_brand[tstep - 1] = len(ignited_homes) - homes_before_brand
        step_log.append('- Branding ignitions registered.\n')
        step_log.append(f'    Structure pixels ignited so far: {str_pixels_ignited}\n')
        step_log.append(f'    Structures ignited so far: {len(ignited_homes)}\n')
        step_log.append(f'    Wall time: {datetime.now()}\n')
        new_fire_mask = (fire == 0) & (ignition == 1)
        fire[new_fire_mask] = 0.11
        ig_total[tstep - 1] = ignition[homes_positive].sum()
        house_ig_total[tstep - 1] = len(ignited_homes)
        newly_on_fire = (fire != 0) & (out_fire == 0)
        out_fire[newly_on_fire] = (tstep - 1) * cfg.t_step_min
        t_plot0 = time.perf_counter()
        plt_mat = build_plt_mat(rows, cols, data.binary_cover, ignition, fire, fstep, lstep, data.water)
        io_futures.append(io_pool.submit(save_frame_state_npy, plt_mat.copy(), tstep, frame_state_dir))
        if save_frames:
            io_futures.append(io_pool.submit(save_snapshot_from_plt_mat, plt_mat.copy(), data.long, data.lati, sim_time, tstep, frames_dir, dpi_hires))
        if save_frame_csv:
            io_futures.append(io_pool.submit(save_frame_csv_from_plt_mat, plt_mat.copy(), tstep, frame_csvs_dir))
        if dump_interval > 0 and tstep % dump_interval == 0:
            step_dir = os.path.join(timesteps_dir, f't{tstep:06d}')
            dumper = _dump_step_csv if dump_csv else _dump_step_binary
            io_futures.append(io_pool.submit(dumper, step_dir, fire.copy(), ignition.copy(), radtotal.copy(), out_fire.copy(), zvector.copy()))
        _profile('output', time.perf_counter() - t_plot0)
        _write_log(fh, ''.join(step_log), flush=True)
        _profile('step_total', time.perf_counter() - t_step0)
    out_fire[(out_fire == 0) & (knownig_mat == 0)] = np.nan
    for fut in io_futures:
        fut.result()
    io_pool.shutdown(wait=True)
    wall_end = time.time()
    runtime_min = (wall_end - wall_start) / 60
    _write_log(fh, '\n################################\n')
    _write_log(fh, f'Runtime: {runtime_min:.1f} minutes.\n')
    _write_log(fh, f'rad_energy_ig: {cfg.rad_energy_ig}\n')
    _write_log(fh, f'fb_wind_coef: {cfg.fb_wind_coef}\n')
    _write_log(fh, f'fb_wind_sd: {cfg.fb_wind_sd}\n')
    _write_log(fh, f'fb_wind_sd_transverse: {cfg.fb_wind_sd_transverse}\n')
    _write_log(fh, f'fb_mass: {cfg.fb_mass}\n')
    _write_log(fh, f'fb_dist_mu: {cfg.fb_dist_mu}\n')
    _write_log(fh, f'fb_dist_sd: {cfg.fb_dist_sd}\n')
    fh.close()
    if make_video and save_frames:
        if phase_callback is not None:
            phase_callback('Generating video')
        print('Assembling video and GIF …')
        assemble_video(frames_dir, output_dir, tag='')
    step_size = max(1, maxstep // 6)
    tick_positions = list(range(1, maxstep + 1, step_size))
    time_labels = [t_num_vec[k - 1].strftime('%H:%M') for k in tick_positions]
    plot_pixel_ignitions(output_dir, maxstep, time_labels, tick_positions, ig_known, ig_dev, ig_rad, ig_brand, ig_total)
    plot_structure_ignitions(output_dir, maxstep, time_labels, tick_positions, house_ig_known, house_ig_rad, house_ig_brand, house_ig_total)
    np.savetxt(os.path.join(output_dir, 'fire_prog.csv'), out_fire, delimiter=',')
    np.savetxt(os.path.join(output_dir, 'zvector.csv'), zvector, delimiter=',')
    print(f'Simulation complete.  Outputs in {output_dir}')

def _update_zvector(ignition: np.ndarray, homes_mat: np.ndarray, binary_cover: np.ndarray, zvector: np.ndarray, tstep: int, previously_ignited: set, cause_column: int) -> None:
    mask = (ignition == 1) & (binary_cover > 0) & (homes_mat > 0)
    if not np.any(mask):
        return
    hids = np.unique(homes_mat[mask].astype(int))
    for hid in hids:
        hid_i = int(hid)
        if hid_i <= 0:
            continue
        if hid_i in previously_ignited:
            continue
        if zvector[hid_i - 1, 1] == 0:
            zvector[hid_i - 1, 1] = 1
            zvector[hid_i - 1, cause_column] = 1
            zvector[hid_i - 1, 4] = tstep
