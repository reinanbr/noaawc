"""
ocean_plots.py
==============
Batch-render all ocean variables (GODAS / OISST / ERSST) in Orthographic
and PlateCarrée projections.  Architecture mirrors test_plot_all_keys.py.

Data sources
------------
OISST v2  — sst (°C)                      0.25°  1981-present
GODAS     — pottmp/salt/ucur/vcur/sshg    ~1°    1980-present
ERSST v5  — sst fallback for pre-1981     2°     1854-present

Usage
-----
    python ocean_plots.py                        # all vars, skip existing
    python ocean_plots.py --force                # re-render everything
    python ocean_plots.py --year 2023 --month 6  # specific month
    python ocean_plots.py --show                 # display interactively
"""

from __future__ import annotations

import argparse
import copy
import traceback
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import xarray as xr
from matplotlib.colors import BoundaryNorm
from scipy.interpolate import RegularGridInterpolator

from kitano import puts
from noawclg.ocean import get_godas, open_ersst
from noaawc.ocean_variables import (
    OCEAN_VARIABLE_PRESETS,
    OCEAN_NO_CONTOUR_VARS,
    OCEAN_VARIABLES_INFO,
)
from noaawc.geo import _add_features, _add_reference_lines
from noaawc.overlays import _colorbar, _title
from noaawc.utils import _font_scale

import noaawc.theme  # noqa: F401 — dark rcParams applied as side effect


# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

# Default date: previous month (GODAS/OISST have ~1-month lag)
_today = date.today()
YEAR: int = _today.year if _today.month > 1 else _today.year - 1
MONTH: int = _today.month - 1 if _today.month > 1 else 12

OUTPUT_ROOT = Path("./plots/ocean")
ERROR_LOG = OUTPUT_ROOT / "errors" / "ocean_errors.txt"

# SST source: "oisst" (0.25°, 1981-present) or "ersst" (2°, 1854-present)
SST_SOURCE: str = "oisst"

# OISST v2 High-Res OPeNDAP endpoint
_OISST_URL = (
    "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.mnmean.nc"
)

