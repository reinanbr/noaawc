# mypy: disable-error-code=attr-defined

"""
PlateCarreeAnimator
================
Renders animated weather maps using the PlateCarree (equirectangular) projection,
built on the same design language as OrthoAnimator.

Two region-definition approaches:
  • set_region()  — explicit bounding box in lat/lon degrees
  • set_zoom()    — zoom level around a central point

See README_PlateCarreeAnimator.md for full documentation.
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
# (they live in the same package; import only what is needed)
from noaawc.projections.ortho import (          # adjust import path as needed
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
# Region helpers
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# Quality presets — 16:9 cinematic/TV aspect ratio
# ──────────────────────────────────────────────────────────────────────────────
# PlateCarree maps are rectangular, not square like the OrthoAnimator globe.
# These presets target standard broadcast/streaming resolutions (16:9) so the
# output drops directly into video timelines without letterboxing.
#
#   sd   →  1280×720  px  (HD-ready)
#   hd   →  1920×1080 px  (Full HD)
#   4k   →  3840×2160 px  (Ultra HD)
#   4k_60→  3840×2160 px  @ 60 fps
# ══════════════════════════════════════════════════════════════════════════════

QUALITY_PRESETS: dict = {
    "sd": {
        "dpi": 72,
        "figsize": (17.7778, 10.0000),  # 1280×720 px  (16:9)
        "fps": 6,
        "codec": "libx264",
        "quality": 6,
        "description": "SD 720p 16:9 — fast render, small file",
    },
    "hd": {
        "dpi": 120,
        "figsize": (16.0000, 9.0000),   # 1920×1080 px  (16:9)
        "fps": 24,
        "codec": "libx264",
        "quality": 8,
        "description": "Full HD 1080p 16:9 — balanced quality and speed",
    },
    "4k": {
        "dpi": 220,
        "figsize": (17.4545, 9.8182),   # 3840×2159 px  (16:9)
        "fps": 30,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K 16:9 — maximum quality, large file",
    },
    "4k_60": {
        "dpi": 220,
        "figsize": (17.4545, 9.8182),   # 3840×2159 px  (16:9)
        "fps": 60,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K 16:9 @ 60 fps — silky smooth, very large file",
    },
}


# Default region: South America + adjacent Atlantic
_DEFAULT_REGION = {
    "toplat":    5.0,
    "bottomlat": -35.0,
    "leftlon":   -82.0,
    "rightlon":  -30.0,
}

# Zoom-level → approximate degree-radius lookup (half-side in degrees)
# zoom=1 shows a ~continent-scale view; higher values zoom in progressively.
# The formula is: half_side = 180 / (2 ** zoom) — halves with each step.
def _zoom_to_half_side(zoom: float) -> float:
    """Return the half-side length in degrees for a given zoom level."""
    if zoom < 1:
        raise ValueError("zoom must be >= 1")
    # zoom=1  → 90°  (near-global),  zoom=2 → 45°,  zoom=4 → 22.5°, …
    return 90.0 / zoom


def _region_from_zoom(lat: float, lon: float, zoom: float) -> dict:
    """Build a region dict centred on (lat, lon) with the given zoom level."""
    half = _zoom_to_half_side(zoom)
    # 85° keeps a small margin from ±90° to avoid Cartopy feature artefacts
    return {
        "toplat":    min( 85.0, lat + half),
        "bottomlat": max(-85.0, lat - half),
        "leftlon":   lon - half,
        "rightlon":  lon + half,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Map feature helper (PlateCarree)
# ══════════════════════════════════════════════════════════════════════════════

def _add_features_pc(
    ax: plt.Axes,
    lw: float = 0.4,
    show_states: bool = False,
    show_ocean: bool = True,
) -> None:
    """Add cartographic features to a PlateCarree axes."""
    ax.add_feature(cfeature.LAND,      facecolor="#13171d", edgecolor="none",   zorder=0)
    if show_ocean:
        ax.add_feature(cfeature.OCEAN,     facecolor="#0d1520", edgecolor="none",   zorder=0)
    ax.add_feature(cfeature.COASTLINE, edgecolor="#2d6db5", linewidth=lw,        zorder=3)
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


def _add_gridlines_pc(ax: plt.Axes, scale: float = 1.0) -> None:
    """Add labelled gridlines to a PlateCarree axes."""
    gl = ax.gridlines(
        crs=ccrs.PlateCarree(),
        draw_labels=True,
        linewidth=0.3 * scale,
        color="#14181c",
        alpha=0.8,
        linestyle="--",
        zorder=2,
    )
    gl.top_labels   = False
    gl.right_labels = False
    gl.xlocator = mticker.MultipleLocator(10)
    gl.ylocator = mticker.MultipleLocator(10)
    gl.xlabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}
    gl.ylabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}


# ══════════════════════════════════════════════════════════════════════════════
# Axes-anchored overlay helpers
# ──────────────────────────────────────────────────────────────────────────────
# _draw_info_box() and _draw_data_credit() are defined in ortho_animator and
# imported above.  Both accept an optional ``ax`` keyword: when supplied they
# use ax.transAxes (anchored to the map frame); when omitted they fall back to
# figure coordinates (used by OrthoAnimator).
#
# PlateCarreeAnimator always passes ax=ax so the overlays sit correctly inside
# the map area regardless of the figure aspect ratio or colorbar padding.
# ══════════════════════════════════════════════════════════════════════════════


class PlateCarreeAnimator:
    """
    Renders an animated weather map using the PlateCarree (equirectangular) projection.

    Designed to be a sibling of OrthoAnimator: same API, same dark theme,
    same variable presets, same quality presets — but on a 2-D flat map
    that is more natural for regional views.

    Region definition
    -----------------
    You MUST define the visible region before calling animate() or plot().
    Two approaches are available:

    1. Explicit bounding box::

        anim.set_region(
            region={
                "toplat":    5,
                "bottomlat": -35,
                "leftlon":   -75,
                "rightlon":  -34,
            }
        )

    2. Zoom around a point::

        anim.set_zoom(zoom=4, pos=(-9.4, -40.5))   # (lat, lon)

    Named shortcut regions (call set_region with a string key)::

        anim.set_region("south_america")   # entire continent
        anim.set_region("brazil")          # Brazil only
        anim.set_region("northeast_br")    # Northeast Brazil
        anim.set_region("north_br")        # North Brazil
        anim.set_region("southeast_br")    # Southeast Brazil
        anim.set_region("south_br")        # South Brazil

    Quick start
    -----------
    ::

        anim = PlateCarreeAnimator(ds, "t2m")
        anim.set_region("south_america")
        anim.set_output("sa_temperature.mp4")
        anim.animate()

    Zoom example::

        anim = PlateCarreeAnimator(ds, "prmsl")
        anim.set_zoom(zoom=3, pos=(-15.0, -50.0))
        anim.set_quality("hd")
        anim.animate()

    Annotations, author, quality presets, titles, and all other setters work
    identically to OrthoAnimator — see that class for full documentation.
    """

    # ── named region shortcuts ────────────────────────────────────────────────
    # PlateCarree supports ±90°, but we cap at ±85° to avoid feature artefacts.
    # The "global" preset uses ±85° which is visually near-global and safe.
    _NAMED_REGIONS: dict[str, dict] = {
        "south_america": {"toplat":  15.0, "bottomlat": -60.0, "leftlon":  -85.0, "rightlon":  -30.0},
        "brazil":        {"toplat":   6.0, "bottomlat": -34.0, "leftlon":  -75.0, "rightlon":  -28.0},
        "northeast_br":  {"toplat":  -1.0, "bottomlat": -18.0, "leftlon":  -47.0, "rightlon":  -34.0},
        "north_br":      {"toplat":   5.5, "bottomlat":  -5.0, "leftlon":  -74.0, "rightlon":  -44.0},
        "southeast_br":  {"toplat": -14.0, "bottomlat": -25.5, "leftlon":  -53.0, "rightlon":  -39.0},
        "south_br":      {"toplat": -22.0, "bottomlat": -34.0, "leftlon":  -58.0, "rightlon":  -47.0},
        "global":        {"toplat":  85.0, "bottomlat": -85.0, "leftlon": -179.9, "rightlon":  179.9},
    }

    # Hard latitude limits for the PlateCarree projection.
    # Beyond ±85° the y-coordinate diverges to ±∞ and Cartopy raises
    # "Axis limits cannot be NaN or Inf".  We clamp silently.
    _PC_LAT_MAX: float = 80.0

    # ── class-level defaults ──────────────────────────────────────────────────
    _OUTPUT_DEFAULT       = "output_plate_carree.mp4"
    _FPS_DEFAULT          = 6
    _STEP_DEFAULT         = 1
    _DPI_DEFAULT          = 120
    _FIGSIZE_DEFAULT      = (16.0, 9.0)   # 16:9 — Full HD aspect ratio
    _CODEC_DEFAULT        = "libx264"
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

        # region — start with South America as sensible default
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
                f"[PlateCarreeAnimator] No preset for '{var}' — "
                f"falling back to temperature defaults."
            )
        self._cmap        = p["cmap"]
        self._levels      = np.asarray(p["levels"])
        self._cbar_label  = p["cbar_label"]
        self._plot_title  = p["plot_title"]

    def use_variable_defaults(self, var: str | None = None) -> "PlateCarreeAnimator":
        """Apply the plotting preset for *var* (or the instance variable if omitted)."""
        key = var if var is not None else self._var
        self._apply_variable_preset(key, silent=False)
        return self

    # ── region / zoom ─────────────────────────────────────────────────────────

    def set_region(
        self,
        region: dict | str | None = None,
        *,
        toplat:    float | None = None,
        bottomlat: float | None = None,
        leftlon:   float | None = None,
        rightlon:  float | None = None,
    ) -> "PlateCarreeAnimator":
        """
        Define the map extent as a bounding box.

        You can pass the region in three ways:

        **1. Named shortcut (string)**::

            anim.set_region("south_america")
            anim.set_region("brazil")
            anim.set_region("northeast_br")
            anim.set_region("north_br")
            anim.set_region("southeast_br")
            anim.set_region("south_br")
            anim.set_region("global")

        **2. Dictionary**::

            anim.set_region(
                region={
                    "toplat":    5,
                    "bottomlat": -35,
                    "leftlon":   -75,
                    "rightlon":  -34,
                }
            )

        **3. Keyword arguments**::

            anim.set_region(toplat=5, bottomlat=-35, leftlon=-75, rightlon=-34)

        Parameters
        ----------
        region : dict or str, optional
            Either a named shortcut key or a dict with keys
            ``toplat``, ``bottomlat``, ``leftlon``, ``rightlon``.
        toplat, bottomlat, leftlon, rightlon : float, optional
            Individual edge values — used when *region* is ``None``.

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
            }

        self._validate_region()
        return self

    def set_zoom(
        self,
        zoom: float,
        pos: tuple[float, float],
    ) -> "PlateCarreeAnimator":
        """
        Define the map extent by zooming into a geographic point.

        The visible area is a square centred on *pos* with a half-side of
        ``90 / zoom`` degrees.

        Parameters
        ----------
        zoom : float
            Zoom level.  Must be ≥ 1.

            =======  ===========  ====================================
            Value    Half-side    Coverage
            =======  ===========  ====================================
            1        90°          Near-global
            2        45°          Continental  (e.g. South America)
            3        30°          Sub-continental
            4        22.5°        Regional     (e.g. Northeast Brazil)
            6        15°          State-level
            8        11.25°       City + surroundings
            =======  ===========  ====================================

        pos : (lat, lon)
            Centre of the zoomed view in decimal degrees.
            Example: ``(-9.4, -40.5)`` for Juazeiro-BA.

        Returns
        -------
        self

        Examples
        --------
        ::

            anim.set_zoom(zoom=4, pos=(-9.4, -40.5))    # Northeast Brazil
            anim.set_zoom(zoom=2, pos=(-15.0, -50.0))   # Central Brazil
            anim.set_zoom(zoom=1, pos=(0.0, 0.0))        # Global-ish
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
    # (mirrors OrthoAnimator exactly)

    def set_output(self, path: str) -> "PlateCarreeAnimator":
        """Output file path (.mp4 or .gif)."""
        self._output = path
        return self

    def set_fps(self, fps: int) -> "PlateCarreeAnimator":
        """Frames per second for the output video."""
        self._fps = fps
        return self

    def set_step(self, step: int) -> "PlateCarreeAnimator":
        """Spatial decimation factor (1 = no decimation)."""
        self._step = step
        return self

    def set_dpi(self, dpi: int) -> "PlateCarreeAnimator":
        """Figure resolution in dots per inch."""
        self._dpi = dpi
        return self

    def set_figsize(self, w: float, h: float) -> "PlateCarreeAnimator":
        """Figure size in inches (width, height)."""
        self._figsize = (w, h)
        return self

    def set_codec(self, codec: str) -> "PlateCarreeAnimator":
        """Video codec (libx264, libx265, vp9, prores)."""
        self._codec = codec
        return self

    def set_video_quality(self, quality: int) -> "PlateCarreeAnimator":
        """Encoding quality 0–10 (higher = better / larger file)."""
        if not 0 <= quality <= 10:
            raise ValueError("quality must be between 0 and 10.")
        self._video_quality = quality
        return self

    def set_quality(self, preset: str) -> "PlateCarreeAnimator":
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

    def set_cmap(self, cmap) -> "PlateCarreeAnimator":
        """Override the colormap (name string or matplotlib object)."""
        self._cmap = plt.get_cmap(cmap) if isinstance(cmap, str) else cmap
        return self

    def set_levels(self, levels) -> "PlateCarreeAnimator":
        """Override the BoundaryNorm levels."""
        self._levels = np.asarray(levels)
        return self

    def set_cbar_label(self, label: str) -> "PlateCarreeAnimator":
        """Label shown on the colorbar."""
        self._cbar_label = label
        return self

    def set_plot_title(self, title: str) -> "PlateCarreeAnimator":
        """Static left-side title shown on each frame."""
        self._plot_title = title
        return self

    def set_title(
        self,
        template: str,
        date_style: str = "en",
    ) -> "PlateCarreeAnimator":
        """
        Dynamic per-frame title with ``%S`` as the date placeholder.

        Supported ``date_style`` values: ``"en"``, ``"pt-br"``, ``"es"``, ``"fr"``.
        """
        self._title_template  = template if template else None
        self._title_date_style = date_style
        return self

    # ── feature flags ─────────────────────────────────────────────────────────

    def set_states(self, visible: bool = True) -> "PlateCarreeAnimator":
        """Show / hide state/province boundary lines."""
        self._show_states = visible
        return self

    def set_ocean(self, visible: bool = True) -> "PlateCarreeAnimator":
        """Show / hide the ocean colour fill (default: on)."""
        self._show_ocean = visible
        return self

    def set_grid(self, visible: bool = True) -> "PlateCarreeAnimator":
        """Show / hide lat/lon gridlines with labels (default: on)."""
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
    ) -> "PlateCarreeAnimator":
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
    ) -> "PlateCarreeAnimator":
        """
        Add a text annotation (with optional position marker) on every frame.

        Parameters and behaviour are identical to ``OrthoAnimator.set_annotate()``.

        Examples
        --------
        ::

            anim.set_annotate("Juazeiro %.1f°C", pos=(-9.4, -40.5))
            anim.set_annotate("Fortaleza %.1f°C", pos=(-3.72, -38.54),
                              color="#58a6ff", marker="*")
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

    def clear_annotations(self) -> "PlateCarreeAnimator":
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
        r = self._region

        # ── clamp latitudes to safe PlateCarree bounds ───────────────────────
        # PlateCarree clips at ±90°, but we stay at ±85° to avoid edge
        # artefacts with some Cartopy feature datasets.
        lat_max  = self._PC_LAT_MAX
        safe_top = max(-lat_max, min(lat_max, r["toplat"]))
        safe_bot = max(-lat_max, min(lat_max, r["bottomlat"]))

        proj  = ccrs.PlateCarree()
        scale = _font_scale(self._dpi)

        fig, ax = plt.subplots(
            figsize=self._figsize,
            subplot_kw={"projection": proj},
            facecolor="#0d1117",
            dpi=self._dpi,
        )
        ax.set_extent(
            [r["leftlon"], r["rightlon"], safe_bot, safe_top],
            crs=ccrs.PlateCarree(),
        )
        _add_features_pc(
            ax,
            lw=0.5 * scale,
            show_states=self._show_states,
            show_ocean=self._show_ocean,
        )
        if self._show_grid:
            _add_gridlines_pc(ax, scale=scale)

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

        # figure-level overlays — anchored to the axes, not the figure,
        # so they stay inside the map frame for any aspect ratio.
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
        print(
            f"Render: {n_frames} frames  |  {px_w}×{px_h} px  |  {self._dpi} dpi  |  "
            f"{self._fps} fps  |  codec={self._codec}  quality={self._video_quality}  "
            f"annotations={len(self._annotations)}\n"
            f"Region: lat [{r['bottomlat']:.1f} … {r['toplat']:.1f}]  "
            f"lon [{r['leftlon']:.1f} … {r['rightlon']:.1f}]  →  {self._output}"
        )

    # ── public entry points ───────────────────────────────────────────────────

    def plot(
        self,
        time_idx: int = 0,
        save: str | None = None,
        show: bool = True,
    ) -> "PlateCarreeAnimator":
        """
        Render a single static frame.

        Parameters
        ----------
        time_idx : int
            Time index (default 0 = first step).
        save : str, optional
            Path to save the PNG (e.g. ``"snapshot.png"``).
            If ``None``, ``plt.show()`` is called.
        show : bool
            Whether to call plt.show() after saving (default True).

        Examples
        --------
        ::

            anim.plot(time_idx=6)
            anim.plot(time_idx=0, save="fig.png")
        """
        lat, lon, field, time_val = self._get(time_idx)
        fig, ax = self._build_axes()
        self._draw_field(fig, ax, lat, lon, field, time_val)
        fig.tight_layout()

        if save:
            fig.savefig(save, dpi=self._dpi, bbox_inches="tight")
            w, h = self._figsize
            print(f"Saved: {save}  ({int(w*self._dpi)}×{int(h*self._dpi)} px @ {self._dpi} dpi)")
            plt.close(fig)
        if show:
            plt.show()
        return self

    def animate(self) -> "PlateCarreeAnimator":
        """
        Render all frames to disk, then assemble the video.

        Missing frames are rendered; existing frames are reused (cache-friendly).
        """
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir     = _frames_dir(f"pc_{self._var}", run_date, cycle)
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