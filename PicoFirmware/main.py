import _thread
import time

from config import *            # must define: leds (list), cs (Pin), shutdown_pico()
from antenna_mode import *      # read_sense()
from led_control import *       # update_leds(), set_wiper()
from voltage_control import *   # read_voltage(), read_mode()
from i2c import *               # update_shift_registers()

# ——— GLOBALS ———
pattern = []   # holds last 48-bit shift-register state

# ——— COMMAND LISTENER THREAD ———
def command_listener():
    """Background thread to listen for commands."""
    global pattern

    while True:
        cmd = input("Enter command: ").strip().lower()

        if cmd == "shutdown":
            shutdown_pico()
            break

        elif cmd.startswith("setres"):
            parts = cmd.split()
            if len(parts) == 3:
                channel, pos = parts[1], parts[2]
                try:
                    pos = int(pos)
                    if channel == "adjustable":
                        ch = 0
                    elif channel == "fixed":
                        ch = 1
                    else:
                        print("Unknown channel; use 'adjustable' or 'fixed'")
                        continue
                    set_wiper(ch, pos)
                except ValueError:
                    print("Position must be an integer 0–255")
            else:
                print("Usage: setres <channel> <position>")

        elif cmd.startswith("readvolt"):
            parts = cmd.split()
            if len(parts) == 2 and parts[1] in ("fixed", "adjustable"):
                read_voltage(parts[1])
            else:
                print("Usage: readvolt <fixed|adjustable>")

        elif cmd == "readmode":
            read_mode()

        elif cmd == "antenna":
            read_sense()

        elif cmd.startswith("setfan"):
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    speed = int(parts[1])
                    set_fan_speed(speed)
                except ValueError:
                    print("Speed must be an integer percentage")
            else:
                print("Usage: setfan <percentage>")

        elif cmd.startswith("write"):
            parts = cmd.split()
            # expect: "write b1 b2 ... b48" → 49 total parts
            if len(parts) == 49:
                try:
                    bits = [int(b) for b in parts[1:]]
                    if all(b in (0,1) for b in bits):
                        update_shift_registers(bits)
                        pattern = bits[:]   # save for read
                    else:
                        print("All bits must be 0 or 1")
                except ValueError:
                    print("All bits must be integers 0 or 1")
            else:
                print("Usage: write <48 bits separated by spaces>")

        elif cmd == "read":
            print("Previous shift register:", pattern)

        else:
            print(f"Unknown command '{cmd}'. Valid: shutdown, setres, readvolt, readmode, antenna, setfan, write, read.")

# ——— STARTUP ROUTINE ———
def startup():
    # 1) Turn all LEDs white, pause
    for i in range(len(leds)):
        leds[i] = [1, 1, 1]
    update_leds()
    time.sleep(1)

    # 2) Read voltages
    fixed_v      = read_voltage("fixed")
    adjustable_v = read_voltage("adjustable")

    # 3) Release chip-select
    cs.value(1)

    # 4) Turn LEDs off briefly
    for i in range(len(leds)):
        leds[i] = [0, 0, 0]
    update_leds()
    time.sleep(0.5)

    # 5) Map adjustable voltage (3–9 V) to 7 “rainbow” steps and set LED0
    color_options = [
        ([1, 0, 0], 3.0),  # red
        ([1, 1, 0], 4.0),  # yellow
        ([0, 1, 0], 5.0),  # green
        ([0, 1, 1], 6.0),  # cyan
        ([0, 0, 1], 7.0),  # blue
        ([1, 0, 1], 8.0),  # magenta
        ([1, 1, 1], 9.0)   # white
    ]
    closest_bits = min(color_options, key=lambda item: abs(adjustable_v - item[1]))[0]

    # 6) Write the 3-bit pattern into LED0 and update
    leds[0] = closest_bits
    update_leds()

# ——— MAIN ———
startup()
_thread.start_new_thread(command_listener, ())

# initialize shift-register with a test pattern
pattern = [i % 2 for i in range(48)]
update_shift_registers(pattern)

# keep the main thread alive
while True:
    update_leds()
    #time.sleep(1)
    #print(adjustable_v)