
'''
Reinan Br <slimchatuba@gmail.com>
5 jan 2022 19:08 (init)
lib: noaawc
license: GPLv3
--------------------------------------------------

'''
import numpy as np
#import pygrib
import psutil as ps
import imageio
import time
import os
from noaawc.plot import plot_global
import matplotlib.pyplot as plt
from noawclg.main import get_noaa_data as gnd
from dataclasses import dataclass
from kitano import puts
import statistics as stts
import urllib
from noaawc.video import RenderVideo

from matplotlib.colors import ListedColormap
from dataclasses import dataclass, field

global time0
global ping_list
time0=time.time()
ping_list = [0]

def ping_fun(ping_init:float,i,size):
    ping = time.time()-ping_init
    ping_list.append(ping)
    ping_m = stts.median(ping_list) #sum(ping_list)/len(ping_list)
    i_=i+1
    eta = (size-i_)*ping_m
    min_eta = eta//60
    seg_eta = eta%60
    per = (i_/size)*100
    perr = time.time()-time0
    min_perr = perr//60
    seg_perr = perr%60
    puts(f'echo "[{i_}/{size} {per:.2f}% | PER :{int(min_perr)}min :{int(seg_perr)}seg / ETA: {int(min_eta)}min :{int(seg_eta)}seg]   [CPU:{ps.cpu_percent()}% | RAM:{ps.virtual_memory().percent}% swap:{ps.swap_memory().percent}%]"')




@dataclass
class Create_plot_gif:
    dn:gnd
    path_gif:str='img.gif'
    path_mp4:str='video.mp4'
    size:int=70
    path_data:str='data'
    title:str=''
    key_noaa:str='vgrdpbl'
    loc_focus:tuple=(-9.45,-40.5)
    point_init=False
    point_end:float=False
    text_cb:str='°C'
    lon_stop:float=False
    alpha:float=.9
    subtr_data:float=273
    speed_frame:float=1
    speed_degree_frame:float=1
    
    zoom:tuple = None
    
    line_states:float=0.1
    color_line_states:str = 'yellow'
    annotate_data_focus:str = None
    
    line_countries:float=1.5
    color_line_countries:str='green'
    
    author = '@gpfc_ | @reinanbr_'
    annotate_data_foc:str = None
    annotate_loc_txt:str = None
    annotate_loc_pos:tuple = (40.776676,-73.971321)
    color_annote_loc:str = 'white'
    fps:float = 10
    cmap: ListedColormap = field(default_factory=lambda: ListedColormap(["red", "blue"]))#cmap:plt.cm=plt.cm.jet
    resolution:str = 'c'
    point_init:tuple = None
    point_end:tuple = None
    text_cb:str = '°C'



    def tracing(self):
        assert self.size < 128, print('size of data is max 128!!')
        self.speed_degree_frame = self.speed_frame
        self.frames = self.size*self.fps
        self.locs_focus = []
        if self.loc_focus:
            for _ in range(self.frames):
                self.locs_focus.append(self.loc_focus)
            
        if self.point_init and self.point_end:
            self.lat_space = (self.point_init[0],self.point_end[0])
            self.lon_space = (self.point_init[1],self.point_end[1])
            
            self.lat_list = np.linspace(self.lat_space[0],self.lat_space[1],self.size)
            
            self.lon_list = np.linspace(self.lon_space[0],self.lon_space[1],self.size)
            #print('after',lon_list)
            
            if self.lon_stop:
                print('istop: yes')
                k = self.speed_degree_frame*self.size+self.lon_space[0]-self.lon_space[1]
                self.lon_list = np.linspace(self.lon_space[0],self.lon_space[1]+k,self.size)
                self.lon_list[abs(self.lon_list)<abs(self.lon_stop)] = self.lon_stop
                #print('before',lon_list)
            self.locs_focus = list(zip(self.lat_list,self.lon_list))





    def render_cache(self):
        time_0=time.time()

        if not os.path.isdir(self.path_data):
            os.mkdir(self.path_data)

        images = []
        images_path = []
        img_path = urllib.parse.quote(self.title)
        for i in range(self.frames):
            path_img = f'{self.path_data}/{img_path}_{i}.png'

            pg = plot_global(dn=self.dn,
                             path=path_img,
                             line_states=self.line_states,
                             color_line_states=self.color_line_states,
                             line_countries=self.line_countries,
                             color_line_countries=self.color_line_countries,
                             title=self.title,
                             key_noaa=self.key_noaa,
                             alpha=self.alpha,
                             indice=i,
                             loc_focus=self.locs_focus[i],
                             subtr_data=self.subtr_data,
                             author=self.author,
                             text_cb=self.text_cb)

            if self.zoom:
                pg.zoom(*self.zoom)
                
            if self.annotate_data_focus:
                pg.annotate_data_focus(self.annotate_data_focus)
            
            if self.annotate_loc_txt:
                pg.annotate_data_loc(self.annotate_loc_txt,loc=self.annotate_loc_pos,color=self.color_annote_loc)

            pg.cmap = self.cmap

            pg.render(show=False)
            ping_fun(time_0,i,self.frames)
            images.append(imageio.imread(path_img))
            images_path.append(path_img)
        self.images = images
        self.images_path = images_path




    def render_gif(self):
        print('rendering gif...')
        path_gif = self.path_gif
        imageio.mimsave(path_gif,self.images,fps=self.fps)
        #for img in self.images:
        os.system(f'rm -rf {self.path_data}/*.png')



    def render_mp4(self,path_save:str):
        print('rendering mp4...')
        file_mp4 = path_save
        render_video = RenderVideo(self.images_path[1:],fps=self.fps)
        render_video.render_mp4(file_mp4)
        #for img in self.images:
        os.system(f'rm -rf {self.path_data}/*.png')



