from noaawc.animate import Create_plot_gif as Cpf
from noawclg.main import get_noaa_data as gnd


def test_render():
    dn = gnd(date= '27/01/2023')

    point_init=[-9.43,-89]
    point_jua = [-9.43,-40.50]

    gif = Cpf(dn=dn)
    gif.path_save='tests_gifs/test_zoom_focus_loc_temp_surface.gif'
    gif.key_noaa = 'tmpsfc'
    gif.title='temperatura da superficie'
    gif.loc_focus= point_jua
    gif.zoom = (4,-4,-.5,6)
    gif.annotate_focus_txt = '. Juazeiro: %(data)sºC'

    gif.annotate_loc_pos = (40.776676,-73.971321)
    gif.annotate_loc_txt = '. Nova York: %(data)sºC'

    gif.tracing()
    gif.render()