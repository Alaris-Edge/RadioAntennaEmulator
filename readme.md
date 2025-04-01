# Pi Pico Radio Emulator Control Documentation

This document will outline how to interact with the Pi Pico to control its core functions.

## Voltage output control and setting
### Setting Output through resistance control
Setting the resistance
``setres <potentiometer_channel> <potentiometer_position>``

for adjustable line ``potentiometer_channel == "adjustable"``
for 3.3V line ``potentiometer_channel == "fixed"``

 ``0 => potentiometer_position > 256``

To set the second channel of the digital potentiometer to its lowest value:
``setres fixed 255``

**Note** that when first powered the digital potentiometer will default to its middle position, **127** or a resistance of **5k** Ohm.

### Reading the output
Reading the output voltage
``readvolt <voltage_channel>``

for adjustable line ``voltage_channel== "adjustable"``
for 3.3V line ``voltage_channel== "fixed"``

To read the fixed channel voltage level: ``readvolt fixed``

This will return ``<voltage_channel> "Voltage: " <voltage> " V"`` (e.g. ``Fixed voltage: 3.23 V``)

**Note** that the voltage traces are read indirectly through a 25k-5k resistor. The value read is multiplied by **5** to obtain the input level, this multiplier may need initial calibration for accurate readings.

## Antenna sense read
 Reading the antenna pin value
 ``antenna``

This will return a value in the range 0 to 65535

A response may will look like ``"Antenna: " <value>`` (e.g. ``Antenna: 65020``)

## Read FM Mode

Reading the current mode
``readmode``

This will return 4 binary values for each of the FM pins to be read.

A response will look like ``Current Mode: 0010``

## Kill Power
The ``shutdown`` command will kill the power about 1000 milliseconds after it is received.

It will respond: ``Shutdown in 1000ms – say goodbye to your Pico!``

## Fan Control
**This feature should not be needed and has not been tested**
To set the fan speed ``setfan <duty_cycle>`` (e.g. ``setfan 55``)

This fan will be off when below 20% duty cycle. The fan will be on between 20% and 100% duty cycle.

When the command is received, the fan speed will be set and there is a message to say that it has been set.

When the Pi Pico is shutdown the PWM will be disabled.

## Startup
On start up the Pi Pico will perform the following in order:

- Turn all LEDs on (white)
- Read both analogue voltage levels and send over serial
- Turn all LEDs off
- Set the first LED to a color corresponding to the adjustable voltage level:
         RED for 3.3V, GREEN for 5V, BLUE for 8V, WHITE for 9V.

After the startup has finished it will wait for a command sent over serial.




