"""Verification utilities for comparing Python outputs against MATLAB reference.

Provides both:
- Deterministic bit-exact checks (fire, ignition, radtotal, out_fire, zvector)
- Statistical comparison for stochastic components
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np


# ═══════════════════════════════════════════════════════════════════════════
# Per-timestep CSV comparison
# ═══════════════════════════════════════════════════════════════════════════

def compare_timestep_csvs(
    matlab_dir: str,
    python_dir: str,
    tstep: int,
    variables: Tuple[str, ...] = ("fire", "ignition", "radtotal", "out_fire", "zvector"),
    atol: float = 1e-10,
    rtol: float = 0.0,
) -> Dict[str, dict]:
    """Compare per-timestep CSV dumps between MATLAB and Python.

    Returns a dict mapping variable name -> comparison result dict with keys:
        match (bool), max_abs_diff (float), n_mismatched (int), shape_match (bool).
    """
    results = {}
    step_tag = f"t{tstep:06d}"

    for var in variables:
        m_path = os.path.join(matlab_dir, step_tag, f"{var}.csv")
        p_path = os.path.join(python_dir, step_tag, f"{var}.csv")

        if not os.path.isfile(m_path):
            results[var] = {"match": None, "error": f"MATLAB file missing: {m_path}"}
            continue
        if not os.path.isfile(p_path):
            results[var] = {"match": None, "error": f"Python file missing: {p_path}"}
            continue

        m = np.loadtxt(m_path, delimiter=",")
        p = np.loadtxt(p_path, delimiter=",")

        if m.shape != p.shape:
            results[var] = {
                "match": False,
                "shape_match": False,
                "matlab_shape": m.shape,
                "python_shape": p.shape,
            }
            continue

        close = np.allclose(m, p, atol=atol, rtol=rtol)
        diff = np.abs(m - p)
        results[var] = {
            "match": bool(close),
            "shape_match": True,
            "max_abs_diff": float(diff.max()),
            "mean_abs_diff": float(diff.mean()),
            "n_mismatched": int((diff > atol).sum()),
            "total_elements": int(m.size),
        }

    return results


def batch_compare(
    matlab_timesteps_dir: str,
    python_timesteps_dir: str,
    max_step: int,
    variables: Tuple[str, ...] = ("fire", "ignition", "radtotal", "out_fire", "zvector"),
    atol: float = 1e-10,
) -> Dict[int, Dict[str, dict]]:
    """Run comparison across all timesteps.  Returns nested dict[step][var]."""
    all_results: Dict[int, Dict[str, dict]] = {}
    for tstep in range(1, max_step + 1):
        all_results[tstep] = compare_timestep_csvs(
            matlab_timesteps_dir, python_timesteps_dir, tstep,
            variables=variables, atol=atol,
        )
    return all_results


def summarise_comparison(results: Dict[int, Dict[str, dict]]) -> str:
    """Pretty-print a summary of batch comparison results."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("SWUIFT Verification Summary")
    lines.append("=" * 72)

    variables = set()
    for step_res in results.values():
        variables.update(step_res.keys())

    for var in sorted(variables):
        n_match = 0
        n_mismatch = 0
        n_missing = 0
        max_diff = 0.0
        for step, step_res in sorted(results.items()):
            r = step_res.get(var, {})
            if r.get("match") is True:
                n_match += 1
            elif r.get("match") is False:
                n_mismatch += 1
                max_diff = max(max_diff, r.get("max_abs_diff", 0))
            else:
                n_missing += 1

        total = n_match + n_mismatch + n_missing
        status = "PASS" if n_mismatch == 0 and n_missing == 0 else "FAIL"
        lines.append(f"\n  {var:20s}  [{status}]  match={n_match}/{total}"
                      f"  max_diff={max_diff:.2e}")

    lines.append("\n" + "=" * 72)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Statistical comparison
# ═══════════════════════════════════════════════════════════════════════════

def compare_final_outputs(
    matlab_out_fire: np.ndarray,
    python_out_fire: np.ndarray,
    matlab_zvector: np.ndarray,
    python_zvector: np.ndarray,
) -> dict:
    """Compute statistical similarity metrics on the final simulation outputs.

    Returns a dict with correlation, total-structures-ignited comparison, etc.
    """
    result = {}

    # Spatial correlation of out_fire (NaN-safe)
    m_flat = matlab_out_fire.ravel()
    p_flat = python_out_fire.ravel()
    valid = np.isfinite(m_flat) & np.isfinite(p_flat)
    if valid.sum() > 2:
        r = np.corrcoef(m_flat[valid], p_flat[valid])[0, 1]
        result["out_fire_pearson_r"] = float(r)
    else:
        result["out_fire_pearson_r"] = None

    # Total structures ignited
    m_ig = int((matlab_zvector[:, 1] > 0).sum()) if matlab_zvector.ndim == 2 else 0
    p_ig = int((python_zvector[:, 1] > 0).sum()) if python_zvector.ndim == 2 else 0
    result["matlab_structures_ignited"] = m_ig
    result["python_structures_ignited"] = p_ig
    if m_ig > 0:
        result["structures_ignited_pct_diff"] = abs(m_ig - p_ig) / m_ig * 100
    else:
        result["structures_ignited_pct_diff"] = 0.0

    # Cause breakdown
    for col, cause in [(2, "radiation"), (3, "branding")]:
        mk = int((matlab_zvector[:, col] > 0).sum()) if matlab_zvector.ndim == 2 else 0
        pk = int((python_zvector[:, col] > 0).sum()) if python_zvector.ndim == 2 else 0
        result[f"matlab_{cause}"] = mk
        result[f"python_{cause}"] = pk

    return result


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point for standalone verification
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Compare MATLAB vs Python SWUIFT outputs.")
    parser.add_argument("matlab_dir", help="MATLAB timesteps directory (e.g. outs/timesteps)")
    parser.add_argument("python_dir", help="Python timesteps directory")
    parser.add_argument("--max-step", type=int, required=True)
    parser.add_argument("--atol", type=float, default=1e-10)
    args = parser.parse_args()

    results = batch_compare(args.matlab_dir, args.python_dir, args.max_step, atol=args.atol)
    print(summarise_comparison(results))


if __name__ == "__main__":
    main()
