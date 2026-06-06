from noaawc.weather import WeatherAnimator
from noaawc.animators import (
    OrthoAnimator,
    NearsidePerspectiveAnimator,
    PlateCarreeAnimator,
    RobinsonAnimator,
)
from noaawc.presets import QUALITY_PRESETS_SQUARE, QUALITY_PRESETS_WIDE, list_quality_presets
from noaawc.variables import list_variable_presets
from noaawc.ocean_variables import (
    OCEAN_VARIABLES_INFO,
    OCEAN_VARIABLE_PRESETS,
    OCEAN_NO_CONTOUR_VARS,
    GODAS_LEVELS,
    GODAS_VARS,
    ERSST_VARS,
    NINO_BOXES,
    list_ocean_variable_presets,
)

__all__ = [
    "WeatherAnimator",
    "OrthoAnimator",
    "NearsidePerspectiveAnimator",
    "PlateCarreeAnimator",
    "RobinsonAnimator",
    "QUALITY_PRESETS_SQUARE",
    "QUALITY_PRESETS_WIDE",
    "list_quality_presets",
    "list_variable_presets",
    # ocean
    "OCEAN_VARIABLES_INFO",
    "OCEAN_VARIABLE_PRESETS",
    "OCEAN_NO_CONTOUR_VARS",
    "GODAS_LEVELS",
    "GODAS_VARS",
    "ERSST_VARS",
    "NINO_BOXES",
    "list_ocean_variable_presets",
]
