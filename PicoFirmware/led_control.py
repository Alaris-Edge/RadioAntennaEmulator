"""
led_control.py

Controls the 4-status LEDs via a shift register:
 - LED0 displays a heat-map of the adjustable voltage rail.
 - LED1 displays the current antenna mode.
 - LED2 and LED3 support manual overrides with future placeholders for auto-update.

All four LEDs are written each cycle, respecting per-LED auto-update flags.
Debug logs occur only when the `debug` parameter is True, with detailed tracing.
"""
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
    """Map a voltage to one of 8 palette colors."""
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


def update_leds(filtered_voltages=None, antenna_mode=None, auto_update_led=None, debug=False):
    """
    Write current RGB bit patterns to the 4-LED shift register.

    Args:
        filtered_voltages (dict): Optional filtered voltages for heat-map.
        antenna_mode (int): Optional current mode for LED1.
        auto_update_led (dict): Flags for each LED index (0–3) to enable auto-update.
        debug (bool): If True, print debug logs.
    """
    # Prepare auto-update flags
    if auto_update_led is None:
        auto_update_led = {}

    # Determine adjustable voltage for LED0
    if filtered_voltages and 'adjustable' in filtered_voltages:
        adj_voltage = filtered_voltages['adjustable']
    else:
        from voltage_control import read_voltage
        adj_voltage = read_voltage('adjustable')

    # Determine antenna mode for LED1
    if antenna_mode is None:
        antenna_mode = read_mode()

    # LED0: heat-map
    if auto_update_led.get(0, True):
        leds[0] = list(get_heat_map_color(adj_voltage))

    # LED1: mode indicator
    try:
        mode_idx = int(antenna_mode)
    except:
        mode_idx = 0
    if mode_idx < 0 or mode_idx >= len(HEAT_PALETTE):
        mode_idx = 0
    if auto_update_led.get(1, True):
        leds[1] = list(HEAT_PALETTE[mode_idx])

    # LED2: placeholder for future automatic updates (manual overrides persist)
    if auto_update_led.get(2, True):
        pass  # TODO: add auto logic for LED2

    # LED3: placeholder for future automatic updates (manual overrides persist)
    if auto_update_led.get(3, True):
        pass  #: add auto logic for LED3 (IMPLEMENTED in MAIN, not here)

    # There is a layout error causing bits to be swapped. Let's fix this here
    leds_to_write = [[bit for bit in led] for led in leds] #Deep copy leds to not overwrite values
    # LED 1 RED swapped with LED 2 BLUE
    leds_to_write[1][0],leds_to_write[2][2] = leds_to_write[2][2],leds_to_write[1][0] 
    # LED 1 GREEN swapped with LED 2 GREEN
    leds_to_write[1][1],leds_to_write[2][1] = leds_to_write[2][1],leds_to_write[1][1] 

    # Debug logs
    if debug:
        print("DEBUG update_leds: leds=", leds)

    # Begin shift register write
    LED_OE.value(0)
    LED_SRCLR.value(1)
    LED_RCK.value(0)

    # Shift out bits: each LED is [R, G, B], send reversed (B, G, R)
    for led_idx, led in enumerate(leds_to_write):
        for bit_idx, bit in enumerate(reversed(led)):
            if debug:
                print(f"LED{led_idx} bit{bit_idx} -> {bit}")
            LED_SER_IN.value(bit)
            LED_SRCK.value(1)
            time.sleep_us(100)
            LED_SRCK.value(0)
            time.sleep_us(100)

    # Latch data
    LED_RCK.value(1)
    time.sleep_us(100)
    LED_RCK.value(0)
