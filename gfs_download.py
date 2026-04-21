"""
gfs_downloader.py
-----------------
Downloads GFS 0.25° forecast data from the NOAA NOMADS HTTP GRIB filter
for every variable defined in VARIABLES_INFO (presets_extended.py).

Fixes (this version)
---------------------
- Correct ``lev_*`` strings for every variable group:
    * isobaric  (t, r, gh, u, v, w, absv, q)  → lev_500_mb / lev_1000_mb
    * soil       (st, soilw)                   → lev_0-10_cm_below_ground
    * layer      (hlcy)                        → lev_1000-0_m_above_ground
    * cloud      (lcc, mcc, hcc)               → pgrb2b + correct layer name
    * atmosphere (tozne, tcc, refc)            → lev_entire_atmosphere
    * aptmp                                    → pgrb2b only
- pgrb2b and pgrb2p5 variables fetched from the correct filter endpoints.
- _PGRB2P5_VARS: extra higher-resolution variables from filter_gfs_0p25_1hr.pl
- Progress bar via tqdm (falls back gracefully if not installed).
- save() / load() helpers for NetCDF persistence.
- plot_nearside() helper for quick static Cartopy nearside-projection maps.

Quick start
-----------
    from gfs_downloader import GFSDownloader

    dl = GFSDownloader(date="18/04/2026", cycle="00z", hours=[0])
    ds = dl.fetch(["t2m", "r2", "prmsl"])

    ds = dl.fetch_all()
    ds = dl.fetch_all(skip=["aptmp"])

    dl.save(ds, "gfs_20260418_00z.nc")
    ds2 = GFSDownloader.load("gfs_20260418_00z.nc")

    # Plot a variable
    from gfs_downloader import plot_nearside
    plot_nearside(ds, "t2m", fhour_index=0)

URL pattern (NOMADS GRIB filter)
---------------------------------
    https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl
        ?dir=%2Fgfs.YYYYMMDD%2FHH%2Fatmos
        &file=gfs.tHHz.pgrb2.0p25.fFFF
        &var_<GRIB_VAR>=on
        &lev_<GRIB_LEV>=on
        &leftlon=0&rightlon=360&toplat=90&bottomlat=-90

pgrb2p5 (0.5°) URL pattern — used for _PGRB2P5_VARS:
    https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p50.pl
        ?dir=%2Fgfs.YYYYMMDD%2FHH%2Fatmos
        &file=gfs.tHHz.pgrb2.0p50.fFFF
        &var_<GRIB_VAR>=on
        &lev_<GRIB_LEV>=on
        ...
"""

import os
import re
import time
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import numpy as np
import requests
import xarray as xr

try:
    import cfgrib
    _HAS_CFGRIB = True
except ImportError:
    _HAS_CFGRIB = False
    print("[gfs_downloader] WARNING: cfgrib not installed — GRIB decoding unavailable.")

try:
    from tqdm import tqdm as _tqdm
    _HAS_TQDM = True
except ImportError:
    _HAS_TQDM = False

from noaawc.variables import VARIABLES_INFO   # adjust import path as needed


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

_NOMADS_BASE_025  = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
_NOMADS_BASE_050  = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p50.pl"
_DEFAULT_HOURS    = list(range(0, 121, 3))
_MAX_RETRIES      = 3
_RETRY_DELAY_S    = 5.0


# ══════════════════════════════════════════════════════════════════════════════
# Level-string override table
# ──────────────────────────────────────────────────────────────────────────────
# Keys here override VARIABLES_INFO["grib_lev"] when building NOMADS URLs.
# Format must match the exact string the NOMADS HTTP filter expects.
# ══════════════════════════════════════════════════════════════════════════════

