from noaawc.plot import plot_global
from noawclg.main import get_noaa_data as gnd
import matplotlib.pyplot as plt

plt.style.use('dark_background')
cmap = 'inferno'

date_base = '20/06/2025'
dn = gnd(date=date_base)
indice = 5



pg = plot_global(dn=dn)
pg.path=f'{cmap}_juazeiro_wind_focus2.png'
pg.title=f'Temperatura dos Jatos de Ventos'
pg.key_noaa='tmpmwl'
pg.indice=indice

pg.loc_focus=(-29.43847,-40.5052)
pg.annotate_data_focus('. : %(data)sºC')
pg.annotate_color_focus = 'white'

pg.text_cb='°C'
pg.author='@gpftc | @reinanbr_'
pg.cmap = cmap



pg.render(show=True)
