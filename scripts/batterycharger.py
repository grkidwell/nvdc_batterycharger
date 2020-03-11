
# coding: utf-8

#TO DO:  add power throttling to prevent batt discharge when SOC < 20% or whatever

import numpy as np

class Battery:
  
    def __init__(self,nstack=2,Whr=50,soc=0.3,res=0.1):
    
        self.nstack=nstack    # 2S, 3S, or 4S
        self.Whr=Whr          # Watt*hrs
        self.soc=soc          # state of charge.  0.01 to 1  (1% to 100%)
    
        self.vcellmin=3.0
        self.vcellnom=3.7
        self.vcellmax=4.35
    
        self.res=res # Rbattery.  Path resistance, in Ohms, between the battery and charger output. Includes cell chemistry + busbar+connectors+cable+beads+pcb+BFET
    
        self.vmin=self.nstack*self.vcellmin
        self.vnom=self.nstack*self.vcellnom
        self.vmax=self.nstack*self.vcellmax
    
        self.Ahr=self.Whr/self.vnom   #Amp*hrs
    
        k=[3.542,1.391,6.43e-3,2.683]  #coefficients from Mathcad curve fit
        vcell=k[0]+k[1]*np.exp(-k[3]*(1-self.soc))-k[2]/(self.soc+.001)
    
        self.voltage=max(self.vmin,min(self.vmax, self.nstack*vcell))  #battery voltage has upper and lower clamp
    
        #m=[17.5,1,0.1]  #coefficients from Mathcad curve fit
        m=[9.5,1,0.1]  #coefficients from Mathcad curve fit
        #when soc <80%, charger sets charge current from value provided by battery.
        #when soc >=80%, battery chemistry limits charge current.  battery impedance increases until SOC=100%, when smart
        #battery will then open its charge FET
        self.irate= min(1,m[0]*(self.soc-m[1])**2 + m[2])*0**(self.soc>0.99)
      
        self.ibat_max = self.irate*self.Ahr   
      
      
 
class Adapter:
  
    def __init__(self, power=60, voltage=20):
        
        self.rating=power
        Aclim_tol  = 0.05
    
        self.power=power*(1-Aclim_tol)
        self.voltage=voltage
    
        self.ilim=self.power*(1-Aclim_tol)/voltage

    
    
    
