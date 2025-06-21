
import numpy as np
#import pygrib
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
from noawclg import get_noaa_data as gnd
import pandas as pd
from datetime import datetime
from kitano import puts

from matplotlib.colors import ListedColormap
from dataclasses import dataclass, field


plt.style.use('dark_background')


# global dn
# global date_base

# date_base = None
# def set_date(date:str):
#     date_base = date
#     print('oi')

# def load_data():
#     if date_base:
#         puts(f'loading data from date {date_base}')
#         dn = gnd(date=date_base)
#     else:
#         today = datetime.datetime.now()
#         yesterday = today - datetime.timedelta(days=1)
#         yesterday = yesterday.strftime('%d/%m/%Y')
#         puts(f'loading data from yesterday date {yesterday}')
#         dn = gnd(date=yesterday)

#keys = dn.get_noaa_keys()
'''
the function base and more
important from it work
'''

@dataclass
class plot_global:
    dn:gnd
    path:str='plot.png'
    indice:int=0
    date:str=None
    title:str='plot'
    text:str=False
    pos_text:tuple=False
    annotate:str=False
    pos_annotate:tuple=False
    text_color:str='white'
    text_size=9
    fontweight_text='bold'
    facecolor_text:str='red'
    edgecolor_text:str='white'
    annotate_size:float=9
    annotate_color:str='white'
    loc_focus:tuple=(0,0)
    key_noaa:str='tmpmwl'
    subtr_data:str=273,
    text_cb:str='ºC'
    alpha:float=.9
    author:str='@gpftc_ | @reinanbr_'
    level_data:int=25
    resolution:str='i'
    keys:str = ''
    fillcontinents_colors:str = ''
    cmap: ListedColormap = field(default_factory=lambda: ListedColormap(["red", "blue"])) #cmap:plt.cm = plt.cm.inferno
    ax:plt.subplot = plt.subplot(111)
    plt:plt=plt
    
    line_states:float=0.1
    color_line_states:str = 'yellow'
    
    line_countries:float=1.5
    color_line_countries:str='green'
    
    xleft:int=None
    xright:int=None
    yup:int=None
    ydown:int=None
    
    annotate_pos_focus:tuple=None
    annotate_text_focus:str = None
    annotate_color_focus:str = "white"
    annotate_fontweight_focus:str = None
    
    annotate_loc_focus:tuple=None
    annotate_loc_txt:str = None
    annotate_loc_color:str = 'white'
    fontweight_annote_loc:str = None
    #annotate_pos_focus:str = None
    
    
    
    
    def mining_data(self):
        puts('mining data ...')
        self.fillcontinents_colors:str = {'color':'coral','lake_color':'aqua'}
        self.keys = self.dn.get_noaa_keys()
        self.data = self.dn[self.key_noaa][self.indice]-self.subtr_data
        self.data1 = self.dn[self.key_noaa][1]-self.subtr_data
        #import pandas as pd 
        self.lat  = self.dn['lat'][:]
        self.lon  = self.dn['lon'][:]
        puts(f'lat: {len(self.lat)} | lon: {len(self.lon)}')
        self.data = self.dn[self.key_noaa][self.indice]-self.subtr_data
        self.data1 = self.dn[self.key_noaa][1]-self.subtr_data
        puts(f'data: {self.data.shape} | data1: {self.data1.shape}')
        
        #if not self.indice==None:
        self.date_pd=self.dn['time'][self.indice].to_numpy()
        puts(f'date: {self.date_pd}')
        
        self.ts = pd.to_datetime(str(self.date_pd))
        puts(f'ts: {self.ts}') 
        self.date_text = self.ts.strftime('%d %h %Y\n %H:%M UTC')
        puts(f'date_text: {self.date_text}')
        self.min_temp = float(self.data1.min())
        self.max_temp = float(self.data1.max())
        
        puts(f'min temp: {self.min_temp} | max temp: {self.max_temp} | levels: {self.level_data}')
        self.levels = np.linspace(self.min_temp,self.max_temp,int(self.level_data))

    def zoom(self,xright:int=None,xleft:int=None,ydown:int=None,yup:int=None):
        decai = 1000000
        if xleft and xright and yup and ydown:
            puts(f'zooming with xright: {xright} | xleft: {xleft} | yup: {yup} | ydown: {ydown}')
            self.xright = xright*decai
            self.xleft = xleft*decai
            self.yup = yup*decai
            self.ydown = ydown*decai

    def rendering_image(self):
        puts('rendering image ...')
        self.plt.style.use('dark_background')
        puts('creating basemap ...')
        self.m = Basemap(projection='ortho',
                         lat_0=self.loc_focus[0],
                         lon_0=self.loc_focus[1],
                         resolution=self.resolution,llcrnrx=self.xleft, llcrnry=self.ydown, urcrnrx=self.xright, urcrnry=self.yup, 
)
        puts('created basemap')
        #self.m.bluemarble(scale=.5)
        puts('creating meshgrid ...')
        
        self.x, self.y = self.m(*np.meshgrid(self.lon,self.lat))
        puts(f'x: {self.x.shape} | y: {self.y.shape}')
        puts('created meshgrid')
        self.m.fillcontinents(self.fillcontinents_colors['color'],
                             self.fillcontinents_colors['lake_color'])
        puts('filled continents')
        self.m.drawmapboundary(fill_color='aqua')
        puts('draw map boundary')
        self.cm=self.m.contourf(self.x,self.y,self.data,100,
                                alpha=self.alpha,
                                levels=self.levels,
                                cmap=self.cmap)
        puts('contourf created')
        #cm1=plt.contourf(x,y,data1,100,shading='nearest',cmap=plt.get_cmap('inferno'))
        #plt.cla()
        #plt.clf()
        self.cbar=self.plt.colorbar(self.cm,orientation='horizontal',fraction=0.04,pad=-0.1)
        puts('colorbar created')
        self.cbar.ax.tick_params(labelsize=7)
        
        #self.m.bluemarble()
        self.m.drawcoastlines()
        puts('draw coastlines')
        #self.m.drawmapboundary()#fill_color='aqua')
        self.m.drawstates(linewidth=self.line_states,color=self.color_line_states)
        puts('draw states')
        self.m.drawcountries(linewidth=self.line_countries,color=self.color_line_countries)
        puts('draw countries')
        #self.m.drawcountries(linewidth=0.25)
        
        #m.drawmapboundary(fill_color='aqua')

        self.m.drawmeridians(np.arange(0,360,30))
        puts('draw meridians')
        self.m.drawparallels(np.arange(-90,90,30))
        puts('draw parallels')
        #print(dir(m))
        
        
    
    
    def rendering_text(self):
        puts('rendering text ...')
        self.cbar.set_label(self.text_cb,y=0,ha='right',color='white',fontsize=9)
        puts('set colorbar label',self.text_cb)
        self.cbar.ax.set_title(f'by: {self.author}',fontweight='bold',fontsize=9)
        puts('set colorbar title',self.author)
        ticklabs = self.cbar.ax.get_yticklabels()
        puts('set colorbar tick labels',ticklabs)
        self.cbar.ax.set_yticklabels(ticklabs, fontsize=15)
        
        #xn2,yn2=m(-9.52,-40.61)
        puts('setting text ...')
        self.t = self.plt.text(-0.24,0.99,self.date_text, transform=self.ax.transAxes,
                    color='white', fontweight='bold',fontsize=10)
        puts('set date text',self.date_text)
        self.t = self.plt.text(1.06,1,f'*\n{self.key_noaa}:\n{self.keys[self.key_noaa]}',transform=self.ax.transAxes,
                    color='grey', fontweight='bold',fontsize=5)
        puts('set key noaa text',self.key_noaa)
        self.t = self.plt.text(1.08,0.235,'data: GFS 0.25', transform=self.ax.transAxes,
                    color='white', fontweight='bold',fontsize=6)
        puts('set data source text')
        self.t = self.plt.text(1.09,0.21,'NOAA/NASA', transform=self.ax.transAxes,
                    color='grey', fontweight='bold',fontsize=6)
        #t.set_bbox(dict(facecolor='red', alpha=0.81, edgecolor='black'))
        #puts('set data source text',self.dn.source)
        if self.pos_text and self.text:
            puts('setting custom text ...')
            self.t = self.plt.text(self.pos_text[0],self.pos_text[1], self.text, transform=self.ax.transAxes,
                        color=self.text_color, fontweight='bold',fontsize=self.text_size)
            puts('set custom text',self.text)
            self.t.set_bbox(dict(facecolor='red', alpha=0.81, edgecolor='white'))
            puts('set custom text bbox',self.text)
        # anotate data focus
        if self.annotate_text_focus and self.annotate_pos_focus:
        #    puts('writing data focus')
            puts('annotating data focus ...')
            xn,yn=self.m(self.annotate_pos_focus[1],self.annotate_pos_focus[0])
            puts(f'annotate pos focus: {self.annotate_pos_focus} | xn: {xn} | yn: {yn}')
            self.plt.annotate(self.annotate_text_focus,
                              color=self.annotate_color_focus,
                              xy=(xn,yn),
                              fontweight=self.annotate_fontweight_focus,
                              xytext=(xn,yn),
                              xycoords='data',
                              textcoords='data')
            puts('annotated data focus',self.annotate_text_focus)
        # anotate data focus
        if self.annotate_loc_txt and self.annotate_loc_focus:
            puts('annotating data location ...')
          #  puts('writing data focus')
            xn,yn=self.m(self.annotate_loc_focus[1],self.annotate_loc_focus[0])
            puts(f'annotate loc focus: {self.annotate_loc_focus} | xn: {xn} | yn: {yn}')
            self.plt.annotate(self.annotate_loc_txt,
                              color=self.annotate_loc_color,
                              xy=(xn,yn),
                              fontweight=self.fontweight_annote_loc,
                              xytext=(xn,yn),
                              xycoords='data',
                              textcoords='data')
            
        self.plt.title(self.title,fontweight='bold',fontsize=14)
        puts('set title',self.title)
        
        
    def annotate_data_focus(self,txt:str,fontsize:int=None,color:str='white',fontweight:str='bold'):
        puts('annotating data focus ...')
        data_city = self.dn.get_data_from_point(self.loc_focus)
        puts(f'annotating data focus: {self.loc_focus} | key: {self.key_noaa} | indice: {self.indice}')
        post_data = f'{(float(data_city[self.key_noaa].to_pandas()[self.indice]-self.subtr_data)):.2f}'
        puts(f'post data: {post_data}')
        self.annotate_text_focus = txt%{'data':post_data}
        puts(f'annotate text focus: {self.annotate_text_focus}')
        self.annotate_color_focus = color
        puts(f'annotate color focus: {self.annotate_color_focus}')
        self.annotate_fontweight_focus = fontweight
        puts(f'annotate fontweight focus: {self.annotate_fontweight_focus}')
        self.annotate_pos_focus = self.loc_focus
        puts(f'annotate pos focus: {self.annotate_pos_focus}')
        
        
    def annotate_data_loc(self,txt:str,loc:tuple=(40.776676,-73.971321),fontsize:int=None,color:str='white',fontweight:str='bold'):
        puts('annotating data location ...')
        data_city = self.dn.get_data_from_point(loc)
        puts(f'annotating data location: {loc} | key: {self.key_noaa} | indice: {self.indice}')
        post_data = f'{(float(data_city[self.key_noaa].to_pandas().iloc[self.indice]-self.subtr_data)):.2f}'
        puts(f'post data: {post_data}')
        self.annotate_loc_txt = txt%{'data':post_data}
        puts(f'annotate loc txt: {self.annotate_loc_txt}')
        self.annotate_loc_color = color
        puts(f'annotate loc color: {self.annotate_loc_color}')
        self.fontweight_annote_loc = fontweight
        puts(f'annotate loc fontweight: {self.fontweight_annote_loc}')
        self.annotate_loc_focus = loc
        puts(f'annotate loc focus: {self.annotate_loc_focus}')
        
        
    def render(self,show=True,save=True):
        puts('rendering plot ...')
        self.plt.style.use('dark_background')
        
       # puts('getting data ..')
       
        self.mining_data()
       # puts('getted data')
        
      #  puts('renderinzing plot ...')
        self.rendering_image()
        self.rendering_text()
     #   puts('renderinzed plot')
        
        if save:
         #   puts('saving plot ...')
            self.plt.savefig(self.path,dpi=600)
        #    puts('saved plot')
#        if show:
        #    self.plt.show()
        self.plt.cla()
        self.plt.clf()

