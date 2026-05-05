# mypy: disable-error-code=attr-defined

"""
noaawc.projections.animators
============================
Unified module for all GFS weather-map animators.

Provides four projection-based animator classes that share a common dark-theme
design language, variable presets, quality presets, annotation system, and
author-label API:

    OrthoAnimator               — Orthographic (globe) projection
    NearsidePerspectiveAnimator — Satellite / nearside perspective projection
    PlateCarreeAnimator         — Equirectangular (flat) projection
    RobinsonAnimator            — Robinson pseudo-cylindrical world projection

All classes are importable directly from this module:

    from noaawc.projections.animators import (
        OrthoAnimator,
        NearsidePerspectiveAnimator,
        PlateCarreeAnimator,
        RobinsonAnimator,
    )

See README_animators.md for full documentation and usage examples.
"""

from __future__ import annotations

import copy
import os
import re
from datetime import datetime, timezone
from typing import Any

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import imageio
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.colors import BoundaryNorm

from noaawc.variables import VARIABLE_PRESETS, VARIABLES_INFO, NO_CONTOUR_VARS


# ══════════════════════════════════════════════════════════════════════════════
# Quality presets
# ══════════════════════════════════════════════════════════════════════════════

#: Square quality presets — used by OrthoAnimator and NearsidePerspectiveAnimator.
QUALITY_PRESETS_SQUARE: dict[str, dict[str, Any]] = {
    "sd": {
        "dpi": 72,
        "figsize": (8.0, 8.0),
        "fps": 6,
        "codec": "libx264",
        "quality": 6,
        "description": "Standard Definition — fast render, small file",
    },
    "hd": {
        "dpi": 120,
        "figsize": (10.0, 10.0),
        "fps": 24,
        "codec": "libx264",
        "quality": 8,
        "description": "Full HD (1080p-range) — balanced quality and speed",
    },
    "4k": {
        "dpi": 220,
        "figsize": (17.07, 17.07),
        "fps": 30,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K — maximum quality, large file and slow render",
    },
    "4k_60": {
        "dpi": 220,
        "figsize": (17.07, 17.07),
        "fps": 60,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K @ 60 fps — silky smooth, very large file",
    },
}

#: 16:9 quality presets — used by PlateCarreeAnimator and RobinsonAnimator.
QUALITY_PRESETS_WIDE: dict[str, dict[str, Any]] = {
    "sd": {
        "dpi": 72,
        "figsize": (17.7778, 10.0000),
        "fps": 6,
        "codec": "libx264",
        "quality": 6,
        "description": "SD 720p 16:9 — fast render, small file",
    },
    "hd": {
        "dpi": 120,
        "figsize": (16.0000, 9.0000),
        "fps": 24,
        "codec": "libx264",
        "quality": 8,
        "description": "Full HD 1080p 16:9 — balanced quality and speed",
    },
    "4k": {
        "dpi": 220,
        "figsize": (17.4545, 9.8182),
        "fps": 30,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K 16:9 — maximum quality, large file",
    },
    "4k_60": {
        "dpi": 220,
        "figsize": (17.4545, 9.8182),
        "fps": 60,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K 16:9 @ 60 fps — silky smooth, very large file",
    },
}

# Backward-compatible alias — OrthoAnimator used to export QUALITY_PRESETS.
QUALITY_PRESETS = QUALITY_PRESETS_SQUARE




# ── Raw field accessor with convert + mask_below (shared by all animators) ────
# FIX: previously only NearsidePerspectiveAnimator applied the variable preset's
# "convert" and "mask_below" transforms. The other three animators used the bare
# _get_field() helper which skipped both, causing values to fall outside the
# colormap levels and rendering as a blank/white map. All animators now use this
# unified _get_field_full() that mirrors the Nearside behaviour.

def _get_field_full(ds, var: str, time_idx: int, step: int = 1):
    """Return (lats, lons, data, time_val) with convert + mask_below applied."""
    da   = ds[var][time_idx]
    lats = da.latitude.values[::step]
    lons = da.longitude.values[::step]
    data = da.values[::step, ::step]
    time = da.time.values

    preset = VARIABLE_PRESETS.get(var, {})

    convert = preset.get("convert", None)
    if convert is not None:
        data = convert(data)

    mask_below = preset.get("mask_below", None)
    if mask_below is not None:
        data = np.where(data < mask_below, np.nan, data)

    return lats, lons, data, time


# ══════════════════════════════════════════════════════════════════════════════
# Matplotlib dark-theme defaults
# ══════════════════════════════════════════════════════════════════════════════

plt.rcParams.update(
    {
        "figure.facecolor": "#0d1117",
        "axes.facecolor": "#0d1117",
        "text.color": "#e6edf3",
        "axes.labelcolor": "#e6edf3",
        "xtick.color": "#8b949e",
        "ytick.color": "#8b949e",
        "font.family": "monospace",
        "axes.titlepad": 10,
    }
)


# ══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════════════════════

def _remove_contours(ax: plt.Axes) -> None:
    """Remove all contour line collections from an axes (used as a fallback
    when cartopy raises TypeError during deferred path reprojection at draw
    time — e.g. GeometryCollection on nearside disk boundaries).

    Note: LineCollection moved from matplotlib.contour to matplotlib.collections
    in matplotlib >= 3.8; always import from the canonical location.
    """
    from matplotlib.collections import LineCollection
    for coll in list(ax.collections):
        if isinstance(coll, LineCollection):
            coll.remove()

def list_quality_presets(wide: bool = False) -> None:
    """Print all available quality presets and their settings.

    Parameters
    ----------
    wide : bool
        ``True``  → print the 16:9 presets (PlateCarree / Robinson).
        ``False`` → print the square presets (Ortho / Nearside) — default.
    """
    presets = QUALITY_PRESETS_WIDE if wide else QUALITY_PRESETS_SQUARE
    label = "16:9 wide" if wide else "square"
    print(f"\n  Quality presets ({label})\n")
    print(f"  {'Preset':<10}  {'DPI':<5}  {'Figsize (in)':<20}  {'FPS':<5}  {'Codec':<10}  Description")
    print("  " + "─" * 100)
    for name, p in presets.items():
        w, h = p["figsize"]
        px_w = int(w * p["dpi"])
        px_h = int(h * p["dpi"])
        print(
            f"  {name:<10}  {p['dpi']:<5}  {w:.1f}×{h:.1f} ({px_w}×{px_h} px)"
            f"{'':>2}  {p['fps']:<5}  {p['codec']:<10}  {p['description']}"
        )
    print()


def list_variable_presets() -> None:
    """Print all variable presets and their associated colormaps / level ranges."""
    print(f"\n  {'Variable':<14}  {'Cmap':<24}  {'Range (N steps)':<32}  Label")
    print("  " + "─" * 100)
    for key, p in VARIABLE_PRESETS.items():
        lvl = np.asarray(p["levels"])
        lvl_str = f"{lvl[0]:.3g} … {lvl[-1]:.3g}  ({len(lvl)} steps)"
        cmap_name = getattr(p["cmap"], "name", str(p["cmap"]))
        print(f"  {key:<14}  {cmap_name:<24}  {lvl_str:<32}  {p['cbar_label']}")
    print()


# ── Month name tables per locale ──────────────────────────────────────────────

_MONTHS: dict[str, list[str]] = {
    "en":    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "pt-br": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
               "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
    "es":    ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
    "fr":    ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
               "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"],
}


def _format_date(time_val, date_style: str = "en") -> str:
    """Convert a numpy datetime64 / Python datetime to a human-readable string.

    Output format: ``DD Mon YYYY HH:MM``  (e.g. ``17 Abr 2026 03:00``)
    """
    if hasattr(time_val, "astype"):
        ts = int(time_val.astype("datetime64[s]").astype("int64"))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif isinstance(time_val, datetime):
        dt = time_val
    else:
        dt = datetime.fromtimestamp(float(time_val), tz=timezone.utc)

    months = _MONTHS.get(date_style.lower(), _MONTHS["en"])
    return f"{dt.day:02d} {months[dt.month - 1]} {dt.year} {dt.hour:02d}:{dt.minute:02d}"


