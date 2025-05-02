"""
led_control.py

Controls status LEDs via shift register, mapping adjustable voltage to LED0 color.
"""

import time
from config import (
    LED_OE,
    LED_SRCK,
    LED_RCK,
    LED_SRCLR,
    LED_SER_IN,
    leds,
    adjustable_led_color_options
)
from voltage_control import read_voltage


def update_leds():
    """
    Read adjustable rail voltage, update LED0 color, and shift out all LED bits.
    """
    # Read calibrated adjustable voltage
    adjustable_v = read_voltage('adjustable')

    # Determine color for LED0 based on thresholds
    chosen_color = adjustable_led_color_options[-1][0]
    for color, threshold in adjustable_led_color_options:
        if adjustable_v <= threshold:
            chosen_color = color
            break
    # Update LED0 RGB state
    leds[0] = chosen_color

    # Prepare bit sequence [R,G,B] for each LED in order
    bit_sequence = []
    for (r, g, b) in leds:
        bit_sequence.extend([r, g, b])

    # Begin shifting: clear shift register if needed (optional)
    LED_SRCLR.value(1)  # ensure not clearing
    LED_RCK.value(0)    # prepare to latch new data

    # Shift out each bit (MSB first in sequence)
    for bit in bit_sequence:
        LED_SER_IN.value(bit)
        # Pulse shift clock
        LED_SRCK.value(1)
        time.sleep_us(1)
        LED_SRCK.value(0)
        time.sleep_us(1)

    # Latch shifted data to outputs
    LED_RCK.value(1)
    time.sleep_us(1)
    LED_RCK.value(0)

    # Ensure outputs enabled
    LED_OE.value(0)
