# -*- coding: utf-8 -*-
"""
Created on Tue Nov 17 11:13:37 2020

@author: roboTMS
"""

from __future__ import division
from multiprocessing import Pipe
from threading import Thread
from sys import version_info, platform
from os.path import realpath, join, dirname
from os import getcwd
from magstim import calcCRC, MagstimError
from collections import OrderedDict
from math import ceil, floor
from threading import Timer
from yaml import load
from ast import literal_eval
from _virtual import virtualMagstim, virtualPortController, default_timer
from base import Mock

class QuickFireBox(Mock):
    """For Triggering with low latency a second box is used."""
      
    def acknowledge(self, state=1):
        msg = self.encode(b'\x06', state)
        self.write(msg)
    
    def trigger(self, duration_in_us=1000):
        """Trigger the BNC default for 1ms.
        
        Parameters
        ----------
        duration_in_us : int
            trigger duration in microseconds
        """
        msg = self.encode(b'\x21', max(0, min((duration_in_us, 10000))))
        self.write(msg)

class virtualHorizon(virtualMagstim):

    # Load settings file (resort to default values if not found)
    __location__ = realpath(join(getcwd(), dirname(__file__)))
    try:
        with open(join(__location__, 'rapid_config.yaml')) as yaml_file:
            config_data = load(yaml_file)
    except:
        DEFAULT_VOLTAGE = 240
        DEFAULT_UNLOCK_CODE = ''
        ENFORCE_ENERGY_SAFETY = True
        DEFAULT_VIRTUAL_VERSION = (5,0,0)
        DEFAULT_UNLOCK_CODE = '1234-12345678-ý\x91'
    else:
        DEFAULT_VOLTAGE = config_data['defaultVoltage']
        DEFAULT_UNLOCK_CODE = config_data['unlockCode']
        ENFORCE_ENERGY_SAFETY = config_data['enforceEnergySafety']
        DEFAULT_VIRTUAL_VERSION = literal_eval(config_data['virtualVersionNumber'])
        DEFAULT_UNLOCK_CODE = config_data['virtualUnlockCode']

    # Load system info file
    with open(join(__location__, 'rapid_system_info.yaml')) as yaml_file:
        system_info = load(yaml_file)
    # Maximum allowed rTMS frequency based on voltage and current power setting
    MAX_FREQUENCY = system_info['maxFrequency']
    # Minimum wait time (s) required for rTMS train. Power:Joules per pulse
    JOULES = system_info['joules']

    def getRapidMaxOnTime(power, frequency):
        """ Calculate maximum train duration for given power and frequency. If greater than 60 seconds, will allow for continuous operation for up to 6000 pulses."""
        return 63000.0 / (frequency * virtualHorizon.JOULES[power])

    def __init__(self,serialConnection, unlockCode=DEFAULT_UNLOCK_CODE, voltage=DEFAULT_VOLTAGE, version=DEFAULT_VIRTUAL_VERSION):
        super(virtualHorizon,self).__init__(serialConnection)
        self._unlockCode = unlockCode
        self._voltage = voltage
        self._version = version
        print('Version: ', self._version)
        self._secretUnlockCode = '1234-12345678-ý\x91'
        # If an unlock code has been supplied, then the Rapid requires a different command to stay in contact with it.
        if self._unlockCode:
            self._connectionCommandCharacter = 'x'
        else:
            self._connectionCommandCharacter = 'Q'

        self._rapidStatus = OrderedDict([('modifiedCoilAlgorithm', 0),
                                         ('thetaPSUDetected',      1),
                                         ('coilReady',             1),
                                         ('hvpsuConnected',        1),
                                         ('singlePulseMode',       1),
                                         ('wait',                  0),
                                         ('train',                 0),
                                         ('enhancedPowerMode',     0)])

        self._extendedStatus = {'LSB': OrderedDict([('plus1ModuleDetected',      0),
                                                    ('specialTriggerModeActive', 0),
                                                    ('chargeDelaySet',           0),
                                                    ('Unused3',                  0),
                                                    ('Unused4',                  0),
                                                    ('Unused5',                  0),
                                                    ('Unused6',                  0),
                                                    ('Unused7',                  0)]),
                                'MSB' :{'Unused' + str(x):0 for x in range(8,16)}}

        self._params = {'power'     : 30,
                        'frequency' : 0,
                        'nPulses'   : 1,
                        'duration'  : 0,
                        'wait'      : 1}

        self._chargeDelay = 0

    def _okToFire(self):
        return default_timer() > (self._lastFired + self._params['wait'])

    def _getParams(self):
        return str(self._params['power']).zfill(3) + str(self._params['frequency']).zfill(4) + str(self._params['nPulses']).zfill(4) + str(self._params['duration']).zfill(3) + str(self._params['wait']).zfill(3)

    def _getMaxFreq(self):
        return virtualHorizon.MAX_FREQUENCY[self._voltage][0][self._params['power']]

    def _processMessage(self,message):
        message = message.decode('latin_1')
        # Later versions of Magstim only respond to commands that don't require remote control when not under remote control
        if (message[0] not in {'Q', 'R', 'F', '\\'}) and not self._instrStatus['remoteStatus']:
            return None
        # Catch overloaded Magstim commands here
        if message[0] in {'Q', '@', 'J'}:
            parentParsedMessage = '?'
        # Otherwise, try and process message using parent function
        else:
            parentParsedMessage = super(virtualHorizon,self)._processMessage(message)
        # If parent returns ?, then it didn't understand the message - so try and parse it here
        if parentParsedMessage == '?':
            if message[0] in {'Q','\\','I','N','@','E','b','^','_','B','D','['} or (self._version > (9,0,0) and message[0] in {'x','o','n'}):
                # Get the instrument status prior to effecting changes (this is Magstim behaviour)
                messageData = self._parseStatus(self._instrStatus)
                # Overwrite enable remote control
                if message[0] == 'Q':
                    if self._version >= (9,0,0) and message[1:-1] != self._secretUnlockCode:
                        return None
                    else:
                        self._instrStatus['remoteStatus'] = 1
                        messageData = self._parseStatus(self._instrStatus)
                # Return Rapid parameters
                elif message[0] == '\\':
                    messageData += self._parseStatus(self._rapidStatus)
                    messageData += self._getParams()
                # Return Error Code (Not currently implemented - Not sure if this needs remote control or not)
                elif message[0] == 'I':
                    messageData = 'S'
                # All other commands require remote control to have been established
                elif self._instrStatus['remoteStatus']:
                    # Get device version (for some reason this needs remote control status)
                    if message[0] == 'N':
                        if message[1] == 'D':
                            messageData = ''.join([str(x) for x in self._version]) + '\x00'
                        else:
                            messageData = '?'
                    # Set power
                    elif message[0] == '@':
                        try:
                            newParameter = int(message[1:-1])
                        except ValueError:
                            messageData = '?'
                        else:
                            if 0 <= newParameter <= (110 if self._rapidStatus['enhancedPowerMode'] else 100):
                                self._params['power'] = newParameter
                            else:
                                messageData = 'S'
                    # Get system status
                    elif message[0] == 'x':
                        messageData += self._parseStatus(self._rapidStatus)
                        messageData += self._parseStatus(self._extendedStatus['MSB'])
                        messageData += self._parseStatus(self._extendedStatus['LSB'])
                    # Get charge delay
                    elif message[0] == 'o':
                        messageData += (self._chargeDelay).zfill(4 if self._version >= (10,0,0) else 3)
                    # Set charge delay
                    elif message[0] == 'n':
                        try:
                            newParameter = int(message[1:-1])
                        except ValueError:
                            messageData = '?'
                        else:
                            if 0 <= newParameter <= (10000 if self._version >= (10,0,0) else 2000):
                                self._chargeDelay = newParameter
                            else:
                                messageData = 'S'
                    # Ignoring coil safety switch, so just pass
                    elif message[0] == 'b':
                        pass
                    # Enable/Disable enhanced power mode
                    elif message[0] in {'^','_'}:
                        if self._instrStatus['standby']:
                            messageData += self._getRapidStatus 
                            self._params['enhancedPowerMode'] = 1 if message[0] == '^' else 0
                        else:
                            messageData = 'S'
                    # Toggle repetitive mode
                    elif message[0] == '[' and self._params['singlePulseMode']:
                        if int(message[1:-1]) == 1 and self._instrStatus['standby']:
                            self._params['singlePulseMode'] = 0
                            messageData += self._getRapidStatus
                        else:
                            messageData = 'S'
                    # Set rTMS parameters
                    elif message[0] in {'B','D','['} and not self._params['singlePulseMode']:
                        try:
                            newParameter = int(message[1:-1])
                        except ValueError:
                            messageData = '?'
                        else:
                            if message[0] == 'B':
                                if 0 < newParameter < self._getMaxFreq():
                                    messageData += self._getRapidStatus 
                                    self._params['frequency'] = newParameter
                                else:
                                    messageData = 'S'
                            elif message[0] == 'D':
                                if 1<= newParameter <= 6000:
                                    messageData += self._getRapidStatus 
                                    self._params['nPulses'] = newParameter
                                else:
                                    messageData = 'S'
                            elif message[0] == '[':
                                if 1 <= newParameter <= (9999 if self._version >= (9,0,0) else 999):
                                    messageData += self._getRapidStatus 
                                    self._params['duration'] = newParameter
                                elif newParameter == 0 and self._instrStatus['standby']:
                                    self._params['singlePulseMode'] = 1
                                    messageData += self._getRapidStatus
                                else:
                                    messageData = 'S'
                else:
                    messageData = 'S'
            else:
                return '?'
            # Only reset timer if a valid command is being returned
            if messageData not in {'?','S'} and (self._instrStatus['ready'] or self._instrStatus['armed']):
                if self._connectionTimer is not None:
                    self._connectionTimer.cancel()
                self._startTimer()
            returnMessage = bytearray(message[0] + messageData,'latin_1')
            return returnMessage + calcCRC(returnMessage)
        # Otherwise, it did understand the message (one way or another, so return)
        else:
            return parentParsedMessage