def _font_scale(dpi: int, base_dpi: int = 120) -> float:
    """Return a DPI-proportional font scale factor (square-root dampened).

    Reference: 120 dpi → 1.0.  At 220 dpi → ≈ 1.35.  At 72 dpi → ≈ 0.77.
    """
    return (dpi / base_dpi) ** 0.5


def _gfs_meta(ds, var: str) -> tuple[str, str]:
    """Return ``(run_date_str, cycle_str)`` from dataset attributes."""
    return str(ds.attrs.get("run_date", "unknown")), str(ds.attrs.get("cycle", "00z"))


def _frames_dir(var: str, run_date: str, cycle: str) -> str:
    path = os.path.join("frames", f"{var}_{run_date}_{cycle}")
    os.makedirs(path, exist_ok=True)
    return path


def _frame_path(fdir: str, tidx: int) -> str:
    return os.path.join(fdir, f"frame_{tidx:04d}.png")


def _interp_field_value(lat_arr, lon_arr, field, pos: tuple) -> float:
    """Return the field value at the grid point nearest to ``pos=(lat, lon)``."""
    lat_target, lon_target = pos
    i = int(np.argmin(np.abs(lat_arr - lat_target)))
    j = int(np.argmin(np.abs(lon_arr - lon_target)))
    return float(field[i, j])


def _run_label(time_val) -> str:
    return f"GFS — {time_val}"


# ── Geographic reference lines ─────────────────────────────────────────────────

_REF_LATITUDES = {
    "equator":          {"lat":   0.0, "color": "#1e4a75", "lw_factor": 1.4, "ls": "-",  "alpha": 0.70},
    "tropic_cancer":    {"lat":  23.5, "color": "#7a5510", "lw_factor": 0.9, "ls": "--", "alpha": 0.60},
    "tropic_capricorn": {"lat": -23.5, "color": "#7a5510", "lw_factor": 0.9, "ls": "--", "alpha": 0.60},
    "arctic":           {"lat":  66.5, "color": "#2a5a6b", "lw_factor": 0.8, "ls": ":",  "alpha": 0.55},
    "antarctic":        {"lat": -66.5, "color": "#2a5a6b", "lw_factor": 0.8, "ls": ":",  "alpha": 0.55},
}

_REF_LONGITUDES = {
    "prime":     {"lon":   0.0, "color": "#3a3f45", "lw_factor": 1.1, "ls": "-",  "alpha": 0.55},
    "date_line": {"lon": 180.0, "color": "#2e3338", "lw_factor": 0.9, "ls": "--", "alpha": 0.45},
    "w90":       {"lon": -90.0, "color": "#1f2328", "lw_factor": 0.7, "ls": "--", "alpha": 0.35},
    "e90":       {"lon":  90.0, "color": "#1f2328", "lw_factor": 0.7, "ls": "--", "alpha": 0.35},
}


def _add_reference_lines(ax: plt.Axes, lw: float = 0.4) -> None:
    """Draw key geographic reference lines (Equator, Tropics, Prime Meridian, etc.)."""
    transform  = ccrs.PlateCarree()
    lon_range  = np.linspace(-180, 180, 361)
    lat_range  = np.linspace(-90, 90, 181)

    for cfg in _REF_LATITUDES.values():
        ax.plot(lon_range, np.full_like(lon_range, cfg["lat"]),
                transform=transform, color=cfg["color"],
                linewidth=lw * cfg["lw_factor"], linestyle=cfg["ls"],
                alpha=cfg["alpha"], zorder=2)

    for cfg in _REF_LONGITUDES.values():
        ax.plot(np.full_like(lat_range, cfg["lon"]), lat_range,
                transform=transform, color=cfg["color"],
                linewidth=lw * cfg["lw_factor"], linestyle=cfg["ls"],
                alpha=cfg["alpha"], zorder=2)


# ── Shared map-feature helpers ────────────────────────────────────────────────

def _add_features(
    ax: plt.Axes,
    lw: float = 0.4,
    show_states: bool = False,
    show_ocean: bool = False,
) -> None:
    """Add standard cartographic features (land, coast, borders, optional states/ocean)."""
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


# ── Figure-level overlay helpers ───────────────────────────────────────────────

def _colorbar(
    fig: plt.Figure,
    cf,
    ax: plt.Axes,
    label: str,
    orientation: str = "horizontal",
    scale: float = 1.0,
) -> None:
    """Draw a styled colorbar below the axes."""
    cb = fig.colorbar(cf, ax=ax, orientation=orientation, pad=0.03,
                      fraction=0.03, shrink=0.85)
    cb.set_label(label, fontsize=round(8 * scale, 1), color="#8b949e")
    cb.ax.tick_params(labelsize=round(7 * scale, 1), colors="#8b949e")
    cb.outline.set_edgecolor("#30363d")


def _title(ax: plt.Axes, main: str, sub: str = "", scale: float = 1.0) -> None:
    """Set the left (main) and right (subtitle) axis titles."""
    ax.set_title(main, fontsize=round(10 * scale, 1), fontweight="bold",
                 color="#e6edf3", loc="left", pad=6 * scale)
    if sub:
        ax.set_title(sub, fontsize=round(7 * scale, 1), color="#8b949e",
                     loc="right", pad=6 * scale)


# Vertical position constant — approximate top of horizontal colorbar area.
_CBAR_BOTTOM_Y: float = 0.10


def _draw_info_box(
    fig: plt.Figure,
    var_key: str,
    cycle: str,
    date_str: str,
    scale: float = 1.0,
    ax: plt.Axes | None = None,
    x: float = 0.985,
    y: float = 0.985,
) -> None:
    """Draw the variable / cycle / date overlay box.

    Pass ``ax`` for flat projections (anchors to axes frame);
    omit for globe projections (uses figure coordinates).
    """
    lines = [
        f"key: {var_key} - {VARIABLES_INFO.get(var_key, {}).get('long_name', var_key)}",
        f"Date Cycle: {date_str} {cycle}",
    ]
    props = dict(
        ha="right", va="top",
        fontsize=round(7.5 * scale, 1), color="#828283",
        fontweight="bold", fontfamily="monospace", linespacing=1.55,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#161b22",
                  edgecolor="#30363d", linewidth=0.8 * scale, alpha=0.88),
        zorder=10,
    )
    text = "\n".join(lines)
    if ax is not None:
        ax.text(0.995, 0.995, text, transform=ax.transAxes, **props)
    else:
        fig.text(x, y, text, **props)


def _draw_data_credit(
    fig: plt.Figure,
    scale: float = 1.0,
    ax: plt.Axes | None = None,
) -> None:
    """Draw the bottom-right data-source credit ('GFS 0.25° / NASA · NOAA')."""
    props = dict(
        ha="right", va="bottom",
        fontsize=round(6.5 * scale, 1), color="#8b949e",
        fontweight="bold", fontfamily="monospace", linespacing=1.45, zorder=10,
    )
    if ax is not None:
        ax.text(0.995, 0.008, "GFS 0.25°\nNASA / NOAA",
                transform=ax.transAxes, **props)
    else:
        fig.text(0.985, 0.012, "GFS 0.25°\nNASA / NOAA", **props)


def _draw_author(
    fig: plt.Figure,
    author: str,
    scale: float = 1.0,
    x: float | None = 0.4966,
    y: float | None = 0.1,
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
) -> None:
    """Draw the author name in the gap between the figure bottom and the colorbar."""
    x_pos: float = x if x is not None else 0.5

    if y is not None:
        y_pos = y
    else:
        fig_height_px: float = fig.get_figheight() * fig.dpi
        font_height_fig: float = (fontsize * scale * 1.4) / fig_height_px
        y_pos = (_CBAR_BOTTOM_Y / 2.0 + 0.005) + font_height_fig * 0.5

    bbox_props = None
    if bbox:
        bbox_props = dict(
            boxstyle=f"round,pad={bbox_pad}",
            facecolor=bbox_facecolor,
            edgecolor=bbox_edgecolor,
            linewidth=0.8 * scale,
            alpha=bbox_alpha,
        )

    fig.text(
        x_pos, y_pos, author,
        ha=ha, va=va,
        fontsize=round(fontsize * scale, 1),
        color=color, fontweight=fontweight, fontfamily=fontfamily,
        alpha=alpha, bbox=bbox_props, zorder=10,
    )


