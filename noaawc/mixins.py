from __future__ import annotations

from noaawc.utils import _get_field_full, _gfs_meta, _frames_dir
import matplotlib.pyplot as plt


class _RotatingAnimatorMixin:
    _LAT_LIMIT: float = 89.9

    def _rotation_init(self) -> None:
        self._lon_start: float | None = None
        self._lat_start: float | None = None
        self._lon_end: float | None = None
        self._lat_end: float | None = None
        self._stop_frame: int | None = None
        self._stop_fraction: float | None = None

    def _default_camera(self) -> tuple[float, float]:
        raise NotImplementedError

    def set_rotation(
        self,
        lon_start: float,
        lon_end: float,
        lat_start: float | None = None,
        lat_end: float | None = None,
    ):
        def _clamp(v: float, name: str) -> float:
            c = max(-self._LAT_LIMIT, min(self._LAT_LIMIT, v))
            if abs(c - v) > 0.01:
                print(
                    f"[{self.__class__.__name__}] WARNING: {name}={v:.4f}° "
                    f"clamped to {c:.4f}°."
                )
            return c

        lon0, lat0 = self._default_camera()
        self._lon_start = float(lon_start)
        self._lon_end = float(lon_end)
        self._lat_start = _clamp(float(lat_start) if lat_start is not None else lat0, "lat_start")
        self._lat_end = _clamp(float(lat_end) if lat_end is not None else lat0, "lat_end")
        return self

    def set_rotation_stop(self, frame: int | None = None, fraction: float | None = None):
        if frame is not None and fraction is not None:
            raise ValueError("Provide 'frame' or 'fraction', not both.")
        if fraction is not None:
            if not 0.0 < fraction < 1.0:
                raise ValueError("fraction must be strictly between 0 and 1.")
            self._stop_fraction = float(fraction)
            self._stop_frame = None
        else:
            self._stop_frame = frame
            self._stop_fraction = None
        return self

    def _resolve_stop_frame(self, n: int) -> int:
        if self._stop_fraction is not None:
            return max(1, int(round(self._stop_fraction * n)))
        return self._stop_frame if self._stop_frame is not None else n

    def _camera_at(self, tidx: int, stop: int) -> tuple[float, float]:
        if self._lon_start is None:
            lon, lat = self._default_camera()
            return (lon, max(-self._LAT_LIMIT, min(self._LAT_LIMIT, lat)))
        if tidx >= stop:
            lon, lat = float(self._lon_end), float(self._lat_end)  # type: ignore[arg-type]
        else:
            t = tidx / stop
            lon = self._lon_start + t * (self._lon_end - self._lon_start)  # type: ignore[operator]
            lat = self._lat_start + t * (self._lat_end - self._lat_start)  # type: ignore[operator]
        return (float(lon), max(-self._LAT_LIMIT, min(self._LAT_LIMIT, float(lat))))


class _FlatAnimatorMixin:
    _NAMED_REGIONS: dict[str, dict] = {}
    _LAT_MAX: float = 85.0

    def set_region(
        self,
        region=None,
        *,
        toplat: float | None = None,
        bottomlat: float | None = None,
        leftlon: float | None = None,
        rightlon: float | None = None,
        central_longitude: float = 0.0,
    ):
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
            if toplat is None or bottomlat is None or leftlon is None or rightlon is None:
                raise ValueError("Provide all four: toplat, bottomlat, leftlon, rightlon.")
            self._region = {
                "toplat": float(toplat),
                "bottomlat": float(bottomlat),
                "leftlon": float(leftlon),
                "rightlon": float(rightlon),
                "central_longitude": float(central_longitude),
            }
        return self

    def set_zoom(self, zoom: float, pos: tuple[float, float]):
        if zoom < 1:
            raise ValueError("zoom must be >= 1.")
        lat, lon = pos
        half = 90.0 / zoom
        self._region = {
            "toplat": min(self._LAT_MAX, lat + half),
            "bottomlat": max(-self._LAT_MAX, lat - half),
            "leftlon": lon - half,
            "rightlon": lon + half,
            "central_longitude": lon,
        }
        return self

    def set_ocean(self, visible: bool = True):
        self._show_ocean = visible
        return self

    def set_grid(self, visible: bool = True):
        self._show_grid = visible
        return self

    def _get(self, time_idx: int):
        return _get_field_full(self._ds, self._var, time_idx, self._step)

    def _overlays_ax_anchored(self) -> bool:
        return True

    def _log_region_info(self) -> str:
        r = self._region
        return (
            f"lat [{r['bottomlat']:.1f}…{r['toplat']:.1f}] "
            f"lon [{r['leftlon']:.1f}…{r['rightlon']:.1f}]"
        )

    def plot(self, time_idx: int = 0, save: str | None = None, show: bool = True):
        lat, lon, field, time_val = self._get(time_idx)
        fig, ax = self._build_axes()
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

    def animate(self):
        run_date, cycle = _gfs_meta(self._ds, self._var)
        fdir = _frames_dir(f"{self._frames_prefix()}_{self._var}", run_date, cycle)
        n_frames = len(self._ds[self._var].time)
        self._log_animate_header(n_frames, extra=self._log_region_info())
        self._animate_loop(fdir, n_frames)
        return self
