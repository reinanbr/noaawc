# mypy: disable-error-code=attr-defined
"""
Oceanic variable catalogue and plot presets for GODAS and ERSST data.

Data sources
------------
NOAA NCEP GODAS  — Monthly subsurface fields (1980-present, ~1/3°×1°, 40 levels)
NOAA ERSST v5    — Monthly SST record (1854-present, 2° grid)

Variables
---------
GODAS: pottmp, salt, ucur, vcur, sshg
ERSST: sst
"""

from __future__ import annotations

from typing import Any

import numpy as np
import matplotlib.pyplot as plt
import cmocean


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _lev(start: float, stop: float, step: float) -> np.ndarray:
    return np.arange(start, stop + step * 0.01, step)


# ══════════════════════════════════════════════════════════════════════════════
# GODAS depth levels (m) — 40 levels, 5 m to 4 478 m
# ══════════════════════════════════════════════════════════════════════════════

GODAS_LEVELS: np.ndarray = np.array(
    [
        5,
        15,
        25,
        35,
        45,
        55,
        65,
        75,
        85,
        95,
        105,
        115,
        125,
        135,
        145,
        155,
        165,
        175,
        185,
        195,
        205,
        215,
        225,
        238,
        262,
        303,
        366,
        459,
        584,
        747,
        949,
        1193,
        1479,
        1807,
        2174,
        2579,
        3016,
        3483,
        3972,
        4478,
    ],
    dtype=float,
)

#: Shallow levels suitable for surface/mixed-layer analysis (≤ 300 m)
GODAS_LEVELS_SHALLOW: np.ndarray = GODAS_LEVELS[GODAS_LEVELS <= 300]

#: Deep levels for thermohaline structure (> 300 m)
GODAS_LEVELS_DEEP: np.ndarray = GODAS_LEVELS[GODAS_LEVELS > 300]


# ══════════════════════════════════════════════════════════════════════════════
# ENSO monitoring regions (longitude 0–360 convention)
# ══════════════════════════════════════════════════════════════════════════════

NINO_BOXES: dict[str, dict] = {
    "1+2": {"lat": (-10.0, 0.0), "lon": (270.0, 280.0)},
    "3": {"lat": (-5.0, 5.0), "lon": (210.0, 270.0)},
    "3.4": {"lat": (-5.0, 5.0), "lon": (190.0, 240.0)},
    "4": {"lat": (-5.0, 5.0), "lon": (160.0, 210.0)},
}

#: Warm Water Volume integration box (5°S–5°N, 120°E–80°W)
WWV_BOX: dict = {"lat": (-5.0, 5.0), "lon": (120.0, 280.0)}


# ══════════════════════════════════════════════════════════════════════════════
# OCEAN_VARIABLES_INFO — metadata catalog (mirrors noawclg.ocean.GODAS_VARS)
# ══════════════════════════════════════════════════════════════════════════════

