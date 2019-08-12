
# coding: utf-8

#TO DO:  add power throttling to prevent batt discharge when SOC < 20% or whatever

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
        #when soc <80%, charger sets charge current from value provided by battery.
        #when soc >=80%, battery chemistry limits charge current.  battery impedance increases until SOC=100%, when smart
        #battery will then open its charge FET
        self.irate= min(0.8,m[0]*(self.soc-m[1])**2 + m[2])*0**(self.soc>0.999)
      
        self.ibat_max = self.irate*self.Ahr   
      
      
 
class Adaptor:
  
    def __init__(self, power=60, voltage=20):
        
        self.rating=power
        Aclim_tol  = 0.05
    
        self.power=power*(1-Aclim_tol)
        self.voltage=voltage
    
        self.ilim=self.power*(1-Aclim_tol)/voltage

    
    
    
class Charger:
  
    def __init__(self, adaptor, battery, psystem=0, imax=7.5):  #adaptor and battery are objects
        
        self.adaptor_rating=adaptor.rating
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

        def quadsolver(coeff):
            a, b, c = coeff
            return (-b+(b**2-4*a*c)**0.5)/(2*a)
          
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

      x = [-b +/- sqrt(b^2 - 4ac)]/2a

      Vsys = [Vbat + sqrt(Vbat^2 + 4(Pmax-Psys)Rbat)]/2

      above solution is imaginary if:

      Vbat^2 < 4(Psys-Pmax)Rbat
      Vbat^2/(4Rbat) < Psys-Pmax
      36/0.8 < Psys-Pmax   - depleted 2S battery
      45 < Psys - Pmax

      note also that Vsys = Vbat/2 at this condition.
            '''
            quadcoeff = [1, -self.vbat, -(self.pmax-self.psys)*self.rbat]
            #vsys1 = max(np.roots(quadcoeff))   
            
            #assumes charge current is limited by parasitic resistance rbat

            vsys1 = quadsolver(quadcoeff)
            
            #in CV charge mode (SOC>80%), the smart battery's charge FET limits the max vbat voltage and the battery chemistry limits the charge current.  
            #Battery charge FET turns off when SOC =100%
            icharge = min(battery.ibat_max,(vsys1-self.vbat)/self.rbat)
            
            vsys = self.vbat + icharge*self.rbat
            isys = self.psys/vsys
            iout = icharge + isys 

            self.pout = vsys*iout
            return [self.pout,icharge,vsys,iout]
    
        def loop_chargecurrent():
            vsys = self.vbat + self.ichargemax*self.rbat
            pout = vsys*self.ichargemax + self.psys
            iout = pout/vsys
            return [pout,self.ichargemax,vsys,iout]

        def loop_voltage():
            vsys = self.vsysmax
            icharge_rpath_limited = (vsys-self.vbat)/self.rbat

            #in CV charge mode (SOC>80%), the battery charge FET limits the max vbat voltage and the battery chemistry limits the charge current.  
            #Battery charge FET turns off when SOC =100%
            icharge = min(battery.ibat_max,icharge_rpath_limited)
            pout = vsys*icharge + self.psys
            iout = pout/vsys
            return [pout,icharge,vsys,iout]

        def loop_maxcurrent():   #a new loop designed to limit the FET and inductor current, specifically when vbat=low and psys=high.  system will
            #need to throttle when this loop engages.  
            '''
      Derive quadratic equation for Vsys at max output current
      
      Vsys = Vbat + icharge*Rbat
           = Vbat + (imax- Psys/Vsys)*Rbat
           = Vbat + imax*Rbat - Psys*Rbat/Vsys
           
      Vsys^2 - (Vbat+imax*Rbat)Vsys + Psys*Rbat = 0
            '''
            quadcoeff = [1, -(self.vbat+self.imax*self.rbat), self.psys*self.rbat]
            #vsys = max(np.roots(quadcoeff))
            vsys = quadsolver(quadcoeff)
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
        #    self.psys  = self.pmax
            # self.VRhot = True
    
        charger_refs = [round(x,2) for x in [self.pmax,self.ichargemax,self.vsysmax,self.imax]]
        loop_list    = [loop_adaptorpwr,loop_chargecurrent,loop_voltage,loop_maxcurrent]
        
        charger_states_by_loop = [loop() for loop in loop_list]  #remember that each loop function returns a 4 element list of charger attributes/params
        loop_errors_by_loop = []
        for charger_state in charger_states_by_loop:
            loop_errors_by_loop.append([round(ref - charger_state[i],2) for i, ref in enumerate(charger_refs)])
        try:
            idx = min_error_idx(loop_errors_by_loop)
            charger_state_dominant = charger_states_by_loop[idx]
            if idx==3:
                self.VRhot = True
        except:
            print(charger_refs)
            print(charger_states_by_loop)
            print(loop_errors_by_loop)
        
        self.pout, self.icharge, self.vsys, self.iout = charger_state_dominant   
        self.charger_state = charger_state_dominant
        
def batterystate_vs_t(charger):
    adaptor_state=Adaptor(power=charger.adaptor_rating)   
          
    battery_stack=charger.nstack
    battery_Whr=charger.Whr
        
    system_power=charger.psys
    charger_maxcurrent=charger.imax
        
    timestep_hrs=1/60   
    soc_cum=charger.soc
    idx=0
    timelist=[] 
    soclist=[]
    poutlist=[]
    vbatlist=[]
    vsyslist=[]
    ioutlist=[]
    ichargelist=[]
    while soc_cum < 0.99 and idx < 600:
        battery_state = Battery(battery_stack,battery_Whr,soc=soc_cum)
        charger_state = Charger(adaptor_state,battery_state,psystem=system_power,imax=charger_maxcurrent)
        ichargerate   = charger_state.icharge*1/battery_state.Ahr
        soc_cum       = soc_cum + ichargerate*timestep_hrs
        timelist.append(round(idx*timestep_hrs,2))
        soclist.append(soc_cum)
        poutlist.append(charger_state.pout)
        vbatlist.append(battery_state.voltage)
        vsyslist.append(charger_state.vsys)
        ioutlist.append(charger_state.iout)
        ichargelist.append(charger_state.icharge) #ichargerate)
        idx+=1
    return [timelist,soclist,poutlist,vbatlist,vsyslist,ioutlist,ichargelist]

def chargetime(vadaptor=20,padaptor=60,ncell=2, whr=50, psystem=0,imax=8):
    adaptor = Adaptor(padaptor,vadaptor)
    battery = Battery(ncell,whr,soc=0.01)
    charger = Charger(adaptor,battery,psystem,imax)
    time_list = batterystate_vs_t(charger)[0]
    return time_list[-1]   #returns last element in time list
    

            
