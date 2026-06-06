# mypy: disable-error-code="attr-defined"
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs

from noaawc.presets import QUALITY_PRESETS_WIDE
from noaawc.base import _AnimatorBase
from noaawc.mixins import _FlatAnimatorMixin
from noaawc.utils import _font_scale
from noaawc.geo import _add_features

_ROB_DEFAULT_REGION = {
    "toplat": 85.0,
    "bottomlat": -85.0,
    "leftlon": -180.0,
    "rightlon": 180.0,
    "central_longitude": 0.0,
}


class RobinsonAnimator(_FlatAnimatorMixin, _AnimatorBase):
    """Robinson pseudo-cylindrical projection animator."""

    _QUALITY_PRESETS = QUALITY_PRESETS_WIDE
    _OUTPUT_DEFAULT = "output_robinson.mp4"
    _FPS_DEFAULT = 6
    _STEP_DEFAULT = 1
    _DPI_DEFAULT = 120
    _FIGSIZE_DEFAULT = (16.0, 9.0)
    _CODEC_DEFAULT = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8
    _LAT_MAX = 85.0

    _NAMED_REGIONS: dict[str, dict] = {
        "global": {
            "toplat": 85.0,
            "bottomlat": -85.0,
            "leftlon": -180.0,
            "rightlon": 180.0,
            "central_longitude": 0.0,
        },
        "north_hemisphere": {
            "toplat": 85.0,
            "bottomlat": 0.0,
            "leftlon": -180.0,
            "rightlon": 180.0,
            "central_longitude": 0.0,
        },
        "south_hemisphere": {
            "toplat": 0.0,
            "bottomlat": -85.0,
            "leftlon": -180.0,
            "rightlon": 180.0,
            "central_longitude": 0.0,
        },
        "atlantic": {
            "toplat": 75.0,
            "bottomlat": -60.0,
            "leftlon": -100.0,
            "rightlon": 20.0,
            "central_longitude": -40.0,
        },
        "pacific": {
            "toplat": 70.0,
            "bottomlat": -70.0,
            "leftlon": 100.0,
            "rightlon": 290.0,
            "central_longitude": 180.0,
        },
        "south_america": {
            "toplat": 15.0,
            "bottomlat": -60.0,
            "leftlon": -85.0,
            "rightlon": -30.0,
            "central_longitude": -57.5,
        },
        "africa": {
            "toplat": 40.0,
            "bottomlat": -40.0,
            "leftlon": -20.0,
            "rightlon": 55.0,
            "central_longitude": 17.5,
        },
        "europe_asia": {
            "toplat": 75.0,
            "bottomlat": 10.0,
            "leftlon": -30.0,
            "rightlon": 150.0,
            "central_longitude": 60.0,
        },
        "north_america": {
            "toplat": 80.0,
            "bottomlat": 5.0,
            "leftlon": -170.0,
            "rightlon": -50.0,
            "central_longitude": -100.0,
        },
        "asia": {
            "toplat": 75.0,
            "bottomlat": -10.0,
            "leftlon": 40.0,
            "rightlon": 150.0,
            "central_longitude": 95.0,
        },
    }

    def __init__(self, ds, var: str):
        self._region: dict = dict(_ROB_DEFAULT_REGION)
        self._show_ocean: bool = True
        self._show_grid: bool = True
        self._base_init(ds, var)

    def _frames_prefix(self) -> str:
        return "rob"

    def _build_axes(self) -> tuple[plt.Figure, plt.Axes]:
        r = self._region
        c_lon = r.get("central_longitude", 0.0)
        scale = _font_scale(self._dpi)
        safe_top = max(-self._LAT_MAX, min(self._LAT_MAX, r["toplat"]))
        safe_bot = max(-self._LAT_MAX, min(self._LAT_MAX, r["bottomlat"]))

        fig, ax = plt.subplots(
            figsize=self._figsize,
            subplot_kw={"projection": ccrs.Robinson(central_longitude=c_lon)},
            facecolor="#0d1117",
            dpi=self._dpi,
        )
        ax.set_extent(
            [r["leftlon"], r["rightlon"], safe_bot, safe_top], crs=ccrs.PlateCarree()
        )
        _add_features(
            ax,
            lw=0.5 * scale,
            show_states=self._show_states,
            show_ocean=self._show_ocean,
        )

        if self._show_grid:
            gl = ax.gridlines(
                crs=ccrs.PlateCarree(),
                draw_labels=False,
                linewidth=0.3 * scale,
                color="#14181c",
                alpha=0.8,
                linestyle="--",
                zorder=2,
            )
            gl.xlocator = mticker.MultipleLocator(30)
            gl.ylocator = mticker.MultipleLocator(30)

        return fig, ax
