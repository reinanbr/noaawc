from datetime import datetime, timezone

import numpy as np
import pytest

pytest.importorskip("cartopy")
pytest.importorskip("cmocean")

from noaawc.main import _format_date


def test_format_date_with_numpy_datetime64_and_locale_ptbr():
    ts = np.datetime64("2026-04-18T03:00:00")
    out = _format_date(ts, date_style="pt-br")
    assert out == "18 Abr 2026 03:00"


def test_format_date_fallbacks_to_english_for_unknown_locale():
    dt = datetime(2026, 4, 18, 3, 0, tzinfo=timezone.utc)
    out = _format_date(dt, date_style="xx")
    assert out == "18 Apr 2026 03:00"
