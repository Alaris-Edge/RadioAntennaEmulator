"""
main.py

Entry point: startup sequence, CLI command listener, voltage target control, and LED update loop.
"""

import _thread
import time

from config import *
from antenna_mode import update_shift_registers, read_sense, read_mode, set_fan_speed
from led_control import update_leds
from voltage_control import (
    read_voltage,
    shutdown_pico,
    set_wiper,
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
help_text = [
    "help: Show this help message.",
    "shutdown: Shutdown the Pico.",
    "setres <pot> <value>: Set wiper; pot 0=adjustable,1=fixed (or 'adjustable','fixed').",
    "setvolt <channel> <voltage>: Set voltage target; channel 'fixed' or 'adjustable'.",
    "readvolt [channel]: Read current and target voltage; optional channel.",
    "calibrate <channel>: Calibrate channel; 'fixed' or 'adjustable'.",
    "calibrate_all: Calibrate both channels.",
    "debugvolt [channel]: Show raw count, calibration, and voltage.",
    "debug: Toggle debug messages on/off.",
    "resetcal: Reset calibration to defaults and delete calibration file.",
]

# Voltage targets (initialized at startup)
target_voltages = {'fixed': 3.3, 'adjustable': 5.0}
# Track current wiper positions (0-255)
current_wipers = {'fixed': 127, 'adjustable': 127}

# Command implementations

def command_help():
    print("Available commands:")
    for line in help_text:
        print(f"  {line}")


def command_shutdown():
    shutdown_pico()


def command_setres(pot, value):
    try:
        key = pot.lower()
        if key in target_voltages:
            p = 1 if key == 'fixed' else 0
        else:
            p = int(pot)
            key = 'fixed' if p == 1 else 'adjustable'
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
        slope, intercept = get_calibration(ch)
        if slope is None or slope == 0:
            print(f"Error: invalid calibration slope={slope}")
            return
        raw_target = (target - (intercept or 0.0)) / slope
        # Map raw ADC count (0-65535) to wiper value (0-255)
        wiper_guess = int(max(0, min(255, raw_target * 255 / 65535)))
        p = 1 if ch == 'fixed' else 0
        set_wiper(p, wiper_guess)
        current_wipers[ch] = wiper_guess
        target_voltages[ch] = target
        print(f"{ch} target set to {target:.3f} V, initial wiper {wiper_guess}")
    except Exception as e:
        print(f"Error: {e}")


def command_readvolt(*args):
    try:
        keys = [args[0].lower()] if args else list(target_voltages.keys())
        for ch in keys:
            if ch in target_voltages:
                v = read_voltage(ch)
                tgt = target_voltages[ch]
                print(f"{ch} voltage: {v:.3f} V (target: {tgt:.2f} V)")
            else:
                print(f"Unknown channel '{ch}'")
    except Exception as e:
        print(f"Error: {e}")


def command_calibrate(channel):
    if channel.lower() not in target_voltages:
        print("Error: channel must be 'fixed' or 'adjustable'.")
        return
    pot = 0 if channel.lower() == 'adjustable' else 1
    calibrate_channel(channel, pot)


def command_calibrate_all():
    calibrate_all()


def command_debugvolt(*args):
    keys = [args[0].lower()] if args else list(target_voltages.keys())
    for ch in keys:
        if ch in target_voltages:
            raw = get_raw_count(ch)
            slope, intercept = get_calibration(ch)
            v = read_voltage(ch)
            print(f"{ch} raw_count={raw}, slope={slope:.9f}, intercept={intercept:.6f}, voltage={v:.3f} V")
        else:
            print(f"Unknown channel '{ch}'")


def command_debug():
    global debug_enabled
    debug_enabled = not debug_enabled
    print(f"Debug messages {'enabled' if debug_enabled else 'disabled'}.")


def command_resetcal():
    reset_calibration()
    print("Calibration reset to defaults.")


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


def command_listener():
    while True:
        inp = input("> ").strip().split()
        if not inp:
            continue
        cmd, *args = inp
        if cmd in commands:
            commands[cmd](*args)
        else:
            print(f"Unknown command '{cmd}'. Type 'help' for list.")


def startup():
    print("Starting system... Command listener started. Type 'help' for available commands.")
    # Welcome status
    fixed_v = read_voltage('fixed')
    adj_v = read_voltage('adjustable')
    print(f"Current voltages -> Fixed: {fixed_v:.2f} V, Adjustable: {adj_v:.2f} V")
    print(f"Target voltages  -> Fixed: {target_voltages['fixed']:.2f} V, Adjustable: {target_voltages['adjustable']:.2f} V")

if __name__ == '__main__':
    _register_commands()
    _thread.start_new_thread(command_listener, ())
    startup()
    while True:
        update_leds()
        for ch, tgt in target_voltages.items():
            if tgt is None:
                continue
            current = read_voltage(ch)
            if debug_enabled:
                print(f"[DEBUG] {ch}: current={current:.3f} V, target={tgt:.3f} V, wiper={current_wipers[ch]}")
            diff = current - tgt
            if abs(diff) >= 0.01:
                step = 1 if diff > 0 else -1
                new_w = max(0, min(255, current_wipers[ch] + step))
                if debug_enabled:
                    print(f"[DEBUG] {ch}: diff={diff:.3f}, step={step}, new_wiper={new_w}")
                if new_w != current_wipers[ch]:
                    set_wiper(1 if ch=='fixed' else 0, new_w)
                    current_wipers[ch] = new_w
        #time.sleep(0.1)
