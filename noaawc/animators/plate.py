from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs

from noaawc.presets import QUALITY_PRESETS_WIDE
from noaawc.base import _AnimatorBase
from noaawc.mixins import _FlatAnimatorMixin
from noaawc.utils import _font_scale
from noaawc.geo import _add_features

_PC_DEFAULT_REGION = {
    "toplat": 5.0,
    "bottomlat": -35.0,
    "leftlon": -82.0,
    "rightlon": -30.0,
    "central_longitude": 0.0,
}


class PlateCarreeAnimator(_FlatAnimatorMixin, _AnimatorBase):
    """PlateCarree (equirectangular) flat map animator."""

    _QUALITY_PRESETS = QUALITY_PRESETS_WIDE
    _OUTPUT_DEFAULT = "output_plate_carree.mp4"
    _FPS_DEFAULT = 6
    _STEP_DEFAULT = 1
    _DPI_DEFAULT = 120
    _FIGSIZE_DEFAULT = (16.0, 9.0)
    _CODEC_DEFAULT = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8
    _LAT_MAX = 80.0

    _NAMED_REGIONS: dict[str, dict] = {
        "south_america": {"toplat": 15.0, "bottomlat": -60.0, "leftlon": -85.0, "rightlon": -30.0, "central_longitude": 0.0},
        "brazil":        {"toplat":  6.0, "bottomlat": -34.0, "leftlon": -75.0, "rightlon": -28.0, "central_longitude": 0.0},
        "northeast_br":  {"toplat": -1.0, "bottomlat": -18.0, "leftlon": -47.0, "rightlon": -34.0, "central_longitude": 0.0},
        "north_br":      {"toplat":  5.5, "bottomlat":  -5.0, "leftlon": -74.0, "rightlon": -44.0, "central_longitude": 0.0},
        "southeast_br":  {"toplat": -14.0, "bottomlat": -25.5, "leftlon": -53.0, "rightlon": -39.0, "central_longitude": 0.0},
        "south_br":      {"toplat": -22.0, "bottomlat": -34.0, "leftlon": -58.0, "rightlon": -47.0, "central_longitude": 0.0},
        "global":        {"toplat": 85.0, "bottomlat": -85.0, "leftlon": -179.9, "rightlon": 179.9, "central_longitude": 0.0},
    }

    def __init__(self, ds, var: str):
        self._region: dict = dict(_PC_DEFAULT_REGION)
        self._show_ocean: bool = True
        self._show_grid: bool = True
        self._base_init(ds, var)

    def _frames_prefix(self) -> str:
        return "pc"

    def _build_axes(self) -> tuple[plt.Figure, plt.Axes]:
        r = self._region
        scale = _font_scale(self._dpi)
        safe_top = max(-self._LAT_MAX, min(self._LAT_MAX, r["toplat"]))
        safe_bot = max(-self._LAT_MAX, min(self._LAT_MAX, r["bottomlat"]))

        fig, ax = plt.subplots(
            figsize=self._figsize,
            subplot_kw={"projection": ccrs.PlateCarree()},
            facecolor="#0d1117",
            dpi=self._dpi,
        )
        ax.set_extent([r["leftlon"], r["rightlon"], safe_bot, safe_top], crs=ccrs.PlateCarree())
        _add_features(ax, lw=0.5 * scale, show_states=self._show_states, show_ocean=self._show_ocean)

        if self._show_grid:
            gl = ax.gridlines(
                crs=ccrs.PlateCarree(), draw_labels=True,
                linewidth=0.3 * scale, color="#14181c", alpha=0.8,
                linestyle="--", zorder=2,
            )
            gl.top_labels = False
            gl.right_labels = False
            gl.xlocator = mticker.MultipleLocator(10)
            gl.ylocator = mticker.MultipleLocator(10)
            gl.xlabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}
            gl.ylabel_style = {"size": round(6 * scale, 1), "color": "#8b949e"}

        return fig, ax
