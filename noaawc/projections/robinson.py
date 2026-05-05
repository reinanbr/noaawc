# mypy: disable-error-code=attr-defined

"""
RobinsonAnimator
================
Renders animated weather maps using the Robinson projection,
built on the same design language as PlateCarreeAnimator and OrthoAnimator.

The Robinson projection is a pseudo-cylindrical compromise projection designed
by Arthur Robinson in 1963.  It distorts neither area nor shape perfectly but
minimises both simultaneously, making it the standard choice for
world/global thematic maps.  It is NOT conformal and NOT equal-area, but it
LOOKS good — which is why National Geographic used it from 1988 to 1998.

Two region-definition approaches:
  • set_region()  — explicit bounding box in lat/lon degrees
  • set_zoom()    — zoom level around a central point (maps to central_longitude)

See README_RobinsonAnimator.md for full documentation.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import imageio
from matplotlib.colors import BoundaryNorm
from datetime import datetime, timezone
from typing import Any

from noaawc.variables import VARIABLE_PRESETS, VARIABLES_INFO

# ── re-use all shared helpers from the OrthoAnimator module ──────────────────
from noaawc.projections.ortho import (
    _font_scale,
    _add_reference_lines,
    _colorbar,
    _title,
    _run_label,
    _MONTHS,
    _format_date,
    _gfs_meta,
    _frames_dir,
    _frame_path,
    _interp_field_value,
    _draw_info_box,
    _draw_data_credit,
    _draw_author,
    list_quality_presets,
    list_variable_presets,
)


# ══════════════════════════════════════════════════════════════════════════════
# Quality presets — 16:9 cinematic/TV aspect ratio
# ──────────────────────────────────────────────────────────────────────────────
# Robinson maps have an intrinsic ~1.97:1 width-to-height ratio at global
# extent.  For regional views the box below is fine; for global views the
# aspect ratio is automatically respected via set_extent().
#
#   sd   →  1280×720  px  (HD-ready)
#   hd   →  1920×1080 px  (Full HD)
#   4k   →  3840×2160 px  (Ultra HD)
#   4k_60→  3840×2160 px  @ 60 fps
# ══════════════════════════════════════════════════════════════════════════════

QUALITY_PRESETS: dict = {
    "sd": {
        "dpi": 72,
        "figsize": (17.7778, 10.0000),   # 1280×720 px  (16:9)
        "fps": 6,
        "codec": "libx264",
        "quality": 6,
        "description": "SD 720p 16:9 — fast render, small file",
    },
    "hd": {
        "dpi": 120,
        "figsize": (16.0000, 9.0000),    # 1920×1080 px  (16:9)
        "fps": 24,
        "codec": "libx264",
        "quality": 8,
        "description": "Full HD 1080p 16:9 — balanced quality and speed",
    },
    "4k": {
        "dpi": 220,
        "figsize": (17.4545, 9.8182),    # 3840×2159 px  (16:9)
        "fps": 30,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K 16:9 — maximum quality, large file",
    },
    "4k_60": {
        "dpi": 220,
        "figsize": (17.4545, 9.8182),    # 3840×2159 px  (16:9)
        "fps": 60,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K 16:9 @ 60 fps — silky smooth, very large file",
    },
}


# ── Robinson projection limits ────────────────────────────────────────────────
# The Robinson projection is defined for latitudes −90°…+90°.  In Cartopy
# pcolormesh / contour calls we use PlateCarree source data, so we cap the
# displayed latitude range at ±85° to avoid artefacts near the poles.
_ROB_LAT_MAX: float = 85.0

# Default region: global (centred on 0° longitude)
_DEFAULT_REGION = {
    "toplat":    85.0,
    "bottomlat": -85.0,
    "leftlon":   -180.0,
    "rightlon":   180.0,
    "central_longitude": 0.0,
}


# ══════════════════════════════════════════════════════════════════════════════
# Region / zoom helpers
# ══════════════════════════════════════════════════════════════════════════════

def _zoom_to_half_side(zoom: float) -> float:
    """Return the half-side length in degrees for a given zoom level."""
    if zoom < 1:
        raise ValueError("zoom must be >= 1")
    return 90.0 / zoom


def _region_from_zoom(lat: float, lon: float, zoom: float) -> dict:
    """Build a region dict centred on (lat, lon) with the given zoom level."""
    half = _zoom_to_half_side(zoom)
    return {
        "toplat":    min( _ROB_LAT_MAX,  lat + half),
        "bottomlat": max(-_ROB_LAT_MAX, lat - half),
        "leftlon":   lon - half,
        "rightlon":  lon + half,
        "central_longitude": lon,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Map feature helper (Robinson)
# ══════════════════════════════════════════════════════════════════════════════

def _add_features_rob(
    ax: plt.Axes,
    lw: float = 0.4,
    show_states: bool = False,
    show_ocean: bool = True,
) -> None:
    """Add cartographic features to a Robinson axes."""
    ax.add_feature(cfeature.LAND,      facecolor="#13171d", edgecolor="none",  zorder=0)
    if show_ocean:
        ax.add_feature(cfeature.OCEAN, facecolor="#0d1520", edgecolor="none",  zorder=0)
    ax.add_feature(cfeature.COASTLINE, edgecolor="#2d6db5", linewidth=lw,      zorder=3)
    ax.add_feature(
        cfeature.BORDERS,
        edgecolor="#2a2f36",
        linewidth=lw * 0.7,
        zorder=3,
    )
    if show_states:
        ax.add_feature(
            cfeature.NaturalEarthFeature(
                category="cultural",
                name="admin_1_states_provinces",
                scale="10m",
            ),
            edgecolor="#1e2a35",
            linewidth=lw * 0.5,
            linestyle="--",
            zorder=3,
            facecolor="none",
        )
    _add_reference_lines(ax, lw=lw)


def _add_gridlines_rob(ax: plt.Axes, scale: float = 1.0) -> None:
    """
    Add labelled gridlines to a Robinson axes.

    Note: Cartopy's gridline labeller has limited support for Robinson.
    Labels are drawn at standard parallels (every 30°) and meridians (every 30°).
    For regional views, the spacing is tightened automatically.
    """
    gl = ax.gridlines(
        crs=ccrs.PlateCarree(),
        draw_labels=False,          # Robinson labels must be drawn manually
        linewidth=0.3 * scale,
        color="#14181c",
        alpha=0.8,
        linestyle="--",
        zorder=2,
    )
    gl.xlocator = mticker.MultipleLocator(30)
    gl.ylocator = mticker.MultipleLocator(30)


# ══════════════════════════════════════════════════════════════════════════════
# RobinsonAnimator
# ══════════════════════════════════════════════════════════════════════════════

class RobinsonAnimator:
    """
    Renders an animated weather map using the Robinson projection.

    The Robinson projection is a pseudo-cylindrical, compromise projection
    often used for world maps.  It minimises both area and shape distortion,
    making it an aesthetically pleasing choice for global and hemispheric
    weather visualisations.

    This class shares the same API, dark theme, variable presets, and quality
    presets as ``PlateCarreeAnimator`` and ``OrthoAnimator``.

    Region definition
    -----------------
    You MUST define the visible region before calling ``animate()`` or
    ``plot()``.  Three approaches are available:

    1. Named shortcut::

        anim.set_region("global")          # full world map
        anim.set_region("north_hemisphere") # NH only
        anim.set_region("south_hemisphere") # SH only
        anim.set_region("atlantic")         # North Atlantic
        anim.set_region("pacific")          # Pacific basin
        anim.set_region("south_america")    # SA continent
        anim.set_region("africa")           # Africa
        anim.set_region("europe_asia")      # Eurasia

    2. Explicit bounding box dict::

        anim.set_region(
            region={
                "toplat":    90,
                "bottomlat": -90,
                "leftlon":   -180,
                "rightlon":   180,
                "central_longitude": 0,   # optional; default 0
            }
        )

    3. Keyword arguments::

        anim.set_region(toplat=90, bottomlat=-90, leftlon=-180, rightlon=180)

    Zoom approach (centres the map on a point)::

        anim.set_zoom(zoom=2, pos=(0.0, -30.0))   # Atlantic-centric world view

    Quick start
    -----------
    ::

        anim = RobinsonAnimator(ds, "t2m")
        anim.set_region("global")
        anim.set_output("world_temperature.mp4")
        anim.animate()

    Zoomed example::

        anim = RobinsonAnimator(ds, "prmsl")
        anim.set_zoom(zoom=2, pos=(20.0, 10.0))   # Africa + Europe
        anim.set_quality("hd")
        anim.animate()
    """

    # ── named region shortcuts ────────────────────────────────────────────────
    _NAMED_REGIONS: dict[str, dict] = {
        "global": {
            "toplat":  85.0, "bottomlat": -85.0,
            "leftlon": -180.0, "rightlon": 180.0,
            "central_longitude": 0.0,
        },
        "north_hemisphere": {
            "toplat":  85.0, "bottomlat":   0.0,
            "leftlon": -180.0, "rightlon": 180.0,
            "central_longitude": 0.0,
        },
        "south_hemisphere": {
            "toplat":   0.0, "bottomlat": -85.0,
            "leftlon": -180.0, "rightlon": 180.0,
            "central_longitude": 0.0,
        },
        "atlantic": {
            "toplat":  75.0, "bottomlat": -60.0,
            "leftlon": -100.0, "rightlon":  20.0,
            "central_longitude": -40.0,
        },
        "pacific": {
            "toplat":  70.0, "bottomlat": -70.0,
            "leftlon":  100.0, "rightlon": 290.0,   # cross date-line
            "central_longitude": 180.0,
        },
        "south_america": {
            "toplat":  15.0, "bottomlat": -60.0,
            "leftlon": -85.0, "rightlon":  -30.0,
            "central_longitude": -57.5,
        },
        "africa": {
            "toplat":  40.0, "bottomlat": -40.0,
            "leftlon": -20.0, "rightlon":   55.0,
            "central_longitude": 17.5,
        },
        "europe_asia": {
            "toplat":  75.0, "bottomlat":  10.0,
            "leftlon": -30.0, "rightlon":  150.0,
            "central_longitude": 60.0,
        },
        "north_america": {
            "toplat":  80.0, "bottomlat":   5.0,
            "leftlon": -170.0, "rightlon":  -50.0,
            "central_longitude": -100.0,
        },
        "asia": {
            "toplat":  75.0, "bottomlat":  -10.0,
            "leftlon":  40.0, "rightlon":   150.0,
            "central_longitude": 95.0,
        },
    }

    # ── class-level defaults ──────────────────────────────────────────────────
    _OUTPUT_DEFAULT        = "output_robinson.mp4"
    _FPS_DEFAULT           = 6
    _STEP_DEFAULT          = 1
    _DPI_DEFAULT           = 120
    _FIGSIZE_DEFAULT       = (16.0, 9.0)   # 16:9 — Full HD aspect ratio
    _CODEC_DEFAULT         = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8

    def __init__(self, ds, var: str):
        self._ds  = ds
        self._var = var

        # output options
        self._output        = self._OUTPUT_DEFAULT
        self._fps           = self._FPS_DEFAULT
        self._step          = self._STEP_DEFAULT
        self._dpi           = self._DPI_DEFAULT
        self._figsize: tuple[float, float] = self._FIGSIZE_DEFAULT
        self._codec         = self._CODEC_DEFAULT
        self._video_quality = self._VIDEO_QUALITY_DEFAULT

        # region — start with global view
        self._region: dict = dict(_DEFAULT_REGION)

        # variable preset
        self._apply_variable_preset(var, silent=False)

        # annotations
        self._annotations: list[dict] = []

        # custom title
        self._title_template: str | None = None
        self._title_date_style: str = "en"

        # feature flags
        self._show_states: bool = False
        self._show_ocean:  bool = True
        self._show_grid:   bool = True

        # author label
        self._author: str = ""
        self._author_kwargs: dict[str, Any] = {}

    # ── variable preset ───────────────────────────────────────────────────────

    def _apply_variable_preset(self, var: str, silent: bool = True) -> None:
        if var in VARIABLE_PRESETS:
            p = VARIABLE_PRESETS[var]
            if not silent:
                print(f"Variable preset '{var}': {p['plot_title']}")
        else:
            p = VARIABLE_PRESETS["t2m"]
            print(
                f"[RobinsonAnimator] No preset for '{var}' — "
                f"falling back to temperature defaults."
            )
        self._cmap        = p["cmap"]
        self._levels      = np.asarray(p["levels"])
        self._cbar_label  = p["cbar_label"]
        self._plot_title  = p["plot_title"]

    def use_variable_defaults(self, var: str | None = None) -> "RobinsonAnimator":
        """Apply the plotting preset for *var* (or the instance variable if omitted)."""
        key = var if var is not None else self._var
        self._apply_variable_preset(key, silent=False)
        return self

    # ── region / zoom ─────────────────────────────────────────────────────────

    def set_region(
        self,
        region: dict | str | None = None,
        *,
        toplat:             float | None = None,
        bottomlat:          float | None = None,
        leftlon:            float | None = None,
        rightlon:           float | None = None,
        central_longitude:  float = 0.0,
    ) -> "RobinsonAnimator":
        """
        Define the map extent as a bounding box.

        You can pass the region in three ways:

        **1. Named shortcut (string)**::

            anim.set_region("global")
            anim.set_region("north_hemisphere")
            anim.set_region("south_hemisphere")
            anim.set_region("atlantic")
            anim.set_region("pacific")
            anim.set_region("south_america")
            anim.set_region("africa")
            anim.set_region("europe_asia")
            anim.set_region("north_america")
            anim.set_region("asia")

        **2. Dictionary** (``central_longitude`` is optional; defaults to 0)::

            anim.set_region(
                region={
                    "toplat":    85,
                    "bottomlat": -85,
                    "leftlon":   -180,
                    "rightlon":   180,
                    "central_longitude": -60,   # optional
                }
            )

        **3. Keyword arguments**::

            anim.set_region(
                toplat=85, bottomlat=-85,
                leftlon=-180, rightlon=180,
                central_longitude=-60,
            )

        Parameters
        ----------
        region : dict or str, optional
            Named shortcut or dict with keys
            ``toplat``, ``bottomlat``, ``leftlon``, ``rightlon``,
            and optionally ``central_longitude``.
        toplat, bottomlat, leftlon, rightlon : float, optional
            Individual edge values — used when *region* is ``None``.
        central_longitude : float
            The longitude placed at the centre of the projection (default 0).
            Rotating the globe so your area of interest is centred reduces
            distortion.  Only used in the keyword-argument path; for the dict
            path include ``central_longitude`` in the dict.

        Returns
        -------
        self
        """
        if isinstance(region, str):
            key = region.lower()
            if key not in self._NAMED_REGIONS:
                opts = ", ".join(f'"{k}"' for k in self._NAMED_REGIONS)
                raise ValueError(
                    f"Unknown named region '{region}'. Available: {opts}"
                )
            self._region = dict(self._NAMED_REGIONS[key])

        elif isinstance(region, dict):
            required = {"toplat", "bottomlat", "leftlon", "rightlon"}
            missing  = required - set(region.keys())
            if missing:
                raise ValueError(f"region dict is missing keys: {missing}")
            self._region = dict(region)
            if "central_longitude" not in self._region:
                self._region["central_longitude"] = 0.0

        else:
            # keyword arguments path
            if any(v is None for v in (toplat, bottomlat, leftlon, rightlon)):
                raise ValueError(
                    "Provide all four: toplat, bottomlat, leftlon, rightlon."
                )
            self._region = {
                "toplat":    float(toplat),
                "bottomlat": float(bottomlat),
                "leftlon":   float(leftlon),
                "rightlon":  float(rightlon),
                "central_longitude": float(central_longitude),
            }

        self._validate_region()
        return self

    def set_zoom(
        self,
        zoom: float,
        pos: tuple[float, float],
    ) -> "RobinsonAnimator":
        """
        Define the map extent by zooming into a geographic point.

        The visible area is a square (in degrees) centred on *pos* with a
        half-side of ``90 / zoom`` degrees.  The projection's
        ``central_longitude`` is set to *pos[1]* so the centre of interest
        appears undistorted.

        Parameters
        ----------
        zoom : float
            Zoom level ≥ 1.

            =======  ===========  ====================================
            Value    Half-side    Coverage
            =======  ===========  ====================================
            1        90°          Near-global
            2        45°          Continental  (e.g. Africa)
            3        30°          Sub-continental
            4        22.5°        Regional
            6        15°          Country-level
            8        11.25°       State / province
            =======  ===========  ====================================

        pos : (lat, lon)
            Centre of the zoomed view in decimal degrees.

        Returns
        -------
        self

        Examples
        --------
        ::

            anim.set_zoom(zoom=1, pos=(20.0, 0.0))    # Global, Africa-centred
            anim.set_zoom(zoom=2, pos=(10.0, 20.0))   # Africa continent
            anim.set_zoom(zoom=3, pos=(50.0, 10.0))   # Western Europe
        """
        if zoom < 1:
            raise ValueError("zoom must be >= 1.")
        lat, lon = pos
        self._region = _region_from_zoom(lat, lon, zoom)
        return self

    def _validate_region(self) -> None:
        r = self._region
        if r["bottomlat"] >= r["toplat"]:
            raise ValueError("bottomlat must be < toplat.")
        if r["leftlon"] >= r["rightlon"]:
            raise ValueError("leftlon must be < rightlon.")

    # ── output options ────────────────────────────────────────────────────────

    def set_output(self, path: str) -> "RobinsonAnimator":
        """Output file path (.mp4 or .gif)."""
        self._output = path
        return self

    def set_fps(self, fps: int) -> "RobinsonAnimator":
        """Frames per second for the output video."""
        self._fps = fps
        return self

    def set_step(self, step: int) -> "RobinsonAnimator":
        """Spatial decimation factor (1 = no decimation)."""
        self._step = step
        return self

    def set_dpi(self, dpi: int) -> "RobinsonAnimator":
        """Figure resolution in dots per inch."""
        self._dpi = dpi
        return self

    def set_figsize(self, w: float, h: float) -> "RobinsonAnimator":
        """Figure size in inches (width, height)."""
        self._figsize = (w, h)
        return self

    def set_codec(self, codec: str) -> "RobinsonAnimator":
        """Video codec (libx264, libx265, vp9, prores)."""
        self._codec = codec
        return self

    def set_video_quality(self, quality: int) -> "RobinsonAnimator":
        """Encoding quality 0–10 (higher = better / larger file)."""
        if not 0 <= quality <= 10:
            raise ValueError("quality must be between 0 and 10.")
        self._video_quality = quality
        return self

    def set_quality(self, preset: str) -> "RobinsonAnimator":
        """
        Apply a named quality preset.

        Available: ``"sd"``, ``"hd"``, ``"4k"``, ``"4k_60"``.
        Call ``list_quality_presets()`` for details.
        """
        if preset not in QUALITY_PRESETS:
            options = ", ".join(f'"{k}"' for k in QUALITY_PRESETS)
            raise ValueError(f"Unknown preset '{preset}'. Choose from: {options}")
        p = QUALITY_PRESETS[preset]
        self._dpi           = p["dpi"]
        self._figsize       = p["figsize"]
        self._fps           = p["fps"]
        self._codec         = p["codec"]
        self._video_quality = p["quality"]
        print(f"Quality preset '{preset}': {p['description']}")
        return self

    # ── colormap / levels ─────────────────────────────────────────────────────

    def set_cmap(self, cmap) -> "RobinsonAnimator":
        """Override the colormap (name string or matplotlib object)."""
        self._cmap = plt.get_cmap(cmap) if isinstance(cmap, str) else cmap
        return self

    def set_levels(self, levels) -> "RobinsonAnimator":
        """Override the BoundaryNorm levels."""
        self._levels = np.asarray(levels)
        return self

    def set_cbar_label(self, label: str) -> "RobinsonAnimator":
        """Label shown on the colorbar."""
        self._cbar_label = label
        return self

    def set_plot_title(self, title: str) -> "RobinsonAnimator":
        """Static left-side title shown on each frame."""
        self._plot_title = title
        return self

    def set_title(
        self,
        template: str,
        date_style: str = "en",
    ) -> "RobinsonAnimator":
        """
        Dynamic per-frame title with ``%S`` as the date placeholder.

        Supported ``date_style`` values: ``"en"``, ``"pt-br"``, ``"es"``, ``"fr"``.
        """
        self._title_template   = template if template else None
        self._title_date_style = date_style
        return self

    # ── feature flags ─────────────────────────────────────────────────────────

    def set_states(self, visible: bool = True) -> "RobinsonAnimator":
        """Show / hide state/province boundary lines."""
        self._show_states = visible
        return self

    def set_ocean(self, visible: bool = True) -> "RobinsonAnimator":
        """Show / hide the ocean colour fill (default: on)."""
        self._show_ocean = visible
        return self

    def set_grid(self, visible: bool = True) -> "RobinsonAnimator":
        """Show / hide lat/lon gridlines (default: on)."""
        self._show_grid = visible
        return self

    # ── author label ──────────────────────────────────────────────────────────

    def set_author(
        self,
        name: str,
        x: float | None = None,
        y: float | None = None,
        ha: str = "center",
        va: str = "center",
        color: str = "#e6edf3",
        fontsize: float = 8.5,
        fontweight: str = "bold",
        fontfamily: str = "monospace",
        alpha: float = 1.0,
        bbox: bool = False,
        bbox_facecolor: str = "#161b22",
        bbox_edgecolor: str = "#30363d",
        bbox_alpha: float = 0.75,
        bbox_pad: float = 0.4,
    ) -> "RobinsonAnimator":
        """
        Set the author / credit label displayed on every frame.

        Pass ``""`` to disable.  All parameters are identical to
        ``OrthoAnimator.set_author()``.
        """
        self._author = name.strip()
        if not x or not y:
            x, y = 0.4967, 0.1
        self._author_kwargs = dict(
            x=x, y=y, ha=ha, va=va,
            color=color, fontsize=fontsize,
            fontweight=fontweight, fontfamily=fontfamily,
            alpha=alpha, bbox=bbox,
            bbox_facecolor=bbox_facecolor,
            bbox_edgecolor=bbox_edgecolor,
            bbox_alpha=bbox_alpha, bbox_pad=bbox_pad,
        )
        return self

    # ── annotations ───────────────────────────────────────────────────────────

    def set_annotate(
        self,
        text_base: str,
        pos: tuple[float, float],
        size: float = 9.0,
        color: str = "#e6edf3",
        weight: str = "bold",
        alpha: float = 0.9,
        bbox: bool = True,
        bbox_color: str = "#0d1117",
        bbox_alpha: float = 0.55,
        interpolate: bool = True,
        zorder: int = 5,
        marker: str | None = "o",
        marker_size: float = 6.0,
        marker_color: str | None = None,
        marker_edge_color: str = "#0d1117",
        marker_edge_width: float = 0.8,
        marker_alpha: float = 1.0,
        text_offset: tuple[float, float] = (0.0, 0.8),
    ) -> "RobinsonAnimator":
        """
        Add a text annotation (with optional position marker) on every frame.

        Parameters and behaviour are identical to ``OrthoAnimator.set_annotate()``.

        Examples
        --------
        ::

            anim.set_annotate("London %.1f°C", pos=(51.5, -0.1))
            anim.set_annotate("Cairo %.1f°C",  pos=(30.0, 31.2), color="#f0a500")
        """
        self._annotations.append(dict(
            text_base=text_base, pos=pos, size=size,
            color=color, weight=weight, alpha=alpha,
            bbox=bbox, bbox_color=bbox_color, bbox_alpha=bbox_alpha,
            interpolate=interpolate, zorder=zorder,
            marker=marker, marker_size=marker_size,
            marker_color=marker_color,
            marker_edge_color=marker_edge_color,
            marker_edge_width=marker_edge_width,
            marker_alpha=marker_alpha,
            text_offset=text_offset,
        ))
        return self

    def clear_annotations(self) -> "RobinsonAnimator":
        """Remove all registered annotations."""
        self._annotations.clear()
        return self

    # ── internal helpers ──────────────────────────────────────────────────────

    def _get(self, time_idx: int):
        ds   = self._ds
        var  = self._var
        step = self._step
        da   = ds[var][time_idx]
        lats = da.latitude.values[::step]
        lons = da.longitude.values[::step]
        data = da.values[::step, ::step]
        time = da.time.values
        return lats, lons, data, time

    def _build_axes(self) -> tuple[plt.Figure, plt.Axes]:
        r     = self._region
        c_lon = r.get("central_longitude", 0.0)
        proj  = ccrs.Robinson(central_longitude=c_lon)
        scale = _font_scale(self._dpi)

        fig, ax = plt.subplots(
            figsize=self._figsize,
            subplot_kw={"projection": proj},
            facecolor="#0d1117",
            dpi=self._dpi,
        )

        # Clamp latitudes to safe bounds
        safe_top = max(-_ROB_LAT_MAX, min(_ROB_LAT_MAX, r["toplat"]))
        safe_bot = max(-_ROB_LAT_MAX, min(_ROB_LAT_MAX, r["bottomlat"]))

        ax.set_extent(
            [r["leftlon"], r["rightlon"], safe_bot, safe_top],
            crs=ccrs.PlateCarree(),
        )
        _add_features_rob(
            ax,
            lw=0.5 * scale,
            show_states=self._show_states,
            show_ocean=self._show_ocean,
        )
        if self._show_grid:
            _add_gridlines_rob(ax, scale=scale)

        return fig, ax

    def _draw_annotations(self, ax, lat, lon, field) -> None:
        if not self._annotations:
            return
        scale = _font_scale(self._dpi)
        for ann in self._annotations:
            lat_a, lon_a = ann["pos"]
            d_lon, d_lat = ann.get("text_offset", (0.0, 0.8))

            if ann["interpolate"] and ("%" in ann["text_base"]):
                val  = _interp_field_value(lat, lon, field, ann["pos"])
                try:
                    text = ann["text_base"] % val
                except TypeError:
                    text = ann["text_base"]
            else:
                text = ann["text_base"]

            mk = ann.get("marker", "o")
            if mk is not None:
                mk_color = ann.get("marker_color") or ann["color"]
                ax.plot(
                    lon_a, lat_a,
                    marker=mk,
                    markersize=ann.get("marker_size", 6.0) * scale,
                    color=mk_color,
                    markeredgecolor=ann.get("marker_edge_color", "#0d1117"),
                    markeredgewidth=ann.get("marker_edge_width", 0.8) * scale,
                    alpha=ann.get("marker_alpha", 1.0),
                    transform=ccrs.PlateCarree(),
                    zorder=ann["zorder"],
                    linestyle="none",
                )

            bbox_props = None
            if ann["bbox"]:
                bbox_props = dict(
                    boxstyle="round,pad=0.3",
                    facecolor=ann["bbox_color"],
                    alpha=ann["bbox_alpha"],
                    edgecolor="none",
                )
            ax.annotate(
                text,
                xy=(lon_a + d_lon, lat_a + d_lat),
                xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
                fontsize=round(ann["size"] * scale, 1),
                color=ann["color"],
                fontweight=ann["weight"],
                alpha=ann["alpha"],
                bbox=bbox_props,
                ha="center",
                va="center",
                zorder=ann["zorder"],
            )

    def _draw_field(self, fig, ax, lat, lon, field, time_val) -> None:
        scale = _font_scale(self._dpi)
        norm  = BoundaryNorm(self._levels, ncolors=self._cmap.N, clip=True)

        cf = ax.pcolormesh(
            lon, lat, field,
            cmap=self._cmap,
            norm=norm,
            transform=ccrs.PlateCarree(),
            zorder=1,
        )
        ax.contour(
            lon[::3], lat[::3], field[::3, ::3],
            levels=self._levels[::5],
            colors="white",
            linewidths=0.25 * scale,
            alpha=0.4,
            transform=ccrs.PlateCarree(),
            zorder=2,
        )

        self._draw_annotations(ax, lat, lon, field)

        _colorbar(fig, cf, ax, self._cbar_label, scale=scale)

        # titles
        if self._title_template is not None:
            date_str   = _format_date(time_val, self._title_date_style)
            main_title = self._title_template.replace("%S", date_str)
            _title(ax, main_title, scale=scale)
        else:
            _title(ax, self._plot_title, _run_label(time_val), scale=scale)

        _, cycle     = _gfs_meta(self._ds, self._var)
        date_str_box = self._ds["time"][0].dt.strftime("%Y-%m-%d").item()
        _draw_info_box(fig, self._var, cycle, date_str_box, scale=scale, ax=ax)
        _draw_data_credit(fig, scale=scale, ax=ax)

        if self._author:
            _draw_author(fig, self._author, scale=scale, **self._author_kwargs)

    def _render_frame(self, tidx: int, fpath: str) -> None:
        lat, lon, field, time_val = self._get(tidx)
        fig, ax = self._build_axes()
        self._draw_field(fig, ax, lat, lon, field, time_val)
        fig.tight_layout()
        fig.savefig(fpath, format="png", dpi=self._dpi)
        plt.close(fig)

    def _write_video(self, fdir: str, n_frames: int) -> None:
        writer_kwargs: dict = {"fps": self._fps}
        if self._output.endswith(".mp4"):
            writer_kwargs["codec"]   = self._codec
            writer_kwargs["quality"] = self._video_quality
            if self._codec in ("libx265", "hevc"):
                writer_kwargs["output_params"] = ["-pix_fmt", "yuv420p"]
        with imageio.get_writer(self._output, **writer_kwargs) as writer:
            for tidx in range(n_frames):
                writer.append_data(imageio.imread(_frame_path(fdir, tidx)))

    def _print_render_info(self, n_frames: int) -> None:
        w, h  = self._figsize
        px_w  = int(w * self._dpi)
        px_h  = int(h * self._dpi)
        r     = self._region
        c_lon = r.get("central_longitude", 0.0)
        print(
            f"Render: {n_frames} frames  |  {px_w}×{px_h} px  |  {self._dpi} dpi  |  "
            f"{self._fps} fps  |  codec={self._codec}  quality={self._video_quality}  "
            f"annotations={len(self._annotations)}\n"
            f"Region (Robinson, central_lon={c_lon:.1f}°): "
            f"lat [{r['bottomlat']:.1f} … {r['toplat']:.1f}]  "
            f"lon [{r['leftlon']:.1f} … {r['rightlon']:.1f}]  →  {self._output}"
        )

    # ── public entry points ───────────────────────────────────────────────────

    def plot(
        self,
        time_idx: int = 0,
        save: str | None = None,
        show: bool = True,
    ) -> "RobinsonAnimator":
        """
        Render a single static frame.

        Parameters
        ----------
        time_idx : int
            Time index (default 0 = first step).
        save : str, optional
            Path to save the PNG.  If ``None``, ``plt.show()`` is called.
        show : bool
            Whether to call plt.show() after saving (default True).

        Examples
        --------
        ::

            anim.plot(time_idx=4)
            anim.plot(time_idx=0, save="snapshot.png", show=False)
        """
        lat, lon, field, time_val = self._get(time_idx)
        fig, ax = self._build_axes()
        self._draw_field(fig, ax, lat, lon, field, time_val)
        fig.tight_layout()

        if save:
            fig.savefig(save, dpi=self._dpi, bbox_inches="tight")
            w, h = self._figsize
            print(
                f"Saved: {save}  "
                f"({int(w * self._dpi)}×{int(h * self._dpi)} px @ {self._dpi} dpi)"
            )
            plt.close(fig)
        if show:
            plt.show()
        return self

    def animate(self) -> "RobinsonAnimator":
        """
        Render all frames to disk, then assemble the video.

        Missing frames are rendered; existing frames are reused (cache-friendly).
        """
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir     = _frames_dir(f"rob_{self._var}", run_date, cycle)
        n_frames = len(self._ds[self._var].time)

        self._print_render_info(n_frames)

        for tidx in range(n_frames):
            fpath = _frame_path(fdir, tidx)
            if not os.path.exists(fpath):
                self._render_frame(tidx, fpath)
            print(f"  frame {tidx + 1}/{n_frames}  →  {fpath}", end="\r")

        print()
        self._write_video(fdir, n_frames)
        print(f"Saved: {self._output}")
        return self