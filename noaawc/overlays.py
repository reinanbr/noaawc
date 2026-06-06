from __future__ import annotations

import re
from typing import Any, cast

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

from noaawc.variables import VARIABLES_INFO
from noaawc.utils import _font_scale, _interp_field_value


_CBAR_BOTTOM_Y: float = 0.10
_FMT_RE = re.compile(r"%[-+0-9*.]*[diouxXeEfFgGcrs]")


def _colorbar(
    fig: plt.Figure,
    cf,
    ax: plt.Axes,
    label: str,
    orientation: str = "horizontal",
    scale: float = 1.0,
) -> None:
    cb = fig.colorbar(
        cf, ax=ax, orientation=orientation, pad=0.03, fraction=0.03, shrink=0.85
    )
    cb.set_label(label, fontsize=round(8 * scale, 1), color="#8b949e")
    cb.ax.tick_params(labelsize=round(7 * scale, 1), colors="#8b949e")
    cast(Any, cb.outline).set_edgecolor("#30363d")


def _title(ax: plt.Axes, main: str, sub: str = "", scale: float = 1.0) -> None:
    ax.set_title(
        main,
        fontsize=round(10 * scale, 1),
        fontweight="bold",
        color="#e6edf3",
        loc="left",
        pad=6 * scale,
    )
    if sub:
        ax.set_title(
            sub,
            fontsize=round(7 * scale, 1),
            color="#8b949e",
            loc="right",
            pad=6 * scale,
        )


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
    lines = [
        f"key: {var_key} - {VARIABLES_INFO.get(var_key, {}).get('long_name', var_key)}",
        f"Date Cycle: {date_str} {cycle}",
    ]
    props: dict[str, Any] = dict(
        ha="right",
        va="top",
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
    props: dict[str, Any] = dict(
        ha="right",
        va="bottom",
        fontsize=round(6.5 * scale, 1),
        color="#8b949e",
        fontweight="bold",
        fontfamily="monospace",
        linespacing=1.45,
        zorder=10,
    )
    if ax is not None:
        ax.text(0.995, 0.008, "GFS 0.25°\nNASA / NOAA", transform=ax.transAxes, **props)
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
        x_pos,
        y_pos,
        author,
        ha=ha,
        va=va,
        fontsize=round(fontsize * scale, 1),
        color=color,
        fontweight=fontweight,
        fontfamily=fontfamily,
        alpha=alpha,
        bbox=bbox_props,
        zorder=10,
    )


def _author_above_cbar(
    fig: plt.Figure,
    text: str,
    scale: float = 1.0,
    kw: dict | None = None,
) -> None:
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

    font_h_frac = (kw.get("fontsize", 8.5) * scale * 1.6) / (
        fig.get_figheight() * fig.dpi
    )
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


def _draw_annotations_on(
    ax: plt.Axes, lat, lon, field, annotations: list[dict], dpi: int
) -> None:
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
                lon_a,
                lat_a,
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
