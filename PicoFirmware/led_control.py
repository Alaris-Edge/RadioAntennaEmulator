import time
from config import LED_OE, LED_SRCK, LED_RCK, LED_SRCLR, LED_SER_IN, leds
from antenna_mode import read_mode

# Heat map parameters for adjustable rail
# Index 0 = OFF, 1–7 correspond to increasing voltage levels
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
    """
    Map a voltage reading to a color in the heat palette.

    Returns a tuple (R, G, B) from HEAT_PALETTE.
    """
    if voltage < 3.2:
        idx = 0
    elif voltage < 3.5:
        idx = 1
    elif voltage < 4.5:
        idx = 2
    elif voltage < 5.5:
        idx = 3
    elif voltage < 6.5:
        idx = 4
    elif voltage < 7.5:
        idx = 5
    elif voltage < 8.5:
        idx = 6
    else:
        idx = 7
    return HEAT_PALETTE[idx]


def update_leds(filtered_voltages=None, antenna_mode=None):
    """
    Write current RGB bit patterns to the LED shift register.
    LED0 shows a heat-map of the adjustable voltage rail.
    LED1 shows the current antenna mode.

    Args:
      filtered_voltages: dict with 'fixed' and 'adjustable' float readings.
      antenna_mode: optional integer mode; if None, read raw.
    """
    # Determine adjustable voltage for LED0
    if filtered_voltages is not None and 'adjustable' in filtered_voltages:
        adj_voltage = filtered_voltages['adjustable']
    else:
        from voltage_control import read_voltage
        adj_voltage = read_voltage('adjustable')

    # Determine antenna mode for LED1
    if antenna_mode is None:
        antenna_mode = read_mode()

    # Update LED0 (heat-map)
    leds[0] = list(get_heat_map_color(adj_voltage))

    # Update LED1 (antenna mode)
    try:
        mode_idx = int(antenna_mode)
    except Exception:
        mode_idx = 0
    if mode_idx < 0 or mode_idx >= len(HEAT_PALETTE):
        mode_idx = 0
    leds[1] = list(HEAT_PALETTE[mode_idx])

    # Begin shift register cycle
    LED_OE.value(0)       # Enable outputs (active LOW)
    LED_SRCLR.value(1)    # Normal operation (not clearing)
    LED_RCK.value(0)      # Prepare to latch new data

    # Shift out bits for all LEDs: reverse bit order within each [R, G, B]
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