# Region presets  (lon in −180/180 convention)
_REGIONS: dict[str, dict] = {
    "global": {
        "toplat": 80.0,
        "bottomlat": -80.0,
        "leftlon": -180.0,
        "rightlon": 180.0,
        "central_lon": 0.0,
    },
    "tropical": {
        "toplat": 25.0,
        "bottomlat": -25.0,
        "leftlon": -180.0,
        "rightlon": 180.0,
        "central_lon": 0.0,
    },
    "pacific": {
        "toplat": 30.0,
        "bottomlat": -30.0,
        "leftlon": 100.0,
        "rightlon": 300.0,
        "central_lon": 200.0,
    },
    "atlantic": {
        "toplat": 65.0,
        "bottomlat": -65.0,
        "leftlon": -80.0,
        "rightlon": 25.0,
        "central_lon": 0.0,
    },
    "indian": {
        "toplat": 30.0,
        "bottomlat": -45.0,
        "leftlon": 30.0,
        "rightlon": 120.0,
        "central_lon": 0.0,
    },
    "enso": {
        "toplat": 10.0,
        "bottomlat": -10.0,
        "leftlon": 120.0,
        "rightlon": 280.0,
        "central_lon": 200.0,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Variable catalogue
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class VarConfig:
    var: str
    depth: float | None
    key: str  # filename-safe identifier
    label: str  # human-readable title


OCEAN_VARS: list[VarConfig] = [
    # ── surface / integrated ──────────────────────────────────────────────────
    VarConfig("sst", None, "sst", "Sea Surface Temperature"),
    VarConfig("sshg", None, "sshg", "Sea Surface Height"),
    # ── near-surface (5 m) ───────────────────────────────────────────────────
    VarConfig("pottmp", 5.0, "pottmp_005m", "Potential Temperature @ 5 m"),
    VarConfig("salt", 5.0, "salt_005m", "Salinity @ 5 m"),
    VarConfig("ucur", 5.0, "ucur_005m", "U Current @ 5 m"),
    VarConfig("vcur", 5.0, "vcur_005m", "V Current @ 5 m"),
    # ── thermocline zone (50 – 200 m) ────────────────────────────────────────
    VarConfig("pottmp", 50.0, "pottmp_050m", "Potential Temperature @ 50 m"),
    VarConfig("pottmp", 100.0, "pottmp_100m", "Potential Temperature @ 100 m"),
    VarConfig("pottmp", 200.0, "pottmp_200m", "Potential Temperature @ 200 m"),
    VarConfig("salt", 100.0, "salt_100m", "Salinity @ 100 m"),
    VarConfig("ucur", 100.0, "ucur_100m", "U Current @ 100 m"),
    VarConfig("vcur", 100.0, "vcur_100m", "V Current @ 100 m"),
    # ── deep ocean (500 m) ───────────────────────────────────────────────────
    VarConfig("pottmp", 500.0, "pottmp_500m", "Potential Temperature @ 500 m"),
    VarConfig("salt", 500.0, "salt_500m", "Salinity @ 500 m"),
]


# ══════════════════════════════════════════════════════════════════════════════
# Projection profiles
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class Profile:
    mode: str
    subdir: str
    suffix: str
    configure: Callable[[VarConfig], dict]  # returns extra kwargs for plot_fn
    plot_fn: Callable  # plot_ortho | plot_plate


def _cfg_ortho_global(cfg: VarConfig) -> dict:
    return {"central_lon": 0.0, "central_lat": 0.0}


def _cfg_ortho_pacific(cfg: VarConfig) -> dict:
    return {"central_lon": 200.0, "central_lat": 0.0}


def _cfg_plate_global(cfg: VarConfig) -> dict:
    return {"region": "global"}


def _cfg_plate_tropical(cfg: VarConfig) -> dict:
    return {"region": "tropical"}


PROFILES: list[Profile] = [
    Profile(
        mode="ortho",
        subdir="ortho",
        suffix="_ortho.png",
        configure=_cfg_ortho_global,
        plot_fn=None,  # filled after plot_ortho is defined
    ),
    Profile(
        mode="ortho",
        subdir="ortho_pacific",
        suffix="_ortho_pac.png",
        configure=_cfg_ortho_pacific,
        plot_fn=None,
    ),
    Profile(
        mode="plate",
        subdir="plate",
        suffix="_plate.png",
        configure=_cfg_plate_global,
        plot_fn=None,
    ),
    Profile(
        mode="plate",
        subdir="plate_tropical",
        suffix="_plate_trop.png",
        configure=_cfg_plate_tropical,
        plot_fn=None,
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# Data loading
# ══════════════════════════════════════════════════════════════════════════════


def _to_180(lon: np.ndarray) -> np.ndarray:
    return np.where(lon > 180.0, lon - 360.0, lon)


def open_oisst(year: int, month: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load one month of NOAA OISST v2 High-Res SST (0.25°, 1981-present)."""
    ds = xr.open_dataset(_OISST_URL, engine="netcdf4")
    sst = ds["sst"].squeeze()

    target = np.datetime64(f"{year}-{month:02d}")
    tidx = int(np.argmin(np.abs(sst["time"].values - target)))
    field = sst.isel(time=tidx).values.astype(float)

    lat = sst["lat"].values.astype(float)
    lon_raw = sst["lon"].values.astype(float)

    fv = sst.attrs.get("missing_value", sst.attrs.get("_FillValue", None))
    if fv is not None:
        field = np.where(field == float(fv), np.nan, field)
    field = np.where(np.abs(field) > 100, np.nan, field)

    if lat[0] > lat[-1]:
        lat, field = lat[::-1], field[::-1, :]

    lon_180 = _to_180(lon_raw)
    idx = np.argsort(lon_180)
    return lat, lon_180[idx], field[:, idx]


def _load(
    var: str,
    year: int,
    month: int,
    depth_m: float | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (lat 1-D asc, lon 1-D −180/180 asc, field 2-D)."""
    info = OCEAN_VARIABLES_INFO[var]

    if info["source"] == "ERSST":
        if SST_SOURCE == "oisst" and year >= 1981:
            return open_oisst(year, month)
        target = np.datetime64(f"{year}-{month:02d}")
        da = open_ersst(year, year)
        tidx = int(np.argmin(np.abs(da["time"].values - target)))
        lat = da["lat"].values.astype(float)
        lon_raw = da["lon"].values.astype(float)
        field = da.isel(time=tidx).values.astype(float)
    else:
        target = np.datetime64(f"{year}-{month:02d}")
        depth_arg = depth_m if info.get("has_levels") else None
        da = get_godas(year, year, variable=var, depth_m=depth_arg)
        tidx = int(np.argmin(np.abs(da["time"].values - target)))
        lat = da["lat"].values.astype(float)
        lon_raw = da["lon"].values.astype(float)
        field = da.isel(time=tidx).values.astype(float)

    if lat[0] > lat[-1]:
        lat, field = lat[::-1], field[::-1, :]

    lon_180 = _to_180(lon_raw)
    idx = np.argsort(lon_180)
    return lat, lon_180[idx], field[:, idx]


# ══════════════════════════════════════════════════════════════════════════════
# Grid upsampling
# ══════════════════════════════════════════════════════════════════════════════


def _upsample(
    lat: np.ndarray,
    lon: np.ndarray,
    field: np.ndarray,
    factor: int = 4,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Bilinear upsampling by *factor*.  NaN propagates so coastlines stay sharp.
    factor=4 → ERSST 2° → 0.5°; GODAS 1° → 0.25°; OISST 0.25° → 0.06° (skip).
    """
    lat_new = np.linspace(lat[0], lat[-1], len(lat) * factor)
    lon_new = np.linspace(lon[0], lon[-1], len(lon) * factor)
    interp = RegularGridInterpolator(
        (lat, lon),
        field,
        method="linear",
        bounds_error=False,
        fill_value=np.nan,
    )
    lon_g, lat_g = np.meshgrid(lon_new, lat_new)
    return lat_new, lon_new, interp((lat_g, lon_g))


# ══════════════════════════════════════════════════════════════════════════════
# Shared render helpers
# ══════════════════════════════════════════════════════════════════════════════


def _norm_cmap(levels: np.ndarray, cmap):
    cm = copy.copy(cmap)
    cm.set_under(alpha=0)
    cm.set_bad(alpha=0)
    return BoundaryNorm(levels, ncolors=cm.N, clip=False), cm


def _contours(ax, lat, lon, field, levels, var, dpi: int) -> None:
    if var in OCEAN_NO_CONTOUR_VARS:
        return
    stride = max(1, len(lat) // 90)
    scale = _font_scale(dpi)
    try:
        ax.contour(
            lon[::stride],
            lat[::stride],
            field[::stride, ::stride],
            levels=levels[::5],
            colors="white",
            linewidths=0.25 * scale,
            alpha=0.35,
            transform=ccrs.PlateCarree(),
            zorder=2,
        )
    except Exception:
        pass


def _depth_tag(depth_m: float | None) -> str:
    return f" @ {depth_m:.0f} m" if depth_m is not None else ""


def _finalize(fig, save: str | None, show: bool, dpi: int) -> None:
    fig.tight_layout()
    if save:
        Path(save).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save, format="png", dpi=dpi, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# plot_ortho / plot_plate
# ══════════════════════════════════════════════════════════════════════════════


def plot_ortho(
    var: str,
    year: int,
    month: int,
    *,
    depth_m: float | None = None,
    central_lon: float = 0.0,
    central_lat: float = 0.0,
    upsample: int = 4,
    save: str | None = None,
    show: bool = False,
    dpi: int = 150,
    figsize: tuple[float, float] = (8.0, 8.0),
) -> None:
    """Orthographic (globe) map of an ocean variable."""
    preset = OCEAN_VARIABLE_PRESETS[var]
    lat, lon, field = _load(var, year, month, depth_m)
    if upsample > 1:
        lat, lon, field = _upsample(lat, lon, field, factor=upsample)
    levels = np.asarray(preset["levels"])
    scale = _font_scale(dpi)
    norm, cmap = _norm_cmap(levels, preset["cmap"])

    proj = ccrs.Orthographic(
        central_longitude=central_lon, central_latitude=central_lat
    )
    fig, ax = plt.subplots(
        figsize=figsize,
        subplot_kw={"projection": proj},
        facecolor="#0d1117",
        dpi=dpi,
    )
    ax.set_global()
    _add_features(ax, lw=0.5 * scale, show_states=False)
    _add_reference_lines(ax, lw=0.3 * scale)

    cf = ax.pcolormesh(
        lon, lat, field, cmap=cmap, norm=norm, transform=ccrs.PlateCarree(), zorder=1
    )
    _contours(ax, lat, lon, field, levels, var, dpi)
    _colorbar(fig, cf, ax, preset["cbar_label"], scale=scale)
    _title(
        ax,
        f"{preset['plot_title']}{_depth_tag(depth_m)}",
        f"{year}-{month:02d}",
        scale=scale,
    )

    _finalize(fig, save, show, dpi)


def plot_plate(
    var: str,
    year: int,
    month: int,
    *,
    depth_m: float | None = None,
    region: str = "global",
    upsample: int = 4,
    save: str | None = None,
    show: bool = False,
    dpi: int = 120,
    figsize: tuple[float, float] = (16.0, 9.0),
) -> None:
    """PlateCarrée (equirectangular) map of an ocean variable."""
    preset = OCEAN_VARIABLE_PRESETS[var]
    lat, lon, field = _load(var, year, month, depth_m)
    if upsample > 1:
        lat, lon, field = _upsample(lat, lon, field, factor=upsample)
    levels = np.asarray(preset["levels"])
    r = _REGIONS.get(region, _REGIONS["global"])
    scale = _font_scale(dpi)
    norm, cmap = _norm_cmap(levels, preset["cmap"])

    proj = ccrs.PlateCarree(central_longitude=r["central_lon"])
    fig, ax = plt.subplots(
        figsize=figsize,
        subplot_kw={"projection": proj},
        facecolor="#0d1117",
        dpi=dpi,
    )
    ax.set_extent(
        [r["leftlon"], r["rightlon"], r["bottomlat"], r["toplat"]],
        crs=ccrs.PlateCarree(),
    )
    _add_features(ax, lw=0.5 * scale, show_states=False, show_ocean=True)
    _add_reference_lines(ax, lw=0.3 * scale)

    step = 30 if region in ("global", "tropical", "pacific", "enso") else 15
    gl = ax.gridlines(
        crs=ccrs.PlateCarree(),
        draw_labels=True,
        linewidth=0.3 * scale,
        color="#14181c",
        alpha=0.7,
        linestyle="--",
        zorder=2,
    )
    gl.top_labels = False
    gl.right_labels = False
    gl.xlocator = mticker.MultipleLocator(step)
    gl.ylocator = mticker.MultipleLocator(step // 2)
    gl.xlabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}
    gl.ylabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}

    cf = ax.pcolormesh(
        lon, lat, field, cmap=cmap, norm=norm, transform=ccrs.PlateCarree(), zorder=1
    )
    _contours(ax, lat, lon, field, levels, var, dpi)
    _colorbar(fig, cf, ax, preset["cbar_label"], scale=scale)
    _title(
        ax,
        f"{preset['plot_title']}{_depth_tag(depth_m)}",
        f"{year}-{month:02d}  |  {region}",
        scale=scale,
    )

    _finalize(fig, save, show, dpi)


# Wire up profile plot_fn references now that the functions are defined
PROFILES[0].plot_fn = plot_ortho
PROFILES[1].plot_fn = plot_ortho
PROFILES[2].plot_fn = plot_plate
PROFILES[3].plot_fn = plot_plate


# ══════════════════════════════════════════════════════════════════════════════
# Batch infrastructure  (mirrors test_plot_all_keys.py)
# ══════════════════════════════════════════════════════════════════════════════


def output_path(profile: Profile, cfg: VarConfig) -> Path:
    return OUTPUT_ROOT / profile.subdir / f"{cfg.key}{profile.suffix}"


def log_error(cfg: VarConfig, profile: Profile, exc: Exception) -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = (
        f"[{profile.mode.upper()}] [{cfg.key} — {cfg.label}]\n"
        f"{traceback.format_exc()}\n" + "─" * 60 + "\n"
    )
    with ERROR_LOG.open("a") as fh:
        fh.write(entry)


def process(
    cfg: VarConfig,
    profile: Profile,
    year: int,
    month: int,
    force: bool = False,
    show: bool = False,
) -> bool:
    """Render one variable × one projection.  Returns True if a new file was saved."""
    path = output_path(profile, cfg)

    if path.exists() and not force:
        puts(f"    skip  [{profile.mode}] {cfg.key}  →  already exists")
        return False

    extra = profile.configure(cfg)
    profile.plot_fn(
        cfg.var,
        year,
        month,
        depth_m=cfg.depth,
        save=str(path),
        show=show,
        **extra,
    )
    puts(f"    saved  [{profile.mode}] {cfg.key}  →  {path}")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# CLI + main
# ══════════════════════════════════════════════════════════════════════════════


def _parse_args():
    p = argparse.ArgumentParser(
        description="Ocean data batch plots — Orthographic + PlateCarrée"
    )
    p.add_argument("--year", type=int, default=YEAR, help=f"Year   (default: {YEAR})")
    p.add_argument(
        "--month", type=int, default=MONTH, help=f"Month  (default: {MONTH})"
    )
    p.add_argument(
        "--force", action="store_true", help="Re-render even if file already exists"
    )
    p.add_argument("--show", action="store_true", help="Display plots interactively")
    p.add_argument(
        "--var",
        default=None,
        help="Render only this variable key  (e.g. sst, pottmp_100m)",
    )
    p.add_argument(
        "--mode",
        default=None,
        choices=["ortho", "plate"],
        help="Render only this projection mode",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    vars_to_run = [c for c in OCEAN_VARS if args.var is None or c.key == args.var]
    profiles_to_run = [p for p in PROFILES if args.mode is None or p.mode == args.mode]

    total = len(vars_to_run) * len(profiles_to_run)
    puts(
        f"Ocean plots — {len(vars_to_run)} variable(s) × "
        f"{len(profiles_to_run)} projection(s) = {total} plots  "
        f"[{args.year}-{args.month:02d}]\n"
    )

    ok = skipped = errors = 0

    for cfg in vars_to_run:
        puts(f"  {cfg.key}  ({cfg.label})")
        for profile in profiles_to_run:
            try:
                saved = process(
                    cfg,
                    profile,
                    args.year,
                    args.month,
                    force=args.force,
                    show=args.show,
                )
                if saved:
                    ok += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                log_error(cfg, profile, exc)
                puts(f"    error  [{profile.mode}] {cfg.key}: {exc}")

    puts(f"\nDone — ok={ok}  skipped={skipped}  errors={errors}")
    if errors:
        puts(f"Error details → {ERROR_LOG}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
