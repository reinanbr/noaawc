
<h1 align='center'></h1>
<p align='center'>
<img src='https://raw.githubusercontent.com/reinanbr/noaawc/main/img/photo_2023-01-17_02-10-48.jpg' width='350' height='300'>


<br/>
<a href="https://github.com/perseu912"><img title="Autor" src="https://img.shields.io/badge/Autor-reinan_br-blue.svg?style=for-the-badge&logo=github"></a>

<p align='center'>
<!-- github dados --
<!-- sites de pacotes -->
<a href='https://pypi.org/project/noaawc/'><img src='https://img.shields.io/pypi/v/noaawc'></a>
<!-- <a href='#'><img src='https://img.shields.io/pypi/wheel/noaawc'></a>
<a href='#'><img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/noawclg"></a> -->
<img alt="PyPI - License" src="https://img.shields.io/pypi/l/noaawc">
<br/>
<!-- outros premios e analises -->
<!-- <a href='#'><img alt="CodeFactor Grade" src="https://img.shields.io/codefactor/grade/github/perseu912/noawclg?logo=codefactor">
</a> -->
<!-- redes sociais -->
<a href='https://instagram.com/gpftc_ifsertao/'><img src='https://shields.io/badge/insta-gpftc_ifsertao-darkviolet?logo=instagram&style=flat'></a>
<a href='https://discord.gg/pFZP86gvEm'><img src='https://img.shields.io/discord/856582838467952680.svg?label=discord&logo=discord'></a>

</p>
</p>
<h3 align='center'>NOAAWC</h3>
<p align='center'> <b>Library for plotting the world data climate with the data <a href='https://nomads.ncep.noaa.gov/' title='NOAA Operational Model Archive and Distribution System
'>NOMADS</a> NOAA/NASA</b></p>
<hr/>

## Installation

```bash
$ pip install noaawc -U
```




## Examples


### Wind Jet's
spinning
```py
from noaawc.animate import Create_plot_gif as Cpf # importing class to work gif plot
from noawclg.main import get_noaa_data as gnd # importing class to work data

dn = gnd(date='16/01/2023') # set the now date (best yesterday) in format d/m/Y

point_init=[-9.43,-89] #point init to spinning
point_jua = [-9.43,-40.50] # end point (my city)

gif = Cpf(dn=dn) # setting data noaa on the class to work gif

cmap = 'inferno' # cmap theme color plot

gif.path_save=f'tests_gifs/wind/{cmap}_test_spin_temp_wind.gif' #path to save gif

gif.key_noaa = 'tmpmwl' # key from data that we want 

gif.title='temperatura dos jatos de vento' # title plot gif

#setting the points
gif.point_init=point_init 
gif.point_end=point_jua

#longitude stop
gif.lon_stop=-39

# setting cmap
gif.cmap = cmap

gif.author = '@gpfc_ | @reinanbr_' #setting the title author plot

gif.text_cb = 'ºC' #title from colorbar
gif.subtr_data = 273 # substitution of data (273, because K - 273 = ºC)

gif.tracing() # working string's, map's, daw's, line's
gif.render() # rendering the frames of gif
```

in the .../tests_gifs/wind/CMRmap_test_spin_temp_wind.gif:

<img height='300' src='https://raw.githubusercontent.com/reinanbr/noaawc/main/tests_gifs/wind/CMRmap_test_spin_temp_wind.gif'>

<hr>

### surface temperature
```py
from noaawc.animate import Create_plot_gif as Cpf
from noawclg.main import get_noaa_data as gnd

dn = gnd(date='16/01/2023')

point_init=[-9.43,-89]
point_jua = [-9.43,-40.50]

gif = Cpf(dn=dn)
gif.path_save='https://raw.githubusercontent.com/reinanbr/noaawc/main/tests_gifs/surface_temp/CMRmap_test_spin_temp_surface.gif'
gif.key_noaa = 'tmpsfc'
gif.title='temperatura da superficie'
gif.point_init=point_init
gif.point_end=point_jua
gif.lon_stop=-39
gif.annotate_loc_txt = '. Nova York: %(data)sºC'
gif.color_annote_loc = 'white'
gif.cmap = 'CMRmap'

gif.annotate_loc_pos:tuple = (40.776676,-73.971321) # point for write a text
gif.annotate_loc_txt = '. Nova York: %(data)sºC' # text for write in the plot
gif.color_annote_loc = 'white' # color of text

gif.tracing()
gif.render()
```
<img height='300' src='https://raw.githubusercontent.com/reinanbr/noaawc/main/tests_gifs/surface_temp/CMRmap_test_spin_temp_surface.gif'>

<hr>

### zoom on a focus
```py
from noaawc.animate import Create_plot_gif as Cpf
from noawclg.main import get_noaa_data as gnd

dn = gnd()

gif = Cpf(dn=dn)
gif.path_save='tests_gifs/test_zoom_focus_temp_surface.gif'
gif.key_noaa = 'tmpsfc'
gif.title='temperatura da superficie'
gif.loc_focus= point_jua
gif.zoom = (4,-4,-.5,6) # xl,xr,yu,yd for zoom
gif.annotate_focus_txt = '. Juazeiro: %(data)sºC' # write text on focus point
gif.annotate_loc_txt = '. Nova York: %(data)sºC'
gif.tracing()
gif.render()
```
<img height='300' src='https://raw.githubusercontent.com/reinanbr/noaawc/main/tests_gifs/surface_temp/test_zoom_focus_temp_surface.gif'>