def _author_above_cbar(
    fig: plt.Figure,
    text: str,
    scale: float = 1.0,
    kw: dict | None = None,
) -> None:
    """Draw the author label just above the horizontal colorbar.

    Must be called **after** ``fig.tight_layout()`` so colorbar bbox is final.
    Used by NearsidePerspectiveAnimator.
    """
    if kw is None:
        kw = {}

    cbar_top = None
    renderer = fig.canvas.get_renderer()
    for child_ax in fig.axes:
        bb = child_ax.get_window_extent(renderer=renderer)
        fig_w_px = fig.get_figwidth() * fig.dpi
        fig_h_px = fig.get_figheight() * fig.dpi
        w_frac = bb.width / fig_w_px
        h_frac = bb.height / fig_h_px
        if w_frac > 0.3 and h_frac < 0.08:
            top_frac = (bb.y0 + bb.height) / fig_h_px
            if cbar_top is None or top_frac > cbar_top:
                cbar_top = top_frac

    if cbar_top is None:
        cbar_top = 0.06

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


# ── Raw field accessor ─────────────────────────────────────────────────────────

def _get_field(ds, var: str, time_idx: int = 0, step: int = 1):
    """Return ``(lats, lons, data, time_val)`` for the given dataset slice."""
    da = ds[var][time_idx]
    return (
        da.latitude.values[::step],
        da.longitude.values[::step],
        da.values[::step, ::step],
        da.time.values,
    )


# ── Annotation drawing (shared implementation) ────────────────────────────────

_FMT_RE = re.compile(r'%[-+0-9*.]*[diouxXeEfFgGcrs]')


def _draw_annotations_on(ax: plt.Axes, lat, lon, field, annotations: list[dict],
                          dpi: int) -> None:
    """Render all registered annotations onto *ax*."""
    if not annotations:
        return
    scale = _font_scale(dpi)
    for ann in annotations:
        lat_a, lon_a = ann["pos"]
        d_lon, d_lat = ann.get("text_offset", (0.0, 0.8))

        if ann["interpolate"] and _FMT_RE.search(ann["text_base"]):
            val = _interp_field_value(lat, lon, field, ann["pos"])
            if np.isnan(val):
                val = 0.0
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
                lon_a, lat_a, marker=mk,
                markersize=ann.get("marker_size", 6.0) * scale,
                color=mk_color,
                markeredgecolor=ann.get("marker_edge_color", "#0d1117"),
                markeredgewidth=ann.get("marker_edge_width", 0.8) * scale,
                alpha=ann.get("marker_alpha", 1.0),
                transform=ccrs.PlateCarree(),
                zorder=ann["zorder"], linestyle="none",
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
            color=ann["color"], fontweight=ann["weight"],
            alpha=ann["alpha"], bbox=bbox_props,
            ha="center", va="center", zorder=ann["zorder"],
        )


# ── Shared setter mixin ────────────────────────────────────────────────────────

