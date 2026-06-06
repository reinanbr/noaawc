# mypy: disable-error-code="attr-defined,arg-type,operator,no-redef"
"""
noaawc.main — backward-compatibility re-export shim.

All symbols previously defined here have been refactored into sub-modules:
    noaawc.presets   — quality presets
    noaawc.theme     — dark matplotlib theme
    noaawc.utils     — GFS / field helpers
    noaawc.geo       — geographic reference lines and map features
    noaawc.overlays  — figure overlays (colorbar, title, info box, annotations)
    noaawc.base      — _AnimatorBase
    noaawc.mixins    — _RotatingAnimatorMixin, _FlatAnimatorMixin
    noaawc.animators — OrthoAnimator, NearsidePerspectiveAnimator,
                       PlateCarreeAnimator, RobinsonAnimator
"""

from noaawc.presets import (
    QUALITY_PRESETS_SQUARE,
    QUALITY_PRESETS_WIDE,
    QUALITY_PRESETS,
    list_quality_presets,
)
from noaawc.variables import VARIABLE_PRESETS, VARIABLES_INFO, NO_CONTOUR_VARS  # noqa: F401
from noaawc.utils import (  # noqa: F401
    _format_date,
    _font_scale,
    _gfs_meta,
    _frames_dir,
    _frame_path,
    _interp_field_value,
    _run_label,
    _get_field_full,
    _get_field,
    _remove_contours,
)
from noaawc.geo import _add_reference_lines, _add_features  # noqa: F401
from noaawc.overlays import (  # noqa: F401
    _colorbar,
    _title,
    _draw_info_box,
    _draw_data_credit,
    _draw_author,
    _author_above_cbar,
    _draw_annotations_on,
)
from noaawc.base import _AnimatorBase  # noqa: F401
from noaawc.mixins import _RotatingAnimatorMixin, _FlatAnimatorMixin  # noqa: F401
from noaawc.animators import (
    OrthoAnimator,
    NearsidePerspectiveAnimator,
    PlateCarreeAnimator,
    RobinsonAnimator,
    GEOSTATIONARY_HEIGHT,
    EARTH_RADIUS,
)
from noaawc.variables import list_variable_presets

__all__ = [
    "OrthoAnimator",
    "NearsidePerspectiveAnimator",
    "PlateCarreeAnimator",
    "RobinsonAnimator",
    "QUALITY_PRESETS_SQUARE",
    "QUALITY_PRESETS_WIDE",
    "QUALITY_PRESETS",
    "GEOSTATIONARY_HEIGHT",
    "EARTH_RADIUS",
    "list_quality_presets",
    "list_variable_presets",
]
