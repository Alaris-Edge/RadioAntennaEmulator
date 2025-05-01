#from machine import Pin, PWM, ADC, I2C, SoftSPI
#import config
import _thread

from config import *
from antenna_mode import *
from led_control import *
from voltage_control import *
from i2c import *
# --- Functions ---
    
def command_listener():
    """Background thread to listen for commands."""
    while True:
        cmd = input("Enter command: ").strip().lower()
        if cmd == "shutdown":
            shutdown_pico()
            break
        elif cmd.startswith("setres"):
            # Expected command format: setres <channel> <value>
            try:
                parts = cmd.split()
                if len(parts) == 3:
                    channel = parts[1]
                    res_value = int(parts[2])
                    if channel == "adjustable":
                        channel_value = 0
                    if channel == "fixed":
                        channel_value = 1
                    set_wiper(channel_value, res_value)
                else:
                    print("Usage: setres <channel> <position> (channel: adjustable or fixed, value: 0-255)")
            except Exception as e:
                print("Error parsing command:", e)
        elif cmd.startswith("readvolt"):
            # Expected command format: readvolt <fixed|adjustable>
            parts = cmd.split()
            if len(parts) == 2:
                read_voltage(parts[1])
            else:
                print("Usage: readvolt <fixed|adjustable>")
        elif cmd.startswith("readmode"):
            read_mode()
        elif cmd.startswith("antenna"):
            read_sense()
        elif cmd.startswith("setfan"):
            # Expected command format: setfan <percentage>
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    speed = int(parts[1])
                    set_fan_speed(speed)
                except Exception as e:
                    print("Invalid speed value:", e)
        elif cmd.startswith("write"):
            parts = cmd.split()
            if parts == 51:
                update_shift_registers([
                    parts[1],  parts[2],  parts[3],  parts[4],  parts[5],  parts[6],  parts[7],  parts[8],  parts[9],  parts[10],
                    parts[11], parts[12], parts[13], parts[14], parts[15], parts[16], parts[17], parts[18], parts[19], parts[20],
                    parts[21], parts[22], parts[23], parts[24], parts[25], parts[26], parts[27], parts[28], parts[29], parts[30],
                    parts[31], parts[32], parts[32], parts[34], parts[35], parts[36], parts[37], parts[38], parts[39], parts[40],
                    parts[41], parts[42], parts[43], parts[44], parts[45], parts[46], parts[47], parts[48]])
        elif cmd.startswith("read"):
            print("Previous shift register: " + str(read_data))
        else:
            print("Unknown command '{}'. Try 'shutdown', 'setres <channel> <value>', or 'readvolt <fixed|adjustable>'.".format(cmd))

def startup():
    """
    Startup routine:
    - Turn all LEDs on (white).
    - Read both analog voltage levels.
    - Convert ADC readings to the real voltage (ADC reading * (3.3/65535) * 5).
    - Print the voltages.
    - Turn all LEDs off.
    - Set the first LED to a color corresponding to the adjustable voltage level:
         RED for 3.3V, GREEN for 5V, BLUE for 8V, WHITE for 9V.
    """
    for i in range(len(leds)):
        leds[i] = [1, 1, 1]
    update_leds()
    time.sleep(1)
    fixed_voltage = read_voltage("fixed")
    adjustable_voltage = read_voltage("adjustable")
    
    # DM Chip Select pin
    cs.value(1)

    for i in range(len(leds)):
        leds[i] = [0, 0, 0]
    update_leds()
    time.sleep(0.5)
    color_options = [
        ([1, 0, 0], 3.3),  # Red
        ([0, 1, 0], 5.0),  # Green
        ([0, 0, 1], 8.0),  # Blue
        ([1, 1, 1], 9.0)   # White
    ]
    closest_color = min(color_options, key=lambda x: abs(adjustable_voltage - x[1]))[0]
    leds[0] = closest_color
    update_leds()

# --- Main Execution ---

startup()
_thread.start_new_thread(command_listener, ())

# Example usage: Update the 50-pin connector's shift register using a test pattern.
pattern = [i % 2 for i in range(48)]
update_shift_registers(pattern)

while True:
    time.sleep(1)


