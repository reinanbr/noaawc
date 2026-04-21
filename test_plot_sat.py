from noaawc.nearside import NearsidePerspectiveAnimator
from noawclg.main import get_noaa_data as gnd



ds = gnd(date="16/04/2026", keys=["t2m"])._ds
height = 10_786_000  # in meters (geostationary satellite altitude)

anim = NearsidePerspectiveAnimator(ds, "t2m")
anim.set_view(lon=-50.0, lat=-15.0,satellite_height=height)
#comeca em juazeiro BA e termina em Moscou - Russia, passando por Brasilia, Lisboa, Londres, Paris, Berlim, Varsóvia, Kiev e Moscou
anim.set_rotation(
    lon_start=-47.52, lon_end=55.75,  # Juazeiro, BA to Moscow, Russia
    lat_start= -15.47, lat_end=37.62,  # Juazeiro, BA to Moscow, Russia
)
anim.set_fps(16)
anim.set_annotate(
    "Juazeiro - BA: %.1f °C", pos=(-9.4, -40.5), marker="*",
    marker_color="yellow", marker_size=10, size=6, text_offset=(0.8, 0)
)
anim.set_annotate(
    "Moscou - Russia: %.1f °C", pos=(55.75, 37.62), marker="*",
    marker_color="red", marker_size=10, size=6, text_offset=(0.8, 0)
)



anim.set_title(f"Temperatura da Superfície do Mar ({height/1000:.1f} km) \n%S", date_style="pt-br")
anim.set_author('@reinanbr_')
anim.set_output("satellite_view.mp4")

# Camera freezes at the end point after 65 % of the frames
anim.set_rotation_stop(fraction=0.90)

anim.animate()
#anim.plot(time_idx=0, show=True)