class _AnimatorBase:
    """
    Internal mixin that implements all setters shared across the four animators.

    Subclasses must define:
        _QUALITY_PRESETS : dict   — the preset table to use (square or wide)
        _OUTPUT_DEFAULT  : str
        _FPS_DEFAULT     : int
        _STEP_DEFAULT    : int
        _DPI_DEFAULT     : int
        _FIGSIZE_DEFAULT : tuple[float, float]
        _CODEC_DEFAULT   : str
        _VIDEO_QUALITY_DEFAULT : int

    And must call ``_base_init(ds, var)`` from their ``__init__``.
    """

    _QUALITY_PRESETS: dict = QUALITY_PRESETS_SQUARE   # override in subclass

    # ── initialisation ────────────────────────────────────────────────────────

    def _base_init(self, ds, var: str) -> None:
        self._ds  = ds
        self._var = var

        self._output        = self._OUTPUT_DEFAULT          # type: ignore[attr-defined]
        self._fps           = self._FPS_DEFAULT             # type: ignore[attr-defined]
        self._step          = self._STEP_DEFAULT            # type: ignore[attr-defined]
        self._dpi           = self._DPI_DEFAULT             # type: ignore[attr-defined]
        self._figsize: tuple[float, float] = self._FIGSIZE_DEFAULT  # type: ignore[attr-defined]
        self._codec         = self._CODEC_DEFAULT           # type: ignore[attr-defined]
        self._video_quality = self._VIDEO_QUALITY_DEFAULT   # type: ignore[attr-defined]

        self._annotations: list[dict] = []
        self._title_template: str | None = None
        self._title_date_style: str = "en"
        self._show_states: bool = False
        self._author: str = ""
        self._author_kwargs: dict[str, Any] = {}

        self._apply_variable_preset(var, silent=False)

    # ── variable preset ───────────────────────────────────────────────────────

    def _apply_variable_preset(self, var: str, silent: bool = True) -> None:
        if var in VARIABLE_PRESETS:
            p = VARIABLE_PRESETS[var]
            if not silent:
                print(f"[{self.__class__.__name__}] Variable preset '{var}': {p['plot_title']}")
        else:
            p = VARIABLE_PRESETS["t2m"]
            print(
                f"[{self.__class__.__name__}] No preset for '{var}' — "
                f"falling back to temperature defaults."
            )
        self._cmap       = p["cmap"]
        self._levels     = np.asarray(p["levels"])
        self._cbar_label = p["cbar_label"]
        self._plot_title = p["plot_title"]

    def use_variable_defaults(self, var: str | None = None):
        """Apply the plotting preset for *var* (or the instance variable if omitted)."""
        self._apply_variable_preset(var if var is not None else self._var, silent=False)
        return self

    # ── output setters ────────────────────────────────────────────────────────

    def set_output(self, path: str):
        """Output file path (.mp4 or .gif)."""
        self._output = path
        return self

    def set_fps(self, fps: int):
        """Frames per second for the output video."""
        self._fps = fps
        return self

    def set_step(self, step: int):
        """Spatial decimation factor (1 = no decimation)."""
        self._step = step
        return self

    def set_dpi(self, dpi: int):
        """Figure resolution in dots per inch."""
        self._dpi = dpi
        return self

    def set_figsize(self, w: float, h: float):
        """Figure size in inches (width, height)."""
        self._figsize = (w, h)
        return self

    def set_codec(self, codec: str):
        """Video codec (libx264, libx265, vp9, prores)."""
        self._codec = codec
        return self

    def set_video_quality(self, quality: int):
        """Encoding quality 0–10 (higher = better / larger file)."""
        if not 0 <= quality <= 10:
            raise ValueError("quality must be between 0 and 10.")
        self._video_quality = quality
        return self

    def set_quality(self, preset: str):
        """Apply a named quality preset (sd, hd, 4k, 4k_60)."""
        if preset not in self._QUALITY_PRESETS:
            opts = ", ".join(f'"{k}"' for k in self._QUALITY_PRESETS)
            raise ValueError(f"Unknown preset '{preset}'. Choose from: {opts}")
        p = self._QUALITY_PRESETS[preset]
        self._dpi           = p["dpi"]
        self._figsize       = p["figsize"]
        self._fps           = p["fps"]
        self._codec         = p["codec"]
        self._video_quality = p["quality"]
        print(f"Quality preset '{preset}': {p['description']}")
        return self

    # ── colormap / levels setters ─────────────────────────────────────────────

    def set_cmap(self, cmap):
        """Override the colormap (name string or matplotlib colormap object)."""
        self._cmap = plt.get_cmap(cmap) if isinstance(cmap, str) else cmap
        return self

    def set_levels(self, levels):
        """Override the BoundaryNorm levels."""
        self._levels = np.asarray(levels)
        return self

    def set_cbar_label(self, label: str):
        """Label shown on the colorbar."""
        self._cbar_label = label
        return self

    def set_plot_title(self, title: str):
        """Static left-side title shown on each frame."""
        self._plot_title = title
        return self

    def set_title(self, template: str, date_style: str = "en"):
        """Dynamic per-frame title — use ``%S`` as the date placeholder.

        Supported ``date_style`` values: ``"en"``, ``"pt-br"``, ``"es"``, ``"fr"``.
        """
        self._title_template   = template if template else None
        self._title_date_style = date_style
        return self

    # ── feature setters ───────────────────────────────────────────────────────

    def set_states(self, visible: bool = True):
        """Show / hide state/province boundary lines (default: off)."""
        self._show_states = visible
        return self

    # ── author label setters ──────────────────────────────────────────────────

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
    ):
        """Set the author / credit label displayed on every frame.

        Pass ``""`` to disable.
        """
        self._author = name.strip()
        if not x or not y:
            x, y = 0.4967, 0.1
        self._author_kwargs = dict(
            x=x, y=y, ha=ha, va=va,
            color=color, fontsize=fontsize,
            fontweight=fontweight, fontfamily=fontfamily,
            alpha=alpha, bbox=bbox,
            bbox_facecolor=bbox_facecolor, bbox_edgecolor=bbox_edgecolor,
            bbox_alpha=bbox_alpha, bbox_pad=bbox_pad,
        )
        return self

    # ── annotation setters ────────────────────────────────────────────────────

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
    ):
        """Add a city-label / value annotation overlaid on every frame.

        Use ``%d`` / ``%.1f`` as a placeholder for the field value at ``pos``.
        ``pos`` is ``(lat, lon)`` in decimal degrees.
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

    def clear_annotations(self):
        """Remove all registered annotations."""
        self._annotations.clear()
        return self

    # ── named-variable convenience shortcuts ──────────────────────────────────

    def use_temperature_defaults(self):
        return self.use_variable_defaults("t2m")

    def use_pressure_defaults(self):
        return self.use_variable_defaults("prmsl")

    def use_precipitation_defaults(self):
        return self.use_variable_defaults("prate")

    def use_humidity_defaults(self):
        return self.use_variable_defaults("r2")

    def use_wind_speed_defaults(self):
        return self.use_variable_defaults("wspd10")

    # ── internal video writer ─────────────────────────────────────────────────

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

    # ── title rendering helper ────────────────────────────────────────────────

    def _resolve_title(self, ax: plt.Axes, time_val, scale: float) -> None:
        """Render the left axis title (static or dynamic)."""
        if self._title_template is not None:
            date_str = _format_date(time_val, self._title_date_style)
            main_title = self._title_template.replace("%S", date_str)
            _title(ax, main_title, scale=scale)
        else:
            _title(ax, self._plot_title, _run_label(time_val), scale=scale)


# ══════════════════════════════════════════════════════════════════════════════
# OrthoAnimator
# ══════════════════════════════════════════════════════════════════════════════

class OrthoAnimator(_AnimatorBase):
    """Renders an animated weather map using the Orthographic (globe) projection.

    The camera is conceptually at infinite distance, so the globe appears with
    no perspective foreshortening.  Use :class:`NearsidePerspectiveAnimator`
    if you want a physically realistic satellite view with a curved limb.

    Quick start
    -----------
    ::

        anim = OrthoAnimator(ds, "t2m")
        anim.set_output("output.mp4")
        anim.set_rotation(lon_start=-90, lon_end=-20, lat_start=-5, lat_end=-20)
        anim.set_rotation_stop(fraction=0.65)
        anim.animate()

    Camera rotation
    ---------------
    ::

        anim.set_rotation(lon_start=-90, lon_end=-20,
                          lat_start=-5,  lat_end=-20)
        anim.set_rotation_stop(fraction=0.65)

    Zoom
    ----
    ::

        anim.set_zoom(2)          # Continental scale
        anim.set_zoom(4)          # Regional / sub-continental

    Quality presets
    ---------------
    ::

        anim.set_quality("sd")     #  72 dpi,  8×8 in,   6 fps
        anim.set_quality("hd")     # 120 dpi, 10×10 in, 24 fps
        anim.set_quality("4k")     # 220 dpi, 17×17 in, 30 fps

    Static snapshot
    ---------------
    ::

        anim.plot(time_idx=0, save="snapshot.png")
    """

    _QUALITY_PRESETS   = QUALITY_PRESETS_SQUARE
    _OUTPUT_DEFAULT    = "output_ortho.mp4"
    _FPS_DEFAULT       = 6
    _STEP_DEFAULT      = 1
    _DPI_DEFAULT       = 120
    _FIGSIZE_DEFAULT   = (8.0, 8.0)
    _CODEC_DEFAULT     = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8

    def __init__(
        self,
        ds,
        var: str,
        central_point: tuple[float, float] = (-45.0, -15.0),
    ):
        self._central_point = (float(central_point[0]), float(central_point[1]))
        self._zoom: float = 1.0
        self._lon_start: float | None = None
        self._lat_start: float | None = None
        self._lon_end:   float | None = None
        self._lat_end:   float | None = None
        self._stop_frame:    int   | None = None
        self._stop_fraction: float | None = None
        self._base_init(ds, var)

    # ── view / rotation ───────────────────────────────────────────────────────

    def set_view(self, lon: float, lat: float, zoom: float | None = None):
        """Set the central point and optional zoom level in one call."""
        self._central_point = (float(lon), float(lat))
        if zoom is not None:
            if zoom < 1:
                raise ValueError("zoom must be >= 1.")
            self._zoom = float(zoom)
        return self

    def set_zoom(self, zoom: float):
        """Zoom into the globe around the central point.

        zoom=1 shows the full hemisphere; zoom=2 → 45° radius, zoom=4 → 22.5°, etc.
        """
        if zoom < 1:
            raise ValueError("zoom must be >= 1.")
        self._zoom = float(zoom)
        return self

    def set_rotation(
        self,
        lon_start: float,
        lon_end:   float,
        lat_start: float | None = None,
        lat_end:   float | None = None,
    ):
        """Define the camera arc from (lon_start, lat_start) to (lon_end, lat_end)."""
        self._lon_start = lon_start
        self._lon_end   = lon_end
        self._lat_start = lat_start if lat_start is not None else self._central_point[1]
        self._lat_end   = lat_end   if lat_end   is not None else self._central_point[1]
        return self

    def set_rotation_stop(
        self,
        frame: int | None = None,
        fraction: float | None = None,
    ):
        """Frame index at which rotation ends and camera freezes."""
        if frame is not None and fraction is not None:
            raise ValueError("Provide 'frame' or 'fraction', not both.")
        if fraction is not None:
            if not 0.0 < fraction < 1.0:
                raise ValueError("fraction must be strictly between 0 and 1.")
            self._stop_fraction = fraction
            self._stop_frame    = None
        else:
            self._stop_frame    = frame
            self._stop_fraction = None
        return self

    # ── internal ──────────────────────────────────────────────────────────────

    def _resolve_stop_frame(self, n: int) -> int:
        if self._stop_fraction is not None:
            return max(1, int(round(self._stop_fraction * n)))
        return self._stop_frame if self._stop_frame is not None else n

    def _rotation_at(self, tidx: int, stop: int) -> tuple[float, float]:
        if self._lon_start is None:
            return self._central_point
        if tidx >= stop:
            return (self._lon_end, self._lat_end)   # type: ignore[return-value]
        t = tidx / stop
        lon = self._lon_start + t * (self._lon_end - self._lon_start)  # type: ignore[operator]
        lat = self._lat_start + t * (self._lat_end - self._lat_start)  # type: ignore[operator]
        return (lon, lat)

    def _build_axes(self, central: tuple) -> tuple[plt.Figure, plt.Axes]:
        proj  = ccrs.Orthographic(*central)
        scale = _font_scale(self._dpi)
        fig, ax = plt.subplots(
            figsize=self._figsize,
            subplot_kw={"projection": proj},
            facecolor="#0d1117",
            dpi=self._dpi,
        )
        ax.set_global()
        if self._zoom > 1.0:
            lon_c, lat_c = central
            r = 90.0 / self._zoom
            ax.set_extent([lon_c - r, lon_c + r, lat_c - r, lat_c + r],
                          crs=ccrs.PlateCarree())
        _add_features(ax, lw=0.5 * scale, show_states=self._show_states)
        return fig, ax

    def _draw_field(self, fig, ax, lat, lon, field, time_val) -> None:
        scale = _font_scale(self._dpi)
        norm  = BoundaryNorm(self._levels, ncolors=self._cmap.N, clip=True)

        cf = ax.pcolormesh(lon, lat, field, cmap=self._cmap, norm=norm,
                           transform=ccrs.PlateCarree(), zorder=1)
        ax.contour(lon[::3], lat[::3], field[::3, ::3],
                   levels=self._levels[::5], colors="white",
                   linewidths=0.25 * scale, alpha=0.4,
                   transform=ccrs.PlateCarree(), zorder=2)

        _draw_annotations_on(ax, lat, lon, field, self._annotations, self._dpi)
        _colorbar(fig, cf, ax, self._cbar_label, scale=scale)
        self._resolve_title(ax, time_val, scale)

        _, cycle     = _gfs_meta(self._ds, self._var)
        date_str_box = self._ds["time"][0].dt.strftime("%Y-%m-%d").item()
        _draw_info_box(fig, self._var, cycle, date_str_box, scale=scale)
        _draw_data_credit(fig, scale=scale)

        if self._author:
            _draw_author(fig, self._author, scale=scale, **self._author_kwargs)

    def _render_frame(self, tidx: int, fpath: str, central: tuple) -> None:
        lat, lon, field, time_val = _get_field(self._ds, self._var, tidx, self._step)
        fig, ax = self._build_axes(central)
        self._draw_field(fig, ax, lat, lon, field, time_val)
        fig.tight_layout()
        fig.savefig(fpath, format="png", dpi=self._dpi)
        plt.close(fig)

    # ── public API ────────────────────────────────────────────────────────────

    def plot(
        self,
        time_idx: int = 0,
        central_point: tuple | None = None,
        save: str | None = None,
        show: bool = True,
    ) -> "OrthoAnimator":
        """Render a single static frame."""
        centre = central_point if central_point is not None else self._central_point
        lat, lon, field, time_val = _get_field(self._ds, self._var, time_idx, self._step)
        fig, ax = self._build_axes(centre)
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

    def animate(self) -> "OrthoAnimator":
        """Render all frames and assemble the video."""
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir     = _frames_dir(self._var, run_date, cycle)
        n_frames = len(self._ds[self._var].time)
        stop     = self._resolve_stop_frame(n_frames)

        w, h = self._figsize
        print(f"[OrthoAnimator] {n_frames} frames | "
              f"{int(w*self._dpi)}×{int(h*self._dpi)} px | "
              f"{self._dpi} dpi | {self._fps} fps | {self._output}")

        for tidx in range(n_frames):
            fpath   = _frame_path(fdir, tidx)
            central = self._rotation_at(tidx, stop)
            if not os.path.exists(fpath):
                self._render_frame(tidx, fpath, central)
            print(f"  frame {tidx+1}/{n_frames}  →  {fpath}", end="\r")

        print()
        self._write_video(fdir, n_frames)
        print(f"Saved: {self._output}")
        return self


# ══════════════════════════════════════════════════════════════════════════════
# NearsidePerspectiveAnimator
# ══════════════════════════════════════════════════════════════════════════════

# Geostationary orbit altitude (GOES-16 / Meteosat / Himawari-9).
GEOSTATIONARY_HEIGHT: float = 35_786_000.0
EARTH_RADIUS: float = 6_371_229.0


def _visible_radius_deg(satellite_height: float) -> float:
    """Return the maximum visible angular radius (degrees) from a given altitude."""
    R, h = EARTH_RADIUS, satellite_height
    return float(np.degrees(np.arccos(R / (R + h)))) - 1.0


class NearsidePerspectiveAnimator(_AnimatorBase):
    """Renders an animated weather map using the Nearside Perspective projection.

    Simulates a camera at a finite altitude above a central geographic point,
    producing a realistic globe with a visible curved horizon — the defining
    visual of actual weather satellite imagery.

    Unlike :class:`OrthoAnimator` (camera at infinity), this animator uses a
    physically meaningful ``satellite_height`` parameter to control the field
    of view and the degree of perspective foreshortening.

    Quick start
    -----------
    ::

        anim = NearsidePerspectiveAnimator(ds, "t2m")
        anim.set_view(lon=-50.0, lat=-15.0)
        anim.set_output("brazil_sat.mp4")
        anim.animate()

    Altitude reference table
    ------------------------
    ==============  ===========================================================
    Height (m)      Description
    ==============  ===========================================================
    200 000         Low Earth Orbit — very tight view, heavy perspective
    3 000 000       Regional satellite — South America fills the disk
    35 786 000      Geostationary orbit (GOES / Meteosat / Himawari) ← default
    100 000 000     High exospheric — near-orthographic
    ==============  ===========================================================

    Camera rotation
    ---------------
    ::

        anim.set_rotation(lon_start=-90, lon_end=-20,
                          lat_start=-5,  lat_end=-20)
        anim.set_rotation_stop(fraction=0.65)
    """

    _QUALITY_PRESETS   = QUALITY_PRESETS_SQUARE
    _OUTPUT_DEFAULT    = "output_nearside.mp4"
    _FPS_DEFAULT       = 6
    _STEP_DEFAULT      = 1
    _DPI_DEFAULT       = 120
    _FIGSIZE_DEFAULT   = (10.0, 10.0)
    _CODEC_DEFAULT     = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8

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
        self._lon:    float = float(lon)
        self._lat:    float = float(lat)
        self._height: float = float(satellite_height)

        self._lon_start:     float | None = None
        self._lat_start:     float | None = None
        self._lon_end:       float | None = None
        self._lat_end:       float | None = None
        self._stop_frame:    int   | None = None
        self._stop_fraction: float | None = None

        self._base_init(ds, var)

    # ── camera control ────────────────────────────────────────────────────────

    def set_view(
        self,
        lon: float,
        lat: float,
        satellite_height: float | None = None,
    ) -> "NearsidePerspectiveAnimator":
        """Set the sub-satellite point and optional altitude."""
        self._lon = float(lon)
        self._lat = float(lat)
        if satellite_height is not None:
            self._height = float(satellite_height)
        return self

    def set_satellite_height(self, height: float) -> "NearsidePerspectiveAnimator":
        """Set the camera altitude above Earth's surface in metres."""
        if height <= 0:
            raise ValueError("satellite_height must be > 0.")
        self._height = float(height)
        return self

    # ── rotation ──────────────────────────────────────────────────────────────

    def set_rotation(
        self,
        lon_start: float,
        lon_end:   float,
        lat_start: float | None = None,
        lat_end:   float | None = None,
    ) -> "NearsidePerspectiveAnimator":
        """Define the camera arc from (lon_start, lat_start) to (lon_end, lat_end)."""
        _LAT_LIMIT = 89.9

        def _safe(v: float, name: str) -> float:
            c = max(-_LAT_LIMIT, min(_LAT_LIMIT, v))
            if abs(c - v) > 0.01:
                print(f"[NearsidePerspectiveAnimator] WARNING: {name}={v:.4f}° "
                      f"clamped to {c:.4f}°.")
            return c

        self._lon_start = float(lon_start)
        self._lon_end   = float(lon_end)
        self._lat_start = _safe(float(lat_start) if lat_start is not None else self._lat, "lat_start")
        self._lat_end   = _safe(float(lat_end)   if lat_end   is not None else self._lat, "lat_end")
        return self

    def set_rotation_stop(
        self,
        frame: int | None = None,
        fraction: float | None = None,
    ) -> "NearsidePerspectiveAnimator":
        """Frame index at which rotation ends and camera freezes."""
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

    # ── internal ──────────────────────────────────────────────────────────────

    def _get(self, time_idx: int):
        da      = self._ds[self._var][time_idx]
        step    = self._step
        lats    = da.latitude.values[::step]
        lons    = da.longitude.values[::step]
        data    = da.values[::step, ::step]
        time    = da.time.values
        convert = VARIABLE_PRESETS.get(self._var, {}).get("convert", None)
        if convert is not None:
            data = convert(data)
        mask_below = VARIABLE_PRESETS.get(self._var, {}).get("mask_below", None)
        if mask_below is not None:
            data = np.where(data < mask_below, np.nan, data)
        return lats, lons, data, time

    def _resolve_stop_frame(self, n: int) -> int:
        if self._stop_fraction is not None:
            return max(1, int(round(self._stop_fraction * n)))
        return self._stop_frame if self._stop_frame is not None else n

    def _camera_at(self, tidx: int, stop: int) -> tuple[float, float]:
        _LAT_LIMIT = 89.9
        if self._lon_start is None:
            return (self._lon, max(-_LAT_LIMIT, min(_LAT_LIMIT, self._lat)))
        if tidx >= stop:
            lon, lat = self._lon_end, self._lat_end  # type: ignore[assignment]
        else:
            t   = tidx / stop
            lon = self._lon_start + t * (self._lon_end - self._lon_start)   # type: ignore[operator]
            lat = self._lat_start + t * (self._lat_end - self._lat_start)   # type: ignore[operator]
        return (float(lon), max(-_LAT_LIMIT, min(_LAT_LIMIT, float(lat))))

    def _build_axes(self, central: tuple) -> tuple[plt.Figure, plt.Axes]:
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
        _add_features(ax, lw=0.5 * scale, show_states=self._show_states)
        return fig, ax

    def _draw_field(self, fig, ax, lat, lon, field, time_val, central) -> None:
        scale = _font_scale(self._dpi)
        cmap  = copy.copy(self._cmap)
        cmap.set_under(alpha=0)
        cmap.set_bad(alpha=0)
        norm = BoundaryNorm(self._levels, ncolors=cmap.N, clip=False)

        cf = ax.pcolormesh(lon, lat, field, cmap=cmap, norm=norm,
                           transform=ccrs.PlateCarree(), zorder=1)

        if self._var not in NO_CONTOUR_VARS:
            # Note: cartopy defers path reprojection to draw time, so the
            # GeometryCollection TypeError does NOT surface here — it fires
            # inside fig.savefig(). The try/except in _render_frame handles it.
            ax.contour(lon[::3], lat[::3], field[::3, ::3],
                       levels=self._levels[::5], colors="white",
                       linewidths=0.25 * scale, alpha=0.4,
                       transform=ccrs.PlateCarree(), zorder=2)

        _draw_annotations_on(ax, lat, lon, field, self._annotations, self._dpi)
        _colorbar(fig, cf, ax, self._cbar_label, scale=scale)
        self._resolve_title(ax, time_val, scale)

        _, cycle     = _gfs_meta(self._ds, self._var)
        date_str_box = self._ds["time"][0].dt.strftime("%Y-%m-%d").item()
        _draw_info_box(fig, self._var, cycle, date_str_box, scale=scale)
        _draw_data_credit(fig, scale=scale)


    def _render_frame(self, tidx: int, fpath: str, central: tuple[float, float]) -> None:
        lat, lon, field, time_val = self._get(tidx)
        fig, ax = self._build_axes(central)
        self._draw_field(fig, ax, lat, lon, field, time_val, central)
        fig.tight_layout()

        # Cartopy defers path reprojection to draw time, so the TypeError from
        # the GeometryCollection / shapely bug surfaces inside savefig(), not
        # inside ax.contour(). Strategy: try to save; on failure strip all
        # contour LineCollections from the axes (which removes the broken
        # deferred transforms) and save again without them.
        try:
            fig.savefig(fpath, format="png", dpi=self._dpi)
        except TypeError:
            from matplotlib.collections import LineCollection
            for coll in list(ax.collections):
                if isinstance(coll, LineCollection):
                    coll.remove()
            fig.savefig(fpath, format="png", dpi=self._dpi)
        finally:
            plt.close(fig)


    # ── public API ────────────────────────────────────────────────────────────

    def plot(
        self,
        time_idx: int = 0,
        central: tuple[float, float] | None = None,
        save: str | None = None,
        show: bool = True,
    ) -> "NearsidePerspectiveAnimator":
        """Render a single static frame."""
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
            print(f"Saved: {save}  ({int(w*self._dpi)}×{int(h*self._dpi)} px @ {self._dpi} dpi)")
            plt.close(fig)
        if show:
            plt.show()
        return self

    def animate(self) -> "NearsidePerspectiveAnimator":
        """Render all frames and assemble the video."""
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir     = _frames_dir(f"ns_{self._var}", run_date, cycle)
        n_frames = len(self._ds[self._var].time)
        stop     = self._resolve_stop_frame(n_frames)

        w, h     = self._figsize
        r_deg    = _visible_radius_deg(self._height)
        print(f"[NearsidePerspectiveAnimator] {n_frames} frames | "
              f"{int(w*self._dpi)}×{int(h*self._dpi)} px | "
              f"height={self._height/1000:.0f} km | visible≈{r_deg:.1f}° | {self._output}")

        for tidx in range(n_frames):
            fpath   = _frame_path(fdir, tidx)
            central = self._camera_at(tidx, stop)
            if not os.path.exists(fpath):
                self._render_frame(tidx, fpath, central)
            print(f"  frame {tidx+1}/{n_frames}  →  {fpath}", end="\r")

        print()
        self._write_video(fdir, n_frames)
        print(f"Saved: {self._output}")
        return self


