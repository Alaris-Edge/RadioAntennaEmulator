from config import *


def shutdown_pico():
    print("Shutdown in 1000 ms – say goodbye to your Pico!")
    fan_pwm.duty_u16(0)
    time.sleep_ms(1000)
    kill_pin.value(1)

    
def read_voltage(channel):
    """
    Reads the voltage from the specified channel and returns the computed voltage.
    channel: 'fixed' for the fixed 3.3V rail measurement,
             'adjustable' for the adjustable measurement.
    """
    #print('HERE')
    if channel == "fixed":
        val = fixed_measure.read_u16()
        voltage = (val / 65535) * 3.3 * 3.7 # Adjust value for accurate voltage read
        #print("Fixed voltage: {:.2f} V".format(voltage))
        return voltage
    elif channel == "adjustable":
        val = adjustable_measure.read_u16()
        voltage = (val / 65535) * 3.3 * 3.7 # Adjust value for accurate voltage read
        #print("Adjustable voltage: {:.2f} V".format(voltage))
        return voltage
    else:
        print("Invalid channel. Use 'fixed' or 'adjustable'.")
        return None