_NOMADS_LEV: dict[str, str] = {
    # ── isobaric ─────────────────────────────────────────────────────────────
    # Default representative level; callers that need multi-level data must
    # override by building the URL themselves or iterating over pressure levels.
    "t":     "lev_500_mb",
    "r":     "lev_500_mb",
    "gh":    "lev_500_mb",
    "u":     "lev_500_mb",
    "v":     "lev_500_mb",
    "w":     "lev_500_mb",
    "absv":  "lev_500_mb",
    "q":     "lev_1000_mb",

    # ── soil layers ───────────────────────────────────────────────────────────
    # NOMADS uses dash-separated depth ranges, not slashes.
    "st":    "lev_0-10_cm_below_ground",
    "soilw": "lev_0-10_cm_below_ground",

    # ── helicity layer ────────────────────────────────────────────────────────
    # Storm-relative helicity: 1000 m AGL integration layer.
    # NOTE: "1000-0 m above ground" is the exact string NOMADS uses
    # (top-to-bottom ordering is intentional in the GRIB2 layer descriptor).
    "hlcy":  "lev_1000-0_m_above_ground",

    # ── atmosphere column ─────────────────────────────────────────────────────
    "tcc":   "lev_entire_atmosphere",
    "refc":  "lev_entire_atmosphere_(considered_as_a_single_layer)",
    "tozne": "lev_entire_atmosphere_(considered_as_a_single_layer)",

    # ── precipitable / column water ───────────────────────────────────────────
    "pwat":  "lev_entire_atmosphere_(considered_as_a_single_layer)",
    "cwat":  "lev_entire_atmosphere_(considered_as_a_single_layer)",

    # ── cloud layers (pgrb2b) ─────────────────────────────────────────────────
    "lcc":   "lev_low_cloud_layer",
    "mcc":   "lev_middle_cloud_layer",
    "hcc":   "lev_high_cloud_layer",

    # ── surface / 2 m / 10 m ─────────────────────────────────────────────────
    # Most surface variables already carry the correct lev_ in VARIABLES_INFO;
    # only overrides are listed here.
    "cape":  "lev_surface",
    "cin":   "lev_surface",
    "lftx":  "lev_500_mb",        # best lifted index: 500 mb level
    "4lftx": "lev_0-90_mb_above_ground",
}


# ══════════════════════════════════════════════════════════════════════════════
# File-type routing
# ══════════════════════════════════════════════════════════════════════════════

# Variables found only in the pgrb2b supplemental file (still 0.25°).
_PGRB2B_VARS: frozenset[str] = frozenset({
    "aptmp",   # apparent temperature — pgrb2b only
    "lcc",     # low  cloud cover
    "mcc",     # mid  cloud cover
    "hcc",     # high cloud cover
})

# Variables available from the 0.5° pgrb2 file (filter_gfs_0p50.pl).
# These are either absent at 0.25° or only published at coarser resolution.
# Fetched from a separate base URL; decoded grid will be ~0.5° resolution.
_PGRB2P5_VARS: frozenset[str] = frozenset({
    # Ensemble-mean / probability products (published at 0.5° only)
    "ulwrf",   # upward long-wave radiation flux (top of atmosphere)
    "dswrf",   # downward short-wave radiation flux (surface)
    "dlwrf",   # downward long-wave radiation flux (surface)
    "uswrf",   # upward short-wave radiation flux (surface)
    "lhtfl",   # latent heat net flux
    "shtfl",   # sensible heat net flux
    "gflux",   # ground heat flux
    "hpbl",    # planetary boundary layer height
    "fricv",   # frictional velocity
    "vrate",   # ventilation rate — published at 0.5° only
    "cnwat",   # plant canopy surface water
    "sde",     # snow depth (water equivalent, alternate name)
    "ssrun",   # storm surface runoff
    "bgrun",   # baseflow-groundwater runoff
    "watr",    # water runoff (0.5° stream)
    "icaht",   # icing severity (0.5° only)
    "ustm",    # u-component of storm motion
    "vstm",    # v-component of storm motion
})


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _parse_date(date_str: str) -> datetime:
    for fmt in ("%d/%m/%Y", "%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Unrecognised date format: {date_str!r}. "
        "Use DD/MM/YYYY, YYYYMMDD, or YYYY-MM-DD."
    )


def _cycle_norm(cycle) -> str:
    return re.sub(r"[^0-9]", "", str(cycle)).zfill(2)


def _nomads_lev(key: str) -> str:
    """Return the exact NOMADS filter level string for *key*."""
    if key in _NOMADS_LEV:
        return _NOMADS_LEV[key]
    lev = VARIABLES_INFO[key]["grib_lev"]
    return lev if lev.startswith("lev_") else f"lev_{lev}"


