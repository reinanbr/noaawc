from noaawc import WeatherAnimator
from noawclg import load

# mostrando os efeitos do el niño em 2026, o mais forte já registrado
date = "17/05/2026"
ds = load(date=date, keys=["t2m"])

animator = WeatherAnimator(ds, var="t2m", mode="nearside")
animator.set_cmap("jet")
animator.set_rotation(
    lon_start=-60.0,
    lon_end=-90.0,
    lat_start=-55.0,  # Cabo Horn / ponta da Patagônia
    lat_end=23.0,  # México central
)
animator.set_rotation_stop(fraction=0.80)

# Pacífico Equatorial Central — epicentro do El Niño (região Niño 3.4)
animator.set_annotate(
    text_base="El Niño\n%.1f°C",
    pos=(0.0, -140.0),  # lat 0°, lon 140°W — Pacífico equatorial central
    size=10.0,
    color="#ff4444",
    weight="bold",
    bbox=True,
    bbox_color="#0d1117",
    bbox_alpha=0.70,
    interpolate=True,  # busca o valor real do campo t2m nessa coordenada
    marker="o",
    marker_size=7.0,
    marker_color="#ff4444",
    text_offset=(0.0, 2.5),
)

animator.set_output("el_nino_2026.mp4")
animator.set_quality("hd")
animator.set_title("El Niño 2026 — Temperatura %S", date_style="pt-br")
animator.animate()
