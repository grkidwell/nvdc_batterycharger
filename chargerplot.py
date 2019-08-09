import batterycharger as bc 
import numpy as np 
import matplotlib as plt 

plt.style.use('seaborn')

socvar = np.arange(.01,1.01,.01)
vbatlist = []
ibatlist = []
for i in socvar:
  vbatlist.append(bc.Battery(2,50,soc=i).voltage) 
  ibatlist.append(bc.Battery(2,50,soc=i).irate)
fig, ax1 = plt.subplots()

ax1.plot(socvar,vbatlist,color='r')
ax2 = ax1.twinx()

ax2.plot(socvar,ibatlist,color='b')

ax1.set_xlabel('SOC')
ax1.set_ylabel('Voltage')
ax2.set_ylabel('Charge Rate')
plt.title("bc.Battery Voltage and Charge Rate vs. State of Charge" , fontsize=16)
plt.show()