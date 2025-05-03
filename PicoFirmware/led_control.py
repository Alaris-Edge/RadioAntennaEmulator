import time
from config import LED_OE, LED_SRCK, LED_RCK, LED_SRCLR, LED_SER_IN, leds
from antenna_mode import read_mode

# Heat map parameters for adjustable rail

HEAT_PALETTE = [
    (0, 0, 0),  # OFF
    (0, 0, 1),  # Blue
    (0, 1, 1),  # Cyan
    (0, 1, 0),  # Green
    (1, 1, 0),  # Yellow
    (1, 0, 0),  # Red
    (1, 0, 1),  # Magenta
    (1, 1, 1),  # White
]

def get_heat_map_color(voltage):
    if voltage < 3.2: idx = 0
    elif voltage < 3.5: idx = 1
    elif voltage < 4.5: idx = 2
    elif voltage < 6.5: idx = 3
    elif voltage < 6.5: idx = 4
    elif voltage < 7.5: idx = 5
    elif voltage < 8.5: idx = 6
    elif voltage < 9.5: idx = 7

    return HEAT_PALETTE[idx]

# Updated to accept filtered_voltages from main loop

def update_leds(filtered_voltages=None,antenna_mode=None):
    '''Write current RGB bit patterns to the LED shift register, with LED0 as a heat-map.'''
    # Determine adjustable voltage for LED0: use filtered if available
    if filtered_voltages is not None and 'adjustable' in filtered_voltages:
        adj_voltage = filtered_voltages['adjustable']
    else:
        # Fallback to raw read
        from voltage_control import read_voltage
        adj_voltage = read_voltage('adjustable')

    # Determine antenna mode for LED1
    if antenna_mode is None:
        # Fallback to raw read
        antenna_mode = read_mode()

    # Update LED0 color based on adjustable voltage
    leds[0] = list(get_heat_map_color(adj_voltage))

    # Update LED1 color based on antenna mode
    leds[1] = list(HEAT_PALETTE[int(antenna_mode)])

    # Begin shift register cycle
    LED_OE.value(0)       # Enable outputs
    LED_SRCLR.value(1)    # Normal operation (not clearing)
    LED_RCK.value(0)      # Prepare to latch new data

    # Shift out bits for all LEDs: reverse bit order within each LED [R, G, B]
    for led in leds:
        for bit in reversed(led):
            LED_SER_IN.value(bit)
            LED_SRCK.value(1)
            time.sleep_us(100)
            LED_SRCK.value(0)
            time.sleep_us(100)

    # Latch shifted data to outputs
    LED_RCK.value(1)
    time.sleep_us(100)
    LED_RCK.value(0)
