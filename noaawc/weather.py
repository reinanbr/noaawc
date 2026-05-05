"""
WeatherAnimator
===============
A unified entry point for all four GFS weather map animators.

Instead of importing four different classes, just use WeatherAnimator()
and pick a mode:

    mode="ortho"     → OrthoAnimator               (orthographic globe)
    mode="nearside"  → NearsidePerspectiveAnimator  (satellite-view globe)
    mode="plate"     → PlateCarreeAnimator          (flat equirectangular map)
    mode="robinson"  → RobinsonAnimator             (Robinson pseudo-cylindrical)

Every mode returns the original animator instance, so the full API of each
class is available — tab-completion, docstrings, and all.

Examples
--------
    from noaawc.weather import WeatherAnimator

    # Orthographic globe with rotation
    anim = WeatherAnimator(ds, "t2m", mode="ortho", central_point=(-50, -15))
    anim.set_rotation(lon_start=-90, lon_end=-20, lat_start=-5, lat_end=-20)
    anim.set_rotation_stop(fraction=0.65)
    anim.set_quality("hd")
    anim.set_output("globe.mp4")
    anim.animate()

    # Satellite view (geostationary altitude, GOES-16 look)
    anim = WeatherAnimator(ds, "t2m", mode="nearside", lon=-50.0, lat=-15.0)
    anim.set_satellite_height(35_786_000)
    anim.set_quality("hd")
    anim.set_output("satellite.mp4")
    anim.animate()

    # Flat map — South America region
    anim = WeatherAnimator(ds, "t2m", mode="plate")
    anim.set_region("south_america")
    anim.set_quality("hd")
    anim.set_output("flat_map.mp4")
    anim.animate()

    # Robinson world map
    anim = WeatherAnimator(ds, "t2m", mode="robinson")
    anim.set_region("global")
    anim.set_quality("hd")
    anim.set_output("world.mp4")
    anim.animate()

Factory helpers
---------------
    list_modes()              — print all available modes
    list_quality_presets()    — print quality presets per mode
    list_variable_presets()   — print all variable presets
"""

from __future__ import annotations

from typing import Literal, overload

from noaawc.main import (
    OrthoAnimator,
    NearsidePerspectiveAnimator,
    PlateCarreeAnimator,
    RobinsonAnimator,
    GEOSTATIONARY_HEIGHT,
    list_quality_presets,
    list_variable_presets,
)

__all__ = [
    "WeatherAnimator",
    "list_modes",
    "list_quality_presets",
    "list_variable_presets",
    "OrthoAnimator",
    "NearsidePerspectiveAnimator",
    "PlateCarreeAnimator",
    "RobinsonAnimator",
]

# ── valid mode registry ───────────────────────────────────────────────────────

_MODES: dict[str, dict] = {
    "ortho": {
        "class":       OrthoAnimator,
        "description": "Orthographic globe — camera at infinity, full hemisphere view",
        "init_kwargs": ["central_point"],
        "specific":    ["set_rotation", "set_rotation_stop", "set_zoom", "set_states"],
    },
    "nearside": {
        "class":       NearsidePerspectiveAnimator,
        "description": "Nearside Perspective — satellite view from a finite altitude",
        "init_kwargs": ["lon", "lat", "satellite_height"],
        "specific":    ["set_view", "set_satellite_height", "set_rotation",
                        "set_rotation_stop", "set_states"],
    },
    "robinson": {
        "class":       RobinsonAnimator,
        "description": "Robinson projection — visually balanced global flat map",
        "init_kwargs": [],
        "specific":    ["set_region", "set_states", "set_ocean", "set_grid"],
    },
    "plate": {
        "class":       PlateCarreeAnimator,
        "description": "PlateCarree (equirectangular) — flat 2-D regional map",
        "init_kwargs": [],
        "specific":    ["set_region", "set_zoom", "set_states", "set_ocean", "set_grid"],
    },
}


# ── overloaded signatures — VS Code / Pylance resolve the return type ─────────

@overload
def WeatherAnimator(
    ds,
    var: str,
    mode: Literal["ortho"],
    *,
    central_point: tuple[float, float] = ...,
) -> OrthoAnimator: ...

@overload
def WeatherAnimator(
    ds,
    var: str,
    mode: Literal["nearside"],
    *,
    lon: float = ...,
    lat: float = ...,
    satellite_height: float = ...,
) -> NearsidePerspectiveAnimator: ...

@overload
def WeatherAnimator(
    ds,
    var: str,
    mode: Literal["plate"],
) -> PlateCarreeAnimator: ...

@overload
def WeatherAnimator(
    ds,
    var: str,
    mode: Literal["robinson"],
) -> RobinsonAnimator: ...

@overload
def WeatherAnimator(
    ds,
    var: str,
    mode: str = ...,
    **kwargs,
) -> OrthoAnimator | NearsidePerspectiveAnimator | PlateCarreeAnimator | RobinsonAnimator: ...


# ── factory implementation ────────────────────────────────────────────────────

