# mypy: disable-error-code=attr-defined

"""
NearsidePerspectiveAnimator
===========================
Renders animated GFS weather maps using the Nearside Perspective projection —
a satellite-view of the globe seen from a finite altitude above a central point.

Unlike the Orthographic projection (which simulates a camera at infinite
distance), Nearside Perspective uses a physically meaningful satellite_height
parameter to control how much of the globe is visible and the degree of
curvature at the limb.  Lower altitudes zoom in and reveal more atmospheric
perspective; higher altitudes approach the look of an orthographic globe.

Key unique parameters
---------------------
central_point : (lon, lat)
    Geographic point directly below the satellite camera.

satellite_height : float
    Camera altitude above Earth's surface in metres.
    Controls the field of view: lower = tighter zoom, higher = wider globe.

    Useful reference altitudes
    --------------------------
    200_000        Low Earth Orbit (LEO) — very tight, almost orthographic
    35_786_000     Geostationary orbit (GOES / Meteosat height) ← default
    100_000_000    High exospheric — near-orthographic wide view
    1_000_000_000  "Moon distance" — essentially orthographic

rotation : set_rotation(lon_start, lon_end, lat_start, lat_end)
    Animate the camera arc across the globe (same API as OrthoAnimator).

See README_NearsidePerspectiveAnimator.md for full documentation.
"""

import os
import re
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


