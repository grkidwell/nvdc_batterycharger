# author: Gary Kidwell

# The pi GPIO demon must first be run with the bash command, 'sudo pigpiod'

import pigpio, time


def enter_shipmode(pi):

    BUS = 1 #Bus that the Pi is using for communication
    ADDR = 0X0B #Address of the battery
    open_bus = pi.i2c_open(BUS,ADDR) # open i2c bus
    reg_addr = [0x00,0x80]
    reg_data = [0x00,0x10,0x00]
    for i in range(2):
        try:
            pi.i2c_write_device(open_bus,reg_addr)
            time.sleep(0.1)
            pi.i2c_write_device(open_bus,reg_data)
        except:
            print('failed to write to SMBus')

        time.sleep(1)

    pi.i2c_close(open_bus) # close the i2c bus



def main():
    enter_shipmode(pigpio.pi())

if __name__ =="__main__":
    main()