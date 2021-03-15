Design
======================
The design of the external control of the horizon stimulator is shown in the figure below.

.. figure:: ../../horizonscheme.png
   :align: center


   *Figure: Horizon scheme*


The horizon box enables the communication between the control PC and the mainframe, therefore it is connected to the control PC via a FTDI chip,
that converts an USB signal (control pc) to a RS232 serial port (horizon box).
A switcher is used for toggling between manual (User Interface) and external mode.

The Quick-Fire Box contains an Arduino Nano with an AtMega328P chip and converts a USB command into a trigger at the BNC,
that leads in the Trig In of the “Horizon Trigger Box”. (https://github.com/neuromti/app-arduino)