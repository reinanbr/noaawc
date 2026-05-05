from __future__ import annotations

import traceback
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable

from noaawc.variables import VARIABLES_INFO
from noaawc.weather import WeatherAnimator
from noawclg.main import get_noaa_data as gnd
from kitano import puts

# ── configuration ─────────────────────────────────────────────────────────────

DATE   = "02/05/2026"
HOURS_16DAYS_3H = list(range(0, 121, 3)) + list(range(123, 385, 3))
HOURS = HOURS_16DAYS_3H
KEYS: list[str] = list(VARIABLES_INFO.keys())
# KEYS = ["t2m"]  # uncomment to test a single variable

# Variáveis derivadas — precisam ser calculadas antes da renderização
DERIVED = {"wspd10", "wspd"}

OUTPUT_ROOT = Path("./videos")
ERROR_LOG   = OUTPUT_ROOT / "errors" / "variables_errors.txt"

# Qualidade padrão para todos os vídeos ("sd" | "hd" | "4k" | "4k_60")
QUALITY = "hd"

# Codec padrão ("libx264" | "libx265" | "vp9" | "prores")
CODEC = "libx264"


# ── projection profiles ───────────────────────────────────────────────────────

@dataclass
class Profile:
    """Descreve um modo de projeção e como configurar seu animator."""
    mode:        str
    subdir:      str
    suffix:      str
    configure:   Callable   # (anim, key) → None
    init_kwargs: dict = field(default_factory=dict)


def _configure_ortho(anim, key: str) -> None:
    # ref: "4K temperature animation — rotating globe" no README
    long_name = VARIABLES_INFO[key]["long_name"]
    anim.set_quality(QUALITY)
    anim.set_codec(CODEC)
    anim.set_title(f"{long_name}\n%S", date_style="pt-br")
    anim.set_author("@reinanbr_")
    anim.set_rotation(lon_start=-90, lon_end=-20, lat_start=-5, lat_end=-20)
    anim.set_rotation_stop(fraction=0.65)
    anim.set_fps(16)
    anim.set_annotate("Juazeiro - BA: %.1f", pos=(-9.4, -40.5))


def _configure_nearside(anim, key: str) -> None:
    # ref: "Satellite-style CAPE animation" no README
    long_name = VARIABLES_INFO[key]["long_name"]
    anim.set_quality(QUALITY)
    anim.set_codec(CODEC)
    anim.set_title(f"{long_name}\n%S", date_style="pt-br")
    anim.set_author("@reinanbr_")
    anim.set_fps(16)
    anim.set_annotate("Juazeiro - BA: %.1f", pos=(-9.4, -40.5))


def _configure_plate(anim, key: str) -> None:
    # ref: "Brazil precipitation animation — flat map" no README
    long_name = VARIABLES_INFO[key]["long_name"]
    anim.set_region("south_america")
    anim.set_states()
    anim.set_quality(QUALITY)
    anim.set_codec(CODEC)
    anim.set_title(f"{long_name}\n%S", date_style="pt-br")
    anim.set_author("@reinanbr_")
    anim.set_fps(16)
    anim.set_annotate("Juazeiro - BA: %.1f", pos=(-9.4, -40.5))


def _configure_robinson(anim, key: str) -> None:
    # ref: "Global wind speed — Robinson world map" no README
    long_name = VARIABLES_INFO[key]["long_name"]
    anim.set_region("global")
    anim.set_quality(QUALITY)
    anim.set_codec(CODEC)
    anim.set_title(f"{long_name}\n%S", date_style="pt-br")
    anim.set_author("@reinanbr_")
    anim.set_fps(16)
    anim.set_annotate("Juazeiro - BA: %.1f", pos=(-9.4, -40.5))


PROFILES: list[Profile] = [
    Profile(
        mode="ortho",
        subdir="ortho",
        suffix="_ortho.mp4",
        configure=_configure_ortho,
        init_kwargs={"central_point": (-50.0, -15.0)},
    ),
    Profile(
        mode="nearside",
        subdir="nearside",
        suffix="_satellite.mp4",
        configure=_configure_nearside,
        init_kwargs={"lon": -50.0, "lat": -15.0},
    ),
    Profile(
        mode="plate",
        subdir="plate",
        suffix="_plate.mp4",
        configure=_configure_plate,
    ),
    Profile(
        mode="robinson",
        subdir="robinson",
        suffix="_robinson.mp4",
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


def compute_derived(ds, key: str):
    """Calcula variáveis derivadas que não existem diretamente no GRIB2."""
    if key == "wspd10" and "wspd10" not in ds:
        ds["wspd10"] = np.sqrt(ds["u10"] ** 2 + ds["v10"] ** 2)
    if key == "wspd" and "wspd" not in ds:
        ds["wspd"] = np.sqrt(ds["u"] ** 2 + ds["v"] ** 2)
    return ds


def process(key: str, profile: Profile) -> bool:
    """Renderiza um vídeo para uma variável e uma projeção. Retorna True se salvou."""
    path = output_path(profile, key)

    if path.exists():
        puts(f"    skip  [{profile.mode}] {key}  →  já existe")
        return False

    path.parent.mkdir(parents=True, exist_ok=True)

    # Carrega dados — variáveis derivadas requerem seus componentes
    if key == "wspd10":
        ds = gnd(date=DATE, keys=["u10", "v10"], hours=HOURS)._ds
    elif key == "wspd":
        ds = gnd(date=DATE, keys=["u", "v"], hours=HOURS)._ds
    else:
        ds = gnd(date=DATE, keys=[key], hours=HOURS)._ds

    ds = compute_derived(ds, key)

    anim = WeatherAnimator(ds, key, mode=profile.mode, **profile.init_kwargs)
    profile.configure(anim, key)
    anim.set_output(str(path))
    anim.animate()

    puts(f"    saved  [{profile.mode}] {key}  →  {path}")
    return True


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    total = len(KEYS) * len(PROFILES)
    ok = skipped = errors = 0

    puts(f"Renderizando {len(KEYS)} variável(is) × {len(PROFILES)} projeção(ões) = {total} vídeos\n")
    puts(f"Qualidade: {QUALITY}  |  Codec: {CODEC}  |  Horas: {HOURS[0]}–{HOURS[-1]} h  ({len(HOURS)} frames)\n")

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

    puts(f"\nConcluído — ok={ok}  pulados={skipped}  erros={errors}")
    if errors:
        puts(f"Detalhes dos erros → {ERROR_LOG}")


if __name__ == "__main__":
    main()