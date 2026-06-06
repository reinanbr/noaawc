from __future__ import annotations

from typing import cast

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature


_REF_LATITUDES = {
    "equator": {
        "lat": 0.0,
        "color": "#1e4a75",
        "lw_factor": 1.4,
        "ls": "-",
        "alpha": 0.70,
    },
    "tropic_cancer": {
        "lat": 23.5,
        "color": "#7a5510",
        "lw_factor": 0.9,
        "ls": "--",
        "alpha": 0.60,
    },
    "tropic_capricorn": {
        "lat": -23.5,
        "color": "#7a5510",
        "lw_factor": 0.9,
        "ls": "--",
        "alpha": 0.60,
    },
    "arctic": {
        "lat": 66.5,
        "color": "#2a5a6b",
        "lw_factor": 0.8,
        "ls": ":",
        "alpha": 0.55,
    },
    "antarctic": {
        "lat": -66.5,
        "color": "#2a5a6b",
        "lw_factor": 0.8,
        "ls": ":",
        "alpha": 0.55,
    },
}

_REF_LONGITUDES = {
    "prime": {
        "lon": 0.0,
        "color": "#3a3f45",
        "lw_factor": 1.1,
        "ls": "-",
        "alpha": 0.55,
    },
    "date_line": {
        "lon": 180.0,
        "color": "#2e3338",
        "lw_factor": 0.9,
        "ls": "--",
        "alpha": 0.45,
    },
    "w90": {
        "lon": -90.0,
        "color": "#1f2328",
        "lw_factor": 0.7,
        "ls": "--",
        "alpha": 0.35,
    },
    "e90": {
        "lon": 90.0,
        "color": "#1f2328",
        "lw_factor": 0.7,
        "ls": "--",
        "alpha": 0.35,
    },
}


def _add_reference_lines(ax: plt.Axes, lw: float = 0.4) -> None:
    transform = ccrs.PlateCarree()
    lon_range = np.linspace(-180, 180, 361)
    lat_range = np.linspace(-90, 90, 181)

    for cfg in _REF_LATITUDES.values():
        ax.plot(
            lon_range,
            np.full_like(lon_range, cast(float, cfg["lat"])),
            transform=transform,
            color=cast(str, cfg["color"]),
            linewidth=lw * cast(float, cfg["lw_factor"]),
            linestyle=cast(str, cfg["ls"]),
            alpha=cast(float, cfg["alpha"]),
            zorder=2,
        )

    for cfg in _REF_LONGITUDES.values():
        ax.plot(
            np.full_like(lat_range, cast(float, cfg["lon"])),
            lat_range,
            transform=transform,
            color=cast(str, cfg["color"]),
            linewidth=lw * cast(float, cfg["lw_factor"]),
            linestyle=cast(str, cfg["ls"]),
            alpha=cast(float, cfg["alpha"]),
            zorder=2,
        )


def _add_features(
    ax: plt.Axes,
    lw: float = 0.4,
    show_states: bool = False,
    show_ocean: bool = False,
) -> None:
    ax.add_feature(cfeature.LAND, facecolor="#13171d", edgecolor="none", zorder=0)
    if show_ocean:
        ax.add_feature(cfeature.OCEAN, facecolor="#0d1520", edgecolor="none", zorder=0)
    ax.add_feature(cfeature.COASTLINE, edgecolor="#2d6db5", linewidth=lw, zorder=3)
    ax.add_feature(cfeature.BORDERS, edgecolor="#2a2f36", linewidth=lw * 0.9, zorder=3)
    if show_states:
        ax.add_feature(
            cfeature.NaturalEarthFeature(
                category="cultural",
                name="admin_1_states_provinces",
                scale="10m",
            ),
            edgecolor="#1e2a35",
            linewidth=lw * 0.3,
            linestyle="--",
            zorder=3,
            facecolor="none",
        )
    _add_reference_lines(ax, lw=lw)
