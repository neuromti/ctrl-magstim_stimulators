# -*- coding: utf-8 -*-
"""Converts a simple USB ! to a trigger out at the BNC 
Robert Guggenberger
"""
import serial
from serial.tools.list_ports import comports
import weakref
import struct
import json
from time import sleep
# %%
def available(port: str=None):
        availablePorts = [port for port in comports()]
        availablePorts = [a.device for a in comports() if 
                          a.vid == 6790 and a.pid == 29987] 
        
        if len(availablePorts) == 0:
            raise ConnectionError("No device connected at any port")

        if port is None:            
            return availablePorts

        if port.upper() in availablePorts:
            return [port]
        else:
            raise ConnectionError("No device connected at " + port)


# %%
class Base():
#    instance = [None]
#
#    def __new__(cls, **kwargs):
#        new_instance = None
#        if not cls.instance[0] is None:            
#            new_instance =  cls.instance[0]()         
#        if new_instance is not None:
#            print(f'Reusing old arduino instance {cls.instance[0]()}')
#            return new_instance
#            
#        print('Creating new arduino instance')
#        return object.__new__(cls)
#    
    def __init__(self,
                 port=None,
                 baud=115200,
                 timeout=None,
                 version:str = None,
                 ):
        print("Connecting arduino")
        if version:
            version_found = False
            for self.port in available(port):
                self.baud = baud
                self.timeout = timeout
                self.interface = serial.Serial(port=self.port,
                                               baudrate=self.baud,
                                               timeout=self.timeout)
                self.interface.open()
                sleep(2)
                connected_version = self.enquire()[0]['version']
                if version == connected_version:
                    version_found = True
                    break
            if not(version_found):
                raise ConnectionError("There was no arduino of the given version found. Please check the connection!")
        else:
            self.port = available(port)[0]
            self.baud = baud
            self.timeout = timeout
            self.interface = serial.Serial(port=self.port,
                                           baudrate=self.baud,
                                           timeout=self.timeout)
            sleep(5)

#        self.instance[0] = weakref.ref(self)

    def write(self, message: bytes):
        for l in serial.iterbytes(message):
            self.interface.write(l)
        self.interface.flush()

    def enquire(self, verbose=False):
        msg = self.encode(b'\x05')
        responses = self.query(msg)
        if verbose:
            for s in responses:
                print(s)
        return responses

    @staticmethod
    def encode(command=b"?", parameter=0, terminator=b"\n"):
        stream = b''.join((command,
                           struct.pack('<H', parameter),
                           terminator))
        return stream

    def receive(self, blocking=False):
        buffer = b''
        while buffer[-2:] != b'\r\n':
            message = self.interface.read_all()
            buffer += message
            if buffer == b'':
                if blocking:
                    sleep(0.1)
                else:
                    return None
        lines = buffer.splitlines()
        dicts = []
        for l in lines:
            try:
                decoded = l.decode().replace("'", '"')
                d = json.loads(decoded)
                dicts.append(d)
            except json.JSONDecodeError as e:
                print(decoded)
                raise e
        return dicts

    def query(self, msg: bytes):
        self.write(msg)
        return self.receive(True)
    def acknowledge(self, state=1):
        msg = self.encode(b'\x06', state)
        self.write(msg)

class Mock():

    def __init__(self,
                 port=None,
                 baud=115200,
                 ):        
        self.port = port
        self.baud = baud     
        self.message = b'-\n'
        
    def write(self, message: bytes):
        print(f'Mocking {message}')
        self.message = message

    def receive(self):
        return self.message
    
    @staticmethod
    def encode(command=b"?", parameter=0, terminator=b"\n"):
        stream = b''.join((command,
                           struct.pack('<H', parameter),
                           terminator))
        return stream
    

# %%
#if __name__ == '__main__':
    
#    a = Arduino()
