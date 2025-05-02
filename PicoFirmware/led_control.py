from config import *
from voltage_control import *

def update_leds():
    """Update the LED shift register with the current values from the 'leds' array."""
    LED_OE.value(0)
    LED_RCK.value(0)
    for led in leds:
        for bit in led:
            LED_SER_IN.value(bit)
            LED_SRCK.value(1)
            time.sleep_us(100)
            LED_SRCK.value(0)
            time.sleep_us(100)
    LED_RCK.value(1)
    time.sleep_us(100)
    LED_RCK.value(0)

    fixed_v = read_voltage("adjustable")
    adjustable_v = read_voltage("adjustable")
    closest_bits = min(adjustable_led_color_options, key=lambda item: abs(adjustable_v - item[1]))[0]# 6) Write the 3-bit pattern into LED0 and update
    leds[0] = closest_bits