# ══════════════════════════════════════════════════════════════════════════════
# PlateCarreeAnimator
# ══════════════════════════════════════════════════════════════════════════════

_PC_DEFAULT_REGION = {
    "toplat": 5.0, "bottomlat": -35.0,
    "leftlon": -82.0, "rightlon": -30.0,
}
_PC_LAT_MAX: float = 80.0


def _zoom_to_half_side(zoom: float) -> float:
    if zoom < 1:
        raise ValueError("zoom must be >= 1")
    return 90.0 / zoom


def _region_from_zoom_pc(lat: float, lon: float, zoom: float) -> dict:
    half = _zoom_to_half_side(zoom)
    return {
        "toplat":    min( 85.0, lat + half),
        "bottomlat": max(-85.0, lat - half),
        "leftlon":   lon - half,
        "rightlon":  lon + half,
    }


class PlateCarreeAnimator(_AnimatorBase):
    """Renders an animated weather map using the PlateCarree (equirectangular) projection.

    Flat 2-D map with 16:9 output — better for regional broadcast/streaming
    use-cases than the square globe projections.

    Region definition (required before ``animate()`` / ``plot()``)
    --------------------------------------------------------------
    ::

        anim.set_region("south_america")      # named shortcut
        anim.set_region("brazil")
        anim.set_region("northeast_br")
        anim.set_region("global")

        anim.set_region(toplat=5, bottomlat=-35, leftlon=-75, rightlon=-34)

        anim.set_zoom(zoom=4, pos=(-9.4, -40.5))   # zoom around a point

    Quick start
    -----------
    ::

        anim = PlateCarreeAnimator(ds, "t2m")
        anim.set_region("south_america")
        anim.set_output("sa_temperature.mp4")
        anim.animate()
    """

    _QUALITY_PRESETS   = QUALITY_PRESETS_WIDE
    _OUTPUT_DEFAULT    = "output_plate_carree.mp4"
    _FPS_DEFAULT       = 6
    _STEP_DEFAULT      = 1
    _DPI_DEFAULT       = 120
    _FIGSIZE_DEFAULT   = (16.0, 9.0)
    _CODEC_DEFAULT     = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8

    _NAMED_REGIONS: dict[str, dict] = {
        "south_america": {"toplat":  15.0, "bottomlat": -60.0, "leftlon":  -85.0, "rightlon":  -30.0},
        "brazil":        {"toplat":   6.0, "bottomlat": -34.0, "leftlon":  -75.0, "rightlon":  -28.0},
        "northeast_br":  {"toplat":  -1.0, "bottomlat": -18.0, "leftlon":  -47.0, "rightlon":  -34.0},
        "north_br":      {"toplat":   5.5, "bottomlat":  -5.0, "leftlon":  -74.0, "rightlon":  -44.0},
        "southeast_br":  {"toplat": -14.0, "bottomlat": -25.5, "leftlon":  -53.0, "rightlon":  -39.0},
        "south_br":      {"toplat": -22.0, "bottomlat": -34.0, "leftlon":  -58.0, "rightlon":  -47.0},
        "global":        {"toplat":  85.0, "bottomlat": -85.0, "leftlon": -179.9, "rightlon":  179.9},
    }

    def __init__(self, ds, var: str):
        self._region: dict = dict(_PC_DEFAULT_REGION)
        self._show_ocean: bool = True
        self._show_grid:  bool = True
        self._base_init(ds, var)

    # ── region setters ────────────────────────────────────────────────────────

    def set_region(
        self,
        region: dict | str | None = None,
        *,
        toplat: float | None = None,
        bottomlat: float | None = None,
        leftlon: float | None = None,
        rightlon: float | None = None,
    ) -> "PlateCarreeAnimator":
        """Define the map extent.  Accepts a named shortcut string, a dict, or keyword args."""
        if isinstance(region, str):
            key = region.lower()
            if key not in self._NAMED_REGIONS:
                opts = ", ".join(f'"{k}"' for k in self._NAMED_REGIONS)
                raise ValueError(f"Unknown named region '{region}'. Available: {opts}")
            self._region = dict(self._NAMED_REGIONS[key])
        elif isinstance(region, dict):
            self._region = dict(region)
        else:
            if any(v is None for v in (toplat, bottomlat, leftlon, rightlon)):
                raise ValueError("Provide all four: toplat, bottomlat, leftlon, rightlon.")
            self._region = {"toplat": float(toplat), "bottomlat": float(bottomlat),
                            "leftlon": float(leftlon), "rightlon": float(rightlon)}
        return self

    def set_zoom(self, zoom: float, pos: tuple[float, float]) -> "PlateCarreeAnimator":
        """Define the map extent by zooming into a geographic point ``(lat, lon)``."""
        if zoom < 1:
            raise ValueError("zoom must be >= 1.")
        lat, lon = pos
        self._region = _region_from_zoom_pc(lat, lon, zoom)
        return self

    def set_ocean(self, visible: bool = True) -> "PlateCarreeAnimator":
        """Show / hide the ocean colour fill."""
        self._show_ocean = visible
        return self

    def set_grid(self, visible: bool = True) -> "PlateCarreeAnimator":
        """Show / hide lat/lon gridlines with labels."""
        self._show_grid = visible
        return self

    # ── internal ──────────────────────────────────────────────────────────────

    def _get(self, time_idx: int):
        da   = self._ds[self._var][time_idx]
        step = self._step
        return (da.latitude.values[::step], da.longitude.values[::step],
                da.values[::step, ::step], da.time.values)

    def _build_axes(self) -> tuple[plt.Figure, plt.Axes]:
        r     = self._region
        scale = _font_scale(self._dpi)
        safe_top = max(-_PC_LAT_MAX, min(_PC_LAT_MAX, r["toplat"]))
        safe_bot = max(-_PC_LAT_MAX, min(_PC_LAT_MAX, r["bottomlat"]))

        fig, ax = plt.subplots(
            figsize=self._figsize,
            subplot_kw={"projection": ccrs.PlateCarree()},
            facecolor="#0d1117",
            dpi=self._dpi,
        )
        ax.set_extent([r["leftlon"], r["rightlon"], safe_bot, safe_top],
                      crs=ccrs.PlateCarree())
        _add_features(ax, lw=0.5 * scale, show_states=self._show_states,
                      show_ocean=self._show_ocean)

        if self._show_grid:
            gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True,
                              linewidth=0.3 * scale, color="#14181c",
                              alpha=0.8, linestyle="--", zorder=2)
            gl.top_labels   = False
            gl.right_labels = False
            gl.xlocator = mticker.MultipleLocator(10)
            gl.ylocator = mticker.MultipleLocator(10)
            gl.xlabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}
            gl.ylabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}

        return fig, ax

    def _draw_field(self, fig, ax, lat, lon, field, time_val) -> None:
        scale = _font_scale(self._dpi)
        norm  = BoundaryNorm(self._levels, ncolors=self._cmap.N, clip=True)

        cf = ax.pcolormesh(lon, lat, field, cmap=self._cmap, norm=norm,
                           transform=ccrs.PlateCarree(), zorder=1)
        ax.contour(lon[::3], lat[::3], field[::3, ::3],
                   levels=self._levels[::5], colors="white",
                   linewidths=0.25 * scale, alpha=0.4,
                   transform=ccrs.PlateCarree(), zorder=2)

        _draw_annotations_on(ax, lat, lon, field, self._annotations, self._dpi)
        _colorbar(fig, cf, ax, self._cbar_label, scale=scale)
        self._resolve_title(ax, time_val, scale)

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

    # ── public API ────────────────────────────────────────────────────────────

    def plot(
        self,
        time_idx: int = 0,
        save: str | None = None,
        show: bool = True,
    ) -> "PlateCarreeAnimator":
        """Render a single static frame."""
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
        """Render all frames and assemble the video."""
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir     = _frames_dir(f"pc_{self._var}", run_date, cycle)
        n_frames = len(self._ds[self._var].time)

        r = self._region
        w, h = self._figsize
        print(f"[PlateCarreeAnimator] {n_frames} frames | "
              f"{int(w*self._dpi)}×{int(h*self._dpi)} px | "
              f"lat [{r['bottomlat']:.1f}…{r['toplat']:.1f}] "
              f"lon [{r['leftlon']:.1f}…{r['rightlon']:.1f}] | {self._output}")

        for tidx in range(n_frames):
            fpath = _frame_path(fdir, tidx)
            if not os.path.exists(fpath):
                self._render_frame(tidx, fpath)
            print(f"  frame {tidx+1}/{n_frames}  →  {fpath}", end="\r")

        print()
        self._write_video(fdir, n_frames)
        print(f"Saved: {self._output}")
        return self


