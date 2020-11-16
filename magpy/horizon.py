# -*- coding: utf-8 -*-
"""
Created on Mon Nov 16 13:31:07 2020

@author: roboTMS

Design Horizon Box:

    I/O:
    DB25(Stimulator - via DB26-Adapter)
    DB25(Magstim UserInterface-UI with Horizon Trigger Box between)
    RS232 (Control PC - via FTDI RS232-USB Converter)
    
    Manual Mode:
        1 -  1: Tout+
        3 -  3: Tin+
        5 -  5: UI_Stop
        6 -  6: Triggate
        8 -  8: UI_Rx
        9 -  9: UI_Tx
        10- 10: GND
        11- 11: GND
        12- 12: supply voltage
        13- 13: supply voltage
        
    Remote Control: 
        FTDI/RXD(yellow) - 8 (UI_Rx)
        FTDI/TXD(orange) - 9 (UI_Tx)
        FTDI/GND(black)  - 10+11 (GND)
        
    Switch (ON-OFF-ON)
        ON-RemoteControl: connected RXD-8 and TXD-9, disconnected 5-5(UI_Stop) and 12-12/13-13 (supply voltage)
        OFF: disconnected RXD-8 and TXD-9 and 5-5(UI_Stop) and 12-12/13-13 (supply voltage)
        ON-Manual Mode: connected 5-5(UI_Stop) and 12-12/13-13 (supply voltage), disconnected RXD-8 and TXD-9
        N.B. The disconnections are necessary because it´s set up to have a single master slave relationship
            
    DB25 (Horizon Box) to DB26(Stimulator)-Adapter Pinout:
        1 -  10b
        3 -  10a
        5 -  7a
        6 -  7b
        8 -  9a
        9 -  8b
        10- 13a+b
        11- 1a+b
        12- 2a+b
        13- 2a+b
    
Design QuickFireBox:
    
    USB-BNC Interface: contains an Arduino Nano with AtMega328P (Old Bootloader)
    - --> 10/11 (GND)
    + --> 3 (Tin+/TTL)
    BNC connected to Trig IN of Horizon Trigger Box (between Horizon Box and Magstim-UserInterface)
    
    More Information: https://github.com/translationalneurosurgery/app-arduino
"""


from __future__ import division
from magstim import Magstim, serialPortController, MagstimError, connectionRobot
import serial
from sys import version_info, platform
from os.path import realpath, join, dirname
from os import getcwd
from math import floor
from time import sleep
from multiprocessing import Queue, Process
from functools import partial
from yaml import load
from ast import literal_eval
from base import Base


class QuickFireBox(Base):
    """For Triggering with low latency a second box is used."""
          
    def trigger(self, duration_in_us=1000):
        """Trigger the BNC default for 1ms.
        
        Parameters
        ----------
        duration_in_us : int
            trigger duration in microseconds
        """
        msg = self.encode(b'\x21', max(0, min((duration_in_us, 10000))))
        self.write(msg)

