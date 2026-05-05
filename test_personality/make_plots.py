"""
generate_examples.py
====================
Generates all static and animated example plots referenced in the noaawc README.

Output structure:
    docs/examples/
    ├── ortho_t2m.png
    ├── nearside_prmsl.png
    ├── plate_prate.png
    ├── robinson_t2m.png
    ├── plate_r2_ne_brazil.png
    ├── temperature_4k_preview.gif
    ├── cape_satellite_preview.gif
    ├── brazil_precipitation_preview.gif
    └── world_wind_speed_preview.gif

Usage:
    python generate_examples.py

    # Only statics (fast)
    python generate_examples.py --only-static

    # Only animations
    python generate_examples.py --only-animated

    # Single variable/mode
    python generate_examples.py --var t2m --mode ortho
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from noawclg import load
import numpy as np
from noaawc.weather import WeatherAnimator

# ── output directory ──────────────────────────────────────────────────────────

DOCS_DIR = Path("docs/examples")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# ── GFS data configuration ────────────────────────────────────────────────────

RUN_DATE      = "02/05/2026"
CYCLE         = "00"
STATIC_HOURS  = [0]
ANIM_HOURS    = list(range(0, 121, 3))

# ── helpers ───────────────────────────────────────────────────────────────────

def add_wind_speed(ds):
    """Attach derived 10-m wind speed to dataset in-place."""
    if "wspd10" not in ds and "u10" in ds and "v10" in ds:
        ds["wspd10"] = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)
    return ds


def skip_if_exists(path: Path) -> bool:
    if path.exists():
        print(f"  skip  (already exists)  →  {path}")
        return True
    return False


def report_error(label: str, exc: Exception) -> None:
    print(f"\n  ERROR [{label}]: {exc}")
    traceback.print_exc()
    print()


# ══════════════════════════════════════════════════════════════════════════════
# Static snapshots
# ══════════════════════════════════════════════════════════════════════════════

def static_ortho_t2m():
    """Orthographic globe — 2m temperature."""
    out = DOCS_DIR / "ortho_t2m.png"
    if skip_if_exists(out): return

    print("  [static] ortho / t2m ...")
    ds = load(RUN_DATE, CYCLE, ["t2m"], STATIC_HOURS)

    anim = WeatherAnimator(ds, "t2m", mode="ortho", central_point=(-50, -15))
    anim.set_quality("hd")
    anim.set_title("2m Temperature — %S")
    anim.set_author("@reinanbr_")
    anim.set_annotate("Juazeiro %.1f°C",  pos=(-9.4,  -40.5))
    anim.set_annotate("Fortaleza %.1f°C", pos=(-3.72, -38.54), color="#58a6ff")
    anim.set_annotate("Manaus %.1f°C",    pos=(-3.10, -60.02))
    anim.plot(time_idx=0, save=str(out), show=False)
    print(f"  saved  →  {out}")


def static_nearside_prmsl():
    """Nearside perspective — mean sea-level pressure."""
    out = DOCS_DIR / "nearside_prmsl.png"
    if skip_if_exists(out): return

    print("  [static] nearside / prmsl ...")
    ds = load(RUN_DATE, CYCLE, ["prmsl"], STATIC_HOURS)

    anim = WeatherAnimator(ds, "prmsl", mode="nearside",
                           lon=-50.0, lat=-15.0,
                           satellite_height=35_786_000)
    anim.set_quality("hd")
    anim.set_title("Sea-Level Pressure — %S")
    anim.set_author("@reinanbr_")
    anim.set_annotate("Recife %.0f hPa",    pos=(-8.05,  -34.88))
    anim.set_annotate("Brasília %.0f hPa",  pos=(-15.78, -47.93))
    anim.plot(time_idx=0, save=str(out), show=False)
    print(f"  saved  →  {out}")


def static_plate_prate():
    """PlateCarrée — precipitation rate, South America."""
    out = DOCS_DIR / "plate_prate.png"
    if skip_if_exists(out): return

    print("  [static] plate / prate ...")
    ds = load(RUN_DATE, CYCLE, ["prate"], STATIC_HOURS)

    anim = WeatherAnimator(ds, "prate", mode="plate")
    anim.set_region("south_america")
    anim.set_states()
    anim.set_quality("hd")
    anim.set_title("Precipitation Rate — %S")
    anim.set_author("@reinanbr_")
    anim.set_annotate("Brasília %.2f mm/h",  pos=(-15.78, -47.93))
    anim.set_annotate("Manaus %.2f mm/h",    pos=(-3.10,  -60.02))
    anim.set_annotate("Buenos Aires %.2f",   pos=(-34.61, -58.38))
    anim.plot(time_idx=0, save=str(out), show=False)
    print(f"  saved  →  {out}")


def static_robinson_t2m():
    """Robinson — global 2m temperature."""
    out = DOCS_DIR / "robinson_t2m.png"
    if skip_if_exists(out): return

    print("  [static] robinson / t2m ...")
    ds = load(RUN_DATE, CYCLE, ["t2m"], STATIC_HOURS)

    anim = WeatherAnimator(ds, "t2m", mode="robinson")
    anim.set_region("global")
    anim.set_quality("hd")
    anim.set_title("Global 2m Temperature — %S")
    anim.set_author("@reinanbr_")
    anim.set_annotate("New York %.0f°C",   pos=(40.71, -74.01))
    anim.set_annotate("London %.0f°C",     pos=(51.51,  -0.13))
    anim.set_annotate("São Paulo %.0f°C",  pos=(-23.55, -46.63))
    anim.set_annotate("Tokyo %.0f°C",      pos=(35.68,  139.69))
    anim.plot(time_idx=0, save=str(out), show=False)
    print(f"  saved  →  {out}")


def static_plate_r2_ne_brazil():
    """PlateCarrée — relative humidity, NE Brazil zoom."""
    out = DOCS_DIR / "plate_r2_ne_brazil.png"
    if skip_if_exists(out): return

    print("  [static] plate / r2 / NE Brazil ...")
    ds = load(RUN_DATE, CYCLE, ["r2"], STATIC_HOURS)

    anim = WeatherAnimator(ds, "r2", mode="plate")
    anim.set_zoom(zoom=4, pos=(-9.4, -40.5))
    anim.set_states()
    anim.set_quality("hd")
    anim.set_title("Relative Humidity — %S")
    anim.set_author("@reinanbr_")
    anim.set_annotate("Juazeiro %.0f%%",   pos=(-9.4,  -40.5), marker="*",
                      marker_color="#f7c948")
    anim.set_annotate("Fortaleza %.0f%%",  pos=(-3.72, -38.54))
    anim.set_annotate("Recife %.0f%%",     pos=(-8.05, -34.88))
    anim.plot(time_idx=0, save=str(out), show=False)
    print(f"  saved  →  {out}")


# ══════════════════════════════════════════════════════════════════════════════
# Animated videos (exported as GIF previews for the README)
# ══════════════════════════════════════════════════════════════════════════════

def anim_temperature_4k():
    """4K rotating globe — 2m temperature."""
    out = DOCS_DIR / "temperature_4k_preview.gif"
    if skip_if_exists(out): return

    print("  [anim] ortho / t2m / 4K rotating ...")
    ds = load(RUN_DATE, CYCLE, ["t2m"], ANIM_HOURS)

    anim = WeatherAnimator(ds, "t2m", mode="ortho", central_point=(-50, -15))
    anim.set_output(str(out))
    anim.set_quality("hd")
    anim.set_fps(10)
    anim.set_title("2m Temperature — %S", date_style="pt-br")
    anim.set_author("@reinanbr_")
    anim.set_rotation(lon_start=-90, lon_end=-30, lat_start=-10, lat_end=-15)
    anim.set_rotation_stop(fraction=0.7)
    anim.set_annotate("Juazeiro %.1f°C",   pos=(-9.4,  -40.5))
    anim.set_annotate("Fortaleza %.1f°C",  pos=(-3.72, -38.54), color="#58a6ff")
    anim.animate()
    print(f"  saved  →  {out}")


def anim_cape_satellite():
    """Nearside perspective — CAPE, satellite view."""
    out = DOCS_DIR / "cape_satellite_preview.gif"
    if skip_if_exists(out): return

    print("  [anim] nearside / cape / satellite ...")
    ds = load(RUN_DATE, CYCLE, ["cape"], ANIM_HOURS)

    anim = WeatherAnimator(ds, "cape", mode="nearside",
                           lon=-50.0, lat=-15.0,
                           satellite_height=10_000_000)
    anim.set_output(str(out))
    anim.set_quality("hd")
    anim.set_fps(10)
    anim.set_title("CAPE — %S")
    anim.set_author("@reinanbr_")
    anim.set_annotate("Juazeiro %.0f J/kg", pos=(-9.4, -40.5))
    anim.animate()
    print(f"  saved  →  {out}")


def anim_brazil_precipitation():
    """PlateCarrée — precipitation rate, Brazil."""
    out = DOCS_DIR / "brazil_precipitation_preview.gif"
    if skip_if_exists(out): return

    print("  [anim] plate / prate / Brazil ...")
    ds = load(RUN_DATE, CYCLE, ["prate"], ANIM_HOURS)

    anim = WeatherAnimator(ds, "prate", mode="plate")
    anim.set_region("brazil")
    anim.set_states()
    anim.set_output(str(out))
    anim.set_quality("hd")
    anim.set_fps(10)
    anim.set_title("Precipitation Rate — %S", date_style="pt-br")
    anim.set_author("INMET / FUNCEME", bbox=True)
    anim.set_annotate("Brasília %.2f mm/h",  pos=(-15.78, -47.93))
    anim.set_annotate("São Paulo %.2f mm/h", pos=(-23.55, -46.63))
    anim.set_annotate("Manaus %.2f mm/h",    pos=(-3.10,  -60.02))
    anim.animate()
    print(f"  saved  →  {out}")


def anim_world_wind_speed():
    """Robinson — global 10m wind speed."""
    out = DOCS_DIR / "world_wind_speed_preview.gif"
    if skip_if_exists(out): return

    print("  [anim] robinson / wspd10 / global ...")
    ds = load(RUN_DATE, CYCLE, ["u10", "v10"], ANIM_HOURS)
    ds = add_wind_speed(ds)

    anim = WeatherAnimator(ds, "wspd10", mode="robinson")
    anim.set_region("global")
    anim.set_output(str(out))
    anim.set_quality("hd")
    anim.set_fps(10)
    anim.set_title("10m Wind Speed — %S")
    anim.set_author("GFS Analysis", bbox=True)
    anim.animate()
    print(f"  saved  →  {out}")


# ══════════════════════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════════════════════

STATIC_JOBS = [
    ("ortho/t2m",          static_ortho_t2m),
    ("nearside/prmsl",     static_nearside_prmsl),
    ("plate/prate",        static_plate_prate),
    ("robinson/t2m",       static_robinson_t2m),
    ("plate/r2/ne-brazil", static_plate_r2_ne_brazil),
]

ANIMATED_JOBS = [
    ("ortho/t2m/4k-rotation",       anim_temperature_4k),
    ("nearside/cape/satellite",      anim_cape_satellite),
    ("plate/prate/brazil",           anim_brazil_precipitation),
    ("robinson/wspd10/global",       anim_world_wind_speed),
]


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate noaawc README example plots."
    )
    p.add_argument("--only-static",   action="store_true",
                   help="Only render static snapshots")
    p.add_argument("--only-animated", action="store_true",
                   help="Only render animated GIFs")
    p.add_argument("--var",  default=None,
                   help="Filter by variable key (e.g. t2m)")
    p.add_argument("--mode", default=None,
                   help="Filter by projection mode (ortho, nearside, plate, robinson)")
    return p.parse_args()


def run_jobs(jobs: list, label: str, var_filter: str | None, mode_filter: str | None):
    ok = errors = 0
    for tag, fn in jobs:
        parts = tag.split("/")
        mode_tag = parts[0]
        var_tag  = parts[1] if len(parts) > 1 else ""

        if var_filter  and var_filter  not in var_tag:  continue
        if mode_filter and mode_filter not in mode_tag: continue

        print(f"\n── {label} [{tag}]")
        try:
            fn()
            ok += 1
        except Exception as exc:
            report_error(tag, exc)
            errors += 1

    return ok, errors


def main():
    args = parse_args()

    run_static   = not args.only_animated
    run_animated = not args.only_static

    total_ok = total_err = 0

    if run_static:
        print("\n══ Static snapshots ══════════════════════════════════════")
        ok, err = run_jobs(STATIC_JOBS, "static", args.var, args.mode)
        total_ok  += ok
        total_err += err

    if run_animated:
        print("\n══ Animated GIFs ═════════════════════════════════════════")
        ok, err = run_jobs(ANIMATED_JOBS, "anim", args.var, args.mode)
        total_ok  += ok
        total_err += err

    print(f"\n{'═'*55}")
    print(f"  Done — ok={total_ok}  errors={total_err}")
    print(f"  Output dir: {DOCS_DIR.resolve()}")

    if total_err:
        sys.exit(1)


if __name__ == "__main__":
    main()