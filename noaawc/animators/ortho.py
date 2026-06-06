from __future__ import annotations

import matplotlib.pyplot as plt
import cartopy.crs as ccrs

from noaawc.presets import QUALITY_PRESETS_SQUARE
from noaawc.base import _AnimatorBase
from noaawc.mixins import _RotatingAnimatorMixin
from noaawc.utils import _get_field_full, _gfs_meta, _frames_dir, _font_scale
from noaawc.geo import _add_features


class OrthoAnimator(_RotatingAnimatorMixin, _AnimatorBase):
    """Orthographic (globe) projection animator."""

    _QUALITY_PRESETS = QUALITY_PRESETS_SQUARE
    _OUTPUT_DEFAULT = "output_ortho.mp4"
    _FPS_DEFAULT = 6
    _STEP_DEFAULT = 1
    _DPI_DEFAULT = 120
    _FIGSIZE_DEFAULT = (8.0, 8.0)
    _CODEC_DEFAULT = "libx264"
    _VIDEO_QUALITY_DEFAULT = 8

    def __init__(self, ds, var: str, central_point: tuple[float, float] = (-45.0, -15.0)):
        self._central_point = (float(central_point[0]), float(central_point[1]))
        self._zoom: float = 1.0
        self._rotation_init()
        self._base_init(ds, var)

    def _default_camera(self) -> tuple[float, float]:
        return self._central_point

    def set_view(self, lon: float, lat: float, zoom: float | None = None):
        self._central_point = (float(lon), float(lat))
        if zoom is not None:
            if zoom < 1:
                raise ValueError("zoom must be >= 1.")
            self._zoom = float(zoom)
        return self

    def set_zoom(self, zoom: float):
        if zoom < 1:
            raise ValueError("zoom must be >= 1.")
        self._zoom = float(zoom)
        return self

    def _frames_prefix(self) -> str:
        return self._var

    def _get(self, time_idx: int):
        return _get_field_full(self._ds, self._var, time_idx, self._step)

    def _build_axes(self, central: tuple | None = None) -> tuple[plt.Figure, plt.Axes]:
        if central is None:
            central = self._central_point
        proj = ccrs.Orthographic(*central)
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
            ax.set_extent([lon_c - r, lon_c + r, lat_c - r, lat_c + r], crs=ccrs.PlateCarree())
        _add_features(ax, lw=0.5 * scale, show_states=self._show_states)
        return fig, ax

    def plot(
        self,
        time_idx: int = 0,
        central_point: tuple | None = None,
        save: str | None = None,
        show: bool = True,
    ) -> "OrthoAnimator":
        centre = central_point if central_point is not None else self._central_point
        lat, lon, field, time_val = self._get(time_idx)
        fig, ax = self._build_axes(central=centre)
        self._draw_field(fig, ax, lat, lon, field, time_val)
        fig.tight_layout()
        if save:
            fig.savefig(save, dpi=self._dpi, bbox_inches="tight")
            w, h = self._figsize
            print(f"Saved: {save}  ({int(w * self._dpi)}×{int(h * self._dpi)} px @ {self._dpi} dpi)")
            plt.close(fig)
        if show:
            plt.show()
        return self

    def animate(self) -> "OrthoAnimator":
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir = _frames_dir(self._var, run_date, cycle)
        n_frames = len(self._ds[self._var].time)
        stop = self._resolve_stop_frame(n_frames)
        self._log_animate_header(n_frames)
        self._animate_loop(
            fdir, n_frames,
            build_kw_for=lambda tidx: {"central": self._camera_at(tidx, stop)},
        )
        return self
