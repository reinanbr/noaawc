# Changelog

## [0.5.1] - 2026-06-06

### Fixed
- Added `Programming Language :: Python :: 3.10/3.11/3.12` classifiers to
  `setup.py` so the PyPI `pyversions` badge displays correctly.
- Updated package description to reflect GFS, GODAS, OISST and ERSST support.
- Fixed CI badge URL in README (`tests.yml` → `ci-publish.yml`).
- Fixed `noawclg` link in README (`your-org` → `reinanbr`).

---

## [0.5.0] - 2026-06-06

### Added
- **`ocean_plots.py`** — batch renderer for oceanic data in Orthographic and
  PlateCarrée projections, mirroring the `test_plot_all_keys.py` architecture
  (`VarConfig`, `Profile`, skip-if-exists, per-error log).
- **`noaawc.ocean_variables`** — variable catalogue and plot presets for GODAS
  and ERSST data: `OCEAN_VARIABLES_INFO`, `OCEAN_VARIABLE_PRESETS`,
  `OCEAN_NO_CONTOUR_VARS`, `GODAS_LEVELS`, `NINO_BOXES`, `WWV_BOX`.
- **OISST v2 High-Res** (`open_oisst`) — 0.25° monthly SST via NOAA PSL
  OPeNDAP; used automatically for `sst` when `year >= 1981`.
- **Bilinear grid upsampling** (`_upsample`) via
  `scipy.interpolate.RegularGridInterpolator`; smooths GODAS 1° → 0.25°
  and ERSST 2° → 0.5° before rendering.
- 14 ocean variable configurations across 4 depth levels (surface, 50 m,
  100 m, 200 m, 500 m): `sst`, `sshg`, `pottmp`, `salt`, `ucur`, `vcur`.
- 4 projection profiles: ortho-Atlantic, ortho-Pacific, plate-global,
  plate-tropical.
- `scipy` added to `install_requires` in `setup.py`.

### Fixed
- Removed unused imports in `noaawc/base.py` (`_frames_dir`,
  `_get_field_full`), `noaawc/presets.py` (`numpy`),
  `noaawc/ocean_variables.py` (`matplotlib.colors`), and
  `noaawc/overlays.py` (`_format_date`).
- All backward-compat re-exports in `noaawc/main.py` annotated with
  `# noqa: F401`; `ruff check` now passes clean across the entire package.

### Changed
- Updated `setup.py` version to `0.5.0`.
- README extended with a full **Ocean Data** section covering data sources,
  variable catalogue, region presets, batch CLI, and single-plot API.

---

## [0.4.1] - 2026-05-06

### Changed
- Updated package version to `0.4.1` in `setup.py` to prepare the `v0.4.1` release tag.
- Refreshed the release notes to mirror the current README structure: the unified `WeatherAnimator` entry point, four projection modes, shared quality presets, output controls, annotations, and camera rotation helpers.

### CI/CD
- Release workflow continues to publish on `v*` tags and extracts the matching changelog section for GitHub Releases.
- Lint and test jobs remain aligned with the Cartopy-based stack documented in the README.

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
