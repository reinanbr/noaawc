import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import imageio
from matplotlib.colors import BoundaryNorm
from datetime import datetime, timezone

# ── variable presets — single source of truth ─────────────────────────────────
#
# VARIABLE_PRESETS is defined and maintained in presets_extended.py.
# Do NOT duplicate entries here — edit presets_extended.py instead.
#
from noaawc.variables import VARIABLE_PRESETS, VARIABLES_INFO


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






# ── quality presets ───────────────────────────────────────────────────────────

QUALITY_PRESETS = {
    "sd": {
        "dpi":     72,
        "figsize": (8, 8),
        "fps":     6,
        "codec":   "libx264",
        "quality": 6,
        "description": "Standard Definition — fast render, small file",
    },
    "hd": {
        "dpi":     120,
        "figsize": (10, 10),
        "fps":     24,
        "codec":   "libx264",
        "quality": 8,
        "description": "Full HD (1080p-range) — balanced quality and speed",
    },
    "4k": {
        "dpi":     220,
        "figsize": (17.07, 17.07),
        "fps":     30,
        "codec":   "libx264",
        "quality": 10,
        "description": "Ultra HD 4K — maximum quality, large file and slow render",
    },
    "4k_60": {
        "dpi":     220,
        "figsize": (17.07, 17.07),
        "fps":     60,
        "codec":   "libx264",
        "quality": 10,
        "description": "Ultra HD 4K @ 60 fps — silky smooth, very large file",
    },
}


plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor":   "#0d1117",
    "text.color":       "#e6edf3",
    "axes.labelcolor":  "#e6edf3",
    "xtick.color":      "#8b949e",
    "ytick.color":      "#8b949e",
    "font.family":      "monospace",
    "axes.titlepad":    10,
})


# ══════════════════════════════════════════════════════════════════════════════
# Module-level map helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get(ds, var: str, time_idx: int = 0, step: int = 2):
    da = ds[var][time_idx]
    return (
        da.latitude.values[::step],
        da.longitude.values[::step],
        da.values[::step, ::step],
        da.time.values,
    )


def _add_features(ax: plt.Axes, lw: float = 0.4) -> None:
    ax.add_feature(cfeature.LAND,      facecolor="#1c2128", edgecolor="none",        zorder=0)
    ax.add_feature(cfeature.COASTLINE, edgecolor="#58a6ff", linewidth=lw,            zorder=3)
    ax.add_feature(cfeature.BORDERS,   edgecolor="#484f58", linewidth=lw * 0.7,
                   linestyle="--", zorder=3)


def _font_scale(dpi: int, base_dpi: int = 120) -> float:
    """
    Return a multiplier so that text stays visually proportional across DPIs.

    The reference point is the default HD preset (120 dpi = scale 1.0).
    At 220 dpi (4K) this gives ~1.83×, making labels clearly readable on a
    high-resolution render without becoming oversized in SD previews.

    The square-root dampening prevents text from growing as fast as pixels,
    which matches how human perception works on large screens.

        scale = sqrt(dpi / base_dpi)

    Examples
    --------
    dpi= 72  → scale ≈ 0.77   (SD — slightly smaller text)
    dpi=120  → scale = 1.00   (HD — reference)
    dpi=220  → scale ≈ 1.35   (4K — noticeably larger, still balanced)
    dpi=300  → scale ≈ 1.58   (print — comfortable for close-up viewing)
    """
    return (dpi / base_dpi) ** 0.5


def _add_gridlines(ax: plt.Axes, proj, scale: float = 1.0) -> None:
    draw = isinstance(proj, (ccrs.Mercator, ccrs.PlateCarree))
    gl = ax.gridlines(
        crs=ccrs.PlateCarree(), draw_labels=draw,
        linewidth=0.3 * scale, color="#21262d", alpha=0.8, linestyle="--", zorder=2,
    )
    gl.top_labels   = False
    gl.right_labels = False
    gl.xlocator     = mticker.MultipleLocator(10)
    gl.ylocator     = mticker.MultipleLocator(10)
    gl.xlabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}
    gl.ylabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}


def _colorbar(fig, cf, ax, label: str, orientation: str = "horizontal",
              scale: float = 1.0) -> None:
    cb = fig.colorbar(cf, ax=ax, orientation=orientation,
                      pad=0.03, fraction=0.03, shrink=0.85)
    cb.set_label(label, fontsize=round(8 * scale, 1), color="#8b949e")
    cb.ax.tick_params(labelsize=round(7 * scale, 1), colors="#8b949e")
    cb.outline.set_edgecolor("#30363d")


def _title(ax, main: str, sub: str = "", scale: float = 1.0) -> None:
    ax.set_title(main, fontsize=round(10 * scale, 1), fontweight="bold",
                 color="#e6edf3", loc="left", pad=6 * scale)
    if sub:
        ax.set_title(sub, fontsize=round(7 * scale, 1), color="#8b949e",
                     loc="right", pad=6 * scale)


def _run_label(time_val) -> str:
    return f"GFS — {time_val}"


# ── month name tables per date_style ─────────────────────────────────────────

_MONTHS: dict[str, list[str]] = {
    "pt-br": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
              "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
    "en":    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "es":    ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
    "fr":    ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
              "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"],
}


