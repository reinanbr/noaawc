from __future__ import annotations

import traceback
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable

from noaawc.variables import VARIABLES_INFO
from noaawc.weather import WeatherAnimator
from noawclg.main import get_noaa_data as gnd
from kitano import puts

# ── configuration ─────────────────────────────────────────────────────────────

DATE   = "18/04/2026"
HOURS  = [0]

KEYS: list[str] = list(VARIABLES_INFO.keys())
# KEYS = ["prate"]  # uncomment to test a single variable

OUTPUT_ROOT = Path("./plots")
ERROR_LOG   = OUTPUT_ROOT / "errors" / "variables_errors.txt"


# ── projection profiles ───────────────────────────────────────────────────────

@dataclass
class Profile:
    """Describes one projection mode and how to configure its animator."""
    mode:        str
    subdir:      str
    suffix:      str
    configure:   Callable   # (anim, key) → None
    init_kwargs: dict = field(default_factory=dict)


def _configure_ortho(anim, key: str) -> None:
    # ref: "Orthographic globe — single frame" example in README
    long_name = VARIABLES_INFO[key]["long_name"]
    anim.set_quality("hd")
    anim.set_title(f"{long_name}\n%S", date_style="pt-br")
    anim.set_author("@reinanbr_")
    anim.set_annotate("Juazeiro - BA: %.1f", pos=(-9.4, -40.5))


def _configure_nearside(anim, key: str) -> None:
    # ref: "Satellite view — single frame" example in README
    long_name = VARIABLES_INFO[key]["long_name"]
    anim.set_quality("hd")
    anim.set_title(f"{long_name}\n%S", date_style="pt-br")
    anim.set_author("@reinanbr_")
    anim.set_annotate("Juazeiro - BA: %.1f", pos=(-9.4, -40.5))


def _configure_plate(anim, key: str) -> None:
    # ref: "Flat regional map — South America" example in README
    long_name = VARIABLES_INFO[key]["long_name"]
    anim.set_region("south_america")
    anim.set_states()
    anim.set_quality("hd")
    anim.set_title(f"{long_name}\n%S", date_style="pt-br")
    anim.set_author("@reinanbr_")
    anim.set_annotate("Juazeiro - BA: %.1f", pos=(-9.4, -40.5))


def _configure_robinson(anim, key: str) -> None:
    # ref: "Robinson world map — global temperature" example in README
    long_name = VARIABLES_INFO[key]["long_name"]
    anim.set_region("global")
    anim.set_quality("hd")
    anim.set_title(f"{long_name}\n%S", date_style="pt-br")
    anim.set_author("@reinanbr_")
    anim.set_annotate("Juazeiro - BA: %.1f", pos=(-9.4, -40.5))


PROFILES: list[Profile] = [
    Profile(
        mode="ortho",
        subdir="ortho",
        suffix="_ortho.png",
        configure=_configure_ortho,
        init_kwargs={"central_point": (-50.0, -15.0)},
    ),
    Profile(
        mode="nearside",
        subdir="nearside",
        suffix="_satellite.png",
        configure=_configure_nearside,
        init_kwargs={"lon": -50.0, "lat": -15.0},
    ),
    Profile(
        mode="plate",
        subdir="plate",
        suffix="_plate.png",
        configure=_configure_plate,
    ),
    Profile(
        mode="robinson",
        subdir="robinson",
        suffix="_robinson.png",
        configure=_configure_robinson,
    ),
]


# ── helpers ───────────────────────────────────────────────────────────────────

def output_path(profile: Profile, key: str) -> Path:
    return OUTPUT_ROOT / profile.subdir / f"{key}{profile.suffix}"


def log_error(key: str, profile: Profile, exc: Exception) -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    long_name = VARIABLES_INFO[key]["long_name"]
    entry = (
        f"[{profile.mode.upper()}] [{key} - {long_name}]\n"
        f"{traceback.format_exc()}\n"
        + "-" * 60 + "\n"
    )
    with ERROR_LOG.open("a") as fh:
        fh.write(entry)


def process(key: str, profile: Profile) -> bool:
    """Render one variable for one projection. Returns True if a new plot was saved."""
    path = output_path(profile, key)

    if path.exists():
        puts(f"    skip  [{profile.mode}] {key}  →  already exists")
        return False

    path.parent.mkdir(parents=True, exist_ok=True)

    ds   = gnd(date=DATE, keys=[key], hours=HOURS)._ds
    anim = WeatherAnimator(ds, key, mode=profile.mode, **profile.init_kwargs)
    profile.configure(anim, key)
    anim.plot(time_idx=0, save=str(path), show=False)
    puts(f"    saved  [{profile.mode}] {key}  →  {path}")
    return True


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    total = len(KEYS) * len(PROFILES)
    ok = skipped = errors = 0

    puts(f"Rendering {len(KEYS)} variable(s) × {len(PROFILES)} projection(s) = {total} plots\n")

    for key in KEYS:
        puts(f"  {key}  ({VARIABLES_INFO[key]['long_name']})")
        for profile in PROFILES:
            try:
                saved = process(key, profile)
                if saved:
                    ok += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                log_error(key, profile, exc)
                puts(f"    error  [{profile.mode}] {key}: {exc}")

    puts(f"\nDone — ok={ok}  skipped={skipped}  errors={errors}")
    if errors:
        puts(f"Error details → {ERROR_LOG}")


if __name__ == "__main__":
    main()