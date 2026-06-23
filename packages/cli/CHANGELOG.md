# Changelog

All notable changes to this project will be documented in this file.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) where applicable.

## [1.1.0] - 2026-03-11

### Added
- Inline comments throughout core modules (CLI entrypoint, runners, data loading, and simulation utilities) to clarify control flow, data shapes, and key modeling assumptions.
- A consolidated list and description of primary hyperparameters in `README.md` to support easier configuration, tuning, and reproducibility of experiments.

### Changed
- Water matrix handling: the water matrix is no longer treated as a mandatory default input. When a water matrix is not supplied, the system now explicitly constructs a “no water” mask (using NA/zeroed semantics internally) and ensures downstream plotting and analysis correctly reflect the absence of water cells.

## [1.0.0] - 2025-xx-xx

### Added
- Initial public CLI for running single and batch SWUIFT experiments.
- Core data-loading, wind handling, and simulation pipeline.
- Basic documentation and example JSON job specification.