class Horizon(Magstim):
    
    # Load settings file (resort to default values if not found)
    __location__ = realpath(join(getcwd(), dirname(__file__)))
    try:
        with open(join(__location__, 'rapid_config.yaml')) as yaml_file:
            config_data = load(yaml_file)
    except:
        DEFAULT_VOLTAGE = 240
        DEFAULT_UNLOCK_CODE = ''
        ENFORCE_ENERGY_SAFETY = True
        DEFAULT_VIRTUAL_VERSION = (9,0,0)
    else:
        DEFAULT_VOLTAGE = config_data['defaultVoltage']
        DEFAULT_UNLOCK_CODE = config_data['unlockCode']
        ENFORCE_ENERGY_SAFETY = config_data['enforceEnergySafety']
        DEFAULT_VIRTUAL_VERSION = literal_eval(config_data['virtualVersionNumber'])

    # Load system info file
    with open(join(__location__, 'rapid_system_info.yaml')) as yaml_file:
        system_info = load(yaml_file)
    # Maximum allowed rTMS frequency based on voltage and current power setting
    MAX_FREQUENCY = system_info['maxFrequency']
    # Minimum wait time (s) required for rTMS train. Power:Joules per pulse
    JOULES = system_info['joules']

    def getMinWaitTime(power, nPulses, frequency):
        """Calculate minimum wait time between trains.
        
        N.B. The absolute minimum wait time ist 0.5 seconds.
 
        Parameters
        ----------
        power : int
            Current power in settings.
        nPulses : int
            Number of pulses per train.
        frequency : int
            Stimulation frequency.

        Returns
        -------
        int
            The minimum wait time between trains for given power, frequency, and number of pulses.

        """ 
        return max(0.5, (nPulses * ((frequency * Horizon.JOULES[power]) - 1050.0)) / (1050.0 * frequency))

    def getMaxOnTime(power, frequency):
        """Calculate maximum train duration per minute for given power and frequency.
        
        To ensure that the System must not be made to dissipate more than 63000 Joules per minute.
        If greater than 60 seconds, will allow for continuous operation for up to 6000 pulses.

        Parameters
        ----------
        power : int
            Current power in settings.
        frequency : int
            stimulation frequency.

        Returns
        -------
        int
           Maximum On Time.

        """
        return 63000.0 / (frequency * Horizon.JOULES[power])

    def getMaxContinuousOperationFrequency(power):
        """Calculate Maximal continuous operation frequency.

        Parameters
        ----------
        power : int
            Current power in settings.

        Returns
        -------
        int
            Maximum continuous operation frequency
            that will allow for continuous operation (up to 6000 pulses).   

        """
        return 1050.0 / Horizon.JOULES[power]

    def __init__(self, serialConnection, unlockCode=DEFAULT_UNLOCK_CODE, voltage=DEFAULT_VOLTAGE, version=DEFAULT_VIRTUAL_VERSION):
        self._unlockCode = unlockCode
        self.connectiontype = serialConnection
        self._voltage = voltage
        self._version = version if serialConnection.lower() == 'virtual' else (0,0,0)
        # If an unlock code has been supplied, then the Horizon requires a different command to stay in contact with it.
        if self._unlockCode:
            self._connectionCommand = (b'x@G', None, 6)
            self._queryCommand = self.getSystemStatus
        self._parameterReturnBytes = None
        self._sequenceValidated = False
        self._repetitiveMode = False

    def _setupSerialPort(self, serialConnection):
        if serialConnection.lower() == 'virtual':
            from _virtual import virtualPortController
            self._connection = virtualPortController(self.__class__.__name__,self._sendQueue,self._receiveQueue,unlockCode=self._unlockCode,voltage=self._voltage,version=self._version)
        else:
            self._connection = serialPortController(serialConnection, self._sendQueue, self._receiveQueue)

    def getVersion(self):
        """Get Magstim software version number.
        
        This is needed when obtaining parameters from the Magstim.
        
        Returns
        -------
        tuple int
            Error code (0 = no error; 1+ = error).
        tuple ?
            If error is 0 (False) returns a tuple containing the version number (in (Major,Minor,Patch) format),
            otherwise returns an error string
        """
        error, message = self._processCommand(b'ND', 'version', None)
        #If we didn't receive an error, update the version number and the number of bytes that will be returned by a getParameters() command
        if not error:
            self._version = message
            if self._version >= (9,):
                self._parameterReturnBytes = 24
            elif self._version >= (7,):
                self._parameterReturnBytes = 22
            else:
                self._parameterReturnBytes = 21
        return (error,message)

    def getErrorCode(self):
        """Get current error code from Horizon.

        See the Operating Manual for how to interpret these error codes.
        
        Returns
        -------
        tuple int
            Error code (0 = no error; 1+ = error).
        tuple dict,str
            If error is 0 (False) returns a dict containing Horizon instrument status ['instr']
            and current error code ['errorCode'] dicts, otherwise returns an error string
        """
        return self._processCommand(b'I@', 'error', 6)

    def connect(self, receipt=False):
        """Connect to the Rapid.
        
        This starts the serial port controller,
        as well as a process that constantly keeps in contact with the Horizon so as not to lose control.
        It also collects the software version number of the Horizon
        in order to send the correct command for obtaining parameter settings.

        Parameters
        ----------
        receipt : boolean, optional
            Whether to return occurrence of an error and the automated response from the Horizon unit.
            The default is False.

        Raises
        ------
        MagstimError
            Either if no remote control could be established or if the Version couldn´t be determined.

        """
        super(Horizon,self).connect()
        # We have to be able to determine the software version of the Horizon, otherwise we won't be able to communicate properly
        error, message = self.getVersion()
        if error:
            self.disconnect()
            raise MagstimError('Could not determine software version of Horizon. Disconnecting.')

    def disconnect(self):
        """ 
        Disconnect from the Magstim.
        
        This stops maintaining contact with the Magstim and turns the serial port controller off.
        """ 
        #Just some housekeeping before we call the base magstim class method disconnect
        self._sequenceValidated = False
        self._repetitiveMode = False
        return super(Horizon, self).disconnect()

    def rTMSMode(self, enable, receipt=False):
        """Helper function to enable/disable rTMS mode.

        Parameters
        ----------
        enable : boolean
            Whether to enable (True) or disable (False) control.
        receipt : boolean, optional
            Whether to return occurrence of an error and
            the automated response from the Horizon unit.
            The default is False.
            
        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Horizon instrument status ['instr']
                and rMTS setting ['rapid'] dicts,
                otherwise returns an error string
            If receipt argument is True.
        None
            If receipt argument is False. 
        """
        self._sequenceValidated =  False
        # Get current parameters
        updateError,currentParameters = self.getParameters()
        if updateError:
            return Magstim.PARAMETER_ACQUISTION_ERR
        else:
            # See if Horizon already in rTMS mode (if enabling) or already in single-pulse mode (if disabling)
            if (not currentParameters['rapid']['singlePulseMode'] and enable) or (currentParameters['rapid']['singlePulseMode'] and not enable):
                del currentParameters['rapidParam']
                return (0,currentParameters) if receipt else None
            # Durations of 1 or 0 are used to toggle repetitive mode on and off
            if self._version >= (9,):
                commandString = b'[0010' if enable else b'[0000'
            else:
                commandString = b'[010' if enable else b'[000'
            error,message = self._processCommand(commandString, 'instrRapid', 4)
            if not error:
                if enable:
                    self._repetitiveMode = True
                    updateError,currentParameters = self.getParameters()
                    if not updateError:
                        if currentParameters['rapidParam']['frequency'] == 0:
                            updateError,currentParameters = self._processCommand(b'B0010', 'instrRapid', 4)
                            if updateError:
                                return Magstim.PARAMETER_UPDATE_ERR
                    else:
                        return Magstim.PARAMETER_ACQUISTION_ERR
                else:
                    self._repetitiveMode = False
        
        return (error,message) if receipt else None

    def ignoreCoilSafetySwitch(self, receipt=False):
        """Allow the stimulator to ignore the state of coil safety interlock switch.
        
        Parameters
        ----------
        receipt : boolean, optional
            Whether to return occurrence of an error and
            the automated response from the Horizon unit.
            The default is False.

        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Horizon instrument status ['instr'] dict,
                otherwise returns an error string
            If receiptType argument is True.
        None
            If receipt argument is False.

        """
        return self._processCommand(b'b@', 'instr' if receipt else None, 3)

    def remoteControl(self, enable, receipt=False):
        """Enable/Disable remote control of stimulator.
        
        Disabling remote control will first disarm the Magstim unit.

        Parameters
        ----------
        enable : boolean
            Whether to enable (True) or disable (False) control.
        receipt : boolean, optional
            Whether to return occurrence of an error and
            the automated response from the Horizon unit.
            The default is False.

        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Horizon instrument status ['instr'] dict,
                otherwise returns an error string
            If receiptType argument is True.
        None
            If receipt argument is False.

        """
        self._sequenceValidated = False
        if self._unlockCode:
            return self._processCommand(b'Q' + bytearray(self._unlockCode,encoding='latin_1') if enable else b'R@', 'instr' if receipt else None, 3)
        else:
            return self._processCommand(b'Q@' if enable else b'R@', 'instr' if receipt else None, 3)
    
    
    def setFrequency(self, newFrequency, receipt=False):
        """Set frequency of rTMS pulse train.
        
        Changing the Frequency will automatically update the NPulses parameter
        based on the current Duration parameter setting.
        The maximum frequency allowed depends on the current power level
        and the regional power settings (i.e., 115V vs. 240V)
        
        Parameters
        ----------
        newFrequency : int/float
            Stimulation Frequency of pulse train in Hz
            (0-100 for 240V systems, 0-60 for 115V systems);
            decimal values are allowed for frequencies up to 30Hz
        receipt : boolean, optional
            Whether to return occurrence of an error and
            the automated response from the Horizon unit.
            The default is False.

        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Horizon instrument status ['instr'] and rMTS setting ['rapid'] dicts,
                otherwise returns an error string
            If receiptType argument is True.
        None
            If receipt argument is False.

        """
        self._sequenceValidated =  False

        # Convert to tenths of a Hz
        newFrequency = newFrequency * 10
        # Make sure we have a valid frequency value
        if newFrequency % 1:
            return Magstim.PARAMETER_PRECISION_ERR
        updateError,currentParameters = self.getParameters()
        if updateError:
            return Magstim.PARAMETER_ACQUISTION_ERR
        else:
            maxFrequency = Horizon.MAX_FREQUENCY[self._voltage][self._super][currentParameters['rapidParam']['power']] * 10
            if not (0 <= newFrequency <= maxFrequency):
                return Magstim.PARAMETER_RANGE_ERR

        #Send command
        error, message = self._processCommand(b'B' + bytearray(str(int(newFrequency)).zfill(4),encoding='ascii'), 'instrRapid', 4) 
        #If we didn't get an error, update the other parameters accordingly
        if not error:
            updateError,currentParameters = self.getParameters()
            if not updateError:
                updateError,currentParameters = self._processCommand(b'D' + bytearray(str(int(currentParameters['rapidParam']['duration'] * currentParameters['rapidParam']['frequency'])).zfill(5 if self._version >= (9,) else 4),encoding='ascii'), 'instrRapid', 4)
                if updateError:
                    return Magstim.PARAMETER_UPDATE_ERR
            else:
                return Magstim.PARAMETER_ACQUISTION_ERR

        return (error, message) if receipt else None
    
    def setNPulses(self, newNPulses, receipt=False):
        """Set number of pulses in rTMS pulse train.
        
        N.B. Changing the NPulses parameter will automatically update the Duration parameter.
        (this cannot exceed 10 s) based on the current Frequency parameter setting.
        
        Parameters
        ----------
        newNPulses : int
            New number of pulses in each train can be set beween 1 and 6000 in steps of 1.
        receipt : boolean, optional
            Whether to return occurrence of an error and
            the automated response from the Horizon unit.
            The default is False.

        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Horizon instrument status ['instr'] and rMTS setting ['rapid'] dicts,
                otherwise returns an error string
            If receiptType argument is True.
        None
            If receipt argument is False

        """
        self._sequenceValidated =  False

        # Make sure we have a valid number of pulses value
        if newNPulses % 1:
            return Magstim.PARAMETER_FLOAT_ERR
        if not (0 <= newNPulses <= 6000):
            return Magstim.PARAMETER_RANGE_ERR

        #Send command
        error, message = self._processCommand(b'D' + bytearray(str(int(newNPulses)).zfill(5 if self._version >= (9,) else 4),encoding='ascii'), 'instrRapid', 4)
        #If we didn't get an error, update the other parameters accordingly
        if not error:
            updateError, currentParameters = self.getParameters()
            if not updateError:
                updateError, currentParameters = self._processCommand(b'[' + bytearray(str(int(currentParameters['rapidParam']['nPulses'] / currentParameters['rapidParam']['frequency'])).zfill(4 if self._version >= (9,) else 3),encoding='ascii'), 'instrRapid' if receipt else None, 4)
                if updateError:
                    return Magstim.PARAMETER_UPDATE_ERR
            else:
                return Magstim.PARAMETER_ACQUISTION_ERR

        return (error, message) if receipt else None
    
    def setDuration(self, newDuration, receipt=False):
        """Set duration of rTMS pulse train.
        
        N.B. Changing the Duration parameter will automatically update the NPulses parameter
        based on the current Frequency parameter setting.
        
        Parameters
        ----------
        newDuration : int/float
            The duration of each ‘train’(set) of pulses can be set from 0.1s (seconds) up
            to a maximum of 600s - in 0.1s increments up to 30s and in 1.0s increments thereafter.
        receipt : boolean, optional
            Whether to return occurrence of an error and
            the automated response from the Horizon unit.
            The default is False.

        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Horizon instrument status ['instr'] and rMTS setting ['rapid'] dicts,
                otherwise returns an error string
            If receiptType argument is True.
        None
            If receipt argument is False

        """
        self._sequenceValidated =  False

        # Convert to tenths of a second
        newDuration = newDuration * 10
        # Make sure we have a valid duration value
        if newDuration % 1:
            return Magstim.PARAMETER_PRECISION_ERR
        elif not (0 <= newDuration <= (999 if self._version < (9,) else 9999)):
            return Magstim.PARAMETER_RANGE_ERR

        error, message = self._processCommand(b'[' + bytearray(str(int(newDuration)).zfill(4 if self._version >= (9,) else 3),encoding='ascii'), 'instrRapid', 4)
        if not error:
            updateError, currentParameters = self.getParameters()
            if not updateError:
                updateError, currentParameters = self._processCommand(b'D' + bytearray(str(int(currentParameters['rapidParam']['duration'] * currentParameters['rapidParam']['frequency'])).zfill(5 if self._version >= (9,) else 4),encoding='ascii'), 'instrRapid', 4)
                if updateError:
                    return Magstim.PARAMETER_UPDATE_ERR
            else:
                return Magstim.PARAMETER_ACQUISTION_ERR

        return (error, message) if receipt else None
    
    def getParameters(self):
        """Request current parameter settings from the Horizon.

        Returns
        -------
        Tuple:
            error: int
                error code (0 = no eRapidrror; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Horizon instrument status ['instr'],
                rMTS setting ['rapid'], and parameter setting ['rapidParam'] dicts
                otherwise returns an error string
            If receiptType argument is True.
        None
            If receipt argument is False

        """
        return self._processCommand(b'\\@', 'rapidParam', self._parameterReturnBytes)
    
    def setPower(self, newPower, receipt=False, delay=False):
        """Set power level for the .
        
        N.B. Allow 100 ms per unit drop in power, or 10 ms per unit increase in power.
        Changing the power level can result in automatic updating of the Frequency parameter
        (if in rTMS mode)
        

        Parameters
        ----------
        newPower : int
            New power level (0-100; or 0-110 if enhanced-power mode is enabled)
        receipt : boolean, optional
            Whether to return occurrence of an error and
            the automated response from the Horizon unit.
            The default is False.
        delay : boolean, optional
            Enforce delay to allow Horizon time to change Power.
            The default is False.

        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Magstim instrument status ['instr']
                otherwise returns an error string
            If receiptType argument is True.
        None
            If receipt argument is False

        """
        self._sequenceValidated =  False

        # Check current enhanced power status
        if self.isEnhanced():
            maxPower = 110
        else:
            maxPower = 100

        # Make sure we have a valid power value
        if newPower % 1:
            return Magstim.PARAMETER_FLOAT_ERR
        elif not 0 <= newPower <= maxPower:
            return Magstim.PARAMETER_RANGE_ERR
        
        error, message = super(Horizon,self).setPower(newPower,True,delay,b'@')
        if not error:
            updateError, currentParameters = self.getParameters()
            if not updateError:
                if not currentParameters['rapid']['singlePulseMode']:
                    maxFrequency = Horizon.MAX_FREQUENCY[self._voltage][self._super][currentParameters['rapidParam']['power']]
                    if currentParameters['rapidParam']['frequency'] > maxFrequency:
                        if not self.setFrequency(maxFrequency)[0]:
                            return Magstim.PARAMETER_UPDATE_ERR
            else:
                return Magstim.PARAMETER_ACQUISTION_ERR
        
        return (error,message) if receipt else None


    def fire(self, receipt=False):
        """Fire the stimulator.
        
        This checks whether rTMS mode is active,
        and if so whether the sequence has been validated
        and the min wait time between trains has elapsed.
        
        N.B. Will only succeed if previously armed.
        

        Parameters
        ----------
        receipt : boolean, optional
            Whether to return occurrence of an error and
            the automated response from the Horizon unit.
            The default is False.

        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Magstim instrument status ['instr']
                otherwise returns an error string
            If receiptType argument is True.
        None
            If receipt argument is False

        """
        if self._repetitiveMode and Horizon.ENFORCE_ENERGY_SAFETY and not self._sequenceValidated:
            return Magstim.SEQUENCE_VALIDATION_ERR
        else:
            return super(Horizon,self).fire(receipt)

    def quickFire(self):
        """Trigger the stimulator to fire with very low latency.
        
        N.B. The signal will be sent via the QuickFire-Box.
        
        Parameters
        ----------
        duration : int
            Trigger duration in microseconds.
            
        """
        if self._repetitiveMode and Horizon().ENFORCE_ENERGY_SAFETY and not self._sequenceValidated:
            return Magstim.SEQUENCE_VALIDATION_ERR
        else:
            super(Horizon,self).quickFire()

    def validateSequence(self):
        """Validate the energy consumption for the current rTMS parameters for the Horizon.
        
        This must be performed before running any new sequence,
        otherwise calling fire() will return an error.
        
        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns current parameters,
                otherwise returns an error string
            If receiptType argument is True.

        """
        self._sequenceValidated = False
        error,parameters = self.getParameters()
        if error:
            return Magstim.PARAMETER_ACQUISTION_ERR
        elif min(parameters['rapidParam']['duration'], 60) > Horizon.getMaxOnTime(parameters['rapidParam']['power'], parameters['rapidParam']['frequency']):
            return Magstim.MAX_ON_TIME_ERR
        else:
            self._sequenceValidated = True
            return (0, parameters)

    def getSystemStatus(self):
        """Get system status from the Horizon.

        Returns
        -------
        Tuple:
            error: int
                error code (0 = no error; 1+ = error)
            message: dict,str
                if error is 0 (False) returns a dict
                containing Horizon instrument status ['instr'],rMTS setting ['rapid']
                and extended instrument status ['extInstr'] dicts,
                otherwise returns an error string
            If receiptType argument is True.

        """
        if self._version is None:
            return Magstim.GET_SYSTEM_STATUS_ERR
        elif self._version >= (9,):
            return self._processCommand(b'x@', 'systemRapid', 6)
        else:
            return Magstim.SYSTEM_STATUS_VERSION_ERR
