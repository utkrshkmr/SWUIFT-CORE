#!/usr/bin/env python3
"""Backward-compatible wrapper for the smoke15 comparison preset."""

from __future__ import annotations

import sys

from compare_suite import main


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--preset" not in argv:
        argv = ["--preset", "smoke15", *argv]
    raise SystemExit(main(argv))
