"""
main.py

Entry point: startup sequence, CLI command listener, and main LED update loop.
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

commands = {}
help_text = [
    "help: Show this help message.",
    "shutdown: Shutdown the Pico.",
    "setres <pot> <value>: Set wiper; pot 0=adjustable,1=fixed or names 'adjustable','fixed'.",
    "readvolt [channel]: Read voltage; channel 'fixed' or 'adjustable'. If no channel, shows both.",
    "calibrate <channel>: Calibrate channel; 'fixed' or 'adjustable'.",
    "calibrate_all: Calibrate both channels.",
    "debugvolt [channel]: Show raw ADC count, calibration, and computed voltage.",
    "resetcal: Reset calibration to defaults and delete calibration file.",
]

def command_help():
    print("Available commands:")
    for line in help_text:
        print(f"  {line}")


def command_shutdown():
    shutdown_pico()


def command_setres(pot, value):
    try:
        if pot.lower() in ('fixed', 'adjustable'):
            p = 1 if pot.lower() == 'fixed' else 0
        else:
            p = int(pot)
        v = int(value)
        set_wiper(p, v)
        name = 'fixed' if p == 1 else 'adjustable'
        print(f"Pot {p} ({name}) set to {v}")
    except Exception as e:
        print(f"Error: {e}")


def command_readvolt(*args):
    try:
        if not args:
            for ch in ('fixed', 'adjustable'):
                v = read_voltage(ch)
                print(f"{ch} voltage: {v:.3f} V")
        else:
            ch = args[0]
            v = read_voltage(ch)
            print(f"{ch} voltage: {v:.3f} V")
    except Exception as e:
        print(f"Error: {e}")


def command_calibrate(channel):
    if channel not in ('fixed', 'adjustable'):
        print("Error: channel must be 'fixed' or 'adjustable'")
        return
    pot = 0 if channel == 'adjustable' else 1
    calibrate_channel(channel, pot)


def command_calibrate_all():
    calibrate_all()


def command_debugvolt(*args):
    targets = args if args else ('fixed', 'adjustable')
    for ch in targets:
        try:
            raw = get_raw_count(ch)
            slope, intercept = get_calibration(ch)
            v = read_voltage(ch)
            print(f"{ch} raw_count={raw}, slope={slope:.9f}, intercept={intercept:.6f}, voltage={v:.3f} V")
        except Exception as e:
            print(f"Error ({ch}): {e}")


def command_resetcal():
    reset_calibration()
    print("Calibration reset to defaults.")


def _register_commands():
    commands['help'] = command_help
    commands['shutdown'] = command_shutdown
    commands['setres'] = command_setres
    commands['readvolt'] = command_readvolt
    commands['calibrate'] = command_calibrate
    commands['calibrate_all'] = command_calibrate_all
    commands['debugvolt'] = command_debugvolt
    commands['resetcal'] = command_resetcal


def command_listener():
    while True:
        try:
            inp = input("> ").strip().split()
            if not inp:
                continue
            cmd, *args = inp
            if cmd in commands:
                commands[cmd](*args)
            else:
                print(f"Unknown command '{cmd}'. Type 'help' for list.")
        except Exception as e:
            print(f"Error: {e}")


def startup():
    print("Starting system... Command listener started. Type 'help' for available commands.")
    fixed_v = read_voltage('fixed')
    adj_v = read_voltage('adjustable')
    print(f"Initial voltages - Fixed: {fixed_v:.2f} V, Adjustable: {adj_v:.2f} V")

if __name__ == '__main__':
    _register_commands()
    _thread.start_new_thread(command_listener, ())
    startup()
    while True:
        update_leds()
        time.sleep(1)
