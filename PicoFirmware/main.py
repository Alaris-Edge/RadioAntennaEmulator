"""
main.py

Entry point: startup sequence, CLI command listener, scheduled LED and voltage control loops,
manual and automatic control for potentiometers and LEDs, and onboard LED toggle.
"""

import _thread
import time
from machine import Pin

from config import *
from antenna_mode import update_shift_registers, read_mode
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

# Help text for CLI
help_text = """
General:
  help                     Show this help message
     Example: help
  shutdown                 Shutdown the Pico (LED, voltage, CPLD states remain as-is after power-down)
     Example: shutdown

Voltage Control and Potentiometer:
  setres <pot> <value>     Set wiper; pot 0=adjustable,1=fixed
     Examples: setres adjustable 128, setres 1 200
  setvolt <ch> <V>         Set voltage target; ch='fixed' or 'adjustable'
     Example: setvolt fixed 3.3
  readvolt [ch]            Read current and target voltage; optional channel
     Examples: readvolt, readvolt adjustable

Calibration:
  calibrate <ch>           Calibrate channel; 'fixed', 'adjustable', or 'all' calibrate both
     Example: calibrate fixed
  calibrate_all            Calibrate both channels
     Example: calibrate_all
  resetcal                 Reset calibration to defaults
     Example: resetcal

Debug:
  debugvolt [ch]           Show raw count, calibration, and voltage
     Example: debugvolt adjustable
  debug                    Toggle debug messages on/off
     Example: debug

CPLD Interface:
  cpld_write <data>        Write 48-bit pattern to the CPLD interface
     Examples: cpld_write 0x123456789ABC, cpld_write 101010... (48 bits)

LED Control:
  setled <idx> <rgb>       Set LED idx (0-3) with contiguous RGB bits
     Example: setled 2 010
  setled <idx> auto        Re-enable automatic update for LED idx
     Example: setled 2 auto
"""

# Voltage targets and wiper tracking
target_voltages = DEFAULT_TARGET_VOLTAGES.copy()
current_wipers = {'fixed': 255, 'adjustable': 255}

# Filtered voltage readings
filtered_voltages = {ch: 0.0 for ch in target_voltages}

# Calibration lock flag
calibrating = False

# Auto-control flags for voltage channels and LEDs
auto_control = {ch: True for ch in target_voltages}
auto_update_led = {i: True for i in range(4)}

# --- Command Handlers ---

def command_help():
    print(help_text.lstrip("\n"))


def command_shutdown():
    leds[3] = [1, 0, 0]
    update_leds(filtered_voltages, mode, auto_update_led, debug = debug_enabled)
    shutdown_pico()


def command_setres(pot, value):
    try:
        key = pot.lower()
        if key in ('fixed', 'adjustable'):
            p = 1 if key == 'fixed' else 0
        else:
            p = int(pot)
            key = 'fixed' if p == 1 else 'adjustable'
        v = int(value)
        set_wiper(p, v)
        current_wipers[key] = v
        auto_control[key] = False
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
    if ch is 'all':
        command_calibrate_all()
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


def command_setled(idx, *args):
    try:
        i = int(idx)
        if i not in auto_update_led:
            print("Error: LED index must be 0-3.")
            return
        # Re-enable auto-update
        if len(args) == 1 and args[0].lower() == 'auto':
            auto_update_led[i] = True
            print(f"LED {i} auto-update re-enabled.")
            return
        # Contiguous RGB bits input
        if len(args) == 1 and len(args[0]) == 3 and all(c in '01' for c in args[0]):
            r, g, b = (int(c) for c in args[0])
            leds[i] = [r, g, b]
            auto_update_led[i] = False
            print(f"LED {i} manually set to [{r}, {g}, {b}].")
            return
        # Separate RGB inputs
        if len(args) == 3:
            r, g, b = map(int, args)
            for bit in (r, g, b):
                if bit not in (0, 1):
                    raise ValueError
            leds[i] = [r, g, b]
            auto_update_led[i] = False
            print(f"LED {i} manually set to [{r}, {g}, {b}].")
            return
        print("Usage: setled <idx> <rgb> or setled <idx> auto")
    except ValueError:
        print("Error: r, g, b must be 0 or 1.")
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
    commands['setled'] = command_setled

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

# --- Thread Setup & Startup ---

if __name__ == '__main__':
    _register_commands()
    # Start CLI on core1
    _thread.start_new_thread(command_listener, ())
    # Initialize system
    print("System started. Type 'help' to see available commands.")
    filtered_voltages['fixed'] = read_voltage('fixed')
    filtered_voltages['adjustable'] = read_voltage('adjustable')
    set_wiper(0, current_wipers['adjustable'])
    set_wiper(1, current_wipers['fixed'])

    # Scheduled loops on core0
    LED_INTERVAL_MS = 250
    VOLT_INTERVAL_MS = 10
    TOGGLE_INTERVAL_MS = 1000
    last_led = time.ticks_ms()
    last_volt = time.ticks_ms()
    last_toggle = time.ticks_ms()

    while True:
        now = time.ticks_ms()
        
        # Onboard LED toggle every second
        if time.ticks_diff(now, last_toggle) >= TOGGLE_INTERVAL_MS and auto_update_led[3]:
            if calibrating: # Flash blue LED when calibrating
                # onboard_led.value(not onboard_led.value())
                # Onboard LED not working, let's use one of the other ones
                leds[3] = [0, 0, not(leds[3][2])]
            else: # Flash green LED when not calibrating
                # onboard_led.value(not onboard_led.value())
                # Onboard LED not working, let's use one of the other ones
                leds[3] = [0, not(leds[3][1]), 0]
            last_toggle = now


        # LED update at 4 Hz
        if time.ticks_diff(now, last_led) >= LED_INTERVAL_MS:
            try:
                if debug_enabled:
                    print("DEBUG: Reading antenna mode.")
                mode = read_mode()
                if debug_enabled:
                    print("DEBUG: Updating LEDs.")
                update_leds(filtered_voltages, mode, auto_update_led, debug = debug_enabled)
            except Exception as e:
                print(f"Error in LED loop: {e}")
            last_led = now

        # Voltage control at ~100 Hz
        # This block runs most often. I have moved it here so as not to bblock the slower periodic functions
        if time.ticks_diff(now, last_volt) >= VOLT_INTERVAL_MS:
            try:
                voltage_control_step(filtered_voltages, target_voltages, current_wipers, debug_enabled, calibrating, auto_control)
            except Exception as e:
                print(f"Error in voltage loop: {e}")
            last_volt = now

        # Yield to other tasks
        time.sleep(0)
