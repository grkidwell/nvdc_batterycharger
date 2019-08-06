# author: Gary Kidwell
# modified from 'dellbaten.py' program authored by Anthony Alonzo

# The pi GPIO demon must first be run with the bash command, 'sudo pigpiod'

import pigpio, time, sys
import battery_registers as batreg

def s16(value):   #
    return -(value & 0x8000) | (value & 0x7fff)

def read_battery_status(batt_addr_dict,pi):

    BUS = 1 #Bus that the Pi is using for communication
    ADDR = 0X0B #Address of the battery
    open_bus = pi.i2c_open(BUS,ADDR) # open i2c bus

    batt_value_dict = {}
    for reg_name, reg_addr in batt_addr_dict.items():
        #Write the address to be read to the battery
        try:
            pi.i2c_write_device(open_bus,reg_addr)
        except Exception as e:
            print('def read_back_check; ',e,'; address',reg_addr,' ;Type: ',type(e))
            print('Arguments for Fail: ', e.args)
            next
        time.sleep(0.2)
        # Read back the data
        bytenum=2
        try:
            byteArray = pi.i2c_read_device(open_bus,bytenum)[1]
        except:
            print('byte read fail')
        # Flip the byte order and convert to hex
        hexbyteArray = ''
        for byte in reversed(byteArray):
            hexbyteArray += (format(byte,'x'))
        intvalue= s16(int(hexbyteArray,16))
        #intvalue =
        #print(intvalue)
        # scale each value
        scalefactor = batreg.scale_dict[reg_name]
        if reg_name == 'Temp':
            intvalue = round((intvalue * .1 - 273),2)
        batt_value_dict[reg_name] = intvalue*scalefactor

    pi.i2c_close(open_bus) # close the i2c bus
    return batt_value_dict

def print_battery_state(batt_value_dict):
    for name, value in batt_value_dict.items():
        print("%s: %s" % (name,value))

def main():
    while True:
        try:
            battery_state = read_battery_status(batreg.abrev_addr_dict,pigpio.pi())
            print_battery_state(battery_state)
            print()
        except:
            print("if first you don't succeed.....")
        time.sleep(1)

if __name__ =="__main__":
    main()
