from noaawc.weather import WeatherAnimator
from noawclg.main import get_noaa_data as gnd



ds = gnd(date="02/05/2026", keys=["prate"],hours=[0])._ds
height = 10_786_000  # in meters (geostationary satellite altitude)

anim = WeatherAnimator(ds, "prate", mode="plate")
anim.set_region("south_america")
anim.set_states()
#comeca em juazeiro BA e termina em Moscou - Russia, passando por Brasilia, Lisboa, Londres, Paris, Berlim, Varsóvia, Kiev e Moscou

anim.set_annotate(
    "Juazeiro - BA: %.1f °C", pos=(-9.4, -40.5), marker="*",
    marker_color="yellow", marker_size=10, size=6, text_offset=(0.8, 0)
)




#anim.set_title(f"Temperatura da Superfície do Mar ({height/1000:.1f} km) \n%S", date_style="pt-br")
anim.set_author('@reinanbr_')
anim.set_output("satellite_view.mp4")

# Camera freezes at the end point after 65 % of the frames

anim.plot(time_idx=0, show=True)
#anim.plot(time_idx=0, show=True)