from config import LED_OE, LED_SRCK, LED_RCK, LED_SRCLR, LED_SER_IN, leds, get_heat_map_color
from voltage_control import read_voltage
import time

def update_leds():
    '''Write current RGB bit patterns to the LED shift register, with LED0 as a heat-map.'''
    # Update LED0 color based on adjustable voltage
    adj_voltage = read_voltage('adjustable')
    leds[0] = list(get_heat_map_color(adj_voltage))

    # Begin shift register cycle
    LED_OE.value(0)       # Enable outputs
    LED_SRCLR.value(1)    # Normal operation (not clearing)
    LED_RCK.value(0)      # Prepare to latch new data

    # Shift out bits for all LEDs (each led is [R, G, B])
    for led in leds:
        for bit in led:
            LED_SER_IN.value(bit)
            LED_SRCK.value(1)
            time.sleep_us(100)
            LED_SRCK.value(0)
            time.sleep_us(100)

    # Latch shifted data to outputs
    LED_RCK.value(1)
    time.sleep_us(100)
    LED_RCK.value(0)
