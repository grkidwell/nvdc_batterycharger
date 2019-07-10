
# coding: utf-8

import numpy as np

class Battery:
  
    def __init__(self,nstack=2,Whr=50, soc=0.3):
    
        self.nstack=nstack    # 2S, 3S, or 4S
        self.Whr=Whr          # Watt*hrs
        self.soc=soc          # state of charge.  0.01 to 1  (1% to 100%)
    
        self.vcellmin=3.0
        self.vcellnom=3.7
        self.vcellmax=4.35
    
        self.res=0.2  # Rbattery.  Path resistance, in Ohms, between the battery and charger output. Includes cell chemistry + busbar+connectors+cable+beads+pcb+BFET
    
        self.vmin=self.nstack*self.vcellmin
        self.vnom=self.nstack*self.vcellnom
        self.vmax=self.nstack*self.vcellmax
    
        self.Ahr=self.Whr/self.vnom   #Amp*hrs
    
        k=[3.542,1.391,6.43e-3,2.683]  #coefficients from Mathcad curve fit
        vcell=k[0]+k[1]*np.exp(-k[3]*(1-self.soc))-k[2]/(self.soc+.001)
    
        self.voltage=max(self.vmin,min(self.vmax, self.nstack*vcell))  #battery voltage has upper and lower clamp
    
        m=[17.5,1,0.1]  #coefficients from Mathcad curve fit
        self.irate= min(0.8,m[0]*(self.soc-m[1])**2 + m[2])
      
        self.ibat_cv = self.irate*self.Ahr   #load that the battery presents during cv charge mode (>80% SOC)
                                             #when charging curring decays to 10%, SOC=100 and charger should turn off BFET
      
      
 
class Adaptor:
  
    def __init__(self, power=60, voltage=20):
  
        Aclim_tol  = 0.05
    
        self.power=power*(1-Aclim_tol)
        self.voltage=voltage
    
        self.ilim=self.power*(1-Aclim_tol)/voltage

    
    
    
class Charger:
  
    def __init__(self, adaptor, battery, psystem=0, imax=7.5):  #adaptor and battery are objects
  
        Efficiency = 0.95
        self.pmax=adaptor.power*Efficiency
        self.imax=imax
        self.psys=psystem
    
        self.nstack=battery.nstack
        self.Whr=battery.Whr
        self.rbat=battery.res
      
        voltheadroom=0.3      #because of rbat, vsys must be > vbat to charge battery past soc=80%
        self.vsysmax=battery.vmax+voltheadroom
        self.vsysmin=battery.vmin     
        self.vbat=battery.voltage
        self.soc=battery.soc
    
      
        self.ichargemax=0.8*battery.Ahr       #charging current limited by battery and charger setting
      
        self.VRhot = False
      
      

    
        # 4 control loops - adaptor power, charge current, system voltage, max charger current
        # each loop returns 4 state variables, 1 for each control loop

          
        def loop_adaptorpwr():
            '''
      Derive quadratic equation for Vsys at max output power.  roots will be complex when Psys>Padaptor.  
      but there should be a real solution for when negative current in battery simplest band aid is to flip 
      polarity of "c" quad coeff when this is the case or perhaps taking magnitude of complex root will give 
      the proper solution of Vsys.  need to verify.

      Vsys = Vbat + icharge*Rbat
           = Vbat + (iout-isys)*Rbat
           = Vbat + (Pmax/Vsys - Psys/Vsys)*Rbat
           = Vbat + (Pmax-Psys)/Vsys*Rbat
           
      Vsys^2 - Vbat*Vsys - (Pmax-Psys)Rbat = 0
            '''
            quadcoeff = [1, -self.vbat, -(self.pmax-self.psys)*self.rbat]
            vsys = max(np.roots(quadcoeff))
            iout = self.pmax/vsys
            icharge = (vsys - self.vbat)/self.rbat
            if self.soc >=0.99:
                icharge = 0
                vsys = self.vsysmax
                iout = self.psys/vsys
            self.pout = vsys*iout
            return [self.pout,icharge,vsys,iout]
    
        def loop_chargecurrent():
            vsys = self.vbat + self.ichargemax*self.rbat
            pout = vsys*self.ichargemax + self.psys
            iout = pout/vsys
            return [pout,self.ichargemax,vsys,iout]

        def loop_voltage():
            icharge_rpath_limited = (self.vsysmax-self.vbat)/self.rbat
            if self.soc<0.8:  
                icharge = icharge_rpath_limited
                vsys = self.vsysmax
            elif self.soc >= 0.99:
                icharge = 0
                vsys = self.vsysmax

            else: #in CV charge mode (SOC>80%), the battery sets the charge current.  BIOS turns off charger when SOC =100%
                icharge = min(icharge_rpath_limited,battery.ibat_cv)
                vsys = self.vsysmax #self.vbat + icharge*self.rbat
            pout = vsys*icharge + self.psys
            iout = pout/vsys
            return [pout,icharge,vsys,iout]

        def loop_maxcurrent():
            '''
      Derive quadratic equation for Vsys at max output current
      
      Vsys = Vbat + icharge*Rbat
           = Vbat + (imax- Psys/Vsys)*Rbat
           = Vbat + imax*Rbat - Psys*Rbat/Vsys
           
      Vsys^2 - (Vbat+imax*Rbat)Vsys + Psys*Rbat = 0
            '''
            quadcoeff = [1, -(self.vbat+self.imax*self.rbat), self.psys*self.rbat]
            vsys = max(np.roots(quadcoeff))
            icharge = (vsys - self.vbat)/self.rbat
            pout = vsys*icharge + self.psys
            return [pout,icharge,vsys,self.imax]
        
        def min_error_idx(listoflists):
            def all_pos(list):
                flag=True
                for i in list:
                    if i < 0:
                        flag=False
                return flag
            min_error = min([min(errors) for errors in listoflists if all_pos(errors)])
            idx = [i for i, errors in enumerate(listoflists) if min(errors) == min_error][0]
            return idx
        
