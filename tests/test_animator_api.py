import numpy as np
import pytest
import xarray as xr

pytest.importorskip("cartopy")
pytest.importorskip("cmocean")

from noaawc.ortho import OrthoAnimator, _font_scale


@pytest.fixture
def sample_ds():
    times = np.array(
        [
            np.datetime64("2026-04-18T00:00:00"),
            np.datetime64("2026-04-18T03:00:00"),
        ]
    )
    lat = np.array([-10.0, -9.5])
    lon = np.array([-41.0, -40.5])
    data = np.array(
        [
            [[25.0, 26.0], [27.0, 28.0]],
            [[24.0, 25.0], [26.0, 27.0]],
        ]
    )

    ds = xr.Dataset(
        {
            "t2m": xr.DataArray(
                data,
                dims=("time", "latitude", "longitude"),
                coords={"time": times, "latitude": lat, "longitude": lon},
            )
        },
        attrs={"run_date": "20260418", "cycle": "00z"},
    )
    return ds


def test_orhoanimator_fallbacks_to_t2m_when_preset_missing(sample_ds, capsys):
    anim = OrthoAnimator(sample_ds, "unknown_var")

    captured = capsys.readouterr()
    assert "No preset for 'unknown_var'" in captured.out
    assert anim._plot_title == "2-m Temperature"
    assert anim._cbar_label == "2-m Temperature (°C)"


def test_set_video_quality_validates_bounds(sample_ds):
    anim = OrthoAnimator(sample_ds, "t2m")

    with pytest.raises(ValueError):
        anim.set_video_quality(-1)

    with pytest.raises(ValueError):
        anim.set_video_quality(11)


def test_set_quality_unknown_preset_raises(sample_ds):
    anim = OrthoAnimator(sample_ds, "t2m")

    with pytest.raises(ValueError):
        anim.set_quality("ultra")


def test_rotation_stop_fraction_validation(sample_ds):
    anim = OrthoAnimator(sample_ds, "t2m")

    with pytest.raises(ValueError):
        anim.set_rotation_stop(fraction=0.0)

    with pytest.raises(ValueError):
        anim.set_rotation_stop(fraction=1.0)


def test_rotation_at_interpolates_until_stop(sample_ds):
    anim = OrthoAnimator(sample_ds, "t2m")
    anim.set_rotation(lon_start=-60, lon_end=-30, lat_start=-20, lat_end=-10)

    lon0, lat0 = anim._rotation_at(0, stop=2)
    lon1, lat1 = anim._rotation_at(1, stop=2)
    lon2, lat2 = anim._rotation_at(2, stop=2)

    assert (lon0, lat0) == (-60, -20)
    assert (lon2, lat2) == (-30, -10)
    assert lon1 == pytest.approx(-45.0)
    assert lat1 == pytest.approx(-15.0)


def test_font_scale_grows_with_dpi():
    assert _font_scale(120) == pytest.approx(1.0)
    assert _font_scale(220) > _font_scale(120)
    assert _font_scale(72) < _font_scale(120)
