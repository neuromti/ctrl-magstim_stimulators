Design
======================
The design of the external control of the horizon stimulator is shown in Figure 1 below.

.. figure:: ../../horizonscheme.png
   :align: center
   :width: 450


   *Figure 1: Horizon scheme*


The horizon box enables the communication between the control PC and the mainframe, therefore it is connected to the control PC via a FTDI chip,
that converts an USB signal (control pc) to a RS232 serial port (horizon box). (Figure 2)
A switcher is used for toggling between manual (User Interface) and external mode. (Figure 3)

The Quick-Fire Box contains an Arduino Nano with an AtMega328P chip and `converts a USB command into a trigger at the BNC <https://github.com/neuromti/app-arduino>`_,
that leads in the Trig In of the “Horizon Trigger Box”.

.. figure:: ../../wiring_horizonbox.jpg
   :align: center
   :width: 450


   *Figure 2: Wiring of the Horizon Box*



.. figure:: ../../wiring_switch.jpg
   :align: center
   :width: 400


   *Figure 3: Wiring of the switch; EC – external control, UI – User Interface*