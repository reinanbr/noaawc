# mypy: disable-error-code="attr-defined,arg-type,operator,no-redef"
from __future__ import annotations

import copy
from typing import Any

import os

import imageio
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from matplotlib.colors import BoundaryNorm

from noaawc.presets import QUALITY_PRESETS_SQUARE
from noaawc.variables import VARIABLE_PRESETS, NO_CONTOUR_VARS
from noaawc.utils import (
    _font_scale,
    _format_date,
    _gfs_meta,
    _frame_path,
    _run_label,
)
from noaawc.overlays import (
    _colorbar,
    _title,
    _draw_info_box,
    _draw_data_credit,
    _draw_author,
    _draw_annotations_on,
)

import noaawc.theme  # noqa: F401 — applies dark rcParams as side effect


class _AnimatorBase:
    _QUALITY_PRESETS: dict = QUALITY_PRESETS_SQUARE

    def _base_init(self, ds, var: str) -> None:
        self._ds = ds
        self._var = var

        self._output = self._OUTPUT_DEFAULT  # type: ignore[attr-defined]
        self._fps = self._FPS_DEFAULT  # type: ignore[attr-defined]
        self._step = self._STEP_DEFAULT  # type: ignore[attr-defined]
        self._dpi = self._DPI_DEFAULT  # type: ignore[attr-defined]
        self._figsize: tuple[float, float] = self._FIGSIZE_DEFAULT  # type: ignore[attr-defined]
        self._codec = self._CODEC_DEFAULT  # type: ignore[attr-defined]
        self._video_quality = self._VIDEO_QUALITY_DEFAULT  # type: ignore[attr-defined]

        self._annotations: list[dict] = []
        self._title_template: str | None = None
        self._title_date_style: str = "en"
        self._show_states: bool = False
        self._author: str = ""
        self._author_kwargs: dict[str, Any] = {}

        self._apply_variable_preset(var, silent=False)

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
        self._cmap = p["cmap"]
        self._levels = np.asarray(p["levels"])
        self._cbar_label = p["cbar_label"]
        self._plot_title = p["plot_title"]

    def use_variable_defaults(self, var: str | None = None):
        self._apply_variable_preset(var if var is not None else self._var, silent=False)
        return self

    # ── output setters ────────────────────────────────────────────────────────

    def set_output(self, path: str):
        self._output = path
        return self

    def set_fps(self, fps: int):
        self._fps = fps
        return self

    def set_step(self, step: int):
        self._step = step
        return self

    def set_dpi(self, dpi: int):
        self._dpi = dpi
        return self

    def set_figsize(self, w: float, h: float):
        self._figsize = (w, h)
        return self

    def set_codec(self, codec: str):
        self._codec = codec
        return self

    def set_video_quality(self, quality: int):
        if not 0 <= quality <= 10:
            raise ValueError("quality must be between 0 and 10.")
        self._video_quality = quality
        return self

    def set_quality(self, preset: str):
        if preset not in self._QUALITY_PRESETS:
            opts = ", ".join(f'"{k}"' for k in self._QUALITY_PRESETS)
            raise ValueError(f"Unknown preset '{preset}'. Choose from: {opts}")
        p = self._QUALITY_PRESETS[preset]
        self._dpi = p["dpi"]
        self._figsize = p["figsize"]
        self._fps = p["fps"]
        self._codec = p["codec"]
        self._video_quality = p["quality"]
        print(f"Quality preset '{preset}': {p['description']}")
        return self

    # ── colormap / levels setters ─────────────────────────────────────────────

    def set_cmap(self, cmap):
        self._cmap = plt.get_cmap(cmap) if isinstance(cmap, str) else cmap
        return self

    def set_levels(self, levels):
        self._levels = np.asarray(levels)
        return self

    def set_cbar_label(self, label: str):
        self._cbar_label = label
        return self

    def set_plot_title(self, title: str):
        self._plot_title = title
        return self

    def set_title(self, template: str, date_style: str = "en"):
        self._title_template = template if template else None
        self._title_date_style = date_style
        return self

    # ── feature setters ───────────────────────────────────────────────────────

    def set_states(self, visible: bool = True):
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
        self._author = name.strip()
        if not x or not y:
            x, y = 0.4967, 0.1
        self._author_kwargs = dict(
            x=x, y=y, ha=ha, va=va, color=color, fontsize=fontsize,
            fontweight=fontweight, fontfamily=fontfamily, alpha=alpha,
            bbox=bbox, bbox_facecolor=bbox_facecolor,
            bbox_edgecolor=bbox_edgecolor, bbox_alpha=bbox_alpha, bbox_pad=bbox_pad,
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
        self._annotations.append(
            dict(
                text_base=text_base, pos=pos, size=size, color=color,
                weight=weight, alpha=alpha, bbox=bbox, bbox_color=bbox_color,
                bbox_alpha=bbox_alpha, interpolate=interpolate, zorder=zorder,
                marker=marker, marker_size=marker_size, marker_color=marker_color,
                marker_edge_color=marker_edge_color, marker_edge_width=marker_edge_width,
                marker_alpha=marker_alpha, text_offset=text_offset,
            )
        )
        return self

    def clear_annotations(self):
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

    # ── internal helpers ──────────────────────────────────────────────────────

    def _write_video(self, fdir: str, n_frames: int) -> None:
        writer_kwargs: dict = {"fps": self._fps}
        if self._output.endswith(".mp4"):
            writer_kwargs["codec"] = self._codec
            writer_kwargs["quality"] = self._video_quality
            if self._codec in ("libx265", "hevc"):
                writer_kwargs["output_params"] = ["-pix_fmt", "yuv420p"]
        with imageio.get_writer(self._output, **writer_kwargs) as writer:
            for tidx in range(n_frames):
                writer.append_data(imageio.imread(_frame_path(fdir, tidx)))

    def _resolve_title(self, ax: plt.Axes, time_val, scale: float) -> None:
        if self._title_template is not None:
            date_str = _format_date(time_val, self._title_date_style)
            main_title = self._title_template.replace("%S", date_str)
            _title(ax, main_title, scale=scale)
        else:
            _title(ax, self._plot_title, _run_label(time_val), scale=scale)

    def _draw_overlays(
        self,
        fig: plt.Figure,
        ax: plt.Axes,
        lat,
        lon,
        field,
        time_val,
        cf,
        *,
        ax_anchored: bool = False,
    ) -> None:
        scale = _font_scale(self._dpi)
        _, cycle = _gfs_meta(self._ds, self._var)
        date_str_box = self._ds["time"][0].dt.strftime("%Y-%m-%d").item()
        ax_ref = ax if ax_anchored else None

        _draw_annotations_on(ax, lat, lon, field, self._annotations, self._dpi)
        _colorbar(fig, cf, ax, self._cbar_label, scale=scale)
        self._resolve_title(ax, time_val, scale)
        _draw_info_box(fig, self._var, cycle, date_str_box, scale=scale, ax=ax_ref)
        _draw_data_credit(fig, scale=scale, ax=ax_ref)

        if self._author:
            _draw_author(fig, self._author, scale=scale, **self._author_kwargs)

    # ── abstract interface ────────────────────────────────────────────────────

    def _get(self, time_idx: int):
        raise NotImplementedError

    def _build_axes(self, *args, **kwargs) -> tuple[plt.Figure, plt.Axes]:
        raise NotImplementedError

    def _draw_field_extra(self, fig, ax, lat, lon, field, time_val, cf) -> None:
        pass

    def _frames_prefix(self) -> str:
        raise NotImplementedError

    # ── shared render pipeline ────────────────────────────────────────────────

    def _draw_field(self, fig, ax, lat, lon, field, time_val, _suppress_contours: bool = False, **build_kw) -> None:
        norm, cmap = self._make_norm_and_cmap()
        cf = ax.pcolormesh(
            lon, lat, field, cmap=cmap, norm=norm,
            transform=ccrs.PlateCarree(), zorder=1,
        )
        if not _suppress_contours:
            self._draw_contour(ax, lat, lon, field)
        self._draw_overlays(
            fig, ax, lat, lon, field, time_val, cf,
            ax_anchored=self._overlays_ax_anchored(),
        )

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
                lon[::3], lat[::3], field[::3, ::3],
                levels=self._levels[::5],
                colors="white",
                linewidths=0.25 * scale,
                alpha=0.4,
                transform=ccrs.PlateCarree(),
                zorder=2,
            )
        except TypeError:
            from noaawc.utils import _remove_contours
            _remove_contours(ax)

    def _overlays_ax_anchored(self) -> bool:
        return False

    def _render_frame(self, tidx: int, fpath: str, **build_kw) -> None:
        lat, lon, field, time_val = self._get(tidx)

        def _do_render(suppress_contours: bool) -> None:
            fig, ax = self._build_axes(**build_kw)
            try:
                self._draw_field(fig, ax, lat, lon, field, time_val, _suppress_contours=suppress_contours, **build_kw)
                fig.tight_layout()
                fig.savefig(fpath, format="png", dpi=self._dpi)
            finally:
                plt.close(fig)

        try:
            _do_render(suppress_contours=False)
        except TypeError:
            _do_render(suppress_contours=True)

    def _animate_loop(self, fdir: str, n_frames: int, build_kw_for: Any = None) -> None:
        for tidx in range(n_frames):
            fpath = _frame_path(fdir, tidx)
            if not os.path.exists(fpath):
                kw = build_kw_for(tidx) if build_kw_for is not None else {}
                self._render_frame(tidx, fpath, **kw)
            print(f"  frame {tidx + 1}/{n_frames}  →  {fpath}", end="\r")
        print()
        self._write_video(fdir, n_frames)
        print(f"Saved: {self._output}")

    def _log_animate_header(self, n_frames: int, extra: str = "") -> None:
        w, h = self._figsize
        print(
            f"[{self.__class__.__name__}] {n_frames} frames | "
            f"{int(w * self._dpi)}×{int(h * self._dpi)} px | "
            f"{self._dpi} dpi | {self._fps} fps"
            f"{(' | ' + extra) if extra else ''} | {self._output}"
        )