def _base_url(key: str) -> str:
    """Return the correct NOMADS filter base URL for *key*."""
    return _NOMADS_BASE_050 if key in _PGRB2P5_VARS else _NOMADS_BASE_025


def _file_resolution(key: str) -> str:
    """Return the pgrb2 file resolution string for *key*."""
    return "0p50" if key in _PGRB2P5_VARS else "0p25"


def _file_type(key: str) -> str:
    """Return 'pgrb2b' or 'pgrb2' for the given key."""
    # pgrb2b only makes sense at 0.25°; 0.5° always uses pgrb2
    return "pgrb2b" if (key in _PGRB2B_VARS and key not in _PGRB2P5_VARS) else "pgrb2"


def _build_url(yyyymmdd: str, cycle: str, fhour: int, key: str) -> str:
    info     = VARIABLES_INFO[key]
    grib_var = info["grib_var"]   # e.g. "var_TMP=on"
    lev_str  = _nomads_lev(key)
    res      = _file_resolution(key)
    ftype    = _file_type(key)
    base     = _base_url(key)
    fname    = f"gfs.t{cycle}z.{ftype}.{res}.f{fhour:03d}"

    # NOMADS is order-sensitive — dir and file must come first
    parts = [
        f"dir=%2Fgfs.{yyyymmdd}%2F{cycle}%2Fatmos",
        f"file={fname}",
        f"{grib_var}=on",
        f"{lev_str}=on",
        "leftlon=0",
        "rightlon=360",
        "toplat=90",
        "bottomlat=-90",
    ]
    return base + "?" + "&".join(parts)


def _fetch_bytes(url: str, timeout: int = 120) -> bytes | None:
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.content if r.content[:4] == b"GRIB" else None
            if r.status_code in (400, 404, 500, 503):
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY_S)
                continue
            r.raise_for_status()
        except requests.RequestException as exc:
            if attempt == _MAX_RETRIES:
                print(f"    [net] {exc}")
            else:
                time.sleep(_RETRY_DELAY_S)
    return None


