import batterycharger as bc
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
plt.style.use('seaborn')

import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

root= tk.Tk()

soc=0.1
padaptor=65
ichargermax=7



def nvdc_system(event):
    psystem=var.get()
    data=bc.batterystate_vs_t(bc.Charger(bc.Adapter(power=padaptor),bc.Battery(soc=soc),psystem=psystem, imax=ichargermax))
    chargetime = str(data[0][-1])+'hrs'
    df=pd.DataFrame(np.array(data[1:]).T,index=data[0],columns=['SOC','pout','vbat','vsys','iout','icharge'])
    df.index.name='time(hr)'
    df1=df['SOC']
    figure1 = plt.Figure(figsize=(5,4), dpi=100)
    ax1 = figure1.add_subplot(111)
    line1 = FigureCanvasTkAgg(figure1, root)
    line1.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH)
    df1.plot(kind='line', legend=True, ax=ax1, color='r', fontsize=10)    

def change_(slider_value):
    welcome_message.size=slider_value


var=tk.IntVar()
psys = tk.Scale(root, from_=0, to=60,variable=var)#,command=nvdc_system)
psys.set(0)
psys.bind('<ButtonRelease>', nvdc_system)
psys.pack()
#nvdc_system(padaptor,psystem,ichargermax)





#ax2.set_title('Year Vs. Unemployment Rate')

#df.plot(subplots=True, layout=(3,2),figsize=(10,10),sharex=False,use_index=True)

root.mainloop()