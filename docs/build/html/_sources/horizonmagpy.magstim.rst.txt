.. _linkmagstim:

Magstim (Parent class)
===========================

The Magstim class serves as parent class for all Magstim stimulator types.

In addition, there are two further classes, that have not been documented at this point. First, the "serialPortController(Process)", communicating with the serial port via two queues, one for writing and one for reading.
Second,the "connectionRobot(Process) that sends an 'enable remote control' command to the Magstim via the serialPortController process every 500ms in order to maintain the contact to the stimulator.
Further documentation is available in the `wiki of the original toolbox <https://github.com/nicolasmcnair/magpy/wiki>`_.

.. autoclass:: horizonmagpy.magstim.Magstim
   :members:
   :undoc-members:
   :show-inheritance: