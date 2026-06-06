# mypy: disable-error-code="attr-defined"
from __future__ import annotations

import copy

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from matplotlib.colors import BoundaryNorm

from noaawc.presets import QUALITY_PRESETS_SQUARE
from noaawc.base import _AnimatorBase
from noaawc.mixins import _RotatingAnimatorMixin
from noaawc.utils import (
    _get_field_full,
    _gfs_meta,
    _frames_dir,
    _font_scale,
    _remove_contours,
)
from noaawc.geo import _add_features
from noaawc.variables import NO_CONTOUR_VARS

GEOSTATIONARY_HEIGHT: float = 35_786_000.0
EARTH_RADIUS: float = 6_371_229.0


def _visible_radius_deg(satellite_height: float) -> float:
    R, h = EARTH_RADIUS, satellite_height
    return float(np.degrees(np.arccos(R / (R + h)))) - 1.0


class NearsidePerspectiveAnimator(_RotatingAnimatorMixin, _AnimatorBase):
    """Nearside Perspective (satellite-view) projection animator."""

    _QUALITY_PRESETS = QUALITY_PRESETS_SQUARE
    _OUTPUT_DEFAULT = "output_nearside.mp4"
    _FPS_DEFAULT = 6
    _STEP_DEFAULT = 1
    _DPI_DEFAULT = 120
    _FIGSIZE_DEFAULT = (10.0, 10.0)
    _CODEC_DEFAULT = "libx264"
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
        self._lon: float = float(lon)
        self._lat: float = float(lat)
        self._height: float = float(satellite_height)
        self._rotation_init()
        self._base_init(ds, var)

    def _default_camera(self) -> tuple[float, float]:
        return (self._lon, self._lat)

    def set_view(
        self, lon: float, lat: float, satellite_height: float | None = None
    ) -> "NearsidePerspectiveAnimator":
        self._lon = float(lon)
        self._lat = float(lat)
        if satellite_height is not None:
            self._height = float(satellite_height)
        return self

    def set_satellite_height(self, height: float) -> "NearsidePerspectiveAnimator":
        if height <= 0:
            raise ValueError("satellite_height must be > 0.")
        self._height = float(height)
        return self

    def _frames_prefix(self) -> str:
        return f"ns_{self._var}"

    def _get(self, time_idx: int):
        return _get_field_full(self._ds, self._var, time_idx, self._step)

    def _build_axes(self, central: tuple | None = None) -> tuple[plt.Figure, plt.Axes]:
        if central is None:
            central = (self._lon, self._lat)
        lon_c, lat_c = central
        proj = ccrs.NearsidePerspective(
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

    def _make_norm_and_cmap(self):
        cmap = copy.copy(self._cmap)
        cmap.set_under(alpha=0)
        cmap.set_bad(alpha=0)
        norm = BoundaryNorm(self._levels, ncolors=cmap.N, clip=False)
        return norm, cmap

    def _draw_contour(self, ax, lat, lon, field) -> None:
        if self._var in NO_CONTOUR_VARS:
            return
        scale = _font_scale(self._dpi)
        try:
            ax.contour(
                lon[::3],
                lat[::3],
                field[::3, ::3],
                levels=self._levels[::5],
                colors="white",
                linewidths=0.25 * scale,
                alpha=0.4,
                transform=ccrs.PlateCarree(),
                zorder=2,
            )
        except TypeError:
            _remove_contours(ax)

    def plot(
        self,
        time_idx: int = 0,
        central: tuple[float, float] | None = None,
        save: str | None = None,
        show: bool = True,
    ) -> "NearsidePerspectiveAnimator":
        cam = central if central is not None else (self._lon, self._lat)
        lat, lon, field, time_val = self._get(time_idx)
        fig, ax = self._build_axes(central=cam)
        self._draw_field(fig, ax, lat, lon, field, time_val)
        fig.tight_layout()
        if save:
            fig.savefig(save, dpi=self._dpi)
            w, h = self._figsize
            print(
                f"Saved: {save}  ({int(w * self._dpi)}×{int(h * self._dpi)} px @ {self._dpi} dpi)"
            )
            plt.close(fig)
        if show:
            plt.show()
        return self

    def animate(self) -> "NearsidePerspectiveAnimator":
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir = _frames_dir(f"ns_{self._var}", run_date, cycle)
        n_frames = len(self._ds[self._var].time)
        stop = self._resolve_stop_frame(n_frames)
        r_deg = _visible_radius_deg(self._height)
        self._log_animate_header(
            n_frames,
            extra=f"height={self._height / 1000:.0f} km | visible≈{r_deg:.1f}°",
        )
        self._animate_loop(
            fdir,
            n_frames,
            build_kw_for=lambda tidx: {"central": self._camera_at(tidx, stop)},
        )
        return self