# ══════════════════════════════════════════════════════════════════════════════
# RobinsonAnimator
# ══════════════════════════════════════════════════════════════════════════════

_ROB_LAT_MAX: float = 85.0
_ROB_DEFAULT_REGION = {
    "toplat": 85.0, "bottomlat": -85.0,
    "leftlon": -180.0, "rightlon": 180.0,
    "central_longitude": 0.0,
}


def _region_from_zoom_rob(lat: float, lon: float, zoom: float) -> dict:
    half = _zoom_to_half_side(zoom)
    return {
        "toplat":    min( _ROB_LAT_MAX, lat + half),
        "bottomlat": max(-_ROB_LAT_MAX, lat - half),
        "leftlon":   lon - half,
        "rightlon":  lon + half,
        "central_longitude": lon,
    }


class RobinsonAnimator(_AnimatorBase):
    """Renders an animated weather map using the Robinson pseudo-cylindrical projection.

    The Robinson projection minimises both area and shape distortion, making it
    the standard choice for world/global thematic maps.  It is NOT conformal and
    NOT equal-area, but it looks good — used by National Geographic (1988–1998).

    Region definition (required before ``animate()`` / ``plot()``)
    --------------------------------------------------------------
    ::

        anim.set_region("global")
        anim.set_region("north_hemisphere")
        anim.set_region("south_america")
        anim.set_region("africa")
        anim.set_region("europe_asia")
        anim.set_region("north_america")
        anim.set_region("pacific")

        anim.set_region(toplat=85, bottomlat=-85, leftlon=-180, rightlon=180,
                        central_longitude=-60)

        anim.set_zoom(zoom=2, pos=(0.0, -30.0))   # Atlantic-centric world view

    Quick start
    -----------
    ::

        anim = RobinsonAnimator(ds, "t2m")
        anim.set_region("global")
        anim.set_output("world_temperature.mp4")
        anim.animate()
    """

    _QUALITY_PRESETS   = QUALITY_PRESETS_WIDE
    _OUTPUT_DEFAULT    = "output_robinson.mp4"
    _FPS_DEFAULT       = 6
    _STEP_DEFAULT      = 1
    _DPI_DEFAULT       = 120
    _FIGSIZE_DEFAULT   = (16.0, 9.0)
    _CODEC_DEFAULT     = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8

    _NAMED_REGIONS: dict[str, dict] = {
        "global":           {"toplat":  85.0, "bottomlat": -85.0, "leftlon": -180.0, "rightlon":  180.0, "central_longitude":    0.0},
        "north_hemisphere": {"toplat":  85.0, "bottomlat":   0.0, "leftlon": -180.0, "rightlon":  180.0, "central_longitude":    0.0},
        "south_hemisphere": {"toplat":   0.0, "bottomlat": -85.0, "leftlon": -180.0, "rightlon":  180.0, "central_longitude":    0.0},
        "atlantic":         {"toplat":  75.0, "bottomlat": -60.0, "leftlon": -100.0, "rightlon":   20.0, "central_longitude":  -40.0},
        "pacific":          {"toplat":  70.0, "bottomlat": -70.0, "leftlon":  100.0, "rightlon":  290.0, "central_longitude":  180.0},
        "south_america":    {"toplat":  15.0, "bottomlat": -60.0, "leftlon":  -85.0, "rightlon":  -30.0, "central_longitude":  -57.5},
        "africa":           {"toplat":  40.0, "bottomlat": -40.0, "leftlon":  -20.0, "rightlon":   55.0, "central_longitude":   17.5},
        "europe_asia":      {"toplat":  75.0, "bottomlat":  10.0, "leftlon":  -30.0, "rightlon":  150.0, "central_longitude":   60.0},
        "north_america":    {"toplat":  80.0, "bottomlat":   5.0, "leftlon": -170.0, "rightlon":  -50.0, "central_longitude": -100.0},
        "asia":             {"toplat":  75.0, "bottomlat": -10.0, "leftlon":   40.0, "rightlon":  150.0, "central_longitude":   95.0},
    }

    def __init__(self, ds, var: str):
        self._region: dict = dict(_ROB_DEFAULT_REGION)
        self._show_ocean: bool = True
        self._show_grid:  bool = True
        self._base_init(ds, var)

    # ── region setters ────────────────────────────────────────────────────────

    def set_region(
        self,
        region: dict | str | None = None,
        *,
        toplat: float | None = None,
        bottomlat: float | None = None,
        leftlon: float | None = None,
        rightlon: float | None = None,
        central_longitude: float = 0.0,
    ) -> "RobinsonAnimator":
        """Define the map extent.  Accepts a named shortcut, a dict, or keyword args."""
        if isinstance(region, str):
            key = region.lower()
            if key not in self._NAMED_REGIONS:
                opts = ", ".join(f'"{k}"' for k in self._NAMED_REGIONS)
                raise ValueError(f"Unknown named region '{region}'. Available: {opts}")
            self._region = dict(self._NAMED_REGIONS[key])
        elif isinstance(region, dict):
            self._region = dict(region)
            if "central_longitude" not in self._region:
                self._region["central_longitude"] = 0.0
        else:
            if any(v is None for v in (toplat, bottomlat, leftlon, rightlon)):
                raise ValueError("Provide all four: toplat, bottomlat, leftlon, rightlon.")
            self._region = {
                "toplat": float(toplat), "bottomlat": float(bottomlat),
                "leftlon": float(leftlon), "rightlon": float(rightlon),
                "central_longitude": float(central_longitude),
            }
        return self

    def set_zoom(self, zoom: float, pos: tuple[float, float]) -> "RobinsonAnimator":
        """Define the map extent by zooming into a geographic point ``(lat, lon)``."""
        if zoom < 1:
            raise ValueError("zoom must be >= 1.")
        lat, lon = pos
        self._region = _region_from_zoom_rob(lat, lon, zoom)
        return self

    def set_ocean(self, visible: bool = True) -> "RobinsonAnimator":
        """Show / hide the ocean colour fill."""
        self._show_ocean = visible
        return self

    def set_grid(self, visible: bool = True) -> "RobinsonAnimator":
        """Show / hide lat/lon gridlines."""
        self._show_grid = visible
        return self

    # ── internal ──────────────────────────────────────────────────────────────

    def _get(self, time_idx: int):
        da   = self._ds[self._var][time_idx]
        step = self._step
        return (da.latitude.values[::step], da.longitude.values[::step],
                da.values[::step, ::step], da.time.values)

    def _build_axes(self) -> tuple[plt.Figure, plt.Axes]:
        r     = self._region
        c_lon = r.get("central_longitude", 0.0)
        scale = _font_scale(self._dpi)
        safe_top = max(-_ROB_LAT_MAX, min(_ROB_LAT_MAX, r["toplat"]))
        safe_bot = max(-_ROB_LAT_MAX, min(_ROB_LAT_MAX, r["bottomlat"]))

        fig, ax = plt.subplots(
            figsize=self._figsize,
            subplot_kw={"projection": ccrs.Robinson(central_longitude=c_lon)},
            facecolor="#0d1117",
            dpi=self._dpi,
        )
        ax.set_extent([r["leftlon"], r["rightlon"], safe_bot, safe_top],
                      crs=ccrs.PlateCarree())
        _add_features(ax, lw=0.5 * scale, show_states=self._show_states,
                      show_ocean=self._show_ocean)

        if self._show_grid:
            gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False,
                              linewidth=0.3 * scale, color="#14181c",
                              alpha=0.8, linestyle="--", zorder=2)
            gl.xlocator = mticker.MultipleLocator(30)
            gl.ylocator = mticker.MultipleLocator(30)

        return fig, ax

    def _draw_field(self, fig, ax, lat, lon, field, time_val) -> None:
        scale = _font_scale(self._dpi)
        norm  = BoundaryNorm(self._levels, ncolors=self._cmap.N, clip=True)

        cf = ax.pcolormesh(lon, lat, field, cmap=self._cmap, norm=norm,
                           transform=ccrs.PlateCarree(), zorder=1)
        ax.contour(lon[::3], lat[::3], field[::3, ::3],
                   levels=self._levels[::5], colors="white",
                   linewidths=0.25 * scale, alpha=0.4,
                   transform=ccrs.PlateCarree(), zorder=2)

        _draw_annotations_on(ax, lat, lon, field, self._annotations, self._dpi)
        _colorbar(fig, cf, ax, self._cbar_label, scale=scale)
        self._resolve_title(ax, time_val, scale)

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

    # ── public API ────────────────────────────────────────────────────────────

    def plot(
        self,
        time_idx: int = 0,
        save: str | None = None,
        show: bool = True,
    ) -> "RobinsonAnimator":
        """Render a single static frame."""
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

    def animate(self) -> "RobinsonAnimator":
        """Render all frames and assemble the video."""
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir     = _frames_dir(f"rob_{self._var}", run_date, cycle)
        n_frames = len(self._ds[self._var].time)

        r = self._region
        w, h = self._figsize
        print(f"[RobinsonAnimator] {n_frames} frames | "
              f"{int(w*self._dpi)}×{int(h*self._dpi)} px | "
              f"central_lon={r.get('central_longitude', 0.0):.1f}° | {self._output}")

        for tidx in range(n_frames):
            fpath = _frame_path(fdir, tidx)
            if not os.path.exists(fpath):
                self._render_frame(tidx, fpath)
            print(f"  frame {tidx+1}/{n_frames}  →  {fpath}", end="\r")

        print()
        self._write_video(fdir, n_frames)
        print(f"Saved: {self._output}")
        return self


# ══════════════════════════════════════════════════════════════════════════════
# Public re-exports
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Animators
    "OrthoAnimator",
    "NearsidePerspectiveAnimator",
    "PlateCarreeAnimator",
    "RobinsonAnimator",
    # Preset tables
    "QUALITY_PRESETS_SQUARE",
    "QUALITY_PRESETS_WIDE",
    "QUALITY_PRESETS",           # backward-compat alias → QUALITY_PRESETS_SQUARE
    "GEOSTATIONARY_HEIGHT",
    "EARTH_RADIUS",
    # Utility functions
    "list_quality_presets",
    "list_variable_presets",
    "QUALITY_PRESETS",
]