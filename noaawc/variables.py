"""
presets_extended.py
-------------------
Plotting presets for every variable defined in variables.py (VARIABLES dict).

Imported by animator.py — do not import animator.py from here (avoid cycles).

Each entry in VARIABLE_PRESETS defines:
    cmap        : matplotlib colormap object
    levels      : 1-D numpy array of BoundaryNorm / contour boundaries
    cbar_label  : colorbar axis label (with units)
    plot_title  : left-side per-frame title

Design rationale per group
--------------------------
Temperature             cmocean.thermal     perceptually uniform, warm palette
Dewpoint / humidity     cmocean.haline      blue-green, intuitive for moisture
Wind components         plt.RdBu_r          diverging ±, zero at center
Wind speed / gust       cmocean.speed       sequential white→dark
Pressure                plt.RdBu_r          diverging: blue=low, red=high
Precipitation           cmocean.rain        white→navy, log-spaced levels
Cloud / water / snow    cmocean.ice         white→dark: dense = darker
Soil                    cmocean.matter      brown earth tones
Convection (CAPE)       plt.YlOrRd          yellow→red instability
Convection (CIN/LI)     plt.RdBu_r          diverging: stable=blue, unstable=red
Vorticity / omega       plt.RdBu_r          diverging ± around zero
Categorical precip      plt.Blues/winter…   two-tone binary (0=no, 1=yes)
Reflectivity            _REFC_CMAP          18-colour NWS WSR-88D standard palette
Ozone / diagnostics     cmocean.deep        sequential deep-ocean repurposed
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cmocean
from typing import Any


# ── helpers ───────────────────────────────────────────────────────────────────

def _lev(start: float, stop: float, step: float) -> np.ndarray:
    """np.arange shorthand that always includes *stop* when exactly reachable."""
    return np.arange(start, stop + step * 0.01, step)


# ── NWS WSR-88D radar reflectivity palette (18 colours) ──────────────────────
_REFC_COLORS = [
    "#646464", "#04e9e7", "#019ff4", "#0300f4",
    "#02fd02", "#01c501", "#008e00", "#fdf802",
    "#e5bc00", "#fd9500", "#fd0000", "#d40000",
    "#bc0000", "#f800fd", "#9854c6", "#fdfdfd",
    "#ffffff", "#ffffff",
]
_REFC_CMAP = mcolors.ListedColormap(_REFC_COLORS, name="nws_refc")


# ══════════════════════════════════════════════════════════════════════════════
# VARIABLE_PRESETS
# One entry per key in VARIABLES.  OrthoAnimator loads the matching entry
# automatically; no preset → falls back to "t2m" with a printed warning.
# ══════════════════════════════════════════════════════════════════════════════

VARIABLE_PRESETS: dict[str, dict] = {

    # ── 2-metre / surface temperature ────────────────────────────────────────

    "t2m": {
        "cmap":       cmocean.cm.thermal,
        "levels":     _lev(-20, 50, 2),
        "cbar_label": "2-m Temperature (°C)",
        "plot_title": "2-m Temperature",
    },
    "d2m": {
        "cmap":       cmocean.cm.haline,
        "levels":     _lev(-30, 30, 2),
        "cbar_label": "2-m Dewpoint Temperature (°C)",
        "plot_title": "2-m Dewpoint Temperature",
    },
    # pgrb2b_only — falls back to calculation from t2m + r2 + wind if needed
    "aptmp": {
        "cmap":       cmocean.cm.thermal,
        "levels":     _lev(-30, 50, 2),
        "cbar_label": "Apparent Temperature (°C)",
        "plot_title": "Apparent Temperature (Heat Index / Wind Chill)",
    },

    # ── humidity ──────────────────────────────────────────────────────────────

    "r2": {
        "cmap":       cmocean.cm.haline,
        "levels":     _lev(0, 100, 5),
        "cbar_label": "2-m Relative Humidity (%)",
        "plot_title": "2-m Relative Humidity",
    },
    "sh2": {
        "cmap":       cmocean.cm.haline,
        "levels":     np.array([0, 1, 2, 4, 6, 8, 10, 12, 15, 18, 22, 26]) * 1e-3,
        "cbar_label": "2-m Specific Humidity (kg kg\u207b\u00b9)",
        "plot_title": "2-m Specific Humidity",
    },
    "pwat": {
        "cmap":       cmocean.cm.haline,
        "levels":     _lev(0, 80, 4),
        "cbar_label": "Precipitable Water (kg m\u207b\u00b2)",
        "plot_title": "Precipitable Water",
    },
    "cwat": {
        "cmap":       cmocean.cm.ice,
        "levels":     np.array([0, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8,
                                 1.0, 1.5, 2.0, 3.0, 5.0]),
        "cbar_label": "Column Cloud Water (kg m\u207b\u00b2)",
        "plot_title": "Column Cloud Water",
    },

    # ── 10-metre wind ─────────────────────────────────────────────────────────

    "u10": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     _lev(-30, 30, 2),
        "cbar_label": "10-m U Wind Component (m s\u207b\u00b9)",
        "plot_title": "10-m U Wind Component",
    },
    "v10": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     _lev(-30, 30, 2),
        "cbar_label": "10-m V Wind Component (m s\u207b\u00b9)",
        "plot_title": "10-m V Wind Component",
    },

    # ── 10-metre wind speed (scalar magnitude from u10 + v10) ────────────────
    #
    # "wspd10" is a derived variable — it is NOT present directly in GFS GRIB2
    # files. You must compute it before passing to OrthoAnimator:
    #
    #   ds["wspd10"] = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)
    #
    # cmocean.cm.speed maps white (calm) → dark teal (strong winds), which is
    # perceptually intuitive and colour-blind safe.
    # Levels cover 0–30 m/s (calm to hurricane-force), step 1 m/s.
    # Extend the upper bound for tropical applications (e.g. _lev(0, 60, 2)).
    #
    "wspd10": {
        "cmap":       cmocean.cm.speed,
        "levels":     _lev(0, 30, 1),
        "cbar_label": "10-m Wind Speed (m s\u207b\u00b9)",
        "plot_title": "10-m Wind Speed",
    },

    "gust": {
        "cmap":       cmocean.cm.speed,
        "levels":     _lev(0, 50, 2),
        "cbar_label": "Wind Speed Gust (m s\u207b\u00b9)",
        "plot_title": "Surface Wind Gust",
    },

    # ── pressure ──────────────────────────────────────────────────────────────

    "prmsl": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     _lev(960, 1044, 2),
        "cbar_label": "MSLP (hPa)",
        "plot_title": "Mean Sea-Level Pressure",
    },
    "mslet": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     _lev(960, 1044, 2),
        "cbar_label": "MSLP \u2014 Eta Reduction (hPa)",
        "plot_title": "MSLP (Eta Model Reduction)",
    },
    "sp": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     _lev(500, 1050, 10),
        "cbar_label": "Surface Pressure (hPa)",
        "plot_title": "Surface Pressure",
    },

    # ── topography / static ───────────────────────────────────────────────────

    "orog": {
        "cmap":       cmocean.cm.topo,
        "levels":     np.array([0, 50, 100, 200, 400, 600, 800, 1000,
                                 1500, 2000, 2500, 3000, 4000, 5000, 6000]),
        "cbar_label": "Orography (m)",
        "plot_title": "Orography (Surface Height)",
    },
    "lsm": {
        "cmap":       plt.cm.BrBG,
        "levels":     np.linspace(0, 1, 11),
        "cbar_label": "Land-Sea Mask (0=sea  1=land)",
        "plot_title": "Land-Sea Mask",
    },
    "veg": {
        "cmap":       cmocean.cm.algae,
        "levels":     _lev(0, 100, 5),
        "cbar_label": "Vegetation (%)",
        "plot_title": "Vegetation Fraction",
    },

    # ── visibility ────────────────────────────────────────────────────────────

    "vis": {
        "cmap":       cmocean.cm.gray,
        "levels":     np.array([0, 200, 500, 1000, 2000, 4000, 6000,
                                 8000, 10000, 15000, 20000, 30000, 50000]),
        "cbar_label": "Visibility (m)",
        "plot_title": "Surface Visibility",
    },

    # ── precipitation / hydrology ─────────────────────────────────────────────

    "prate": {
        "cmap":       cmocean.cm.rain,
        "levels":     np.array([0, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64]),
        "cbar_label": "Precipitation Rate (mm h\u207b\u00b9)",
        "plot_title": "Precipitation Rate",
    },
    "cpofp": {
        "cmap":       plt.cm.cool,
        "levels":     _lev(0, 100, 10),
        "cbar_label": "Frozen Precipitation (%)",
        "plot_title": "Percent Frozen Precipitation",
    },
    # Categorical fields: binary 0/1 — two-tone palette, levels straddle 0.5
    "crain": {
        "cmap":       plt.cm.Blues,
        "levels":     np.array([-0.5, 0.5, 1.5]),
        "cbar_label": "Categorical Rain (0=no  1=yes)",
        "plot_title": "Categorical Rain",
    },
    "csnow": {
        "cmap":       plt.cm.winter,
        "levels":     np.array([-0.5, 0.5, 1.5]),
        "cbar_label": "Categorical Snow (0=no  1=yes)",
        "plot_title": "Categorical Snow",
    },
    "cfrzr": {
        "cmap":       plt.cm.PuBu,
        "levels":     np.array([-0.5, 0.5, 1.5]),
        "cbar_label": "Categorical Freezing Rain (0=no  1=yes)",
        "plot_title": "Categorical Freezing Rain",
    },
    "cicep": {
        "cmap":       plt.cm.Purples,
        "levels":     np.array([-0.5, 0.5, 1.5]),
        "cbar_label": "Categorical Ice Pellets (0=no  1=yes)",
        "plot_title": "Categorical Ice Pellets",
    },
    "sde": {
        "cmap":       cmocean.cm.ice,
        "levels":     np.array([0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3,
                                 0.5, 0.75, 1.0, 1.5, 2.0]),
        "cbar_label": "Snow Depth (m)",
        "plot_title": "Snow Depth",
    },
    "sdwe": {
        "cmap":       cmocean.cm.ice,
        "levels":     np.array([0, 5, 10, 20, 40, 60, 80, 100,
                                 150, 200, 300, 500]),
        "cbar_label": "Snow Water Equivalent (kg m\u207b\u00b2)",
        "plot_title": "Water Equivalent of Snow Depth",
    },

    # ── cloud cover ───────────────────────────────────────────────────────────

    "tcc": {
        "cmap":       cmocean.cm.ice,
        "levels":     _lev(0, 100, 5),
        "cbar_label": "Total Cloud Cover (%)",
        "plot_title": "Total Cloud Cover",
    },
    # pgrb2b_only in GFS v16+ — preset kept for pgrb2b reads
    "lcc": {
        "cmap":       cmocean.cm.ice,
        "levels":     _lev(0, 100, 5),
        "cbar_label": "Low Cloud Cover (%)",
        "plot_title": "Low Cloud Cover",
    },
    "mcc": {
        "cmap":       cmocean.cm.ice,
        "levels":     _lev(0, 100, 5),
        "cbar_label": "Medium Cloud Cover (%)",
        "plot_title": "Medium Cloud Cover",
    },
    "hcc": {
        "cmap":       cmocean.cm.ice,
        "levels":     _lev(0, 100, 5),
        "cbar_label": "High Cloud Cover (%)",
        "plot_title": "High Cloud Cover",
    },

    # ── convection / instability ──────────────────────────────────────────────

    "cape": {
        "cmap":       plt.cm.YlOrRd,
        "levels":     np.array([0, 100, 250, 500, 750, 1000, 1500,
                                 2000, 2500, 3000, 4000, 5000]),
        "cbar_label": "CAPE (J kg\u207b\u00b9)",
        "plot_title": "Convective Available Potential Energy",
    },
    "cin": {
        "cmap":       plt.cm.RdPu,
        "levels":     np.array([-500, -300, -200, -150, -100,
                                  -75,  -50,  -25,  -10,    0]),
        "cbar_label": "CIN (J kg\u207b\u00b9)",
        "plot_title": "Convective Inhibition",
    },
    "lftx": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     _lev(-12, 10, 1),
        "cbar_label": "Surface Lifted Index (K)",
        "plot_title": "Surface Lifted Index",
    },
    "lftx4": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     _lev(-12, 10, 1),
        "cbar_label": "Best 4-Layer Lifted Index (K)",
        "plot_title": "Best (4-Layer) Lifted Index",
    },
    "hlcy": {
        "cmap":       plt.cm.YlOrRd,
        "levels":     np.array([0, 50, 100, 150, 200, 250, 300,
                                 400, 500, 750, 1000]),
        "cbar_label": "Storm Relative Helicity (m\u00b2 s\u207b\u00b2)",
        "plot_title": "Storm Relative Helicity (0\u20133 km)",
    },

    # ── upper-air multi-level (isobaric) ──────────────────────────────────────
    # animate_multilevel() appends the hPa level to plot_title automatically.

    "t": {
        "cmap":       cmocean.cm.thermal,
        "levels":     _lev(-80, 40, 4),
        "cbar_label": "Temperature (\u00b0C)",
        "plot_title": "Upper-Air Temperature",
    },
    "r": {
        "cmap":       cmocean.cm.haline,
        "levels":     _lev(0, 100, 5),
        "cbar_label": "Relative Humidity (%)",
        "plot_title": "Upper-Air Relative Humidity",
    },
    "q": {
        "cmap":       cmocean.cm.haline,
        "levels":     np.array([0, 0.5, 1, 2, 3, 5, 7, 10, 14, 18]) * 1e-3,
        "cbar_label": "Specific Humidity (kg kg\u207b\u00b9)",
        "plot_title": "Upper-Air Specific Humidity",
    },
    "gh": {
        "cmap":       cmocean.cm.deep,
        "levels":     _lev(0, 6000, 60),
        "cbar_label": "Geopotential Height (gpm)",
        "plot_title": "Geopotential Height",
    },
    "u": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     _lev(-60, 60, 4),
        "cbar_label": "U Component of Wind (m s\u207b\u00b9)",
        "plot_title": "Upper-Air U Wind",
    },
    "v": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     _lev(-60, 60, 4),
        "cbar_label": "V Component of Wind (m s\u207b\u00b9)",
        "plot_title": "Upper-Air V Wind",
    },
    "w": {
        # Omega: negative = rising motion (blue), positive = sinking (red)
        "cmap":       plt.cm.RdBu_r,
        "levels":     np.array([-5, -2, -1, -0.5, -0.25, -0.1, 0,
                                  0.1, 0.25, 0.5, 1, 2, 5]),
        "cbar_label": "Vertical Velocity \u03c9 (Pa s\u207b\u00b9)",
        "plot_title": "Vertical Velocity (\u03c9)",
    },

    # ── upper-air wind speed (derived, pressure levels) ───────────────────────
    #
    # "wspd" is a derived isobaric variable — compute it from "u" and "v":
    #
    #   ds["wspd"] = np.sqrt(ds["u"] ** 2 + ds["v"] ** 2)
    #
    # Levels cover 0–80 m/s to capture jet-stream speeds at 200/250 hPa.
    # cmocean.cm.speed maintains the same white→dark convention used for
    # the surface wind speed preset ("wspd10") above.
    #
    "wspd": {
        "cmap":       cmocean.cm.speed,
        "levels":     _lev(0, 80, 4),
        "cbar_label": "Wind Speed (m s\u207b\u00b9)",
        "plot_title": "Upper-Air Wind Speed",
    },

    "absv": {
        "cmap":       plt.cm.RdBu_r,
        "levels":     np.array([-8, -6, -4, -3, -2, -1, -0.5, 0,
                                  0.5, 1, 2, 3, 4, 6, 8]) * 1e-4,
        "cbar_label": "Absolute Vorticity (s\u207b\u00b9)",
        "plot_title": "Absolute Vorticity",
    },

    # ── soil (4-layer) ────────────────────────────────────────────────────────
    # animate_multilevel() appends the depth label to plot_title automatically.

    "st": {
        "cmap":       cmocean.cm.matter,
        "levels":     _lev(-10, 40, 2),
        "cbar_label": "Soil Temperature (\u00b0C)",
        "plot_title": "Soil Temperature",
    },
    "soilw": {
        "cmap":       cmocean.cm.matter,
        "levels":     np.linspace(0, 1, 21),
        "cbar_label": "Volumetric Soil Moisture (proportion)",
        "plot_title": "Volumetric Soil Moisture Content",
    },

    # ── diagnostics ───────────────────────────────────────────────────────────

    "refc": {
        "cmap":       _REFC_CMAP,
        "levels":     _lev(-10, 75, 5),
        "cbar_label": "Composite Reflectivity (dBZ)",
        "plot_title": "Maximum/Composite Radar Reflectivity",
    },
    "siconc": {
        "cmap":       cmocean.cm.ice,
        "levels":     np.linspace(0, 1, 21),
        "cbar_label": "Sea Ice Fraction (0\u20131)",
        "plot_title": "Sea Ice Area Fraction",
    },
    # f000_only — only emitted at analysis hour; use hour=0 when downloading
    "tozne": {
        "cmap":       cmocean.cm.deep,
        "levels":     _lev(200, 500, 10),
        "cbar_label": "Total Ozone (DU)",
        "plot_title": "Total Ozone Column",
    },

    # ── meta / index ──────────────────────────────────────────────────────────

    "forecast_hour": {
        "cmap":       plt.cm.viridis,
        "levels":     _lev(0, 240, 6),
        "cbar_label": "Forecast Hour",
        "plot_title": "Forecast Hour",
    },
}


# ── depth label map for soil variables ───────────────────────────────────────
# Maps the integer level key used in VARIABLES["st"]["levels"] to a
# human-readable depth string appended to the plot title by animate_multilevel.

SOIL_DEPTH_LABELS: dict[int, str] = {
    0:   "0\u201310 cm",
    10:  "10\u201340 cm",
    40:  "40\u2013100 cm",
    100: "100\u2013200 cm",
}

# ── isobaric variables that receive per-level title suffix ───────────────────
ISOBARIC_VARS = frozenset({"t", "r", "q", "gh", "u", "v", "w", "absv", "wspd"})

# ── soil variables that use SOIL_DEPTH_LABELS ────────────────────────────────
SOIL_VARS = frozenset({"st", "soilw"})


# ── convenience helper ────────────────────────────────────────────────────────

def list_variable_presets() -> None:
    """Print all variable presets: colormap, level range, and label."""
    print(f"\n  {'Variable':<14}  {'Colormap':<24}  {'Range (N steps)':<32}  Label")
    print("  " + "\u2500" * 108)
    for key, p in VARIABLE_PRESETS.items():
        lvl       = np.asarray(p["levels"])
        lvl_str   = f"{lvl[0]:.3g} \u2026 {lvl[-1]:.3g}  ({len(lvl)} steps)"
        cmap_name = getattr(p["cmap"], "name", str(p["cmap"]))
        print(f"  {key:<14}  {cmap_name:<24}  {lvl_str:<32}  {p['cbar_label']}")
    print()

VARIABLES_INFO: dict[str, dict[str, Any]] = {
    "t2m":   {"short":"t2m","long_name":"2 metre temperature","units":"C","tlev":"heightAboveGround","levels":[2],"grib_var":"var_TMP","grib_lev":"lev_2_m_above_ground","converter":lambda x:x-273.15},
    "d2m":   {"short":"d2m","long_name":"2 metre dewpoint temperature","units":"C","tlev":"heightAboveGround","levels":[2],"grib_var":"var_DPT","grib_lev":"lev_2_m_above_ground","converter":lambda x:x-273.15},
    "r2":    {"short":"r2","long_name":"2 metre relative humidity","units":"%","tlev":"heightAboveGround","levels":[2],"grib_var":"var_RH","grib_lev":"lev_2_m_above_ground","converter":None},
    "sh2":   {"short":"sh2","long_name":"2 metre specific humidity","units":"kg kg**-1","tlev":"heightAboveGround","levels":[2],"grib_var":"var_SPFH","grib_lev":"lev_2_m_above_ground","converter":None},
    "aptmp": {"short":"aptmp","long_name":"Apparent temperature","units":"C","tlev":"heightAboveGround","levels":[2],"grib_var":"var_APTMP","grib_lev":"lev_2_m_above_ground","converter":lambda x:x-273.15},
    "u10":   {"short":"u10","long_name":"10 metre U wind component","units":"m s**-1","tlev":"heightAboveGround","levels":[10],"grib_var":"var_UGRD","grib_lev":"lev_10_m_above_ground","converter":None},
    "v10":   {"short":"v10","long_name":"10 metre V wind component","units":"m s**-1","tlev":"heightAboveGround","levels":[10],"grib_var":"var_VGRD","grib_lev":"lev_10_m_above_ground","converter":None},
    "gust":  {"short":"gust","long_name":"Wind speed (gust)","units":"m s**-1","tlev":"surface","levels":None,"grib_var":"var_GUST","grib_lev":"lev_surface","converter":None},
    "prmsl": {"short":"prmsl","long_name":"Pressure reduced to MSL","units":"hPa","tlev":"meanSea","levels":None,"grib_var":"var_PRMSL","grib_lev":"lev_mean_sea_level","converter":lambda x:x/100},
    "mslet": {"short":"mslet","long_name":"MSLP (Eta model reduction)","units":"hPa","tlev":"meanSea","levels":None,"grib_var":"var_MSLET","grib_lev":"lev_mean_sea_level","converter":lambda x:x/100},
    "sp":    {"short":"sp","long_name":"Surface pressure","units":"hPa","tlev":"surface","levels":None,"grib_var":"var_PRES","grib_lev":"lev_surface","converter":lambda x:x/100},
    "orog":  {"short":"orog","long_name":"Orography","units":"m","tlev":"surface","levels":None,"grib_var":"var_HGT","grib_lev":"lev_surface","converter":None},
    "lsm":   {"short":"lsm","long_name":"Land-sea mask","units":"0 - 1","tlev":"surface","levels":None,"grib_var":"var_LAND","grib_lev":"lev_surface","converter":None},
    "vis":   {"short":"vis","long_name":"Visibility","units":"m","tlev":"surface","levels":None,"grib_var":"var_VIS","grib_lev":"lev_surface","converter":None},
    "prate": {"short":"prate","long_name":"Precipitation rate","units":"kg m**-2 s**-1","tlev":"surface","levels":None,"grib_var":"var_PRATE","grib_lev":"lev_surface","converter":None},
    "cpofp": {"short":"cpofp","long_name":"Percent frozen precipitation","units":"%","tlev":"surface","levels":None,"grib_var":"var_CPOFP","grib_lev":"lev_surface","converter":None},
    "crain": {"short":"crain","long_name":"Categorical rain","units":"Code table 4.222","tlev":"surface","levels":None,"grib_var":"var_CRAIN","grib_lev":"lev_surface","converter":None},
    "csnow": {"short":"csnow","long_name":"Categorical snow","units":"Code table 4.222","tlev":"surface","levels":None,"grib_var":"var_CSNOW","grib_lev":"lev_surface","converter":None},
    "cfrzr": {"short":"cfrzr","long_name":"Categorical freezing rain","units":"Code table 4.222","tlev":"surface","levels":None,"grib_var":"var_CFRZR","grib_lev":"lev_surface","converter":None},
    "cicep": {"short":"cicep","long_name":"Categorical ice pellets","units":"Code table 4.222","tlev":"surface","levels":None,"grib_var":"var_CICEP","grib_lev":"lev_surface","converter":None},
    "sde":   {"short":"sde","long_name":"Snow depth","units":"m","tlev":"surface","levels":None,"grib_var":"var_SNOD","grib_lev":"lev_surface","converter":None},
    "sdwe":  {"short":"sdwe","long_name":"Water equivalent of accumulated snow depth","units":"kg m**-2","tlev":"surface","levels":None,"grib_var":"var_WEASD","grib_lev":"lev_surface","converter":None},
    "pwat":  {"short":"pwat","long_name":"Precipitable water","units":"kg m**-2","tlev":"atmosphereSingleLayer","levels":None,"grib_var":"var_PWAT","grib_lev":"lev_entire_atmosphere_(considered_as_a_single_layer)","converter":None},
    "cwat":  {"short":"cwat","long_name":"Cloud water","units":"kg m**-2","tlev":"atmosphereSingleLayer","levels":None,"grib_var":"var_CWAT","grib_lev":"lev_entire_atmosphere_(considered_as_a_single_layer)","converter":None},
    "tcc":   {"short":"tcc","long_name":"Total cloud cover","units":"%","tlev":"atmosphere","levels":None,"grib_var":"var_TCDC","grib_lev":"lev_entire_atmosphere","converter":None},
    "lcc":   {"short":"lcc","long_name":"Low cloud cover","units":"%","tlev":"lowCloudLayer","levels":None,"grib_var":"var_TCDC","grib_lev":"lev_low_cloud_layer","converter":None},
    "mcc":   {"short":"mcc","long_name":"Medium cloud cover","units":"%","tlev":"middleCloudLayer","levels":None,"grib_var":"var_TCDC","grib_lev":"lev_middle_cloud_layer","converter":None},
    "hcc":   {"short":"hcc","long_name":"High cloud cover","units":"%","tlev":"highCloudLayer","levels":None,"grib_var":"var_TCDC","grib_lev":"lev_high_cloud_layer","converter":None},
    "cape":  {"short":"cape","long_name":"Convective available potential energy","units":"J kg**-1","tlev":"surface","levels":None,"grib_var":"var_CAPE","grib_lev":"lev_surface","converter":None,"multilevel":True},
    "cin":   {"short":"cin","long_name":"Convective inhibition","units":"J kg**-1","tlev":"surface","levels":None,"grib_var":"var_CIN","grib_lev":"lev_surface","converter":None,"multilevel":True},
    "lftx":  {"short":"lftx","long_name":"Surface lifted index","units":"K","tlev":"surface","levels":None,"grib_var":"var_LFTX","grib_lev":"lev_surface","converter":None},
    "lftx4": {"short":"lftx4","long_name":"Best (4-layer) lifted index","units":"K","tlev":"surface","levels":None,"grib_var":"var_4LFTX","grib_lev":"lev_surface","converter":None},
    "hlcy":  {"short":"hlcy","long_name":"Storm relative helicity","units":"m**2 s**-2","tlev":"heightAboveGroundLayer","levels":None,"grib_var":"var_HLCY","grib_lev":"lev_height_above_ground_layer","converter":None},
    "t":     {"short":"t","long_name":"Temperature","units":"C","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_TMP","grib_lev":"lev_500_mb","converter":lambda x:x-273.15,"multilevel":True},
    "r":     {"short":"r","long_name":"Relative humidity","units":"%","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_RH","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "q":     {"short":"q","long_name":"Specific humidity","units":"kg kg**-1","tlev":"isobaricInhPa","levels":[1000],"grib_var":"var_SPFH","grib_lev":"lev_1000_mb","converter":None,"multilevel":True},
    "gh":    {"short":"gh","long_name":"Geopotential height","units":"gpm","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_HGT","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "u":     {"short":"u","long_name":"U component of wind","units":"m s**-1","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_UGRD","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "v":     {"short":"v","long_name":"V component of wind","units":"m s**-1","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_VGRD","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "w":     {"short":"w","long_name":"Vertical velocity","units":"Pa s**-1","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_VVEL","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "absv":  {"short":"absv","long_name":"Absolute vorticity","units":"s**-1","tlev":"isobaricInhPa","levels":[500],"grib_var":"var_ABSV","grib_lev":"lev_500_mb","converter":None,"multilevel":True},
    "st":    {"short":"st","long_name":"Soil temperature","units":"C","tlev":"depthBelowLandLayer","levels":[0],"grib_var":"var_TSOIL","grib_lev":"lev_0-10_cm_below_ground","converter":lambda x:x-273.15,"multilevel":True},
    "soilw": {"short":"soilw","long_name":"Volumetric soil moisture content","units":"Proportion","tlev":"depthBelowLandLayer","levels":[0],"grib_var":"var_SOILW","grib_lev":"lev_0-10_cm_below_ground","converter":None,"multilevel":True},
    "refc":  {"short":"refc","long_name":"Maximum/Composite radar reflectivity","units":"dB","tlev":"atmosphere","levels":None,"grib_var":"var_REFC","grib_lev":"lev_entire_atmosphere","converter":None},
    "siconc":{"short":"siconc","long_name":"Sea ice area fraction","units":"0 - 1","tlev":"surface","levels":None,"grib_var":"var_ICEC","grib_lev":"lev_surface","converter":None},
    "veg":   {"short":"veg","long_name":"Vegetation","units":"%","tlev":"surface","levels":None,"grib_var":"var_VEG","grib_lev":"lev_surface","converter":None},
    "tozne": {"short":"tozne","long_name":"Total ozone","units":"DU","tlev":"atmosphere","levels":None,"grib_var":"var_TOZNE","grib_lev":"lev_entire_atmosphere","converter":None},
}
