from noaawc.projections.plate import PlateCarreeAnimator
from noawclg.main import get_noaa_data as gnd

ds = gnd(date="16/04/2026", keys=["v10"])._ds

pca = PlateCarreeAnimator(ds, var="v10")
pca.set_region('global')

pca.set_title("Velocidade do Vento \n %S")
pca.set_annotate(
    "Juazeiro: %.1f m/s",
    pos=(-9.4, -40.5),
    marker="*",
    marker_color="yellow",
    marker_size=10,
    size=6,
    text_offset=(0.8, 0),
)
pca.set_fps(16)
pca.animate()
#pca.plot(time_idx=0, show=True)