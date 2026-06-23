"""Command-line entry point for strict SWUIFT runs (single or batch)."""

from __future__ import annotations

import argparse
import sys

from .job import JobSpec, load_jobs, parse_datetime, validate_output_dir
from .logger import format_command
from .runner import run_single


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swuift",
        description="SWUIFT wildfire-urban-interface simulation (explicit inputs only).",
    )
    parser.add_argument("--batch", help="Path to JSON file containing a jobs array.")
    parser.add_argument("--job-name", help="Unique name for single-run mode.")

    # Input files
    parser.add_argument("--fire-prog")
    parser.add_argument("--domains")
    parser.add_argument("--landcover")
    parser.add_argument("--homes")
    parser.add_argument("--lat")
    parser.add_argument("--lon")
    parser.add_argument("--harden-rad-map")
    parser.add_argument("--harden-spo-map")
    parser.add_argument("--water")
    parser.add_argument("--wind")

    # Required hyperparameters
    parser.add_argument("--grid-size", type=int)
    parser.add_argument("--t-start", type=parse_datetime)
    parser.add_argument("--t-end", type=parse_datetime)
    parser.add_argument("--harden-rad", type=float)
    parser.add_argument("--harden-spo", type=float)
    parser.add_argument("--rad-ig-thresh", type=float)
    parser.add_argument("--rad-decay", type=float)
    parser.add_argument("--brand-wind-coef", type=float)
    parser.add_argument("--brand-wind-sd", type=float)
    parser.add_argument("--brand-wind-sd-lat", type=float)
    parser.add_argument("--seed-harden", type=int)
    parser.add_argument("--seed-spread", type=int)
    parser.add_argument(
        "--lazy-wind",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable lazy HDF5 wind loading (required in single-run mode).",
    )

    # Run controls required for single mode
    parser.add_argument("--output-dir")
    parser.add_argument("--frame-dpi", type=int)
    parser.add_argument("--dump-every", type=int)
    parser.add_argument(
        "--dump-csv",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Dump step-state as CSV (or disable for .npy). Required in single mode.",
    )

    # Output controls (defaults only here)
    parser.add_argument("--out-frames", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-video", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-gif", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-ig-plots", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-fire-csv", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--out-buildings-csv", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--out-rad-steps", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--out-spo-steps", action=argparse.BooleanOptionalAction, default=False)
    return parser


def _missing_single_fields(args: argparse.Namespace) -> list[str]:
    required = [
        "job_name",
        "fire_prog",
        "domains",
        "landcover",
        "homes",
        "lat",
        "lon",
        "harden_rad_map",
        "harden_spo_map",
        "water",
        "wind",
        "grid_size",
        "t_start",
        "t_end",
        "harden_rad",
        "harden_spo",
        "rad_ig_thresh",
        "rad_decay",
        "brand_wind_coef",
        "brand_wind_sd",
        "brand_wind_sd_lat",
        "seed_harden",
        "seed_spread",
        "lazy_wind",
        "output_dir",
        "frame_dpi",
        "dump_every",
        "dump_csv",
    ]
    return [name for name in required if getattr(args, name) is None]


def _build_single_job(args: argparse.Namespace) -> JobSpec:
    missing = _missing_single_fields(args)
    if missing:
        joined = ", ".join(f"--{m.replace('_', '-')}" for m in missing)
        raise ValueError(f"Job {args.job_name!r} missing required CLI parameters: {joined}")
    return JobSpec(
        name=args.job_name,
        fire_prog=args.fire_prog,
        domains=args.domains,
        landcover=args.landcover,
        homes=args.homes,
        lat=args.lat,
        lon=args.lon,
        harden_rad_map=args.harden_rad_map,
        harden_spo_map=args.harden_spo_map,
        water=args.water,
        wind=args.wind,
        grid_size=args.grid_size,
        t_start=args.t_start,
        t_end=args.t_end,
        harden_rad=args.harden_rad,
        harden_spo=args.harden_spo,
        rad_ig_thresh=args.rad_ig_thresh,
        rad_decay=args.rad_decay,
        brand_wind_coef=args.brand_wind_coef,
        brand_wind_sd=args.brand_wind_sd,
        brand_wind_sd_lat=args.brand_wind_sd_lat,
        seed_harden=args.seed_harden,
        seed_spread=args.seed_spread,
        lazy_wind=args.lazy_wind,
        output_dir=validate_output_dir(args.output_dir, args.job_name),
        frame_dpi=args.frame_dpi,
        dump_every=args.dump_every,
        dump_csv=args.dump_csv,
        out_frames=args.out_frames,
        out_video=args.out_video,
        out_gif=args.out_gif,
        out_ig_plots=args.out_ig_plots,
        out_fire_csv=args.out_fire_csv,
        out_buildings_csv=args.out_buildings_csv,
        out_rad_steps=args.out_rad_steps,
        out_spo_steps=args.out_spo_steps,
    )


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    command_line = format_command(["swuift", *(argv or sys.argv[1:])])

    if args.batch:
        jobs = load_jobs(args.batch)
        for idx, job in enumerate(jobs, start=1):
            print(f"[{idx}/{len(jobs)}] Executing {job.name}")
            run_single(job, command_line=f"{command_line} --job {job.name}")
        return

    job = _build_single_job(args)
    run_single(job, command_line=command_line)


if __name__ == "__main__":
    main()