def _format_date(time_val, date_style: str = "en") -> str:
    """
    Convert a numpy datetime64 / Python datetime / timestamp to a human-readable
    date string, using the month abbreviations for `date_style`.

    Output format: ``DD Mon YYYY HH:MM``  (e.g. ``17 Abr 2026 03:00``)

    Parameters
    ----------
    time_val : numpy.datetime64 | datetime | int | float
        Frame timestamp as returned by xarray (usually numpy.datetime64).
    date_style : str
        Locale key.  Supported: ``"pt-br"``, ``"en"``, ``"es"``, ``"fr"``.
        Falls back to ``"en"`` for unknown keys.

    Returns
    -------
    str   Formatted date string.
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


def _gfs_meta(ds, var: str):
    """Return (run_date_str, cycle_str) from dataset attributes."""
    run_date = str(ds.attrs.get("run_date", "unknown"))
    cycle    = str(ds.attrs.get("cycle",    "00z"))
    return run_date, cycle


def _frames_dir(var: str, run_date: str, cycle: str) -> str:
    path = os.path.join("frames", f"{var}_{run_date}_{cycle}")
    os.makedirs(path, exist_ok=True)
    return path


def _frame_path(fdir: str, tidx: int) -> str:
    return os.path.join(fdir, f"frame_{tidx:04d}.png")


def _interp_field_value(lat_arr, lon_arr, field, pos: tuple) -> float:
    """
    Return the field value at the grid point nearest to pos=(lat, lon).

    Uses nearest-neighbour lookup — no interpolation weights, which keeps
    the call fast inside a per-frame render loop.

    Parameters
    ----------
    lat_arr : 1-D array  Latitude grid values (degrees).
    lon_arr : 1-D array  Longitude grid values (degrees).
    field   : 2-D array  Data values on the (lat, lon) grid.
    pos     : (lat, lon) Target geographic position in decimal degrees.

    Returns
    -------
    float   Scalar field value at the nearest grid point.
    """
    lat_target, lon_target = pos
    i = int(np.argmin(np.abs(lat_arr - lat_target)))
    j = int(np.argmin(np.abs(lon_arr - lon_target)))
    return float(field[i, j])


def list_quality_presets() -> None:
    """Print all available quality presets and their settings."""
    print(f"{'Preset':<10}  {'DPI':<5}  {'Figsize (in)':<16}  {'FPS':<5}  {'Codec':<10}  Description")
    print("-" * 90)
    for name, p in QUALITY_PRESETS.items():
        w, h = p["figsize"]
        px_w = int(w * p["dpi"])
        px_h = int(h * p["dpi"])
        print(
            f"{name:<10}  {p['dpi']:<5}  {w:.1f}×{h:.1f} ({px_w}×{px_h} px)"
            f"{'':>2}  {p['fps']:<5}  {p['codec']:<10}  {p['description']}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Figure-level overlay helpers
# ══════════════════════════════════════════════════════════════════════════════

def _draw_info_box(
    fig: plt.Figure,
    var_key: str,
    cycle: str,
    date_str: str,
    scale: float = 1.0,
) -> None:
    """
    Draw a top-right overlay box on the figure showing variable key,
    model cycle, and frame date.

    Placed in figure coordinates so it always sits just inside the
    top-right corner regardless of map projection or axes extent.

    Layout example::

        ┌──────────────────────┐
        │  Key   : t2m         │
        │  Cycle : 00z         │
        │  Date  : 17 Apr 2026 │
        │          03:00 UTC   │
        └──────────────────────┘

    Parameters
    ----------
    fig      : active Figure
    var_key  : variable identifier shown in the Key row  (e.g. "t2m")
    cycle    : GFS cycle string from dataset attrs        (e.g. "00z")
    date_str : pre-formatted frame date                   (e.g. "17 Apr 2026 03:00")
    scale    : DPI-proportional font scale factor
    """
    lines = [
        f"key: {var_key} - {VARIABLES_INFO.get(var_key, {}).get('long_name', var_key)}",
        f"Date Cycle: {date_str} {cycle}",
    ]
    text = "\n".join(lines)

    fig.text(
        0.985, 0.985,
        text,
        ha="right", va="top",
        fontsize=round(7.5 * scale, 1),
        color="#828283",
        fontweight="bold",
        fontfamily="monospace",
        linespacing=1.55,
        bbox=dict(
            boxstyle="round,pad=0.45",
            facecolor="#161b22",
            edgecolor="#30363d",
            linewidth=0.8 * scale,
            alpha=0.88,
        ),
        zorder=10,
    )


def _draw_data_credit(fig: plt.Figure, scale: float = 1.0) -> None:
    """
    Draw a bottom-right data-source credit on the figure.

    Renders as::

        GFS 0.25°
        NASA / NOAA

    Text is grey and bold, intentionally small so it does not
    compete with map content.

    Parameters
    ----------
    fig   : active Figure
    scale : DPI-proportional font scale factor
    """
    fig.text(
        0.985, 0.012,
        "GFS 0.25°\nNASA / NOAA",
        ha="right", va="bottom",
        fontsize=round(6.5 * scale, 1),
        color="#8b949e",
        fontweight="bold",
        fontfamily="monospace",
        linespacing=1.45,
        zorder=10,
    )

# ── figure-level constants ─────────────────────────────────────────────────────

# Vertical position of the colorbar in figure coordinates.
# The horizontal colorbar is placed at ~pad=0.03 below the axes, fraction=0.03
# tall, so its top edge sits at roughly y=0.10 in figure space.
# The author label is centred in the gap between y=0 and y=0.10.
_CBAR_BOTTOM_Y: float = 0.10   # approximate top of the horizontal colorbar area


def _draw_author(
    fig: plt.Figure,
    author: str,
    scale: float = 1.0,
    # ── layout ──────────────────────────────────────────────────────────────
    x: float | None = 0.4966,
    y: float | None = 0.1,
    ha: str = "center",
    va: str = "center",
    # ── appearance ──────────────────────────────────────────────────────────
    color: str = "#e6edf3",
    fontsize: float = 8.5,
    fontweight: str = "bold",
    fontfamily: str = "monospace",
    alpha: float = 1.0,
    # ── optional background pill ────────────────────────────────────────────
    bbox: bool = False,
    bbox_facecolor: str = "#161b22",
    bbox_edgecolor: str = "#30363d",
    bbox_alpha: float = 0.75,
    bbox_pad: float = 0.4,
) -> None:
    """
    Draw the author name on the figure.

    Default placement: horizontally centred in the gap between the bottom
    of the figure (y=0) and the bottom edge of the horizontal colorbar
    (approximately y=0.10), so the label never overlaps map or colorbar.

    The vertical midpoint of that gap is:

        y_mid = _CBAR_BOTTOM_Y / 2   ≈ 0.050

    At higher DPIs the colorbar occupies slightly more figure height because
    the colorbar fraction is fixed and the axis area is the same proportion,
    so we leave a small upward bias (+0.005) to keep the label visually
    centred for the HD/4K presets.

    Parameters
    ----------
    fig            : active Figure
    author         : text to render
    scale          : DPI-proportional font scale factor  (from _font_scale())
    x              : figure x-coordinate [0..1].  Default: 0.5 (centred).
    y              : figure y-coordinate [0..1].
                     Default: auto-computed midpoint of the sub-colorbar gap,
                     adjusted for the rendered font height so the label does
                     not visually crowd the colorbar edge.
    ha             : horizontal alignment  ("left" | "center" | "right").
                     Default "center".
    va             : vertical alignment    ("top" | "center" | "bottom").
                     Default "center".
    color          : text colour.  Default "#e6edf3" (near-white).
    fontsize       : base font size in points at the HD reference DPI (120).
                     Scaled by `scale` before use.  Default 8.5.
    fontweight     : "normal" | "bold" (default) | "heavy".
    fontfamily     : font family string.  Default "monospace".
    alpha          : text opacity [0..1].  Default 1.0.
    bbox           : draw a rounded background pill behind the text.
                     Useful when the label needs to stand out over a busy
                     region.  Default False.
    bbox_facecolor : pill fill colour.    Default "#161b22".
    bbox_edgecolor : pill border colour.  Default "#30363d".
    bbox_alpha     : pill opacity.        Default 0.75.
    bbox_pad       : internal padding around the text in font-size units.
                     Default 0.4.
    """
    # ── resolve x ─────────────────────────────────────────────────────────────
    x_pos: float = x if x is not None else 0.5

    # ── resolve y (auto-centre in the sub-colorbar gap) ───────────────────────
    if y is not None:
        y_pos = y
    else:
        # Estimate the rendered font height in figure-coordinate units.
        # At the reference DPI (120) an 8.5pt monospace character is ~12px tall.
        # Figure height in pixels ≈ figsize[1] * dpi.
        fig_height_px: float = fig.get_figheight() * fig.dpi
        font_height_fig: float = (fontsize * scale * 1.4) / fig_height_px   # 1.4 = line-height
        # Centre of the gap, shifted up by half a line-height so the visual
        # centre of the glyphs sits at the mathematical midpoint.
        gap_centre: float = _CBAR_BOTTOM_Y / 2.0 + 0.005   # slight upward bias
        y_pos = gap_centre + font_height_fig * 0.5

    # ── optional bbox ──────────────────────────────────────────────────────────
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
        x_pos, y_pos,
        author,
        ha=ha, va=va,
        fontsize=round(fontsize * scale, 1),
        color=color,
        fontweight=fontweight,
        fontfamily=fontfamily,
        alpha=alpha,
        bbox=bbox_props,
        zorder=10,
    )



# ══════════════════════════════════════════════════════════════════════════════
# OrthoAnimator
# ══════════════════════════════════════════════════════════════════════════════

class OrthoAnimator:
    """
    Renders an orthographic animation of a GFS variable.

    Variable presets are loaded automatically from presets_extended.VARIABLE_PRESETS.
    Call list_variable_presets() to see every supported key.  A subset of the
    most common ones is listed below; any key not found falls back to "t2m".

    Common surface variables
    -------------------------
    "t2m"       2-metre temperature (°C)
    "d2m"       2-metre dewpoint temperature (°C)
    "r2"        2-metre relative humidity (%)
    "sh2"       2-metre specific humidity (kg kg⁻¹)
    "pwat"      Precipitable water (kg m⁻²)
    "cwat"      Column cloud water (kg m⁻²)
    "prmsl"     Mean sea-level pressure (hPa)
    "sp"        Surface pressure (hPa)
    "prate"     Precipitation rate (mm h⁻¹)
    "cape"      CAPE (J kg⁻¹)
    "cin"       Convective inhibition (J kg⁻¹)
    "refc"      Composite reflectivity (dBZ)
    "tcc"       Total cloud cover (%)
    "vis"       Surface visibility (m)
    "orog"      Orography / terrain height (m)

    Wind variables  ── derived: compute sqrt(u²+v²) before use ──
    --------------------------------------------------------------
    "u10"       10-m U wind component (m s⁻¹)
    "v10"       10-m V wind component (m s⁻¹)
    "wspd10"    10-m wind speed scalar (m s⁻¹)  ← ds["wspd10"] = sqrt(u10²+v10²)
    "gust"      Surface wind gust (m s⁻¹)

    Upper-air / isobaric
    ---------------------
    "t"         Temperature (°C)
    "r"         Relative humidity (%)
    "gh"        Geopotential height (gpm)
    "u"         U wind component (m s⁻¹)
    "v"         V wind component (m s⁻¹)
    "wspd"      Wind speed scalar (m s⁻¹)       ← ds["wspd"] = sqrt(u²+v²)
    "w"         Vertical velocity ω (Pa s⁻¹)
    "absv"      Absolute vorticity (s⁻¹)

    Quick start
    -----------
    anim = OrthoAnimator(ds, "t2m")
    anim.set_output("output.mp4")
    anim.set_rotation(lon_start=-90, lon_end=-20, lat_start=-5, lat_end=-20)
    anim.set_rotation_stop(fraction=0.65)
    anim.animate()

    Wind speed example (derived variable)
    --------------------------------------
    import numpy as np
    ds["wspd10"] = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)
    anim = OrthoAnimator(ds, "wspd10")
    anim.set_output("wind_speed_10m.mp4")
    anim.animate()

    4K output
    ---------
    anim.set_quality("4k")          # preset: dpi=220, figsize=17×17 in, fps=30
    anim.set_quality("4k_60")       # same pixels, 60 fps
    anim.set_quality("hd")          # Full-HD range, fps=24
    anim.set_quality("sd")          # lightweight preview

    Fine-grained control (overrides preset values individually)
    -----------------------------------------------------------
    anim.set_dpi(400)               # custom DPI
    anim.set_figsize(17.07, 17.07)  # ~3840 px wide at 225 dpi
    anim.set_fps(60)
    anim.set_video_quality(10)      # libx264 CRF-like quality, 0–10
    anim.set_codec("libx265")       # H.265 for smaller 4K files

    Map annotations
    ---------------
    anim.set_annotate("Juazeiro - BA %d°C", pos=(-9.4, -40.5))
    anim.set_annotate("Fortaleza %d°C",     pos=(-3.72, -38.54), color="#58a6ff")
    anim.clear_annotations()

    Dynamic title with per-frame date
    ----------------------------------
    anim.set_title("Temperatura da Superfície — %S", date_style="pt-br")
    # renders as: "Temperatura da Superfície — 17 Abr 2026 03:00"

    anim.set_title("Surface Temperature  %S")
    # renders as: "Surface Temperature  17 Apr 2026 03:00"

    # Supported date_style values: "en" (default), "pt-br", "es", "fr"

    Top-right info box  (automatic — always rendered)
    --------------------------------------------------
    Every frame includes a top-right panel showing:
        Key   : <variable key, e.g. t2m>
        Cycle : <GFS cycle, e.g. 00z>
        Date  : <frame timestamp, e.g. 17 Apr 2026 03:00>

    Bottom-right data credit  (automatic — always rendered)
    --------------------------------------------------------
    Every frame shows "GFS 0.25° / NASA · NOAA" in grey bold at the
    bottom-right corner.

    Author label
    ------------
    anim.set_author("Maria Silva")
    # renders the name centred between the colorbar and the bottom edge,
    # in white bold on every frame.

    anim.set_author("")   # clear / disable the author label

    Static snapshot
    ---------------
    anim.plot(time_idx=0, save="snapshot.png")
    anim.plot(time_idx=0)          # opens interactive window
    """

    # ── class-level defaults ──────────────────────────────────────────────────
    _OUTPUT_DEFAULT        = "output.mp4"
    _FPS_DEFAULT           = 6
    _STEP_DEFAULT          = 1
    _DPI_DEFAULT           = 120
    _FIGSIZE_DEFAULT       = (8, 8)
    _CODEC_DEFAULT         = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8      # imageio quality scale: 0 (worst) – 10 (best)

    def __init__(self, ds, var: str, central_point: tuple = (-45.0, -15.0)):
        self._ds            = ds
        self._var           = var
        self._central_point = central_point

        # output options
        self._output        = self._OUTPUT_DEFAULT
        self._fps           = self._FPS_DEFAULT
        self._step          = self._STEP_DEFAULT
        self._dpi           = self._DPI_DEFAULT
        self._figsize       = self._FIGSIZE_DEFAULT
        self._codec         = self._CODEC_DEFAULT
        self._video_quality = self._VIDEO_QUALITY_DEFAULT

        # ── auto-load variable preset (falls back to temperature defaults) ────
        self._apply_variable_preset(var, silent=False)

        # rotation (None = no rotation)
        self._lon_start     = None
        self._lat_start     = None
        self._lon_end       = None
        self._lat_end       = None
        self._stop_frame    = None
        self._stop_fraction = None

        # annotations
        self._annotations: list[dict] = []

        # custom title template (set via set_title())
        self._title_template: str | None = None
        self._title_date_style: str      = "en"

        # author label (set via set_author())
        # author label
        self._author: str = ""
        self._author_kwargs: dict = {}   # populated by set_author()
    # ── variable preset helpers ───────────────────────────────────────────────

    def _apply_variable_preset(self, var: str, silent: bool = True) -> None:
        """
        Load cmap / levels / labels from VARIABLE_PRESETS[var].

        Falls back to temperature defaults when the key is not found and
        prints a one-line notice so the caller is aware.
        """
        if var in VARIABLE_PRESETS:
            p = VARIABLE_PRESETS[var]
            if not silent:
                print(f"Variable preset '{var}': {p['plot_title']}")
        else:
            p = VARIABLE_PRESETS["t2m"]
            print(
                f"[OrthoAnimator] No preset for '{var}' — "
                f"falling back to temperature defaults.  "
                f"Call use_variable_defaults(key) to override."
            )
        self._cmap       = p["cmap"]
        self._levels     = np.asarray(p["levels"])
        self._cbar_label = p["cbar_label"]
        self._plot_title = p["plot_title"]

    def use_variable_defaults(self, var: str | None = None) -> "OrthoAnimator":
        """
        Apply the plotting preset for `var` (or for the instance's own variable
        if `var` is omitted).

        All keys defined in presets_extended.VARIABLE_PRESETS are valid.
        Call list_variable_presets() to see the full list.

        Examples
        --------
        anim.use_variable_defaults()           # re-apply preset for current var
        anim.use_variable_defaults("prmsl")    # switch to pressure preset
        anim.use_variable_defaults("wspd10")   # switch to 10-m wind speed preset
        anim.use_variable_defaults("wspd")     # switch to upper-air wind speed
        """
        key = var if var is not None else self._var
        self._apply_variable_preset(key, silent=False)
        return self

    # ── output options ────────────────────────────────────────────────────────

    def set_output(self, path: str) -> "OrthoAnimator":
        """Output file path (.mp4 or .gif)."""
        self._output = path
        return self

    def set_fps(self, fps: int) -> "OrthoAnimator":
        """
        Frames per second for the output video.

        Common values
        -------------
        6   → smooth enough for slow-moving weather fields (default)
        24  → cinematic HD
        30  → broadcast / streaming standard
        60  → ultra-smooth / gaming-grade (pairs well with 4K)
        """
        self._fps = fps
        return self

    def set_step(self, step: int) -> "OrthoAnimator":
        """Spatial decimation factor (1 = no decimation)."""
        self._step = step
        return self

    def set_dpi(self, dpi: int) -> "OrthoAnimator":
        """
        Figure resolution in dots per inch.

        Output pixel dimensions = figsize (inches) × dpi.

        Common targets
        --------------
        72   → screen preview / SD
        120  → Full-HD range  (default)
        150  → ~2K at 14-in figure
        220  → ~3840 px wide at 17.07-in figure (4K)
        300  → print-quality stills
        400+ → extreme close-up / poster crops
        """
        self._dpi = dpi
        return self

    def set_figsize(self, w: float, h: float) -> "OrthoAnimator":
        """
        Figure size in inches (width, height).

        Pixel output = (w × dpi, h × dpi).

        4K target: set_figsize(17.07, 17.07) with set_dpi(225)
        → 17.07 × 225 ≈ 3841 px per side.
        """
        self._figsize = (w, h)
        return self

    def set_codec(self, codec: str) -> "OrthoAnimator":
        """
        Video codec passed to imageio / ffmpeg.

        Common options
        --------------
        "libx264"   → H.264, widest compatibility (default)
        "libx265"   → H.265 / HEVC, ~40 % smaller files at same quality
                      (recommended for 4K to keep file sizes manageable)
        "vp9"       → open-source, good for web delivery
        "prores"    → Apple ProRes, lossless-ish, large files, ideal for editing
        """
        self._codec = codec
        return self

    def set_video_quality(self, quality: int) -> "OrthoAnimator":
        """
        Encoding quality passed to imageio (0 = worst, 10 = best).

        Higher values produce larger files but sharper detail — matters
        most at 4K where compression artefacts are more visible.

        Recommended values
        ------------------
        6   → SD / draft renders
        8   → HD (default)
        10  → 4K final output
        """
        if not 0 <= quality <= 10:
            raise ValueError("quality must be between 0 and 10.")
        self._video_quality = quality
        return self

    def set_quality(self, preset: str) -> "OrthoAnimator":
        """
        Apply a named quality preset in one call.

        Available presets (call list_quality_presets() to print them)
        --------------------------------------------------------------
        "sd"     →  72 dpi,  8×8 in,   6 fps  — fast preview
        "hd"     → 120 dpi, 10×10 in, 24 fps  — Full-HD range
        "4k"     → 220 dpi, 17×17 in, 30 fps  — Ultra HD 4K
        "4k_60"  → 220 dpi, 17×17 in, 60 fps  — Ultra HD 4K @ 60 fps

        Any individual setter called afterwards overrides the preset value.

        Examples
        --------
        anim.set_quality("4k")
        anim.set_quality("4k").set_fps(24)   # 4K pixels but 24 fps
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

    # ── colormap / levels options ─────────────────────────────────────────────

    def set_cmap(self, cmap) -> "OrthoAnimator":
        """
        Override the colormap used for the pcolormesh fill.

        Accepts any matplotlib-compatible colormap object or name string.

        Examples
        --------
        anim.set_cmap(cmocean.cm.thermal)
        anim.set_cmap("RdBu_r")
        anim.set_cmap(plt.cm.viridis)
        """
        self._cmap = plt.get_cmap(cmap) if isinstance(cmap, str) else cmap
        return self

    def set_levels(self, levels) -> "OrthoAnimator":
        """
        Override the contour / BoundaryNorm levels.

        Accepts a 1-D array-like of level boundaries.

        Examples
        --------
        anim.set_levels(np.arange(960, 1040, 2))          # pressure
        anim.set_levels(np.linspace(-30, 45, 40))          # custom temperature
        anim.set_levels(np.arange(0, 65, 2))               # extend wind to 64 m/s
        """
        self._levels = np.asarray(levels)
        return self

    def set_cbar_label(self, label: str) -> "OrthoAnimator":
        """Label shown on the colorbar."""
        self._cbar_label = label
        return self

    def set_plot_title(self, title: str) -> "OrthoAnimator":
        """Main title shown on each frame / static plot."""
        self._plot_title = title
        return self

    def set_title(
        self,
        template: str,
        date_style: str = "en",
    ) -> "OrthoAnimator":
        """
        Set a dynamic left-side title that updates on every frame.

        Use ``%S`` anywhere in the template string as a placeholder — it is
        replaced at render time with the frame's data timestamp, formatted
        according to ``date_style``.

        Parameters
        ----------
        template : str
            Title text with an optional ``%S`` placeholder.

            Examples::

                "Surface Temperature  %S"
                "Temperatura da Superfície — %S"
                "Precipitation Rate  |  GFS  |  %S"
                "Wind Speed (10 m)  %S"
                "CAPE — %S"

        date_style : str
            Controls the language of the month abbreviation in the substituted
            date string.  Supported values:

            =========  ===============================  ====================
            Key        Month example                    Full example
            =========  ===============================  ====================
            ``"en"``   Apr                              17 Apr 2026 03:00
            ``"pt-br"``Abr                              17 Abr 2026 03:00
            ``"es"``   Abr                              17 Abr 2026 03:00
            ``"fr"``   Avr                              17 Avr 2026 03:00
            =========  ===============================  ====================

            Unknown keys fall back to ``"en"``.  Default: ``"en"``.

        Returns
        -------
        self
            Enables method chaining.

        Notes
        -----
        * ``set_title()`` takes priority over ``set_plot_title()`` — if both
          are called, the template set here is used for the left title and
          ``set_plot_title()`` has no visible effect.
        * To revert to the preset-defined title, call ``set_title("")`` or
          ``use_variable_defaults()``.
        * The right-side subtitle (``GFS — <raw timestamp>``) is suppressed
          when a custom title template is active, since the date is already
          embedded in the left title.

        Examples
        --------
        >>> anim.set_title("Temperatura da Superfície — %S", date_style="pt-br")
        # renders as: "Temperatura da Superfície — 17 Abr 2026 03:00"

        >>> anim.set_title("Surface Temperature  %S")
        # renders as: "Surface Temperature  17 Apr 2026 03:00"

        >>> (anim
        ...     .set_title("Wind Speed (10 m) — %S", date_style="pt-br")
        ...     .set_quality("4k")
        ...     .animate())
        """
        self._title_template   = template if template else None
        self._title_date_style = date_style
        return self

    # ── author label ──────────────────────────────────────────────────────────

    def set_author(
        self,
        name: str,
        # ── layout ──────────────────────────────────────────────────────────
        x: float | None = None,
        y: float | None = None,
        ha: str = "center",
        va: str = "center",
        # ── appearance ──────────────────────────────────────────────────────
        color: str = "#e6edf3",
        fontsize: float = 8.5,
        fontweight: str = "bold",
        fontfamily: str = "monospace",
        alpha: float = 1.0,
        # ── optional background pill ─────────────────────────────────────────
        bbox: bool = False,
        bbox_facecolor: str = "#161b22",
        bbox_edgecolor: str = "#30363d",
        bbox_alpha: float = 0.75,
        bbox_pad: float = 0.4,
    ) -> "OrthoAnimator":
        """
        Set the author name (or any short credit string) displayed on every frame.

        The label is rendered by default in white bold monospace, horizontally
        centred in the gap between the bottom of the figure and the colorbar —
        so it is always readable without overlapping map or colorbar content.

        Pass an empty string (``""``) to disable the label entirely.

        Parameters
        ----------
        name : str
            Author name or any short credit string.
            Examples: ``"Maria Silva"``, ``"@msilva_met"``, ``"INMET / FUNCEME"``

        x : float or None
            Horizontal position in figure coordinates [0..1].
            ``None`` (default) → 0.5 (centred).

        y : float or None
            Vertical position in figure coordinates [0..1].
            ``None`` (default) → auto-computed midpoint of the gap between
            y=0 and the bottom of the colorbar, adjusted for font height.
            Override when your layout differs from the default (e.g. portrait
            figures, very large fonts, or multi-line credits).

        ha : str
            Horizontal text alignment — ``"left"``, ``"center"`` (default),
            ``"right"``.  Change together with ``x`` when placing the label
            off-centre::

                anim.set_author("@handle", x=0.98, ha="right")

        va : str
            Vertical text alignment — ``"top"``, ``"center"`` (default),
            ``"bottom"``.

        color : str
            Text colour.  Default ``"#e6edf3"`` (near-white on the dark theme).

        fontsize : float
            Base font size in points at the HD reference DPI (120 dpi).
            The size is scaled proportionally with ``_font_scale(dpi)`` at
            render time, so it grows naturally when you switch to a 4K preset.
            Default ``8.5``.

        fontweight : str
            ``"normal"`` | ``"bold"`` (default) | ``"heavy"``.

        fontfamily : str
            Font family string passed to matplotlib.  Default ``"monospace"``.

        alpha : float
            Text opacity [0..1].  Default ``1.0``.

        bbox : bool
            Draw a rounded background pill behind the text.  Useful when the
            label colour blends into the map or when you want a more polished
            look.  Default ``False``.

        bbox_facecolor : str
            Pill background fill colour.  Default ``"#161b22"``.

        bbox_edgecolor : str
            Pill border colour.  Default ``"#30363d"``.

        bbox_alpha : float
            Pill opacity.  Default ``0.75``.

        bbox_pad : float
            Internal padding around the text in font-size units.  Default ``0.4``.

        Returns
        -------
        self
            Enables method chaining.

        Examples
        --------
        Basic usage — name centred in the sub-colorbar gap, white bold::

            anim.set_author("Maria Silva")

        Custom colour and slightly lower position::

            anim.set_author("@msilva_met", color="#58a6ff", y=0.03)

        Right-aligned handle near the bottom-right corner::

            anim.set_author("@msilva_met", x=0.98, ha="right", y=0.015)

        With a dark background pill (stands out over light map edges)::

            anim.set_author(
                "INMET / FUNCEME",
                bbox=True,
                bbox_facecolor="#161b22",
                bbox_edgecolor="#30363d",
            )

        Disable the author label::

            anim.set_author("")

        Method chaining::

            (anim
                .set_author("Maria Silva", color="#f7c948", bbox=True)
                .set_quality("4k")
                .animate())
        """
        self._author = name.strip()

        # Store all style kwargs so _draw_author() can be called with them later
        self._author_kwargs: dict = dict(
            x=x, y=y, ha=ha, va=va,
            color=color, fontsize=fontsize,
            fontweight=fontweight, fontfamily=fontfamily,
            alpha=alpha,
            bbox=bbox,
            bbox_facecolor=bbox_facecolor,
            bbox_edgecolor=bbox_edgecolor,
            bbox_alpha=bbox_alpha,
            bbox_pad=bbox_pad,
        )
        return self
    # ── named-variable convenience shortcuts ─────────────────────────────────

    def use_temperature_defaults(self) -> "OrthoAnimator":
        """Switch to 2-metre temperature (t2m) defaults."""
        return self.use_variable_defaults("t2m")

    def use_pressure_defaults(self) -> "OrthoAnimator":
        """Switch to mean sea-level pressure (prmsl) defaults."""
        return self.use_variable_defaults("prmsl")

    def use_precipitation_defaults(self) -> "OrthoAnimator":
        """Switch to precipitation rate (prate) defaults."""
        return self.use_variable_defaults("prate")

    def use_humidity_defaults(self) -> "OrthoAnimator":
        """Switch to 2-metre relative humidity (r2) defaults."""
        return self.use_variable_defaults("r2")

    def use_cloud_water_defaults(self) -> "OrthoAnimator":
        """Switch to column cloud water (cwat) defaults."""
        return self.use_variable_defaults("cwat")

    def use_wind_speed_defaults(self) -> "OrthoAnimator":
        """
        Switch to 10-m wind speed (wspd10) defaults.

        IMPORTANT: wspd10 is a derived variable — assign it to the dataset
        before constructing OrthoAnimator:

            ds["wspd10"] = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)
        """
        return self.use_variable_defaults("wspd10")

    def use_upper_wind_speed_defaults(self) -> "OrthoAnimator":
        """
        Switch to upper-air wind speed (wspd) defaults.

        IMPORTANT: wspd is a derived variable — assign it to the dataset
        before constructing OrthoAnimator:

            ds["wspd"] = np.sqrt(ds["u"] ** 2 + ds["v"] ** 2)
        """
        return self.use_variable_defaults("wspd")

    # ── rotation options ──────────────────────────────────────────────────────

    def set_rotation(
        self,
        lon_start: float,
        lon_end: float,
        lat_start: float | None = None,
        lat_end: float | None = None,
    ) -> "OrthoAnimator":
        """
        Define the camera arc from (lon_start, lat_start) to (lon_end, lat_end).

        If lat_start / lat_end are omitted, the latitude of central_point is
        used as a fixed value throughout the rotation.
        """
        self._lon_start = lon_start
        self._lon_end   = lon_end
        self._lat_start = lat_start if lat_start is not None else self._central_point[1]
        self._lat_end   = lat_end   if lat_end   is not None else self._central_point[1]
        return self

    def set_rotation_stop(
        self,
        frame: int | None = None,
        fraction: float | None = None,
    ) -> "OrthoAnimator":
        """
        Frame at which the rotation ends and the camera freezes on the end point.

        Provide either `frame` (absolute index) **or** `fraction` (0.0–1.0
        relative to total frames).
        """
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

    # ── annotation options ────────────────────────────────────────────────────
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
        # ── marker ───────────────────────────────────────────────────
        marker: str | None = "o",
        marker_size: float = 6.0,
        marker_color: str | None = None,
        marker_edge_color: str = "#0d1117",
        marker_edge_width: float = 0.8,
        marker_alpha: float = 1.0,
        text_offset: tuple[float, float] = (0.0, 0.8),
    ) -> "OrthoAnimator":
        """
        Add a text annotation (with optional position marker) overlaid on the
        map in every frame.
 
        Parameters
        ----------
        text_base : str
            Label text.  Use ``%d`` / ``%.1f`` / ``%.2f`` as a placeholder for
            the field value sampled at ``pos``.
 
            Examples::
 
                "Juazeiro: %.1f°C"     →   "Juazeiro: 32.4°C"
                "Salvador %.1f hPa"    →   "Salvador 1012.3 hPa"
                "Recife %.1f m/s"      →   "Recife 6.4 m/s"
 
        pos : tuple (lat, lon)
            Geographic position in decimal degrees.  Example: ``(-9.4, -40.5)``.
 
        size : float
            Font size in points at the HD reference DPI (120 dpi).  Default 9.
 
        color : str
            Text colour.  Default ``"#e6edf3"``.
 
        weight : str
            ``"normal"`` | ``"bold"`` (default) | ``"heavy"``.
 
        alpha : float
            Text opacity.  Default ``0.9``.
 
        bbox : bool
            Draw a rounded background box behind the text.  Default ``True``.
 
        bbox_color : str
            Background fill colour.  Default ``"#0d1117"``.
 
        bbox_alpha : float
            Background box opacity.  Default ``0.55``.
 
        interpolate : bool
            Replace ``%…`` placeholder with the field value at ``pos``.
            Default ``True``.
 
        zorder : int
            Render layer.  Default ``5``.
 
        marker : str or None
            Matplotlib marker symbol plotted at the exact geographic position.
            ``None`` disables the marker.
 
            Common choices
            --------------
            ``"o"``  filled circle  (default)
            ``"^"``  triangle up
            ``"s"``  square
            ``"D"``  diamond
            ``"*"``  star
            ``"+"``  plus
            ``"x"``  X mark
            ``None`` no marker
 
        marker_size : float
            Marker size in points at the HD reference DPI.  Default ``6.0``.
 
        marker_color : str or None
            Marker fill colour.  ``None`` (default) inherits ``color``.
 
        marker_edge_color : str
            Marker outline colour.  Default ``"#0d1117"``.
 
        marker_edge_width : float
            Marker outline width in points.  Default ``0.8``.
 
        marker_alpha : float
            Marker opacity.  Default ``1.0``.
 
        text_offset : tuple (Δlon, Δlat)
            Shift the text label relative to ``pos`` in decimal degrees so it
            does not sit on top of the marker.  Default ``(0.0, 0.8)`` —
            0.8 ° north of the point.
 
        Returns
        -------
        self
 
        Examples
        --------
        # Default: circle marker + label 0.8° north
        anim.set_annotate("Juazeiro: %.1f°C", pos=(-9.4, -40.5))
 
        # Star, custom colour, bigger offset
        anim.set_annotate(
            "Fortaleza: %.1f°C",
            pos=(-3.72, -38.54),
            marker="*",
            marker_size=10,
            marker_color="#f7c948",
            text_offset=(0.5, 1.2),
        )
 
        # No marker — text only
        anim.set_annotate("Manaus", pos=(-3.10, -60.02), marker=None)
 
        # Method chaining
        (anim
            .set_annotate("Recife %.1f m/s",    pos=(-8.05,  -34.88))
            .set_annotate("Fortaleza %.1f m/s", pos=(-3.72,  -38.54))
            .set_annotate("Manaus %.1f m/s",    pos=(-3.10,  -60.02))
        )
        """
        self._annotations.append(dict(
            text_base         = text_base,
            pos               = pos,
            size              = size,
            color             = color,
            weight            = weight,
            alpha             = alpha,
            bbox              = bbox,
            bbox_color        = bbox_color,
            bbox_alpha        = bbox_alpha,
            interpolate       = interpolate,
            zorder            = zorder,
            marker            = marker,
            marker_size       = marker_size,
            marker_color      = marker_color,   # None → inherits color
            marker_edge_color = marker_edge_color,
            marker_edge_width = marker_edge_width,
            marker_alpha      = marker_alpha,
            text_offset       = text_offset,
        ))
        return self
 
 

    def clear_annotations(self) -> "OrthoAnimator":
        """Remove all registered annotations."""
        self._annotations.clear()
        return self

    # ── internal helpers ──────────────────────────────────────────────────────

    def _resolve_stop_frame(self, n_frames: int) -> int:
        """Convert fraction → absolute index (called once per animate())."""
        if self._stop_fraction is not None:
            return max(1, int(round(self._stop_fraction * n_frames)))
        if self._stop_frame is not None:
            return self._stop_frame
        return n_frames

    def _rotation_at(self, tidx: int, stop: int) -> tuple[float, float]:
        """Return the (lon, lat) of the camera centre for frame `tidx`."""
        if self._lon_start is None:
            return self._central_point

        if tidx >= stop:
            return (self._lon_end, self._lat_end)

        t   = tidx / stop
        lon = self._lon_start + t * (self._lon_end - self._lon_start)
        lat = self._lat_start + t * (self._lat_end - self._lat_start)
        return (lon, lat)

    def _build_axes(self, central: tuple) -> tuple[plt.Figure, plt.Axes]:
        """Create and return a (fig, ax) pair with the orthographic projection."""
        proj  = ccrs.Orthographic(*central)
        scale = _font_scale(self._dpi)
        fig, ax = plt.subplots(
            figsize=self._figsize,
            subplot_kw={"projection": proj},
            facecolor="#0d1117",
            dpi=self._dpi,
        )
        ax.set_global()
        _add_features(ax, 0.5 * scale)
        return fig, ax

    def _draw_annotations(
        self,
        ax: plt.Axes,
        lat, lon, field,
    ) -> None:
        """Draw all registered map annotations (marker + text) onto the axes."""
        if not self._annotations:
            return
 
        scale = _font_scale(self._dpi)
 
        for ann in self._annotations:
            lat_a, lon_a = ann["pos"]
            d_lon, d_lat = ann.get("text_offset", (0.0, 0.8))
 
            # ── resolve label text ────────────────────────────────────
            if ann["interpolate"] and ("%" in ann["text_base"]):
                val = _interp_field_value(lat, lon, field, ann["pos"])
                try:
                    text = ann["text_base"] % val
                except TypeError:
                    text = ann["text_base"]
            else:
                text = ann["text_base"]
 
            # ── marker at the exact geographic position ───────────────
            mk = ann.get("marker", "o")
            if mk is not None:
                mk_color = ann.get("marker_color") or ann["color"]
                mk_size  = ann.get("marker_size", 6.0) * scale
 
                ax.plot(
                    lon_a, lat_a,
                    marker          = mk,
                    markersize      = mk_size,
                    color           = mk_color,
                    markeredgecolor = ann.get("marker_edge_color", "#0d1117"),
                    markeredgewidth = ann.get("marker_edge_width", 0.8) * scale,
                    alpha           = ann.get("marker_alpha", 1.0),
                    transform       = ccrs.PlateCarree(),
                    zorder          = ann["zorder"],
                    linestyle       = "none",
                )
 
            # ── text label (offset from the marker) ───────────────────
            bbox_props = None
            if ann["bbox"]:
                bbox_props = dict(
                    boxstyle  = "round,pad=0.3",
                    facecolor = ann["bbox_color"],
                    alpha     = ann["bbox_alpha"],
                    edgecolor = "none",
                )
 
            ax.annotate(
                text,
                xy       = (lon_a + d_lon, lat_a + d_lat),
                xycoords = ccrs.PlateCarree()._as_mpl_transform(ax),
                fontsize = round(ann["size"] * scale, 1),
                color    = ann["color"],
                fontweight = ann["weight"],
                alpha    = ann["alpha"],
                bbox     = bbox_props,
                ha       = "center",
                va       = "center",
                zorder   = ann["zorder"],
            )



    def _draw_field(
        self,
        fig: plt.Figure,
        ax: plt.Axes,
        lat, lon, field, time_val,
    ) -> None:
        """
        Draw pcolormesh + contours + map annotations + colorbar + axis titles
        onto the axes, then layer the figure-level overlays:
          • top-right  : info box (key / cycle / date)
          • bottom-right: data source credit
          • bottom-centre: author label (if set)
        """
        scale = _font_scale(self._dpi)
        norm  = BoundaryNorm(self._levels, ncolors=self._cmap.N, clip=True)

        cf = ax.pcolormesh(
            lon, lat, field,
            cmap=self._cmap, norm=norm,
            transform=ccrs.PlateCarree(), zorder=1,
        )
        ax.contour(
            lon[::3], lat[::3], field[::3, ::3],
            levels=self._levels[::5],
            colors="white", linewidths=0.25 * scale, alpha=0.4,
            transform=ccrs.PlateCarree(), zorder=2,
        )

        # ── map annotations (cities, custom labels, etc.) ─────────────
        self._draw_annotations(ax, lat, lon, field)

        _colorbar(fig, cf, ax, self._cbar_label, scale=scale)

        # ── axis titles ───────────────────────────────────────────────
        if self._title_template is not None:
            date_str   = _format_date(time_val, self._title_date_style)
            main_title = self._title_template.replace("%S", date_str)
            _title(ax, main_title, scale=scale)
        else:
            _title(ax, self._plot_title, _run_label(time_val), scale=scale)

        # ── figure-level overlays ─────────────────────────────────────

        # top-right info box: key / cycle / date
        _, cycle    = _gfs_meta(self._ds, self._var)
        date_str_box = self._ds['time'][0].dt.strftime("%Y-%m-%d").item()
        
        _draw_info_box(fig, self._var, cycle, date_str_box, scale=scale)

        # bottom-right: data source credit  (GFS 0.25° / NASA · NOAA)
        _draw_data_credit(fig, scale=scale)

        # bottom-centre: optional author name
        # bottom-centre: optional author name
        if self._author:
            _draw_author(fig, self._author, scale=scale, **self._author_kwargs)


    def _render_frame(self, tidx: int, fpath: str, central: tuple) -> None:
        """Render a single frame and save it to disk."""
        lat, lon, field, time_val = _get(
            self._ds, self._var, time_idx=tidx, step=self._step
        )
        fig, ax = self._build_axes(central)
        self._draw_field(fig, ax, lat, lon, field, time_val)
        fig.tight_layout()
        fig.savefig(fpath, format="png", dpi=self._dpi)
        plt.close(fig)

    def _write_video(self, fdir: str, n_frames: int) -> None:
        """Assemble the video by reading frames from disk one at a time."""
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
        """Print a short summary of render settings before the loop starts."""
        w, h = self._figsize
        px_w = int(w * self._dpi)
        px_h = int(h * self._dpi)
        ann_count = len(self._annotations)
        print(
            f"Render: {n_frames} frames  |  {px_w}×{px_h} px  |  "
            f"{self._dpi} dpi  |  {self._fps} fps  |  "
            f"codec={self._codec}  quality={self._video_quality}  "
            f"annotations={ann_count}  →  {self._output}"
        )

    # ── public entry points ───────────────────────────────────────────────────

    def plot(
        self,
        time_idx: int = 0,
        central_point: tuple | None = None,
        save: str | None = None,
        show: bool = True,
    ) -> "OrthoAnimator":
        """
        Render a single static frame and either save it or show it interactively.

        Parameters
        ----------
        time_idx : int
            Time index to plot (default 0 = first time step).
        central_point : tuple, optional
            Override (lon, lat) for this plot only.
        save : str, optional
            File path to save the figure (e.g. "snapshot.png").
            If None, plt.show() is called instead.

        Examples
        --------
        anim.plot(time_idx=6)
        anim.plot(time_idx=0, central_point=(-60, -20), save="fig.png")
        """
        centre = central_point if central_point is not None else self._central_point
        lat, lon, field, time_val = _get(
            self._ds, self._var, time_idx=time_idx, step=self._step
        )
        fig, ax = self._build_axes(centre)
        self._draw_field(fig, ax, lat, lon, field, time_val)
        fig.tight_layout()

        if save:
            fig.savefig(save, dpi=self._dpi, bbox_inches="tight")
            w, h = self._figsize
            print(f"Saved: {save}  ({int(w * self._dpi)}×{int(h * self._dpi)} px @ {self._dpi} dpi)")
            plt.close(fig)
        else:
            plt.show()
        if show:
            plt.show()
        return self

    def animate(self) -> "OrthoAnimator":
        """
        Step 1 — render missing frames to disk.
        Step 2 — assemble the video from the PNG files.
        """
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir     = _frames_dir(self._var, run_date, cycle)
        n_frames = len(self._ds[self._var].time)
        stop     = self._resolve_stop_frame(n_frames)

        self._print_render_info(n_frames)

        for tidx in range(n_frames):
            fpath   = _frame_path(fdir, tidx)
            central = self._rotation_at(tidx, stop)

            if not os.path.exists(fpath):
                self._render_frame(tidx, fpath, central)

            print(f"  frame {tidx + 1}/{n_frames}  →  {fpath}", end="\r")

        print()
        self._write_video(fdir, n_frames)
        print(f"Saved: {self._output}")
        return self