# ── shared helpers from OrthoAnimator ────────────────────────────────────────
from noaawc.ortho import (          # adjust import path as needed
    QUALITY_PRESETS,
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
# Projection constants
# ══════════════════════════════════════════════════════════════════════════════

# Geostationary orbit altitude — same as GOES-16, Meteosat, Himawari-9.
# At this height roughly 42 % of Earth's surface is visible, which gives
# a recognisable "weather satellite" look with a clear curved horizon.
GEOSTATIONARY_HEIGHT: float = 35_786_000.0   # metres

# Earth's mean radius used by Cartopy's Globe (metres).
EARTH_RADIUS: float = 6_371_229.0

# The maximum angular radius (degrees from sub-satellite point) that is
# visible at a given satellite_height h is:
#
#   max_angle = arccos( R / (R + h) )
#
# We stay a few degrees inside this to avoid singularities at the limb.
def _visible_radius_deg(satellite_height: float) -> float:
    """
    Return the maximum angular radius (degrees) visible from the given altitude.

    Parameters
    ----------
    satellite_height : float
        Camera altitude above Earth's surface in metres.

    Returns
    -------
    float
        Angular radius in degrees (slightly inset from the true limb to avoid
        projection singularities at the very edge).
    """
    R = EARTH_RADIUS
    h = satellite_height
    # True limb angle; subtract 1° safety margin so the horizon stays finite.
    return float(np.degrees(np.arccos(R / (R + h)))) - 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Map feature helper
# ══════════════════════════════════════════════════════════════════════════════

def _add_features_ns(
    ax: plt.Axes,
    lw: float = 0.4,
    show_states: bool = False,
) -> None:
    """Add cartographic features to a Nearside Perspective axes."""
    ax.add_feature(cfeature.LAND,      facecolor="#13171d", edgecolor="none", zorder=0)
    ax.add_feature(cfeature.COASTLINE, edgecolor="#2d6db5", linewidth=lw,     zorder=3)
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


# ══════════════════════════════════════════════════════════════════════════════
# NearsidePerspectiveAnimator
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# Author-label helper — reads the colorbar position after tight_layout()
# ══════════════════════════════════════════════════════════════════════════════

def _author_above_cbar(
    fig: plt.Figure,
    text: str,
    scale: float = 1.0,
    kw: dict | None = None,
) -> None:
    """
    Draw the author label in figure coordinates, horizontally centred and
    vertically just above the horizontal colorbar.

    Must be called **after** ``fig.tight_layout()`` (or ``fig.savefig`` with
    ``bbox_inches="tight"``) so that the colorbar axes bounding box is
    already in its final position.

    Position is computed by iterating over all axes in the figure and taking
    the highest ``y0`` of any axes whose width is notably larger than its
    height (i.e. the colorbar strip).  Falls back to ``y=0.06`` when no
    colorbar axes is found.

    Parameters
    ----------
    fig   : active Figure
    text  : author string
    scale : DPI-proportional font scale factor
    kw    : author_kwargs dict stored by set_author()
    """
    if kw is None:
        kw = {}

    # ── locate colorbar axes ──────────────────────────────────────────────────
    cbar_top = None
    renderer = fig.canvas.get_renderer()
    for child_ax in fig.axes:
        bb = child_ax.get_window_extent(renderer=renderer)
        # Colorbar is much wider than tall in figure coords
        fig_w_px = fig.get_figwidth()  * fig.dpi
        fig_h_px = fig.get_figheight() * fig.dpi
        w_frac = bb.width  / fig_w_px
        h_frac = bb.height / fig_h_px
        if w_frac > 0.3 and h_frac < 0.08:          # horizontal colorbar heuristic
            top_frac = (bb.y0 + bb.height) / fig_h_px
            if cbar_top is None or top_frac > cbar_top:
                cbar_top = top_frac

    if cbar_top is None:
        cbar_top = 0.06   # safe fallback

    # Place the label a small fixed gap above the colorbar top edge.
    # The gap scales with the font height so it looks consistent at all DPIs.
    font_h_frac = (kw.get("fontsize", 8.5) * scale * 1.6) / (fig.get_figheight() * fig.dpi)
    y_pos = cbar_top + font_h_frac * 0.8

    bbox_props = None
    if kw.get("bbox"):
        bbox_props = dict(
            boxstyle=f"round,pad={kw.get('bbox_pad', 0.4)}",
            facecolor=kw.get("bbox_facecolor", "#161b22"),
            edgecolor=kw.get("bbox_edgecolor", "#30363d"),
            linewidth=0.8 * scale,
            alpha=kw.get("bbox_alpha", 0.75),
        )

    fig.text(
        kw.get("x") or 0.5,
        y_pos,
        text,
        ha=kw.get("ha", "center"),
        va="bottom",
        fontsize=round(kw.get("fontsize", 8.5) * scale, 1),
        color=kw.get("color", "#e6edf3"),
        fontweight=kw.get("fontweight", "bold"),
        fontfamily=kw.get("fontfamily", "monospace"),
        alpha=kw.get("alpha", 1.0),
        bbox=bbox_props,
        zorder=10,
    )

class NearsidePerspectiveAnimator:
    """
    Renders an animated weather map using the Nearside Perspective projection.

    The Nearside Perspective (also called "satellite view" or "tilted perspective")
    simulates a camera at a finite altitude above a central geographic point.
    It produces a realistic globe with a visible curved horizon — the defining
    visual of actual weather satellite imagery.

    Compared to OrthoAnimator
    -------------------------
    - OrthoAnimator uses ccrs.Orthographic: camera at infinity → no perspective foreshortening.
    - NearsidePerspectiveAnimator uses ccrs.NearsidePerspective: camera at a finite
      satellite_height → realistic perspective distortion and a physically-correct limb.

    The API is identical to OrthoAnimator — same quality presets, variable presets,
    annotation system, rotation, author label, and dark theme.

    Quick start
    -----------
    ::

        anim = NearsidePerspectiveAnimator(ds, "t2m")
        anim.set_view(lon=-50.0, lat=-15.0)
        anim.set_output("brazil_sat.mp4")
        anim.animate()

    Geostationary look (GOES-16 / Meteosat style)
    ----------------------------------------------
    The default satellite_height is 35 786 000 m (geostationary orbit),
    which matches GOES-16, Meteosat-12, and Himawari-9 and shows roughly
    42 % of the Earth's surface with a familiar curved horizon::

        anim.set_view(lon=-75.0, lat=0.0)   # GOES-West-ish position

    Zoomed satellite look
    ---------------------
    Lower altitudes zoom in on the central point — useful for regional
    "high-resolution satellite" aesthetics::

        anim.set_view(lon=-40.5, lat=-9.4, satellite_height=3_000_000)

    Camera rotation (same as OrthoAnimator)
    ----------------------------------------
    ::

        anim.set_rotation(lon_start=-90, lon_end=-20,
                          lat_start=-5,  lat_end=-20)
        anim.set_rotation_stop(fraction=0.65)

    Altitude reference table
    ------------------------
    ==============  ===========================================================
    Height (m)      Description
    ==============  ===========================================================
    200 000         Low Earth Orbit — very tight view, heavy perspective
    1 000 000       Low satellite / CubeSat altitude
    3 000 000       Regional satellite — South America fills the disk
    10 000 000      Mid-range — continent + ocean context
    35 786 000      **Geostationary orbit** (GOES / Meteosat / Himawari) ← default
    100 000 000     High exospheric — near-orthographic
    1 000 000 000   "Moon distance" — essentially identical to Orthographic
    ==============  ===========================================================

    Quality presets
    ---------------
    Identical to OrthoAnimator (square figure, globe fills the frame)::

        anim.set_quality("sd")      #  72 dpi,  8×8 in,   6 fps
        anim.set_quality("hd")      # 120 dpi, 10×10 in, 24 fps
        anim.set_quality("4k")      # 220 dpi, 17×17 in, 30 fps
        anim.set_quality("4k_60")   # 220 dpi, 17×17 in, 60 fps

    Annotations
    -----------
    ::

        anim.set_annotate("Juazeiro %.1f°C", pos=(-9.4, -40.5))
        anim.set_annotate("Fortaleza %.1f°C", pos=(-3.72, -38.54),
                          color="#58a6ff", marker="*")

    Author label
    ------------
    ::

        anim.set_author("Maria Silva")
        anim.set_author("@handle", x=0.98, ha="right")

    Dynamic title with per-frame date
    ----------------------------------
    ::

        anim.set_title("Surface Temperature — %S", date_style="pt-br")

    Static snapshot
    ---------------
    ::

        anim.plot(time_idx=0, save="snapshot.png")
    """

    # ── class-level defaults ──────────────────────────────────────────────────
    _OUTPUT_DEFAULT        = "output_nearside.mp4"
    _FPS_DEFAULT           = 6
    _STEP_DEFAULT          = 1
    _DPI_DEFAULT           = 120
    _FIGSIZE_DEFAULT       = (10.0, 10.0)   # square — globe fills the frame
    _CODEC_DEFAULT         = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8

    # Default view: centred over South America, geostationary altitude.
    _DEFAULT_LON: float = -50.0
    _DEFAULT_LAT: float = -15.0
    _DEFAULT_HEIGHT: float = GEOSTATIONARY_HEIGHT

    def __init__(
        self,
        ds,
        var: str,
        lon: float = _DEFAULT_LON,
        lat: float = _DEFAULT_LAT,
        satellite_height: float = _DEFAULT_HEIGHT,
    ):
        """
        Parameters
        ----------
        ds               : xarray Dataset (GFS / noaawc format)
        var              : variable key  (e.g. "t2m")
        lon              : sub-satellite longitude in decimal degrees
        lat              : sub-satellite latitude  in decimal degrees
        satellite_height : camera altitude above Earth's surface in metres.
                           Default: 35 786 000 (geostationary orbit).
        """
        self._ds  = ds
        self._var = var

        # camera / projection
        self._lon:    float = float(lon)
        self._lat:    float = float(lat)
        self._height: float = float(satellite_height)

        # output
        self._output        = self._OUTPUT_DEFAULT
        self._fps           = self._FPS_DEFAULT
        self._step          = self._STEP_DEFAULT
        self._dpi           = self._DPI_DEFAULT
        self._figsize: tuple[float, float] = self._FIGSIZE_DEFAULT
        self._codec         = self._CODEC_DEFAULT
        self._video_quality = self._VIDEO_QUALITY_DEFAULT

        # variable preset
        self._apply_variable_preset(var, silent=False)

        # rotation (None = static camera)
        self._lon_start:     float | None = None
        self._lat_start:     float | None = None
        self._lon_end:       float | None = None
        self._lat_end:       float | None = None
        self._stop_frame:    int   | None = None
        self._stop_fraction: float | None = None

        # annotations
        self._annotations: list[dict] = []

        # custom title
        self._title_template:   str | None = None
        self._title_date_style: str = "en"

        # feature flags
        self._show_states: bool = False

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
                f"[NearsidePerspectiveAnimator] No preset for '{var}' — "
                f"falling back to temperature defaults."
            )
        self._cmap       = p["cmap"]
        self._levels     = np.asarray(p["levels"])
        self._cbar_label = p["cbar_label"]
        self._plot_title = p["plot_title"]

    def use_variable_defaults(self, var: str | None = None) -> "NearsidePerspectiveAnimator":
        """Apply the plotting preset for *var* (or the instance variable if omitted)."""
        key = var if var is not None else self._var
        self._apply_variable_preset(key, silent=False)
        return self

    # ── camera / view ─────────────────────────────────────────────────────────

    def set_view(
        self,
        lon: float,
        lat: float,
        satellite_height: float | None = None,
    ) -> "NearsidePerspectiveAnimator":
        """
        Set the sub-satellite point and optional altitude.

        Parameters
        ----------
        lon              : sub-satellite longitude (decimal degrees)
        lat              : sub-satellite latitude  (decimal degrees)
        satellite_height : camera altitude in metres.
                           If omitted, the current height is kept unchanged.

        Examples
        --------
        ::

            anim.set_view(lon=-50.0, lat=-15.0)                     # keep current height
            anim.set_view(lon=-75.0, lat=0.0, satellite_height=35_786_000)  # GOES-West
            anim.set_view(lon=-40.5, lat=-9.4, satellite_height=3_000_000)  # regional zoom
        """
        self._lon = float(lon)
        self._lat = float(lat)
        if satellite_height is not None:
            self._height = float(satellite_height)
        return self

    def set_satellite_height(self, height: float) -> "NearsidePerspectiveAnimator":
        """
        Set the camera altitude above Earth's surface in metres.

        This is the primary zoom control for the Nearside Perspective projection.
        Lower values zoom in on the central point; higher values approach the
        look of an orthographic globe.

        Parameters
        ----------
        height : float
            Altitude in metres.  Must be > 0.

        Altitude presets (use as reference)
        ------------------------------------
        ::

            anim.set_satellite_height(200_000)          # LEO — very tight
            anim.set_satellite_height(3_000_000)        # Regional satellite
            anim.set_satellite_height(35_786_000)       # Geostationary (default)
            anim.set_satellite_height(100_000_000)      # Near-orthographic

        Returns
        -------
        self
        """
        if height <= 0:
            raise ValueError("satellite_height must be > 0.")
        self._height = float(height)
        return self

    # ── rotation (identical API to OrthoAnimator) ─────────────────────────────

    def set_rotation(
        self,
        lon_start: float,
        lon_end:   float,
        lat_start: float | None = None,
        lat_end:   float | None = None,
    ) -> "NearsidePerspectiveAnimator":
        """
        Define the camera arc from (lon_start, lat_start) to (lon_end, lat_end).

        The sub-satellite point interpolates smoothly between the two positions
        across the animation frames (up to the stop frame set by
        set_rotation_stop()).

        If lat_start / lat_end are omitted, the current sub-satellite latitude
        is held constant throughout the rotation.

        Examples
        --------
        ::

            anim.set_rotation(lon_start=-90, lon_end=-20,
                              lat_start=-5,  lat_end=-20)
            anim.set_rotation_stop(fraction=0.65)
        """
        # ── validate and clamp latitude endpoints ───────────────────────────
        # pyproj's nsper projection rejects |lat_0| > 90 with CRSError.
        # We clamp silently and warn so the user knows what happened, rather
        # than letting an invalid value propagate through 100+ frames and
        # crash mid-render.
        _LAT_LIMIT = 89.9   # leave a 0.1° margin from the pole

        def _safe_lat(v: float, name: str) -> float:
            clamped = max(-_LAT_LIMIT, min(_LAT_LIMIT, v))
            if abs(clamped - v) > 0.01:
                print(
                    f"[NearsidePerspectiveAnimator] WARNING: {name}={v:.4f}° "
                    f"is outside ±{_LAT_LIMIT}° — clamped to {clamped:.4f}°."
                )
            return clamped

        self._lon_start = float(lon_start)
        self._lon_end   = float(lon_end)
        self._lat_start = _safe_lat(
            float(lat_start) if lat_start is not None else self._lat,
            "lat_start",
        )
        self._lat_end = _safe_lat(
            float(lat_end) if lat_end is not None else self._lat,
            "lat_end",
        )
        return self

    def set_rotation_stop(
        self,
        frame:    int   | None = None,
        fraction: float | None = None,
    ) -> "NearsidePerspectiveAnimator":
        """
        Frame index at which the camera arc ends and the view freezes.

        Provide either ``frame`` (absolute index) **or** ``fraction``
        (0.0–1.0 relative to total frame count), not both.
        """
        if frame is not None and fraction is not None:
            raise ValueError("Provide 'frame' or 'fraction', not both.")
        if fraction is not None:
            if not 0.0 < fraction < 1.0:
                raise ValueError("fraction must be strictly between 0 and 1.")
            self._stop_fraction = float(fraction)
            self._stop_frame    = None
        else:
            self._stop_frame    = frame
            self._stop_fraction = None
        return self

    # ── output options ────────────────────────────────────────────────────────

    def set_output(self, path: str) -> "NearsidePerspectiveAnimator":
        """Output file path (.mp4 or .gif)."""
        self._output = path
        return self

    def set_fps(self, fps: int) -> "NearsidePerspectiveAnimator":
        """Frames per second for the output video."""
        self._fps = fps
        return self

    def set_step(self, step: int) -> "NearsidePerspectiveAnimator":
        """Spatial decimation factor (1 = no decimation)."""
        self._step = step
        return self

    def set_dpi(self, dpi: int) -> "NearsidePerspectiveAnimator":
        """Figure resolution in dots per inch."""
        self._dpi = dpi
        return self

    def set_figsize(self, w: float, h: float) -> "NearsidePerspectiveAnimator":
        """Figure size in inches (width, height)."""
        self._figsize = (w, h)
        return self

    def set_codec(self, codec: str) -> "NearsidePerspectiveAnimator":
        """Video codec (libx264, libx265, vp9, prores)."""
        self._codec = codec
        return self

    def set_video_quality(self, quality: int) -> "NearsidePerspectiveAnimator":
        """Encoding quality 0–10 (higher = better / larger file)."""
        if not 0 <= quality <= 10:
            raise ValueError("quality must be between 0 and 10.")
        self._video_quality = quality
        return self

    def set_quality(self, preset: str) -> "NearsidePerspectiveAnimator":
        """
        Apply a named quality preset.

        The Nearside Perspective projection produces a square globe image —
        the presets use square figsize values identical to OrthoAnimator.

        Available: ``"sd"``, ``"hd"``, ``"4k"``, ``"4k_60"``.
        Call ``list_quality_presets()`` for details.
        """
        if preset not in QUALITY_PRESETS:
            opts = ", ".join(f'"{k}"' for k in QUALITY_PRESETS)
            raise ValueError(f"Unknown preset '{preset}'. Choose from: {opts}")
        p = QUALITY_PRESETS[preset]
        self._dpi           = p["dpi"]
        self._figsize       = p["figsize"]
        self._fps           = p["fps"]
        self._codec         = p["codec"]
        self._video_quality = p["quality"]
        print(f"Quality preset '{preset}': {p['description']}")
        return self

    # ── colormap / levels ─────────────────────────────────────────────────────

    def set_cmap(self, cmap) -> "NearsidePerspectiveAnimator":
        """Override the colormap (name string or matplotlib object)."""
        self._cmap = plt.get_cmap(cmap) if isinstance(cmap, str) else cmap
        return self

    def set_levels(self, levels) -> "NearsidePerspectiveAnimator":
        """Override the BoundaryNorm levels."""
        self._levels = np.asarray(levels)
        return self

    def set_cbar_label(self, label: str) -> "NearsidePerspectiveAnimator":
        """Label shown on the colorbar."""
        self._cbar_label = label
        return self

    def set_plot_title(self, title: str) -> "NearsidePerspectiveAnimator":
        """Static left-side title shown on each frame."""
        self._plot_title = title
        return self

    def set_title(
        self,
        template: str,
        date_style: str = "en",
    ) -> "NearsidePerspectiveAnimator":
        """
        Dynamic per-frame title with ``%S`` as the date placeholder.

        Supported ``date_style`` values: ``"en"``, ``"pt-br"``, ``"es"``, ``"fr"``.

        Examples
        --------
        ::

            anim.set_title("Surface Temperature — %S", date_style="pt-br")
            # → "Surface Temperature — 17 Abr 2026 03:00"
        """
        self._title_template   = template if template else None
        self._title_date_style = date_style
        return self

    # ── feature flags ─────────────────────────────────────────────────────────

    def set_states(self, visible: bool = True) -> "NearsidePerspectiveAnimator":
        """Show / hide state/province boundary lines (default: off)."""
        self._show_states = visible
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
    ) -> "NearsidePerspectiveAnimator":
        """
        Set the author / credit label displayed on every frame.

        Pass ``""`` to disable.  All parameters are identical to
        ``OrthoAnimator.set_author()``.
        """
        self._author = name.strip()
        # x=None / y=None → _draw_author computes the position at render time
        # from the actual figure dimensions and DPI, so the label scales
        # correctly across all presets and aspect ratios.
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
    ) -> "NearsidePerspectiveAnimator":
        """
        Add a city label / value annotation on every frame.

        Parameters and behaviour are identical to ``OrthoAnimator.set_annotate()``.
        Annotations outside the visible disk are automatically clipped by Cartopy.

        Examples
        --------
        ::

            anim.set_annotate("Juazeiro %.1f°C",  pos=(-9.4,  -40.5))
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

    def clear_annotations(self) -> "NearsidePerspectiveAnimator":
        """Remove all registered annotations."""
        self._annotations.clear()
        return self

    # ── named variable convenience shortcuts ──────────────────────────────────

    def use_temperature_defaults(self)    -> "NearsidePerspectiveAnimator":
        return self.use_variable_defaults("t2m")

    def use_pressure_defaults(self)       -> "NearsidePerspectiveAnimator":
        return self.use_variable_defaults("prmsl")

    def use_precipitation_defaults(self)  -> "NearsidePerspectiveAnimator":
        return self.use_variable_defaults("prate")

    def use_humidity_defaults(self)       -> "NearsidePerspectiveAnimator":
        return self.use_variable_defaults("r2")

    def use_wind_speed_defaults(self)     -> "NearsidePerspectiveAnimator":
        return self.use_variable_defaults("wspd10")

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

    def _resolve_stop_frame(self, n_frames: int) -> int:
        if self._stop_fraction is not None:
            return max(1, int(round(self._stop_fraction * n_frames)))
        if self._stop_frame is not None:
            return self._stop_frame
        return n_frames

    def _camera_at(self, tidx: int, stop: int) -> tuple[float, float]:
        """
        Return the (lon, lat) of the sub-satellite point for frame *tidx*.

        Latitude is clamped to [-89.9°, 89.9°] on every call — pyproj's
        nsper projection raises CRSError for |lat_0| > 90°, and the linear
        interpolation between two valid endpoints can still produce an
        out-of-range intermediate value when stop=1 and tidx=0 on edge cases.

        When no rotation is set the camera stays fixed at (self._lon, self._lat).
        """
        _LAT_LIMIT = 89.9

        if self._lon_start is None:
            return (self._lon, max(-_LAT_LIMIT, min(_LAT_LIMIT, self._lat)))

        if tidx >= stop:
            lon = self._lon_end   # type: ignore[assignment]
            lat = self._lat_end   # type: ignore[assignment]
        else:
            t   = tidx / stop
            lon = self._lon_start + t * (self._lon_end - self._lon_start)   # type: ignore[operator]
            lat = self._lat_start + t * (self._lat_end - self._lat_start)   # type: ignore[operator]

        return (float(lon), max(-_LAT_LIMIT, min(_LAT_LIMIT, float(lat))))

    def _build_axes(self, central: tuple[float, float]) -> tuple[plt.Figure, plt.Axes]:
        """
        Create a figure and axes with the Nearside Perspective projection
        centred on *central* = (lon, lat) at the current satellite_height.
        """
        lon_c, lat_c = central
        proj  = ccrs.NearsidePerspective(
            central_longitude=lon_c,
            central_latitude=lat_c,
            satellite_height=self._height,
        )
        scale = _font_scale(self._dpi)

        fig, ax = plt.subplots(
            figsize=self._figsize,
            subplot_kw={"projection": proj},
            facecolor="#0d1117",
            dpi=self._dpi,
        )
        ax.set_global()
        _add_features_ns(ax, lw=0.5 * scale, show_states=self._show_states)
        return fig, ax

    def _draw_annotations(self, ax, lat, lon, field) -> None:
        if not self._annotations:
            return
        scale = _font_scale(self._dpi)
        # Regex matches real printf-style specs (%d, %.1f, %e, …) only.
        # A bare "%" (unit symbol like "80%" or "(%)" ) does NOT match,
        # preventing "incomplete format" ValueError on variables like r2.
        _FMT_RE = re.compile(r'%[-+0-9*.]*[diouxXeEfFgGcrs]')
        for ann in self._annotations:
            lat_a, lon_a = ann["pos"]
            d_lon, d_lat = ann.get("text_offset", (0.0, 0.8))

            if ann["interpolate"] and _FMT_RE.search(ann["text_base"]):
                val = _interp_field_value(lat, lon, field, ann["pos"])
                try:
                    text = ann["text_base"] % val
                except (TypeError, ValueError):
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

    def _draw_field(
        self,
        fig:      plt.Figure,
        ax:       plt.Axes,
        lat,
        lon,
        field,
        time_val,
        central:  tuple[float, float],
    ) -> None:
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

        # ── axis titles ───────────────────────────────────────────────────────
        if self._title_template is not None:
            date_str   = _format_date(time_val, self._title_date_style)
            main_title = self._title_template.replace("%S", date_str)
            _title(ax, main_title, scale=scale)
        else:
            _title(ax, self._plot_title, _run_label(time_val), scale=scale)

        # ── figure-level overlays ─────────────────────────────────────────────
        # NearsidePerspective fills the figure squarely (like OrthoAnimator)
        # so figure coordinates work correctly for the info box and credit.
        _, cycle     = _gfs_meta(self._ds, self._var)
        date_str_box = self._ds["time"][0].dt.strftime("%Y-%m-%d").item()
        _draw_info_box(fig, self._var, cycle, date_str_box, scale=scale)
        _draw_data_credit(fig, scale=scale)

        # Author label is drawn after tight_layout() in _render_frame / plot()
        # so its position is computed from the finalised colorbar bounding box.

    def _render_frame(
        self,
        tidx:    int,
        fpath:   str,
        central: tuple[float, float],
    ) -> None:
        lat, lon, field, time_val = self._get(tidx)
        fig, ax = self._build_axes(central)
        self._draw_field(fig, ax, lat, lon, field, time_val, central)
        fig.tight_layout()
        # Draw author AFTER tight_layout so the colorbar bbox is finalised.
        if self._author:
            _author_above_cbar(fig, self._author,
                               scale=_font_scale(self._dpi),
                               kw=self._author_kwargs)
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

    def _print_render_info(self, n_frames: int, stop: int) -> None:
        w, h   = self._figsize
        px_w   = int(w * self._dpi)
        px_h   = int(h * self._dpi)
        h_km   = self._height / 1000.0
        r_deg  = _visible_radius_deg(self._height)
        rot    = (
            f"rotation: ({self._lon_start:.1f},{self._lat_start:.1f}) → "
            f"({self._lon_end:.1f},{self._lat_end:.1f})  stop={stop}"
            if self._lon_start is not None
            else f"static: lon={self._lon:.1f}  lat={self._lat:.1f}"
        )
        print(
            f"Render : {n_frames} frames  |  {px_w}×{px_h} px  |  "
            f"{self._dpi} dpi  |  {self._fps} fps  |  "
            f"codec={self._codec}  quality={self._video_quality}  "
            f"annotations={len(self._annotations)}\n"
            f"Camera : height={h_km:,.0f} km  visible_radius≈{r_deg:.1f}°  "
            f"{rot}\n"
            f"Output : {self._output}"
        )

    # ── public entry points ───────────────────────────────────────────────────

    def plot(
        self,
        time_idx: int = 0,
        central:  tuple[float, float] | None = None,
        save:     str | None = None,
        show:     bool = True,
    ) -> "NearsidePerspectiveAnimator":
        """
        Render a single static frame.

        Parameters
        ----------
        time_idx : int
            Time index (default 0 = first step).
        central : (lon, lat), optional
            Override the sub-satellite point for this plot only.
        save : str, optional
            File path to save the PNG.  If ``None``, ``plt.show()`` is called.
        show : bool
            Call ``plt.show()`` after saving (default ``True``).

        Examples
        --------
        ::

            anim.plot(time_idx=6)
            anim.plot(time_idx=0, save="snapshot.png")
            anim.plot(central=(-75.0, 0.0))    # GOES-West position, first frame
        """
        cam = central if central is not None else (self._lon, self._lat)
        lat, lon, field, time_val = self._get(time_idx)
        fig, ax = self._build_axes(cam)
        self._draw_field(fig, ax, lat, lon, field, time_val, cam)
        fig.tight_layout()
        if self._author:
            _author_above_cbar(fig, self._author,
                               scale=_font_scale(self._dpi),
                               kw=self._author_kwargs)
        if save:
            fig.savefig(save, dpi=self._dpi)
            w, h = self._figsize
            print(
                f"Saved: {save}  "
                f"({int(w * self._dpi)}×{int(h * self._dpi)} px @ {self._dpi} dpi)"
            )
            plt.close(fig)
        if show:
            plt.show()
        return self

    def animate(self) -> "NearsidePerspectiveAnimator":
        """
        Render all frames to disk, then assemble the video.

        Missing frames are rendered; existing frames are reused (cache-friendly
        restart after interruption).
        """
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir     = _frames_dir(f"ns_{self._var}", run_date, cycle)
        n_frames = len(self._ds[self._var].time)
        stop     = self._resolve_stop_frame(n_frames)

        self._print_render_info(n_frames, stop)

        for tidx in range(n_frames):
            fpath   = _frame_path(fdir, tidx)
            central = self._camera_at(tidx, stop)

            if not os.path.exists(fpath):
                self._render_frame(tidx, fpath, central)

            print(f"  frame {tidx + 1}/{n_frames}  →  {fpath}", end="\r")

        print()
        self._write_video(fdir, n_frames)
        print(f"Saved: {self._output}")
        return self