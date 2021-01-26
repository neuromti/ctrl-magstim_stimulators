# -*- coding: utf-8 -*-
"""
Created on Tue Nov 17 09:43:05 2020

@author: roboTMS
"""

import horizon
import time

if __name__ == "__main__":
# otherwise ever-increasing number of additional processes
#as the main script is imported in the child processes
    
    stimulator = horizon.Horizon('COM4', unlockCode='7cef-5b86b67b-0a')
    #ths creates two additional Python processes:
    #one for the purposes of directly controlling the serial port
    #and another for maintaining constant contact
    stimulator.connect()
    errorCode,parameterInfo = stimulator.getParameters()
    
    print('Temperature: ', stimulator.getTemperature()[1])
    print('Version: ', stimulator.getVersion()[1])
    print('System Settings: ', stimulator.getSystemStatus()[1])
    time.sleep(3)
    
    stimulator.rTMSMode(enable=False)
    
    time.sleep(1)
    
    stimulator.setPower(newPower=60)
    
    stimulator.arm(delay=True)
    stimulator.fire()
   
    time.sleep(1)
    
    stimulator.setPower(newPower=80)
    
    time.sleep(3)
    
    stimulator.arm(delay=True)
    stimulator.quickFire(2000)

    time.sleep(1)
    
    #%% for testing repetitive mode

    stimulator.rTMSMode(enable=True, receipt=True)
    time.sleep(3)
    
    print('System Settings: ', stimulator.getSystemStatus()[1])
    
    newDuration=2
    newFrequency=1
    newNPulses=4
    
    stimulator.setDuration(newDuration, receipt=False) #in seconds
    stimulator.setFrequency(newFrequency, receipt=True) #in Hz
    stimulator.setNPulses(newNPulses, receipt=False) #number of pulses
    
    #ensure that the current parameters would not violate the maximum 'on time'
    stimulator.validateSequence()
    time.sleep(2)
    
    stimulator.arm(delay=True)
    time.sleep(1)
    stimulator.fire()
    #return to single-pulse mode
    time.sleep(2)
    stimulator.rTMSMode(enable=False)
    time.sleep(2)
    
    print('System Settings: ', stimulator.getSystemStatus()[1])
    time.sleep(3)
   # #horizon.setDuration(0)
    
    #%%%
    
    stimulator.disconnect()
    
    if not stimulator.connectiontype == 'virtual':
        stimulator._qfb.interface.close()
        

    
    