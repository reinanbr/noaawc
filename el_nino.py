from noaawc import WeatherAnimator
from noawclg import load

# mostrando os efeitos do el niño em 2026, o mais forte já registrado
date = "17/05/2026"
ds = load(date=date, keys=["t2m"])

animator = WeatherAnimator(ds, var="t2m", mode="nearside")
animator.set_cmap("jet")           # jet é desaconselhado p/ anomalias —
                                       # RdBu_r (azul=frio, vermelho=quente)
                                       # comunica El Niño muito melhor
animator.set_surface("ocean")          # El Niño é fenômeno oceânico
animator.set_rotation(
    lon_start=-150.0,  # Pacífico central — epicentro do El Niño
    lon_end=-150.0,    # longitude fixa, só a latitude se move
    lat_start=-60.0,   # começa "embaixo" (Antártico)
    lat_end=0.0,       # sobe até o equador
)
animator.set_rotation_stop(fraction=0.75)   # câmera para em 75% do vídeo
animator.set_output("el_nino_2026.mp4")
animator.set_quality("hd")
animator.set_title("El Niño 2026 — Temperatura %S", date_style="pt-br")
animator.animate()