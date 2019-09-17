import scripts.batterycharger as bc
import numpy as np
import pandas as pd

from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Panel
from bokeh.models.widgets import Slider, Tabs, RadioButtonGroup, PreText

from bokeh.layouts import column, row, WidgetBox, gridplot
from bokeh.palettes import Category20_16

def chargetime_tab():
    
    def make_dataset(padaptor=45,psystem=0,ichargermax=7, soc=0.01, Whr=60):
        data=bc.batterystate_vs_t(bc.Charger(bc.Adapter(power=padaptor), bc.Battery(soc=soc,Whr=Whr),
                                             psystem=psystem, imax=ichargermax))
        chargetime = str(data[0][-1])+'hrs'
        df=pd.DataFrame(np.array(data[1:]).T,index=data[0],columns=['SOC','pout','vbat','vsys','iout','icharge'])
        df.index.name='time(hr)'
        return ColumnDataSource(df)
    
    def make_plot(src,yaxis,plotnum):
        p = figure(plot_height = 200, plot_width = 200, 
                   title = yaxis,
                   x_axis_label = 'time (hr)')
        p.line(x='time(hr)', y=yaxis, source=src, line_width=2, color=Category20_16[plotnum*2])
        return p
    
    def update(attr, old, new):
        new_src = make_dataset(padaptor=adaptoroptions[padaptor_select.active],
                               Whr=batteryoptions[ebattery_select.active],
                               psystem=psystem_select.value,
                               ichargermax=imax_select.value)
        src.data.update(new_src.data)
        
# create input control widgets        
    adaptoroptions=[45,65,90]
    adaptorselecttitle = PreText(text="Padaptor(W)")
    
    batteryoptions=[52,60,68]
    batteryselecttitle = PreText(text="Battery Capacity(Whr)")
    
    padaptor_select = RadioButtonGroup(name="Padaptor", labels=[str(element) for element in adaptoroptions], active=0)
    padaptor_select.on_change('active', update)
    
    ebattery_select = RadioButtonGroup(name="Ebattery", labels=[str(element) for element in batteryoptions], active=0)
    ebattery_select.on_change('active', update)
    
    psystem_select = Slider(start=0, end=60, value=0, step=5, title="Psystem")
    psystem_select.on_change('value', update)
    
    imax_select = Slider(start=5, end=12, value=5, step=0.5, title="Max Total Current")
    imax_select.on_change('value', update)

# calculate the state of the system
    src = make_dataset(padaptor=adaptoroptions[padaptor_select.active],
                       Whr=batteryoptions[ebattery_select.active],
                       psystem=psystem_select.value,
                       ichargermax=imax_select.value)
    
# create grid of plots
    plot_names = ['SOC','pout','vbat','vsys','iout','icharge']    
    plot_figs = {}
    for plot_num, plot_yaxis in enumerate(plot_names):
        plot_figs[plot_yaxis] = make_plot(src,plot_yaxis,plot_num)
    
    grid = gridplot([[plot_figs['pout'], plot_figs['vsys'], plot_figs['iout']],
                     [plot_figs['SOC'],  plot_figs['vbat'], plot_figs['icharge']]])
    
# Link together the x-axes for panning and zooming
    plot_figs['SOC'].x_range = \
    plot_figs['vbat'].x_range = \
    plot_figs['icharge'].x_range = \
    plot_figs['pout'].x_range = \
    plot_figs['vsys'].x_range = \
    plot_figs['iout'].x_range

# set up the display panel
    controls = WidgetBox(adaptorselecttitle,
                         padaptor_select,
                         psystem_select,
                         imax_select,
                         batteryselecttitle,
                         ebattery_select)
    layout = row(controls,grid)
    tab = Panel(child=layout, title = "Charger State vs. Time")
    
    return tab