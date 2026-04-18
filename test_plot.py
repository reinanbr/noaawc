from noaawc import OrthoAnimator
from noawclg.main import get_noaa_data as gnd

ds = gnd(date="16/04/2026", keys=["t2m"])._ds

oa = OrthoAnimator(ds, var="t2m", central_point=(-40.5052, -9.43847))
oa.set_title("Temperatura da Superficie \n %S")
# Padrão: círculo + texto 0.8° ao norte
oa.set_annotate(
    "Juazeiro: %.1f°C",
    pos=(-9.4, -40.5),
    marker="*",
    marker_color="yellow",
    marker_size=10,
    size=6,
    text_offset=(0.8, 0),
)

# Estrela amarela, offset maior

oa.set_author("By @reinanbr_")
oa.plot(time_idx=0, show=True)
