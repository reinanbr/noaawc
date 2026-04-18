# Changelog

## [0.3.1] - 2026-04-18

### Changed
- Updated package version to `0.3.1` in `setup.py`.
- Updated metadata tests to parse `setup.py` via AST and validate version without relying on string formatting.

### CI/CD
- Removed Basemap installation from workflow jobs and kept test pipeline aligned with Cartopy-only stack.

## [0.3.0] - 2026-04-18

### Added
- Added a pytest suite in `tests/` covering core `OrthoAnimator` API validations and helper functions.
- Added `pytest.ini` to scope test discovery to the `tests/` directory.
- Added GitHub Actions workflow `.github/workflows/ci-publish.yml` for CI and release automation.

### Changed
- Updated package version to `0.3.0` in `setup.py`.

### CI/CD
- CI now runs on pull requests and pushes to `main`/`master` using Python 3.10, 3.11 and 3.12.
- Publishing to PyPI is automated on tag pushes matching `v*`.
- PyPI publish step expects repository secret `PYPI_API_TOKEN`.