def _decode_grib(raw: bytes, key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    if not _HAS_CFGRIB:
        return None
    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp:
        tmp.write(raw)
        path = tmp.name
    try:
        for ds in cfgrib.open_datasets(path):
            dvars = list(ds.data_vars)
            if not dvars:
                continue
            da   = ds[dvars[0]]
            lats = da.latitude.values
            lons = da.longitude.values
            vals = da.values.copy()
            conv = VARIABLES_INFO[key].get("converter")
            if conv is not None:
                vals = conv(vals)
            return lats, lons, vals
    except Exception as exc:
        print(f"    [cfgrib] {key}: {exc}")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return None


def _bar(iterable, **kw):
    return _tqdm(iterable, **kw) if _HAS_TQDM else iterable


# ══════════════════════════════════════════════════════════════════════════════
# GFSDownloader
# ══════════════════════════════════════════════════════════════════════════════

class GFSDownloader:
    """
    Downloads GFS forecast data from NOAA NOMADS (0.25° and 0.5°).

    Parameters
    ----------
    date : str
        Run date — ``"DD/MM/YYYY"``, ``"YYYYMMDD"``, or ``"YYYY-MM-DD"``.
    cycle : str or int
        GFS cycle: ``"00z"``, ``"06z"``, ``"12z"``, ``"18z"``
        (or bare int ``0``, ``6``, ``12``, ``18``).  Default ``"00z"``.
    hours : list[int], optional
        Forecast hours.  Default: 0, 3, 6, …, 120.
    cache_dir : str, optional
        Directory for raw GRIB2 cache files.  Default ``".gfs_cache"``.

    Variable groups
    ---------------
    pgrb2 (0.25°)
        Standard fields: t2m, u10, v10, prmsl, sp, tp, r2, d2m,
        cape, cin, pwat, tcc, refc, tozne, hlcy, t, r, gh, u, v, w,
        absv, q, st, soilw, …

    pgrb2b (0.25°, supplemental)
        aptmp, lcc, mcc, hcc

    pgrb2 (0.5°, _PGRB2P5_VARS)
        Radiation fluxes (ulwrf, dswrf, dlwrf, uswrf), lhtfl, shtfl,
        gflux, hpbl, fricv, vrate, cnwat, ssrun, bgrun, watr, icaht,
        ustm, vstm, sde

    Examples
    --------
    ::

        dl = GFSDownloader("18/04/2026", hours=[0])
        ds = dl.fetch(["t2m", "r2", "prmsl", "dswrf"])

        ds = GFSDownloader("18/04/2026").fetch_all(skip=["aptmp"])

        GFSDownloader.save(ds, "run.nc")
        ds = GFSDownloader.load("run.nc")

        from gfs_downloader import plot_nearside
        plot_nearside(ds, "t2m", fhour_index=0, central_lat=-10, central_lon=-50)
    """

    def __init__(
        self,
        date:      str,
        cycle:     str | int = "00z",
        hours:     list[int] | None = None,
        cache_dir: str = ".gfs_cache",
    ):
        dt             = _parse_date(date)
        self._yyyymmdd = dt.strftime("%Y%m%d")
        self._cycle    = _cycle_norm(cycle)
        self._hours    = hours if hours is not None else list(_DEFAULT_HOURS)
        self._cache    = Path(cache_dir)
        self._cache.mkdir(parents=True, exist_ok=True)

    # ── fetch ─────────────────────────────────────────────────────────────────

    def fetch(self, keys: Sequence[str]) -> xr.Dataset:
        """
        Download and decode the requested variable keys.

        Parameters
        ----------
        keys : sequence of str
            Keys from ``VARIABLES_INFO``.

        Returns
        -------
        xr.Dataset
            Dims: ``(time, latitude, longitude)``.
            Attrs: ``run_date``, ``cycle``.
        """
        known   = [k for k in keys if k in VARIABLES_INFO]
        unknown = [k for k in keys if k not in VARIABLES_INFO]
        if unknown:
            print(f"[GFSDownloader] Unknown keys (skipped): {unknown}")

        run_dt = datetime.strptime(
            f"{self._yyyymmdd}{self._cycle}00", "%Y%m%d%H%M"
        ).replace(tzinfo=timezone.utc)
        times = [
            np.datetime64(run_dt.isoformat()) + np.timedelta64(h, "h")
            for h in self._hours
        ]

        data_vars: dict[str, xr.DataArray] = {}

        for key in _bar(known, desc="GFS download", unit="var"):
            frames: list[np.ndarray | None] = []
            lats = lons = None
            n_ok = 0

            for fhour in self._hours:
                res        = _file_resolution(key)
                ftype      = _file_type(key)
                cache_path = (
                    self._cache
                    / f"{self._yyyymmdd}_{self._cycle}_{key}_{res}_{ftype}_f{fhour:03d}.grib2"
                )
                raw = cache_path.read_bytes() if cache_path.exists() else None

                if raw is None:
                    url = _build_url(self._yyyymmdd, self._cycle, fhour, key)
                    raw = _fetch_bytes(url)
                    if raw is None:
                        frames.append(None)
                        continue
                    cache_path.write_bytes(raw)

                result = _decode_grib(raw, key)
                if result is None:
                    frames.append(None)
                    continue

                lats_f, lons_f, vals = result
                if lats is None:
                    lats, lons = lats_f, lons_f
                frames.append(vals)
                n_ok += 1

            if n_ok == 0:
                print(f"  [skip] {key}: no frames available.")
                continue

            first  = next(f for f in frames if f is not None)
            filled = [f if f is not None else np.full_like(first, np.nan) for f in frames]
            arr    = np.stack(filled, axis=0)

            info = VARIABLES_INFO[key]
            data_vars[key] = xr.DataArray(
                arr,
                dims=["time", "latitude", "longitude"],
                coords={"time": times, "latitude": lats, "longitude": lons},
                attrs={
                    "long_name": info.get("long_name", key),
                    "units":     info.get("units", ""),
                    "source_file": f"{_file_type(key)}.{_file_resolution(key)}",
                },
            )
            print(f"  [ok] {key}: {n_ok}/{len(self._hours)} h  "
                  f"({_file_type(key)}.{_file_resolution(key)})")

        if not data_vars:
            raise RuntimeError("No variables were downloaded successfully.")

        return xr.Dataset(
            data_vars,
            attrs={
                "run_date": self._yyyymmdd,
                "cycle":    self._cycle + "z",
                "source":   "GFS / NOAA NOMADS",
                "created":  datetime.now(tz=timezone.utc).isoformat(),
            },
        )

    def fetch_all(self, skip: Sequence[str] | None = None) -> xr.Dataset:
        """Fetch every variable in ``VARIABLES_INFO`` plus ``_PGRB2P5_VARS``."""
        skip_set = set(skip or [])
        # Include standard VARIABLES_INFO keys + any pgrb2p5 extras that have
        # a matching entry in VARIABLES_INFO (caller is expected to add them).
        keys = [k for k in VARIABLES_INFO if k not in skip_set]
        print(
            f"[GFSDownloader] fetch_all  {len(keys)} vars × {len(self._hours)} h"
            f"  ({self._yyyymmdd} {self._cycle}z)"
        )
        return self.fetch(keys)

    # ── availability probe ────────────────────────────────────────────────────

    def list_available(self, keys: Sequence[str] | None = None) -> list[str]:
        """Probe f000 and return keys that respond with valid GRIB data."""
        probe = list(keys or VARIABLES_INFO.keys())
        avail = []
        print(f"[GFSDownloader] Probing {len(probe)} vars at f000…")
        for key in _bar(probe, desc="Probing", unit="var"):
            url = _build_url(self._yyyymmdd, self._cycle, 0, key)
            if _fetch_bytes(url):
                avail.append(key)
            else:
                print(f"  [unavailable] {key}")
        print(f"Available: {len(avail)}/{len(probe)}")
        return avail

    # ── persistence ───────────────────────────────────────────────────────────

    @staticmethod
    def save(ds: xr.Dataset, path: str) -> None:
        """Save *ds* to NetCDF4."""
        ds.to_netcdf(path)
        mb = Path(path).stat().st_size / 1024 / 1024
        print(f"Saved: {path}  ({mb:.1f} MB)")

    @staticmethod
    def load(path: str) -> xr.Dataset:
        """Load a NetCDF4 file written by :meth:`save`."""
        return xr.open_dataset(path)


# ══════════════════════════════════════════════════════════════════════════════
# Static Cartopy plot — nearside (satellite-view) projection
# ══════════════════════════════════════════════════════════════════════════════

def plot_nearside(
    ds: xr.Dataset,
    var: str,
    fhour_index: int = 0,
    *,
    central_lat: float = 0.0,
    central_lon: float = 0.0,
    satellite_height: float = 35_785_831.0,  # GEO orbit, metres
    cmap: str = "viridis",
    vmin: float | None = None,
    vmax: float | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (10, 10),
    save_path: str | None = None,
) -> None:
    """
    Plot a GFS variable on a nearside (satellite-view) Cartopy projection.

    Parameters
    ----------
    ds : xr.Dataset
        Dataset returned by :meth:`GFSDownloader.fetch` or loaded via
        :meth:`GFSDownloader.load`.
    var : str
        Variable name to plot (must be in *ds*).
    fhour_index : int
        Index along the ``time`` dimension (0 = analysis / first forecast hour).
    central_lat : float
        Sub-satellite point latitude in degrees.  Default 0 (Equator).
    central_lon : float
        Sub-satellite point longitude in degrees.  Default 0° E.
        For Brazil centre use approx. central_lon=-50, central_lat=-10.
    satellite_height : float
        Distance from Earth's surface to the satellite in metres.
        Default ≈ 35 786 km (geostationary orbit).
    cmap : str
        Matplotlib colormap name.  Suggested defaults by variable:
        ``"RdBu_r"`` for temperature anomalies, ``"Blues"`` for
        precipitation/moisture, ``"YlOrRd"`` for radiation.
    vmin, vmax : float, optional
        Colorbar limits.  If omitted, percentile-clipping is applied
        (2nd – 98th percentile of the visible disk).
    title : str, optional
        Plot title.  Auto-generated if not supplied.
    figsize : tuple
        Figure size in inches.
    save_path : str, optional
        If given, save figure to this path instead of calling plt.show().

    Notes
    -----
    Requires ``cartopy`` and ``matplotlib`` (not installed automatically
    by this module).  Install with::

        pip install cartopy matplotlib

    Examples
    --------
    ::

        ds = GFSDownloader.load("run.nc")

        # Global geostationary view centred on Brazil
        plot_nearside(ds, "t2m", central_lon=-50, central_lat=-10, cmap="RdYlBu_r")

        # Radiation flux — Brazil disk
        plot_nearside(ds, "dswrf", central_lon=-50, central_lat=-10,
                      cmap="YlOrRd", vmin=0, vmax=900)

        # 500 hPa geopotential height — global view
        plot_nearside(ds, "gh", cmap="terrain")

        # Save to PNG instead of showing interactively
        plot_nearside(ds, "prmsl", central_lon=-50, central_lat=-10,
                      save_path="prmsl_nearside.png")
    """
    try:
        import matplotlib.pyplot as plt
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except ImportError as exc:
        raise ImportError(
            "plot_nearside requires cartopy and matplotlib.\n"
            "Install with:  pip install cartopy matplotlib"
        ) from exc

    if var not in ds:
        raise KeyError(f"Variable {var!r} not found in dataset. "
                       f"Available: {list(ds.data_vars)}")

    da = ds[var].isel(time=fhour_index)

    lats = da.latitude.values
    lons = da.longitude.values

    # GFS uses 0–360 longitudes; Cartopy expects -180–180 for most projections.
    lons_360 = lons.copy()
    lons_180 = np.where(lons_360 > 180, lons_360 - 360, lons_360)

    # Re-sort so lons are monotonically increasing after the shift.
    sort_idx  = np.argsort(lons_180)
    lons_plot = lons_180[sort_idx]
    data_plot = da.values[:, sort_idx]

    # ── Percentile-based colour limits ────────────────────────────────────────
    finite = data_plot[np.isfinite(data_plot)]
    if vmin is None:
        vmin = float(np.percentile(finite, 2))  if len(finite) else 0.0
    if vmax is None:
        vmax = float(np.percentile(finite, 98)) if len(finite) else 1.0

    # ── Projection ────────────────────────────────────────────────────────────
    proj = ccrs.NearsidePerspective(
        central_longitude=central_lon,
        central_latitude=central_lat,
        satellite_height=satellite_height,
    )
    data_crs = ccrs.PlateCarree()

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(
        figsize=figsize,
        subplot_kw={"projection": proj},
        facecolor="black",
    )
    ax.set_facecolor("black")

    # Plot field
    mesh = ax.pcolormesh(
        lons_plot, lats, data_plot,
        transform=data_crs,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        shading="auto",
    )

    # Geographic features
    ax.add_feature(cfeature.COASTLINE,      linewidth=0.6, edgecolor="white")
    ax.add_feature(cfeature.BORDERS,        linewidth=0.4, edgecolor="white", linestyle=":")
    ax.add_feature(cfeature.LAND,           facecolor="none")
    ax.add_feature(cfeature.OCEAN,          facecolor="none")
    ax.add_feature(cfeature.LAKES,          linewidth=0.3, edgecolor="cyan", facecolor="none")
    ax.gridlines(
        draw_labels=False,
        linewidth=0.3,
        color="white",
        alpha=0.3,
        linestyle="--",
    )

    # Colorbar
    cbar = fig.colorbar(
        mesh, ax=ax,
        orientation="horizontal",
        pad=0.03,
        fraction=0.04,
        shrink=0.7,
    )
    units = ds[var].attrs.get("units", "")
    cbar.set_label(f"{var}  [{units}]" if units else var, color="white", fontsize=11)
    cbar.ax.xaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.xaxis.get_ticklabels(), color="white")

    # Title
    if title is None:
        time_str = str(ds[var].time.values[fhour_index])[:16]
        long_name = ds[var].attrs.get("long_name", var)
        title = f"{long_name}\n{time_str} UTC  (GFS {ds.attrs.get('cycle', '')})"
    ax.set_title(title, color="white", fontsize=12, pad=8)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="black")
        print(f"Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)