OCEAN_VARIABLES_INFO: dict[str, dict[str, Any]] = {
    # ── GODAS subsurface fields ───────────────────────────────────────────────
    "pottmp": {
        "short": "pottmp",
        "long_name": "Potential temperature",
        "units_in": "K",
        "units": "°C",
        "source": "GODAS",
        "has_levels": True,
        "valid_min": 200.0,
        "converter": lambda x: x - 273.15,
        "multilevel": True,
        "levels_ref": GODAS_LEVELS,
    },
    "salt": {
        "short": "salt",
        "long_name": "Salinity",
        "units_in": "kg/kg",
        "units": "PSU",
        "source": "GODAS",
        "has_levels": True,
        "valid_min": 0.001,
        "converter": lambda x: x * 1000.0,
        "multilevel": True,
        "levels_ref": GODAS_LEVELS,
    },
    "ucur": {
        "short": "ucur",
        "long_name": "U-component of ocean current (eastward)",
        "units_in": "m/s",
        "units": "m/s",
        "source": "GODAS",
        "has_levels": True,
        "valid_min": None,
        "converter": None,
        "multilevel": True,
        "levels_ref": GODAS_LEVELS,
    },
    "vcur": {
        "short": "vcur",
        "long_name": "V-component of ocean current (northward)",
        "units_in": "m/s",
        "units": "m/s",
        "source": "GODAS",
        "has_levels": True,
        "valid_min": None,
        "converter": None,
        "multilevel": True,
        "levels_ref": GODAS_LEVELS,
    },
    "sshg": {
        "short": "sshg",
        "long_name": "Sea Surface Height relative to geoid",
        "units_in": "m",
        "units": "m",
        "source": "GODAS",
        "has_levels": False,
        "valid_min": None,
        "converter": None,
        "multilevel": False,
    },
    # ── ERSST v5 ──────────────────────────────────────────────────────────────
    "sst": {
        "short": "sst",
        "long_name": "Sea Surface Temperature",
        "units_in": "°C",
        "units": "°C",
        "source": "ERSST",
        "has_levels": False,
        "valid_min": None,
        "converter": None,
        "multilevel": False,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# OCEAN_VARIABLE_PRESETS — colormap / levels / labels for plotting
# ══════════════════════════════════════════════════════════════════════════════

OCEAN_VARIABLE_PRESETS: dict[str, dict[str, Any]] = {
    # ── Potential temperature ─────────────────────────────────────────────────
    # cmocean.thermal: perceptually uniform warm palette — standard for ocean T
    "pottmp": {
        "cmap": cmocean.cm.thermal,
        "levels": _lev(-2, 32, 2),
        "cbar_label": "Potential Temperature (°C)",
        "plot_title": "Ocean Potential Temperature",
    },
    # ── Salinity ──────────────────────────────────────────────────────────────
    # cmocean.haline: designed specifically for salinity (blue → green → yellow)
    "salt": {
        "cmap": cmocean.cm.haline,
        "levels": _lev(30, 38, 0.5),
        "cbar_label": "Salinity (PSU)",
        "plot_title": "Ocean Salinity",
    },
    # ── Ocean currents (diverging ± around zero) ──────────────────────────────
    "ucur": {
        "cmap": plt.cm.RdBu_r,
        "levels": _lev(-2.0, 2.0, 0.2),
        "cbar_label": "U Current (m s⁻¹)",
        "plot_title": "Eastward Ocean Current",
    },
    "vcur": {
        "cmap": plt.cm.RdBu_r,
        "levels": _lev(-2.0, 2.0, 0.2),
        "cbar_label": "V Current (m s⁻¹)",
        "plot_title": "Northward Ocean Current",
    },
    # Derived: current speed (magnitude)
    "speed": {
        "cmap": cmocean.cm.speed,
        "levels": _lev(0, 2.5, 0.1),
        "cbar_label": "Current Speed (m s⁻¹)",
        "plot_title": "Ocean Current Speed",
    },
    # ── Sea Surface Height ─────────────────────────────────────────────────────
    # cmocean.balance: diverging palette symmetric around zero — ideal for SSH
    "sshg": {
        "cmap": cmocean.cm.balance,
        "levels": _lev(-0.5, 0.5, 0.05),
        "cbar_label": "SSH anomaly (m)",
        "plot_title": "Sea Surface Height (relative to geoid)",
    },
    # ── ERSST Sea Surface Temperature ─────────────────────────────────────────
    "sst": {
        "cmap": cmocean.cm.thermal,
        "levels": _lev(-2, 32, 2),
        "cbar_label": "SST (°C)",
        "plot_title": "Sea Surface Temperature (ERSST v5)",
    },
    # ── Thermocline depth D20 ─────────────────────────────────────────────────
    # cmocean.deep: sequential deep-ocean blue — deeper = darker
    "d20": {
        "cmap": cmocean.cm.deep,
        "levels": np.array(
            [20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 250, 300]
        ),
        "cbar_label": "D20 Thermocline Depth (m)",
        "plot_title": "Depth of 20 °C Isotherm (D20)",
    },
    # ── Niño 3.4 SST anomaly ──────────────────────────────────────────────────
    # cmocean.balance: diverging blue (cool/La Niña) ↔ red (warm/El Niño)
    "sst_anom": {
        "cmap": cmocean.cm.balance,
        "levels": _lev(-3.0, 3.0, 0.25),
        "cbar_label": "SST Anomaly (°C)",
        "plot_title": "SST Anomaly (relative to 1991–2020 climatology)",
    },
}


# ── Ocean variables that should not display contour lines ─────────────────────
# Current components: noisy diverging fields where contours add clutter.
# SSH: the colormap gradient already encodes the anomaly magnitude clearly.
OCEAN_NO_CONTOUR_VARS: frozenset[str] = frozenset({"ucur", "vcur", "speed", "sshg"})


# ── Convenience lists ─────────────────────────────────────────────────────────
GODAS_VARS: list[str] = ["pottmp", "salt", "ucur", "vcur", "sshg"]
ERSST_VARS: list[str] = ["sst"]
OCEAN_MULTILEVEL_VARS: list[str] = [
    k for k, v in OCEAN_VARIABLES_INFO.items() if v.get("multilevel")
]
OCEAN_SURFACE_VARS: list[str] = [
    k for k, v in OCEAN_VARIABLES_INFO.items() if not v.get("multilevel")
]


# ── Helper ────────────────────────────────────────────────────────────────────


def list_ocean_variable_presets() -> None:
    """Print all ocean variable presets: colormap, level range, and label."""
    print(
        f"\n  {'Variable':<12}  {'Source':<8}  {'Colormap':<22}  {'Range (N steps)':<30}  Label"
    )
    print("  " + "─" * 110)
    for key, p in OCEAN_VARIABLE_PRESETS.items():
        lvl = np.asarray(p["levels"])
        lvl_str = f"{lvl[0]:.3g} … {lvl[-1]:.3g}  ({len(lvl)} steps)"
        cmap_name = getattr(p["cmap"], "name", str(p["cmap"]))
        src = OCEAN_VARIABLES_INFO.get(key, {}).get("source", "derived")
        print(
            f"  {key:<12}  {src:<8}  {cmap_name:<22}  {lvl_str:<30}  {p['cbar_label']}"
        )
    print()
