from noaawc import OrthoAnimator
from noawclg.main import get_noaa_data as gnd


data = gnd(date="16/04/2026", keys=["u10"])



anim = OrthoAnimator(data._ds, "u10")
(anim
    .set_output("v.mp4")
    #.set_quality("hd")
    .set_rotation(lon_start=-90, lon_end=-20, lat_start=-5, lat_end=-20)
    .set_rotation_stop(fraction=0.65)
    .set_annotate("Juazeiro - BA %dm/s", pos=(-9.4, -40.5), marker="*",
            marker_color="yellow", marker_size=10, size=6, text_offset=(0.8, 0))
    .set_fps(16)
    .set_author('@reinanbr_')
    .set_title("Velocidade dos Ventos\n%S", date_style="pt-br")
    .set_author('@reinanbr_')
    .animate()
)