def WeatherAnimator(  # type: ignore[misc]  # intentional overload mismatch
    ds,
    var: str,
    mode: str = "ortho",
    **kwargs,
) -> OrthoAnimator | NearsidePerspectiveAnimator | PlateCarreeAnimator | RobinsonAnimator:
    """
    Create and return the appropriate animator for the requested projection mode.

    Parameters
    ----------
    ds : xarray.Dataset
        GFS dataset in noaawc format.

    var : str
        Variable key (e.g. "t2m", "prmsl", "prate").
        Call list_variable_presets() to see all supported keys.

    mode : str
        Projection mode. One of:

        ``"ortho"``
            Orthographic globe. Camera sits at infinity — the classic
            "view from space" with no perspective distortion.
            Extra kwargs: ``central_point=(lon, lat)``

        ``"nearside"``
            Nearside Perspective globe. Camera at a finite satellite altitude,
            producing realistic perspective foreshortening and a curved horizon.
            Default altitude: 35 786 000 m (geostationary orbit, GOES / Meteosat).
            Extra kwargs: ``lon``, ``lat``, ``satellite_height``

        ``"plate"``
            PlateCarree (equirectangular) flat map. Best for regional views
            where geographic accuracy and axis labels matter.
            No extra kwargs at construction time — use ``set_region()`` or
            ``set_zoom()`` after construction.

        ``"robinson"``
            Robinson pseudo-cylindrical world map. Minimises area and shape
            distortion — the standard for global thematic maps.
            No extra kwargs at construction time — use ``set_region()`` after.

    **kwargs
        Passed directly to the underlying class constructor.
        Mode-specific accepted kwargs:

        ============  =====================================================
        mode          accepted kwargs
        ============  =====================================================
        ``ortho``     ``central_point=(lon, lat)``  (default: (-45, -15))
        ``nearside``  ``lon``, ``lat``, ``satellite_height``
        ``plate``     *(none — configure via set_region / set_zoom)*
        ``robinson``  *(none — configure via set_region)*
        ============  =====================================================

    Returns
    -------
    OrthoAnimator | NearsidePerspectiveAnimator | PlateCarreeAnimator | RobinsonAnimator
        The fully constructed animator instance. All mode-specific methods
        are available on the returned object.

        VS Code / Pylance resolves the **exact** return type when ``mode``
        is passed as a literal string (e.g. ``mode="nearside"``), giving
        full autocomplete for every ``set_*`` method.

    Raises
    ------
    ValueError
        If an unknown mode string is passed.

    Examples
    --------
    Orthographic globe — full South America rotation::

        anim = WeatherAnimator(ds, "t2m", mode="ortho", central_point=(-50, -15))
        anim.set_rotation(lon_start=-90, lon_end=-20, lat_start=-5, lat_end=-20)
        anim.set_rotation_stop(fraction=0.65)
        anim.set_quality("hd")
        anim.set_output("globe.mp4")
        anim.animate()

    Satellite view — geostationary orbit::

        anim = WeatherAnimator(ds, "t2m", mode="nearside", lon=-75.0, lat=0.0,
                               satellite_height=35_786_000)
        anim.set_quality("hd")
        anim.set_output("satellite.mp4")
        anim.animate()

    Regional zoom — Northeast Brazil, flat map::

        anim = WeatherAnimator(ds, "t2m", mode="plate")
        anim.set_zoom(zoom=4, pos=(-9.4, -40.5))
        anim.set_states()
        anim.set_quality("hd")
        anim.set_output("northeast.mp4")
        anim.animate()

    Global Robinson map::

        anim = WeatherAnimator(ds, "t2m", mode="robinson")
        anim.set_region("global")
        anim.set_quality("hd")
        anim.set_output("world.mp4")
        anim.animate()

    Static snapshot (any mode)::

        anim = WeatherAnimator(ds, "prmsl", mode="plate")
        anim.set_region("brazil")
        anim.plot(time_idx=0, save="snapshot.png")
    """
    mode = mode.lower().strip()

    if mode not in _MODES:
        valid = ", ".join(f'"{m}"' for m in _MODES)
        raise ValueError(
            f"Unknown mode '{mode}'. Valid options are: {valid}.\n"
            f"Call list_modes() to see a description of each."
        )

    entry    = _MODES[mode]
    cls      = entry["class"]
    accepted = set(entry["init_kwargs"])
    filtered = {k: v for k, v in kwargs.items() if k in accepted}
    ignored  = {k: v for k, v in kwargs.items() if k not in accepted}

    if ignored:
        print(
            f"[WeatherAnimator] mode='{mode}' ignored unknown kwargs: "
            + ", ".join(f"{k}={v!r}" for k, v in ignored.items())
        )

    return cls(ds, var, **filtered)


# ── discovery helpers ─────────────────────────────────────────────────────────

def list_modes() -> None:
    """Print all available projection modes and their descriptions."""
    print()
    print(f"  {'Mode':<12}  {'Class':<34}  Description")
    print("  " + "─" * 100)
    for name, entry in _MODES.items():
        cls_name = entry["class"].__name__
        print(f"  {name:<12}  {cls_name:<34}  {entry['description']}")
    print()
    print("  Mode-specific methods:")
    for name, entry in _MODES.items():
        methods = ", ".join(entry["specific"])
        print(f"    {name:<10} → {methods}")
    print()
