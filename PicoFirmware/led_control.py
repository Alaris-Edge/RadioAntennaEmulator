import time
from config import LED_OE, LED_SRCK, LED_RCK, LED_SRCLR, LED_SER_IN, leds

# Heat map parameters for adjustable rail
MIN_VOLTAGE = 3.3
MAX_VOLTAGE = 9.0
HEAT_PALETTE = [
    (0, 0, 1),  # Blue
    (0, 1, 1),  # Cyan
    (0, 1, 0),  # Green
    (1, 1, 0),  # Yellow
    (1, 0, 0),  # Red
    (1, 0, 1),  # Magenta
    (1, 1, 1),  # White
]

def get_heat_map_color(voltage):
    norm = (voltage - MIN_VOLTAGE) / (MAX_VOLTAGE - MIN_VOLTAGE)
    #print(norm)
    if norm <= 0:
        return HEAT_PALETTE[0]
    if norm >= 1:
        return HEAT_PALETTE[-1]
    idx = round(norm * len(HEAT_PALETTE))
    #print(idx)
    if idx >= len(HEAT_PALETTE):
        idx = len(HEAT_PALETTE) - 1
    return HEAT_PALETTE[idx]

# Updated to accept filtered_voltages from main loop

def update_leds(filtered_voltages=None):
    '''Write current RGB bit patterns to the LED shift register, with LED0 as a heat-map.'''
    # Determine adjustable voltage for LED0: use filtered if available
    if filtered_voltages is not None and 'adjustable' in filtered_voltages:
        adj_voltage = filtered_voltages['adjustable']
    else:
        # Fallback to raw read
        from voltage_control import read_voltage
        adj_voltage = read_voltage('adjustable')

    # Update LED0 color based on adjustable voltage
    leds[0] = list(get_heat_map_color(adj_voltage))

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