#Main init program.  First run all loops.  The loop with all positive errors AND the lowest error establishes the state of the charger

        #if self.psys   > self.pmax:     #throttle system by setting VRhot. Will eventually want to allow power drawn from battery
            # self.psys  = self.pmax
            # self.VRhot = True
    
        charger_refs = [self.pmax,self.ichargemax,self.vsysmax,self.imax]
        loop_list    = [loop_adaptorpwr,loop_chargecurrent,loop_voltage,loop_maxcurrent] 
        
        charger_states_by_loop = [loop() for loop in loop_list]  #remember that each loop function returns a 4 element list of charger attributes/params
        loop_errors_by_loop = []
        for charger_state in charger_states_by_loop:
            loop_errors_by_loop.append([ref - charger_state[i] for i, ref in enumerate(charger_refs)])
        try:
            idx = min_error_idx(loop_errors_by_loop)
            charger_state_dominant = charger_states_by_loop[idx]
            if idx==3:
                self.VRhot = True
        except:
            print(loop_errors_by_loop)
        
        self.pout, self.icharge, self.vsys, self.iout = charger_state_dominant   
        
def batterystate_vs_t(charger):
    adaptor_state=Adaptor(power=charger.pmax)
          
    battery_stack=charger.nstack
    battery_Whr=charger.Whr
        
    system_power=charger.psys
    charger_maxcurrent=charger.imax
        
    timestep_hrs=1/60   
    soc_cum=charger.soc
    idx=0
    timelist=[] 
    soclist=[]
    vbatlist=[]
    ichargelist=[]
    while soc_cum < 1:
        battery_state = Battery(battery_stack,battery_Whr,soc=soc_cum)
        charger_state = Charger(adaptor_state,battery_state,psystem=system_power,imax=charger_maxcurrent)
        ichargerate   = charger_state.icharge*1/battery_state.Ahr
        soc_cum       = soc_cum + ichargerate*timestep_hrs
        timelist.append(idx*timestep_hrs)
        soclist.append(soc_cum)
        vbatlist.append(battery_state.voltage)
        ichargelist.append(ichargerate)
        idx+=1
    return [timelist,soclist,vbatlist,ichargelist]
    

            
