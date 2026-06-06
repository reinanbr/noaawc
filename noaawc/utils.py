from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from noaawc.variables import VARIABLE_PRESETS


_MONTHS: dict[str, list[str]] = {
    "en": [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ],
    "pt-br": [
        "Jan",
        "Fev",
        "Mar",
        "Abr",
        "Mai",
        "Jun",
        "Jul",
        "Ago",
        "Set",
        "Out",
        "Nov",
        "Dez",
    ],
    "es": [
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    ],
    "fr": [
        "Jan",
        "Fév",
        "Mar",
        "Avr",
        "Mai",
        "Jun",
        "Jul",
        "Aoû",
        "Sep",
        "Oct",
        "Nov",
        "Déc",
    ],
}


def _remove_contours(ax: plt.Axes) -> None:
    for coll in list(ax.collections):
        if isinstance(coll, LineCollection):
            coll.remove()


def _format_date(time_val, date_style: str = "en") -> str:
    if hasattr(time_val, "astype"):
        ts = int(time_val.astype("datetime64[s]").astype("int64"))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif isinstance(time_val, datetime):
        dt = time_val
    else:
        dt = datetime.fromtimestamp(float(time_val), tz=timezone.utc)
    months = _MONTHS.get(date_style.lower(), _MONTHS["en"])
    return (
        f"{dt.day:02d} {months[dt.month - 1]} {dt.year} {dt.hour:02d}:{dt.minute:02d}"
    )


def _font_scale(dpi: int, base_dpi: int = 120) -> float:
    return (dpi / base_dpi) ** 0.5


def _gfs_meta(ds, var: str) -> tuple[str, str]:
    return str(ds.attrs.get("run_date", "unknown")), str(ds.attrs.get("cycle", "00z"))


def _frames_dir(var: str, run_date: str, cycle: str) -> str:
    path = os.path.join("frames", f"{var}_{run_date}_{cycle}")
    os.makedirs(path, exist_ok=True)
    return path


def _frame_path(fdir: str, tidx: int) -> str:
    return os.path.join(fdir, f"frame_{tidx:04d}.png")


def _interp_field_value(lat_arr, lon_arr, field, pos: tuple) -> float:
    lat_target, lon_target = pos
    i = int(np.argmin(np.abs(lat_arr - lat_target)))
    j = int(np.argmin(np.abs(lon_arr - lon_target)))
    return float(field[i, j])


def _run_label(time_val) -> str:
    return f"GFS — {time_val}"


def _get_field_full(ds, var: str, time_idx: int, step: int = 1):
    """Return (lats, lons, data, time_val) with convert + mask_below applied."""
    da = ds[var][time_idx]
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


def _get_field(ds, var: str, time_idx: int = 0, step: int = 1):
    da = ds[var][time_idx]
    return (
        da.latitude.values[::step],
        da.longitude.values[::step],
        da.values[::step, ::step],
        da.time.values,
    )