class Charger:
  
    def __init__(self, adapter, battery, psystem=0, imax=7.5, maxrate=0.9):  #adapter and battery are objects
        
        self.adapter = adapter
        Efficiency = 0.95
        self.pmax=self.adapter.power*Efficiency
        self.imax=imax
        self.psys=psystem
        self.maxrate=maxrate

        self.battery=battery
    
        voltheadroom=0.3      #because of rbat, vsys must be > vbat to charge battery past soc=80%
        self.vsysmax=battery.vmax+voltheadroom
        self.vsysmin=battery.vmin     
        
        self.ichargemax=self.maxrate*battery.Ahr       #charging current limited by battery and charger setting
      
        self.VRhot = False
      
            
        # 4 control loops - adapter power, charge current, system voltage, max charger current
        # each loop returns 4 state variables, 1 for each control loop

        def quadsolver(coeff):
            a, b, c = coeff
            return (-b+(b**2-4*a*c)**0.5)/(2*a)
          
        def loop_adapterpwr():
            '''
      Derive quadratic equation for Vsys at max output power.  roots will be complex when Psys>Padapter.  
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
            quadcoeff = [1, -self.battery.voltage, -(self.pmax-self.psys)*self.battery.res]
            #vsys1 = max(np.roots(quadcoeff))   
            
            #assumes charge current is limited by parasitic resistance rbat

            vsys1 = quadsolver(quadcoeff)
            
            #in CV charge mode (SOC>80%), the smart battery's charge FET limits the max vbat voltage?  
            #Battery charge FET turns off when SOC =100%
            icharge = min(self.ichargemax,(vsys1-self.battery.voltage)/self.battery.res)
            
            vsys = self.battery.voltage + icharge*self.battery.res
            isys = self.psys/vsys
            iout = icharge + isys 

            self.pout = vsys*iout - 0.01
            return [self.pout,icharge,vsys,iout]
    
        def loop_chargecurrent():
            vsys = self.battery.voltage + self.ichargemax*self.battery.res
            pout = vsys*self.ichargemax + self.psys
            iout = pout/vsys
            return [pout,self.ichargemax,vsys,iout]

        def loop_voltage():
            vsys = self.vsysmax
            icharge_rpath_limited = (vsys-self.battery.voltage)/self.battery.res

            #in CV charge mode (SOC>80%), the battery charge FET limits the max vbat voltage and the battery chemistry limits the charge current.  
            #Battery charge FET turns off when SOC =100%
            #icharge_battery_limited = self.ichargemax
            icharge_battery_limited = self.battery.irate*self.ichargemax

            #icharge = min(icharge_rpath_limited,icharge_battery_limited)
            icharge = icharge_rpath_limited*self.battery.irate
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
            quadcoeff = [1, -(self.battery.voltage+self.imax*self.battery.res), self.psys*self.battery.res]
            #vsys = max(np.roots(quadcoeff))
            vsys = quadsolver(quadcoeff)
            icharge = (vsys - self.battery.voltage)/self.battery.res
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

        def min_error_idx_numpy(errorlistoflists):
            '''
        The dominant control loop(Padaptor,Icharge,Vsysmax,Iout) defines the state of the system, which consists of
        the 4 state variables: pout,icharge,vsys,iout 
        This function determines which control loop is dominant by checking 2 criteria:
        1) all 4 state variable have positive errors (no controlled parameter is > it's reference threshold)
        2) contains the state variable with the smallest error of those states satisfying criteria #1.

            '''
            errorarray=np.array(errorlistoflists)
            positive_threshold = -0.01  #small offset to "positive error" criteria   
            posmask_by_element = errorarray>=positive_threshold
            posmask_by_loop = np.all(posmask_by_element,axis=1) #all errors in loop >= threshold
            min_pos_error = np.amin(errorarray[np.all(errorarray>=positive_threshold, axis=1)])
            for loop, errors in enumerate(errorarray):
                if posmask_by_loop[loop] and np.amin(errors)== min_pos_error:
                    idx = loop
            return idx
        
#Main init program.  First run all loops.  The loop with all positive errors AND the lowest error establishes the state of the charger

        #if self.psys   > self.pmax:     #throttle system by setting VRhot. Will eventually want to allow power drawn from battery
        #    self.psys  = self.pmax
            # self.VRhot = True
    
        charger_refs = [round(x,2) for x in [self.pmax,self.ichargemax,self.vsysmax,self.imax]]
        loop_list    = [loop_adapterpwr,loop_chargecurrent,loop_voltage,loop_maxcurrent]
        
        self.charger_states_by_loop = [loop() for loop in loop_list]  #remember that each loop function returns a 4 element list of charger attributes/params
        loop_errors_by_loop = []
        for charger_state in self.charger_states_by_loop:
            loop_errors_by_loop.append([(ref - charger_state[i]) for i, ref in enumerate(charger_refs)])  #round delta
        try:
            idx = min_error_idx_numpy(loop_errors_by_loop)
            charger_state_dominant = self.charger_states_by_loop[idx]
            if idx==3:
                self.VRhot = True
        except:
            print(charger_refs)
            print(self.charger_states_by_loop)
            print(loop_errors_by_loop)
        
        self.pout, self.icharge, self.vsys, self.iout = charger_state_dominant   
        self.charger_state = charger_state_dominant
        self.error_state = loop_errors_by_loop[idx]
        self.error_idx = idx
        #elf.csbl=charger_states_by_loop

def batterystate_vs_t(charger):
    adapter_state=Adapter(power=charger.adapter.rating)   
          
    battery_stack=charger.battery.nstack
    battery_Whr=charger.battery.Whr
        
    system_power=charger.psys
    charger_maxcurrent=charger.imax
    charger_maxrate=charger.maxrate
        
    timestep_hrs=1/60   
    soc_cum=charger.battery.soc
    idx=0
    timelist=[] 
    soclist=[]
    poutlist=[]
    vbatlist=[]
    vsyslist=[]
    ioutlist=[]
    ichargelist=[]
    looplist=[]
    errorlist=[]

    while soc_cum < 0.99 and idx < 600:
        battery_state = Battery(battery_stack,battery_Whr,soc=soc_cum)
        charger_state = Charger(adapter_state,battery_state,psystem=system_power,imax=charger_maxcurrent,maxrate=charger_maxrate)
        ichargerate   = charger_state.icharge*1/battery_state.Ahr
        soc_cum       = soc_cum + ichargerate*timestep_hrs
        timelist.append(round(idx*timestep_hrs,3))
        soclist.append(soc_cum)
        poutlist.append(charger_state.pout)
        vbatlist.append(battery_state.voltage)
        vsyslist.append(charger_state.vsys)
        ioutlist.append(charger_state.iout)
        ichargelist.append(charger_state.icharge) #ichargerate)
        looplist.append(charger_state.error_idx)
        cs = [round(x,2) for x in charger_state.error_state]
        errorlist.append(cs)
        idx+=1
    return [timelist,soclist,poutlist,vbatlist,vsyslist,ioutlist,ichargelist,looplist,errorlist]

#need to look at below function.  may only need charger object as input parameter.
def chargetime(vadapter=20,padapter=60,ncell=2, whr=50, psystem=0,imax=8,maxrate=0.8):
    adapter = Adapter(padapter,vadapter)
    battery = Battery(ncell,whr,soc=0.01)
    charger = Charger(adapter,battery,psystem,imax,maxrate)
    time_list = batterystate_vs_t(charger)[0]
    return time_list[-1]   #returns last element in time list
    

            
