"""
main.py

Entry point: startup sequence, CLI command listener, LED update loop, and voltage control delegation.
"""

import _thread
import time

from config import *
from antenna_mode import update_shift_registers
from led_control import update_leds
from voltage_control import (
    read_voltage,
    shutdown_pico,
    set_wiper,
    set_voltage_target,
    voltage_control_step,
    calibrate_channel,
    calibrate_all,
    get_raw_count,
    get_calibration,
    reset_calibration,
)

# Command registry and debug flag
commands = {}
debug_enabled = False

# Help text for CLI (grouped for readability)
help_text = """
General:
  help             Show this help message
  shutdown         Shutdown the Pico

Potentiometer:
  setres <pot> <value>  Set wiper; pot 0=adjustable,1=fixed (or 'adjustable','fixed')

Voltage Control:
  setvolt <ch> <V>      Set voltage target; ch='fixed' or 'adjustable'
  readvolt [ch]         Read current and target voltage; optional channel

Calibration:
  calibrate <ch>        Calibrate channel; 'fixed' or 'adjustable'
  calibrate_all         Calibrate both channels
  resetcal              Reset calibration to defaults and delete file

Debug:
  debugvolt [ch]        Show raw count, calibration, and voltage
  debug                 Toggle debug messages on/off

CPLD Interface:
  cpld_write <data>     Write 48-bit pattern to the CPLD interface (hex or binary)
"""

# Voltage targets and wiper tracking
# Initialize from config defaults
target_voltages = DEFAULT_TARGET_VOLTAGES.copy()
current_wipers = {'fixed': 255, 'adjustable': 255}

# Filter settings for voltage readings
filtered_voltages = {ch: 0.0 for ch in target_voltages}

# Auto-control flags (reset on restart)
auto_control = {ch: True for ch in target_voltages}

# Calibration lock flag: when True, main loop skips control updates
calibrating = False

# --- Command Handlers ---

def command_help():
    print(help_text.strip('\n'))


def command_shutdown():
    shutdown_pico()


def command_setres(pot, value):
    try:
        key = pot.lower()
        if key in ('fixed', 'adjustable'):
            p = 1 if key == 'fixed' else 0
        else:
            p = int(pot)
            key = 'fixed' if p == 1 else 'adjustable'
        # Disable automatic control for manual pot adjustment
        auto_control[key] = False
        # Sleep for 50ms to let the pending SPI writes settle and ensure all threads depending on auto_control get the update
        time.sleep_ms(50)
        v = int(value)
        set_wiper(p, v)
        current_wipers[key] = v
        print(f"Pot {p} ({key}) set to {v}")
    except Exception as e:
        print(f"Error: {e}")


def command_setvolt(channel, voltage):
    try:
        ch = channel.lower()
        if ch not in target_voltages:
            print("Error: channel must be 'fixed' or 'adjustable'.")
            return
        target = float(voltage)
        set_voltage_target(ch, target, filtered_voltages, target_voltages)
        # Re-enable automatic control for this channel
        auto_control[ch] = True
        print(f"{ch} target set to {target:.3f} V")
    except Exception as e:
        print(f"Error: {e}")


def command_readvolt(*args):
    try:
        keys = [args[0].lower()] if args else list(target_voltages.keys())
        for ch in keys:
            if ch not in target_voltages:
                print(f"Unknown channel '{ch}'")
                continue
            v = read_voltage(ch)
            tgt = target_voltages[ch]
            print(f"{ch} voltage: {v:.3f} V (target: {tgt:.2f} V)")
    except Exception as e:
        print(f"Error: {e}")


def command_calibrate(channel):
    global calibrating
    ch = channel.lower()
    if ch not in target_voltages:
        print("Error: channel must be 'fixed' or 'adjustable'.")
        return
    pot = 0 if ch == 'adjustable' else 1
    calibrating = True
    try:
        calibrate_channel(ch, pot)
    finally:
        calibrating = False


def command_calibrate_all():
    global calibrating
    calibrating = True
    try:
        calibrate_all()
    finally:
        calibrating = False


def command_debugvolt(*args):
    keys = [args[0].lower()] if args else list(target_voltages.keys())
    for ch in keys:
        if ch not in target_voltages:
            print(f"Unknown channel '{ch}'")
            continue
        raw = get_raw_count(ch)
        slope, intercept = get_calibration(ch)
        v = read_voltage(ch)
        print(f"{ch} raw_count={raw}, slope={slope:.9f}, intercept={intercept:.6f}, voltage={v:.3f} V")


def command_debug():
    global debug_enabled
    debug_enabled = not debug_enabled
    print(f"Debug messages {'enabled' if debug_enabled else 'disabled'}.")


def command_resetcal():
    reset_calibration()
    print("Calibration reset to defaults.")


def command_cpld_write(data):
    try:
        bits = update_shift_registers(data)
        print("CPLD interface updated. Read-back bits:", ''.join(str(b) for b in bits))
    except Exception as e:
        print(f"Error: {e}")

# --- Command Registration ---

def _register_commands():
    commands['help'] = command_help
    commands['shutdown'] = command_shutdown
    commands['setres'] = command_setres
    commands['setvolt'] = command_setvolt
    commands['readvolt'] = command_readvolt
    commands['calibrate'] = command_calibrate
    commands['calibrate_all'] = command_calibrate_all
    commands['debugvolt'] = command_debugvolt
    commands['debug'] = command_debug
    commands['resetcal'] = command_resetcal
    commands['cpld_write'] = command_cpld_write

# --- CLI Listener ---

def command_listener():
    while True:
        try:
            inp = input("> ").strip().split()
        except (EOFError, KeyboardInterrupt):
            print("Exiting command listener.")
            break
        if not inp:
            continue
        cmd, *args = inp
        if cmd in commands:
            try:
                commands[cmd](*args)
            except TypeError as te:
                print(f"Invalid arguments for '{cmd}': {te}")
            except Exception as e:
                print(f"Error executing '{cmd}': {e}")
        else:
            print(f"Unknown command '{cmd}'. Type 'help'.")

# --- Startup ---

def startup():
    print("System started. Type 'help' to see available commands.")
    filtered_voltages['fixed'] = read_voltage('fixed')
    filtered_voltages['adjustable'] = read_voltage('adjustable')
    set_wiper(0, current_wipers['adjustable'])
    set_wiper(1, current_wipers['fixed'])

# --- Periodic Tasks ---

def led_loop():
    """Call update_leds at 4 Hz."""
    while True:
        try:
            update_leds(filtered_voltages)
        except Exception as e:
            print(f"LED task error: {e}")
        time.sleep(0.25)


def voltage_loop():
    """Call voltage_control_step at ~100 Hz."""
    while True:
        try:
            voltage_control_step(filtered_voltages, target_voltages, current_wipers, debug_enabled, calibrating, auto_control)
        except Exception as e:
            print(f"Voltage task error: {e}")
        time.sleep(0)
        time.sleep(0.01)


if __name__ == '__main__':
    _register_commands()
    # Start CLI listener
    _thread.start_new_thread(command_listener, ())
    # Start periodic tasks
    _thread.start_new_thread(led_loop, ())
    _thread.start_new_thread(voltage_loop, ())
    # Initialization
    startup()
    # Keep the main thread alive
    while True:
        time.sleep(1)
